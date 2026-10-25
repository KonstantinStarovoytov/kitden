import assert from 'node:assert/strict';
import { test } from 'node:test';

// gateway.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
const { GATEWAY_COLUMNS, afterPress, findRows, gatewayTree, glanceFor, heldServer, kitdenLinks, linkRemoval, listAt, listRows, litFor, mapMotion, narrowFor, serverCount } = await import('../../src/kitden/web/static/js/gateway.js');
const { dropBody, dropTarget, pressGrip, placeMoved } = await import('../../src/kitden/web/static/js/gateway-drag.js');
const { moveBody, moveTargets } = await import('../../src/kitden/web/static/js/details.js');
const { offersSwitch } = await import('../../src/kitden/web/static/js/gateway-details.js');
const { blockLabel, findChip, findIn, keepOpen, layoutTree, pressOpen, wideWidth } = await import('../../src/kitden/web/static/js/map.js');
const { kitdenClients } = await import('../../src/kitden/web/static/js/parts.js');
const { viewMode } = await import('../../src/kitden/web/static/js/store.js');

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
      { name: 'docs', clients: ['claude_code'], columns: ['claude_code'], items: ['a'], stays: null },
      { name: 'github', clients: ['claude_code'], columns: ['claude_code'], items: ['g'], stays: null },
    ],
    local: [
      { name: 'docs', clients: ['codex'], columns: ['codex'], items: ['b'], stays: null },
      { name: 'files', clients: ['cursor'], columns: ['cursor'], items: ['c'], stays: null },
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
  assert.deepEqual([outside[0].y, outside[1].y, outside[0].h], [309, 365, 50]);
  assert.equal(wideWidth(gatewayTree(MEDIUM_VIEW, OPTS)), 836);
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
  assert.equal(block(tree, 'tool:files/write_file').tag, 'This project');
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
  // Found lights the dot, but no client reaches a gateway yet: its state, and the word a screen
  // reader hears, stay Off, as the map shows no link.
  const codex = m.blocks.find((b) => b.id === 'client:codex');
  assert.deepEqual([codex.dot, codex.state], ['on', 'off']);
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
  assert.equal(block(tree, 'gateway:kitden').meta, '2 clients · 2 servers');
  // Not read: no count of clients it does not know.
  assert.equal(block(gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: null }), 'gateway:kitden').meta, '2 servers');
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
  // Its meta says its clients and servers: an "On" beside it would say more than Kitden knows.
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.equal(blockLabel(block(tree, 'gateway:kitden')), 'Kitden gateway, 2 clients · 2 servers');
  const none = ['claude_code', 'codex', 'cursor'].map((c) => entry(c, 'missing'));
  assert.equal(blockLabel(block(gatewayTree(MEDIUM_VIEW, { ...OPTS, setup: none }), 'gateway:kitden')), 'Kitden gateway, 0 clients · 2 servers');
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

test('N more and a group address open the List at that group', () => {
  const rows = Array.from({ length: 8 }, (_, i) => ({ name: `direct-${i}`, clients: ['codex'], columns: ['codex'], items: ['x'], stays: null, override: false }));
  const tree = gatewayTree({ ...MEDIUM_VIEW, groups: { move: rows, local: [], plugin: [] } }, OPTS);
  const more = layoutTree(tree, { open: new Set(), narrow: false }).blocks.find((b) => b.kind === 'more');
  assert.equal(more.id, 'more:group:outside');
  assert.deepEqual(listAt(more.id), { mode: 'list', selected: { kind: 'group', name: 'outside' } });
  assert.deepEqual(listAt('group:outside'), { mode: 'list', selected: { kind: 'group', name: 'outside' } });
  assert.deepEqual(listAt('more:group:kitden:remote').selected, { kind: 'group', name: 'kitden:remote' });
});

test('the map goes narrow by the window rule, or where the wide map does not fit its box', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  // 1440 px with Details beside the page leaves the map 840 px: the wide map fits.
  assert.equal(narrowFor(tree, { window: 1440, box: 840, docked: true }), false);
  assert.equal(narrowFor(tree, { window: 1100, box: 836, docked: false }), false);
  assert.equal(narrowFor(tree, { window: 1100, box: 500, docked: true }), true);
  assert.equal(narrowFor(tree, { window: 900, box: 868, docked: false }), true);
  // 1366 px with Details: the window rule says wide, but 766 px is too small.
  assert.equal(narrowFor(tree, { window: 1366, box: 766, docked: true }), true);
  // Before the box is measured, the window rule alone.
  assert.equal(narrowFor(tree, { window: 1440, box: null, docked: false }), false);
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

test('a match behind N more shows its group whole', () => {
  const rows = Array.from({ length: 8 }, (_, i) => ({ name: `direct-${i}`, clients: ['codex'], columns: ['codex'], items: ['x'], stays: null, override: false }));
  const tree = gatewayTree({ ...MEDIUM_VIEW, groups: { move: rows, local: [], plugin: [] } }, OPTS);
  const shown = (open) => layoutTree(tree, { open, narrow: false }).blocks.map((b) => b.id);
  assert.ok(shown(new Set()).includes('more:group:outside') && !shown(new Set()).includes('outside:move:direct-7'));
  const found = findIn(tree, 'direct-7');
  assert.ok(shown(found.open).includes('outside:move:direct-7') && !shown(found.open).includes('more:group:outside'));
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

test('a preview shows a preview block and link in the right group', () => {
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, preview: { name: 'github', kind: 'remote' } });
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
  // One preview at a time: no grips while it shows.
  assert.ok(tree.blocks.every((b) => !b.grip));
  // A local server goes to Local; a group the gateway does not have yet comes with it, Remote first.
  const local = gatewayTree(MEDIUM_VIEW, { ...OPTS, preview: { name: 'docs', kind: 'local' } });
  assert.equal(block(local, 'preview:docs').parent, 'group:kitden:local');
  assert.ok(!keys(local).includes('client:codex>outside:local:docs direct') && keys(local).includes('client:claude_code>outside:move:docs direct'));
  const onlyLocal = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers: [MEDIUM_VIEW.gateways[0].servers[0]] }] };
  const fresh = gatewayTree(onlyLocal, { ...OPTS, preview: { name: 'github', kind: 'remote' } });
  assert.deepEqual(fresh.blocks.filter((b) => b.column === 'servers').map((b) => b.id).slice(0, 4), ['group:kitden:remote', 'preview:github', 'group:kitden:local', 'held:kitden:files']);
  assert.equal(block(fresh, 'group:kitden:remote').name, 'Remote');
});

test('a drag opens the slot "Drop to add" in its group, and its line hides', () => {
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, drop: { name: 'github', kind: 'remote' } });
  const slot = tree.blocks.find((b) => b.kind === 'slot');
  assert.deepEqual([slot.name, slot.parent, slot.state, slot.column], ['Drop to add', 'group:kitden:remote', 'preview', 'servers']);
  assert.ok(keys(tree).includes(`gateway:kitden>${slot.id} preview`));
  assert.ok(!keys(tree).includes('client:claude_code>outside:move:github direct'));
  assert.ok(!tree.blocks.some((b) => b.kind === 'preview'));
  // The gateway is still a gateway block: the slot is not a first run.
  assert.equal(block(tree, 'gateway:kitden').kind, 'gateway');
});

test('a drop on its own group puts the block back; only the rest of Servers previews', () => {
  const at = (l, id) => l.blocks.find((b) => b.id === id);
  // Before the block leaves its group no slot opens, so a click that wobbles 4 px lands on its own
  // group: it goes back and asks for nothing.
  const still = gatewayTree(MEDIUM_VIEW, OPTS);
  const before = layoutTree(still, { open: new Set(), narrow: false });
  const home = at(before, 'outside:move:github');
  assert.equal(dropTarget(still, before, home.x + 12, home.y + 14), null);
  // Out of it, the slot opens and the group moves down; on the slot, or on a server in the
  // gateway, a drop previews.
  const tree = gatewayTree(MEDIUM_VIEW, { ...OPTS, drop: { name: 'github', kind: 'remote' } });
  const layout = layoutTree(tree, { open: new Set(), narrow: false });
  const slot = at(layout, 'slot:github');
  assert.equal(dropTarget(tree, layout, slot.x + 10, slot.y + 10), 'servers');
  const files = at(layout, 'held:kitden:files');
  assert.equal(dropTarget(tree, layout, files.x + 10, files.y + 10), 'servers');
  // On the outside group as it is shown now, from its caption to its last block: back.
  const caption = at(layout, 'group:outside');
  const now = at(layout, 'outside:move:github');
  const last = layout.blocks.filter((b) => b.id.startsWith('outside:')).at(-1);
  for (const [x, y] of [[caption.x + 5, caption.y + 2], [now.x + 10, now.y + 10], [last.x + 10, last.y + last.h - 1]]) {
    assert.equal(dropTarget(tree, layout, x, y), null);
  }
  // Off the Servers column: back.
  assert.equal(dropTarget(tree, layout, 5, slot.y + 10), null);
  assert.equal(dropTarget(tree, layout, at(layout, 'gateway:kitden').x + 5, slot.y + 10), null);
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
});

test('a link the map can act on says what its × does', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const link = (key) => tree.links.find((l) => `${l.from}>${l.to}` === key);
  assert.deepEqual(linkRemoval(tree, link('gateway:kitden>held:kitden:files'), ''),
    { tip: 'Remove files from the gateway', body: { action: 'gateway.remove', targets: [], params: { server: 'files' } } });
  assert.deepEqual(linkRemoval(tree, link('held:kitden:files>tool:files/read_file'), 'website'),
    { tip: 'Turn off read_file', body: { action: 'gateway.rule', targets: [], params: { server: 'files', tool: 'read_file', state: 'off', project: 'website' } } });
  assert.equal(linkRemoval(tree, link('client:codex>gateway:kitden'), ''), null);
  assert.equal(linkRemoval(tree, link('client:codex>outside:local:docs'), ''), null);
});

test('a second press on the selected block lets go, unless the press opened it', () => {
  assert.equal(afterPress({ selected: 'client:codex', id: 'client:codex', opened: false }), 'letGo');
  assert.equal(afterPress({ selected: 'held:kitden:files', id: 'held:kitden:files', opened: true }), 'select');
  assert.equal(afterPress({ selected: null, id: 'client:codex', opened: false }), 'select');
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
  globalThis.document = { addEventListener: (type, fn) => { (heard[type] ||= []).push(fn); }, removeEventListener() {}, documentElement: { classList: { add() {}, remove() {} } } };
  try {
    const tree = gatewayTree(MEDIUM_VIEW, OPTS);
    const layout = layoutTree(tree, { open: new Set(), narrow: false });
    const calls = [];
    const node = { dataset: { focus: 'block:outside:move:github' }, getBoundingClientRect: () => ({ left: 0, top: 0 }) };
    const view = { node: () => node, hold: () => calls.push('hold'), letGo() {}, box: { isConnected: true, classList: { toggle() {}, remove() {} } }, area: { getBoundingClientRect: () => ({ left: 0, top: 0 }) } };
    placeMoved({ view, model: tree, layout, redraw() {} });
    const home = layout.blocks.find((b) => b.id === 'outside:move:github');
    const [x, y] = [home.x + 10, home.y + 10];
    pressGrip({ button: 0, target: { closest: () => node }, clientX: x, clientY: y }, () => calls.push('letGo'));
    heard.pointermove[0]({ clientX: x + 2, clientY: y });
    assert.deepEqual(calls, [], 'a wobble under 4 px starts nothing');
    heard.pointermove[0]({ clientX: x + 6, clientY: y });
    heard.pointermove[0]({ clientX: x + 9, clientY: y });
    assert.deepEqual(calls, ['letGo', 'hold', 'hold']);
    heard.pointerup[0]({ type: 'pointerup', clientX: x + 9, clientY: y });
  } finally { delete globalThis.document; }
});

test('a drag keeps the pointer inside the block when the layout changes its size under the drag', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const heard = {};
  globalThis.document = { addEventListener: (type, fn) => { (heard[type] ||= []).push(fn); }, removeEventListener() {}, documentElement: { classList: { add() {}, remove() {} } } };
  try {
    const tree = gatewayTree(MEDIUM_VIEW, OPTS);
    const narrow = layoutTree(tree, { open: new Set(), narrow: true });
    const wide = layoutTree(tree, { open: new Set(), narrow: false });
    const id = 'outside:move:github';
    const [was, now] = [narrow, wide].map((layout) => layout.blocks.find((b) => b.id === id));
    assert.ok(was.w > now.w, 'the narrow block is wider than the wide one');
    const held = [];
    const node = { dataset: { focus: `block:${id}` }, getBoundingClientRect: () => ({ left: was.x, top: was.y, width: was.w, height: was.h }), removeAttribute() {}, querySelectorAll: () => [] };
    const view = { node: () => node, hold: (_, at) => held.push(at), letGo() {}, box: { isConnected: true, classList: { toggle() {}, remove() {} } }, area: { getBoundingClientRect: () => ({ left: 0, top: 0 }) } };
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
