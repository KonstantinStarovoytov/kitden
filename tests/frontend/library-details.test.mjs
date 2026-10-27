import assert from 'node:assert/strict';
import { test } from 'node:test';

// The Library map's Details, drawn in a small browser (as in library-map.test.mjs): elements, the
// page's fixed parts, a stand-in server for the tray, and frames and a clock that only the test moves.
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
delete globalThis.navigator;
let now = 0;
let frames = [];
Object.defineProperty(globalThis, 'performance', { value: { now: () => now, mark() {}, measure() {}, getEntriesByName: () => [] }, configurable: true, writable: true });
globalThis.requestAnimationFrame = (fn) => frames.push(fn);
const tick = (ms) => { now += ms; const run = frames; frames = []; for (const fn of run) fn(now); };
const settle = () => { while (frames.length) tick(10000); };
const flush = async () => { settle(); await new Promise((done) => setImmediate(done)); settle(); await new Promise((done) => setImmediate(done)); settle(); };
globalThis.ResizeObserver = class { observe() {} disconnect() {} };
// What hears the drawer's class: the test calls it when Details close.
const watchers = [];
globalThis.MutationObserver = class { constructor(fn) { this.fn = fn; } observe(node) { watchers.push({ node, fn: this.fn }); } };
globalThis.innerWidth = 1440;
globalThis.getComputedStyle = () => ({ strokeDasharray: 'none', strokeOpacity: '1', paddingLeft: '0', paddingRight: '0' });
globalThis.localStorage = { getItem: () => null, setItem() {} };
globalThis.addEventListener = () => {};

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
    get childNodes() { return node.children; },
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
    replaceWith(...nodes) { const parent = node.parentNode; for (const n of nodes) parent.insertBefore(n, node); detach(node); },
    remove() { detach(node); },
    replaceChildren(...nodes) { for (const n of [...node.children]) detach(n); node.append(...nodes); },
    contains(other) { for (let at = other; at; at = at.parentNode) if (at === node) return true; return false; },
    focus() { globalThis.document.activeElement = node; },
    matches: () => false,
    closest: () => null,
    querySelector: (selector) => {
      if (selector === ':scope > .ink') return node.children.find((n) => n.classList.contains('ink')) || null;
      if (selector === ':scope > summary') return node.children.find((n) => n.tagName === 'SUMMARY') || null;
      return null;
    },
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
for (const id of ['#main', '#drawer', '#scrim', '.shell', '#dock', '#find-chip', '#said', '#content', '#topbar']) {
  pages[id] = element('DIV');
  pages[id].root = true;
}
const hintLine = element('P');
globalThis.document = {
  hidden: false, activeElement: null, body: element('BODY'),
  createElement: (tag) => element(tag.toUpperCase()), createElementNS: (namespace, tag) => element(tag),
  querySelector: (selector) => pages[selector] ?? null, querySelectorAll: () => [], getElementById: (id) => (id === 'hint' ? hintLine : null),
  listeners: {}, addEventListener(type, fn) { (document.listeners[type] ||= []).push(fn); }, removeEventListener() {},
  documentElement: { classList: { add() {}, remove() {} }, style: { setProperty() {}, removeProperty() {} } },
};
// The tray's server: every preview of the tray's rows comes back as one change.
const sent = [];
globalThis.fetch = (url, init = {}) => {
  const body = init.body ? JSON.parse(init.body) : null;
  if (body) sent.push({ url, body });
  const json = url === '/api/batch/preview'
    ? { id: `c${sent.length}`, action: 'batch', state: 'previewed', error: null, target: { scope: 'all' }, undo_note: null, steps: body.requests.map(() => ({ client: 'claude_code', name: 'x' })), rows: body.requests.map((request, index) => ({ id: request.id, kind: request.kind, title: request.title, detail: '', project: null, steps: [index], target: { scope: 'all' }, after: [], undo_note: null })) }
    : {};
  return Promise.resolve({ ok: true, status: 200, json: async () => json });
};

const { renderLibrary } = await import('../../src/kitden/web/static/js/library.js');
const details = await import('../../src/kitden/web/static/js/library-details.js');
const { libraryTree } = await import('../../src/kitden/web/static/js/library-map.js');
const { closePanel, closeForProject, initPanel, isPanelOpen, panelState } = await import('../../src/kitden/web/static/js/panel.js');
const { data, state } = await import('../../src/kitden/web/static/js/store.js');
const { setHint } = await import('../../src/kitden/web/static/js/parts.js');
const { reducedMotion } = await import('../../src/kitden/web/static/js/motion.js');
const { addToTray, cancelTray, keyFor, tray } = await import('../../src/kitden/web/static/js/tray.js');
// As app.js does: the panel's keys and its tray looks, then the Library's Details.
initPanel();
details.initLibraryDetails();

// The medium sample's answer, cut short (views/library_map.py), with what Details may offer.
const none = { skills: [], commands: [], agents: [], hooks: [], mcp_servers: [] };
const plugin = (id, name, fields) => ({ id, name, kind: 'plugin', plugin: `${name}@demo-market`, by: {}, through: {}, items: {}, here: {}, source: 'demo-market', can: { add: [], off: [] }, technical: {}, ...fields });
const own = (id, name, kind, fields) => ({ id, name, kind, by: {}, through: {}, items: {}, here: {}, source: 'Your skills', can: { off: [] }, technical: {}, ...fields });
const SUPERPOWERS = plugin('p2', 'superpowers', {
  by: { claude_code: 'on', cursor: 'on' }, through: { cursor: 'claude_code' }, items: { claude_code: ['cc-sp'], cursor: ['cu-sp'] },
  inside: { ...none, skills: ['brainstorm', 'plan', 'review'], commands: ['ship'] }, count: 4, can: { add: ['codex'], off: ['claude_code'] },
  technical: { path: '/home/u/.claude/plugins/cache/demo-market/superpowers/1.0.0', marketplace: '/home/u/.claude/plugins/marketplaces/demo-market' },
});
const MEDIUM = {
  clients: [
    { id: 'claude_code', name: 'Claude Code', state: 'on', words: 'Connected' },
    { id: 'codex', name: 'Codex', state: 'on', words: 'Connected' },
    { id: 'cursor', name: 'Cursor', state: 'via', words: 'Via Claude Code' },
  ],
  groups: [
    { key: 'marketplace:demo-market', name: 'demo-market', icon: 'store', kind: 'marketplace', items: [
      plugin('p1', 'pr-review', { by: { claude_code: 'off', cursor: 'off' }, items: { claude_code: ['cc-pr'], cursor: ['cu-pr'] }, inside: { ...none, mcp_servers: ['pr-index'] }, count: 1, can: { add: ['codex'], off: [] } }),
      SUPERPOWERS,
    ] },
    { key: 'skills', name: 'Your skills', icon: 'user-round', kind: 'skills', items: [
      own('s1', 'release-notes', 'skill', { by: { claude_code: 'on', codex: 'on', cursor: 'on' }, through: { cursor: 'claude_code' }, items: { claude_code: ['cc-rn'], codex: ['cx-rn'], cursor: ['cu-rn'] }, can: { off: ['claude_code', 'codex'] }, technical: { path: '/home/u/.claude/skills/release-notes/SKILL.md' } }),
    ] },
    { key: 'settings', name: 'Your settings', icon: 'settings', kind: 'settings', items: [own('h1', 'PreToolUse: Bash', 'hook', { source: 'Your settings', by: { claude_code: 'on' }, items: { claude_code: ['cc-h'] }, can: {} })] },
  ],
  skill_rules: { some: true, projects: { atlas: 'ok', web: 'own', site: 'new' } },
};
const PROJECTS = [{ id: 'atlas', path: '/home/u/work/atlas', exists: true }, { id: 'web', path: '/home/u/work/web', exists: true }, { id: 'site', path: '/home/u/work/site', exists: true }];

const main = pages['#main'];
const drawer = pages['#drawer'];
const map = () => main.children.find((n) => n.classList.contains('map')) || null;
const node = (box, key) => walk(box).find((n) => n.dataset.focus === key) || null;
const texts = (root) => walk(root).map((n) => n.textContent).filter(Boolean);
const press = (n) => n.listeners.click.forEach((fn) => fn({ preventDefault() {} }));
const facts = (card) => card.facts.map((f) => [f.label, typeof f.value === 'string' ? f.value : f.text]);
const labels = (card) => card.actions.map((a) => [a.label, Boolean(a.primary)]);
const c = () => details.context(MEDIUM, '', '');

async function showMap(sample = MEDIUM, { project = '' } = {}) {
  Object.assign(data, { libraryMap: sample, projects: PROJECTS });
  data.scope.libraryMap = project;
  Object.assign(state, { view: 'library', mode: 'map', kind: 'plugin', project, q: '', selected: null });
  main.replaceChildren();
  setHint('');
  renderLibrary(main);
  await flush();
  return map();
}

async function reset() {
  if (isPanelOpen()) closePanel({ instant: true, focus: false });
  await cancelTray();
  sent.length = 0;
}

test('a click on a plugin opens its Inside column, lights the path and opens Details', async () => {
  await reset();
  const box = await showMap();
  const card = node(box, 'block:item:p2');
  card.focus();
  press(card);
  await flush();
  assert.ok(node(box, 'block:part:p2:skills:brainstorm'));
  assert.match(card.className, /\bselected\b/);
  assert.ok(box.classList.contains('focus'));
  assert.equal(isPanelOpen(), true);
  assert.deepEqual(panelState.current, { type: 'library', id: 'item:p2' });
  assert.ok(texts(drawer).includes('superpowers'));
  // Focus moved into Details.
  assert.ok(drawer.contains(document.activeElement));
});

test('a second click on the open selected plugin folds it', async () => {
  await reset();
  const box = await showMap();
  press(node(box, 'block:item:p2'));
  await flush();
  press(node(box, 'block:item:p2'));
  await flush();
  assert.equal(node(box, 'block:part:p2:skills:brainstorm'), null);
  assert.ok(!box.classList.contains('focus'));
  assert.equal(isPanelOpen(), false);
});

test('the Inside rows grow out of the plugin, 15 apart, and fold back in 160 ms', async () => {
  await reset();
  const box = await showMap();
  press(node(box, 'block:item:p2'));
  const rows = ['brainstorm', 'plan', 'review'].map((name) => node(box, `block:part:p2:skills:${name}`));
  // They start small and unseen inside the plugin's right side.
  assert.deepEqual(rows.map((n) => [n.style.opacity, /scale\(0\.3\)/.test(n.style.transform || '')]), [['0', true], ['0', true], ['0', true]]);
  tick(110); // 15 ms past the second one's start
  const seen = rows.map((n) => Number(n.style.opacity));
  assert.ok(seen[0] > seen[1] && seen[1] > seen[2], seen.join(' '));
  await flush();
  assert.ok(rows.every((n) => !n.style.opacity));
  // Folding: they shrink back into it and are gone in 160 ms.
  press(node(box, 'block:item:p2'));
  tick(1);
  tick(150);
  assert.ok(node(box, 'block:part:p2:skills:brainstorm'));
  tick(20);
  assert.equal(node(box, 'block:part:p2:skills:brainstorm'), null);
  await flush();
});

test('under reduced motion the unfold lands at once', async () => {
  await reset();
  reducedMotion.matches = true;
  try {
    const box = await showMap();
    press(node(box, 'block:item:p2'));
    assert.equal(frames.length, 0);
    assert.ok(node(box, 'block:part:p2:skills:brainstorm'));
    assert.ok(walk(box).every((n) => n.style.opacity === undefined || n.style.opacity === ''));
  } finally {
    reducedMotion.matches = false;
    await flush();
  }
});

test('plugin Details show the facts and Add to <client>… steps to a checklist; each tick is one row', async () => {
  await reset();
  const card = details.pluginCard(SUPERPOWERS, c());
  assert.deepEqual([card.kind, card.title, card.id], ['Plugin', 'superpowers', 'demo-market']);
  assert.deepEqual(facts(card), [['State', 'On'], ['Inside', '3 skills · 1 command'], ['Clients', 'Claude Code, Cursor'], ['Comes from', 'All projects']]);
  // A plugin no client has on: "None yet", as the mockup says.
  assert.deepEqual(facts(details.pluginCard(MEDIUM.groups[0].items[0], c()))[2], ['Clients', 'None yet']);
  assert.equal(card.why, 'Claude Code loads it in every project. Cursor gets it through Claude Code.');
  assert.deepEqual(labels(card), [['Add to Codex…', true], ['Turn off for all projects…', false]]);
  // Paths only under Technical details.
  assert.ok(texts(card.technical).some((t) => t.includes('superpowers/1.0.0')));
  assert.ok(![card.why, ...facts(card).flat()].some((t) => String(t).includes('/')));
  const box = await showMap();
  press(node(box, 'block:item:p2'));
  await flush();
  press(node(drawer, 'action:Add to Codex…'));
  await flush();
  assert.deepEqual(panelState.current, { type: 'library', id: 'item:p2', step: 'add' });
  assert.ok(texts(drawer).includes('Add superpowers to the clients you pick'));
  const codex = node(drawer, 'tick:codex');
  assert.equal(document.activeElement, codex);
  assert.deepEqual([codex.disabled, node(drawer, 'tick:claude_code').disabled], [false, true]);
  press(codex);
  await flush();
  assert.deepEqual(tray.rows.map((r) => r.body), [{ action: 'plugin.install', targets: [{ client: 'codex' }], params: { plugin: 'superpowers@demo-market' } }]);
  assert.equal(codex.getAttribute('aria-checked'), 'true');
  assert.ok(texts(codex).includes('In preview'));
  assert.equal(codex.getAttribute('aria-label'), 'Codex, In preview');
  // Done steps back, focus on the button that stepped there.
  press(walk(drawer).find((n) => n.textContent === 'Done'));
  await flush();
  assert.equal(panelState.current.step, undefined);
  assert.equal(document.activeElement, node(drawer, 'action:Add to Codex…'));
});

test('Cursor is never a choice for a plugin', async () => {
  await reset();
  const both = { ...SUPERPOWERS, items: {}, by: {}, can: { add: ['claude_code', 'codex'], off: [] } };
  assert.equal(details.addLabel(both.can.add), 'Add to Claude Code or Codex…');
  const nodes = details.addNodes(both, () => {});
  const ticks = walk(nodes[1]).filter((n) => n.dataset.focus?.startsWith('tick:')).map((n) => n.dataset.focus);
  assert.deepEqual(ticks, ['tick:claude_code', 'tick:codex']);
  const card = details.pluginCard({ ...SUPERPOWERS, can: { add: [], off: [] } }, c());
  assert.ok(!labels(card).some(([label]) => label.startsWith('Add to')));
});

test('an inside item says Follows its plugin and has no switch', async () => {
  await reset();
  const model = libraryTree(MEDIUM);
  const part = model.blocks.find((b) => b.id === 'part:p2:skills:brainstorm');
  const card = details.partCard(part, c());
  assert.deepEqual([card.kind, card.title, card.why], ['Skill', 'brainstorm', 'Follows its plugin.']);
  assert.deepEqual(facts(card), [['Plugin', 'superpowers'], ['Kind', 'Skill'], ['Source', 'demo-market'], ['Clients', '2 clients']]);
  assert.equal((card.actions || []).length, 0);
  assert.equal(card.after, null);
  // In a project Claude Code can take a rule in: one quiet line that turns its plugin off there.
  const here = details.partCard(part, details.context(MEDIUM, 'atlas', 'atlas'));
  assert.equal(here.after.textContent, '');
  assert.equal(here.after.title, 'Turn off superpowers in this project…');
  assert.match(here.after.className, /ghost/);
});

test("a skill's Turn off for all projects adds one skill.rule row per client that can", async () => {
  await reset();
  const skill = MEDIUM.groups[1].items[0];
  const card = details.skillCard(skill, c());
  assert.deepEqual(facts(card), [['Plugin', 'None, a skill on its own'], ['State', 'On'], ['Comes from', 'All projects'], ['Source', 'Your skills'], ['Clients', '3 clients']]);
  assert.deepEqual(labels(card), [['Turn off for all projects…', false], ['Turn off in some projects…', false]]);
  assert.match(card.why, /Codex has no switch for one project\. Cursor has no switch to turn off one skill\.$/);
  assert.deepEqual(details.offBodies(skill), [
    { action: 'skill.rule', targets: [{ client: 'claude_code', item: 'cc-rn' }], params: { scope: 'all', off: true } },
    { action: 'skill.rule', targets: [{ client: 'codex', item: 'cx-rn' }], params: { scope: 'all', off: true } },
  ]);
  const box = await showMap();
  press(node(box, 'block:item:s1'));
  await flush();
  const off = node(drawer, 'action:Turn off for all projects…');
  press(off);
  await flush();
  assert.deepEqual(tray.rows.map((r) => r.key), ['skill:claude_code:cc-rn@', 'skill:codex:cx-rn@']);
  assert.equal(off.getAttribute('aria-disabled'), 'true');
  assert.ok(texts(off).includes('In preview'));
  // A plugin turns off with its own switch, one row per client that has it on.
  assert.deepEqual(details.offBodies(SUPERPOWERS), [{ action: 'plugin.disable', targets: [{ item: 'cc-sp' }], params: {} }]);
});

test('Turn off in some projects… uses the project checklist', async () => {
  await reset();
  const skill = MEDIUM.groups[1].items[0];
  // Offered only while no file blocks a one-project rule.
  assert.equal(details.offersSome(skill, details.context({ ...MEDIUM, skill_rules: { some: false, projects: { atlas: 'ok' } } })), false);
  // ... and only while some project can take the rule.
  assert.equal(details.offersSome(skill, details.context({ ...MEDIUM, skill_rules: { some: true, projects: { web: 'own', site: 'new' } } })), false);
  const box = await showMap();
  press(node(box, 'block:item:s1'));
  await flush();
  press(node(drawer, 'action:Turn off in some projects…'));
  await flush();
  assert.ok(texts(drawer).includes('Turn off release-notes in the projects you pick'));
  assert.equal(document.activeElement, node(drawer, 'find'));
  const rows = ['atlas', 'site', 'web'].map((id) => node(drawer, `tick:${id}`));
  assert.deepEqual(rows.map((n) => n.disabled), [false, true, true]);
  assert.ok(texts(rows[2]).includes('Has its own skill settings'));
  assert.ok(texts(rows[1]).includes('No Claude Code settings yet'));
  press(rows[0]);
  await flush();
  assert.deepEqual(tray.rows.map((r) => r.body), [{ action: 'skill.rule', targets: [{ client: 'claude_code', item: 'cc-rn' }], params: { scope: 'project', project: 'atlas', off: true } }]);
  assert.ok(texts(drawer).includes('1 project in preview. Apply them from the tray.'));
  press(rows[0]);
  await flush();
  assert.equal(tray.rows.length, 0);
});

test('a hook, a client, a link and a marketplace have their own Details', async () => {
  await reset();
  const hook = details.hookCard(MEDIUM.groups[2].items[0], c());
  assert.deepEqual([hook.kind, facts(hook), hook.actions], ['Hook', [['State', 'On'], ['Comes from', 'All projects'], ['Source', 'Your settings'], ['Clients', '1 client']], undefined]);
  const client = details.clientCard('claude_code', c());
  assert.deepEqual([client.kind, client.title, client.id], ['Client', 'Claude Code', 'Connected']);
  assert.deepEqual(texts(client.list).filter((t) => !t.includes('<')), ['Loads in every project', 'superpowers', 'Plugin · 4 items', 'release-notes', 'Skill', 'PreToolUse: Bash', 'Hook']);
  const model = libraryTree(MEDIUM);
  const byId = new Map(model.blocks.map((b) => [b.id, b]));
  const link = details.connectionCard({ from: byId.get('client:cursor'), to: byId.get('item:p2') }, c());
  assert.deepEqual([link.kind, link.id, facts(link), link.why], ['Connection', 'Through Claude Code', [['From', 'Cursor'], ['To', 'superpowers'], ['State', 'On'], ['Written in', "Claude Code's settings"]], "Cursor loads superpowers through Claude Code's folder."]);
  const market = details.marketplaceCard(MEDIUM.groups[0]);
  assert.deepEqual([market.kind, market.title, texts(market.list)], ['Marketplace', 'demo-market', ['Plugins on the map', 'pr-review', 'Plugin · 1 item', 'superpowers', 'Plugin · 4 items']]);
  // On the map: a link and the caption open their Details.
  const box = await showMap();
  const caption = node(box, 'block:group:marketplace:demo-market');
  assert.equal(caption.tagName, 'BUTTON');
  press(caption);
  await flush();
  assert.ok(texts(drawer).includes('Plugins on the map'));
  const hit = node(box, 'link:client:claude_code>item:p2');
  press(hit);
  await flush();
  assert.deepEqual(panelState.current, { type: 'library', id: 'client:claude_code>item:p2' });
  assert.ok(texts(drawer).includes('Claude Code loads superpowers in every project.'));
});

test("a Cursor plugin's link has no ×, and its Details say where to remove it", () => {
  const ui = plugin('p9', 'ui-kit', { by: { cursor: 'on' }, items: { cursor: ['cu-ui'] }, can: { add: [], off: [], remove: [] } });
  const cursor = { id: 'client:cursor', kind: 'client', client: 'cursor', name: 'Cursor' };
  const link = details.connectionCard({ from: cursor, to: { id: 'item:p9', kind: 'plugin', name: 'ui-kit', item: ui } }, c());
  assert.equal(link.why, 'Cursor loads ui-kit in every project. Cursor keeps its plugins in its own database. Remove it in Cursor: Customize → Plugins.');
  // A plugin Claude Code removes has no such line.
  const claude = { id: 'client:claude_code', kind: 'client', client: 'claude_code', name: 'Claude Code' };
  const other = details.connectionCard({ from: claude, to: { id: 'item:p2', kind: 'plugin', name: 'superpowers', item: SUPERPOWERS } }, c());
  assert.equal(other.why, 'Claude Code loads superpowers in every project.');
});

test('a project switch keeps an open plugin and its Details, or lets go when it is gone', async () => {
  await reset();
  const box = await showMap();
  press(node(box, 'block:item:p2'));
  await flush();
  // Another project: Details stay while it is read, and follow the same plugin, drawn for it.
  state.project = 'atlas';
  closeForProject();
  assert.equal(isPanelOpen(), true);
  const atlas = { ...MEDIUM, groups: MEDIUM.groups.map((g) => ({ ...g, items: g.items.map((i) => (i.id === 'p2' ? { ...i, by: { claude_code: 'off', cursor: 'off' }, here: { claude_code: true, cursor: false } } : i)) })) };
  Object.assign(data, { libraryMap: atlas });
  data.scope.libraryMap = 'atlas';
  main.replaceChildren();
  renderLibrary(main, { again: true });
  await flush();
  assert.equal(map(), box);
  assert.ok(node(box, 'block:part:p2:skills:brainstorm'), 'still open');
  assert.equal(isPanelOpen(), true);
  assert.ok(texts(drawer).includes('Off'));
  assert.ok(texts(drawer).includes('This project · atlas'));
  // A project without it: the map lets go and Details close.
  state.project = 'web';
  closeForProject();
  const web = { ...MEDIUM, groups: MEDIUM.groups.map((g) => ({ ...g, items: g.items.filter((i) => i.id !== 'p2') })) };
  Object.assign(data, { libraryMap: web });
  data.scope.libraryMap = 'web';
  main.replaceChildren();
  renderLibrary(main, { again: true });
  await flush();
  assert.equal(isPanelOpen(), false);
  assert.ok(!walk(box).some((n) => /\bselected\b/.test(n.className)));
  state.project = '';
});

test('Enter opens, Escape closes and focus returns', async () => {
  await reset();
  const box = await showMap();
  // A block is a real button: the browser presses it on Enter or Space. Nothing on the map takes
  // the key first.
  const block = node(box, 'block:item:s1');
  assert.deepEqual([block.tagName, block.type], ['BUTTON', 'button']);
  block.focus();
  let kept = false;
  const enter = { key: 'Enter', target: block, preventDefault() { kept = true; }, stopPropagation() {} };
  for (const fn of [...(block.listeners.keydown || []), ...(box.listeners.keydown || [])]) fn(enter);
  assert.equal(kept, false);
  press(block);
  await flush();
  assert.equal(isPanelOpen(), true);
  assert.ok(drawer.contains(document.activeElement));
  // Escape in Details, by panel.js's own key: the panel closes, focus goes back to the block and
  // the map lets go once the drawer has closed.
  const escape = { key: 'Escape', preventDefault() {}, shiftKey: false };
  for (const fn of document.listeners.keydown) fn(escape);
  assert.equal(isPanelOpen(), false);
  for (const { node: watched, fn } of watchers) if (watched === drawer) fn();
  await flush();
  assert.equal(document.activeElement, block);
  assert.ok(!walk(box).some((n) => /\bselected\b/.test(n.className)));
  // Escape on the map lets go of the selection and closes Details; focus stays on the map.
  press(block);
  await flush();
  block.focus();
  box.listeners.keydown.forEach((fn) => fn({ key: 'Escape' }));
  await flush();
  assert.equal(isPanelOpen(), false);
  assert.equal(document.activeElement, block);
});

test('the tray rows keep their keys', () => {
  const skill = MEDIUM.groups[1].items[0];
  assert.equal(keyFor(details.projectBody(skill, 'atlas')), 'skill:claude_code:cc-rn@atlas');
  assert.equal(details.hereBody(SUPERPOWERS, details.context(MEDIUM, 'site', 'site')), null);
  assert.deepEqual(details.hereBody(SUPERPOWERS, details.context(MEDIUM, 'atlas', 'atlas')), { action: 'skill.rule', targets: [{ client: 'claude_code', item: 'cc-sp' }], params: { scope: 'project', project: 'atlas', off: true } });
});

test('the tray never holds a skill rule for all projects and one for a project in Claude Code', async () => {
  await reset();
  const skill = MEDIUM.groups[1].items[0];
  const box = await showMap();
  press(node(box, 'block:item:s1'));
  await flush();
  // A rule for all projects waits: every project row is off and says why.
  await addToTray(details.offBodies(skill)[0]);
  await flush();
  press(node(drawer, 'action:Turn off in some projects…'));
  await flush();
  const atlas = node(drawer, 'tick:atlas');
  assert.equal(atlas.disabled, true);
  assert.ok(texts(atlas).includes('Apply the rule for all projects first'));
  // Out of the tray again: the row can be ticked.
  await cancelTray();
  await flush();
  assert.deepEqual([atlas.disabled, texts(atlas).includes('Apply the rule for all projects first')], [false, false]);
  // A project rule waits: "Turn off for all projects…" leaves Claude Code out and says why.
  press(atlas);
  await flush();
  assert.equal(details.skillOffBodies(skill, MEDIUM).map((b) => b.targets[0].client).join(), 'codex');
  press(walk(drawer).find((n) => n.textContent === 'Done'));
  await flush();
  assert.ok(texts(drawer).includes('Apply the project rules in preview first; then Claude Code can turn it off for all projects.'));
  press(node(drawer, 'action:Turn off for all projects…'));
  await flush();
  assert.deepEqual(tray.rows.map((r) => r.key), ['skill:claude_code:cc-rn@atlas', 'skill:codex:cx-rn@']);
  // A plugin's rule in one project is not skillOverrides: it blocks nothing.
  await cancelTray();
  await addToTray(details.projectBody(SUPERPOWERS, 'atlas'));
  assert.equal(details.skillRuleWaits('project', MEDIUM), false);
  await cancelTray();
});

test('the no-switch notes say only what applies', () => {
  const skill = MEDIUM.groups[1].items[0];
  // Codex has it (a skill of all projects): its note; Cursor only through Claude Code but on: its note.
  assert.match(details.skillCard(skill, c()).why, /Codex has no switch for one project\. Cursor has no switch to turn off one skill\.$/);
  // Even when no project can take the rule, Codex still has no switch for one.
  const closed = details.context({ ...MEDIUM, skill_rules: { some: false, projects: {} } });
  assert.match(details.skillCard(skill, closed).why, /Codex has no switch for one project\./);
  // Cursor off, no Codex: no notes.
  const quiet = { ...skill, by: { claude_code: 'on', cursor: 'off' }, through: {} };
  assert.doesNotMatch(details.skillCard(quiet, c()).why, /no switch/);
  // Off in Codex: no Codex note either.
  const codexOff = { ...skill, by: { claude_code: 'on', codex: 'off', cursor: 'off' }, through: {} };
  assert.doesNotMatch(details.skillCard(codexOff, c()).why, /no switch/);
});

test('where the project decides, only Turn off in this project… is offered', async () => {
  await reset();
  const atlas = details.context(MEDIUM, 'atlas', 'atlas');
  // A plugin the project's shared settings turn on: no switch for all projects (library_map.py).
  const decided = { ...SUPERPOWERS, here: { claude_code: true }, can: { add: [], off: [] } };
  assert.deepEqual(labels(details.pluginCard(decided, atlas)), [['Turn off in this project…', false]]);
  // A project's own skill: a rule in this project, never the user's file.
  const mine = own('s9', 'site-notes', 'skill', { source: 'Only this project', by: { claude_code: 'on' }, items: { claude_code: ['cc-sn'] } });
  const card = details.skillCard(mine, atlas);
  assert.deepEqual(labels(card), [['Turn off in this project…', false]]);
  assert.deepEqual(details.skillHereBody(mine, atlas), { action: 'skill.rule', targets: [{ client: 'claude_code', item: 'cc-sn' }], params: { scope: 'project', project: 'atlas', off: true } });
  // Not where the project cannot take the rule, nor with no project picked.
  assert.equal(details.skillHereBody(mine, details.context(MEDIUM, 'web', 'web')), null);
  assert.equal(details.skillHereBody(mine, c()), null);
  // A skill of all projects that the project does not decide keeps its usual actions.
  assert.equal(details.skillHereBody(MEDIUM.groups[1].items[0], atlas), null);
  // Its button adds the one row, and hides while a rule for all projects waits.
  const button = card.actions[0].node;
  press(button);
  await flush();
  assert.deepEqual(tray.rows.map((r) => r.key), ['skill:claude_code:cc-sn@atlas']);
  await cancelTray();
  await addToTray(details.offBodies(MEDIUM.groups[1].items[0])[0]);
  await flush();
  assert.equal(details.skillCard(mine, atlas).actions[0].node.hidden, true);
  await cancelTray();
});

// The Instructions tab's Details (decisions "Instructions", frames I1 and M8·5): a file and what it
// pulls in. Kitden only reads them: nothing here adds a row to the tray.
const { instructionsTree } = await import('../../src/kitden/web/static/js/library-map.js');
const INSTR = {
  clients: MEDIUM.clients,
  groups: [
    { key: 'all', name: 'All projects', files: [
      { id: 'f2', name: 'AGENTS.md', by: { codex: true }, imports: [], size: 1, technical: { path: '/home/u/.codex/AGENTS.md', lines: ['# Codex'] } },
    ] },
    { key: 'project', name: 'Only this project · website', files: [
      { id: 'f3', name: 'CLAUDE.md', by: { claude_code: true }, imports: ['i2', 'i3', 'i4'], size: 42, technical: { path: '/home/u/work/website/CLAUDE.md', lines: ['# Working on the website', '@docs/design.md'] } },
      { id: 'f4', name: 'AGENTS.md', by: { cursor: true, claude_code: true }, through: 'CLAUDE.md for Claude Code', imports: [], size: 10, technical: { path: '/home/u/work/website/AGENTS.md', lines: ['# Agents'] } },
      { id: 'f5', name: '.cursor/rules', by: { cursor: true }, count: 2, imports: [], technical: { path: '/home/u/work/website/.cursor/rules', lines: ['backend:api', 'style'] } },
      { id: 'f6', name: 'CLAUDE.local.md', by: { claude_code: true }, imports: [], size: null, technical: { path: '/home/u/work/website/CLAUDE.local.md', lines: ['# Long'], cut: true } },
    ] },
    { key: 'commands', name: 'Commands and agents', files: [
      { id: 'c1', kind: 'command', name: 'review', names: ['review'], by: { claude_code: true }, imports: [], size: 3, technical: { path: '/home/u/.claude/commands/review.md', lines: ['# Review'] } },
      { id: 'c2', kind: 'agent', name: 'reviewer', names: ['reviewer'], by: { claude_code: true }, imports: [], size: 5, technical: { path: '/home/u/.claude/agents/reviewer.md', lines: ['# Reviewer'] } },
    ] },
  ],
  imports: [
    { id: 'i2', name: 'docs/design.md', by_files: ['f3'], outside: false, missing: false, technical: { path: '/home/u/work/website/docs/design.md' } },
    { id: 'i3', name: '~/shared.md', by_files: ['f3'], outside: true, missing: false, technical: { path: '/home/u/shared.md' } },
    { id: 'i4', name: 'gone.md', by_files: ['f3'], outside: false, missing: true, technical: {} },
  ],
};
const instr = () => new Map(instructionsTree(INSTR).blocks.map((b) => [b.id, b]));
const ci = () => details.context(INSTR, '', '');

async function showInstructions() {
  Object.assign(data, { libraryMap: MEDIUM, instructionsMap: INSTR, projects: PROJECTS });
  Object.assign(data.scope, { libraryMap: '', instructionsMap: '' });
  Object.assign(state, { view: 'library', mode: 'map', kind: 'instructions', project: '', q: '', selected: null });
  main.replaceChildren();
  setHint('');
  renderLibrary(main);
  await flush();
  return map();
}

test('a click on a file lights its client and imports and opens its Details', async () => {
  await reset();
  const box = await showInstructions();
  press(node(box, 'block:file:f3'));
  await flush();
  const lit = (id) => node(box, `block:${id}`).className.split(' ').includes('lit');
  assert.match(node(box, 'block:file:f3').className, /\bselected\b/);
  assert.deepEqual(['client:claude_code', 'import:i2', 'import:i3', 'import:i4'].map(lit), [true, true, true, true]);
  assert.deepEqual(['client:codex', 'file:f2'].map(lit), [false, false]);
  assert.deepEqual(panelState.current, { type: 'library', id: 'file:f3' });
  for (const words of ['Instruction file', 'CLAUDE.md', 'Read by', 'Claude Code', '42 lines', 'Kitden only reads this file. It brings in 3 more.']) assert.ok(texts(drawer).includes(words), words);
  // An import lights the files that bring it in, not their clients.
  press(node(box, 'block:import:i2'));
  await flush();
  assert.deepEqual(['import:i2', 'file:f3', 'client:claude_code'].map(lit), [true, true, false]);
  assert.ok(texts(drawer).includes('Imported file'));
  // A client lists the files it reads.
  press(node(box, 'block:client:cursor'));
  await flush();
  assert.ok(texts(drawer).includes('.cursor/rules'));
  // A link opens its own Details.
  press(node(box, 'link:client:claude_code>file:f3'));
  await flush();
  assert.ok(texts(drawer).includes('Claude Code reads CLAUDE.md. Kitden only reads this file.'));
  assert.equal(tray.rows.length, 0);
  await reset();
});

test('file Details show Read by, Through, Size and the say line; the path and first lines sit under Technical details', () => {
  const blocks = instr();
  const card = details.fileCard(blocks.get('file:f3'), ci());
  assert.deepEqual([card.kind, card.title, card.id, facts(card), card.why, card.actions], ['Instruction file', 'CLAUDE.md', 'Claude Code · 3 imports', [['Read by', 'Claude Code'], ['Size', '42 lines']], 'Kitden only reads this file. It brings in 3 more.', undefined]);
  const tech = texts(card.technical);
  assert.ok(tech.includes('Technical details'));
  assert.ok(tech.some((t) => t.includes('website/CLAUDE.md')), tech.join(' | '));
  assert.ok(tech.includes('# Working on the website\n@docs/design.md'));
  // Claude Code reads AGENTS.md in place of a CLAUDE.md: Through says so.
  const agents = details.fileCard(blocks.get('file:f4'), ci());
  assert.deepEqual(facts(agents), [['Read by', 'Claude Code, Cursor'], ['Through', 'CLAUDE.md for Claude Code'], ['Size', '10 lines']]);
  assert.equal(agents.why, 'Kitden only reads this file. It imports nothing.');
  // A file longer than Kitden reads, and a rules folder, have no Size.
  assert.deepEqual(facts(details.fileCard(blocks.get('file:f6'), ci())), [['Read by', 'Claude Code']]);
  const rules = details.fileCard(blocks.get('file:f5'), ci());
  assert.deepEqual([rules.id, facts(rules)], ['Cursor · 2 rules', [['Read by', 'Cursor']]]);
  assert.ok(texts(rules.technical).includes('backend:api\nstyle'));
});

// Final fix wave: commands and agents are back, read only, with their own kicker.
test('a command or an agent: its kicker, Read by and Size, Kitden only reads it, and its path under Technical details', () => {
  const blocks = instr();
  const command = details.fileCard(blocks.get('file:c1'), ci());
  assert.deepEqual([command.kind, command.title, command.id, facts(command), command.why, command.actions], ['Command', 'review', 'Claude Code · command', [['Read by', 'Claude Code'], ['Size', '3 lines']], 'Kitden only reads this file.', undefined]);
  const tech = texts(command.technical);
  assert.ok(tech.some((t) => t.includes('.claude/commands/review.md')), tech.join(' | '));
  assert.ok(tech.includes('# Review'));
  assert.equal(details.fileCard(blocks.get('file:c2'), ci()).kind, 'Agent');
  // A client lists it by its kind.
  const client = details.clientCard('claude_code', ci());
  assert.ok(texts(client.list).includes('Command'));
  assert.ok(texts(client.list).includes('Agent'));
});

test('an outside import says Claude Code may ask before it reads this', () => {
  const blocks = instr();
  const outside = details.importCard(blocks.get('import:i3'), ci());
  assert.deepEqual([outside.kind, outside.title, outside.id, outside.why], ['Imported file', '~/shared.md', 'Brought in by CLAUDE.md', 'Kitden only reads it. Claude Code may ask before it reads this.']);
  assert.ok(texts(outside.technical).some((t) => t.includes('shared.md')));
  assert.equal(details.importCard(blocks.get('import:i2'), ci()).why, 'Kitden only reads it.');
  // A missing import says so, and has no path.
  const gone = details.importCard(blocks.get('import:i4'), ci());
  assert.deepEqual([gone.why, gone.technical], ['Kitden could not find this file.', null]);
});

test('a plugin turns on again and a plugin or skill is removed, as the old Details and the × did', async () => {
  const { linkRemoval } = await import('../../src/kitden/web/static/js/library-rules.js');
  // pr-review is off in Claude Code: "Turn on in Claude Code…" is one plugin.enable row.
  const off = { ...MEDIUM.groups[0].items[0], can: { add: ['codex'], off: [], on: ['claude_code'], remove: ['claude_code'] } };
  const card = details.pluginCard(off, c());
  const on = card.actions.find((a) => a.label === 'Turn on in Claude Code…');
  assert.deepEqual(on.body, { action: 'plugin.enable', targets: [{ item: 'cc-pr' }], params: {} });
  // Under More: "Remove from Claude Code…", the same tray row as the link's ×.
  assert.deepEqual(card.more.map((a) => a.label), ['Remove from Claude Code…']);
  const remove = card.more[0].body;
  assert.deepEqual(remove, { action: 'plugin.remove', targets: [{ item: 'cc-pr' }], params: {} });
  const spX = linkRemoval({ ...SUPERPOWERS, can: { ...SUPERPOWERS.can, remove: ['claude_code'] } }, 'claude_code', MEDIUM);
  const spCard = details.pluginCard({ ...SUPERPOWERS, can: { ...SUPERPOWERS.can, remove: ['claude_code'] } }, c());
  assert.equal(keyFor(spCard.more[0].body), keyFor(spX.body));
  // A plugin with nothing off and nothing to remove offers neither.
  assert.deepEqual(details.pluginCard(SUPERPOWERS, c()).more, []);
  assert.ok(!details.pluginCard(SUPERPOWERS, c()).actions.some((a) => a.label.startsWith('Turn on')));
  // A skill: Remove from the client whose own folder holds it (Cursor's ui-polish).
  const skill = own('s2', 'ui-polish', 'skill', { by: { cursor: 'on' }, items: { cursor: ['cu-ui'] }, can: { add: [], off: [], remove: ['cursor'] } });
  const skillCard = details.skillCard(skill, c());
  assert.deepEqual(skillCard.more.map((a) => [a.label, a.body.action]), [['Remove from Cursor…', 'skill.remove']]);
  assert.equal(keyFor(skillCard.more[0].body), keyFor(linkRemoval(skill, 'cursor', MEDIUM).body));
});

test("where a project's own settings decide, Details say so and offer no Turn on or Remove", () => {
  // website's settings turn superpowers off for Claude Code (can.project, views/library_map.py).
  const decided = { ...SUPERPOWERS, by: { claude_code: 'off', cursor: 'off' }, can: { add: ['codex'], off: [], on: [], remove: [], project: ['claude_code'] } };
  const card = details.pluginCard(decided, details.context(MEDIUM, 'w', 'website'));
  assert.equal(card.after.textContent, "Claude Code's setting for this comes from website's own settings.");
  assert.ok(!card.actions.some((a) => a.label.startsWith('Turn on')));
  assert.deepEqual(card.more, []);
  // A skill too; with All projects there is no such line.
  const skill = own('s9', 'api-style', 'skill', { by: { codex: 'on', cursor: 'on' }, items: { codex: ['cx'], cursor: ['cu'] }, can: { add: [], off: [], remove: [], project: ['codex', 'cursor'] } });
  assert.equal(details.skillCard(skill, details.context(MEDIUM, 'a', 'atlas')).after.textContent, "Codex's setting for this comes from atlas's own settings. Cursor's setting for this comes from atlas's own settings.");
  assert.equal(details.pluginCard({ ...decided, can: { ...decided.can, project: [] } }, c()).after, null);
});

test('the account card says what Claude Code keeps in the account, and that it is not known', () => {
  const card = details.accountCard({ id: 'item:acc', kind: 'account', name: 'Claude account plugins and connectors', reason: 'Stored in your Claude account. Change it in the Claude app or on claude.ai.', item: { by: { claude_code: 'unknown' } } });
  assert.equal(card.title, 'Claude account plugins and connectors');
  assert.deepEqual(facts(card), [['State', 'Unknown']]);
  assert.equal(card.why, 'Stored in your Claude account. Change it in the Claude app or on claude.ai.');
  assert.equal(card.actions, undefined);
});

test("Use the shared rule… takes the project's local key out, for a skill and a plugin", async () => {
  await reset();
  const atlas = details.context(MEDIUM, 'atlas', 'atlas');
  // The project's local settings turn superpowers off for Claude Code (can.local, library_map.py).
  const plugin = { ...SUPERPOWERS, by: { claude_code: 'off', cursor: 'off' }, here: { claude_code: true }, can: { add: [], off: [], on: [], remove: [], project: ['claude_code'], local: ['claude_code'], shared: [] } };
  const card = details.pluginCard(plugin, atlas);
  assert.deepEqual(labels(card), [['Use the shared rule…', false]]);
  assert.equal(card.after.textContent, "Claude Code's setting for this comes from atlas's local settings.");
  assert.deepEqual(details.sharedBody(plugin, atlas), { action: 'skill.rule', targets: [{ client: 'claude_code', item: 'cc-sp' }], params: { scope: 'project', project: 'atlas', off: false } });
  // Drawn: its press adds the one row and it says "In preview"; "Turn off in this project…" for
  // the same key (on and off share it) is another row, so it does not.
  const sample = { ...MEDIUM, groups: MEDIUM.groups.map((g) => ({ ...g, items: g.items.map((i) => (i.id === 'p2' ? plugin : i)) })) };
  const box = await showMap(sample, { project: 'atlas' });
  press(node(box, 'block:item:p2'));
  await flush();
  await addToTray(details.projectBody(plugin, 'atlas'));
  await flush();
  const back = node(drawer, 'action:Use the shared rule…');
  assert.ok(!texts(back).includes('In preview'));
  press(back);
  await flush();
  assert.deepEqual(tray.rows.map((r) => [r.key, r.body.params.off]), [['skill:claude_code:cc-sp@atlas', false]]);
  assert.ok(texts(back).includes('In preview'));
  await reset();
  // A skill too; it never blocks a rule for all projects (it adds no skillOverrides).
  const skill = { ...MEDIUM.groups[1].items[0], by: { claude_code: 'off', codex: 'on', cursor: 'off' }, here: { claude_code: true }, can: { off: ['codex'], project: ['claude_code'], local: ['claude_code'], shared: [] } };
  assert.ok(labels(details.skillCard(skill, atlas)).some(([label]) => label === 'Use the shared rule…'));
  await addToTray(details.sharedBody(skill, atlas));
  assert.equal(details.skillRuleWaits('project', MEDIUM), false);
  await cancelTray();
  // The project's shared, committed settings: the line says so, and nothing changes that file.
  const committed = { ...plugin, can: { ...plugin.can, local: [], shared: ['claude_code'] } };
  const shared = details.pluginCard(committed, details.context(MEDIUM, 'w', 'website'));
  assert.equal(shared.after.textContent, "Claude Code's setting for this comes from website's shared settings.");
  assert.deepEqual(labels(shared), []);
  // With All projects there is none.
  assert.equal(details.sharedBody(plugin, c()), null);
});

test('a project that already turns the skill off is Already off there and cannot be ticked', async () => {
  await reset();
  const skill = { ...MEDIUM.groups[1].items[0], off_in: ['atlas'] };
  const nodes = details.someNodes(skill, details.context(MEDIUM, '', ''), () => {});
  drawer.replaceChildren(...nodes);
  const atlas = node(drawer, 'tick:atlas');
  assert.equal(atlas.disabled, true);
  assert.ok(texts(atlas).includes('Already off there'));
  drawer.replaceChildren();
});

test('a Codex skill in one project gets Turn off this copy in Codex…', async () => {
  await reset();
  const atlas = details.context(MEDIUM, 'atlas', 'atlas');
  const mine = own('s7', 'api-style', 'skill', { source: 'Only this project', by: { codex: 'on' }, items: { codex: ['cx-api'] }, can: { off: [], project: ['codex'], local: [], shared: [], copy: ['codex'] } });
  const card = details.skillCard(mine, atlas);
  assert.deepEqual(labels(card), [['Turn off this copy in Codex…', false]]);
  assert.doesNotMatch(card.why, /no switch for one project/);
  press(card.actions[0].node);
  await flush();
  assert.deepEqual(tray.rows.map((r) => r.body), [{ action: 'skill.rule', targets: [{ client: 'codex', item: 'cx-api' }], params: { scope: 'all', off: true } }]);
  await cancelTray();
});

test("another client's project copy does not offer Turn off in this project… for Claude Code", () => {
  const atlas = details.context(MEDIUM, 'atlas', 'atlas');
  // atlas has its own Codex copy; Claude Code loads the user's copy there (here is per client).
  const skill = { ...MEDIUM.groups[1].items[0], here: { claude_code: false, codex: true, cursor: false } };
  assert.equal(details.skillHereBody(skill, atlas), null);
  assert.ok(!labels(details.skillCard(skill, atlas)).some(([label]) => label === 'Turn off in this project…'));
  // Still "This project" under Comes from: a client's state there comes from the project.
  assert.deepEqual(facts(details.skillCard(skill, atlas))[2], ['Comes from', 'This project · atlas']);
  // Claude Code decided there: offered.
  const decided = { ...skill, here: { claude_code: true } };
  assert.ok(details.skillHereBody(decided, atlas));
});

test('a project-only Claude Code skill shows the reason while the user file has skillOverrides', () => {
  const mine = own('s9', 'site-notes', 'skill', { source: 'Only this project', by: { claude_code: 'on' }, items: { claude_code: ['cc-sn'] }, can: { off: [], project: ['claude_code'], local: [], shared: [] } });
  const blocked = details.context({ ...MEDIUM, skill_rules: { some: false, projects: { atlas: 'ok' } } }, 'atlas', 'atlas');
  const card = details.skillCard(mine, blocked);
  assert.deepEqual(labels(card), []);
  assert.ok(texts(card.after).includes('Claude Code may not merge skill settings across files, so Kitden cannot turn it off in this project.'));
  // Where the rule can go, no reason.
  const open = details.skillCard(mine, details.context(MEDIUM, 'atlas', 'atlas'));
  assert.ok(!texts(open.after).includes('Claude Code may not merge skill settings across files, so Kitden cannot turn it off in this project.'));
});

test("the part card's button and the checklist's tick tell a rule's on and off apart", async () => {
  await reset();
  const atlas = details.context(MEDIUM, 'atlas', 'atlas');
  // "Use the shared rule…" for superpowers waits: the same key, but off is false.
  await addToTray({ ...details.projectBody(SUPERPOWERS, 'atlas'), params: { scope: 'project', project: 'atlas', off: false } });
  const part = libraryTree(MEDIUM).blocks.find((b) => b.id === 'part:p2:skills:brainstorm');
  const button = details.partCard(part, atlas).after;
  drawer.replaceChildren(button);
  await flush();
  assert.ok(!texts(button).includes('In preview'));
  press(button);
  await flush();
  assert.deepEqual(tray.rows.map((r) => r.body.params.off), [true]);
  assert.ok(texts(button).includes('In preview'));
  await cancelTray();
  // A project row is ticked only by its own off rule.
  const skill = MEDIUM.groups[1].items[0];
  await addToTray({ ...details.projectBody(skill, 'atlas'), params: { scope: 'project', project: 'atlas', off: false } });
  drawer.replaceChildren(...details.someNodes(skill, c(), () => {}));
  await flush();
  assert.equal(node(drawer, 'tick:atlas').getAttribute('aria-checked'), 'false');
  drawer.replaceChildren();
  await reset();
});

test("a project whose rule file Kitden does not write says so and offers no rule there", async () => {
  await reset();
  const answer = { ...MEDIUM, skill_rules: { some: true, projects: { atlas: 'outside', web: 'ok' }, outside: { atlas: 'repo' } } };
  const words = "Claude Code keeps this project's local settings in repo, where Kitden does not write.";
  const atlas = details.context(answer, 'atlas', 'atlas');
  // A plugin and a skill: the quiet line, and no "Turn off in this project…".
  const plugin = details.pluginCard(SUPERPOWERS, atlas);
  assert.equal(plugin.after.textContent, words);
  assert.ok(!labels(plugin).some(([label]) => label === 'Turn off in this project…'));
  const mine = own('s9', 'site-notes', 'skill', { source: 'Only this project', by: { claude_code: 'on' }, items: { claude_code: ['cc-sn'] }, can: { off: [], project: ['claude_code'], local: [], shared: [] } });
  const skill = details.skillCard(mine, atlas);
  assert.deepEqual(labels(skill), []);
  assert.ok(texts(skill.after).includes(words));
  assert.ok(!texts(skill.after).some((t) => t.includes('may not merge')));
  // Not in another project.
  assert.equal(details.pluginCard(SUPERPOWERS, details.context(answer, 'web', 'web')).after, null);
  // The checklist row cannot be ticked and says why.
  drawer.replaceChildren(...details.someNodes(MEDIUM.groups[1].items[0], details.context(answer, '', ''), () => {}));
  await flush();
  const row = node(drawer, 'tick:atlas');
  assert.equal(row.disabled, true);
  assert.ok(texts(row).includes(words));
  drawer.replaceChildren();
});
