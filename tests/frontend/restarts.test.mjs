import assert from 'node:assert/strict';
import { test } from 'node:test';

// motion.js reads matchMedia when it loads.
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
const { SEEN_KEY, gotIt, onReturn, seenIds, shownStrips, stripKey } = await import('../../src/kitden/web/static/js/restarts.js');

const CURSOR = { client: 'cursor', note: 'Restart Cursor for this to take effect.', change: 'c1' };
const CODEX = { client: 'codex', note: 'Restart Codex for this to take effect.', change: 'c2' };
const K1 = stripKey(CURSOR);

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
  gotIt(K1, store);
  assert.deepEqual(shownStrips([CURSOR, CODEX], seenIds(store)), [CODEX]);
});

test('Got it is kept for the next visit', () => {
  const store = storage();
  gotIt(K1, store);
  assert.deepEqual(JSON.parse(store.items[SEEN_KEY]), [K1]);
  assert.deepEqual(shownStrips([CURSOR], seenIds(store)), []);
});

test('a newer change for the same client shows again', () => {
  const store = storage();
  gotIt(K1, store);
  const newer = { ...CURSOR, change: 'c3' };
  assert.deepEqual(shownStrips([newer], seenIds(store)), [newer]);
});

test('Got it twice keeps one id, and the list stays short', () => {
  const store = storage();
  gotIt(K1, store);
  gotIt(K1, store);
  assert.deepEqual(JSON.parse(store.items[SEEN_KEY]), [K1]);
  for (let n = 0; n < 80; n += 1) gotIt(`x${n}`, store);
  const kept = JSON.parse(store.items[SEEN_KEY]);
  assert.ok(kept.length <= 50);
  assert.equal(kept.at(-1), 'x79');
});

test('without storage nothing breaks and the strip is only hidden for now', () => {
  assert.deepEqual([...seenIds(broken)], []);
  assert.doesNotThrow(() => gotIt(K1, broken));
  assert.deepEqual([...seenIds(undefined)], []);
});

test('a damaged list is read as empty', () => {
  assert.deepEqual([...seenIds(storage({ [SEEN_KEY]: '{oops' }))], []);
  assert.deepEqual([...seenIds(storage({ [SEEN_KEY]: '"c1"' }))], []);
});

test('one change for two clients keeps two strips, each got on its own', () => {
  const cursor = { ...CURSOR, change: 'c5' };
  const codex = { ...CODEX, change: 'c5' };
  assert.notEqual(stripKey(cursor), stripKey(codex));
  const store = storage();
  gotIt(stripKey(cursor), store);
  assert.deepEqual(shownStrips([cursor, codex], seenIds(store)), [codex]);
});

// The strips ask again when the person comes back from restarting an agent.
function page(state = 'visible') {
  const doc = new EventTarget();
  doc.visibilityState = state;
  return { doc, win: new EventTarget() };
}

const tick = () => new Promise((next) => setTimeout(next, 0));

test('coming back to the tab or the window asks again, one ask at a time', async () => {
  const { doc, win } = page();
  const asks = [];
  onReturn(() => new Promise((done) => asks.push(done)), doc, win);
  doc.dispatchEvent(new Event('visibilitychange'));
  win.dispatchEvent(new Event('focus')); // both come together: still one ask
  assert.equal(asks.length, 1);
  asks[0]();
  await tick();
  win.dispatchEvent(new Event('focus'));
  assert.equal(asks.length, 2);
});

test('a tab that goes to the background does not ask', () => {
  const { doc, win } = page('hidden');
  let asks = 0;
  onReturn(() => { asks += 1; }, doc, win);
  doc.dispatchEvent(new Event('visibilitychange'));
  assert.equal(asks, 0);
});

test('an ask that fails does not stop the next one', async () => {
  const { doc, win } = page();
  let asks = 0;
  onReturn(() => { asks += 1; return Promise.reject(new Error('offline')); }, doc, win);
  win.dispatchEvent(new Event('focus'));
  await tick();
  win.dispatchEvent(new Event('focus'));
  assert.equal(asks, 2);
});
