import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';

// details.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
// Node before 21 has no navigator; details.js must load there too.
delete globalThis.navigator;
const { DETAILS_ORDER, detailsOrder, fileScopeWords, layerState, originWords, scopeWords, techRows, whyLines } = await import('../../src/kitden/web/static/js/details.js');

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
  assert.deepEqual(whyLines([def({ client: 'codex', loads: false, enabled: 'unknown' })], null), ['Codex keeps its on/off state where Kitden cannot read it.']);
  assert.deepEqual(whyLines([def({ client: 'claude_code', scope: 'project', project: '/a/site', loads: false }), def({ client: 'claude_code', scope: 'project', project: '/a/api', loads: false })], null),
    ['It is in 2 projects; it loads only there.']);
  assert.deepEqual(whyLines([def({ client: 'codex', kind: 'instructions' })], null), []);
});

test('why names a folder that several clients read, in words', () => {
  const folder = '/Users/me/.agents/skills/code-review/SKILL.md';
  assert.deepEqual(whyLines([def({ client: 'codex', source: folder }), def({ client: 'cursor', owner_client: 'shared', source: folder })], null),
    ['Codex and Cursor load it from all projects.', 'One folder, read by Codex and Cursor.']);
  // Two folders, one per client: nothing shared to say.
  assert.deepEqual(whyLines([def({ client: 'codex', source: folder }), def({ client: 'cursor', source: '/Users/me/.cursor/skills/code-review/SKILL.md' })], null),
    ['Codex and Cursor load it from all projects.']);
});

test('why says a merge, a server in the Kitden gateway and a stand-in for unknown states', () => {
  assert.deepEqual(whyLines([def({ client: 'claude_code', kind: 'mcp_server', scope: 'project', project: site }), def({ client: 'claude_code', kind: 'mcp_server', loads: false, merged: true })], site),
    ['Claude Code loads it from this project.', 'In Claude Code, the ones from this project and from all projects are merged.']);
  const held = (client) => def({ client, kind: 'mcp_server', owner_client: 'kitden', via_gateway: 'kitden' });
  assert.deepEqual(whyLines([held('claude_code'), held('cursor')], null), ['Claude Code and Cursor load it through the Kitden gateway.']);
  assert.deepEqual(whyLines([def({ client: 'codex', loads: false, enabled: 'unknown' }), def({ client: 'cursor', loads: false, enabled: 'unknown' })], null),
    ['Codex and Cursor keep their on/off state where Kitden cannot read it.']);
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

test('a layer leaves the rule to the Why: no override sentence under it', () => {
  const loaded = { kind: 'mcp_server', enabled: 'on', loads: true };
  assert.equal(layerState({ ...loaded, why: 'Loads. It overrides the user definition.' }).why, '');
  assert.equal(layerState({ kind: 'plugin', enabled: 'on', loads: false, overridden: true, why: 'Does not load: the project definition overrides it.' }).why, '');
  assert.equal(layerState({ kind: 'mcp_server', enabled: 'on', loads: false, merged: true, why: 'Merged with the project definition; its fields win.' }).why, '');
  // What is not a rule between two definitions stays.
  const elsewhere = 'Does not load here: it belongs to another project.';
  assert.equal(layerState({ kind: 'skill', enabled: 'on', loads: false, why: elsewhere }).why, elsewhere);
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
