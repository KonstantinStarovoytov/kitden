import assert from 'node:assert/strict';
import { test } from 'node:test';

// panel.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
// Node before 21 has no navigator; panel.js must load there too.
delete globalThis.navigator;
const { afterParts, alignGroups, canShowReview, closeForProject, countedDefinition, changeOutcome, chosenKeys, callsText, changeWords, footerActions, heldActions, isPanelOpen, offerLabel, layerState, leftOutText, kindWord, loadsLede, moveFor, moveTargets, openPanel, plainSecrets, scopeWords, toolRows, writingToolsOn } = await import('../../src/kitden/web/static/js/panel.js');
const { addOptions, whyNoAction } = await import('../../src/kitden/web/static/js/offer.js');
const { busy, data, state } = await import('../../src/kitden/web/static/js/store.js');

const github = { kind: 'mcp_server', name: 'github' };
const direct = { name: 'github', items: ['entry-1', 'entry-2'] };
const obot = { id: 'gw-1', movable: true };
const other = { id: 'gw-2', movable: false };
const kitden = { id: 'kitden', kind: 'kitden', name: 'Kitden gateway', movable: true };
const model = (gateways, local = []) => ({ gateways, groups: { move: [direct], local, plugin: [] } });
const remove = { def: { id: 'entry-1', client: 'codex' }, action: 'mcp.remove_direct' };
const duplicate = { level: 'warning', client: 'codex', fix_action: 'mcp.remove_direct' };

test('without a registered gateway Details has nothing to move into', () => {
  assert.equal(moveFor(github, model([])), null);
  // So it behaves as before: a lone Remove leads, and no gateway note is due.
  assert.deepEqual(footerActions([remove], [], null), { lead: remove, rest: [] });
});

test('the gateways that take servers are the move targets', () => {
  assert.deepEqual(moveFor(github, model([other, obot])), { items: direct.items, gateways: [obot] });
  assert.deepEqual(moveFor(github, model([other])), { items: direct.items, gateways: [] });
});

test('the Kitden gateway is offered first, a registered gateway second, never in its place', () => {
  assert.deepEqual(moveTargets(model([kitden, other, obot]), 'move'), [kitden, obot]);
  assert.deepEqual(moveFor(github, model([kitden, obot])), { items: direct.items, gateways: [kitden, obot] });
  // A local server starts a program on this Mac: only the Kitden gateway can hold it.
  const local = { name: 'files', items: ['entry-3'] };
  assert.deepEqual(moveTargets(model([kitden, obot]), 'local'), [kitden]);
  assert.deepEqual(moveFor({ kind: 'mcp_server', name: 'files' }, model([kitden, obot], [local])), { items: local.items, gateways: [kitden] });
  // Without it a local server stays where it is, and says nothing about a gateway.
  assert.equal(moveFor({ kind: 'mcp_server', name: 'files' }, model([obot], [local])), null);
  assert.deepEqual(moveTargets(model([kitden, obot]), 'plugin'), []);
  assert.deepEqual(moveTargets(null, 'move'), []);
});

test('only an MCP server with entries to take can move, matched by its exact name', () => {
  assert.equal(moveFor({ kind: 'plugin', name: 'github' }, model([obot])), null);
  assert.equal(moveFor({ kind: 'mcp_server', name: 'GitHub' }, model([obot])), null);
  assert.equal(moveFor(github, { gateways: [obot], groups: { move: [{ name: 'github', items: [] }] } }), null);
  assert.equal(moveFor(github, null), null);
});

test('Move leads when nothing is wrong, and Remove waits under More', () => {
  const move = { items: direct.items, gateways: [obot] };
  assert.deepEqual(footerActions([remove], [], move), { lead: 'move', rest: [remove] });
});

test('a problem comes before an option: the duplicate fix leads, Move waits', () => {
  const move = { items: direct.items, gateways: [kitden, obot] };
  assert.deepEqual(footerActions([remove], [duplicate], move), { lead: remove, rest: ['move'] });
  // A warning no button fixes: nothing leads, Move is one plain choice.
  const unfixable = { ...duplicate, fix_action: null };
  assert.deepEqual(footerActions([remove], [unfixable], move), { lead: null, rest: ['move', remove] });
});

test('a duplicate plugin leads with Remove; turning it off waits under More', () => {
  const off = { def: { id: 'p-1', client: 'claude_code' }, action: 'plugin.disable' };
  const removePlugin = { def: { id: 'p-1', client: 'claude_code' }, action: 'plugin.remove' };
  const twice = { level: 'warning', client: 'claude_code', fix_action: 'plugin.remove' };
  assert.deepEqual(footerActions([off, removePlugin], [twice], null), { lead: removePlugin, rest: [off] });
});

test('a plugin removal names the plugin and the client', () => {
  const change = { action: 'plugin.remove', steps: [{ client: 'claude_code', name: 'superpowers@claude-plugins-official' }] };
  assert.equal(changeWords(change).title, 'Remove superpowers from Claude Code');
  assert.equal(changeWords(change).done, 'Removed superpowers from Claude Code');
});

test('a skill removal names the skill and every client that reads its folder', () => {
  const change = { action: 'skill.remove', steps: [{ client: 'codex', name: 'tidy', reaches: ['codex', 'cursor'] }] };
  assert.equal(changeWords(change).title, 'Remove tidy from Codex and Cursor');
  assert.equal(changeWords(change).done, 'Removed tidy from Codex and Cursor');
});

test('a skill removal names only the clients that lose the skill', () => {
  const some = { action: 'skill.remove', steps: [{ client: 'claude_code', name: 'tidy', reaches: ['claude_code', 'cursor'], keeps: ['cursor'] }] };
  assert.equal(changeWords(some).title, 'Remove tidy from Claude Code');
  assert.equal(changeWords(some).done, 'Removed tidy from Claude Code');
  const all = { action: 'skill.remove', steps: [{ client: 'codex', name: 'docker-expert', reaches: ['codex', 'cursor'], keeps: ['codex', 'cursor'] }] };
  assert.equal(changeWords(all).title, 'Remove one copy of docker-expert from Codex and Cursor');
  assert.equal(changeWords(all).done, 'Removed one copy of docker-expert from Codex and Cursor');
});

test('two Remove buttons of one client name their folder', () => {
  const at = (folder) => ({ def: { id: folder, client: 'codex', scope: 'user', source: `/Users/me/${folder}/docker-expert/SKILL.md` }, action: 'skill.remove' });
  const offers = [at('.agents/skills'), at('.codex/skills')];
  assert.equal(offerLabel(offers[0], offers), 'Remove from Codex (.agents/skills)…');
  assert.equal(offerLabel(offers[1], offers), 'Remove from Codex (.codex/skills)…');
  // A home outside /Users still gives a short label.
  const deep = (folder) => ({ def: { id: folder, client: 'codex', scope: 'user', source: `/var/sandbox/home/${folder}/x/SKILL.md` }, action: 'skill.remove' });
  const sandbox = [deep('.agents/skills'), deep('.codex/skills')];
  assert.equal(offerLabel(sandbox[0], sandbox), 'Remove from Codex (.agents/skills)…');
  // Another entry names its file the same way.
  const file = (path) => ({ def: { id: path, client: 'cursor', scope: 'user', source: `/Users/me/${path}` }, action: 'mcp.remove_direct' });
  const files = [file('.cursor/mcp.json'), file('work/.cursor/mcp.json')];
  assert.equal(offerLabel(files[0], files), 'Remove from Cursor (.cursor/mcp.json)…');
  // One button stays plain; twins in different scopes keep the scope words.
  assert.equal(offerLabel(offers[0], offers.slice(0, 1)), 'Remove from Codex…');
  const project = { def: { id: 'p', client: 'codex', scope: 'project', project: '/w/api', source: '/w/api/.agents/skills/x/SKILL.md' }, action: 'skill.remove' };
  assert.equal(offerLabel(project, [offers[0], project]), 'Remove from Codex (project api)…');
});

test('a server to add in the gateway by hand first keeps a lone Remove plain', () => {
  const move = { items: direct.items, gateways: [] };
  assert.deepEqual(footerActions([remove], [], move), { lead: null, rest: [remove] });
});

test('a gateway that could not be read keeps a lone Remove plain', () => {
  // Without the gateway model Move cannot be judged, so Remove must not lead in its place.
  const unread = moveFor(github, null, true);
  assert.deepEqual(unread, { items: [], gateways: [], unread: true });
  assert.deepEqual(footerActions([remove], [], unread), { lead: null, rest: [remove] });
  // Only an MCP server can move; for anything else the gateway does not matter.
  assert.equal(moveFor({ kind: 'plugin', name: 'github' }, null, true), null);
  // An earlier read for this project is still shown, so it still decides.
  assert.deepEqual(moveFor(github, model([obot]), true), { items: direct.items, gateways: [obot] });
});

// The Kitden gateway: moves, tool rules and their review -----------------------------------

const kitdenMove = {
  action: 'gateway.move',
  steps: [
    { client: 'kitden', name: 'files' },
    { client: 'kitden', name: 'PATH' },
    { client: 'kitden', name: 'search' },
    { client: 'claude_code', name: 'files', restart_note: 'Restart Claude Code for this to take effect.' },
    { client: 'cursor', name: 'files' },
    { client: 'cursor', name: 'kitden' },
    { client: 'codex', name: 'kitden' },
  ],
};

test('a move into the Kitden gateway names the servers and that gateway, not its own steps', () => {
  const words = changeWords(kitdenMove);
  assert.equal(words.title, 'Move files into the Kitden gateway');
  assert.equal(words.done, 'Moved files into the Kitden gateway · Restart Claude Code');
  // A registered gateway keeps its words.
  const obotMove = { action: 'gateway.move', steps: [{ client: 'gateway', name: 'docs' }, { client: 'cursor', name: 'docs' }] };
  assert.equal(changeWords(obotMove).title, 'Move docs into the gateway');
  // A server the Kitden gateway holds as it is: the move only removes the client's entry.
  const held = { action: 'gateway.move', steps: [{ client: 'cursor', name: 'files' }] };
  assert.equal(changeWords(held).title, 'Move files into the Kitden gateway');
});

const rule = (params) => ({ action: 'gateway.rule', steps: [{ client: 'kitden', name: params.tool || params.server }] });

test('a tool rule review names the tool, its server and the project', () => {
  data.projects = [{ id: 'p1', path: '/Users/me/work/website' }];
  const off = { action: 'gateway.rule', params: { server: 'echo', tool: 'slow', state: 'off', project: 'p1' } };
  assert.deepEqual(changeWords(rule(off.params), off), { title: 'Turn off slow of echo in website', done: 'Turned off slow of echo in website' });
  const on = { ...off, params: { server: 'echo', tool: null, state: 'on', project: null } };
  assert.deepEqual(changeWords(rule(on.params), on), { title: 'Turn on echo in all projects', done: 'Turned on echo in all projects' });
  const follow = { ...off, params: { ...off.params, state: null } };
  // What it then follows (all projects, or the project around it) is in the review's words.
  assert.deepEqual(changeWords(rule(follow.params), follow), {
    title: 'Remove the own setting for slow of echo in website',
    done: 'slow of echo in website: own setting removed',
  });
  data.projects = null;
});

test('an add into one project names the project', () => {
  data.projects = [{ id: 'p1', path: '/Users/me/work/website' }];
  const change = { action: 'skill.install', steps: [{ client: 'codex', name: 'tidy', reaches: ['codex'] }] };
  assert.deepEqual(changeWords(change, { params: { skill: 'x', project: 'p1' } }), { title: 'Add tidy to Codex in website', done: 'Added tidy to Codex in website' });
  assert.deepEqual(changeWords(change, { params: { skill: 'x' } }), { title: 'Add tidy to Codex', done: 'Added tidy to Codex' });
  const plugin = { action: 'plugin.install', steps: [{ client: 'claude_code', name: 'linter@official' }] };
  assert.equal(changeWords(plugin, { params: { plugin: 'linter@official', project: 'p1' } }).title, 'Add linter@official to Claude Code in website');
  data.projects = null;
});

test('an after entry with only a note draws no client chip', () => {
  const note = 'slow of echo will be off in website. No client uses the Kitden gateway yet.';
  assert.deepEqual(afterParts([{ note }]), { chips: [], notes: [note] });
  const cursor = { client: 'cursor', state: 'off', word: 'Off', note: 'Applies to new sessions.' };
  assert.deepEqual(afterParts([cursor, { client: 'codex', state: 'off', word: 'Off' }]).chips.map((c) => c.client), ['cursor', 'codex']);
  assert.deepEqual(afterParts([cursor]).notes, ['Applies to new sessions.']);
});

test('a held server lists the whole server first, then each tool, for the project picked', () => {
  const answer = {
    server: 'echo', state: 'on', differs: true, follows: 'repo', problem: null,
    tools: [
      { name: 'echo', description: 'Says it back', state: 'on', differs: false, follows: null },
      { name: 'slow', description: '', state: 'off', differs: true, follows: null },
    ],
  };
  const rows = toolRows(answer, 'website');
  // A row that differs names what it follows without its own setting: a project or all projects.
  assert.deepEqual(rows.map((r) => [r.key, r.tool, r.on, r.differs, r.follows]), [
    ['server', null, true, true, 'repo'],
    ['tool:echo', 'echo', true, false, 'all projects'],
    ['tool:slow', 'slow', false, true, 'all projects'],
  ]);
  assert.equal(rows[0].name, 'Whole server');
  assert.equal(rows[1].label, 'Turn off echo of echo in website…');
  assert.equal(rows[2].label, 'Turn on slow of echo in website…');
  assert.equal(rows[0].label, 'Turn off echo in website…');
  // With Global picked the switches are the rules for all projects.
  assert.equal(toolRows(answer, null)[2].label, 'Turn on slow of echo in all projects…');
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

// One Details for every row: every way to add it, or why not -------------------------------

const cell = (fields) => ({ state: 'none', where: null, items: [], word: null, add: null, reason: null, ...fields });
const plain = { action: 'plugin.install', label: '+ Add', plugin: 'figma@openai-curated', skill: null, marketplace: null, warn: null };
const skills = { ...plain, action: 'plugin.skills', label: '+ Add skills', plugin: 'superpowers@cursor-public' };
const labels = (options) => options.map((o) => o.label);
const entry = { kind: 'plugin', id: 'figma@openai-curated' };

test('Details offer each cell action as a button', () => {
  // A Cursor plugin: Add skills to the other two, in column order whatever order the cells come in.
  const twin = { kind: 'plugin', cells: { cursor: cell({ state: 'on' }), codex: cell({ add: skills }), claude_code: cell({ add: skills }) } };
  const options = addOptions(twin, null);
  assert.deepEqual(labels(options), ['Add skills to Claude Code…', 'Add skills to Codex…']);
  assert.deepEqual(options.map((o) => [o.client, o.add]), [['claude_code', skills], ['codex', skills]]);
  // "+ Add" in the Codex column is "Add to Codex…"; a skill's plugin add keeps its words.
  const plugin = { kind: 'plugin', cells: { claude_code: cell({ state: 'on' }), codex: cell({ add: plain }), cursor: cell({ state: 'via' }) } };
  assert.deepEqual(labels(addOptions(plugin, entry)), ['Add to Codex…']);
  const needs = { kind: 'skill', cells: { claude_code: cell({ state: 'on' }), cursor: cell({ add: { ...plain, label: '+ Add the plugin' } }) } };
  assert.deepEqual(labels(addOptions(needs, entry)), ['Add the plugin to Cursor…']);
  // Two clients take it as a plain add: "Add…" too, to add to both in one review. It needs the
  // marketplace's entry, so without one it is left out.
  const two = { kind: 'plugin', cells: { claude_code: cell({ add: plain }), codex: cell({ add: plain }), cursor: cell({ reason: 'No.' }) } };
  assert.deepEqual(labels(addOptions(two, entry)), ['Add to Claude Code…', 'Add to Codex…', 'Add…']);
  assert.equal(addOptions(two, entry)[2].form, true);
  assert.deepEqual(labels(addOptions(two, null)), ['Add to Claude Code…', 'Add to Codex…']);
  // The real install comes first, then Add the plugin, then Add skills; each in column order.
  // Add skills and Add the plugin are not plain adds of the item, so they never make "Add…".
  const mixed = { kind: 'plugin', cells: { claude_code: cell({ add: skills }), codex: cell({ add: plain }), cursor: cell({ add: skills }) } };
  const ordered = addOptions(mixed, entry);
  assert.deepEqual(labels(ordered), ['Add to Codex…', 'Add skills to Claude Code…', 'Add skills to Cursor…']);
  assert.equal(footerActions([], [], null, ordered).lead.label, 'Add to Codex…');
  const copy = { ...plain, action: 'skill.install', plugin: null, skill: 'tidy@skills' };
  const skill = { kind: 'skill', cells: { claude_code: cell({ add: copy }), codex: cell({ add: { ...plain, label: '+ Add the plugin' } }), cursor: cell({ add: copy }) } };
  assert.deepEqual(labels(addOptions(skill, { kind: 'skill' })), ['Add to Claude Code…', 'Add to Cursor…', 'Add the plugin to Codex…', 'Add…']);

  // With no lead yet, the first add is the primary button and the rest wait under More.
  const [first, second] = options;
  assert.deepEqual(footerActions([], [], null, [first, second]), { lead: first, rest: [second] });
  // Today's lead stays first: a lone switch leads and the adds wait.
  const off = { def: { id: 'p-1', client: 'claude_code' }, action: 'plugin.disable' };
  assert.deepEqual(footerActions([off], [], null, [first]), { lead: off, rest: [first] });
  // A warning no button fixes: nothing leads, so no add looks like the fix.
  const twice = { level: 'warning', client: 'cursor', fix_action: null, via: 'claude_code' };
  assert.deepEqual(footerActions([], [twice], null, [first, second]), { lead: null, rest: [first, second] });
});

test('Details with nothing to do say why first', () => {
  const cant = (client) => `${client} can't install this plugin, and it has no skills to copy.`;
  const row = { kind: 'plugin', cells: { cursor: cell({ reason: cant('Cursor') }), codex: cell({ state: 'unk' }), claude_code: cell({ reason: cant('Claude Code') }) } };
  // No button at all: nothing leads and nothing waits.
  assert.deepEqual(footerActions([], [], null, addOptions(row, null)), { lead: null, rest: [] });
  // Clients with the same reason make one sentence, in column order.
  assert.equal(whyNoAction(row, []), "Claude Code and Cursor can't install this plugin, and it has no skills to copy.");
  const elsewhere = (client) => `${client} has it in another project.`;
  const three = { cells: { claude_code: cell({ reason: elsewhere('Claude Code') }), codex: cell({ reason: elsewhere('Codex') }), cursor: cell({ reason: elsewhere('Cursor') }) } };
  assert.equal(whyNoAction(three), 'Claude Code, Codex and Cursor have it in another project.');
  const mixed = { cells: { claude_code: cell({ reason: cant('Claude Code') }), codex: cell({ reason: elsewhere('Codex') }), cursor: cell({ reason: cant('Cursor') }) } };
  assert.equal(whyNoAction(mixed), `Claude Code and Cursor can't install this plugin, and it has no skills to copy. ${elsewhere('Codex')}`);
  const needs = (client) => `${client} can't install the plugin this skill needs.`;
  assert.equal(whyNoAction({ cells: { codex: cell({ reason: needs('Codex') }), cursor: cell({ reason: needs('Cursor') }) } }), "Codex and Cursor can't install the plugin this skill needs.");
  const outside = "This skill uses files outside its folder, so it can't be copied.";
  assert.equal(whyNoAction({ cells: { claude_code: cell({ reason: outside }), codex: cell({ reason: outside }) } }), outside);
  // No reasons: where to change it, from the item's own settings.
  const hint = 'On/off is stored in your ChatGPT account. Change it in Codex: Plugins.';
  const remote = { cells: { codex: cell({ state: 'unk' }) } };
  assert.equal(whyNoAction(remote, [{ change_hint: null }, { change_hint: hint }]), hint);
  // Nothing known (an MCP server row from the scan has no reasons): no line.
  assert.equal(whyNoAction({ cells: { codex: { state: 'on', where: 'all projects', items: [] } } }, []), '');
});

test('the Details lede says where it loads, and where it may', () => {
  const columns = [{ id: 'claude_code', name: 'Claude Code' }, { id: 'codex', name: 'Codex' }, { id: 'cursor', name: 'Cursor' }];
  const lede = (states) => loadsLede({ cells: Object.fromEntries(Object.entries(states).map(([c, state]) => [c, cell({ state })])) }, columns);
  assert.equal(lede({ claude_code: 'on', codex: 'gw', cursor: 'none' }), 'Available in Claude Code and Codex.');
  // The page cannot tell whether it is on: it may load there.
  assert.equal(lede({ codex: 'unk' }), 'Unknown in Codex.');
  assert.equal(lede({ claude_code: 'on', codex: 'unk' }), 'Available in Claude Code. Unknown in Codex.');
  assert.equal(lede({ claude_code: 'off', cursor: 'via' }), 'Not available here.');
});

test('Details names the scope with the same phrases as the cells', () => {
  assert.equal(scopeWords({ scope: 'user' }, ''), 'All projects');
  assert.equal(scopeWords({ scope: 'project', project: '/w/website' }, '/w/website'), 'This project');
  assert.equal(scopeWords({ scope: 'project', project: '/w/api' }, '/w/website'), 'Project api');
  assert.equal(scopeWords({ scope: 'user', client: 'cursor', owner_client: 'claude_code' }, ''), "All projects · through Claude Code's folder");
});

test('a new tool in strict mode is flagged', () => {
  const rows = toolRows({ server: 'github', state: 'on', strict: true, tools: [{ name: 'create_issue', description: '', state: 'off', new: true }, { name: 'list_issues', description: '', state: 'on', new: false }] }, null);
  assert.equal(rows[1].flag, 'New');
  assert.equal(rows[2].flag, null);
  assert.equal(rows[0].flag, null);
});

test('tool rows carry the hint and where it comes from', () => {
  const rows = toolRows({ server: 'github', state: 'on', strict: false, tools: [{ name: 'read_file', description: '', state: 'on', hint: 'reads', hint_from: 'server', new: false }] }, null);
  assert.equal(rows[1].hint, 'reads'); assert.equal(rows[1].hintFrom, 'server');
  assert.equal(rows[0].hint, null);
});

test('the batch switch takes the writing tools that are on', () => {
  const tools = [{ name: 'a', state: 'on', hint: 'writes' }, { name: 'b', state: 'off', hint: 'writes' }, { name: 'c', state: 'on', hint: 'may write' }, { name: 'd', state: 'on', hint: 'reads' }];
  assert.deepEqual(writingToolsOn(tools), ['a', 'c']);
  assert.deepEqual(writingToolsOn([]), []);
});

test('the batch review counts the tools and names the project', () => {
  data.projects = [{ id: 'p1', path: '/Users/me/work/website' }];
  const body = { action: 'gateway.rules', params: { server: 'github', tools: ['a', 'c'], state: 'off', project: 'p1' } };
  const change = { action: 'gateway.rules', steps: [{ client: 'kitden', name: 'a' }, { client: 'kitden', name: 'c' }] };
  assert.deepEqual(changeWords(change, body), { title: 'Turn off 2 tools of github in website', done: 'Turned off 2 tools of github in website' });
  const one = { ...body, params: { ...body.params, tools: ['a'], project: null } };
  assert.deepEqual(changeWords(change, one), { title: 'Turn off 1 tool of github in all projects', done: 'Turned off 1 tool of github in all projects' });
  data.projects = null;
});

test('calls text says how many and when', () => {
  process.env.TZ = 'UTC'; // the times are shown in local time
  const now = new Date('2026-10-21T15:00:00Z');
  assert.equal(callsText({ count: 12, last: '2026-10-21T14:02Z' }, now), 'Called 12 times, last today 14:02');
  assert.equal(callsText({ count: 1, last: '2026-10-20T09:15Z' }, now), 'Called once, last 20 Oct 09:15');
  assert.equal(callsText(null, now), null);
});

test('a held server offers Remove and Put back in each found client', () => {
  const actions = heldActions('files', ['claude_code', 'cursor']);
  assert.deepEqual(actions.map((a) => a.label), ['Remove from the Kitden gateway…', 'Put back in Claude Code…', 'Put back in Cursor…']);
  assert.deepEqual(actions[0].body, { action: 'gateway.remove', targets: [], params: { server: 'files' } });
  assert.deepEqual(actions[2].body, { action: 'gateway.put_back', targets: [{ client: 'cursor' }], params: { server: 'files' } });
});

test('a held server with plain secrets also offers to move them to the Keychain', () => {
  const actions = heldActions('files', ['codex'], true);
  assert.deepEqual(actions.map((a) => a.label), ['Remove from the Kitden gateway…', 'Put back in Codex…', 'Move secrets to the Keychain…']);
  assert.deepEqual(actions[2].body, { action: 'gateway.keychain', targets: [], params: { server: 'files' } });
  const model = { gateways: [{ kind: 'kitden', servers: [{ name: 'files', plain_secrets: true }, { name: 'docs', plain_secrets: false }] }] };
  assert.equal(plainSecrets(model, 'files'), true);
  assert.equal(plainSecrets(model, 'docs'), false);
  assert.equal(plainSecrets(model, 'nope'), false);
  assert.equal(plainSecrets(null, 'files'), false);
});

test('moving the secrets of a held server is named', () => {
  const change = { action: 'gateway.keychain', steps: [{ client: 'kitden', name: 'files' }] };
  assert.deepEqual(changeWords(change, { params: { server: 'files' } }), { title: 'Move the secrets of files to the Keychain', done: 'Moved the secrets of files to the Keychain' });
});

test('removing from or putting back from the Kitden gateway is named', () => {
  const remove = { action: 'gateway.remove', steps: [{ client: 'kitden', name: 'files' }, { client: 'kitden', name: 'files' }] };
  assert.deepEqual(changeWords(remove, { params: { server: 'files' } }), { title: 'Remove files from the Kitden gateway', done: 'Removed files from the Kitden gateway' });
  assert.equal(changeWords(remove).title, 'Remove files from the Kitden gateway');
  const back = { action: 'gateway.put_back', steps: [{ client: 'claude_code', name: 'files', restart_note: 'Start a new Claude Code session (or a new Code tab chat) for this to take effect.' }] };
  assert.deepEqual(changeWords(back, { params: { server: 'files' } }), { title: 'Put files back in Claude Code', done: 'Put files back in Claude Code · Start a new Claude Code session (or a new Code tab chat)' });
});

test('a server added to another client is named', () => {
  assert.deepEqual(changeWords({ action: 'mcp.add', steps: [{ client: 'codex', name: 'github' }] }), { title: 'Add github to Codex', done: 'Added github to Codex' });
});

test('the align review groups what each client lacks and keeps the choice', () => {
  const align = { candidates: [
    { key: 'mcp_server:github:codex', kind: 'mcp_server', name: 'github', from: 'claude_code', to: 'codex', place: 'all', chosen: true },
    { key: 'skill:brandkit:cursor', kind: 'skill', name: 'brandkit', from: 'claude_code', to: 'cursor', place: 'project', chosen: false, note: 'Cursor already has Brandkit; this adds brandkit beside it.' },
  ], not_same: [], left_out: [] };
  assert.deepEqual(alignGroups(align), [
    { client: 'codex', name: 'Codex', items: [{ key: 'mcp_server:github:codex', label: 'github · MCP server · from Claude Code · all projects', note: null, chosen: true }] },
    { client: 'cursor', name: 'Cursor', items: [{ key: 'skill:brandkit:cursor', label: 'brandkit · Skill · from Claude Code · this project', note: 'Cursor already has Brandkit; this adds brandkit beside it.', chosen: false }] },
  ]);
  assert.deepEqual(chosenKeys(align, 'skill:brandkit:cursor', true), ['mcp_server:github:codex', 'skill:brandkit:cursor']);
  assert.deepEqual(chosenKeys(align, 'mcp_server:github:codex', false), []);
  data.projects = [{ id: 'p1', path: '/Users/me/work/website' }];
  assert.deepEqual(changeWords({ action: 'project.align', steps: [{ client: 'codex', name: 'github' }], align }, { params: { project: 'p1' } }), { title: 'Add what website is missing', done: 'Added 1 item for website' });
  data.projects = null;
});

test('an instruction file never says Loads', () => {
  const columns = [{ id: 'codex', name: 'Codex' }, { id: 'cursor', name: 'Cursor' }];
  const row = { kind: 'instructions', category: 'instructions', cells: { codex: { state: 'on' }, cursor: { state: 'on' } } };
  assert.equal(loadsLede(row, columns), 'Available in Codex and Cursor.');
  assert.equal(loadsLede({ ...row, cells: { codex: { state: 'on' }, cursor: { state: 'none' } } }, columns), 'Available in Codex.');
  assert.equal(kindWord(row), 'Instruction file');
  assert.equal(kindWord({ kind: 'instructions', category: 'agent' }), 'Agent');
  assert.equal(kindWord({ kind: 'skill' }), 'Skill');
});

test('an instruction file layer never says Loads or Not loaded', () => {
  const def = { kind: 'instructions', enabled: 'on', why: 'Read when a session starts.' };
  assert.equal(layerState({ ...def, loads: true }).badge, 'Available');
  assert.equal(layerState({ ...def, loads: false, project: '/h/work/site' }).badge, 'In a project');
  assert.equal(layerState({ ...def, loads: false, project: null }).badge, '');
  assert.equal(layerState({ kind: 'skill', enabled: 'on', loads: false, why: 'x' }).badge, 'Not loaded');
  // The badge says Available; the why never says Loads again under it.
  const loaded = { kind: 'mcp_server', enabled: 'on', loads: true };
  assert.equal(layerState({ ...loaded, why: 'Loads.' }).why, '');
  assert.equal(layerState({ ...loaded, why: 'Loads. It overrides the user definition.' }).why, 'It overrides the user definition.');
});

test('Details shows the tool count once, from a definition in the Kitden gateway', () => {
  const direct = { client: 'codex', via_gateway: null, tools: null };
  const held = { client: 'cursor', via_gateway: 'kitden', tools: 3 };
  assert.equal(countedDefinition([direct, held, { ...held, client: 'claude_code' }]), held);
  assert.equal(countedDefinition([direct]), null);
  assert.equal(countedDefinition([{ ...held, tools: null }]), null);
});

test('an Add missing list with nothing chosen shows as a review, not an error', () => {
  assert.equal(canShowReview({ ok: true, data: { id: 'c1', steps: [] } }), true);
  assert.equal(canShowReview({ ok: true, data: { action: 'project.align', steps: [], after: [], align: { candidates: [] } } }), true);
  assert.equal(canShowReview({ ok: true, data: { steps: [] } }), false);
  assert.equal(canShowReview({ ok: false, data: { detail: 'Unknown project.' } }), false);
  assert.equal(canShowReview(null), false);
});

// Just enough of a page for the panel to open and close: the drawer and its scrim.
function fakePanelPage() {
  const node = () => {
    const classes = new Set();
    return {
      classList: {
        add: (name) => classes.add(name),
        remove: (name) => classes.delete(name),
        toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)),
        contains: (name) => classes.has(name),
      },
      replaceChildren() {}, focus() {}, contains: () => false,
    };
  };
  const nodes = { '#drawer': node(), '#scrim': node() };
  globalThis.document = {
    activeElement: null,
    documentElement: { classList: { remove() {} } },
    querySelector: (selector) => nodes[selector] ?? null,
    querySelectorAll: () => [],
  };
}

test('picking another project closes the panel, so a switch never acts on a project it does not name', () => {
  fakePanelPage();
  try {
    state.project = 'atlas';
    openPanel([]);
    closeForProject();
    assert.equal(isPanelOpen(), true); // the same project keeps it open
    state.project = 'web';
    closeForProject();
    assert.equal(isPanelOpen(), false);
    openPanel([]); // opened again, it belongs to the project now picked
    closeForProject();
    assert.equal(isPanelOpen(), true);
  } finally {
    state.project = '';
    delete globalThis.document;
  }
});

test('Details drawn again after an Apply belongs to the project picked during it', () => {
  fakePanelPage();
  try {
    state.project = 'atlas';
    openPanel([]);
    busy.change = true; // the change is being written: the panel stays
    state.project = 'web';
    closeForProject();
    assert.equal(isPanelOpen(), true);
    openPanel([]); // verified: Details is drawn again, for web
    busy.change = false;
    state.project = 'atlas'; // Back
    closeForProject();
    assert.equal(isPanelOpen(), false);
  } finally {
    busy.change = false;
    state.project = '';
    delete globalThis.document;
  }
});
