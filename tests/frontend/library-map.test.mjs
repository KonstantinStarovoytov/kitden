import assert from 'node:assert/strict';
import { test } from 'node:test';

// The Library's map drawn in a small browser (as in gateway-page.test.mjs): elements, the page's
// fixed parts, and frames and a clock that only the test moves.
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
delete globalThis.navigator;
let now = 0;
let frames = [];
Object.defineProperty(globalThis, 'performance', { value: { now: () => now, mark() {}, measure() {}, getEntriesByName: () => [] }, configurable: true, writable: true });
globalThis.requestAnimationFrame = (fn) => frames.push(fn);
const tick = (ms) => { now += ms; const run = frames; frames = []; for (const fn of run) fn(now); };
const settle = () => { while (frames.length) tick(10000); };
// Every motion ends, then what waits for its end runs, and its motions end too.
const flush = async () => { settle(); await new Promise((done) => setImmediate(done)); settle(); };
globalThis.ResizeObserver = class { observe() {} disconnect() {} };
globalThis.MutationObserver = class { observe() {} };
globalThis.innerWidth = 1440;
globalThis.getComputedStyle = () => ({ strokeDasharray: 'none', strokeOpacity: '1', paddingLeft: '0', paddingRight: '0' });
globalThis.localStorage = { getItem: () => null, setItem() {} };

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
    tagName, style, dataset: {}, children: [], parentNode: null, textContent: '', listeners: {}, animations: [], offsetLeft: 0, offsetTop: 0, offsetWidth: 0, offsetHeight: 0,
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
    querySelector: (selector) => (selector === ':scope > .ink' ? node.children.find((n) => n.classList.contains('ink')) || null : null),
    querySelectorAll: () => [],
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
const hintLine = element('P');
hintLine.hidden = true;
globalThis.document = {
  hidden: false, activeElement: null, body: element('BODY'),
  createElement: (tag) => element(tag.toUpperCase()), createElementNS: (namespace, tag) => element(tag),
  querySelector: (selector) => pages[selector] ?? null, querySelectorAll: () => [], getElementById: (id) => (id === 'hint' ? hintLine : null),
  addEventListener() {}, removeEventListener() {},
  documentElement: { classList: { add() {}, remove() {} }, style: { setProperty() {}, removeProperty() {} } },
};
globalThis.fetch = () => new Promise(() => {});

const { libraryMode, libraryTree, LIBRARY_COLUMNS } = await import('../../src/kitden/web/static/js/library-map.js');
const { renderLibrary } = await import('../../src/kitden/web/static/js/library.js');
const { findChip, layoutTree } = await import('../../src/kitden/web/static/js/map.js');
const { data, hashFor, libraryShows, parseHash, state } = await import('../../src/kitden/web/static/js/store.js');
const { setHint } = await import('../../src/kitden/web/static/js/parts.js');
const { reducedMotion } = await import('../../src/kitden/web/static/js/motion.js');

// The medium sample's answer, cut short (views/library_map.py).
const none = { skills: [], commands: [], agents: [], hooks: [], mcp_servers: [] };
const plugin = (id, name, fields) => ({ id, name, kind: 'plugin', plugin: `${name}@demo-market`, by: {}, through: {}, items: {}, here: false, source: 'demo-market', technical: {}, ...fields });
const own = (id, name, kind, fields) => ({ id, name, kind, by: {}, through: {}, items: {}, here: false, source: '', technical: {}, ...fields });
const MEDIUM = {
  clients: [
    { id: 'claude_code', name: 'Claude Code', state: 'on', words: 'Connected' },
    { id: 'codex', name: 'Codex', state: 'on', words: 'Connected' },
    { id: 'cursor', name: 'Cursor', state: 'via', words: 'Via Claude Code' },
  ],
  groups: [
    { key: 'marketplace:demo-market', name: 'demo-market', icon: 'store', kind: 'marketplace', items: [
      plugin('p1', 'pr-review', { by: { claude_code: 'off', cursor: 'off' }, inside: { ...none, mcp_servers: ['pr-index'] }, count: 1 }),
      plugin('p2', 'superpowers', { by: { claude_code: 'on', cursor: 'on' }, through: { cursor: 'claude_code' }, inside: { ...none, skills: ['brainstorm', 'plan'], commands: ['ship'] }, count: 3 }),
      plugin('p3', 'test-helper', { by: { codex: 'on', cursor: 'via' }, inside: { ...none, skills: ['fixtures'] }, count: 1 }),
    ] },
    { key: 'other', name: 'Other plugins', icon: 'puzzle', kind: 'other', items: [plugin('p4', 'calendar', { by: { codex: 'unknown' } })] },
    { key: 'skills', name: 'Your skills', icon: 'user-round', kind: 'skills', items: [
      own('s1', 'release-notes', 'skill', { by: { claude_code: 'on', cursor: 'on' }, through: { cursor: 'claude_code' }, here: true }),
      own('s2', 'ui-polish', 'skill', { by: { cursor: 'on' } }),
    ] },
    { key: 'settings', name: 'Your settings', icon: 'settings', kind: 'settings', items: [own('h1', 'PreToolUse: Bash', 'hook', { by: { claude_code: 'on' } })] },
  ],
};
// The large sample's shape: 30 plugins in one marketplace, the first with twenty skills, and 127 skills.
const LARGE = {
  clients: MEDIUM.clients,
  groups: [
    { key: 'marketplace:bench-market', name: 'bench-market', icon: 'store', kind: 'marketplace', items: Array.from({ length: 30 }, (_, i) => {
      const skills = i === 0 ? Array.from({ length: 20 }, (__, k) => `plugin-00-skill-${String(k + 1).padStart(2, '0')}`) : [`plugin-${i}-skill`];
      return plugin(`b${i}`, `plugin-${String(i).padStart(2, '0')}`, { by: { claude_code: 'on' }, inside: { ...none, skills }, count: skills.length });
    }) },
    { key: 'skills', name: 'Your skills', icon: 'user-round', kind: 'skills', items: Array.from({ length: 127 }, (_, i) => own(`k${i}`, `bench-skill-${String(i).padStart(3, '0')}`, 'skill', { by: { codex: 'on' } })) },
  ],
};

const main = pages['#main'];
const map = () => main.children.find((n) => n.classList.contains('map')) || null;
const node = (box, key) => walk(box).find((n) => n.dataset.focus === key) || null;
const byId = (model) => new Map(model.blocks.map((b) => [b.id, b]));
const texts = (root) => walk(root).map((n) => n.textContent).filter(Boolean);

function showMap(sample = MEDIUM, { q = '' } = {}) {
  Object.assign(data, { libraryMap: sample, projects: [] });
  data.scope.libraryMap = '';
  Object.assign(state, { view: 'library', mode: 'map', project: '', q, selected: null });
  main.replaceChildren();
  setHint(''); // as app.js does before each draw
  const found = renderLibrary(main);
  return { box: map(), found };
}

test('the head has the tabs, the lede, the scope bar and Map | List', () => {
  showMap();
  settle();
  const [head, lede, tabs, scope] = main.children;
  assert.equal(head.className, 'page-head');
  assert.equal(head.children[0].textContent, 'Library');
  const seg = head.children.at(-1);
  assert.deepEqual(seg.children.filter((n) => n.tagName === 'BUTTON').map((n) => [n.textContent, n.getAttribute('aria-pressed')]), [['Map', 'true'], ['List', 'false']]);
  assert.equal(lede.textContent, 'Follow the source. Connect only what you need.');
  assert.equal(tabs.className, 'seg sm map-tabs');
  assert.deepEqual(tabs.children.filter((n) => n.tagName === 'BUTTON').map((n) => [n.textContent, n.getAttribute('aria-pressed')]), [['Plugins and skills', 'true'], ['Instructions', 'false']]);
  assert.ok(texts(scope).includes('Shared setup · project overrides stay separate'));
  assert.ok(map());
  assert.equal(hintLine.hidden, false);
  assert.equal(hintLine.children.at(-1).textContent, 'Point at a link for its Details · click a plugin to see what it holds · drag a plugin onto a client to add it there');
});

test('in a project the scope bar names it with a folder', () => {
  Object.assign(data, { libraryMap: MEDIUM, projects: [{ id: 'a', path: '/home/work/atlas' }] });
  data.scope.libraryMap = 'a';
  Object.assign(state, { view: 'library', mode: 'map', project: 'a', q: '', selected: null });
  main.replaceChildren();
  renderLibrary(main);
  const scope = main.children[3];
  assert.equal(scope.className, 'scope-bar project');
  assert.ok(texts(scope).includes('Project atlas'));
  state.project = '';
});

test("List shows today's table and keeps its six tabs", () => {
  Object.assign(state, { view: 'library', mode: 'list', kind: 'mcp_server', project: '', q: '' });
  main.replaceChildren();
  setHint('');
  assert.equal(renderLibrary(main), null);
  const [head] = main.children;
  assert.equal(head.children[0].textContent, 'Library');
  assert.equal(head.children.at(-1).children.find((n) => n.textContent === 'List').getAttribute('aria-pressed'), 'true');
  assert.equal(main.children[1].textContent, 'What each client loads, and what you can add to it. Based on saved settings.');
  const tablist = main.children.find((n) => n.getAttribute('role') === 'tablist');
  assert.deepEqual(tablist.children.filter((n) => n.tagName === 'BUTTON').map((n) => n.dataset.kind), ['mcp_server', 'plugin', 'skill', 'hook', 'marketplace', 'instructions']);
  assert.equal(map(), null);
  assert.equal(hintLine.hidden, true);
});

test('the page opens in List past 15 plugins and skills, unless the address says', () => {
  Object.assign(state, { mode: '', project: '' });
  data.scope.libraryMap = '';
  data.libraryMap = MEDIUM;
  assert.equal(libraryMode(), 'map');
  data.libraryMap = LARGE;
  assert.equal(libraryMode(), 'list');
  state.mode = 'map';
  assert.equal(libraryMode(), 'map');
});

test('the map draws clients, captions in source order, plugin cards with n items, skill and hook rows', () => {
  const model = libraryTree(MEDIUM);
  assert.deepEqual(LIBRARY_COLUMNS.map((c) => [c.id, c.caption, c.w, c.h]), [['clients', 'Clients', 150, 54], ['plugins', 'Plugins and skills', 180, 60], ['inside', 'Inside', 200, 34]]);
  const groups = model.blocks.filter((b) => b.kind === 'group');
  assert.deepEqual(groups.map((g) => [g.name, g.icon]), [['demo-market', 'store'], ['Other plugins', 'puzzle'], ['Your skills', 'user-round'], ['Your settings', 'settings']]);
  const blocks = byId(model);
  const client = blocks.get('client:cursor');
  assert.deepEqual([client.name, client.meta, client.lamp], ['Cursor', 'Via Claude Code', 'on']);
  const card = blocks.get('item:p2');
  assert.deepEqual([card.kind, card.name, card.meta, card.lamp, card.count], ['plugin', 'superpowers', '3 items', 'on', 3]);
  assert.deepEqual([blocks.get('item:p1').meta, blocks.get('item:p1').lamp], ['1 item', 'off']);
  // A plugin whose state Kitden does not know has an Unknown lamp and no link; with nothing read inside it says its state.
  const unknown = blocks.get('item:p4');
  assert.deepEqual([unknown.lamp, unknown.meta, unknown.count], ['unk', 'Unknown', undefined]);
  assert.ok(!model.links.some((l) => l.to === 'item:p4'));
  const skill = blocks.get('item:s1');
  assert.deepEqual([skill.kind, skill.h, skill.label, skill.tag, skill.lamp], ['skill', 34, { icon: 'sparkles', words: 'Skill' }, 'This project', 'on']);
  const hook = blocks.get('item:h1');
  assert.deepEqual([hook.kind, hook.h, hook.label], ['hook', 34, { icon: 'webhook', words: 'Hook' }]);
  // What a plugin holds is in the Inside column, joined to it; the layout shows it only while it is open.
  assert.ok(!layoutTree(model, { narrow: false }).blocks.some((b) => b.id.startsWith('part:')));
  const open = model;
  const inside = open.blocks.filter((b) => b.column === 'inside' && b.plugin.id === 'p2');
  assert.deepEqual(inside.map((b) => [b.name, b.label.words, b.label.icon]), [['brainstorm', 'Skill', 'sparkles'], ['plan', 'Skill', 'sparkles'], ['ship', 'Command', 'square-terminal']]);
  assert.ok(inside.every((b) => open.links.some((l) => l.from === 'item:p2' && l.to === b.id && l.kind === 'on')));
  assert.ok(inside.every((b) => !b.lamp && !b.state));
  // At the mockup's x: 0, 250 and 500; a group caption, then its first card under it.
  const layout = layoutTree(open, { open: new Set(['item:p2']), narrow: false });
  assert.deepEqual(layout.columns.map((c) => c.x), [0, 250, 500]);
  const at = new Map(layout.blocks.map((b) => [b.id, b]));
  assert.deepEqual(['client:claude_code', 'client:codex', 'client:cursor'].map((id) => at.get(id).y), [140, 212, 284]);
  assert.equal(at.get('group:marketplace:demo-market').y, 37);
  assert.ok(at.get('item:p2').y - at.get('item:p1').y === 64);
});

test('no block says N of M on', () => {
  for (const sample of [MEDIUM, LARGE]) {
    const model = libraryTree(sample);
    for (const block of model.blocks) assert.doesNotMatch(String(block.meta || ''), / of /, block.id);
  }
});

test('a big group and a big plugin page in place and nothing overflows', () => {
  const open = new Set(['item:b0']);
  const model = libraryTree(LARGE);
  const layout = layoutTree(model, { open, narrow: false });
  const shown = new Map(layout.blocks.map((b) => [b.id, b]));
  // Plugins and skills page five at a time, the Inside column eight at a time, each with "N more".
  assert.equal(layout.blocks.filter((b) => b.kind === 'plugin').length, 5);
  assert.equal(shown.get('more:group:marketplace:bench-market').name, '25 more');
  assert.equal(shown.get('group:marketplace:bench-market').name, 'bench-market · 1–5 of 30');
  assert.equal(layout.blocks.filter((b) => b.kind === 'skill').length, 5);
  assert.equal(shown.get('more:group:skills').name, '122 more');
  assert.equal(layout.blocks.filter((b) => b.kind === 'part').length, 8);
  assert.equal(shown.get('more:inside:item:b0').name, '12 more');
  assert.equal(shown.get('inside:item:b0').name, 'plugin-00 · 1–8 of 20');
  // Every block sits in its column, none on another, and the Inside stack never starts above 26.
  const of = (b) => model.blocks.find((m) => m.id === b.id)?.column || layout.columns.find((c) => c.x === b.x)?.id;
  for (const b of layout.blocks.filter((at) => at.kind !== 'column')) {
    const column = layout.columns.find((c) => c.id === of(b));
    assert.ok(column && b.x === column.x && b.w === column.w, b.id);
  }
  for (const column of layout.columns) {
    const mine = layout.blocks.filter((b) => b.kind !== 'column' && of(b) === column.id).sort((a, b) => a.y - b.y);
    for (let i = 1; i < mine.length; i++) assert.ok(mine[i].y >= mine[i - 1].y + mine[i - 1].h, `${mine[i - 1].id} overlaps ${mine[i].id}`);
  }
  assert.ok(layout.blocks.filter((b) => b.kind !== 'column' && of(b) === 'inside').every((b) => b.y >= 26));
});

test('Cursor via Claude Code draws a faint line or none', () => {
  const model = libraryTree(MEDIUM);
  const link = (from, to) => model.links.find((l) => l.from === from && l.to === to);
  assert.equal(link('client:claude_code', 'item:p2').kind, 'on');
  assert.equal(link('client:cursor', 'item:p2').kind, 'faint');
  // "Via Claude Code" but not loaded yet: no line. Off: no line.
  assert.equal(link('client:cursor', 'item:p3'), undefined);
  assert.equal(link('client:codex', 'item:p3').kind, 'on');
  assert.equal(link('client:claude_code', 'item:p1'), undefined);
  // Cursor's own copy is a plain line.
  assert.equal(link('client:cursor', 'item:s2').kind, 'on');
});

test('the entrance rises 22 apart and lands every block', () => {
  const { box } = showMap();
  const blocks = walk(box).filter((n) => n.dataset.focus?.startsWith('block:'));
  assert.ok(blocks.length > 5);
  assert.equal(blocks[0].style.opacity, '0');
  settle();
  assert.ok(walk(box).every((n) => n.style.opacity === undefined || n.style.opacity === ''));
});

test('find dims what does not match', () => {
  const { box, found } = showMap(MEDIUM, { q: 'super' });
  settle();
  assert.deepEqual([...found.matches], ['item:p2']);
  assert.ok(box.classList.contains('finding'));
  assert.match(node(box, 'block:item:p2').className, /\bfound\b/);
  assert.doesNotMatch(node(box, 'block:item:p1').className, /\bfound\b/);
  // A match on another page brings its page.
  const big = showMap(LARGE, { q: 'bench-skill-100' });
  settle();
  assert.ok(node(big.box, 'block:item:k100'));
  state.q = '';
});

test('a click on a plugin opens what it holds and lights its path; a second click folds it', async () => {
  const { box } = showMap();
  settle();
  node(box, 'block:item:p2').listeners.click[0]();
  await flush();
  assert.ok(node(box, 'block:part:p2:skills:brainstorm'));
  assert.match(node(box, 'block:item:p2').className, /\bselected\b/);
  assert.ok(box.classList.contains('focus'));
  assert.equal(node(box, 'block:item:p2').getAttribute('aria-expanded'), 'true');
  // Another plugin opens in its place: one at a time.
  node(box, 'block:item:p1').listeners.click[0]();
  await flush();
  assert.equal(node(box, 'block:part:p2:skills:brainstorm'), null);
  assert.ok(node(box, 'block:part:p1:mcp_servers:pr-index'));
  node(box, 'block:item:p1').listeners.click[0]();
  await flush();
  assert.equal(node(box, 'block:part:p1:mcp_servers:pr-index'), null);
  assert.ok(!box.classList.contains('focus'));
});

test('the count of a plugin card opens and folds it and nothing else; its words say items', async () => {
  const { box } = showMap();
  settle();
  const count = node(box, 'count:item:p2');
  assert.deepEqual([count.tagName, count.textContent, count.getAttribute('aria-label'), count.title, count.getAttribute('aria-expanded')], ['BUTTON', '3', 'Show 3 items', 'Show 3 items', 'false']);
  assert.equal(node(box, 'count:item:p1').getAttribute('aria-label'), 'Show 1 item');
  // A card with nothing read, a skill and a hook have no count.
  assert.deepEqual(['p4', 's1', 'h1'].map((id) => node(box, `count:item:${id}`)), [null, null, null]);
  count.focus();
  count.listeners.click[0]();
  await flush();
  assert.ok(node(box, 'block:part:p2:skills:brainstorm'));
  assert.deepEqual([count.getAttribute('aria-label'), count.getAttribute('aria-expanded'), node(box, 'count:item:p2') === count, document.activeElement === count], ['Hide items', 'true', true, true]);
  // Nothing is selected and nothing is lit.
  assert.ok(!walk(box).some((n) => /\bselected\b/.test(n.className)));
  assert.ok(!box.classList.contains('focus'));
  // Another plugin's count opens it in place of this one; the same count folds it.
  node(box, 'count:item:p1').listeners.click[0]();
  await flush();
  assert.deepEqual([node(box, 'block:part:p2:skills:brainstorm'), count.getAttribute('aria-label')], [null, 'Show 3 items']);
  assert.ok(node(box, 'block:part:p1:mcp_servers:pr-index'));
  node(box, 'count:item:p1').listeners.click[0]();
  await flush();
  assert.equal(node(box, 'block:part:p1:mcp_servers:pr-index'), null);
  // The card itself still opens and selects.
  node(box, 'block:item:p2').listeners.click[0]();
  await flush();
  assert.match(node(box, 'block:item:p2').className, /\bselected\b/);
});

test('folding the plugin that holds the selection lets the selection go', async () => {
  const { box } = showMap();
  settle();
  node(box, 'block:item:p2').listeners.click[0]();
  await flush();
  node(box, 'block:part:p2:skills:brainstorm').listeners.click[0]();
  await flush();
  assert.match(node(box, 'block:part:p2:skills:brainstorm').className, /\bselected\b/);
  node(box, 'count:item:p2').listeners.click[0]();
  await flush();
  assert.ok(!walk(box).some((n) => /\bselected\b/.test(n.className)));
});

test('under reduced motion it lands at once', () => {
  reducedMotion.matches = true;
  try {
    const { box } = showMap();
    assert.equal(frames.length, 0);
    assert.ok(walk(box).every((n) => n.style.opacity === undefined || n.style.opacity === ''));
  } finally {
    reducedMotion.matches = false;
  }
});

test('the address the page writes reads back as the same view and tab', () => {
  for (const drawn of ['map', 'list']) {
    libraryShows.mode = drawn;
    for (const kind of ['hook', 'skill', 'plugin', 'instructions']) {
      const back = parseHash(hashFor({ ...state, view: 'library', kind, mode: '', project: '', q: '', selected: null }));
      assert.deepEqual([back.view, back.kind, back.mode], ['library', kind, drawn], kind);
    }
  }
  // After a draw with no choice, the address names the view drawn.
  showMap();
  state.mode = '';
  assert.equal(libraryShows.mode, 'map');
  libraryShows.mode = '';
});

test('find matches what a folded plugin holds and lights that plugin, without opening it', () => {
  const { box, found } = showMap(MEDIUM, { q: 'brainstorm' });
  settle();
  // The chip counts the plugin card that lights.
  assert.deepEqual([...found.matches], ['item:p2']);
  assert.match(node(box, 'block:item:p2').className, /\bfound\b/);
  assert.doesNotMatch(node(box, 'block:item:p1').className, /\bfound\b/);
  assert.equal(node(box, 'block:part:p2:skills:brainstorm'), null);
  assert.equal(node(box, 'block:item:p2').getAttribute('aria-expanded'), 'false');
  // In the large sample the plugin's page comes, and only one plugin is ever open.
  const big = showMap(LARGE, { q: 'plugin-29-skill' });
  settle();
  assert.match(node(big.box, 'block:item:b29').className, /\bfound\b/);
  state.q = '';
});

test('the find chip counts what lights: a plugin card once, however many of its parts match', () => {
  // plugin-00 and its 20 skills match; one card lights.
  const { found } = showMap(LARGE, { q: 'plugin-00' });
  settle();
  assert.equal(findChip(found), '1 match');
  // A skill on its own and a plugin each count.
  assert.equal(findChip(showMap(MEDIUM, { q: 'brainstorm' }).found), '1 match');
  assert.equal(findChip(showMap(LARGE, { q: 'zzz' }).found), 'No matches');
  state.q = '';
});

test('"Instructions" opens the List on its Instructions tab', async () => {
  const { box } = showMap();
  settle();
  const tab = walk(main).find((n) => n.dataset.focus === 'map-tab:instructions');
  tab.listeners.click[0]();
  assert.equal(tab.getAttribute('aria-pressed'), 'true');
  await flush();
  assert.deepEqual([state.mode, state.kind], ['list', 'instructions']);
  assert.ok(box);
});

test('a map with no clients, or one Kitden could not read, draws no links from it', () => {
  const none = libraryTree({ ...MEDIUM, clients: [] });
  assert.equal(none.links.filter((l) => l.from.startsWith('client:')).length, 0);
  assert.ok(none.blocks.some((b) => b.id === 'item:p2'));
  const unread = { ...MEDIUM, clients: [...MEDIUM.clients.slice(0, 2), { id: 'cursor', name: 'Cursor', state: 'unreadable', words: 'Could not read' }] };
  unread.groups = MEDIUM.groups.map((g) => ({ ...g, items: g.items.map((i) => ({ ...i, by: Object.fromEntries(Object.entries(i.by).filter(([c]) => c !== 'cursor')) })) }));
  const model = libraryTree(unread);
  const cursor = model.blocks.find((b) => b.id === 'client:cursor');
  assert.deepEqual([cursor.meta, cursor.lamp, cursor.state], ['Could not read', null, 'unk']);
  assert.ok(!model.links.some((l) => l.from === 'client:cursor'));
  const { box } = showMap({ ...MEDIUM, clients: [] });
  settle();
  assert.ok(node(box, 'block:item:p2'));
});

test('long names end in "…" inside the map', () => {
  const long = 'a-very-long-plugin-name-that-goes-on';
  const sample = { ...LARGE, groups: [{ ...LARGE.groups[0], items: [{ ...LARGE.groups[0].items[0], name: long }] }] };
  const open = new Set(['item:b0']);
  const layout = layoutTree(libraryTree(sample), { open, narrow: false });
  const caption = layout.blocks.find((b) => b.id === 'inside:item:b0');
  assert.equal(caption.name, 'a-very-long-p… · 1–8 of 20');
  // 11 px semibold, at most about 6.5 px a letter, with its 13 px icon and gap: it fits in its 200 px column.
  assert.ok(caption.name.length * 6.5 + 19 <= 200);
});

// Drags on the Library map (library-notes §4, decisions "Drag a plugin or skill onto a client").
const { DRAGS, addBody, withWaiting } = await import('../../src/kitden/web/static/js/library-map.js');
const { previewFor } = await import('../../src/kitden/web/static/js/library.js');
const { addToTray, cancelTray, tray } = await import('../../src/kitden/web/static/js/tray.js');
globalThis.window ||= { addEventListener() {}, removeEventListener() {} };

// The medium sample with what Details may offer: superpowers can go to Codex, pr-review nowhere;
// brandkit is a skill Claude Code has, with a route to Codex and to Cursor.
const withCan = (item, can) => ({ ...item, can });
const DRAG_SAMPLE = {
  ...MEDIUM,
  groups: MEDIUM.groups.map((g) => {
    if (g.key === 'marketplace:demo-market') return { ...g, items: g.items.map((i) => withCan(i, i.id === 'p2' ? { add: ['codex'], off: ['claude_code'] } : { add: [], off: [] })) };
    if (g.key === 'skills') return { ...g, items: [...g.items.map((i) => withCan(i, { off: [] })), own('s3', 'brandkit', 'skill', { by: { claude_code: 'on' }, skill: 'brandkit@skills', can: { add: ['codex', 'cursor'], off: ['claude_code'] } })] };
    return g;
  }),
};

// The map drawn, with the document and the window hearing the pointer. The map's area is at the
// window's top left, so a map point is a window point. Details and the dock cover what `covers`
// says (window rects by selector), else nothing.
function libraryDrag(sample = DRAG_SAMPLE, { covers = {} } = {}) {
  const heard = {};
  const doc = globalThis.document;
  const saved = { add: doc.addEventListener, remove: doc.removeEventListener, query: doc.querySelector };
  doc.addEventListener = (type, fn) => { (heard[type] ||= []).push(fn); };
  doc.removeEventListener = (type, fn) => { heard[type] = (heard[type] || []).filter((f) => f !== fn); };
  doc.querySelector = (selector) => {
    if (covers[selector]) return { getBoundingClientRect: () => covers[selector] };
    return ['#drawer.open', '#dock'].includes(selector) ? null : saved.query(selector);
  };
  const { box } = showMap(sample);
  settle();
  walk(box).find((n) => n.classList.contains('map-area')).getBoundingClientRect = () => ({ left: 0, top: 0 });
  const layout = layoutTree(libraryTree(sample), { open: new Set(), narrow: false });
  const at = (id) => layout.blocks.find((b) => b.id === id);
  const drag = {
    box, heard, at,
    // A press 10 px into the block (or on its count, `count: true`).
    press(id, { count = false } = {}) {
      const block = node(box, `block:${id}`);
      const home = at(id);
      block.getBoundingClientRect = () => ({ left: home.x, top: home.y, width: home.w, height: home.h });
      block.setPointerCapture = () => {};
      const pressed = count ? node(box, `count:${id}`) : block;
      pressed.setPointerCapture = () => {};
      const event = { button: 0, pointerId: 1, target: { closest: () => pressed }, clientX: home.x + 10, clientY: home.y + 10 };
      for (const fn of box.listeners.pointerdown || []) fn(event);
      drag.move(home.x + 16, home.y + 10);
    },
    move: (x, y) => { for (const fn of [...(heard.pointermove || [])]) fn({ clientX: x, clientY: y }); },
    up: (x, y) => { for (const fn of [...(heard.pointerup || [])]) fn({ type: 'pointerup', clientX: x, clientY: y }); },
    onto: (id) => [at(id).x + 10, at(id).y + 10],
    tip: () => walk(box).find((n) => n.className.split(' ').includes('dragtip')) || null,
    restore: () => Object.assign(doc, { addEventListener: saved.add, removeEventListener: saved.remove, querySelector: saved.query }),
  };
  return drag;
}
const looks = (box, id) => node(box, `block:${id}`).className.split(' ');
// The links the map draws, by the focus key of their hits.
const linkKeys = (box) => walk(box).map((n) => n.dataset.focus).filter((key) => key && key.startsWith('link:')).sort();
const shook = (box, id) => node(box, `block:${id}`).animations.some((a) => JSON.stringify(a.keyframes).includes('-7px'));

test('a plugin dragged onto Codex adds one plugin.install row for Codex', async () => {
  const map = libraryDrag();
  try {
    // A hook, a client and a thing inside a plugin do not drag.
    for (const id of ['item:h1', 'client:codex']) {
      map.press(id);
      assert.equal(map.tip(), null, id);
      map.up(0, 0);
    }
    assert.ok(DRAGS.item && looks(map.box, 'item:p2').includes('drags') && looks(map.box, 'item:s1').includes('drags'));
    assert.ok(!looks(map.box, 'item:h1').includes('drags'));
    map.press('item:p2');
    assert.equal(map.tip().textContent, 'Drop on a client');
    assert.ok(looks(map.box, 'item:p2').includes('dragging'));
    map.move(...map.onto('client:codex'));
    assert.deepEqual([map.tip().textContent, map.tip().className], ['Add to Codex', 'dragtip on']);
    assert.ok(looks(map.box, 'client:codex').includes('drop'));
    assert.ok(walk(map.box).some((n) => n.className === 'link preview lit'), 'a dashed wire runs from the client');
    map.up(...map.onto('client:codex'));
    assert.deepEqual(tray.rows.map((r) => r.body), [{ action: 'plugin.install', targets: [{ client: 'codex' }], params: { plugin: 'superpowers@demo-market' } }]);
    // The same body as a cell's add.
    assert.deepEqual(addBody(DRAG_SAMPLE.groups[0].items[1], 'codex'), previewFor({ action: 'plugin.install', plugin: 'superpowers@demo-market' }, 'codex'));
    assert.equal(map.tip(), null);
    await flush();
    // The block always comes home.
    assert.ok(!looks(map.box, 'item:p2').includes('dragging'));
    assert.ok(!looks(map.box, 'client:codex').includes('drop'));
  } finally {
    map.restore();
    await cancelTray();
  }
});

test('a plugin over Cursor says Cursor gets plugins through Claude Code and Cursor shakes on release', async () => {
  const map = libraryDrag();
  try {
    map.press('item:p2');
    map.move(...map.onto('client:cursor'));
    assert.deepEqual([map.tip().textContent, map.tip().className], ['Cursor gets plugins through Claude Code', 'dragtip']);
    assert.ok(!looks(map.box, 'client:cursor').includes('drop'));
    assert.ok(!walk(map.box).some((n) => n.className === 'link preview lit'));
    map.up(...map.onto('client:cursor'));
    assert.ok(shook(map.box, 'client:cursor'));
    assert.equal(tray.rows.length, 0);
    await flush();
    assert.ok(!looks(map.box, 'item:p2').includes('dragging'));
  } finally {
    map.restore();
    await cancelTray();
  }
});

test('a client that has it says Already in <Client>; a waiting add says Already in preview', async () => {
  const map = libraryDrag();
  try {
    map.press('item:p2');
    map.move(...map.onto('client:claude_code'));
    assert.equal(map.tip().textContent, 'Already in Claude Code');
    map.move(...map.onto('client:codex'));
    map.up(...map.onto('client:codex'));
    await flush();
    map.press('item:p2');
    map.move(...map.onto('client:codex'));
    assert.equal(map.tip().textContent, 'Already in preview');
    map.up(...map.onto('client:codex'));
    assert.equal(tray.rows.length, 1);
    await flush();
    // No route: the client cannot get it.
    map.press('item:p1');
    map.move(...map.onto('client:codex'));
    assert.equal(map.tip().textContent, 'Codex cannot get pr-review');
    map.up(...map.onto('client:codex'));
    assert.ok(shook(map.box, 'client:codex'));
    assert.equal(tray.rows.length, 1);
  } finally {
    map.restore();
    await cancelTray();
  }
});

// Review Focus
test('a drop over Details, the dock or nothing leaves the tray as it was', async () => {
  const probe = libraryDrag();
  const [x, y] = probe.onto('client:codex');
  probe.restore();
  const over = { left: x - 50, top: y - 50, right: x + 50, bottom: y + 50, width: 100, height: 100 };
  const cases = [
    ['over Details', { '#drawer.open': over }, [x, y]],
    ['over the dock', { '#dock': over }, [x, y]],
    ['on nothing', {}, [1200, 10]],
  ];
  for (const [name, covers, [dropX, dropY]] of cases) {
    const map = libraryDrag(DRAG_SAMPLE, { covers });
    try {
      const links = linkKeys(map.box);
      map.press('item:p2');
      map.move(dropX, dropY);
      assert.ok(!looks(map.box, 'client:codex').includes('drop'), name);
      map.up(dropX, dropY);
      await flush();
      assert.equal(tray.rows.length, 0, name);
      assert.ok(!looks(map.box, 'item:p2').includes('dragging'), name);
      // The map's links are as they were: no preview link, no wire.
      assert.deepEqual(linkKeys(map.box), links, name);
      assert.ok(!walk(map.box).some((n) => n.className === 'link preview' || n.className === 'link preview lit'), name);
    } finally {
      map.restore();
    }
  }
  // Escape does the same.
  const map = libraryDrag();
  try {
    map.press('item:p2');
    map.move(x, y);
    const escape = { key: 'Escape', preventDefault() {}, stopImmediatePropagation() {} };
    for (const fn of [...map.heard.keydown]) fn(escape);
    await flush();
    assert.equal(tray.rows.length, 0);
    assert.ok(!looks(map.box, 'item:p2').includes('dragging'));
  } finally {
    map.restore();
    await cancelTray();
  }
});

test('a waiting add draws a dashed link and Preview · <Client>; a press takes it out', async () => {
  const map = libraryDrag();
  try {
    map.press('item:p2');
    map.move(...map.onto('client:codex'));
    map.up(...map.onto('client:codex'));
    await flush();
    const link = node(map.box, 'link:client:codex>item:p2');
    assert.ok(link, 'the preview link takes the pointer');
    assert.ok(walk(map.box).some((n) => n.className === 'link preview'));
    const card = node(map.box, 'block:item:p2');
    assert.equal(card.getAttribute('aria-label'), 'superpowers, Preview · Codex');
    assert.equal(card.title, 'In preview. Click to take it out.');
    // A press on the card takes the row out, and opens nothing.
    card.listeners.click[0]();
    await flush();
    assert.equal(tray.rows.length, 0);
    assert.equal(node(map.box, 'block:part:p2:skills:brainstorm'), null);
    assert.equal(node(map.box, 'block:item:p2').getAttribute('aria-label'), 'superpowers, 3 items, On');
    assert.equal(node(map.box, 'link:client:codex>item:p2'), null);
    // A press on the link does too.
    map.press('item:p2');
    map.move(...map.onto('client:codex'));
    map.up(...map.onto('client:codex'));
    await flush();
    node(map.box, 'link:client:codex>item:p2').listeners.click[0]();
    await flush();
    assert.equal(tray.rows.length, 0);
  } finally {
    map.restore();
    await cancelTray();
  }
});

test('a skill may drop on Cursor when it has a route', async () => {
  const map = libraryDrag();
  try {
    map.press('item:s3');
    map.move(...map.onto('client:cursor'));
    assert.deepEqual([map.tip().textContent, map.tip().className], ['Add to Cursor', 'dragtip on']);
    map.up(...map.onto('client:cursor'));
    assert.deepEqual(tray.rows.map((r) => r.body), [{ action: 'skill.install', targets: [{ client: 'cursor' }], params: { skill: 'brandkit@skills' } }]);
    assert.deepEqual(addBody(DRAG_SAMPLE.groups[2].items[2], 'cursor'), previewFor({ action: 'skill.install', skill: 'brandkit@skills' }, 'cursor'));
    await flush();
    assert.equal(node(map.box, 'block:item:s3').getAttribute('aria-label'), 'brandkit, Skill, Preview · Cursor');
    // A skill with no route there cannot go.
    map.press('item:s2');
    map.move(...map.onto('client:codex'));
    assert.equal(map.tip().textContent, 'Codex cannot get ui-polish');
    map.up(...map.onto('client:codex'));
    assert.equal(tray.rows.length, 1);
  } finally {
    map.restore();
    await cancelTray();
  }
});

test('under reduced motion a drag lands at once', async () => {
  reducedMotion.matches = true;
  const map = libraryDrag();
  try {
    map.press('item:p2');
    map.move(...map.onto('client:codex'));
    map.up(...map.onto('client:codex'));
    const home = map.at('item:p2');
    const card = node(map.box, 'block:item:p2');
    assert.equal(card.style.translate, `${home.x}px ${home.y}px`);
    assert.ok(!looks(map.box, 'item:p2').includes('dragging'));
    assert.equal(tray.rows.length, 1);
    assert.ok(walk(map.box).every((n) => n.style.opacity === undefined || n.style.opacity === '' || n.style.opacity === '1'));
  } finally {
    reducedMotion.matches = false;
    map.restore();
    await cancelTray();
  }
});

test('a waiting add for two clients, or for one project, says Already in preview and adds nothing', async () => {
  const plugin = 'superpowers@demo-market';
  const both = { action: 'plugin.install', targets: [{ client: 'codex' }, { client: 'claude_code' }], params: { plugin } };
  const one = { action: 'plugin.install', targets: [{ client: 'codex' }], params: { plugin, project: '/work/atlas' } };
  for (const [name, body] of [['two clients', both], ['one project', one]]) {
    addToTray(body);
    const map = libraryDrag();
    try {
      map.press('item:p2');
      map.move(...map.onto('client:codex'));
      assert.equal(map.tip().textContent, 'Already in preview', name);
      assert.ok(!looks(map.box, 'client:codex').includes('drop'), name);
      map.up(...map.onto('client:codex'));
      assert.ok(shook(map.box, 'client:codex'), name);
      assert.deepEqual(tray.rows.map((r) => r.body), [body], name);
    } finally {
      map.restore();
      await cancelTray();
    }
  }
  // A project's add draws only while that project is picked; the two-client one draws for both.
  const rows = [{ key: 'k1', body: one }];
  const card = (model) => model.blocks.find((b) => b.id === 'item:p2');
  const all = withWaiting(libraryTree(DRAG_SAMPLE), rows, '');
  assert.equal(card(all).meta, '3 items');
  assert.ok(!all.links.some((l) => l.kind === 'preview'));
  const atlas = withWaiting(libraryTree(DRAG_SAMPLE), rows, '/work/atlas');
  assert.deepEqual([card(atlas).meta, card(atlas).rows], ['Preview · Codex', ['k1']]);
  const two = withWaiting(libraryTree(DRAG_SAMPLE), [{ key: 'k2', body: both }], '');
  assert.equal(card(two).meta, 'Preview · Codex and Claude Code');
  assert.deepEqual(two.links.filter((l) => l.kind === 'preview').map((l) => l.from), ['client:codex', 'client:claude_code']);
});

test('a drop on a client that already has it shakes the client and leaves the tray as it was', async () => {
  const map = libraryDrag();
  try {
    map.press('item:p2');
    map.move(...map.onto('client:claude_code'));
    map.up(...map.onto('client:claude_code'));
    assert.ok(shook(map.box, 'client:claude_code'));
    assert.equal(tray.rows.length, 0);
    await flush();
    assert.ok(!looks(map.box, 'item:p2').includes('dragging'));
  } finally {
    map.restore();
    await cancelTray();
  }
});

test("a press on a plugin card's count, then a 5 px move, drags the card", async () => {
  const map = libraryDrag();
  try {
    map.press('item:p2', { count: true });
    assert.equal(map.tip().textContent, 'Drop on a client');
    assert.ok(looks(map.box, 'item:p2').includes('dragging'));
    map.move(...map.onto('client:codex'));
    map.up(...map.onto('client:codex'));
    assert.equal(tray.rows.length, 1);
  } finally {
    map.restore();
    await cancelTray();
  }
});

test('a redraw in the middle of a drag keeps the block with the pointer', async () => {
  const map = libraryDrag();
  try {
    map.press('item:p2');
    map.move(600, 300);
    const card = node(map.box, 'block:item:p2');
    // The press was 10 px into the block.
    assert.equal(card.style.translate, '590px 290px');
    // Another change joins the tray: the map draws again in place.
    addToTray({ action: 'plugin.install', targets: [{ client: 'codex' }], params: { plugin: 'pr-review@demo-market' } });
    await flush();
    assert.equal(card.style.translate, '590px 290px');
    assert.ok(looks(map.box, 'item:p2').includes('dragging'));
    assert.equal(map.tip().textContent, 'Drop on a client');
    map.move(610, 300);
    assert.equal(card.style.translate, '600px 290px');
    map.up(610, 300);
    await flush();
    assert.ok(!looks(map.box, 'item:p2').includes('dragging'));
  } finally {
    map.restore();
    await cancelTray();
  }
});


// The × of a link (library-notes §5, decisions "Link ×"). It only adds a row to the tray.
const { setBusy } = await import('../../src/kitden/web/static/js/store.js');
const { linkRemoval } = await import('../../src/kitden/web/static/js/library-rules.js');

// Superpowers: Claude Code removes its own entry, Cursor reads it through Claude Code (faint).
// browser: Codex's own. ui-kit: Cursor's own plugin. release-notes: a skill Claude Code and Codex
// load on their own. ui-polish: a skill in Cursor's own folder. calendar: Codex is not sure.
const X_SAMPLE = {
  ...MEDIUM,
  groups: [
    { key: 'marketplace:demo-market', name: 'demo-market', icon: 'store', kind: 'marketplace', items: [
      plugin('p2', 'superpowers', { by: { claude_code: 'on', cursor: 'on' }, through: { cursor: 'claude_code' }, items: { claude_code: ['cc-sp'], cursor: ['cu-sp'] }, inside: { ...none, skills: ['brainstorm'] }, count: 1, can: { add: ['codex'], off: ['claude_code'], remove: ['claude_code'] } }),
      plugin('p5', 'browser', { by: { codex: 'on' }, items: { codex: ['cx-br'] }, can: { add: [], off: ['codex'], remove: ['codex'] } }),
      plugin('p6', 'ui-kit', { by: { cursor: 'on' }, items: { cursor: ['cu-ui'] }, can: { add: [], off: [], remove: [] } }),
    ] },
    { key: 'other', name: 'Other plugins', icon: 'puzzle', kind: 'other', items: [plugin('p4', 'calendar', { by: { codex: 'unknown' }, items: { codex: ['cx-cal'] }, can: { add: [], off: [], remove: [] } })] },
    { key: 'skills', name: 'Your skills', icon: 'user-round', kind: 'skills', items: [
      own('s1', 'release-notes', 'skill', { by: { claude_code: 'on', codex: 'on' }, items: { claude_code: ['cc-rn'], codex: ['cx-rn'] }, can: { add: [], off: ['claude_code', 'codex'], remove: ['claude_code', 'codex'] } }),
      own('s2', 'ui-polish', 'skill', { by: { cursor: 'on' }, items: { cursor: ['cu-pol'] }, can: { add: [], off: [], remove: ['cursor'] } }),
    ] },
    { key: 'settings', name: 'Your settings', icon: 'settings', kind: 'settings', items: [own('h1', 'PreToolUse: Bash', 'hook', { by: { claude_code: 'on' }, items: { claude_code: ['cc-h'] }, can: {} })] },
  ],
};

// Pointing at a link, as the page hears it: its hit takes the pointer, and the × shows. Delete is
// the key the hit hears.
function linkX(sample = X_SAMPLE) {
  const { box } = showMap(sample);
  settle();
  const crossOf = () => walk(box).find((n) => n.classList.contains('link-x'));
  const x = {
    box,
    hit: (id) => node(box, `link:${id}`),
    // The words the × would say, and whether there is one at all.
    tip: (id) => x.hit(id).getAttribute('aria-description'),
    point(id) {
      x.hit(id).listeners.pointerover[0]();
      return crossOf();
    },
    press(id) {
      const cross = x.point(id);
      assert.equal(cross.hidden, false, `${id} shows a ×`);
      cross.listeners.click[0]();
    },
    del(id, extra = {}) {
      const event = { key: 'Delete', repeat: false, altKey: false, ctrlKey: false, metaKey: false, shiftKey: false, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...extra };
      x.hit(id).listeners.keydown[0](event);
      return event;
    },
    leaving: () => walk(box).filter((n) => /^link /.test(n.className) && n.classList.contains('leaving')).length,
  };
  return x;
}
const bodies = () => tray.rows.map((r) => r.body);

test("a client→plugin link's × adds plugin.remove for that client", async () => {
  const x = linkX();
  try {
    assert.equal(x.tip('client:claude_code>item:p2'), 'Remove superpowers from Claude Code');
    assert.equal(x.hit('client:claude_code>item:p2').getAttribute('aria-keyshortcuts'), 'Delete');
    assert.equal(x.point('client:claude_code>item:p2').getAttribute('aria-label'), 'Remove superpowers from Claude Code');
    assert.equal(x.tip('client:codex>item:p5'), 'Remove browser from Codex');
    x.press('client:claude_code>item:p2');
    assert.deepEqual(bodies(), [{ action: 'plugin.remove', targets: [{ item: 'cc-sp' }], params: {} }]);
    assert.equal(tray.rows[0].icon, 'x');
    // Nothing is written: the row waits in the tray, and its link is drawn leaving.
    await flush();
    assert.equal(x.leaving(), 1);
    assert.equal(x.tip('client:claude_code>item:p2'), 'Take it out of the preview');
    // The × again takes the row out, and the link is whole again.
    x.press('client:claude_code>item:p2');
    await flush();
    assert.equal(tray.rows.length, 0);
    assert.equal(x.leaving(), 0);
    assert.equal(x.tip('client:claude_code>item:p2'), 'Remove superpowers from Claude Code');
  } finally {
    await cancelTray();
  }
});

test("a client→skill link's × turns it off in Claude Code or Codex, and removes Cursor's own copy", async () => {
  const x = linkX();
  try {
    assert.equal(x.tip('client:claude_code>item:s1'), 'Turn off release-notes in Claude Code');
    assert.equal(x.tip('client:codex>item:s1'), 'Turn off release-notes in Codex');
    assert.equal(x.tip('client:cursor>item:s2'), 'Remove ui-polish from Cursor');
    x.press('client:codex>item:s1');
    x.press('client:cursor>item:s2');
    assert.deepEqual(bodies(), [
      { action: 'skill.rule', targets: [{ client: 'codex', item: 'cx-rn' }], params: { scope: 'all', off: true } },
      { action: 'skill.remove', targets: [{ item: 'cu-pol' }], params: {} },
    ]);
    // The same rows as Details' "Turn off for all projects…".
    const { offBodies } = await import('../../src/kitden/web/static/js/library-details.js');
    assert.deepEqual(bodies()[0], offBodies(X_SAMPLE.groups[2].items[0])[1]);
    await flush();
    // The row of Details is the same row: the × says so.
    assert.equal(x.tip('client:codex>item:s1'), 'Take it out of the preview');
  } finally {
    await cancelTray();
  }
});

test("Claude Code's skill × waits for a skill rule of a project in the tray, as Details does", async () => {
  const x = linkX();
  try {
    addToTray({ action: 'skill.rule', targets: [{ client: 'claude_code', item: 'cc-rn' }], params: { scope: 'project', project: 'atlas', off: true } });
    await flush();
    assert.equal(x.tip('client:claude_code>item:s1'), null);
    assert.equal(x.tip('client:codex>item:s1'), 'Turn off release-notes in Codex');
  } finally {
    await cancelTray();
  }
});

test("a preview link's × takes the row out", async () => {
  const x = linkX();
  try {
    addToTray(addBody(X_SAMPLE.groups[0].items[0], 'codex'));
    await flush();
    assert.equal(x.tip('client:codex>item:p2'), 'Take it out of the preview');
    x.press('client:codex>item:p2');
    await flush();
    assert.equal(tray.rows.length, 0);
    assert.equal(node(x.box, 'link:client:codex>item:p2'), null);
  } finally {
    await cancelTray();
  }
});

test('plugin→inside, Cursor plugin, faint, Unknown and hook links have no ×', async () => {
  const x = linkX();
  try {
    // The Unknown client has no link; a Cursor plugin, a faint line and a hook link have no ×.
    assert.equal(node(x.box, 'link:client:codex>item:p4'), null);
    for (const id of ['client:cursor>item:p6', 'client:cursor>item:p2', 'client:claude_code>item:h1']) {
      assert.ok(x.hit(id), id);
      assert.equal(x.tip(id), null, id);
      assert.equal(x.hit(id).getAttribute('aria-keyshortcuts'), null, id);
      x.hit(id).listeners.pointerover[0]();
      assert.ok(walk(x.box).filter((n) => n.classList.contains('link-x')).every((n) => n.hidden), id);
    }
    // A plugin's inside link: the plugin opens, its link takes the pointer and says nothing.
    node(x.box, 'block:item:p2').listeners.click[0]();
    await flush();
    const inside = 'item:p2>part:p2:skills:brainstorm';
    assert.ok(x.hit(inside));
    assert.equal(x.tip(inside), null);
    // Delete on a link with no × is left to the page.
    assert.equal(x.del('client:cursor>item:p6').defaultPrevented, false);
    assert.equal(tray.rows.length, 0);
    // None of them can be removed from the helper either.
    assert.equal(linkRemoval(X_SAMPLE.groups[0].items[2], 'cursor', X_SAMPLE), null);
    assert.equal(linkRemoval(X_SAMPLE.groups[0].items[0], 'cursor', X_SAMPLE), null);
  } finally {
    await cancelTray();
  }
});

test('Delete on a focused link does what its × does', async () => {
  const x = linkX();
  try {
    // A held key or a key with a modifier is not a press.
    for (const extra of [{ repeat: true }, { metaKey: true }]) {
      x.del('client:codex>item:p5', extra);
      assert.equal(tray.rows.length, 0);
    }
    const event = x.del('client:codex>item:p5');
    assert.equal(event.defaultPrevented, true);
    assert.deepEqual(bodies(), [{ action: 'plugin.remove', targets: [{ item: 'cx-br' }], params: {} }]);
    await flush();
    // Delete again takes the row out.
    x.del('client:codex>item:p5');
    await flush();
    assert.equal(tray.rows.length, 0);
  } finally {
    await cancelTray();
  }
});

test('while a change is written the × waits and removes nothing', async () => {
  const x = linkX();
  try {
    setBusy(true);
    const cross = x.point('client:codex>item:p5');
    assert.equal(cross.getAttribute('aria-disabled'), 'true');
    assert.equal(cross.title, 'Another change is being written.');
    cross.listeners.click[0]();
    x.del('client:codex>item:p5');
    assert.equal(tray.rows.length, 0);
    setBusy(false);
    assert.equal(x.point('client:codex>item:p5').getAttribute('aria-disabled'), null);
  } finally {
    setBusy(false);
    await cancelTray();
  }
});
