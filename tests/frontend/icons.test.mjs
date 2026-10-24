import assert from 'node:assert/strict';
import { test } from 'node:test';

// A tiny fake element: it keeps attributes, dataset and children, which is all icon() uses.
// It has no innerHTML on purpose: icon() must build its children with the DOM calls.
globalThis.document = {
  createElementNS(namespace, tag) {
    const attrs = {};
    return {
      namespaceURI: namespace,
      tagName: tag,
      dataset: {},
      children: [],
      attrs,
      setAttribute(name, value) { attrs[name] = String(value); },
      getAttribute(name) { return name in attrs ? attrs[name] : null; },
      append(...nodes) { this.children.push(...nodes); },
      appendChild(node) { this.children.push(node); return node; },
    };
  },
};
const { icon } = await import('../../src/kitden/web/static/js/dom.js');
const { ICONS } = await import('../../src/kitden/web/static/js/icons.js');

const SVG_NS = 'http://www.w3.org/2000/svg';
const TAGS = ['path', 'circle', 'rect', 'line', 'polyline', 'polygon', 'ellipse'];
const ATTRS = ['d', 'cx', 'cy', 'r', 'rx', 'ry', 'x', 'y', 'x1', 'y1', 'x2', 'y2',
  'width', 'height', 'points', 'fill'];

test('icon draws the lucide shapes at the asked size', () => {
  const node = icon('house', 14);
  assert.equal(node.namespaceURI, SVG_NS);
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
  assert.equal(node.children.length, ICONS.house.length);
  assert.ok(node.children.length > 0);
  for (const child of node.children) {
    assert.equal(child.namespaceURI, SVG_NS);
    assert.equal(child.tagName, 'path');
    assert.match(child.getAttribute('d'), /^M/i);
  }
});

test('each shape keeps its own tag and attributes', () => {
  const dots = icon('grip-vertical').children;
  assert.equal(dots.length, 6);
  assert.deepEqual(dots.map((child) => child.tagName), Array(6).fill('circle'));
  assert.equal(dots[0].getAttribute('cx'), '9');
  assert.equal(dots[0].getAttribute('r'), '1');
});

test('size and class have defaults and can be set', () => {
  assert.equal(icon('plus').getAttribute('width'), '16');
  assert.equal(icon('plus', 20, 'ic big').getAttribute('class'), 'ic big');
});

test('an unknown icon is empty and does not throw', () => {
  const node = icon('nope');
  assert.equal(node.children.length, 0);
  assert.equal(node.getAttribute('width'), '16');
  assert.equal(node.dataset.icon, 'nope');
});

test('a name from Object.prototype is not an icon', () => {
  for (const name of ['constructor', 'toString', '__proto__']) {
    assert.equal(icon(name).children.length, 0);
  }
});

test('the module holds the 46 icons, sorted, as shape data', () => {
  const names = Object.keys(ICONS);
  assert.equal(names.length, 46);
  assert.deepEqual(names, [...names].sort());
  for (const shapes of Object.values(ICONS)) {
    assert.ok(Array.isArray(shapes) && shapes.length > 0);
    for (const [tag, attrs] of shapes) {
      assert.ok(TAGS.includes(tag), tag);
      for (const [key, value] of Object.entries(attrs)) {
        assert.ok(ATTRS.includes(key), key);
        assert.equal(typeof value, 'string');
      }
      if ('fill' in attrs) assert.equal(attrs.fill, 'currentColor');
    }
  }
});
