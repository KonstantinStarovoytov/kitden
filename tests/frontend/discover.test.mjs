import assert from 'node:assert/strict';
import { test } from 'node:test';

// discover.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
const { addLabel, alsoLoads, cursorLine, cursorPlugin, startChosen } = await import('../../src/kitden/web/static/js/discover.js');

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

test('Details say how Cursor gets a plugin only when that is a fact', () => {
  const through = 'Cursor: loads it through Claude Code.';
  const once = 'Cursor: gets it through Claude Code once you add it there.';
  const has = 'Cursor: has it.';
  const claude = { installed: ['claude_code'], routes: { claude_code: 'ready' } };
  // Cursor imports Claude Code's plugins and Claude Code has this one: it loads it now.
  assert.equal(cursorLine(claude, both), through);
  // Claude Code can take it but has not: Cursor gets it only after that.
  assert.equal(cursorLine({ installed: [], routes: { claude_code: 'ready' } }, both), once);
  // Cursor does not import them, or Claude Code cannot have this one: nothing to say.
  assert.equal(cursorLine(claude, none), '');
  assert.equal(cursorLine({ installed: [], routes: { codex: 'ready' } }, both), '');
  // A plugin Cursor holds itself is Cursor's own, whether or not it imports.
  assert.equal(cursorLine({ installed: ['cursor'], routes: {} }, both), has);
  assert.equal(cursorLine({ installed: ['cursor'], routes: {} }, none), has);
  assert.equal(cursorLine({ installed: ['cursor'], routes: { claude_code: 'ready' } }, both), has);
  assert.equal(cursorLine({ installed: ['claude_code', 'cursor'], routes: {} }, none), has);
  // Claude Code has it too and Cursor imports: it loads it through Claude Code.
  assert.equal(cursorLine({ installed: ['claude_code', 'cursor'], routes: {} }, both), through);
});

test('an Add button names its item and where it comes from', () => {
  assert.equal(addLabel('canva', 'claude-plugins-official'), 'Add canva from claude-plugins-official');
  assert.equal(addLabel('canva', 'canva@community-tools'), 'Add canva from canva@community-tools');
  assert.equal(addLabel('canva', ''), 'Add canva');
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

test('a Codex copy reaches Cursor through the shared skills folder', () => {
  const line = 'Cursor will also load it from the shared skills folder.';
  const open = ['claude_code', 'codex', 'cursor'];
  // Cursor reads that folder whatever its third-party switch says, so `inherits` does not matter.
  assert.equal(alsoLoads('skill', none, new Set(['codex']), open), line);
  assert.equal(alsoLoads('skill', both, new Set(['codex']), open), line);
  // Not when Cursor is checked (named already), or is not a choice here (missing, or has it).
  assert.equal(alsoLoads('skill', both, new Set(['codex', 'cursor']), open), '');
  assert.equal(alsoLoads('skill', both, new Set(['codex']), ['claude_code', 'codex']), '');
  // Plugins have no shared folder, and a Claude Code copy alone does not use it.
  assert.equal(alsoLoads('plugin', both, new Set(['codex']), open), '');
  assert.equal(alsoLoads('skill', none, new Set(['claude_code']), open), '');
  // With both checked and the switch on, the Claude Code line is the one shown.
  assert.equal(alsoLoads('skill', both, new Set(['claude_code', 'codex']), open), "Cursor will also load it from Claude Code's folder.");
  assert.equal(alsoLoads('skill', none, new Set(['claude_code', 'codex']), open), line);
});

test('a client is checked for you only when it is the one choice', () => {
  assert.deepEqual([...startChosen(['codex'])], ['codex']);
  assert.deepEqual([...startChosen(['claude_code', 'codex'])], []);
});
