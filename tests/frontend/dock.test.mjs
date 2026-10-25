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
    focus() { globalThis.document.activeElement = node; },
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
const { appliedToast, barWords, drawTray, initDock, outcomeLine, rowWords, writingLine } = await import(dockPath);
const { changeWords } = await import('../../src/kitden/web/static/js/review.js');
const { addToTray, cancelTray, endApplied, takeOut, tray, tryAgain } = await import('../../src/kitden/web/static/js/tray.js');
const { busy, state } = await import('../../src/kitden/web/static/js/store.js');
const { hideToast, isPanelOpen, panelState, toast } = await import('../../src/kitden/web/static/js/panel.js');
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
  globalThis.document.activeElement = null;
  hideToast();
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
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
  reduce(false);
  const section = bar();
  const line = named(section, 'tray-head')[0].children[1];
  assert.match(line.textContent, /Click one on the map to take it out\./);
  const animations = all(section).map((node) => node.animations.length);
  state.view = 'library';
  drawTray(tray);
  drawTray(tray); // safe to call twice
  assert.ok(bar() === section, 'the same bar');
  assert.equal(line.textContent, 'Nothing is written until you Apply.');
  assert.deepEqual(all(section).map((node) => node.animations.length), animations);
  state.view = 'gateway';
  drawTray(tray);
  assert.match(line.textContent, /Click one on the map/);
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
