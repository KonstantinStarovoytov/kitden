import assert from 'node:assert/strict';
import { test } from 'node:test';

// dom.js needs nothing from a browser to load; the tab keys read the page's focused element.
const { focusKey, gridKey, tabAfter, tabKeys } = await import('../../src/kitden/web/static/js/dom.js');

test('a control is found again by its data-focus key, a table row by its own key', () => {
  assert.equal(focusKey({ dataset: { focus: 'tab:skill' } }), 'tab:skill');
  assert.equal(focusKey({ dataset: { focus: 'filter:category', key: 'x' } }), 'filter:category');
  assert.equal(focusKey({ dataset: { key: 'mcp_server:github' } }), 'row:mcp_server:github');
  assert.equal(focusKey({ dataset: {} }), null);
});

test('arrows move to the next or previous tab and wrap; Home and End go to the ends', () => {
  assert.equal(tabAfter('ArrowRight', 0, 3), 1);
  assert.equal(tabAfter('ArrowRight', 2, 3), 0);
  assert.equal(tabAfter('ArrowLeft', 1, 3), 0);
  assert.equal(tabAfter('ArrowLeft', 0, 3), 2);
  assert.equal(tabAfter('Home', 2, 3), 0);
  assert.equal(tabAfter('End', 0, 3), 2);
  assert.equal(tabAfter('Enter', 0, 3), null);
  assert.equal(tabAfter('ArrowDown', 0, 3), null);
});

// A tab row with three tabs; `press` sends a key to the tab at `at`.
function tabRow(at) {
  const log = [];
  const tabs = ['a', 'b', 'c'].map((name) => ({
    focus() { globalThis.document.activeElement = this; log.push(`focus ${name}`); },
    click() { log.push(`click ${name}`); },
  }));
  let listener = null;
  const box = {
    addEventListener(type, fn) { if (type === 'keydown') listener = fn; },
    querySelectorAll: () => tabs,
  };
  globalThis.document = { activeElement: tabs[at] };
  tabKeys(box);
  return {
    log,
    press(key, extra = {}) {
      let stopped = false;
      listener({ key, preventDefault() { stopped = true; }, ...extra });
      return stopped;
    },
  };
}

test('an arrow on a tab moves focus to the next tab, then selects it', () => {
  const row = tabRow(0);
  assert.equal(row.press('ArrowRight'), true);
  assert.deepEqual(row.log, ['focus b', 'click b']);
});

test('End goes to the last tab and Home to the first', () => {
  const row = tabRow(1);
  row.press('End');
  row.press('Home');
  assert.deepEqual(row.log, ['focus c', 'click c', 'focus a', 'click a']);
});

test('a key that is not a tab key, or has a modifier, is left to the browser', () => {
  const row = tabRow(0);
  assert.equal(row.press('Enter'), false);
  assert.equal(row.press('ArrowRight', { altKey: true }), false);
  assert.equal(row.press('ArrowLeft', { metaKey: true }), false);
  assert.deepEqual(row.log, []);
});

test('staying on the same tab does not select it again', () => {
  const row = tabRow(0);
  assert.equal(row.press('Home'), true);
  assert.deepEqual(row.log, []);
});

test('the list moves by keys', () => {
  const rows = [{ id: 'g', group: true, expanded: true }, { id: 's', parent: 'g', expanded: false }, { id: 't', parent: 's' }];
  assert.deepEqual(gridKey(rows, 1, 'ArrowRight'), { at: 1, toggle: 's' });
  assert.deepEqual(gridKey(rows, 1, 'ArrowLeft'), { at: 0 });
  assert.deepEqual(gridKey(rows, 1, 'Enter'), { at: 1, details: 's' });
  assert.equal(gridKey(rows, 1, 'x'), null);
});

test('Down, Up, Home and End move and stop at the ends; Right goes into an open row, Left closes it', () => {
  const rows = [{ id: 'g', group: true, expanded: true }, { id: 's', parent: 'g', expanded: true }, { id: 't', parent: 's' }];
  assert.deepEqual(gridKey(rows, 0, 'ArrowDown'), { at: 1 });
  assert.deepEqual(gridKey(rows, 2, 'ArrowDown'), { at: 2 });
  assert.deepEqual(gridKey(rows, 0, 'ArrowUp'), { at: 0 });
  assert.deepEqual(gridKey(rows, 1, 'Home'), { at: 0 });
  assert.deepEqual(gridKey(rows, 0, 'End'), { at: 2 });
  assert.deepEqual(gridKey(rows, 1, 'ArrowRight'), { at: 2 });
  assert.deepEqual(gridKey(rows, 1, 'ArrowLeft'), { at: 1, toggle: 's' });
  assert.deepEqual(gridKey(rows, 0, 'ArrowLeft'), { at: 0, toggle: 'g' });
  // A row that does not fold: Right stays, Left goes to its parent.
  assert.deepEqual(gridKey(rows, 2, 'ArrowRight'), { at: 2 });
  assert.deepEqual(gridKey(rows, 2, 'ArrowLeft'), { at: 1 });
  // A group has no Details: Enter folds or unfolds it.
  assert.deepEqual(gridKey(rows, 0, 'Enter'), { at: 0, toggle: 'g' });
  assert.equal(gridKey([], 0, 'ArrowDown'), null);
});
