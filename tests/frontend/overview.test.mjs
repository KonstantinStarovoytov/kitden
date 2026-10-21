import assert from 'node:assert/strict';
import { test } from 'node:test';

// overview.js needs only this from a browser to load.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
const { gatewayCardWords } = await import('../../src/kitden/web/static/js/overview.js');

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
