import assert from 'node:assert/strict';
import { test } from 'node:test';

// The whole Gateway page drawn in a small browser: elements, the page's fixed parts, and frames and
// a clock that only the test moves. It shows how the page answers the tray, not how it looks.
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
delete globalThis.navigator;
let now = 0;
let frames = [];
Object.defineProperty(globalThis, 'performance', { value: { now: () => now, mark() {}, measure() {}, getEntriesByName: () => [] }, configurable: true, writable: true });
globalThis.requestAnimationFrame = (fn) => frames.push(fn);
// Every motion runs to its end.
const settle = () => { while (frames.length) { now += 10000; const run = frames; frames = []; for (const fn of run) fn(now); } };
globalThis.ResizeObserver = class { observe() {} disconnect() {} };
globalThis.MutationObserver = class { observe() {} };
globalThis.innerWidth = 1440;
globalThis.getComputedStyle = (node) => (node.classList?.contains('leaving') ? { strokeDasharray: '4 4', strokeOpacity: '0.4' } : { strokeDasharray: 'none', strokeOpacity: '1', paddingLeft: '0', paddingRight: '0' });

const walk = (root) => root.children.flatMap((n) => [n, ...walk(n)]);
function detach(node) {
  const parent = node.parentNode;
  if (!parent) return;
  parent.children.splice(parent.children.indexOf(node), 1);
  node.parentNode = null;
}
function element(tagName) {
  let names = [];
  const attributes = new Map();
  const style = { setProperty(name, value) { style[name] = value; }, removeProperty(name) { delete style[name]; } };
  const node = {
    tagName, style, dataset: {}, children: [], parentNode: null, textContent: '', listeners: {}, animations: [],
    get className() { return names.join(' '); },
    set className(value) { names = String(value).split(' ').filter(Boolean); },
    classList: {
      add: (...add) => { for (const name of add) if (!names.includes(name)) names.push(name); },
      remove: (...gone) => { names = names.filter((name) => !gone.includes(name)); },
      toggle: (name, force = !names.includes(name)) => { node.classList[force ? 'add' : 'remove'](name); return force; },
      contains: (name) => names.includes(name),
    },
    get isConnected() { let at = node; while (at.parentNode) at = at.parentNode; return Boolean(at.root); },
    setAttribute(name, value) { if (name === 'class') node.className = value; else attributes.set(name, String(value)); },
    getAttribute: (name) => (name === 'class' ? node.className : attributes.has(name) ? attributes.get(name) : null),
    removeAttribute(name) { attributes.delete(name); },
    get firstElementChild() { return node.children[0] || null; },
    get lastElementChild() { return node.children.at(-1) || null; },
    append(...nodes) { for (const n of nodes) node.insertBefore(typeof n === 'string' ? element('#text') : n, null); },
    prepend(...nodes) { const first = node.children[0] || null; for (const n of nodes) node.insertBefore(n, first); },
    insertBefore(n, ref) {
      detach(n);
      node.children.splice(ref ? node.children.indexOf(ref) : node.children.length, 0, n);
      n.parentNode = node;
      return n;
    },
    remove() { detach(node); },
    replaceChildren(...nodes) { for (const n of [...node.children]) detach(n); node.append(...nodes); },
    contains(other) { for (let at = other; at; at = at.parentNode) if (at === node) return true; return false; },
    focus() { globalThis.document.activeElement = node; },
    matches: () => false,
    querySelector: () => null,
    querySelectorAll: (selector) => (selector === '[data-focus]' ? walk(node).filter((n) => n.dataset.focus) : []),
    addEventListener(type, fn) { (node.listeners[type] ||= []).push(fn); },
    animate(keyframes, options) {
      const animation = { keyframes, options, cancelled: false, finished: Promise.resolve(), cancel() { animation.cancelled = true; } };
      node.animations.push(animation);
      return animation;
    },
    getAnimations: () => node.animations.filter((a) => !a.cancelled),
  };
  return node;
}
const pages = {};
for (const id of ['#main', '#drawer', '#scrim', '.shell', '#dock']) {
  pages[id] = element('DIV');
  pages[id].root = true;
}
globalThis.document = {
  hidden: false, activeElement: null, body: element('BODY'),
  createElement: (tag) => element(tag.toUpperCase()), createElementNS: (namespace, tag) => element(tag),
  querySelector: (selector) => pages[selector] ?? null, querySelectorAll: () => [], getElementById: () => null,
  addEventListener() {}, removeEventListener() {},
  documentElement: { classList: { add() {}, remove() {} }, style: { setProperty() {}, removeProperty() {} } },
};

// A stand-in server for the tray, as in gateway.test.mjs.
const replies = new Map();
globalThis.fetch = (url, init = {}) => {
  const body = init.body ? JSON.parse(init.body) : null;
  const waiting = replies.get(url) || [];
  const next = waiting.length ? waiting.shift() : { status: 200, json: {} };
  const reply = typeof next === 'function' ? next(body) : next;
  return Promise.resolve(reply).then((made) => ({ ok: made.status < 400, status: made.status, json: async () => made.json }));
};
const queue = (url, ...items) => replies.set(url, [...(replies.get(url) || []), ...items]);
const PREVIEW = '/api/batch/preview';
const batch = (id) => (sent) => ({
  status: 200,
  json: {
    id, action: 'batch', state: 'previewed', error: null, target: { scope: 'all' }, undo_note: null,
    steps: sent.requests.map(() => ({ client: 'kitden', name: 'x' })),
    rows: sent.requests.map((request, index) => ({ id: request.id, kind: request.kind, title: request.title, detail: '', project: null, steps: [index], target: { scope: 'all' }, after: [], undo_note: null })),
  },
});

const { renderGateway } = await import('../../src/kitden/web/static/js/gateway.js');
const { dropBody } = await import('../../src/kitden/web/static/js/gateway-drag.js');
const { arrival, data, setRenderer, state } = await import('../../src/kitden/web/static/js/store.js');
const { addToTray, cancelTray, keyFor, takeOut } = await import('../../src/kitden/web/static/js/tray.js');
const { reducedMotion } = await import('../../src/kitden/web/static/js/motion.js');

// The medium sample, cut short (gateway.test.mjs has it whole): files and tracker in the Kitden
// gateway, github outside it.
const tool = (name, state) => ({ name, title: null, state, effective: state, hint: 'reads', origin: 'default', origin_from: null });
const VIEW = {
  gateways: [{ id: 'kitden', kind: 'kitden', name: 'Kitden gateway', where: 'On this Mac', movable: true, servers: [
    { name: 'files', kind: 'local', state: 'on', differs: false, origin: 'default', tools: 1, on_count: 1, on_in: 0, projects: 0, tool_list: [tool('read_file', 'on')] },
    { name: 'tracker', kind: 'remote', state: 'on', differs: false, origin: 'default', tools: 1, on_count: 1, on_in: 0, projects: 0, tool_list: [tool('list_issues', 'on')] },
  ] }],
  connections: { kitden: { claude_code: ['files'], codex: ['files'], cursor: [] } },
  used: ['kitden'],
  groups: { move: [{ name: 'github', clients: ['claude_code'], columns: ['claude_code'], items: ['g'], stays: null }], local: [], plugin: [] },
  own_rules: 0,
};
const entry = (client, s) => ({ client, state: s, item: null, enabled: true });
Object.assign(data, { gateway: VIEW, setupServer: [entry('claude_code', 'added'), entry('codex', 'added'), entry('cursor', 'missing')], clients: [], projects: null });
data.scope.gateway = '';
state.view = 'gateway';
let renders = 0;
setRenderer(() => { renders += 1; });

const main = pages['#main'];
const map = () => main.children.find((n) => n.classList.contains('map')) || null;
const node = (box, key) => walk(box).find((n) => n.dataset.focus === key) || null;
// The link from the gateway to files, as drawn in `box`: the line its hit lies on.
const filesLink = (box) => {
  const hit = node(box, 'link:gateway:kitden>held:kitden:files');
  return walk(box).find((n) => n.tagName === 'path' && /\blink\b/.test(n.className) && n.getAttribute('d') === hit.getAttribute('d'));
};
const REMOVE_FILES = { action: 'gateway.remove', targets: [], params: { server: 'files' } };

test('a tray change draws the Gateway map again in place: no new page, no entrance', async () => {
  state.mode = 'map';
  main.replaceChildren();
  renderGateway(main);
  settle();
  const box = map();
  const head = main.children[0];
  const client = node(box, 'block:client:codex');
  const place = client.style.translate;
  assert.ok(box && place && !/\bleaving\b/.test(filesLink(box).className));
  queue(PREVIEW, batch('c1'));
  await addToTray(REMOVE_FILES);
  // The answer drew the map in place: the same head, map and blocks, and nothing rose into its
  // place again (an entrance would start every block below its place, unseen).
  assert.equal(renders, 0);
  assert.deepEqual([main.children[0], map(), node(box, 'block:client:codex')], [head, box, client]);
  assert.deepEqual([client.style.translate, client.style.opacity], [place, '']);
  assert.match(filesLink(box).className, /\bleaving\b/);
  settle();
  await cancelTray();
  settle();
  assert.doesNotMatch(filesLink(box).className, /\bleaving\b/);
  assert.equal(renders, 0);
});

test('on the List, or once the page shows another place, a tray change draws nothing', async () => {
  // The List draws while a move is in the tray, with no row for its preview.
  queue(PREVIEW, batch('c2'));
  await addToTray(dropBody(VIEW.groups.move[0], VIEW));
  state.mode = 'list';
  main.replaceChildren();
  renderGateway(main);
  const list = main.children.find((n) => n.getAttribute('role') === 'treegrid');
  const shown = walk(list).filter((n) => n.dataset.row).map((n) => n.dataset.row);
  assert.ok(shown.includes('outside:move:github') && !shown.some((id) => id.startsWith('preview:') || id.startsWith('slot:')));
  const before = [...main.children];
  await cancelTray();
  assert.deepEqual([main.children, renders], [before, 0]);
  // Another place: the map's box is off the page, and is not drawn.
  state.mode = 'map';
  main.replaceChildren();
  renderGateway(main);
  settle();
  const box = map();
  main.replaceChildren();
  queue(PREVIEW, batch('c3'));
  await addToTray(REMOVE_FILES);
  assert.doesNotMatch(filesLink(box).className, /\bleaving\b/);
  assert.equal(renders, 0);
  await cancelTray();
});

// The path drawn for a link of `box`: the line its hit lies on.
const linkLine = (box, key) => {
  const hit = node(box, `link:${key}`);
  return hit && walk(box).find((n) => n.tagName === 'path' && /\blink\b/.test(n.className) && n.getAttribute('d') === hit.getAttribute('d'));
};
const lastMotion = (n) => {
  const { keyframes, options } = n.animations.at(-1);
  return [keyframes, options.duration, options.easing];
};
const CONNECT_CURSOR = { action: 'setup_server.register', targets: [{ client: 'cursor' }], params: {} };
const DISCONNECT_CODEX = { action: 'client.disconnect', targets: [{ client: 'codex' }], params: {} };
const MOVE_FILES_OUT = { action: 'gateway.move_out', targets: [{ client: 'claude_code' }], params: { server: 'files' } };
const CALM = 'cubic-bezier(.2,.8,.2,1)';

function freshMap() {
  state.mode = 'map';
  main.replaceChildren();
  renderGateway(main);
  settle();
  return map();
}

test('a connect link fades in and a disconnect link blends to leaving; taken out, both go back', async (t) => {
  const box = freshMap();
  t.after(() => cancelTray());
  queue(PREVIEW, batch('c4'), batch('c5'), batch('c6'));
  await addToTray(CONNECT_CURSOR);
  const connect = linkLine(box, 'client:cursor>gateway:kitden');
  assert.match(connect.className, /\bpreview\b/);
  assert.deepEqual(lastMotion(connect), [[{ opacity: 0 }, { opacity: 1 }], 300, CALM]);
  // Cursor's lamp is the dashed ring, and its words say the change waits.
  const cursor = node(box, 'block:client:cursor');
  assert.ok(walk(cursor).some((n) => n.className === 'lamp pv'));
  assert.ok(walk(cursor).some((n) => n.className === 'block-wait' && n.textContent === '\u00a0· in preview'));
  await addToTray(DISCONNECT_CODEX);
  const codex = linkLine(box, 'client:codex>gateway:kitden');
  assert.match(codex.className, /\bleaving\b/);
  assert.deepEqual(lastMotion(codex), [[{ strokeDasharray: '8 0', strokeOpacity: '1' }, { strokeDasharray: '4 4', strokeOpacity: '0.4' }], 300, CALM]);
  settle();
  // Taken out: the connect link fades out, the other blends back to a solid link.
  await takeOut(keyFor(CONNECT_CURSOR));
  assert.deepEqual(lastMotion(connect), [[{ opacity: 1 }, { opacity: 0 }], 240, 'ease-out']);
  assert.ok(!walk(node(box, 'block:client:cursor')).some((n) => n.className === 'block-wait'));
  await cancelTray();
  assert.doesNotMatch(codex.className, /\bleaving\b/);
  assert.deepEqual(lastMotion(codex), [[{ strokeDasharray: '4 4', strokeOpacity: '0.4' }, { strokeDasharray: '8 0', strokeOpacity: '1' }], 300, CALM]);
  settle();
});

test('under reduced motion a connect link shows at once', async () => {
  const box = freshMap();
  reducedMotion.matches = true;
  try {
    queue(PREVIEW, batch('c7'));
    await addToTray(CONNECT_CURSOR);
    const connect = linkLine(box, 'client:cursor>gateway:kitden');
    assert.deepEqual([connect.animations.length, connect.style.opacity], [0, '']);
    assert.ok(walk(node(box, 'block:client:cursor')).some((n) => n.className === 'lamp pv'));
  } finally {
    reducedMotion.matches = false;
    await cancelTray();
    settle();
  }
});

test('a press on the move-out block takes its row out and gives focus back to the server', async () => {
  const box = freshMap();
  try {
    queue(PREVIEW, batch('c8'));
    await addToTray(MOVE_FILES_OUT);
    settle();
    assert.equal(node(box, 'block:held:kitden:files'), null);
    const shown = node(box, 'block:preview-out:files');
    assert.ok(shown && linkLine(box, 'client:claude_code>preview-out:files'));
  assert.match(linkLine(box, 'gateway:kitden>preview-out:files').className, /\bleaving\b/);
    shown.focus();
    shown.listeners.click[0]();
    await new Promise((resolve) => setImmediate(resolve));
    settle();
    assert.deepEqual([document.activeElement, node(box, 'block:preview-out:files')], [node(box, 'block:held:kitden:files'), null]);
  } finally {
    await cancelTray();
    settle();
  }
});

test('the List draws none of them', async (t) => {
  t.after(() => cancelTray());
  queue(PREVIEW, batch('c9'), batch('c10'), batch('c11'), batch('c12'));
  await addToTray(CONNECT_CURSOR);
  await addToTray(DISCONNECT_CODEX);
  await addToTray(MOVE_FILES_OUT);
  await addToTray({ action: 'mcp.remove_direct', targets: [{ item: 'g' }], params: {} });
  state.mode = 'list';
  main.replaceChildren();
  renderGateway(main);
  const list = main.children.find((n) => n.getAttribute('role') === 'treegrid');
  const rows = walk(list).filter((n) => n.dataset.row);
  const ids = rows.map((n) => n.dataset.row);
  // files is still in the gateway and github outside it; no row is a preview.
  assert.ok(ids.includes('held:kitden:files') && ids.includes('outside:move:github'));
  assert.ok(!ids.some((id) => id.startsWith('preview')));
  // Cursor's row says what is true now, and nothing leaves.
  const cursor = rows.find((n) => n.dataset.row === 'client:cursor');
  assert.deepEqual(walk(cursor).filter((n) => n.className === 'meta').map((n) => n.textContent), ['Not connected']);
  assert.ok(!walk(list).some((n) => /\bleaving\b|block-wait/.test(n.className)));
});

// Twelve servers outside the gateway: three pages of five.
const TWELVE = { ...VIEW, groups: { move: Array.from({ length: 12 }, (_, i) => ({ name: `direct-${i}`, clients: ['codex'], columns: ['codex'], items: [`d${i}`], stays: null })), local: [], plugin: [] } };
const outsideShown = (box) => walk(box).filter((n) => n.dataset.focus?.startsWith('block:outside:')).map((n) => n.dataset.focus.split(':').at(-1));
async function onTwelve(t) {
  data.gateway = TWELVE;
  t.after(() => {
    data.gateway = VIEW;
    state.q = '';
    state.selected = null;
  });
  const box = freshMap();
  return box;
}

test('a press on N more turns the page in place; focus stays on it', async (t) => {
  const box = await onTwelve(t);
  const more = node(box, 'block:more:group:outside');
  assert.deepEqual(outsideShown(box), ['direct-0', 'direct-1', 'direct-2', 'direct-3', 'direct-4']);
  more.focus();
  more.listeners.click[0]();
  settle();
  assert.deepEqual(outsideShown(box), ['direct-5', 'direct-6', 'direct-7', 'direct-8', 'direct-9']);
  // The List does not open: the same map and button, its focus kept.
  assert.deepEqual([state.mode, map(), node(box, 'block:more:group:outside'), document.activeElement], ['map', box, more, more]);
  assert.equal(more.getAttribute('aria-label'), '2 more');
  more.listeners.click[0]();
  settle();
  assert.equal(more.getAttribute('aria-label'), 'Show the first 5');
  more.listeners.click[0]();
  settle();
  assert.deepEqual(outsideShown(box), ['direct-0', 'direct-1', 'direct-2', 'direct-3', 'direct-4']);
  // A turn that hides the selected server lets go of it.
  node(box, 'block:outside:move:direct-1').listeners.click[0]();
  settle();
  assert.match(node(box, 'block:outside:move:direct-1').className, /\bselected\b/);
  more.listeners.click[0]();
  settle();
  assert.ok(!walk(box).some((n) => /\bselected\b/.test(n.className)));
  more.listeners.click[0]();
  more.listeners.click[0]();
  settle();
});

// Review Focus
test('a search match on page 3 shows page 3 and stays after the search', async (t) => {
  const box = await onTwelve(t);
  state.q = 'direct-11';
  renderGateway(main, { again: true });
  settle();
  assert.deepEqual(outsideShown(box), ['direct-10', 'direct-11']);
  // The search ends: its page stays.
  state.q = '';
  renderGateway(main, { again: true });
  settle();
  assert.deepEqual(outsideShown(box), ['direct-10', 'direct-11']);
  // Turn back to the first page for the next test.
  node(box, 'block:more:group:outside').listeners.click[0]();
  settle();
});

test('an arrival on another page brings its page and selects its server', async (t) => {
  const box = await onTwelve(t);
  state.selected = { kind: 'mcp_server', name: 'direct-7' };
  arrival.pending = true;
  renderGateway(main, { again: true });
  await new Promise((resolve) => setImmediate(resolve));
  settle();
  assert.deepEqual(outsideShown(box), ['direct-5', 'direct-6', 'direct-7', 'direct-8', 'direct-9']);
  assert.match(node(box, 'block:outside:move:direct-7').className, /\bselected\b/);
});
