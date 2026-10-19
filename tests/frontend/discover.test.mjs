import assert from 'node:assert/strict';
import { test } from 'node:test';

// discover.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
const { alsoLoads, cursorPlugin, startChosen } = await import('../../src/kitden/web/static/js/discover.js');

const both = { plugin: true, skill: true };
const none = { plugin: false, skill: false };

test('Cursor shows a plugin only when it imports what Claude Code has', () => {
  const ready = { installed: [], routes: { claude_code: 'ready' } };
  assert.equal(cursorPlugin(ready, both), 'off');
  assert.equal(cursorPlugin(ready, none), 'none');
  assert.equal(cursorPlugin({ installed: ['claude_code'], routes: {} }, both), 'off');
  assert.equal(cursorPlugin({ installed: ['codex'], routes: { codex: 'ready' } }, both), 'none');
  assert.equal(cursorPlugin({ installed: ['claude_code', 'cursor'], routes: {} }, both), 'on');
});

test('the plugin form names Cursor while Claude Code is checked', () => {
  const line = 'Cursor will also load this through Claude Code.';
  assert.equal(alsoLoads('plugin', both, new Set(['claude_code'])), line);
  assert.equal(alsoLoads('plugin', both, new Set(['codex'])), '');
  assert.equal(alsoLoads('plugin', { plugin: false, skill: true }, new Set(['claude_code'])), '');
});

test('the skill form names Cursor only when Cursor is not checked itself', () => {
  const line = "Cursor will also load it from Claude Code's folder.";
  assert.equal(alsoLoads('skill', both, new Set(['claude_code'])), line);
  assert.equal(alsoLoads('skill', both, new Set(['claude_code', 'cursor'])), '');
  assert.equal(alsoLoads('skill', { plugin: true, skill: false }, new Set(['claude_code'])), '');
});

test('a client is checked for you only when it is the one choice', () => {
  assert.deepEqual([...startChosen(['codex'])], ['codex']);
  assert.deepEqual([...startChosen(['claude_code', 'codex'])], []);
});
