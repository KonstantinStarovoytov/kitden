import assert from 'node:assert/strict';
import { test } from 'node:test';

// gateway.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
const { GATEWAY_COLUMNS, gatewayTree, heldServer, kitdenLinks, listAt, listRows, narrowFor, serverCount } = await import('../../src/kitden/web/static/js/gateway.js');
const { offersSwitch } = await import('../../src/kitden/web/static/js/gateway-details.js');
const { findIn, layoutTree } = await import('../../src/kitden/web/static/js/map.js');
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
    { ...MEDIUM_VIEW.gateways[0].servers[0], origin: 'project', differs: true, tool_list: [tool('write_file', 'off', 'writes', { origin: 'project' })] },
    { ...MEDIUM_VIEW.gateways[0].servers[1], state: 'off', origin: 'project', differs: true },
  ];
  const view = { ...MEDIUM_VIEW, gateways: [{ ...MEDIUM_VIEW.gateways[0], servers }] };
  const tree = gatewayTree(view, { ...OPTS, picked: 'atlas' });
  assert.equal(block(tree, 'tool:files/write_file').tag, 'This project');
  assert.equal(block(tree, 'held:kitden:files').tag, 'Only this project');
  assert.equal(block(tree, 'held:kitden:tracker').tag, 'This project');
  assert.equal(block(gatewayTree(MEDIUM_VIEW, OPTS), 'held:kitden:files').tag, null);
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
  // Found is a good state: its dot is lit, though no client reaches a gateway yet.
  assert.equal(m.blocks.find((b) => b.id === 'client:codex').state, 'on');
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
