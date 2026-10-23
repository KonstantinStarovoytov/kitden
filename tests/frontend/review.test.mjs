import assert from 'node:assert/strict';
import { test } from 'node:test';

// review.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
// Node before 21 has no navigator; review.js must load there too.
delete globalThis.navigator;
const { PLACE_IN_TITLE, changeWords, checkStale, reviewLede, staleCheckWanted, targetWords } = await import('../../src/kitden/web/static/js/review.js');
const { panelState } = await import('../../src/kitden/web/static/js/panel.js');

const target = (scope, project = null, others = false) => ({ scope, project, others_unchanged: others });
const remove = { action: 'mcp.remove_direct', steps: [{ client: 'codex', name: 'neon' }] };
const add = { action: 'skill.install', steps: [{ client: 'codex', name: 'tidy', reaches: ['codex'] }] };
const NOTE = 'Undo installs it again; its saved options are not brought back.';

test('the title names the scope the steps target', () => {
  assert.deepEqual(changeWords({ ...remove, target: target('project', '/Users/me/work/website', true) }), { title: 'Remove neon from Codex in website', done: 'Removed neon from Codex in website' });
  assert.equal(changeWords({ ...remove, target: target('all') }).title, 'Remove neon from Codex for all projects');
  assert.equal(changeWords(remove).title, 'Remove neon from Codex'); // no target (an old change): today's words
  // The steps decide over the request: a mix says no scope, even for an add.
  assert.equal(changeWords({ ...add, target: target('mixed') }, { params: { skill: 'x' } }).title, 'Add tidy to Codex');
  assert.equal(changeWords(add, { params: { skill: 'x' } }).title, 'Add tidy to Codex for all projects'); // no target: Part 2's addScope
  // A title that names its place keeps it once.
  const rule = { action: 'gateway.rule', steps: [{ client: 'kitden', name: 'slow' }], target: target('all') };
  assert.equal(changeWords(rule, { params: { server: 'echo', tool: 'slow', state: 'off', project: null } }).title, 'Turn off slow of echo in all projects');
});

test('a title that names its place, or has none, gets no scope words', () => {
  for (const action of ['gateway.rule', 'gateway.rules', 'gateway.strict', 'project.align', 'setup_server.update', 'gateway.remove', 'gateway.keychain']) {
    assert.ok(PLACE_IN_TITLE.includes(action), action);
  }
  const update = { action: 'setup_server.update', steps: [{ client: 'claude_code', name: 'kitden' }], target: target('all') };
  assert.equal(changeWords(update).title, 'Update “show my setup” to Kitden in Claude Code');
  const keychain = { action: 'gateway.keychain', steps: [{ client: 'kitden', name: 'files' }], target: target('all') };
  assert.equal(changeWords(keychain, { params: { server: 'files' } }).title, 'Move the secrets of files to the Keychain');
  const gone = { action: 'gateway.remove', steps: [{ client: 'kitden', name: 'files' }], target: target('mixed') };
  assert.equal(changeWords(gone, { params: { server: 'files' } }).done, 'Removed files from the Kitden gateway');
});

test('the scope words are the folder, all projects, or none', () => {
  assert.equal(targetWords(target('project', '/Users/me/work/website'), 'website'), ' in website');
  assert.equal(targetWords(target('all'), ''), ' for all projects');
  assert.equal(targetWords(target('mixed'), ''), '');
  assert.equal(targetWords(null, ''), '');
  // Without a folder given, the project's own folder name; a project at / is never "undefined".
  assert.equal(targetWords(target('project', '/Users/me/work/website')), ' in website');
  assert.equal(targetWords(target('project', '/')), ' in /');
});

test('a definition the picked project overrides goes to every project but that one', () => {
  const others = { ...remove, target: target('others', '/Users/me/work/website') };
  assert.deepEqual(changeWords(others), { title: 'Remove neon from Codex for all projects except website', done: 'Removed neon from Codex for all projects except website' });
  // Not all projects, and not one project: the lede promises neither.
  assert.equal(reviewLede({ ...add, target: target('others', '/a/web') }, ''), 'Nothing is written until you press Apply. A backup is kept.');
});

test('the title names every client the change reaches, as Details does', () => {
  // Cursor loads Claude Code's plugins: the server says the step reaches it too.
  const plugin = { action: 'plugin.remove', steps: [{ client: 'claude_code', name: 'linter@official', reaches: ['claude_code', 'cursor'] }], target: target('all') };
  assert.deepEqual(changeWords(plugin), { title: 'Remove linter from Claude Code and Cursor for all projects', done: 'Removed linter from Claude Code and Cursor for all projects' });
});

test('the lede promises only the Undo it can keep', () => {
  assert.equal(reviewLede({ ...remove, target: target('project', '/a/web', true), undo_note: null }, 'p1'), 'Other projects are unchanged. Nothing is written until you press Apply. A backup is kept.');
  assert.equal(reviewLede({ action: 'plugin.remove', target: target('all'), undo_note: NOTE }, ''), `Nothing is written until you press Apply. A backup is kept. ${NOTE}`);
  assert.equal(reviewLede({ ...add, target: target('all'), undo_note: null }, ''), 'Adds for all projects. Nothing is written until you press Apply. A backup is kept.');
  assert.equal(reviewLede(remove, ''), 'Nothing is written until you press Apply. A backup is kept.');
  // In one project, but another known project is inside it or around it: no promise.
  assert.equal(reviewLede({ ...remove, target: target('project', '/a/web', false) }, 'p1'), 'Nothing is written until you press Apply. A backup is kept.');
});

test('only an open, previewed review is checked, never while a change is written', () => {
  const review = { type: 'review', change: { id: 'c1', state: 'previewed' } };
  assert.equal(staleCheckWanted(review, { change: false }), true);
  assert.equal(staleCheckWanted(review, { change: true }), false);
  assert.equal(staleCheckWanted({ type: 'review', change: { id: 'c1', state: 'verified' } }, { change: false }), false);
  assert.equal(staleCheckWanted({ type: 'review', change: { state: 'previewed' } }, { change: false }), false); // Add missing with nothing chosen
  assert.equal(staleCheckWanted({ type: 'item' }, { change: false }), false);
  assert.equal(staleCheckWanted(null, { change: false }), false);
});

test('settings changed since the preview: the callout comes first and Apply gives way to Preview again', async () => {
  const node = (tag) => ({
    tag, className: '', textContent: '', children: [], attributes: {}, dataset: {}, listeners: {},
    append(...nodes) { this.children.push(...nodes); },
    prepend(...nodes) { this.children.unshift(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(type, listener) { this.listeners[type] = listener; },
    replaceWith(other) { this.replacedBy = other; },
    focus() { globalThis.document.activeElement = this; },
  });
  const apply = node('button');
  const body = node('div');
  const drawn = { '#drawer .apply': apply, '#drawer .body': body };
  globalThis.document = { createElement: node, querySelector: (selector) => drawn[selector] || null, activeElement: apply };
  const asked = [];
  let answer = { id: 'c1', state: 'previewed', stale: true };
  let meanwhile = () => {};
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url) => { asked.push(url); meanwhile(); return { ok: true, json: async () => answer }; };
  try {
    const review = { type: 'review', change: { id: 'c1', state: 'previewed' }, previewBody: { action: 'mcp.remove_direct' }, note: null, back: null };
    // Not changed: nothing moves.
    answer = { ...answer, stale: false };
    panelState.current = review;
    await checkStale();
    assert.deepEqual([asked, body.children.length, apply.replacedBy], [['/api/changes/c1'], 0, undefined]);
    // Changed: the warning first, read out at once; focus follows from Apply to Preview again.
    answer = { ...answer, stale: true };
    await checkStale();
    const [warning] = body.children;
    assert.equal(warning.attributes.role, 'alert');
    assert.equal(warning.children[1].textContent, 'Settings changed since this preview.');
    assert.equal(apply.replacedBy.textContent, 'Preview again');
    assert.equal(apply.replacedBy.className, 'btn primary');
    assert.equal(globalThis.document.activeElement, apply.replacedBy);
    // Another review opened while the server answered: the old answer changes nothing.
    const later = node('button');
    drawn['#drawer .apply'] = later;
    body.children = [];
    meanwhile = () => { panelState.current = { ...review }; };
    await checkStale();
    assert.deepEqual([body.children.length, later.replacedBy], [0, undefined]);
  } finally {
    panelState.current = null;
    delete globalThis.document;
    globalThis.fetch = realFetch;
  }
});
