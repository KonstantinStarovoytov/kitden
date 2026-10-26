import assert from 'node:assert/strict';
import { test } from 'node:test';

// The shared add panel (add-panel.js) with a config of its own, in a small browser: elements with
// parents, the page's fixed parts and a wide window (Details float). It shows what the panel does
// for any page; gateway-add.test.mjs and library-add.test.mjs show each page's own panel.
globalThis.matchMedia = (query) => ({ matches: query.includes('min-width'), addEventListener() {} });
delete globalThis.navigator;
globalThis.requestAnimationFrame = () => 0;
globalThis.MutationObserver = class { observe() {} };
globalThis.addEventListener = () => {};
// The window a drag listens to for a blur.
globalThis.window = { addEventListener() {}, removeEventListener() {} };

const walk = (root) => root.children.flatMap((n) => [n, ...walk(n)]);
const motions = [];
function element(tagName) {
  let names = [];
  const attributes = new Map();
  const style = { setProperty(name, value) { style[name] = value; }, removeProperty(name) { delete style[name]; } };
  const node = {
    tagName, style, dataset: {}, children: [], parentNode: null, textContent: '', listeners: {}, hidden: false, offsetLeft: 0, offsetTop: 0, offsetWidth: 0, offsetHeight: 0,
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
    getAttribute: (name) => (attributes.has(name) ? attributes.get(name) : null),
    removeAttribute(name) { attributes.delete(name); },
    append(...nodes) { for (const n of nodes) node.insertBefore(typeof n === 'string' ? Object.assign(element('#text'), { textContent: n }) : n, null); },
    prepend(...nodes) { const first = node.children[0] || null; for (const n of nodes) node.insertBefore(n, first); },
    insertBefore(n, ref) {
      if (n.parentNode) n.parentNode.children.splice(n.parentNode.children.indexOf(n), 1);
      node.children.splice(ref ? node.children.indexOf(ref) : node.children.length, 0, n);
      n.parentNode = node;
      return n;
    },
    remove() { if (node.parentNode) node.parentNode.children.splice(node.parentNode.children.indexOf(node), 1); node.parentNode = null; },
    replaceChildren(...nodes) { for (const n of [...node.children]) n.parentNode = null; node.children = []; node.append(...nodes); },
    contains(other) { for (let at = other; at; at = at.parentNode) if (at === node) return true; return false; },
    focus() { globalThis.document.activeElement = node; },
    matches: () => false,
    querySelector: (selector) => (selector === ':scope > .ink' ? node.children.find((n) => n.className === 'ink') || null : null),
    querySelectorAll(selector) {
      const key = selector.match(/^\[data-(\w+)\]$/);
      return key ? walk(node).filter((n) => n.dataset[key[1]] !== undefined) : [];
    },
    getBoundingClientRect: () => ({ top: 0, bottom: 0, left: 0, right: 1345 }),
    setPointerCapture() {},
    // A copy of the node and what it holds, with no listeners.
    cloneNode(deep) {
      const copy = element(tagName);
      copy.className = node.className;
      Object.assign(copy.dataset, node.dataset);
      for (const [name, value] of attributes) copy.setAttribute(name, value);
      copy.textContent = node.textContent;
      if (deep) copy.append(...node.children.map((n) => n.cloneNode(true)));
      return copy;
    },
    addEventListener(type, fn) { (node.listeners[type] ||= []).push(fn); },
    animate(keyframes, options) { motions.push({ node, keyframes, options }); return { finished: Promise.resolve(), cancel() {} }; },
    getAnimations: () => [],
  };
  return node;
}
const pages = {};
for (const id of ['#main', '#drawer', '#scrim', '#topbar', '#content', '#dock']) {
  pages[id] = element('DIV');
  pages[id].root = true;
}
// What the document hears, by type.
const docHeard = {};
globalThis.document = {
  hidden: false, activeElement: null, body: element('BODY'),
  createElement: (tag) => element(tag.toUpperCase()), createElementNS: (namespace, tag) => element(tag),
  querySelector: (selector) => pages[selector] ?? null, querySelectorAll: () => [], getElementById: () => null,
  addEventListener(type, fn) { (docHeard[type] ||= []).push(fn); },
  removeEventListener(type, fn) { docHeard[type] = (docHeard[type] || []).filter((f) => f !== fn); },
  documentElement: { classList: { add() {}, remove() {} }, style: { setProperty() {}, removeProperty() {} } },
};

globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({}) });

const { matchRows, openAddPanel, shownList } = await import('../../src/kitden/web/static/js/add-panel.js');
const { closePanel, initPanel, isPanelOpen, panelState } = await import('../../src/kitden/web/static/js/panel.js');
const { reducedMotion } = await import('../../src/kitden/web/static/js/motion.js');
const { state } = await import('../../src/kitden/web/static/js/store.js');
state.view = 'library';
initPanel();

const ROWS = [
  { id: 'a', kind: 'fruit', name: 'Apple', marketplace: 'north' },
  { id: 'b', kind: 'nut', name: 'Brazil', marketplace: 'north' },
  { id: 'c', kind: 'fruit', name: 'Cherry', marketplace: 'south', gone: true },
];
// A page's config: rows of two kinds, a press that counts, and a door to more under the list.
function config(rows = ROWS) {
  const pressed = [];
  const dragged = [];
  const waiting = new Set();
  const done = new Set();
  return {
    pressed, dragged, waiting, done,
    type: 'test-add', kicker: 'Test', title: 'Add a thing', foot: 'Click one.', noMatch: 'Nothing matches.', none: 'Nothing here.',
    pill: [['all', 'All'], ['fruit', 'Fruit'], ['nut', 'Nuts']], addKey: 'add:things',
    status: { added: 'Added', preview: 'In preview' },
    read: async () => rows,
    letGo() {},
    words: (row, inTray) => (done.has(row.id) ? { status: 'Added', off: true, line: row.kind } : row.gone ? { status: '', off: true, line: 'Gone' } : { status: inTray ? 'In preview' : '', off: false, line: row.kind }),
    icon: () => 'puzzle',
    key: (row) => `thing:${row.id}`,
    waits: (row) => waiting.has(row.id),
    press: (row) => { pressed.push(row.id); },
    drag: (event, row) => { dragged.push(row.id); },
    after: () => [Object.assign(element('BUTTON'), { textContent: 'More…' })],
  };
}

const wait = (ms = 0) => new Promise((resolve) => setTimeout(resolve, ms));
const text = (node) => (node.children.length ? node.children.map(text).join(' ') : node.textContent).trim();
const drawer = pages['#drawer'];
const find = (fn) => walk(drawer).filter(fn);
const rows = () => find((n) => n.className.split(' ').includes('res'));
const shown = () => rows().filter((n) => !n.hidden);
const pill = () => find((n) => n.className === 'seg sm')[0].children.filter((n) => n.tagName === 'BUTTON');
const fire = (node, type, event = {}) => { for (const fn of node.listeners[type] || []) fn({ preventDefault() {}, stopPropagation() {}, target: node, ...event }); };
const press = async (node) => { fire(node, 'click'); await wait(); await wait(); };

async function open(page) {
  await openAddPanel(page, { from: null });
  await wait(200);
}
function done() {
  closePanel({ instant: true, focus: false });
  reducedMotion.matches = false;
  motions.length = 0;
}

test('the search and the pill keep the rows of one kind whose name matches', () => {
  assert.deepEqual(matchRows(ROWS, ' r', 'all').map((r) => r.id), ['b', 'c']);
  assert.deepEqual(matchRows(ROWS, '', 'fruit').map((r) => r.id), ['a', 'c']);
  assert.deepEqual(matchRows(ROWS, 'north', 'all'), []);
});

test("a page's config gives the words, the groups, the pill and what goes under the list", async () => {
  const page = config();
  await open(page);
  try {
    assert.deepEqual(panelState.current, { type: 'test-add' });
    const [head, body, foot] = drawer.children;
    assert.deepEqual([text(head.children[0]), text(head.children[1]), text(foot)], ['Test Close', 'Add a thing', 'Click one.']);
    assert.deepEqual(find((n) => n.className === 'add-group').map(text), ['north', 'south']);
    assert.deepEqual(pill().map((b) => b.textContent), ['All', 'Fruit', 'Nuts']);
    assert.equal(body.children.at(-1).textContent, 'More…');
    assert.ok(shownList(page));
    assert.equal(shownList(config()), null);
    await press(pill()[2]);
    assert.deepEqual(shown().map((r) => r.dataset.focus), ['add-row:b']);
  } finally {
    done();
  }
});

test("a press runs the page's press, a greyed row has none, and a free row may drag", async () => {
  const page = config();
  await open(page);
  try {
    const [apple, , cherry] = rows();
    await press(apple);
    await press(cherry);
    assert.deepEqual(page.pressed, ['a']);
    assert.deepEqual([cherry.classList.contains('off'), cherry.children[2].children[1].textContent], [true, 'Gone']);
    fire(apple, 'pointerdown', { button: 0 });
    fire(cherry, 'pointerdown', { button: 0 });
    assert.deepEqual(page.dragged, ['a']);
    // While its change waits it says so and does not drag.
    page.waiting.add('a');
    shownList(page).paint();
    assert.deepEqual([apple.children[3].textContent, apple.classList.contains('on')], ['In preview', true]);
    fire(apple, 'pointerdown', { button: 0 });
    assert.deepEqual(page.dragged, ['a']);
    // A new read that says it was added: Added slides in from 6 px (280 ms CALM).
    page.waiting.clear();
    page.done.add('a');
    motions.length = 0;
    shownList(page).update(ROWS);
    assert.deepEqual([apple.children[3].textContent, apple.classList.contains('done')], ['Added', true]);
    assert.deepEqual(motions.filter((m) => m.node === apple.children[3]).map((m) => m.options.duration), [280]);
  } finally {
    done();
  }
});

test('no rows says the page\'s none, and a failed read offers Try again', async () => {
  await open(config([]));
  try {
    assert.deepEqual(find((n) => n.className === 'muted add-none').map((n) => [n.hidden, n.textContent]), [[false, 'Nothing here.']]);
    closePanel({ instant: true, focus: false });
    const page = config();
    page.read = async () => null;
    await open(page);
    assert.deepEqual(drawer.children[1].children.map((n) => n.textContent), ['Could not read the marketplaces.', 'Try again']);
    assert.equal(isPanelOpen(), true);
  } finally {
    done();
  }
});

test('under reduced motion it opens at once and nothing moves', async () => {
  reducedMotion.matches = true;
  motions.length = 0;
  const page = config();
  try {
    await openAddPanel(page, { from: null });
    assert.equal(rows().length, 3);
    await press(pill()[1]);
    await press(pill()[0]);
    assert.deepEqual(motions, []);
  } finally {
    done();
  }
});
