import assert from 'node:assert/strict';
import { test } from 'node:test';

// panel.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
// Node before 21 has no navigator; panel.js must load there too.
delete globalThis.navigator;
const { changeOutcome, changeWords, footerActions, leftOutText, moveFor } = await import('../../src/kitden/web/static/js/panel.js');

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

test('a gateway that could not be read keeps a lone Remove plain', () => {
  // Without the gateway model Move cannot be judged, so Remove must not lead in its place.
  const unread = moveFor(github, null, true);
  assert.deepEqual(unread, { items: [], gateway: null, unread: true });
  assert.deepEqual(footerActions([remove], [], unread), { lead: null, rest: [remove] });
  // Only an MCP server can move; for anything else the gateway does not matter.
  assert.equal(moveFor({ kind: 'plugin', name: 'github' }, null, true), null);
  // An earlier read for this project is still shown, so it still decides.
  assert.deepEqual(moveFor(github, model([obot]), true), { items: direct.items, gateway: obot });
});

// The server, as fetch sees it: the Apply or Undo answer, then the change read back. Records
// each call.
function server(answer, readBack) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push(`${options.method || 'GET'} ${url}`);
    return options.method === 'POST' ? answer() : readBack();
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
const LOST = 'Could not confirm the result. Check Changes before trying again.';

test('an Apply answer with a change in it is used as it is', async () => {
  const calls = server(() => Response.json(verified), () => Response.json(verified));
  assert.deepEqual(await changeOutcome('c1', 'apply'), { after: verified, failure: null });
  assert.deepEqual(calls, [apply]);
});

test('an Apply refusal the server explains is a failure, not a lost answer', async () => {
  const calls = server(() => Response.json({ detail: 'nothing to change in ~/.claude.json' }, { status: 422 }), () => Response.json(verified));
  assert.deepEqual(await changeOutcome('c1', 'apply'), { after: null, failure: 'nothing to change in ~/.claude.json' });
  assert.deepEqual(calls, [apply]);
});

test('Apply again after a lost answer reads the change back, never shows the server words', async () => {
  // The first Apply ran, but its answer and the read-back were both lost. A second Apply is
  // refused, because the change is no longer previewed.
  const refused = () => Response.json({ detail: 'cannot move from verified to applying' }, { status: 409 });
  const calls = server(refused, () => Response.json(verified));
  assert.deepEqual(await changeOutcome('c1', 'apply'), { after: verified, failure: LOST });
  assert.deepEqual(calls, [apply, read]);
  // Any other end gets the usual words for it in the Apply flow.
  const stale = { id: 'c1', state: 'stale' };
  server(refused, () => Response.json(stale));
  assert.deepEqual(await changeOutcome('c1', 'apply'), { after: stale, failure: LOST });
  // Not ended, or not readable: the page cannot say how it went.
  server(refused, () => Response.json({ id: 'c1', state: 'applying' }));
  assert.deepEqual(await changeOutcome('c1', 'apply'), { after: null, failure: LOST });
  server(refused, () => new Response('', { status: 502 }));
  assert.deepEqual(await changeOutcome('c1', 'apply'), { after: null, failure: LOST });
});

test('an Apply answer with no readable body is read back, not called a failure', async () => {
  const answers = [
    () => { throw new TypeError('fetch failed'); },
    () => new Response('', { status: 200 }),
    () => new Response('Internal Server Error', { status: 500 }),
  ];
  for (const lost of answers) {
    const calls = server(lost, () => Response.json(verified));
    assert.deepEqual(await quietly(() => changeOutcome('c1', 'apply')), { after: verified, failure: 'Could not confirm the result. Check Changes before trying again.' });
    assert.deepEqual(calls, [apply, read]);
  }
});

test('a lost Apply answer whose change has not ended cannot say how it went', async () => {
  server(() => new Response('', { status: 502 }), () => Response.json({ id: 'c1', state: 'applying' }));
  assert.deepEqual(await quietly(() => changeOutcome('c1', 'apply')), { after: null, failure: 'Could not confirm the result. Check Changes before trying again.' });
});

const undone = { id: 'c1', state: 'undone' };
const undo = 'POST /api/changes/c1/undo';
const lostAnswers = [
  () => { throw new TypeError('fetch failed'); },
  () => new Response('', { status: 200 }),
  () => new Response('Internal Server Error', { status: 500 }),
];

test('a lost Undo answer is read back, not called a failure', async () => {
  for (const lost of lostAnswers) {
    const calls = server(lost, () => Response.json(undone));
    assert.deepEqual(await quietly(() => changeOutcome('c1', 'undo')), { after: undone, failure: LOST });
    assert.deepEqual(calls, [undo, read]);
  }
});

test('a lost Undo answer whose change has not ended cannot say how it went', async () => {
  // Still applied: the undo may not have reached the server, so it is not over.
  for (const lost of lostAnswers) {
    server(lost, () => Response.json(verified));
    assert.deepEqual(await quietly(() => changeOutcome('c1', 'undo')), { after: null, failure: LOST });
  }
  // The read-back fails too.
  server(lostAnswers[0], () => new Response('', { status: 502 }));
  assert.deepEqual(await quietly(() => changeOutcome('c1', 'undo')), { after: null, failure: LOST });
});

test('an Undo answer is used as it is, and a refusal the server explains is a failure', async () => {
  const blocked = { id: 'c1', state: 'undo_blocked', error: 'The file changed.' };
  let calls = server(() => Response.json(blocked, { status: 409 }), () => Response.json(verified));
  assert.deepEqual(await changeOutcome('c1', 'undo'), { after: blocked, failure: null });
  assert.deepEqual(calls, [undo]);
  calls = server(() => Response.json({ detail: 'The gateway cannot be managed from here' }, { status: 422 }), () => Response.json(undone));
  assert.deepEqual(await changeOutcome('c1', 'undo'), { after: null, failure: 'The gateway cannot be managed from here' });
  assert.deepEqual(calls, [undo]);
  // Refused because it moved on already: read back, as for Apply.
  calls = server(() => Response.json({ detail: 'cannot move from undone to undone' }, { status: 409 }), () => Response.json(undone));
  assert.deepEqual(await changeOutcome('c1', 'undo'), { after: undone, failure: LOST });
  assert.deepEqual(calls, [undo, read]);
});

// Add skills: one change, one review line for what is left out ------------------------------

const copy = (name, reaches) => ({ client: 'claude_code', name, reaches });
const added = { action: 'plugin.skills', steps: [copy('tidy', ['claude_code', 'cursor']), copy('docs', ['claude_code', 'cursor'])] };

test('the review of Add skills names the plugin and every client the copies reach', () => {
  const words = changeWords(added, { params: { plugin: 'toolbox@claude-plugins-official' } });
  assert.equal(words.title, "Add toolbox's skills to Claude Code and Cursor");
  assert.equal(words.done, 'Added 2 skills to Claude Code and Cursor');
  assert.equal(changeWords({ ...added, steps: [added.steps[0]] }).done, 'Added 1 skill to Claude Code and Cursor');
});

test('what Add skills leaves out is one plain line, or nothing', () => {
  assert.equal(leftOutText([]), '');
  assert.equal(leftOutText(undefined), '');
  assert.equal(
    leftOutText([{ name: 'b', why: 'needs the rest of the plugin' }, { name: 'c', why: 'Claude Code already has it' }]),
    'Left out: b (needs the rest of the plugin), c (Claude Code already has it).',
  );
});
