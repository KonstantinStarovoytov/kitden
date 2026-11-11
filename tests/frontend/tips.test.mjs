import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { test } from 'node:test';

const { tipFor } = await import('../../src/kitden/web/static/js/tips.js');

const JS = new URL('../../src/kitden/web/static/js/', import.meta.url);
const source = readdirSync(JS).filter((f) => f.endsWith('.js')).map((f) => readFileSync(new URL(f, JS), 'utf8')).join('\n');

// Words that end in "…" but are not actions: a wait, a placeholder, a search box, a step of an update.
const NOT_ACTIONS = new Set(['Applying…', 'Bearer …', 'Checking the version…', 'Checking…', 'Downloading…', 'Find a project…', 'Installing…', 'Loading…', 'Reading what it holds…', 'Reloading the page…', 'Restarting Kitden…', 'Search MCP servers…', 'Search plugins and skills…', 'Searching…', 'Still checking …', 'Waiting for browser…']);
// Actions whose label says it all: hover words would only repeat it.
const SAYS_IT_ALL = new Set(['Add…', 'Add to Codex…', 'Add to Claude Code or Codex…', 'Show…', 'Update…']);

test('every action label has hover words, or is known to say it all', () => {
  const labels = [...new Set([...source.matchAll(/"([A-Z][A-Za-z ,'/-]{2,40}…)"/g)].map((m) => m[1]))].filter((l) => !NOT_ACTIONS.has(l));
  assert.ok(labels.length > 30);
  assert.deepEqual(labels.filter((label) => !tipFor(label) && !SAYS_IT_ALL.has(label)), []);
});

test('hover words never repeat a plain label', () => {
  for (const label of ['Close', 'Done', 'Cancel', 'Cancel all', 'Details', 'More', 'Map', 'List', 'Remove', 'Preview', 'Sign in', 'Show all', 'Try again', 'Take it out', 'Add to Codex…']) {
    assert.equal(tipFor(label), null, label);
  }
});

test('labels built with a name get words that add something', () => {
  for (const label of [
    'Connect Cursor to the gateway…', 'Disconnect Codex from the gateway…', 'Move all 3…', 'Move into Obot…',
    'Move secrets to the Keychain…', 'Put back in Cursor…', 'Remove from Codex…', 'Set up in Cursor…',
    'Turn off in website…', 'Turn on search_docs in website…', 'Turn it on in Codex…', 'Turn off Figma in this project…',
    "Update neon's Kitden entry…", "Use website's rule…", 'Apply', 'Apply all', 'Apply 3', 'Undo', 'Replace…', 'Sign out', 'Add access…',
  ]) assert.ok(tipFor(label), label);
});

test('the words say what the label leaves out', () => {
  assert.equal(tipFor('Move all 3…'), 'Moves every server outside the gateway that can move into it, in one change. Servers set up differently in two clients stay out until you keep one.');
  assert.equal(tipFor('Turn off in some projects…'), 'You pick the projects. Every other project keeps the shared rule, and new projects follow it too.');
  assert.equal(tipFor('Turn off in website…'), 'A rule for website only. The shared rule and other projects stay as they are.');
});

const { wordsOf } = await import('../../src/kitden/web/static/js/tips.js');

test('words already on screen are not shown again, unless they are cut off', () => {
  globalThis.getComputedStyle = () => ({ textOverflow: 'ellipsis' });
  const node = (text, title, cut = false) => ({
    title, textContent: text, dataset: {}, disabled: false, scrollWidth: 100, clientWidth: 100,
    removeAttribute(name) { if (name === 'title') this.title = ''; },
    getAttribute: () => null,
    querySelectorAll: () => [{ scrollWidth: cut ? 200 : 100, clientWidth: 100 }],
  });
  assert.equal(wordsOf(node('+ Add to Codex…', '+ Add to Codex…')), null);
  assert.equal(wordsOf(node('+ Add to Codex…', '+ Add to Codex…', true)), '+ Add to Codex…');
  // A map block's title is its name, already shown beside its state.
  assert.equal(wordsOf(node('Kitden gateway On this computer 3 clients 7 servers', 'Kitden gateway')), null);
  assert.equal(wordsOf(node('reference-lang… 2 of 2 on', 'reference-langfuse-docs', true)), 'reference-langfuse-docs');
  assert.equal(wordsOf(node('Move all 3…', 'Move all 3…')), tipFor('Move all 3…'));
  assert.equal(wordsOf(node('', 'In preview. Press to take it out.')), 'In preview. Press to take it out.');
});

test('an icon whose name is written beside it gets no hover words', () => {
  const icon = {
    title: 'Kitden gateway', textContent: '', dataset: {}, disabled: false, scrollWidth: 24, clientWidth: 24,
    parentElement: { textContent: ' Kitden gateway 7 servers' },
    getAttribute: () => null, querySelectorAll: () => [],
  };
  assert.equal(wordsOf(icon), null);
  // Alone, as a client tile among others, its name is the hover words.
  assert.equal(wordsOf({ ...icon, parentElement: { textContent: '' } }), 'Kitden gateway');
});
