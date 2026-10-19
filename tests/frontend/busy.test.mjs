import assert from 'node:assert/strict';
import { test } from 'node:test';

// parts.js reads matchMedia (through motion.js) when it loads.
globalThis.matchMedia = () => ({ matches: false });
const { busyWhile } = await import('../../src/kitden/web/static/js/dom.js');
const { stepText } = await import('../../src/kitden/web/static/js/parts.js');

// A button stub: classes, attributes, disabled and dataset are all busyWhile touches.
function buttonStub() {
  const classes = new Set();
  const node = {
    disabled: false, dataset: {}, attributes: {},
    classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), contains: (c) => classes.has(c) },
    setAttribute(name, value) { node.attributes[name] = value; },
    removeAttribute(name) { delete node.attributes[name]; },
  };
  return node;
}
const later = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

test('quick work never shows the busy look, so nothing flickers', async () => {
  const node = buttonStub();
  await busyWhile(node, later(5), 40);
  await later(60);
  assert.equal(node.classList.contains('busy'), false);
  assert.equal(node.disabled, false);
});

test('slow work shows the spinner after the delay and gives the button back after', async () => {
  const node = buttonStub();
  const work = busyWhile(node, later(80), 20);
  await later(40);
  assert.equal(node.classList.contains('busy'), true);
  assert.equal(node.attributes['aria-busy'], 'true');
  assert.equal(node.disabled, true);
  await work;
  assert.equal(node.classList.contains('busy'), false);
  assert.equal('aria-busy' in node.attributes, false);
  assert.equal(node.disabled, false);
});

test('a button that was off stays off, and a failure still ends the busy look', async () => {
  const node = buttonStub();
  node.disabled = true;
  const work = busyWhile(node, later(60).then(() => { throw new Error('no'); }), 10);
  await assert.rejects(work);
  assert.equal(node.classList.contains('busy'), false);
  assert.equal(node.disabled, true);
});

test('a second press while the work runs is ignored', async () => {
  const node = buttonStub();
  const first = busyWhile(node, later(30), 100);
  assert.equal(node.dataset.working, '1');
  await first;
  assert.equal(node.dataset.working, undefined);
});

test('a change with several steps counts them; one step just says the verb', () => {
  assert.equal(stepText('Applying', 2, 5), 'Applying 2 of 5');
  assert.equal(stepText('Applying', 1, 1), 'Applying…');
});
