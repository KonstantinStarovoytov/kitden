import assert from 'node:assert/strict';
import { test } from 'node:test';

// A search on a map page shows its first match when none is in view (map-page.js revealMatch).
let reduced = false;
globalThis.matchMedia = () => ({ get matches() { return reduced; }, addEventListener() {} });
delete globalThis.navigator;
globalThis.localStorage = { getItem: () => null, setItem() {} };
globalThis.getComputedStyle = (node) => ({ overflowX: node.scrolls ? 'auto' : 'visible', overflowY: node.scrolls ? 'auto' : 'visible' });
const bar = { getBoundingClientRect: () => ({ left: 0, right: 1000, top: 0, bottom: 66 }) };
globalThis.document = { body: {}, querySelector: (selector) => (selector === '.topbar' ? bar : null) };

const { cut, revealMatch } = await import('../../src/kitden/web/static/js/map-page.js');

// A found block at `top`, inside a scrolling column from y 0 to 600.
const column = { scrolls: true, parentElement: null, getBoundingClientRect: () => ({ left: 0, right: 1000, top: 0, bottom: 600 }) };
function block(top) {
  const node = { parentElement: column, scrolled: [], getBoundingClientRect: () => ({ left: 10, right: 200, top, bottom: top + 50 }), scrollIntoView(options) { node.scrolled.push(options); } };
  return node;
}
const boxOf = (...blocks) => ({ isConnected: true, querySelectorAll: (selector) => (selector === '.block.found' ? blocks : []) });

test('cut keeps the part of a box inside another', () => {
  assert.deepEqual(cut({ left: 0, right: 10, top: 0, bottom: 10 }, { left: 5, right: 20, top: 5, bottom: 20 }), { left: 5, right: 10, top: 5, bottom: 10 });
  assert.equal(cut({ left: 0, right: 10, top: 0, bottom: 10 }, { left: 10, right: 20, top: 0, bottom: 10 }), null);
});

test('a match out of view scrolls into view, smoothly, once for one search', () => {
  reduced = false;
  const far = block(900);
  const box = boxOf(far, block(1200));
  revealMatch('library', box, 'docs');
  assert.deepEqual(far.scrolled, [{ behavior: 'smooth', block: 'center', inline: 'nearest' }]);
  // A redraw of the same search does not scroll again.
  revealMatch('library', box, 'docs');
  assert.equal(far.scrolled.length, 1);
  // A new search does.
  revealMatch('library', box, 'docs2');
  assert.equal(far.scrolled.length, 2);
  // So does the same text on the other page.
  revealMatch('gateway', box, 'docs2');
  assert.equal(far.scrolled.length, 3);
});

test('a match in view, or under the top bar only, is handled as seen or not', () => {
  reduced = false;
  revealMatch('library', boxOf(), '');
  const seen = block(200);
  revealMatch('library', boxOf(block(900), seen), 'one');
  assert.equal(seen.scrolled.length, 0, 'a lit block in view means no scroll');
  // A block hidden under the top bar is not in view.
  revealMatch('library', boxOf(), '');
  const hidden = block(-10);
  revealMatch('library', boxOf(hidden), 'two');
  assert.equal(hidden.scrolled.length, 1);
});

test('reduced motion scrolls at once, and no search or no match scrolls nothing', () => {
  reduced = true;
  revealMatch('library', boxOf(), '');
  const far = block(900);
  revealMatch('library', boxOf(far), 'three');
  assert.deepEqual(far.scrolled, [{ behavior: 'auto', block: 'center', inline: 'nearest' }]);
  reduced = false;
  revealMatch('library', boxOf(), '');
  const none = block(900);
  revealMatch('library', boxOf(), 'four');
  revealMatch('library', { isConnected: false, querySelectorAll: () => [none] }, 'five');
  assert.equal(none.scrolled.length, 0);
});
