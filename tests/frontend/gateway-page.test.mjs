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
for (const id of ['#main', '#drawer', '.shell', '#dock']) {
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
const { data, setRenderer, state } = await import('../../src/kitden/web/static/js/store.js');
const { addToTray, cancelTray } = await import('../../src/kitden/web/static/js/tray.js');

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
