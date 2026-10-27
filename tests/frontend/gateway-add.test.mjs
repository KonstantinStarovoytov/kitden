import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

// The Add a server panel in a small browser: elements with parents, the page's fixed parts, a wide
// window (Details float) and a stand-in server. It shows what the panel does, not how it looks.
globalThis.matchMedia = (query) => ({ matches: query.includes('min-width'), addEventListener() {} });
delete globalThis.navigator;
globalThis.requestAnimationFrame = () => 0;
globalThis.MutationObserver = class { observe() {} };
globalThis.addEventListener = () => {};
// The window a drag listens to for a blur.
globalThis.window = { addEventListener() {}, removeEventListener() {} };

const walk = (root) => root.children.flatMap((n) => [n, ...walk(n)]);
const motions = [];
function element(tagName) {
  let names = [];
  const attributes = new Map();
  const style = { setProperty(name, value) { style[name] = value; }, removeProperty(name) { delete style[name]; } };
  const node = {
    tagName, style, dataset: {}, children: [], parentNode: null, textContent: '', listeners: {}, hidden: false, offsetLeft: 0, offsetTop: 0, offsetWidth: 0, offsetHeight: 0,
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
    getAttribute: (name) => (attributes.has(name) ? attributes.get(name) : null),
    removeAttribute(name) { attributes.delete(name); },
    append(...nodes) { for (const n of nodes) node.insertBefore(typeof n === 'string' ? Object.assign(element('#text'), { textContent: n }) : n, null); },
    prepend(...nodes) { const first = node.children[0] || null; for (const n of nodes) node.insertBefore(n, first); },
    insertBefore(n, ref) {
      if (n.parentNode) n.parentNode.children.splice(n.parentNode.children.indexOf(n), 1);
      node.children.splice(ref ? node.children.indexOf(ref) : node.children.length, 0, n);
      n.parentNode = node;
      return n;
    },
    remove() { if (node.parentNode) node.parentNode.children.splice(node.parentNode.children.indexOf(node), 1); node.parentNode = null; },
    replaceChildren(...nodes) { for (const n of [...node.children]) n.parentNode = null; node.children = []; node.append(...nodes); },
    contains(other) { for (let at = other; at; at = at.parentNode) if (at === node) return true; return false; },
    focus() { globalThis.document.activeElement = node; },
    matches: () => false,
    querySelector: (selector) => (selector === ':scope > .ink' ? node.children.find((n) => n.className === 'ink') || null : null),
    querySelectorAll(selector) {
      const key = selector.match(/^\[data-(\w+)\]$/);
      return key ? walk(node).filter((n) => n.dataset[key[1]] !== undefined) : [];
    },
    getBoundingClientRect: () => ({ top: 0, bottom: 0, left: 0, right: 1345 }),
    setPointerCapture() {},
    // A copy of the node and what it holds, with no listeners.
    cloneNode(deep) {
      const copy = element(tagName);
      copy.className = node.className;
      Object.assign(copy.dataset, node.dataset);
      for (const [name, value] of attributes) copy.setAttribute(name, value);
      copy.textContent = node.textContent;
      if (deep) copy.append(...node.children.map((n) => n.cloneNode(true)));
      return copy;
    },
    addEventListener(type, fn) { (node.listeners[type] ||= []).push(fn); },
    animate(keyframes, options) { motions.push({ node, keyframes, options }); return { finished: Promise.resolve(), cancel() {} }; },
    getAnimations: () => [],
  };
  return node;
}
const pages = {};
for (const id of ['#main', '#drawer', '#scrim', '#topbar', '#content', '#dock']) {
  pages[id] = element('DIV');
  pages[id].root = true;
}
// What the document hears, by type.
const docHeard = {};
globalThis.document = {
  hidden: false, activeElement: null, body: element('BODY'),
  createElement: (tag) => element(tag.toUpperCase()), createElementNS: (namespace, tag) => element(tag),
  querySelector: (selector) => pages[selector] ?? null, querySelectorAll: () => [], getElementById: () => null,
  addEventListener(type, fn) { (docHeard[type] ||= []).push(fn); },
  removeEventListener(type, fn) { docHeard[type] = (docHeard[type] || []).filter((f) => f !== fn); },
  documentElement: { classList: { add() {}, remove() {} }, style: { setProperty() {}, removeProperty() {} } },
};

// The stand-in server: the marketplaces' servers, and a batch preview with one row per request.
const sent = [];
let servers = null;
globalThis.fetch = async (url, init = {}) => {
  const body = init.body ? JSON.parse(init.body) : null;
  sent.push({ url, body });
  if (url === '/api/market-servers') {
    if (!servers) return { ok: false, status: 500, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ servers }) };
  }
  if (url === '/api/batch/preview') {
    const rows = body.requests.map((r, at) => ({ id: r.id, kind: r.kind, title: r.title, detail: '', project: null, steps: [at], after: [] }));
    const json = { id: `c${sent.length}`, action: 'batch', state: 'previewed', error: null, undo_note: null, steps: body.requests.map(() => ({ client: 'kitden', name: 'x' })), rows };
    return { ok: true, status: 200, json: async () => json };
  }
  return { ok: true, status: 200, json: async () => ({}) };
};

const { ADD_SERVER, addRowWords, matchRows, openAdd } = await import('../../src/kitden/web/static/js/gateway-add.js');
const { gatewayCard } = await import('../../src/kitden/web/static/js/gateway-details.js');
const { closePanel, initPanel, isPanelOpen, openPanel, panelState } = await import('../../src/kitden/web/static/js/panel.js');
const { reducedMotion } = await import('../../src/kitden/web/static/js/motion.js');
const { state } = await import('../../src/kitden/web/static/js/store.js');
const { cancelTray, tray } = await import('../../src/kitden/web/static/js/tray.js');
const { placeMoved } = await import('../../src/kitden/web/static/js/gateway-drag.js');
state.view = 'gateway';
initPanel();

const SERVERS = [
  { id: 'db-tools@demo/db-query', name: 'db-query', plugin: 'db-tools', marketplace: 'demo', kind: 'local', held: false, refusal: null },
  { id: 'pr-review@demo/pr-index', name: 'pr-index', plugin: 'pr-review', marketplace: 'demo', kind: 'local', held: false, refusal: "pr-index runs a file inside its plugin folder; Kitden can't run it from the gateway." },
  { id: 'test-helper@demo/test-status', name: 'test-status', plugin: 'test-helper', marketplace: 'demo', kind: 'remote', held: false, refusal: null },
  { id: 'gh@team/github', name: 'GitHub', plugin: 'gh', marketplace: 'team', kind: 'remote', held: true, refusal: 'GitHub is in the gateway already.' },
];

const wait = (ms = 0) => new Promise((resolve) => setTimeout(resolve, ms));
const text = (node) => (node.children.length ? node.children.map(text).join(' ') : node.textContent).trim();
const drawer = pages['#drawer'];
const find = (test) => walk(drawer).filter(test);
const search = () => find((n) => n.tagName === 'INPUT')[0];
const rows = () => find((n) => n.className.split(' ').includes('res'));
const shown = () => rows().filter((n) => !n.hidden);
const captions = () => find((n) => n.className === 'add-group');
const pill = () => find((n) => n.className === 'seg sm')[0].children.filter((n) => n.tagName === 'BUTTON');
const rowWords = (row) => [text(row.children[2].children[0]), row.children[2].children[1].textContent, row.children[3].textContent];
const fire = (node, type, event = {}) => { for (const fn of node.listeners[type] || []) fn({ preventDefault() {}, stopPropagation() {}, target: node, ...event }); };
// A press on a button() runs its work after a tick (dom.js).
const press = async (node) => { fire(node, 'click'); await wait(); await wait(); };
const pressKey = (key) => { for (const fn of [...(docHeard.keydown || [])]) fn({ key, preventDefault() {}, stopImmediatePropagation() {}, metaKey: false, ctrlKey: false }); };
const pointer = (type, x, y) => { for (const fn of [...(docHeard[type] || [])]) fn({ type, clientX: x, clientY: y }); };

// "+ Add" beside the map's Servers caption, as map-view.js draws it.
function addButton() {
  const node = element('BUTTON');
  node.className = 'btn small';
  node.dataset.focus = 'add:servers';
  pages['#main'].replaceChildren(node);
  return node;
}

// Open the panel from `from` and wait until its content has come in (after the skeleton's 160 ms).
async function open(from = addButton()) {
  servers = SERVERS;
  await openAdd({ from });
  await wait(200);
  return from;
}

async function done() {
  await cancelTray();
  closePanel({ instant: true, focus: false });
  reducedMotion.matches = false;
  motions.length = 0;
}

test('a row says, first match wins: Added, In the gateway, its refusal, In preview, or nothing', () => {
  const [free, refused, remote, held] = SERVERS;
  assert.deepEqual(addRowWords(free, { inTray: false, added: new Set() }), { status: '', off: false, line: 'Local' });
  assert.deepEqual(addRowWords(remote, { inTray: true, added: new Set() }), { status: 'In preview', off: false, line: 'Remote' });
  assert.deepEqual(addRowWords(refused, { inTray: false, added: new Set() }), { status: '', off: true, line: refused.refusal });
  // A held row says In the gateway, not the list's refusal words.
  assert.deepEqual(addRowWords(held, { inTray: false, added: new Set() }), { status: 'In the gateway', off: true, line: 'Remote' });
  // Added comes first: a row an Apply added is held too.
  assert.deepEqual(addRowWords(held, { inTray: false, added: new Set([held.id]) }), { status: 'Added', off: true, line: 'Remote' });
});

test('the search matches part of the name in any case, and the pill keeps one kind', () => {
  assert.deepEqual(matchRows(SERVERS, ' DB ', 'all').map((r) => r.name), ['db-query']);
  assert.deepEqual(matchRows(SERVERS, '-', 'local').map((r) => r.name), ['db-query', 'pr-index']);
  assert.deepEqual(matchRows(SERVERS, '', 'remote').map((r) => r.name), ['test-status', 'GitHub']);
  assert.deepEqual(matchRows(SERVERS, 'demo', 'all'), []);
});

test('+ Add opens the panel, focus goes to the search, and + Add looks pressed', async () => {
  const from = await open();
  try {
    assert.equal(isPanelOpen(), true);
    assert.deepEqual(panelState.current, { type: 'add' });
    const [head, body, foot] = drawer.children;
    assert.deepEqual([text(head.children[0]), text(head.children[1])], ['Gateway Close', 'Add a server']);
    assert.equal(document.activeElement, search());
    assert.deepEqual([search().placeholder, search().getAttribute('aria-label')], ['Search the marketplaces…', 'Search the marketplaces']);
    assert.deepEqual(pill().map((b) => [b.textContent, b.getAttribute('aria-pressed')]), [['All', 'true'], ['Remote', 'false'], ['Local', 'false']]);
    assert.equal(body.className, 'body add-body');
    assert.deepEqual([foot.className, text(foot)], ['step-foot', 'Click a server or drag it onto the map to preview it.']);
    assert.deepEqual([from.className, from.getAttribute('aria-expanded')], ['btn small primary', 'true']);
    // Only the list was read: nothing is written, and the tray is empty.
    assert.deepEqual(sent.map((s) => s.url).filter((u) => u !== '/api/market-servers'), []);
    assert.deepEqual(tray.rows, []);
    // It came after its skeleton and rose in (panel.js land).
    assert.ok(motions.some((m) => m.node === head && m.keyframes[0].transform === 'translateY(6px)'));
  } finally {
    await done();
  }
});

test('Close and Escape close it, focus goes back to + Add, and + Add looks plain again', async () => {
  let from = await open();
  try {
    await press(drawer.children[0].children[0].children[1]);
    assert.equal(isPanelOpen(), false);
    assert.equal(document.activeElement, from);
    assert.deepEqual([from.className, from.getAttribute('aria-expanded')], ['btn small', 'false']);
    from = await open();
    pressKey('Escape');
    assert.equal(isPanelOpen(), false);
    assert.equal(document.activeElement, from);
    assert.equal(from.className, 'btn small');
    // Another selection takes the panel's place: + Add lets go too.
    from = await open();
    panelState.current = { type: 'held', name: 'files' };
    openPanel([element('HEADER')]);
    assert.equal(isPanelOpen(), true);
    assert.equal(from.className, 'btn small');
    // So does a selection made while the list is still being read.
    from = addButton();
    servers = SERVERS;
    const opening = openAdd({ from });
    panelState.current = { type: 'held', name: 'files' };
    openPanel([element('HEADER')]);
    await opening;
    await wait(200);
    assert.equal(from.className, 'btn small');
    assert.equal(search(), undefined);
  } finally {
    await done();
  }
});

test('the groups follow the marketplaces and the pill filters Remote and Local', async () => {
  await open();
  try {
    assert.deepEqual(captions().map(text), ['demo', 'team']);
    assert.ok(captions().every((c) => c.children[0].dataset.icon === 'store'));
    assert.deepEqual(rows().map((r) => rowWords(r)[0]), ['db-query', 'pr-index', 'test-status', 'GitHub']);
    // The tile shows the map's icon of a remote or a local server.
    assert.deepEqual(rows().map((r) => r.children[1].children[0].dataset.icon), ['hard-drive', 'hard-drive', 'globe', 'globe']);
    pill().forEach((b, at) => { b.offsetLeft = 3 + at * 40; });
    motions.length = 0;
    await press(pill()[1]);
    assert.deepEqual(pill().map((b) => b.getAttribute('aria-pressed')), ['false', 'true', 'false']);
    // The raised mark glides to the pressed choice in 280 ms (motion.js glide).
    const [ink] = find((n) => n.className === 'ink');
    assert.deepEqual(motions.filter((m) => m.node === ink).map((m) => [m.keyframes.at(-1).transform, m.options.duration]), [['translate(43px, 0px)', 280]]);
    assert.deepEqual(shown().map((r) => rowWords(r)[0]), ['test-status', 'GitHub']);
    await press(pill()[2]);
    assert.deepEqual(shown().map((r) => rowWords(r)[0]), ['db-query', 'pr-index']);
    assert.deepEqual(captions().map((c) => c.hidden), [false, true]);
    await press(pill()[0]);
    assert.equal(shown().length, 4);
  } finally {
    await done();
  }
});

test('a search hides rows and empty groups and says No servers match.', async () => {
  await open();
  try {
    const none = () => find((n) => n.className === 'muted add-none')[0];
    assert.equal(none().hidden, true);
    search().value = 'GIT';
    fire(search(), 'input');
    assert.deepEqual(shown().map((r) => rowWords(r)[0]), ['GitHub']);
    assert.deepEqual(captions().map((c) => c.hidden), [true, false]);
    search().value = 'nothing like it';
    fire(search(), 'input');
    assert.deepEqual([shown().length, captions().every((c) => c.hidden), none().hidden, none().textContent], [0, true, false, 'No servers match.']);
    // A row that comes back rises: opacity, 4 px, 240 ms CALM.
    motions.length = 0;
    search().value = '';
    fire(search(), 'input');
    assert.equal(shown().length, 4);
    assert.equal(none().hidden, true);
    const rise = motions.filter((m) => m.node.className.includes('res'));
    assert.equal(rise.length, 4);
    assert.deepEqual(rise[0].keyframes, [{ opacity: 0, transform: 'translateY(-4px)' }, { opacity: 1, transform: 'none' }]);
    assert.deepEqual([rise[0].options.duration, rise[0].options.easing], [240, 'cubic-bezier(.2,.8,.2,1)']);
  } finally {
    await done();
  }
});

test('a list with no server says so, and a failed read offers Try again', async () => {
  servers = [];
  await openAdd({ from: addButton() });
  await wait(200);
  try {
    assert.deepEqual(find((n) => n.className === 'muted add-none').map((n) => [n.hidden, n.textContent]), [[false, 'No marketplace on this computer offers an MCP server.']]);
    closePanel({ instant: true, focus: false });
    servers = null;
    await openAdd({ from: addButton() });
    await wait(200);
    const body = drawer.children[1];
    assert.deepEqual(body.children.map((n) => n.textContent), ['Could not read the marketplaces.', 'Try again']);
    assert.equal(body.children[1].className, 'btn ghost small');
    assert.equal(document.activeElement, body.children[1]);
    servers = SERVERS;
    await press(body.children[1]);
    await wait(200);
    assert.equal(rows().length, 4);
  } finally {
    await done();
  }
});

test('a refused row is greyed, shows its reason and has no grip', async () => {
  await open();
  try {
    const [free, refused, , held] = rows();
    assert.deepEqual(rowWords(refused), ['pr-index', SERVERS[1].refusal, '']);
    assert.deepEqual([refused.classList.contains('off'), refused.getAttribute('aria-disabled'), refused.children[0].classList.contains('gone')], [true, 'true', true]);
    assert.deepEqual(rowWords(held), ['GitHub', 'Remote', 'In the gateway']);
    assert.equal(held.classList.contains('off'), true);
    assert.deepEqual([free.classList.contains('off'), free.children[0].dataset.icon, free.children[0].classList.contains('gone')], [false, 'grip-vertical', false]);
    // A press on a greyed row asks for nothing.
    fire(refused, 'click');
    fire(held, 'click');
    await wait();
    assert.deepEqual(tray.rows, []);
    assert.ok(!sent.some((s) => s.url === '/api/batch/preview' && s.body.requests.length));
  } finally {
    await done();
  }
});

test('a click adds one gateway.add row; the row says In preview; a second click takes it out', async () => {
  await open();
  try {
    const row = rows()[0];
    fire(row, 'click');
    await wait(10);
    assert.deepEqual(tray.rows.map((r) => [r.key, r.body, r.icon]), [['add:db-tools@demo/db-query', { action: 'gateway.add', targets: [], params: { server: 'db-tools@demo/db-query' } }, 'plus']]);
    assert.deepEqual(rowWords(row), ['db-query', 'Local', 'In preview']);
    assert.equal(row.classList.contains('on'), true);
    fire(row, 'click');
    await wait(10);
    assert.deepEqual(tray.rows, []);
    assert.deepEqual(rowWords(row), ['db-query', 'Local', '']);
    assert.equal(row.classList.contains('on'), false);
  } finally {
    await done();
  }
});

test('Enter and Space click a row', async () => {
  await open();
  try {
    const row = rows()[2];
    assert.deepEqual([row.getAttribute('role'), row.getAttribute('tabindex')], ['button', '0']);
    fire(row, 'keydown', { key: 'Enter' });
    await wait(10);
    assert.deepEqual(tray.rows.map((r) => r.key), ['add:test-helper@demo/test-status']);
    fire(row, 'keydown', { key: ' ' });
    await wait(10);
    assert.deepEqual(tray.rows, []);
    fire(row, 'keydown', { key: 'a' });
    await wait(10);
    assert.deepEqual(tray.rows, []);
  } finally {
    await done();
  }
});

test('a held Enter clicks a row once', async () => {
  await open();
  try {
    const row = rows()[2];
    fire(row, 'keydown', { key: 'Enter' });
    await wait(10);
    // The key held down repeats: the row stays in the tray.
    fire(row, 'keydown', { key: 'Enter', repeat: true });
    await wait(10);
    assert.deepEqual(tray.rows.map((r) => r.key), ['add:test-helper@demo/test-status']);
    fire(row, 'keydown', { key: ' ' });
    await wait(10);
    fire(row, 'keydown', { key: ' ', repeat: true });
    await wait(10);
    assert.deepEqual(tray.rows, []);
  } finally {
    await done();
  }
});

test('+ Add while the panel is open keeps it as it is and gives focus to the search', async () => {
  const from = await open();
  try {
    search().value = 'db';
    fire(search(), 'input');
    await press(pill()[2]);
    const [body, before] = [drawer.children[1], sent.length];
    from.focus();
    await openAdd({ from });
    await wait(200);
    // Nothing is read again: the same list, its search and its pill.
    assert.deepEqual([drawer.children[1], sent.length, search().value], [body, before, 'db']);
    assert.deepEqual(pill().map((b) => b.getAttribute('aria-pressed')), ['false', 'false', 'true']);
    assert.deepEqual(shown().map((r) => rowWords(r)[0]), ['db-query']);
    assert.equal(document.activeElement, search());
    assert.deepEqual([from.className, from.getAttribute('aria-expanded')], ['btn small primary', 'true']);
  } finally {
    await done();
  }
});

// The map as the drag engine sees it (gateway-drag.js placeMoved): shown, with no gateway to drop on.
function mapShown() {
  const area = element('DIV');
  const box = element('DIV');
  box.root = true;
  box.append(area);
  const view = { box, area, node: () => null, tip() {}, untip() {}, lightTarget() {}, unlightTarget() {}, glance() {} };
  placeMoved({ view, model: { blocks: [], links: [] }, layout: { blocks: [], columns: [] } });
}

// A press on a row and a move of 10 px: whether a drag started, then the release far away.
async function dragged(row) {
  fire(row, 'pointerdown', { button: 0, pointerId: 1, clientX: 20, clientY: 20 });
  pointer('pointermove', 30, 20);
  const ghost = walk(document.body).find((n) => n.className.split(' ').includes('ghost'));
  const started = [row.classList.contains('dragging'), Boolean(ghost)];
  pointer('pointerup', 30, 20);
  await wait(10);
  return { started, ghost };
}

test('a greyed or previewed row does not drag', async () => {
  await open();
  mapShown();
  try {
    const [free, refused, remote, held] = rows();
    // A free row drags: it fades and its ghost follows the pointer; let go anywhere, it comes back.
    const { started, ghost } = await dragged(free);
    assert.deepEqual(started, [true, true]);
    assert.deepEqual([free.classList.contains('dragging'), ghost.parentNode], [false, null]);
    assert.deepEqual(ghost.children.map((n) => n.className), free.children.map((n) => n.className));
    assert.deepEqual(tray.rows, []);
    // A greyed row (refused, in the gateway) and one in preview do not.
    for (const row of [refused, held]) assert.deepEqual((await dragged(row)).started, [false, false]);
    fire(remote, 'click');
    await wait(10);
    assert.ok(remote.classList.contains('on'));
    assert.deepEqual((await dragged(remote)).started, [false, false]);
    assert.deepEqual(tray.rows.map((r) => r.key), ['add:test-helper@demo/test-status']);
    // Only the left button drags.
    fire(free, 'pointerdown', { button: 2, pointerId: 1, clientX: 20, clientY: 20 });
    pointer('pointermove', 40, 20);
    assert.equal(free.classList.contains('dragging'), false);
    pointer('pointerup', 40, 20);
  } finally {
    await done();
  }
});

test("the Kitden gateway's More list opens the same panel", async () => {
  const from = addButton();
  servers = SERVERS;
  const kitden = { id: 'kitden', kind: 'kitden', name: 'Kitden gateway', where: 'On this Mac', movable: true, servers: [] };
  const view = { gateways: [kitden], connections: { kitden: {} }, used: ['kitden'], groups: { move: [], local: [], plugin: [] } };
  const card = gatewayCard(kitden, { view, setup: [], clients: [] });
  const more = card.more.find((m) => m.label === ADD_SERVER);
  assert.equal(ADD_SERVER, 'Add a server…');
  try {
    await more.run();
    await wait(200);
    assert.equal(rows().length, 4);
    assert.equal(document.activeElement, search());
    // Focus goes back to the map's + Add, which looks pressed meanwhile.
    assert.equal(from.className, 'btn small primary');
    pressKey('Escape');
    assert.equal(document.activeElement, from);
    assert.equal(from.className, 'btn small');
  } finally {
    await done();
  }
});

test('under reduced motion it opens and rises at once', async () => {
  reducedMotion.matches = true;
  motions.length = 0;
  const from = addButton();
  servers = SERVERS;
  try {
    await openAdd({ from });
    // No skeleton and no wait: the content is in as soon as it is read.
    assert.equal(rows().length, 4);
    assert.equal(document.activeElement, search());
    search().value = 'x';
    fire(search(), 'input');
    search().value = '';
    fire(search(), 'input');
    await press(pill()[1]);
    assert.deepEqual(motions, []);
    // Nothing stays at opacity 0.
    assert.ok(walk(drawer).every((n) => n.style.opacity !== '0' || n.className === 'ink'));
  } finally {
    await done();
  }
});

// Review Focus: the panel open while the tray applies and the page reads again.
test('after Apply a row says Added once the page reads again, with focus kept; an Undo frees it', async () => {
  const { pageRead } = await import('../../src/kitden/web/static/js/gateway-add.js');
  const { applyTray, endApplied } = await import('../../src/kitden/web/static/js/tray.js');
  const fetchWas = globalThis.fetch;
  globalThis.fetch = (url, init) => (/^\/api\/changes\/[^/]+\/apply$/.test(url)
    ? Promise.resolve({ ok: true, status: 200, json: async () => ({ id: url.split('/')[3], state: 'verified', error: null }) })
    : fetchWas(url, init));
  const held = SERVERS.map((r) => (r.name === 'test-status' ? { ...r, held: true, refusal: 'test-status is in the gateway already.' } : r));
  const reads = () => sent.filter((s) => s.url === '/api/market-servers').length;
  // What Kitden read: the Kitden gateway with the named servers in it.
  const gateway = (...names) => ({ gateways: [{ kind: 'kitden', servers: names.map((name) => ({ name })) }] });
  await open();
  try {
    fire(rows()[2], 'click');
    await wait(10);
    await applyTray();
    assert.equal(tray.phase, 'applied');
    const row = rows()[2];
    row.focus();
    // The page reads Kitden again: the row says Added, sliding in from 6 px (280 ms CALM), and the
    // panel reads the marketplaces again. The panel stays open and focus stays on the row.
    servers = held;
    const before = reads();
    motions.length = 0;
    pageRead(gateway('test-status'));
    await wait();
    assert.deepEqual(rowWords(row), ['test-status', 'Remote', 'Added']);
    assert.ok(row.classList.contains('done') && row.classList.contains('off') && !row.classList.contains('on'));
    assert.deepEqual(motions.filter((m) => m.node === row.children[3]).map((m) => [m.keyframes, m.options.duration, m.options.easing]),
      [[[{ opacity: 0, transform: 'translateX(6px)' }, { opacity: 1, transform: 'none' }], 280, 'cubic-bezier(.2,.8,.2,1)']]);
    assert.deepEqual([isPanelOpen(), document.activeElement, reads()], [true, row, before + 1]);
    // The same read again asks nothing; the tray empties and the row stays Added.
    const same = gateway('test-status');
    pageRead(same);
    pageRead(same);
    await wait();
    assert.equal(reads(), before + 2);
    endApplied();
    assert.equal(rowWords(row)[2], 'Added');
    // A press on it does nothing.
    fire(row, 'click');
    await wait(10);
    assert.deepEqual(tray.rows, []);
    // Opened again later, it still says Added, with no motion.
    closePanel({ instant: true, focus: false });
    motions.length = 0;
    servers = held;
    await openAdd({ from: addButton() });
    await wait(200);
    assert.equal(rowWords(rows()[2])[2], 'Added');
    assert.ok(!motions.some((m) => m.node === rows()[2].children[3]));
    // An Undo: the page reads again, the gateway no longer holds it, and the row is free.
    servers = SERVERS;
    pageRead(gateway());
    await wait();
    assert.deepEqual([rowWords(rows()[2]), rows()[2].classList.contains('off')], [['test-status', 'Remote', ''], false]);
  } finally {
    globalThis.fetch = fetchWas;
    servers = SERVERS;
    await done();
  }
});

test('the panel shows no path, address or command, and uses no inline style or markup', () => {
  const code = readFileSync(new URL('../../src/kitden/web/static/js/gateway-add.js', import.meta.url), 'utf8');
  assert.doesNotMatch(code, /innerHTML|cssText|style\s*=|\.style\./);
  for (const field of ['url', 'command', 'args', 'path']) assert.doesNotMatch(code, new RegExp(`row\\.${field}\\b`));
});
