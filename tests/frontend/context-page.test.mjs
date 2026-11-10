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
