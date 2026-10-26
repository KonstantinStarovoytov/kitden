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
for (const id of ['#main', '#drawer', '#scrim', '.shell', '#dock', '#find-chip', '#said']) {
  pages[id] = element('DIV');
  pages[id].root = true;
}
const hintLine = element('P');
globalThis.document = {
  hidden: false, activeElement: null, body: element('BODY'),
  createElement: (tag) => element(tag.toUpperCase()), createElementNS: (namespace, tag) => element(tag),
  querySelector: (selector) => pages[selector] ?? null, querySelectorAll: () => [], getElementById: (id) => (id === 'hint' ? hintLine : null),
  addEventListener() {}, removeEventListener() {},
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
const { closePanel, closeForProject, isPanelOpen, panelState } = await import('../../src/kitden/web/static/js/panel.js');
const { data, state } = await import('../../src/kitden/web/static/js/store.js');
const { setHint } = await import('../../src/kitden/web/static/js/parts.js');
const { reducedMotion } = await import('../../src/kitden/web/static/js/motion.js');
const { cancelTray, keyFor, onTray, tray } = await import('../../src/kitden/web/static/js/tray.js');
const { syncTray } = await import('../../src/kitden/web/static/js/details.js');
details.initLibraryDetails();
// As initPanel does: Details follow the tray.
onTray(syncTray);

// The medium sample's answer, cut short (views/library_map.py), with what Details may offer.
const none = { skills: [], commands: [], agents: [], hooks: [], mcp_servers: [] };
const plugin = (id, name, fields) => ({ id, name, kind: 'plugin', plugin: `${name}@demo-market`, by: {}, through: {}, items: {}, here: false, source: 'demo-market', can: { add: [], off: [] }, technical: {}, ...fields });
const own = (id, name, kind, fields) => ({ id, name, kind, by: {}, through: {}, items: {}, here: false, source: 'Your skills', can: { off: [] }, technical: {}, ...fields });
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
  Object.assign(state, { view: 'library', mode: 'map', project, q: '', selected: null });
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
  assert.ok(texts(codex).includes('Not added · in preview'));
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

test('a project switch keeps an open plugin and its Details, or lets go when it is gone', async () => {
  await reset();
  const box = await showMap();
  press(node(box, 'block:item:p2'));
  await flush();
  // Another project: Details stay while it is read, and follow the same plugin, drawn for it.
  state.project = 'atlas';
  closeForProject();
  assert.equal(isPanelOpen(), true);
  const atlas = { ...MEDIUM, groups: MEDIUM.groups.map((g) => ({ ...g, items: g.items.map((i) => (i.id === 'p2' ? { ...i, by: { claude_code: 'off', cursor: 'off' }, here: true } : i)) })) };
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
  // A block is a button: Enter and Space press it.
  const block = node(box, 'block:item:s1');
  assert.equal(block.tagName, 'BUTTON');
  block.focus();
  press(block);
  await flush();
  assert.equal(isPanelOpen(), true);
  assert.ok(drawer.contains(document.activeElement));
  // Escape in Details (panel.js), or Close: the panel closes, focus goes back to the block and the map lets go.
  closePanel({ instant: true });
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
