import assert from 'node:assert/strict';
import { test } from 'node:test';

// offer.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
const { addOptions, alsoLoads, cursorLine, formNote, mcpRows, projectNote, sourceRows, startChosen } = await import('../../src/kitden/web/static/js/offer.js');

const both = { plugin: true, skill: true };
const none = { plugin: false, skill: false };

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

test('the plugin form names Cursor while Claude Code is checked', () => {
  const line = 'Cursor will also load this through Claude Code.';
  assert.equal(alsoLoads('plugin', both, new Set(['claude_code'])), line);
  assert.equal(alsoLoads('plugin', both, new Set(['codex'])), '');
  assert.equal(alsoLoads('plugin', { plugin: false, skill: true }, new Set(['claude_code'])), '');
});

test('the form names Cursor only when Cursor is on this computer', () => {
  // The same rule as the Affects line in Details (addReach): without Cursor, nothing to name.
  assert.equal(alsoLoads('plugin', both, new Set(['claude_code']), [], ['claude_code', 'codex']), '');
  assert.equal(alsoLoads('skill', both, new Set(['claude_code']), ['claude_code', 'codex'], ['claude_code', 'codex']), '');
  assert.equal(alsoLoads('plugin', both, new Set(['claude_code']), [], ['claude_code', 'cursor']), 'Cursor will also load this through Claude Code.');
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

test('an add in a project view says it is for every project', () => {
  assert.equal(projectNote('p1'), 'Adds for all projects.');
  assert.equal(projectNote(''), null);
});

test('the Add form passes the warning of each checked client, as its cell does', () => {
  const warn = 'Codex already has documents from openai-curated. It will load both.';
  const row = { cells: {
    claude_code: { add: { action: 'plugin.install', warn: null } },
    codex: { add: { action: 'plugin.install', warn } },
    cursor: { add: null },
  } };
  assert.equal(formNote(row, ['claude_code'], ''), null);
  assert.equal(formNote(row, ['claude_code', 'codex'], ''), warn);
  assert.equal(formNote(row, ['codex'], 'p1'), `${warn} Adds for all projects.`);
  assert.equal(formNote(row, ['claude_code'], 'p1'), 'Adds for all projects.');
});

test('Details offers the add the cell offers', () => {
  const own = { action: 'skill.install', label: '+ Add', skill: 'project/api-style', project_only: true };
  const row = { kind: 'skill', cells: { claude_code: { add: own }, codex: { add: null }, cursor: { add: null } } };
  assert.deepEqual(addOptions(row, null).map((o) => [o.client, o.label]), [['claude_code', 'Add to Claude Code…']]);
});

test("a plugin's commands, source and pinned version wait under Technical details", () => {
  const offer = {
    inside: { skills: [], commands: [], agents: [], hooks: [], mcp_servers: [{ name: 'files', runs: 'npx files-mcp' }] },
    source: { repo: 'acme/tools', path: 'plugins/files', ref: 'main', sha: '0123456789abcdef' },
  };
  assert.deepEqual(mcpRows(offer), [{ title: 'MCP server files', summary: 'npx files-mcp' }]);
  assert.deepEqual(sourceRows(offer), [
    { title: 'Source', summary: 'acme/tools · plugins/files' },
    { title: 'Pinned to', summary: 'main · 0123456789ab' },
  ]);
  // Not downloaded yet, or no source given: nothing to fold.
  assert.deepEqual(mcpRows({ inside: null }), []);
  assert.deepEqual(sourceRows({ source: {} }), []);
  assert.deepEqual(sourceRows({ source: { path: '/m/plugins/x', sha: 'abc' } }), [
    { title: 'Source', summary: '/m/plugins/x' },
    { title: 'Pinned to', summary: 'abc' },
  ]);
});
