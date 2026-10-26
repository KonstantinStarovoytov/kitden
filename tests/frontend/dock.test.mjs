import assert from 'node:assert/strict';
import { test } from 'node:test';

// Reduced motion is switched per test (D() reads it at every call). Any other query is a wide window.
const motionQuery = { matches: true };
globalThis.matchMedia = (query) => (/reduced-motion/.test(query) ? motionQuery : { matches: false, addEventListener() {} });
delete globalThis.navigator;
const reduce = (flag) => { motionQuery.matches = flag; };

// A small tree of stand-in nodes: enough of the DOM for the bar, the toast and the side panel.
const textNode = (value) => ({ nodeType: 3, textContent: String(value), parent: null });
// How tall the bar is: its text, and a row of the list on top of that. A toast is shorter than a bar.
// While a size animation runs, the browser reports its animated height, not the natural one.
const running = (run) => !run.cancelled && Date.now() - run.startedAt < run.options.duration;
const rects = (node) => {
  const sizing = node.animations.findLast((run) => run.frames[0].height && running(run));
  return { width: 380, height: sizing ? parseFloat(sizing.frames[0].height) : node.classList.contains('toast') ? 40 : 60 + 50 * all(node).filter((n) => n.tag === 'li').length, bottom: 0 };
};
function fakeNode(tag) {
  const classes = new Set();
  let disabled = false;
  const node = {
    nodeType: 1, tag, parent: null, childNodes: [], attributes: {}, dataset: {}, listeners: {}, animations: [],
    style: { setProperty(name, value) { this[name] = String(value); }, removeProperty(name) { delete this[name]; } },
    // A button that is turned off while it has focus loses it (the browser's focus fixup).
    get disabled() { return disabled; },
    set disabled(value) { disabled = Boolean(value); if (disabled && globalThis.document.activeElement === node) globalThis.document.activeElement = null; },
    get offsetHeight() { return rects(node).height; },
    // A node points to its parent and children: a failed assertion prints only its name.
    [Symbol.for('nodejs.util.inspect.custom')]: () => `<${tag}>`,
    get className() { return [...classes].join(' '); },
    set className(value) { classes.clear(); String(value).split(/\s+/).filter(Boolean).forEach((name) => classes.add(name)); },
    classList: {
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      toggle: (name, on = !classes.has(name)) => { if (on) classes.add(name); else classes.delete(name); return on; },
      contains: (name) => classes.has(name),
    },
    get textContent() { return node.childNodes.map((child) => child.textContent).join(''); },
    set textContent(value) { node.replaceChildren(...(String(value) === '' ? [] : [String(value)])); },
    get children() { return node.childNodes.filter((child) => child.nodeType === 1); },
    get firstElementChild() { return node.children[0] || null; },
    get lastElementChild() { return node.children.at(-1) || null; },
    get isConnected() { let up = node; while (up.parent) up = up.parent; return up.root === true; },
    adopt(items) {
      return items.map((item) => (typeof item === 'string' ? textNode(item) : item)).map((child) => {
        if (child.parent) child.parent.childNodes = child.parent.childNodes.filter((other) => other !== child);
        child.parent = node;
        return child;
      });
    },
    append(...items) { node.childNodes.push(...node.adopt(items)); },
    prepend(...items) { node.childNodes.unshift(...node.adopt(items)); },
    // A node that leaves the page takes focus with it: the page is left with none.
    replaceChildren(...items) { for (const child of node.childNodes) { leave(child); child.parent = null; } node.childNodes = []; node.childNodes = node.adopt(items); },
    remove() { leave(node); if (node.parent) node.parent.childNodes = node.parent.childNodes.filter((child) => child !== node); node.parent = null; },
    replaceWith(other) {
      if (!node.parent) return;
      const at = node.parent.childNodes.indexOf(node);
      other.parent = node.parent;
      node.parent.childNodes[at] = other;
      node.parent = null;
    },
    contains(other) { return other === node || node.children.some((child) => child.contains(other)); },
    setAttribute(name, value) { node.attributes[name] = String(value); if (name === 'class') node.className = value; },
    getAttribute: (name) => (name in node.attributes ? node.attributes[name] : null),
    removeAttribute(name) { delete node.attributes[name]; },
    addEventListener(type, listener) { (node.listeners[type] ||= []).push(listener); },
    // A press: every listener runs; the promise is the first one's work.
    click() { const runs = (node.listeners.click || []).map((listener) => listener({ preventDefault() {} })); return Promise.all(runs); },
    // How it was last given focus: `focusedWith.preventScroll` keeps the page where it is.
    focus(options) { globalThis.document.activeElement = node; node.focusedWith = options; },
    animate(frames, options) {
      const run = { frames, options, startedAt: Date.now(), cancelled: false };
      run.handle = { finished: Promise.resolve(), cancel() { run.cancelled = true; } };
      node.animations.push(run);
      return run.handle;
    },
    getAnimations: () => node.animations.filter(running).map((run) => run.handle),
    getBoundingClientRect: () => rects(node),
    querySelector: (selector) => (selector === ':scope > summary' ? node.children.find((child) => child.tag === 'summary') || null : null),
    querySelectorAll: (selector) => (selector === '[data-focus]' ? all(node).filter((child) => child !== node && child.dataset.focus) : []),
  };
  return node;
}
const all = (node) => [node, ...node.children.flatMap(all)];
const leave = (node) => { if (node.nodeType === 1 && node.contains(globalThis.document.activeElement)) globalThis.document.activeElement = null; };
const named = (root, name) => all(root).filter((n) => n.classList.contains(name));
const tagged = (root, tag) => all(root).filter((n) => n.tag === tag);
const labelOf = (node) => node.attributes['aria-label'] || node.textContent;
const buttonsOf = (root) => tagged(root, 'button');
const button = (root, label) => buttonsOf(root).find((node) => labelOf(node) === label || node.textContent === label);

const pages = {};
for (const id of ['#dock', '#drawer', '#scrim', '#said', '#main', '.shell']) {
  pages[id] = fakeNode('div');
  pages[id].root = true;
}
// What a screen reader hears: every text the page's quiet live region (#said) is given, in order.
const saidLog = [];
Object.defineProperty(pages['#said'], 'textContent', { get: () => saidLog.at(-1) ?? '', set: (value) => { saidLog.push(String(value)); } });
const heard = () => saidLog.filter(Boolean);
// The Gateway shows its map (not its List): the map's box is on the page.
const showMap = (on) => { if (on) pages['#main .map'] = fakeNode('div'); else delete pages['#main .map']; };
const listeners = new Map();
// The page's root holds the room kept for the dock (--dock-room).
const rootStyle = { setProperty(name, value) { this[name] = String(value); }, removeProperty(name) { delete this[name]; } };
const room = () => rootStyle['--dock-room'];
globalThis.document = {
  activeElement: null,
  hidden: false,
  documentElement: { classList: { add() {}, remove() {} }, style: rootStyle },
  createElement: fakeNode,
  createElementNS: (namespace, tag) => fakeNode(tag),
  getElementById: (id) => (id === 'content' ? { scrollTop: 0 } : null),
  querySelector: (selector) => pages[selector] ?? null,
  querySelectorAll: () => [],
  addEventListener(type, listener) { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(listener); },
  removeEventListener(type, listener) { if (listeners.has(type)) listeners.get(type).delete(listener); },
  fire(type, detail) { for (const listener of [...(listeners.get(type) || [])]) listener({ detail }); },
};

// A stand-in server, as in tray.test.mjs: each address answers from its own queue.
const calls = [];
const replies = new Map();
globalThis.fetch = (url, init = {}) => {
  calls.push({ url, method: init.method || 'GET', body: init.body ? JSON.parse(init.body) : null });
  const waiting = replies.get(url) || [];
  const next = waiting.length ? waiting.shift() : { status: 200, json: {} };
  const reply = typeof next === 'function' ? next(calls.at(-1).body) : next;
  return Promise.resolve(reply).then((made) => ({ ok: made.status < 400, status: made.status, json: async () => made.json }));
};
const queue = (url, ...items) => replies.set(url, [...(replies.get(url) || []), ...items]);
const posted = () => calls.filter((call) => call.method === 'POST').map((call) => call.url);

const dockPath = '../../src/kitden/web/static/js/dock.js';
const { appliedToast, barWords, drawTray, initDock, outcomeLine, rowWords, setCancelFocus, writingLine } = await import(dockPath);
const { changeWords, detailsAgain, undoChange } = await import('../../src/kitden/web/static/js/review.js');
const { addToTray, cancelTray, endApplied, takeOut, tray, tryAgain } = await import('../../src/kitden/web/static/js/tray.js');
const { busy, render, setBusy, setRenderer, state } = await import('../../src/kitden/web/static/js/store.js');
const { closePanel, hideToast, isPanelOpen, keepFrom, openPanel, panelState, toast, toolsSection } = await import('../../src/kitden/web/static/js/panel.js');
initDock();

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function quietly(fn) {
  const log = console.error;
  console.error = () => {};
  try { return await fn(); } finally { console.error = log; }
}

const PREVIEW = '/api/batch/preview';
const add = (name) => ({ action: 'mcp.add', targets: [{ client: 'codex' }], params: { item: name } });
const target = { scope: 'all', project: null, others_unchanged: false };
// The server's answer to a batch: one step per request, each row naming its step.
const batch = (id, requests) => ({
  status: 200,
  json: {
    id, action: requests.length === 1 ? requests[0].kind : 'batch', state: 'previewed', error: null, target,
    steps: requests.map((request) => ({ client: 'codex', name: request.params.item, path: '/Users/me/.codex/config.toml', diff: '--- before\n+++ after\n+x' })),
    undo_note: null,
    rows: requests.map((request, index) => ({
      id: request.id, kind: request.kind, title: request.title, detail: request.detail, project: null, steps: [index],
      target, after: [{ client: 'codex', state: 'on', word: 'Added' }], undo_note: null,
    })),
  },
});
const previewed = (id) => (sent) => batch(id, sent.requests);
function slowPreview(id) {
  let release;
  let sent = null;
  const held = new Promise((resolve) => { release = resolve; });
  return { reply: (body) => { sent = body; return held; }, release: () => release(batch(id, sent.requests)) };
}
function slow() {
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  return { reply: () => held, release };
}
const refusal = (detail) => ({ status: 422, json: { detail, row: null } });
const verified = (id) => ({ status: 200, json: { id, state: 'verified', steps: [] } });
const stale = (id) => ({ status: 409, json: { id, state: 'stale', error: 'Settings changed.' } });

const bar = () => pages['#dock'].children.find((child) => child.classList.contains('bar')) || null;
const toastNode = () => pages['#dock'].children.find((child) => child.classList.contains('toast')) || null;
const toastParts = () => toastNode().children.filter((child) => child.className !== 'life').map((child) => [child.tag, child.textContent]);

// An empty tray, a quiet server and no motion in every test; a test that looks at motion turns it on.
async function fresh() {
  reduce(true);
  await cancelTray();
  endApplied();
  await settle();
  pages['#dock'].replaceChildren();
  pages['#drawer'].replaceChildren();
  pages['#drawer'].classList.remove('open');
  rootStyle.removeProperty('--dock-room');
  panelState.current = null;
  calls.length = 0;
  replies.clear();
  state.project = '';
  state.view = 'overview';
  showMap(false);
  globalThis.document.activeElement = null;
  hideToast();
  await settle();
  saidLog.length = 0;
}

const row = (title, detail = '') => ({ title, detail, part: {} });
const trayOf = (rows, fields = {}) => ({ rows, change: null, phase: 'ready', refused: null, failure: null, done: 0, total: 0, stale: false, ...fields });
const WORDS = { applyWaits: false, retry: false, changes: false };

test('barWords says one change by its title', () => {
  assert.deepEqual(barWords(trayOf([row('Add github to Codex', 'Codex: Added.')])), {
    head: 'Add github to Codex', line: 'Codex: Added.', cancel: 'Cancel', apply: 'Apply', ...WORDS,
  });
});

test('barWords counts many changes', () => {
  const three = trayOf([row('a'), row('b'), row('c')]);
  assert.deepEqual(barWords(three), {
    head: '3 changes in preview', line: 'Nothing is written until you Apply.', cancel: 'Cancel all', apply: 'Apply all', ...WORDS,
  });
  // Only on the Gateway map can a change be clicked to take it out.
  assert.equal(barWords(three, { onMap: true }).line, 'Nothing is written until you Apply. Click one on the map to take it out.');
});

test('barWords waits while a preview is asked', () => {
  const asking = barWords(trayOf([row('Add github', 'Codex: Added.')], { phase: 'asking' }));
  assert.deepEqual(asking, { head: 'Add github', line: 'Codex: Added.', cancel: 'Cancel', apply: 'Apply', applyWaits: true, retry: false, changes: false });
  assert.equal(barWords(trayOf([row('a'), row('b')], { phase: 'asking' })).applyWaits, true);
});

test('barWords counts the steps while Apply runs', () => {
  const change = { steps: [{ client: 'codex' }, { client: 'claude_code' }] };
  const running = trayOf([row('a'), row('b')], { phase: 'applying', change, done: 2, total: 5 });
  assert.deepEqual(barWords(running), {
    head: '2 changes in preview', line: 'Writing the settings of Codex and Claude Code. A backup is kept.', cancel: 'Cancel all',
    apply: 'Applying 2 of 5', applyWaits: true, retry: false, changes: false,
  });
  // Before the first step ends there is no count to say.
  assert.equal(barWords({ ...running, done: 0, total: 0 }).apply, 'Applying…');
  const one = barWords(trayOf([row('a')], { phase: 'applying', change: { steps: [{ client: 'codex' }] } }));
  assert.equal(one.line, "Writing Codex's settings. A backup is kept.");
  // Once applied the button says so, and takes no more presses.
  const applied = trayOf([row('a'), row('b')], { phase: 'applied', change });
  assert.deepEqual([barWords(applied).apply, barWords(applied).applyWaits], ['All applied', true]);
  assert.equal(barWords({ ...applied, rows: [row('a')] }).apply, 'Applied');
});

test('barWords says Nothing was changed only when true', () => {
  const failed = (failure, rows = [row('a')]) => barWords(trayOf(rows, { phase: 'failed', failure }));
  const STALE = 'Settings changed since this preview.';
  assert.deepEqual(failed({ state: 'stale', error: 'Settings changed.' }), {
    head: 'Nothing was changed', line: STALE, cancel: 'Cancel', apply: 'Try again', applyWaits: false, retry: true, changes: false,
  });
  // The engine put every file back: its words end with the sentence that says so.
  const back = failed({ state: 'restored', error: 'It did not check out. The original settings were restored.' }, [row('a'), row('b')]);
  assert.deepEqual(back, {
    head: 'Nothing was changed', line: 'The change did not check out. Kitden put the files back.', cancel: 'Cancel all',
    apply: 'Try again', applyWaits: false, retry: true, changes: false,
  });
  // Not every file went back: no Try again, a way to Changes.
  const partly = failed({ state: 'restored', error: 'Could not restore a file.' });
  assert.deepEqual(partly, {
    head: 'Not everything was put back', line: 'Check Changes before trying again.', cancel: 'Cancel', apply: null,
    applyWaits: false, retry: false, changes: true,
  });
  assert.equal(failed({ state: 'restored', error: null }).head, 'Not everything was put back');
  // The end is not known, or is one that says nothing about the files.
  for (const failure of [{ state: null, error: null }, { state: 'cancelled', error: null }]) {
    assert.deepEqual(failed(failure), {
      head: 'Could not confirm the result', line: 'Check Changes before trying again.', cancel: 'Cancel', apply: null,
      applyWaits: false, retry: false, changes: true,
    });
  }
});

test("the bar never shows the engine's own words: no path, no command", () => {
  // What the engine says when a change stops: paths, commands and Keychain names. They stay in
  // Details and on Changes.
  const ends = [
    { state: 'stale', error: '/Users/me/.codex/config.toml changed since preview; review the change again' },
    { state: 'restored', error: '`claude mcp add` failed in /Users/me/.claude.json. The original settings were restored.' },
    { state: 'restored', error: '`claude mcp add` failed. github/TOKEN in your Keychain keeps the new value.' },
    { state: 'cancelled', error: '/Users/me/.claude.json' }, { state: null, error: null },
  ];
  for (const failure of ends) {
    for (const rows of [[row('Move github into the Kitden gateway')], [row('a'), row('b')]]) {
      const words = barWords(trayOf(rows, { phase: 'failed', failure }));
      for (const text of Object.values(words).filter((value) => typeof value === 'string')) {
        assert.ok(!/[/~`]/.test(text) && !text.includes('review the change again'), text);
      }
    }
  }
});

test('a reason that names a file shows only its name in the bar', () => {
  const reason = '/Users/me/.cursor/mcp.json has a hard link; so has ~/.codex/config.toml.';
  const shown = 'mcp.json has a hard link; so has config.toml.';
  assert.equal(barWords(trayOf([row('a')], { refused: { reason } })).line, shown);
  assert.equal(barWords(trayOf([], { phase: 'idle', refused: { reason } })).line, shown);
  assert.equal(barWords(trayOf([row('a'), row('b')], { phase: 'failed', refused: { reason } })).line, shown);
  // Words that only look like a path stay as they are.
  const plain = 'Turn a tool on and/or off (read/write) in "/" here.';
  assert.equal(barWords(trayOf([row('a')], { refused: { reason: plain } })).line, plain);
});

test('barWords shows a refusal with no rows', () => {
  assert.deepEqual(barWords(trayOf([], { phase: 'idle', refused: { reason: 'Nothing to change.' } })), {
    head: 'Could not prepare this change', line: 'Nothing to change.', cancel: 'Close', apply: null, applyWaits: false, retry: false, changes: false,
  });
});

test('barWords keeps the rows of a refused add and of a refused preview', () => {
  // An add the server refused: the tray stands, and the reason takes the line.
  const refusedAdd = barWords(trayOf([row('Add github', 'Codex: Added.')], { refused: { reason: 'Choose a server in the Kitden gateway.' } }));
  assert.deepEqual(refusedAdd, {
    head: 'Add github', line: 'Choose a server in the Kitden gateway.', cancel: 'Cancel', apply: 'Apply', ...WORDS,
  });
  // The rows asked again and the server refused: they stay with no change, and Try again asks afresh.
  const refusedPreview = barWords(trayOf([row('a'), row('b')], { phase: 'failed', refused: { reason: 'Apply the preview first.' } }));
  assert.deepEqual(refusedPreview, {
    head: 'Could not prepare the preview', line: 'Apply the preview first.', cancel: 'Cancel all', apply: 'Try again',
    applyWaits: false, retry: true, changes: false,
  });
});

test('barWords keeps the failure when an add is refused after a failed Apply, and adds the reason', () => {
  const rows = [row('a'), row('b')];
  const refused = { reason: '/Users/me/.cursor/mcp.json has a hard link.' };
  const stale = barWords(trayOf(rows, { phase: 'failed', failure: { state: 'stale', error: 'Settings changed.' }, refused }));
  assert.deepEqual([stale.head, stale.line, stale.apply, stale.retry], ['Nothing was changed', 'Settings changed since this preview. mcp.json has a hard link.', 'Try again', true]);
  const lost = barWords(trayOf(rows, { phase: 'failed', failure: { state: null, error: null }, refused }));
  assert.deepEqual([lost.head, lost.line, lost.changes, lost.apply], ['Could not confirm the result', 'Check Changes before trying again. mcp.json has a hard link.', true, null]);
  // A refused preview with no failure behind it is as before.
  assert.deepEqual(barWords(trayOf(rows, { phase: 'failed', refused })).head, 'Could not prepare the preview');
});

test('barWords says the preview went stale', () => {
  const words = barWords(trayOf([row('a'), row('b')], { stale: true }));
  assert.deepEqual([words.line, words.apply, words.retry, words.applyWaits], ['Settings changed since this preview.', 'Preview again', true, false]);
  // A preview that is on its way is not stale.
  assert.equal(barWords(trayOf([row('a')], { stale: true, phase: 'asking' })).apply, 'Apply');
});

const remove = { action: 'plugin.disable', steps: [{ client: 'claude_code', name: 'github@official' }], target: { scope: 'all' } };

test('rowWords is the title of the change and its outcome, else the note', () => {
  const after = [{ client: 'claude_code', state: 'off', word: 'Off' }];
  assert.deepEqual(rowWords({ ...remove, after }, {}, 'A note.'), { title: changeWords(remove, {}).title, detail: 'Claude Code: Off.' });
  assert.equal(rowWords({ ...remove, after: [] }, {}, 'A note.').detail, 'A note.');
  assert.equal(rowWords({ ...remove, after: [] }, {}, null).detail, '');
});

test("the outcome line groups the After chips by word, else the first note's first sentence", () => {
  const after = [{ client: 'claude_code', state: 'gw', word: 'Via gateway' }, { client: 'codex', state: 'gw', word: 'Via gateway' }, { client: 'cursor', state: 'off', word: 'Removed' }];
  assert.equal(outcomeLine({ after }), 'Claude Code and Codex: Via gateway. Cursor: Removed.');
  assert.equal(outcomeLine({ after: [{ note: 'No client uses the Kitden gateway yet. Set one up first.' }] }), 'No client uses the Kitden gateway yet.');
  assert.equal(outcomeLine({ after: [] }), '');
  assert.equal(writingLine([{ client: 'claude_code' }]), "Writing Claude Code's settings. A backup is kept.");
  assert.equal(writingLine([{ client: 'kitden' }]), "Writing the Kitden gateway's settings. A backup is kept.");
  assert.equal(writingLine([{ client: 'kitden' }, { client: 'claude_code' }]), 'Writing the settings of the Kitden gateway and Claude Code. A backup is kept.');
});

test("appliedToast says one change's own words with Undo", async () => {
  await fresh();
  const one = { part: remove, body: {}, key: 'k1' };
  appliedToast({ change: { id: 'c1' }, rows: [one] });
  try {
    assert.deepEqual(toastParts(), [
      ['span', ''], ['span', changeWords(remove, {}).done], ['button', 'Undo'],
    ]);
    assert.match(toastParts()[1][1], /^Turned off github in Claude Code/);
  } finally {
    hideToast();
  }
});

test('appliedToast says Applied 3 changes with Undo all, and Undo all undoes the combined change', async () => {
  await fresh();
  const rows = ['k1', 'k2', 'k3'].map((key) => ({ part: remove, body: {}, key }));
  queue('/api/changes/c9/undo', { status: 200, json: { id: 'c9', state: 'undone', steps: [] } });
  appliedToast({ change: { id: 'c9' }, rows });
  try {
    assert.deepEqual(toastParts(), [['span', ''], ['span', 'Applied 3 changes'], ['button', 'Undo all']]);
    await quietly(async () => {
      button(toastNode(), 'Undo all').click();
      await sleep(20);
    });
    assert.deepEqual(posted().filter((url) => url.endsWith('/undo')), ['/api/changes/c9/undo']);
    assert.equal(busy.change, false);
  } finally {
    hideToast();
  }
});

test('a tray change that draws a bar replaces a toast at once', async () => {
  await fresh();
  toast('Undone. The previous settings are back.', null, { ok: true });
  const shown = toastNode();
  assert.equal(room(), '86px'); // the toast's 40 px and the dock's 46 px offset
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  assert.equal(shown.isConnected, false);
  assert.deepEqual(pages['#dock'].children, [bar()]);
  assert.equal(toastNode(), null);
  assert.equal(room(), '106px');
});

test('a toast takes the bar\'s place while the tray keeps its rows, and the bar comes back after it', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  const first = bar();
  assert.equal(room(), '106px');
  toast('Could not find this item in the Library.');
  assert.equal(first.isConnected, false);
  assert.deepEqual(pages['#dock'].children, [toastNode()]);
  assert.equal(tray.rows.length, 1);
  assert.equal(room(), '86px', 'the room follows the toast');
  // The toast has gone: the bar is drawn again from the tray, with its Apply.
  hideToast();
  assert.equal(toastNode(), null);
  assert.ok(button(bar(), 'Apply'), 'the bar is back');
  assert.equal(tray.rows.length, 1);
  assert.equal(room(), '106px', 'the room follows the bar');
  // A toast over the bar and then a tray change: the new bar replaces the toast, and has both rows.
  toast('Could not find this item in the Library.');
  await addToTray(add('neon'));
  assert.equal(toastNode(), null);
  assert.ok(button(bar(), 'Apply all'), 'the bar has both rows');
  assert.equal(bar().classList.contains('many'), true);
  hideToast();
  assert.equal(bar().classList.contains('many'), true);
});

test('drawTray draws one row with Show changes and Apply', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  const section = bar();
  const title = 'Add github to Codex for all projects';
  assert.deepEqual([section.tag, section.className, section.attributes.role, section.attributes['aria-label']], ['section', 'bar tray', 'region', title]);
  const [words, acts] = section.children;
  assert.deepEqual(words.children.map((node) => [node.tag, node.textContent]), [['b', title], ['small', 'Codex: Added.'], ['button', 'Show changes']]);
  assert.equal(words.children[1].attributes.role, 'status'); // read out when it changes
  assert.deepEqual(acts.children.map((node) => [node.tag, node.className, node.textContent]), [
    ['button', 'btn', 'Cancel'], ['button', 'btn primary apply', 'Apply'],
  ]);
  const apply = acts.children[1];
  assert.deepEqual(apply.children.map((node) => [node.tag, node.className]), [['span', 'lbl'], ['svg', 'ic'], ['i', 'meter']]);
  assert.equal(apply.children[1].dataset.icon, 'arrow-right');
  assert.equal(apply.attributes['aria-disabled'], undefined);
  // Focus stays where it was.
  assert.ok(globalThis.document.activeElement === null, 'focus is not where it should be');
  // Cancel asks the server to forget the preview, and the bar goes.
  await acts.children[0].click();
  assert.equal(bar(), null);
  assert.deepEqual(posted(), [PREVIEW, '/api/changes/c1/cancel']);
});

test('drawTray draws a list with a take-out button per row', async () => {
  await fresh();
  state.view = 'gateway';
  showMap(true);
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  const section = bar();
  assert.deepEqual([section.className, section.attributes['aria-label']], ['bar tray many', '2 changes in preview']);
  const [head, list, acts] = section.children;
  assert.deepEqual([head.className, list.tag, list.className, acts.className], ['tray-head', 'ul', 'tray-list', 'acts']);
  const [count, line] = head.children;
  assert.deepEqual([count.tag, count.textContent, named(count, 'num').length], ['b', '2 changes in preview', 1]);
  assert.deepEqual([line.attributes.role, line.textContent], ['status', 'Nothing is written until you Apply. Click one on the map to take it out.']);
  const items = list.children;
  assert.deepEqual(items.map((li) => li.dataset.key), tray.rows.map((r) => r.key));
  const first = items[0];
  assert.deepEqual(first.children.map((node) => node.className), ['ti', 'tt', 'ib', 'ts', 'x']);
  assert.equal(first.children[0].children[0].dataset.icon, 'plus');
  assert.deepEqual(first.children[1].children.map((node) => [node.tag, node.textContent]), [['b', 'Add github to Codex for all projects'], ['small', 'Codex: Added.']]);
  assert.deepEqual(items.map((li) => labelOf(li.children[2])), ['Show changes: Add github to Codex for all projects', 'Show changes: Add neon to Codex for all projects']);
  assert.equal(first.children[2].children[0].dataset.icon, 'file-text');
  assert.deepEqual(items.map((li) => labelOf(li.children[4])), ['Take it out of the preview', 'Take it out of the preview']);
  assert.equal(first.children[4].children[0].dataset.icon, 'x');
  assert.deepEqual(acts.children.map((node) => node.textContent), ['Cancel all', 'Apply all']);
  // Off the Gateway the line does not send anyone to a map.
  state.view = 'library';
  drawTray(tray);
  assert.equal(line.textContent, 'Nothing is written until you Apply.');
  // × takes one out; the rest are previewed again, and one change left is drawn as one.
  queue(PREVIEW, previewed('c3'));
  await items[0].children[4].click();
  assert.equal(bar().className, 'bar tray');
  assert.equal(bar().attributes['aria-label'], 'Add neon to Codex for all projects');
  assert.equal(button(bar(), 'Apply').attributes['aria-disabled'], undefined);
  assert.equal(calls.filter((call) => call.url === '/api/changes/c2/cancel').length, 1);
});

test('drawTray disables Cancel and × while Apply runs, then shows Applied', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  const writing = slow();
  queue('/api/changes/c2/apply', writing.reply);
  const second = tray.rows[1];
  const section = bar();
  const running = button(section, 'Apply all').click();
  const apply = button(section, 'Applying…');
  assert.ok(apply, 'the button counts while it works');
  assert.equal(apply.attributes['aria-disabled'], 'true');
  assert.equal(button(section, 'Cancel all').disabled, true);
  assert.deepEqual(named(section, 'x').map((node) => node.disabled), [true, true]);
  assert.equal(named(section, 'tray-head')[0].children[1].textContent, "Writing Codex's settings. A backup is kept.");
  // The icon is the spinner; the first row spins at once, the second waits.
  assert.deepEqual([apply.children[1].dataset.icon, apply.children[1].className], ['rotate-cw', 'ic spin']);
  const spinners = () => named(section, 'ts').map((node) => node.children.map((icon) => icon.dataset.icon));
  assert.deepEqual(spinners(), [['rotate-cw'], []]);
  // A finished step: the count says it, the meter fills that share, and its row spins.
  document.fire('kitden:progress', { id: 'c2', done: 2, total: 5, row: second.id });
  assert.equal(apply.children[0].textContent, 'Applying 2 of 5');
  assert.equal(apply.children[2].style.transform, 'scaleX(0.4)');
  assert.deepEqual(spinners(), [['rotate-cw'], ['rotate-cw']]);
  // Verified: the button turns green with a check, and every row checks.
  writing.release(verified('c2'));
  await settle();
  assert.deepEqual([apply.className, apply.children[0].textContent, apply.children[1].dataset.icon], ['btn apply ok', 'All applied', 'check']);
  assert.equal(apply.attributes['aria-disabled'], 'true');
  assert.deepEqual(spinners(), [['check'], ['check']]);
  await running;
  // The page took the result in: the tray is empty, the bar is gone, and the toast offers Undo all.
  assert.deepEqual([tray.rows.length, tray.phase, bar()], [0, 'idle', null]);
  assert.deepEqual(toastParts().map(([, text]) => text), ['', 'Applied 2 changes', 'Undo all']);
  assert.equal(posted().filter((url) => url === '/api/changes/c2/apply').length, 1);
  hideToast();
});

// motion-spec M4 step 3: the step number rolls (rollTo) from the second step on.
test('the step number of "Applying 2 of 5" rolls from step 2; under reduced motion it changes at once', async () => {
  for (const calm of [false, true]) {
    await fresh();
    queue(PREVIEW, previewed('c1'), previewed('c2'));
    await addToTray(add('github'));
    await addToTray(add('neon'));
    reduce(calm);
    const writing = slow();
    queue('/api/changes/c2/apply', writing.reply);
    const running = button(bar(), 'Apply all').click();
    const apply = button(bar(), 'Applying…');
    document.fire('kitden:progress', { id: 'c2', done: 1, total: 5, row: tray.rows[0].id });
    const label = apply.children[0];
    const num = label.children[0];
    assert.deepEqual([label.textContent, num.className], ['Applying 1 of 5', 'num roll']);
    // The first number shows as it is.
    assert.deepEqual(num.children.map((n) => [n.textContent, n.animations.length]), [['1', 0]]);
    document.fire('kitden:progress', { id: 'c2', done: 2, total: 5, row: tray.rows[1].id });
    assert.equal(label.children[0], num);
    if (calm) assert.ok(num.children.every((n) => n.animations.length === 0));
    else {
      const [old, next] = num.children;
      assert.deepEqual([old.textContent, next.textContent], ['1', '2']);
      assert.deepEqual([old.animations[0].options.duration, next.animations[0].options.duration, next.animations[0].options.delay], [140, 200, 140]);
    }
    await sleep(160);
    assert.equal(label.textContent, 'Applying 2 of 5');
    writing.release(verified('c2'));
    await running;
    hideToast();
  }
});

test('drawTray waits while a preview is asked: Apply takes no press', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  const late = slowPreview('c2');
  queue(PREVIEW, late.reply);
  const adding = addToTray(add('neon'));
  // The new change has no words yet, so the bar still shows the one it has.
  assert.equal(bar().className, 'bar tray');
  const apply = button(bar(), 'Apply');
  assert.equal(apply.attributes['aria-disabled'], 'true');
  await apply.click();
  assert.equal(posted().some((url) => url.endsWith('/apply')), false);
  assert.equal(tray.phase, 'asking');
  late.release();
  await adding;
  assert.equal(bar().className, 'bar tray many');
  assert.equal(button(bar(), 'Apply all').attributes['aria-disabled'], undefined);
});

test('under reduced motion the bar and rows end at opacity 1', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'), previewed('c3'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  await addToTray(add('slack'));
  queue(PREVIEW, previewed('c4'));
  await button(bar(), 'Take it out of the preview').click();
  // Nothing is left animating, so nothing can stay at opacity 0.
  const animated = all(pages['#dock']).flatMap((node) => node.animations);
  assert.deepEqual(animated, []);
  assert.equal(named(bar(), 'tray-list')[0].children.length, 2);
  // The count changes at once (the old number is dropped by time), and the bar is gone at once.
  await settle();
  assert.equal(named(bar(), 'num')[0].children.length, 1);
  assert.equal(named(bar(), 'num')[0].textContent, '2');
  const section = bar();
  await button(section, 'Cancel all').click();
  assert.deepEqual([bar(), section.isConnected, section.animations], [null, false, []]);
});

test('with motion the bar, its size and its rows move as the mockup says', async () => {
  await fresh();
  reduce(false);
  queue(PREVIEW, previewed('c1'), previewed('c2'), previewed('c3'));
  await addToTray(add('github'));
  const section = bar();
  const enter = [{ opacity: 0, transform: 'translateY(18px) scale(.97)' }, { opacity: 1, transform: 'none' }];
  const CALM = 'cubic-bezier(.2,.8,.2,1)';
  assert.deepEqual(section.animations.map(({ frames, options }) => [frames, options.duration, options.delay, options.easing]), [[enter, 220, 0, CALM]]);
  // Two changes: the same bar is rebuilt and grows from its old size to its new one; both rows enter.
  await addToTray(add('neon'));
  assert.ok(bar() === section, 'the same bar');
  const [, grow, ...rest] = section.animations;
  assert.deepEqual([grow.frames, grow.options.duration, grow.options.easing], [[{ height: '60px', width: '380px' }, { height: '160px', width: '380px' }], 200, CALM]);
  assert.deepEqual(rest, []);
  const rowEnter = [{ opacity: 0, transform: 'translateY(10px) scale(.98)' }, { opacity: 1, transform: 'none' }];
  const items = named(section, 'tray-list')[0].children;
  for (const li of items) {
    assert.deepEqual(li.animations.map(({ frames, options }) => [frames, options.duration, options.delay, options.easing]), [[rowEnter, 200, 80, CALM]]);
  }
  // A third: only the new row enters, and the number rolls.
  await addToTray(add('slack'));
  const list = named(section, 'tray-list')[0].children;
  assert.deepEqual(list.map((li) => li.animations.length), [1, 1, 1]);
  const count = named(section, 'num')[0];
  assert.deepEqual(count.children.map((node) => node.textContent), ['2', '3']);
  assert.equal(count.children[0].animations.length, 1); // the old one leaves
  assert.equal(count.children[1].animations.length, 1); // the new one comes in
  // × slides its row out to the right, 180 ms ease-in; the row is removed, and the bar is previewed again.
  queue(PREVIEW, previewed('c4'));
  const out = list[0];
  const leaving = button(out, 'Take it out of the preview').click();
  assert.deepEqual(out.animations.at(-1).frames, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateX(18px)' }]);
  assert.deepEqual([out.animations.at(-1).options.duration, out.animations.at(-1).options.easing, out.animations.at(-1).options.fill], [180, 'ease-in', 'forwards']);
  await leaving;
  assert.equal(out.isConnected, true); // it is still sliding
  await sleep(220);
  assert.equal(out.isConnected, false);
  assert.equal(named(section, 'tray-list')[0].children.length, 2);
  await sleep(160);
  // Cancel all: the bar goes down 10 px in 160 ms ease-in and is removed by time.
  await button(section, 'Cancel all').click();
  assert.deepEqual(section.animations.at(-1).frames, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(10px)' }]);
  assert.deepEqual([section.animations.at(-1).options.duration, section.animations.at(-1).options.easing], [160, 'ease-in']);
  assert.equal(section.isConnected, true); // on its way out, removed by time
  await sleep(200);
  assert.equal(section.isConnected, false);
  assert.equal(bar(), null);
});

test('a toast that comes while a row slides out stays when the row has gone', async () => {
  await fresh();
  reduce(false);
  queue(PREVIEW, previewed('c1'), previewed('c2'), previewed('c3'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  await addToTray(add('slack'));
  const section = bar();
  queue(PREVIEW, previewed('c4'));
  const leaving = button(named(section, 'tray-list')[0].children[0], 'Take it out of the preview').click();
  await leaving;
  // The toast takes the dock while the row is still on its way out.
  toast('Could not find this item in the Library.');
  const note = toastNode();
  assert.ok(note);
  await sleep(260);
  assert.ok(toastNode() === note, 'the toast stays');
  assert.equal(note.isConnected, true);
  assert.equal(bar(), null);
  // When the toast has gone, the bar comes back with the rows that are left.
  hideToast({ now: true });
  drawTray();
  assert.equal(named(bar(), 'tray-list')[0].children.length, 2);
  reduce(true);
});

test('a failed Apply stays in the bar, shakes it and puts focus on Try again', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  reduce(false);
  queue('/api/changes/c2/apply', stale('c2'));
  const section = bar();
  await button(section, 'Apply all').click();
  assert.equal(section.className, 'bar tray many err');
  assert.equal(section.attributes['aria-label'], 'Nothing was changed');
  const [head] = section.children;
  assert.deepEqual(head.children.map((node) => node.textContent), ['Nothing was changed', 'Settings changed since this preview.']);
  assert.deepEqual(named(section, 'acts')[0].children.map((node) => node.textContent), ['Cancel all', 'Try again']);
  // The rows stay, each with a ×, and none is marked.
  assert.deepEqual(named(section, 'x').map((node) => node.disabled), [false, false]);
  assert.deepEqual(named(section, 'ts').map((node) => node.children.length), [0, 0]);
  assert.ok(globalThis.document.activeElement === button(section, 'Try again'), 'focus is not where it should be');
  const shaking = section.animations.at(-1);
  assert.deepEqual(shaking.frames.map((frame) => frame.transform), ['translateX(0)', 'translateX(-7px)', 'translateX(6px)', 'translateX(-3px)', 'translateX(0)']);
  assert.equal(shaking.options.duration, 380);
  // Try again asks for a new preview of the same rows; the person presses Apply again.
  queue(PREVIEW, previewed('c3'));
  await button(section, 'Try again').click();
  assert.equal(section.className, 'bar tray many');
  assert.equal(button(section, 'Apply all').attributes['aria-disabled'], undefined);
  assert.equal(section.attributes['aria-label'], '2 changes in preview');
});

test('an end that is not known leaves Open Changes and no Try again', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  queue('/api/changes/c1/apply', { status: 422, json: { detail: 'Not now.' } });
  await button(bar(), 'Apply').click();
  const section = bar();
  assert.equal(section.className, 'bar tray err');
  assert.deepEqual(section.children[0].children.map((node) => node.textContent).slice(0, 2), ['Could not confirm the result', 'Check Changes before trying again.']);
  assert.deepEqual(named(section, 'acts')[0].children.map((node) => node.textContent), ['Cancel', 'Open Changes']);
  assert.ok(globalThis.document.activeElement === button(section, 'Open Changes'), 'focus is not where it should be');
  await button(section, 'Open Changes').click();
  assert.equal(state.view, 'changes');
});

test('a refusal with no rows says why and closes', async () => {
  await fresh();
  queue(PREVIEW, refusal('Nothing to change.'));
  assert.equal(await addToTray(add('github')), false);
  const section = bar();
  assert.equal(section.className, 'bar tray err');
  assert.deepEqual(section.attributes['aria-label'], 'Could not prepare this change');
  const [words, acts] = section.children;
  assert.deepEqual(words.children.map((node) => [node.tag, node.className, node.textContent]), [['b', '', 'Could not prepare this change'], ['small', 'bad', 'Nothing to change.']]);
  assert.deepEqual(acts.children.map((node) => node.textContent), ['Close']);
  await button(section, 'Close').click();
  assert.deepEqual([bar(), tray.refused], [null, null]);
});

test('a refused add keeps the bar, shakes it and says why until the next add', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), refusal('Choose a server in the Kitden gateway.'), previewed('c3'));
  await addToTray(add('github'));
  reduce(false);
  const section = bar();
  const before = section.animations.length;
  assert.equal(await addToTray(add('neon')), false);
  assert.ok(bar() === section, 'the same bar');
  assert.equal(section.className, 'bar tray');
  const line = section.children[0].children[1];
  assert.deepEqual([line.textContent, line.className], ['Choose a server in the Kitden gateway.', 'bad']);
  assert.equal(section.animations.length, before + 1);
  assert.deepEqual(section.animations.at(-1).frames[1], { transform: 'translateX(-7px)' });
  reduce(true);
  // The next add clears it.
  assert.equal(await addToTray(add('slack')), true);
  assert.equal(bar().className, 'bar tray many');
  assert.equal(named(bar(), 'bad').length, 0);
});

test("Show changes opens the row's review in Details with no Apply of its own", async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  await button(bar(), 'Show changes').click();
  const drawer = pages['#drawer'];
  assert.equal(isPanelOpen(), true);
  assert.equal(panelState.current.type, 'row-review'); // never the type that cancels a change when it closes
  assert.equal(panelState.current.row, tray.rows[0]);
  const [head, body, footer] = drawer.children;
  assert.equal(tagged(head, 'h1')[0].textContent, 'Add github to Codex for all projects');
  assert.match(body.textContent, /Codex/);
  assert.deepEqual(buttonsOf(footer).map((node) => node.textContent), ['Take it out', 'Close']);
  assert.equal(all(drawer).filter((node) => node.classList.contains('apply')).length, 0);
  assert.equal(/Enter to apply/.test(drawer.textContent), false);
  // Close leaves the change as it is: the server is asked nothing.
  const asked = calls.length;
  await button(footer, 'Close').click();
  assert.equal(isPanelOpen(), false);
  assert.equal(calls.length, asked);
  assert.equal(tray.rows.length, 1);
});

test('Take it out in a row review takes the row out of the tray and closes Details', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  queue(PREVIEW, previewed('c3'));
  await button(bar(), 'Show changes: Add github to Codex for all projects').click();
  assert.equal(panelState.current.type, 'row-review');
  await button(pages['#drawer'], 'Take it out').click();
  await settle();
  assert.equal(isPanelOpen(), false);
  assert.deepEqual(tray.rows.map((r) => r.body.params.item), ['neon']);
  assert.equal(bar().attributes['aria-label'], 'Add neon to Codex for all projects');
});

test('a row review closes with the row: Cancel all leaves nothing to review', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  await button(bar(), 'Show changes').click();
  assert.equal(isPanelOpen(), true);
  await button(bar(), 'Cancel').click();
  assert.equal(isPanelOpen(), false);
  assert.equal(panelState.current, null);
});

test("Take it out in a row's review waits while Apply runs", async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  await button(bar(), 'Show changes: Add github to Codex for all projects').click();
  const out = button(pages['#drawer'], 'Take it out');
  assert.equal(out.attributes['aria-disabled'], undefined);
  const writing = slow();
  queue('/api/changes/c2/apply', writing.reply);
  const running = button(bar(), 'Apply all').click();
  // As the bar's ×: a change being written cannot stop halfway. The press does nothing.
  assert.equal(out.attributes['aria-disabled'], 'true');
  await out.click();
  await settle();
  assert.equal(isPanelOpen(), true);
  assert.equal(tray.rows.length, 2);
  assert.equal(posted().filter((url) => url === PREVIEW).length, 2);
  writing.release(verified('c2'));
  await settle();
  assert.equal(out.attributes['aria-disabled'], 'true', 'still off once applied');
  await running;
  // The row was applied: its review closed with it.
  assert.equal(isPanelOpen(), false);
  hideToast();
});

test("Take it out in a row's review hands focus to the bar's Apply, or to the page when the bar goes", async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'), previewed('c3'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  // Opened by a click that gives the button no focus (as in Safari): Details take it.
  await button(bar(), 'Show changes: Add github to Codex for all projects').click();
  assert.ok(pages['#drawer'].contains(globalThis.document.activeElement), 'focus is in Details');
  await button(pages['#drawer'], 'Take it out').click();
  await settle();
  assert.equal(isPanelOpen(), false);
  assert.ok(globalThis.document.activeElement === button(bar(), 'Apply'), 'focus is not on Apply');
  // The last row: the bar goes, and focus goes to the page without scrolling it.
  await button(bar(), 'Show changes').click();
  pages['#main'].focusedWith = null;
  await button(pages['#drawer'], 'Take it out').click();
  await settle();
  assert.equal(bar(), null);
  assert.ok(globalThis.document.activeElement === pages['#main'], 'focus is not on the page');
  assert.deepEqual(pages['#main'].focusedWith, { preventScroll: true });
});

test('a screen reader hears each change join and leave the tray', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'), previewed('c3'), previewed('c4'));
  await addToTray(add('github'));
  await settle();
  assert.deepEqual(heard(), ['Add github to Codex for all projects: in the preview.']);
  await addToTray(add('neon'));
  await settle();
  await addToTray(add('slack'));
  await settle();
  assert.deepEqual(heard().slice(1), [
    'Add neon to Codex for all projects: in the preview. 2 changes in preview.',
    'Add slack to Codex for all projects: in the preview. 3 changes in preview.',
  ]);
  // A row taken out is said at once, before the rest are previewed again; the new answer says nothing more.
  await takeOut(tray.rows[0].key);
  await settle();
  assert.deepEqual(heard().slice(3), ['Add github to Codex for all projects: taken out of the preview.']);
  // A refused add with the bar on the page: the bar's own line (a status) says why, once.
  queue(PREVIEW, refusal('Choose a server in the Kitden gateway.'));
  await addToTray(add('files'));
  await settle();
  assert.equal(heard().length, 4);
  // Cancel all takes every row out.
  await button(bar(), 'Cancel all').click();
  await settle();
  assert.deepEqual(heard().slice(4), ['2 changes taken out of the preview.']);
  // A first add that is refused: the bar comes in with the reason, so it is said here, with no path.
  queue(PREVIEW, refusal('/Users/me/.cursor/mcp.json has a hard link.'));
  await addToTray(add('github'));
  await settle();
  assert.deepEqual(heard().slice(5), ['Could not prepare this change. mcp.json has a hard link.']);
});

test('the toast says an applied tray, and the rows leaving it say nothing more', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  await settle();
  saidLog.length = 0;
  queue('/api/changes/c2/apply', verified('c2'));
  await button(bar(), 'Apply all').click();
  await settle();
  assert.deepEqual(heard(), ['Applied 2 changes']);
  hideToast();
});

test('a toast that shows while a change joins: the bar takes the dock and says the change', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  toast('Could not find this item in the Library.');
  await settle();
  saidLog.length = 0;
  await addToTray(add('neon'));
  await settle();
  assert.deepEqual(heard(), ['Add neon to Codex for all projects: in the preview. 2 changes in preview.']);
});

test('a row taken out while its × has focus hands focus to Apply before its buttons are turned off', async () => {
  for (const motion of [true, false]) {
    await fresh();
    queue(PREVIEW, previewed('c1'), previewed('c2'));
    await addToTray(add('github'));
    await addToTray(add('neon'));
    reduce(!motion);
    const cross = named(bar(), 'x')[0];
    cross.focus();
    queue(PREVIEW, previewed('c3'));
    const out = cross.click();
    // The press has turned the × off by now; focus is on Apply, not on nothing.
    assert.equal(cross.disabled, true);
    // With motion the list is still there (Apply all); without it the bar is one change already.
    assert.ok(globalThis.document.activeElement === button(bar(), motion ? 'Apply all' : 'Apply'), `focus, motion ${motion}`);
    await out;
    await sleep(motion ? 220 : 0);
    // The bar is one change now; its Apply has focus.
    assert.ok(globalThis.document.activeElement === button(bar(), 'Apply'), `focus at the end, motion ${motion}`);
  }
});

test('a bar that leaves with focus inside it hands focus to the page', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c1'), previewed('c1'));
  await addToTray(add('github'));
  button(bar(), 'Cancel').focus();
  await button(bar(), 'Cancel').click();
  assert.ok(globalThis.document.activeElement === pages['#main'], 'focus is not where it should be');
  // Focus that was somewhere else stays there.
  await addToTray(add('github'));
  const elsewhere = fakeNode('a');
  elsewhere.focus();
  await button(bar(), 'Cancel').click();
  assert.ok(globalThis.document.activeElement === elsewhere, 'focus is not where it should be');
  // After a verified Apply the bar leaves too, with focus on its Apply.
  await addToTray(add('github'));
  queue('/api/changes/c1/apply', verified('c1'));
  button(bar(), 'Apply').focus();
  await button(bar(), 'Apply').click();
  assert.equal(bar(), null);
  assert.ok(globalThis.document.activeElement === pages['#main'], 'focus is not where it should be');
  hideToast();
});

test('focus stays on the same button when the bar is built again', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  button(bar(), 'Cancel').focus();
  await addToTray(add('neon'));
  // One change became two: Cancel became Cancel all, and keeps focus.
  assert.ok(globalThis.document.activeElement === button(bar(), 'Cancel all'), 'focus is not where it should be');
  assert.equal(globalThis.document.activeElement.dataset.focus, 'tray:cancel');
  // A list that could not be previewed again is not counted; asked again, it is, and the same row's ×
  // keeps focus though the head is built again.
  await cancelTray();
  queue(PREVIEW, previewed('c3'), previewed('c4'), previewed('c5'), refusal('Apply the preview first.'), previewed('c6'));
  for (const name of ['github', 'neon', 'slack']) await addToTray(add(name));
  await takeOut(tray.rows[0].key);
  assert.deepEqual([tray.phase, named(bar(), 'num').length, bar().attributes['aria-label']], ['failed', 0, 'Could not prepare the preview']);
  const key = tray.rows[1].key;
  const second = named(bar(), 'x')[1];
  second.focus();
  const asking = tryAgain();
  assert.equal(named(bar(), 'num').length, 1);
  assert.ok(globalThis.document.activeElement !== second, 'focus left the old ×');
  assert.equal(globalThis.document.activeElement.dataset.focus, `tray:x:${key}`);
  assert.equal(globalThis.document.activeElement.isConnected, true);
  await asking;
});

test('the line follows the place without drawing the bar in again', async () => {
  await fresh();
  state.view = 'gateway';
  showMap(true);
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  reduce(false);
  const section = bar();
  const line = named(section, 'tray-head')[0].children[1];
  assert.match(line.textContent, /Click one on the map to take it out\./);
  const animations = all(section).map((node) => node.animations.length);
  // The page draws the place again as app.js does (`place`): the bar on the page follows it.
  state.view = 'library';
  showMap(false);
  drawTray(tray, { toastStays: true });
  drawTray(tray, { toastStays: true }); // safe to call twice
  assert.ok(bar() === section, 'the same bar');
  assert.equal(line.textContent, 'Nothing is written until you Apply.');
  assert.deepEqual(all(section).map((node) => node.animations.length), animations);
  state.view = 'gateway';
  showMap(true);
  drawTray(tray, { toastStays: true });
  assert.match(line.textContent, /Click one on the map/);
});

test('the line sends no one to the map while the Gateway shows its List', async () => {
  await fresh();
  state.view = 'gateway';
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  const line = named(bar(), 'tray-head')[0].children[1];
  assert.equal(line.textContent, 'Nothing is written until you Apply.');
  showMap(true);
  drawTray(tray, { toastStays: true });
  assert.equal(line.textContent, 'Nothing is written until you Apply. Click one on the map to take it out.');
});

test('a page redraw keeps a toast while rows wait; a tray change still replaces it', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  toast('Undone. The previous settings are back.', null, { ok: true });
  const shown = toastNode();
  // The page draws again (after an Undo, a search, a live refresh): the toast stays, and so does its room.
  drawTray(tray, { toastStays: true });
  drawTray(tray, { toastStays: true });
  assert.ok(toastNode() === shown, 'the toast stays');
  assert.equal(bar(), null);
  assert.equal(room(), '86px');
  // A change of the tray takes the dock: the bar replaces the toast at once, with both rows.
  await addToTray(add('neon'));
  assert.equal(shown.isConnected, false);
  assert.ok(button(bar(), 'Apply all'), 'the bar has both rows');
  // The bar still comes back when a toast leaves.
  toast('Could not find this item in the Library.');
  hideToast();
  assert.ok(button(bar(), 'Apply all'), 'the bar is back');
});

test('an Undo while rows wait keeps its toast, and the tray asks at once whether its preview is stale', async () => {
  await fresh();
  // What app.js does on every redraw of the page.
  setRenderer(() => drawTray(tray, { toastStays: true }));
  try {
    queue(PREVIEW, previewed('c1'));
    await addToTray(add('github'));
    queue('/api/changes/c0/undo', { status: 200, json: { id: 'c0', state: 'undone', steps: [] } });
    queue('/api/changes/c1', { status: 200, json: { id: 'c1', state: 'previewed', stale: true } });
    await quietly(() => undoChange({ id: 'c0' }));
    // The page's cross-fade draws it again a frame after the toast came.
    render();
    assert.deepEqual(toastParts().map(([, text]) => text), ['', 'Undone. The previous settings are back.']);
    assert.equal(tray.stale, true);
    // Once the toast has gone the bar is back, and offers a fresh preview.
    hideToast();
    assert.ok(button(bar(), 'Preview again'), 'the bar offers Preview again');
  } finally {
    setRenderer(() => {});
  }
});

test('an Undo whose Details cannot be read again still says how it went', async () => {
  await fresh();
  const body = fakeNode('div');
  const footer = fakeNode('footer');
  panelState.current = { type: 'item' };
  openPanel([body, footer]);
  keepFrom(() => {}, [body, footer], async () => { throw new Error('Could not read the item.'); });
  queue('/api/changes/c0/undo', { status: 200, json: { id: 'c0', state: 'undone', steps: [] } });
  try {
    await quietly(() => undoChange({ id: 'c0' }));
    assert.deepEqual(toastParts().map(([, text]) => text), ['', 'Undone. The previous settings are back.']);
    assert.equal(busy.change, false);
  } finally {
    hideToast();
    closePanel({ focus: false });
  }
});

test('the page keeps room under the bar while the dock shows one', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  assert.equal(room(), '106px'); // the bar's 60 px and the dock's 46 px offset
  await addToTray(add('neon'));
  assert.equal(room(), '206px');
  await button(bar(), 'Cancel all').click();
  assert.equal(room(), undefined);
  // With motion the room goes when the bar has gone.
  queue(PREVIEW, previewed('c3'));
  await addToTray(add('github'));
  reduce(false);
  await button(bar(), 'Cancel').click();
  assert.equal(room(), '106px');
  await sleep(200);
  assert.equal(room(), undefined);
  // A bar that grows with motion: the room is for its new height, not the animated one.
  await fresh();
  queue(PREVIEW, previewed('c4'), previewed('c5'));
  reduce(false);
  await addToTray(add('github'));
  await addToTray(add('neon'));
  assert.equal(room(), '206px');
  // A third change joins while that size animation still runs: the room is for the new height.
  queue(PREVIEW, previewed('c6'));
  await addToTray(add('slack'));
  assert.equal(room(), '256px');
  await sleep(250);
  assert.equal(room(), '256px');
});

test('a first refused add comes in with the entrance and does not shake', async () => {
  await fresh();
  reduce(false);
  queue(PREVIEW, refusal('Nothing to change.'));
  await addToTray(add('github'));
  const section = bar();
  assert.deepEqual(section.animations.map(({ frames }) => frames[0]), [{ opacity: 0, transform: 'translateY(18px) scale(.97)' }]);
});

// Details as a press drew them: a body with one control (`switch:i1`) and a footer. Reading them
// again (after Apply all or an Undo) counts in `seen.reads` and draws new nodes.
function openDetails(seen) {
  const body = fakeNode('div');
  const control = fakeNode('button');
  control.dataset.focus = 'switch:i1';
  body.append(control);
  const footer = fakeNode('footer');
  panelState.current = { type: 'item' };
  openPanel([body, footer]);
  keepFrom(() => openDetails(seen), [body, footer], async () => { seen.reads += 1; openDetails(seen); });
  return control;
}

test('open Details are read again after Apply all and after Undo all, focus left where it is', async () => {
  await fresh();
  const seen = { reads: 0 };
  openDetails(seen);
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  // Apply all from the dock: Details show the new files, and focus is not pulled into them.
  queue('/api/changes/c1/apply', verified('c1'));
  const apply = button(bar(), 'Apply');
  apply.focus();
  await apply.click();
  assert.deepEqual([seen.reads, isPanelOpen()], [1, true]);
  assert.ok(!pages['#drawer'].contains(globalThis.document.activeElement), 'focus moved into Details');
  // Undo from the toast: they are read again.
  queue('/api/changes/c1/undo', { status: 200, json: { id: 'c1', state: 'undone', steps: [] } });
  await quietly(async () => {
    button(toastNode(), 'Undo').click();
    await sleep(20);
  });
  assert.deepEqual([seen.reads, isPanelOpen()], [2, true]);
  assert.ok(!pages['#drawer'].contains(globalThis.document.activeElement), 'focus moved into Details');
  hideToast();
  // Focus in Details (⌘ Enter from a switch) stays on that control, drawn anew.
  queue(PREVIEW, previewed('c2'));
  await addToTray(add('neon'));
  queue('/api/changes/c2/apply', verified('c2'));
  const before = all(pages['#drawer']).find((node) => node.dataset.focus === 'switch:i1');
  before.focus();
  await button(bar(), 'Apply').click();
  assert.equal(seen.reads, 3);
  const now = globalThis.document.activeElement;
  assert.ok(now !== before && now.dataset.focus === 'switch:i1', 'focus did not stay on the switch');
  hideToast();
  closePanel({ focus: false });
});

test('a tool list of a server off by the shared rule says how many projects decide otherwise', async () => {
  await fresh();
  // All projects: files is off by the shared rule, two known projects turn it on.
  const projects = [{ id: 'a', server: 'on', tools: {} }, { id: 'b', server: 'on', tools: {} }, { id: 'c', server: 'off', tools: {} }];
  queue('/api/gateway/tools?server=files', { status: 200, json: { server: 'files', state: 'off', shared: 'off', strict: false, tools: [{ name: 'read_file', state: 'on', effective: 'off', hint: 'reads' }], projects } });
  const section = toolsSection('files', () => {});
  pages['#drawer'].replaceChildren(section);
  await settle();
  assert.ok(section.textContent.includes('files is off by the shared rule, so none of its tools are offered. 2 projects decide otherwise.'), section.textContent);
  assert.ok(!section.textContent.includes('off in all projects'), section.textContent);
  pages['#drawer'].replaceChildren();
});

test('a tool list drawn again gives focus to Refresh tools when the control asked for is gone', async () => {
  await fresh();
  // The writing tools are off now: "Turn off every writing tool…" is not drawn.
  queue('/api/gateway/tools?server=files', { status: 200, json: { server: 'files', state: 'on', strict: false, tools: [{ name: 'read_file', state: 'on', hint: 'reads' }] } });
  const section = toolsSection('files', () => {}, { focus: 'writing' });
  pages['#drawer'].replaceChildren(section);
  await settle();
  assert.equal(globalThis.document.activeElement.dataset.focus, 'tools:refresh');
  // A control that is there keeps it.
  queue('/api/gateway/tools?server=files', { status: 200, json: { server: 'files', state: 'on', strict: false, tools: [{ name: 'read_file', state: 'on', hint: 'reads' }] } });
  const again = toolsSection('files', () => {}, { focus: 'tool:read_file' });
  pages['#drawer'].replaceChildren(again);
  await settle();
  assert.equal(globalThis.document.activeElement.dataset.focus, 'tool:read_file');
  pages['#drawer'].replaceChildren();
});

const WAITS = 'Another change is being written.';

test("Apply and the toast's Undo wait while another change is written, and say why", async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  const apply = button(bar(), 'Apply');
  // An Undo is being written: Apply keeps its words and focus, and says why it waits.
  setBusy(true);
  try {
    assert.deepEqual([apply.attributes['aria-disabled'], apply.title], ['true', WAITS]);
    await apply.click();
    assert.equal(posted().filter((url) => url.endsWith('/apply')).length, 0);
  } finally {
    setBusy(false);
  }
  assert.deepEqual([apply.attributes['aria-disabled'], apply.title], [undefined, '']);
  // The toast's Undo waits the same way; a press does nothing and the toast stays.
  let undos = 0;
  toast('Turned off github', () => { undos += 1; }, { ok: true });
  const undo = button(toastNode(), 'Undo');
  setBusy(true);
  try {
    assert.deepEqual([undo.attributes['aria-disabled'], undo.title], ['true', WAITS]);
    await undo.click();
    assert.equal(undos, 0);
    assert.ok(toastNode(), 'the toast stays');
  } finally {
    setBusy(false);
  }
  assert.deepEqual([undo.attributes['aria-disabled'], undo.title], [undefined, '']);
  await undo.click();
  await settle();
  assert.equal(undos, 1);
  // A toast that comes while a change is written waits from the start.
  setBusy(true);
  try {
    toast('Turned off neon', () => {}, { ok: true });
    assert.equal(button(toastNode(), 'Undo').attributes['aria-disabled'], 'true');
  } finally {
    setBusy(false);
    hideToast();
  }
});

test('Cancel from the dock gives focus to the place the page names for its rows', async () => {
  await fresh();
  // The Gateway names the server a single move would have taken (gateway.js cancelFocusFor).
  const server = fakeNode('div');
  server.dataset.focus = 'block:outside:move:github';
  pages['#main'].replaceChildren(server);
  setCancelFocus((rows) => (rows.length === 1 ? 'block:outside:move:github' : null));
  try {
    queue(PREVIEW, previewed('c1'));
    await addToTray(add('github'));
    const cancel = button(bar(), 'Cancel');
    cancel.focus();
    await cancel.click();
    assert.equal(bar(), null);
    assert.equal(globalThis.document.activeElement, server);
    // Anything else: focus goes to the page.
    queue(PREVIEW, previewed('c2'), previewed('c3'));
    await addToTray(add('github'));
    await addToTray(add('neon'));
    const all = button(bar(), 'Cancel all');
    all.focus();
    await all.click();
    assert.equal(globalThis.document.activeElement, pages['#main']);
  } finally {
    setCancelFocus(() => null);
    pages['#main'].replaceChildren();
  }
});

test('an Undo with a tool list open leaves focus where it was, unless it was in Details', async () => {
  await fresh();
  const answer = { status: 200, json: { server: 'files', state: 'on', strict: false, tools: [{ name: 'read_file', state: 'on', hint: 'reads' }] } };
  queue('/api/gateway/tools?server=files', answer);
  const asked = [];
  const section = toolsSection('files', (next) => { asked.push(next); }, { flip: 'tool:read_file' });
  openPanel([section]);
  await settle();
  const outside = fakeNode('button');
  pages['#main'].replaceChildren(outside);
  try {
    outside.focus();
    queue('/api/changes/c0/undo', { status: 200, json: { id: 'c0', state: 'undone', steps: [] } });
    await quietly(() => undoChange({ id: 'c0' }));
    assert.deepEqual(asked, [{ focus: null, flip: 'tool:read_file' }]);
    assert.equal(globalThis.document.activeElement, outside);
    // Focus in Details goes to the switch the Undo changed back.
    pages['#drawer'].focus();
    queue('/api/changes/c0/undo', { status: 200, json: { id: 'c0', state: 'undone', steps: [] } });
    await quietly(() => undoChange({ id: 'c0' }));
    assert.deepEqual(asked[1], { focus: 'tool:read_file', flip: 'tool:read_file' });
  } finally {
    hideToast();
    closePanel({ focus: false });
    pages['#main'].replaceChildren();
  }
});

test("a row's review follows its row when it is added again under the same key", async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'), { key: 'same' });
  await button(bar(), 'Show changes').click();
  const title = () => tagged(pages['#drawer'], 'h1')[0].textContent;
  assert.equal(title(), 'Add github to Codex for all projects');
  // Focus in the bar stays there while the review follows.
  const apply = button(bar(), 'Apply');
  apply.focus();
  queue(PREVIEW, previewed('c2'));
  await addToTray(add('neon'), { key: 'same' });
  assert.equal(panelState.current.row, tray.rows[0]);
  assert.equal(title(), 'Add neon to Codex for all projects');
  assert.equal(globalThis.document.activeElement, apply);
  closePanel({ focus: false });
});

test('Details read again stay quiet only while the panel shows them; a read draws nothing over what opened meanwhile', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  // Details whose read waits, and that draw, as openItem does, only while they are what the panel
  // shows.
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  const body = fakeNode('div');
  const control = fakeNode('button');
  control.dataset.focus = 'switch:i1';
  body.append(control);
  const footer = fakeNode('footer');
  const mark = { type: 'item', name: 'github' };
  panelState.current = mark;
  openPanel([body, footer]);
  keepFrom(() => {}, [body, footer], async () => {
    await held;
    if (panelState.current === mark) openPanel([fakeNode('div'), fakeNode('footer')]);
  });
  control.focus();
  const again = detailsAgain([]);
  // Meanwhile the person shows the row's review from the bar: it is theirs, and takes focus.
  const show = button(bar(), 'Show changes');
  show.focus();
  await show.click();
  const drawer = pages['#drawer'];
  assert.equal(panelState.current.type, 'row-review');
  assert.equal(globalThis.document.activeElement, drawer);
  const out = button(drawer, 'Take it out');
  out.focus();
  release();
  await again;
  // The read ends: it draws nothing over the review, and focus stays where the person put it.
  assert.equal(panelState.current.type, 'row-review');
  assert.equal(globalThis.document.activeElement, out);
  closePanel({ focus: false });
});
