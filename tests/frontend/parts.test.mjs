import assert from 'node:assert/strict';
import { test } from 'node:test';

// parts.js needs only these from a browser to load; this stub builds just enough nodes.
globalThis.matchMedia = () => ({ matches: false });
globalThis.document = {
  createElement: (tag) => ({
    tag, className: '', textContent: '', children: [], attributes: {},
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
  }),
};
const { opens } = await import('../../src/kitden/web/static/js/parts.js');

test('a row that opens Details ends with a chevron for the eye and words for a screen reader', () => {
  const node = opens();
  assert.equal(node.className, 'opens');
  const [chevron, words] = node.children;
  assert.equal(chevron.textContent, '›');
  assert.equal(chevron.attributes['aria-hidden'], 'true');
  assert.equal(words.className, 'sr-only');
  assert.equal(words.textContent, 'Open details');
});
