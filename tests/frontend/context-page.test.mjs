import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';

// The Context page drawn in a small browser: the title, the lede, the client chips with their
// lamps, the window cards and the verdict, all from /api/context as the server writes it.
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

const { renderContext } = await import('../../src/kitden/web/static/js/context.js');
const { arrival, data, loadContext, reload, setRenderer, state } = await import('../../src/kitden/web/static/js/store.js');

const STATIC = new URL('../../src/kitden/web/static/', import.meta.url);
const LEDE = 'Every chat starts with a list of your skills. The agent reads it to choose the right skill.';
const NO_CHECK = 'Kitden cannot check its estimate against your last chat, so it shows none.';

// A window card as the server gives it (views/context_view.py).
function window(title, models, tag, short, say, { budget = 30000, misfit = null, room = null } = {}) {
  return { title, models, tag, budget, result: { short, say, sent: {}, over: {}, used: 100, size: 100, room, misfit } };
}
const CLAUDE = {
  client: 'claude_code', lamp: 'ok', lede: `${LEDE} Claude Code lets this list use 1% of the context window.`, message: null, unit: 'characters', checked: true,
  fact: { date: 'Nov 6', surface: 'in the Claude app', folder: '/work/a', version: '2.1.311' },
  windows: [
    window('1M window', 'Opus 5.5 · in the Claude app', 'Last chat · Nov 6', 'All 3 sent', 'In your last chat on Nov 6, all 3 skills were sent with their descriptions.', { room: 'Estimate: about 3,116 characters left before the limit.' }),
    window('200K window', 'Older models', 'Estimate', 'All 3 would be sent', 'Estimate: On a 200K window, every skill would keep its description.', { budget: 8000 }),
  ],
  sides: ['Description sent', 'Name only'], skills: [], after: null, how: [],
};
const CODEX = {
  client: 'codex', lamp: 'warn', lede: `${LEDE} Codex lets this list use 2% of the context window.`, message: null, unit: 'tokens', checked: true,
  fact: { date: 'Oct 30', surface: null, folder: '/work/a', version: '0.163.0' },
  windows: [
    window('272K window', 'gpt-6-astra', 'Last chat · Oct 30', '3 cut short', 'In your last chat on Oct 30, Codex cut 3 of 9 descriptions short.', { budget: 5440, misfit: { kind: 'cut', n: 3 } }),
  ],
  sides: ['Full description', 'Cut short'], skills: [], after: null, how: [],
};
// Codex when the files of the skills it sent cannot be found: the server cannot tell.
const UNKNOWN = {
  ...CODEX, lamp: 'none', checked: false,
  windows: [window('272K window', 'gpt-6-astra', 'Last chat · Oct 29', '58 sent', 'In your last chat on Oct 29, Codex sent 58 skills. Kitden cannot find all their files, so it cannot tell if any were cut.', { budget: 5440 })],
};
const CURSOR = {
  client: 'cursor', lamp: 'none', lede: `${LEDE} Cursor does not publish a limit for this list.`,
  message: 'Kitden cannot see what Cursor sends, so it cannot tell if your skills fit.', unit: 'characters', checked: false, fact: null,
  windows: [], sides: ['The agent can pick it', 'Only when you ask'], skills: [], after: null, how: [],
};
const answer = (...clients) => ({ project: null, clients: structuredClone(clients) });

const main = pages['#main'];
// The page as app.js draws it: the main box emptied, then Context drawn into it.
let shownAt = null;
function show(context = answer(CLAUDE, CODEX, CURSOR), { again = false } = {}) {
  data.context = context;
  data.scope.context = state.project;
  delete data.errors.context;
  state.view = 'context';
  shownAt = 'context';
  main.replaceChildren();
  renderContext(main, { again });
}
setRenderer(() => { if (state.view === 'context') show(data.context, { again: shownAt === 'context' }); });

const byClass = (root, name) => walk(root).filter((n) => n.classList.contains(name));
const chips = () => byClass(main, 'ctx-client');
const cards = () => byClass(main, 'ctx-win');
const verdict = () => byClass(main, 'ctx-verdict')[0];
const chipFor = (name) => chips().find((n) => text(n).startsWith(name));
const lampOf = (node) => byClass(node, 'lamp')[0];

async function fresh() {
  reduced = true;
  replies.clear();
  asked.length = 0;
  state.view = 'context';
  state.project = '';
  state.selected = null;
  arrival.pending = false;
  data.context = null;
  data.errors = {};
  data.scope = {};
  shownAt = null;
}

test('the rail has Context after Library, drawn with the gauge', () => {
  const html = readFileSync(new URL('index.html', STATIC), 'utf8');
  const links = [...html.matchAll(/<a href="#(\w+)" data-view="(\w+)"><span class="label">(\w+)<\/span>/g)].map((m) => m[3]);
  assert.deepEqual(links.slice(0, 4), ['Overview', 'Library', 'Context', 'Gateway']);
  assert.match(html, /<a href="#context" data-view="context"><span class="label">Context<\/span><\/a>/);
  const app = readFileSync(new URL('js/app.js', STATIC), 'utf8');
  assert.match(app, /\.nav \[data-view="context"\]'\)\.prepend\(icon\("gauge"\)\)/);
  assert.match(app, /context: \{ title: "Context", render: renderContext \}/);
  assert.match(app.split('const PROJECT_PLACES')[1].split('\n')[0], /"context"/);
});

test('the page draws the title, the lede, the clients, the windows and the verdict', async () => {
  await fresh();
  show();
  assert.equal(main.children[0].tagName, 'H1');
  assert.equal(text(main.children[0]), 'Do your skills fit?');
  // Codex is the first client whose lamp is amber, so it shows.
  assert.equal(text(byClass(main, 'lede')[0]), CODEX.lede);
  assert.deepEqual(chips().map((n) => text(n)), ['Claude Code', 'Codex', 'Cursor']);
  assert.deepEqual(chips().map((n) => lampOf(n).className), ['lamp on', 'lamp warn', 'lamp']);
  assert.deepEqual(chips().map((n) => n.getAttribute('aria-pressed')), ['false', 'true', 'false']);
  assert.deepEqual(chips().map((n) => byClass(n, 'client-mark').length), [1, 1, 1]);
  assert.equal(cards().length, 1);
  const card = cards()[0];
  assert.deepEqual(['b', 'em', 'small'].map((tag) => text(walk(card).find((n) => n.tagName === tag.toUpperCase()))), ['272K window', 'Last chat · Oct 30', 'gpt-6-astra']);
  assert.equal(text(byClass(card, 'ctx-short')[0]), '3 cut short');
  assert.equal(lampOf(card).className, 'lamp warn');
  assert.equal(text(verdict()), 'In your last chat on Oct 30, Codex cut 3 of 9 descriptions short.');
});

test('the address picks the client; with nothing amber it is Claude Code', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show();
  assert.equal(chipFor('Claude Code').getAttribute('aria-pressed'), 'true');
  assert.equal(text(byClass(main, 'lede')[0]), CLAUDE.lede);
  assert.deepEqual(cards().map((n) => text(byClass(n, 'ctx-short')[0])), ['All 3 sent', 'All 3 would be sent']);
  assert.deepEqual(cards().map((n) => lampOf(n).className), ['lamp on', 'lamp on']);
  assert.equal(text(verdict()), 'In your last chat on Nov 6, all 3 skills were sent with their descriptions.');
  // A name that is no client falls back to the default.
  await fresh();
  state.selected = { kind: 'client', name: 'nobody' };
  show();
  assert.equal(chipFor('Codex').getAttribute('aria-pressed'), 'true');
  await fresh();
  show(answer(CLAUDE, { ...CODEX, lamp: 'ok' }, CURSOR));
  assert.equal(chipFor('Claude Code').getAttribute('aria-pressed'), 'true');
});

test('a client chip shows that client and writes it in the address', async () => {
  await fresh();
  show();
  await fire(chipFor('Cursor'), 'click');
  assert.deepEqual(state.selected, { kind: 'client', name: 'cursor' });
  assert.equal(chipFor('Cursor').getAttribute('aria-pressed'), 'true');
  assert.equal(text(byClass(main, 'lede')[0]), CURSOR.lede);
});

test('a client with no windows says its message as the verdict', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'cursor' };
  show();
  assert.equal(cards().length, 0);
  assert.equal(text(verdict()), CURSOR.message);
  assert.equal(byClass(main, 'ctx-note').length, 0);
});

test('a window card shows its own result and keeps the choice across a redraw', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show();
  assert.deepEqual(cards().map((n) => n.getAttribute('aria-pressed')), ['true', 'false']);
  await fire(cards()[1], 'click');
  assert.deepEqual(cards().map((n) => n.getAttribute('aria-pressed')), ['false', 'true']);
  assert.equal(text(verdict()), 'Estimate: On a 200K window, every skill would keep its description.');
  assert.equal(text(byClass(verdict(), 'ctx-est')[0]), 'Estimate:');
  show(data.context, { again: true });
  assert.equal(cards()[1].getAttribute('aria-pressed'), 'true');
  // Another client starts on its first window.
  await fire(chipFor('Codex'), 'click');
  assert.equal(cards()[0].getAttribute('aria-pressed'), 'true');
});

test('a message beside windows is a quiet note under the verdict', async () => {
  await fresh();
  const unchecked = { ...CLAUDE, checked: false, message: NO_CHECK, windows: [CLAUDE.windows[0]] };
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer(unchecked, CODEX, CURSOR));
  assert.equal(cards().length, 1);
  assert.equal(text(verdict()), CLAUDE.windows[0].result.say);
  assert.equal(text(byClass(main, 'ctx-note')[0]), NO_CHECK);
});

test('the page waits with a skeleton, says when the read failed, and uses up the arrival', async () => {
  await fresh();
  arrival.pending = true;
  state.selected = { kind: 'client', name: 'codex' };
  main.replaceChildren();
  renderContext(main);
  assert.equal(text(main.children[0]), 'Do your skills fit?');
  assert.equal(byClass(main, 'skeleton').length > 0, true);
  assert.equal(arrival.pending, false);
  data.errors.context = new Error('down');
  data.errorScope.context = '';
  main.replaceChildren();
  renderContext(main);
  assert.match(text(byClass(main, 'banner')[0]), /^Could not load the skill check\./);
  assert.equal(byClass(main, 'skeleton').length, 0);
});

test('loadContext reads the picked project, and a reload reads it only while Context shows', async () => {
  await fresh();
  queue('/api/context', { status: 200, json: answer(CLAUDE) });
  await loadContext();
  assert.deepEqual(asked.map((a) => a.url), ['/api/context']);
  assert.equal(data.context.clients[0].client, 'claude_code');
  state.project = 'p1';
  queue('/api/context?project=p1', { status: 200, json: answer(CODEX) });
  await loadContext();
  assert.equal(data.context.clients[0].client, 'codex');
  assert.equal(data.scope.context, 'p1');
  state.project = '';
  asked.length = 0;
  state.view = 'overview';
  await reload();
  assert.equal(asked.some((a) => a.url.startsWith('/api/context')), false);
  state.view = 'context';
  await reload();
  assert.equal(asked.some((a) => a.url.startsWith('/api/context')), true);
});

test('the last chat\'s window takes the client\'s lamp, so "cannot tell" is never green', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'codex' };
  show(answer(CLAUDE, UNKNOWN, CURSOR));
  assert.equal(lampOf(chipFor('Codex')).className, 'lamp');
  assert.equal(lampOf(cards()[0]).className, 'lamp');
  // An estimate keeps its own lamp.
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer({ ...CLAUDE, lamp: 'warn' }, UNKNOWN, CURSOR));
  assert.deepEqual(cards().map((n) => lampOf(n).className), ['lamp warn', 'lamp on']);
});

test('the room left shows under the verdict with the Estimate start marked', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show();
  await fire(cards()[0], 'click'); // the page keeps the window picked in an earlier test
  const room = byClass(main, 'ctx-room')[0];
  assert.equal(text(room), 'Estimate: about 3,116 characters left before the limit.');
  assert.equal(text(byClass(room, 'ctx-est')[0]), 'Estimate:');
  const order = main.children.filter((n) => n.classList.contains('ctx-verdict') || n.classList.contains('ctx-room'));
  assert.deepEqual(order.map((n) => n.className), ['ctx-verdict', 'ctx-room']);
  // The other window has no room sentence.
  await fire(cards()[1], 'click');
  assert.equal(byClass(main, 'ctx-room').length, 0);
});

test('the chips and the window cards are real buttons, named and pressed by click', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show();
  for (const node of [...chips(), ...cards()]) {
    assert.equal(node.tagName, 'BUTTON');
    assert.equal(node.type, 'button');
  }
  assert.deepEqual(chips().map((n) => n.getAttribute('aria-label')), ['Claude Code', 'Codex', 'Cursor']);
  // A button answers Enter and Space with a click; one click picks.
  await fire(chipFor('Codex'), 'click');
  assert.equal(chipFor('Codex').getAttribute('aria-pressed'), 'true');
  assert.equal(chipFor('Claude Code').getAttribute('aria-pressed'), 'false');
});
