import assert from 'node:assert/strict';
import { test } from 'node:test';

// gateway.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
const { gatewayTree, heldServer, kitdenLinks, offersSwitch, serverFor, visibleRows } = await import('../../src/kitden/web/static/js/gateway.js');
const { kitdenClients } = await import('../../src/kitden/web/static/js/parts.js');

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

test('a group shows six rows and says how many more there are', () => {
  const rows = Array.from({ length: 7 }, (_, i) => ({ name: `s${i}` }));
  assert.deepEqual(visibleRows(rows, false), { shown: rows.slice(0, 6), cut: 1 });
  assert.deepEqual(visibleRows(rows.slice(0, 6), false), { shown: rows.slice(0, 6), cut: 0 });
  assert.deepEqual(visibleRows(rows, true), { shown: rows, cut: 0 });
});

test('the Gateway opens only a selected server', () => {
  const map = { rows: [{ kind: 'mcp_server', name: 'github' }, { kind: 'skill', name: 'github' }] };
  assert.equal(serverFor(map, { kind: 'mcp_server', name: 'github' }), map.rows[0]);
  assert.equal(serverFor(map, { kind: 'skill', name: 'github' }), null);
  assert.equal(serverFor(map, { kind: 'mcp_server', name: 'gone' }), null);
  assert.equal(serverFor(null, { kind: 'mcp_server', name: 'github' }), null);
});

test('a selected server the Kitden gateway holds opens in its own panel', () => {
  const model = { gateways: [{ kind: 'kitden', servers: [{ name: 'files' }] }, { kind: 'metamcp', servers: [{ name: 'x' }] }] };
  assert.equal(heldServer(model, { kind: 'mcp_server', name: 'files' }).name, 'files');
  assert.equal(heldServer(model, { kind: 'mcp_server', name: 'x' }), null);
  assert.equal(heldServer(model, { kind: 'skill', name: 'files' }), null);
  assert.equal(heldServer(null, { kind: 'mcp_server', name: 'files' }), null);
});

// The medium sample's /api/gateway-view, cut short: held files (local) and tracker (remote);
// docs set up twice, in Claude Code (remote) and in Codex (local); Cursor's direct files.
const MEDIUM_VIEW = {
  gateways: [{ id: 'kitden', kind: 'kitden', name: 'Kitden gateway', servers: [
    { name: 'files', kind: 'local', state: 'on', tools: 4 },
    { name: 'tracker', kind: 'remote', state: 'off', tools: 3 },
  ] }],
  groups: {
    move: [{ name: 'docs', clients: ['claude_code'], items: ['a'] }],
    local: [{ name: 'docs', clients: ['codex'], items: ['b'] }, { name: 'files', clients: ['cursor'], items: ['c'] }],
    plugin: [],
  },
};
const SETUP = [entry('claude_code', 'added'), entry('codex', 'added'), entry('cursor', 'missing')];
const keys = (tree) => tree.links.map((l) => `${l.from}>${l.to} ${l.kind}`);

test('the probe tree joins linked clients to the gateway and each outside row to its clients', () => {
  const tree = gatewayTree(MEDIUM_VIEW, { setup: SETUP, open: new Set() });
  assert.deepEqual(tree.blocks.filter((b) => b.kind === 'client').map((b) => b.id), ['client:claude_code', 'client:codex', 'client:cursor']);
  assert.ok(keys(tree).includes('client:codex>gateway:kitden on'));
  assert.ok(!keys(tree).some((k) => k.startsWith('client:cursor>gateway:')));
  assert.ok(!keys(gatewayTree(MEDIUM_VIEW, { setup: [entry('codex', 'missing')], open: new Set() })).includes('client:codex>gateway:kitden on'));
  // Held servers sit in Remote and Local groups; an off server has no link from the gateway.
  const files = tree.blocks.find((b) => b.id === 'held:kitden:files');
  assert.deepEqual([files.parent, files.column, files.count], ['group:kitden:local', 'servers', 4]);
  assert.equal(tree.blocks.find((b) => b.id === 'held:kitden:tracker').parent, 'group:kitden:remote');
  assert.ok(keys(tree).includes('gateway:kitden>held:kitden:files on'));
  assert.ok(!keys(tree).some((k) => k.startsWith('gateway:kitden>held:kitden:tracker')));
  // One name in two groups is two blocks, each joined to its own client by a direct line.
  assert.ok(keys(tree).includes('client:codex>outside:local:docs direct'));
  assert.ok(keys(tree).includes('client:claude_code>outside:move:docs direct'));
  assert.equal(tree.blocks.find((b) => b.id === 'outside:local:files').parent, 'group:outside');
  // No tools while folded.
  assert.ok(!tree.blocks.some((b) => b.kind === 'tool'));
});

test("an open server's tools come from its tool list, and an off tool has no link", () => {
  const tools = { files: [{ name: 'read_file', state: 'on' }, { name: 'delete_file', state: 'off' }, { name: 'write_file', state: 'on', effective: 'off' }] };
  const tree = gatewayTree(MEDIUM_VIEW, { setup: SETUP, open: new Set(['held:kitden:files']), tools });
  assert.deepEqual(tree.blocks.filter((b) => b.kind === 'tool').map((b) => [b.id, b.parent, b.state]), [
    ['tool:files/read_file', 'held:kitden:files', 'on'],
    ['tool:files/delete_file', 'held:kitden:files', 'off'],
    ['tool:files/write_file', 'held:kitden:files', 'off'],
  ]);
  assert.deepEqual(keys(tree).filter((k) => k.includes('>tool:')), ['held:kitden:files>tool:files/read_file on']);
});

test("a held server's panel links to the Library only when a client loads it through the gateway", () => {
  const model = { connections: { kitden: { claude_code: ['files'], codex: ['files'], cursor: [] } } };
  assert.deepEqual(kitdenLinks(model, 'files').map((l) => [l.label, l.view, l.selected]), [['Compare across clients', 'library', { kind: 'mcp_server', name: 'files' }]]);
  // No client reaches tracker here, so the Library has no row for it.
  assert.deepEqual(kitdenLinks(model, 'tracker'), []);
  assert.deepEqual(kitdenLinks(null, 'files'), []);
});
