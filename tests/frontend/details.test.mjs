import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';

// details.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
// Node before 21 has no navigator; details.js must load there too.
delete globalThis.navigator;
const { DETAILS_ORDER, affectsFor, affectsText, contextLinks, detailsOrder, fileScopeWords, footerActions, layerState, offerLabel, originWords, scopeWords, techRows, whyLines, whyParts } = await import('../../src/kitden/web/static/js/details.js');
const { addReach } = await import('../../src/kitden/web/static/js/offer.js');

const def = (fields) => ({ kind: 'skill', scope: 'user', project: null, enabled: 'on', owner_client: fields.client, loads: true, overridden: false, merged: false, ...fields });
const site = '/Users/me/work/website';

test('each side panel module loads first, on its own', () => {
  // panel.js, details.js, tools.js and review.js import each other; none may call an import
  // while it loads, or the module that happens to load first breaks.
  for (const name of ['panel', 'details', 'tools', 'review']) {
    const url = new URL(`../../src/kitden/web/static/js/${name}.js`, import.meta.url).href;
    const code = `globalThis.matchMedia = () => ({ matches: false }); delete globalThis.navigator; await import(${JSON.stringify(url)});`;
    const run = spawnSync(process.execPath, ['--input-type=module', '-e', code], { encoding: 'utf8' });
    assert.equal(run.status, 0, `${name}.js: ${run.stderr}`);
  }
});

test('Details keeps the five questions in order', () => {
  assert.deepEqual(detailsOrder(new Set(DETAILS_ORDER)), ['warnings', 'about', 'why', 'clients', 'tools', 'secret', 'next', 'links', 'technical']);
  assert.deepEqual(detailsOrder(new Set(['technical', 'why', 'next'])), ['why', 'next', 'technical']);
});

test('why says where it loads from and the rule that decides', () => {
  assert.deepEqual(whyLines([def({ client: 'codex' }), def({ client: 'cursor', owner_client: 'shared' })], null), ['Codex and Cursor load it from all projects.']);
  assert.deepEqual(whyLines([def({ client: 'claude_code', scope: 'project', project: site }), def({ client: 'claude_code', loads: false, overridden: true })], site),
    ['Claude Code loads it from this project.', 'In Claude Code, the one from this project overrides the one from all projects.']);
  assert.deepEqual(whyLines([def({ client: 'claude_code', kind: 'plugin' }), def({ client: 'cursor', kind: 'plugin', owner_client: 'claude_code' })], null),
    ["Claude Code loads it from all projects; Cursor through Claude Code's folder."]);
  assert.deepEqual(whyLines([def({ client: 'codex', loads: false, enabled: 'off' })], null), ['Turned off in Codex.']);
  // An unknown state: the layer gives its own reason, so the Why adds nothing.
  assert.deepEqual(whyLines([def({ client: 'codex', loads: false, enabled: 'unknown' })], null), []);
  assert.deepEqual(whyLines([def({ client: 'claude_code', scope: 'project', project: '/a/site', loads: false }), def({ client: 'claude_code', scope: 'project', project: '/a/api', loads: false })], null),
    ['It is in 2 projects; it loads only there.']);
  assert.deepEqual(whyLines([def({ client: 'codex', kind: 'instructions' })], null), []);
});

test('why names a folder that several clients read, in words', () => {
  const folder = '/Users/me/.agents/skills/code-review/SKILL.md';
  assert.deepEqual(whyLines([def({ client: 'codex', source: folder }), def({ client: 'cursor', owner_client: 'shared', source: folder })], null),
    ['Codex and Cursor load it from all projects.', 'One folder, read by Codex and Cursor.']);
  // Turned off in one of them: both facts.
  assert.deepEqual(whyLines([def({ client: 'codex', source: folder, loads: false, enabled: 'off' }), def({ client: 'cursor', owner_client: 'shared', source: folder })], null),
    ['Cursor loads it from all projects.', 'One folder, read by Codex and Cursor. Turned off in Codex.']);
  // Two folders, one per client: nothing shared to say.
  assert.deepEqual(whyLines([def({ client: 'codex', source: folder }), def({ client: 'cursor', source: '/Users/me/.cursor/skills/code-review/SKILL.md' })], null),
    ['Codex and Cursor load it from all projects.']);
});

test('why says a merge and a server in the Kitden gateway', () => {
  assert.deepEqual(whyLines([def({ client: 'claude_code', kind: 'mcp_server', scope: 'project', project: site }), def({ client: 'claude_code', kind: 'mcp_server', loads: false, merged: true })], site),
    ['Claude Code loads it from this project.', 'In Claude Code, the ones from this project and from all projects are merged.']);
  const held = (client, fields = {}) => def({ client, kind: 'mcp_server', name: 'files', owner_client: 'kitden', via_gateway: 'kitden', ...fields });
  assert.deepEqual(whyLines([held('claude_code'), held('cursor')], null), ['Claude Code and Cursor load it through the Kitden gateway.']);
  assert.deepEqual(whyLines([def({ client: 'codex', loads: false, enabled: 'unknown' }), def({ client: 'cursor', loads: false, enabled: 'unknown' })], null), []);
});

test('two definitions that come the same way are told apart, or said plainly', () => {
  // A held server with a switch of its own in this project: Codex merges, Claude Code overrides.
  const held = (client, fields = {}) => def({ client, kind: 'mcp_server', name: 'files', owner_client: 'kitden', via_gateway: 'kitden', ...fields });
  const mine = { scope: 'project', project: site };
  assert.deepEqual(whyLines([held('claude_code', mine), held('claude_code', { loads: false, overridden: true }), held('codex', mine), held('codex', { loads: false, merged: true })], site),
    ["Claude Code and Codex load it through the Kitden gateway.", "Claude Code and Codex use this project's switch for files in the Kitden gateway."]);
  // Both through Claude Code's folder: the scope tells them apart.
  const imported = (fields) => def({ client: 'cursor', kind: 'plugin', owner_client: 'claude_code', ...fields });
  assert.deepEqual(whyLines([imported(mine), imported({ loads: false, overridden: true })], site),
    ["Cursor loads it through Claude Code's folder.", 'In Cursor, the one from this project overrides the one from all projects.']);
  // Two plugins with a server of one name: nothing tells them apart.
  const fromPlugin = (fields) => def({ client: 'claude_code', kind: 'mcp_server', scope: 'plugin', ...fields });
  assert.deepEqual(whyLines([fromPlugin({}), fromPlugin({ loads: false, overridden: true })], null),
    ['Claude Code loads it from a plugin.', 'In Claude Code, two of them come from a plugin; only one loads.']);
  // The project's switch is off: said once, as the switch's state, not as each client's.
  const off = { scope: 'project', project: site, loads: false, enabled: 'off' };
  assert.deepEqual(whyLines([held('claude_code', off), held('claude_code', { loads: false, overridden: true }), held('codex', off), held('codex', { loads: false, merged: true })], site),
    ["In the Kitden gateway, this project's switch for files is off."]);
  // The project's own setting turns it off over the one for all projects.
  assert.deepEqual(whyLines([def({ client: 'claude_code', kind: 'plugin', ...mine, loads: false, enabled: 'off' }), def({ client: 'claude_code', kind: 'plugin', loads: false, overridden: true })], site),
    ['In Claude Code, the one from this project overrides the one from all projects. Turned off in Claude Code.']);
});

test('the origin uses the route words, then the scope', () => {
  assert.equal(originWords(def({ client: 'cursor', owner_client: 'claude_code' }), null), "through Claude Code's folder");
  assert.equal(originWords(def({ client: 'cursor', owner_client: 'shared' }), null), 'from all projects');
  assert.equal(originWords(def({ client: 'cursor', kind: 'mcp_server', owner_client: 'kitden', via_gateway: 'kitden' }), null), 'through the Kitden gateway');
  assert.equal(originWords(def({ client: 'claude_desktop_code_tab', kind: 'mcp_server' }), null), 'from the Desktop app');
  assert.equal(originWords(def({ client: 'claude_code', scope: 'plugin' }), null), 'from a plugin');
  assert.equal(originWords(def({ client: 'claude_code', scope: 'local', project: site }), site), 'from this project');
  assert.equal(originWords(def({ client: 'claude_code', scope: 'project', project: '/a/api' }), site), 'from api');
  assert.equal(originWords(def({ client: 'claude_code', scope: 'managed' }), null), 'from your organization');
  assert.equal(originWords(def({ client: 'claude_code', scope: 'account' }), null), 'from your Claude account');
});

test('a section title names only a known client as the owner of a folder', () => {
  assert.equal(scopeWords({ scope: 'user', client: 'cursor', owner_client: 'shared' }, null), 'All projects');
  assert.equal(scopeWords({ scope: 'user', client: 'cursor', owner_client: 'kitden', via_gateway: 'kitden' }, null), 'All projects');
  assert.equal(fileScopeWords({ scope: 'user', client: 'cursor', owner_client: 'shared' }), 'Global settings');
  assert.equal(fileScopeWords({ scope: 'user', client: 'cursor', owner_client: 'claude_code' }), 'Global settings · via Claude Code');
  assert.equal(fileScopeWords({ scope: 'local', client: 'claude_code', owner_client: 'claude_code', project: site }), 'Only on this Mac · website');
});

test('a copy that is off says so only where the client loads nothing else', () => {
  // Two plugins of one name from two marketplaces, one of them off: Claude Code still loads it.
  const two = [def({ client: 'claude_code', kind: 'plugin', name: 'superpowers@a' }), def({ client: 'claude_code', kind: 'plugin', name: 'superpowers@b', loads: false, enabled: 'off', why: 'Does not load: it is turned off.' })];
  assert.deepEqual(whyLines(two, null), ['Claude Code loads it from all projects.']);
  assert.equal(layerState(two[1], whyParts(two, null).said).why, 'Does not load: it is turned off.');
  // A Codex skill in two folders, one turned off.
  assert.deepEqual(whyLines([def({ client: 'codex', source: '/h/.agents/skills/a/SKILL.md' }), def({ client: 'codex', source: '/h/.codex/skills/a/SKILL.md', loads: false, enabled: 'off' })], null),
    ['Codex loads it from all projects.']);
});

test('with All projects picked, a project that has it off is named', () => {
  const site = def({ client: 'claude_code', scope: 'project', project: '/a/site', loads: false });
  const api = def({ client: 'claude_code', scope: 'project', project: '/a/api', loads: false, enabled: 'off' });
  assert.deepEqual(whyLines([site, api], null), ['It is in 2 projects; it loads only there. Turned off in api.']);
  const user = def({ client: 'claude_code' });
  assert.deepEqual(whyLines([user, api], null), ['Claude Code loads it from all projects.', 'Turned off in api.']);
});

test('a layer leaves to the Why what the Why says', () => {
  const loaded = { kind: 'mcp_server', enabled: 'on', loads: true };
  assert.equal(layerState({ ...loaded, why: 'Loads. It overrides the user definition.' }).why, '');
  assert.equal(layerState({ kind: 'plugin', enabled: 'on', loads: false, overridden: true, why: 'Does not load: the project definition overrides it.' }).why, '');
  assert.equal(layerState({ kind: 'mcp_server', enabled: 'on', loads: false, merged: true, why: 'Merged with the project definition; its fields win.' }).why, '');
  // Turned off, and only in other projects: the Why says these, so the layers do not.
  const off = def({ client: 'codex', kind: 'plugin', loads: false, enabled: 'off', why: 'Does not load: it is turned off.' });
  assert.equal(layerState(off, whyParts([off], null).said).why, '');
  assert.equal(layerState(off).why, 'Does not load: it is turned off.');
  const elsewhere = def({ client: 'claude_code', loads: false, scope: 'project', project: '/a/api', why: 'Does not load here: it belongs to another project.' });
  assert.equal(layerState(elsewhere, whyParts([elsewhere], null).said).why, '');
  // What the Why does not say stays: a plugin that is not loaded, and an unknown state's reason.
  const part = 'Does not load here: its plugin is not loaded.';
  const notLoaded = def({ client: 'claude_code', kind: 'mcp_server', loads: false, scope: 'plugin', why: part });
  assert.equal(layerState(notLoaded, whyParts([notLoaded], site).said).why, part);
  assert.equal(layerState({ kind: 'plugin', enabled: 'unknown', unknown_reason: 'stored_in_account', loads: false }).why, 'Its on/off state is kept in your Claude account, not on this Mac.');
  assert.equal(layerState({ kind: 'instructions', enabled: 'on', loads: true, why: 'Read when a session starts.' }).why, 'Read when a session starts.');
});

test('technical details keep the path, the key, the command and the first lines', () => {
  const rows = techRows([
    { client: 'cursor', scope: 'user', project: null, source: '/Users/me/.cursor/mcp.json', key: 'mcpServers.github', summary: 'npx -y github-mcp', preview: null },
    { client: 'claude_code', scope: 'user', project: null, source: '/Users/me/.claude/CLAUDE.md', key: null, summary: null, preview: ['# rules'] },
    { client: 'claude_code', scope: 'account', project: null, source: 'account', key: null, summary: null, preview: null },
  ]);
  assert.deepEqual(rows.map((r) => [r.client, r.path, r.key, r.summary, r.preview]), [
    ['claude_code', '/Users/me/.claude/CLAUDE.md', null, null, ['# rules']],
    ['cursor', '/Users/me/.cursor/mcp.json', 'mcpServers.github', 'npx -y github-mcp', null],
  ]);
  assert.equal(rows[1].title, 'Cursor · Global settings');
  assert.deepEqual(techRows([{ client: 'claude_code', scope: 'account', source: 'account' }]), []);
});

test('technical details show one file once, for every client that reads it', () => {
  const gateway = '/Users/me/Library/Application Support/kitden/gateway.json';
  const held = (client) => ({ client, scope: 'user', project: null, owner_client: 'kitden', via_gateway: 'kitden', source: gateway, key: 'servers.files', summary: 'npx files-mcp', preview: null });
  const own = { client: 'cursor', scope: 'user', project: null, owner_client: 'cursor', source: '/Users/me/.cursor/mcp.json', key: 'mcpServers.files', summary: 'npx files-mcp', preview: null };
  assert.deepEqual(techRows([held('cursor'), held('claude_code'), held('codex'), own]).map((r) => [r.title, r.path, r.key]), [
    ['Kitden gateway · Global settings', gateway, 'servers.files'],
    ['Cursor · Global settings', '/Users/me/.cursor/mcp.json', 'mcpServers.files'],
  ]);
  const skill = '/Users/me/.agents/skills/code-review/SKILL.md';
  assert.deepEqual(techRows([def({ client: 'cursor', owner_client: 'shared', source: skill }), def({ client: 'codex', source: skill })]).map((r) => r.title),
    ['Codex and Cursor · Global settings']);
});

// The Affects line and the links ------------------------------------------------------------

const codexDef = { id: 'd1', client: 'codex', project: null, affects: { clients: ['codex', 'cursor'], scope: 'all', note: "Cursor reads Codex's folder" } };

test('the Affects line names every client the lead changes, and why', () => {
  const affects = affectsFor({ def: codexDef, action: 'skill.remove' }, { definitions: [codexDef] });
  assert.equal(affectsText(affects, null), "Changes Codex and Cursor (Cursor reads Codex's folder). All projects.");
});

test('a project definition names its project', () => {
  const local = { id: 'd2', client: 'claude_code', project: site, affects: { clients: ['claude_code'], scope: 'project', note: null } };
  const affects = affectsFor({ def: local, action: 'mcp.remove_direct' }, { definitions: [local] });
  assert.equal(affectsText(affects, site), 'Changes Claude Code. In this project.');
  assert.equal(affectsText(affects, null), 'Changes Claude Code. In website.');
});

test('a definition another one overrides in this project is not promised for this project', () => {
  const user = def({ id: 'u', client: 'claude_code', kind: 'mcp_server', loads: false, overridden: true, affects: { clients: ['claude_code'], scope: 'all', note: null } });
  const mine = def({ id: 'p', client: 'claude_code', kind: 'mcp_server', scope: 'project', project: site });
  const affects = affectsFor({ def: user, action: 'mcp.remove_direct' }, { definitions: [user, mine], project: site });
  assert.equal(affectsText(affects, site), 'Changes Claude Code. All projects except this one.');
  // Overridden by another of all projects (two plugins): nothing to leave out.
  const other = def({ id: 'o', client: 'claude_code', kind: 'mcp_server', scope: 'plugin' });
  assert.equal(affectsText(affectsFor({ def: user, action: 'mcp.remove_direct' }, { definitions: [user, other], project: site }), site), 'Changes Claude Code. All projects.');
  // It also reaches another client, whose copy nothing overrides here: all projects.
  const shared = { ...user, client: 'codex', affects: { clients: ['codex', 'cursor'], scope: 'all', note: null } };
  const codexHere = { ...mine, client: 'codex' };
  assert.equal(affectsText(affectsFor({ def: shared, action: 'skill.remove' }, { definitions: [shared, codexHere], project: site }), site), 'Changes Codex and Cursor. All projects.');
});

test('a move names every client whose entry moves', () => {
  const cc = { id: 'e1', client: 'claude_code', project: null, affects: { clients: ['claude_code'], scope: 'all', note: null } };
  const cx = { id: 'e2', client: 'codex', project: null, affects: { clients: ['codex'], scope: 'all', note: null } };
  assert.equal(affectsText(affectsFor('move', { definitions: [cc, cx], move: { items: ['e1', 'e2'], gateways: [{}] } }), null), 'Changes Claude Code and Codex. All projects.');
  // Every entry in one project's files: that project.
  const p1 = { ...cc, project: site, affects: { ...cc.affects, scope: 'project' } };
  const p2 = { ...cx, project: site, affects: { ...cx.affects, scope: 'project' } };
  assert.equal(affectsText(affectsFor('move', { definitions: [p1, p2], move: { items: ['e1', 'e2'], gateways: [{}] } }), site), 'Changes Claude Code and Codex. In this project.');
  assert.equal(affectsText(affectsFor('move', { definitions: [p1, cx], move: { items: ['e1', 'e2'], gateways: [{}] } }), site), 'Changes Claude Code and Codex. All projects.');
});

test('a move into a gateway also names every client that reaches the gateway already', () => {
  // github in the medium sample: Claude Code and Codex reach files through the Kitden gateway.
  const github = { id: 'g1', client: 'claude_code', project: null, affects: { clients: ['claude_code'], scope: 'all', note: null } };
  const kitden = { id: 'kitden', kind: 'kitden' };
  const obot = { id: 'gw-1', movable: true };
  const connections = { kitden: { claude_code: ['files'], codex: ['files', 'tracker'], cursor: [] }, 'gw-1': { claude_code: [], codex: ['search'], cursor: ['search'] } };
  const move = (gateways) => ({ items: ['g1'], gateways });
  assert.equal(affectsText(affectsFor('move', { definitions: [github], move: move([kitden]), connections }), null), 'Changes Claude Code and Codex. All projects.');
  // Two gateways to choose from: only what every choice reaches (Cursor reaches only one).
  assert.equal(affectsText(affectsFor('move', { definitions: [github], move: move([kitden, obot]), connections }), null), 'Changes Claude Code and Codex. All projects.');
  assert.equal(affectsText(affectsFor('move', { definitions: [github], move: move([obot]), connections }), null), 'Changes Claude Code, Codex and Cursor. All projects.');
  // The gateway could not be read: only the entries that move.
  assert.equal(affectsText(affectsFor('move', { definitions: [github], move: move([kitden]) }), null), 'Changes Claude Code. All projects.');
});

test('the first move into the Kitden gateway names every client whose kitden entry is on', () => {
  // It holds no server yet, so no client reaches a server through it; Codex's entry is on.
  const github = { id: 'g1', client: 'claude_code', project: null, affects: { clients: ['claude_code'], scope: 'all', note: null } };
  const move = { items: ['g1'], gateways: [{ id: 'kitden', kind: 'kitden' }] };
  const empty = { kitden: { claude_code: [], codex: [], cursor: [] } };
  assert.equal(affectsText(affectsFor('move', { definitions: [github], move, connections: empty, kitdenLinked: ['codex'] }), null), 'Changes Claude Code and Codex. All projects.');
  // The entries were not read: what the gateway page shows.
  assert.equal(affectsText(affectsFor('move', { definitions: [github], move, connections: empty, kitdenLinked: null }), null), 'Changes Claude Code. All projects.');
});

test('an add names what its copy reaches, and says when the place is chosen next', () => {
  const inherits = { plugin: true, skill: true };
  const found = ['claude_code', 'codex', 'cursor'];
  assert.deepEqual(addReach('codex', 'skill.install', inherits, found, false), { clients: ['codex', 'cursor'], note: "Cursor reads Codex's folder" });
  assert.deepEqual(addReach('claude_code', 'plugin.skills', inherits, found, false), { clients: ['claude_code', 'cursor'], note: "Cursor reads Claude Code's folder" });
  assert.deepEqual(addReach('claude_code', 'skill.install', { plugin: true, skill: false }, found, false), { clients: ['claude_code'], note: null });
  assert.deepEqual(addReach('claude_code', 'plugin.install', inherits, found, false), { clients: ['claude_code', 'cursor'], note: "Cursor loads Claude Code's plugins" });
  assert.deepEqual(addReach('claude_code', 'plugin.install', inherits, found, true), { clients: ['claude_code'], note: null });
  assert.deepEqual(addReach('codex', 'skill.install', inherits, ['codex'], false), { clients: ['codex'], note: null });
  assert.deepEqual(addReach('cursor', 'skill.install', inherits, found, false), { clients: ['cursor'], note: null });
  const add = { client: 'codex', add: { action: 'skill.install', project_place: true }, label: 'Add to Codex…' };
  assert.equal(affectsText(affectsFor(add, { definitions: [], inherits, found, project: 'p1' }), site),
    "Changes Codex and Cursor (Cursor reads Codex's folder). You choose this project or all projects next.");
  // A project's own skill goes into the picked project, with no choice.
  const own = { client: 'claude_code', add: { action: 'skill.install', project_only: true, project_place: false }, label: 'Add to Claude Code…' };
  assert.equal(affectsText(affectsFor(own, { definitions: [], inherits, found, project: site }), site),
    "Changes Claude Code and Cursor (Cursor reads Claude Code's folder). In this project.");
  // With All projects picked, nothing to choose.
  assert.equal(affectsText(affectsFor(add, { definitions: [], inherits, found, project: '' }), ''),
    "Changes Codex and Cursor (Cursor reads Codex's folder). All projects.");
});

test('nothing to lead, the Add form, or no answer from the server: no Affects line', () => {
  assert.equal(affectsFor(null, { definitions: [] }), null);
  assert.equal(affectsFor({ form: true, label: 'Add…' }, { definitions: [] }), null);
  assert.equal(affectsFor({ def: { id: 'x', client: 'codex' }, action: 'plugin.disable' }, { definitions: [] }), null);
});

test('links lead to another page with the same item', () => {
  const row = { kind: 'mcp_server', name: 'files' };
  const held = [{ via_gateway: 'kitden' }];
  assert.deepEqual(contextLinks(row, held, 'overview').map((l) => [l.label, l.view]), [['Compare across clients', 'library'], ['Manage tools', 'gateway']]);
  assert.deepEqual(contextLinks(row, held, 'library').map((l) => l.label), ['Manage tools']);
  assert.deepEqual(contextLinks(row, [{ via_gateway: null }], 'gateway').map((l) => l.label), ['Compare across clients']);
  assert.deepEqual(contextLinks(row, held, 'overview')[0].selected, { kind: 'mcp_server', name: 'files' });
  assert.deepEqual(contextLinks(row, held, 'library')[0].selected, { kind: 'mcp_server', name: 'files' });
  // A plugin row goes by its full name in the Library.
  assert.deepEqual(contextLinks({ kind: 'plugin', name: 'figma', lookup: 'figma@a' }, [], 'gateway')[0].selected, { kind: 'plugin', name: 'figma@a' });
});

test('a Remove names every client it reaches; a switch names its own client', () => {
  const remove = { def: codexDef, action: 'skill.remove' };
  assert.equal(offerLabel(remove, [remove]), 'Remove from Codex and Cursor…');
  const plugin = { id: 'p', client: 'claude_code', scope: 'user', affects: { clients: ['claude_code', 'cursor'], scope: 'all', note: "Cursor loads Claude Code's plugins" } };
  assert.equal(offerLabel({ def: plugin, action: 'plugin.remove' }, []), 'Remove from Claude Code and Cursor…');
  assert.equal(offerLabel({ def: plugin, action: 'plugin.disable' }, []), 'Turn off in Claude Code…');
  // Twins still name their folder after the clients.
  const at = (folder, clients) => ({ def: { id: folder, client: 'codex', scope: 'user', source: `/Users/me/${folder}/x/SKILL.md`, affects: { clients, scope: 'all', note: null } }, action: 'skill.remove' });
  const twins = [at('.agents/skills', ['codex', 'cursor']), at('.codex/skills', ['codex'])];
  assert.equal(offerLabel(twins[0], twins), 'Remove from Codex and Cursor (.agents/skills)…');
  assert.equal(offerLabel(twins[1], twins), 'Remove from Codex (.codex/skills)…');
});

test('a lone Remove gives way to an add; a lone switch still leads', () => {
  const remove = { def: { id: 'r', client: 'codex' }, action: 'skill.remove' };
  const add = { client: 'claude_code', add: { action: 'skill.install', project_only: true }, label: 'Add to Claude Code…' };
  assert.deepEqual(footerActions([remove], [], null, [add]), { lead: add, rest: [remove] });
  assert.deepEqual(footerActions([remove], [], null, []), { lead: remove, rest: [] });
  const off = { def: { id: 'p', client: 'claude_code' }, action: 'plugin.disable' };
  assert.deepEqual(footerActions([off], [], null, [add]), { lead: off, rest: [add] });
});

test('a server the Kitden gateway holds leads with Manage tools; Move waits under More', () => {
  const removeCursor = { def: { id: 'c', client: 'cursor' }, action: 'mcp.remove_direct' };
  const move = { items: ['c'], gateways: [{ kind: 'kitden' }] };
  const manage = { label: 'Manage tools', view: 'gateway', selected: { kind: 'mcp_server', name: 'files' } };
  assert.deepEqual(footerActions([removeCursor], [], move, [], manage), { lead: manage, rest: ['move', removeCursor] });
  // A problem still comes first; the link then stays with the other links.
  const duplicate = { level: 'warning', client: 'cursor', fix_action: 'mcp.remove_direct' };
  assert.deepEqual(footerActions([removeCursor], [duplicate], move, [], manage), { lead: removeCursor, rest: ['move'] });
  // What the tool switches change: every client that loads it through the gateway.
  const held = (client) => def({ client, kind: 'mcp_server', name: 'files', owner_client: 'kitden', via_gateway: 'kitden' });
  const definitions = [def({ client: 'cursor', kind: 'mcp_server', name: 'files' }), held('claude_code'), held('codex')];
  assert.equal(affectsText(affectsFor(manage, { definitions, project: '' }), ''), 'Changes Claude Code and Codex. All projects.');
  assert.equal(affectsText(affectsFor(manage, { definitions, project: site }), site), 'Changes Claude Code and Codex. In this project.');
});
