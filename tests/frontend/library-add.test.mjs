import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

// The Library's add panel beside its map, in a small browser (as in library-map.test.mjs):
// elements with parents, the page's fixed parts, a narrow window (Details are the drawer, with no
// skeleton), frames and a clock that only the test moves, and a stand-in server.
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
delete globalThis.navigator;
let now = 0;
let frames = [];
Object.defineProperty(globalThis, 'performance', { value: { now: () => now, mark() {}, measure() {}, getEntriesByName: () => [] }, configurable: true, writable: true });
globalThis.requestAnimationFrame = (fn) => frames.push(fn);
const tick = (ms) => { now += ms; const run = frames; frames = []; for (const fn of run) fn(now); };
const settle = () => { while (frames.length) tick(10000); };
const flush = async () => { settle(); await new Promise((done) => setImmediate(done)); settle(); };
globalThis.ResizeObserver = class { observe() {} disconnect() {} };
globalThis.MutationObserver = class { observe() {} };
globalThis.innerWidth = 1440;
globalThis.getComputedStyle = () => ({ strokeDasharray: 'none', strokeOpacity: '1', paddingLeft: '0', paddingRight: '0' });
globalThis.localStorage = { getItem: () => null, setItem() {} };
globalThis.addEventListener = () => {};
globalThis.window = { addEventListener() {}, removeEventListener() {} };

const walk = (root) => root.children.flatMap((n) => [n, ...walk(n)]);
function detach(node) {
  const parent = node.parentNode;
  if (!parent) return;
  parent.children.splice(parent.children.indexOf(node), 1);
  node.parentNode = null;
}
const NO_BOX = { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 };
function element(tagName) {
  let names = [];
  const attributes = new Map();
  const style = { setProperty(name, value) { style[name] = value; }, removeProperty(name) { delete style[name]; } };
  const node = {
    tagName, style, dataset: {}, children: [], parentNode: null, textContent: '', listeners: {}, animations: [], hidden: false, offsetLeft: 0, offsetTop: 0, offsetWidth: 0, offsetHeight: 0,
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
    append(...nodes) { for (const n of nodes) node.insertBefore(typeof n === 'string' ? Object.assign(element('#text'), { textContent: n }) : n, null); },
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
    querySelectorAll(selector) {
      const key = selector.match(/^\[data-(\w+)\]$/);
      return key ? walk(node).filter((n) => n.dataset[key[1]] !== undefined) : [];
    },
    getBoundingClientRect: () => NO_BOX,
    getClientRects: () => [],
    setPointerCapture() {},
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
for (const id of ['#main', '#drawer', '#scrim', '.shell', '#dock', '#find-chip', '#said', '#content', '#topbar']) {
  pages[id] = element('DIV');
  pages[id].root = true;
}
const hintLine = element('P');
const docHeard = {};
globalThis.document = {
  hidden: false, activeElement: null, body: element('BODY'),
  createElement: (tag) => element(tag.toUpperCase()), createElementNS: (namespace, tag) => element(tag),
  querySelector: (selector) => pages[selector] ?? null, querySelectorAll: () => [], getElementById: (id) => (id === 'hint' ? hintLine : null),
  addEventListener(type, fn) { (docHeard[type] ||= []).push(fn); },
  removeEventListener(type, fn) { docHeard[type] = (docHeard[type] || []).filter((f) => f !== fn); },
  documentElement: { classList: { add() {}, remove() {} }, style: { setProperty() {}, removeProperty() {} } },
};
document.body.root = true;

// The stand-in server: the offers, and a batch preview with one row per request.
const sent = [];
let offers = null;
globalThis.fetch = async (url, init = {}) => {
  const body = init.body ? JSON.parse(init.body) : null;
  sent.push({ url, body });
  if (url === '/api/library-offers') {
    if (!offers) return { ok: false, status: 500, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ offers }) };
  }
  if (url === '/api/batch/preview') {
    const rows = body.requests.map((r, at) => ({ id: r.id, kind: r.kind, title: r.title, detail: '', project: null, steps: [at], after: [] }));
    const json = { id: `c${sent.length}`, action: 'batch', state: 'previewed', error: null, undo_note: null, steps: body.requests.map(() => ({ client: 'claude_code', name: 'x' })), rows };
    return { ok: true, status: 200, json: async () => json };
  }
  if (/^\/api\/changes\/[^/]+\/apply$/.test(url)) return { ok: true, status: 200, json: async () => ({ id: url.split('/')[3], state: 'verified', error: null }) };
  return { ok: true, status: 200, json: async () => ({}) };
};

const { initLibraryAdd, libraryRowWords, openLibraryAdd } = await import('../../src/kitden/web/static/js/library-add.js');
const { libraryTree, withWaiting } = await import('../../src/kitden/web/static/js/library-map.js');
const { renderLibrary } = await import('../../src/kitden/web/static/js/library.js');
const { layoutTree } = await import('../../src/kitden/web/static/js/map.js');
const { closePanel, initPanel, isPanelOpen, panelState } = await import('../../src/kitden/web/static/js/panel.js');
const { reducedMotion } = await import('../../src/kitden/web/static/js/motion.js');
const { data, state } = await import('../../src/kitden/web/static/js/store.js');
const { setHint } = await import('../../src/kitden/web/static/js/parts.js');
const { applyTray, cancelTray, endApplied, tray } = await import('../../src/kitden/web/static/js/tray.js');
initPanel();
initLibraryAdd();

// The map's answer: superpowers is on in Claude Code and can go to Codex; pr-review is in both.
const none = { skills: [], commands: [], agents: [], hooks: [], mcp_servers: [] };
const plugin = (id, name, fields) => ({ id, name, kind: 'plugin', plugin: `${name}@demo-market`, by: {}, through: {}, items: {}, here: false, source: 'demo-market', technical: {}, can: { add: [], off: [] }, ...fields });
const MAP = {
  clients: [
    { id: 'claude_code', name: 'Claude Code', state: 'on', words: 'Connected' },
    { id: 'codex', name: 'Codex', state: 'on', words: 'Connected' },
    { id: 'cursor', name: 'Cursor', state: 'via', words: 'Via Claude Code' },
  ],
  groups: [
    { key: 'marketplace:demo-market', name: 'demo-market', icon: 'store', kind: 'marketplace', items: [
      plugin('p1', 'pr-review', { by: { claude_code: 'on', codex: 'on' }, inside: { ...none, mcp_servers: ['pr-index'] }, count: 1 }),
      plugin('p2', 'superpowers', { by: { claude_code: 'on' }, inside: { ...none, skills: ['planning', 'brainstorming'] }, count: 2, can: { add: ['codex'], off: [] } }),
    ] },
    { key: 'skills', name: 'Your skills', icon: 'user-round', kind: 'skills', items: [
      { id: 's1', name: 'release-notes', kind: 'skill', by: { claude_code: 'on' }, through: {}, items: {}, here: false, source: '', technical: {}, skill: 'release-notes@skills', can: { add: ['codex'], off: [] } },
    ] },
  ],
};
// The offers (/api/library-offers): by marketplace, then name.
const NEEDS = 'This skill needs the rest of its plugin. Add the plugin instead.';
const OFFERS = [
  { id: 'db-tools@demo-market', kind: 'plugin', name: 'db-tools', marketplace: 'demo-market', count: 1, unit: 'item', routes: { claude_code: 'ready', codex: 'ready' }, installed: [], refusal: null },
  { id: 'planning@superpowers@demo-market', kind: 'skill', name: 'planning', marketplace: 'demo-market', routes: { codex: 'ready' }, installed: ['claude_code', 'cursor'], refusal: null },
  { id: 'pr-review@demo-market', kind: 'plugin', name: 'pr-review', marketplace: 'demo-market', count: 1, unit: 'item', routes: { claude_code: 'ready', codex: 'ready' }, installed: ['claude_code', 'codex'], refusal: null },
  { id: 'superpowers@demo-market', kind: 'plugin', name: 'superpowers', marketplace: 'demo-market', count: 2, unit: 'skill', routes: { claude_code: 'ready', codex: 'ready' }, installed: ['claude_code'], refusal: null },
  { id: 'rooted@toolbox@team-market', kind: 'skill', name: 'rooted', marketplace: 'team-market', routes: {}, installed: [], refusal: NEEDS },
  { id: 'toolbox@team-market', kind: 'plugin', name: 'toolbox', marketplace: 'team-market', routes: { claude_code: 'ready' }, installed: [], refusal: null },
];

const wait = (ms = 0) => new Promise((resolve) => setTimeout(resolve, ms));
const text = (node) => (node.children.length ? node.children.map(text).join(' ') : node.textContent).trim();
const main = pages['#main'];
const drawer = pages['#drawer'];
const map = () => main.children.find((n) => n.classList.contains('map')) || null;
const node = (box, key) => walk(box).find((n) => n.dataset.focus === key) || null;
const find = (fn) => walk(drawer).filter(fn);
const search = () => find((n) => n.tagName === 'INPUT')[0];
const rows = () => find((n) => n.className.split(' ').includes('res'));
const shown = () => rows().filter((n) => !n.hidden);
const row = (name) => rows().find((r) => text(r.children[2].children[0]) === name);
const captions = () => find((n) => n.className === 'add-group');
const pill = () => find((n) => n.className === 'seg sm')[0].children.filter((n) => n.tagName === 'BUTTON');
const rowWords = (r) => [text(r.children[2].children[0]), r.children[2].children[1].textContent, r.children[3].textContent];
const fire = (target, type, event = {}) => { for (const fn of target.listeners[type] || []) fn({ preventDefault() {}, stopPropagation() {}, target, ...event }); };
const press = async (target) => { fire(target, 'click'); await wait(); await wait(); };
const pointer = (type, x, y) => { for (const fn of [...(docHeard[type] || [])]) fn({ type, clientX: x, clientY: y }); };
const bodies = () => tray.rows.map((r) => r.body);

function showMap() {
  Object.assign(data, { libraryMap: MAP, projects: [] });
  data.scope.libraryMap = '';
  Object.assign(state, { view: 'library', mode: 'map', project: '', q: '', selected: null });
  main.replaceChildren();
  setHint('');
  renderLibrary(main);
  settle();
  return map();
}

// The map drawn, then "+ Add" beside its Plugins and skills caption pressed, and the offers read.
async function open() {
  offers = OFFERS;
  const box = showMap();
  const add = node(box, 'add:plugins');
  await press(add);
  await wait(10);
  return { box, add };
}

async function done() {
  await cancelTray();
  closePanel({ instant: true, focus: false });
  reducedMotion.matches = false;
  await flush();
}

test('the map hint says the decided words', () => {
  showMap();
  assert.equal(hintLine.children.at(-1).textContent, 'Point at a link and press × to remove it · drag a plugin onto a client to add it there · + adds it for all projects · click anything for its Details');
});

test('+ Add opens Add a plugin or skill; the pill filters Plugins and Skills', async () => {
  const { add } = await open();
  try {
    assert.equal(isPanelOpen(), true);
    assert.deepEqual(panelState.current, { type: 'library-add' });
    const [head, body, foot] = drawer.children;
    assert.deepEqual([text(head.children[0]), text(head.children[1])], ['Library Close', 'Add a plugin or skill']);
    assert.equal(document.activeElement, search());
    assert.deepEqual([search().placeholder, search().getAttribute('aria-label')], ['Search the marketplaces…', 'Search the marketplaces']);
    assert.deepEqual(pill().map((b) => [b.textContent, b.getAttribute('aria-pressed')]), [['All', 'true'], ['Plugins', 'false'], ['Skills', 'false']]);
    assert.deepEqual(text(foot), 'Click to preview, or drag onto a client.');
    assert.deepEqual([add.className, add.getAttribute('aria-expanded')], ['btn small primary', 'true']);
    // One group per marketplace, in name order, each with the store icon.
    assert.deepEqual(captions().map(text), ['demo-market', 'team-market']);
    assert.ok(captions().every((c) => c.children[0].dataset.icon === 'store'));
    assert.deepEqual(rows().map((r) => rowWords(r).slice(0, 2)), [
      ['db-tools', 'Plugin · 1 item'], ['planning', 'Skill'], ['pr-review', 'Plugin · 1 item'], ['superpowers', 'Plugin · 2 skills'], ['rooted', NEEDS], ['toolbox', 'Plugin'],
    ]);
    assert.deepEqual(rows().map((r) => r.children[1].children[0].dataset.icon), ['puzzle', 'sparkles', 'puzzle', 'puzzle', 'sparkles', 'puzzle']);
    // A quiet "Add a marketplace…" ends the list.
    const more = body.children.at(-1);
    assert.deepEqual([more.textContent, more.className], ['Add a marketplace…', 'btn ghost small add-more']);
    await press(pill()[1]);
    assert.deepEqual(shown().map((r) => rowWords(r)[0]), ['db-tools', 'pr-review', 'superpowers', 'toolbox']);
    await press(pill()[2]);
    assert.deepEqual(shown().map((r) => rowWords(r)[0]), ['planning', 'rooted']);
    search().value = 'ROOT';
    fire(search(), 'input');
    assert.deepEqual(shown().map((r) => rowWords(r)[0]), ['rooted']);
    assert.deepEqual(captions().map((c) => c.hidden), [true, false]);
    // Only the offers were read: nothing is written, and the tray is empty.
    assert.deepEqual(tray.rows, []);
  } finally {
    await done();
  }
});

test('a row says Added, In every client, its refusal or In preview', () => {
  const [db, planning, pr, superpowers, rooted] = OFFERS;
  assert.deepEqual(libraryRowWords(db), { status: '', off: false, line: 'Plugin · 1 item' });
  assert.deepEqual(libraryRowWords(superpowers, { inTray: true }), { status: 'In preview', off: false, line: 'Plugin · 2 skills' });
  assert.deepEqual(libraryRowWords(pr), { status: 'In every client', off: true, line: 'Plugin · 1 item' });
  assert.deepEqual(libraryRowWords(rooted), { status: '', off: true, line: NEEDS });
  assert.deepEqual(libraryRowWords(planning, { added: new Map([[planning.id, ['codex']]]) }), { status: 'Added', off: true, line: 'Skill' });
});

test('a click adds for all projects to every client with a route that lacks it, and a second click takes it out', async () => {
  await open();
  try {
    const db = row('db-tools');
    await press(db);
    await flush();
    assert.deepEqual(bodies(), [{ action: 'plugin.install', targets: [{ client: 'claude_code' }, { client: 'codex' }], params: { plugin: 'db-tools@demo-market' } }]);
    assert.deepEqual(rowWords(db), ['db-tools', 'Plugin · 1 item', 'In preview']);
    assert.ok(db.classList.contains('on'));
    await press(db);
    await flush();
    assert.deepEqual(tray.rows, []);
    assert.deepEqual([rowWords(db)[2], db.classList.contains('on')], ['', false]);
    // superpowers lacks only Codex; a skill goes to the clients it can be copied to.
    await press(row('superpowers'));
    await press(row('planning'));
    await flush();
    assert.deepEqual(bodies(), [
      { action: 'plugin.install', targets: [{ client: 'codex' }], params: { plugin: 'superpowers@demo-market' } },
      { action: 'skill.install', targets: [{ client: 'codex' }], params: { skill: 'planning@superpowers@demo-market' } },
    ]);
    // A greyed row adds nothing.
    await cancelTray();
    for (const name of ['pr-review', 'rooted']) await press(row(name));
    assert.deepEqual(tray.rows, []);
    // Enter does what a click does.
    fire(row('toolbox'), 'keydown', { key: 'Enter' });
    await flush();
    assert.deepEqual(bodies(), [{ action: 'plugin.install', targets: [{ client: 'claude_code' }], params: { plugin: 'toolbox@team-market' } }]);
  } finally {
    await done();
  }
});

test('after Apply a row says Added, and an Undo frees it', async () => {
  await open();
  try {
    await press(row('db-tools'));
    await flush();
    await applyTray();
    assert.equal(tray.phase, 'applied');
    // The page reads the result, then the tray empties: the panel reads the offers again.
    offers = OFFERS.map((o) => (o.name === 'db-tools' ? { ...o, installed: ['claude_code', 'codex'] } : o));
    const before = sent.filter((s) => s.url === '/api/library-offers').length;
    endApplied();
    await wait(10);
    assert.equal(sent.filter((s) => s.url === '/api/library-offers').length, before + 1);
    assert.deepEqual(rowWords(row('db-tools'))[2], 'Added');
    assert.ok(row('db-tools').classList.contains('done') && row('db-tools').classList.contains('off'));
    // Opened again after an Undo, the read frees it.
    closePanel({ instant: true, focus: false });
    offers = OFFERS;
    await openLibraryAdd();
    await wait(10);
    assert.deepEqual(rowWords(row('db-tools'))[2], '');
  } finally {
    offers = OFFERS;
    await done();
  }
});

test('a plugin no client has shows as a preview card with dashed links while it waits', async () => {
  const { box } = await open();
  try {
    await press(row('db-tools'));
    await flush();
    const id = 'item:new:plugin:db-tools@demo-market';
    const card = node(box, `block:${id}`);
    assert.ok(card, 'a new card');
    assert.equal(card.getAttribute('aria-label'), 'db-tools, Preview · for all projects');
    assert.equal(card.dataset.state, 'preview');
    assert.ok(node(box, `link:client:claude_code>${id}`) && node(box, `link:client:codex>${id}`));
    // It sits in its marketplace's group, after the plugins the map had.
    const model = withWaiting(libraryTree(MAP), tray.rows, '');
    const block = model.blocks.find((b) => b.id === id);
    assert.equal(block.parent, 'group:marketplace:demo-market');
    assert.deepEqual(model.links.filter((l) => l.to === id).map((l) => [l.from, l.kind]), [['client:claude_code', 'preview'], ['client:codex', 'preview']]);
    // A press on the card takes it out, and the card goes.
    card.listeners.click[0]();
    await flush();
    assert.deepEqual(tray.rows, []);
    assert.equal(node(box, `block:${id}`), null);
    // A marketplace the map has no group for gets one, before Your skills; one client says its name.
    await press(row('toolbox'));
    await flush();
    const team = withWaiting(libraryTree(MAP), tray.rows, '');
    const groups = team.blocks.filter((b) => b.kind === 'group' && b.column === 'plugins' && !b.parent).map((b) => b.id);
    assert.deepEqual(groups, ['group:marketplace:demo-market', 'group:marketplace:team-market', 'group:skills']);
    assert.equal(node(box, 'block:item:new:plugin:toolbox@team-market').getAttribute('aria-label'), 'toolbox, Preview · Claude Code');
    // An add for one project draws nothing under another, not even its group.
    const elsewhere = withWaiting(libraryTree(MAP), [{ key: 'k1', body: { action: 'plugin.install', targets: [{ client: 'codex' }], params: { plugin: 'toolbox@team-market', project: '/work/atlas' } } }], '');
    assert.ok(!elsewhere.blocks.some((b) => b.id === 'group:marketplace:team-market'));
    // A skill inside a plugin is a skill row of its own.
    await press(row('planning'));
    await flush();
    const skill = withWaiting(libraryTree(MAP), tray.rows, '').blocks.find((b) => b.id === 'item:new:skill:planning@superpowers@demo-market');
    assert.deepEqual([skill.kind, skill.h, skill.meta, skill.parent], ['skill', 34, 'Preview · Codex', 'group:marketplace:demo-market']);
    // One the map shows already waits on its own card.
    await press(row('superpowers'));
    await flush();
    assert.equal(node(box, 'block:item:p2').getAttribute('aria-label'), 'superpowers, Preview · Codex');
  } finally {
    await done();
  }
});

// A press on a panel row and moves of the pointer: the map's area is at the window's top left,
// so a map point is a window point.
function layoutOf() {
  return layoutTree(libraryTree(MAP), { open: new Set(), narrow: false });
}
const onto = (id) => { const at = layoutOf().blocks.find((b) => b.id === id); return [at.x + 10, at.y + 10]; };
const tip = (box) => walk(box).find((n) => n.className.split(' ').includes('dragtip')) || null;
const ghost = () => walk(document.body).find((n) => n.className.split(' ').includes('ghost')) || null;

test('a panel row dragged onto Codex adds for Codex only', async () => {
  const { box } = await open();
  try {
    const db = row('db-tools');
    fire(db, 'pointerdown', { button: 0, pointerId: 1, clientX: 900, clientY: 300 });
    pointer('pointermove', 890, 300);
    assert.ok(db.classList.contains('dragging') && ghost());
    pointer('pointermove', ...onto('client:codex'));
    assert.deepEqual([tip(box).textContent, tip(box).className], ['Add to Codex', 'dragtip on']);
    assert.ok(ghost().classList.contains('over'));
    assert.ok(node(box, 'block:client:codex').className.split(' ').includes('drop'));
    // Cursor gets plugins through Claude Code; Claude Code lacks it too, but only Codex is asked.
    pointer('pointermove', ...onto('client:cursor'));
    assert.equal(tip(box).textContent, 'Cursor gets plugins through Claude Code');
    assert.ok(!ghost().classList.contains('over'));
    pointer('pointermove', ...onto('client:codex'));
    pointer('pointerup', ...onto('client:codex'));
    await flush();
    assert.deepEqual(bodies(), [{ action: 'plugin.install', targets: [{ client: 'codex' }], params: { plugin: 'db-tools@demo-market' } }]);
    // The ghost flies back onto its row; the row says In preview and no longer drags.
    assert.equal(ghost(), null);
    assert.ok(!db.classList.contains('dragging'));
    assert.equal(rowWords(db)[2], 'In preview');
    assert.equal(node(box, 'block:item:new:plugin:db-tools@demo-market').getAttribute('aria-label'), 'db-tools, Preview · Codex');
    fire(db, 'pointerdown', { button: 0, pointerId: 1, clientX: 900, clientY: 300 });
    pointer('pointermove', 880, 300);
    assert.equal(ghost(), null);
    pointer('pointerup', 880, 300);
    // A row that has it everywhere does not drag; a refused drop shakes the client.
    fire(row('pr-review'), 'pointerdown', { button: 0, pointerId: 1, clientX: 900, clientY: 300 });
    pointer('pointermove', 880, 300);
    assert.equal(ghost(), null);
    pointer('pointerup', 880, 300);
    fire(row('superpowers'), 'pointerdown', { button: 0, pointerId: 1, clientX: 900, clientY: 300 });
    pointer('pointermove', ...onto('client:claude_code'));
    assert.equal(tip(box).textContent, 'Already in Claude Code');
    pointer('pointerup', ...onto('client:claude_code'));
    await flush();
    assert.ok(node(box, 'block:client:claude_code').animations.some((a) => JSON.stringify(a.keyframes).includes('-7px')));
    assert.equal(bodies().length, 1);
  } finally {
    await done();
  }
});

test('Add a marketplace… opens the marketplace form', async () => {
  await open();
  try {
    await press(drawer.children[1].children.at(-1));
    const [head] = drawer.children;
    assert.deepEqual([text(head.children[0]), text(head.children[1])], ['Add marketplace Close', 'From a link']);
    assert.ok(find((n) => n.tagName === 'INPUT').some((n) => n.placeholder === 'owner/repo, a github.com address, or a folder'));
  } finally {
    await done();
  }
});

test('under reduced motion it lands at once', async () => {
  reducedMotion.matches = true;
  const { box } = await open();
  try {
    const motions = () => [drawer, box, document.body].flatMap((root) => walk(root)).flatMap((n) => n.animations).length;
    const before = motions();
    await press(pill()[1]);
    search().value = 'x';
    fire(search(), 'input');
    search().value = '';
    fire(search(), 'input');
    await press(row('db-tools'));
    await flush();
    fire(row('superpowers'), 'pointerdown', { button: 0, pointerId: 1, clientX: 900, clientY: 300 });
    pointer('pointermove', 880, 300);
    pointer('pointerup', 880, 300);
    await flush();
    // The ghost is gone, the card is in place, and nothing moved.
    assert.equal(ghost(), null);
    assert.ok(node(box, 'block:item:new:plugin:db-tools@demo-market'));
    assert.equal(motions(), before);
    // Nothing stays at opacity 0.
    assert.ok([drawer, box].flatMap((root) => walk(root)).every((n) => n.style.opacity !== '0' || n.className === 'ink'));
  } finally {
    await done();
  }
});

test('the panels show no path, address or command, and use no inline style or markup', () => {
  for (const name of ['add-panel.js', 'library-add.js', 'gateway-add.js']) {
    const code = readFileSync(new URL(`../../src/kitden/web/static/js/${name}`, import.meta.url), 'utf8');
    assert.doesNotMatch(code, /innerHTML|cssText|style\s*=|\.style\./, name);
    for (const field of ['url', 'command', 'args', 'path']) assert.doesNotMatch(code, new RegExp(`row\\.${field}\\b`), name);
  }
});
