import assert from 'node:assert/strict';
import { test } from 'node:test';

// gateway-details.js needs only this from a browser to load; the card builders make a few
// nodes (client tiles, check boxes with an icon, the folded evidence), so a stand-in document keeps what they get.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
function fakeNode(tag) {
  const classes = new Set();
  const node = {
    tag, textContent: '', childNodes: [], attributes: {}, dataset: {}, style: { setProperty() {} },
    get className() { return [...classes].join(' '); },
    set className(value) { classes.clear(); for (const name of String(value).split(/\s+/).filter(Boolean)) classes.add(name); },
    classList: {
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      toggle: (name, on = !classes.has(name)) => (on ? classes.add(name) : classes.delete(name)),
      contains: (name) => classes.has(name),
    },
    listeners: {},
    append(...nodes) { node.childNodes.push(...nodes); },
    prepend(...nodes) { node.childNodes.unshift(...nodes); },
    replaceChildren(...nodes) { node.childNodes = [...nodes]; },
    get children() { return node.childNodes.filter((child) => typeof child === 'object'); },
    setAttribute(name, value) { node.attributes[name] = String(value); },
    getAttribute: (name) => (name in node.attributes ? node.attributes[name] : null),
    removeAttribute(name) { delete node.attributes[name]; },
    addEventListener(type, listener) { (node.listeners[type] ||= []).push(listener); },
    focus() { globalThis.document.activeElement = node; },
    querySelector: (selector) => (selector === ':scope > summary' ? node.childNodes.find((child) => child.tag === 'summary') || null : null),
  };
  return node;
}
globalThis.document = { createElement: fakeNode, createElementNS: (namespace, tag) => fakeNode(tag) };
// Every URL asked for: the cards are built from what the page has, and never read the map.
const asked = [];
globalThis.fetch = async (url) => { asked.push(url); return { ok: true, status: 200, json: async () => ({}) }; };

const { SETUP_NOTE, clientCard, gatewayCard, heldCard, outsideCard, reported, toolCard, toolState } = await import('../../src/kitden/web/static/js/gateway-details.js');
const { detailsCard, moveBody, projectChoice, syncTray } = await import('../../src/kitden/web/static/js/details.js');
const { cancelTray, onTray, tray } = await import('../../src/kitden/web/static/js/tray.js');
const { GATEWAY_NOTE } = await import('../../src/kitden/web/static/js/parts.js');
const { switchList, toolRows } = await import('../../src/kitden/web/static/js/tools.js');

// The words of a node: its own text, then its children's.
const textOf = (node) => (typeof node === 'string' ? node : node ? `${node.textContent}${node.childNodes.map(textOf).join('')}` : '');
const facts = (card) => card.facts.map((f) => [f.label, typeof f.value === 'string' ? f.value : f.text]);
const labels = (card) => card.actions.map((a) => a.label);

const entry = (client, state, fields = {}) => ({ client, state, item: null, enabled: true, ...fields });
const SETUP = [entry('claude_code', 'added'), entry('codex', 'added'), entry('cursor', 'missing')];
const CLIENTS = [
  { id: 'claude_code', status: 'found', version: '2.1.283', app_url: null },
  { id: 'codex', status: 'found', version: '0.159.2', app_url: 'codex://' },
  { id: 'cursor', status: 'found', version: '3.21.16', app_url: null },
];
const FOUND = ['claude_code', 'codex', 'cursor'];
const KITDEN = { id: 'kitden', kind: 'kitden', name: 'Kitden gateway', where: 'On this Mac', movable: true, servers: [{ name: 'files', kind: 'local', state: 'on' }, { name: 'tracker', kind: 'remote', state: 'on' }] };
const row = (name, client, items, fields = {}) => ({ name, clients: [client], columns: [client], items, stays: null, ...fields });
const GITHUB = row('github', 'claude_code', ['g']);
const DOCS = row('docs', 'claude_code', ['a']);
const DOCS_LOCAL = row('docs', 'codex', ['b']);
const FILES = row('files', 'cursor', ['c']);
const VIEW = { gateways: [KITDEN], connections: { kitden: { claude_code: ['files'], codex: ['files'], cursor: [] } }, used: ['kitden'], groups: { move: [DOCS, GITHUB], local: [DOCS_LOCAL, FILES], plugin: [] } };
const def = (id, client, fields = {}) => ({
  id, client, kind: 'mcp_server', scope: 'user', project: null, via_gateway: null, actions: ['mcp.remove_direct'],
  affects: { clients: [client], scope: 'all', note: null }, source: `/Users/me/.${client}.json`, key: 'mcpServers', summary: null, ...fields,
});
const PROJECTS = [{ id: 'p1', path: '/w/atlas', own_rules: 1 }, { id: 'p2', path: '/w/web', own_rules: 0 }];

test('an outside server offers move, adds and removes, and never reads the map', () => {
  asked.length = 0;
  const card = outsideCard(GITHUB, 'move', [def('g', 'claude_code', { summary: 'https://api.github.example.test/mcp' })], { view: VIEW, clients: FOUND });
  assert.deepEqual([card.kind, card.title], ['Server', 'github']);
  assert.deepEqual(labels(card), ['Move into the gateway…', '+ Add to Codex…', '+ Add to Cursor…', 'Remove from Claude Code…']);
  assert.deepEqual(card.actions.map((a) => Boolean(a.primary)), [true, false, false, false]);
  // One gateway can take it: the button is the move's own, so it can say "In preview".
  assert.deepEqual([card.actions[0].body, card.actions[0].run], [moveBody(KITDEN, ['g']), undefined]);
  assert.deepEqual(card.actions[1].body, { action: 'mcp.add', targets: [{ client: 'codex' }], params: { item: 'g' } });
  assert.deepEqual(card.actions[3].body, { action: 'mcp.remove_direct', targets: [{ item: 'g' }], params: {} });
  assert.deepEqual(facts(card), [['In', 'Claude Code'], ['Kind', 'Remote'], ['Gateway', "Outside · calls skip Kitden's rules"]]);
  assert.equal(card.why, "Claude Code calls it directly, so Kitden's tool rules do not reach it.");
  // The address waits under Technical details.
  assert.ok(textOf(card.technical).includes('https://api.github.example.test/mcp'));
  assert.deepEqual(asked, []);
});

test('a server in two groups adds and removes only its own entries; a gateway client gets no add', () => {
  const docs = outsideCard(DOCS, 'move', [def('a', 'claude_code'), def('b', 'codex')], { view: VIEW, clients: FOUND });
  assert.deepEqual(labels(docs), ['Move into the gateway…', '+ Add to Cursor…', 'Remove from Claude Code…']);
  assert.deepEqual(docs.actions[1].body.params, { item: 'a' });
  // Claude Code and Codex get files through the Kitden gateway: nothing to add anywhere.
  const via = { via_gateway: 'kitden', actions: [], affects: null };
  const files = outsideCard(FILES, 'local', [def('c', 'cursor'), def('k1', 'claude_code', via), def('k2', 'codex', via)], { view: VIEW, clients: FOUND });
  assert.deepEqual(labels(files), ['Move into the gateway…', 'Remove from Cursor…']);
  assert.deepEqual(facts(files)[1], ['Kind', 'Local']);
  // Two clients say "call"; a project's own entry is not a source for an add.
  const two = outsideCard(row('n8n', 'codex', ['n1', 'n2'], { columns: ['claude_code', 'codex'] }), 'local', [def('n1', 'claude_code', { scope: 'project', project: '/w/atlas' }), def('n2', 'codex')], { view: VIEW, clients: FOUND });
  assert.equal(two.why, "Claude Code and Codex call it directly, so Kitden's tool rules do not reach it.");
  assert.deepEqual(two.actions[1].body.params, { item: 'n2' });
});

test('a server that stays says why instead of Move; without a gateway a remote one can lose its entry', () => {
  const stays = "docs is in the project's own files; it stays there.";
  const kept = outsideCard({ ...DOCS, stays }, 'move', [def('a', 'claude_code')], { view: VIEW, clients: FOUND });
  assert.ok(!labels(kept).includes('Move into the gateway…'));
  assert.equal(textOf(kept.after), stays);
  const none = outsideCard(GITHUB, 'move', [def('g', 'claude_code')], { view: { ...VIEW, gateways: [] }, clients: FOUND });
  assert.deepEqual(labels(none), ['Remove direct entry…', '+ Add to Codex…', '+ Add to Cursor…', 'Remove from Claude Code…']);
  assert.deepEqual(none.actions[0].body, { action: 'mcp.remove_direct', targets: [{ item: 'g' }], params: {} });
  assert.equal(textOf(none.after), GATEWAY_NOTE);
  // A plugin's server stays with its plugin, and says so.
  const plugin = outsideCard(row('linear', 'claude_code', [], { stays: 'linear comes with a plugin; it stays with the plugin.' }), 'plugin', [def('l', 'claude_code', { actions: [] })], { view: VIEW, clients: FOUND });
  assert.deepEqual([labels(plugin), facts(plugin)[1]], [[], ['Kind', 'From a plugin']]);
  assert.equal(textOf(plugin.after), 'linear comes with a plugin; it stays with the plugin.');
});

test('a client without the entry offers set up; one with it off says so', () => {
  const cursor = clientCard('cursor', { setup: SETUP, clients: CLIENTS, view: VIEW });
  assert.deepEqual([cursor.kind, cursor.title], ['Client', 'Cursor']);
  assert.deepEqual(facts(cursor), [['Version', '3.21.16'], ['Kitden entry', 'Not set up'], ['Gateway', 'Not connected']]);
  assert.equal(cursor.why, 'Cursor does not use the Kitden gateway yet.');
  assert.deepEqual(labels(cursor), ['Set up in Cursor…']);
  assert.deepEqual([cursor.actions[0].primary, cursor.actions[0].body], [true, { action: 'setup_server.register', targets: [{ client: 'cursor' }], params: {} }]);
  const off = clientCard('claude_code', { setup: [entry('claude_code', 'added', { enabled: false })], clients: CLIENTS, view: VIEW });
  assert.deepEqual(facts(off).slice(1), [['Kitden entry', 'Off'], ['Gateway', 'Not connected']]);
  // Claude Code and Cursor keep their switch for an entry in their own settings (docs checked
  // 2026-10-24): the card says where to turn it on.
  assert.equal(off.why, "Claude Code has the kitden entry turned off, so it does not reach the gateway. Turn it on in Claude Code's own MCP settings.");
  assert.deepEqual(labels(off), []);
  // Codex turns an entry off with `enabled = false`: Kitden turns it on again, in a review.
  const codexOff = clientCard('codex', { setup: [entry('codex', 'added', { enabled: false })], clients: CLIENTS, view: VIEW });
  assert.equal(codexOff.why, 'Codex has the kitden entry turned off, so it does not reach the gateway.');
  assert.deepEqual(labels(codexOff), ['Turn it on in Codex…', 'Open ChatGPT']);
  assert.deepEqual([codexOff.actions[0].primary, codexOff.actions[0].body], [true, { action: 'setup_server.enable', targets: [{ client: 'codex' }], params: {} }]);
  // A plugin's entry that is off is the plugin's switch: only the sentence.
  const pluginOff = clientCard('codex', { setup: [entry('codex', 'plugin', { enabled: false })], clients: CLIENTS, view: VIEW });
  assert.deepEqual(labels(pluginOff), ['Open ChatGPT']);
  assert.ok(pluginOff.why.endsWith("Turn it on in Codex's own MCP settings."));
  // Connected, with its app's link scheme known: the app opens from here.
  const codex = clientCard('codex', { setup: SETUP, clients: CLIENTS, view: VIEW });
  assert.deepEqual(facts(codex).slice(1), [['Kitden entry', 'On'], ['Gateway', 'Connected']]);
  assert.equal(codex.why, 'Codex reaches the Kitden gateway through its kitden entry.');
  assert.deepEqual(labels(codex), ['Open ChatGPT']);
  // An old entry is set up again, and a client Kitden did not find says so.
  const old = clientCard('codex', { setup: [entry('codex', 'old', { item: 'codex:agentsetup' })], clients: [{ id: 'codex', status: 'not_found', version: null }], view: VIEW });
  assert.deepEqual(facts(old), [['Version', 'Not installed'], ['Kitden entry', 'Old'], ['Gateway', 'Not connected']]);
  assert.deepEqual(old.actions[0].body, { action: 'setup_server.update', targets: [{ item: 'codex:agentsetup' }], params: {} });
});

test('the Kitden gateway moves every outside server that can go, in one review', () => {
  const stays = "docs is in the project's own files; it stays there.";
  const view = { ...VIEW, groups: { move: [{ ...DOCS, stays }, GITHUB], local: [DOCS_LOCAL, FILES], plugin: [row('linear', 'claude_code', [], { stays: 'with the plugin' })] } };
  const card = gatewayCard(KITDEN, { view, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.deepEqual([card.kind, card.title, card.id], ['Gateway', 'Kitden gateway', 'On this Mac']);
  assert.match(card.actions[0].label, /^Move all \d+…$/);
  // docs is in two groups: it moves on its own, so neither of its rows is in "Move all".
  assert.deepEqual(labels(card), ['Move all 2…', 'Add another gateway…']);
  assert.deepEqual(card.actions[0].body, { action: 'gateway.move', targets: [{ item: 'g' }, { item: 'c' }], params: { gateway: 'kitden' } });
  assert.equal(card.actions[0].primary, true);
  assert.deepEqual(facts(card), [['Clients', '2 clients'], ['Servers', '2 servers'], ['Rules', '1 project has its own rules']]);
  assert.equal(card.why, 'The gateway controls only the servers in it. Direct entries and terminal tools are outside it.');
  assert.equal(card.warning, null);
  // Nothing left to move: only the add.
  const done = gatewayCard({ ...KITDEN, servers: [] }, { view: { ...VIEW, groups: { move: [], local: [], plugin: [] } }, setup: SETUP, projects: [], clients: FOUND });
  assert.deepEqual(labels(done), ['Add another gateway…']);
  assert.deepEqual(facts(done).slice(1), [['Servers', 'Nothing yet. Move a server in from the outside group.'], ['Rules', 'No project has its own rules']]);
  // "Add another gateway…" shows the form in the column.
  assert.ok(gatewayCard(KITDEN, { view, setup: SETUP, projects: PROJECTS, clients: FOUND, adding: true }).after);
});

test("Move all leaves out a name set up differently in two clients, as the medium sample's docs", () => {
  // The medium sample: docs is remote in Claude Code and local in Codex.
  const view = { ...VIEW, groups: {
    move: [row('analytics', 'codex', ['an']), DOCS, GITHUB],
    local: [row('browser-tools', 'cursor', ['bt']), DOCS_LOCAL, FILES, row('n8n', 'cursor', ['n8'])],
    plugin: [],
  } };
  const card = gatewayCard(KITDEN, { view, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.equal(card.actions[0].label, 'Move all 5…');
  assert.deepEqual(card.actions[0].body.targets.map((t) => t.item), ['an', 'g', 'bt', 'c', 'n8']);
  // Only the pair left: nothing to move all of.
  const pair = gatewayCard(KITDEN, { view: { ...VIEW, groups: { move: [DOCS], local: [DOCS_LOCAL], plugin: [] } }, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.deepEqual(labels(pair), ['Add another gateway…']);
});

test('Move all leaves out a name set up differently in two clients of one group', () => {
  const stays = 'files is set up differently in Codex and Cursor; keep one first.';
  const files = { ...row('files', 'codex', ['c', 'd']), clients: ['codex', 'cursor'], columns: ['codex', 'cursor'], stays };
  const view = { ...VIEW, groups: { move: [GITHUB], local: [files], plugin: [] } };
  const card = gatewayCard(KITDEN, { view, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.equal(card.actions[0].label, 'Move all 1…');
  assert.deepEqual(card.actions[0].body.targets.map((t) => t.item), ['g']);
});

test('rules count projects in words, and an unread list is not known', () => {
  const two = [...PROJECTS, { id: 'p3', path: '/w/site', own_rules: 3 }];
  assert.deepEqual(facts(gatewayCard(KITDEN, { view: VIEW, setup: SETUP, projects: two, clients: FOUND })).at(-1), ['Rules', '2 projects have their own rules']);
  assert.deepEqual(facts(gatewayCard(KITDEN, { view: VIEW, setup: SETUP, projects: null, clients: FOUND })).at(-1), ['Rules', 'Not known']);
});

test('a client Kitden could not read the setup for is not known, not not connected', () => {
  const card = clientCard('codex', { setup: null, clients: CLIENTS, view: VIEW });
  assert.deepEqual(facts(card).slice(1), [['Kitden entry', 'Not known'], ['Gateway', 'Not known']]);
  assert.equal(card.why, 'Kitden could not read which clients use it.');
  assert.deepEqual(labels(card), ['Open ChatGPT']);
});

test('the Kitden gateway says what it could not read', () => {
  const problem = 'Could not read the Kitden gateway settings.';
  const broken = gatewayCard({ ...KITDEN, servers: [], problem }, { view: VIEW, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.equal(broken.warning, problem);
  assert.ok(!facts(broken).some(([label]) => label === 'Servers'));
  const unknown = gatewayCard(KITDEN, { view: VIEW, setup: null, projects: PROJECTS, clients: FOUND });
  assert.equal(unknown.warning, 'Kitden could not read which clients use it.');
  assert.ok(!facts(unknown).some(([label]) => label === 'Clients'));
});

test('a registered gateway says what it holds and offers to take the clients over', () => {
  const obot = { id: 'gw-1', kind: 'obot', url: 'http://127.0.0.1:8080/mcp-connect/x', ui_url: 'http://127.0.0.1:8080', movable: false, managed: true };
  const meta = { id: 'gw-2', kind: 'metamcp', url: 'http://127.0.0.1:12008/metamcp/local/mcp', movable: true, managed: true };
  const view = { ...VIEW, gateways: [KITDEN, obot, meta], used: ['gw-2', 'kitden'],
    connections: { ...VIEW.connections, 'gw-1': { claude_code: [], codex: [], cursor: [] }, 'gw-2': { claude_code: [], codex: ['x'], cursor: [] } } };
  const card = gatewayCard(obot, { view, setup: SETUP, projects: PROJECTS, clients: FOUND, held: { servers: [{ name: 'x', type: 'remote', url: 'http://h/x' }] } });
  assert.deepEqual([card.kind, card.title], ['Gateway', 'Obot']);
  assert.deepEqual(facts(card), [['Clients', 'No clients yet'], ['Servers', '1 server'], ['State', 'Not used']]);
  assert.deepEqual(labels(card), ['Open Obot ↗', 'Use this gateway…']);
  assert.deepEqual(card.actions[1].body, { action: 'gateway.switch', targets: [], params: { gateway: 'gw-1', name: 'obot' } });
  // Claude Code and Cursor use no registered gateway: they can connect here.
  assert.ok(textOf(card.after).includes('Connect clients'));
  assert.ok(textOf(card.technical).includes(obot.url));
  // The gateway in use: its clients and no switch; a failed read says so.
  const used = gatewayCard(meta, { view, setup: SETUP, projects: PROJECTS, clients: FOUND, held: { servers: null, error: 'Could not read what the gateway holds.' } });
  assert.deepEqual(facts(used), [['Clients', '1 client'], ['Servers', 'Could not read what the gateway holds.'], ['State', 'Used']]);
  assert.ok(!labels(used).includes('Use this gateway…'));
  // Saved without what Kitden needs to read it: the sentence says what to add.
  const unread = gatewayCard({ ...obot, managed: false }, { view, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.equal(unread.why, 'To see what it holds from here, save the gateway again with the name of the variable that holds an Obot API key.');
});

// Tools and servers in the Kitden gateway ---------------------------------------------------

// A call today at 14:02, in local time, as the file keeps it (UTC).
const TODAY_1402 = (() => { const at = new Date(); at.setHours(14, 2, 0, 0); return at.toISOString(); })();
const LINKED = ['claude_code', 'codex'];
const HELD_GITHUB = { name: 'github', kind: 'remote', state: 'on' };
const tool = (fields) => ({ name: 'push_files', title: 'Push files', state: 'off', effective: 'off', hint: 'writes', origin: 'global', origin_from: null, ...fields });
// The known projects, as the menu reads them, and the server's rules in each: what
// /api/gateway/tools answers (`states`: project id -> the tool's state; `server`: the server's).
const CHOICE = [{ id: 'a', path: '/w/atlas', own_rules: 1, exists: true }, { id: 'm', path: '/w/mcp-gateway', own_rules: 0, exists: true }, { id: 'w', path: '/w/atlas/web', own_rules: 0, exists: true }];
const rulesFor = (states, { name = 'push_files', shared = 'on', server = {} } = {}) => ({
  shared,
  projects: Object.entries(states).map(([id, state]) => ({ id, server: server[id] || 'on', tools: { [name]: state } })),
});

test('a tool off for all projects offers to turn it on, for all or in one project', () => {
  const rules = rulesFor({ a: 'off', m: 'off', w: 'off' });
  const card = toolCard(tool(), { name: 'github', kind: 'remote', state: 'on' }, { linked: ['claude_code', 'codex'], picked: '', folder: '', detail: { shared: 'off', calls: { count: 12, last: TODAY_1402 } }, rules, projects: CHOICE });
  assert.deepEqual([card.kind, card.title, card.id], ['Tool', 'Push files', 'push_files']);
  assert.deepEqual(card.facts.map((f) => [f.label, typeof f.value === 'string' ? f.value : f.text]), [
    ['Server', 'github · Remote'], ['State', 'Off'], ['Comes from', 'All projects'], ['Reported', 'May write'], ['Clients', '2 clients'], ['Calls', '12 calls · last today 14:02']]);
  assert.equal(card.why, "Claude Code and Codex can't call this tool through Kitden by the shared rule.");
  assert.deepEqual(card.actions.map((a) => a.label), ['Turn on for all projects…', 'Turn on in one project…']);
  assert.deepEqual(card.actions[0].body, { action: 'gateway.rule', targets: [], params: { server: 'github', tool: 'push_files', state: 'on', project: null } });
  // "In one project" shows the project choice in the column first.
  assert.equal(typeof card.actions[1].run, 'function');
  // Without calls there is no Calls fact; without a title the name is the title. Without the
  // rules of each project Kitden cannot say which project a change would reach: no choice.
  const quiet = toolCard(tool({ title: null, state: 'on', effective: 'on' }), HELD_GITHUB, { linked: LINKED, picked: '', folder: '', detail: { shared: 'on' }, projects: CHOICE });
  assert.deepEqual([quiet.title, quiet.id, facts(quiet).map(([label]) => label)], ['push_files', null, ['Server', 'State', 'Comes from', 'Reported', 'Clients']]);
  assert.equal(quiet.why, 'Claude Code and Codex can call this tool through Kitden by the shared rule.');
  assert.deepEqual(labels(quiet), ['Turn off for all projects…']);
});

// The medium sample with All projects: atlas turns write_file off, atlas/web follows atlas and
// turns search_files off itself; old-app, sandbox and website follow the shared rule.
const MEDIUM_PROJECTS = [
  { id: 'atlas', path: '/h/work/atlas', own_rules: 1, exists: true }, { id: 'web', path: '/h/work/atlas/web', own_rules: 1, exists: true },
  { id: 'old', path: '/h/work/old-app', own_rules: 0, exists: false }, { id: 'sand', path: '/h/work/sandbox', own_rules: 0, exists: true },
  { id: 'site', path: '/h/work/website', own_rules: 0, exists: true },
];
const MEDIUM_RULES = {
  shared: 'on',
  projects: [['atlas', 'off', 'on'], ['web', 'off', 'off'], ['old', 'on', 'on'], ['sand', 'on', 'on'], ['site', 'on', 'on']]
    .map(([id, write, search]) => ({ id, server: 'on', tools: { write_file: write, search_files: search } })),
};
const FILES_ROW = { name: 'files', kind: 'local', state: 'on' };
const medium = (name, extra = {}) => toolCard({ name, title: null, state: 'on', effective: 'on', hint: 'writes', origin: 'default', origin_from: null }, FILES_ROW, { linked: LINKED, picked: '', folder: '', detail: { shared: 'on' }, rules: MEDIUM_RULES, projects: MEDIUM_PROJECTS, ...extra });

test('in one project offers only the projects it would change, and all projects says who differs', () => {
  const write = medium('write_file', { choosing: true });
  assert.equal(write.why, 'Claude Code and Codex can call this tool through Kitden by the shared rule. 2 projects decide otherwise.');
  assert.deepEqual(labels(write), ['Turn off for all projects…', 'Turn off in one project…']);
  // atlas has write_file off already, and atlas/web follows it: neither is offered.
  assert.deepEqual(write.after.childNodes.map(textOf), ['old-appFolder missing', 'sandbox', 'website']);
  assert.equal(medium('search_files').why, 'Claude Code and Codex can call this tool through Kitden by the shared rule. 1 project decides otherwise.');
  // Every project has it off already: nothing to turn off in one project.
  const off = { ...MEDIUM_RULES, projects: MEDIUM_RULES.projects.map((p) => ({ ...p, tools: { write_file: 'off' } })) };
  const none = medium('write_file', { rules: off });
  assert.deepEqual(labels(none), ['Turn off for all projects…']);
  assert.equal(none.why, 'Claude Code and Codex can call this tool through Kitden by the shared rule. 5 projects decide otherwise.');
  // In a project the sentence names it, and says nothing about the others.
  const atlas = toolCard({ name: 'write_file', title: null, state: 'off', effective: 'off', hint: 'writes', origin: 'project', origin_from: null }, FILES_ROW, { linked: LINKED, picked: 'atlas', folder: 'atlas', detail: { shared: 'on' }, rules: MEDIUM_RULES, projects: MEDIUM_PROJECTS });
  assert.equal(atlas.why, "Claude Code and Codex can't call this tool through Kitden in atlas.");
  assert.deepEqual(labels(atlas), ['Use the shared rule…', 'Turn off for all projects…', 'Turn on in one project…']);
});

test("a project's own rule leads with the shared rule, or its parent's", () => {
  const rules = rulesFor({ a: 'off', m: 'on', w: 'on' });
  const own = toolCard(tool({ state: 'on', effective: 'on', origin: 'project' }), HELD_GITHUB, { linked: LINKED, picked: 'm', folder: 'mcp-gateway', detail: { shared: 'off', follows: null }, rules, projects: CHOICE });
  assert.deepEqual([own.facts[1].value, own.facts[2].value], ['On in this project', 'This project · mcp-gateway']);
  assert.equal(own.facts[2].accent, true);
  assert.deepEqual(own.actions.map((a) => a.label), ['Use the shared rule…', 'Turn on for all projects…', 'Turn off in one project…']);
  assert.deepEqual(own.actions.map((a) => Boolean(a.primary)), [true, false, false]);
  assert.deepEqual(own.actions[0].body, { action: 'gateway.rule', targets: [], params: { server: 'github', tool: 'push_files', state: null, project: 'm' } });
  assert.equal(own.why, 'Claude Code and Codex can call this tool through Kitden in mcp-gateway.');
  const nested = toolCard(tool({ state: 'on', effective: 'on', origin: 'project' }), HELD_GITHUB, { linked: LINKED, picked: 'w', folder: 'web', detail: { shared: 'off', follows: 'atlas' }, rules, projects: CHOICE });
  assert.equal(nested.actions[0].label, "Use atlas's rule…");
  // A rule from a parent folder says so; with no client on the gateway the sentence says that.
  const parent = toolCard(tool({ origin: 'parent', origin_from: 'atlas' }), HELD_GITHUB, { linked: [], picked: 'w', folder: 'web', detail: { shared: 'on' }, rules, projects: CHOICE });
  assert.deepEqual([parent.facts[1].value, parent.facts[2].value, parent.facts[4].text], ['Off', 'From atlas', 'No clients yet']);
  assert.equal(parent.why, 'No client uses the Kitden gateway yet.');
  assert.deepEqual(labels(parent), ['Turn off for all projects…', 'Turn on in one project…']);
  // Without the clients' setup Kitden does not know who can call it.
  const unknown = toolCard(tool(), HELD_GITHUB, { linked: null, picked: '', folder: '', detail: { shared: 'off' } });
  assert.deepEqual([unknown.facts[4].value, unknown.why], ['Not known', 'Kitden could not read which clients use it.']);
});

test('a tool of a server that is off says so and offers nothing', () => {
  const card = toolCard(tool({ state: 'on', effective: 'off', why: 'server_off' }), { name: 'files', kind: 'local', state: 'off' }, { linked: LINKED, picked: 'w', folder: 'web', detail: {} });
  assert.equal(card.facts[1].value, 'Off · server off');
  assert.equal(card.facts[0].value, 'files · Local');
  assert.equal(card.why, 'files is off in web, so none of its tools can be called.');
  assert.deepEqual(card.actions.map((a) => a.label), ['Open files']);
  assert.equal(typeof card.actions[0].run, 'function');
  // With All projects: off by the shared rule, and the projects that turn the server on.
  const rules = rulesFor({ a: 'on', m: 'on', w: 'on' }, { shared: 'off', server: { a: 'on', m: 'off', w: 'on' } });
  const shared = toolCard(tool({ state: 'on', effective: 'off', why: 'server_off' }), { name: 'files', kind: 'local', state: 'off' }, { linked: LINKED, picked: '', folder: '', detail: { shared: 'on' }, rules });
  assert.equal(shared.why, 'files is off by the shared rule, so none of its tools can be called. 2 projects decide otherwise.');
});

test('a tool says what it is reported to do and where its state comes from', () => {
  assert.equal(reported('reads', 'server'), 'Read only');
  assert.equal(reported('writes', 'server'), 'May write');
  assert.equal(reported('may write', 'name'), 'Not reported · its name suggests it writes');
  assert.equal(reported('unknown', null), 'Not reported');
  // The Gateway's short tool list says where a hint comes from by its word alone.
  assert.equal(reported('reads'), 'Read only');
  assert.equal(reported('may write'), 'Not reported · its name suggests it writes');
  assert.equal(toolState(tool({ effective: 'on', origin: 'project' }), ''), 'On');
  assert.equal(toolState(tool({ origin: 'project' }), 'w'), 'Off in this project');
  assert.equal(toolState({ state: 'off' }, ''), 'Off');
  // A strict server's new tool waits; the server's own words wait under Technical details.
  const waiting = toolCard(tool({ origin: 'strict', hint: 'unknown' }), HELD_GITHUB, { linked: LINKED, picked: '', folder: '', detail: { shared: 'off', calls: null, description: 'Pushes files.' } });
  assert.deepEqual(facts(waiting).slice(2, 4), [['Comes from', 'New · waits'], ['Reported', 'Not reported']]);
  assert.ok(textOf(waiting.technical).includes('Pushes files.'));
});

// The medium sample's files, with All projects picked: write_file writes and is on.
const FILES_HELD = {
  name: 'files', kind: 'local', state: 'on', differs: false, origin: 'default', origin_from: null, plain_secrets: true, tools: 4,
  tool_list: [
    { name: 'read_file', title: null, state: 'on', effective: 'on', hint: 'reads', origin: 'default', origin_from: null },
    { name: 'write_file', title: null, state: 'on', effective: 'on', hint: 'writes', origin: 'default', origin_from: null },
    { name: 'delete_file', title: null, state: 'off', effective: 'off', hint: 'may write', origin: 'global', origin_from: null },
    { name: 'search_files', title: null, state: 'on', effective: 'on', hint: 'unknown', origin: 'default', origin_from: null },
  ],
  on_count: 3, on_in: 0, projects: 2,
};

// The server's /api/gateway/tools answer for files with All projects picked: read_file has a
// title and reads, write_file writes, delete_file may write by its name, search_files says nothing.
const answerTool = (name, fields = {}) => ({ name, title: null, hint: 'unknown', hint_from: null, description: '', calls: null, new: false, state: 'on', effective: 'on', differs: false, follows: null, origin: 'default', origin_from: null, ...fields });
const FILES_TOOLS = {
  server: 'files', state: 'on', differs: false, follows: null, origin: 'default', origin_from: null, shared: 'on', strict: false, problem: null,
  projects: MEDIUM_RULES.projects,
  tools: [
    answerTool('read_file', { title: 'Read file', hint: 'reads', hint_from: 'server', description: 'Reads one file.' }),
    answerTool('write_file', { hint: 'writes', hint_from: 'server' }),
    answerTool('delete_file', { hint: 'may write', hint_from: 'name', state: 'off', effective: 'off', origin: 'global' }),
    answerTool('search_files'),
  ],
};
const held = (server, extra = {}) => heldCard(server, { linked: LINKED, picked: '', folder: '', view: VIEW, clients: FOUND, detail: FILES_TOOLS, projects: MEDIUM_PROJECTS, ...extra });
// A card's tool list: its head, any quiet line, and each row as [look, name, its lines…, switch on].
const listOf = (card) => card.list.children.find((node) => node.className === 'sw-list');
const listRows = (card) => listOf(card).children.map((row) => [row.className, ...row.children[0].children.map(textOf), row.children[1].attributes['aria-checked']]);
const listLines = (card) => card.list.children.filter((node) => node.className !== 'sw-list').map(textOf);

// A press, and what it set off.
const click = async (node) => {
  for (const listener of node.listeners.click || []) listener({});
  await new Promise((resolve) => setTimeout(resolve, 0));
};
// A stand-in server for the tray (a batch preview answers one row per request; `sent` keeps every
// address), and the controls under `nodes()` following the tray, as initPanel makes them.
async function withTray(nodes, run) {
  const saved = { document: globalThis.document, fetch: globalThis.fetch };
  const sent = [];
  const all = (node) => (node && typeof node === 'object' ? [node, ...node.childNodes.flatMap(all)] : []);
  const drawer = { querySelectorAll: (selector) => (selector === '[data-tray]' ? nodes().flatMap(all).filter((node) => node.dataset && node.dataset.tray) : []) };
  globalThis.document = { ...saved.document, querySelector: (selector) => (selector === '#drawer' ? drawer : null) };
  globalThis.fetch = async (url, options = {}) => {
    sent.push(url);
    if (url !== '/api/batch/preview') return Response.json({});
    const { requests } = JSON.parse(options.body);
    return Response.json({
      id: `c${sent.length}`, action: 'batch', state: 'previewed', error: null, undo_note: null, steps: requests.map(() => ({ client: 'kitden', name: 'files' })),
      rows: requests.map((r, at) => ({ id: r.id, kind: r.kind, title: r.title, detail: '', project: null, steps: [at], after: [] })),
    });
  };
  const stop = onTray(syncTray);
  try {
    await run(nodes(), sent);
  } finally {
    await cancelTray();
    stop();
    Object.assign(globalThis, saved);
  }
}

test('the server panel lists its tools with a switch each and a Whole server row', () => {
  const card = held(FILES_HELD);
  assert.deepEqual([card.kind, card.title, card.id], ['Server', 'files', 'Local · in the Kitden gateway']);
  assert.equal(held({ ...FILES_HELD, kind: 'remote' }).id, 'Remote · in the Kitden gateway');
  assert.deepEqual(facts(card), [['Tools', '3 of 4 on'], ['Comes from', 'All projects'], ['Clients', '2 clients']]);
  assert.equal(card.why, undefined);
  assert.deepEqual(listLines(card), ['Tools · All projects']);
  assert.deepEqual(listRows(card), [
    ['sw-row whole', 'Whole server', '3 of 4 tools on', 'true'],
    ['sw-row', 'read_file', 'Read file · Reads only', 'true'],
    ['sw-row', 'write_file', 'May write', 'true'],
    ['sw-row', 'delete_file', 'May write', 'false'],
    // The server says nothing of what search_files does: no word.
    ['sw-row', 'search_files', 'true'],
  ]);
  // The tool's name is mono, where its word comes from waits in hover text, and its description
  // waits in its own panel.
  const read = listOf(card).children[1].children[0];
  assert.deepEqual([read.children[0].children[0].tag, read.children[1].title, read.children.length], ['code', 'from the server', 2]);
  // Each switch adds the rule for all projects; the list sits in the body, under the facts.
  const [, body] = detailsCard(card);
  assert.deepEqual(body.children.map((node) => node.className), ['facts', 'tools']);
  // A server that is off: every tool is off, and the list says why the tools still show a state.
  const allOff = { ...FILES_TOOLS, state: 'off', tools: FILES_TOOLS.tools.map((t) => ({ ...t, effective: 'off', why: 'server_off' })) };
  const off = held({ ...FILES_HELD, state: 'off', on_count: 0 }, { detail: allOff });
  assert.deepEqual(facts(off)[0], ['Tools', '0 of 4 on']);
  assert.deepEqual(listRows(off)[0], ['sw-row whole', 'Whole server', 'Every tool is off', 'false']);
  assert.deepEqual(listLines(off), ['Tools · All projects', 'files is off by the shared rule, so none of its tools are offered.']);
  // Off by the shared rule but on in two projects: the list says so, as the map block does.
  const someOn = { ...allOff, shared: 'off', projects: MEDIUM_RULES.projects.map((p, at) => ({ ...p, server: at < 2 ? 'on' : 'off' })) };
  assert.deepEqual(listLines(held({ ...FILES_HELD, state: 'off', on_count: 0, on_in: 2 }, { detail: someOn }))[1], 'files is off by the shared rule, so none of its tools are offered. 2 projects decide otherwise.');
  // In a project it names the project, and nothing else.
  assert.deepEqual(listLines(held({ ...FILES_HELD, state: 'off', on_count: 0 }, { picked: 'web', folder: 'web', detail: someOn }))[1], 'files is off in web, so none of its tools are offered there.');
  // Before Kitden knows its tools: the facts say so and the list asks for a refresh.
  const unknown = held({ ...FILES_HELD, tool_list: [], on_count: 0, tools: null }, { detail: { ...FILES_TOOLS, tools: [] } });
  assert.deepEqual(facts(unknown)[0], ['Tools', 'Not known yet']);
  assert.deepEqual(listRows(unknown), [['sw-row whole', 'Whole server', 'true']]);
  assert.deepEqual(listLines(unknown).at(-1), 'Kitden does not know its tools yet. Refresh tools asks the server.');
  // Without the server's answer there is no list to draw; the card says it could not load.
  assert.equal(held(FILES_HELD, { detail: {} }).list, null);
  // The Library lists the same rows, and keeps a tool's description, in two lines at most.
  const library = switchList(toolRows(FILES_TOOLS, null), { server: 'files', project: null });
  assert.deepEqual(library.children[1].children[0].children.map(textOf), ['read_file', 'Read file · Reads only', 'Reads one file.']);
});

test('a tool with its own rule in this project offers Use all projects', async () => {
  // In atlas: files has a rule of its own, write_file is off there; in web it follows atlas.
  const atlas = {
    ...FILES_TOOLS, differs: true, origin: 'project',
    tools: FILES_TOOLS.tools.map((t) => (t.name === 'write_file' ? { ...t, state: 'off', effective: 'off', differs: true, origin: 'project' } : t)),
  };
  const card = held({ ...FILES_HELD, origin: 'project', on_count: 2 }, { picked: 'atlas', folder: 'atlas', detail: atlas });
  assert.deepEqual(facts(card)[1], ['Comes from', 'This project · atlas']);
  assert.equal(card.facts[1].accent, true);
  assert.deepEqual(listLines(card), ['Tools · atlas']);
  // Only the tool's row says it differs; the server's own rule goes back under More.
  assert.deepEqual(listRows(card).slice(0, 3), [
    ['sw-row whole', 'Whole server', '2 of 4 tools on', 'true'],
    ['sw-row', 'read_file', 'Read file · Reads only', 'true'],
    ['sw-row', 'write_file', 'May write', 'Differs from all projects · Use all projects', 'false'],
  ]);
  assert.equal(card.more[0].label, 'Use the shared rule…');
  const web = held({ ...FILES_HELD, on_count: 2 }, { picked: 'web', folder: 'web', detail: { ...atlas, differs: false, origin: 'parent', tools: atlas.tools.map((t) => (t.differs ? { ...t, follows: 'atlas' } : t)) } });
  assert.equal(listRows(web)[2][3], 'Differs from atlas · Use atlas');
  // A press on it adds the rule back to all projects for this project, and the switch rests pending.
  await withTray(() => [card.list], async () => {
    const row = listOf(card).children[2];
    const use = row.children[0].children[2].children.at(-1);
    await click(use);
    assert.deepEqual(tray.rows.map((r) => r.body), [{ action: 'gateway.rule', targets: [], params: { server: 'files', tool: 'write_file', state: null, project: 'atlas' } }]);
    assert.deepEqual([textOf(use), use.attributes['aria-disabled'], row.children[1].className], ['In preview', 'true', 'switch pending']);
  });
});

test('a tool switch pressed twice leaves the tray as it was', async () => {
  const card = held(FILES_HELD);
  await withTray(() => [card.list], async (nodes, sent) => {
    const toggle = listOf(card).children[2].children[1];
    assert.deepEqual([toggle.className, toggle.attributes['aria-label']], ['switch', 'Turn off write_file of files in all projects…']);
    await click(toggle);
    assert.deepEqual(tray.rows.map((r) => [r.key, r.body.params.state]), [['rule:files/write_file@', 'off']]);
    assert.deepEqual([toggle.className, toggle.attributes['aria-checked'], toggle.attributes['aria-label']], ['switch pending', 'true', 'Turn off write_file of files in all projects… (in preview)']);
    // The second press takes its row out: the tray is empty, the server forgets the preview, and
    // the switch is back as it was.
    await click(toggle);
    assert.deepEqual(tray.rows, []);
    assert.ok(sent.some((url) => url.endsWith('/cancel')), sent.join(' '));
    assert.deepEqual([toggle.className, toggle.attributes['aria-checked'], toggle.attributes['aria-label']], ['switch', 'true', 'Turn off write_file of files in all projects…']);
    // The Whole server switch is the server's rule for all projects.
    await click(listOf(card).children[0].children[1]);
    assert.deepEqual(tray.rows.map((r) => r.body), [{ action: 'gateway.rule', targets: [], params: { server: 'files', tool: null, state: 'off', project: null } }]);
  });
});

test("every action of today's server panel is still there, under More", () => {
  const card = held(FILES_HELD, { detail: { ...FILES_TOOLS, ...MEDIUM_RULES } });
  // The panel's own button steps to the client choice; nothing else stands beside it.
  assert.deepEqual(card.actions.map((a) => [a.label, typeof a.run, Boolean(a.primary)]), [['Move out of the gateway…', 'function', false]]);
  assert.deepEqual(card.more.map((a) => a.label), [
    'Turn off in one project…', 'Turn strict mode on…', 'Turn off every writing tool…', 'Refresh tools',
    'Remove from the Kitden gateway…', 'Put back in Claude Code…', 'Put back in Codex…', 'Put back in Cursor…', 'Move secrets to the Keychain…',
  ]);
  const body = (label) => card.more.find((a) => a.label === label).body;
  assert.deepEqual(body('Turn strict mode on…'), { action: 'gateway.strict', targets: [], params: { server: 'files', state: 'on' } });
  assert.deepEqual(body('Turn off every writing tool…'), { action: 'gateway.rules', targets: [], params: { server: 'files', tools: ['write_file'], state: 'off', project: null } });
  assert.deepEqual(body('Remove from the Kitden gateway…'), { action: 'gateway.remove', targets: [], params: { server: 'files' } });
  assert.deepEqual(body('Put back in Codex…'), { action: 'gateway.put_back', targets: [{ client: 'codex' }], params: { server: 'files' } });
  assert.deepEqual(body('Move secrets to the Keychain…'), { action: 'gateway.keychain', targets: [], params: { server: 'files' } });
  // Claude Code and Codex reach files through the Kitden gateway: the Library has its row.
  assert.ok(textOf(card.after).includes('Compare across clients'));
  // Every project has the server on: "in one project" offers each of them.
  const choosing = held(FILES_HELD, { view: null, detail: { ...FILES_TOOLS, ...MEDIUM_RULES }, choosing: true });
  assert.equal(choosing.after.childNodes.length, MEDIUM_PROJECTS.length);
  // In a project with a rule of its own: its parent's rule back, and the rule for all projects.
  const off = { ...FILES_HELD, state: 'off', origin: 'project', on_count: 0, projects: 1 };
  const rules = rulesFor({ a: 'on', m: 'on', w: 'on' }, { server: { w: 'off' } });
  const web = held(off, { picked: 'w', folder: 'web', detail: { ...FILES_TOOLS, state: 'off', strict: true, follows: 'atlas', ...rules }, projects: CHOICE });
  // While it is off no writing tool can be called: nothing to turn off.
  assert.deepEqual(web.more.slice(0, 5).map((a) => a.label), ["Use atlas's rule…", 'Turn off for all projects…', 'Turn on in one project…', 'Turn strict mode off…', 'Refresh tools']);
  assert.deepEqual(web.more[0].body, { action: 'gateway.rule', targets: [], params: { server: 'files', tool: null, state: null, project: 'w' } });
  assert.deepEqual(web.more[1].body, { action: 'gateway.rule', targets: [], params: { server: 'files', tool: null, state: 'off', project: null } });
  // The server's answer did not come: no switches, so the rule for all projects waits under More.
  const unread = held(FILES_HELD, { detail: {} });
  assert.equal(unread.list, null);
  assert.deepEqual(unread.more[0], { label: 'Turn off for all projects…', body: { action: 'gateway.rule', targets: [], params: { server: 'files', tool: null, state: 'off', project: null } } });
  // No client Kitden can write: no move out; without each project's rules, no choice.
  const alone = held(FILES_HELD, { clients: [], detail: { ...FILES_TOOLS, projects: undefined } });
  assert.deepEqual([alone.actions, alone.more.map((a) => a.label).includes('Turn off in one project…')], [[], false]);
});

// The column's choice offers projects by folder name, never All projects.
const press = (node, key) => {
  const event = { key, stopped: false, preventDefault() {}, stopPropagation() { event.stopped = true; } };
  for (const listener of node.listeners.keydown || []) listener(event);
  return event;
};
const chosen = (box) => box.childNodes.filter((o) => o.attributes['aria-selected'] === 'true').map(textOf);

test('a project choice row is a menu row: a folder icon, the name over its sub line, the count apart', () => {
  const rows = [{ id: 'g', path: '/w/gone', own_rules: 2, exists: false }, CHOICE[1]];
  const [missing, plain] = projectChoice(rows, 'g', () => {}).childNodes;
  const parts = (row) => row.childNodes.map((c) => c.dataset.icon || c.className);
  assert.deepEqual(parts(missing), ['folder', 'where-tx', 'where-count']);
  assert.deepEqual(missing.childNodes[1].childNodes.map((c) => [c.className, c.textContent]), [['where-label', 'gone'], ['where-sub', 'Folder missing']]);
  assert.equal(missing.childNodes[2].textContent, '2 own rules');
  // No count and no sub line: the icon and the name only. The choice shows no check; it picks nothing yet.
  assert.deepEqual(parts(plain), ['folder', 'where-tx']);
  assert.deepEqual(plain.childNodes[1].childNodes.map((c) => c.className), ['where-label']);
});

test('the project choice starts on the picked project', () => {
  const picks = [];
  const box = projectChoice(CHOICE, 'm', (id) => picks.push(id));
  assert.equal(box.attributes.role, 'listbox');
  assert.deepEqual(box.childNodes.map(textOf), ['atlas1 own rule', 'mcp-gateway', 'web']);
  assert.deepEqual(chosen(box), ['mcp-gateway']);
  assert.equal(box.attributes['aria-activedescendant'], box.childNodes[1].id);
  press(box, 'Enter');
  assert.deepEqual(picks, ['m']);
  // The menu's keys move; a click picks too.
  press(box, 'ArrowDown');
  assert.deepEqual(chosen(box), ['web']);
  press(box, 'Enter');
  box.childNodes[0].listeners.click[0]();
  assert.deepEqual(picks, ['m', 'w', 'a']);
  // Escape closes only the choice, not the Details around it.
  assert.equal(press(box, 'Escape').stopped, true);
  assert.equal(box.hidden, true);
  // With All projects picked it starts on the first project.
  assert.deepEqual(chosen(projectChoice(CHOICE, '', () => {})), ['atlas1 own rule']);
  // A picked project the choice does not offer is not added to it: it starts on the first.
  const offered = projectChoice(CHOICE.filter((p) => p.id !== 'm'), 'm', () => {});
  assert.deepEqual([offered.childNodes.map(textOf), chosen(offered)], [['atlas1 own rule', 'web'], ['atlas1 own rule']]);
});

test("a card's change waits in the tray with its note, and its button says In preview", async () => {
  const sent = [];
  const before = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    sent.push(url);
    if (url !== '/api/batch/preview') return Response.json({});
    const { requests } = JSON.parse(options.body);
    return Response.json({
      id: 'c1', action: 'batch', state: 'previewed', error: null, undo_note: null, steps: [{ client: 'cursor', name: 'kitden' }],
      rows: requests.map((r, at) => ({ id: r.id, kind: r.kind, title: r.title, detail: '', project: null, steps: [at], after: [] })),
    });
  };
  try {
    const card = clientCard('cursor', { setup: SETUP, clients: CLIENTS, view: VIEW });
    const register = { action: 'setup_server.register', targets: [{ client: 'cursor' }], params: {} };
    assert.deepEqual([card.actions[0].body, card.actions[0].note], [register, SETUP_NOTE]);
    const press = (node) => Promise.all(node.listeners.click.map((listener) => listener({})));
    const [, , footer] = detailsCard(card);
    await press(footer.childNodes[0]);
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.deepEqual(tray.rows.map((r) => [r.body, r.note]), [[register, SETUP_NOTE]]);
    // Drawn again while it waits, the button says so and takes no press.
    const [, , again] = detailsCard(card);
    assert.deepEqual([textOf(again.childNodes[0]), again.childNodes[0].attributes['aria-disabled'], again.childNodes[0].title], ['In preview', 'true', 'Set up in Cursor…']);
    await press(again.childNodes[0]);
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.deepEqual(sent, ['/api/batch/preview']);
  } finally {
    await cancelTray();
    globalThis.fetch = before;
  }
});

test("an outside server's Move says In preview while it waits; with two gateways it asks which", async () => {
  const sent = [];
  const before = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    sent.push(url);
    if (url !== '/api/batch/preview') return Response.json({});
    const { requests } = JSON.parse(options.body);
    return Response.json({
      id: 'c1', action: 'batch', state: 'previewed', error: null, undo_note: null, steps: [{ client: 'kitden', name: 'github' }],
      rows: requests.map((r, at) => ({ id: r.id, kind: r.kind, title: r.title, detail: '', project: null, steps: [at], after: [] })),
    });
  };
  try {
    const card = outsideCard(GITHUB, 'move', [def('g', 'claude_code')], { view: VIEW, clients: FOUND });
    const press = (node) => Promise.all(node.listeners.click.map((listener) => listener({})));
    const [, , footer] = detailsCard(card);
    await press(footer.childNodes[0]);
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.deepEqual(tray.rows.map((r) => r.body), [moveBody(KITDEN, ['g'])]);
    const [, , again] = detailsCard(card);
    assert.deepEqual([textOf(again.childNodes[0]), again.childNodes[0].attributes['aria-disabled']], ['In preview', 'true']);
    // Two gateways can take it: the button asks which first.
    const obot = { id: 'gw-1', kind: 'obot', name: 'Obot', movable: true };
    const two = outsideCard(GITHUB, 'move', [def('g', 'claude_code')], { view: { ...VIEW, gateways: [KITDEN, obot] }, clients: FOUND });
    assert.deepEqual([typeof two.actions[0].run, two.actions[0].body], ['function', undefined]);
  } finally {
    await cancelTray();
    globalThis.fetch = before;
  }
});

// Showing a card in the panel ------------------------------------------------------------------

const { showHeld, showOutside } = await import('../../src/kitden/web/static/js/gateway-details.js');
const { closePanel, panelState } = await import('../../src/kitden/web/static/js/panel.js');
const { data, state } = await import('../../src/kitden/web/static/js/store.js');
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const isSkeleton = (drawer) => drawer.children.some((node) => node.className.includes('sk-body'));

// The Gateway in a wide window, so Details float: `reply(url)` answers each read. `run(drawer)`
// gets the panel; the page is put back after it.
async function onGatewayPage(reply, run) {
  const saved = { document: globalThis.document, fetch: globalThis.fetch, matchMedia: globalThis.matchMedia };
  const page = {};
  for (const id of ['#drawer', '#scrim', '#main', '#topbar', '#content', '.shell', '#dock']) {
    page[id] = Object.assign(fakeNode('div'), {
      offsetLeft: 1081, focus() {}, contains: () => false, getAnimations: () => [], getBoundingClientRect: () => ({ top: 0, bottom: 83, right: 1345 }),
    });
  }
  // `#drawer .body` is the body the drawer shows now, skeleton or card.
  const querySelector = (selector) => (selector === '#drawer .body' ? page['#drawer'].children.find((node) => node.className.split(' ').includes('body')) : page[selector] ?? null);
  globalThis.document = { ...saved.document, activeElement: null, body: {}, documentElement: { classList: { remove() {} } }, querySelector, querySelectorAll: () => [], addEventListener() {} };
  globalThis.matchMedia = (query) => ({ matches: query.includes('min-width'), addEventListener() {} });
  globalThis.fetch = async (url, options) => reply(url, options);
  Object.assign(data, { gateway: VIEW, setupServer: SETUP, clients: CLIENTS, projects: [] });
  data.scope.gateway = state.project;
  state.view = 'gateway';
  try {
    await run(page['#drawer']);
  } finally {
    closePanel({ instant: true, focus: false });
    Object.assign(data, { gateway: null, setupServer: null, clients: null, projects: null });
    Object.assign(globalThis, saved);
    state.view = 'overview';
  }
}

test("an outside server's read that fails at once still says it could not load the details", async () => {
  const failed = (url) => (url.startsWith('/api/explain') ? { ok: false, status: 500, json: async () => ({}) } : { ok: true, status: 200, json: async () => ({}) });
  await onGatewayPage(failed, async (drawer) => {
    // The read fails while the card still waits behind its skeleton (160 ms).
    await showOutside('move', 'github');
    assert.equal(isSkeleton(drawer), true);
    await wait(400);
    const [head, body] = drawer.children;
    assert.equal(head.children[1].textContent, 'github');
    assert.ok(textOf(body).includes('Could not load the details.'), textOf(body));
  });
});

test('a held server opens on its skeleton and fills in; drawn again it shows no skeleton', async () => {
  const ok = () => ({ ok: true, status: 200, json: async () => ({ tools: [], projects: [] }) });
  await onGatewayPage(ok, async (drawer) => {
    // The panel opens at once on the skeleton of its kind, while the rules are read.
    const first = showHeld('files');
    assert.equal(isSkeleton(drawer), true);
    assert.equal(drawer.children[0].children[0].children[0].textContent, 'Server');
    await first;
    // The read is in, but the skeleton stays its 160 ms; then the card replaces it.
    assert.equal(isSkeleton(drawer), true);
    await wait(400);
    assert.equal(isSkeleton(drawer), false);
    assert.equal(drawer.children[0].children[1].textContent, 'files');
    assert.deepEqual(panelState.current, { type: 'held', name: 'files' });
    // The same card drawn again (after Apply all, Refresh tools): no skeleton, the new card as
    // soon as its read is in.
    const shown = drawer.children[0];
    const again = showHeld('files');
    assert.equal(isSkeleton(drawer), false);
    await again;
    assert.equal(isSkeleton(drawer), false);
    assert.notEqual(drawer.children[0], shown);
    assert.equal(drawer.children[0].children[1].textContent, 'files');
  });
});

// The Gateway with the files server's panel open (its rules from `rules`, null: the read fails),
// a batch preview that refuses a move into `refuse`, and the panel's controls following the tray.
// `run(drawer, sent)` gets the panel and every address asked.
async function onFilesPanel(run, { rules = FILES_TOOLS, refuse = null } = {}) {
  const sent = [];
  const reply = (url, options = {}) => {
    sent.push(url);
    if (url === '/api/batch/preview') {
      const { requests } = JSON.parse(options.body);
      if (refuse && requests.some((r) => r.targets[0] && r.targets[0].client === refuse)) return Response.json({ detail: 'Cursor already has files.' }, { status: 422 });
      return Response.json({
        id: `c${sent.length}`, action: 'batch', state: 'previewed', error: null, undo_note: null, steps: [{ client: 'codex', name: 'files' }],
        rows: requests.map((r, at) => ({ id: r.id, kind: r.kind, title: r.title, detail: '', project: null, steps: [at], after: [] })),
      });
    }
    if (url.startsWith('/api/gateway/tools')) return rules ? Response.json(rules) : Response.json({}, { status: 500 });
    return Response.json({});
  };
  const view = { ...VIEW, gateways: [{ ...KITDEN, servers: [FILES_HELD] }] };
  await onGatewayPage(reply, async (drawer) => {
    data.gateway = view;
    data.scope.gateway = state.project;
    const all = (node) => (node && typeof node === 'object' ? [node, ...node.childNodes.flatMap(all)] : []);
    drawer.querySelectorAll = (selector) => all(drawer).filter((node) => node.dataset && (selector === '[data-tray]' ? node.dataset.tray : selector === '[data-focus]' ? node.dataset.focus : false));
    drawer.contains = (node) => all(drawer).includes(node);
    drawer.focus = () => { globalThis.document.activeElement = drawer; };
    const stop = onTray(syncTray);
    try {
      await showHeld('files');
      await wait(400);
      await run(drawer, sent);
    } finally {
      stop();
      await cancelTray();
    }
  });
}
// The open panel's control with this focus key.
const control = (drawer, key) => drawer.querySelectorAll('[data-focus]').find((node) => node.dataset.focus === key);
const MOVE = 'action:Move out of the gateway…';

test('Move out steps to a client choice and a pick adds one move-out row', async () => {
  await onFilesPanel(async (drawer) => {
    await click(control(drawer, MOVE));
    await wait(50);
    // The next step in the panel: Back, where it came from, Close, and the question.
    const [head, body, foot] = drawer.children;
    const [top, title] = head.children;
    assert.deepEqual(top.children.map((node) => node.attributes['aria-label'] || textOf(node)), ['Back', 'Server · files', 'Close']);
    assert.equal(textOf(title), 'Move files out of the gateway');
    const [say, picks] = body.children;
    assert.equal(textOf(say), 'Pick the client that keeps it.');
    // One row each: the client's tile, its name over whether it uses the gateway, and the radio.
    assert.deepEqual(picks.children.map((node) => node.children.map((part) => part.className.split(' ')[0])), Array(3).fill(['client-mark', 'pk-tx', 'radio']));
    assert.deepEqual(picks.children.map((node) => textOf(node.children[1])), ['Claude CodeUses the gateway now', 'CodexUses the gateway now', 'CursorNot connected to the gateway']);
    assert.equal(picks.children[2].attributes['aria-label'], 'Cursor, Not connected to the gateway');
    assert.equal(textOf(foot), "The other clients lose files's tools.");
    assert.deepEqual(panelState.current, { type: 'moveout', name: 'files' });
    // A pick adds the move at once; its row marks it picked.
    const [, codex, cursor] = picks.children;
    await click(codex);
    const out = (client) => ({ action: 'gateway.move_out', targets: [{ client }], params: { server: 'files' } });
    assert.deepEqual(tray.rows.map((r) => r.body), [out('codex')]);
    assert.deepEqual(picks.children.map((node) => node.attributes['aria-pressed']), ['false', 'true', 'false']);
    // Another pick replaces it: one server moves out to one client.
    await click(cursor);
    assert.deepEqual(tray.rows.map((r) => r.body), [out('cursor')]);
    assert.deepEqual(picks.children.map((node) => node.className), ['pick', 'pick', 'pick on']);
    // A second press on the picked client takes its row out.
    await click(cursor);
    assert.deepEqual(tray.rows, []);
    // Back steps to the server's panel.
    await click(top.children[0]);
    await wait(50);
    assert.equal(textOf(drawer.children[0].children[1]), 'files');
    assert.deepEqual(panelState.current, { type: 'held', name: 'files' });
  });
});

test('Move out takes focus to the client picked, and Back to Move out', async () => {
  await onFilesPanel(async (drawer) => {
    const focused = () => globalThis.document.activeElement.dataset.focus;
    control(drawer, MOVE).focus();
    await click(control(drawer, MOVE));
    await wait(50);
    // Nothing picked yet: the first client.
    assert.equal(focused(), 'pick:claude_code');
    await click(control(drawer, 'pick:codex'));
    await click(drawer.children[0].children[0].children[0]);
    await wait(50);
    assert.equal(focused(), MOVE);
    // With the move into Codex waiting, the step opens on Codex.
    await click(control(drawer, MOVE));
    await wait(50);
    assert.equal(focused(), 'pick:codex');
  });
});

test('a quick second press on a client sends one preview; a refused pick keeps the row before it', async () => {
  await onFilesPanel(async (drawer, sent) => {
    await click(control(drawer, MOVE));
    await wait(50);
    const codex = control(drawer, 'pick:codex');
    const asked = () => sent.filter((url) => url === '/api/batch/preview').length;
    // Two presses before the first answer: one ask.
    for (const listener of codex.listeners.click) listener({});
    for (const listener of codex.listeners.click) listener({});
    await wait(20);
    assert.equal(asked(), 1);
    const out = (client) => ({ action: 'gateway.move_out', targets: [{ client }], params: { server: 'files' } });
    assert.deepEqual(tray.rows.map((r) => r.body), [out('codex')]);
    // Cursor has a server of that name already: the tray keeps Codex, and says why.
    await click(control(drawer, 'pick:cursor'));
    await wait(20);
    assert.deepEqual(tray.rows.map((r) => r.body), [out('codex')]);
    assert.equal(tray.refused.reason, 'Cursor already has files.');
    assert.deepEqual(['pick:codex', 'pick:cursor'].map((key) => control(drawer, key).className), ['pick on', 'pick']);
  }, { refuse: 'cursor' });
});

test('back from Move out keeps the warning the panel had', async () => {
  await onFilesPanel(async (drawer) => {
    const says = () => textOf(drawer.children[1]).includes('Could not load the details.');
    assert.equal(says(), true);
    await click(control(drawer, MOVE));
    await wait(50);
    await click(drawer.children[0].children[0].children[0]);
    await wait(50);
    assert.equal(textOf(drawer.children[0].children[1]), 'files');
    assert.equal(says(), true);
  }, { rules: null });
});
