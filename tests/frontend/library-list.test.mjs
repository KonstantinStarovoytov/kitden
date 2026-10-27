import assert from 'node:assert/strict';
import { test } from 'node:test';

// The Library's List drawn in a small browser (as in library-map.test.mjs): elements, the page's
// fixed parts, and frames and a clock that only the test moves. Reads answer from `answers`.
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
    closest(selector) {
      for (let at = node; at; at = at.parentNode) {
        if (selector === 'button' ? at.tagName === 'BUTTON' : at.classList && at.classList.contains(selector.slice(1))) return at;
      }
      return null;
    },
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
  querySelector: (selector) => pages[selector] ?? null, querySelectorAll: () => [], getElementById: (id) => (id === 'hint' ? hintLine : id === 'content' ? pages['#main'] : null),
  addEventListener() {}, removeEventListener() {},
  documentElement: { classList: { add() {}, remove() {} }, style: { setProperty() {}, removeProperty() {} } },
};
// What each read answers, by its path; a test sets them. `asked` keeps every URL read.
const answers = {};
const asked = [];
globalThis.fetch = (url) => {
  asked.push(url);
  const path = String(url).split('?')[0];
  if (!(path in answers)) return new Promise(() => {});
  return Promise.resolve({ ok: true, status: 200, json: async () => answers[path] });
};

const { listRows, loadLibrary, renderLibrary } = await import('../../src/kitden/web/static/js/library.js');
const { libraryThing, onLibrarySelect } = await import('../../src/kitden/web/static/js/library-map.js');
const { data, freshness, go, hashFor, parseHash, state } = await import('../../src/kitden/web/static/js/store.js');
const { setHint } = await import('../../src/kitden/web/static/js/parts.js');

// The medium sample, cut short: the List's answer (views/library.py library_list) and the map's
// (views/library_map.py), which Details read.
const cell = (state, fields = {}) => ({ state, where: null, origin: null, route: null, stale_at: null, items: [], word: null, add: null, reason: null, ...fields });
const add = (fields) => ({ action: 'plugin.install', label: '+ Add', plugin: null, skill: null, marketplace: null, item: null, warn: null, project_place: false, project_hint: null, project_only: false, ...fields });
const COLUMNS = [
  { id: 'claude_code', name: 'Claude Code', mark: 'claude', hidden: false, note: null },
  { id: 'codex', name: 'Codex', mark: 'codex', hidden: false, note: null },
  { id: 'cursor', name: 'Cursor', mark: 'cursor', hidden: false, note: null },
];
const item = (id, kind, name, cells, fields = {}) => ({ id, kind, name, source: 'demo-market', same_name: false, lookup: name, flags: [], count: null, cells, ...fields });
const LIST = {
  columns: COLUMNS,
  attention: 1,
  notes: [],
  groups: [
    { key: 'marketplace:demo-market', name: 'demo-market', icon: 'store', kind: 'marketplace', items: [
      item('p2', 'plugin', 'superpowers', { claude_code: cell('on'), codex: cell('none', { add: add({ plugin: 'superpowers@demo-market' }) }), cursor: cell('on') }, {
        lookup: 'superpowers@demo-market', count: 3, flags: [{ text: 'Loads twice', level: 'warning' }],
        parts: [
          { key: 'skills', kind: 'skill', name: 'brainstorm', source: 'superpowers@demo-market', same_name: false, cells: { claude_code: cell('on'), codex: cell('none', { add: add({ action: 'skill.install', skill: 'brainstorm@superpowers@demo-market' }) }), cursor: cell('on') } },
          { key: 'skills', kind: 'skill', name: 'plan', source: 'superpowers@demo-market', same_name: false, lookup: 'plan', flags: [{ text: 'Same name, another source.', level: 'warning' }], cells: { claude_code: cell('on'), codex: cell('none'), cursor: cell('on') } },
          { key: 'commands', kind: 'command', name: 'ship', source: 'demo-market', same_name: false, cells: { claude_code: cell('on'), codex: cell('none'), cursor: cell('on') } },
        ] }),
      item('p1', 'plugin', 'pr-review', { claude_code: cell('off'), codex: cell('none'), cursor: cell('via', { word: 'Via Claude Code' }) }, { lookup: 'pr-review@demo-market', count: 0, parts: [] }),
    ] },
    { key: 'skills', name: 'Your skills', icon: 'user-round', kind: 'skills', items: [
      item('s1', 'skill', 'release-notes', { claude_code: cell('on'), codex: cell('none', { reason: 'Codex has its own copy.' }), cursor: cell('on') }, { source: 'Claude Code' }),
    ] },
    { key: 'settings', name: 'Your settings', icon: 'settings', kind: 'settings', items: [
      item('h1', 'hook', 'PreToolUse: Bash', { claude_code: cell('on'), codex: cell('none'), cursor: cell('none') }, { source: null }),
    ] },
  ],
};
const FILES = {
  columns: COLUMNS, attention: 0, notes: [],
  groups: [{ key: 'all', name: 'All projects', icon: 'layers', kind: 'files', items: [
    { id: 'f1', kind: 'file', name: 'CLAUDE.md', flags: [], cells: { claude_code: cell('on', { word: 'Reads it' }), codex: cell('none'), cursor: cell('none') } },
    { id: 'f2', kind: 'file', name: 'AGENTS.md', flags: [], cells: { claude_code: cell('none'), codex: cell('on', { word: 'Reads it' }), cursor: cell('none') } },
  ] }],
};
const none = { skills: [], commands: [], agents: [], hooks: [], mcp_servers: [] };
const MAP = {
  clients: [
    { id: 'claude_code', name: 'Claude Code', state: 'on', words: 'Connected' },
    { id: 'codex', name: 'Codex', state: 'on', words: 'Connected' },
    { id: 'cursor', name: 'Cursor', state: 'via', words: 'Via Claude Code' },
  ],
  groups: [
    { key: 'marketplace:demo-market', name: 'demo-market', icon: 'store', kind: 'marketplace', items: [
      { id: 'p2', name: 'superpowers', kind: 'plugin', plugin: 'superpowers@demo-market', by: { claude_code: 'on', cursor: 'on' }, through: { cursor: 'claude_code' }, items: {}, here: false, source: 'demo-market', technical: {}, can: { add: ['codex'], off: [], remove: [] }, inside: { ...none, skills: ['brainstorm', 'plan'], commands: ['ship'] }, count: 3 },
    ] },
    { key: 'settings', name: 'Your settings', icon: 'settings', kind: 'settings', items: [
      { id: 'h1', name: 'PreToolUse: Bash', kind: 'hook', by: { claude_code: 'on' }, through: {}, items: {}, here: false, source: 'Your settings', technical: {} },
    ] },
  ],
};
const INSTRUCTIONS = { clients: MAP.clients, groups: [{ key: 'all', name: 'All projects', files: [{ id: 'f1', name: 'CLAUDE.md', by: { claude_code: true }, imports: [], size: 4, technical: { path: '/home/CLAUDE.md', lines: [] } }] }], imports: [] };

const main = pages['#main'];
const node = (box, key) => walk(box).find((n) => n.dataset.focus === key) || null;
// What a row or cell shows; words only a screen reader hears are left out.
const texts = (root) => walk(root).filter((n) => !walk(root).some((o) => o.classList.contains('sr-only') && o.contains(n))).map((n) => n.textContent).filter(Boolean);
const grid = () => walk(main).find((n) => n.getAttribute('role') === 'treegrid') || null;
const rowNodes = () => grid().children.filter((n) => n.dataset.row);
const rowIds = () => rowNodes().map((n) => n.dataset.row);
const rowOf = (id) => rowNodes().find((n) => n.dataset.row === id);
const selected = [];
const hows = [];
onLibrarySelect((id, how) => { selected.push(id); hows.push(how); });

// Draw the List of `tab` once its rows are read.
async function showList({ kind = 'plugin', show = 'mine', attention = false, q = '', project = '', list = kind === 'instructions' ? FILES : LIST } = {}) {
  answers['/api/library-list'] = list;
  Object.assign(data, { libraryMap: MAP, instructionsMap: INSTRUCTIONS, projects: [{ id: 'a', path: '/home/work/atlas' }] });
  data.scope.libraryMap = project;
  data.scope.instructionsMap = project;
  Object.assign(state, { view: 'library', mode: 'list', kind, show, attention, q, project, selected: null, category: '' });
  freshness.reloadStartedAt = performance.now();
  await loadLibrary();
  main.replaceChildren();
  setHint('');
  renderLibrary(main);
  return grid();
}
const keyOn = (id, key) => {
  const target = rowOf(id);
  const event = { key, target, preventDefault() { event.prevented = true; } };
  for (const fn of grid().listeners.keydown) fn(event);
  return event;
};

test('the List has the two tabs and one column per client', async () => {
  const box = await showList();
  const [head, lede, tabs, scope] = main.children;
  assert.equal(head.children[0].textContent, 'Library');
  assert.equal(head.children.at(-1).children.find((n) => n.textContent === 'List').getAttribute('aria-pressed'), 'true');
  assert.equal(lede.textContent, 'Follow the source. Connect only what you need.');
  assert.equal(tabs.className, 'seg sm map-tabs');
  assert.deepEqual(tabs.children.filter((n) => n.tagName === 'BUTTON').map((n) => [n.textContent, n.getAttribute('aria-pressed')]), [['Plugins and skills', 'true'], ['Instructions', 'false']]);
  assert.ok(texts(scope).includes('Shared setup · project overrides stay separate'));
  // Name, then one column per client, each with its tile and a quiet "−".
  const columns = box.children[0];
  assert.equal(columns.getAttribute('role'), 'row');
  assert.equal(columns.children[0].textContent, 'Name');
  assert.deepEqual(columns.children.slice(1).map((c) => walk(c).find((n) => n.tagName === 'SPAN' && n.parentNode.classList.contains('who') && !n.classList.contains('client-mark'))?.textContent), ['Claude Code', 'Codex', 'Cursor']);
  assert.ok(node(columns, 'hide:codex'));
  assert.equal(box.style['--tg-cols'], 'minmax(0, 1fr) repeat(3, 150px)');
  // One group row per source, then its items; no MCP servers.
  assert.deepEqual(rowIds(), ['group:marketplace:demo-market', 'item:p2', 'item:p1', 'group:skills', 'item:s1', 'group:settings', 'item:h1']);
  assert.equal(hintLine.children.at(-1).textContent, 'One row per item, one column per client. Right opens a plugin, Enter opens Details.');
  // No paths on the page, and none of the old tabs or filters.
  assert.ok(!texts(main).some((t) => t.includes('/home/')));
  for (const gone of ['MCP servers', 'Marketplaces', 'New', 'All', 'All categories', 'Add a marketplace…']) assert.ok(!texts(main).includes(gone), gone);
});

test('a plugin row says Plugin · n items and folds its parts', async () => {
  await showList();
  const plugin = rowOf('item:p2');
  assert.ok(texts(plugin).includes('superpowers'));
  assert.ok(texts(plugin).includes('Plugin · 3 items'));
  assert.equal(plugin.getAttribute('aria-expanded'), 'false');
  // A plugin Kitden read nothing in has no fold, and says only "Plugin".
  assert.equal(rowOf('item:p1').getAttribute('aria-expanded'), null);
  assert.ok(texts(rowOf('item:p1')).includes('Plugin'));
  assert.ok(!texts(rowOf('item:p1')).some((t) => t.startsWith('Plugin · ')));
  assert.ok(texts(rowOf('item:s1')).includes('Skill'));
  assert.ok(texts(rowOf('item:h1')).includes('Hook'));
  // A press on its fold mark opens it: its parts come in under it with their kind word.
  const caret = walk(plugin).find((n) => n.classList.contains('caret'));
  plugin.listeners.click[0]({ target: caret });
  renderLibrary((main.replaceChildren(), main));
  assert.deepEqual(rowIds().slice(1, 6), ['item:p2', 'part:p2:skills:brainstorm', 'part:p2:skills:plan', 'part:p2:commands:ship', 'item:p1']);
  assert.equal(rowOf('item:p2').getAttribute('aria-expanded'), 'true');
  assert.ok(texts(rowOf('part:p2:skills:plan')).includes('Skill'));
  assert.ok(texts(rowOf('part:p2:commands:ship')).includes('Command'));
  assert.equal(rowOf('part:p2:skills:plan').getAttribute('aria-level'), '3');
  // A press there again folds it.
  rowOf('item:p2').listeners.click[0]({ target: walk(rowOf('item:p2')).find((n) => n.classList.contains('caret')) });
  renderLibrary((main.replaceChildren(), main));
  assert.ok(!rowIds().includes('part:p2:skills:plan'));
});

test('cells say On, Off, Via Claude Code, + Add or nothing', async () => {
  await showList();
  const words = (id) => rowOf(id).children.slice(1).map((c) => texts(c).filter((t) => !t.startsWith('Add ')).join(' '));
  assert.deepEqual(words('item:p2'), ['On', '+ Add', 'On']);
  assert.deepEqual(words('item:p1'), ['Off', '', 'Via Claude Code']);
  // Nothing to do: the cell is empty, and its hover says why.
  const empty = rowOf('item:s1').children[2];
  assert.equal(texts(empty).filter((t) => t !== '—').length <= 1, true);
  assert.ok(!texts(empty).includes('—'));
  assert.equal(walk(empty).find((n) => n.classList.contains('socket')).title, 'Codex has its own copy.');
  // "+ Add" is today's add: one client, here for all projects.
  const button = walk(rowOf('item:p2')).find((n) => n.tagName === 'BUTTON' && n.textContent === '+ Add');
  assert.equal(button.getAttribute('aria-label'), 'Add superpowers to Codex');
});

test('the Instructions List has one row per file', async () => {
  await showList({ kind: 'instructions' });
  const tabs = main.children[2];
  assert.deepEqual(tabs.children.filter((n) => n.tagName === 'BUTTON').map((n) => n.getAttribute('aria-pressed')), ['false', 'true']);
  assert.deepEqual(rowIds(), ['group:all', 'file:f1', 'file:f2']);
  assert.deepEqual(rowOf('file:f1').children.slice(1).map((c) => texts(c).join(' ')), ['Reads it', '', '']);
  // Nothing to filter or add here, and its hint is the map tab's.
  assert.equal(walk(main).find((n) => n.classList.contains('toolbar')), undefined);
  assert.equal(hintLine.children.at(-1).textContent, 'Kitden only reads instruction files. It never changes them.');
  // A press on a file opens the file's Details, as on the map.
  selected.length = 0;
  rowOf('file:f1').listeners.click[0]({ target: rowOf('file:f1') });
  assert.deepEqual(selected, ['file:f1']);
  assert.equal(libraryThing('file:f1').block.kind, 'file');
  // The other tab lets go of them, as on the map.
  answers['/api/library-list'] = LIST;
  tabs.children.find((n) => n.textContent === 'Plugins and skills').listeners.click[0]();
  await new Promise((done) => setTimeout(done, 5));
  assert.deepEqual(selected, ['file:f1', null]);
  assert.equal(state.kind, 'plugin');
});

test('hooks sit under Your settings; a marketplace row opens its Details', async () => {
  await showList();
  const settings = rowOf('group:settings');
  assert.ok(texts(settings).includes('Your settings'));
  assert.equal(rowNodes()[rowIds().indexOf('group:settings') + 1].dataset.row, 'item:h1');
  // A press on a marketplace's row opens its caption's Details; a press on another group folds it.
  selected.length = 0;
  const market = rowOf('group:marketplace:demo-market');
  market.listeners.click[0]({ target: market });
  assert.deepEqual(selected, ['group:marketplace:demo-market']);
  assert.equal(libraryThing('group:marketplace:demo-market').block.group.name, 'demo-market');
  settings.listeners.click[0]({ target: settings });
  assert.deepEqual(selected, ['group:marketplace:demo-market']);
  renderLibrary((main.replaceChildren(), main));
  assert.ok(!rowIds().includes('item:h1'));
  assert.equal(rowOf('group:settings').getAttribute('aria-expanded'), 'false');
  rowOf('group:settings').listeners.click[0]({ target: rowOf('group:settings') });
  renderLibrary((main.replaceChildren(), main));
  assert.ok(rowIds().includes('item:h1'));
  // A plugin, a hook and a part open the same Details as the map.
  rowOf('item:h1').listeners.click[0]({ target: rowOf('item:h1') });
  assert.equal(selected.at(-1), 'item:h1');
  assert.equal(libraryThing('item:h1').block.kind, 'hook');
  assert.deepEqual(state.selected, { kind: 'hook', name: 'PreToolUse: Bash' });
});

test('Up, Down, Right, Left and Enter work', async () => {
  await showList();
  selected.length = 0;
  keyOn('group:marketplace:demo-market', 'ArrowDown');
  assert.equal(document.activeElement, rowOf('item:p2'));
  assert.equal(rowOf('item:p2').tabIndex, 0);
  assert.equal(rowOf('group:marketplace:demo-market').tabIndex, -1);
  keyOn('item:p2', 'ArrowDown');
  assert.equal(document.activeElement, rowOf('item:p1'));
  keyOn('item:p1', 'ArrowUp');
  assert.equal(document.activeElement, rowOf('item:p2'));
  // Right opens a plugin, then goes into it; Left goes back to it, then folds it.
  keyOn('item:p2', 'ArrowRight');
  renderLibrary((main.replaceChildren(), main));
  assert.ok(rowIds().includes('part:p2:skills:brainstorm'));
  keyOn('item:p2', 'ArrowRight');
  assert.equal(document.activeElement, rowOf('part:p2:skills:brainstorm'));
  keyOn('part:p2:skills:brainstorm', 'ArrowLeft');
  assert.equal(document.activeElement, rowOf('item:p2'));
  keyOn('item:p2', 'ArrowLeft');
  renderLibrary((main.replaceChildren(), main));
  assert.ok(!rowIds().includes('part:p2:skills:brainstorm'));
  // Enter opens Details; on a marketplace's row too.
  const enter = keyOn('item:p2', 'Enter');
  assert.ok(enter.prevented);
  keyOn('group:marketplace:demo-market', 'Enter');
  assert.deepEqual(selected, ['item:p2', 'group:marketplace:demo-market']);
  // A key with a modifier is the browser's.
  const back = { key: 'ArrowLeft', altKey: true, target: rowOf('item:p2'), preventDefault() { back.prevented = true; } };
  for (const fn of grid().listeners.keydown) fn(back);
  assert.equal(back.prevented, undefined);
});

test('Installed | Differences reads show=diff, and an empty Differences says so', async () => {
  await showList();
  const seg = walk(main).find((n) => n.getAttribute('aria-label') === 'Show' && n.classList.contains('seg') && !n.classList.contains('map-tabs'));
  assert.deepEqual(seg.children.filter((n) => n.tagName === 'BUTTON').map((n) => [n.textContent, n.getAttribute('aria-pressed')]), [['Installed', 'true'], ['Differences', 'false']]);
  asked.length = 0;
  answers['/api/library-list'] = { ...LIST, groups: [] };
  seg.children.find((n) => n.textContent === 'Differences').listeners.click[0]();
  await new Promise((done) => setTimeout(done, 5));
  assert.ok(asked.some((url) => url.includes('show=diff')));
  assert.equal(state.show, 'diff');
  assert.equal(hashFor(state), '#library?kind=plugin&show=diff&view=list');
  main.replaceChildren();
  renderLibrary(main);
  const empty = walk(main).find((n) => n.classList.contains('empty'));
  assert.ok(texts(empty).includes('No differences between your clients'));
  const back = walk(empty).find((n) => n.textContent === 'Show installed');
  back.listeners.click[0]();
  await new Promise((done) => setTimeout(done, 5));
  assert.equal(state.show, 'mine');
});

test('Needs attention still filters', async () => {
  await showList();
  const toggle = node(main, 'filter:attention');
  assert.equal(toggle.textContent, 'Needs attention · 1');
  assert.equal(toggle.getAttribute('aria-pressed'), 'false');
  asked.length = 0;
  toggle.listeners.click[0]();
  await new Promise((done) => setTimeout(done, 5));
  assert.ok(asked.some((url) => url.includes('attention=1')));
  assert.equal(state.attention, true);
  // Its flag shows on the row.
  assert.ok(texts(rowOf('item:p2')).includes('Loads twice'));
});

test('in a project, Add missing… keeps today\'s review', async () => {
  await showList({ project: 'a' });
  const missing = node(main, 'add:missing');
  assert.equal(missing.textContent, 'Add missing…');
  await showList();
  assert.equal(node(main, 'add:missing'), null);
});

test('old show=new and kind=marketplace links land in their new place', () => {
  assert.deepEqual([parseHash('#library?kind=skill&show=new&view=list').kind, parseHash('#library?kind=skill&show=new&view=list').show], ['plugin', 'mine']);
  assert.equal(parseHash('#library?kind=plugin&show=all&view=list').show, 'mine');
  assert.equal(parseHash('#library?kind=plugin&show=diff&view=list').show, 'diff');
  const market = parseHash('#library?kind=marketplace');
  assert.deepEqual([market.view, market.kind], ['library', 'plugin']);
  const hook = parseHash('#library?kind=hook&sel=hook%3APreToolUse%3A%20Bash');
  assert.deepEqual([hook.view, hook.kind, hook.selected], ['library', 'plugin', { kind: 'hook', name: 'PreToolUse: Bash' }]);
  assert.equal(parseHash('#library?kind=instructions&view=list').kind, 'instructions');
  assert.equal(parseHash('#library').kind, 'plugin');
  const server = parseHash('#library?kind=mcp_server&sel=mcp_server%3Agithub');
  assert.deepEqual([server.view, server.mode, server.selected], ['gateway', 'list', { kind: 'mcp_server', name: 'github' }]);
  // A page that still goes to the Library's MCP servers lands on the Gateway's List.
  go('library', { kind: 'mcp_server', show: 'mine', mode: 'list' });
  assert.deepEqual([state.view, state.mode], ['gateway', 'list']);
  go('library', { kind: 'skill', mode: 'list' });
  assert.deepEqual([state.view, state.kind], ['library', 'plugin']);
});

test('an arrival opens its row and its Details', async () => {
  const { arrival } = await import('../../src/kitden/web/static/js/store.js');
  selected.length = 0;
  answers['/api/library-list'] = LIST;
  Object.assign(state, { view: 'library', mode: 'list', kind: 'plugin', show: 'mine', attention: false, q: '', project: '' });
  await loadLibrary();
  state.selected = { kind: 'plugin', name: 'superpowers@demo-market' };
  arrival.pending = true;
  main.replaceChildren();
  renderLibrary(main);
  assert.deepEqual(selected, ['item:p2']);
  assert.equal(rowOf('item:p2').getAttribute('aria-selected'), 'true');
  assert.ok(rowOf('item:p2').classList.contains('arrive'));
});

test('a search opens a plugin whose part it found', async () => {
  await showList({ q: 'plan' });
  assert.ok(rowIds().includes('part:p2:skills:plan'));
  await showList();
  assert.ok(!rowIds().includes('part:p2:skills:plan'));
});

test('listRows is the grid in order, with depth, folds and Details', () => {
  const rows = listRows(LIST, new Set(['item:p2']), new Set(['group:settings']));
  assert.deepEqual(rows.map((r) => [r.id, r.depth, r.expanded]), [
    ['group:marketplace:demo-market', 0, true], ['item:p2', 1, true],
    ['part:p2:skills:brainstorm', 2, undefined], ['part:p2:skills:plan', 2, undefined], ['part:p2:commands:ship', 2, undefined],
    ['item:p1', 1, undefined], ['group:skills', 0, true], ['item:s1', 1, undefined], ['group:settings', 0, false],
  ]);
  // A marketplace's row opens Details on Enter; another group folds.
  assert.equal(rows[0].group, false);
  assert.equal(rows.find((r) => r.id === 'group:skills').group, true);
});

test('Details a row opened follow another project, and close when it is gone there', async () => {
  await showList();
  selected.length = 0;
  hows.length = 0;
  rowOf('item:p2').listeners.click[0]({ target: rowOf('item:p2') });
  assert.deepEqual(selected, ['item:p2']);
  // Its Details show (library-details.js draws them).
  const { panelState } = await import('../../src/kitden/web/static/js/panel.js');
  pages['#drawer'].classList.add('open');
  panelState.current = { type: 'library', id: 'item:p2' };
  // Another project with the same plugin: the same Details, drawn for it.
  data.projects = [{ id: 'a', path: '/home/work/atlas' }, { id: 'b', path: '/home/work/bare' }];
  Object.assign(state, { project: 'a' });
  data.scope.libraryMap = 'a';
  await loadLibrary();
  main.replaceChildren();
  renderLibrary(main);
  assert.deepEqual([selected.at(-1), hows.at(-1)], ['item:p2', { follow: true }]);
  // Drawn again for the same project: nothing more.
  main.replaceChildren();
  renderLibrary(main);
  assert.equal(selected.length, 2);
  // A project whose map has no superpowers: Details let go.
  Object.assign(state, { project: 'b' });
  data.libraryMap = { ...MAP, groups: MAP.groups.slice(1) };
  data.scope.libraryMap = 'b';
  await loadLibrary();
  main.replaceChildren();
  renderLibrary(main);
  assert.deepEqual([selected.at(-1), hows.at(-1)], [null, { follow: true }]);
  Object.assign(state, { project: '' });
  data.libraryMap = MAP;
  data.scope.libraryMap = '';
  pages['#drawer'].classList.remove('open');
  panelState.current = null;
});

test('an arrival for a skill inside a plugin opens the plugin at its row, which shows its flag', async () => {
  const { arrival } = await import('../../src/kitden/web/static/js/store.js');
  selected.length = 0;
  answers['/api/library-list'] = LIST;
  Object.assign(state, { view: 'library', mode: 'list', kind: 'plugin', show: 'mine', attention: false, q: '', project: '' });
  await loadLibrary();
  state.selected = { kind: 'skill', name: 'plan' };
  arrival.pending = true;
  main.replaceChildren();
  renderLibrary(main);
  assert.deepEqual(selected, ['part:p2:skills:plan']);
  assert.equal(rowOf('item:p2').getAttribute('aria-expanded'), 'true');
  assert.ok(rowOf('part:p2:skills:plan').classList.contains('arrive'));
  assert.ok(texts(rowOf('part:p2:skills:plan')).includes('Same name, another source.'));
});

test('a part the map does not draw opens its plugin, an account row opens its own card', async () => {
  // documents: Kitden read nothing inside it, so the map has no part blocks; the List has its
  // skills from the skill rows. "Claude account plugins and connectors" is not on the map at all.
  const documents = item('p9', 'plugin', 'documents', { claude_code: cell('none'), codex: cell('on'), cursor: cell('none') }, {
    lookup: 'documents@openai-curated', count: null,
    parts: [{ key: 'skills', kind: 'skill', name: 'docx', source: 'documents@openai-curated', same_name: false, lookup: 'docx', flags: [], cells: { claude_code: cell('none'), codex: cell('on'), cursor: cell('none') } }],
  });
  const account = { ...item('acc', 'plugin', 'Claude account plugins and connectors', { claude_code: cell('unk'), codex: cell('none'), cursor: cell('none') }), parts: [], account: true, reason: 'Stored in your Claude account. Change it in the Claude app or on claude.ai.' };
  const list = { ...LIST, groups: [...LIST.groups, { key: 'other', name: 'Other plugins', icon: 'puzzle', kind: 'other', items: [documents, account] }] };
  const mapAnswer = { ...MAP, groups: [...MAP.groups, { key: 'other', name: 'Other plugins', icon: 'puzzle', kind: 'other', items: [{ id: 'p9', name: 'documents', kind: 'plugin', plugin: 'documents@openai-curated', by: { codex: 'on' }, through: {}, items: { codex: ['cx-doc'] }, here: false, source: 'Other plugins', technical: {}, can: { add: [], off: [], on: [], remove: [], project: [] } }] }] };
  tick(5); // a new read: the List's answer changed
  await showList({ list });
  data.libraryMap = mapAnswer;
  selected.length = 0;
  rowOf('item:p9').listeners.click[0]({ target: walk(rowOf('item:p9')).find((n) => n.classList.contains('caret')) });
  main.replaceChildren();
  renderLibrary(main);
  rowOf('part:p9:skills:docx').listeners.click[0]({ target: rowOf('part:p9:skills:docx') });
  assert.deepEqual(selected, ['item:p9']);
  rowOf('item:acc').listeners.click[0]({ target: rowOf('item:acc') });
  assert.equal(selected.at(-1), 'item:acc');
  const thing = libraryThing('item:acc');
  assert.deepEqual([thing.block.kind, thing.block.name, thing.block.item.by], ['account', 'Claude account plugins and connectors', { claude_code: 'unknown' }]);
  assert.equal(thing.block.reason, 'Stored in your Claude account. Change it in the Claude app or on claude.ai.');
  // An Overview arrival for docx opens documents' Details too.
  const { arrival } = await import('../../src/kitden/web/static/js/store.js');
  selected.length = 0;
  state.selected = { kind: 'skill', name: 'docx' };
  arrival.pending = true;
  main.replaceChildren();
  renderLibrary(main);
  assert.deepEqual(selected, ['item:p9']);
  data.libraryMap = MAP;
  tick(5);
});
