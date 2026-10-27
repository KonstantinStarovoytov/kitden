import assert from 'node:assert/strict';
import { test } from 'node:test';

// offer.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
const { addFormBody, addOptions, alsoLoads, cursorLine, formNote, mcpRows, projectNote, sourceRows, startChosen } = await import('../../src/kitden/web/static/js/offer.js');
const { syncTray } = await import('../../src/kitden/web/static/js/details.js');
const { review } = await import('../../src/kitden/web/static/js/review.js');
const { cancelTray, keyFor, onTray, takeOut, tray } = await import('../../src/kitden/web/static/js/tray.js');

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

// A page whose Details hold `controls`, and a stand-in server for the tray: a batch preview answers
// with one row per request (as details.test.mjs's trayPage). `sent` keeps every address asked.
function formPage() {
  const page = { controls: [], sent: [] };
  const node = (tag) => {
    const classes = new Set();
    const made = {
      tag, textContent: '', childNodes: [], attributes: {}, dataset: {}, listeners: {}, title: '', disabled: false,
      get className() { return [...classes].join(' '); },
      set className(value) { classes.clear(); String(value).split(/\s+/).filter(Boolean).forEach((name) => classes.add(name)); },
      classList: { add: (name) => classes.add(name), remove: (name) => classes.delete(name), toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)), contains: (name) => classes.has(name) },
      append(...nodes) { made.childNodes.push(...nodes); },
      setAttribute(name, value) { made.attributes[name] = String(value); },
      getAttribute: (name) => (name in made.attributes ? made.attributes[name] : null),
      removeAttribute(name) { delete made.attributes[name]; },
      addEventListener(type, listener) { (made.listeners[type] ||= []).push(listener); },
      // An event on this node, and what it set off.
      async fire(type) { (made.listeners[type] || []).forEach((listener) => listener({ preventDefault() {} })); await new Promise((resolve) => setTimeout(resolve, 0)); },
    };
    return made;
  };
  const drawer = { querySelectorAll: (selector) => (selector === '[data-tray]' ? page.controls.filter((c) => c.dataset.tray) : []) };
  globalThis.document = { createElement: node, getElementById: () => null, querySelector: (selector) => (selector === '#drawer' ? drawer : null), querySelectorAll: () => [] };
  globalThis.fetch = async (url, options = {}) => {
    page.sent.push(url);
    if (url !== '/api/batch/preview') return Response.json({});
    const { requests } = JSON.parse(options.body);
    return Response.json({
      id: `c${page.sent.length}`, action: 'batch', state: 'previewed', error: null, undo_note: null,
      steps: requests.map(() => ({ client: 'codex', name: 'x' })),
      rows: requests.map((r, at) => ({ id: r.id, kind: r.kind, title: r.title, detail: '', project: null, steps: [at], after: [] })),
    });
  };
  // What initPanel does: the looks follow every change of the tray.
  page.stop = onTray(syncTray);
  return page;
}

test('an add form says In preview while its row waits and goes back after', async () => {
  const page = formPage();
  try {
    const chosen = new Set(['codex']);
    const bodyOf = () => ({ action: 'skill.install', targets: [...chosen].map((client) => ({ client })), params: { skill: 'tidy@toolbox' } });
    const form = addFormBody(document.createElement('fieldset'), chosen, bodyOf, (body) => review(body, { note: 'Adds for all projects.' }));
    const submit = form.childNodes.find((n) => n.tag === 'button');
    page.controls.push(submit);
    const words = () => submit.childNodes.map((n) => n.textContent).join('');
    assert.deepEqual([words(), submit.attributes['aria-disabled']], ['Preview', undefined]);
    await form.fire('submit');
    assert.deepEqual(tray.rows.map((r) => [r.key, r.note]), [[keyFor(bodyOf()), 'Adds for all projects.']]);
    // While its row waits it says so and takes no press.
    assert.deepEqual([words(), submit.attributes['aria-disabled']], ['In preview', 'true']);
    const asked = page.sent.length;
    await form.fire('submit');
    assert.equal(page.sent.length, asked);
    // Another tick is another change: Preview again, and back to In preview with the first.
    chosen.add('claude_code');
    await form.fire('change');
    assert.deepEqual([words(), submit.attributes['aria-disabled']], ['Preview', undefined]);
    chosen.delete('claude_code');
    await form.fire('change');
    assert.equal(words(), 'In preview');
    // Out of the tray, the form is back.
    await takeOut(keyFor(bodyOf()));
    assert.deepEqual([words(), submit.attributes['aria-disabled']], ['Preview', undefined]);
  } finally {
    await cancelTray();
    page.stop();
    delete globalThis.document;
    delete globalThis.fetch;
  }
});
