import assert from 'node:assert/strict';
import { test } from 'node:test';

// gateway.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
// The window a drag listens to for a blur.
const windowHeard = {};
globalThis.window = {
  addEventListener: (type, fn) => { (windowHeard[type] ||= []).push(fn); },
  removeEventListener: (type, fn) => { windowHeard[type] = (windowHeard[type] || []).filter((f) => f !== fn); },
};
const { GATEWAY_COLUMNS, afterPress, besideBy, bringBeside, clickLink, contentWidth, findRows, gatewayTree, glanceFor, heldServer, kitdenLinks, letGoCloses, linkRemoval, linkTip, listRows, litFor, lightsLater, mapMotion, narrowFor, pressBlock, removeLink, rowsOnMap, serverCount, stillSelected, takesPointer } = await import('../../src/kitden/web/static/js/gateway.js');
const { DRAGS, dropBody, movingOn, pointOf, pressGrip, placeMoved, startDrag } = await import('../../src/kitden/web/static/js/gateway-drag.js');
const { moveBody, moveTargets } = await import('../../src/kitden/web/static/js/details.js');
const { offersSwitch, ruleBody } = await import('../../src/kitden/web/static/js/gateway-details.js');
const { blockLabel, findChip, findIn, isNarrow, keepOpen, layoutTree, linkClass, pagesWith, pressOpen, wideWidth } = await import('../../src/kitden/web/static/js/map.js');
const { kitdenClients } = await import('../../src/kitden/web/static/js/parts.js');
const { CALM } = await import('../../src/kitden/web/static/js/motion.js');
const { data, state, viewMode } = await import('../../src/kitden/web/static/js/store.js');
const { addToTray, applyTray, cancelTray, endApplied, keyFor, takeOut, tray } = await import('../../src/kitden/web/static/js/tray.js');

// A stand-in server for the tray: each address answers from its own queue (a reply, or a function
// of the request body that gives one); an address with nothing queued answers 200 with no body.
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
const PREVIEW = '/api/batch/preview';
// The server's answer to a batch preview: one step and one row per request.
const batch = (id) => (sent) => ({
  status: 200,
  json: {
    id, action: 'batch', state: 'previewed', error: null, target: { scope: 'all' }, undo_note: null,
    steps: sent.requests.map(() => ({ client: 'kitden', name: 'x' })),
    rows: sent.requests.map((request, index) => ({ id: request.id, kind: request.kind, title: request.title, detail: '', project: null, steps: [index], target: { scope: 'all' }, after: [], undo_note: null })),
  },
});
// The microtasks of a stand-in answer run (a mocked setTimeout does not hold this up).
const flush = () => new Promise((resolve) => setImmediate(resolve));
// An empty tray and a quiet server.
async function freshTray() {
  await cancelTray();
  endApplied();
  calls.length = 0;
  replies.clear();
  state.project = '';
}

const entry = (client, state, fields = {}) => ({ client, state, item: null, enabled: true, ...fields });

test('the Kitden card connects every client with an on kitden entry and sets up the rest', () => {
  const { linked, setup, off, known } = kitdenClients([
    entry('claude_code', 'added'),
    entry('codex', 'missing'),
    entry('cursor', 'plugin'),
  ]);
  assert.deepEqual(linked, ['claude_code', 'cursor']);
  assert.deepEqual(off, []);
  assert.equal(known, true);
  assert.deepEqual(setup, [{ client: 'codex', label: 'Set up in Codex…', body: { action: 'setup_server.register', targets: [{ client: 'codex' }], params: {} } }]);
});

test('an old entry is updated, an off entry is not connected, a missing client is left out', () => {
  const { linked, setup, off } = kitdenClients([
    entry('claude_code', 'added', { enabled: false }),
    entry('codex', 'old', { item: 'codex:agentsetup' }),
    entry('cursor', 'not_installed', { enabled: null }),
  ]);
  assert.deepEqual(linked, []);
  // An entry that is there but off: no wire, and the card says so.
  assert.deepEqual(off, ['claude_code']);
  assert.deepEqual(setup, [{ client: 'codex', label: 'Set up in Codex…', body: { action: 'setup_server.update', targets: [{ item: 'codex:agentsetup' }], params: {} } }]);
  // Without the answer nothing is offered, and the card does not claim who connects.
  assert.deepEqual(kitdenClients(null), { linked: [], setup: [], off: [], known: false });
});

test('a registered gateway offers to take the clients over only from another registered one', () => {
  const kitden = { id: 'kitden', kind: 'kitden' };
  const obot = { id: 'gw-1' };
  const meta = { id: 'gw-2' };
  const model = (used) => ({ gateways: [kitden, obot, meta], used });
  // The clients use only the Kitden gateway: a registered gateway has nothing to take over.
  assert.equal(offersSwitch(model(['kitden']), obot), false);
  assert.equal(offersSwitch(model(['kitden', 'gw-2']), obot), true);
  assert.equal(offersSwitch(model(['gw-1']), obot), false);
  assert.equal(offersSwitch(model([]), obot), false);
  assert.equal(offersSwitch(model(['gw-2']), kitden), false);
});

test('a selected server the Kitden gateway holds opens in its own panel', () => {
  const model = { gateways: [{ kind: 'kitden', servers: [{ name: 'files' }] }, { kind: 'metamcp', servers: [{ name: 'x' }] }] };
  assert.equal(heldServer(model, { kind: 'mcp_server', name: 'files' }).name, 'files');
  assert.equal(heldServer(model, { kind: 'mcp_server', name: 'x' }), null);
  assert.equal(heldServer(model, { kind: 'skill', name: 'files' }), null);
  assert.equal(heldServer(null, { kind: 'mcp_server', name: 'files' }), null);
});

// The medium sample's /api/gateway-view, cut short: held files (local, on) and tracker (remote,
// off for all projects, on in one); docs set up twice, in Claude Code (remote) and in Codex
// (local); github in Claude Code; Cursor's direct files.
const tool = (name, state, hint, fields = {}) => ({ name, title: null, state, effective: state, hint, origin: 'default', origin_from: null, ...fields });
const MEDIUM_VIEW = {
  gateways: [{ id: 'kitden', kind: 'kitden', name: 'Kitden gateway', where: 'On this Mac', movable: true, servers: [
    { name: 'files', kind: 'local', state: 'on', differs: false, origin: 'default', tools: 4, on_count: 3, on_in: 0, projects: 2, tool_list: [
      tool('read_file', 'on', 'reads'), tool('write_file', 'on', 'writes'), tool('delete_file', 'off', 'may write', { origin: 'global' }), tool('search_files', 'on', 'unknown'),
    ] },
    { name: 'tracker', kind: 'remote', state: 'off', differs: false, origin: 'global', tools: 3, on_count: 0, on_in: 1, projects: 1, tool_list: [
      tool('list_issues', 'on', 'reads', { effective: 'off', why: 'server_off' }), tool('create_issue', 'on', 'may write', { effective: 'off', why: 'server_off' }), tool('export_report', 'off', 'unknown', { origin: 'strict' }),
    ] },
  ] }],
  connections: { kitden: { claude_code: ['files'], codex: ['files'], cursor: [] } },
  used: ['kitden'],
  groups: {
    move: [
      { name: 'docs', clients: ['claude_code'], columns: ['claude_code'], items: ['a'], client_items: { claude_code: ['a'] }, stays: null },
      { name: 'github', clients: ['claude_code'], columns: ['claude_code'], items: ['g'], client_items: { claude_code: ['g'] }, stays: null },
    ],
    local: [
      { name: 'docs', clients: ['codex'], columns: ['codex'], items: ['b'], client_items: { codex: ['b'] }, stays: null },
      { name: 'files', clients: ['cursor'], columns: ['cursor'], items: ['c'], client_items: { cursor: ['c'] }, stays: null },
    ],
    plugin: [],
  },
  own_rules: 0,
};
const SETUP = [entry('claude_code', 'added'), entry('codex', 'added'), entry('cursor', 'missing')];
const CLIENTS = ['claude_code', 'codex', 'cursor'].map((id) => ({ id, status: 'found', version: '1.0', app_url: null }));
const OPTS = { setup: SETUP, clients: CLIENTS, open: new Set(), held: new Map() };
const keys = (tree) => tree.links.map((l) => `${l.from}>${l.to} ${l.kind}`);
const block = (tree, id) => tree.blocks.find((b) => b.id === id);

test('the Gateway map has the mockup numbers', () => {
  const l = layoutTree(gatewayTree(MEDIUM_VIEW, OPTS), { open: new Set(), narrow: false });
  const y = (id) => l.blocks.find((b) => b.id === id).y;
  assert.deepEqual(l.columns.map((c) => c.x), [0, 196, 396, 636]);
  assert.deepEqual(['client:claude_code', 'client:codex', 'client:cursor'].map(y), [124, 196, 268]);
  assert.deepEqual([y('gateway:kitden'), l.blocks.find((b) => b.id === 'gateway:kitden').h], [124, 124]);
  assert.deepEqual(['group:kitden:remote', 'held:kitden:tracker', 'group:kitden:local', 'held:kitden:files'].map(y), [58, 81, 154, 177]);
  assert.equal(y('group:outside'), 268);
  const outside = l.blocks.filter((b) => b.kind === 'outside');
  // Its caption is one line, as in the mockup: the first block is 21 under it.
  assert.deepEqual([outside[0].y, outside[1].y, outside[0].h], [289, 345, 50]);
  assert.equal(wideWidth(gatewayTree(MEDIUM_VIEW, OPTS)), 836);
});

test('narrow, a tool is 190 wide as it was before the mockup made the wide one 200', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const wide = layoutTree(tree, { open: new Set(['held:kitden:files']), narrow: false });
  const narrow = layoutTree(tree, { open: new Set(['held:kitden:files']), narrow: true });
  const tools = (layout) => layout.blocks.filter((b) => b.kind === 'tool');
  assert.ok(tools(wide).length > 0 && tools(wide).every((b) => b.w === 200));
  assert.ok(tools(narrow).length > 0 && tools(narrow).every((b) => b.w === 190 && b.h === 30));
});

test('group captions carry their icons', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.deepEqual(['group:kitden:remote', 'group:kitden:local', 'group:outside'].map((id) => block(tree, id).icon), ['cloud', 'hard-drive', 'info']);
});

test('the tree joins linked clients to the gateway and each outside row to its clients', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.deepEqual(tree.blocks.filter((b) => b.kind === 'client').map((b) => [b.id, b.meta]), [
    ['client:claude_code', 'Connected'], ['client:codex', 'Connected'], ['client:cursor', 'Not connected']]);
  assert.ok(keys(tree).includes('client:codex>gateway:kitden on'));
  assert.ok(!keys(tree).some((k) => k.startsWith('client:cursor>gateway:')));
  assert.ok(!keys(gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: [entry('codex', 'missing')] })).includes('client:codex>gateway:kitden on'));
  // Held servers sit in Remote and Local groups; an off server has no link from the gateway.
  const files = block(tree, 'held:kitden:files');
  assert.deepEqual([files.parent, files.column, files.count], ['group:kitden:local', 'servers', 4]);
  assert.equal(block(tree, 'held:kitden:tracker').parent, 'group:kitden:remote');
  assert.ok(keys(tree).includes('gateway:kitden>held:kitden:files on'));
  assert.ok(!keys(tree).some((k) => k.startsWith('gateway:kitden>held:kitden:tracker')));
  // One name in two groups is two blocks, each joined to its own client by a direct line.
  assert.ok(keys(tree).includes('client:codex>outside:local:docs direct'));
  assert.ok(keys(tree).includes('client:claude_code>outside:move:docs direct'));
  assert.equal(block(tree, 'outside:local:files').parent, 'group:outside');
  assert.equal(block(tree, 'outside:local:docs').meta, 'In Codex');
});

test('the Kitden block comes first, then each registered gateway, the used one first', () => {
  const obot = { id: 'gw-1', kind: 'obot', url: 'http://127.0.0.1:8080/mcp-connect/x', movable: true, managed: true };
  const meta = { id: 'gw-2', kind: 'metamcp', url: 'http://127.0.0.1:12008/metamcp/local/mcp', movable: true, managed: true };
  const view = { ...MEDIUM_VIEW, gateways: [...MEDIUM_VIEW.gateways, obot, meta], used: ['gw-2', 'kitden'],
    connections: { ...MEDIUM_VIEW.connections, 'gw-1': { claude_code: [], codex: [], cursor: [] }, 'gw-2': { claude_code: [], codex: ['x'], cursor: [] } } };
  const held = new Map([['gw-2', { servers: [{ name: 'x', type: 'STREAMABLE_HTTP', url: 'http://h/x' }, { name: 'y', type: 'uvx', url: null }] }]]);
  const tree = gatewayTree(view, { ...OPTS, held });
  assert.deepEqual(tree.blocks.filter((b) => b.kind === 'gateway').map((b) => [b.id, b.name]), [
    ['gateway:kitden', 'Kitden gateway'], ['gateway:gw-2', 'MetaMCP'], ['gateway:gw-1', 'Obot']]);
  assert.ok(keys(tree).includes('client:codex>gateway:gw-2 on'));
  // Its servers come from the live read, without tools: a remote one and one it hosts.
  assert.deepEqual([block(tree, 'held:gw-2:x').parent, block(tree, 'held:gw-2:x').meta], ['group:gw-2:remote', 'Remote']);
  assert.deepEqual([block(tree, 'held:gw-2:y').parent, block(tree, 'held:gw-2:y').meta], ['group:gw-2:local', 'Hosted']);
  assert.ok(keys(tree).includes('gateway:gw-2>held:gw-2:x on'));
  assert.ok(!tree.blocks.some((b) => b.parent === 'held:gw-2:x'));
});

test("every held server's tools are in the model; a folded server shows none", () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.deepEqual(tree.blocks.filter((b) => b.parent === 'held:kitden:files').map((b) => [b.id, b.column, b.state]), [
    ['tool:files/read_file', 'tools', 'on'],
    ['tool:files/write_file', 'tools', 'on'],
    ['tool:files/delete_file', 'tools', 'off'],
    ['tool:files/search_files', 'tools', 'on'],
  ]);
  // A tool of a server that is off is off: `effective`, so no link.
  assert.equal(block(tree, 'tool:tracker/list_issues').state, 'off');
  assert.deepEqual(keys(tree).filter((k) => k.includes('>tool:files/')).length, 3);
  assert.ok(!keys(tree).some((k) => k.includes('>tool:tracker/')));
  assert.ok(findIn(tree, 'export').open.has('held:kitden:tracker'));
  assert.ok(!layoutTree(tree, { open: new Set(), width: 1248 }).blocks.some((b) => b.id.startsWith('tool:')));
});

test('a held server says how many tools are on, or where it is on', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.equal(block(tree, 'held:kitden:files').meta, '3 of 4 on');
  assert.equal(block(tree, 'held:kitden:tracker').meta, 'On in 1 project');
  const unknown = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: [{ name: 'n8n', kind: 'local', state: 'on', tools: null, on_count: 0, on_in: 0, tool_list: [] }] }] };
  assert.equal(block(gatewayTree(unknown, OPTS), 'held:kitden:n8n').meta, 'Local');
});

test('tags say where a rule comes from', () => {
  const servers = [
    { ...MEDIUM_VIEW.gateways[0].servers[0], origin: 'project', differs: true, on_elsewhere: 0, tool_list: [tool('write_file', 'off', 'writes', { origin: 'project' })] },
    { ...MEDIUM_VIEW.gateways[0].servers[1], state: 'off', origin: 'project', differs: true, on_elsewhere: 0 },
  ];
  const view = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers }] };
  const tree = gatewayTree(view, { ...OPTS, picked: 'atlas' });
  assert.deepEqual(block(tree, 'tool:files/write_file').projects, { words: 'This project', said: 'own rule in this project', own: true });
  assert.equal(block(tree, 'held:kitden:files').tag, 'Only this project');
  assert.equal(block(tree, 'held:kitden:tracker').tag, 'This project');
  assert.equal(block(gatewayTree(MEDIUM_VIEW, OPTS), 'held:kitden:files').tag, null);
  // Another project turns it on too (website, or a folder under atlas): not only this one.
  const shared = { ...view, gateways: [{ ...view.gateways[0], servers: [{ ...servers[0], on_elsewhere: 1 }] }] };
  assert.equal(block(gatewayTree(shared, { ...OPTS, picked: 'atlas' }), 'held:kitden:files').tag, 'This project');
});

test('the list has clients, each gateway with Remote and Local, then the outside group', () => {
  const rows = listRows(gatewayTree(MEDIUM_VIEW, { setup: SETUP, clients: CLIENTS, open: new Set(), held: new Map() }), new Set());
  assert.deepEqual(rows.filter((r) => r.group).map((r) => r.name), ['Clients', 'Remote', 'Local', "Outside the gateway · calls skip Kitden's rules"]);
  assert.deepEqual(rows.find((r) => r.id === 'held:kitden:files').tools, '3 of 4 on');
  assert.equal(rows.find((r) => r.id === 'outside:move:github').action, 'move');
  // Each gateway has its own row, so its Details has a keyboard path too.
  assert.deepEqual(rows.slice(0, 5).map((r) => [r.id, r.depth, r.meta || null]), [
    ['group:clients', 0, null], ['client:claude_code', 1, 'Connected'], ['client:codex', 1, 'Connected'], ['client:cursor', 1, 'Not connected'], ['gateway:kitden', 0, '2 servers']]);
  assert.deepEqual(rows.find((r) => r.id === 'group:kitden:remote').parent, 'gateway:kitden');
  // Used by: a held server's linked clients while it is on; an outside row's clients.
  assert.deepEqual(rows.find((r) => r.id === 'held:kitden:files').usedBy, ['claude_code', 'codex']);
  assert.deepEqual(rows.find((r) => r.id === 'held:kitden:tracker').usedBy, []);
  assert.deepEqual(rows.find((r) => r.id === 'outside:local:docs').usedBy, ['codex']);
  // Kitden does not know an outside server's tools.
  assert.equal(rows.find((r) => r.id === 'outside:local:docs').tools, null);
  // Folded, a server shows no tools.
  assert.equal(rows.find((r) => r.id === 'held:kitden:files').expanded, false);
  assert.ok(!rows.some((r) => r.kind === 'tool'));
});

test("under an open server, its tools: a mark, the name, and Read, Write or May write", () => {
  const model = gatewayTree(MEDIUM_VIEW, OPTS);
  const rows = listRows(model, new Set(['held:kitden:files']));
  assert.equal(rows.find((r) => r.id === 'held:kitden:files').expanded, true);
  assert.deepEqual(rows.filter((r) => r.parent === 'held:kitden:files').map((r) => [r.name, r.state, r.tag, r.depth]), [
    ['read_file', 'on', 'Read', 3], ['write_file', 'on', 'Write', 3], ['delete_file', 'off', 'May write', 3], ['search_files', 'on', null, 3]]);
});

test('every group row of the List has the icon of its caption on the map', () => {
  const rows = listRows(gatewayTree(MEDIUM_VIEW, OPTS), new Set());
  assert.deepEqual(rows.filter((r) => r.group).map((r) => [r.name, r.icon]), [['Clients', 'monitor'], ['Remote', 'cloud'], ['Local', 'hard-drive'], ["Outside the gateway · calls skip Kitden's rules", 'info']]);
});

test('a folded group hides its rows', () => {
  const rows = listRows(gatewayTree(MEDIUM_VIEW, OPTS), new Set(), new Set(['group:outside', 'gateway:kitden']));
  assert.equal(rows.find((r) => r.id === 'group:outside').expanded, false);
  assert.equal(rows.find((r) => r.id === 'gateway:kitden').expanded, false);
  assert.ok(!rows.some((r) => r.kind === 'outside' || r.kind === 'held' || r.id === 'group:kitden:remote'));
});

test('what Kitden could not read says so, never a state', () => {
  // The setup was not read: no client is "Not connected", and no gateway has clients.
  const rows = listRows(gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: null }), new Set());
  assert.deepEqual(rows.filter((r) => r.kind === 'client').map((r) => [r.meta, r.state]), [['Not known', 'unk'], ['Not known', 'unk'], ['Not known', 'unk']]);
  assert.deepEqual(rows.find((r) => r.id === 'gateway:kitden').usedBy, []);
  // The gateway's settings were not read: no "0 servers".
  const broken = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: [], problem: 'Could not read gateway.json.' }] };
  assert.equal(listRows(gatewayTree(broken, OPTS), new Set()).find((r) => r.id === 'gateway:kitden').meta, 'Could not read its settings.');
  // A registered gateway says its failed read, and nothing while it reads.
  const obot = { id: 'gw-1', kind: 'obot', url: 'http://127.0.0.1:8080/mcp-connect/x', managed: true };
  const view = { ...MEDIUM_VIEW, gateways: [...MEDIUM_VIEW.gateways, obot], connections: { ...MEDIUM_VIEW.connections, 'gw-1': {} } };
  const meta = (held) => listRows(gatewayTree(view, { ...OPTS, held }), new Set()).find((r) => r.id === 'gateway:gw-1').meta;
  assert.equal(meta(new Map([['gw-1', { servers: null, error: 'Could not read what the gateway holds.' }]])), 'Could not read what the gateway holds.');
  assert.equal(meta(new Map([['gw-1', { loading: true }]])), null);
  assert.equal(meta(new Map([['gw-1', { servers: [] }]])), '0 servers');
});

test('one name in two groups is two rows', () => {
  const ids = listRows(gatewayTree(MEDIUM_VIEW, OPTS), new Set()).map((r) => r.id);
  assert.ok(ids.includes('outside:move:docs') && ids.includes('outside:local:docs'));
});

test('a row that stays gets no Move in…', () => {
  const stays = "docs is in the project's own files; it stays there.";
  const view = { ...MEDIUM_VIEW, groups: { ...MEDIUM_VIEW.groups, move: [{ ...MEDIUM_VIEW.groups.move[0], stays }, MEDIUM_VIEW.groups.move[1]], plugin: [{ name: 'linear', clients: ['claude_code'], columns: ['claude_code'], items: [], stays: 'linear comes with a plugin; it stays with the plugin.' }] } };
  const rows = listRows(gatewayTree(view, OPTS), new Set());
  assert.equal(rows.find((r) => r.id === 'outside:move:docs').action, 'open');
  assert.equal(rows.find((r) => r.id === 'outside:plugin:linear').action, 'open');
  assert.equal(rows.find((r) => r.id === 'outside:move:github').action, 'move');
  // Without a gateway that takes it there is nothing to move into.
  const none = listRows(gatewayTree({ ...MEDIUM_VIEW, gateways: [] }, OPTS), new Set());
  assert.equal(none.find((r) => r.id === 'outside:move:github').action, 'open');
});

test('the large sample opens in List', () => {
  const view = {
    ...MEDIUM_VIEW,
    gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: Array.from({ length: 12 }, (_, i) => ({ name: `held-${i}`, kind: 'remote', state: 'on', tool_list: [] })) }],
    groups: { move: Array.from({ length: 157 }, (_, i) => ({ name: `direct-${i}`, clients: ['codex'], columns: ['codex'], items: [], stays: null })), local: [], plugin: [] },
  };
  const LARGE_SERVER_COUNT = serverCount(view);
  assert.equal(LARGE_SERVER_COUNT, 169);
  assert.equal(viewMode({ mode: '' }, LARGE_SERVER_COUNT), 'list');
  assert.equal(viewMode({ mode: '' }, serverCount(MEDIUM_VIEW)), 'map');
});

test("a held server's panel links to the Library only when a client loads it through the gateway", () => {
  const model = { connections: { kitden: { claude_code: ['files'], codex: ['files'], cursor: [] } } };
  assert.deepEqual(kitdenLinks(model, 'files').map((l) => [l.label, l.view, l.selected]), [['Compare across clients', 'library', { kind: 'mcp_server', name: 'files' }]]);
  // No client reaches tracker here, so the Library has no row for it.
  assert.deepEqual(kitdenLinks(model, 'tracker'), []);
  assert.deepEqual(kitdenLinks(null, 'files'), []);
});

// A first run: every client found, none with a kitden entry, an empty Kitden gateway, and two
// servers each client set up on its own.
const FIRST_RUN_VIEW = {
  gateways: [{ id: 'kitden', kind: 'kitden', name: 'Kitden gateway', where: 'On this Mac', movable: true, servers: [] }],
  connections: { kitden: { claude_code: [], codex: [], cursor: [] } },
  used: [],
  groups: {
    move: [{ name: 'github', clients: ['claude_code'], columns: ['claude_code'], items: ['g'], stays: null, override: false }],
    local: [{ name: 'files', clients: ['codex'], columns: ['codex'], items: ['f'], stays: null, override: false }],
    plugin: [],
  },
  own_rules: 0,
};
const NO_ENTRIES = ['claude_code', 'codex', 'cursor'].map((id) => entry(id, 'missing'));
const FOUND = [
  { id: 'claude_code', status: 'found', version: '2.1.4' },
  { id: 'codex', status: 'found', version: '0.48' },
  { id: 'cursor', status: 'found', version: null },
];

test('a first run shows the gateway as a slot to set up and no grips', () => {
  const m = gatewayTree(FIRST_RUN_VIEW, { setup: NO_ENTRIES, clients: FOUND, open: new Set(), held: new Map() });
  const slot = m.blocks.find((b) => b.column === 'gateway');
  assert.deepEqual([slot.kind, slot.name], ['slot', 'No gateway yet']);
  assert.deepEqual([slot.meta, slot.action], ['One place for servers, rules and logins.', 'Set up…']);
  // One review sets up every client that has no kitden entry.
  assert.deepEqual(slot.setup, { action: 'setup_server.register', targets: [{ client: 'claude_code' }, { client: 'codex' }, { client: 'cursor' }], params: {} });
  assert.ok(!m.links.some((l) => l.to === slot.id));
  assert.ok(m.blocks.filter((b) => b.kind === 'outside').every((b) => !b.grip));
  assert.equal(m.blocks.find((b) => b.id === 'client:codex').meta, 'Found · 0.48');
  assert.equal(m.blocks.find((b) => b.id === 'client:cursor').meta, 'Found');
  // Found lights the lamp, but no client reaches a gateway yet: its state, and the word a screen
  // reader hears, stay Off, as the map shows no link.
  const codex = m.blocks.find((b) => b.id === 'client:codex');
  assert.deepEqual([codex.lamp, codex.state], ['on', 'off']);
  assert.equal(blockLabel(codex), 'Codex, Found · 0.48, Off');
  // Direct lines are elbows on a first run too.
  assert.ok(m.links.filter((l) => l.to.startsWith('outside:')).every((l) => l.kind === 'direct'));
  // A client with the kitden entry is not a first run, nor is a setup Kitden could not read.
  const linked = gatewayTree(FIRST_RUN_VIEW, { ...OPTS, setup: [entry('claude_code', 'added'), entry('codex', 'missing')], clients: FOUND });
  assert.equal(linked.blocks.find((b) => b.column === 'gateway').kind, 'gateway');
  assert.ok(linked.blocks.find((b) => b.id === 'outside:move:github').grip);
  assert.equal(gatewayTree(FIRST_RUN_VIEW, { ...OPTS, setup: null, clients: FOUND }).blocks.find((b) => b.column === 'gateway').kind, 'gateway');
  // The List keeps a row for it, with the same words.
  const row = listRows(m, new Set()).find((r) => r.id === slot.id);
  assert.deepEqual([row.depth, row.name, row.meta], [0, 'No gateway yet', 'One place for servers, rules and logins.']);
});

test('the map columns, and the Kitden gateway says its clients and servers', () => {
  assert.deepEqual(GATEWAY_COLUMNS.map((c) => c.caption), ['Clients', 'Gateway', 'Servers', 'Tools']);
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.deepEqual(block(tree, 'gateway:kitden').stats.map((s) => s.words), ['2 clients', '2 servers']);
  // Not read: no count of clients it does not know.
  assert.deepEqual(block(gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: null }), 'gateway:kitden').stats.map((s) => s.words), ['2 servers']);
});

test('no grip where the row stays', () => {
  const row = (name, fields = {}) => ({ name, clients: ['claude_code'], columns: ['claude_code'], items: [name], stays: null, override: false, ...fields });
  const view = { ...MEDIUM_VIEW, groups: {
    move: [
      row('github'),
      row('docs', { stays: "docs is in the project's own files; it stays there." }),
      row('secret', { stays: 'secret uses ${API_KEY}; Kitden cannot move a value it does not know.' }),
      row('kept', { stays: 'From the last good read at 14:02; Kitden can change it once it reads .claude.json again.' }),
      row('empty', { items: [] }),
    ],
    local: [row('files', { clients: ['codex'], columns: ['codex'] })],
    plugin: [row('linear', { stays: 'linear comes with a plugin; it stays with the plugin.' })],
  } };
  const tree = gatewayTree(view, OPTS);
  assert.deepEqual(tree.blocks.filter((b) => b.kind === 'outside').map((b) => [b.name, Boolean(b.grip)]), [
    ['github', true], ['docs', false], ['secret', false], ['kept', false], ['empty', false], ['files', true], ['linear', false]]);
  // Without a gateway that takes it, nothing has a grip.
  assert.ok(gatewayTree({ ...view, gateways: [] }, OPTS).blocks.every((b) => !b.grip));
});

test('a name set up differently in two clients of one group has no grip and no "Move in…"', () => {
  // The server's `stays` is the move's own refusal (gateway_view.py), so nothing offers the move.
  const stays = 'files is set up differently in Codex and Cursor; keep one first.';
  const files = { name: 'files', clients: ['codex', 'cursor'], columns: ['codex', 'cursor'], items: ['c', 'd'], stays, override: false };
  const tree = gatewayTree({ ...MEDIUM_VIEW, groups: { ...MEDIUM_VIEW.groups, local: [files] } }, OPTS);
  const shown = block(tree, 'outside:local:files');
  assert.deepEqual([shown.grip, shown.move], [false, false]);
  assert.equal(listRows(tree).find((r) => r.id === 'outside:local:files').action, 'open');
});

test('an outside server Kitden does not know to be on has a dashed line and says "Not known"', () => {
  // A project's .mcp.json server Claude Code has not approved yet: no entry of it is known on.
  const notes = { name: 'notes', clients: ['claude_code'], columns: ['claude_code'], items: [], stays: "notes is in the project's own files; it stays there.", override: false, unknown: true };
  const tree = gatewayTree({ ...MEDIUM_VIEW, groups: { ...MEDIUM_VIEW.groups, local: [notes] } }, OPTS);
  const shown = block(tree, 'outside:local:notes');
  assert.equal(shown.state, 'unk');
  assert.equal(blockLabel(shown), 'notes, In Claude Code, Not known');
  // The line still shows which client has the entry, dashed: it does not claim "on".
  assert.deepEqual(tree.links.find((l) => l.to === 'outside:local:notes'), { from: 'client:claude_code', to: 'outside:local:notes', kind: 'direct', unk: true });
  assert.equal(layoutTree(tree, { width: 1440 }).links.find((l) => l.to === 'outside:local:notes').unk, true);
  assert.equal(listRows(tree).find((r) => r.id === 'outside:local:notes').meta, 'Not known');
  // A server a client loads stays on, with a plain line.
  assert.equal(blockLabel(block(tree, 'outside:move:github')), 'github, In Claude Code, On');
  assert.equal(tree.links.find((l) => l.to === 'outside:move:github').unk, undefined);
  assert.equal(layoutTree(tree, { width: 1440 }).links.find((l) => l.to === 'outside:move:github').unk, undefined);
  assert.equal(listRows(tree).find((r) => r.id === 'outside:move:github').meta, null);
});

test('a gateway block speaks no state word, and one Kitden could not read is not known', () => {
  // Its words say where it runs and its clients and servers: an "On" beside them would say more
  // than Kitden knows.
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.equal(blockLabel(block(tree, 'gateway:kitden')), 'Kitden gateway, On this Mac, 2 clients · 2 servers');
  const none = ['claude_code', 'codex', 'cursor'].map((c) => entry(c, 'missing'));
  assert.equal(blockLabel(block(gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: none }), 'gateway:kitden')), 'Kitden gateway, On this Mac, 0 clients · 2 servers');
  const broken = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: [], problem: 'Kitden could not read the gateway settings.' }] };
  const unread = block(gatewayTree(broken, OPTS), 'gateway:kitden');
  assert.equal(unread.state, 'unk');
  assert.equal(blockLabel(unread), 'Kitden gateway, Could not read its settings.');
});

test('find skips the group captions, so they are not counted as matches', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  for (const words of ['Remote', 'local', 'Outside the gateway']) {
    assert.deepEqual(findIn(tree, words), { matches: new Set(), open: new Set() }, words);
    assert.equal(findChip(findIn(tree, words)), 'No matches', words);
  }
  assert.equal(findChip(findIn(tree, 'docs')), '2 matches');
});

test('a Desktop Code tab entry draws its line from Claude Code', () => {
  const desk = { name: 'desk', clients: ['claude_desktop_code_tab'], columns: ['claude_code'], items: ['d'], stays: null, override: false };
  const tree = gatewayTree({ ...MEDIUM_VIEW, groups: { ...MEDIUM_VIEW.groups, move: [desk] } }, OPTS);
  assert.ok(keys(tree).includes('client:claude_code>outside:move:desk direct'));
  assert.equal(block(tree, 'outside:move:desk').meta, 'In Claude Code');
});

test('With All projects a server only some projects turn on says so', () => {
  const servers = [MEDIUM_VIEW.gateways[0].servers[0], { ...MEDIUM_VIEW.gateways[0].servers[1], on_in: 2 }];
  const view = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers }] };
  const tree = gatewayTree(view, OPTS);
  assert.equal(block(tree, 'held:kitden:tracker').meta, 'On in 2 projects');
  assert.ok(!tree.links.some((l) => l.to === 'held:kitden:tracker'));
  // Its words say where it is on; no On or Off word beside them.
  assert.equal(blockLabel(block(tree, 'held:kitden:tracker')), 'tracker, On in 2 projects');
  assert.equal(listRows(tree, new Set()).find((r) => r.id === 'held:kitden:tracker').said, null);
  // A server with no such words still says its state.
  assert.equal(blockLabel(block(tree, 'held:kitden:files')), 'files, 3 of 4 on, On');
  assert.equal(listRows(tree, new Set()).find((r) => r.id === 'held:kitden:files').said, 'On');
  // In a project the server says how many of its tools are on there.
  assert.equal(block(gatewayTree(view, { ...OPTS, picked: 'atlas' }), 'held:kitden:tracker').meta, '0 of 3 on');
});

test('in atlas the docs block says This project', () => {
  const docs = { ...MEDIUM_VIEW.groups.move[0], override: true };
  const view = { ...MEDIUM_VIEW, groups: { ...MEDIUM_VIEW.groups, move: [docs, MEDIUM_VIEW.groups.move[1]] } };
  const atlas = gatewayTree(view, { ...OPTS, picked: 'atlas' });
  assert.equal(block(atlas, 'outside:move:docs').tag, 'This project');
  assert.equal(block(atlas, 'outside:local:docs').tag, null);
  // The List shows the tag too.
  assert.equal(listRows(atlas, new Set()).find((r) => r.id === 'outside:move:docs').tag, 'This project');
  // With All projects no block carries it.
  assert.equal(block(gatewayTree(view, OPTS), 'outside:move:docs').tag, null);
});

test('N more is as high as the blocks it stands for', () => {
  const rows = Array.from({ length: 8 }, (_, i) => ({ name: `direct-${i}`, clients: ['codex'], columns: ['codex'], items: ['x'], stays: null, override: false }));
  const tree = gatewayTree({ ...MEDIUM_VIEW, groups: { move: rows, local: [], plugin: [] } }, OPTS);
  const more = layoutTree(tree, { open: new Set(), narrow: false }).blocks.find((b) => b.kind === 'more');
  assert.equal(more.id, 'more:group:outside');
  // An outside server's block is 50 high, not a plain 60.
  assert.equal(more.h, 50);
});

test('the map goes narrow by the window rule, or where the wide map does not fit its box', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.equal(narrowFor(tree, { window: 1100, box: 836 }), false);
  assert.equal(narrowFor(tree, { window: 1100, box: 500 }), true);
  assert.equal(narrowFor(tree, { window: 900, box: 868 }), true);
  // Before the box is measured, the window rule alone.
  assert.equal(narrowFor(tree, { window: 1440, box: null }), false);
});

test('opening Details no longer makes the map narrow', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  // Details float over the map: at 1100 px and 1366 px the box keeps its whole width, and the wide
  // map fits it. Only a window under 1024 px is narrow.
  assert.equal(isNarrow(1100), false);
  assert.equal(isNarrow(1279), false);
  assert.equal(isNarrow(1023), true);
  assert.equal(narrowFor(tree, { window: 1100, box: 874 }), false);
  assert.equal(narrowFor(tree, { window: 1366, box: 1140 }), false);
  // What the page said about open Details before counts no more.
  assert.equal(narrowFor(tree, { window: 1100, box: 874, docked: true }), false);
  // A selected block the floating Details cover scrolls left until it ends 16 px before them.
  assert.equal(besideBy(1023, 1081), 0);
  assert.equal(besideBy(1023, 921), 118);
});

test('a map block under floating Details, selected or focused, scrolls beside them', () => {
  // Details float from 741 px (a 1100 px window); the map takes room and scrolls by what they cover.
  const drawer = { offsetLeft: 741, classList: { contains: (name) => ['open', 'floating'].includes(name) } };
  globalThis.document = { querySelector: (selector) => (selector === '#drawer' ? drawer : null) };
  const scrolled = [];
  const looks = new Set();
  const box = { classList: { add: (name) => looks.add(name) }, scrollBy: (options) => scrolled.push(options) };
  const endsAt = (right) => ({ getBoundingClientRect: () => ({ right }) });
  try {
    bringBeside(box, endsAt(1023));
    assert.deepEqual(scrolled, [{ left: 298, behavior: 'smooth' }]);
    assert.equal(looks.has('beside'), true);
    // Clear of them, or nothing to show: nothing moves.
    bringBeside(box, endsAt(700));
    bringBeside(box, null);
    assert.equal(scrolled.length, 1);
    // The drawer under 1024 px covers the page on purpose: nothing moves.
    drawer.classList.contains = (name) => name === 'open';
    bringBeside(box, endsAt(1023));
    assert.equal(scrolled.length, 1);
  } finally {
    delete globalThis.document;
  }
});

test('find lights both docs and opens what hides them', () => {
  const found = findIn(gatewayTree(MEDIUM_VIEW, OPTS), 'docs');
  assert.deepEqual([...found.matches].sort(), ['outside:local:docs', 'outside:move:docs']);
  assert.equal(findChip(found), '2 matches');
  assert.equal(findChip(findIn(gatewayTree(MEDIUM_VIEW, OPTS), 'export')), '1 match');
  // The tool of a folded server is found; its server and group open to show it.
  const tool = findIn(gatewayTree(MEDIUM_VIEW, OPTS), 'export');
  assert.deepEqual([...tool.matches], ['tool:tracker/export_report']);
  assert.ok(tool.open.has('held:kitden:tracker') && tool.open.has('group:kitden:remote'));
});

// Twelve servers outside the gateway: three pages of five.
const twelve = () => {
  const rows = Array.from({ length: 12 }, (_, i) => ({ name: `direct-${i}`, clients: ['codex'], columns: ['codex'], items: ['x'], stays: null, override: false }));
  return gatewayTree({ ...MEDIUM_VIEW, groups: { move: rows, local: [], plugin: [] } }, OPTS);
};
const shownWith = (tree, pages, open = new Set()) => layoutTree(tree, { open, pages, narrow: false }).blocks.map((b) => b.id);

test('a search match turns its group to the page that holds it; a match on the page shown turns nothing', () => {
  const tree = twelve();
  const found = findIn(tree, 'direct-11');
  // The search no longer shows the group whole: its page shows, with the block that turns it.
  assert.ok(!shownWith(tree, new Map(), found.open).includes('outside:move:direct-11'));
  const pages = pagesWith(tree, new Map(), found.matches);
  assert.deepEqual([...pages], [['group:outside', 2]]);
  assert.ok(shownWith(tree, pages).includes('outside:move:direct-11') && shownWith(tree, pages).includes('more:group:outside'));
  // Every server matches "direct", and the page shown has some: nothing turns.
  assert.equal(pagesWith(tree, pages, findIn(tree, 'direct').matches), pages);
  // A selection that is no block (a link's key) turns nothing.
  assert.equal(pagesWith(tree, pages, ['client:codex>outside:move:direct-1']), pages);
});

test('while the Outside group pages, its caption names the page in place of "drag one in"', () => {
  const caption = (tree, pages = new Map()) => layoutTree(tree, { open: new Set(), pages, narrow: false }).blocks.find((b) => b.id === 'group:outside');
  assert.equal(caption(twelve()).name, 'Outside the gateway · 1–5 of 12');
  assert.equal(caption(twelve(), new Map([['group:outside', 1]])).name, 'Outside the gateway · 6–10 of 12');
  // A group that does not page keeps its words, which ask for a drag.
  const few = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.equal(caption(few).name, undefined);
  assert.equal(block(few, 'group:outside').name, 'Outside the gateway · drag one in');
});

test('a selection or an arrival on another page brings its page', () => {
  const tree = twelve();
  const target = block(tree, 'outside:move:direct-7');
  const mine = new Set(['held:kitden:files']);
  const pages = pagesWith(tree, new Map(), [target.id]);
  assert.deepEqual([...pages], [['group:outside', 1]]);
  // On its page it shows: what the person opened stays as it is, and no group opens.
  assert.equal(keepOpen(tree, mine, target, pages), mine);
  assert.ok(!keepOpen(tree, new Set(), target).has('group:outside'));
});

test('the List lights a match and opens what holds it, without changing what the person folded', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const found = findIn(tree, 'search_files');
  const open = new Set();
  const folded = new Set(['gateway:kitden', 'group:clients']);
  const ids = (rows) => rows.map((r) => r.id);
  assert.ok(!ids(listRows(tree, open, folded)).includes('tool:files/search_files'));
  const rows = findRows(tree, found, open, folded);
  // The folded gateway shows its rows, the server shows its tools, and only the match is lit.
  assert.ok(ids(rows).includes('held:kitden:files') && ids(rows).includes('tool:files/search_files'));
  assert.deepEqual(rows.filter((r) => r.found).map((r) => r.id), ['tool:files/search_files']);
  assert.deepEqual([[...open], [...folded].sort()], [[], ['gateway:kitden', 'group:clients']]);
  // The rows that hold the match are kept open for the search: a press on one folds nothing.
  assert.deepEqual(rows.filter((r) => r.kept).map((r) => r.id).sort(), ['gateway:kitden', 'group:kitden:local', 'held:kitden:files']);
  // A client is found too, and its folded group opens.
  const client = findRows(tree, findIn(tree, 'cursor'), open, folded);
  assert.deepEqual(client.filter((r) => r.found).map((r) => r.id), ['client:cursor']);
  // No search: the rows as they are, none lit.
  assert.deepEqual(findRows(tree, null, open, folded), listRows(tree, open, folded));
});

test('a press on a block the search holds open leaves what the person opened alone', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const mine = new Set(['held:kitden:files']);
  const found = findIn(tree, 'export'); // opens the tracker server for the view
  // The tracker is open only for the search: pressing it changes nothing, and files stays open.
  assert.deepEqual([...pressOpen(tree, mine, found, 'held:kitden:tracker')], ['held:kitden:files']);
  // Without a search, or on a block the search does not hold, a press opens it as always: one
  // server per column, so files closes; and files, which the person opened, folds.
  assert.deepEqual([...pressOpen(tree, mine, null, 'held:kitden:tracker')], ['held:kitden:tracker']);
  assert.deepEqual([...pressOpen(tree, mine, found, 'held:kitden:files')], []);
  assert.deepEqual([...mine], ['held:kitden:files']);
});

test('a tool the search showed stays on the map when the search ends', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const tool = block(tree, 'tool:tracker/export_report');
  const mine = new Set(['held:kitden:files']);
  const shown = (open) => layoutTree(tree, { open, narrow: false }).blocks.map((b) => b.id);
  assert.ok(!shown(mine).includes(tool.id));
  const kept = keepOpen(tree, mine, tool);
  // Its server opens, and as always one server per column: files folds.
  assert.ok(shown(kept).includes(tool.id));
  assert.ok(kept.has('held:kitden:tracker') && !kept.has('held:kitden:files'));
  // A block that shows already changes nothing, so the person's server stays open.
  assert.equal(keepOpen(tree, mine, block(tree, 'tool:files/read_file')), mine);
  assert.equal(keepOpen(tree, mine, block(tree, 'outside:move:docs')), mine);
  assert.deepEqual([...mine], ['held:kitden:files']);
});

test("a drag's preview equals the Move preview", () => {
  const row = MEDIUM_VIEW.groups.move.find((r) => r.name === 'github');
  assert.deepEqual(dropBody(row, MEDIUM_VIEW), moveBody(moveTargets(MEDIUM_VIEW, 'move')[0], row.items));
  // A drop always moves into the Kitden gateway, also with a registered gateway that takes it.
  const obot = { id: 'gw-1', kind: 'obot', movable: true };
  assert.deepEqual(dropBody(row, { ...MEDIUM_VIEW, gateways: [obot, ...MEDIUM_VIEW.gateways] }).params, { gateway: 'kitden' });
  assert.equal(dropBody(row, { ...MEDIUM_VIEW, gateways: [obot] }), null);
});

test("a drag takes only its own row's entries", () => {
  const docs = MEDIUM_VIEW.groups.local.find((r) => r.name === 'docs');
  assert.deepEqual(dropBody(docs, MEDIUM_VIEW).targets, docs.items.map((item) => ({ item })));
});

// A tray row as the map reads it: its key, its body, and its part of the preview (null while it is
// still being asked).
const trayRow = (body, part = {}) => ({ key: keyFor(body), body, part });
const GITHUB = MEDIUM_VIEW.groups.move.find((r) => r.name === 'github');
const LOCAL_DOCS = MEDIUM_VIEW.groups.local.find((r) => r.name === 'docs');
const moveRow = (row, part = {}) => trayRow(dropBody(row, MEDIUM_VIEW), part);
const REMOVE_FILES = { action: 'gateway.remove', targets: [], params: { server: 'files' } };
const linkOf = (tree, key) => tree.links.find((l) => `${l.from}>${l.to}` === key);

test('a move in the tray shows a preview block and link in the right group', () => {
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [moveRow(GITHUB)] });
  const shown = block(tree, 'preview:github');
  assert.deepEqual([shown.parent, shown.kind, shown.state, shown.column, shown.meta], ['group:kitden:remote', 'preview', 'preview', 'servers', 'Preview']);
  assert.equal(blockLabel(shown), 'github, Preview');
  assert.ok(keys(tree).includes('gateway:kitden>preview:github preview'));
  // It comes after the group's servers, before the Local group.
  const ids = tree.blocks.filter((b) => b.column === 'servers').map((b) => b.id);
  assert.deepEqual(ids.slice(0, 4), ['group:kitden:remote', 'held:kitden:tracker', 'preview:github', 'group:kitden:local']);
  // The row being moved hides its direct line while the preview is there; the other docs keeps its own.
  assert.ok(!keys(tree).includes('client:claude_code>outside:move:github direct'));
  assert.ok(keys(tree).includes('client:claude_code>outside:move:docs direct'));
  // A local server goes to Local; a group the gateway does not have yet comes with it, Remote first.
  const local = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [moveRow(LOCAL_DOCS)] });
  assert.equal(block(local, 'preview:docs').parent, 'group:kitden:local');
  assert.ok(!keys(local).includes('client:codex>outside:local:docs direct') && keys(local).includes('client:claude_code>outside:move:docs direct'));
  const onlyLocal = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: [MEDIUM_VIEW.gateways[0].servers[0]] }] };
  const fresh = gatewayTree(onlyLocal, { ...OPTS, rows: [moveRow(GITHUB)] });
  assert.deepEqual(fresh.blocks.filter((b) => b.column === 'servers').map((b) => b.id).slice(0, 4), ['group:kitden:remote', 'preview:github', 'group:kitden:local', 'held:kitden:files']);
  assert.equal(block(fresh, 'group:kitden:remote').name, 'Remote');
  // A move into another gateway is not drawn on the Kitden gateway.
  const other = trayRow(moveBody({ id: 'gw-1', kind: 'obot' }, GITHUB.items));
  assert.ok(!gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [other] }).blocks.some((b) => b.kind === 'preview'));
});

test('two moves in the tray show two preview blocks', () => {
  const rows = [moveRow(GITHUB), moveRow(LOCAL_DOCS)];
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows });
  assert.deepEqual([block(tree, 'preview:github').parent, block(tree, 'preview:github').row], ['group:kitden:remote', rows[0].key]);
  assert.deepEqual([block(tree, 'preview:docs').parent, block(tree, 'preview:docs').row], ['group:kitden:local', rows[1].key]);
  assert.ok(keys(tree).includes('gateway:kitden>preview:github preview') && keys(tree).includes('gateway:kitden>preview:docs preview'));
  // Each outside row a move takes hides its direct lines; the other docs keeps its own.
  assert.ok(!keys(tree).includes('client:claude_code>outside:move:github direct'));
  assert.ok(!keys(tree).includes('client:codex>outside:local:docs direct'));
  assert.ok(keys(tree).includes('client:claude_code>outside:move:docs direct'));
  // A server whose move is in the tray is drawn only in the gateway; every other one keeps its grip.
  assert.deepEqual(tree.blocks.filter((b) => b.kind === 'outside').map((b) => [b.id, Boolean(b.grip)]), [
    ['outside:move:docs', true], ['outside:local:files', true]]);
  // A move still being asked shows the slot "Drop to add" in its place; its server waits there
  // with its line and no grip.
  const asked = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [moveRow(GITHUB, null), moveRow(LOCAL_DOCS)] });
  assert.deepEqual([block(asked, 'slot:github').name, block(asked, 'slot:github').parent], ['Drop to add', 'group:kitden:remote']);
  assert.ok(!block(asked, 'preview:github') && block(asked, 'preview:docs'));
  assert.ok(keys(asked).includes('client:claude_code>outside:move:github direct') && !block(asked, 'outside:move:github').grip);
});

test('the List shows no block of the tray and counts none', () => {
  const plain = listRows(gatewayTree(MEDIUM_VIEW, OPTS), new Set());
  // A move that has answered (a preview block) and one still being asked (the slot).
  for (const part of [{}, null]) {
    const rows = listRows(gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [moveRow(GITHUB, part)] }), new Set());
    assert.ok(!rows.some((r) => /^(preview|slot):/.test(r.id)), JSON.stringify(part));
    assert.equal(rows.find((r) => r.id === 'gateway:kitden').meta, '2 servers');
    // A map with a move answered draws its server only as the preview (the List itself is drawn
    // from no rows of the tray, so it keeps the server's row).
    const moved = part ? ['outside:move:github'] : [];
    assert.deepEqual(rows.map((r) => r.id), plain.map((r) => r.id).filter((id) => !moved.includes(id)));
  }
  // A drag's slot is no row either; a group that would hold only a preview has no row.
  const onlyLocal = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: [MEDIUM_VIEW.gateways[0].servers[0]] }] };
  const rows = listRows(gatewayTree(onlyLocal, { ...OPTS, rows: [moveRow(GITHUB)], drop: { name: 'docs', kind: 'local' } }), new Set());
  assert.ok(!rows.some((r) => r.id === 'group:kitden:remote' || /^(preview|slot):/.test(r.id)));
  assert.equal(rows.find((r) => r.id === 'gateway:kitden').meta, '1 server');
});

test('a removal in the tray makes its link leave', () => {
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [trayRow(REMOVE_FILES)] });
  const link = linkOf(tree, 'gateway:kitden>held:kitden:files');
  assert.deepEqual([link.kind, link.leaving, link.row], ['on', true, keyFor(REMOVE_FILES)]);
  assert.equal(layoutTree(tree, { open: new Set(), narrow: false }).links.find((l) => l.to === 'held:kitden:files').leaving, true);
  // The server stays where it is until Apply; its other links are as they were.
  assert.equal(block(tree, 'held:kitden:files').state, 'on');
  assert.equal(linkOf(tree, 'held:kitden:files>tool:files/read_file').leaving, undefined);
  // A row still being asked changes nothing on the map yet, nor does an empty tray.
  assert.equal(linkOf(gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [trayRow(REMOVE_FILES, null)] }), 'gateway:kitden>held:kitden:files').leaving, undefined);
  assert.equal(linkOf(gatewayTree(MEDIUM_VIEW, OPTS), 'gateway:kitden>held:kitden:files').leaving, undefined);
});

test('a tool turned off in the tray makes its link leave', () => {
  const off = (project) => trayRow(ruleBody('files', 'read_file', 'off', project));
  const leaving = (opts) => linkOf(gatewayTree(MEDIUM_VIEW, { ...OPTS, ...opts }), 'held:kitden:files>tool:files/read_file').leaving;
  // For all projects with All projects picked, or in the project picked at the top.
  assert.equal(leaving({ rows: [off(null)] }), true);
  assert.equal(leaving({ picked: 'website', rows: [off('website')] }), true);
  // A rule for another scope than the one shown leaves no link.
  assert.equal(leaving({ rows: [off('website')] }), undefined);
  assert.equal(leaving({ picked: 'website', rows: [off(null)] }), undefined);
  // Turning a tool on takes no link out.
  assert.equal(leaving({ rows: [trayRow(ruleBody('files', 'read_file', 'on', null))] }), undefined);
  // Its link shows only while its server is open.
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [off(null)] });
  const shown = (open) => layoutTree(tree, { open: new Set(open), narrow: false }).links.find((l) => l.to === 'tool:files/read_file');
  assert.equal(shown([]), undefined);
  assert.equal(shown(['held:kitden:files']).leaving, true);
});

test('the map draws no rows once the change is applied', () => {
  const rows = [moveRow(GITHUB)];
  assert.deepEqual(rowsOnMap({ phase: 'ready', rows }), rows);
  assert.deepEqual(rowsOnMap({ phase: 'applying', rows }), rows);
  assert.deepEqual(rowsOnMap({ phase: 'applied', rows }), []);
  // A row with no part yet is drawn only while the tray asks for it.
  const asked = [moveRow(GITHUB, null), moveRow(LOCAL_DOCS)];
  assert.deepEqual(rowsOnMap({ phase: 'asking', rows: asked }), asked);
  assert.deepEqual(rowsOnMap({ phase: 'failed', rows: asked }), [asked[1]]);
});

test('a move left with no answer, and nothing asked, draws nothing and its block goes home', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const heard = {};
  globalThis.document = { addEventListener: (type, fn) => { (heard[type] ||= []).push(fn); }, removeEventListener() {}, documentElement: { classList: { add() {}, remove() {} } }, querySelector: () => null, createElement: (tag) => ({ tag }) };
  Object.assign(data, { gateway: MEDIUM_VIEW });
  data.scope.gateway = '';
  try {
    const tree = gatewayTree(MEDIUM_VIEW, OPTS);
    const layout = layoutTree(tree, { open: new Set(), narrow: false });
    const held = [];
    const node = { dataset: { focus: 'block:outside:move:github' }, getBoundingClientRect: () => ({ left: 0, top: 0 }), querySelector: () => null, querySelectorAll: () => [], setAttribute() {}, removeAttribute() {}, append() {} };
    const view = { node: () => node, hold: (id, at, how) => held.push([id, at, how]), homeIn: (id, ms) => held.push(['homeIn', id, ms]), lightTarget() {}, unlightTarget() {}, glance() {}, tip() {}, untip() {}, box: { isConnected: true, classList: { toggle() {}, remove() {} } }, area: { getBoundingClientRect: () => ({ left: 0, top: 0 }) } };
    placeMoved({ view, model: tree, layout });
    // The drop is asked; a second add drops that ask, and both it and the ask for the rest are
    // refused. The move stays in the tray with no part, and nothing is asked any more.
    let late;
    queue(PREVIEW, (sent) => new Promise((resolve) => { late = () => resolve(batch('c1')(sent)); }));
    queue(PREVIEW, { status: 422, json: { detail: 'No.' } }, { status: 422, json: { detail: 'Still no.' } });
    const home = layout.blocks.find((b) => b.id === 'outside:move:github');
    const files = layout.blocks.find((b) => b.id === 'held:kitden:files');
    // The block is where the layout puts it: the press is 10 px into it.
    node.getBoundingClientRect = () => ({ left: home.x, top: home.y });
    pressGrip({ button: 0, target: { closest: () => node }, clientX: home.x + 10, clientY: home.y + 10 });
    heard.pointermove[0]({ clientX: home.x + 16, clientY: home.y + 10 });
    heard.pointermove[0]({ clientX: files.x + 10, clientY: files.y + 10 });
    heard.pointerup[0]({ type: 'pointerup', clientX: files.x + 10, clientY: files.y + 10 });
    assert.equal(await addToTray(REMOVE_FILES), false);
    late();
    await flush();
    assert.deepEqual([tray.phase, tray.rows.map((r) => [r.body.action, r.part])], ['failed', [['gateway.move', null]]]);
    // No slot and no preview: github is back outside with its line and its grip.
    const now = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: rowsOnMap(tray) });
    assert.ok(!block(now, 'slot:github') && !block(now, 'preview:github'));
    assert.ok(keys(now).includes('client:claude_code>outside:move:github direct') && block(now, 'outside:move:github').grip);
    // The block the drop parked on the slot goes home.
    held.length = 0;
    placeMoved({ view, model: now, layout: layoutTree(now, { open: new Set(), narrow: false }) });
    assert.deepEqual(held, [['homeIn', 'outside:move:github', 220]]);
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null });
    await freshTray();
  }
});

test('while the tray is written a link offers no × and a press takes nothing out', async () => {
  await freshTray();
  queue(PREVIEW, batch('c1'), batch('c2'));
  await addToTray(dropBody(GITHUB, MEDIUM_VIEW));
  await addToTray(REMOVE_FILES, { icon: 'x' });
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: rowsOnMap(tray) });
  const links = ['gateway:kitden>held:kitden:files', 'gateway:kitden>preview:github', 'held:kitden:files>tool:files/read_file'];
  let verify;
  queue('/api/changes/c2/apply', () => new Promise((resolve) => { verify = () => resolve({ status: 200, json: { id: 'c2', state: 'verified', steps: [] } }); }));
  globalThis.document = { activeElement: null, body: {}, querySelector: () => ({ querySelectorAll: () => [] }), addEventListener() {}, removeEventListener() {} };
  try {
    const applying = applyTray();
    assert.equal(tray.phase, 'applying');
    // No link takes the pointer or has a ×, and nothing leaves.
    assert.equal(takesPointer(), false);
    assert.deepEqual(links.map((key) => linkTip(tree, linkOf(tree, key), '')), ['', '', '']);
    pressBlock(tree, 'preview:github');
    clickLink(tree, linkOf(tree, 'gateway:kitden>held:kitden:files'));
    await removeLink(tree, linkOf(tree, 'gateway:kitden>held:kitden:files'), '');
    await flush();
    assert.deepEqual([tray.phase, tray.rows.length], ['applying', 2]);
    verify();
    await applying;
    assert.equal(linkTip(tree, linkOf(tree, links[0]), ''), '');
    assert.equal(takesPointer(), false);
    // Once it has landed, the links take the pointer and offer their × again.
    endApplied();
    const now = gatewayTree(MEDIUM_VIEW, OPTS);
    assert.equal(takesPointer(), true);
    assert.equal(linkTip(now, linkOf(now, links[0]), ''), 'Remove files from the gateway');
  } finally {
    await freshTray();
    delete globalThis.document;
  }
});

test('a press on a preview block takes its row out', async () => {
  await freshTray();
  queue(PREVIEW, batch('c1'), batch('c2'), batch('c3'));
  await addToTray(dropBody(GITHUB, MEDIUM_VIEW));
  await addToTray(REMOVE_FILES, { icon: 'x' });
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: rowsOnMap(tray) });
  pressBlock(tree, 'preview:github');
  await flush();
  // The rest is previewed again as one change.
  assert.deepEqual(tray.rows.map((r) => r.key), [keyFor(REMOVE_FILES)]);
  assert.deepEqual([tray.phase, tray.change.id], ['ready', 'c3']);
  assert.deepEqual(calls.filter((c) => c.url === PREVIEW).at(-1).body.requests.map((r) => r.kind), ['gateway.remove']);
  await freshTray();
});

test('a click on a leaving link takes its row out', async () => {
  await freshTray();
  queue(PREVIEW, batch('c1'), batch('c2'), batch('c3'));
  await addToTray(dropBody(GITHUB, MEDIUM_VIEW));
  await addToTray(REMOVE_FILES, { icon: 'x' });
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: rowsOnMap(tray) });
  // A link the tray draws says what a press on it does.
  assert.equal(linkTip(tree, linkOf(tree, 'gateway:kitden>held:kitden:files'), ''), 'Take it out of the preview');
  assert.equal(linkTip(tree, linkOf(tree, 'gateway:kitden>preview:github'), ''), 'Take it out of the preview');
  assert.equal(linkTip(tree, linkOf(tree, 'held:kitden:files>tool:files/read_file'), ''), 'Turn off read_file');
  clickLink(tree, linkOf(tree, 'gateway:kitden>held:kitden:files'));
  await flush();
  assert.deepEqual(tray.rows.map((r) => r.key), [keyFor(dropBody(GITHUB, MEDIUM_VIEW))]);
  // A click on the preview link of a move takes it out too: the last row out cancels the change.
  const now = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: rowsOnMap(tray) });
  clickLink(now, linkOf(now, 'gateway:kitden>preview:github'));
  await flush();
  assert.deepEqual([tray.rows, tray.phase, posted().at(-1)], [[], 'idle', '/api/changes/c3/cancel']);
});

test('the × of a link in the tray takes it out, else adds it', async () => {
  await freshTray();
  state.project = 'website';
  queue(PREVIEW, batch('c1'));
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, picked: 'website' });
  const tool = 'held:kitden:files>tool:files/read_file';
  // Not in the tray: the × adds its change, with the × icon.
  await removeLink(tree, linkOf(tree, tool), 'website');
  assert.deepEqual(tray.rows.map((r) => [r.key, r.icon, r.body]), [['rule:files/read_file@website', 'x', ruleBody('files', 'read_file', 'off', 'website')]]);
  // In the tray: the × of its leaving link takes it out.
  const drawn = gatewayTree(MEDIUM_VIEW, { ...OPTS, picked: 'website', rows: rowsOnMap(tray) });
  assert.equal(linkOf(drawn, tool).leaving, true);
  await removeLink(drawn, linkOf(drawn, tool), 'website');
  assert.deepEqual(tray.rows, []);
  // A row still being asked is in the tray too: a second × takes it out before it answers.
  state.project = '';
  let answer;
  queue(PREVIEW, () => new Promise((resolve) => { answer = resolve; }));
  const gone = 'gateway:kitden>held:kitden:files';
  const adding = removeLink(tree, linkOf(tree, gone), '');
  assert.deepEqual(tray.rows.map((r) => [r.key, r.part]), [[keyFor(REMOVE_FILES), null]]);
  await removeLink(tree, linkOf(tree, gone), '');
  answer(batch('c2')({ requests: calls.filter((c) => c.url === PREVIEW).at(-1).body.requests }));
  assert.equal(await adding, false);
  assert.deepEqual(tray.rows, []);
  // A link the map does not act on does nothing.
  const registered = { ...MEDIUM_VIEW, gateways: [...MEDIUM_VIEW.gateways, { id: 'gw-2', kind: 'metamcp', url: 'http://h/mcp', movable: true, managed: true }], connections: { ...MEDIUM_VIEW.connections, 'gw-2': { claude_code: [], codex: ['x'], cursor: [] } } };
  const other = gatewayTree(registered, OPTS);
  assert.equal(removeLink(other, linkOf(other, 'client:codex>gateway:gw-2'), ''), null);
  await freshTray();
});

test("a bypass link's × removes that client's own entry", async () => {
  await freshTray();
  queue(PREVIEW, batch('c1'));
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const link = linkOf(tree, 'client:codex>outside:local:docs');
  const body = { action: 'mcp.remove_direct', targets: [{ item: 'b' }], params: {} };
  assert.deepEqual(linkRemoval(tree, link, ''), { tip: 'Remove docs from Codex', body });
  await removeLink(tree, link, '');
  assert.deepEqual(tray.rows.map((r) => [r.body, r.icon]), [[body, 'x']]);
  // While it waits, the link's hit and × say a press takes it out, as other tray links do.
  assert.equal(linkTip(tree, link, ''), 'Take it out of the preview');
  assert.equal(linkTip(gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: rowsOnMap(tray) }), link, ''), 'Take it out of the preview');
  // A server a plugin brings has no entry of the client's own to remove.
  const plugin = { ...MEDIUM_VIEW, groups: { ...MEDIUM_VIEW.groups, plugin: [{ name: 'linear', clients: ['codex'], columns: ['codex'], items: [], client_items: {}, stays: 'with the plugin' }] } };
  const withPlugin = gatewayTree(plugin, OPTS);
  assert.equal(linkRemoval(withPlugin, linkOf(withPlugin, 'client:codex>outside:plugin:linear'), ''), null);
  await freshTray();
});

test("the client link's × adds a disconnect row", async () => {
  await freshTray();
  queue(PREVIEW, batch('c1'));
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const link = linkOf(tree, 'client:codex>gateway:kitden');
  const body = { action: 'client.disconnect', targets: [{ client: 'codex' }], params: {} };
  assert.deepEqual(linkRemoval(tree, link, ''), { tip: 'Disconnect Codex', body });
  assert.equal(linkTip(tree, link, ''), 'Disconnect Codex');
  // The row has the plug, as the panel's Disconnect gives it.
  await removeLink(tree, link, '');
  assert.deepEqual(tray.rows.map((r) => [r.body, r.icon]), [[body, 'plug']]);
  // A second × takes it out.
  await removeLink(tree, link, '');
  assert.deepEqual(tray.rows, []);
  // A plugin gives Cursor its entry: Kitden cannot take it out, so its link has no ×.
  const plugin = gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: [...SETUP.slice(0, 2), entry('cursor', 'plugin')] });
  assert.equal(linkRemoval(plugin, linkOf(plugin, 'client:cursor>gateway:kitden'), ''), null);
  await freshTray();
});

const CONNECT_CURSOR = { action: 'setup_server.register', targets: [{ client: 'cursor' }], params: {} };
const DISCONNECT_CODEX = { action: 'client.disconnect', targets: [{ client: 'codex' }], params: {} };
const moveOut = (server, client) => ({ action: 'gateway.move_out', targets: [{ client }], params: { server } });
const removeDirect = (...items) => ({ action: 'mcp.remove_direct', targets: items.map((item) => ({ item })), params: {} });
const laidOut = (tree) => layoutTree(tree, { open: new Set(), narrow: false });

test('a client is heard by its meta once, and a change that waits is still heard', () => {
  // The meta says the state, so no state word follows it.
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.equal(blockLabel(block(tree, 'client:claude_code')), 'Claude Code, Connected');
  assert.equal(blockLabel(block(tree, 'client:cursor')), 'Cursor, Not connected');
  // Without the setup read: "Not known" once.
  assert.equal(blockLabel(block(gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: null }), 'client:codex')), 'Codex, Not known');
});

test('a connect row draws a dashed link to the gateway', () => {
  const row = trayRow(CONNECT_CURSOR);
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [row] });
  const link = linkOf(tree, 'client:cursor>gateway:kitden');
  assert.deepEqual([link.kind, link.row], ['preview', row.key]);
  assert.equal(linkClass(laidOut(tree).links.find((l) => l.from === 'client:cursor')), 'link preview');
  // The client's lamp is the dashed ring and its meta says the change waits; it is not connected
  // yet, so the gateway still counts two clients.
  const cursor = block(tree, 'client:cursor');
  // A no-break space keeps the dot with "Not connected" when the words wrap.
  assert.deepEqual([cursor.meta, cursor.wait, cursor.lamp, cursor.state], ['Not connected', '\u00a0· in preview', 'preview', 'preview']);
  assert.equal(blockLabel(cursor), 'Cursor, Not connected, in preview');
  assert.deepEqual(block(tree, 'gateway:kitden').stats.map((s) => s.words), ['2 clients', '2 servers']);
  // A press on the link takes the row out.
  assert.equal(linkTip(tree, link, ''), 'Take it out of the preview');
  // An old entry is updated: its row names the entry, and the map finds the client by it.
  const setup = [...SETUP.slice(0, 2), entry('cursor', 'old', { item: 'cursor:kitden' })];
  const update = trayRow({ action: 'setup_server.update', targets: [{ item: 'cursor:kitden' }], params: {} });
  assert.equal(linkOf(gatewayTree(MEDIUM_VIEW, { ...OPTS, setup, rows: [update] }), 'client:cursor>gateway:kitden').kind, 'preview');
  // An entry that is off, turned on again ("Turn it on in Codex…"), connects the client too.
  const off = [entry('claude_code', 'added'), entry('codex', 'added', { enabled: false }), entry('cursor', 'missing')];
  const enable = trayRow({ action: 'setup_server.enable', targets: [{ client: 'codex' }], params: {} });
  const turnedOn = gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: off, rows: [enable] });
  assert.deepEqual([linkOf(turnedOn, 'client:codex>gateway:kitden').kind, block(turnedOn, 'client:codex').lamp], ['preview', 'preview']);
  // A row still being asked draws nothing yet, and no row nothing at all.
  for (const rows of [[trayRow(CONNECT_CURSOR, null)], []]) {
    const plain = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows });
    assert.equal(linkOf(plain, 'client:cursor>gateway:kitden'), undefined);
    assert.deepEqual([block(plain, 'client:cursor').lamp, block(plain, 'client:cursor').wait], ['off', undefined]);
  }
});

test('a disconnect row makes the client\'s link leave', () => {
  const row = trayRow(DISCONNECT_CODEX);
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [row] });
  const link = linkOf(tree, 'client:codex>gateway:kitden');
  assert.deepEqual([link.kind, link.leaving, link.row], ['on', true, row.key]);
  assert.equal(linkClass(laidOut(tree).links.find((l) => l.from === 'client:codex' && l.to === 'gateway:kitden')), 'link on leaving');
  // Codex is connected until Apply: its block says so; the other clients keep their links.
  const codex = block(tree, 'client:codex');
  assert.deepEqual([codex.meta, codex.lamp, codex.wait], ['Connected', 'on', undefined]);
  assert.equal(linkOf(tree, 'client:claude_code>gateway:kitden').leaving, undefined);
  assert.equal(linkTip(tree, link, ''), 'Take it out of the preview');
  assert.equal(linkOf(gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [trayRow(DISCONNECT_CODEX, null)] }), 'client:codex>gateway:kitden').leaving, undefined);
});

test('a move-out row shows the server outside, moving to its client', () => {
  const row = trayRow(moveOut('files', 'claude_code'));
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [row] });
  // files is not drawn in the gateway: nor its tools, its links, or its Local group; the gateway
  // counts only the servers not in preview (gateway-notes 4.1), and counts it again once the row
  // is taken out.
  assert.ok(!['held:kitden:files', 'group:kitden:local', 'tool:files/read_file'].some((id) => block(tree, id)));
  assert.ok(!tree.links.some((l) => [l.from, l.to].includes('held:kitden:files')));
  assert.deepEqual(block(tree, 'gateway:kitden').stats.map((s) => s.words), ['2 clients', '1 server']);
  assert.deepEqual(block(gatewayTree(MEDIUM_VIEW, OPTS), 'gateway:kitden').stats.map((s) => s.words), ['2 clients', '2 servers']);
  // It shows outside, after the local rows (Cursor's own files stays apart), moving to Claude Code.
  const shown = block(tree, 'preview-out:files');
  assert.deepEqual([shown.kind, shown.parent, shown.name, shown.meta, shown.lamp, shown.state, shown.icon, shown.h], ['preview', 'group:outside', 'files', 'Moves to Claude Code', 'preview', 'preview', 'hard-drive', 50]);
  assert.deepEqual([shown.takeOut, shown.row, shown.ports], ['In preview. Click to take it out.', row.key, { left: 'out' }]);
  assert.equal(blockLabel(shown), 'files, Moves to Claude Code, In preview');
  assert.deepEqual(tree.blocks.filter((b) => b.parent === 'group:outside').map((b) => b.id), ['outside:move:docs', 'outside:move:github', 'outside:local:docs', 'outside:local:files', 'preview-out:files']);
  // A preview line joins it to Claude Code, at right angles, and its link from the gateway leaves.
  const line = linkOf(tree, 'client:claude_code>preview-out:files');
  assert.deepEqual([line.kind, line.preview, line.row], ['direct', true, row.key]);
  const away = linkOf(tree, 'gateway:kitden>preview-out:files');
  assert.deepEqual([away.kind, away.leaving, away.row], ['on', true, row.key]);
  assert.deepEqual(tree.links.filter((l) => l.to === 'preview-out:files').map((l) => l.from), ['client:claude_code', 'gateway:kitden']);
  const drawn = laidOut(tree).links.filter((l) => l.to === 'preview-out:files');
  assert.deepEqual(drawn.map((l) => [l.shape, linkClass(l)]), [['step', 'link direct preview'], ['curve', 'link on leaving']]);
  assert.equal(linkTip(tree, line, ''), 'Take it out of the preview');
  assert.equal(linkTip(tree, away, ''), 'Take it out of the preview');
  // A remote server sits after the remote rows; with nothing outside, the group comes with it.
  const tracker = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [trayRow(moveOut('tracker', 'codex'))] });
  assert.deepEqual(tracker.blocks.filter((b) => b.parent === 'group:outside').map((b) => b.id).slice(1, 4), ['outside:move:github', 'preview-out:tracker', 'outside:local:docs']);
  assert.deepEqual([block(tracker, 'preview-out:tracker').meta, block(tracker, 'preview-out:tracker').icon], ['Moves to Codex', 'globe']);
  const bare = { ...MEDIUM_VIEW, groups: { move: [], local: [], plugin: [] } };
  const alone = gatewayTree(bare, { ...OPTS, rows: [row] });
  assert.deepEqual(alone.blocks.filter((b) => b.column === 'servers').map((b) => b.id).slice(-2), ['group:outside', 'preview-out:files']);
  // A row still being asked changes nothing yet.
  assert.ok(block(gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [trayRow(moveOut('files', 'claude_code'), null)] }), 'held:kitden:files'));
});

test('a press on the move-out block takes its row out', async () => {
  await freshTray();
  queue(PREVIEW, batch('c1'), batch('c2'), batch('c3'));
  await addToTray(moveOut('files', 'claude_code'));
  await addToTray(REMOVE_FILES, { icon: 'x' });
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: rowsOnMap(tray) });
  pressBlock(tree, 'preview-out:files');
  await flush();
  assert.deepEqual([tray.rows.map((r) => r.key), tray.phase], [[keyFor(REMOVE_FILES)], 'ready']);
  // A click on its line takes it out too: the last row out cancels the change.
  await cancelTray();
  queue(PREVIEW, batch('c4'));
  await addToTray(moveOut('files', 'codex'));
  const now = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: rowsOnMap(tray) });
  assert.equal(block(now, 'preview-out:files').meta, 'Moves to Codex');
  clickLink(now, linkOf(now, 'client:codex>preview-out:files'));
  await flush();
  assert.deepEqual([tray.rows, tray.phase], [[], 'idle']);
  // And a click on its leaving link from the gateway.
  queue(PREVIEW, batch('c5'));
  await addToTray(moveOut('files', 'codex'));
  const again = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: rowsOnMap(tray) });
  clickLink(again, linkOf(again, 'gateway:kitden>preview-out:files'));
  await flush();
  assert.deepEqual([tray.rows, tray.phase], [[], 'idle']);
  await freshTray();
});

test('a bypass removal makes its line leave, and its block when every client loses it', () => {
  // docs in Claude Code: its only client's entry goes, so the block leaves too, with no grip.
  const row = trayRow(removeDirect('a'));
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [row] });
  const line = linkOf(tree, 'client:claude_code>outside:move:docs');
  assert.deepEqual([line.kind, line.leaving, line.row], ['direct', true, row.key]);
  assert.equal(linkClass(laidOut(tree).links.find((l) => l.to === 'outside:move:docs')), 'link direct leaving');
  const docs = block(tree, 'outside:move:docs');
  assert.deepEqual([docs.leaving, Boolean(docs.grip)], [true, false]);
  assert.equal(blockLabel(docs), 'docs, In Claude Code, On, Leaving');
  assert.equal(linkTip(tree, line, ''), 'Take it out of the preview');
  // The other rows stay as they are.
  assert.ok(!block(tree, 'outside:move:github').leaving && !linkOf(tree, 'client:claude_code>outside:move:github').leaving);
  // A server two clients set up: one client's removal takes only its line; both take the block.
  const both = { name: 'github', clients: ['claude_code', 'codex'], columns: ['claude_code', 'codex'], items: ['g', 'h'], client_items: { claude_code: ['g'], codex: ['h'] }, stays: null };
  const view = { ...MEDIUM_VIEW, groups: { ...MEDIUM_VIEW.groups, move: [both] } };
  const one = gatewayTree(view, { ...OPTS, rows: [trayRow(removeDirect('h'))] });
  assert.deepEqual([linkOf(one, 'client:codex>outside:move:github').leaving, linkOf(one, 'client:claude_code>outside:move:github').leaving], [true, undefined]);
  assert.equal(block(one, 'outside:move:github').leaving, undefined);
  const all = gatewayTree(view, { ...OPTS, rows: [trayRow(removeDirect('g', 'h'))] });
  assert.ok(block(all, 'outside:move:github').leaving && linkOf(all, 'client:claude_code>outside:move:github').leaving);
  // A row still being asked changes nothing yet.
  assert.equal(block(gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [trayRow(removeDirect('a'), null)] }), 'outside:move:docs').leaving, undefined);
  // A server whose removal from the gateway waits says it leaves too.
  assert.equal(blockLabel(block(gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [trayRow(REMOVE_FILES)] }), 'held:kitden:files')), 'files, 3 of 4 on, On, Leaving');
});

test('a drop adds a move to the tray', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const heard = {};
  globalThis.document = { addEventListener: (type, fn) => { (heard[type] ||= []).push(fn); }, removeEventListener() {}, documentElement: { classList: { add() {}, remove() {} } }, querySelector: () => null, createElement: (tag) => ({ tag }) };
  Object.assign(data, { gateway: MEDIUM_VIEW });
  data.scope.gateway = '';
  try {
    const tree = gatewayTree(MEDIUM_VIEW, OPTS);
    const layout = layoutTree(tree, { open: new Set(), narrow: false });
    const held = [];
    const node = { dataset: { focus: 'block:outside:move:github' }, getBoundingClientRect: () => ({ left: 0, top: 0 }), querySelector: () => null, querySelectorAll: () => [], setAttribute() {}, removeAttribute() {}, append() {} };
    const view = { node: () => node, hold: (id, at, how) => held.push([id, at, how]), homeIn: (id, ms) => held.push(['homeIn', id, ms]), lightTarget() {}, unlightTarget() {}, glance() {}, tip() {}, untip() {}, box: { isConnected: true, classList: { toggle() {}, remove() {} } }, area: { getBoundingClientRect: () => ({ left: 0, top: 0 }) } };
    placeMoved({ view, model: tree, layout });
    const home = layout.blocks.find((b) => b.id === 'outside:move:github');
    const files = layout.blocks.find((b) => b.id === 'held:kitden:files');
    // The block is where the layout puts it: the press is 10 px into it.
    node.getBoundingClientRect = () => ({ left: home.x, top: home.y });
    let answer;
    queue(PREVIEW, (sent) => new Promise((resolve) => { answer = () => resolve(batch('c1')(sent)); }));
    pressGrip({ button: 0, target: { closest: () => node }, clientX: home.x + 10, clientY: home.y + 10 });
    heard.pointermove[0]({ clientX: home.x + 16, clientY: home.y + 10 });
    heard.pointermove[0]({ clientX: files.x + 10, clientY: files.y + 10 });
    heard.pointerup[0]({ type: 'pointerup', clientX: files.x + 10, clientY: files.y + 10 });
    // The same move as "Move into the gateway…", in the tray at once, with the move's arrow.
    const body = dropBody(GITHUB, MEDIUM_VIEW);
    assert.deepEqual(tray.rows.map((r) => [r.key, r.body, r.part, r.icon]), [[keyFor(body), body, null, 'arrow-right']]);
    // Until it answers the slot shows, and the block waits on it.
    const asked = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: rowsOnMap(tray) });
    const askedLayout = layoutTree(asked, { open: new Set(), narrow: false });
    const slot = askedLayout.blocks.find((b) => b.id === 'slot:github');
    held.length = 0;
    placeMoved({ view, model: asked, layout: askedLayout });
    // The slot hides at once under it.
    assert.deepEqual(held, [['outside:move:github', { x: slot.x, y: slot.y }, { glide: true, ms: 200, onto: 'slot:github' }]]);
    // Its answer puts the preview block in the slot's place, where the block turns into it: it is
    // not sent home.
    answer();
    await flush();
    const answered = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: rowsOnMap(tray) });
    assert.ok(block(answered, 'preview:github') && !block(answered, 'slot:github') && !block(answered, 'outside:move:github'));
    held.length = 0;
    placeMoved({ view, model: answered, layout: layoutTree(answered, { open: new Set(), narrow: false }) });
    assert.deepEqual(held, []);
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null });
    await freshTray();
  }
});

// Just enough of a page for the focus after Apply: the map in #main (the gateway block and a
// client block) and Apply in the dock.
function focusPage() {
  const node = (focus) => ({ dataset: focus ? { focus } : {}, focus() { globalThis.document.activeElement = this; } });
  const gateway = node('block:gateway:kitden');
  const client = node('block:client:codex');
  const apply = node('tray:apply');
  const main = { dataset: {}, querySelectorAll: () => [gateway, client], contains: (other) => [gateway, client].includes(other), focus() { globalThis.document.activeElement = this; } };
  const dock = { contains: (other) => other === apply };
  const body = {};
  globalThis.document = { activeElement: body, body, querySelector: (selector) => ({ '#main': main, '#dock': dock })[selector] ?? null, addEventListener() {}, removeEventListener() {} };
  return { gateway, client, apply, main, body };
}

test('focus goes to the gateway after an applied removal', async () => {
  await freshTray();
  const page = focusPage();
  try {
    const tree = gatewayTree(MEDIUM_VIEW, OPTS);
    // The × of a server's link, focus somewhere, then Apply in the dock; the change is verified.
    const applyRemoval = async (focus) => {
      queue(PREVIEW, batch('c1'));
      queue('/api/changes/c1/apply', { status: 200, json: { id: 'c1', state: 'verified', steps: [] } });
      await removeLink(tree, linkOf(tree, 'gateway:kitden>held:kitden:files'), '');
      focus();
      const focused = globalThis.document.activeElement;
      await applyTray();
      // Applied: the map draws no row now, and focus has not moved yet.
      assert.deepEqual([tray.phase, rowsOnMap(tray), globalThis.document.activeElement], ['applied', [], focused]);
      endApplied();
      await flush();
    };
    // Focus on Apply, whose bar leaves: it goes to the gateway block, not to the page.
    await applyRemoval(() => page.apply.focus());
    assert.equal(globalThis.document.activeElement, page.gateway);
    // Focus the change took away (its link went, so focus is on nothing): the same.
    await applyRemoval(() => { globalThis.document.activeElement = page.body; });
    assert.equal(globalThis.document.activeElement, page.gateway);
    // Focus on a block that is still there stays.
    await applyRemoval(() => page.client.focus());
    assert.equal(globalThis.document.activeElement, page.client);
  } finally {
    await freshTray();
    delete globalThis.document;
  }
});

test('a drag opens the slot "Drop to add" in its group, and its line follows it', () => {
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, drop: { name: 'github', kind: 'remote' } });
  const slot = tree.blocks.find((b) => b.kind === 'slot');
  assert.deepEqual([slot.name, slot.parent, slot.state, slot.column], ['Drop to add', 'group:kitden:remote', 'preview', 'servers']);
  assert.ok(keys(tree).includes(`gateway:kitden>${slot.id} preview`));
  assert.ok(keys(tree).includes('client:claude_code>outside:move:github direct'));
  assert.ok(!tree.blocks.some((b) => b.kind === 'preview'));
  // The gateway is still a gateway block: the slot is not a first run.
  assert.equal(block(tree, 'gateway:kitden').kind, 'gateway');
});

// A drag on the map with stand-ins (Task 4.7): the document hears the pointer, the floating Details
// and the dock are where `covers` says (window rects by selector), and the view records what the
// drag asks of it. Each redraw draws the tree again with the tray and the drag, as gateway.js does.
// The map's area is at the window's top left, so a map point is a window point.
function dragMap({ covers = {}, id = 'outside:move:github', view: shown = MEDIUM_VIEW, opts = OPTS } = {}) {
  const heard = {};
  const asked = [];
  const captured = [];
  globalThis.document = {
    addEventListener: (type, fn) => { (heard[type] ||= []).push(fn); },
    removeEventListener: (type, fn) => { heard[type] = (heard[type] || []).filter((f) => f !== fn); },
    documentElement: { classList: { add() {}, remove() {} } },
    querySelector: (selector) => (covers[selector] ? { getBoundingClientRect: () => covers[selector] } : null),
    createElement: (tag) => ({ tag }),
  };
  const node = { dataset: { focus: `block:${id}` }, getBoundingClientRect: () => ({ left: 0, top: 0 }), setPointerCapture: (pointer) => captured.push(pointer), querySelector: () => null, querySelectorAll: () => [], setAttribute() {}, removeAttribute() {}, append() {} };
  const view = {
    node: () => node,
    hold: (at, point, how = {}) => asked.push(['hold', at, point, how]),
    homeIn: (at, ms) => asked.push(['homeIn', at, ms]),
    lightTarget: (at) => asked.push(['light', at]),
    unlightTarget: () => asked.push(['unlight']),
    glance: (set) => asked.push(['glance', set ? [...set] : null]),
    tip: (text, how = {}) => asked.push(['tip', text, how]),
    untip: () => asked.push(['untip']),
    wire: (from, to, how) => asked.push(['wire', from, to, ...(how ? [how] : [])]),
    unwire: (how) => asked.push(['unwire', ...(how ? [how] : [])]),
    box: { isConnected: true, classList: { toggle() {}, remove() {} } },
    area: { getBoundingClientRect: () => ({ left: 0, top: 0 }) },
  };
  const grabbing = new Set();
  globalThis.document.documentElement.classList = { add: (name) => grabbing.add(name), remove: (name) => grabbing.delete(name) };
  const map = { asked, captured, heard, view, grabbing, node, tree: null, layout: null };
  const redraw = () => {
    map.tree = gatewayTree(shown, { ...opts, rows: rowsOnMap(tray), ...movingOn() });
    map.layout = layoutTree(map.tree, { open: new Set(), narrow: false });
    placeMoved({ view, model: map.tree, layout: map.layout, redraw });
  };
  redraw();
  const at = (which) => map.layout.blocks.find((b) => b.id === which);
  const home = at(id);
  node.getBoundingClientRect = () => ({ left: home.x, top: home.y, width: home.w, height: home.h });
  Object.assign(map, {
    at,
    home,
    redraw,
    // A press 10 px into the block, and the moves and the let go of that pointer.
    press: (onStart) => pressGrip({ button: 0, pointerId: 7, target: { closest: () => node }, clientX: home.x + 10, clientY: home.y + 10 }, onStart),
    move: (x, y) => { for (const fn of heard.pointermove || []) fn({ clientX: x, clientY: y }); },
    up: (x, y) => { for (const fn of heard.pointerup || []) fn({ type: 'pointerup', clientX: x, clientY: y }); },
    // Where the pointer puts the block's top left on a block of the map: its centre is that block's.
    onto: (which) => [at(which).x + 10, at(which).y + 10],
  });
  return map;
}

test('a drag starts after 5 px and swallows its click', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW });
  try {
    const map = dragMap();
    const [x, y] = [map.home.x + 10, map.home.y + 10];
    const started = [];
    map.press(() => started.push('start'));
    // The block takes the pointer at the press.
    assert.deepEqual(map.captured, [7]);
    map.move(x + 3, y + 4 - 0.01);
    assert.deepEqual([started, map.asked], [[], []], 'under 5 px nothing starts');
    map.move(x + 3, y + 4);
    assert.deepEqual(started, ['start']);
    assert.deepEqual(map.asked[0], ['hold', 'outside:move:github', { x: map.home.x + 3, y: map.home.y + 4 }, { pressed: true }]);
    map.up(x + 3, y + 4);
    // The click that ends it selects nothing.
    const click = { prevented: false, stopped: false, preventDefault() { this.prevented = true; }, stopPropagation() { this.stopped = true; } };
    for (const fn of map.heard.click) fn(click);
    assert.deepEqual([click.prevented, click.stopped], [true, true]);
    // A press that moves under 5 px is a click: it is not swallowed.
    map.heard.click = [];
    map.press();
    map.move(x + 2, y + 2);
    map.up(x + 2, y + 2);
    assert.deepEqual(map.heard.click, []);
    assert.equal(tray.rows.length, 0);
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null });
    await freshTray();
  }
});

// Review Focus
test('a drop over Details, over the dock, on nothing or home leaves the tray as it was and glides home in 220', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW });
  try {
    const probe = dragMap();
    // The tracker's spot in the gateway: a drop there, with nothing over it, would move github in.
    const [x, y] = probe.onto('held:kitden:tracker');
    const over = { left: x - 50, top: y - 50, right: x + 50, bottom: y + 50, width: 100, height: 100 };
    const cases = [
      ['over Details', { '#drawer.open': over }, [x, y]],
      ['over the dock', { '#dock': over }, [x, y]],
      ['on nothing', {}, [1200, 10]],
      ['home', {}, [probe.home.x + 10, probe.home.y + 10]],
    ];
    for (const [name, covers, [dropX, dropY]] of cases) {
      const map = dragMap({ covers });
      map.press();
      map.move(map.home.x + 16, map.home.y + 10);
      map.move(dropX, dropY);
      map.up(dropX, dropY);
      await flush();
      assert.deepEqual([tray.rows, posted()], [[], []], name);
      assert.deepEqual(map.asked.at(-1), ['homeIn', 'outside:move:github', 220], name);
      // Over Details or the dock the gateway never lights and no slot opens.
      assert.ok(!map.asked.some(([what]) => what === 'light'), name);
      assert.deepEqual(movingOn(), {}, name);
    }
    // Escape does the same, before Details or the map hear it.
    const map = dragMap();
    map.press();
    map.move(x, y);
    const escape = { key: 'Escape', preventDefault() {}, stopImmediatePropagation() { this.stopped = true; } };
    for (const fn of map.heard.keydown) fn(escape);
    assert.ok(escape.stopped);
    assert.deepEqual([tray.rows.length, map.asked.at(-1)], [0, ['homeIn', 'outside:move:github', 220]]);
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null });
    await freshTray();
  }
});

test('Escape, then release, selects nothing', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW });
  try {
    const map = dragMap();
    map.press();
    map.move(...map.onto('held:kitden:tracker'));
    const escape = { key: 'Escape', preventDefault() {}, stopImmediatePropagation() {} };
    for (const fn of map.heard.keydown) fn(escape);
    assert.deepEqual([tray.rows.length, map.asked.at(-1)], [0, ['homeIn', 'outside:move:github', 220]]);
    // The button is let go later: the click of that release, which the captured block hears, is
    // swallowed then.
    t.mock.timers.tick(10);
    for (const fn of [...(map.heard.pointerup || [])]) fn({ type: 'pointerup', clientX: 0, clientY: 0 });
    const click = { prevented: false, preventDefault() { this.prevented = true; }, stopPropagation() {} };
    for (const fn of map.heard.click || []) fn(click);
    assert.ok(click.prevented, 'the click after Escape selects nothing');
    assert.equal(tray.rows.length, 0);
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null });
    await freshTray();
  }
});

test('a blur of the window ends a drag: nothing stays held and the tray is as it was', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW });
  try {
    const map = dragMap();
    map.press();
    map.move(...map.onto('held:kitden:tracker'));
    assert.ok(map.grabbing.has('grabbing') && map.asked.some(([what]) => what === 'light'));
    for (const fn of [...(windowHeard.blur || [])]) fn({ type: 'blur' });
    assert.equal(map.grabbing.size, 0);
    assert.ok(map.asked.some(([what]) => what === 'unlight'));
    assert.deepEqual(map.asked.at(-1), ['homeIn', 'outside:move:github', 220]);
    assert.deepEqual([movingOn(), tray.rows.length, windowHeard.blur.length], [{}, 0, 0]);
    // The pointer that moves on moves nothing.
    const before = map.asked.length;
    map.move(...map.onto('held:kitden:files'));
    assert.equal(map.asked.length, before);
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null });
    await freshTray();
  }
});

test('a still drag leaves its block where it is; its tip can go by the pointer', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW });
  const seen = [];
  const map = dragMap({ id: 'client:cursor' });
  DRAGS.still = {
    still: true,
    begin: () => seen.push('begin'),
    over: (drag) => map.view.tip('Drop on the gateway', { at: pointOf(drag) }),
    drop: (drag, at) => { seen.push(['drop', at]); return false; },
  };
  try {
    const client = block(map.tree, 'client:cursor');
    startDrag({ button: 0, pointerId: 7, target: { closest: () => map.node }, clientX: map.home.x + 10, clientY: map.home.y + 10 }, client, 'still');
    map.move(map.home.x + 40, map.home.y + 10);
    // No hold: the block stays. The tip goes by the pointer, a map point.
    const pointer = { x: map.home.x + 40, y: map.home.y + 10 };
    assert.ok(!map.asked.some(([what]) => what === 'hold'));
    assert.deepEqual(map.asked.find(([what]) => what === 'tip'), ['tip', 'Drop on the gateway', { at: pointer }]);
    map.up(pointer.x, pointer.y);
    // The drop hears a map point; nothing went off its place, so nothing goes home.
    assert.deepEqual(seen, ['begin', ['drop', pointer]]);
    assert.ok(!map.asked.some(([what]) => what === 'homeIn'));
  } finally {
    delete DRAGS.still;
    delete globalThis.document;
    Object.assign(data, { gateway: null });
    await freshTray();
  }
});

test('the slot grows out of the Kitden gateway', () => {
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, drop: { name: 'github', kind: 'remote' } });
  assert.equal(block(tree, 'slot:github').growsFrom, 'gateway:kitden');
  assert.equal(block(gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [moveRow(GITHUB, null)] }), 'slot:github').growsFrom, 'gateway:kitden');
});

test("the gateway lights and the slot opens over the block's own group", async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW });
  try {
    const map = dragMap();
    map.press();
    map.move(map.home.x + 16, map.home.y + 10);
    // It lights the block, the gateway and its dotted line, as a glance does.
    assert.deepEqual(map.asked.find(([what]) => what === 'glance'), ['glance', ['outside:move:github', 'gateway:kitden', 'client:claude_code>outside:move:github']]);
    assert.deepEqual(movingOn(), {}, 'no slot while the block is in its own group');
    // Its centre over the gateway's groups, in the Local group's place too: the slot opens in its
    // own group, Remote, and the gateway lights.
    map.move(...map.onto('held:kitden:files'));
    assert.deepEqual(movingOn(), { drop: { name: 'github', kind: 'remote' } });
    assert.equal(block(map.tree, 'slot:github').parent, 'group:kitden:remote');
    assert.deepEqual(map.asked.filter(([what]) => what === 'light'), [['light', 'gateway:kitden']]);
    // Its dotted line follows it.
    assert.ok(keys(map.tree).includes('client:claude_code>outside:move:github direct'));
    // Back over its own group: the slot closes and the gateway lets go.
    map.move(map.home.x + 10, map.home.y + 10);
    assert.deepEqual([movingOn(), map.asked.at(-2)], [{}, ['unlight']]);
    map.up(map.home.x + 10, map.home.y + 10);
    // A local server opens its slot in Local.
    const local = dragMap({ id: 'outside:local:docs' });
    local.press();
    local.move(local.home.x + 16, local.home.y + 10);
    local.move(...local.onto('held:kitden:tracker'));
    assert.deepEqual(movingOn(), { drop: { name: 'docs', kind: 'local' } });
    assert.equal(block(local.tree, 'slot:docs').parent, 'group:kitden:local');
    local.up(local.home.x + 10, local.home.y + 10);
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null });
    await freshTray();
  }
});

test('a moving server is drawn once, in the gateway, and the Outside list closes up', () => {
  const plain = layoutTree(gatewayTree(MEDIUM_VIEW, OPTS), { open: new Set(), narrow: false });
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [moveRow(GITHUB)] });
  const moved = layoutTree(tree, { open: new Set(), narrow: false });
  // One github in the Servers column: the preview block in Remote.
  assert.deepEqual(tree.blocks.filter((b) => b.name === 'github').map((b) => b.id), ['preview:github']);
  assert.equal(block(tree, 'preview:github').from, 'outside:move:github');
  // The Outside list closes up: each server under it takes the place of the one above.
  const outside = (layout) => {
    const caption = layout.blocks.find((b) => b.id === 'group:outside');
    return layout.blocks.filter((b) => b.kind === 'outside').map((b) => [b.id, b.y - caption.y]);
  };
  assert.deepEqual(outside(moved).map(([, y]) => y), outside(plain).map(([, y]) => y).slice(0, 3));
  assert.deepEqual(outside(moved).map(([id]) => id), ['outside:move:docs', 'outside:local:docs', 'outside:local:files']);
  // While its row is still asked the block waits on the slot, so it is still the outside block.
  const asked = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [moveRow(GITHUB, null)] });
  assert.ok(block(asked, 'outside:move:github') && block(asked, 'slot:github') && !block(asked, 'preview:github'));
  // Taken out, it comes back from where its preview was.
  assert.equal(block(gatewayTree(MEDIUM_VIEW, OPTS), 'outside:move:github').from, 'preview:github');
});

// Review Focus
test('a server behind N more moves up into the freed place and back after a take-out', async () => {
  await freshTray();
  const many = Array.from({ length: 8 }, (_, i) => ({ name: `s${i + 1}`, clients: ['codex'], columns: ['codex'], items: [`i${i + 1}`], client_items: { codex: [`i${i + 1}`] }, stays: null }));
  const view = { ...MEDIUM_VIEW, groups: { move: many, local: [], plugin: [] } };
  const shown = () => {
    const tree = gatewayTree(view, { ...OPTS, rows: rowsOnMap(tray) });
    const layout = layoutTree(tree, { open: new Set(), narrow: false });
    return layout.blocks.filter((b) => b.id.startsWith('outside:') || b.id.startsWith('more:')).map((b) => (b.kind === 'more' ? b.name : b.id.split(':').at(-1)));
  };
  assert.deepEqual(shown(), ['s1', 's2', 's3', 's4', 's5', '3 more']);
  queue(PREVIEW, batch('c1'));
  await addToTray(dropBody(many[1], view));
  // s6 moves up into the place s2 left.
  assert.deepEqual(shown(), ['s1', 's3', 's4', 's5', 's6', '2 more']);
  await takeOut(tray.rows[0].key);
  await flush();
  assert.deepEqual(shown(), ['s1', 's2', 's3', 's4', 's5', '3 more']);
  await freshTray();
});

test("its client's dotted line runs to the preview block", () => {
  const rows = [moveRow(GITHUB), moveRow(LOCAL_DOCS)];
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows });
  assert.ok(keys(tree).includes('client:claude_code>preview:github direct'));
  assert.ok(keys(tree).includes('client:codex>preview:docs direct'));
  // It is the row's: a press on it, or its ×, takes the move out.
  assert.equal(linkOf(tree, 'client:claude_code>preview:github').row, rows[0].key);
  assert.equal(linkTip(tree, linkOf(tree, 'client:claude_code>preview:github'), ''), 'Take it out of the preview');
  // It is drawn at right angles, as a dotted line from a client is.
  const layout = layoutTree(tree, { open: new Set(), narrow: false });
  assert.equal(layout.links.find((l) => l.from === 'client:claude_code' && l.to === 'preview:github').shape, 'step');
});

// A drag of a held server onto a client (Task 4.7, gateway-notes 6.2): the tips the drag gave.
const tips = (map) => map.asked.filter(([what]) => what === 'tip');
const startOn = (map) => {
  map.press();
  map.move(map.home.x + 16, map.home.y + 10);
};

test('a held server shows the client tip and a wire that follows it', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW, clients: CLIENTS });
  try {
    const map = dragMap({ id: 'held:kitden:files' });
    // No grip: the whole block takes the pointer.
    assert.ok(!block(map.tree, 'held:kitden:files').grip);
    startOn(map);
    assert.deepEqual(map.captured, [7]);
    // The block, every client and its link from the gateway light; the tip asks for a client.
    assert.deepEqual(map.asked.find(([what]) => what === 'glance'), ['glance', ['held:kitden:files', 'client:claude_code', 'client:codex', 'client:cursor', 'gateway:kitden>held:kitden:files']]);
    assert.deepEqual(tips(map).at(-1), ['tip', 'Drop on a client', { on: false }]);
    // The pointer over Codex, whose box is widened 40 px on the right and 16 down: Codex lights, a
    // wire runs from it to the block, and the tip says what a drop does.
    const codex = map.at('client:codex');
    map.move(codex.x + codex.w + 39, codex.y + codex.h + 15);
    assert.deepEqual(map.asked.filter(([what]) => what === 'light'), [['light', 'client:codex']]);
    assert.deepEqual(map.asked.filter(([what]) => what === 'wire'), [['wire', 'client:codex', 'held:kitden:files']]);
    assert.deepEqual(tips(map).at(-1), ['tip', 'Move into Codex', { on: true }]);
    // The block moves on over Codex: it is held where the pointer is, and the wire stays one.
    map.move(codex.x - 23, codex.y + 10);
    assert.deepEqual(map.asked.filter(([what]) => what === 'hold').at(-1), ['hold', 'held:kitden:files', { x: codex.x - 33, y: codex.y }, { pressed: true }]);
    assert.equal(map.asked.filter(([what]) => what === 'wire').length, 1);
    // Off the client the light and the wire go, and the tip asks again.
    map.asked.length = 0;
    map.move(codex.x + codex.w + 41, codex.y + 10);
    assert.deepEqual(map.asked.filter(([what]) => what !== 'hold'), [['unlight'], ['unwire'], ['tip', 'Drop on a client', { on: false }]]);
    // A drop on nothing glides home and leaves the tray as it was.
    map.up(codex.x + codex.w + 41, codex.y + 10);
    await flush();
    assert.deepEqual(map.asked.at(-1), ['homeIn', 'held:kitden:files', 220]);
    assert.deepEqual([tray.rows, posted()], [[], []]);
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null, clients: null });
    await freshTray();
  }
});

test('a drop on a client adds one move-out row and the preview is carried to the Outside list', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW, clients: CLIENTS });
  try {
    const map = dragMap({ id: 'held:kitden:tracker' });
    let answer;
    queue(PREVIEW, (sent) => new Promise((resolve) => { answer = () => resolve(batch('c1')(sent)); }));
    startOn(map);
    const codex = map.at('client:codex');
    const [x, y] = [codex.x + 20, codex.y + 20];
    map.move(x, y);
    const before = map.asked.length;
    map.up(x, y);
    // The same change as the server panel's move out, with its icon, at once; the wire goes.
    assert.deepEqual(tray.rows.map((r) => [r.key, r.body, r.icon]), [['moveout:tracker', moveOut('tracker', 'codex'), 'log-out']]);
    assert.ok(map.asked.slice(before).some(([what]) => what === 'unwire'));
    assert.ok(!map.asked.some(([what]) => what === 'homeIn'));
    // Until its row answers the block waits where it was let go (the press was 10 px into it).
    map.asked.length = 0;
    map.redraw();
    assert.deepEqual(map.asked, [['hold', 'held:kitden:tracker', { x: x - 10, y: y - 10 }, {}]]);
    // Its answer draws the preview block in the Outside list in its place: it starts where the
    // block was (`from`), and nothing is sent home.
    answer();
    await flush();
    map.asked.length = 0;
    map.redraw();
    assert.deepEqual(map.asked, []);
    assert.ok(!block(map.tree, 'held:kitden:tracker'));
    const shown = block(map.tree, 'preview-out:tracker');
    assert.deepEqual([shown.parent, shown.meta, shown.from], ['group:outside', 'Moves to Codex', 'held:kitden:tracker']);
    assert.equal(tray.rows.length, 1);
    // Taken out, the server comes back from where its preview was.
    assert.equal(block(gatewayTree(MEDIUM_VIEW, OPTS), 'held:kitden:tracker').from, 'preview-out:tracker');
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null, clients: null });
    await freshTray();
  }
});

test('a second drop on another client replaces the row', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW, clients: CLIENTS });
  try {
    const map = dragMap({ id: 'held:kitden:tracker' });
    queue(PREVIEW, batch('c1'), batch('c2'));
    const dropOn = (id) => {
      const client = map.at(id);
      startOn(map);
      map.move(client.x + 20, client.y + 20);
      map.up(client.x + 20, client.y + 20);
    };
    dropOn('client:codex');
    // The page draws the tray while the row is asked: the block waits where it was let go.
    map.redraw();
    dropOn('client:claude_code');
    await flush();
    assert.deepEqual(tray.rows.map((r) => [r.key, r.body]), [['moveout:tracker', moveOut('tracker', 'claude_code')]]);
    assert.equal(tray.phase, 'ready');
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null, clients: null });
    await freshTray();
  }
});

test('a client that has the name refuses before the drop, with the reason, and shakes on release', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW, clients: CLIENTS });
  try {
    const refused = async (id, clients, why) => {
      data.clients = clients;
      const map = dragMap({ id });
      const shook = [];
      const cursorNode = { animate: (frames, how) => { shook.push([frames.map((f) => f.transform), how.duration, how.easing]); return { finished: Promise.resolve() }; } };
      map.view.node = (which) => (which === 'client:cursor' ? cursorNode : map.node);
      startOn(map);
      const cursor = map.at('client:cursor');
      map.move(cursor.x + 20, cursor.y + 20);
      // The tip says why in its plain look; Cursor does not light and gets no wire.
      assert.deepEqual(tips(map).at(-1), ['tip', why, { on: false }], why);
      assert.ok(!map.asked.some(([what]) => what === 'light' || what === 'wire'), why);
      assert.deepEqual(shook, [], why);
      // On release the block goes home, the tray is as it was, and Cursor shakes once.
      map.up(cursor.x + 20, cursor.y + 20);
      await flush();
      assert.deepEqual(map.asked.at(-1), ['homeIn', id, 220], why);
      assert.deepEqual([tray.rows, posted()], [[], []], why);
      assert.deepEqual(shook, [[['translateX(0)', 'translateX(-7px)', 'translateX(6px)', 'translateX(-3px)', 'translateX(0)'], 380, 'ease-out']], why);
    };
    // Cursor sets up its own files.
    await refused('held:kitden:files', CLIENTS, 'Cursor already has files.');
    // Cursor is not on this Mac.
    const away = CLIENTS.map((c) => (c.id === 'cursor' ? { ...c, status: 'missing' } : c));
    await refused('held:kitden:tracker', away, 'Cursor is not on this Mac.');
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null, clients: null });
    await freshTray();
  }
});

// A free client's wire to the gateway (Task 4.7, gateway-notes 6.3).
const wires = (map) => map.asked.filter(([what]) => what === 'wire');
const unwires = (map) => map.asked.filter(([what]) => what === 'unwire');

test('a free client draws a wire to the pointer and the gateway lights under it', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW, clients: CLIENTS });
  try {
    const map = dragMap({ id: 'client:cursor' });
    // Cursor can be connected and nothing waits: it can be dragged (the grab cursor).
    assert.deepEqual([block(map.tree, 'client:cursor').connect, block(map.tree, 'client:cursor').drags], [CONNECT_CURSOR, true]);
    // An entry that is off, which Kitden can turn on, connects by turning it on.
    const off = gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: [entry('claude_code', 'added'), entry('codex', 'added', { enabled: false }), entry('cursor', 'missing')] });
    assert.deepEqual(block(off, 'client:codex').connect, { action: 'setup_server.enable', targets: [{ client: 'codex' }], params: {} });
    map.press();
    assert.deepEqual(map.captured, [7]);
    const [x, y] = [map.home.x + 40, map.home.y + 10];
    map.move(x, y);
    // The block stays where it is; Cursor and the gateway light, with no links.
    assert.ok(!map.asked.some(([what]) => what === 'hold'));
    assert.deepEqual(map.asked.find(([what]) => what === 'glance'), ['glance', ['client:cursor', 'gateway:kitden']]);
    // A plain wire from its right port to the pointer; the tip asks for the gateway, by the pointer.
    assert.deepEqual(wires(map).at(-1), ['wire', 'client:cursor', { x, y }, { plain: true }]);
    assert.deepEqual(tips(map).at(-1), ['tip', 'Drop on the gateway', { on: false, at: { x, y } }]);
    // The pointer in the gateway's box, widened 24 px each side and 16 up and down: the gateway
    // lights, the wire ends on its left port, and the tip says what a drop does.
    const gw = map.at('gateway:kitden');
    map.move(gw.x - 23, gw.y - 15);
    assert.deepEqual(map.asked.filter(([what]) => what === 'light'), [['light', 'gateway:kitden']]);
    assert.deepEqual(wires(map).at(-1), ['wire', 'client:cursor', 'gateway:kitden', { plain: true }]);
    assert.deepEqual(tips(map).at(-1), ['tip', 'Connect Cursor', { on: true, at: { x: gw.x - 23, y: gw.y - 15 } }]);
    map.move(gw.x + gw.w + 23, gw.y + gw.h + 15);
    assert.equal(map.asked.filter(([what]) => what === 'light').length, 1);
    // Off it the light goes and the wire runs to the pointer again.
    map.asked.length = 0;
    map.move(gw.x + gw.w + 25, gw.y + 10);
    const pointer = { x: gw.x + gw.w + 25, y: gw.y + 10 };
    assert.deepEqual(map.asked, [['unlight'], ['wire', 'client:cursor', pointer, { plain: true }], ['tip', 'Drop on the gateway', { on: false, at: pointer }]]);
    map.up(pointer.x, pointer.y);
    // Over Details the gateway never lights.
    const covered = dragMap({ id: 'client:cursor', covers: { '#drawer.open': { left: gw.x - 30, top: gw.y - 30, right: gw.x + gw.w + 30, bottom: gw.y + gw.h + 30, width: 1, height: 1 } } });
    covered.press();
    covered.move(covered.home.x + 40, covered.home.y + 10);
    covered.move(gw.x + 20, gw.y + 20);
    assert.ok(!covered.asked.some(([what]) => what === 'light'));
    assert.deepEqual(wires(covered).at(-1), ['wire', 'client:cursor', { x: gw.x + 20, y: gw.y + 20 }, { plain: true }]);
    covered.up(gw.x + 20, gw.y + 20);
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null, clients: null });
    await freshTray();
  }
});

test('a drop on the gateway adds one connect row', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW, clients: CLIENTS });
  try {
    const map = dragMap({ id: 'client:cursor' });
    queue(PREVIEW, batch('c1'));
    const gw = map.at('gateway:kitden');
    map.press();
    map.move(map.home.x + 40, map.home.y + 10);
    map.move(gw.x + 20, gw.y + 20);
    map.up(gw.x + 20, gw.y + 20);
    // The wire goes at once; the row is the client's Connect, the same as in its Details.
    assert.deepEqual(unwires(map), [['unwire', { ms: 0 }]]);
    assert.deepEqual(tray.rows.map((r) => [r.key, r.body]), [[keyFor(CONNECT_CURSOR), CONNECT_CURSOR]]);
    assert.ok(!map.asked.some(([what]) => what === 'hold' || what === 'homeIn'));
    // While it is asked a press starts nothing.
    map.captured.length = 0;
    map.press();
    assert.deepEqual(map.captured, []);
    await flush();
    map.redraw();
    // Its answer draws the preview link to the gateway and " · in preview"; Cursor no longer drags.
    assert.ok(keys(map.tree).includes('client:cursor>gateway:kitden preview'));
    const cursor = block(map.tree, 'client:cursor');
    assert.deepEqual([cursor.wait, cursor.connect, cursor.drags], [' · in preview', null, false]);
    map.press();
    assert.deepEqual([map.captured, tray.rows.length, posted()], [[], 1, [PREVIEW]]);
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null, clients: null });
    await freshTray();
  }
});

test('a miss leaves the tray as it was and the wire fades', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW, clients: CLIENTS });
  try {
    const probe = dragMap({ id: 'client:cursor' });
    const gw = probe.at('gateway:kitden');
    const over = { left: gw.x, top: gw.y, right: gw.x + gw.w, bottom: gw.y + gw.h, width: gw.w, height: gw.h };
    const cases = [
      ['on nothing', {}, [1200, 10]],
      ['home', {}, [probe.home.x + 10, probe.home.y + 10]],
      ['over Details', { '#drawer.open': over }, [gw.x + 20, gw.y + 20]],
      ['over the dock', { '#dock': over }, [gw.x + 20, gw.y + 20]],
    ];
    for (const [name, covers, [dropX, dropY]] of cases) {
      const map = dragMap({ id: 'client:cursor', covers });
      map.press();
      map.move(map.home.x + 40, map.home.y + 10);
      map.move(dropX, dropY);
      map.up(dropX, dropY);
      await flush();
      assert.deepEqual([tray.rows, posted()], [[], []], name);
      // The wire fades out in 180 ms CALM; the block never moved, so nothing goes home.
      assert.deepEqual(unwires(map), [['unwire', { ms: 180, ease: CALM }]], name);
      assert.ok(!map.asked.some(([what]) => what === 'hold' || what === 'homeIn'), name);
      assert.equal(map.asked.at(-1)[0], 'unwire', name);
    }
    // Escape does the same.
    const map = dragMap({ id: 'client:cursor' });
    map.press();
    map.move(gw.x + 20, gw.y + 20);
    for (const fn of map.heard.keydown) fn({ key: 'Escape', preventDefault() {}, stopImmediatePropagation() {} });
    assert.deepEqual([tray.rows.length, unwires(map)], [0, [['unwire', { ms: 180, ease: CALM }]]]);
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null, clients: null });
    await freshTray();
  }
});

test('a connected client cannot be dragged', async (t) => {
  await freshTray();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  Object.assign(data, { gateway: MEDIUM_VIEW, clients: CLIENTS });
  try {
    const map = dragMap({ id: 'client:codex' });
    assert.deepEqual([block(map.tree, 'client:codex').connect, block(map.tree, 'client:codex').drags], [null, false]);
    map.press();
    map.move(map.home.x + 40, map.home.y + 10);
    map.up(map.home.x + 40, map.home.y + 10);
    assert.deepEqual([map.captured, map.asked], [[], []]);
    // One whose kitden entry comes from a plugin (on or off) says why on press, in the tip's plain
    // look by the pointer, until the pointer lets go. Nothing lights and no wire shows.
    for (const fields of [{}, { enabled: false }]) {
      const setup = [entry('claude_code', 'added'), entry('codex', 'plugin', fields), entry('cursor', 'missing')];
      const plugin = dragMap({ id: 'client:codex', opts: { ...OPTS, setup } });
      const { x, y } = plugin.home;
      plugin.press();
      assert.deepEqual([plugin.captured, plugin.asked], [[], [['tip', 'Codex gets Kitden from a plugin.', { at: { x: x + 10, y: y + 10 } }]]]);
      plugin.move(x + 40, y + 10);
      assert.deepEqual(plugin.asked.at(-1), ['tip', 'Codex gets Kitden from a plugin.', { at: { x: x + 40, y: y + 10 } }]);
      plugin.up(x + 40, y + 10);
      assert.deepEqual(plugin.asked.at(-1), ['untip']);
      assert.ok(!plugin.asked.some(([what]) => ['light', 'wire', 'hold', 'glance'].includes(what)));
      // The pointer that moves on shows nothing.
      plugin.move(x + 60, y + 10);
      assert.deepEqual(plugin.asked.at(-1), ['untip']);
      assert.deepEqual([tray.rows, posted()], [[], []]);
    }
  } finally {
    delete globalThis.document;
    Object.assign(data, { gateway: null, clients: null });
    await freshTray();
  }
});

test('a grip shows only where the Kitden gateway can take the server', () => {
  const obot = { id: 'gw-1', kind: 'obot', movable: true };
  const tree = gatewayTree({ ...MEDIUM_VIEW, gateways: [obot], connections: {}, used: [] }, OPTS);
  assert.ok(tree.blocks.filter((b) => b.kind === 'outside').every((b) => !b.grip));
  assert.ok(block(gatewayTree(MEDIUM_VIEW, OPTS), 'outside:move:github').grip);
});

test('the map enters when it is new, jumps for a new project or width, and moves otherwise', () => {
  assert.equal(mapMotion({ fresh: true, projectChanged: true, narrowChanged: true }), 'enter');
  assert.equal(mapMotion({ fresh: false, projectChanged: true, narrowChanged: false }), 'none');
  assert.equal(mapMotion({ fresh: false, projectChanged: false, narrowChanged: true }), 'none');
  assert.equal(mapMotion({ fresh: false, projectChanged: false, narrowChanged: false }), 'move');
  // The view switch brings the map in as one piece, so its blocks do not rise one by one too.
  assert.equal(mapMotion({ fresh: true, projectChanged: false, narrowChanged: false, switched: true }), 'none');
});

test('a link the map can act on says what its × does', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const link = (key) => tree.links.find((l) => `${l.from}>${l.to}` === key);
  assert.deepEqual(linkRemoval(tree, link('gateway:kitden>held:kitden:files'), ''),
    { tip: 'Remove files from the gateway', body: { action: 'gateway.remove', targets: [], params: { server: 'files' } } });
  assert.deepEqual(linkRemoval(tree, link('held:kitden:files>tool:files/read_file'), 'website'),
    { tip: 'Turn off read_file', body: { action: 'gateway.rule', targets: [], params: { server: 'files', tool: 'read_file', state: 'off', project: 'website' } } });
  assert.deepEqual(linkRemoval(tree, link('client:codex>gateway:kitden'), ''),
    { tip: 'Disconnect Codex', body: { action: 'client.disconnect', targets: [{ client: 'codex' }], params: {} } });
  assert.equal(linkRemoval(tree, link('client:codex>outside:local:docs'), '').tip, 'Remove docs from Codex');
});

test('a link of a registered gateway gives no ×', () => {
  const meta = { id: 'gw-2', kind: 'metamcp', url: 'http://127.0.0.1:12008/metamcp/local/mcp', movable: true, managed: true };
  const view = { ...MEDIUM_VIEW, gateways: [...MEDIUM_VIEW.gateways, meta], used: ['gw-2', 'kitden'],
    connections: { ...MEDIUM_VIEW.connections, 'gw-2': { claude_code: [], codex: ['x'], cursor: [] } } };
  const tree = gatewayTree(view, { ...OPTS, held: new Map([['gw-2', { servers: [{ name: 'x', type: 'STREAMABLE_HTTP', url: 'http://h/x' }] }]]) });
  const link = (key) => tree.links.find((l) => `${l.from}>${l.to}` === key);
  assert.ok(link('gateway:gw-2>held:gw-2:x') && link('client:codex>gateway:gw-2'));
  assert.equal(linkRemoval(tree, link('gateway:gw-2>held:gw-2:x'), ''), null);
  assert.equal(linkRemoval(tree, link('client:codex>gateway:gw-2'), ''), null);
  // The Kitden gateway's link in the same tree still has one.
  assert.ok(linkRemoval(tree, link('gateway:kitden>held:kitden:files'), ''));
});

test('a link is answered from the tree it is asked of, not from an older one', () => {
  const first = gatewayTree(MEDIUM_VIEW, OPTS);
  const link = first.links.find((l) => `${l.from}>${l.to}` === 'gateway:kitden>held:kitden:files');
  assert.equal(linkRemoval(first, link, '').tip, 'Remove files from the gateway');
  assert.equal(linkRemoval(first, link, '').tip, 'Remove files from the gateway');
  // The same ids in another tree, where the server is no longer the gateway's (a registered one).
  const other = { ...first, blocks: first.blocks.map((b) => (b.id === 'gateway:kitden' ? { ...b, gateway: { id: 'gw-9', kind: 'metamcp' } } : b)) };
  assert.equal(linkRemoval(other, link, ''), null);
});

test('the width of the map box is read as its content, so the first report of the observer changes nothing', () => {
  const box = { isConnected: true, clientWidth: 900 };
  globalThis.getComputedStyle = () => ({ paddingLeft: '6px', paddingRight: '6px' });
  try {
    assert.equal(contentWidth(box), 888);
    // A box that is off the page, or not laid out, has no width yet.
    assert.equal(contentWidth({ ...box, isConnected: false }), null);
    assert.equal(contentWidth({ ...box, clientWidth: 0 }), null);
  } finally { delete globalThis.getComputedStyle; }
});

test('a second press on the selected block lets go, unless the press opened it', () => {
  assert.equal(afterPress({ selected: 'client:codex', id: 'client:codex', opened: false }), 'letGo');
  assert.equal(afterPress({ selected: 'held:kitden:files', id: 'held:kitden:files', opened: true }), 'select');
  assert.equal(afterPress({ selected: null, id: 'client:codex', opened: false }), 'select');
});

test("a click on empty map keeps a row's review in Details", () => {
  // Letting go of the selection (a click on empty map, a second press) closes the Details it
  // opened; a row's review belongs to the tray, so only the map's selection goes.
  assert.equal(letGoCloses({ type: 'row-review', row: {} }), false);
  assert.equal(letGoCloses({ type: 'held', name: 'files' }), true);
  assert.equal(letGoCloses({ type: 'item', row: {} }), true);
  assert.equal(letGoCloses(null), true);
});

test('the path of a press that opened a server lights when its tools are in, if that is still the selection', () => {
  const lit = new Set(['client:codex', 'held:kitden:files']);
  // Only a press that opened its block waits, and only when there is a path to light.
  assert.equal(lightsLater({ unfolds: true, lit }), true);
  assert.equal(lightsLater({ unfolds: false, lit }), false);
  assert.equal(lightsLater({ unfolds: true, lit: new Set() }), false);
  // When the motions end: the same map and the same selection, else a newer one lights its own path.
  const view = {};
  const drawn = { view, selected: 'held:kitden:files' };
  assert.equal(stillSelected(drawn, { view, selected: 'held:kitden:files', width: 900 }), true);
  assert.equal(stillSelected(drawn, { view, selected: 'client:codex' }), false);
  assert.equal(stillSelected(drawn, { view, selected: null }), false);
  assert.equal(stillSelected(drawn, { view: {}, selected: 'held:kitden:files' }), false);
});

test('pointing at a client or a server outside the gateway previews its paths; a selected link lights its two ends', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.ok(glanceFor(tree, 'client:codex').has('client:codex>gateway:kitden'));
  assert.deepEqual([...glanceFor(tree, 'outside:local:files')].sort(), ['client:cursor', 'client:cursor>outside:local:files', 'outside:local:files']);
  assert.equal(glanceFor(tree, 'held:kitden:files'), null);
  assert.deepEqual([...litFor(tree, 'gateway:kitden>held:kitden:files')].sort(), ['gateway:kitden', 'gateway:kitden>held:kitden:files', 'held:kitden:files']);
  assert.equal(litFor(tree, null).size, 0);
});

test('a selected server or gateway also lights what it holds on; a tool lights only its way in', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const server = litFor(tree, 'held:kitden:files');
  for (const id of ['client:codex', 'gateway:kitden', 'held:kitden:files', 'tool:files/read_file', 'held:kitden:files>tool:files/read_file']) assert.ok(server.has(id), id);
  assert.ok(litFor(tree, 'gateway:kitden').has('gateway:kitden>held:kitden:files'));
  const tool = litFor(tree, 'tool:files/read_file');
  assert.ok(tool.has('held:kitden:files>tool:files/read_file') && !tool.has('tool:files/write_file'));
});

test('a drag lets go of the selection when the block first follows the pointer, before the map holds it', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const heard = {};
  globalThis.document = { addEventListener: (type, fn) => { (heard[type] ||= []).push(fn); }, removeEventListener() {}, documentElement: { classList: { add() {}, remove() {} } }, querySelector: () => null };
  try {
    const tree = gatewayTree(MEDIUM_VIEW, OPTS);
    const layout = layoutTree(tree, { open: new Set(), narrow: false });
    const calls = [];
    const node = { dataset: { focus: 'block:outside:move:github' }, getBoundingClientRect: () => ({ left: 0, top: 0 }), removeAttribute() {}, querySelectorAll: () => [] };
    const view = { node: () => node, hold: () => calls.push('hold'), homeIn() {}, lightTarget() {}, unlightTarget() {}, glance() {}, tip() {}, untip() {}, box: { isConnected: true, classList: { toggle() {}, remove() {} } }, area: { getBoundingClientRect: () => ({ left: 0, top: 0 }) } };
    placeMoved({ view, model: tree, layout, redraw() {} });
    const home = layout.blocks.find((b) => b.id === 'outside:move:github');
    const [x, y] = [home.x + 10, home.y + 10];
    pressGrip({ button: 0, target: { closest: () => node }, clientX: x, clientY: y }, () => calls.push('letGo'));
    heard.pointermove[0]({ clientX: x + 4, clientY: y });
    assert.deepEqual(calls, [], 'a wobble under 5 px starts nothing');
    heard.pointermove[0]({ clientX: x + 6, clientY: y });
    heard.pointermove[0]({ clientX: x + 9, clientY: y });
    assert.deepEqual(calls, ['letGo', 'hold', 'hold']);
    heard.pointerup[0]({ type: 'pointerup', clientX: x + 9, clientY: y });
  } finally { delete globalThis.document; }
});

test('a drag keeps the pointer inside the block when the layout changes its size under the drag', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const heard = {};
  globalThis.document = { addEventListener: (type, fn) => { (heard[type] ||= []).push(fn); }, removeEventListener() {}, documentElement: { classList: { add() {}, remove() {} } }, querySelector: () => null };
  try {
    const tree = gatewayTree(MEDIUM_VIEW, OPTS);
    const narrow = layoutTree(tree, { open: new Set(), narrow: true });
    const wide = layoutTree(tree, { open: new Set(), narrow: false });
    const id = 'outside:move:github';
    const [was, now] = [narrow, wide].map((layout) => layout.blocks.find((b) => b.id === id));
    assert.ok(was.w > now.w, 'the narrow block is wider than the wide one');
    const held = [];
    const node = { dataset: { focus: `block:${id}` }, getBoundingClientRect: () => ({ left: was.x, top: was.y, width: was.w, height: was.h }), removeAttribute() {}, querySelectorAll: () => [] };
    const view = { node: () => node, hold: (_, at) => held.push(at), homeIn() {}, lightTarget() {}, unlightTarget() {}, glance() {}, tip() {}, untip() {}, box: { isConnected: true, classList: { toggle() {}, remove() {} } }, area: { getBoundingClientRect: () => ({ left: 0, top: 0 }) } };
    placeMoved({ view, model: tree, layout: narrow, redraw() {} });
    // A press near the right edge of the wide narrow block, then a move that starts the drag.
    const [x, y] = [was.x + was.w - 15, was.y + 10];
    pressGrip({ button: 0, target: { closest: () => node }, clientX: x, clientY: y });
    heard.pointermove[0]({ clientX: x + 6, clientY: y });
    // The layout turns wide (Details let go, the window is wide enough): the block is narrower now.
    placeMoved({ view, model: tree, layout: wide, redraw() {} });
    const at = held.at(-1);
    assert.ok(x + 6 >= at.x && x + 6 <= at.x + now.w, `the pointer is inside the block (${x + 6} in ${at.x}..${at.x + now.w})`);
    assert.ok(x + 6 > at.x + now.w - 40, 'and it stays near the same edge of the block');
    heard.pointerup[0]({ type: 'pointerup', clientX: x + 6, clientY: y });
  } finally { delete globalThis.document; }
});

test('a server block carries its lamp and on count', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  // Its lamp is on while any of its tools is on; the number before "of" rolls on the map. It folds,
  // so it has a right port too (the map shows it only while it is open).
  const files = block(tree, 'held:kitden:files');
  assert.deepEqual([files.lamp, files.meta, files.icon, files.ports], ['on', '3 of 4 on', 'hard-drive', { left: true, right: true }]);
  // Off for all projects (on in one): none of its tools is on, so its lamp is off.
  const tracker = block(tree, 'held:kitden:tracker');
  assert.deepEqual([tracker.lamp, tracker.icon], ['off', 'globe']);
  // On, with every tool off: off too. One whose tools Kitden does not know follows its switch, and
  // does not fold.
  const none = { ...MEDIUM_VIEW.gateways[0].servers[0], on_count: 0 };
  const n8n = { name: 'n8n', kind: 'local', state: 'on', tools: null, on_count: 0, on_in: 0, tool_list: [] };
  const view = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: [none, n8n] }] };
  const other = gatewayTree(view, OPTS);
  assert.equal(block(other, 'held:kitden:files').lamp, 'off');
  assert.deepEqual([block(other, 'held:kitden:n8n').lamp, block(other, 'held:kitden:n8n').ports], ['on', { left: true, right: false }]);
  // A client: its lamp is on while it is connected, and its port is on its right.
  assert.deepEqual(['claude_code', 'cursor'].map((id) => [block(tree, `client:${id}`).lamp, block(tree, `client:${id}`).ports]), [['on', { right: true }], ['off', { right: true }]]);
  // Without the setup read a client says "Not known" with no lamp: a grey one would say off.
  assert.deepEqual(['meta', 'lamp'].map((k) => block(gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: null }), 'client:codex')[k]), ['Not known', null]);
  // A server whose removal waits in the tray looks leaving until Apply.
  const removing = gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [trayRow(REMOVE_FILES)] });
  assert.deepEqual([block(removing, 'held:kitden:files').leaving, block(removing, 'held:kitden:tracker').leaving], [true, undefined]);
});

test('the gateway block counts clients and servers, one in the singular', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const kitden = block(tree, 'gateway:kitden');
  assert.deepEqual([kitden.meta, kitden.lamp, kitden.ports], ['On this Mac', 'on', { left: true, right: true }]);
  assert.deepEqual(kitden.stats, [{ icon: 'monitor', words: '2 clients' }, { icon: 'server', words: '2 servers' }]);
  assert.equal(blockLabel(kitden), 'Kitden gateway, On this Mac, 2 clients · 2 servers');
  const one = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: [MEDIUM_VIEW.gateways[0].servers[0]] }] };
  const alone = [entry('claude_code', 'added'), entry('codex', 'missing'), entry('cursor', 'missing')];
  assert.deepEqual(block(gatewayTree(one, { ...OPTS, setup: alone }), 'gateway:kitden').stats.map((s) => s.words), ['1 client', '1 server']);
  // A server in preview is not in the gateway yet.
  assert.deepEqual(block(gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [moveRow(GITHUB)] }), 'gateway:kitden').stats.map((s) => s.words), ['2 clients', '2 servers']);
  // Without the setup read, no count of clients; with no settings read, no count at all and no lamp.
  assert.deepEqual(block(gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: null }), 'gateway:kitden').stats.map((s) => s.words), ['2 servers']);
  const broken = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: [], problem: 'Kitden could not read the gateway settings.' }] };
  const unread = block(gatewayTree(broken, OPTS), 'gateway:kitden');
  assert.deepEqual([unread.meta, unread.lamp, unread.stats], ['Could not read its settings.', undefined, null]);
  // A registered gateway says where nothing runs: it has its counts only.
  const obot = { id: 'gw-1', kind: 'obot', url: 'http://127.0.0.1:8080/mcp-connect/x', movable: true, managed: true };
  const both = { ...MEDIUM_VIEW, gateways: [...MEDIUM_VIEW.gateways, obot], connections: { ...MEDIUM_VIEW.connections, 'gw-1': { codex: ['x'] } } };
  const registered = block(gatewayTree(both, { ...OPTS, held: new Map([['gw-1', { servers: [{ name: 'x', type: 'STREAMABLE_HTTP' }] }]]) }), 'gateway:gw-1');
  assert.deepEqual([registered.meta, registered.lamp, registered.stats.map((s) => s.words)], [null, undefined, ['1 client', '1 server']]);
  assert.equal(blockLabel(registered), 'Obot, 1 client · 1 server');
});

test('a tool says how many projects have their own rule, also under All projects', () => {
  const files = MEDIUM_VIEW.gateways[0].servers[0];
  const tool_list = [
    tool('read_file', 'on', 'reads', { own_in: 2 }),
    tool('write_file', 'on', 'writes', { own_in: 1 }),
    tool('delete_file', 'off', 'may write', { own_in: 0 }),
  ];
  const view = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: [{ ...files, tool_list }] }] };
  const all = gatewayTree(view, OPTS);
  const shown = (tree, name) => block(tree, `tool:files/${name}`);
  assert.deepEqual(['read_file', 'write_file', 'delete_file'].map((name) => shown(all, name).projects), [
    { words: '2 projects', said: 'own rule in 2 projects', own: false }, { words: '1 project', said: 'own rule in 1 project', own: false }, null]);
  // A round mark: on or off; a left port where its link comes in.
  assert.deepEqual([shown(all, 'read_file').lamp, shown(all, 'delete_file').lamp, shown(all, 'read_file').ports], ['on', 'off', { left: true }]);
  // A screen reader hears what the folder tag means.
  assert.equal(blockLabel(shown(all, 'read_file')), 'read_file, own rule in 2 projects, On');
  // In a project, "This project" in the accent when that project has a rule of its own.
  const own = { ...view, gateways: [{ ...view.gateways[0], servers: [{ ...files, tool_list: [tool('read_file', 'off', 'reads', { origin: 'project', own_in: 2 }), tool('write_file', 'on', 'writes', { own_in: 1 })] }] }] };
  const atlas = gatewayTree(own, { ...OPTS, picked: 'atlas' });
  assert.deepEqual([shown(atlas, 'read_file').projects, shown(atlas, 'write_file').projects], [{ words: 'This project', said: 'own rule in this project', own: true }, null]);
  assert.equal(blockLabel(shown(atlas, 'read_file')), 'read_file, own rule in this project, Off');
  // While a rule for it in the scope shown waits in the tray, its mark is a dashed ring.
  const off = (project) => trayRow(ruleBody('files', 'read_file', 'off', project));
  assert.equal(shown(gatewayTree(view, { ...OPTS, rows: [off(null)] }), 'read_file').lamp, 'preview');
  assert.equal(shown(gatewayTree(own, { ...OPTS, picked: 'atlas', rows: [off('atlas')] }), 'read_file').lamp, 'preview');
  assert.equal(shown(gatewayTree(own, { ...OPTS, picked: 'atlas', rows: [off(null)] }), 'read_file').lamp, 'off');
  assert.equal(shown(gatewayTree(view, { ...OPTS, rows: [off(null)] }), 'write_file').lamp, 'on');
  assert.equal(shown(gatewayTree(view, { ...OPTS, rows: [trayRow(ruleBody('files', 'read_file', 'off', null), null)] }), 'read_file').lamp, 'on');
});

test('the tool block shows the pending project while its rows wait', () => {
  const files = MEDIUM_VIEW.gateways[0].servers[0];
  const view = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: [{ ...files, tool_list: [tool('read_file', 'on', 'reads', { own_in: 2 }), tool('write_file', 'on', 'writes')] }] }] };
  const shown = (options) => gatewayTree(view, { ...OPTS, ...options }).blocks.find((b) => b.id === 'tool:files/read_file');
  const off = (project, part = {}) => trayRow(ruleBody('files', 'read_file', 'off', project), part);
  const saved = data.projects;
  data.projects = [{ id: 'a', path: '/w/atlas' }, { id: 's', path: '/w/website' }];
  try {
    // One project's row waits: the tool names that project in the accent; its mark stays.
    const one = shown({ rows: [off('a')] });
    assert.deepEqual([one.projects, one.lamp], [{ words: 'atlas', said: 'in preview for atlas', own: true, pending: 1 }, 'on']);
    assert.equal(blockLabel(one), 'read_file, in preview for atlas, On');
    // Two: how many.
    assert.deepEqual(shown({ rows: [off('a'), off('s')] }).projects, { words: '2 projects', said: 'in preview for 2 projects', own: true, pending: 2 });
    // A row with no answer yet, a rule for all projects, or another tool's row: the usual tag.
    assert.deepEqual(shown({ rows: [off('a', null), off(null), trayRow(ruleBody('files', 'write_file', 'off', 'a'))] }).projects, { words: '2 projects', said: 'own rule in 2 projects', own: false });
    // In atlas its own row is a ring on the mark, as before; website's row is the pending tag.
    const atlas = shown({ picked: 'a', rows: [off('a'), off('s')] });
    assert.deepEqual([atlas.lamp, atlas.projects.words], ['preview', 'website']);
  } finally {
    data.projects = saved;
  }
});

test('an outside block has a grey-ring lamp and a grip only where the gateway can take it', () => {
  const plugin = { name: 'linear', clients: ['claude_code'], columns: ['claude_code'], items: [], stays: 'linear comes with a plugin; it stays with the plugin.' };
  const tree = gatewayTree({ ...MEDIUM_VIEW, groups: { ...MEDIUM_VIEW.groups, plugin: [plugin] } }, OPTS);
  const shown = (id) => { const b = block(tree, id); return [b.lamp, b.ports, b.icon, Boolean(b.grip), b.meta]; };
  assert.deepEqual(shown('outside:move:github'), ['out', { left: 'out' }, 'globe', true, 'In Claude Code']);
  assert.deepEqual(shown('outside:local:files'), ['out', { left: 'out' }, 'hard-drive', true, 'In Cursor']);
  assert.deepEqual(shown('outside:plugin:linear'), ['out', { left: 'out' }, 'package-open', false, 'In Claude Code']);
  // The caption asks for a drag on the map; the List, which has no drag, keeps its own words.
  assert.equal(block(tree, 'group:outside').name, 'Outside the gateway · drag one in');
  assert.ok(listRows(tree).some((r) => r.name === "Outside the gateway · calls skip Kitden's rules"));
  // A move in the tray: its block is the preview look, with a left port and the words of a press.
  const moving = block(gatewayTree(MEDIUM_VIEW, { ...OPTS, rows: [moveRow(GITHUB)] }), 'preview:github');
  assert.deepEqual([moving.lamp, moving.ports, moving.icon, moving.takeOut], ['preview', { left: true }, 'globe', 'In preview. Click to take it out.']);
});
