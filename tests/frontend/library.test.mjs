import assert from 'node:assert/strict';
import { test } from 'node:test';

// library.js needs only these from a browser to load. The stub element knows classes,
// attributes, children and listeners; the tests read what a cell draws.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
function element(tag) {
  const node = {
    tag, className: '', textContent: '', title: '', children: [], attributes: {}, dataset: {},
    classList: {
      contains: (name) => node.className.split(' ').includes(name),
      add: (name) => { if (!node.classList.contains(name)) node.className = `${node.className} ${name}`.trim(); },
      remove: (name) => { node.className = node.className.split(' ').filter((c) => c !== name).join(' '); },
    },
    append(...nodes) { node.children.push(...nodes); },
    setAttribute(name, value) { node.attributes[name] = value; },
    getAttribute: (name) => node.attributes[name] ?? null,
    listeners: {},
    addEventListener(type, fn) { (node.listeners[type] ||= []).push(fn); },
  };
  return node;
}
// `drawn` is what a test says is on the page: selector → node, for focus.
const drawn = {};
globalThis.document = { createElement: element, querySelector: (selector) => drawn[selector] || null };
// This browser's store: a test swaps `store.broken` on to make every read and write throw.
const store = { broken: false, items: {} };
Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: {
    getItem(key) { if (store.broken) throw new Error('blocked'); return key in store.items ? store.items[key] : null; },
    setItem(key, value) { if (store.broken) throw new Error('blocked'); store.items[key] = String(value); },
  },
});
// Each request waits until the test answers it, so a test decides which answer comes first.
const requests = [];
globalThis.fetch = (url) => new Promise((resolve) => {
  requests.push({ url, answer: (body) => resolve({ ok: true, status: 200, json: async () => body }) });
});
const { cellNode, emptyState, hiddenClients, hiddenLine, hideButton, loadLibrary, loadLibraryFor, metaText, moreLine, nameCell, noteFor, previewFor, setHidden } = await import('../../src/kitden/web/static/js/library.js');
const { freshness, hashFor, parseHash, state } = await import('../../src/kitden/web/static/js/store.js');
const later = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const cell = (fields) => ({ state: 'none', where: null, items: [], word: null, add: null, reason: null, ...fields });
const add = (fields) => ({ action: 'plugin.install', label: '+ Add', plugin: null, skill: null, marketplace: null, warn: null, ...fields });
const row = (cells, fields = {}) => ({ key: 'plugin:1', kind: 'plugin', name: 'figma', source: 'openai-curated', same_name: false, cells, ...fields });

test('a cell with an add shows its label and nothing else', () => {
  const plugin = cellNode(row({ codex: cell({ add: add({ plugin: 'figma@openai-curated' }) }) }), 'codex');
  assert.equal(plugin.tag, 'button');
  assert.equal(plugin.textContent, '+ Add');
  assert.deepEqual(plugin.children, []);
  // A screen reader hears the button's words first, then what and where; twin rows name their source.
  assert.equal(plugin.attributes['aria-label'], 'Add figma to Codex');
  const twin = cellNode(row({ codex: cell({ add: add({ plugin: 'figma@openai-curated' }) }) }, { same_name: true }), 'codex');
  assert.equal(twin.attributes['aria-label'], 'Add figma (openai-curated) to Codex');

  const skills = cellNode(row({ claude_code: cell({ add: add({ action: 'plugin.skills', label: '+ Add skills', plugin: 'figma@openai-curated' }) }) }), 'claude_code');
  assert.equal(skills.textContent, '+ Add skills');
  assert.deepEqual(skills.children, []);
  assert.equal(skills.attributes['aria-label'], 'Add skills from figma to Claude Code');

  const plugin2 = cellNode(row({ cursor: cell({ add: add({ label: '+ Add the plugin', plugin: 'glean@cursor-public' }) }) }, { kind: 'skill', name: 'find-owner' }), 'cursor');
  assert.equal(plugin2.textContent, '+ Add the plugin');
  assert.equal(plugin2.attributes['aria-label'], 'Add the plugin with find-owner to Cursor');
});

test('a cell with nothing to do shows a dash and says why', () => {
  const reason = "Cursor can't install this plugin, and it has no skills to copy.";
  const node = cellNode(row({ cursor: cell({ reason }) }), 'cursor');
  assert.equal(node.children[0].textContent, '—');
  assert.equal(node.title, reason);
  assert.equal(node.attributes['aria-label'], reason);
  // A client that just does not have it (an MCP server) keeps the plain words.
  const plain = cellNode(row({ cursor: cell({}) }), 'cursor');
  assert.equal(plain.title, '');
  assert.equal(plain.attributes['aria-label'], 'Not set up');
});

test('a state cell says the state, and why when the server says', () => {
  const via = cellNode(row({ cursor: cell({ state: 'via', word: 'Via Claude Code', reason: "Cursor loads Claude Code's plugins. Add it to Claude Code." }) }), 'cursor');
  assert.equal(via.className, 'socket s-via');
  assert.equal(via.children[1].textContent, 'Via Claude Code');
  assert.equal(via.title, "Cursor loads Claude Code's plugins. Add it to Claude Code.");
  const done = cellNode(row({ codex: cell({ state: 'done', word: 'Has its skills' }) }), 'codex');
  assert.equal(done.className, 'socket s-done');
  assert.equal(done.children[1].textContent, 'Has its skills');
  const on = cellNode(row({ codex: cell({ state: 'on', where: 'project' }) }), 'codex');
  assert.deepEqual(on.children.map((c) => c.textContent), ['', 'Loads', 'project']);
});

test('a cell add asks for a review of that one client', () => {
  assert.deepEqual(previewFor(add({ plugin: 'figma@openai-curated' }), 'codex'),
    { action: 'plugin.install', targets: [{ client: 'codex' }], params: { plugin: 'figma@openai-curated' } });
  assert.deepEqual(previewFor(add({ action: 'plugin.skills', label: '+ Add skills', plugin: 'documents@openai-curated' }), 'claude_code'),
    { action: 'plugin.skills', targets: [{ client: 'claude_code' }], params: { plugin: 'documents@openai-curated' } });
  assert.deepEqual(previewFor(add({ action: 'skill.install', skill: 'tidy@toolbox@x' }), 'cursor'),
    { action: 'skill.install', targets: [{ client: 'cursor' }], params: { skill: 'tidy@toolbox@x' } });
});

test('the review note warns about a twin and says a project add is for every project', () => {
  const warn = 'Codex already has figma from claude-plugins-official. It will load both.';
  assert.equal(noteFor(add({}), ''), null);
  assert.equal(noteFor(add({ warn }), ''), warn);
  assert.equal(noteFor(add({}), 'p1'), 'Adds for all your projects.');
  assert.equal(noteFor(add({ warn }), 'p1'), `${warn} Adds for all your projects.`);
});

test('meta text shows the source only when names repeat', () => {
  assert.equal(metaText({ category: 'Design', source: 'openai-curated', same_name: true }), 'Design · openai-curated');
  assert.equal(metaText({ category: 'Design', source: 'openai-curated', same_name: false }), 'Design');
  assert.equal(metaText({ category: null, source: 'cursor-public', same_name: true }), 'cursor-public');
  assert.equal(metaText({ category: null, source: null, same_name: true }), '');
});

test('line one is the name and its quiet text; the flags go to line two', () => {
  const twice = { text: 'Cursor loads it twice', level: 'warning' };
  const flagged = row({}, { category: 'Design', same_name: true, description: 'Draw things', flags: [twice, twice] });
  const [one, two] = nameCell(flagged, false).children;
  assert.equal(one.className, 'item');
  assert.deepEqual(one.children.map((c) => [c.className, c.textContent]), [['mono', 'figma'], ['meta', 'Design · openai-curated'], ['opens', '']]);
  // One flag per wording, then what it does.
  assert.equal(two.className, 'sub');
  assert.deepEqual(two.children.map((c) => [c.className, c.textContent]), [['flag', 'Cursor loads it twice'], ['desc', 'Draw things']]);
  // No description: the flags have line two to themselves. Neither: one line.
  assert.deepEqual(nameCell({ ...flagged, description: '' }, false).children[1].children.map((c) => c.className), ['flag']);
  assert.equal(nameCell({ ...flagged, description: '', flags: [] }, false).children.length, 1);
});

test('the more line names what the choice hides', () => {
  assert.equal(moreLine({ more: 3 }, 'mine'), '3 more not on this Mac · Show all');
  assert.equal(moreLine({ more: 3 }, 'new'), '3 more on this Mac · Show all');
  assert.equal(moreLine({ more: 0 }, 'mine'), null);
  assert.equal(moreLine({ more: 3 }, 'all'), null);
});

test('old map and discover addresses open the Library', () => {
  const library = (fields) => ({ view: 'library', kind: 'mcp_server', show: 'mine', category: '', attention: false, project: '', q: '', ...fields });
  assert.deepEqual(parseHash('#map'), library({}));
  // The Load map's "Needs attention" filter carries over.
  assert.deepEqual(parseHash('#map?kind=plugin&only=problems&project=p1&q=git'), library({ kind: 'plugin', attention: true, project: 'p1', q: 'git' }));
  assert.equal(parseHash('#map?only=diff').attention, false);
  assert.deepEqual(parseHash('#discover'), library({ kind: 'plugin', show: 'new' }));
  assert.deepEqual(parseHash('#discover?kind=skill&q=pdf'), library({ kind: 'skill', show: 'new', q: 'pdf' }));
  assert.deepEqual(parseHash('#discover?kind=hook'), library({ kind: 'plugin', show: 'new' }));
  // The Library's own address keeps every choice, and writes back the same.
  const hash = '#library?kind=skill&show=all&category=Design&attention=1&project=p1&q=pdf';
  const parsed = parseHash(hash);
  assert.deepEqual(parsed, library({ kind: 'skill', show: 'all', category: 'Design', attention: true, project: 'p1', q: 'pdf' }));
  assert.equal(hashFor(parsed), hash);
  assert.equal(hashFor(library({})), '#library?kind=mcp_server');
  assert.equal(parseHash('#library?show=nope').show, 'mine');
  assert.equal(parseHash('#nowhere').view, 'overview');
});

test('a search the choice hides shows the more line, not an empty table', () => {
  const box = emptyState({ kind: 'plugin', show: 'mine', q: 'figma' }, moreLine({ more: 2 }, 'mine'));
  assert.equal(box.className, 'empty');
  assert.equal(box.children[0].textContent, 'Nothing on this Mac matches “figma”');
  const [words, all] = box.children[1].children;
  assert.equal(box.children[1].className, 'more');
  assert.equal(words.textContent, '2 more not on this Mac · ');
  assert.equal(all.textContent, 'Show all');
  const added = emptyState({ kind: 'skill', show: 'new', q: 'pdf' }, moreLine({ more: 1 }, 'new'));
  assert.equal(added.children[0].textContent, 'Nothing you can add matches “pdf”');
});

test('an empty tab names its kind the way the tab does', () => {
  const servers = emptyState({ kind: 'mcp_server', show: 'mine', q: '' }, null);
  assert.deepEqual(servers.children.map((c) => c.textContent), ['No MCP servers in any client', 'MCP servers you add in Claude Code, Codex or Cursor will show up here.']);
  const plugins = emptyState({ kind: 'plugin', show: 'mine', q: '' }, null);
  assert.deepEqual(plugins.children.map((c) => c.textContent), ['No plugins in any client', 'Plugins you add in Claude Code, Codex or Cursor will show up here.']);
});

test('an older answer never replaces a newer one for the same tab', async () => {
  Object.assign(state, { view: 'library', kind: 'plugin', show: 'mine', category: '', attention: false, project: '', q: '' });
  freshness.reloadStartedAt = performance.now();
  requests.length = 0;
  const older = loadLibrary();
  await later(2);
  // A rescan: the first request is now old, so the page asks again.
  freshness.reloadStartedAt = performance.now();
  const newer = loadLibrary();
  assert.equal(requests.length, 2);
  requests[1].answer({ rows: ['new'] });
  await newer;
  requests[0].answer({ rows: ['old'] });
  await older;
  // The newer answer is still the one kept: nothing more to ask (a request starts at once).
  loadLibrary();
  assert.equal(requests.length, 2);
});

test('a tab read before the Library shows is kept for it', async () => {
  Object.assign(state, { view: 'overview', kind: 'mcp_server', show: 'new', category: 'Design', attention: true, project: '', q: 'x' });
  freshness.reloadStartedAt = performance.now();
  requests.length = 0;
  const read = loadLibraryFor({ kind: 'skill', show: 'mine', category: '', attention: false, q: '' });
  assert.equal(requests.length, 1);
  assert.match(requests[0].url, /^\/api\/library\?kind=skill&show=mine$/);
  requests[0].answer({ rows: [] });
  await read;
  // Reading it again, or showing that tab, asks nothing new (a request starts at once).
  loadLibraryFor({ kind: 'skill', show: 'mine', category: '', attention: false, q: '' });
  Object.assign(state, { view: 'library', kind: 'skill', show: 'mine', category: '', attention: false, q: '' });
  loadLibrary();
  assert.equal(requests.length, 1);
});

const COLUMNS = [
  { id: 'claude_code', name: 'Claude Code', hidden: false },
  { id: 'codex', name: 'Codex', hidden: false },
  { id: 'cursor', name: 'Cursor', hidden: false },
];
const hiding = (...ids) => COLUMNS.map((c) => ({ ...c, hidden: ids.includes(c.id) }));

test('hidden clients survive a broken store', () => {
  store.items = {};
  setHidden(['codex', 'cursor']);
  assert.deepEqual(hiddenClients(), ['codex', 'cursor']);
  // Anything that is not a list of ids reads as nothing hidden.
  for (const junk of ['not json', '{"a":1}', 'null', '[1,{"x":2}]']) {
    store.items['kitden-hidden-clients'] = junk;
    assert.deepEqual(hiddenClients(), [], junk);
  }
  // A store that throws on every read: nothing hidden, and no error.
  store.broken = true;
  assert.deepEqual(hiddenClients(), []);
  // One that cannot be written: the choice still holds while this page is open.
  setHidden(['cursor']);
  assert.deepEqual(hiddenClients(), ['cursor']);
  store.broken = false;
  assert.deepEqual(hiddenClients(), ['cursor']);
  // Once the store takes a choice again, the store counts.
  setHidden([]);
  assert.equal(store.items['kitden-hidden-clients'], '[]');
  store.items['kitden-hidden-clients'] = '["codex"]';
  assert.deepEqual(hiddenClients(), ['codex']);
  store.items = {};
});

test('a hide works while the store cannot be written', async () => {
  Object.assign(state, { view: 'library', kind: 'plugin', show: 'mine', category: '', attention: false, project: '', q: '' });
  store.items = {};
  store.broken = true;
  freshness.reloadStartedAt = performance.now();
  requests.length = 0;
  hideButton(COLUMNS[1], COLUMNS).listeners.click[0]({});
  await later(2);
  assert.match(requests[0].url, /hidden=codex$/);
  requests[0].answer({ rows: [] });
  await later(2);
  store.broken = false;
  setHidden([]);
  assert.deepEqual(hiddenClients(), []);
});

test('the last column has no hide button', () => {
  const button = hideButton(COLUMNS[1], COLUMNS);
  assert.equal(button.tag, 'button');
  assert.equal(button.textContent, '−');
  assert.equal(button.attributes['aria-label'], 'Hide Codex');
  assert.equal(button.dataset.focus, 'hide:codex');
  assert.equal(hideButton(COLUMNS[1], COLUMNS.slice(0, 2)).attributes['aria-label'], 'Hide Codex');
  assert.equal(hideButton(COLUMNS[1], [COLUMNS[1]]), null);
});

test('the hidden line names every hidden client', () => {
  assert.equal(hiddenLine(hiding()), null);
  const one = hiddenLine(hiding('cursor'));
  const [words, show] = one.children;
  assert.equal(one.className, 'more');
  assert.equal(words.textContent, 'Hidden: Cursor · ');
  assert.equal(show.textContent, 'Show');
  assert.equal(show.dataset.focus, 'hidden:show');
  assert.equal(hiddenLine(hiding('codex', 'cursor')).children[0].textContent, 'Hidden: Codex, Cursor · ');
});

test('the hidden choice is part of the question, so a change asks again', async () => {
  Object.assign(state, { view: 'library', kind: 'skill', show: 'mine', category: '', attention: false, project: '', q: '' });
  store.items = {};
  freshness.reloadStartedAt = performance.now();
  requests.length = 0;
  const all = loadLibrary();
  assert.equal(requests.length, 1);
  assert.doesNotMatch(requests[0].url, /hidden/);
  requests[0].answer({ rows: [] });
  await all;
  // The order they were hidden in does not matter: the server gets one sorted list.
  setHidden(['cursor', 'codex']);
  const fewer = loadLibrary();
  assert.equal(requests.length, 2);
  assert.match(requests[1].url, /^\/api\/library\?kind=skill&show=mine&hidden=codex%2Ccursor$/);
  requests[1].answer({ rows: [] });
  await fewer;
  setHidden(['codex', 'cursor']);
  loadLibrary();
  assert.equal(requests.length, 2);
});

test('a hide button saves the choice, asks again, then focuses the next column or Show', async () => {
  Object.assign(state, { view: 'library', kind: 'plugin', show: 'mine', category: '', attention: false, project: '', q: '' });
  store.items = {};
  freshness.reloadStartedAt = performance.now();
  requests.length = 0;
  const focused = [];
  const focusable = (key) => { drawn[`#main [data-focus="${key}"]`] = { focus: () => focused.push(key) }; };
  focusable('hide:cursor');
  focusable('hidden:show');

  // Hiding Codex: the next column is Cursor.
  hideButton(COLUMNS[1], COLUMNS).listeners.click[0]({});
  await later(2);
  assert.deepEqual(hiddenClients(), ['codex']);
  assert.equal(requests.length, 1);
  assert.match(requests[0].url, /hidden=codex$/);
  requests[0].answer({ rows: [] });
  await later(2);
  assert.deepEqual(focused, ['hide:cursor']);

  // Hiding the last of the shown columns has no next one: focus goes to Show.
  hideButton(COLUMNS[2], [COLUMNS[0], COLUMNS[2]]).listeners.click[0]({});
  await later(2);
  assert.deepEqual(hiddenClients(), ['codex', 'cursor']);
  requests[1].answer({ rows: [] });
  await later(2);
  assert.deepEqual(focused, ['hide:cursor', 'hidden:show']);

  // Show brings every column back, and focus goes to the first one that came back.
  focusable('hide:codex');
  hiddenLine(hiding('codex', 'cursor')).children[1].listeners.click[0]({});
  await later(2);
  assert.deepEqual(hiddenClients(), []);
  assert.doesNotMatch(requests[2].url, /hidden/);
  requests[2].answer({ rows: [] });
  await later(2);
  assert.deepEqual(focused, ['hide:cursor', 'hidden:show', 'hide:codex']);
});
