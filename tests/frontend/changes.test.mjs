import assert from 'node:assert/strict';
import { test } from 'node:test';

// The Changes page drawn in a small browser: elements, the page's fixed parts, a wide window and a
// stand-in server. It shows the timeline, a change's Details, Undo, Redo… and See it on the map.
let reduced = true;
globalThis.matchMedia = (query) => ({ get matches() { return /reduced-motion/.test(query) ? reduced : true; }, addEventListener() {} });
delete globalThis.navigator;
let frames = [];
globalThis.requestAnimationFrame = (fn) => frames.push(fn);
globalThis.ResizeObserver = class { observe() {} disconnect() {} };
globalThis.MutationObserver = class { observe() {} };
globalThis.innerWidth = 1440;
globalThis.getComputedStyle = (node) => ({ backgroundColor: node.className.includes('on') ? 'green' : 'grey', getPropertyValue: () => '' });

const walk = (root) => root.children.flatMap((n) => [n, ...walk(n)]);
const text = (root) => (root.children.length ? root.children.map(text).join('') : root.textContent);
function detach(node) {
  const parent = node.parentNode;
  if (!parent) return;
  parent.children.splice(parent.children.indexOf(node), 1);
  node.parentNode = null;
}
function element(tagName) {
  let names = [];
  const attributes = new Map();
  const style = { setProperty(name, value) { style[name] = value; }, removeProperty(name) { delete style[name]; } };
  const node = {
    tagName, style, dataset: {}, children: [], parentNode: null, textContent: '', listeners: {}, animations: [], hidden: false, offsetLeft: 900,
    get className() { return names.join(' '); },
    set className(value) { names = String(value).split(' ').filter(Boolean); },
    classList: {
      add: (...add) => { for (const name of add) if (!names.includes(name)) names.push(name); },
      remove: (...gone) => { names = names.filter((name) => !gone.includes(name)); },
      toggle: (name, force = !names.includes(name)) => { node.classList[force ? 'add' : 'remove'](name); return force; },
      contains: (name) => names.includes(name),
    },
    get isConnected() { let at = node; while (at.parentNode) at = at.parentNode; return Boolean(at.root); },
    setAttribute(name, value) { if (name === 'class') node.className = value; else attributes.set(name, String(value)); },
    getAttribute: (name) => (name === 'class' ? node.className : attributes.has(name) ? attributes.get(name) : null),
    removeAttribute(name) { attributes.delete(name); },
    get firstElementChild() { return node.children[0] || null; },
    get lastElementChild() { return node.children.at(-1) || null; },
    append(...nodes) { for (const n of nodes) node.insertBefore(typeof n === 'string' ? Object.assign(element('#text'), { textContent: n }) : n, null); },
    prepend(...nodes) { const first = node.children[0] || null; for (const n of nodes) node.insertBefore(n, first); },
    insertBefore(n, ref) {
      detach(n);
      node.children.splice(ref ? node.children.indexOf(ref) : node.children.length, 0, n);
      n.parentNode = node;
      return n;
    },
    remove() { detach(node); },
    replaceChildren(...nodes) { for (const n of [...node.children]) detach(n); node.append(...nodes); },
    contains(other) { for (let at = other; at; at = at.parentNode) if (at === node) return true; return false; },
    focus() { globalThis.document.activeElement = node; },
    getBoundingClientRect: () => ({ top: 0, right: 1200, bottom: 66, left: 0 }),
    matches: () => false,
    closest: () => null,
    get childNodes() { return node.children; },
    querySelector: (selector) => (selector === ':scope > summary' ? node.children.find((n) => n.tagName === 'SUMMARY') || null : null),
    querySelectorAll(selector) {
      const key = selector.match(/^\[data-(\w+)\]$/);
      return key ? walk(node).filter((n) => n.dataset[key[1]] !== undefined) : [];
    },
    addEventListener(type, fn) { (node.listeners[type] ||= []).push(fn); },
    animate(keyframes, options) {
      const animation = { keyframes, options, cancelled: false, finished: Promise.resolve(), cancel() { animation.cancelled = true; }, pause() {}, play() {} };
      node.animations.push(animation);
      return animation;
    },
    getAnimations: () => node.animations.filter((a) => !a.cancelled),
  };
  return node;
}
const fire = (node, type, event = {}) => Promise.all((node.listeners[type] || []).map((fn) => fn({ target: node, preventDefault() {}, ...event })));
const pages = {};
for (const id of ['#main', '#drawer', '#scrim', '.shell', '#dock', '#find-chip', '#said', '#topbar']) {
  pages[id] = element('DIV');
  pages[id].root = true;
}
const hintLine = element('P');
hintLine.hidden = true;
const content = element('DIV');
globalThis.document = {
  hidden: false, activeElement: null, body: element('BODY'),
  createElement: (tag) => element(tag.toUpperCase()), createElementNS: (namespace, tag) => element(tag),
  querySelector: (selector) => pages[selector] ?? null, querySelectorAll: () => [],
  getElementById: (id) => (id === 'hint' ? hintLine : id === 'content' ? content : null),
  addEventListener() {}, removeEventListener() {},
  documentElement: { classList: { add() {}, remove() {} }, style: { setProperty() {}, removeProperty() {} } },
};
try { globalThis.history = { pushState() {}, replaceState() {} }; } catch { /* read only */ }

// A stand-in server: each URL answers from its queue, or with {}.
const replies = new Map();
const asked = [];
globalThis.fetch = (url, init = {}) => {
  const body = init.body ? JSON.parse(init.body) : null;
  asked.push({ url, method: init.method || 'GET', body });
  const waiting = replies.get(url) || [];
  const next = waiting.length ? waiting.shift() : { status: 200, json: {} };
  const reply = typeof next === 'function' ? next(body) : next;
  return Promise.resolve(reply).then((made) => ({ ok: made.status < 400, status: made.status, json: async () => made.json }));
};
const queue = (url, ...items) => replies.set(url, [...(replies.get(url) || []), ...items]);
const flush = async () => { for (let i = 0; i < 8; i += 1) await new Promise((done) => setTimeout(done, 0)); };
const quietly = async (fn) => {
  const log = console.error;
  console.error = () => {};
  try { return await fn(); } finally { console.error = log; }
};

const changesJs = await import('../../src/kitden/web/static/js/changes.js');
const { backupWords, dayWords, renderChanges, weekCount } = changesJs;
const { changeTitle } = await import('../../src/kitden/web/static/js/parts.js');
const { closePanel, hideToast, isPanelOpen } = await import('../../src/kitden/web/static/js/panel.js');
const { STRIKE } = await import('../../src/kitden/web/static/js/motion.js');
const { arrival, data, setRenderer, state } = await import('../../src/kitden/web/static/js/store.js');
const { cancelTray, keyFor, onTray, tray } = await import('../../src/kitden/web/static/js/tray.js');
const { syncTray } = await import('../../src/kitden/web/static/js/details.js');
// What initPanel does for Details: buttons follow the tray.
onTray(syncTray);

// When a change was made: `ago` days back, at h:m local time.
function at(ago, h, m) {
  const date = new Date();
  date.setDate(date.getDate() - ago);
  date.setHours(h, m, 0, 0);
  const pad = (n) => String(n).padStart(2, '0');
  return { time: date.toISOString(), day: `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`, date };
}
const clock = (when) => when.date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const RULE = { action: 'gateway.rule', targets: [], params: { server: 'github', tool: 'push_files', state: 'on' }, picked: null };
const RESTART = 'Restart Codex (the app and any open CLI sessions) for this to take effect.';
// One change as /api/changes gives it (views/changes_view.py), with two tray rows.
function change(id, when, over = {}) {
  const rows = over.rows || [{ title: `Allow Push files ${id}` }, { title: `Turn off Code review ${id}` }];
  return {
    id, time: when.time, day: when.day,
    title_parts: { action: 'batch', steps: [], target: { scope: 'all' }, rule: null, rows },
    state: 'verified', clients: ['claude_code', 'codex'], project: 'mcp-gateway', backup: 'kept',
    takes_effect: [{ client: 'codex', note: RESTART, login: null }],
    history: [{ time: when.time, state: 'previewed' }, { time: when.time, state: 'verified' }],
    rows, redo: [RULE], map: { view: 'gateway', sel: 'tool:github/push_files', gone: false },
    technical: { paths: ['/Users/me/.codex/config.toml'], backups: ['/Users/me/.kitden/backups/c1/config.toml'], commands: ['claude mcp add github'], error: null },
    holds_secret: false, ...over,
  };
}
const TODAY = at(0, 14, 2);
const TODAY_EARLIER = at(0, 11, 15);
const YESTERDAY = at(1, 18, 20);
const OLDER = at(6, 17, 5);
const ENTRIES = [
  change('c1', TODAY),
  change('c2', TODAY_EARLIER, { state: 'undone', backup: 'back', history: [{ time: TODAY_EARLIER.time, state: 'verified' }, { time: TODAY_EARLIER.time, state: 'undone' }] }),
  change('c3', YESTERDAY, { state: 'stale', backup: 'none', takes_effect: [], redo: null, map: null }),
  change('c4', OLDER, { state: 'restored', backup: 'back', takes_effect: [], technical: { paths: [], backups: [], commands: [], error: 'Codex did not start. The original settings were restored.' } }),
];

const main = pages['#main'];
const drawer = pages['#drawer'];
// The page as app.js draws it: the main box emptied, then Changes drawn into it.
let shownAt = null;
function show(entries = ENTRIES, { again = false } = {}) {
  data.changes = structuredClone(entries);
  state.view = 'changes';
  shownAt = 'changes';
  main.replaceChildren();
  renderChanges(main, { again });
}
setRenderer(() => { if (state.view === 'changes') show(data.changes, { again: shownAt === 'changes' }); });

const byClass = (root, name) => walk(root).filter((n) => n.classList.contains(name));
const row = (id) => walk(main).find((n) => n.dataset.change === id) || null;
const cell = (id, name) => byClass(row(id), name)[0] || null;
const buttonIn = (root, label) => walk(root).find((n) => n.tagName === 'BUTTON' && text(n) === label) || null;
const facts = () => {
  const list = byClass(drawer, 'facts')[0];
  const pairs = [];
  for (let i = 0; i < list.children.length; i += 2) pairs.push([text(list.children[i]), text(list.children[i + 1])]);
  return pairs;
};
const panelTitle = () => walk(drawer).find((n) => n.tagName === 'H1');

// A closed panel, an empty tray and dock, and reduced motion in every test; a test that looks at
// motion turns it on.
async function fresh() {
  reduced = true;
  hideToast({ now: true });
  closePanel({ instant: true, focus: false });
  await cancelTray();
  pages['#dock'].replaceChildren();
  replies.clear();
  asked.length = 0;
  state.view = 'changes';
  state.project = '';
  shownAt = null;
}

test('dayWords says Today, Yesterday, then a short date in the person\'s language', () => {
  const now = new Date(2026, 9, 27, 9, 0);
  assert.equal(dayWords('2026-10-27', now), 'Today');
  assert.equal(dayWords('2026-10-26', now), 'Yesterday');
  assert.equal(dayWords('2026-10-19', now, 'en-GB'), 'Mon 19 Oct');
  // Another year names it.
  assert.equal(dayWords('2025-10-20', now, 'en-GB'), 'Mon, 20 Oct 2025');
  assert.equal(dayWords(null, now), 'Earlier');
});

test('the week counts changes since Monday', () => {
  const wednesday = new Date(2026, 9, 28, 9, 0);
  const days = ['2026-10-28', '2026-10-26', '2026-10-25', null].map((day) => ({ day }));
  assert.equal(weekCount(days, wednesday), 2);
});

test('the head says Changes, the lede, the scope with this week\'s count and the hint', async () => {
  await fresh();
  show();
  assert.equal(main.children[0].textContent, 'Changes');
  assert.equal(text(main.children[1]), 'Every change made from this page. Each one has a backup; Undo puts the previous file back.');
  const scope = byClass(main, 'scope-bar')[0];
  assert.equal(scope.children[0].dataset.icon, 'layers');
  assert.match(text(scope), /^All projects · \d+ changes? this week$/);
  assert.equal(hintLine.hidden, false);
  assert.equal(hintLine.children.at(-1).textContent, 'Click a row · Undo · See it on the map');
});

test('the timeline groups by Today, Yesterday and a date, with a rail and a dot per row', async () => {
  await fresh();
  show();
  const groups = byClass(main, 'tl-day');
  const label = (group) => text(byClass(group, 'day')[0]);
  const expected = OLDER.date.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
  assert.deepEqual(groups.map(label), ['Today', 'Yesterday', expected]);
  assert.deepEqual(groups.map((group) => byClass(group, 'row').map((n) => n.dataset.change)), [['c1', 'c2'], ['c3'], ['c4']]);
  for (const group of groups) {
    // One rail per group, and the list is named by its day.
    const rails = byClass(group, 'rail-line');
    assert.equal(rails.length, 1);
    assert.equal(rails[0].getAttribute('aria-hidden'), 'true');
    const list = walk(group).find((n) => n.tagName === 'UL');
    assert.equal(list.getAttribute('aria-labelledby'), byClass(group, 'day')[0].id);
    for (const node of byClass(group, 'row')) assert.equal(byClass(node, 'dot').length, 1);
  }
});

test('a row shows time, title, client tiles, state and Undo', async () => {
  await fresh();
  show();
  const node = row('c1');
  assert.equal(text(cell('c1', 'time')), clock(TODAY));
  assert.equal(text(cell('c1', 't')), 'Allow Push files c1 and 1 more');
  assert.equal(text(cell('c1', 't')), changeTitle(ENTRIES[0].title_parts));
  assert.deepEqual(cell('c1', 'who').children.map((n) => n.title), ['Claude Code', 'Codex']);
  const lamp = byClass(cell('c1', 'state'), 'lamp')[0];
  assert.ok(lamp.classList.contains('on'));
  assert.equal(text(cell('c1', 'sw')), 'Applied');
  const undo = buttonIn(cell('c1', 'act'), 'Undo');
  assert.ok(undo, 'an applied row has Undo');
  assert.equal(undo.children[0].dataset.icon, 'undo-2');
  // Only an applied row has Undo; the row takes focus and names itself to the page.
  assert.equal(buttonIn(cell('c2', 'act'), 'Undo'), null);
  assert.equal(node.getAttribute('tabindex'), '0');
  assert.equal(node.dataset.focus, 'change:c1');
  // No path, backup or command is on the list.
  assert.ok(!text(main).includes('/Users/'), 'no path on the page');
  assert.ok(!text(main).includes('claude mcp'), 'no command on the page');
});

test('undone rows are muted with a strike; failed rows keep their phrase (no cancelled state is logged)', async () => {
  await fresh();
  show();
  assert.ok(row('c2').classList.contains('undone'));
  assert.equal(byClass(row('c2'), 'strike').length, 1);
  assert.equal(text(cell('c2', 'sw')), 'Undone');
  assert.ok(!byClass(cell('c2', 'state'), 'lamp')[0].classList.contains('on'));
  for (const [id, words] of [['c3', 'Not applied: the file changed first'], ['c4', 'Failed, put back']]) {
    assert.ok(!row(id).classList.contains('undone'), id);
    assert.ok(cell(id, 'state').classList.contains('warn'), id);
    assert.ok(byClass(cell(id, 'state'), 'lamp')[0].classList.contains('warn'), id);
    assert.equal(text(cell(id, 'sw')), words);
  }
  show([change('c5', TODAY, { state: 'undo_blocked' }), change('c6', TODAY, { state: 'restored', backup: 'kept', technical: { paths: [], backups: [], commands: [], error: 'Codex did not start.' } })]);
  assert.equal(text(cell('c5', 'sw')), "Can't undo: the file changed after this");
  assert.equal(text(cell('c6', 'sw')), 'Failed');
});

test('a change that touched only the Kitden gateway shows its mark, not 0 clients', async () => {
  await fresh();
  show([change('k1', TODAY, { clients: [] })]);
  const who = cell('k1', 'who');
  assert.equal(who.children.length, 1);
  assert.equal(who.children[0].title, 'Kitden gateway');
  const clients = facts().find(([label]) => label === 'Clients');
  assert.equal(clients[1], 'Kitden gateway');
});

test('the first row is selected with its Details open', async () => {
  await fresh();
  show();
  assert.equal(row('c1').getAttribute('aria-current'), 'true');
  assert.ok(row('c1').classList.contains('selected'));
  assert.equal(row('c2').getAttribute('aria-current'), null);
  assert.ok(isPanelOpen());
  assert.ok(drawer.classList.contains('floating'), 'Details float beside the list');
  assert.equal(text(byClass(drawer, 'kicker')[0]), 'Change');
  assert.equal(text(panelTitle()), 'Allow Push files c1 and 1 more');
  assert.equal(text(byClass(walk(drawer).find((n) => n.tagName === 'HEADER'), 'muted')[0]), `Today ${clock(TODAY)}`);
  // A press on another row selects it and shows its Details.
  await fire(row('c3'), 'click');
  assert.equal(row('c3').getAttribute('aria-current'), 'true');
  assert.equal(row('c1').getAttribute('aria-current'), null);
  assert.equal(text(panelTitle()), 'Allow Push files c3 and 1 more');
  // A later draw keeps the selection and opens nothing again.
  closePanel({ instant: true, focus: false });
  show(ENTRIES, { again: true });
  assert.equal(row('c3').getAttribute('aria-current'), 'true');
  assert.equal(isPanelOpen(), false);
});

test('Enter and Space open a row; the arrows move between rows', async () => {
  await fresh();
  show();
  await fire(row('c2'), 'keydown', { key: 'Enter', target: row('c2') });
  assert.equal(text(panelTitle()), 'Allow Push files c2 and 1 more');
  await fire(row('c3'), 'keydown', { key: ' ', target: row('c3') });
  assert.equal(text(panelTitle()), 'Allow Push files c3 and 1 more');
  await fire(row('c3'), 'keydown', { key: 'ArrowDown', target: row('c3') });
  assert.equal(document.activeElement, row('c4'));
  await fire(row('c4'), 'keydown', { key: 'ArrowUp', target: row('c4') });
  assert.equal(document.activeElement, row('c3'));
});

test('Details show Project, State, Backup, Takes effect, Clients and History', async () => {
  await fresh();
  show();
  const time = clock(TODAY);
  assert.deepEqual(facts(), [
    ['Project', 'mcp-gateway'],
    ['State', 'Applied and checked'],
    ['Backup', 'Kept · Undo puts it back'],
    ['Takes effect', RESTART],
    ['Clients', '2 clients'],
    ['History', `${time} Preview${time} Applied${time} Checked`],
  ]);
  // The history's steps are joined by arrows, none before the first.
  const history = byClass(drawer, 'p-hist')[0];
  assert.deepEqual(history.children.map((n) => n.dataset.icon || text(n)), [`${time} Preview`, 'arrow-right', `${time} Applied`, 'arrow-right', `${time} Checked`]);
  // Every row of the change is named.
  assert.deepEqual(byClass(drawer, 'p-rows')[0].children.map(text), ['Allow Push files c1', 'Turn off Code review c1']);
  // The other states, in words that are true for each.
  await fire(row('c2'), 'click');
  assert.deepEqual(facts().slice(0, 4).map(([, v]) => v), ['mcp-gateway', 'Undone', 'Back in place', RESTART]);
  await fire(row('c3'), 'click');
  assert.deepEqual(facts().slice(0, 4).map(([, v]) => v), ['mcp-gateway', 'Not applied: the file changed first', 'None, nothing was written', 'Nothing to do']);
  show([change('a1', TODAY, { project: null, clients: ['codex'], takes_effect: [{ client: 'codex', note: null, login: 'codex login' }] })]);
  assert.deepEqual(facts().map(([, v]) => v).filter((v, i) => [0, 3, 4].includes(i)), ['All projects', 'Log in: codex login', '1 client']);
});

test('the backup words follow the state, not the backup alone', () => {
  assert.equal(backupWords({ state: 'verified', backup: 'kept' }), 'Kept · Undo puts it back');
  assert.equal(backupWords({ state: 'undo_blocked', backup: 'kept' }), "Kept · Undo can't put it back: the file changed after this");
  assert.equal(backupWords({ state: 'undone', backup: 'back' }), 'Back in place');
  assert.equal(backupWords({ state: 'restored', backup: 'back' }), 'Back in place');
  assert.equal(backupWords({ state: 'restored', backup: 'kept' }), 'Kept · not everything was put back');
  assert.equal(backupWords({ state: 'stale', backup: 'none' }), 'None, nothing was written');
});

test('See it on the map opens the item; a removed item says This item is no longer there.', async () => {
  await fresh();
  show();
  const see = buttonIn(drawer, 'See it on the map');
  assert.ok(see);
  await quietly(() => fire(see, 'click'));
  await flush();
  assert.equal(state.view, 'gateway');
  assert.equal(state.mode, 'map');
  assert.deepEqual(state.selected, { kind: 'tool', name: 'github/push_files' });
  assert.equal(arrival.pending, true);
  arrival.pending = false;
  // An item that is gone: the page stays and says so.
  await fresh();
  state.selected = null;
  show([change('g1', TODAY, { map: { view: 'library', sel: null, gone: true } })]);
  await fire(buttonIn(drawer, 'See it on the map'), 'click');
  await flush();
  assert.equal(state.view, 'changes');
  const status = walk(drawer).find((n) => n.getAttribute('role') === 'status');
  assert.equal(status.textContent, 'This item is no longer there.');
  // A change with no map target offers no button.
  await fire(row('g1'), 'click');
  show([change('n1', TODAY, { map: null })]);
  assert.equal(buttonIn(drawer, 'See it on the map'), null);
});

test('Undo draws the strike and the toast says Undid “…”. The backup is back in place. with Redo…', async () => {
  await fresh();
  show();
  reduced = false;
  const undoneNow = ENTRIES.map((e) => (e.id === 'c1' ? { ...e, state: 'undone', backup: 'back', history: [...e.history, { time: TODAY.time, state: 'undone' }] } : e));
  queue('/api/changes/c1/undo', { status: 200, json: { id: 'c1', state: 'undone', steps: [] } });
  queue('/api/changes', { status: 200, json: undoneNow });
  try {
    await quietly(() => fire(buttonIn(cell('c1', 'act'), 'Undo'), 'click'));
    await flush();
    // The page drew again from what the server says now; the row shows the Undo as it happens.
    const node = row('c1');
    assert.ok(node.classList.contains('undone'));
    const [strike] = byClass(node, 'strike')[0].animations;
    assert.deepEqual(strike.keyframes, [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }]);
    assert.deepEqual([strike.options.duration, strike.options.easing], [200, STRIKE]);
    const [lamp] = byClass(cell('c1', 'state'), 'lamp')[0].animations;
    assert.deepEqual([lamp.keyframes, lamp.options.duration, lamp.options.easing], [[{ backgroundColor: 'green' }, { backgroundColor: 'grey' }], 400, 'ease']);
    // The word rolls: the old one leaves and the new one comes in.
    assert.deepEqual(cell('c1', 'sw').children.map((n) => n.textContent), ['Applied', 'Undone']);
    // The Undo button goes out: opacity and scale to .8 in 180 ms, then it is gone.
    const ghost = byClass(cell('c1', 'act'), 'going')[0];
    assert.deepEqual(ghost.animations[0].keyframes, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'scale(0.8)' }]);
    assert.equal(ghost.animations[0].options.duration, 180);
    assert.equal(ghost.getAttribute('aria-hidden'), 'true');
    await new Promise((done) => setTimeout(done, 200));
    assert.equal(byClass(cell('c1', 'act'), 'going').length, 0);
    // Truth first: the toast came after the verified Undo, with the title and Redo….
    const toast = byClass(pages['#dock'], 'toast')[0];
    assert.equal(text(toast.children[1]), 'Undid “Allow Push files c1 and 1 more”. The backup is back in place.');
    assert.ok(byClass(toast, 'tk').length, 'a green check');
    assert.ok(buttonIn(toast, 'Redo…'));
    assert.equal(buttonIn(toast, 'Undo'), null);
    // Details show the Undo too: the state, the backup, and Redo… in place of Undo.
    assert.equal(facts()[1][1], 'Undone');
    assert.equal(facts()[2][1], 'Back in place');
    assert.equal(buttonIn(drawer, 'Undo'), null);
    assert.ok(buttonIn(drawer, 'Redo…'));
  } finally {
    reduced = true;
  }
});

test('Redo… adds a fresh preview and writes nothing; an old change offers none', async () => {
  await fresh();
  show();
  await fire(row('c2'), 'click');
  queue('/api/batch/preview', (sent) => ({
    status: 200,
    json: { id: 'p1', action: 'batch', state: 'previewed', error: null, target: { scope: 'all' }, undo_note: null, steps: [{ client: 'kitden', name: 'github' }], rows: sent.requests.map((r, i) => ({ id: r.id, kind: r.kind, title: r.title, detail: '', project: null, steps: [i], target: { scope: 'all' }, after: [], undo_note: null })) },
  }));
  await fire(buttonIn(drawer, 'Redo…'), 'click');
  await flush();
  assert.deepEqual(tray.rows.map((r) => r.key), [keyFor(RULE)]);
  assert.ok(asked.every((call) => call.method === 'GET' || call.url === '/api/batch/preview'), 'only a preview was asked');
  assert.ok(!asked.some((call) => call.url.includes('/apply') || call.url.includes('/undo')));
  // While it waits in the tray the button says so.
  assert.ok(buttonIn(drawer, 'In preview'));
  await cancelTray();
  // An old change kept no request: no Redo….
  show([change('o1', TODAY, { state: 'undone', backup: 'back', redo: null })]);
  assert.equal(buttonIn(drawer, 'Redo…'), null);
  // An applied change offers Undo, not Redo….
  show();
  assert.equal(buttonIn(drawer, 'Redo…'), null);
  assert.ok(buttonIn(drawer, 'Undo'));
});

test('Technical details hold the paths', async () => {
  await fresh();
  show();
  const tech = byClass(drawer, 'tech')[0];
  assert.equal(text(tech.children[0]), 'Technical details');
  const all = walk(tech);
  const titled = all.filter((n) => n.title).map((n) => n.title);
  assert.ok(titled.includes('/Users/me/.codex/config.toml'));
  assert.ok(titled.includes('/Users/me/.kitden/backups/c1/config.toml'));
  assert.ok(text(tech).includes('claude mcp add github'));
  // Nowhere else in Details.
  const rest = drawer.children.filter((n) => n !== tech);
  assert.ok(!rest.some((n) => text(n).includes('config.toml') || text(n).includes('claude mcp')));
  // The engine's error names files: it is there too.
  await fire(row('c4'), 'click');
  assert.ok(text(byClass(drawer, 'tech')[0]).includes('Codex did not start.'));
});

test('under reduced motion everything lands at once', async () => {
  await fresh();
  reduced = true;
  show();
  for (const node of walk(main)) assert.deepEqual(node.animations, [], 'nothing moves on the way in');
  const undoneNow = ENTRIES.map((e) => (e.id === 'c1' ? { ...e, state: 'undone', backup: 'back' } : e));
  queue('/api/changes/c1/undo', { status: 200, json: { id: 'c1', state: 'undone', steps: [] } });
  queue('/api/changes', { status: 200, json: undoneNow });
  await quietly(() => fire(buttonIn(cell('c1', 'act'), 'Undo'), 'click'));
  await flush();
  assert.ok(row('c1').classList.contains('undone'));
  assert.deepEqual(cell('c1', 'sw').children.map((n) => n.textContent), ['Undone']);
  assert.equal(byClass(cell('c1', 'act'), 'going').length, 0);
  for (const node of walk(main)) assert.deepEqual(node.animations, [], 'nothing moves after Undo');
  // Details come at once, with no skeleton.
  assert.equal(facts()[1][1], 'Undone');
});

test('on the way in the day labels and rows rise in order, 40 ms apart', async () => {
  await fresh();
  reduced = false;
  try {
    show();
    const order = walk(byClass(main, 'tl')[0]).filter((n) => n.classList.contains('day') || n.classList.contains('row'));
    assert.deepEqual(order.map((n) => n.animations[0].options.delay), order.map((n, i) => i * 40));
    assert.deepEqual(order[0].animations[0].keyframes, [{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }]);
    // A new row at the top after a later Apply comes in on its own; the others stay still.
    const newer = change('c0', at(0, 15, 0));
    show([newer, ...ENTRIES], { again: true });
    assert.deepEqual(row('c0').animations[0].keyframes, [{ opacity: 0, transform: 'translateY(-8px) scale(0.98)' }, { opacity: 1, transform: 'none' }]);
    assert.equal(row('c0').animations[0].options.duration, 220);
    assert.deepEqual(row('c1').animations, []);
  } finally {
    reduced = true;
  }
});
