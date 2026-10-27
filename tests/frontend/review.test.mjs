import assert from 'node:assert/strict';
import { test } from 'node:test';

// review.js draws in a side panel and talks to the tray: a small stand-in page holds what it draws.
// Any media query is a narrow window with reduced motion, so nothing waits for an animation.
globalThis.matchMedia = () => ({ matches: true, addEventListener() {} });
// Node before 21 has no navigator; review.js must load there too.
delete globalThis.navigator;

// A stand-in node: its children, classes, attributes and listeners; a press runs its listeners.
function fakeNode(tag) {
  const classes = new Set();
  const node = {
    nodeType: 1, tag, parent: null, childNodes: [], attributes: {}, dataset: {}, listeners: {}, style: { setProperty() {} }, disabled: false,
    [Symbol.for('nodejs.util.inspect.custom')]: () => `<${tag}>`,
    get className() { return [...classes].join(' '); },
    set className(value) { classes.clear(); String(value).split(/\s+/).filter(Boolean).forEach((name) => classes.add(name)); },
    classList: {
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      toggle: (name, on = !classes.has(name)) => { if (on) classes.add(name); else classes.delete(name); return on; },
      contains: (name) => classes.has(name),
    },
    get textContent() { return node.childNodes.map((child) => (typeof child === 'string' ? child : child.textContent)).join(''); },
    set textContent(value) { node.childNodes = String(value) === '' ? [] : [String(value)]; },
    get children() { return node.childNodes.filter((child) => typeof child !== 'string'); },
    get isConnected() { let up = node; while (up.parent) up = up.parent; return up.root === true; },
    append(...items) { for (const child of items) { if (typeof child !== 'string') child.parent = node; node.childNodes.push(child); } },
    prepend(...items) { for (const child of items) { if (typeof child !== 'string') child.parent = node; } node.childNodes.unshift(...items); },
    replaceChildren(...items) { for (const child of node.children) child.parent = null; node.childNodes = []; node.append(...items); },
    replaceWith(...items) { const up = node.parent; if (!up) return; const at = up.childNodes.indexOf(node); for (const child of items) child.parent = up; up.childNodes.splice(at, 1, ...items); },
    contains(other) { return other === node || node.children.some((child) => child.contains(other)); },
    setAttribute(name, value) { node.attributes[name] = String(value); },
    getAttribute: (name) => (name in node.attributes ? node.attributes[name] : null),
    removeAttribute(name) { delete node.attributes[name]; },
    addEventListener(type, listener) { (node.listeners[type] ||= []).push(listener); },
    // A press: every listener runs; the promise is their work.
    click() { return Promise.all((node.listeners.click || []).map((listener) => listener({ preventDefault() {} }))); },
    focus() { globalThis.document.activeElement = node; },
    querySelector: (selector) => {
      if (selector === ':scope > summary') return node.children.find((child) => child.tag === 'summary') || null;
      return selector.startsWith('.') ? all(node).find((child) => child !== node && child.classList.contains(selector.slice(1))) || null : null;
    },
    querySelectorAll: () => [],
  };
  return node;
}
const all = (node) => [node, ...node.children.flatMap(all)];
const tagged = (root, tag) => all(root).filter((n) => n.tag === tag);
const button = (root, label) => tagged(root, 'button').find((node) => node.textContent === label);

const pages = {};
for (const id of ['#dock', '#drawer', '#scrim', '#main', '.shell']) {
  pages[id] = fakeNode('div');
  pages[id].root = true;
}
globalThis.document = {
  activeElement: null,
  documentElement: { classList: { add() {}, remove() {} }, style: { setProperty() {}, removeProperty() {} } },
  createElement: fakeNode,
  createElementNS: (namespace, tag) => fakeNode(tag),
  querySelector: (selector) => pages[selector] ?? null,
  querySelectorAll: () => [],
  addEventListener() {},
  removeEventListener() {},
};

// A stand-in server: each address answers from its own queue (a reply, or a function of the
// request body that gives one); an address with nothing queued answers 200 with an empty body.
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

const { PLACE_IN_TITLE, addScope, changeWords, review, reviewLede, showRowReview, targetWords } = await import('../../src/kitden/web/static/js/review.js');
const { closePanel, isPanelOpen, openPanel, panelState } = await import('../../src/kitden/web/static/js/panel.js');
const { addToTray, cancelTray, tray } = await import('../../src/kitden/web/static/js/tray.js');
const { busy, state } = await import('../../src/kitden/web/static/js/store.js');

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const PREVIEW = '/api/batch/preview';
const LIST = '/api/changes/preview';

// Add missing in project p1: two servers Claude Code has and Codex lacks, `chosen` ticked.
const ALIGN = { action: 'project.align', targets: [], params: { project: 'p1', chosen: null } };
const candidate = (key, chosen) => ({ key, name: key, kind: 'mcp_server', from: 'claude_code', to: 'codex', place: 'all', note: null, chosen: chosen.includes(key) });
const alignOf = (chosen) => ({ candidates: [candidate('github', chosen), candidate('neon', chosen)], not_same: [], left_out: [] });
const stepsOf = (chosen) => chosen.map((name) => ({ client: 'codex', name, path: '/Users/me/.codex/config.toml', diff: '+x' }));
// The list as /api/changes/preview gives it: with nothing ticked there is no change yet, so no id.
const listing = (chosen) => ({
  status: 200,
  json: { ...(chosen.length ? { id: `a${chosen.length}`, state: 'previewed' } : {}), action: 'project.align', steps: stepsOf(chosen), after: [], target: null, align: alignOf(chosen) },
});
// The server's answer to a batch: one step per request, each row naming its step; an Add missing
// row also carries its list.
const SCOPE = { scope: 'all', project: null, others_unchanged: false };
const previewed = (id) => (sent) => ({
  status: 200,
  json: {
    id, action: 'batch', state: 'previewed', error: null, target: SCOPE, undo_note: null,
    steps: sent.requests.map((request) => ({ client: 'codex', name: request.params.item || 'missing', path: '/Users/me/.codex/config.toml', diff: '+x' })),
    rows: sent.requests.map((request, index) => ({
      id: request.id, kind: request.kind, title: request.title, detail: request.detail, project: null, steps: [index], target: SCOPE, after: [], undo_note: null,
      ...(request.kind === 'project.align' ? { align: alignOf(request.params.chosen) } : {}),
    })),
  },
});
const refusal = (detail) => ({ status: 422, json: { detail, row: null } });
const ADD = { action: 'mcp.add', targets: [{ client: 'codex' }], params: { item: 'github' } };

// A changed tick: the box of `key` in Details is set, and its listeners run.
async function tick(key, checked) {
  const box = tagged(pages['#drawer'], 'input').find((node) => node.dataset.key === key);
  box.checked = checked;
  await Promise.all(box.listeners.change.map((listener) => listener({})));
  await settle();
}

// An empty tray, a closed panel and a quiet server in every test.
async function fresh() {
  await cancelTray();
  await settle();
  pages['#drawer'].replaceChildren();
  pages['#drawer'].classList.remove('open');
  panelState.current = null;
  panelState.from = null;
  calls.length = 0;
  replies.clear();
  state.project = '';
  globalThis.document.activeElement = null;
}

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
  assert.deepEqual([changeWords(update).title, changeWords(update).done], ['Update Kitden in Claude Code', 'Updated Kitden in Claude Code']);
  const keychain = { action: 'gateway.keychain', steps: [{ client: 'kitden', name: 'files' }], target: target('all') };
  assert.equal(changeWords(keychain, { params: { server: 'files' } }).title, 'Move the secrets of files to the Keychain');
  const gone = { action: 'gateway.remove', steps: [{ client: 'kitden', name: 'files' }], target: target('mixed') };
  assert.equal(changeWords(gone, { params: { server: 'files' } }).done, 'Removed files from the Kitden gateway');
});

test('adding a marketplace server names the Kitden gateway and no scope', () => {
  assert.ok(PLACE_IN_TITLE.includes('gateway.add'));
  // The server's own step comes first; a PATH step and Codex's timeouts may follow.
  const steps = [{ client: 'kitden', name: 'test-status' }, { client: 'codex', name: 'kitden' }];
  const add = { action: 'gateway.add', steps, target: target('all') };
  const words = { title: 'Add test-status to the Kitden gateway', done: 'Added test-status to the Kitden gateway' };
  assert.deepEqual(changeWords(add, { params: { server: 'test-helper@demo-market/test-status' } }), words);
  assert.deepEqual(changeWords({ ...add, target: undefined }), words);
  // It is an add: the lede says it is for all projects.
  assert.equal(reviewLede(add, ''), 'Adds for all projects. Nothing is written until you press Apply. A backup is kept.');
});

test('a skill rule says what it turns off and where', () => {
  const step = (client, name) => ({ client, name });
  const off = (scope) => ({ action: 'skill.rule', steps: [step('claude_code', 'deploy')], target: scope });
  const body = (params) => ({ params });
  assert.deepEqual(changeWords(off(target('all')), body({ scope: 'all', off: true })), { title: 'Turn off deploy for all projects', done: 'Turned off deploy for all projects' });
  const here = target('project', '/Users/me/work/website', true);
  assert.deepEqual(changeWords(off(here), body({ scope: 'project', project: 'p1', off: true })), { title: 'Turn off deploy in website', done: 'Turned off deploy in website' });
  // A plugin goes by its short name.
  const plugin = { action: 'skill.rule', steps: [step('claude_code', 'superpowers@demo-market')], target: here };
  assert.equal(changeWords(plugin, body({ scope: 'project', project: 'p1', off: true })).title, 'Turn off superpowers in website');
  // Back to the shared rule: the project's own key goes.
  assert.deepEqual(changeWords(off(here), body({ scope: 'project', project: 'p1', off: false })), { title: 'Use the shared rule for deploy in website', done: 'deploy uses the shared rule in website' });
});

test('connecting a client to Kitden and disconnecting it name their place and no scope', () => {
  for (const action of ['setup_server.register', 'client.disconnect']) assert.ok(PLACE_IN_TITLE.includes(action), action);
  const connect = { action: 'setup_server.register', steps: [{ client: 'cursor', name: 'kitden' }], target: target('all') };
  assert.deepEqual(changeWords(connect), { title: 'Connect Cursor to Kitden', done: 'Connected Cursor to Kitden' });
  // Several clients, in the page's order.
  const two = { ...connect, steps: [{ client: 'codex', name: 'kitden' }, { client: 'claude_code', name: 'kitden' }] };
  assert.deepEqual(changeWords(two), { title: 'Connect Claude Code and Codex to Kitden', done: 'Connected Claude Code and Codex to Kitden' });
  const gone = { action: 'client.disconnect', steps: [{ client: 'codex', name: 'kitden' }], target: target('all') };
  assert.deepEqual(changeWords(gone), { title: 'Disconnect Codex from Kitden', done: 'Disconnected Codex from Kitden' });
  // The same without a target, as a change from before the server named it.
  assert.equal(changeWords({ ...gone, target: undefined }).title, 'Disconnect Codex from Kitden');
  assert.equal(changeWords({ ...connect, target: undefined }).title, 'Connect Cursor to Kitden');
  // Neither is an add that needs a scope in its lede.
  assert.equal(addScope('setup_server.register', ''), null);
  assert.equal(addScope('client.disconnect', ''), null);
  assert.equal(reviewLede({ action: 'client.disconnect' }, ''), 'Nothing is written until you press Apply. A backup is kept.');
});

test('moving a server out of the gateway names the server and the client, and no scope', () => {
  assert.ok(PLACE_IN_TITLE.includes('gateway.move_out'));
  // The client's own step comes first; the gateway's settings steps are not a client.
  const steps = [{ client: 'codex', name: 'files' }, { client: 'kitden', name: 'files' }, { client: 'kitden', name: 'files' }];
  const out = { action: 'gateway.move_out', steps, target: target('all') };
  const words = { title: 'Move files out of the gateway into Codex', done: 'Moved files into Codex' };
  assert.deepEqual(changeWords(out, { params: { server: 'files' } }), words);
  // The same without the preview's body, and without a target.
  assert.deepEqual(changeWords({ ...out, target: undefined }), words);
  // It writes a client's file, but its title says its place: no scope in the lede.
  assert.equal(addScope('gateway.move_out', ''), null);
  assert.equal(reviewLede({ action: 'gateway.move_out' }, ''), 'Nothing is written until you press Apply. A backup is kept.');
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

test('review adds a row and opens nothing', async () => {
  await fresh();
  // Details are open: the press adds its row and they stay as they are.
  panelState.current = { type: 'item', row: {} };
  const details = fakeNode('div');
  openPanel([details]);
  const shown = panelState.current;
  queue(PREVIEW, previewed('c1'));
  await review(ADD, { note: 'Adds for all projects.' });
  assert.deepEqual(posted(), [PREVIEW]); // never a review of its own
  assert.deepEqual(calls[0].body.requests.map((r) => [r.kind, r.targets, r.params]), [['mcp.add', [{ client: 'codex' }], { item: 'github' }]]);
  assert.deepEqual(tray.rows.map((r) => [r.body, r.note]), [[ADD, 'Adds for all projects.']]);
  assert.equal(panelState.current, shown);
  assert.deepEqual(pages['#drawer'].children, [details]);
  // Closed, nothing opens either.
  pages['#drawer'].classList.remove('open');
  queue(PREVIEW, previewed('c2'));
  await review({ ...ADD, params: { item: 'neon' } });
  assert.equal(isPanelOpen(), false);
  assert.equal(tray.rows.length, 2);
});

test('Add missing opens its chooser and adds the row', async () => {
  await fresh();
  queue(LIST, listing([]));
  await review(ALIGN, { note: 'For this project.' });
  // The list shows in Details, with no Apply of its own; nothing is in the tray yet.
  const drawer = pages['#drawer'];
  assert.equal(isPanelOpen(), true);
  assert.equal(panelState.current.type, 'align');
  assert.equal(all(drawer).some((node) => node.classList.contains('apply')), false);
  assert.equal(/Enter to apply/.test(drawer.textContent), false);
  assert.match(drawer.textContent, /For this project\./);
  assert.equal(tray.rows.length, 0);
  // Nothing ticked: "Add to preview" waits for a box.
  assert.match(drawer.textContent, /Choose at least one item\./);
  assert.equal(button(drawer, 'Add to preview').disabled, true);
  assert.deepEqual(tagged(drawer, 'footer')[0].children.map((node) => node.textContent), ['Cancel', 'Add to preview']);
  // A tick asks for the list again with that choice; the server forgets the list's own preview at
  // once, since only the tray is ever applied.
  queue(LIST, listing(['neon']));
  await tick('neon', true);
  assert.deepEqual(calls.filter((call) => call.url === LIST).map((call) => call.body.params.chosen), [null, ['neon']]);
  assert.deepEqual(posted().filter((url) => url.endsWith('/cancel')), ['/api/changes/a1/cancel']);
  const add = button(pages['#drawer'], 'Add to preview');
  assert.equal(add.disabled, false);
  // "Add to preview" closes the list and adds the row with the ticks.
  queue(PREVIEW, previewed('c1'));
  await add.click();
  await settle();
  assert.equal(isPanelOpen(), false);
  assert.deepEqual(tray.rows.map((r) => [r.key, r.body.params.chosen, r.note]), [['align:p1', ['neon'], 'For this project.']]);
  assert.equal(posted().filter((url) => url === LIST).length, 2);
});

test('a refused add calls back with the reason', async () => {
  await fresh();
  const heard = [];
  const back = async (answer) => { heard.push(answer); };
  queue(PREVIEW, refusal('Choose a known item.'));
  await review(ADD, { back });
  assert.deepEqual(heard, [{ error: 'Choose a known item.' }]);
  assert.equal(tray.rows.length, 0);
  // Joined: the way back hears that it waits in the tray.
  queue(PREVIEW, previewed('c1'));
  await review(ADD, { back });
  assert.deepEqual(heard.at(-1), { queued: true });
  // With no way back a refusal opens nothing: the tray's bar says why.
  queue(PREVIEW, refusal('No.'));
  await review({ ...ADD, params: { item: 'neon' } });
  assert.equal(isPanelOpen(), false);
  assert.deepEqual(tray.refused, { reason: 'No.' });
  assert.equal(tray.rows.length, 1);
  // An add that cannot even be asked (a change is being written) hands on no earlier reason.
  const heardBefore = heard.length;
  busy.change = true;
  try {
    assert.equal(await addToTray({ ...ADD, params: { item: 'sqlite' } }), false);
    await review({ ...ADD, params: { item: 'sqlite' } }, { back });
  } finally {
    busy.change = false;
  }
  assert.equal(heard.length, heardBefore);
});

test('a refusal that goes back to a tool list names a file, not its path', async () => {
  await fresh();
  const heard = [];
  queue(PREVIEW, refusal('/Users/me/.cursor/mcp.json has a hard link; so has ~/.codex/config.toml.'));
  await review(ADD, { back: async (answer) => { heard.push(answer); } });
  assert.deepEqual(heard, [{ error: 'mcp.json has a hard link; so has config.toml.' }]);
});

test('a review shows a note once when its After line says the same', async () => {
  await fresh();
  const NOTE_TWICE = "Codex loses the Kitden gateway's servers. Servers it sets up on its own stay.";
  queue(PREVIEW, (sent) => {
    const answer = previewed('c1')(sent);
    answer.json.rows[0].after = [{ client: 'codex', state: 'off', word: 'Off', note: NOTE_TWICE }];
    return answer;
  });
  await addToTray(ADD, { note: NOTE_TWICE });
  showRowReview(tray.rows[0]);
  assert.equal(pages['#drawer'].textContent.split(NOTE_TWICE).length - 1, 1);
  // A different note is still shown beside it.
  await fresh();
  queue(PREVIEW, (sent) => {
    const answer = previewed('c2')(sent);
    answer.json.rows[0].after = [{ client: 'codex', state: 'off', word: 'Off', note: NOTE_TWICE }];
    return answer;
  });
  await addToTray(ADD, { note: 'Adds for all projects.' });
  showRowReview(tray.rows[0]);
  assert.match(pages['#drawer'].textContent, /Adds for all projects\./);
  assert.equal(pages['#drawer'].textContent.split(NOTE_TWICE).length - 1, 1);
});

test("a row review's Take it out stops following the tray when its review closes", async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(ADD);
  showRowReview(tray.rows[0]);
  const out = button(pages['#drawer'], 'Take it out');
  let follows = 0;
  const real = out.removeAttribute;
  out.removeAttribute = (name) => { follows += 1; real(name); };
  // While its review is open it follows the tray.
  await addToTray({ ...ADD, params: { item: 'neon' } });
  assert.ok(follows > 0);
  closePanel();
  follows = 0;
  await addToTray({ ...ADD, params: { item: 'sqlite' } });
  assert.equal(follows, 0);
});

test('a list that answers after another project was picked opens nothing, and the server forgets it', async () => {
  await fresh();
  let answer;
  queue(LIST, () => new Promise((resolve) => { answer = resolve; }));
  state.project = 'p1';
  const pending = review(ALIGN);
  state.project = 'p2';
  answer(listing(['neon']));
  await pending;
  await settle();
  assert.equal(isPanelOpen(), false);
  assert.deepEqual(posted().filter((url) => url.endsWith('/cancel')), ['/api/changes/a1/cancel']);
  assert.equal(tray.rows.length, 0);
});

test('showRowReview has no Apply and takes the row out', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(ADD, { note: 'Adds for all projects.' });
  showRowReview(tray.rows[0]);
  const drawer = pages['#drawer'];
  assert.equal(panelState.current.type, 'row-review');
  assert.equal(all(drawer).some((node) => node.classList.contains('apply')), false);
  assert.equal(/Enter to apply/.test(drawer.textContent), false);
  assert.match(drawer.textContent, /Adds for all projects\./);
  assert.deepEqual(tagged(drawer, 'footer')[0].children.map((node) => node.textContent), ['Take it out', 'Close']);
  await button(drawer, 'Take it out').click();
  await settle();
  assert.equal(isPanelOpen(), false);
  assert.equal(tray.rows.length, 0);
});

test("an Add missing row's review shows its ticks, and a changed tick adds the row again", async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray({ ...ALIGN, params: { project: 'p1', chosen: ['neon'] } });
  showRowReview(tray.rows[0]);
  const boxes = () => tagged(pages['#drawer'], 'input').map((node) => [node.dataset.key, node.checked]);
  assert.deepEqual(boxes(), [['github', false], ['neon', true]]);
  // The same key: the new row takes the old one's place, and the review shows it.
  queue(PREVIEW, previewed('c2'));
  await tick('github', true);
  assert.deepEqual(tray.rows.map((r) => [r.key, r.body.params.chosen]), [['align:p1', ['github', 'neon']]]);
  assert.equal(panelState.current.row, tray.rows[0]);
  assert.deepEqual(boxes(), [['github', true], ['neon', true]]);
  // A refused choice leaves the row as it was, and the review shows it so.
  queue(PREVIEW, refusal('No.'));
  await tick('neon', false);
  assert.deepEqual(tray.rows.map((r) => r.body.params.chosen), [['github', 'neon']]);
  assert.deepEqual(boxes(), [['github', true], ['neon', true]]);
  // No tick at all: nothing to add, the row stays, and the review says to choose one.
  queue(PREVIEW, previewed('c3'));
  await tick('github', false);
  assert.deepEqual(tray.rows.map((r) => r.body.params.chosen), [['neon']]);
  const asked = calls.length;
  await tick('neon', false);
  assert.equal(calls.length, asked);
  assert.match(pages['#drawer'].textContent, /Choose at least one item\./);
  assert.equal(tray.rows.length, 1);
});

// Final wave: one motion per change. After Apply or Undo the Library morphs its cells, the
// Gateway map lands its rows and Changes draws the Undo on its row, so none cross-fades the page;
// the Gateway List and other places do.
test('the effect of a change draws the Gateway map, the Library and Changes with no cross-fade', async () => {
  const { showEffect } = await import('../../src/kitden/web/static/js/review.js');
  const { reducedMotion } = await import('../../src/kitden/web/static/js/motion.js');
  const { gatewayShows, setRenderer } = await import('../../src/kitden/web/static/js/store.js');
  const fades = [];
  let renders = 0;
  setRenderer(() => { renders += 1; });
  globalThis.document.startViewTransition = (change) => {
    fades.push(state.view);
    change();
    return { finished: Promise.resolve(), ready: Promise.resolve(), skipTransition() {} };
  };
  reducedMotion.matches = false;
  const was = state.view;
  try {
    for (const [view, mode, fade] of [['gateway', 'map', false], ['gateway', 'list', true], ['library', '', false], ['changes', '', false], ['agents', '', true]]) {
      fades.length = 0;
      renders = 0;
      state.view = view;
      gatewayShows.mode = mode;
      showEffect();
      assert.deepEqual([fades.length > 0, renders], [fade, 1], `${view} ${mode}`);
    }
  } finally {
    delete globalThis.document.startViewTransition;
    reducedMotion.matches = true;
    state.view = was;
    gatewayShows.mode = '';
    setRenderer(() => {});
  }
});

// Final wave: Add missing's list that the server refuses names a file by its base name.
test("a refused Add missing list names a file, not its path", async () => {
  await fresh();
  queue(LIST, refusal('Could not read /Users/me/.codex/config.toml.'));
  await review(ALIGN);
  const text = pages['#drawer'].textContent;
  assert.match(text, /Could not read config\.toml\./);
  assert.doesNotMatch(text, /\/Users\/me/);
  closePanel({ instant: true, focus: false });
});

// Final wave: a row's review drawn again leaves its old Take it out behind: that one stops
// following the tray.
test("a row's review drawn again: the old Take it out stops following the tray", async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(ADD);
  showRowReview(tray.rows[0]);
  const old = button(pages['#drawer'], 'Take it out');
  showRowReview(tray.rows[0]);
  const now = button(pages['#drawer'], 'Take it out');
  assert.notEqual(old, now);
  let answer;
  queue('/api/changes/c1/apply', () => new Promise((resolve) => { answer = resolve; }));
  const { applyTray } = await import('../../src/kitden/web/static/js/tray.js');
  const applying = applyTray();
  await settle();
  assert.equal(tray.phase, 'applying');
  assert.deepEqual([now.getAttribute('aria-disabled'), old.getAttribute('aria-disabled')], ['true', null]);
  answer({ status: 200, json: { id: 'c1', state: 'restored', error: 'Put back.' } });
  await applying;
  await settle();
  closePanel({ instant: true, focus: false });
});

// Add missing under All projects: what one client has for all projects and another lacks, only
// plugins and skills (MCP servers stay with the Gateway).
const EVERYWHERE = { action: 'project.align', targets: [], params: { project: null, chosen: null } };
const everywhere = (chosen) => {
  const one = (key, kind) => ({ key, name: key, kind, from: 'claude_code', to: 'codex', place: 'all', note: null, chosen: chosen.includes(key) });
  return {
    status: 200,
    json: { ...(chosen.length ? { id: `e${chosen.length}`, state: 'previewed' } : {}), action: 'project.align', steps: stepsOf(chosen), after: [], target: null, align: { candidates: [one('brandkit', 'skill'), one('linter@official', 'plugin')], not_same: [], left_out: [] } },
  };
};

test('Add missing under All projects lists what one client has and another lacks', async () => {
  await fresh();
  queue(LIST, everywhere(['brandkit']));
  await review(EVERYWHERE);
  const drawer = pages['#drawer'];
  assert.equal(panelState.current.type, 'align');
  assert.equal(tagged(drawer, 'h1')[0].textContent, 'Add what your clients are missing');
  assert.deepEqual(tagged(drawer, 'legend').map((node) => node.textContent), ['Add to Codex']);
  assert.match(drawer.textContent, /brandkit · Skill · from Claude Code · all projects/);
  assert.match(drawer.textContent, /linter@official · Plugin · from Claude Code · all projects/);
  assert.doesNotMatch(drawer.textContent, /MCP server/);
  assert.deepEqual(calls.filter((call) => call.url === LIST).map((call) => [call.body.params.project, call.body.picked]), [[null, null]]);
  // "Add to preview" adds one row for all projects; its done words say so.
  queue(PREVIEW, previewed('c1'));
  await button(drawer, 'Add to preview').click();
  await settle();
  assert.deepEqual(tray.rows.map((r) => [r.key, r.body.params]), [['align:', { project: null, chosen: ['brandkit'] }]]);
  const change = { action: 'project.align', steps: stepsOf(['brandkit']), align: everywhere(['brandkit']).json.align };
  assert.deepEqual(changeWords(change, EVERYWHERE), { title: 'Add what your clients are missing', done: 'Added 1 item for all projects' });
});

test('with nothing missing it says Nothing is missing. and adds nothing', async () => {
  await fresh();
  queue(LIST, refusal('Nothing is missing.'));
  await review(EVERYWHERE);
  const drawer = pages['#drawer'];
  // An answer, not a failure: the title says it, with no error and only Close.
  assert.equal(isPanelOpen(), true);
  assert.equal(tagged(drawer, 'h1')[0].textContent, 'Nothing is missing.');
  assert.doesNotMatch(drawer.textContent, /Could not prepare/);
  assert.equal(all(drawer).some((node) => node.classList.contains('error')), false);
  assert.deepEqual(tagged(drawer, 'footer')[0].children.map((node) => node.textContent), ['Close']);
  assert.equal(tray.rows.length, 0);
  assert.deepEqual(posted(), [LIST]);
  closePanel({ instant: true, focus: false });
});

// Final fix wave: with Library Details open (they are what a refusal goes back to), "Nothing is
// missing." is still the calm answer, never a red error in those Details.
test('with Details open, Nothing is missing. is still the calm answer', async () => {
  await fresh();
  const { keepFrom } = await import('../../src/kitden/web/static/js/panel.js');
  let drawn = 0;
  keepFrom(() => { drawn += 1; }, []);
  queue(LIST, refusal('Nothing is missing.'));
  await review(EVERYWHERE);
  await settle();
  const drawer = pages['#drawer'];
  assert.equal(drawn, 0);
  assert.equal(tagged(drawer, 'h1')[0].textContent, 'Nothing is missing.');
  assert.equal(all(drawer).some((node) => node.classList.contains('error')), false);
  // A real refusal still goes back to those Details, with its reason.
  queue(LIST, refusal('Could not read config.toml.'));
  keepFrom(() => { drawn += 1; }, []);
  await review(EVERYWHERE);
  await settle();
  assert.equal(drawn, 1);
  closePanel({ instant: true, focus: false });
});
