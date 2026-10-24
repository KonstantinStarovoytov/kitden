import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';

// store.js needs only these from a browser; fetch answers from the maps below.
globalThis.matchMedia = () => ({ matches: false });
// A place change draws through `transition`, which scrolls #content to the top.
globalThis.document = { getElementById: () => ({}) };
let answers = {};
let failing = null;
const asked = []; // every url read, in order
globalThis.fetch = async (url) => {
  asked.push(url);
  if (url === failing) throw new Error(`${url}: offline`);
  const body = url === '/api/projects' ? [{ id: 'a' }, { id: 'b' }] : (answers[url] ?? {});
  return { ok: true, status: 200, json: async () => body };
};
function fetchAnswers(map) { answers = map; failing = null; }
function fetchFails(url) { failing = url; }
const ALL_OK = {};

const { current, currentError, data, followHash, freshness, go, goTo, hashFor, loadMap, MAP_AT, parseHash, parseSel, projectGone, reload, retry, selFor, setRenderer, state, takeArrival, toolSel, viewMode } = await import('../../src/kitden/web/static/js/store.js');

beforeEach(() => { state.project = ''; });

test('a failed read for a new project never shows the old project', async () => {
  fetchAnswers({ '/api/map?project=a': { rows: ['a-row'] } });
  state.project = 'a'; await reload();
  assert.equal(current('map').rows[0], 'a-row');
  fetchFails('/api/map?project=b');
  state.project = 'b'; await reload();
  assert.equal(current('map'), null);
  assert.ok(data.errors.map);
});

test('the last good read time moves only when every read worked', async () => {
  fetchAnswers(ALL_OK); await reload();
  const good = freshness.lastGoodRead;
  assert.ok(good);
  fetchFails('/api/overview'); await reload();
  assert.equal(freshness.lastGoodRead, good);
  assert.equal(freshness.lastReadFailed, true);
});

test('a Retry that works clears the rail note; one that fails keeps it and the old time', async () => {
  let drawn = 0;
  setRenderer(() => { drawn += 1; });
  fetchAnswers(ALL_OK); await reload();
  const good = freshness.lastGoodRead;
  fetchFails('/api/map'); await reload();
  await retry();
  assert.equal(freshness.lastReadFailed, true);
  assert.equal(freshness.lastGoodRead, good);
  fetchAnswers(ALL_OK);
  await retry();
  assert.equal(freshness.lastReadFailed, false);
  assert.ok(freshness.lastGoodRead >= good);
  assert.equal(data.errors.map, undefined);
  assert.equal(drawn, 2);
  setRenderer(() => {});
});

test('an answer for a project no longer shown is dropped', async () => {
  fetchAnswers({ '/api/map?project=b': { rows: ['b-row'] } });
  state.project = 'b'; await reload();
  state.project = 'a';
  const late = loadMap();
  state.project = 'b';
  await late;
  assert.equal(current('map').rows[0], 'b-row');

  fetchFails('/api/map?project=a');
  state.project = 'a';
  const lateFailure = loadMap();
  state.project = 'b';
  await lateFailure;
  assert.equal(data.errors.map, undefined);
});

test('an error for one project is not an error for the next one', async () => {
  fetchFails('/api/map?project=a');
  state.project = 'a'; await reload();
  assert.ok(currentError('map'));
  state.project = 'b';
  const pending = loadMap();
  assert.equal(currentError('map'), null);
  await pending;
  assert.equal(currentError('map'), null);
});

test('a project no longer on the list stays picked and is said', async () => {
  fetchAnswers(ALL_OK);
  asked.length = 0;
  state.project = 'gone';
  await reload();
  assert.equal(state.project, 'gone');
  assert.equal(projectGone(), true);
  assert.ok(!asked.some((url) => url.includes('project=gone')));
  assert.ok(asked.includes('/api/setup-server'));
  // Nothing read earlier for it shows either.
  assert.equal(current('overview'), null);
  state.project = 'a';
  assert.equal(projectGone(), false);
});

test('parseSel takes only kind:name', () => {
  assert.deepEqual(parseSel('mcp_server:github'), { kind: 'mcp_server', name: 'github' });
  assert.deepEqual(parseSel('mcp_server:a:b'), { kind: 'mcp_server', name: 'a:b' });
  for (const bad of [null, '', 'nope', 'mcp_server:', 'wizard:x', ':github']) assert.equal(parseSel(bad), null);
  assert.equal(selFor(null), '');
  assert.equal(selFor({ kind: 'skill', name: 'tidy' }), 'skill:tidy');
});

test('every place writes the selection and the project into the address', () => {
  const s = { ...parseHash('#gateway?project=a&sel=mcp_server%3Agithub') };
  assert.deepEqual(s.selected, { kind: 'mcp_server', name: 'github' });
  assert.equal(hashFor(s), '#gateway?project=a&sel=mcp_server%3Agithub');
  assert.equal(hashFor({ ...s, view: 'library', kind: 'mcp_server', show: 'mine' }), '#library?kind=mcp_server&project=a&sel=mcp_server%3Agithub');
});

test('an arrival opens once', () => {
  goTo('library', { kind: 'skill', name: 'tidy' });
  assert.equal(state.kind, 'skill');
  assert.deepEqual(takeArrival(), { kind: 'skill', name: 'tidy' });
  assert.equal(takeArrival(), null);
});

test('a plain place change opens no selection', () => {
  goTo('library', { kind: 'skill', name: 'tidy' });
  go('overview');
  go('library', { kind: 'mcp_server' });
  assert.equal(takeArrival(), null);
  assert.deepEqual(state.selected, { kind: 'skill', name: 'tidy' }); // it stays for the next page
});

test('the view choice stays in the address, and List opens first past 15 servers', () => {
  assert.equal(parseHash('#gateway?view=list').mode, 'list');
  assert.equal(parseHash('#gateway?view=nope').mode, '');
  // Only the Gateway and the Library have a Map and a List.
  assert.equal(parseHash('#overview?view=map').mode, '');
  assert.equal(hashFor({ ...state, view: 'gateway', mode: 'map', project: '', q: '', selected: null }), '#gateway?view=map');
  assert.equal(hashFor({ ...state, view: 'overview', mode: 'map', project: '', q: '', selected: null }), '#overview');
  assert.equal(MAP_AT, 15);
  assert.equal(viewMode({ mode: '' }, 15), 'map'); assert.equal(viewMode({ mode: '' }, 16), 'list'); assert.equal(viewMode({ mode: 'map' }, 157), 'map');
  assert.deepEqual(toolSel('github/push/files'), { server: 'github', tool: 'push/files' });
  assert.equal(toolSel('github'), null);
  assert.deepEqual(parseSel('tool:github/push_files'), { kind: 'tool', name: 'github/push_files' });
  assert.deepEqual(parseSel('group:outside'), { kind: 'group', name: 'outside' });
  assert.deepEqual(parseSel('client:codex'), { kind: 'client', name: 'codex' });
});

test('Back switches Map and List, and a mode passed to go wins over the clear', () => {
  followHash('#gateway?view=map');
  assert.equal(state.mode, 'map');
  assert.equal(followHash('#gateway?view=map').same, true);
  // Only the view differs: Back is a change of state.
  const back = followHash('#gateway?view=list');
  assert.equal(back.same, false);
  assert.equal(state.mode, 'list');
  go('gateway', { q: 'docs' }); // the same place keeps it
  assert.equal(state.mode, 'list');
  // A switch adds a history entry, so Back has one to go back to; a search only replaces it.
  const entries = [];
  globalThis.history = { pushState: (_, __, hash) => entries.push(['push', hash]), replaceState: (_, __, hash) => entries.push(['replace', hash]) };
  go('gateway', { mode: 'map' });
  go('gateway', { q: 'files' });
  delete globalThis.history;
  assert.deepEqual(entries, [['push', '#gateway?view=map&q=docs'], ['replace', '#gateway?view=map&q=files']]);
  go('overview');
  assert.equal(state.mode, '');
  go('gateway', { mode: 'list' });
  assert.equal(state.mode, 'list');
  goTo('library', { kind: 'skill', name: 'tidy' });
  assert.equal(state.mode, '');
  goTo('gateway', { kind: 'tool', name: 'files/read_file' }, { mode: 'map' });
  assert.equal(state.mode, 'map');
  assert.deepEqual(takeArrival(), { kind: 'tool', name: 'files/read_file' });
});
