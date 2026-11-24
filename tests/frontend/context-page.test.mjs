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
const { cancelTray, CONTEXT_NOTE, tray } = await import('../../src/kitden/web/static/js/tray.js');
const { closePanel } = await import('../../src/kitden/web/static/js/panel.js');
const { syncTray } = await import('../../src/kitden/web/static/js/details.js');

const STATIC = new URL('../../src/kitden/web/static/', import.meta.url);
const LEDE = 'Every chat starts with a list of your skills. The agent reads it to choose the right skill.';
const NO_CHECK = 'Two limits give the list of your last chat, so Kitden shows no estimate.';

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
  windows: [window('272K window', 'gpt-6-astra', 'Last chat · Oct 29', '58 sent', 'In your last chat on Oct 29, Codex sent 58 skills. A file is gone or was changed after the chat, so Kitden cannot tell if any were cut.', { budget: 5440 })],
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
  // The tray empties while another page shows, so the page reads nothing for it.
  state.view = 'overview';
  await cancelTray();
  closePanel({ instant: true });
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
  assert.equal(main.children[0].className, 'page-head');
  assert.equal(main.children[0].children[0].tagName, 'H1');
  assert.equal(text(main.children[0].children[0]), 'Do your skills fit?');
  assert.deepEqual(byClass(main.children[0], 'head-actions')[0].children.map((n) => text(n)), ['Choose clients…']);
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
  assert.equal(text(main.children[0].children[0]), 'Do your skills fit?');
  assert.equal(main.children[0].children.length, 2);
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


// The picture, the switches and the estimate after Apply ------------------------------------

// A skill as the server gives it (views/context_view.py `_skill`).
const skill = (name, size, side, extra = {}) => ({
  name, shown: name, item: `id-${name}`, project: null, source: 'Your skills', size, side, state: 'on',
  switch: ['on', 'name-only', 'off'], note: 'Name only frees 2 characters. The agent no longer sees when to use it.', ...extra,
});
// Claude Code on a 200K window: alpha and beta sent, gamma only a name.
const TIGHT = {
  ...CLAUDE, lamp: 'warn',
  windows: [{
    title: '200K window', models: 'Sonnet 4.6 · in the terminal', tag: 'Last chat · Nov 7', budget: 8000,
    result: {
      short: '1 of 3 showed only a name', say: 'In your last chat on Nov 7, 1 of 3 skills showed only a name. The agent may not have used them.',
      sent: { alpha: 4000, beta: 2000 }, over: { gamma: 3000 }, used: 6100, size: 9100, room: null, misfit: { kind: 'name', n: 1 },
    },
  }],
  skills: [skill('alpha', 3990, 0), skill('beta', 1990, 0), skill('gamma', 2998, 1)],
  how: ['Last chat: the list Claude Code 2.1.311 sent on Nov 7 in the terminal, read from its chat log.', 'The rest of the window (system prompt, tools, MCP, the chat) is not measured.'],
};
// After Apply with gamma set to Name only (a made-up answer: the page only places it).
const AFTER = {
  say: 'After Apply, estimate: On a 200K window, 1 of 3 skills would show only a name. The agent may not use them. beta loses its description.',
  gets: [], loses: ['beta'],
  result: { short: '', say: '', sent: { alpha: 4000 }, over: { beta: 1992 }, used: 4200, size: 6192, room: null },
};
const DRAFT_URL = `/api/context?draft=${encodeURIComponent(JSON.stringify({ claude_code: { gamma: 'name-only' } }))}`;
const PREVIEW = '/api/batch/preview';
const previewed = (id) => (sent) => ({
  status: 200,
  json: { id, action: 'skill.rule', state: 'previewed', steps: [], after: [], target: {}, rows: sent.requests.map((r) => ({ id: r.id, kind: r.kind, steps: [], target: {}, after: [] })) },
});

const pieces = (kind) => byClass(main, 'ctx-seg').filter((n) => n.classList.contains(kind));
const pieceOf = (name, kind = 'sent') => pieces(kind).find((n) => n.dataset.skill === name);
const sides = () => byClass(main, 'ctx-side');
const pills = (root = main) => byClass(root, 'ctx-pill');
const pillOf = (name) => pills().find((n) => n.dataset.skill === name);
const width = (node) => parseFloat(node.style.width);
const drawer = pages['#drawer'];
const buttonIn = (root, label) => walk(root).find((n) => n.tagName === 'BUTTON' && text(n) === label);

test('the zoom bar has a piece per skill as wide as what was sent, the limit and the hatched rest', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer(TIGHT, CODEX, CURSOR));
  // The scale is the limit plus what did not fit: 8,000 + 3,000.
  assert.equal(width(pieceOf('alpha')).toFixed(3), (4000 / 11000 * 100).toFixed(3));
  assert.equal((width(pieceOf('alpha')) / width(pieceOf('beta'))).toFixed(3), '2.000');
  assert.equal(pieceOf('gamma'), undefined);
  // The names (the list's other characters) are one piece: 6,100 - 6,000.
  assert.equal(width(pieces('names')[0]).toFixed(3), (100 / 11000 * 100).toFixed(3));
  const over = pieceOf('gamma', 'over');
  assert.equal(parseFloat(over.style.left).toFixed(3), (8000 / 11000 * 100).toFixed(3));
  const limit = byClass(main, 'ctx-limit')[0];
  assert.equal(parseFloat(limit.style.left).toFixed(3), (8000 / 11000 * 100).toFixed(3));
  assert.equal(text(byClass(main, 'ctx-flag')[0]), 'Limit: 8,000 characters');
  assert.deepEqual(byClass(main, 'ctx-chip').map(text), ['Sent', 'Over the limit: not sent']);
  // Codex cuts the rest off; a list that fits has room left.
  state.selected = { kind: 'client', name: 'codex' };
  show(answer(TIGHT, { ...CODEX, windows: [{ ...CODEX.windows[0], result: { ...CODEX.windows[0].result, sent: { a: 100 }, over: { a: 40 }, used: 300 } }] }, CURSOR));
  assert.equal(text(byClass(main, 'ctx-flag')[0]), 'Limit: 5,440 tokens');
  assert.deepEqual(byClass(main, 'ctx-chip').map(text), ['Sent', 'Over the limit: cut off']);
  state.selected = { kind: 'client', name: 'claude_code' };
  show();
  assert.deepEqual(byClass(main, 'ctx-chip').map(text), ['Sent', 'Free']);
  assert.equal(pieces('over').length, 0);
});

test('a client with no window shows no picture, only its two sides', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'cursor' };
  show(answer(CLAUDE, CODEX, { ...CURSOR, skills: [skill('pdf', 300, 0, { switch: [] }), skill('xlsx', 200, 1, { switch: [] })] }));
  assert.equal(byClass(main, 'ctx-zoom').length, 0);
  assert.deepEqual(sides().map((n) => text(n.children[0])), ['The agent can pick it', 'Only when you ask']);
  assert.deepEqual(sides().map((n) => pills(n).map((p) => p.dataset.skill)), [['pdf'], ['xlsx']]);
});

test('the two sides list the pills by side, and hovering one lights its piece and the other way', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer(TIGHT, CODEX, CURSOR));
  assert.deepEqual(sides().map((n) => text(n.children[0])), ['Description sent', 'Name only']);
  assert.deepEqual(sides().map((n) => pills(n).map((p) => p.dataset.skill)), [['alpha', 'beta'], ['gamma']]);
  assert.equal(text(pillOf('alpha')), 'alpha3,990');
  await fire(pillOf('beta'), 'mouseenter');
  assert.equal(pieceOf('beta').classList.contains('hot'), true);
  assert.equal(pillOf('beta').classList.contains('hot'), true);
  await fire(pillOf('beta'), 'mouseleave');
  assert.equal(pieceOf('beta').classList.contains('hot'), false);
  await fire(pieceOf('gamma', 'over'), 'mouseenter');
  assert.equal(pillOf('gamma').classList.contains('hot'), true);
  // One lit at a time.
  await fire(pieceOf('alpha'), 'mouseenter');
  assert.deepEqual(pills().filter((p) => p.classList.contains('hot')).map((p) => p.dataset.skill), ['alpha']);
});

test('the sides say what a pill number is, and a plugin skill shows its plugin first', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  const plugged = skill('venture:review', 464, 0, { shown: 'review', plugin: 'venture' });
  show(answer({ ...TIGHT, skills: [skill('alpha', 3990, 0), plugged, skill('gamma', 0, 1)] }, CODEX, CURSOR));
  const note = byClass(main, 'ctx-pillnote')[0];
  assert.equal(text(note), 'The number beside a skill is the length of its description, in characters.');
  // The line sits right above the two panels.
  assert.equal(note.parentNode.children.indexOf(note) + 1, note.parentNode.children.indexOf(byClass(main, 'ctx-sides')[0]));
  // The plugin is its own quiet part before the name; both are in the pill's words and its hover text.
  const pill = pillOf('venture:review');
  assert.equal(text(pill), 'venture:review464');
  assert.deepEqual(pill.children.slice(0, 2).map((n) => [n.className, n.textContent]), [['ctx-plug', 'venture:'], ['', 'review']]);
  assert.equal(pill.getAttribute('title'), 'venture:review');
  // A skill with no plugin is unchanged.
  assert.equal(text(pillOf('alpha')), 'alpha3,990');
  assert.equal(pillOf('alpha').getAttribute('title'), null);
  assert.equal(byClass(pillOf('alpha'), 'ctx-plug').length, 0);
  // No pill with a number: no line.
  show(answer({ ...TIGHT, skills: [skill('gamma', 0, 1)] }, CODEX, CURSOR));
  assert.equal(byClass(main, 'ctx-pillnote').length, 0);
});

test('a skill on the first side warms with its size against the largest there, pill and piece alike', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer(TIGHT, CODEX, CURSOR));
  const heat = (node) => node.style['--heat'];
  assert.deepEqual(['alpha', 'beta'].map((name) => [heat(pillOf(name)), heat(pieceOf(name))]), [['1.00', '1.00'], ['0.50', '0.50']]);
  // Name only stays grey: its pill and its piece past the limit.
  assert.equal(heat(pillOf('gamma')), undefined);
  assert.equal(heat(pieceOf('gamma', 'over')), undefined);
  // On a window where gamma is sent too, it warms against alpha.
  const wide = { ...TIGHT.windows[0], tag: 'Estimate', result: { ...TIGHT.windows[0].result, sent: { alpha: 4000, beta: 2000, gamma: 3000 }, over: {}, misfit: null } };
  show(answer({ ...TIGHT, windows: [TIGHT.windows[0], wide] }, CODEX, CURSOR));
  await fire(cards()[1], 'click');
  assert.equal(heat(pillOf('gamma')), '0.75');
  assert.equal(heat(pieceOf('gamma')), '0.75');
  await fire(cards()[0], 'click');
});

test('Details shows no size for a skill whose description Kitden could not read', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  const skills = [...TIGHT.skills.slice(0, 2), skill('gamma', 0, 1)];
  show(answer({ ...TIGHT, skills }, CODEX, CURSOR));
  await fire(pillOf('gamma'), 'click');
  assert.match(text(drawer), /SourceYour skills/);
  assert.doesNotMatch(text(drawer), /Size/);
});

test('a pill opens Details with the size, the source and the switch; Name only joins the tray', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer(TIGHT, CODEX, CURSOR));
  await fire(pillOf('gamma'), 'click');
  assert.match(text(drawer), /Size2,998 characters/);
  assert.match(text(drawer), /SourceYour skills/);
  assert.match(text(drawer), /Name only frees 2 characters\./);
  const switches = walk(drawer).filter((n) => n.dataset && n.dataset.state);
  assert.deepEqual(switches.map(text), ['On', 'Name only', 'Off']);
  assert.deepEqual(switches.map((n) => n.getAttribute('aria-pressed')), ['true', 'false', 'false']);
  assert.equal(pillOf('gamma').classList.contains('sel'), true);
  queue(PREVIEW, previewed('c1'));
  queue(DRAFT_URL, { status: 200, json: answer({ ...TIGHT, after: AFTER }, CODEX, CURSOR) });
  state.view = 'context';
  await fire(buttonIn(drawer, 'Name only'), 'click');
  await flush();
  await flush();
  const sent = asked.find((a) => a.url === PREVIEW).body.requests[0];
  assert.deepEqual([sent.kind, sent.targets, sent.params], ['skill.rule', [{ client: 'claude_code', item: 'id-gamma' }], { scope: 'all', state: 'name-only' }]);
  assert.equal(tray.rows[0].note, CONTEXT_NOTE);
  // The tray change asks for the estimate after Apply, and the page shows it.
  assert.equal(asked.some((a) => a.url === DRAFT_URL), true);
  assert.equal(text(verdict()), AFTER.say);
  assert.equal(text(byClass(verdict(), 'ctx-est')[0]), 'After Apply, estimate:');
  assert.equal(pillOf('beta').classList.contains('lost'), true);
  assert.equal(pillOf('gamma').classList.contains('chg'), true);
  // The bar and the sides follow the estimate: beta is now past the limit, gamma only a name.
  assert.equal(pieceOf('beta'), undefined);
  assert.notEqual(pieceOf('beta', 'over'), undefined);
  assert.deepEqual(sides().map((n) => pills(n).map((p) => p.dataset.skill)), [['alpha'], ['beta', 'gamma']]);
  // The switch shows the state waiting in the tray (the panel syncs it on each tray change).
  syncTray();
  const now = walk(drawer).filter((n) => n.dataset && n.dataset.state);
  assert.deepEqual(now.map((n) => n.getAttribute('aria-pressed')), ['false', 'true', 'false']);
});

// The skill list limit as the server offers it for TIGHT (specs skill-list-limit and
// limit-line-control): the places the limit line can go, today's first, with the server's words.
const steps = (from, ...more) => [from, ...more];
const STEPS = steps(
  { value: 0.01, limit: 8000, short: 1, say: '1% now · 1 of 3 show only a name', now: true },
  { value: 0.015, limit: 12000, short: 0, say: '1.5% · all 3 fit · about 3,000 more characters per chat' },
  { value: 0.02, limit: 16000, short: 0, say: '2% · all 3 fit · about 3,000 more characters per chat' },
  { value: 0.025, limit: 20000, short: 0, say: '2.5% · all 3 fit · about 3,000 more characters per chat' },
);
const LIMIT = {
  now: '1% of the context window: 8,000 characters',
  offer: { fraction: 0.015, label: 'Set to 1.5%', say: '1.5%: all 3 skills get their description', cost: 'About 3,000 more characters in every chat (about 750 tokens)' },
  back: null,
  note: 'Kitden writes it in your Claude Code user settings, for all projects. Your next chat will show the real list.',
  why: null,
  param: 'fraction',
  steps: STEPS,
};
const LIMIT_URL = `/api/context?draft=${encodeURIComponent(JSON.stringify({ limits: { claude_code: 0.015 } }))}`;
const LIMIT_AFTER = { ...AFTER, say: 'After Apply, estimate: On a 200K window, every skill would keep its description. gamma gets a description.', gets: ['gamma'], loses: [], budget: 12000 };
const EMPTY_URL = `/api/context?draft=${encodeURIComponent('{}')}`;
const grip = () => byClass(main, 'ctx-grip')[0];
const readout = () => byClass(main, 'ctx-readout')[0];
const nextLine = () => byClass(main, 'ctx-next')[0];
// The bar is 1200 px wide from x 0 (the stand-in's box): a pointer at `pct` % of it.
const at = (pct) => ({ button: 0, pointerId: 1, clientX: (pct / 100) * 1200 });
// The scale of TIGHT with the control: 12,000 (the suggested place) and room for the places past it,
// which share the rest of the bar up to 98%: 2% and 2.5% there.
const SCALE = 12000 * 1.3;
const spotOf = (limit) => (limit / SCALE) * 100;
const PAST = [spotOf(12000) + (98 - spotOf(12000)) / 2, 98];
async function drag(...points) {
  const node = grip();
  await fire(node, 'pointerdown', at(spotOf(8000)));
  for (const point of points) await fire(node, 'pointermove', at(point));
  return node;
}

test('the limit line is the control: a handle, a flag that opens Details, no button under the verdict', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  // Nothing to change: the line is only a picture.
  show(answer({ ...TIGHT, limit: { ...LIMIT, offer: null, steps: [] } }, CODEX, CURSOR));
  assert.equal(grip(), undefined);
  show(answer({ ...TIGHT, limit: LIMIT }, CODEX, CURSOR));
  assert.equal(walk(main).some((n) => n.tagName === 'BUTTON' && /limit/i.test(text(n))), false);
  const handle = grip();
  assert.equal(handle.getAttribute('role'), 'slider');
  assert.equal(handle.getAttribute('tabindex'), '0');
  assert.equal(handle.getAttribute('aria-label'), 'Skill list limit');
  assert.equal(handle.getAttribute('aria-valuetext'), '1% now · 1 of 3 show only a name');
  assert.equal(handle.style.left, `${spotOf(8000)}%`);
  assert.equal(nextLine().hidden, true);
  // A press with no move opens Details; so does the flag.
  await fire(handle, 'pointerdown', at(spotOf(8000)));
  await fire(handle, 'pointerup', { ...at(spotOf(8000)), type: 'pointerup' });
  assert.match(text(drawer), /Skill list limit/);
  assert.match(text(drawer), /Suggested1\.5%: all 3 skills get their description/);
  assert.match(text(drawer), /CostAbout 3,000 more characters in every chat \(about 750 tokens\)/);
  closePanel({ instant: true });
  const flag = byClass(main, 'ctx-flag')[0];
  assert.equal(flag.classList.contains('act'), true);
  await fire(flag, 'click');
  assert.match(text(drawer), /Now1% of the context window: 8,000 characters/);
});

test('a drag moves a next-chats line place by place with the server words, snaps, and a release adds the row', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer({ ...TIGHT, limit: LIMIT }, CODEX, CURSOR));
  const handle = await drag(spotOf(8000) + 0.2);
  // Under DRAG_START px: still a press, nothing moves.
  assert.equal(readout().hidden, true);
  await fire(handle, 'pointermove', at(spotOf(12000) - 2.5));
  // Within SNAP of the suggested place: it snaps there; the mark shows where it is.
  assert.equal(text(readout()), '1.5% · all 3 fit · about 3,000 more characters per chat');
  assert.equal(nextLine().hidden, false);
  assert.equal(nextLine().style.left, `${spotOf(12000)}%`);
  assert.equal(byClass(main, 'ctx-mark')[0].hidden, false);
  // The chat's own line stays where it was.
  assert.equal(byClass(main, 'ctx-limit')[0].style.left, `${spotOf(8000)}%`);
  // Past the suggested place the others share the bar's last part: 2%, then 2.5%.
  await fire(handle, 'pointermove', at(PAST[0]));
  assert.equal(text(readout()), '2% · all 3 fit · about 3,000 more characters per chat');
  await fire(handle, 'pointermove', at(PAST[1]));
  assert.equal(text(readout()), '2.5% · all 3 fit · about 3,000 more characters per chat');
  await fire(handle, 'pointermove', at(spotOf(12000) + 1));
  queue(PREVIEW, previewed('c1'));
  queue(LIMIT_URL, { status: 200, json: answer({ ...TIGHT, limit: LIMIT, after: LIMIT_AFTER }, CODEX, CURSOR) });
  state.view = 'context';
  await fire(handle, 'pointerup', { ...at(spotOf(12000) + 1), type: 'pointerup' });
  await flush();
  await flush();
  // The same row as Details' "Set to 1.5%", and no request while it moved.
  const previews = asked.filter((a) => a.url === PREVIEW);
  assert.equal(previews.length, 1);
  assert.deepEqual([previews[0].body.requests[0].kind, previews[0].body.requests[0].params], ['skill.limit', { fraction: 0.015 }]);
  assert.equal(tray.rows[0].note, CONTEXT_NOTE);
  // Drawn again from the tray: the next-chats line waits at 12,000, the chat's line at 8,000.
  assert.equal(nextLine().hidden, false);
  assert.equal(nextLine().style.left, `${spotOf(12000)}%`);
  assert.equal(text(byClass(main, 'ctx-next-tag')[0]), 'Next chats: 12,000 characters');
  assert.equal(grip().style.left, `${spotOf(12000)}%`);
  assert.equal(byClass(main, 'ctx-limit')[0].style.left, `${spotOf(8000)}%`);
  // Dragged back to today's place, the row is taken out.
  const again = grip();
  await fire(again, 'pointerdown', at(spotOf(12000)));
  await fire(again, 'pointermove', at(spotOf(8000)));
  assert.equal(text(readout()), '1% now · 1 of 3 show only a name');
  queue(EMPTY_URL, { status: 200, json: answer({ ...TIGHT, limit: LIMIT }, CODEX, CURSOR) });
  await fire(again, 'pointerup', { ...at(spotOf(8000)), type: 'pointerup' });
  await flush();
  assert.equal(tray.rows.length, 0);
});

test('Esc during a drag, or a release where it started, changes nothing', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer({ ...TIGHT, limit: LIMIT }, CODEX, CURSOR));
  const handle = await drag(spotOf(12000));
  await fire(handle, 'keydown', { key: 'Escape', stopPropagation() {} });
  assert.equal(readout().hidden, true);
  assert.equal(nextLine().hidden, true);
  assert.equal(handle.style.left, `${spotOf(8000)}%`);
  await fire(handle, 'pointerup', { ...at(spotOf(12000)), type: 'pointerup' });
  const back = await drag(spotOf(12000), spotOf(8000));
  await fire(back, 'pointerup', { ...at(spotOf(8000)), type: 'pointerup' });
  await flush();
  assert.equal(asked.some((a) => a.url === PREVIEW), false);
  assert.equal(tray.rows.length, 0);
});

test('keys move the handle place by place; Enter commits, Esc cancels, Enter with no move opens Details', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer({ ...TIGHT, limit: LIMIT }, CODEX, CURSOR));
  const handle = grip();
  await fire(handle, 'keydown', { key: 'Enter' });
  assert.match(text(drawer), /Skill list limit/);
  closePanel({ instant: true });
  await fire(handle, 'keydown', { key: 'ArrowRight' });
  await fire(handle, 'keydown', { key: 'ArrowRight' });
  assert.equal(text(readout()), '2% · all 3 fit · about 3,000 more characters per chat');
  assert.equal(handle.getAttribute('aria-valuenow'), '16000');
  assert.equal(handle.getAttribute('aria-valuetext'), '2% · all 3 fit · about 3,000 more characters per chat');
  await fire(handle, 'keydown', { key: 'Escape', stopPropagation() {} });
  assert.equal(handle.getAttribute('aria-valuenow'), '8000');
  assert.equal(readout().hidden, true);
  await fire(handle, 'keydown', { key: 'ArrowRight' });
  queue(PREVIEW, previewed('c1'));
  queue(LIMIT_URL, { status: 200, json: answer({ ...TIGHT, limit: LIMIT, after: LIMIT_AFTER }, CODEX, CURSOR) });
  await fire(handle, 'keydown', { key: 'Enter' });
  await flush();
  assert.deepEqual(asked.find((a) => a.url === PREVIEW).body.requests[0].params, { fraction: 0.015 });
});

test('with a share above the default, the line drags back to 1% and adds the Back row; a changed limit is said under the verdict', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  const changed = ['The limit was changed after this chat: it is 1.5% now. Your next chat will show the real list.', 'Estimate: On a 200K window, every skill would keep its description.'];
  const backOnly = {
    ...LIMIT, now: '1.5% of the context window: 12,000 characters', offer: null, back: { fraction: 'default', label: 'Back to 1%' }, note: null,
    why: 'Kitden does not offer a new skill list limit: every description fits.',
    steps: [
      { value: 'default', limit: 8000, short: 1, say: '1%, the default · 1 of 3 show only a name · about 3,000 fewer characters per chat' },
      { value: 0.015, limit: 12000, short: 0, say: '1.5% now · all 3 fit', now: true },
    ],
  };
  // The chat was sent at 1%: its line is at 8,000; today's limit, 12,000, is the next-chats line.
  // Nothing lies past 12,000, so the bar is drawn to 12,000 and a little more.
  const spotOf = (limit) => (limit / (12000 * 1.04)) * 100;
  show(answer({ ...TIGHT, limit: backOnly, changed }, CODEX, CURSOR));
  assert.deepEqual(byClass(main, 'ctx-room').map(text), changed);
  assert.equal(text(byClass(byClass(main, 'ctx-room')[1], 'ctx-est')[0]), 'Estimate:');
  assert.equal(nextLine().hidden, false);
  assert.equal(grip().style.left, `${spotOf(12000)}%`);
  // Details, from the flag, show only Now and Back to 1%.
  await fire(byClass(main, 'ctx-flag')[0], 'click');
  assert.match(text(drawer), /Now1\.5% of the context window: 12,000 characters/);
  assert.doesNotMatch(text(drawer), /Suggested|Cost/);
  assert.notEqual(buttonIn(drawer, 'Back to 1%'), undefined);
  closePanel({ instant: true });
  const handle = grip();
  await fire(handle, 'pointerdown', at(spotOf(12000)));
  await fire(handle, 'pointermove', at(spotOf(8000)));
  assert.equal(text(readout()), '1%, the default · 1 of 3 show only a name · about 3,000 fewer characters per chat');
  queue(PREVIEW, previewed('c1'));
  const backUrl = `/api/context?draft=${encodeURIComponent(JSON.stringify({ limits: { claude_code: 'default' } }))}`;
  queue(backUrl, { status: 200, json: answer({ ...TIGHT, limit: backOnly, changed }, CODEX, CURSOR) });
  await fire(handle, 'pointerup', { ...at(spotOf(8000)), type: 'pointerup' });
  await flush();
  assert.deepEqual(asked.find((a) => a.url === PREVIEW).body.requests[0].params, { fraction: 'default' });
});

test('with no limit line for the chat, the control stands at today\'s limit; Details still work', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  const windows = [{ ...TIGHT.windows[0], budget: null }];
  show(answer({ ...TIGHT, windows, limit: LIMIT }, CODEX, CURSOR));
  const flag = byClass(main, 'ctx-flag')[0];
  assert.equal(text(flag), 'Limit now: 8,000 characters');
  assert.notEqual(grip(), undefined);
  await fire(flag, 'click');
  assert.match(text(drawer), /Skill list limit/);
});

// The check failed, so the server counts what all descriptions need: it cannot say how many a limit
// that does not fit them all would still cut (`short` is null).
const COUNTED = {
  ...LIMIT,
  offer: { fraction: 0.02, label: 'Set to 2%', say: '2%: all 3 skills get their description', cost: 'About 3,000 more characters in every chat (about 750 tokens)' },
  counted: [
    "Kitden could not replay this chat's list exactly, so it counts what all descriptions need.",
    '1 skill has no description Kitden can find; it is counted at the longest, 1,536 characters.',
  ],
  steps: steps(
    { value: 0.01, limit: 8000, short: null, say: '1% now · not all fit', now: true },
    { value: 0.015, limit: 12000, short: null, say: '1.5% · not all fit' },
    { value: 0.02, limit: 16000, short: 0, say: '2% · all 3 fit · about 3,000 more characters per chat' },
  ),
};
const UNCHECKED = { ...TIGHT, checked: false, limit: COUNTED };

test('a place whose count of cut skills is not known says so in the readout and to a screen reader', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer(UNCHECKED, CODEX, CURSOR));
  const handle = grip();
  assert.equal(handle.getAttribute('aria-valuetext'), '1% now · not all fit');
  await fire(handle, 'keydown', { key: 'ArrowRight' });
  assert.equal(text(readout()), '1.5% · not all fit');
  assert.equal(handle.getAttribute('aria-valuetext'), '1.5% · not all fit');
  assert.equal(handle.getAttribute('aria-valuenow'), '12000');
  await fire(handle, 'keydown', { key: 'ArrowRight' });
  assert.equal(handle.getAttribute('aria-valuetext'), '2% · all 3 fit · about 3,000 more characters per chat');
  await fire(handle, 'keydown', { key: 'Escape', stopPropagation() {} });
  // Details say it is a count, one quiet line each.
  await fire(byClass(main, 'ctx-flag')[0], 'click');
  assert.deepEqual(byClass(drawer, 'ctx-counted').map(text), COUNTED.counted);
  closePanel({ instant: true });
  show(answer({ ...TIGHT, limit: LIMIT }, CODEX, CURSOR));
  await fire(byClass(main, 'ctx-flag')[0], 'click');
  assert.equal(byClass(drawer, 'ctx-counted').length, 0);
});

test('After Apply by a count: where all fit the picture follows it, else only its sentence shows', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  const fits = {
    say: 'After Apply, estimate: On a 200K window, every skill would keep its description. gamma gets a description.',
    gets: ['gamma'], loses: [], budget: 16000,
    result: { short: '', say: '', sent: { alpha: 4000, beta: 2000, gamma: 3000 }, over: {}, used: 9100, size: 9100, room: null, misfit: null },
  };
  show(answer({ ...UNCHECKED, after: fits }, CODEX, CURSOR));
  assert.equal(text(verdict()), fits.say);
  assert.equal(text(byClass(verdict(), 'ctx-est')[0]), 'After Apply, estimate:');
  assert.equal(pillOf('gamma').classList.contains('back'), true);
  assert.notEqual(pieceOf('gamma'), undefined);
  const not = { say: 'After Apply, estimate: On a 200K window, not all descriptions would fit.', gets: [], loses: [], budget: 12000, result: null };
  show(answer({ ...UNCHECKED, after: not }, CODEX, CURSOR));
  assert.equal(text(verdict()), not.say);
  // No claim about which skills fit: the picture and the sides stay the last chat's.
  assert.equal(pieceOf('gamma'), undefined);
  assert.notEqual(pieceOf('gamma', 'over'), undefined);
  assert.deepEqual(sides().map((n) => pills(n).map((p) => p.dataset.skill)), [['alpha', 'beta'], ['gamma']]);
});

// Codex's limit, in tokens: today's 5,440 (2% of a 272K window), 5,500 fits all, 6,000 more.
const CODEX_LIMIT = {
  now: '2% of the context window: 5,440 tokens',
  offer: { tokens: 5500, label: 'Set to 5,500 tokens', say: '5,500 tokens: no description is cut and no skill is left out', cost: 'About 60 more tokens in every chat' },
  back: null,
  note: 'Kitden writes it in your Codex config.toml, for all projects. Your next chat will show the real list.',
  why: null,
  param: 'tokens',
  steps: [
    { value: 5440, limit: 5440, short: 3, say: '5,440 tokens now · 3 of 9 cut short or left out', now: true },
    { value: 5500, limit: 5500, short: 0, say: '5,500 tokens · all 9 fit · about 60 more tokens per chat' },
    { value: 6000, limit: 6000, short: 0, say: '6,000 tokens · all 9 fit · about 60 more tokens per chat' },
  ],
};

test("Codex's limit line works the same, in tokens: drag, snap, release adds a tokens row", async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'codex' };
  show(answer(CLAUDE, { ...CODEX, limit: CODEX_LIMIT }, CURSOR));
  const scale = 5500 * 1.3;
  const spot = (limit) => (limit / scale) * 100;
  const handle = grip();
  assert.equal(handle.getAttribute('aria-valuetext'), '5,440 tokens now · 3 of 9 cut short or left out');
  assert.equal(text(byClass(main, 'ctx-flag')[0]), 'Limit: 5,440 tokens');
  await fire(handle, 'pointerdown', at(spot(5440)));
  await fire(handle, 'pointermove', at(spot(5440) - 1));
  // Today's place stays reachable, though the suggested place is within SNAP of it.
  assert.equal(text(readout()), '5,440 tokens now · 3 of 9 cut short or left out');
  await fire(handle, 'pointermove', at(spot(5500) + 1.5));
  assert.equal(text(readout()), '5,500 tokens · all 9 fit · about 60 more tokens per chat');
  await fire(handle, 'pointermove', at(98));
  assert.equal(text(readout()), '6,000 tokens · all 9 fit · about 60 more tokens per chat');
  await fire(handle, 'pointermove', at(spot(5500) + 1.9));
  queue(PREVIEW, previewed('c1'));
  const url = `/api/context?draft=${encodeURIComponent(JSON.stringify({ limits: { codex: 5500 } }))}`;
  queue(url, { status: 200, json: answer(CLAUDE, { ...CODEX, limit: CODEX_LIMIT }, CURSOR) });
  state.view = 'context';
  await fire(handle, 'pointerup', { ...at(spot(5500) + 1.9), type: 'pointerup' });
  await flush();
  await flush();
  const sent = asked.find((a) => a.url === PREVIEW).body.requests[0];
  assert.deepEqual([sent.kind, sent.targets, sent.params], ['skill.limit', [{ client: 'codex' }], { tokens: 5500 }]);
  assert.equal(asked.some((a) => a.url === url), true);
  // Details from the flag: in tokens, with Set to 5,500 tokens.
  await fire(byClass(main, 'ctx-flag')[0], 'click');
  assert.match(text(drawer), /Now2% of the context window: 5,440 tokens/);
  assert.notEqual(buttonIn(drawer, 'Set to 5,500 tokens'), undefined);
});

test('Details keep Set to 1.5%, which makes the same row and shows pressed', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer({ ...TIGHT, limit: LIMIT }, CODEX, CURSOR));
  await fire(byClass(main, 'ctx-flag')[0], 'click');
  queue(PREVIEW, previewed('c1'));
  queue(LIMIT_URL, { status: 200, json: answer({ ...TIGHT, limit: LIMIT, after: LIMIT_AFTER }, CODEX, CURSOR) });
  await fire(buttonIn(drawer, 'Set to 1.5%'), 'click');
  await flush();
  await flush();
  assert.deepEqual(asked.find((a) => a.url === PREVIEW).body.requests[0].params, { fraction: 0.015 });
  assert.equal(text(verdict()).startsWith(LIMIT_AFTER.say), true);
  syncTray();
  assert.equal(buttonIn(drawer, 'Set to 1.5%').getAttribute('aria-pressed'), 'true');
  queue(EMPTY_URL, { status: 200, json: answer({ ...TIGHT, limit: LIMIT }, CODEX, CURSOR) });
  await fire(buttonIn(drawer, 'Set to 1.5%'), 'click');
  await flush();
  assert.equal(tray.rows.length, 0);
});

test('a project\'s own skill asks for a rule in its project', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer({ ...TIGHT, skills: [skill('alpha', 3990, 0, { project: 'p9', source: 'Project a' }), skill('beta', 1990, 0), skill('gamma', 2998, 1)] }, CODEX, CURSOR));
  await fire(pillOf('alpha'), 'click');
  assert.match(text(drawer), /SourceProject a/);
  const shown = answer({ ...TIGHT, skills: [skill('alpha', 3990, 0, { project: 'p9' }), skill('beta', 1990, 0), skill('gamma', 2998, 1)] }, CODEX, CURSOR);
  queue(PREVIEW, previewed('c2'));
  queue(`/api/context?draft=${encodeURIComponent(JSON.stringify({ claude_code: { alpha: 'off' } }))}`, { status: 200, json: shown });
  state.view = 'context';
  await fire(buttonIn(drawer, 'Off'), 'click');
  await flush();
  const sent = asked.find((a) => a.url === PREVIEW).body.requests[0];
  assert.deepEqual(sent.params, { scope: 'project', project: 'p9', state: 'off' });
  // The state it has now takes the row out again.
  queue('/api/context', { status: 200, json: shown });
  await fire(buttonIn(drawer, 'On'), 'click');
  await flush();
  assert.equal(tray.rows.length, 0);
});

test('How this is counted is folded, with the lines the server wrote', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  show(answer(TIGHT, CODEX, CURSOR));
  const how = walk(main).find((n) => n.tagName === 'DETAILS');
  assert.equal(text(how.children[0]), 'How this is counted');
  assert.deepEqual(walk(how).filter((n) => n.tagName === 'LI').map(text), TIGHT.how);
  show(answer({ ...TIGHT, how: [] }, CODEX, CURSOR));
  assert.equal(walk(main).some((n) => n.tagName === 'DETAILS'), false);
});

test('with the check failed there is no estimate card and no After Apply', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  const unchecked = { ...TIGHT, checked: false, message: NO_CHECK, windows: [TIGHT.windows[0], CLAUDE.windows[1]], after: AFTER };
  show(answer(unchecked, CODEX, CURSOR));
  assert.equal(cards().length, 1);
  assert.equal(text(main).includes('After Apply'), false);
  assert.equal(text(verdict()), TIGHT.windows[0].result.say);
  assert.equal(pillOf('beta').classList.contains('lost'), false);
});

test('on an estimate window the pills follow that estimate, not the last chat', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  const other = {
    title: '1M window', models: 'Opus 5.5', tag: 'Estimate', budget: 30000,
    result: { short: 'All 3 would fit', say: 'Estimate: On a 1M window, every skill would keep its description.', sent: { alpha: 4000, beta: 2000, gamma: 3000 }, over: {}, used: 9100, size: 9100, room: null, misfit: null },
  };
  show(answer({ ...TIGHT, windows: [TIGHT.windows[0], other] }, CODEX, CURSOR));
  await fire(cards()[0], 'click');
  assert.deepEqual(sides().map((n) => pills(n).map((p) => p.dataset.skill)), [['alpha', 'beta'], ['gamma']]);
  await fire(cards()[1], 'click');
  assert.deepEqual(sides().map((n) => pills(n).map((p) => p.dataset.skill)), [['alpha', 'beta', 'gamma'], []]);
  await fire(cards()[0], 'click');
});

test('a Codex skill that is off shows Off and offers no On', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'codex' };
  show(answer(CLAUDE, { ...CODEX, skills: [skill('lint', 300, 0, { state: 'off', switch: ['on', 'off'] }), skill('fmt', 200, 0, { switch: ['on', 'off'] })] }, CURSOR));
  await fire(pillOf('lint'), 'click');
  let switches = walk(drawer).filter((n) => n.dataset && n.dataset.state);
  assert.deepEqual(switches.map((n) => [text(n), n.getAttribute('aria-pressed')]), [['Off', 'true']]);
  await fire(pillOf('fmt'), 'click');
  switches = walk(drawer).filter((n) => n.dataset && n.dataset.state);
  assert.deepEqual(switches.map(text), ['On', 'Off']);
});

test('a cut pill says how much of its description was sent', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'codex' };
  const result = { ...CODEX.windows[0].result, sent: { a: 100, b: 90 }, over: { b: 60 }, kept: { b: 342 } };
  const cut = { ...CODEX, windows: [{ ...CODEX.windows[0], result }], skills: [skill('a', 200, 0), skill('b', 570, 1)] };
  show(answer(CLAUDE, cut, CURSOR));
  const [whole, short] = sides().map((n) => pills(n));
  assert.equal(text(whole[0]), 'a200');
  assert.equal(text(short[0]), 'b342 of 570');
  assert.equal(short[0].children[1].getAttribute('title'), '342 of 570 characters sent');
});

test('Details shows the description, the part the agent did not get in grey', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  const cut = skill('gamma', 12, 1, { description: 'Makes plans. Long tail.', seen: 12 });
  show(answer({ ...TIGHT, skills: [...TIGHT.skills.slice(0, 2), cut] }, CODEX, CURSOR));
  await fire(pillOf('gamma'), 'click');
  const [box] = byClass(drawer, 'ctx-desc');
  assert.match(text(box), /^DescriptionMakes plans\. Long tail\./);
  assert.deepEqual(byClass(box, 'ctx-cut').map(text), [' Long tail.']);
  assert.match(text(box), /Grey: the part the agent did not get\.$/);
});

test('Details shows a description the agent got whole with nothing grey', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  const whole = skill('gamma', 12, 0, { description: 'Makes plans.', seen: null });
  show(answer({ ...TIGHT, skills: [...TIGHT.skills.slice(0, 2), whole] }, CODEX, CURSOR));
  await fire(pillOf('gamma'), 'click');
  const [box] = byClass(drawer, 'ctx-desc');
  assert.equal(text(box), 'DescriptionMakes plans.');
  assert.deepEqual(byClass(box, 'ctx-cut'), []);
});

test('Details counts characters as Python does, so an emoji does not move the grey part', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  const cut = skill('gamma', 4, 1, { description: '😀abc', seen: 2 });
  show(answer({ ...TIGHT, skills: [...TIGHT.skills.slice(0, 2), cut] }, CODEX, CURSOR));
  await fire(pillOf('gamma'), 'click');
  const [box] = byClass(drawer, 'ctx-desc');
  assert.deepEqual(byClass(box, 'ctx-cut').map(text), ['bc']);
});

test('a built-in skill says so on its pill, and that Kitden cannot turn it off', async () => {
  await fresh();
  state.selected = { kind: 'client', name: 'claude_code' };
  const dataviz = skill('dataviz', 1436, 0, { item: null, source: 'Built into Claude Code', switch: [], built_in: true });
  show(answer({ ...TIGHT, skills: [...TIGHT.skills, dataviz] }, CODEX, CURSOR));
  const pill = pillOf('dataviz');
  assert.equal(text(pill), 'datavizbuilt-in1,436');
  assert.equal(pill.classList.contains('builtin'), true);
  assert.match(pill.getAttribute('title'), /Built into Claude Code\. Kitden cannot turn it off\./);
  assert.equal(pillOf('alpha').classList.contains('builtin'), false);
  assert.equal(pillOf('alpha').getAttribute('title'), null);
});
