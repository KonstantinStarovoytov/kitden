import assert from 'node:assert/strict';
import { test } from 'node:test';

// A tiny fake element: it keeps attributes, dataset and innerHTML, which is all icon() uses.
globalThis.document = {
  createElementNS(namespace, tag) {
    const attrs = {};
    return {
      namespaceURI: namespace,
      tagName: tag,
      dataset: {},
      innerHTML: '',
      setAttribute(name, value) { attrs[name] = String(value); },
      getAttribute(name) { return name in attrs ? attrs[name] : null; },
    };
  },
};
const { icon } = await import('../../src/kitden/web/static/js/dom.js');
const { ICONS } = await import('../../src/kitden/web/static/js/icons.js');

test('icon draws the lucide body at the asked size', () => {
  const node = icon('house', 14);
  assert.equal(node.namespaceURI, 'http://www.w3.org/2000/svg');
  assert.equal(node.tagName, 'svg');
  assert.equal(node.getAttribute('width'), '14');
  assert.equal(node.getAttribute('height'), '14');
  assert.equal(node.getAttribute('viewBox'), '0 0 24 24');
  assert.equal(node.getAttribute('fill'), 'none');
  assert.equal(node.getAttribute('stroke'), 'currentColor');
  assert.equal(node.getAttribute('stroke-width'), '1.75');
  assert.equal(node.getAttribute('stroke-linecap'), 'round');
  assert.equal(node.getAttribute('stroke-linejoin'), 'round');
  assert.equal(node.getAttribute('aria-hidden'), 'true');
  assert.equal(node.getAttribute('class'), 'ic');
  assert.equal(node.dataset.icon, 'house');
  assert.match(node.innerHTML, /<path/);
});

test('size and class have defaults and can be set', () => {
  assert.equal(icon('plus').getAttribute('width'), '16');
  assert.equal(icon('plus', 20, 'ic big').getAttribute('class'), 'ic big');
});

test('an unknown icon is empty and does not throw', () => {
  const node = icon('nope');
  assert.equal(node.innerHTML, '');
  assert.equal(node.getAttribute('width'), '16');
});

test('the module holds the 46 icons, sorted, as plain markup', () => {
  const names = Object.keys(ICONS);
  assert.equal(names.length, 46);
  assert.deepEqual(names, [...names].sort());
  for (const body of Object.values(ICONS)) assert.doesNotMatch(body, /<svg|<\/svg/);
});

test('a name from Object.prototype is not an icon', () => {
  for (const name of ['constructor', 'toString', '__proto__']) assert.equal(icon(name).innerHTML, '');
});
