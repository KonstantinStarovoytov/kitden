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
    closest: () => null,
    querySelector: () => null,
    querySelectorAll(selector) {
      const key = selector.match(/^\[data-(\w+)\]$/);
      return key ? walk(node).filter((n) => n.dataset[key[1]]) : [];
    },
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
for (const id of ['#main', '#drawer', '#scrim', '.shell', '#dock', '#find-chip', '#said']) {
  pages[id] = element('DIV');
  pages[id].root = true;
}
// The hint line under the dock (index.html), hidden until a page gives it words.
const hintLine = element('P');
hintLine.hidden = true;
globalThis.document = {
  hidden: false, activeElement: null, body: element('BODY'),
  createElement: (tag) => element(tag.toUpperCase()), createElementNS: (namespace, tag) => element(tag),
  querySelector: (selector) => pages[selector] ?? null, querySelectorAll: () => [], getElementById: (id) => (id === 'hint' ? hintLine : null),
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

const { drawChip, renderGateway } = await import('../../src/kitden/web/static/js/gateway.js');
const { dropBody } = await import('../../src/kitden/web/static/js/gateway-drag.js');
const { arrival, data, setRenderer, state } = await import('../../src/kitden/web/static/js/store.js');
const { addToTray, cancelTray, keyFor, takeOut, tray } = await import('../../src/kitden/web/static/js/tray.js');
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
// The renderer only counts, unless a test asks it to draw the page as store.js would (`drawing`).
let drawing = false;
setRenderer(() => {
  renders += 1;
  if (drawing) redraw();
});

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

test('the map gives the hint line its words, and the List hides it', () => {
  const heard = () => (hintLine.hidden ? '' : hintLine.children.at(-1).textContent);
  freshMap();
  assert.equal(heard(), 'Point at a link and press × to remove it · click anything for its Details · several changes wait in preview, then Apply all · drag a server onto a client');
  state.mode = 'list';
  main.replaceChildren();
  renderGateway(main);
  assert.equal(heard(), '');
  state.mode = 'map';
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
  // Let go, and back to the first page, for the next tests.
  node(box, 'block:outside:move:direct-7').listeners.click[0]();
  node(box, 'block:more:group:outside').listeners.click[0]();
  node(box, 'block:more:group:outside').listeners.click[0]();
  settle();
  assert.deepEqual(outsideShown(box), ['direct-0', 'direct-1', 'direct-2', 'direct-3', 'direct-4']);
});

// Fix round 1: a row taken out gives its server back on its page; a turn during a search stays.
const press = (box, key) => node(box, key).listeners.click[0]();
const heldShown = (box) => walk(box).filter((n) => n.dataset.focus?.startsWith('block:held:kitden:')).map((n) => n.dataset.focus.split(':').at(-1));
const done = () => new Promise((resolve) => setImmediate(resolve));

test('a move in taken out brings its server back on its page in the Outside list, with focus', async (t) => {
  const box = await onTwelve(t);
  t.after(() => cancelTray());
  // On the last page, direct-11 moves into the gateway.
  press(box, 'block:more:group:outside');
  press(box, 'block:more:group:outside');
  settle();
  assert.deepEqual(outsideShown(box), ['direct-10', 'direct-11']);
  queue(PREVIEW, batch('p1'));
  await addToTray(dropBody(TWELVE.groups.move[11], TWELVE));
  settle();
  assert.deepEqual(outsideShown(box), ['direct-10']);
  // Back on the first page, a press on its preview block takes it out.
  press(box, 'block:more:group:outside');
  settle();
  const preview = node(box, 'block:preview:direct-11');
  preview.focus();
  preview.listeners.click[0]();
  await done();
  settle();
  assert.deepEqual(outsideShown(box), ['direct-10', 'direct-11']);
  assert.equal(document.activeElement, node(box, 'block:outside:move:direct-11'));
  press(box, 'block:more:group:outside');
  settle();
});

test('a move out taken out brings its server back on its page in the gateway, with focus', async (t) => {
  const local = Array.from({ length: 8 }, (_, i) => ({ ...VIEW.gateways[0].servers[0], name: `l${i}`, tool_list: [tool(`t${i}`, 'on')] }));
  const view = { ...VIEW, gateways: [{ ...VIEW.gateways[0], servers: local }], connections: { kitden: { claude_code: [], codex: [], cursor: [] } } };
  data.gateway = view;
  t.after(() => { data.gateway = VIEW; return cancelTray(); });
  const box = freshMap();
  assert.deepEqual(heldShown(box), ['l0', 'l1', 'l2', 'l3', 'l4']);
  // l7, on the second page, moves out while the first page shows.
  queue(PREVIEW, batch('p2'));
  await addToTray({ action: 'gateway.move_out', targets: [{ client: 'claude_code' }], params: { server: 'l7' } });
  settle();
  const preview = node(box, 'block:preview-out:l7');
  preview.focus();
  preview.listeners.click[0]();
  await done();
  settle();
  assert.deepEqual(heldShown(box), ['l5', 'l6', 'l7']);
  assert.equal(document.activeElement, node(box, 'block:held:kitden:l7'));
  press(box, 'block:more:group:kitden:local');
  settle();
});

test('a turn during a search stays when the tray draws the map again', async (t) => {
  const box = await onTwelve(t);
  t.after(() => cancelTray());
  state.q = 'direct-11';
  renderGateway(main, { again: true });
  settle();
  assert.deepEqual(outsideShown(box), ['direct-10', 'direct-11']);
  // The person turns to the first page; the search is still on.
  press(box, 'block:more:group:outside');
  settle();
  queue(PREVIEW, batch('p3'));
  await addToTray(REMOVE_FILES);
  renderGateway(main, { again: true });
  settle();
  assert.deepEqual(outsideShown(box), ['direct-0', 'direct-1', 'direct-2', 'direct-3', 'direct-4']);
  // New search words bring their page again.
  state.q = 'direct-7';
  renderGateway(main, { again: true });
  settle();
  assert.ok(outsideShown(box).includes('direct-7'));
  state.q = '';
  renderGateway(main, { again: true });
  press(box, 'block:more:group:outside');
  press(box, 'block:more:group:outside');
  settle();
});

// Map <-> List (gateway-notes 7.1): the view that shows leaves (120 ease-in, up 4 px), the page
// then draws the other, which comes in (260 CALM, up from 6 px). The selection lets go.
const listBox = () => main.children.find((n) => n.getAttribute('role') === 'treegrid') || null;
const tick = () => new Promise((resolve) => setImmediate(resolve));
const OUT = [[{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-4px)' }], 120, 'ease-in'];
const IN = [[{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }], 260, CALM];

// The page draws its next view the way store.js would after `go`: the test's renderer only counts.
function redraw() {
  main.replaceChildren();
  renderGateway(main, { again: true });
}

test('Map to List and back move out and in', async (t) => {
  const box = freshMap();
  renders = 0;
  drawing = true;
  t.after(() => { drawing = false; });
  // A server is selected: the switch lets go of it.
  press(box, 'block:outside:move:github');
  settle();
  assert.match(node(box, 'block:outside:move:github').className, /\bselected\b/);
  // The old view's motion ends only when the test says: the page keeps the map until then.
  let leave;
  const real = box.animate;
  box.animate = (keyframes, options) => {
    const animation = real(keyframes, options);
    animation.finished = new Promise((resolve) => { leave = resolve; });
    return animation;
  };
  node(main, 'view:list').listeners.click[0]();
  await tick();
  assert.deepEqual(lastMotion(box), OUT);
  assert.equal(box.animations.at(-1).options.fill, 'forwards');
  assert.deepEqual([state.mode, renders], ['map', 0]);
  // The pill moves at once.
  assert.deepEqual([node(main, 'view:list').getAttribute('aria-pressed'), node(main, 'view:map').getAttribute('aria-pressed')], ['true', 'false']);
  leave();
  await tick();
  assert.deepEqual([state.mode, renders], ['list', 1]);
  const list = listBox();
  assert.deepEqual(lastMotion(list), IN);
  assert.equal(state.selected, null);
  // Back to the map: the List leaves, the map comes in as one piece.
  node(main, 'view:map').listeners.click[0]();
  await tick();
  assert.deepEqual(lastMotion(list), OUT);
  assert.deepEqual([state.mode, renders], ['map', 2]);
  const again = map();
  assert.deepEqual(lastMotion(again), IN);
  // Its blocks do not rise one by one on top of that, and none is selected.
  assert.equal(node(again, 'block:client:codex').animations.length, 0);
  assert.ok(!walk(again).some((n) => /\bselected\b/.test(n.className)));
  settle();
});

test('a second press on the pill while a view leaves does nothing', async () => {
  const box = freshMap();
  renders = 0;
  let leave;
  const real = box.animate;
  box.animate = (keyframes, options) => {
    const animation = real(keyframes, options);
    animation.finished = new Promise((resolve) => { leave = resolve; });
    return animation;
  };
  node(main, 'view:list').listeners.click[0]();
  await tick();
  node(main, 'view:list').listeners.click[0]();
  await tick();
  assert.equal(box.animations.filter((a) => a.options.duration === 120).length, 1);
  leave();
  await tick();
  assert.equal(renders, 1);
  redraw();
  settle();
  state.mode = 'map';
});

test('under reduced motion the switch lands at once', async () => {
  const box = freshMap();
  renders = 0;
  reducedMotion.matches = true;
  drawing = true;
  try {
    node(main, 'view:list').listeners.click[0]();
    await tick();
    assert.deepEqual([box.animations.length, state.mode, renders], [0, 'list', 1]);
    assert.equal(listBox().animations.length, 0);
    assert.equal(listBox().style.opacity, undefined);
  } finally {
    reducedMotion.matches = false;
    drawing = false;
    state.mode = 'map';
  }
});

// Final wave: a switch whose page went while the old view left draws nothing: it does not take
// the person back to the Gateway, and the next draw of the map is not taken for the switch's.
test('a view switch lands only while the Gateway still shows the view it left', async (t) => {
  const box = freshMap();
  renders = 0;
  let leave;
  const real = box.animate;
  box.animate = (keyframes, options) => {
    const animation = real(keyframes, options);
    animation.finished = new Promise((resolve) => { leave = resolve; });
    return animation;
  };
  t.after(() => { state.view = 'gateway'; state.mode = 'map'; });
  node(main, 'view:list').listeners.click[0]();
  await tick();
  // Another place opens while the map leaves.
  state.view = 'library';
  leave();
  await tick();
  assert.deepEqual([state.view, state.mode, renders], ['library', 'map', 0]);
  // Back on the Gateway, the next draw is not taken for the switch's: the map does not rise as one
  // piece.
  state.view = 'gateway';
  const risen = (n) => n.animations.filter((a) => a.options.duration === 260 && a.keyframes[0].transform === 'translateY(6px)').length;
  const before = risen(box);
  main.replaceChildren();
  renderGateway(main, { again: true });
  assert.equal(risen(map()), before);
  settle();
});

// The List (gateway-notes 7.2): a header with "Name", "Used by" and "Tools"; group rows with their
// icons; server rows with the clients that use them and "n of m on"; tool rows with a mark, the
// name and a quiet Read or Write; outside rows with their client and "Move in…". The words of the
// List are the mockup's, without sign-in words and tool counts of servers outside the gateway.
test("the List shows the mockup's columns and rows", () => {
  state.mode = 'list';
  main.replaceChildren();
  renderGateway(main);
  const list = listBox();
  const header = walk(list).filter((n) => n.getAttribute('role') === 'columnheader');
  assert.deepEqual(header.map((n) => n.textContent), ['Name', 'Used by', 'Tools', '']);
  assert.equal(header[3].children[0].textContent, 'Action');
  assert.equal(header[3].children[0].className, 'sr-only');
  const row = (id) => walk(list).find((n) => n.dataset.row === id);
  const cells = (id) => row(id).children.filter((n) => n.getAttribute('role') === 'gridcell');
  // Group rows have an icon.
  const iconOf = (id) => walk(row(id)).find((n) => n.dataset.icon)?.dataset.icon;
  assert.deepEqual(['group:kitden:remote', 'group:kitden:local', 'group:outside'].map(iconOf), ['cloud', 'hard-drive', 'info']);
  assert.equal(cells('group:outside')[0].children.at(-1).textContent, "Outside the gateway · calls skip Kitden's rules");
  // A server: the clients that use it as tiles, and how many of its tools are on.
  const files = cells('held:kitden:files');
  assert.equal(files[2].textContent, '1 of 1 on');
  assert.equal(walk(files[1]).filter((n) => /mark/.test(n.className)).length, 2);
  // An outside server: its client's tile, no count of tools, and "Move in…".
  const github = cells('outside:move:github');
  assert.equal(walk(github[1]).filter((n) => /mark/.test(n.className)).length, 1);
  assert.equal(github[2].textContent, '');
  assert.deepEqual(walk(github[3]).filter((n) => n.tagName === 'BUTTON').map((n) => n.textContent), ['Move in…']);
  // The words of the sign-in and of tool counts outside the gateway stay out of the List.
  const words = walk(list).map((n) => n.textContent).join(' ');
  assert.doesNotMatch(words, /Sign in|Signed in|Running|not tested|\d+ tools/);
});

test('an open server shows its tools with a mark, the name and a quiet Read or Write', () => {
  state.mode = 'list';
  main.replaceChildren();
  renderGateway(main);
  const open = walk(listBox()).find((n) => n.dataset.row === 'held:kitden:files');
  open.listeners.click[0]({ target: { closest: (selector) => (selector === '.caret' ? {} : null) } });
  main.replaceChildren();
  renderGateway(main);
  const tool = walk(listBox()).find((n) => n.dataset.row === 'tool:files/read_file');
  const name = tool.children[0];
  assert.ok(walk(name).some((n) => /\btg-dot\b/.test(n.className)));
  const quiet = walk(name).find((n) => n.className === 'hint');
  assert.equal(quiet.textContent, 'Read');
  assert.ok(!walk(name).some((n) => /\bflag\b/.test(n.className)));
  open.listeners.click[0]({ target: { closest: (selector) => (selector === '.caret' ? {} : null) } });
  state.mode = 'map';
});

test('the chip counts again after a tray redraw', async (t) => {
  t.after(() => {
    state.q = '';
    return cancelTray();
  });
  state.q = 'files';
  main.replaceChildren();
  drawChip(renderGateway(main));
  settle();
  const chip = pages['#find-chip'];
  assert.equal(chip.textContent, '1 match');
  // Something else wrote the chip, or it went stale: the redraw in place says the count again.
  chip.textContent = '';
  queue(PREVIEW, batch('chip1'));
  await addToTray(REMOVE_FILES);
  assert.equal(chip.textContent, '1 match');
  // With no search it says nothing.
  state.q = '';
  main.replaceChildren();
  drawChip(renderGateway(main));
  assert.equal(chip.textContent, '');
});

test('the chip counts what lights on the shown page, and counts again when a page turns', async (t) => {
  const servers = Array.from({ length: 8 }, (_, i) => ({ ...VIEW.gateways[0].servers[0], name: `srv-${i + 1}`, kind: 'remote' }));
  data.gateway = { ...VIEW, gateways: [{ ...VIEW.gateways[0], servers }], connections: { kitden: { claude_code: [], codex: [], cursor: [] } } };
  t.after(() => {
    data.gateway = VIEW;
    state.q = '';
    state.mode = 'map';
  });
  // Eight servers match; the group shows five of them.
  state.q = 'srv';
  state.mode = 'map';
  main.replaceChildren();
  const found = renderGateway(main);
  settle();
  const box = map();
  drawChip(found);
  const lit = walk(box).filter((n) => /\bfound\b/.test(n.className) && String(n.dataset.focus).startsWith('block:held:'));
  assert.equal(lit.length, 5);
  assert.equal(pages['#find-chip'].textContent, '5 matches');
  // The turn shows the other three, and the chip says so.
  press(box, 'block:more:group:kitden:remote');
  settle();
  assert.equal(pages['#find-chip'].textContent, '3 matches');
});

// A project switch in place (gateway-notes 7.4): the map stays and changes what the project
// changes. atlas turns read_file off with a rule of its own; web follows the shared rule.
const { ruleBody } = await import('../../src/kitden/web/static/js/gateway-details.js');
const { closePanel, isPanelOpen, panelState } = await import('../../src/kitden/web/static/js/panel.js');
const { RETRACT } = await import('../../src/kitden/web/static/js/motion.js');
const [FILES, TRACKER] = VIEW.gateways[0].servers;
const ATLAS = { ...VIEW, own_rules: 1, gateways: [{ ...VIEW.gateways[0], servers: [{ ...FILES, on_count: 0, tool_list: [{ ...tool('read_file', 'off'), origin: 'project' }] }, TRACKER] }] };
const PROJECTS = [{ id: 'atlas', path: '/h/work/atlas', own_rules: 1, exists: true }, { id: 'web', path: '/h/work/web', own_rules: 0, exists: true }];
const TOOL_LINK = 'held:kitden:files>tool:files/read_file';
const scopeLine = () => main.children.find((n) => /\bscope-bar\b/.test(n.className));
const partOf = (box, key, look) => walk(node(box, key)).find((n) => n.className.split(' ')[0] === look);

// The page picks a project as app.js does on the Gateway: it reads the project, then draws again
// in place.
function pickProject(id, view = VIEW) {
  state.project = id;
  data.gateway = view;
  data.scope.gateway = id;
  main.replaceChildren();
  renderGateway(main, { again: true });
}

// A map with the files server open (and selected, its Details open), every read noted in `asked`.
async function filesOpen(t) {
  const asked = [];
  const fetchWas = globalThis.fetch;
  globalThis.fetch = (url, init) => { asked.push(url); return fetchWas(url, init); };
  data.projects = PROJECTS;
  t.after(async () => {
    globalThis.fetch = fetchWas;
    pickProject('', VIEW);
    closePanel({ instant: true, focus: false });
    await done();
    settle();
    // Fold files again for the next test.
    if (node(map(), 'block:tool:files/read_file')) press(map(), 'block:held:kitden:files');
    settle();
    Object.assign(data, { projects: null });
    Object.assign(state, { selected: null });
    reducedMotion.matches = false;
    await cancelTray();
  });
  const box = freshMap();
  press(box, 'block:held:kitden:files');
  await done();
  settle();
  assert.ok(node(box, 'block:tool:files/read_file'));
  return { box, asked };
}

test('a project switch keeps the map and its open servers', async (t) => {
  const { box, asked } = await filesOpen(t);
  assert.equal(isPanelOpen(), true);
  renders = 0;
  pickProject('atlas', ATLAS);
  settle();
  // The same map: the server is still open and selected, nothing rose into its place again.
  assert.equal(map(), box);
  assert.ok(node(box, 'block:tool:files/read_file'));
  assert.match(node(box, 'block:held:kitden:files').className, /\bselected\b/);
  assert.equal(renders, 0);
  // The scope line swaps its words and rises 4 px in 320 ms.
  assert.match(scopeLine().className, /\bproject\b/);
  assert.equal(scopeLine().children.at(-1).textContent, 'Project atlas · 1 rule differs from the shared setup');
  assert.deepEqual(lastMotion(scopeLine()), [[{ opacity: 0, transform: 'translateY(4px)' }, { opacity: 1, transform: 'none' }], 320, CALM]);
  // Its Details stay open and follow the project: the server's rules are read for atlas.
  await done();
  assert.equal(isPanelOpen(), true);
  assert.deepEqual(panelState.current, { type: 'held', name: 'files' });
  assert.ok(asked.includes('/api/gateway/tools?server=files&project=atlas'), asked.join(' '));
  // A draw for the same project again (the tray, a rescan): the scope line stays still.
  main.replaceChildren();
  renderGateway(main, { again: true });
  assert.equal(scopeLine().animations.length, 0);
});

test('counts roll and flipped links draw or undraw', async (t) => {
  const { box } = await filesOpen(t);
  const line = linkLine(box, TOOL_LINK);
  pickProject('atlas', ATLAS);
  // "1 of 1 on" rolls to "0 of 1 on", and the server's lamp pops as it turns off.
  const holder = walk(node(box, 'block:held:kitden:files')).find((n) => n.className === 'num roll');
  assert.deepEqual(holder.children.map((n) => n.textContent), ['1', '0']);
  assert.deepEqual([holder.children[1].animations[0].options.duration, holder.children[1].animations[0].options.delay], [200, 140]);
  const pops = (n) => n.animations.filter((a) => /^scale\(/.test(a.keyframes[0].transform || '')).map((a) => [a.options.duration, a.options.easing]);
  assert.deepEqual(pops(partOf(box, 'block:held:kitden:files', 'lamp')), [[200, CALM]]);
  // The tool's mark pops, its tag pops in, and its link draws back (380 ms).
  assert.deepEqual(pops(partOf(box, 'block:tool:files/read_file', 'mark')), [[200, CALM]]);
  const tag = partOf(box, 'block:tool:files/read_file', 'block-projects');
  assert.deepEqual(lastMotion(tag), [[{ opacity: 0, transform: 'scale(0.7)' }, { opacity: 1, transform: 'none' }], 200, CALM]);
  assert.deepEqual(lastMotion(line), [[{ strokeDashoffset: 0 }, { strokeDashoffset: 1 }], 380, RETRACT]);
  settle();
  await new Promise((resolve) => setTimeout(resolve, 400));
  // Back to All projects: the link draws in (240 ms) and the mark pops again.
  pickProject('', VIEW);
  assert.deepEqual(lastMotion(linkLine(box, TOOL_LINK)), [[{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], 240, CALM]);
  assert.deepEqual(pops(partOf(box, 'block:tool:files/read_file', 'mark')), [[200, CALM]]);
  settle();
});

// Review Focus
test('rows waiting in the tray keep their looks after a switch', async (t) => {
  const { box } = await filesOpen(t);
  queue(PREVIEW, batch('pj1'));
  await addToTray(ruleBody('files', 'read_file', 'off', 'atlas'));
  settle();
  const looks = () => [partOf(box, 'block:tool:files/read_file', 'mark').className, walk(node(box, 'block:tool:files/read_file')).find((n) => /block-projects/.test(n.className))?.children.at(-1).textContent];
  assert.deepEqual(looks(), ['mark on', 'atlas']);
  // In atlas the rule is this project's: its mark is the dashed ring until Apply.
  pickProject('atlas', ATLAS);
  settle();
  assert.equal(looks()[0], 'mark pv');
  // In web the tool names atlas again, and the tray still holds the row.
  pickProject('web', VIEW);
  settle();
  assert.deepEqual(looks(), ['mark on', 'atlas']);
  assert.equal(tray.rows.length, 1);
});

test('under reduced motion the project switch lands at once', async (t) => {
  const { box } = await filesOpen(t);
  const line = linkLine(box, TOOL_LINK);
  reducedMotion.matches = true;
  pickProject('atlas', ATLAS);
  assert.equal(scopeLine().animations.length, 0);
  const tool = node(box, 'block:tool:files/read_file');
  assert.ok(walk(tool).every((n) => n.animations.length === 0));
  assert.equal(partOf(box, 'block:tool:files/read_file', 'mark').className, 'mark');
  assert.equal(line.parentNode, null);
  assert.equal(linkLine(box, TOOL_LINK), null);
});

test('a project switch keeps each page, and a search brings its matches there', async (t) => {
  const box = await onTwelve(t);
  t.after(() => pickProject('', VIEW));
  state.q = 'direct-11';
  renderGateway(main, { again: true });
  settle();
  // The person turns to the first page while the search is on; another project brings its match.
  press(box, 'block:more:group:outside');
  settle();
  assert.deepEqual(outsideShown(box), ['direct-0', 'direct-1', 'direct-2', 'direct-3', 'direct-4']);
  pickProject('atlas', TWELVE);
  settle();
  assert.deepEqual(outsideShown(box), ['direct-10', 'direct-11']);
  // With no search, a switch keeps the page shown.
  state.q = '';
  press(box, 'block:more:group:outside');
  press(box, 'block:more:group:outside');
  settle();
  assert.deepEqual(outsideShown(box), ['direct-5', 'direct-6', 'direct-7', 'direct-8', 'direct-9']);
  pickProject('', TWELVE);
  settle();
  assert.deepEqual(outsideShown(box), ['direct-5', 'direct-6', 'direct-7', 'direct-8', 'direct-9']);
  press(box, 'block:more:group:outside');
  press(box, 'block:more:group:outside');
  settle();
});

// Fix round 1: "Show" in a tool's panel goes the picker's way (switchProject), and the page draws
// the project in place as app.js does; the panel takes no press until it has stepped.
test('Show switches in place through the page, and the panel waits for its step', async (t) => {
  const { setSwitcher } = await import('../../src/kitden/web/static/js/store.js');
  const { closeForProject } = await import('../../src/kitden/web/static/js/panel.js');
  const rules = { server: 'files', state: 'on', shared: 'on', strict: false, problem: null, tools: [{ name: 'read_file', state: 'on', effective: 'on', hint: 'reads', origin: 'default' }],
    projects: [{ id: 'atlas', server: 'on', tools: { read_file: 'off' }, own: ['read_file'], up: [] }] };
  const { box, asked } = await filesOpen(t);
  const fetchWas = globalThis.fetch;
  globalThis.fetch = (url, init) => (url.startsWith('/api/gateway/tools') ? (asked.push(url), Promise.resolve({ ok: true, status: 200, json: async () => rules })) : fetchWas(url, init));
  setSwitcher(async () => {
    closeForProject();
    pickProject(state.project, state.project === 'atlas' ? ATLAS : VIEW);
  });
  t.after(() => { globalThis.fetch = fetchWas; setSwitcher(async () => {}); });
  press(box, 'block:tool:files/read_file');
  await new Promise((resolve) => setTimeout(resolve, 400));
  const drawer = pages['#drawer'];
  const show = walk(drawer).find((n) => n.dataset.focus === 'show:atlas');
  assert.ok(show, 'Show for atlas');
  asked.length = 0;
  show.listeners.click[0]({});
  await Promise.resolve();
  // The page has drawn atlas in place; the panel holds still while its step reads.
  assert.equal(state.project, 'atlas');
  assert.equal(drawer.inert, true);
  await new Promise((resolve) => setTimeout(resolve, 400));
  assert.equal(drawer.inert, false);
  assert.equal(isPanelOpen(), true);
  assert.deepEqual(panelState.current, { type: 'tool', server: 'files', tool: 'read_file' });
  assert.ok(asked.includes('/api/gateway/tools?server=files&project=atlas'), asked.join(' '));
  assert.equal(map(), box);
});

// After a verified Apply all each row lands on the map in tray order, 60 ms apart (motion-spec M4
// step 6). Undo all plays the rows back in reverse, 120 ms apart, and a link that comes back draws
// in over 480 ms. Here files leaves the gateway, then Codex is disconnected.
const { applyTray, endApplied, undone } = await import('../../src/kitden/web/static/js/tray.js');
const SETUP_BEFORE = data.setupServer;
const SETUP_AFTER = [entry('claude_code', 'added'), entry('codex', 'missing'), entry('cursor', 'missing')];
const VIEW_AFTER = { ...VIEW, gateways: [{ ...VIEW.gateways[0], servers: [TRACKER] }] };
const lampOf = (box, id) => partOf(box, `block:${id}`, 'lamp').className;
const FILES_BLOCK = 'block:held:kitden:files';

async function appliedTwo(t) {
  const box = freshMap();
  t.after(() => {
    Object.assign(data, { gateway: VIEW, setupServer: SETUP_BEFORE });
    undone.id = null;
    reducedMotion.matches = false;
    redraw();
    settle();
  });
  queue(PREVIEW, batch('land0'), batch('land1'));
  await addToTray(REMOVE_FILES);
  await addToTray(DISCONNECT_CODEX);
  settle();
  queue('/api/changes/land1/apply', { status: 200, json: { id: 'land1', state: 'verified', error: null } });
  await applyTray();
  assert.equal(tray.phase, 'applied');
  return box;
}

// What the page does once the Apply is verified (dock.js): it reads the result, draws it, and the
// tray empties.
function drawApplied() {
  Object.assign(data, { gateway: VIEW_AFTER, setupServer: SETUP_AFTER });
  redraw();
  endApplied();
}

// What undoChange (review.js) has the page do once the Undo is verified.
function drawUndone() {
  undone.id = 'land1';
  Object.assign(data, { gateway: VIEW, setupServer: SETUP_BEFORE });
  redraw();
}

test('after Apply all the rows land in tray order, 60 ms apart; Undo all plays them back in reverse, 120 ms apart', async (t) => {
  const box = await appliedTwo(t);
  t.mock.timers.enable({ apis: ['setTimeout'] });
  drawApplied();
  settle();
  // The first row landed: files has gone. The second still waits: Codex is still connected.
  assert.equal(node(box, FILES_BLOCK), null);
  assert.equal(lampOf(box, 'client:codex'), 'lamp on');
  t.mock.timers.tick(59);
  settle();
  assert.equal(lampOf(box, 'client:codex'), 'lamp on');
  t.mock.timers.tick(1);
  settle();
  assert.equal(lampOf(box, 'client:codex'), 'lamp');
  assert.equal(linkLine(box, 'client:codex>gateway:kitden'), null);
  t.mock.timers.tick(1000);
  settle();
  // Undo all: the last row first. Codex's link comes back and draws in over 480 ms; files waits.
  drawUndone();
  assert.equal(lampOf(box, 'client:codex'), 'lamp on');
  assert.deepEqual(lastMotion(linkLine(box, 'client:codex>gateway:kitden')), [[{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], 480, CALM]);
  settle();
  assert.equal(node(box, FILES_BLOCK), null);
  t.mock.timers.tick(119);
  settle();
  assert.equal(node(box, FILES_BLOCK), null);
  t.mock.timers.tick(1);
  settle();
  assert.ok(node(box, FILES_BLOCK));
  t.mock.timers.tick(1000);
  settle();
});

test('under reduced motion every row lands at once, and an Undo puts everything back at once', async (t) => {
  const box = await appliedTwo(t);
  t.mock.timers.enable({ apis: ['setTimeout'] });
  reducedMotion.matches = true;
  drawApplied();
  assert.deepEqual([node(box, FILES_BLOCK), lampOf(box, 'client:codex')], [null, 'lamp']);
  drawUndone();
  assert.ok(node(box, FILES_BLOCK));
  assert.equal(lampOf(box, 'client:codex'), 'lamp on');
  assert.equal(linkLine(box, 'client:codex>gateway:kitden').animations.length, 0);
});

// A first visit (motion-spec M1): what shows under the head before the map, the skeleton, the error
// banner or "No gateway yet", rises as the rest of the visit does; drawn again it stays still.
// Under reduced motion it is there at once.
test('the skeleton, the error banner and "No gateway yet" rise when they come', (t) => {
  t.after(() => {
    Object.assign(data, { gateway: VIEW });
    delete data.errors.gateway;
    delete data.errorScope.gateway;
    reducedMotion.matches = false;
    freshMap();
  });
  const under = () => main.children.at(-1);
  const steps = [
    ['skeleton', () => { data.gateway = null; }, (n) => n.getAttribute('aria-busy') === 'true'],
    ['banner', () => Object.assign(data.errors, { gateway: 'down' }) && Object.assign(data.errorScope, { gateway: '' }), (n) => n.className === 'banner'],
    ['no gateway', () => { delete data.errors.gateway; data.gateway = { ...VIEW, gateways: [] }; }, (n) => n.className === 'card'],
  ];
  for (const calm of [false, true]) {
    reducedMotion.matches = calm;
    steps.forEach(([name, set, is], i) => {
      set();
      main.replaceChildren();
      renderGateway(main, { again: i > 0 });
      assert.ok(is(under()), name);
      if (calm) assert.equal(under().animations.length, 0, name);
      else assert.deepEqual(lastMotion(under()), IN, name);
      // Drawn again as it is, it stays still.
      main.replaceChildren();
      renderGateway(main, { again: true });
      assert.equal(under().animations.length, 0, name);
    });
    delete data.errorScope.gateway;
  }
});

// The head rises on a first visit (riseHead): data that comes while it rises draws a new head,
// which goes on rising from where the old one was, so it does not jump; a scope line that was not
// there rises in its turn. Data that comes later draws the head still.
test('data that comes while the head rises keeps it rising', (t) => {
  t.after(() => {
    data.gateway = VIEW;
    reducedMotion.matches = false;
    freshMap();
  });
  const delays = () => main.children.slice(0, 3).map((n) => (n.animations.length ? n.animations.at(-1).options.delay : null));
  for (const calm of [false, true]) {
    reducedMotion.matches = calm;
    data.gateway = null;
    now = 100000;
    main.replaceChildren();
    renderGateway(main);
    assert.deepEqual(delays().slice(0, 2), calm ? [null, null] : [0, 120]);
    now += 200;
    data.gateway = VIEW;
    main.replaceChildren();
    renderGateway(main, { again: true });
    assert.deepEqual(delays(), calm ? [null, null, null] : [-200, -80, 0]);
    settle();
    now += 1000;
    main.replaceChildren();
    renderGateway(main, { again: true });
    assert.deepEqual(delays(), [null, null, null]);
  }
});

test('a focused link keeps its hit while the tray writes, and every hit is there after a failed Apply', async () => {
  const box = freshMap();
  queue(PREVIEW, batch('w1'));
  await addToTray(REMOVE_FILES);
  settle();
  const key = 'link:gateway:kitden>held:kitden:files';
  const hit = node(box, key);
  const hits = () => walk(box).filter((n) => n.classList.contains('hit')).length;
  const count = hits();
  hit.focus();
  let fail;
  queue('/api/changes/w1/apply', () => new Promise((resolve) => { fail = () => resolve({ status: 200, json: { id: 'w1', state: 'restored', error: 'The original settings were restored.' } }); }));
  try {
    const applying = applyTray();
    settle();
    // While it writes, the map is drawn again: the hits stay, and so does focus.
    assert.equal(tray.phase, 'applying');
    assert.deepEqual([node(box, key), document.activeElement, hits()], [hit, hit, count]);
    fail();
    await applying;
    settle();
    assert.equal(tray.phase, 'failed');
    assert.deepEqual([node(box, key), document.activeElement, hits()], [hit, hit, count]);
  } finally {
    await cancelTray();
    settle();
  }
});

// Final wave: while another project is read (`#main.pending`) the map and the List take no key but
// Tab. The box hears a key first (capture) and keeps it from what it holds.
test('while another project is read, keys on the map and the List do nothing; Tab still moves', async (t) => {
  t.after(() => main.classList.remove('pending'));
  // A key as the browser sends it: the box first, then the control, unless the box stopped it.
  const press = (box, target, key) => {
    const event = { key, target, stopped: false, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, stopPropagation() { this.stopped = true; } };
    box.listeners.keydown[0](event);
    if (!event.stopped) for (const fn of target.listeners.keydown || []) fn(event);
    return event;
  };
  const box = freshMap();
  const hit = node(box, 'link:gateway:kitden>held:kitden:files');
  const client = node(box, 'block:client:codex');
  main.classList.add('pending');
  for (const [target, key] of [[hit, 'Delete'], [hit, 'Enter'], [client, 'Enter'], [client, ' ']]) {
    const event = press(box, target, key);
    assert.deepEqual([event.stopped, event.defaultPrevented], [true, true], key);
  }
  assert.deepEqual([press(box, hit, 'Tab').stopped, tray.rows.length], [false, 0]);
  // The read ends: Delete removes the link again.
  main.classList.remove('pending');
  queue(PREVIEW, batch('k1'));
  press(box, hit, 'Delete');
  await tick();
  assert.deepEqual(tray.rows.map((r) => r.body.action), ['gateway.remove']);
  await cancelTray();
  settle();
  // The List: its arrows do nothing while the read runs.
  state.mode = 'list';
  main.replaceChildren();
  renderGateway(main);
  const list = listBox();
  main.classList.add('pending');
  const first = walk(list).find((n) => n.dataset.row);
  assert.equal(press(list, first, 'ArrowDown').stopped, true);
  state.mode = 'map';
  main.classList.remove('pending');
  freshMap();
});

// Final wave: a turn says the group's caption once, in the page's live region.
test('a turn of a page says which ones show to a screen reader', async (t) => {
  const box = await onTwelve(t);
  const said = pages['#said'];
  // The live region takes its words in a later timer task (toast.js say).
  const heard = () => new Promise((resolve) => setTimeout(resolve, 5));
  press(box, 'block:more:group:outside');
  await heard();
  assert.equal(said.textContent, 'Outside the gateway · 6–10 of 12');
  press(box, 'block:more:group:outside');
  await heard();
  assert.equal(said.textContent, 'Outside the gateway · 11–12 of 12');
  press(box, 'block:more:group:outside');
  await heard();
  assert.equal(said.textContent, 'Outside the gateway · 1–5 of 12');
  settle();
});

// Final wave: a search does not turn the page away from the selected block; it stays selected.
test('a search keeps the page of the selected block, and the selection with it', async (t) => {
  const box = await onTwelve(t);
  press(box, 'block:outside:move:direct-1');
  settle();
  state.q = 'direct-7';
  renderGateway(main, { again: true });
  settle();
  assert.deepEqual(outsideShown(box), ['direct-0', 'direct-1', 'direct-2', 'direct-3', 'direct-4']);
  assert.match(node(box, 'block:outside:move:direct-1').className, /\bselected\b/);
  // Let go: the same search words bring nothing, new ones bring their page.
  press(box, 'block:outside:move:direct-1');
  settle();
  state.q = 'direct-8';
  renderGateway(main, { again: true });
  settle();
  assert.ok(outsideShown(box).includes('direct-8'));
  state.q = '';
  renderGateway(main, { again: true });
  press(box, 'block:more:group:outside');
  press(box, 'block:more:group:outside');
  settle();
  assert.deepEqual(outsideShown(box), ['direct-0', 'direct-1', 'direct-2', 'direct-3', 'direct-4']);
});

// Final wave: a row taken out by the bar's × (takeOut) or Cancel all brings its server back on its
// page too, as a press on the map does.
test("a move taken out by the bar's × or by Cancel brings its server back on its page", async (t) => {
  const box = await onTwelve(t);
  t.after(() => cancelTray());
  for (const takeAway of [() => takeOut(keyFor(dropBody(TWELVE.groups.move[11], TWELVE))), () => cancelTray()]) {
    press(box, 'block:more:group:outside');
    press(box, 'block:more:group:outside');
    settle();
    queue(PREVIEW, batch('x1'));
    await addToTray(dropBody(TWELVE.groups.move[11], TWELVE));
    settle();
    press(box, 'block:more:group:outside');
    settle();
    assert.deepEqual(outsideShown(box), ['direct-0', 'direct-1', 'direct-2', 'direct-3', 'direct-4']);
    await takeAway();
    await done();
    settle();
    assert.deepEqual(outsideShown(box), ['direct-10', 'direct-11']);
    press(box, 'block:more:group:outside');
    settle();
  }
});

// Final wave: the List keeps its open servers across projects (design.md Project switch).
test('the List keeps its open servers when another project is picked', (t) => {
  t.after(() => { state.mode = 'map'; state.project = ''; data.scope.gateway = ''; freshMap(); });
  state.mode = 'list';
  main.replaceChildren();
  renderGateway(main);
  const files = walk(listBox()).find((n) => n.dataset.row === 'held:kitden:files');
  const shownRows = () => walk(listBox()).filter((n) => n.dataset.row).map((n) => n.dataset.row);
  // Right on its row unfolds files.
  for (const fn of listBox().listeners.keydown) fn({ key: 'ArrowRight', target: files, preventDefault() {}, stopPropagation() {} });
  main.replaceChildren();
  renderGateway(main, { again: true });
  assert.ok(shownRows().includes('tool:files/read_file'));
  state.project = 'atlas';
  data.scope.gateway = 'atlas';
  main.replaceChildren();
  renderGateway(main, { again: true });
  assert.ok(shownRows().includes('tool:files/read_file'));
});

// Phase 5 Task 4: a server the Add panel adds waits in preview on the map, at the end of its group
// of the Kitden gateway, and lands there after Apply; an Undo plays it back.
const { ADD_SERVER, openLocalAdd: openAdd, wasAdded } = await import('../../src/kitden/web/static/js/gateway-add.js');
const { gatewayCard } = await import('../../src/kitden/web/static/js/gateway-details.js');
const MARKET = [
  { id: 'test-helper@demo/test-status', name: 'test-status', plugin: 'test-helper', marketplace: 'demo', kind: 'remote', held: false, refusal: null },
  { id: 'db-tools@demo/db-query', name: 'db-query', plugin: 'db-tools', marketplace: 'demo', kind: 'local', held: false, refusal: null },
];
const MARKET_HELD = [{ ...MARKET[0], held: true, refusal: 'test-status is in the gateway already.' }, MARKET[1]];
const STATUS_SERVER = { name: 'test-status', kind: 'remote', state: 'on', differs: false, origin: 'default', tools: 0, on_count: 0, on_in: 0, projects: 0, tool_list: [] };
const VIEW_ADDED = { ...VIEW, gateways: [{ ...VIEW.gateways[0], servers: [...VIEW.gateways[0].servers, STATUS_SERVER] }] };
const STATUS_BLOCK = 'block:preview:test-status';
const STATUS_HELD = 'block:held:kitden:test-status';
// Where a block shows: its x and y on the map.
const at = (n) => n.style.translate.split(' ').map(parseFloat);
// One frame of the clock, `ms` after the last.
const frame = (ms) => { now += ms; const run = frames; frames = []; for (const fn of run) fn(now); };
// The Add panel open beside the map, read with `servers`. Its rows follow the tray as panel.js
// has them do (initPanel).
const { syncTray } = await import('../../src/kitden/web/static/js/details.js');
const { onTray } = await import('../../src/kitden/web/static/js/tray.js');
let followed = false;
async function addPanel(box, servers = MARKET) {
  if (!followed) onTray(syncTray);
  followed = true;
  queue('/api/market-servers', { status: 200, json: { servers } });
  await openAdd({ from: node(box, 'add:servers') });
  await done();
}
const addRowOf = (name) => walk(pages['#drawer']).find((n) => n.dataset.focus === `add-row:${MARKET.find((r) => r.name === name).id}`);
const statusOf = (name) => addRowOf(name).children[3];
// A click on the panel's row of `name`, and the preview's answer (`id`).
async function clickAdd(name, id) {
  queue(PREVIEW, batch(id));
  addRowOf(name).listeners.click[0]();
  await done();
  await done();
}
async function addCleanUp() {
  closePanel({ instant: true, focus: false });
  await cancelTray();
  Object.assign(data, { gateway: VIEW });
  undone.id = null;
  reducedMotion.matches = false;
  redraw();
  settle();
}

test('a click grows it from the gateway and a take-out shrinks it back', async (t) => {
  const box = freshMap();
  t.after(addCleanUp);
  await addPanel(box);
  const [gx, gy] = at(node(box, 'block:gateway:kitden'));
  const local = node(box, 'block:held:kitden:files');
  const [, localWas] = at(local);
  await clickAdd('test-status', 'add1');
  assert.equal(statusOf('test-status').textContent, 'In preview');
  const shown = node(box, STATUS_BLOCK);
  // It starts at .4 of its size, unseen, on the middle of the gateway's right side ...
  assert.deepEqual([at(shown), shown.style.transform, shown.style.opacity], [[gx + 150 - 85, gy + 62 - 30], 'scale(0.4)', '0']);
  // ... and grows to its place in 260 ms, while files, in the Local group below, makes room as long.
  frame(259);
  assert.notEqual(shown.style.transform, '');
  assert.ok(at(local)[1] > localWas);
  const localAt = at(local)[1];
  frame(1);
  assert.deepEqual([shown.style.transform, shown.style.opacity], ['', '']);
  assert.ok(at(local)[1] > localAt);
  const place = at(shown);
  assert.match(linkLine(box, 'gateway:kitden>preview:test-status').className, /\bpreview\b/);
  // A press on it takes it out: it shrinks back into the gateway in 180 ms, and the blocks below
  // move up in 260 ms. Focus that was on it goes to the gateway.
  shown.focus();
  shown.listeners.click[0]();
  await done();
  await done();
  frame(179);
  assert.ok(shown.parentNode);
  frame(1);
  assert.equal(node(box, STATUS_BLOCK), null);
  assert.deepEqual([at(shown), shown.style.transform, shown.style.opacity], [[gx + 150 - 85, gy + 62 - 30], 'scale(0.4)', '0']);
  assert.notEqual(at(local)[1], localWas);
  frame(80);
  assert.equal(at(local)[1], localWas);
  assert.equal(document.activeElement, node(box, 'block:gateway:kitden'));
  assert.equal(statusOf('test-status').textContent, '');
  // The bar's Cancel takes it out the same way.
  await clickAdd('db-query', 'add1b');
  settle();
  // db-query is local: it shows in the Local group, under files, not where test-status was.
  const [px, py] = at(node(box, 'block:preview:db-query'));
  const [fx, fy] = at(local);
  assert.deepEqual([px, py > fy, py !== place[1]], [fx, true, true]);
  await cancelTray();
  frame(180);
  assert.equal(node(box, 'block:preview:db-query'), null);
  settle();
});

// The tray applied with test-status in it, and the page then reads Kitden again (dock.js land).
async function appliedAdd(box) {
  await clickAdd('test-status', 'add2');
  settle();
  queue('/api/changes/add2/apply', { status: 200, json: { id: 'add2', state: 'verified', error: null } });
  await applyTray();
  assert.equal(tray.phase, 'applied');
}
async function readAgain(view, servers) {
  queue('/api/market-servers', { status: 200, json: { servers } });
  Object.assign(data, { gateway: view });
  redraw();
}

// Review Focus
test("Apply lands it and the open panel's row says Added, with focus kept", async (t) => {
  const box = freshMap();
  t.after(addCleanUp);
  await addPanel(box);
  await appliedAdd(box);
  const place = at(node(box, STATUS_BLOCK));
  const row = addRowOf('test-status');
  row.focus();
  await readAgain(VIEW_ADDED, MARKET_HELD);
  endApplied();
  // The server takes the preview's place: it starts where the preview shows, joined by a solid link.
  assert.equal(node(box, STATUS_BLOCK), null);
  const held = node(box, STATUS_HELD);
  assert.deepEqual(at(held), place);
  // (The preview's own dashed link fades out on the same line meanwhile.)
  const hit = node(box, 'link:gateway:kitden>held:kitden:test-status');
  const lines = walk(box).filter((n) => n.tagName === 'path' && /\blink\b/.test(n.className) && n.getAttribute('d') === hit.getAttribute('d'));
  assert.deepEqual(lines.map((n) => /\bpreview\b/.test(n.className)).sort(), [false, true]);
  settle();
  await done();
  // The panel stays open; its row says Added, sliding in from 6 px (280 ms CALM); focus stays.
  assert.equal(isPanelOpen(), true);
  assert.deepEqual([statusOf('test-status').textContent, document.activeElement], ['Added', row]);
  assert.ok(row.classList.contains('done') && row.classList.contains('off'));
  assert.deepEqual(lastMotion(statusOf('test-status')), [[{ opacity: 0, transform: 'translateX(6px)' }, { opacity: 1, transform: 'none' }], 280, CALM]);
  // The page read the marketplaces again; the row is still Added, with no second motion.
  assert.equal(statusOf('test-status').animations.length, 1);
});

test('Undo takes it out and the row is free again', async (t) => {
  const box = freshMap();
  t.after(addCleanUp);
  await addPanel(box);
  await appliedAdd(box);
  await readAgain(VIEW_ADDED, MARKET_HELD);
  endApplied();
  settle();
  await done();
  const [gx, gy] = at(node(box, 'block:gateway:kitden'));
  const row = addRowOf('test-status');
  row.focus();
  // The Undo: the server shrinks back into the gateway (180 ms IN3), as its preview would.
  undone.id = 'add2';
  await readAgain(VIEW, MARKET);
  const held = node(box, STATUS_HELD);
  frame(179);
  assert.ok(held.parentNode);
  frame(1);
  assert.equal(node(box, STATUS_HELD), null);
  assert.deepEqual([at(held), held.style.transform, held.style.opacity], [[gx + 150 - 85, gy + 62 - 30], 'scale(0.4)', '0']);
  settle();
  await done();
  // The panel's row is free again, and focus stays on it.
  assert.deepEqual([statusOf('test-status').textContent, row.classList.contains('off'), document.activeElement], ['', false, row]);
});

test('a project switch keeps the preview block', async (t) => {
  const box = freshMap();
  t.after(async () => { pickProject('', VIEW); await addCleanUp(); });
  await addPanel(box);
  await clickAdd('test-status', 'add3');
  settle();
  const shown = node(box, STATUS_BLOCK);
  pickProject('atlas', ATLAS);
  settle();
  assert.equal(node(box, STATUS_BLOCK), shown);
  assert.deepEqual([shown.style.transform, shown.style.opacity], ['', '']);
  assert.ok(linkLine(box, 'gateway:kitden>preview:test-status'));
  assert.deepEqual([isPanelOpen(), statusOf('test-status').textContent], [true, 'In preview']);
});

test('under reduced motion each lands at once', async (t) => {
  const box = freshMap();
  t.after(addCleanUp);
  reducedMotion.matches = true;
  await addPanel(box);
  const still = () => walk(box).every((n) => n.style.opacity !== '0' && !/scale/.test(n.style.transform || ''));
  // A click: the block is at its place at once.
  await clickAdd('test-status', 'add4');
  assert.ok(node(box, STATUS_BLOCK) && still());
  // A take-out: it is gone at once.
  node(box, STATUS_BLOCK).listeners.click[0]();
  await done();
  await done();
  assert.equal(node(box, STATUS_BLOCK), null);
  // Apply: the server is there at once, and the row says Added with no motion.
  await appliedAdd(box);
  await readAgain(VIEW_ADDED, MARKET_HELD);
  endApplied();
  await done();
  assert.ok(node(box, STATUS_HELD) && still());
  assert.deepEqual([statusOf('test-status').textContent, statusOf('test-status').animations.length], ['Added', 0]);
  // Undo: it is gone at once, and the row is free.
  undone.id = 'add2';
  await readAgain(VIEW, MARKET);
  await done();
  assert.ok(!node(box, STATUS_HELD) && still());
  assert.equal(statusOf('test-status').textContent, '');
});

// Phase 5 final wave
test('Apply fails: the row still says In preview and the preview block stays', async (t) => {
  const box = freshMap();
  t.after(addCleanUp);
  await addPanel(box);
  await clickAdd('test-status', 'add5');
  settle();
  queue('/api/changes/add5/apply', { status: 200, json: { id: 'add5', state: 'restored', error: 'The original settings were restored.' } });
  await applyTray();
  settle();
  assert.equal(tray.phase, 'failed');
  assert.equal(statusOf('test-status').textContent, 'In preview');
  assert.ok(node(box, STATUS_BLOCK));
  assert.equal(node(box, STATUS_HELD), null);
});

test('the More door lets go of the selection, as + Add does, and an empty click leaves the panel', async (t) => {
  const box = freshMap();
  t.after(addCleanUp);
  const kitden = VIEW.gateways[0];
  const more = gatewayCard(kitden, { view: VIEW, setup: [], clients: [] }).more.find((m) => m.label === ADD_SERVER);
  const selected = () => walk(box).filter((n) => /\bselected\b/.test(n.className)).length;
  for (const door of ['more', 'plus']) {
    press(box, 'block:gateway:kitden');
    settle();
    assert.equal(selected(), 1, door);
    queue('/api/market-servers', { status: 200, json: { servers: MARKET } });
    queue('/api/discovery/sources', { status: 200, json: { sources: [], offline: true } });
    if (door === 'more') await more.run();
    else press(box, 'add:servers');
    await done();
    const local = walk(pages['#drawer']).find((n) => n.tagName === 'BUTTON' && n.textContent === 'On this Mac');
    local.listeners.click[0]();
    await done();
    settle();
    assert.deepEqual([selected(), panelState.current && panelState.current.type], [0, 'add'], door);
    // A click on empty map has nothing to let go of: the panel stays.
    for (const fn of box.listeners.click) fn({ target: box });
    settle();
    assert.deepEqual([isPanelOpen(), panelState.current && panelState.current.type], [true, 'add'], door);
    closePanel({ instant: true, focus: false });
  }
});

test('an Undo with the panel closed frees the Added mark at the next read', async (t) => {
  const box = freshMap();
  t.after(addCleanUp);
  await addPanel(box);
  await appliedAdd(box);
  await readAgain(VIEW_ADDED, MARKET_HELD);
  endApplied();
  settle();
  await done();
  assert.equal(wasAdded('test-status'), true);
  // The panel is closed, so no panel read frees the mark; the page's next read of Kitden does.
  closePanel({ instant: true, focus: false });
  Object.assign(data, { gateway: VIEW });
  redraw();
  assert.equal(wasAdded('test-status'), false);
});

// The count of a server is its own control: it opens or folds the server and nothing else.
const countOf = (box) => node(box, 'count:held:kitden:files');
const toolShown = (box) => Boolean(node(box, 'block:tool:files/read_file'));
const countCleanUp = async () => {
  closePanel({ instant: true, focus: false });
  await done();
  settle();
  reducedMotion.matches = false;
  Object.assign(state, { selected: null });
  if (toolShown(map())) countOf(map()).listeners.click[0]();
  settle();
};

test('the count unfolds and folds a server: nothing is selected and no Details open', async (t) => {
  t.after(countCleanUp);
  const box = freshMap();
  const count = countOf(box);
  count.focus();
  count.listeners.click[0]();
  settle();
  assert.equal(toolShown(box), true);
  assert.deepEqual([count.getAttribute('aria-expanded'), count.getAttribute('aria-label'), countOf(box) === count, document.activeElement === count], ['true', 'Hide tools', true, true]);
  assert.ok(!walk(box).some((n) => /\bselected\b/.test(n.className)));
  await done();
  assert.deepEqual([isPanelOpen(), state.selected], [false, null]);
  count.listeners.click[0]();
  settle();
  assert.deepEqual([toolShown(box), count.getAttribute('aria-label'), isPanelOpen(), document.activeElement === count], [false, 'Show 1 tool', false, true]);
});

test('during a search the count of a server the search opened folds it', async (t) => {
  t.after(() => {
    state.q = '';
    return countCleanUp();
  });
  state.q = 'read_file';
  const box = freshMap();
  const count = countOf(box);
  assert.deepEqual([toolShown(box), count.getAttribute('aria-label')], [true, 'Hide tools']);
  count.focus();
  count.listeners.click[0]();
  settle();
  assert.deepEqual([toolShown(box), count.getAttribute('aria-label'), isPanelOpen()], [false, 'Show 1 tool', false]);
  // A second press opens it again.
  count.listeners.click[0]();
  settle();
  assert.equal(toolShown(box), true);
  state.q = '';
});

test('a count fold during a search stays folded after a full redraw, until the text changes', async (t) => {
  t.after(() => {
    state.q = '';
    return countCleanUp();
  });
  // A draw with no search ends any fold of an earlier one; then the search begins.
  state.q = '';
  freshMap();
  state.q = 'read_file';
  const box = freshMap();
  countOf(box).listeners.click[0]();
  settle();
  assert.equal(toolShown(box), false);
  // The page draws again whole, as a reload does: the server stays folded.
  main.replaceChildren();
  renderGateway(main);
  settle();
  assert.equal(toolShown(map()), false);
  // Another search text opens it again.
  state.q = 'read_fil';
  main.replaceChildren();
  renderGateway(main);
  settle();
  assert.equal(toolShown(map()), true);
});

test('a press on the block itself still opens Details and unfolds, as before', async (t) => {
  t.after(countCleanUp);
  const box = freshMap();
  press(box, 'block:held:kitden:files');
  await done();
  settle();
  assert.equal(toolShown(box), true);
  assert.deepEqual([isPanelOpen(), panelState.current], [true, { type: 'held', name: 'files' }]);
  assert.match(node(box, 'block:held:kitden:files').className, /\bselected\b/);
});

test('the count keeps the selection and its Details as they were', async (t) => {
  t.after(countCleanUp);
  const box = freshMap();
  press(box, 'block:held:kitden:tracker');
  await done();
  settle();
  const details = panelState.current;
  assert.deepEqual([isPanelOpen(), details.name], [true, 'tracker']);
  countOf(box).listeners.click[0]();
  settle();
  await done();
  assert.equal(toolShown(box), true);
  assert.deepEqual([isPanelOpen(), panelState.current], [true, details]);
  assert.match(node(box, 'block:held:kitden:tracker').className, /\bselected\b/);
  assert.doesNotMatch(node(box, 'block:held:kitden:files').className, /\bselected\b/);
});

test('folding a server whose tool is selected lets the selection go', async (t) => {
  t.after(countCleanUp);
  const box = freshMap();
  press(box, 'block:held:kitden:files');
  await done();
  settle();
  press(box, 'block:tool:files/read_file');
  await done();
  settle();
  assert.match(node(box, 'block:tool:files/read_file').className, /\bselected\b/);
  countOf(box).listeners.click[0]();
  settle();
  await done();
  assert.deepEqual([toolShown(box), isPanelOpen()], [false, false]);
  assert.ok(!walk(box).some((n) => /\bselected\b/.test(n.className)));
});

test('under reduced motion the count lands at once', async (t) => {
  t.after(countCleanUp);
  const box = freshMap();
  reducedMotion.matches = true;
  countOf(box).listeners.click[0]();
  // No frame is needed: the tools are in their places, whole.
  assert.equal(frames.length, 0);
  const read = node(box, 'block:tool:files/read_file');
  assert.ok(read);
  assert.equal(read.style.opacity, '');
  assert.equal(countOf(box).getAttribute('aria-expanded'), 'true');
});
