import assert from 'node:assert/strict';
import { test } from 'node:test';

// dom.js needs nothing from a browser to load.
const { focusKey, gridKey } = await import('../../src/kitden/web/static/js/dom.js');

test('a control is found again by its data-focus key, a table row by its own key', () => {
  assert.equal(focusKey({ dataset: { focus: 'tab:skill' } }), 'tab:skill');
  assert.equal(focusKey({ dataset: { focus: 'filter:category', key: 'x' } }), 'filter:category');
  assert.equal(focusKey({ dataset: { key: 'mcp_server:github' } }), 'row:mcp_server:github');
  assert.equal(focusKey({ dataset: {} }), null);
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
