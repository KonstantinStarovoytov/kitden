import assert from 'node:assert/strict';
import { test } from 'node:test';

// parts.js needs only these from a browser to load; this stub builds just enough nodes.
globalThis.matchMedia = () => ({ matches: false });
globalThis.document = {
  createElement: (tag) => ({
    tag, className: '', textContent: '', children: [], attributes: {},
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(type, listener) { this.listeners = { ...this.listeners, [type]: listener }; },
  }),
};
const { clientCheck, opens } = await import('../../src/kitden/web/static/js/parts.js');

test('a row that opens Details ends with a chevron for the eye and words for a screen reader', () => {
  const node = opens();
  assert.equal(node.className, 'opens');
  const [chevron, words] = node.children;
  assert.equal(chevron.textContent, '›');
  assert.equal(chevron.attributes['aria-hidden'], 'true');
  assert.equal(words.className, 'sr-only');
  assert.equal(words.textContent, 'Open details');
});

test('a client checkbox is named for its client and keeps the client id as its value', () => {
  const heard = [];
  const label = clientCheck('codex', true, null, (checked) => heard.push(checked));
  const [box, name] = label.children;
  assert.equal(label.tag, 'label');
  assert.equal(box.type, 'checkbox');
  assert.equal(box.value, 'codex');
  assert.equal(box.checked, true);
  assert.equal(box.attributes['aria-label'], 'Codex');
  assert.equal(name.textContent, 'Codex');
  box.checked = false;
  box.listeners.change();
  assert.deepEqual(heard, [false]);
});

test('a note after the client name is read as part of its name', () => {
  const label = clientCheck('claude_code', false, 'adds the marketplace first');
  const [box, name, note] = label.children;
  assert.equal(box.checked, false);
  assert.equal(box.attributes['aria-label'], 'Claude Code · adds the marketplace first');
  assert.equal(name.textContent, 'Claude Code');
  assert.equal(note.textContent, ' · adds the marketplace first');
});
