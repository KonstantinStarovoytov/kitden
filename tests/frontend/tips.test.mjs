import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { test } from 'node:test';

const { tipFor } = await import('../../src/kitden/web/static/js/tips.js');

const JS = new URL('../../src/kitden/web/static/js/', import.meta.url);
const source = readdirSync(JS).filter((f) => f.endsWith('.js')).map((f) => readFileSync(new URL(f, JS), 'utf8')).join('\n');

// Words that end in "…" but are not actions: a wait, a placeholder, a search box.
const NOT_ACTIONS = new Set(['Applying…', 'Bearer …', 'Checking the version…', 'Checking…', 'Find a project…', 'Loading…', 'Reading what it holds…', 'Search MCP servers…', 'Search plugins and skills…', 'Searching…', 'Show…', 'Still checking …', 'Waiting for browser…']);

test('every action label in the page code has hover words', () => {
  const labels = [...new Set([...source.matchAll(/"([A-Z][A-Za-z ,'/-]{2,40}…)"/g)].map((m) => m[1]))].filter((l) => !NOT_ACTIONS.has(l));
  assert.ok(labels.length > 30);
  assert.deepEqual(labels.filter((label) => !tipFor(label)), []);
});

test('labels built with a name get words too', () => {
  for (const label of [
    'Add to Claude Code or Codex…', 'Connect Cursor to the gateway…', 'Disconnect Codex from the gateway…', 'Move all 3…',
    'Move into Obot…', 'Move secrets to the Keychain…', 'Put back in Cursor…', 'Remove from Codex…', 'Set up in Cursor…',
    'Turn off in website…', 'Turn on search_docs in website…', 'Turn it on in Codex…', 'Turn off Figma in this project…',
    'Turn on in Claude Code…', "Update neon's Kitden entry…", "Use website's rule…",
    'Apply', 'Apply all', 'Apply 3', 'Cancel all', 'Undo', 'Preview', 'Rescan', 'Map', 'List', 'Details', 'Replace…', 'Remove', 'Sign out', 'Add access…',
  ]) assert.ok(tipFor(label), label);
});

test('the words say what the button does, plainly', () => {
  assert.equal(tipFor('Turn off in some projects…'), 'Pick the projects where it is off. The other projects keep the shared rule.');
  assert.equal(tipFor('Turn strict mode off…'), 'Tools without a rule of their own are on again, and new tools start on.');
  assert.equal(tipFor('Turn off in this project…'), 'Turns it off only in the picked project. Everything else stays as it is.');
  assert.equal(tipFor("Use website's rule…"), "Drops this project's own rule, so it follows website's rule again.");
  assert.equal(tipFor('Something else'), null);
});
