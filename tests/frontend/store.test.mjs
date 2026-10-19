import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';

// store.js needs only these from a browser; fetch answers from the maps below.
globalThis.matchMedia = () => ({ matches: false });
let answers = {};
let failing = null;
globalThis.fetch = async (url) => {
  if (url === failing) throw new Error(`${url}: offline`);
  const body = url === '/api/projects' ? [{ id: 'a' }, { id: 'b' }] : (answers[url] ?? {});
  return { ok: true, status: 200, json: async () => body };
};
function fetchAnswers(map) { answers = map; failing = null; }
function fetchFails(url) { failing = url; }
const ALL_OK = {};

const { current, currentError, data, freshness, loadMap, reload, retry, setRenderer, state } = await import('../../src/kitden/web/static/js/store.js');

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
