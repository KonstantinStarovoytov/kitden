import assert from 'node:assert/strict';
import { test } from 'node:test';

// panel.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
const { applyOutcome, footerActions, moveFor } = await import('../../src/kitden/web/static/js/panel.js');

const github = { kind: 'mcp_server', name: 'github' };
const direct = { name: 'github', items: ['entry-1', 'entry-2'] };
const obot = { id: 'gw-1', movable: true };
const other = { id: 'gw-2', movable: false };
const model = (gateways) => ({ gateways, groups: { move: [direct] } });
const remove = { def: { id: 'entry-1', client: 'codex' }, action: 'mcp.remove_direct' };
const duplicate = { level: 'warning', client: 'codex', fix_action: 'mcp.remove_direct' };

test('without a registered gateway Details has nothing to move into', () => {
  assert.equal(moveFor(github, model([])), null);
  // So it behaves as before: a lone Remove leads, and no gateway note is due.
  assert.deepEqual(footerActions([remove], [], null), { lead: remove, rest: [] });
});

test('the first gateway that takes servers is the move target', () => {
  assert.deepEqual(moveFor(github, model([other, obot])), { items: direct.items, gateway: obot });
  assert.deepEqual(moveFor(github, model([other])), { items: direct.items, gateway: null });
});

test('only an MCP server with entries to take can move, matched by its exact name', () => {
  assert.equal(moveFor({ kind: 'plugin', name: 'github' }, model([obot])), null);
  assert.equal(moveFor({ kind: 'mcp_server', name: 'GitHub' }, model([obot])), null);
  assert.equal(moveFor(github, { gateways: [obot], groups: { move: [{ name: 'github', items: [] }] } }), null);
  assert.equal(moveFor(github, null), null);
});

test('Move leads when nothing is wrong, and Remove waits under More', () => {
  const move = { items: direct.items, gateway: obot };
  assert.deepEqual(footerActions([remove], [], move), { lead: 'move', rest: [remove] });
});

test('a problem comes before an option: the duplicate fix leads, Move waits', () => {
  const move = { items: direct.items, gateway: obot };
  assert.deepEqual(footerActions([remove], [duplicate], move), { lead: remove, rest: ['move'] });
  // A warning no button fixes: nothing leads, Move is one plain choice.
  const unfixable = { ...duplicate, fix_action: null };
  assert.deepEqual(footerActions([remove], [unfixable], move), { lead: null, rest: ['move', remove] });
});

test('a server to add in the gateway by hand first keeps a lone Remove plain', () => {
  const move = { items: direct.items, gateway: null };
  assert.deepEqual(footerActions([remove], [], move), { lead: null, rest: [remove] });
});

// The server, as fetch sees it: the Apply answer, then the change read back. Records each call.
function server(applyAnswer, readBack) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push(`${options.method || 'GET'} ${url}`);
    return options.method === 'POST' ? applyAnswer() : readBack();
  };
  return calls;
}

// A lost answer logs its error; keep the test output clean.
async function quietly(fn) {
  const log = console.error;
  console.error = () => {};
  try { return await fn(); } finally { console.error = log; }
}

const verified = { id: 'c1', state: 'verified' };
const apply = 'POST /api/changes/c1/apply';
const read = 'GET /api/changes/c1';

test('an Apply answer with a change in it is used as it is', async () => {
  const calls = server(() => Response.json(verified), () => Response.json(verified));
  assert.deepEqual(await applyOutcome('c1'), { after: verified, failure: null });
  assert.deepEqual(calls, [apply]);
});

test('an Apply refusal the server explains is a failure, not a lost answer', async () => {
  const calls = server(() => Response.json({ detail: 'Preview again.' }, { status: 409 }), () => Response.json(verified));
  assert.deepEqual(await applyOutcome('c1'), { after: null, failure: 'Preview again.' });
  assert.deepEqual(calls, [apply]);
});

test('an Apply answer with no readable body is read back, not called a failure', async () => {
  const answers = [
    () => { throw new TypeError('fetch failed'); },
    () => new Response('', { status: 200 }),
    () => new Response('Internal Server Error', { status: 500 }),
  ];
  for (const lost of answers) {
    const calls = server(lost, () => Response.json(verified));
    assert.deepEqual(await quietly(() => applyOutcome('c1')), { after: verified, failure: 'Could not confirm the result. Check Changes before trying again.' });
    assert.deepEqual(calls, [apply, read]);
  }
});

test('a lost Apply answer whose change has not ended cannot say how it went', async () => {
  server(() => new Response('', { status: 502 }), () => Response.json({ id: 'c1', state: 'applying' }));
  assert.deepEqual(await quietly(() => applyOutcome('c1')), { after: null, failure: 'Could not confirm the result. Check Changes before trying again.' });
});
