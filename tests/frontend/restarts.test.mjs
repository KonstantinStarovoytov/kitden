import assert from 'node:assert/strict';
import { test } from 'node:test';

// motion.js reads matchMedia when it loads.
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
const { SEEN_KEY, gotIt, seenIds, shownStrips } = await import('../../src/kitden/web/static/js/restarts.js');

const CURSOR = { client: 'cursor', note: 'Restart Cursor for this to take effect.', change: 'c1' };
const CODEX = { client: 'codex', note: 'Restart Codex for this to take effect.', change: 'c2' };

// A stand-in for localStorage.
function storage(start = {}) {
  const items = { ...start };
  return {
    items,
    getItem: (key) => (key in items ? items[key] : null),
    setItem: (key, value) => { items[key] = String(value); },
  };
}

const broken = {
  getItem() { throw new Error('blocked'); },
  setItem() { throw new Error('blocked'); },
};

test('every strip shows until its change is got', () => {
  assert.deepEqual(shownStrips([CURSOR, CODEX], new Set()), [CURSOR, CODEX]);
});

test('Got it hides the strip for that change and keeps the other', () => {
  const store = storage();
  gotIt('c1', store);
  assert.deepEqual(shownStrips([CURSOR, CODEX], seenIds(store)), [CODEX]);
});

test('Got it is kept for the next visit', () => {
  const store = storage();
  gotIt('c1', store);
  assert.deepEqual(JSON.parse(store.items[SEEN_KEY]), ['c1']);
  assert.deepEqual(shownStrips([CURSOR], seenIds(store)), []);
});

test('a newer change for the same client shows again', () => {
  const store = storage();
  gotIt('c1', store);
  const newer = { ...CURSOR, change: 'c3' };
  assert.deepEqual(shownStrips([newer], seenIds(store)), [newer]);
});

test('Got it twice keeps one id, and the list stays short', () => {
  const store = storage();
  gotIt('c1', store);
  gotIt('c1', store);
  assert.deepEqual(JSON.parse(store.items[SEEN_KEY]), ['c1']);
  for (let n = 0; n < 80; n += 1) gotIt(`x${n}`, store);
  const kept = JSON.parse(store.items[SEEN_KEY]);
  assert.ok(kept.length <= 50);
  assert.equal(kept.at(-1), 'x79');
});

test('without storage nothing breaks and the strip is only hidden for now', () => {
  assert.deepEqual([...seenIds(broken)], []);
  assert.doesNotThrow(() => gotIt('c1', broken));
  assert.deepEqual([...seenIds(undefined)], []);
});

test('a damaged list is read as empty', () => {
  assert.deepEqual([...seenIds(storage({ [SEEN_KEY]: '{oops' }))], []);
  assert.deepEqual([...seenIds(storage({ [SEEN_KEY]: '"c1"' }))], []);
});
