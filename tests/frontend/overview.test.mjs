import assert from 'node:assert/strict';
import { test } from 'node:test';

// overview.js needs only this from a browser to load.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
const { gatewayCardWords, loadCounts, noteGroups, noteItemRow, targetSel } = await import('../../src/kitden/web/static/js/overview.js');

test('the Kitden gateway card says servers, clients and the client to set up', () => {
  const words = gatewayCardWords({ kind: 'kitden', name: 'Kitden gateway', servers: 2, clients: ['claude_code', 'cursor'], lacking: ['codex'], problem: null });
  assert.equal(words.title, 'Kitden gateway');
  assert.equal(words.line, '2 servers · Claude Code, Cursor');
  assert.equal(words.action, 'Set up in Codex…');
});
test('without a gateway the card offers Set up', () => {
  assert.deepEqual(gatewayCardWords(null), { title: 'Gateway', line: 'No gateway yet.', action: 'Set up' });
});
test('an unreadable settings file is said on the card', () => {
  assert.equal(gatewayCardWords({ kind: 'kitden', name: 'Kitden gateway', servers: 0, clients: [], lacking: [], problem: 'Kitden could not read the gateway settings.' }).line, 'Kitden could not read the gateway settings.');
});

const { allClearWords } = await import('../../src/kitden/web/static/js/overview.js');

test('the all-clear names untested versions only when every found client has a version', () => {
  const full = 'No duplicates, no unreadable files, no untested versions.';
  const short = 'No duplicates, no unreadable files.';
  assert.equal(allClearWords([{ status: 'found', version: '2.1.300' }, { status: 'not_found', version: null }]), full);
  assert.equal(allClearWords([{ status: 'found', version: '2.1.300' }, { status: 'found', version: null }]), short);
  assert.equal(allClearWords([]), full);
});

test('a client with only instruction files does not load nothing', () => {
  const rows = [
    { kind: 'instructions', cells: { codex: { state: 'on' }, cursor: { state: 'none' } } },
    { kind: 'skill', cells: { codex: { state: 'off' }, cursor: { state: 'none' } } },
  ];
  assert.deepEqual(loadCounts(rows, 'codex'), [['instructions', 1, '1 instruction file']]);
  assert.deepEqual(loadCounts(rows, 'cursor'), []);
});

const { clientStatus } = await import('../../src/kitden/web/static/js/overview.js');

test('a client whose same-name item needs review still counts it', () => {
  const rows = [{ kind: 'mcp_server', cells: { codex: { state: 'review' } } }];
  assert.deepEqual(loadCounts(rows, 'codex'), [['mcp_server', 1, '1 MCP server']]);
});

test('a client that could not be read says so, not Not installed', () => {
  assert.deepEqual(clientStatus({ status: 'unreadable' }), { state: 'unk', word: 'Could not read' });
  assert.deepEqual(clientStatus({ status: 'not_found' }), { state: 'missing' });
  assert.deepEqual(clientStatus({ status: 'found', version: '1.0', tested: false }), { state: 'unk', word: 'Not tested' });
  assert.equal(clientStatus({ status: 'found', version: '1.0', tested: true }), null);
});

test('notes are grouped by item, each with its clients', () => {
  const note = (type, names, clients) => ({ type, names, clients, items: ['i'], severity: 'info' });
  const groups = noteGroups([
    note('same_name_other_source', ['docs', 'docs'], ['claude_code', 'codex']),
    note('bypasses_gateway', ['docs'], ['claude_code']),
    note('bypasses_gateway', ['docs'], ['codex']),
    note('unknown_state', ['a', 'b'], ['codex']),
  ]);
  assert.deepEqual(groups.map((g) => [g.name, g.clients, g.notes]), [
    ['docs', ['claude_code', 'codex'], ['Same name, another source', 'Not connected to the gateway']],
    ['a', ['codex'], ['On/off state not readable']],
    ['b', ['codex'], ['On/off state not readable']],
  ]);
  assert.equal(groups[0].first.type, 'same_name_other_source');
});

test('a card about an item selects it by kind and name', () => {
  assert.deepEqual(targetSel({ view: 'map', kind: 'skill', name: 'tidy' }), { kind: 'skill', name: 'tidy' });
  assert.equal(targetSel({ view: 'agents' }), null);
});

test('a note row opens the item it names, not the first name of its note', () => {
  const finding = { type: 'unknown_state', names: ['a', 'b'], items: ['ia', 'ib'], clients: ['codex'], severity: 'info' };
  const rows = [
    { key: 'ra', kind: 'plugin', name: 'a', lookup: 'a', cells: { codex: { items: ['ia'] } } },
    { key: 'rb', kind: 'plugin', name: 'b', lookup: 'b', cells: { codex: { items: ['ib'] } } },
  ];
  const [first, second] = noteGroups([finding]);
  assert.equal(noteItemRow(first, rows).key, 'ra');
  assert.equal(noteItemRow(second, rows).key, 'rb');
  assert.equal(noteItemRow(second, rows.slice(0, 1)), null);
});
