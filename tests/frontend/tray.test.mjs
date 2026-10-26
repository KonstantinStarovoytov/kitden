import assert from 'node:assert/strict';
import { test } from 'node:test';

// tray.js needs only this from a browser to load.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;

// A stand-in document: tray.js listens for the progress events of a running change.
const listeners = new Map();
globalThis.document = {
  addEventListener(type, listener) { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(listener); },
  removeEventListener(type, listener) { if (listeners.has(type)) listeners.get(type).delete(listener); },
  fire(type, detail) { for (const listener of [...(listeners.get(type) || [])]) listener({ detail }); },
};
const listening = () => (listeners.get('kitden:progress') || new Set()).size;

// A stand-in server. Every request is recorded as it is made. Each address answers from its own
// queue: a reply, a function of the request body that returns one, or either one as a promise.
// An address with nothing queued answers 200 with an empty body.
const calls = [];
const replies = new Map();
const standIn = (url, init = {}) => {
  const call = { url, method: init.method || 'GET', body: init.body ? JSON.parse(init.body) : null };
  calls.push(call);
  const waiting = replies.get(url) || [];
  const next = waiting.length ? waiting.shift() : { status: 200, json: {} };
  const reply = typeof next === 'function' ? next(call.body) : next;
  return Promise.resolve(reply).then((made) => ({ ok: made.status < 400, status: made.status, json: async () => made.json }));
};
globalThis.fetch = standIn;
const queue = (url, ...items) => replies.set(url, [...(replies.get(url) || []), ...items]);
const asked = (url) => calls.filter((call) => call.url === url);
const urls = () => calls.map((call) => `${call.method} ${call.url}`);

const { PENDING_TITLE, addToTray, applyTray, cancelTray, checkTrayStale, endApplied, iconFor, inTray, keyFor, onTray, partOf, setTrayWords, takeOut, tray, tryAgain } = await import('../../src/kitden/web/static/js/tray.js');
const { busy, setBusy, state } = await import('../../src/kitden/web/static/js/store.js');

const PREVIEW = '/api/batch/preview';
const add = (name) => ({ action: 'mcp.add', targets: [{ client: 'codex' }], params: { item: name } });
const target = { scope: 'all', project: null, others_unchanged: false };

// The server's answer to a batch: one step per request, each row naming its step.
const batch = (id, requests) => ({
  status: 200,
  json: {
    id, action: requests.length === 1 ? requests[0].kind : 'batch', state: 'previewed', error: null, target,
    steps: requests.map((request) => ({ client: 'codex', name: request.params.item })),
    undo_note: null,
    rows: requests.map((request, index) => ({
      id: request.id, kind: request.kind, title: request.title, detail: request.detail, project: null, steps: [index],
      target, after: [`after ${request.params.item}`], undo_note: null,
    })),
  },
});
// A preview that answers with this change id, whatever was asked.
const previewed = (id) => (sent) => batch(id, sent.requests);
// A preview that waits until `release()`, then answers as `previewed(id)` would.
function slowPreview(id) {
  let release;
  let sent = null;
  const held = new Promise((resolve) => { release = resolve; });
  return { reply: (body) => { sent = body; return held; }, release: () => release(batch(id, sent.requests)) };
}
// Any other reply that waits until `release(reply)`.
function slow() {
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  return { reply: () => held, release };
}
const refusal = (detail, row = null) => ({ status: 422, json: { detail, row } });
const verified = (id) => ({ status: 200, json: { id, state: 'verified', steps: [] } });
async function quietly(fn) {
  const log = console.error;
  console.error = () => {};
  try { return await fn(); } finally { console.error = log; }
}

// The tray starts empty and the stand-in server starts quiet in every test.
async function fresh() {
  await cancelTray();
  endApplied();
  calls.length = 0;
  replies.clear();
  state.project = '';
}
// Two rows in the tray, answered as change `c2` (the first ask answered as `c1`).
async function twoRows() {
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  await addToTray(add('github'));
  await addToTray(add('neon'));
}
const words = (part, body, note) => ({ title: `Add ${body.params.item}`, detail: note || '' });

// This test comes first: no words are registered yet.
test('a row asked before the words are set is sent as New change', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  assert.equal(await addToTray(add('github')), true);
  assert.equal(PENDING_TITLE, 'New change');
  assert.deepEqual(asked(PREVIEW)[0].body.requests.map((r) => [r.title, r.detail]), [['New change', '']]);
  assert.deepEqual(tray.rows.map((row) => [row.title, row.detail]), [['', '']]);
  setTrayWords(words);
});

test('keyFor names a switch by what it switches', () => {
  const on = { action: 'plugin.enable', targets: [{ item: 'i1' }], params: {} };
  const off = { action: 'plugin.disable', targets: [{ item: 'i1' }], params: {} };
  assert.equal(keyFor(on), keyFor(off));
  assert.equal(keyFor(on), 'switch:i1');
  assert.notEqual(keyFor(on), keyFor({ ...on, targets: [{ item: 'i2' }] }));
  const rule = (state, project) => ({ action: 'gateway.rule', targets: [], params: { server: 'files', tool: 'read_file', state, project } });
  assert.equal(keyFor(rule('on')), keyFor(rule('off')));
  assert.equal(keyFor(rule('on', 'p1')), 'rule:files/read_file@p1');
  assert.equal(keyFor(rule('on')), 'rule:files/read_file@');
  assert.notEqual(keyFor(rule('on', 'p1')), keyFor(rule('on')));
  assert.equal(keyFor({ action: 'gateway.strict', targets: [], params: { server: 'files', state: 'on' } }), 'strict:files');
  assert.equal(keyFor({ action: 'project.align', targets: [], params: { project: 'p1', chosen: null } }), 'align:p1');
  // A marketplace server added to the Kitden gateway is keyed by its row in the Add panel.
  assert.equal(keyFor({ action: 'gateway.add', targets: [], params: { server: 'db-tools@demo-market/db-query' } }), 'add:db-tools@demo-market/db-query');
  // Any other change: its action, targets and params, whatever order the params came in.
  const first = { action: 'mcp.add', targets: [{ client: 'codex' }], params: { item: 'x', scope: 'user' } };
  const second = { action: 'mcp.add', targets: [{ client: 'codex' }], params: { scope: 'user', item: 'x' } };
  assert.equal(keyFor(first), keyFor(second));
  assert.notEqual(keyFor(first), keyFor({ ...first, params: { item: 'y', scope: 'user' } }));
});

test('a server moves out to one client: another pick replaces its row', async () => {
  const out = (client, server = 'files') => ({ action: 'gateway.move_out', targets: [{ client }], params: { server } });
  assert.equal(keyFor(out('codex')), 'moveout:files');
  assert.equal(keyFor(out('cursor')), keyFor(out('codex')));
  assert.notEqual(keyFor(out('codex', 'tracker')), keyFor(out('codex')));
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  try {
    await addToTray(out('codex'));
    await addToTray(out('cursor'));
    // Two moves of one server into two clients never wait in one tray: the second replaces the first.
    assert.deepEqual(tray.rows.map((row) => [row.key, row.body.targets[0].client]), [['moveout:files', 'cursor']]);
  } finally {
    await cancelTray();
  }
});

test("iconFor picks the mockup's icon", () => {
  const icon = (action, params = {}) => iconFor({ action, targets: [], params });
  assert.equal(icon('gateway.remove'), 'x');
  for (const action of ['mcp.remove_direct', 'plugin.remove', 'skill.remove']) assert.equal(icon(action), 'x', action);
  assert.equal(icon('gateway.rule', { project: 'p1' }), 'folder');
  assert.equal(icon('project.align', { project: 'p1' }), 'folder');
  assert.equal(icon('gateway.rule', { server: 's', project: null }), 'toggle-right');
  for (const action of ['gateway.rules', 'gateway.strict', 'plugin.enable', 'plugin.disable', 'setup_server.enable']) assert.equal(icon(action), 'toggle-right', action);
  for (const action of ['gateway.move', 'gateway.put_back', 'gateway.keychain']) assert.equal(icon(action), 'arrow-right', action);
  assert.equal(icon('gateway.move_out', { server: 'files' }), 'log-out');
  for (const action of ['gateway.connect', 'gateway.switch', 'setup_server.register', 'setup_server.update', 'client.disconnect']) assert.equal(icon(action), 'plug', action);
  for (const action of ['plugin.install', 'skill.install', 'mcp.add', 'marketplace.add', 'plugin.skills', 'gateway.add']) assert.equal(icon(action), 'plus', action);
  assert.equal(icon('something.else'), 'file-text');
});

test('partOf is the change as one row sees it', () => {
  const change = { id: 'c1', action: 'batch', state: 'previewed', steps: ['s0', 's1', 's2'], rows: [{ id: 'r1' }], target: { scope: 'all' }, undo_note: 'whole' };
  const row = { id: 'r1', kind: 'skill.install', steps: [2, 0], target: { scope: 'project' }, after: ['x'], undo_note: 'mine', left_out: ['y'], align: { z: 1 } };
  const part = partOf(change, row);
  assert.equal(part.action, 'skill.install');
  assert.deepEqual(part.steps, ['s2', 's0']);
  assert.deepEqual([part.target, part.after, part.undo_note, part.left_out, part.align], [{ scope: 'project' }, ['x'], 'mine', ['y'], { z: 1 }]);
  assert.equal(part.id, 'c1'); // the same change, so its review can say which one it is
  assert.equal('rows' in part, false);
  assert.equal(partOf(change, { id: 'r2', kind: 'mcp.add', steps: [1], target: null, after: [], undo_note: null }).left_out, undefined);
});

test('an add previews every row as one change', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  assert.equal(await addToTray(add('github'), { note: 'Note A' }), true);
  assert.equal(tray.phase, 'ready');
  assert.equal(tray.change.id, 'c1');
  assert.equal(await addToTray(add('neon')), true);
  const [one, two] = asked(PREVIEW);
  assert.equal(one.body.requests.length, 1);
  assert.deepEqual(two.body.requests.map((r) => [r.kind, r.title, r.detail, r.targets, r.params, r.picked]), [
    ['mcp.add', 'Add github', 'Note A', [{ client: 'codex' }], { item: 'github' }, null],
    ['mcp.add', 'New change', '', [{ client: 'codex' }], { item: 'neon' }, null],
  ]);
  assert.equal('picked' in two.body, false); // each request carries its own
  assert.equal(tray.phase, 'ready');
  assert.equal(tray.change.id, 'c2');
  assert.deepEqual(tray.rows.map((row) => [row.title, row.detail, row.status, row.icon]), [['Add github', 'Note A', '', 'plus'], ['Add neon', '', '', 'plus']]);
  // The first change is gone from the server once the second answered, and only then.
  assert.ok(urls().indexOf('POST /api/changes/c1/cancel') > urls().lastIndexOf(`POST ${PREVIEW}`));
  assert.equal(asked('/api/changes/c2/cancel').length, 0);
  // Each row is its own part of the change.
  assert.deepEqual(tray.rows.map((row) => row.part.steps), [[{ client: 'codex', name: 'github' }], [{ client: 'codex', name: 'neon' }]]);
  assert.deepEqual(tray.rows.map((row) => row.part.after), [['after github'], ['after neon']]);
  assert.equal(inTray(tray.rows[0].key), true);
  assert.equal(inTray('nothing'), false);
});

test('an add with the same key replaces the row and puts it last', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'), previewed('c3'));
  await addToTray(add('github'), { note: 'old' });
  await addToTray(add('neon'));
  await addToTray(add('github'), { note: 'new' });
  assert.deepEqual(asked(PREVIEW)[2].body.requests.map((r) => r.params.item), ['neon', 'github']);
  assert.deepEqual(tray.rows.map((row) => [row.title, row.detail]), [['Add neon', ''], ['Add github', 'new']]);
});

test('a row added again keeps its words and its project until its answer', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  state.project = 'p1';
  await addToTray(add('github'), { note: 'old' });
  const [old] = tray.rows;
  state.project = 'p2';
  const late = slowPreview('c2');
  queue(PREVIEW, late.reply);
  const adding = addToTray(add('github'), { note: 'new', picked: old.picked });
  // While it is asked the bar still has the row's words and its part to draw.
  assert.equal(tray.phase, 'asking');
  assert.deepEqual(tray.rows.map((row) => [row.title, row.part, row.note, row.picked]), [[old.title, old.part, 'new', 'p1']]);
  assert.deepEqual(asked(PREVIEW)[1].body.requests.map((r) => [r.title, r.picked]), [[old.title, 'p1']]);
  late.release();
  assert.equal(await adding, true);
  assert.deepEqual(tray.rows.map((row) => [row.detail, row.picked]), [['new', 'p1']]);
  state.project = '';
});

test('a refused add that would replace a row puts the old row back', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'), refusal('No.'));
  await addToTray(add('github'), { note: 'old' });
  await addToTray(add('neon'));
  const rows = [...tray.rows];
  assert.equal(await addToTray(add('github'), { note: 'new' }), false);
  assert.deepEqual(tray.rows, rows);
  assert.equal(tray.rows[0].detail, 'old');
  assert.equal(tray.change.id, 'c2');
  assert.equal(tray.phase, 'ready');
});

test('an older answer is dropped and its change cancelled', async () => {
  await fresh();
  const late = slowPreview('c1');
  queue(PREVIEW, late.reply, previewed('c2'));
  const first = addToTray(add('github'));
  const second = addToTray(add('neon'));
  // The second ask holds both rows, the first still unanswered.
  assert.deepEqual(asked(PREVIEW)[1].body.requests.map((r) => r.params.item), ['github', 'neon']);
  assert.equal(await second, true);
  assert.equal(tray.change.id, 'c2');
  late.release();
  assert.equal(await first, true); // its row is in the tray, inside the second change
  assert.equal(tray.change.id, 'c2');
  assert.equal(tray.phase, 'ready');
  assert.equal(asked('/api/changes/c1/cancel').length, 1);
  assert.equal(asked('/api/changes/c2/cancel').length, 0);
  assert.deepEqual(tray.rows.map((row) => row.title), ['Add github', 'Add neon']);
});

test('a refused add does not join', async () => {
  await fresh();
  const reason = 'Choose a server in the Kitden gateway.';
  queue(PREVIEW, previewed('c1'), (sent) => refusal(reason, sent.requests[1].id), previewed('c3'));
  await addToTray(add('github'));
  const rows = [...tray.rows];
  const change = tray.change;
  assert.equal(await addToTray(add('neon')), false);
  assert.deepEqual(tray.rows, rows);
  assert.equal(tray.change, change);
  assert.equal(tray.phase, 'ready');
  assert.deepEqual(tray.refused, { reason });
  assert.equal(inTray(keyFor(add('neon'))), false);
  assert.equal(asked('/api/changes/c1/cancel').length, 0); // the change still stands
  // The next add clears it.
  assert.equal(await addToTray(add('slack')), true);
  assert.equal(tray.refused, null);
  assert.deepEqual(tray.rows.map((row) => row.title), ['Add github', 'Add slack']);
});

test('a refused first add leaves an empty tray that says why', async () => {
  await fresh();
  queue(PREVIEW, refusal('Nothing to change.', null));
  assert.equal(await addToTray(add('github')), false);
  assert.deepEqual(tray.rows, []);
  assert.equal(tray.change, null);
  assert.equal(tray.phase, 'idle');
  assert.deepEqual(tray.refused, { reason: 'Nothing to change.' });
  await cancelTray(); // Close
  assert.equal(tray.refused, null);
});

test('an answer with no words and a lost connection both give a reason', async () => {
  await fresh();
  queue(PREVIEW, { status: 500, json: null });
  assert.equal(await addToTray(add('github')), false);
  assert.equal(tray.refused.reason, 'Could not prepare this change (500).');
  globalThis.fetch = () => Promise.reject(new Error('offline'));
  try {
    assert.equal(await quietly(() => addToTray(add('github'))), false);
  } finally {
    globalThis.fetch = standIn;
  }
  assert.equal(tray.refused.reason, 'Could not prepare this change (0).');
  assert.equal(tray.phase, 'idle');
});

test('a refused add while another ask is out asks for the other rows again', async () => {
  await fresh();
  const late = slowPreview('c1');
  queue(PREVIEW, late.reply, (sent) => refusal('Apply the preview first, or take that one out.', sent.requests[1].id), previewed('c3'));
  const first = addToTray(add('github'));
  assert.equal(await addToTray(add('neon')), false);
  // The first ask was dropped by the second, so the refusal asked for github alone.
  assert.deepEqual(asked(PREVIEW)[2].body.requests.map((r) => r.params.item), ['github']);
  assert.equal(tray.phase, 'ready');
  assert.equal(tray.change.id, 'c3');
  assert.deepEqual(tray.refused, { reason: 'Apply the preview first, or take that one out.' });
  assert.deepEqual(tray.rows.map((row) => row.title), ['Add github']);
  late.release();
  assert.equal(await first, true);
  assert.equal(tray.change.id, 'c3');
  assert.equal(asked('/api/changes/c1/cancel').length, 1);
});

test('a row keeps the project it was asked in', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'), previewed('c2'));
  state.project = 'p1';
  await addToTray(add('github'));
  state.project = 'p2';
  await addToTray(add('neon'));
  assert.deepEqual(asked(PREVIEW)[1].body.requests.map((r) => r.picked), ['p1', 'p2']);
  assert.deepEqual(tray.rows.map((row) => row.picked), ['p1', 'p2']);
});

test('taking out the last row cancels the change', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  await takeOut('nothing in the tray has this key');
  assert.equal(tray.rows.length, 1);
  await takeOut(tray.rows[0].key);
  assert.deepEqual(tray.rows, []);
  assert.equal(tray.change, null);
  assert.equal(tray.phase, 'idle');
  assert.equal(asked('/api/changes/c1/cancel').length, 1);
  assert.equal(asked(PREVIEW).length, 1); // nothing left to preview
});

test('taking out one of two previews the rest', async () => {
  await fresh();
  await twoRows();
  const next = slowPreview('c3');
  queue(PREVIEW, next.reply);
  const out = takeOut(tray.rows[0].key);
  assert.equal(tray.phase, 'asking');
  assert.deepEqual(tray.rows.map((row) => row.title), ['Add neon']);
  // Apply waits for the new preview, so the row that left is never written.
  await applyTray();
  assert.equal(asked('/api/changes/c2/apply').length, 0);
  assert.equal(tray.phase, 'asking');
  assert.equal(busy.change, false);
  next.release();
  await out;
  assert.deepEqual(asked(PREVIEW).at(-1).body.requests.map((r) => [r.params.item, r.title]), [['neon', 'Add neon']]);
  assert.equal(tray.phase, 'ready');
  assert.equal(tray.change.id, 'c3');
  assert.equal(asked('/api/changes/c2/cancel').length, 1);
});

test('a refused take-out leaves the rows with no change', async () => {
  await fresh();
  await twoRows();
  queue(PREVIEW, refusal('Apply the preview first, or take that one out.'));
  const part = tray.rows[1].part;
  await takeOut(tray.rows[0].key);
  assert.deepEqual(tray.rows.map((row) => row.title), ['Add neon']);
  assert.equal(tray.rows[0].part, part); // its words stay
  assert.equal(tray.change, null);
  assert.equal(tray.phase, 'failed');
  assert.equal(tray.failure, null);
  assert.deepEqual(tray.refused, { reason: 'Apply the preview first, or take that one out.' });
  assert.equal(asked('/api/changes/c2/cancel').length, 1); // the old change is not left on the server
  // Try again asks the rows afresh.
  queue(PREVIEW, previewed('c4'));
  await tryAgain();
  assert.equal(tray.phase, 'ready');
  assert.equal(tray.refused, null);
  assert.equal(tray.change.id, 'c4');
  assert.equal(asked('/api/changes/c2/cancel').length, 1);
});

test('Cancel all while a preview is on its way drops the late answer', async () => {
  await fresh();
  const late = slowPreview('c1');
  queue(PREVIEW, late.reply);
  const adding = addToTray(add('github'));
  assert.equal(tray.phase, 'asking');
  await cancelTray();
  assert.equal(tray.phase, 'idle');
  assert.deepEqual(tray.rows, []);
  late.release();
  assert.equal(await adding, false);
  assert.deepEqual(tray.rows, []);
  assert.equal(tray.change, null);
  assert.equal(tray.phase, 'idle');
  assert.equal(asked('/api/changes/c1/cancel').length, 1);
});

test('apply names each row as its steps end', async () => {
  await fresh();
  await twoRows();
  const writing = slow();
  queue('/api/changes/c2/apply', writing.reply);
  const second = tray.rows[1];
  const applying = applyTray();
  assert.equal(tray.phase, 'applying');
  assert.equal(busy.change, true);
  assert.equal(listening(), 1);
  assert.deepEqual(tray.rows.map((row) => row.status), ['busy', '']); // the first row at once
  document.fire('kitden:progress', { id: 'c2', done: 1, total: 3, row: second.id });
  assert.equal(tray.done, 1);
  assert.equal(tray.total, 3);
  assert.equal(second.status, 'busy');
  writing.release(verified('c2'));
  await applying;
  assert.deepEqual(tray.rows.map((row) => row.status), ['done', 'done']);
  assert.equal(tray.phase, 'applied');
  assert.equal(tray.change.state, 'verified');
  assert.equal(tray.change.id, 'c2');
  assert.equal(busy.change, false);
  assert.equal(listening(), 0);
  assert.equal(asked('/api/changes/c2/apply').length, 1);
});

test('progress for another change or an unknown row changes only the counts', async () => {
  await fresh();
  await twoRows();
  const writing = slow();
  queue('/api/changes/c2/apply', writing.reply);
  const applying = applyTray();
  document.fire('kitden:progress', { id: 'other', done: 2, total: 4, row: tray.rows[1].id });
  assert.deepEqual([tray.done, tray.total, tray.rows[1].status], [0, 0, '']);
  document.fire('kitden:progress', { id: 'c2', done: 1, total: 3, row: null });
  assert.deepEqual([tray.done, tray.total, tray.rows[1].status], [1, 3, '']);
  document.fire('kitden:progress', { id: 'c2', done: 2, total: 3, row: 'no such row' });
  assert.deepEqual([tray.done, tray.total, tray.rows[1].status], [2, 3, '']);
  writing.release(verified('c2'));
  await applying;
});

test('applying runs only from a ready tray', async () => {
  await fresh();
  await applyTray(); // empty
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  const writing = slow();
  queue('/api/changes/c1/apply', writing.reply);
  const applying = applyTray();
  await applyTray(); // already applying
  assert.equal(asked('/api/changes/c1/apply').length, 1);
  writing.release(verified('c1'));
  await applying;
  await applyTray(); // applied
  assert.equal(asked('/api/changes/c1/apply').length, 1);
});

test('a stale apply keeps the rows', async () => {
  await fresh();
  await twoRows();
  queue('/api/changes/c2/apply', { status: 409, json: { id: 'c2', state: 'stale', error: 'Settings changed.' } });
  await applyTray();
  assert.equal(tray.phase, 'failed');
  assert.deepEqual(tray.failure, { state: 'stale', error: 'Settings changed.' });
  assert.deepEqual(tray.rows.map((row) => [row.title, row.status]), [['Add github', ''], ['Add neon', '']]);
  assert.equal(busy.change, false);
  assert.equal(listening(), 0);
  // Try again asks a fresh preview of the same rows; the person presses Apply again.
  queue(PREVIEW, previewed('c3'));
  await tryAgain();
  assert.deepEqual(asked(PREVIEW).at(-1).body.requests.map((r) => r.params.item), ['github', 'neon']);
  assert.equal(tray.phase, 'ready');
  assert.equal(tray.failure, null);
  assert.equal(tray.change.id, 'c3');
  assert.equal(asked('/api/changes/c2/apply').length, 1);
  assert.equal(asked('/api/changes/c3/apply').length, 0);
  assert.equal(asked('/api/changes/c2/cancel').length, 0); // the server ended it already
});

test('an add after a failed Apply: a new answer clears the failure, a refusal keeps it', async () => {
  await fresh();
  await twoRows();
  const failure = { state: 'stale', error: 'Settings changed.' };
  queue('/api/changes/c2/apply', { status: 409, json: { id: 'c2', ...failure } });
  await applyTray();
  assert.deepEqual([tray.phase, tray.failure], ['failed', failure]);
  // Refused: the tray is as it was, failure and all, and says why.
  queue(PREVIEW, refusal('Choose a known item.'));
  assert.equal(await addToTray(add('slack')), false);
  assert.deepEqual([tray.phase, tray.failure, tray.refused, tray.rows.length], ['failed', failure, { reason: 'Choose a known item.' }, 2]);
  // Joined: a fresh preview of every row, ready to apply.
  queue(PREVIEW, previewed('c4'));
  assert.equal(await addToTray(add('slack')), true);
  assert.deepEqual([tray.phase, tray.failure, tray.refused, tray.change.id], ['ready', null, null, 'c4']);
  assert.deepEqual(tray.rows.map((row) => row.body.params.item), ['github', 'neon', 'slack']);
  assert.equal(asked('/api/changes/c4/apply').length, 0);
});

test('an apply that did not run keeps its rows, and Try again drops the preview', async () => {
  await fresh();
  await twoRows();
  queue('/api/changes/c2/apply', { status: 422, json: { detail: 'nothing to change in ~/.claude.json' } });
  await applyTray();
  assert.equal(tray.phase, 'failed');
  assert.deepEqual(tray.failure, { state: null, error: null }); // the end is not known
  assert.deepEqual(tray.rows.map((row) => row.status), ['', '']);
  queue(PREVIEW, previewed('c3'));
  await tryAgain();
  // The change was still only previewed on the server: it goes before the new preview.
  assert.equal(asked('/api/changes/c2/cancel').length, 1);
  assert.ok(urls().indexOf('POST /api/changes/c2/cancel') < urls().lastIndexOf(`POST ${PREVIEW}`));
  assert.equal(tray.phase, 'ready');
});

test('a refused Try again keeps the rows and says why', async () => {
  await fresh();
  await twoRows();
  queue('/api/changes/c2/apply', { status: 409, json: { id: 'c2', state: 'stale', error: 'Settings changed.' } });
  await applyTray();
  queue(PREVIEW, refusal('Nothing to change.'));
  await tryAgain();
  assert.equal(tray.phase, 'failed');
  assert.equal(tray.failure, null);
  assert.deepEqual(tray.refused, { reason: 'Nothing to change.' });
  assert.equal(tray.change, null);
  assert.equal(tray.rows.length, 2);
  await tryAgain(); // the tray can ask again
  assert.equal(asked(PREVIEW).length, 4);
});

test('an add while applying does nothing', async () => {
  await fresh();
  await twoRows();
  const writing = slow();
  queue('/api/changes/c2/apply', writing.reply);
  const applying = applyTray();
  const before = calls.length;
  assert.equal(await addToTray(add('slack')), false);
  await takeOut(tray.rows[0].key);
  await cancelTray(); // a change being written cannot be cancelled
  await tryAgain();
  assert.equal(calls.length, before);
  assert.equal(tray.rows.length, 2);
  assert.equal(tray.phase, 'applying');
  writing.release(verified('c2'));
  await applying;
  // Nor once it is applied, until the page has taken the result in.
  assert.equal(await addToTray(add('slack')), false);
  assert.equal(calls.length, before);
  endApplied();
  queue(PREVIEW, previewed('c5'));
  assert.equal(await addToTray(add('slack')), true);
  // Nor while another change is written.
  setBusy(true);
  try {
    const count = calls.length;
    assert.equal(await addToTray(add('github')), false);
    assert.equal(calls.length, count);
  } finally {
    setBusy(false);
  }
});

test('endApplied empties the tray', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  queue('/api/changes/c1/apply', verified('c1'));
  await applyTray();
  const seen = [];
  const stop = onTray((now) => seen.push(now.phase));
  endApplied();
  stop();
  assert.deepEqual(seen, ['idle']);
  assert.deepEqual(tray.rows, []);
  assert.equal(tray.change, null);
  assert.deepEqual([tray.phase, tray.done, tray.total, tray.refused, tray.failure, tray.stale], ['idle', 0, 0, null, null, false]);
});

test('checkTrayStale marks a stale preview', async () => {
  await fresh();
  const none = calls.length;
  await checkTrayStale(); // nothing in the tray, nothing asked
  assert.equal(calls.length, none);
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  queue('/api/changes/c1', { status: 200, json: { id: 'c1', state: 'previewed', stale: false } }, { status: 200, json: { id: 'c1', state: 'previewed', stale: true } });
  await checkTrayStale();
  assert.equal(tray.stale, false);
  await checkTrayStale();
  assert.equal(tray.stale, true);
  // A new preview is a new start.
  queue(PREVIEW, previewed('c2'));
  await tryAgain();
  assert.equal(tray.stale, false);
  assert.equal(asked('/api/changes/c1/cancel').length, 1);
});

test('a stale answer that comes after the tray moved on changes nothing', async () => {
  await fresh();
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  const read = slow();
  queue('/api/changes/c1', read.reply);
  const checking = checkTrayStale();
  await cancelTray();
  read.release({ status: 200, json: { id: 'c1', state: 'previewed', stale: true } });
  await checking;
  assert.equal(tray.stale, false);
  assert.equal(tray.phase, 'idle');
});

test('listeners hear every change of state once', async () => {
  await fresh();
  const seen = [];
  const stop = onTray((now) => seen.push([now === tray, now.phase, now.rows.length]));
  queue(PREVIEW, previewed('c1'));
  await addToTray(add('github'));
  assert.deepEqual(seen, [[true, 'asking', 1], [true, 'ready', 1]]);
  await cancelTray();
  assert.deepEqual(seen.at(-1), [true, 'idle', 0]);
  assert.equal(seen.length, 3);
  stop();
  queue(PREVIEW, previewed('c2'));
  await addToTray(add('github'));
  assert.equal(seen.length, 3);
});
