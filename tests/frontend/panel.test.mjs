import assert from 'node:assert/strict';
import { test } from 'node:test';

// panel.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
// Node before 21 has no navigator; panel.js must load there too.
delete globalThis.navigator;
const { FLOAT_MIN, addScope, afterParts, alignGroups, canShowReview, closeForProject, closePanel, countedDefinition, changeOutcome, chosenKeys, callsText, changeWords, floatTop, floatsAt, footerActions, heldActions, initPanel, isPanelOpen, loadPanel, offerLabel, openItem, layerState, leftOutText, kindWord, loadsLede, moveFor, moveTargets, openPanel, panelState, plainSecrets, projectLabel, review, reviewLede, scopeWords, stepTo, swapContent, toolRows, writingToolsOn } = await import('../../src/kitden/web/static/js/panel.js');
const { CALM, reducedMotion } = await import('../../src/kitden/web/static/js/motion.js');
const { readFileSync } = await import('node:fs');
const { detailsCard, factsBlock } = await import('../../src/kitden/web/static/js/details.js');
const { addOptions, whyNoAction } = await import('../../src/kitden/web/static/js/offer.js');
const { data, state } = await import('../../src/kitden/web/static/js/store.js');
const { addToTray, cancelTray, tray } = await import('../../src/kitden/web/static/js/tray.js');

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
  assert.deepEqual(changeWords(change, { params: { skill: 'x' } }), { title: 'Add tidy to Codex for all projects', done: 'Added tidy to Codex for all projects' });
  const plugin = { action: 'plugin.install', steps: [{ client: 'claude_code', name: 'linter@official' }] };
  assert.equal(changeWords(plugin, { params: { plugin: 'linter@official', project: 'p1' } }).title, 'Add linter@official to Claude Code in website');
  data.projects = null;
});

test('an add names its scope in the title and, with All projects, in the lede', () => {
  const add = { action: 'skill.install', steps: [{ client: 'codex', name: 'tidy' }] };
  assert.deepEqual(changeWords(add, { params: { skill: 'x' } }), { title: 'Add tidy to Codex for all projects', done: 'Added tidy to Codex for all projects' });
  assert.equal(changeWords({ action: 'mcp.add', steps: [{ client: 'codex', name: 'github' }] }).title, 'Add github to Codex for all projects');
  assert.equal(reviewLede({ action: 'mcp.add' }, ''), 'Adds for all projects. Nothing is written until you press Apply. A backup is kept.');
  assert.equal(reviewLede({ action: 'mcp.add' }, 'p1'), 'Nothing is written until you press Apply. A backup is kept.');
  assert.equal(reviewLede({ action: 'plugin.disable' }, ''), 'Nothing is written until you press Apply. A backup is kept.');
  // Only an add names a scope; a removal or a switch says its place another way.
  assert.equal(addScope('plugin.disable', ''), null);
  assert.equal(addScope('plugin.skills', ''), ' for all projects');
  // A marketplace and the setup entry are adds too, and always for all projects.
  const market = { action: 'marketplace.add', steps: [{ client: 'codex', name: 'acme' }] };
  assert.deepEqual(changeWords(market), { title: 'Add the acme marketplace to Codex for all projects', done: 'Added the marketplace acme to Codex for all projects' });
  const setup = { action: 'setup_server.register', steps: [{ client: 'cursor', name: 'kitden' }] };
  assert.deepEqual(changeWords(setup), { title: 'Connect Cursor to Kitden', done: 'Connected Cursor to Kitden' });
  assert.equal(reviewLede({ action: 'marketplace.add' }, ''), 'Adds for all projects. Nothing is written until you press Apply. A backup is kept.');
  assert.equal(reviewLede({ action: 'setup_server.register' }, ''), 'Nothing is written until you press Apply. A backup is kept.');
  // Connecting a gateway and putting a server back write each client's own entry: for all
  // projects. The page and the server agree on the adds (test_api_changes.py).
  const connect = { action: 'gateway.connect', steps: [{ client: 'codex', name: 'gateway' }] };
  assert.equal(changeWords(connect, { params: { gateway: 'g1', name: 'gateway' } }).title, 'Connect the gateway to Codex for all projects');
  assert.equal(reviewLede({ action: 'gateway.put_back' }, ''), 'Adds for all projects. Nothing is written until you press Apply. A backup is kept.');
  // Add missing names its project in the title; an update changes an entry where it is.
  const align = { action: 'project.align', steps: [{ client: 'codex', name: 'tidy' }], align: { candidates: [] } };
  assert.ok(changeWords(align, { params: { project: '/w/site' } }).title.endsWith(' is missing'));
  assert.equal(addScope('project.align', '/w/site'), null);
  assert.equal(addScope('setup_server.update', ''), null);
  assert.equal(reviewLede({ action: 'setup_server.update' }, ''), 'Nothing is written until you press Apply. A backup is kept.');
  // The kitden entry turned on again: its title names the client, with no place.
  const enable = { action: 'setup_server.enable', steps: [{ client: 'codex', name: 'kitden' }], target: { scope: 'all' } };
  assert.deepEqual(changeWords(enable), { title: 'Turn on the kitden entry in Codex', done: 'Turned on the kitden entry in Codex' });
});

test('an add into a known project on another disk names that project', () => {
  data.projects = [{ id: 'p9', path: '/Volumes/Other/site' }];
  const add = { action: 'skill.install', steps: [{ client: 'codex', name: 'tidy' }] };
  assert.equal(changeWords(add, { params: { skill: 'x', project: 'p9' } }).title, 'Add tidy to Codex in site');
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
  assert.equal(words.title, "Add toolbox's skills to Claude Code and Cursor for all projects");
  assert.equal(words.done, 'Added 2 skills to Claude Code and Cursor for all projects');
  assert.equal(changeWords({ ...added, steps: [added.steps[0]] }).done, 'Added 1 skill to Claude Code and Cursor for all projects');
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
  assert.equal(whyNoAction({ cells: { codex: { state: 'on', where: null, items: [] } } }, []), '');
});

test('the Details lede says where it loads, and where it may', () => {
  const columns = [{ id: 'claude_code', name: 'Claude Code' }, { id: 'codex', name: 'Codex' }, { id: 'cursor', name: 'Cursor' }];
  const lede = (states) => loadsLede({ cells: Object.fromEntries(Object.entries(states).map(([c, state]) => [c, cell({ state })])) }, columns);
  assert.equal(lede({ claude_code: 'on', codex: 'gw', cursor: 'none' }), 'On in Claude Code and Codex.');
  // The page cannot tell whether it is on: it may load there.
  assert.equal(lede({ codex: 'unk' }), 'Unknown in Codex.');
  assert.equal(lede({ claude_code: 'on', codex: 'unk' }), 'On in Claude Code. Unknown in Codex.');
  assert.equal(lede({ claude_code: 'off', cursor: 'via' }), 'Not on here.');
  assert.equal(lede({ claude_code: 'on', codex: 'review' }), 'On in Claude Code. Needs review in Codex: same name, another source.');
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
  assert.equal(callsText({ count: 12, last: '2026-10-21T14:02Z' }, now), '12 calls · last today 14:02');
  assert.equal(callsText({ count: 1, last: '2026-10-20T09:15Z' }, now), '1 call · last 20 Oct 09:15');
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
  assert.deepEqual(changeWords(back, { params: { server: 'files' } }), { title: 'Put files back in Claude Code for all projects', done: 'Put files back in Claude Code for all projects · Start a new Claude Code session (or a new Code tab chat)' });
});

test('a server added to another client is named', () => {
  assert.deepEqual(changeWords({ action: 'mcp.add', steps: [{ client: 'codex', name: 'github' }] }), { title: 'Add github to Codex for all projects', done: 'Added github to Codex for all projects' });
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
  assert.equal(loadsLede(row, columns), 'On in Codex and Cursor.');
  assert.equal(loadsLede({ ...row, cells: { codex: { state: 'on' }, cursor: { state: 'none' } } }, columns), 'On in Codex.');
  assert.equal(kindWord(row), 'Instruction file');
  assert.equal(kindWord({ kind: 'instructions', category: 'agent' }), 'Agent');
  assert.equal(kindWord({ kind: 'skill' }), 'Skill');
});

test('an instruction file layer never says Loads or Not loaded', () => {
  const def = { kind: 'instructions', enabled: 'on', why: 'Read when a session starts.' };
  assert.equal(layerState({ ...def, loads: true }).badge, 'On');
  assert.equal(layerState({ ...def, loads: false, project: '/h/work/site' }).badge, 'In a project');
  assert.equal(layerState({ ...def, loads: false, project: null }).badge, '');
  assert.equal(layerState({ kind: 'skill', enabled: 'on', loads: false, why: 'x' }).badge, 'Not loaded');
  // The badge says On; the why never says Loads again under it, and the Why lines at
  // the top say which definition overrides which.
  const loaded = { kind: 'mcp_server', enabled: 'on', loads: true };
  assert.equal(layerState({ ...loaded, why: 'Loads.' }).why, '');
  assert.equal(layerState({ ...loaded, why: 'Loads. It overrides the user definition.' }).why, '');
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

// Just enough of a page for the panel to open and close: the drawer, its scrim and the shell, the
// top bar (it ends at 83 px) and the page: its head, and its stage at `stage` px from the top of
// the window. A node keeps its parts, classes, attributes, style and listeners; each motion started
// on one is kept in `motions` ({ node, keyframes, options }).
const motions = [];
function fakeNode(tag = 'div', rect = { top: 0, bottom: 0 }) {
  const classes = new Set();
  const node = {
    tag, rect, attributes: {}, listeners: {}, dataset: {}, children: [], textContent: '',
    style: { setProperty: (name, value) => { node.style[name] = value; } },
    get className() { return [...classes].join(' '); },
    set className(value) { classes.clear(); String(value).split(/\s+/).filter(Boolean).forEach((name) => classes.add(name)); },
    classList: {
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)),
      contains: (name) => classes.has(name),
    },
    setAttribute: (name, value) => { node.attributes[name] = String(value); },
    removeAttribute: (name) => { delete node.attributes[name]; },
    append: (...nodes) => { node.children.push(...nodes); },
    replaceChildren: (...nodes) => { node.children = nodes; },
    addEventListener: (type, fn) => { node.listeners[type] = fn; },
    matches: (selector) => selector.split(',').map((s) => s.trim()).some((s) => s === tag || (s.startsWith('.') && classes.has(s.slice(1)))),
    getBoundingClientRect: () => node.rect,
    animate: (keyframes, options) => { motions.push({ node, keyframes, options }); return { finished: Promise.resolve() }; },
    getAnimations: () => [],
    focus() {}, contains: () => false, querySelectorAll: () => [],
  };
  return node;
}

function fakePanelPage({ stage = 215 } = {}) {
  motions.length = 0;
  globalThis.addEventListener = () => {}; // the window's resize
  const main = fakeNode('main');
  const lede = fakeNode('p', { top: 148, bottom: 165 });
  lede.className = 'lede';
  const map = fakeNode('div', { top: stage, bottom: stage + 600 });
  map.className = 'map';
  main.children = [fakeNode('h1', { top: 109, bottom: 144 }), lede, map];
  const nodes = {
    '#drawer': fakeNode('aside'), '#scrim': fakeNode(), '#main': main, '.shell': fakeNode(),
    '#topbar': fakeNode('div', { top: 17, bottom: 83 }), '#content': fakeNode(),
  };
  globalThis.document = {
    activeElement: null,
    documentElement: { classList: { remove() {} } },
    createElement: (tag) => fakeNode(tag),
    querySelector: (selector) => nodes[selector] ?? null,
    querySelectorAll: () => [],
    addEventListener() {},
  };
  return { ...nodes, drawer: nodes['#drawer'], scrim: nodes['#scrim'], map };
}

// A stand-in server for the tray: every request is kept as { url, body }; a batch preview answers
// with one step and one row per request.
function trayServer(sent) {
  return async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : null;
    sent.push({ url, body });
    if (url !== '/api/batch/preview') return Response.json({});
    const { requests } = body;
    return Response.json({
      id: `c${sent.length}`, action: 'batch', state: 'previewed', error: null, undo_note: null,
      steps: requests.map(() => ({ client: 'codex', name: 'x' })),
      rows: requests.map((r, at) => ({ id: r.id, kind: r.kind, title: r.title, detail: '', project: null, steps: [at], after: [] })),
    });
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

test('a project switch closes the panel and leaves the selection to the address', () => {
  fakePanelPage();
  const github = { kind: 'mcp_server', name: 'github' };
  try {
    state.project = 'atlas';
    state.selected = github;
    openPanel([]);
    state.project = 'web'; // Back to an address of another project, with its own selection
    closeForProject();
    assert.equal(isPanelOpen(), false);
    assert.deepEqual(state.selected, github);
    openPanel([]);
    closePanel({ focus: false }); // closed by the person: nothing is selected
    assert.equal(state.selected, null);
  } finally {
    state.project = '';
    state.selected = null;
    delete globalThis.document;
  }
});

test('Details opened on arrival gives focus back to the selected row, not to the page', () => {
  fakePanelPage();
  const focused = [];
  const row = { dataset: { key: 'row-github' }, setAttribute() {}, focus: () => focused.push('row') };
  const body = { isConnected: true, closest: () => null, focus: () => focused.push('body') };
  const find = document.querySelector;
  Object.assign(document, {
    body,
    activeElement: body, // the button that led here is gone with the old page
    querySelector: (selector) => (selector === 'tr[aria-selected="true"]' ? row : find(selector)),
    querySelectorAll: (selector) => (selector === 'tr[data-key]' ? [row] : []),
  });
  try {
    openPanel([]);
    closePanel();
    assert.deepEqual(focused, ['row']);
  } finally {
    state.selected = null;
    delete globalThis.document;
  }
});


test('a change names the project picked at the top, so the server can tell what it overrides', async () => {
  const sent = [];
  globalThis.fetch = trayServer(sent);
  try {
    state.project = 'p1';
    await review({ action: 'plugin.disable', targets: [{ item: 'i1' }], params: {} }, { back: async () => {} });
    state.project = '';
    await review({ action: 'plugin.disable', targets: [{ item: 'i2' }], params: {} }, { back: async () => {} });
    const asked = sent.filter((call) => call.url === '/api/batch/preview').map((call) => call.body.requests.map((r) => [r.targets[0].item, r.picked]));
    assert.deepEqual(asked, [[['i1', 'p1']], [['i1', 'p1'], ['i2', null]]]);
  } finally {
    state.project = '';
    await cancelTray();
    delete globalThis.fetch;
  }
});

// A stand-in element: enough for a panel's header, body and footer.
function element(tag) {
  const node = {
    tag, className: '', textContent: '', children: [], attributes: {}, dataset: {},
    append(...nodes) { node.children.push(...nodes); },
    prepend(...nodes) { node.children.unshift(...nodes); },
    setAttribute(name, value) { node.attributes[name] = value; },
    addEventListener() {},
  };
  return node;
}

test("a refusal of Add missing's list goes back only to the Details it was asked from", async () => {
  fakePanelPage();
  document.createElement = element;
  let answer;
  globalThis.fetch = () => new Promise((resolve) => { answer = resolve; });
  const drawn = [];
  try {
    panelState.from = { draw: () => drawn.push('asked from'), focus: null };
    const pending = review({ action: 'project.align', targets: [], params: { project: 'p1', chosen: null } });
    // The person opened another item's Details while the preview was prepared.
    panelState.from = { draw: () => drawn.push('another'), focus: null };
    answer({ ok: false, status: 422, json: async () => ({ detail: 'No.' }) });
    await pending;
    assert.deepEqual(drawn, []);
    assert.equal(panelState.current.type, 'error');
  } finally {
    panelState.current = null;
    panelState.from = null;
    delete globalThis.document;
    delete globalThis.fetch;
  }
});

test('a project at / is named /', () => {
  data.projects = [{ id: 'root', path: '/' }, { id: 'p1', path: '/Users/me/work/website' }];
  assert.equal(projectLabel('root'), '/');
  assert.equal(projectLabel('p1'), 'website');
  data.projects = null;
});

test('a definition kept from the last good read says when, on this Mac clock', () => {
  const at = new Date(2026, 9, 22, 14, 2).toISOString();
  const def = { kind: 'mcp_server', enabled: 'on', loads: true, why: '', stale_at: at };
  assert.equal(layerState(def).stale, 'From the last good read at 14:02');
  assert.equal(layerState({ ...def, stale_at: null }).stale, null);
});

// Details beside the page -----------------------------------------------------------------

test('Details float beside the page from 1024 px on Gateway, Library and Changes', () => {
  assert.equal(floatsAt('gateway', 1024), true);
  assert.equal(floatsAt('library', 1023), false);
  assert.equal(floatsAt('changes', 1440), true);
  assert.equal(floatsAt('overview', 1440), false);
  assert.equal(FLOAT_MIN, 1024);
});

// The window is at least 1024 px wide (`wide`), or narrower.
const windowIs = (wide) => { globalThis.matchMedia = () => ({ matches: wide, addEventListener() {} }); };

// Restore what a test of the floating panel changed.
function leaveFloatTest() {
  windowIs(false);
  reducedMotion.matches = false;
  state.view = 'overview';
  delete globalThis.document;
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
// The motions started on `nodes`, as [keyframes, duration, delay, easing].
const motionsOf = (...nodes) => motions.filter((m) => nodes.includes(m.node)).map((m) => [m.keyframes, m.options.duration, m.options.delay, m.options.easing]);
const parts = (count) => Array.from({ length: count }, () => fakeNode('section'));

test('wide, Details float and the page keeps its width', () => {
  const page = fakePanelPage();
  const { drawer, scrim } = page;
  const shell = page['.shell'];
  try {
    state.view = 'gateway';
    windowIs(true);
    initPanel();
    openPanel([]);
    assert.equal(drawer.classList.contains('floating'), true);
    assert.equal(scrim.classList.contains('open'), false);
    // A region beside the map, not a dialog: the page stays usable.
    assert.equal(drawer.attributes.role, 'complementary');
    assert.equal(drawer.attributes['aria-modal'], undefined);
    // Nothing makes room for it: the page keeps its width.
    assert.equal(shell.className, '');
    // Its top is level with the map under the page head.
    assert.equal(drawer.style['--float-top'], '215px');
    // It comes in from 28 px to the right, a little smaller, in 240 ms.
    assert.deepEqual(motionsOf(drawer), [[[{ opacity: 0, transform: 'translateX(28px) scale(.98)' }, { opacity: 1, transform: 'none' }], 240, 0, CALM]]);
    // The page scrolls the map up: the panel stays in view, under the top bar.
    page.map.rect = { top: -185, bottom: 415 };
    page['#content'].listeners.scroll();
    assert.equal(drawer.style['--float-top'], '105px');
    assert.equal(floatTop(215, 83), 215);
    assert.equal(floatTop(-185, 83), 105);
    // It goes 22 px to the right in 180 ms ease-in, seen until then; the page never moved.
    motions.length = 0;
    closePanel({ focus: false });
    assert.equal(isPanelOpen(), false);
    assert.equal(drawer.classList.contains('leaving'), true);
    assert.deepEqual(motionsOf(drawer), [[[{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateX(22px)' }], 180, 0, 'ease-in']]);
    assert.equal(shell.className, '');
    // Overview keeps the drawer in a wide window; a caller can ask to float.
    state.view = 'overview';
    openPanel([]);
    assert.equal(drawer.classList.contains('floating'), false);
    closePanel({ focus: false, instant: true });
    openPanel([], { float: true });
    assert.equal(drawer.classList.contains('floating'), true);
    closePanel({ focus: false, instant: true });
  } finally {
    leaveFloatTest();
  }
});

test('under 1024 px Details are the modal drawer, with the dock above it', () => {
  const { drawer, scrim } = fakePanelPage();
  try {
    state.view = 'gateway';
    windowIs(false);
    openPanel([]);
    assert.equal(drawer.classList.contains('floating'), false);
    assert.equal(scrim.classList.contains('open'), true);
    assert.equal(drawer.attributes.role, 'dialog');
    assert.equal(drawer.attributes['aria-modal'], 'true');
    // It slides in by its own CSS: no floating motion and no top of its own.
    assert.deepEqual(motionsOf(drawer), []);
    assert.equal(drawer.style['--float-top'], undefined);
    closePanel({ focus: false });
    assert.equal(drawer.classList.contains('leaving'), false);
  } finally {
    leaveFloatTest();
  }
  // The dock (the tray's bar, a toast) stands above the scrim and the drawer. The drawer ends 16 px
  // above the window with an empty dock, and 8 px above what the dock shows (its height and 46 px,
  // measured from the frame's content, which ends 17 px inside the window).
  const css = readFileSync(new URL('../../src/kitden/web/static/style.css', import.meta.url), 'utf8');
  const rule = (selector) => css.match(new RegExp(`^${selector.replace(/[.#]/g, '\\$&')} \\{([^}]*)\\}`, 'm'))[1];
  assert.match(rule('.hint-dock'), /z-index: 22;/);
  assert.match(rule('.scrim'), /z-index: 20;/);
  assert.match(rule('.drawer'), /z-index: 21;/);
  assert.match(rule('.drawer'), /bottom: max\(16px, calc\(var\(--dock-room, -9px\) \+ 25px\)\);/);
  // Floating, it ends 46 px above the frame's content, level with the dock's bar.
  assert.match(rule('#drawer.floating'), /bottom: 63px;/);
  assert.match(rule('#drawer.floating'), /right: 39px;/);
});

test('a panel shows its skeleton, then its content rises', async () => {
  const { drawer } = fakePanelPage();
  try {
    state.view = 'gateway';
    windowIs(true);
    loadPanel('Tool');
    assert.equal(isPanelOpen(), true);
    // The kind and Close at once, quiet bars where the title, facts and first button will be.
    const [head, body] = drawer.children;
    assert.deepEqual(head.children[0].children.map((node) => node.textContent), ['Tool', 'Close']);
    assert.equal(head.children[1].attributes['aria-hidden'], 'true');
    assert.equal(body.children.length, 3);
    // The content waits until the skeleton has shown 160 ms, then each part rises 20 ms apart.
    const content = parts(3);
    openPanel(content);
    assert.notDeepEqual(drawer.children, content);
    await wait(200);
    assert.deepEqual(drawer.children, content);
    const rise = [{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }];
    assert.deepEqual(motionsOf(...content), [[rise, 260, 0, CALM], [rise, 260, 20, CALM], [rise, 260, 40, CALM]]);
    // A read that took longer than that lands at once.
    loadPanel('MCP server');
    await wait(200);
    const later = parts(1);
    openPanel(later);
    assert.deepEqual(drawer.children, later);
    // Closed while it loads, it stays closed.
    loadPanel('Client');
    closePanel({ focus: false, instant: true });
    await wait(200);
    assert.equal(isPanelOpen(), false);
    assert.notDeepEqual(drawer.children, later);
  } finally {
    leaveFloatTest();
  }
});

test("another block's Details swap in place", async () => {
  const { drawer } = fakePanelPage();
  try {
    state.view = 'gateway';
    windowIs(true);
    const first = parts(2);
    openPanel(first);
    motions.length = 0;
    loadPanel('Client');
    // The panel stays: it does not go and come again.
    assert.equal(isPanelOpen(), true);
    assert.equal(drawer.classList.contains('leaving'), false);
    assert.deepEqual(motionsOf(drawer), []);
    assert.equal(drawer.children[0].children[0].children[0].textContent, 'Client');
    // Content that comes meanwhile takes the place of content that waits.
    openPanel(parts(1));
    const second = parts(2);
    openPanel(second);
    await wait(200);
    assert.deepEqual(drawer.children, second);
    assert.equal(isPanelOpen(), true);
    closePanel({ focus: false, instant: true });
  } finally {
    leaveFloatTest();
  }
});

test('a step forward and back slide the content', async () => {
  const { drawer } = fakePanelPage();
  try {
    state.view = 'gateway';
    windowIs(true);
    const first = parts(2);
    openPanel(first);
    motions.length = 0;
    const next = parts(1);
    await stepTo(next, 'fwd');
    // The old parts go together 18 px left in 130 ms ease-in, the new come from 22 px right in 220 ms.
    const out = [[[{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateX(-18px)' }], 130, 0, 'ease-in']];
    assert.deepEqual(motionsOf(...first), [...out, ...out]);
    assert.deepEqual(motionsOf(...next), [[[{ opacity: 0, transform: 'translateX(22px)' }, { opacity: 1, transform: 'none' }], 220, 0, CALM]]);
    assert.deepEqual(drawer.children, next);
    // Back is the mirror.
    const back = parts(1);
    await stepTo(back, 'back');
    assert.deepEqual(motionsOf(...next).at(-1), [[{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateX(18px)' }], 130, 0, 'ease-in']);
    assert.deepEqual(motionsOf(...back), [[[{ opacity: 0, transform: 'translateX(-22px)' }, { opacity: 1, transform: 'none' }], 220, 0, CALM]]);
    assert.deepEqual(drawer.children, back);
    // A second step pressed while the first goes out wins.
    const [one, two] = [parts(1), parts(1)];
    const steps = [stepTo(one), stepTo(two)];
    await Promise.all(steps);
    assert.deepEqual(drawer.children, two);
    closePanel({ focus: false, instant: true });
  } finally {
    leaveFloatTest();
  }
});

test('under reduced motion every panel state lands at once', async () => {
  const { drawer } = fakePanelPage();
  try {
    state.view = 'gateway';
    windowIs(true);
    reducedMotion.matches = true;
    // The panel shows its content as soon as it has it: no skeleton flashes first.
    loadPanel('Tool');
    assert.equal(isPanelOpen(), false);
    const first = parts(2);
    openPanel(first);
    assert.equal(isPanelOpen(), true);
    assert.deepEqual(drawer.children, first);
    loadPanel('Client');
    assert.deepEqual(drawer.children, first);
    const second = parts(1);
    openPanel(second);
    assert.deepEqual(drawer.children, second);
    const third = parts(1);
    await stepTo(third, 'fwd');
    assert.deepEqual(drawer.children, third);
    closePanel({ focus: false });
    assert.equal(drawer.classList.contains('leaving'), false);
    assert.deepEqual(motions, []);
  } finally {
    leaveFloatTest();
  }
});

test('a review opened from the floating panel stays in it', () => {
  fakePanelPage();
  const drawer = document.querySelector('#drawer');
  try {
    state.view = 'gateway';
    windowIs(true);
    openPanel([]);
    openPanel([], { float: false }); // a swap keeps how the panel sits
    assert.equal(drawer.classList.contains('floating'), true);
    assert.equal(isPanelOpen(), true);
    closePanel({ focus: false });
  } finally {
    leaveFloatTest();
  }
});

// A page with the key handlers initPanel adds, and a way to press a key.
function keyboardPage() {
  fakePanelPage();
  const listeners = { keydown: [] };
  Object.assign(document, {
    addEventListener: (type, fn) => { (listeners[type] ||= []).push(fn); },
    body: {},
  });
  for (const id of ['#drawer', '#scrim']) document.querySelector(id).addEventListener = () => {};
  document.querySelector('#drawer').querySelectorAll = () => []; // nothing to press in the panel
  const media = { matches: true, change: null, addEventListener: (type, fn) => { media.change = fn; } };
  globalThis.matchMedia = () => media;
  return {
    media,
    press(key, extra = {}) {
      const event = { key, shiftKey: false, prevented: false, preventDefault() { this.prevented = true; }, ...extra };
      for (const fn of listeners.keydown) fn(event);
      return event;
    },
  };
}

test('Tab is not trapped in the floating panel, and Escape closes it', () => {
  const page = keyboardPage();
  const drawer = document.querySelector('#drawer');
  try {
    initPanel();
    state.view = 'changes';
    openPanel([]);
    assert.equal(drawer.classList.contains('floating'), true);
    assert.equal(page.press('Tab').prevented, false); // it leaves the panel
    page.press('Escape');
    assert.equal(isPanelOpen(), false);

    page.media.matches = false;
    openPanel([]);
    assert.equal(page.press('Tab').prevented, true); // the drawer keeps focus inside
    page.press('Escape');
    assert.equal(isPanelOpen(), false);
  } finally {
    leaveFloatTest();
  }
});

test('Tab in the drawer also reaches what the dock shows, the bar or a toast, in the page\'s order', () => {
  const page = keyboardPage();
  const find = document.querySelector;
  const stop = (name) => ({ name, getClientRects: () => [{}], focus() { document.activeElement = this; } });
  const [near, dockLast, own, ownLast] = [stop('dock first'), stop('dock last'), stop('drawer first'), stop('drawer last')];
  const asked = [];
  const dock = {
    querySelectorAll: (selector) => { asked.push(selector); return [near, dockLast]; },
    contains: (node) => node === near || node === dockLast,
  };
  const drawer = document.querySelector('#drawer');
  drawer.querySelectorAll = () => [own, ownLast];
  drawer.contains = (node) => node === own || node === ownLast;
  document.querySelector = (selector) => (selector === '#dock' ? dock : find(selector));
  try {
    initPanel();
    page.media.matches = false;
    openPanel([]);
    // The dock comes before the drawer on the page, so the loop does: from the drawer's last
    // button Tab goes to the dock's first, and Shift+Tab from there comes back.
    ownLast.focus();
    assert.equal(page.press('Tab').prevented, true);
    assert.equal(document.activeElement, near);
    assert.equal(page.press('Tab', { shiftKey: true }).prevented, true);
    assert.equal(document.activeElement, ownLast);
    // In the middle the browser's own order does the work; a turned-off button is not asked for.
    dockLast.focus();
    assert.equal(page.press('Tab').prevented, false);
    assert.ok(asked.every((selector) => selector === 'button:not([disabled])'), asked.join());
    // Focus outside starts at the drawer's own first button.
    document.activeElement = null;
    assert.equal(page.press('Tab').prevented, true);
    assert.equal(document.activeElement, own);
    // An empty dock adds no stops: the drawer's last goes round to its first.
    dock.querySelectorAll = () => [];
    ownLast.focus();
    assert.equal(page.press('Tab').prevented, true);
    assert.equal(document.activeElement, own);
    page.press('Escape');
  } finally {
    leaveFloatTest();
  }
});

test('Escape and other Details keep every tray row', async () => {
  const page = keyboardPage();
  const sent = [];
  globalThis.fetch = trayServer(sent);
  try {
    initPanel();
    await addToTray({ action: 'mcp.add', targets: [{ client: 'codex' }], params: { item: 'github' } });
    await addToTray({ action: 'mcp.add', targets: [{ client: 'codex' }], params: { item: 'neon' } });
    assert.deepEqual([tray.rows.length, tray.phase], [2, 'ready']);
    // A row's review, other Details over it, then Escape.
    panelState.current = { type: 'row-review', row: tray.rows[0] };
    openPanel(['row review']);
    panelState.current = { type: 'item', row: {} };
    openPanel(['other details']);
    page.press('Escape');
    assert.equal(isPanelOpen(), false);
    // A row's review closed by its own Close.
    panelState.current = { type: 'row-review', row: tray.rows[1] };
    openPanel(['row review']);
    closePanel({ focus: false });
    assert.deepEqual([tray.rows.length, tray.phase], [2, 'ready']);
    assert.deepEqual(sent.filter((call) => call.url.endsWith('/cancel')).map((call) => call.url), ['/api/changes/c1/cancel']); // only the first preview, replaced by the second
  } finally {
    await cancelTray();
    panelState.current = null;
    delete globalThis.fetch;
    leaveFloatTest();
  }
});

test("Ctrl Enter presses the tray's Apply when ready", async () => {
  const page = keyboardPage();
  const sent = [];
  globalThis.fetch = trayServer(sent);
  let pressed = 0;
  const apply = { click: () => { pressed += 1; } };
  const [inDock, inDrawer, onPage] = [{ name: 'dock' }, { name: 'drawer' }, { name: 'page' }];
  const dock = { contains: (node) => node === inDock };
  const drawer = document.querySelector('#drawer');
  drawer.contains = (node) => node === inDrawer;
  const find = document.querySelector;
  document.querySelector = (selector) => ({ '#dock': dock, '#dock .apply': apply })[selector] ?? find(selector);
  const ctrl = (extra = { ctrlKey: true }) => page.press('Enter', extra).prevented;
  try {
    initPanel();
    // Nothing in the tray: nothing to press.
    document.activeElement = inDock;
    assert.deepEqual([ctrl(), pressed], [false, 0]);
    await addToTray({ action: 'mcp.add', targets: [{ client: 'codex' }], params: { item: 'github' } });
    assert.equal(tray.phase, 'ready');
    // From the dock, and from Details with ⌘ (on a Mac).
    assert.deepEqual([ctrl(), pressed], [true, 1]);
    openPanel([]);
    document.activeElement = inDrawer;
    assert.deepEqual([ctrl({ metaKey: true }), pressed], [true, 2]);
    // Focus on the page, or Enter alone: nothing.
    document.activeElement = onPage;
    assert.deepEqual([ctrl(), pressed], [false, 2]);
    document.activeElement = inDrawer;
    assert.deepEqual([ctrl({}), pressed], [false, 2]);
    // While a preview is on its way Apply waits, and so does the key.
    tray.phase = 'asking';
    assert.deepEqual([ctrl(), pressed], [false, 2]);
    tray.phase = 'ready';
    // Closed Details: focus in the drawer does not count.
    closePanel({ focus: false });
    document.activeElement = inDrawer;
    assert.deepEqual([ctrl(), pressed], [false, 2]);
  } finally {
    await cancelTray();
    delete globalThis.fetch;
    leaveFloatTest();
  }
});

test('a window that grows or shrinks while Details are open switches the floating panel and the drawer', () => {
  const page = keyboardPage();
  const drawer = document.querySelector('#drawer');
  const scrim = document.querySelector('#scrim');
  const shell = document.querySelector('.shell');
  try {
    initPanel();
    state.view = 'library';
    openPanel([]);
    page.media.change({ matches: false });
    assert.deepEqual([drawer.classList.contains('floating'), scrim.classList.contains('open')], [false, true]);
    assert.equal(drawer.attributes['aria-modal'], 'true');
    page.media.change({ matches: true });
    assert.deepEqual([drawer.classList.contains('floating'), scrim.classList.contains('open')], [true, false]);
    assert.equal(drawer.attributes['aria-modal'], undefined);
    closePanel({ focus: false });
    page.media.change({ matches: false }); // nothing is open: nothing to switch
    assert.equal(shell.className, '');
    assert.equal(scrim.classList.contains('open'), false);
  } finally {
    leaveFloatTest();
  }
});

test('Escape gives focus back to the control that opened Details, found again after a redraw', () => {
  fakePanelPage();
  const focused = [];
  const named = (key, name) => ({ dataset: { focus: key }, focus: () => focused.push(name) });
  const first = { ...named('block:github', 'first'), isConnected: true, closest: function (selector) { return selector.includes('data-focus') ? this : null; } };
  try {
    state.view = 'gateway';
    windowIs(true);
    document.activeElement = first;
    openPanel([]);
    first.isConnected = false; // the page was drawn again: a new node has the same key
    document.querySelectorAll = (selector) => (selector === '[data-focus]' ? [named('block:other', 'other'), named('block:github', 'again')] : []);
    closePanel();
    assert.deepEqual(focused, ['again']);
  } finally {
    leaveFloatTest();
  }
});

test('beside the page, opening another item moves the way back to that item', () => {
  fakePanelPage();
  const focused = [];
  const control = (name) => ({ isConnected: true, closest: () => null, focus: () => focused.push(name) });
  const [first, second] = [control('first'), control('second')];
  try {
    state.view = 'library';
    windowIs(true);
    document.activeElement = first;
    openPanel([]);
    document.activeElement = second; // the page is usable: another row was pressed
    openPanel([]);
    closePanel();
    assert.deepEqual(focused, ['second']);
  } finally {
    leaveFloatTest();
  }
});

test('a redraw of the floating panel does not take focus from the page', () => {
  fakePanelPage();
  const drawer = document.querySelector('#drawer');
  const focused = [];
  drawer.focus = () => focused.push('drawer');
  try {
    state.view = 'library';
    windowIs(true);
    openPanel([]);
    focused.length = 0;
    swapContent([]); // focus is on the page, not in the panel
    assert.deepEqual(focused, []);
    let asked = 0;
    drawer.contains = () => asked++ === 0; // focus was in the panel; its old buttons are gone
    swapContent([]);
    assert.deepEqual(focused, ['drawer']);
    drawer.contains = () => false;
    document.activeElement = null;
    windowIs(false);
    closePanel({ focus: false });
    openPanel([]);
    focused.length = 0;
    swapContent([]); // the drawer always keeps focus
    assert.deepEqual(focused, ['drawer']);
  } finally {
    leaveFloatTest();
  }
});

// A stand-in element: keeps what a builder gives it and runs its click listener.
function domNode(tag) {
  const node = {
    tag, className: '', textContent: '', children: [], attributes: {}, dataset: {}, parent: null, focused: false,
    append(...nodes) { for (const child of nodes) { child.parent = node; node.children.push(child); } },
    prepend(...nodes) { for (const child of nodes) child.parent = node; node.children.unshift(...nodes); },
    setAttribute(name, value) { node.attributes[name] = value; },
    removeAttribute(name) { delete node.attributes[name]; },
    addEventListener(type, fn) { node[`on${type}`] = fn; },
    replaceWith(...nodes) {
      const at = node.parent.children.indexOf(node);
      node.parent.children.splice(at, 1, ...nodes);
      for (const child of nodes) child.parent = node.parent;
    },
    focus() { node.focused = true; },
  };
  return node;
}

// The words of a node: its own text, else its children's.
const wordsOf = (node) => node.textContent || node.children.map(wordsOf).join('');
const words = (nodes) => nodes.map(wordsOf);

test('Facts are labels and values in two columns, and a value can be a node', () => {
  globalThis.document = { createElement: domNode };
  try {
    const value = domNode('span');
    const list = factsBlock([{ label: 'State', value: 'Off in this project', accent: true }, { label: 'Clients', value }]);
    assert.equal(list.tag, 'dl');
    assert.equal(list.className, 'facts');
    assert.deepEqual(list.children.map((node) => [node.tag, node.className, node.textContent]), [
      ['dt', '', 'State'], ['dd', 'accent', 'Off in this project'], ['dt', '', 'Clients'], ['dd', '', ''],
    ]);
    assert.equal(list.children[3].children[0], value);
  } finally {
    delete globalThis.document;
  }
});

const card = (fields) => ({ kind: 'Skill', title: 'release-notes', ...fields });

test('a Details card is the header, the facts and the sentence, the stacked actions, and the folded evidence', () => {
  globalThis.document = { createElement: domNode };
  try {
    const folded = domNode('details');
    const after = domNode('div');
    const nodes = detailsCard(card({
      id: 'release-notes@user',
      facts: [{ label: 'State', value: 'On' }],
      why: 'Claude Code loads it from all projects.',
      actions: [{ label: 'Turn off for all projects…', run() {}, primary: true }, { label: 'Add to Codex…', run() {} }],
      more: [{ label: 'Remove from Claude Code…', run() {} }],
      after,
      technical: folded,
    }));
    const [head, body, footer, evidence] = nodes;
    assert.deepEqual(nodes.map((node) => node.tag), ['header', 'div', 'footer', 'details']);
    // The kind and Close, then the title, then the id quiet under it.
    assert.deepEqual(head.children[0].children.map((node) => node.textContent), ['Skill', 'Close']);
    assert.deepEqual(head.children.slice(1).map((node) => [node.tag, node.textContent]), [['h1', 'release-notes'], ['p', 'release-notes@user']]);
    assert.equal(body.className, 'body');
    assert.deepEqual(body.children.map((node) => [node.tag, node.className]), [['dl', 'facts'], ['p', 'why']]);
    assert.equal(body.children[1].textContent, 'Claude Code loads it from all projects.');
    // The actions in order, the primary one drawn with the action fill; More; then the quiet node.
    assert.equal(footer.className, 'stack');
    assert.deepEqual(words(footer.children.slice(0, 3)), ['Turn off for all projects…', 'Add to Codex…', 'More']);
    assert.deepEqual(footer.children.slice(0, 2).map((node) => node.className), ['btn primary', 'btn']);
    assert.equal(footer.children[3], after);
    assert.equal(evidence, folded);
  } finally {
    delete globalThis.document;
  }
});

test('a Details card with nothing to add leaves the rest out', () => {
  globalThis.document = { createElement: domNode };
  try {
    const nodes = detailsCard(card({ actions: [{ label: 'Open', run() {} }] }));
    assert.deepEqual(nodes.map((node) => node.tag), ['header', 'div', 'footer']);
    assert.deepEqual(nodes[0].children.map((node) => node.tag), ['div', 'h1']); // no id line
    assert.deepEqual(nodes[1].children, []);
    assert.deepEqual(words(nodes[2].children), ['Open']); // no More, no quiet node
    // With nothing to press and nothing quiet to say, there is no empty footer.
    assert.deepEqual(detailsCard(card({ facts: [{ label: 'State', value: 'On' }] })).map((node) => node.tag), ['header', 'div']);
  } finally {
    delete globalThis.document;
  }
});

test('More shows the other actions where it stood, before the quiet node', () => {
  globalThis.document = { createElement: domNode };
  try {
    const after = domNode('div');
    const [, , footer] = detailsCard(card({ actions: [{ label: 'One', run() {} }], more: [{ label: 'Two', run() {} }, { label: 'Three', run() {} }], after }));
    const more = footer.children[1];
    assert.equal(more.textContent, 'More');
    more.onclick({});
    return Promise.resolve().then(() => {
      assert.deepEqual(words(footer.children), ['One', 'Two', 'Three', '']);
      assert.equal(footer.children[3], after);
      assert.equal(footer.children[1].focused, true);
    });
  } finally {
    delete globalThis.document;
  }
});

test('an action runs its own code, else it adds its change to the tray', async () => {
  fakePanelPage();
  document.createElement = domNode;
  const calls = [];
  const body = { action: 'skill.remove', targets: [{ item: 's1' }], params: {} };
  globalThis.fetch = async (url, options = {}) => {
    calls.push([options.method || 'GET', url, options.body]);
    return Response.json({ detail: 'No.' }, { status: 422 });
  };
  try {
    const [, , footer] = detailsCard(card({ actions: [{ label: 'Own', run: () => calls.push('run') }, { label: 'Remove…', body }] }));
    footer.children[0].onclick({});
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.deepEqual(calls, ['run']);
    footer.children[1].onclick({});
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(calls[1][1], '/api/batch/preview');
    assert.deepEqual(JSON.parse(calls[1][2]).requests.map((r) => [r.kind, r.targets, r.params, r.picked]), [[body.action, body.targets, body.params, null]]);
    // Each action is found again by its words after the card is drawn again.
    assert.deepEqual(footer.children.map((node) => node.dataset.focus), ['action:Own', 'action:Remove…']);
  } finally {
    await cancelTray();
    panelState.current = null;
    delete globalThis.document;
    delete globalThis.fetch;
  }
});

test("panel.js re-exports the dock's toast", async () => {
  const dock = await import('../../src/kitden/web/static/js/toast.js');
  const panel = await import('../../src/kitden/web/static/js/panel.js');
  assert.equal(panel.toast, dock.toast);
  assert.equal(panel.hideToast, dock.hideToast);
});
