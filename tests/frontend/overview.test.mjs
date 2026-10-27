import assert from 'node:assert/strict';
import { test } from 'node:test';

// The Overview drawn in a small browser: elements, the page's fixed parts, and frames and a clock
// that only the test moves. It shows what the page draws and how it answers the tray.
let reduced = false;
globalThis.matchMedia = () => ({ get matches() { return reduced; }, addEventListener() {} });
delete globalThis.navigator;
let now = 0;
let frames = [];
Object.defineProperty(globalThis, 'performance', { value: { now: () => now, mark() {}, measure() {}, getEntriesByName: () => [] }, configurable: true, writable: true });
globalThis.requestAnimationFrame = (fn) => frames.push(fn);
// Every frame runs to its end.
const settle = () => { while (frames.length) { now += 10000; const run = frames; frames = []; for (const fn of run) fn(now); } };
globalThis.ResizeObserver = class { observe() {} disconnect() {} };
globalThis.MutationObserver = class { observe() {} };
globalThis.innerWidth = 1440;
globalThis.getComputedStyle = () => ({ strokeDasharray: 'none', strokeOpacity: '1', paddingTop: '12px', paddingBottom: '12px', borderTopWidth: '1px', borderBottomWidth: '1px' });

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
    tagName, style, dataset: {}, children: [], parentNode: null, textContent: '', listeners: {}, animations: [], hidden: false,
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
    append(...nodes) { for (const n of nodes) node.insertBefore(typeof n === 'string' ? element('#text') : n, null); },
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
    matches: () => false,
    closest: () => null,
    querySelector: () => null,
    querySelectorAll(selector) {
      const key = selector.match(/^\[data-(\w+)\]$/);
      return key ? walk(node).filter((n) => n.dataset[key[1]] !== undefined) : [];
    },
    addEventListener(type, fn) { (node.listeners[type] ||= []).push(fn); },
    animate(keyframes, options) {
      const animation = { keyframes, options, cancelled: false, finished: Promise.resolve(), cancel() { animation.cancelled = true; } };
      node.animations.push(animation);
      return animation;
    },
    getAnimations: () => node.animations.filter((a) => !a.cancelled),
  };
  return node;
}
const fire = (node, type, event = {}) => { for (const fn of node.listeners[type] || []) fn({ target: node, preventDefault() {}, ...event }); };
const pages = {};
for (const id of ['#main', '#drawer', '#scrim', '.shell', '#dock', '#find-chip', '#said']) {
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
  asked.push(url);
  const waiting = replies.get(url) || [];
  const next = waiting.length ? waiting.shift() : { status: 200, json: {} };
  const reply = typeof next === 'function' ? next(body) : next;
  return Promise.resolve(reply).then((made) => ({ ok: made.status < 400, status: made.status, json: async () => made.json }));
};
const queue = (url, ...items) => replies.set(url, [...(replies.get(url) || []), ...items]);
const PREVIEW = '/api/batch/preview';
const batch = (id) => (sent) => ({
  status: 200,
  json: {
    id, action: 'batch', state: 'previewed', error: null, target: { scope: 'all' }, undo_note: null,
    steps: sent.requests.map(() => ({ client: 'kitden', name: 'x' })),
    rows: sent.requests.map((request, index) => ({ id: request.id, kind: request.kind, title: request.title, detail: '', project: null, steps: [index], target: { scope: 'all' }, after: [], undo_note: null })),
  },
});
const flush = async () => { for (let i = 0; i < 6; i += 1) await new Promise((done) => setTimeout(done, 0)); };

const { countUp } = await import('../../src/kitden/web/static/js/motion.js');
const overviewJs = await import('../../src/kitden/web/static/js/overview.js');
const { footWords, ledeText, noteGroups, noteItemRow, noteSentence, renderOverview, setupPath, setupTree, targetSel } = overviewJs;
const { data, setRenderer, state } = await import('../../src/kitden/web/static/js/store.js');
const { applyTray, cancelTray, endApplied, keyFor, tray } = await import('../../src/kitden/web/static/js/tray.js');

// The Overview's answer (views/overview.py), cut short.
const MOVE = (item) => ({ action: 'gateway.move', targets: [{ item }], params: { gateway: 'kitden' } });
const UPDATE = { action: 'setup_server.update', targets: [{ item: 'old1' }], params: {} };
const CONNECT = { action: 'setup_server.register', targets: [{ client: 'cursor' }], params: {} };
const SKIPS = "Skips the gateway, so Kitden's rules don't reach it.";
const CARDS = [
  { id: 'unread', group: 'attention', icon: 'file-text', name: 'Could not read mcp.json', line: 'The file has a syntax error, so items from Cursor may be missing or wrong.', clients: ['cursor'], action: null, focus: { clients: ['cursor'], block: null } },
  { id: 'old', group: 'attention', icon: 'house', name: 'Old Kitden entry in Codex', line: 'The working version, agentsetup, made it; update it so Codex starts kitden.', clients: ['codex'], action: { label: 'Update…', body: UPDATE }, focus: { clients: ['codex'], block: 'gateway' } },
  { id: 'dup', group: 'attention', icon: 'puzzle', name: 'superpowers', line: 'Two copies of one plugin load; keep one.', clients: ['cursor'], action: { label: 'Keep one…', go: { view: 'library', sel: 'plugin:superpowers' } }, focus: { clients: ['cursor'], block: 'library' } },
  { id: 'm1', group: 'improve', icon: 'globe', name: 'analytics', line: SKIPS, clients: ['codex'], action: { label: 'Move in…', body: MOVE('a1') }, focus: { clients: ['codex'], block: 'gateway' } },
  { id: 'm2', group: 'improve', icon: 'globe', name: 'github', line: SKIPS, clients: ['claude_code'], action: { label: 'Move in…', body: MOVE('g1') }, focus: { clients: ['claude_code'], block: 'gateway' } },
  { id: 'm3', group: 'improve', icon: 'hard-drive', name: 'notes', line: SKIPS, clients: ['cursor'], action: { label: 'Move in…', body: MOVE('n1') }, focus: { clients: ['cursor'], block: 'gateway' } },
  { id: 'more', group: 'improve', icon: 'server', name: '4 more servers skip the gateway', line: "Kitden's rules don't reach them.", clients: ['claude_code', 'codex', 'cursor'], action: { label: 'Show…', go: { view: 'gateway', sel: 'group:outside', mode: 'list' } }, focus: { clients: ['claude_code', 'codex', 'cursor'], block: 'gateway' } },
  { id: 'conn', group: 'improve', icon: { client: 'cursor' }, name: 'Cursor', line: 'Not connected to the gateway yet.', clients: ['cursor'], action: { label: 'Connect…', body: CONNECT }, focus: { clients: ['cursor'], block: 'gateway' } },
];
const MAP = {
  clients: [
    { id: 'claude_code', name: 'Claude Code', version: '2.1.283', tested: true, on: true },
    { id: 'codex', name: 'Codex', version: '0.159.2', tested: true, on: true },
    { id: 'cursor', name: 'Cursor', version: '3.21.16', tested: true, on: true },
  ],
  gateway: { servers: 2, tools: 7 }, library: { plugins: 4, skills: 7 },
  links: [{ client: 'claude_code', to: 'gateway' }, { client: 'claude_code', to: 'library' }, { client: 'codex', to: 'gateway' }, { client: 'cursor', to: 'library' }],
  projects: 4, own_rules: 3,
};
const MODEL = { cards: CARDS, notes: 3, map: MAP, counts: { attention: 3, clients: 3, projects: 4 } };
const without = (id, attention) => ({ ...MODEL, cards: CARDS.filter((c) => c.id !== id), counts: { ...MODEL.counts, attention } });

const main = pages['#main'];
let drawingPage = false;
setRenderer(() => { if (drawingPage) show(current, { again: true }); });
let current = MODEL;
let readAt = 1;
// The page as app.js draws it: the main box emptied, then the Overview drawn into it.
function show(model = MODEL, { again = false } = {}) {
  current = model;
  Object.assign(data, { overview: structuredClone(model), clients: [{ id: 'claude_code', status: 'found' }], projects: [] });
  data.scope.overview = state.project;
  data.readAt.overview = Date.now() + readAt++;
  state.view = 'overview';
  main.replaceChildren();
  renderOverview(main, { again });
}
const byClass = (root, name) => walk(root).filter((n) => n.classList.contains(name));
const card = (id) => walk(main).find((n) => n.dataset.card === id) || null;
const cardButton = (id) => walk(card(id)).find((n) => n.tagName === 'BUTTON') || null;
const words = (node) => walk(node).filter((n) => n.tagName === 'SPAN' && n.classList.contains('cut')).map((n) => n.textContent)[0] ?? text(node);
const lede = () => byClass(main, 'lede')[0];
const setupBox = () => walk(main).find((n) => n.classList.contains('map')) || null;
const block = (id) => walk(setupBox()).find((n) => n.dataset.focus === `block:${id}`) || null;

test('the head says Your setup, connected. and the lede counts', () => {
  show();
  assert.equal(main.children[0].textContent, 'Your setup, connected.');
  // The first visit counts the numbers up from 0; the frames bring them to their values.
  assert.equal(text(lede()), '0 things need your attention. Everything else looks fine: 0 clients, 0 projects.');
  settle();
  assert.equal(text(lede()), '3 things need your attention. Everything else looks fine: 3 clients, 4 projects.');
  // A later draw shows them at once.
  show(MODEL, { again: true });
  assert.equal(text(lede()), '3 things need your attention. Everything else looks fine: 3 clients, 4 projects.');
  assert.equal(ledeText({ attention: 1, clients: 1, projects: 1 }), '1 thing needs your attention. Everything else looks fine: 1 client, 1 project.');
  assert.equal(ledeText({ attention: 0, clients: 3, projects: 4 }), 'Everything looks fine: 3 clients, 4 projects.');
  // The scope bar: All projects with the layers icon, or the project in the accent.
  const scope = byClass(main, 'scope-bar')[0];
  assert.equal(text(scope), 'All projects');
  assert.equal(scope.children[0].dataset.icon, 'layers');
  assert.equal(hintLine.hidden, false);
  assert.equal(hintLine.children.at(-1).textContent, 'Hover a card to see it on the map · a button adds a preview · click Kitden gateway or Library to open it');
});

test('a picked project shows its name in the scope bar', () => {
  data.projects = [{ id: 'p1', path: '/work/website', exists: true }];
  state.project = 'p1';
  try {
    current = MODEL;
    Object.assign(data, { overview: structuredClone(MODEL), clients: [{ status: 'found' }], projects: [{ id: 'p1', path: '/work/website', exists: true }] });
    data.scope.overview = 'p1';
    main.replaceChildren();
    renderOverview(main, { again: true });
    const scope = byClass(main, 'scope-bar')[0];
    assert.equal(text(scope), 'Project website');
    assert.ok(scope.classList.contains('project'));
    assert.equal(scope.children[0].dataset.icon, 'folder');
  } finally {
    state.project = '';
  }
});

test('a card shows its icon, name, line, client tiles and one button', () => {
  show(MODEL, { again: true });
  const move = card('m1');
  const [tile, words_, who, action] = move.children;
  assert.ok(tile.classList.contains('itile'));
  assert.equal(tile.children[0].dataset.icon, 'globe');
  assert.deepEqual(words_.children.map((n) => n.textContent), ['analytics', SKIPS]);
  assert.deepEqual(who.children.map((n) => n.title), ['Codex']);
  assert.equal(words(action), 'Move in…');
  // A plain button where it can improve, the primary one where it needs attention.
  assert.equal(action.className, 'btn');
  assert.equal(cardButton('dup').className, 'btn primary');
  assert.equal(words(cardButton('dup')), 'Keep one…');
  // A statement has no button; a client's card has the client's mark as its tile.
  assert.equal(cardButton('unread'), null);
  assert.equal(card('unread').children.length, 3);
  assert.equal(card('conn').children[0].title, 'Cursor');
  // The two groups, in order, each with its caption.
  const captions = byClass(main, 'ov-cap').map(text);
  assert.deepEqual(captions, ['Needs attention', 'Can improve', 'Your setup']);
  const [need, can] = byClass(main, 'ov-cap');
  assert.equal(need.children[0].dataset.icon, 'triangle-alert');
  assert.equal(can.children[0].dataset.icon, 'sparkles');
});

test('a group with no card hides its caption', () => {
  show({ ...MODEL, cards: CARDS.filter((c) => c.group === 'improve'), counts: { ...MODEL.counts, attention: 0 } }, { again: true });
  assert.deepEqual(byClass(main, 'ov-group').filter((n) => !n.hidden).map((n) => text(n.children[0])), ['Can improve']);
  assert.equal(text(lede()), 'Everything looks fine: 3 clients, 4 projects.');
});

test('Move in… adds its row; the button says In preview while it waits', async () => {
  show(MODEL, { again: true });
  queue(PREVIEW, batch('c1'));
  fire(cardButton('m1'), 'click');
  await flush();
  assert.deepEqual(tray.rows.map((row) => row.key), [keyFor(MOVE('a1'))]);
  assert.equal(words(cardButton('m1')), 'In preview');
  assert.equal(cardButton('m1').getAttribute('aria-disabled'), 'true');
  // Nothing is written: only the preview was asked for.
  assert.ok(!asked.some((url) => url.includes('/apply')));
  // A card drawn again while it waits still says so.
  show(MODEL, { again: true });
  assert.equal(words(cardButton('m1')), 'In preview');
  await cancelTray();
  assert.equal(words(cardButton('m1')), 'Move in…');
  assert.equal(cardButton('m1').getAttribute('aria-disabled'), null);
});

test('Connect… adds the connect row with the kitden entry note', async () => {
  show(MODEL, { again: true });
  queue(PREVIEW, batch('c2'));
  fire(cardButton('conn'), 'click');
  await flush();
  assert.deepEqual(tray.rows.map((row) => [row.key, Boolean(row.note)]), [[keyFor(CONNECT), true]]);
  await cancelTray();
});

// Update… on the Old Kitden card, applied and checked. Resolves when the tray says "applied".
async function applyUpdate() {
  show(MODEL, { again: true });
  queue(PREVIEW, batch('c3'));
  fire(cardButton('old'), 'click');
  await flush();
  queue('/api/changes/c3/apply', { status: 200, json: { id: 'c3', state: 'verified', action: 'batch', steps: [] } });
  await applyTray();
  assert.equal(tray.phase, 'applied');
}

test('after Apply is verified the card leaves and the count rolls; Undo brings it back', async () => {
  await applyUpdate();
  const old = card('old');
  // Applied, but the page has not read the result yet: the card stays as it is.
  assert.deepEqual(old.animations, []);
  // The page reads the result after Apply: the card is gone from it, so it leaves.
  show(without('old', 2), { again: true });
  assert.equal(card('old'), old);
  const [out] = old.animations;
  assert.deepEqual(out.keyframes, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateX(28px)' }]);
  assert.deepEqual([out.options.duration, out.options.easing, out.options.fill], [180, 'ease-in', 'forwards']);
  // Its button no longer follows the tray, so it does not change while it leaves.
  assert.equal(cardButton('old').dataset.tray, undefined);
  await flush();
  const [, collapse] = old.animations;
  assert.deepEqual(collapse.keyframes.at(-1), { height: '0px', paddingTop: '0px', paddingBottom: '0px', borderTopWidth: '0px', borderBottomWidth: '0px', marginBottom: '-8px' });
  assert.deepEqual([collapse.options.duration, collapse.options.easing], [160, 'cubic-bezier(.2,.8,.2,1)']);
  await flush();
  assert.equal(card('old'), null);
  // The count rolled from 3 to 2: the old number leaves and the new one comes in.
  const need = lede().children[0];
  assert.deepEqual(need.children.map((n) => n.textContent), ['3', '2']);
  assert.deepEqual(need.children[0].animations[0].keyframes.at(-1), { transform: 'translateY(70%)', opacity: 0 });
  endApplied();
  // Undo: the page reads the card again, and it comes back.
  show(MODEL, { again: true });
  const back = card('old');
  assert.notEqual(back, old);
  assert.deepEqual(back.animations.map((a) => [a.keyframes, a.options.duration]), [[[{ opacity: 0, transform: 'translateY(-8px) scale(0.98)' }, { opacity: 1, transform: 'none' }], 220]]);
  // A later draw does not bring it back again.
  show(MODEL, { again: true });
  assert.deepEqual(card('old').animations, []);
});

test('no sibling slides after a card collapses', async () => {
  await applyUpdate();
  show(without('old', 2), { again: true });
  const siblings = ['unread', 'dup'].map(card);
  await flush();
  assert.equal(card('old'), null);
  for (const node of siblings) assert.deepEqual(node.animations, []);
  endApplied();
  show(MODEL, { again: true });
});

test('a card the page still reads after Apply stays', async () => {
  await applyUpdate();
  show(MODEL, { again: true });
  await flush();
  assert.ok(card('old'));
  assert.deepEqual(card('old').animations, []);
  endApplied();
});

test('three server cards and one more card', async () => {
  // Review Focus: past three servers that skip the gateway, one card says how many more.
  show(MODEL, { again: true });
  const can = CARDS.filter((c) => c.group === 'improve').map((c) => [card(c.id).children[1].children[0].textContent, words(cardButton(c.id))]);
  assert.deepEqual(can, [['analytics', 'Move in…'], ['github', 'Move in…'], ['notes', 'Move in…'], ['4 more servers skip the gateway', 'Show…'], ['Cursor', 'Connect…']]);
  // Show… opens the Gateway's List at the outside group.
  fire(cardButton('more'), 'click');
  await flush();
  assert.deepEqual([state.view, state.mode, state.selected], ['gateway', 'list', { kind: 'group', name: 'outside' }]);
  state.view = 'overview';
  state.selected = null;
  state.mode = '';
});

test('hover or focus on a card focuses the setup map on its path', () => {
  show(MODEL, { again: true });
  const box = setupBox();
  fire(card('m1'), 'pointerenter');
  assert.ok(box.classList.contains('focus'));
  assert.deepEqual(['client:codex', 'gateway', 'client:cursor', 'library'].map((id) => block(id).classList.contains('lit')), [true, true, false, false]);
  fire(card('m1'), 'pointerleave');
  assert.ok(!box.classList.contains('focus'));
  // Keyboard focus does the same.
  fire(card('dup'), 'focusin');
  assert.deepEqual(['client:cursor', 'library', 'gateway'].map((id) => block(id).classList.contains('lit')), [true, true, false]);
  fire(card('dup'), 'focusout', { relatedTarget: null });
  assert.ok(!box.classList.contains('focus'));
  // The path: the card's clients, its block, and the links between them that exist.
  const model = setupTree(MAP, null);
  assert.deepEqual([...setupPath(model, { clients: ['claude_code', 'cursor'], block: 'gateway' })].sort(), ['client:claude_code', 'client:claude_code>gateway', 'client:cursor', 'gateway']);
  assert.deepEqual([...setupPath(model, { clients: ['cursor'], block: null })], ['client:cursor']);
});

test('the notes fold opens and closes and is hidden at 0', async () => {
  queue('/api/findings', { status: 200, json: [
    { type: 'same_name_other_source', severity: 'info', names: ['docs'], items: ['i1'], clients: ['codex'] },
    { type: 'bypasses_gateway', severity: 'info', names: ['docs'], items: ['i1'], clients: ['codex'] },
    { type: 'cross_loaded', severity: 'info', names: ['tidy'], items: ['i2'], clients: ['cursor'] },
    { type: 'duplicate_in_client', severity: 'warning', names: ['x'], items: ['i3'], clients: ['cursor'] },
  ] });
  show(MODEL, { again: true });
  const fold = byClass(main, 'ov-fold')[0];
  const box = byClass(main, 'ov-notes')[0];
  assert.equal(text(fold), 'Show 3 notes (nothing to fix)');
  assert.equal(fold.getAttribute('aria-expanded'), 'false');
  assert.equal(fold.children[0].dataset.icon, 'chevron-right');
  assert.equal(box.hidden, true);
  fire(fold, 'click');
  assert.equal(text(fold), 'Hide 3 notes');
  assert.equal(fold.getAttribute('aria-expanded'), 'true');
  assert.equal(box.hidden, false);
  assert.deepEqual(box.animations[0].keyframes[0], { height: '0px', opacity: 0 });
  assert.equal(box.animations[0].options.duration, 280);
  await flush();
  // One plain sentence per item, with the info icon; a warning is no note.
  assert.deepEqual(box.children.map(text), ['docs has the same name as an entry from another source and is not connected to the gateway.', 'tidy loads from another client.']);
  assert.equal(box.children[0].children[0].dataset.icon, 'info');
  assert.ok(box.children.every((n) => n.animations.length === 1 && n.animations[0].options.duration === 260));
  fire(fold, 'click');
  assert.equal(text(fold), 'Show 3 notes (nothing to fix)');
  assert.deepEqual(box.animations.at(-1).keyframes.at(-1), { height: '0px', opacity: 0 });
  assert.deepEqual([box.animations.at(-1).options.duration, box.animations.at(-1).options.easing], [220, 'ease-in']);
  await flush();
  assert.equal(box.hidden, true);
  // At 0 notes there is no fold.
  show({ ...MODEL, notes: 0 }, { again: true });
  assert.equal(byClass(main, 'ov-fold').length, 0);
});

test('the setup map draws clients, Kitden gateway and Library with their counts and the foot', () => {
  show(MODEL, { again: true });
  const model = setupTree(MAP, null);
  assert.deepEqual(model.blocks.map((b) => [b.id, b.name, b.meta]), [
    ['client:claude_code', 'Claude Code', '2.1.283'],
    ['client:codex', 'Codex', '0.159.2'],
    ['client:cursor', 'Cursor', '3.21.16'],
    ['gateway', 'Kitden gateway', '2 servers · 7 tools'],
    ['library', 'Library', '4 plugins · 7 skills'],
  ]);
  // The decided places: clients at x 0 (160 x 54), the two pages at x 250 (220 x 60).
  const at = (id) => { const [x, y] = block(id).style.translate.split(' ').map(parseFloat); return [x, y, parseFloat(block(id).style.width), parseFloat(block(id).style.height)]; };
  assert.deepEqual(at('client:claude_code'), [0, 22, 160, 54]);
  assert.deepEqual(at('client:cursor'), [0, 166, 160, 54]);
  assert.deepEqual(at('gateway'), [250, 40, 220, 60]);
  assert.deepEqual(at('library'), [250, 148, 220, 60]);
  // The page blocks carry their icon tile and the arrow; links have no ×.
  assert.ok(walk(block('gateway')).some((n) => n.dataset.icon === 'house'));
  assert.ok(walk(block('library')).some((n) => n.dataset.icon === 'library'));
  assert.ok(walk(block('gateway')).some((n) => n.dataset.icon === 'arrow-up-right'));
  assert.equal(walk(setupBox()).filter((n) => n.dataset.focus && n.dataset.focus.startsWith('link:')).length, 0);
  const foot = byClass(main, 'ov-foot')[0];
  assert.equal(text(foot), '4 projects · 3 have their own rules');
  assert.equal(foot.children[0].dataset.icon, 'folder');
  assert.equal(footWords(1, 1), '1 project · 1 has its own rules');
  // A client not on this Mac is off and says so.
  const off = setupTree({ ...MAP, clients: [{ id: 'codex', name: 'Codex', version: null, tested: true, on: false }] }, null);
  assert.deepEqual([off.blocks[0].meta, off.blocks[0].lamp], ['Not found', 'off']);
});

test('the Kitden gateway and Library blocks open their pages; a client block focuses its links', async () => {
  show(MODEL, { again: true });
  fire(block('client:claude_code'), 'click');
  assert.ok(setupBox().classList.contains('focus'));
  assert.deepEqual(['client:claude_code', 'gateway', 'library', 'client:codex'].map((id) => block(id).classList.contains('lit')), [true, true, true, false]);
  fire(block('gateway'), 'click');
  assert.equal(state.view, 'gateway');
  show(MODEL, { again: true });
  fire(block('library'), 'click');
  assert.equal(state.view, 'library');
  state.view = 'overview';
  state.mode = '';
});

test('a note opens its item, as before', () => {
  const finding = { type: 'unknown_state', names: ['a', 'b'], items: ['ia', 'ib'], clients: ['codex'], severity: 'info' };
  const rows = [
    { key: 'ra', kind: 'plugin', name: 'a', lookup: 'a', cells: { codex: { items: ['ia'] } } },
    { key: 'rb', kind: 'plugin', name: 'b', lookup: 'b', cells: { codex: { items: ['ib'] } } },
  ];
  const [first, second] = noteGroups([finding]);
  assert.equal(noteItemRow(first, rows).key, 'ra');
  assert.equal(noteItemRow(second, rows).key, 'rb');
  assert.equal(noteItemRow(second, rows.slice(0, 1)), null);
  assert.deepEqual(targetSel({ view: 'map', kind: 'skill', name: 'tidy' }), { kind: 'skill', name: 'tidy' });
  assert.equal(noteSentence(first), 'a has an on/off state Kitden cannot read.');
});

test('notes are grouped by item, each with its clients', () => {
  const note = (type, names, clients) => ({ type, names, clients, items: ['i'], severity: 'info' });
  const groups = noteGroups([
    note('same_name_other_source', ['docs', 'docs'], ['claude_code', 'codex']),
    note('bypasses_gateway', ['docs'], ['claude_code']),
    note('bypasses_gateway', ['docs'], ['codex']),
    note('unknown_state', ['a', 'b'], ['codex']),
  ]);
  assert.deepEqual(groups.map((g) => [g.name, g.clients, g.notes.length]), [
    ['docs', ['claude_code', 'codex'], 2],
    ['a', ['codex'], 1],
    ['b', ['codex'], 1],
  ]);
  assert.equal(groups[0].first.type, 'same_name_other_source');
});

test('with no client found the Overview says so', () => {
  current = MODEL;
  Object.assign(data, { overview: structuredClone(MODEL), clients: [{ status: 'not_found' }], projects: [] });
  data.scope.overview = '';
  main.replaceChildren();
  renderOverview(main, { again: true });
  assert.equal(main.children[0].textContent, 'No clients found');
  assert.equal(byClass(main, 'lede').length, 0);
  assert.ok(walk(main).some((n) => n.textContent === 'Kitden found no AI coding clients.'));
});

test('under reduced motion everything lands at once', async () => {
  reduced = true;
  try {
    // The count-up shows the number at once.
    const number = element('SPAN');
    countUp(number, 12, { dur: 700, delay: 200 });
    assert.equal(number.textContent, '12');
    assert.equal(frames.length, 0);
    // A new visit: nothing rises; the map shows at once.
    show(MODEL);
    assert.ok(walk(main).every((n) => n.animations.length === 0), 'nothing animates');
    // A card that leaves is gone at once, and one that comes back shows at once.
    await applyUpdate();
    show(without('old', 2), { again: true });
    await flush();
    assert.equal(card('old'), null);
    endApplied();
    show(MODEL, { again: true });
    assert.deepEqual(card('old').animations, []);
    // The notes open and close at once.
    queue('/api/findings', { status: 200, json: [] });
    const fold = byClass(main, 'ov-fold')[0];
    const box = byClass(main, 'ov-notes')[0];
    fire(fold, 'click');
    assert.deepEqual(box.animations, []);
    fire(fold, 'click');
    await flush();
    assert.equal(box.hidden, true);
  } finally {
    reduced = false;
  }
});
