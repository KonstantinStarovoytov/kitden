import assert from 'node:assert/strict';
import { test } from 'node:test';

// review.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
// Node before 21 has no navigator; review.js must load there too.
delete globalThis.navigator;
const { PLACE_IN_TITLE, changeWords, checkStale, review, reviewLede, staleCheckWanted, stoppedWords, targetWords } = await import('../../src/kitden/web/static/js/review.js');
const { applyOnMap, barWords, cancelOnMap, leaveMap, mapPreview, outcomeLine, previewOnMap, writingLine } = await import('../../src/kitden/web/static/js/map-review.js');
const { closeForProject, hideToast, isPanelOpen, openPanel, panelState } = await import('../../src/kitden/web/static/js/panel.js');
const { moveBody } = await import('../../src/kitden/web/static/js/details.js');
const { busy, state } = await import('../../src/kitden/web/static/js/store.js');

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

// A review drawn in a stub page: its body and its Apply button. `drawn` is what the page shows
// (a replaced Apply is gone from it); `asked` lists each request; `answers(url, options)` answers.
function stubPage(answers) {
  const drawn = {};
  const node = (tag) => ({
    tag, className: '', textContent: '', children: [], attributes: {}, dataset: {}, listeners: {},
    append(...nodes) { this.children.push(...nodes); },
    prepend(...nodes) { this.children.unshift(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(type, listener) { this.listeners[type] = listener; },
    replaceWith(other) {
      this.replacedBy = other;
      for (const key of Object.keys(drawn)) if (drawn[key] === this) drawn[key] = null;
    },
    focus() { globalThis.document.activeElement = this; },
  });
  const apply = node('button');
  const body = node('div');
  Object.assign(drawn, { '#drawer .apply': apply, '#drawer .body': body });
  globalThis.document = { createElement: node, querySelector: (selector) => drawn[selector] || null, activeElement: apply };
  const asked = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    asked.push({ url, method: options.method || 'GET', body: options.body });
    const { status = 200, json } = await answers(url, options);
    return { ok: status < 400, status, json: async () => json };
  };
  const done = () => {
    panelState.current = null;
    delete globalThis.document;
    globalThis.fetch = realFetch;
  };
  return { node, apply, body, drawn, asked, done };
}

const previewed = (fields = {}) => ({ type: 'review', change: { id: 'c1', state: 'previewed' }, previewBody: { action: 'mcp.remove_direct', targets: [{ item: 'i1' }], params: {} }, note: null, back: null, ...fields });

test('settings changed since the preview: the callout comes first and Apply gives way to Preview again', async () => {
  let stale = false;
  let meanwhile = () => {};
  const page = stubPage(() => { meanwhile(); return { json: { id: 'c1', state: 'previewed', stale } }; });
  const { node, apply, body, drawn, asked } = page;
  try {
    const from = { draw: () => {} };
    const review = previewed({ from });
    // Not changed: nothing moves.
    panelState.current = review;
    await checkStale();
    assert.deepEqual([asked.map((a) => a.url), body.children.length, apply.replacedBy, from.stale], [['/api/changes/c1'], 0, undefined, undefined]);
    // Changed: the warning first, read out at once; focus follows from Apply to Preview again.
    stale = true;
    await checkStale();
    const [warning] = body.children;
    assert.equal(warning.attributes.role, 'alert');
    assert.equal(warning.children[1].textContent, 'Settings changed since this preview.');
    assert.equal(apply.replacedBy.textContent, 'Preview again');
    assert.equal(apply.replacedBy.className, 'btn primary');
    assert.equal(globalThis.document.activeElement, apply.replacedBy);
    // The Details it came from is out of date too: Cancel, also after Preview again, reads it again.
    assert.equal(from.stale, true);
    // A later rescan: Apply has given way already, so the server is not asked again.
    await checkStale();
    assert.equal(asked.length, 2);
    // Another review opened while the server answered: the old answer changes nothing.
    const later = node('button');
    drawn['#drawer .apply'] = later;
    body.children = [];
    meanwhile = () => { panelState.current = { ...review }; };
    await checkStale();
    assert.deepEqual([body.children.length, later.replacedBy], [0, undefined]);
  } finally {
    page.done();
  }
});

test('Preview again drops this preview once and asks for the same change again', async () => {
  const page = stubPage((url) => {
    if (url === '/api/changes/c1') return { json: { id: 'c1', state: 'previewed', stale: true } };
    if (url === '/api/changes/c1/cancel') return { json: { id: 'c1', state: 'cancelled' } };
    return { status: 422, json: { detail: 'Refused.' } }; // the new preview: a refusal goes back
  });
  try {
    let backed;
    const back = new Promise((resolve) => { backed = resolve; });
    const review = previewed({ note: 'For all projects.', back: (answer) => backed(answer) });
    panelState.current = review;
    await checkStale();
    page.apply.replacedBy.listeners.click({});
    assert.deepEqual(await back, { error: 'Refused.' });
    const posts = page.asked.filter((a) => a.method === 'POST');
    assert.deepEqual(posts.map((a) => a.url), ['/api/changes/c1/cancel', '/api/changes/preview']);
    assert.deepEqual(JSON.parse(posts[1].body), { ...review.previewBody, picked: null });
    assert.equal(review.change.state, 'cancelled');
  } finally {
    page.done();
  }
});

// The map's review bar (S.8): a preview started on the map shows there, not in Details.
const IDLE = { body: null, change: null, phase: 'idle', done: 0, total: 0, failure: null, refused: null };
const change = { id: 'c1', action: 'gateway.move', steps: [{ client: 'kitden', name: 'github' }, { client: 'claude_code', name: 'github' }], after: [{ client: 'claude_code', state: 'gw', word: 'Via gateway' }], target: { scope: 'all' } };

test('the bar says what will happen, then what is being written', () => {
  const body = moveBody({ id: 'kitden', kind: 'kitden' }, ['i1']);
  assert.deepEqual(barWords({ ...IDLE, phase: 'ready', change, body }).outcome, 'Claude Code: Via gateway.');
  const applying = barWords({ ...IDLE, phase: 'applying', change, body, done: 1, total: 3 });
  assert.deepEqual([applying.apply, applying.outcome, applying.cancelWaits], ['Applying 1 of 3', 'Writing the settings of the Kitden gateway and Claude Code. A backup is kept.', true]);
  assert.equal(writingLine([{ client: 'claude_code' }]), "Writing Claude Code's settings. A backup is kept.");
});

test('an error stays and says nothing changed when nothing was written', () => {
  const stale = barWords({ ...IDLE, phase: 'failed', change, body: {}, failure: { state: 'stale' } });
  assert.ok(stale.outcome.endsWith('Nothing was changed.')); assert.equal(stale.retry, true);
  const refused = barWords({ ...IDLE, phase: 'failed', refused: 'github signs in with OAuth; it stays direct for now.' });
  assert.equal(refused.outcome, 'github signs in with OAuth; it stays direct for now. Nothing was changed.'); assert.equal(refused.retry, false);
});

test('the bar names the change with its scope, and each end says what Kitden knows', () => {
  const body = moveBody({ id: 'kitden', kind: 'kitden' }, ['i1']);
  const ready = barWords({ ...IDLE, phase: 'ready', change, body });
  assert.deepEqual([ready.title, ready.apply, ready.cancelWaits, ready.retry], ['Move github into the Kitden gateway for all projects', 'Apply', false, false]);
  // Before the server counts the steps, Apply says it is applying.
  assert.equal(barWords({ ...IDLE, phase: 'applying', change, body }).apply, 'Applying…');
  const failed = (failure) => barWords({ ...IDLE, phase: 'failed', change, body, failure });
  assert.equal(failed({ state: 'stale' }).outcome, 'Settings changed since this preview. Nothing was changed.');
  assert.equal(failed({ state: 'restored', error: 'x failed. The original settings were restored.' }).apply, 'Try again');
  // Unknown: it may have been written, so it never says nothing changed.
  const lost = 'Could not confirm the result. Check Changes before trying again.';
  assert.equal(failed({ state: null, text: lost }).outcome, lost);
  // A refusal has no change to name or to apply: only Cancel.
  const refused = barWords({ ...IDLE, phase: 'failed', body, refused: 'Refused.' });
  assert.deepEqual([refused.title, refused.apply], ['Could not prepare this change', null]);
});

// What the engine says when a change stops: paths, commands and Keychain names.
const STALE_ERROR = '/Users/me/.codex/config.toml changed since preview; review the change again';
const BACK_ERROR = '`claude mcp add` failed in /Users/me/.claude.json. The original settings were restored.';
const LOST_ERROR = '`claude mcp add` failed. github/TOKEN in your Keychain keeps the new value.';

test('a change that did not check out says nothing changed only when the engine put everything back', () => {
  const failed = (failure) => barWords({ ...IDLE, phase: 'failed', change, body: {}, failure }).outcome;
  // Everything was put back: "Nothing was changed.". The engine's own words stay in Details.
  assert.equal(failed({ state: 'restored', error: BACK_ERROR }), 'The change did not check out. Nothing was changed.');
  assert.equal(stoppedWords({ state: 'restored', error: BACK_ERROR }, null), 'The change did not check out. (`claude mcp add` failed in ~/.claude.json. The original settings were restored.) Nothing was changed.');
  // Something could not be put back: the bar never claims nothing changed and points to Changes;
  // Details names what.
  const notAll = 'The change did not check out. Not everything was put back. Check Changes before trying again.';
  assert.equal(failed({ state: 'restored', error: LOST_ERROR }), notAll);
  assert.equal(failed({ state: 'restored', error: null }), notAll);
  assert.equal(stoppedWords({ state: 'restored', error: LOST_ERROR }, null), 'The change did not check out. (`claude mcp add` failed. github/TOKEN in your Keychain keeps the new value.)');
  // Both places make the same "Nothing was changed." call through the one helper.
  for (const after of [{ state: 'stale', error: STALE_ERROR }, { state: 'restored', error: BACK_ERROR }, { state: 'restored', error: LOST_ERROR }]) {
    assert.equal(failed(after).endsWith('Nothing was changed.'), stoppedWords(after, null).endsWith('Nothing was changed.'));
  }
  assert.equal(stoppedWords(null, null), 'Could not confirm the result. Check Changes before trying again.');
});

test("the bar never shows the engine's own words: no path, no command", () => {
  const ends = [
    { state: 'stale', error: STALE_ERROR }, { state: 'restored', error: BACK_ERROR }, { state: 'restored', error: LOST_ERROR },
    { state: 'cancelled', error: '/Users/me/.claude.json' }, { state: null, error: null },
  ];
  for (const failure of ends) {
    const words = barWords({ ...IDLE, phase: 'failed', change, body: moveBody({ id: 'kitden', kind: 'kitden' }, ['g']), failure });
    for (const text of Object.values(words).filter((v) => typeof v === 'string')) {
      assert.ok(!/[/~`]/.test(text) && !text.includes('review the change again'), text);
    }
  }
  assert.equal(barWords({ ...IDLE, phase: 'failed', change, body: {}, failure: { state: 'stale', error: STALE_ERROR } }).outcome, 'Settings changed since this preview. Nothing was changed.');
});

test("the outcome line groups the After chips by word, else the first note's first sentence", () => {
  const after = [{ client: 'claude_code', state: 'gw', word: 'Via gateway' }, { client: 'codex', state: 'gw', word: 'Via gateway' }, { client: 'cursor', state: 'off', word: 'Removed' }];
  assert.equal(outcomeLine({ after }), 'Claude Code and Codex: Via gateway. Cursor: Removed.');
  assert.equal(outcomeLine({ after: [{ note: 'No client uses the Kitden gateway yet. Set one up first.' }] }), 'No client uses the Kitden gateway yet.');
  assert.equal(outcomeLine({ after: [] }), '');
  assert.equal(writingLine([{ client: 'kitden' }]), "Writing the Kitden gateway's settings. A backup is kept.");
});

// A fetch that answers each request by `answers(url, sent)` and records it.
function stubFetch(answers) {
  const asked = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    const sent = options.body ? JSON.parse(options.body) : null;
    asked.push({ url, method: options.method || 'GET', body: sent });
    const { status = 200, json = {} } = (await answers(url, sent)) || {};
    return { ok: status < 400, status, json: async () => json };
  };
  const done = () => {
    globalThis.fetch = realFetch;
    Object.assign(mapPreview, IDLE);
    state.project = '';
    busy.change = false;
  };
  return { asked, done };
}
const posts = (asked) => asked.filter((a) => a.method === 'POST').map((a) => a.url);
const body = moveBody({ id: 'kitden', kind: 'kitden' }, ['g']);

test("a map preview posts the move with the picked project; a refusal keeps the server's words", async () => {
  const net = stubFetch(() => ({ status: 422, json: { detail: 'github signs in with OAuth; it stays direct for now.' } }));
  try {
    state.project = 'p1';
    let drawn = 0;
    await previewOnMap(body, () => { drawn += 1; });
    assert.deepEqual(net.asked[0].body, { ...body, picked: 'p1' });
    assert.deepEqual([mapPreview.phase, mapPreview.change, mapPreview.refused], ['failed', null, 'github signs in with OAuth; it stays direct for now.']);
    // Drawn once while it is prepared and once with the answer.
    assert.equal(drawn, 2);
    // Cancel ends it; a refusal has nothing to cancel on the server.
    await cancelOnMap(() => {});
    assert.deepEqual([mapPreview.phase, posts(net.asked)], ['idle', ['/api/changes/preview']]);
  } finally {
    net.done();
  }
});

test('one preview on the map at a time, and another project picked meanwhile drops it', async () => {
  let n = 0;
  const net = stubFetch((url) => (url === '/api/changes/preview' ? { json: { ...change, id: `c${++n}`, state: 'previewed' } } : { json: {} }));
  try {
    await previewOnMap(body, () => {});
    assert.deepEqual([mapPreview.phase, mapPreview.change.id], ['ready', 'c1']);
    // A second drop cancels the first preview on the server before it asks again.
    await previewOnMap(body, () => {});
    assert.deepEqual(posts(net.asked), ['/api/changes/preview', '/api/changes/c1/cancel', '/api/changes/preview']);
    assert.equal(mapPreview.change.id, 'c2');
    // Leaving the map cancels a preview that is only previewed.
    leaveMap();
    assert.deepEqual([mapPreview.phase, posts(net.asked).at(-1)], ['idle', '/api/changes/c2/cancel']);
    // Another project picked while the server prepares it: it shows nothing, the server forgets it.
    const asking = previewOnMap(body, () => {});
    state.project = 'other';
    await asking;
    assert.equal(mapPreview.phase, 'idle');
    assert.equal(posts(net.asked).at(-1), '/api/changes/c3/cancel');
  } finally {
    net.done();
  }
});

test('Apply counts the steps; an error stays in the bar, and Cancel waits while it is written', async () => {
  let progress = null;
  // The bar is on the page while it is written.
  const bar = {};
  globalThis.document = { addEventListener: (type, fn) => { if (type === 'kitden:progress') progress = fn; }, removeEventListener: () => {}, querySelector: (selector) => (selector === '.review-bar' ? bar : null) };
  const net = stubFetch(async (url) => {
    if (url === '/api/changes/preview') return { json: { ...change, state: 'previewed' } };
    if (url === '/api/changes/c1/apply') {
      progress({ detail: { id: 'c1', done: 1, total: 3 } });
      assert.deepEqual([mapPreview.phase, mapPreview.done, mapPreview.total, busy.change], ['applying', 1, 3, true]);
      // Cancel waits while it is written.
      await cancelOnMap(() => {});
      assert.equal(mapPreview.phase, 'applying');
      return { status: 409, json: { ...change, state: 'stale' } };
    }
    return { json: {} };
  });
  try {
    await previewOnMap(body, () => {});
    const words = [];
    await applyOnMap(() => words.push(barWords(mapPreview).apply));
    assert.deepEqual(words.slice(0, 2), ['Applying…', 'Applying 1 of 3']);
    assert.deepEqual([mapPreview.phase, mapPreview.failure.state, busy.change], ['failed', 'stale', false]);
    assert.equal(barWords(mapPreview).outcome, 'Settings changed since this preview. Nothing was changed.');
    // "Try again" is a new preview; the stale one is not cancelled on the server.
    await previewOnMap(mapPreview.body, () => {});
    assert.deepEqual([mapPreview.phase, posts(net.asked).filter((u) => u.endsWith('/cancel'))], ['ready', []]);
  } finally {
    net.done();
    delete globalThis.document;
  }
});

test('a review asked elsewhere first ends a preview on the map, and waits while one is written', async () => {
  const net = stubFetch((url, sent) => {
    if (url !== '/api/changes/preview') return { json: {} };
    return sent.action === 'gateway.move' ? { json: { ...change, state: 'previewed' } } : { status: 422, json: { detail: 'Refused.' } };
  });
  try {
    await previewOnMap(body, () => {});
    const remove = { action: 'mcp.remove_direct', targets: [{ item: 'x' }], params: {} };
    let backed = null;
    const back = (answer) => { backed = answer; };
    mapPreview.phase = 'applying';
    await review(remove, { back });
    assert.deepEqual([posts(net.asked).length, backed], [1, null]); // nothing asked while the map's change is written
    mapPreview.phase = 'ready';
    await review(remove, { back });
    assert.deepEqual(posts(net.asked).slice(1), ['/api/changes/c1/cancel', '/api/changes/preview']);
    assert.deepEqual([mapPreview.phase, backed], ['idle', { error: 'Refused.' }]);
  } finally {
    net.done();
  }
});

// Just enough of a page for the panel and the toast: the drawer, its scrim, the shell, the toast,
// and the map's review bar when `bar` is on the page.
function fakePage({ bar = false } = {}) {
  const node = (tag = 'div') => {
    const classes = new Set();
    return {
      tag, className: '', textContent: '', children: [], attributes: {}, dataset: {}, listeners: {},
      classList: { add: (n) => classes.add(n), remove: (n) => classes.delete(n), toggle: (n, on) => (on ? classes.add(n) : classes.delete(n)), contains: (n) => classes.has(n) },
      append(...nodes) { this.children.push(...nodes); },
      prepend(...nodes) { this.children.unshift(...nodes); },
      replaceChildren(...nodes) { this.children = nodes; },
      setAttribute(name, value) { this.attributes[name] = String(value); },
      removeAttribute(name) { delete this.attributes[name]; },
      addEventListener(type, listener) { this.listeners[type] = listener; },
      focus() {}, contains: () => false,
    };
  };
  const nodes = { '#drawer': node(), '#scrim': node(), '#toast': node(), '#main': node(), '.shell': node(), '.review-bar': bar ? node() : null };
  globalThis.document = {
    activeElement: null,
    documentElement: { classList: { remove() {} } },
    createElement: node,
    querySelector: (selector) => nodes[selector] ?? null,
    querySelectorAll: () => [],
    addEventListener() {}, removeEventListener() {},
  };
  return nodes;
}

test('another project picked drops a map preview that is only previewed (panel.js)', async () => {
  fakePage();
  const net = stubFetch((url) => (url === '/api/changes/preview' ? { json: { ...change, state: 'previewed' } } : { json: {} }));
  try {
    state.project = 'p1';
    await previewOnMap(body, () => {});
    assert.deepEqual([mapPreview.phase, mapPreview.project], ['ready', 'p1']);
    // The same project keeps it.
    closeForProject();
    assert.equal(mapPreview.phase, 'ready');
    // Another project: it goes, and the server forgets it.
    state.project = 'p2';
    closeForProject();
    assert.deepEqual([mapPreview.phase, posts(net.asked)], ['idle', ['/api/changes/preview', '/api/changes/c1/cancel']]);
  } finally {
    net.done();
    delete globalThis.document;
  }
});

test('a drop while a review shows in Details ends that review first; one being written refuses it', async () => {
  fakePage();
  const net = stubFetch((url) => (url === '/api/changes/preview' ? { json: { ...change, state: 'previewed' } } : { json: {} }));
  try {
    const shown = { id: 'd1', state: 'previewed' };
    panelState.current = { type: 'review', change: shown };
    openPanel([]);
    // While its change is written, the drop asks for nothing and the review stays.
    busy.change = true;
    await previewOnMap(body, () => {});
    assert.deepEqual([posts(net.asked), isPanelOpen(), mapPreview.phase], [[], true, 'idle']);
    busy.change = false;
    // Only previewed: it is cancelled on the server and leaves, then the map's preview is asked.
    await previewOnMap(body, () => {});
    assert.deepEqual(posts(net.asked), ['/api/changes/d1/cancel', '/api/changes/preview']);
    assert.deepEqual([isPanelOpen(), shown.state, mapPreview.phase], [false, 'cancelled', 'ready']);
  } finally {
    net.done();
    panelState.current = null;
    delete globalThis.document;
  }
});

test('an Apply that ends while the bar is off the page says so in a toast with no check, then the preview goes', async () => {
  const nodes = fakePage(); // the person went to the List: no bar on the page
  // A stale end with the engine's own words, one that could not put everything back, then an
  // answer with no body whose change cannot be read back.
  const ends = [
    { status: 409, json: { ...change, state: 'stale', error: STALE_ERROR } },
    { status: 409, json: { ...change, state: 'restored', error: LOST_ERROR } },
    { status: 500, json: null },
  ];
  let applies = 0;
  const net = stubFetch((url) => {
    if (url === '/api/changes/preview') return { json: { ...change, state: 'previewed' } };
    if (url === '/api/changes/c1/apply') return ends[applies++];
    if (url === '/api/changes/c1') return { status: 500, json: null };
    return { json: {} };
  });
  const toast = () => nodes['#toast'].children.filter((c) => c.className !== 'timer').map((c) => [c.tag, c.textContent]);
  const logged = console.error;
  console.error = () => {}; // the answer with no body is logged; here it is expected
  const title = 'Move github into the Kitden gateway for all projects';
  try {
    await previewOnMap(body, () => {});
    await applyOnMap(() => {});
    // The bar's words: no path, and nothing that competes with "Try again".
    assert.deepEqual(toast(), [['span', `${title} · Settings changed since this preview. Nothing was changed.`]]);
    assert.equal(mapPreview.phase, 'idle');
    // Not everything put back, or not known: a way to Changes, where the engine's words are.
    await previewOnMap(body, () => {});
    await applyOnMap(() => {});
    assert.deepEqual(toast(), [
      ['span', `${title} · The change did not check out. Not everything was put back. Check Changes before trying again.`],
      ['button', 'Open Changes'],
    ]);
    await previewOnMap(body, () => {});
    await applyOnMap(() => {});
    assert.deepEqual(toast(), [
      ['span', `${title} · Could not confirm the result. Check Changes before trying again.`],
      ['button', 'Open Changes'],
    ]);
    assert.equal(mapPreview.phase, 'idle');
    assert.ok(!posts(net.asked).some((u) => u.endsWith('/cancel')));
  } finally {
    console.error = logged;
    hideToast();
    net.done();
    delete globalThis.document;
  }
});
