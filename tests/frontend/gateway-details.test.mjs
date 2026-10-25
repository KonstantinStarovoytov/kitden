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

const { SETUP_NOTE, clientCard, gatewayCard, heldCard, linkCard, outsideCard, reported, toolCard, toolState } = await import('../../src/kitden/web/static/js/gateway-details.js');
const { detailsCard, moveBody, syncTray } = await import('../../src/kitden/web/static/js/details.js');
const { review } = await import('../../src/kitden/web/static/js/review.js');
const { data, state } = await import('../../src/kitden/web/static/js/store.js');
const { cancelTray, onTray, tray } = await import('../../src/kitden/web/static/js/tray.js');
const { GATEWAY_NOTE } = await import('../../src/kitden/web/static/js/parts.js');
const { switchList, toolRows } = await import('../../src/kitden/web/static/js/tools.js');

// The words of a node: its own text, then its children's.
const textOf = (node) => (typeof node === 'string' ? node : node ? `${node.textContent}${node.childNodes.map(textOf).join('')}` : '');
const facts = (card) => card.facts.map((f) => [f.label, typeof f.value === 'string' ? f.value : f.text]);
const labels = (card) => card.actions.map((a) => a.label);
const moreLabels = (card) => (card.more || []).map((a) => a.label);
const mainOf = (card) => card.actions.map((a) => [a.label, Boolean(a.primary)]);
// A press, and what it set off.
const click = async (node) => {
  for (const listener of node.listeners.click || []) listener({});
  await new Promise((resolve) => setTimeout(resolve, 0));
};

const entry = (client, state, fields = {}) => ({ client, state, item: null, enabled: true, ...fields });
const SETUP = [entry('claude_code', 'added'), entry('codex', 'added'), entry('cursor', 'missing')];
const CLIENTS = [
  { id: 'claude_code', status: 'found', version: '2.1.283', app_url: null },
  { id: 'codex', status: 'found', version: '0.159.2', app_url: 'codex://' },
  { id: 'cursor', status: 'found', version: '3.21.16', app_url: null },
];
const FOUND = ['claude_code', 'codex', 'cursor'];
const KITDEN = { id: 'kitden', kind: 'kitden', name: 'Kitden gateway', where: 'On this Mac', movable: true, servers: [{ name: 'files', kind: 'local', state: 'on' }, { name: 'tracker', kind: 'remote', state: 'on' }] };
const row = (name, client, items, fields = {}) => ({ name, clients: [client], columns: [client], items, client_items: { [client]: items }, stays: null, ...fields });
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
// The Kitden gateway with what its servers say of their tools: files on (3 of its 4 tools on),
// tracker off (none of its 2 on).
const TOOLED = (name, on, all, state = 'on') => ({ name, kind: 'local', state, on_count: on, tool_list: Array.from({ length: all }, (_, at) => ({ name: `${name}_${at}` })) });
const KITDEN_TOOLS = { ...KITDEN, servers: [TOOLED('files', 3, 4), TOOLED('tracker', 0, 2, 'off')] };
const VIEW_TOOLS = { ...VIEW, gateways: [KITDEN_TOOLS] };
const REGISTER = (client) => ({ action: 'setup_server.register', targets: [{ client }], params: {} });
const DISCONNECT = (client) => ({ action: 'client.disconnect', targets: [{ client }], params: {} });

test('the outside panel keeps every action, the rest under More', () => {
  asked.length = 0;
  const card = outsideCard(GITHUB, 'move', [def('g', 'claude_code', { summary: 'https://api.github.example.test/mcp' })], { view: VIEW, clients: FOUND, linked: ['claude_code', 'codex'] });
  assert.deepEqual([card.kind, card.title, card.id], ['Server', 'github', 'Remote · outside the gateway']);
  // Its icon on a tile, as on the map.
  assert.equal(card.tile.childNodes[0].dataset.icon, 'globe');
  assert.deepEqual(mainOf(card), [['Move into the gateway…', true]]);
  assert.deepEqual(moreLabels(card), ['+ Add to Codex…', '+ Add to Cursor…', 'Remove from Claude Code…']);
  // One gateway can take it: the button is the move's own, so it can say "In preview".
  assert.deepEqual([card.actions[0].body, card.actions[0].run], [moveBody(KITDEN, ['g']), undefined]);
  assert.deepEqual(card.more[0].body, { action: 'mcp.add', targets: [{ client: 'codex' }], params: { item: 'g' } });
  assert.deepEqual(card.more[2].body, { action: 'mcp.remove_direct', targets: [{ item: 'g' }], params: {} });
  assert.deepEqual(facts(card), [['Set up in', 'Claude Code'], ['Route', 'Direct, on its own'], ["Kitden's rules", "Don't reach it"]]);
  assert.equal(card.facts[2].warn, true);
  // Claude Code uses the Kitden gateway: it keeps github either way.
  assert.equal(card.why, "Claude Code calls github on its own, so Kitden can't turn its tools on or off. Move it into the gateway to manage them here. Claude Code keeps it either way.");
  // The address waits under Technical details.
  assert.ok(textOf(card.technical).includes('https://api.github.example.test/mcp'));
  assert.deepEqual(asked, []);
  // Cursor does not use the gateway: a move would take files from it, so the panel does not say it keeps it.
  const files = outsideCard(FILES, 'local', [def('c', 'cursor')], { view: VIEW, clients: FOUND, linked: ['claude_code', 'codex'] });
  assert.equal(files.id, 'Local · outside the gateway');
  assert.equal(files.why, "Cursor calls files on its own, so Kitden can't turn its tools on or off. Move it into the gateway to manage them here.");
  // No gateway takes a remote one: its entry can go, under More with the rest.
  const none = outsideCard(GITHUB, 'move', [def('g', 'claude_code')], { view: { ...VIEW, gateways: [] }, clients: FOUND, linked: [] });
  assert.deepEqual([labels(none), moreLabels(none)], [[], ['Remove direct entry…', '+ Add to Codex…', '+ Add to Cursor…', 'Remove from Claude Code…']]);
  assert.deepEqual(none.more[0].body, { action: 'mcp.remove_direct', targets: [{ item: 'g' }], params: {} });
  assert.equal(none.why, "Claude Code calls github on its own, so Kitden can't turn its tools on or off.");
  // Kitden does not know that a client loads it: the panel says only that it is set up there.
  const unknown = outsideCard({ ...GITHUB, unknown: true }, 'move', [def('g', 'claude_code')], { view: VIEW, clients: FOUND, linked: ['claude_code'] });
  assert.ok(unknown.why.startsWith("Claude Code has github set up on its own, so Kitden can't turn its tools on or off."), unknown.why);
});

test('a server in two groups adds and removes only its own entries; a gateway client gets no add', () => {
  const docs = outsideCard(DOCS, 'move', [def('a', 'claude_code'), def('b', 'codex')], { view: VIEW, clients: FOUND });
  assert.deepEqual([labels(docs), moreLabels(docs)], [['Move into the gateway…'], ['+ Add to Cursor…', 'Remove from Claude Code…']]);
  assert.deepEqual(docs.more[0].body.params, { item: 'a' });
  // Claude Code and Codex get files through the Kitden gateway: nothing to add anywhere.
  const via = { via_gateway: 'kitden', actions: [], affects: null };
  const files = outsideCard(FILES, 'local', [def('c', 'cursor'), def('k1', 'claude_code', via), def('k2', 'codex', via)], { view: VIEW, clients: FOUND });
  assert.deepEqual([labels(files), moreLabels(files)], [['Move into the gateway…'], ['Remove from Cursor…']]);
  assert.equal(files.id, 'Local · outside the gateway');
  // Two clients say "call"; a project's own entry is not a source for an add.
  const two = outsideCard(row('n8n', 'codex', ['n1', 'n2'], { columns: ['claude_code', 'codex'] }), 'local', [def('n1', 'claude_code', { scope: 'project', project: '/w/atlas' }), def('n2', 'codex')], { view: VIEW, clients: FOUND, linked: ['claude_code', 'codex'] });
  assert.deepEqual(facts(two)[0], ['Set up in', 'Claude Code and Codex']);
  assert.equal(two.why, "Claude Code and Codex call n8n on their own, so Kitden can't turn its tools on or off. Move it into the gateway to manage them here. Claude Code and Codex keep it either way.");
  assert.deepEqual(two.more[0].body.params, { item: 'n2' });
});

test('a server that stays says why instead of Move', () => {
  const stays = "docs is in the project's own files; it stays there.";
  const kept = outsideCard({ ...DOCS, stays }, 'move', [def('a', 'claude_code')], { view: VIEW, clients: FOUND, linked: ['claude_code'] });
  assert.ok(!labels(kept).includes('Move into the gateway…'));
  assert.equal(textOf(kept.after), stays);
  // It cannot move: the sentence does not ask for it.
  assert.equal(kept.why, "Claude Code calls docs on its own, so Kitden can't turn its tools on or off.");
  const none = outsideCard(GITHUB, 'move', [def('g', 'claude_code')], { view: { ...VIEW, gateways: [] }, clients: FOUND });
  assert.equal(textOf(none.after), GATEWAY_NOTE);
  // A plugin's server stays with its plugin, and says so.
  const plugin = outsideCard(row('linear', 'claude_code', [], { stays: 'linear comes with a plugin; it stays with the plugin.' }), 'plugin', [def('l', 'claude_code', { actions: [] })], { view: VIEW, clients: FOUND });
  assert.deepEqual([labels(plugin), moreLabels(plugin), plugin.id], [[], [], 'From a plugin · outside the gateway']);
  assert.equal(textOf(plugin.after), 'linear comes with a plugin; it stays with the plugin.');
});

test('a connected client offers Disconnect, a free one Connect', () => {
  const codex = clientCard('codex', { setup: SETUP, clients: CLIENTS, view: VIEW });
  assert.deepEqual([codex.kind, codex.title, codex.id], ['Client', 'Codex', 'Version 0.159.2 · on this Mac']);
  assert.ok(codex.tile.childNodes[0].className.startsWith('client-mark'));
  assert.deepEqual(mainOf(codex), [['Disconnect from the gateway…', false], ['See what it loads in Library', false]]);
  assert.deepEqual(codex.actions[0].body, DISCONNECT('codex'));
  // Its note says what Codex loses, in the words of the review's after line.
  assert.equal(codex.actions[0].note, "Codex loses the Kitden gateway's servers and Kitden's own read of your setup. Servers it sets up on its own stay.");
  assert.equal(typeof codex.actions[1].run, 'function');
  // Its app opens from under More (D18).
  assert.deepEqual(moreLabels(codex), ['Open ChatGPT']);
  const cursor = clientCard('cursor', { setup: SETUP, clients: CLIENTS, view: VIEW });
  assert.deepEqual(mainOf(cursor), [['Connect to the gateway…', true], ['See what it loads in Library', false]]);
  assert.deepEqual([cursor.actions[0].body, cursor.actions[0].note], [REGISTER('cursor'), SETUP_NOTE]);
  assert.deepEqual(facts(cursor)[0], ['Gateway', 'Not connected']);
  // An old entry connects by updating it.
  const old = clientCard('codex', { setup: [entry('codex', 'old', { item: 'codex:agentsetup' })], clients: CLIENTS, view: VIEW });
  assert.deepEqual([old.actions[0].label, old.actions[0].primary], ['Update the Kitden entry…', true]);
  assert.deepEqual(old.actions[0].body, { action: 'setup_server.update', targets: [{ item: 'codex:agentsetup' }], params: {} });
  assert.ok(old.why.startsWith('Codex has an old Kitden entry, so it does not use the gateway yet.'), old.why);
  // A found client whose version is not read says so in its own words.
  const quiet = clientCard('cursor', { setup: SETUP, clients: [{ id: 'cursor', status: 'found', version: null }], progress: null, view: VIEW });
  assert.equal(quiet.id, 'Version not known · on this Mac');
  const reading = clientCard('cursor', { setup: SETUP, clients: [{ id: 'cursor', status: 'found', version: null }], progress: { steps: [{ name: 'client versions', done: false }] }, view: VIEW });
  assert.equal(reading.id, 'Checking the version… · on this Mac');
  // A plugin gives Cursor its entry: Kitden cannot take it out, and says how.
  const plugin = clientCard('cursor', { setup: [entry('cursor', 'plugin')], clients: CLIENTS, view: VIEW });
  assert.deepEqual([labels(plugin), facts(plugin)[0]], [['See what it loads in Library'], ['Gateway', 'Connected']]);
  assert.ok(plugin.why.endsWith('Cursor gets Kitden from a plugin: turn the plugin off to disconnect it.'), plugin.why);
  // Not on this Mac: nothing to connect, and the panel says why.
  const gone = clientCard('cursor', { setup: [entry('cursor', 'not_installed', { enabled: null })], clients: [{ id: 'cursor', status: 'not_found', version: null }], view: VIEW });
  assert.deepEqual([gone.id, labels(gone)], ['Not installed', ['See what it loads in Library']]);
  assert.ok(gone.why.startsWith('Kitden did not find Cursor on this Mac, so it cannot connect it.'), gone.why);
  // Its own entry off: Claude Code and Cursor keep that switch in their own settings (docs checked
  // 2026-10-24); Codex turns it on again in a review, under More.
  const off = clientCard('claude_code', { setup: [entry('claude_code', 'added', { enabled: false })], clients: CLIENTS, view: VIEW });
  assert.deepEqual([facts(off)[0], labels(off), moreLabels(off)], [['Gateway', 'Not connected'], ['See what it loads in Library'], []]);
  assert.ok(off.why.startsWith("Claude Code has the kitden entry turned off, so it does not reach the gateway. Turn it on in Claude Code's own MCP settings. "), off.why);
  const codexOff = clientCard('codex', { setup: [entry('codex', 'added', { enabled: false })], clients: CLIENTS, view: VIEW });
  assert.ok(codexOff.why.startsWith('Codex has the kitden entry turned off, so it does not reach the gateway. docs is'), codexOff.why);
  assert.deepEqual(moreLabels(codexOff), ['Turn it on in Codex…', 'Open ChatGPT']);
  assert.deepEqual([codexOff.more[0].body, codexOff.more[0].note], [{ action: 'setup_server.enable', targets: [{ client: 'codex' }], params: {} }, SETUP_NOTE]);
  // A plugin's entry that is off is the plugin's switch: only the sentence.
  const pluginOff = clientCard('codex', { setup: [entry('codex', 'plugin', { enabled: false })], clients: CLIENTS, view: VIEW });
  assert.deepEqual(moreLabels(pluginOff), ['Open ChatGPT']);
  assert.ok(pluginOff.why.includes("Turn it on in Codex's own MCP settings."), pluginOff.why);
  // Without the setup read, Kitden does not know whether it connects: no button claims either.
  const unread = clientCard('codex', { setup: null, clients: CLIENTS, view: VIEW });
  assert.deepEqual(facts(unread).slice(0, 2), [['Gateway', 'Not known'], ['Through Kitden', 'Not known']]);
  assert.equal(unread.why, 'Kitden could not read which clients use it.');
  assert.deepEqual(labels(unread), ['See what it loads in Library']);
});

test('the client panel says what goes through Kitden and what runs on its own', () => {
  const claude = clientCard('claude_code', { setup: SETUP, clients: CLIENTS, view: VIEW_TOOLS });
  // Only files is on: its 3 tools that are on; tracker is off.
  assert.deepEqual(facts(claude), [['Gateway', 'Connected'], ['Through Kitden', '1 server · 3 tools on'], ['On its own', 'docs and github'], ['Projects', 'All projects']]);
  // Each server it sets up on its own is a chip with its icon, as on the map.
  const chips = claude.facts[2].value.children;
  assert.deepEqual(chips.map((chip) => [chip.className, chip.childNodes[0].dataset.icon, textOf(chip)]), [['chip-s', 'globe', 'docs'], ['chip-s', 'globe', 'github']]);
  assert.equal(claude.why, "Claude Code calls 1 server through Kitden, so Kitden's rules apply to them. docs and github are set up in Claude Code on its own and skip those rules.");
  const cursor = clientCard('cursor', { setup: SETUP, clients: CLIENTS, view: VIEW_TOOLS, picked: 'p1', folder: 'atlas' });
  assert.deepEqual(facts(cursor), [['Gateway', 'Not connected'], ['Through Kitden', 'Nothing yet'], ['On its own', 'files'], ['Projects', 'atlas']]);
  assert.equal(cursor.facts[1].quiet, true);
  assert.equal(cursor.why, "Cursor does not use the Kitden gateway yet. files is set up in Cursor on its own and skips Kitden's rules.");
  // Nothing of its own: "Nothing"; tools Kitden does not know yet are not counted.
  const codex = clientCard('codex', { setup: SETUP, clients: CLIENTS, view: { ...VIEW, groups: { move: [], local: [], plugin: [] } } });
  assert.deepEqual(facts(codex).slice(1, 3), [['Through Kitden', '2 servers'], ['On its own', 'Nothing']]);
  assert.equal(codex.why, "Codex calls 2 servers through Kitden, so Kitden's rules apply to them.");
  // No server in the gateway is on: nothing goes through it.
  const quiet = clientCard('codex', { setup: SETUP, clients: CLIENTS, view: { ...VIEW_TOOLS, gateways: [{ ...KITDEN_TOOLS, servers: [TOOLED('tracker', 0, 2, 'off')] }] } });
  assert.deepEqual(facts(quiet)[1], ['Through Kitden', 'Nothing yet']);
  assert.ok(quiet.why.startsWith('Codex uses the Kitden gateway, but no server in it is on by the shared rule.'), quiet.why);
});

test("the client panel's Gateway fact says when its change waits in preview", async () => {
  const card = clientCard('codex', { setup: SETUP, clients: CLIENTS, view: VIEW });
  await withTray(() => [card.facts[0].value], async ([gateway]) => {
    assert.equal(textOf(gateway), 'Connected');
    await review(DISCONNECT('codex'));
    assert.equal(textOf(gateway), 'Connected · change in preview');
  });
});

test('the gateway panel lists every client with its own button', async () => {
  const card = gatewayCard(KITDEN_TOOLS, { view: VIEW_TOOLS, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.deepEqual([card.kind, card.title, card.id], ['Gateway', 'Kitden gateway', 'On this Mac']);
  assert.equal(card.tile.childNodes[0].className, 'p-house');
  assert.deepEqual(facts(card), [['Servers', '2 in the gateway · 4 outside'], ['Tools', '3 of 6 on']]);
  const [head, list] = card.list.children;
  assert.deepEqual([head.className, textOf(head)], ['sw-head', 'Clients']);
  // Each row: the client's tile, its name, whether it is connected, and its own button.
  const rowWords = () => list.children.map((r) => [r.children[1].children.map(textOf), textOf(r.children[2].childNodes[0])]);
  assert.deepEqual(rowWords(), [[['Claude Code', 'Connected'], 'Disconnect…'], [['Codex', 'Connected'], 'Disconnect…'], [['Cursor', 'Not connected'], 'Connect…']]);
  // The button names its client for a screen reader.
  assert.equal(textOf(list.children[2].children[2]), 'Connect… Cursor');
  // Move all and Add another gateway wait under More (D18).
  assert.deepEqual([labels(card), moreLabels(card)], [[], ['Move all 2…', 'Add another gateway…']]);
  assert.deepEqual(card.more[0].body, { action: 'gateway.move', targets: [{ item: 'g' }, { item: 'c' }], params: { gateway: 'kitden' } });
  assert.equal(card.why, 'The gateway controls only the servers in it. Direct entries and terminal tools are outside it.');
  await withTray(() => [list], async ([rows], sent) => {
    await click(rows.children[2].children[2]);
    assert.deepEqual(tray.rows.map((r) => [r.body, r.note]), [[REGISTER('cursor'), SETUP_NOTE]]);
    assert.deepEqual(rowWords()[2], [['Cursor', 'Not connected · in preview'], 'In preview']);
    // A second press on it asks for nothing.
    await click(rows.children[2].children[2]);
    assert.equal(sent.filter((url) => url === '/api/batch/preview').length, 1);
    await click(rows.children[0].children[2]);
    assert.deepEqual(tray.rows.map((r) => r.body), [REGISTER('cursor'), DISCONNECT('claude_code')]);
  });
  // Tools Kitden does not know yet, and an empty gateway.
  assert.deepEqual(facts(gatewayCard(KITDEN, { view: VIEW, setup: SETUP, projects: PROJECTS, clients: FOUND })).at(-1), ['Tools', 'Not known yet']);
  const empty = gatewayCard({ ...KITDEN, servers: [] }, { view: { ...VIEW, groups: { move: [], local: [], plugin: [] } }, setup: SETUP, projects: [], clients: FOUND });
  assert.deepEqual([facts(empty), moreLabels(empty)], [[['Servers', '0 in the gateway · 0 outside'], ['Tools', 'Nothing yet']], ['Add another gateway…']]);
  // A client a plugin connects, or one not on this Mac, has no button.
  const plugin = gatewayCard(KITDEN, { view: VIEW, setup: [entry('claude_code', 'plugin'), entry('codex', 'not_installed', { enabled: null }), entry('cursor', 'missing')], projects: PROJECTS, clients: FOUND });
  assert.deepEqual(plugin.list.children[1].children.map((r) => r.children.length), [2, 2, 3]);
  // A row with no button says why in its small line.
  const smallOf = (card) => card.list.children[1].children.map((r) => textOf(r.children[1].children[1]));
  assert.deepEqual(smallOf(plugin), ['Connected · from a plugin', 'Not connected · not on this Mac', 'Not connected']);
  const off = gatewayCard(KITDEN, { view: VIEW, setup: [entry('claude_code', 'added', { enabled: false }), entry('codex', 'not_installed', { enabled: null }), entry('cursor', 'old', { item: 'cursor:agentsetup' })], clients: FOUND, clientList: [{ id: 'codex', status: 'unreadable' }] });
  assert.deepEqual(smallOf(off), ['Not connected · its entry is off', 'Not connected · settings not readable', 'Not connected']);
  // An old entry is updated, not connected.
  assert.equal(textOf(off.list.children[1].children[2].children[2].childNodes[0]), 'Update…');
  // "Add another gateway…" shows the form in the panel.
  assert.ok(gatewayCard(KITDEN, { view: VIEW, setup: SETUP, projects: PROJECTS, clients: FOUND, adding: true }).after);
});

test("Move all leaves out a name set up differently in two clients, as the medium sample's docs", () => {
  // The medium sample: docs is remote in Claude Code and local in Codex.
  const view = { ...VIEW, groups: {
    move: [row('analytics', 'codex', ['an']), DOCS, GITHUB],
    local: [row('browser-tools', 'cursor', ['bt']), DOCS_LOCAL, FILES, row('n8n', 'cursor', ['n8'])],
    plugin: [],
  } };
  const card = gatewayCard(KITDEN, { view, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.equal(card.more[0].label, 'Move all 5…');
  assert.deepEqual(card.more[0].body.targets.map((t) => t.item), ['an', 'g', 'bt', 'c', 'n8']);
  // Only the pair left: nothing to move all of.
  const pair = gatewayCard(KITDEN, { view: { ...VIEW, groups: { move: [DOCS], local: [DOCS_LOCAL], plugin: [] } }, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.deepEqual(moreLabels(pair), ['Add another gateway…']);
  // A stays reason keeps a row out too.
  const stays = "docs is in the project's own files; it stays there.";
  const kept = gatewayCard(KITDEN, { view: { ...VIEW, groups: { move: [{ ...GITHUB, stays }], local: [FILES], plugin: [] } }, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.equal(kept.more[0].label, 'Move all 1…');
});

test('Move all leaves out a name set up differently in two clients of one group', () => {
  const stays = 'files is set up differently in Codex and Cursor; keep one first.';
  const files = { ...row('files', 'codex', ['c', 'd']), clients: ['codex', 'cursor'], columns: ['codex', 'cursor'], stays };
  const view = { ...VIEW, groups: { move: [GITHUB], local: [files], plugin: [] } };
  const card = gatewayCard(KITDEN, { view, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.equal(card.more[0].label, 'Move all 1…');
  assert.deepEqual(card.more[0].body.targets.map((t) => t.item), ['g']);
});

test('the Kitden gateway says what it could not read', () => {
  const problem = 'Could not read the Kitden gateway settings.';
  const broken = gatewayCard({ ...KITDEN, servers: [], problem }, { view: VIEW, setup: SETUP, projects: PROJECTS, clients: FOUND });
  assert.equal(broken.warning, problem);
  assert.deepEqual(facts(broken), []);
  const unknown = gatewayCard(KITDEN, { view: VIEW, setup: null, projects: PROJECTS, clients: FOUND });
  assert.equal(unknown.warning, 'Kitden could not read which clients use it.');
  // Without the setup read, no row claims a client is connected or not.
  assert.equal(unknown.list, null);
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
// /api/gateway/tools answers (`states`: project id -> the tool's state; `server`: the server's;
// `own`: the projects with a rule of their own for it).
const CHOICE = [{ id: 'a', path: '/w/atlas', own_rules: 1, exists: true }, { id: 'm', path: '/w/mcp-gateway', own_rules: 0, exists: true }, { id: 'w', path: '/w/atlas/web', own_rules: 0, exists: true }];
const rulesFor = (states, { name = 'push_files', shared = 'on', server = {}, own = [] } = {}) => ({
  shared,
  projects: Object.entries(states).map(([id, state]) => ({ id, server: server[id] || 'on', tools: { [name]: state }, own: own.includes(id) ? [name] : [] })),
});
const actionsOf = (card) => card.actions.map((a) => [a.label, Boolean(a.primary)]);
const moreOf = (card) => (card.more || []).map((a) => a.label);

// The medium sample with All projects: atlas turns write_file off, atlas/web follows atlas and
// turns search_files off itself; old-app, sandbox and website follow the shared rule.
const MEDIUM_PROJECTS = [
  { id: 'atlas', path: '/h/work/atlas', own_rules: 1, exists: true }, { id: 'web', path: '/h/work/atlas/web', own_rules: 1, exists: true },
  { id: 'old', path: '/h/work/old-app', own_rules: 0, exists: false }, { id: 'sand', path: '/h/work/sandbox', own_rules: 0, exists: true },
  { id: 'site', path: '/h/work/website', own_rules: 0, exists: true },
];
const MEDIUM_RULES = {
  shared: 'on',
  projects: [['atlas', 'off', 'on', ['write_file']], ['web', 'off', 'off', ['search_files']], ['old', 'on', 'on', []], ['sand', 'on', 'on', []], ['site', 'on', 'on', []]]
    .map(([id, write, search, own]) => ({ id, server: 'on', tools: { write_file: write, search_files: search }, own, up: id === 'web' ? ['atlas'] : [] })),
};
const FILES_ROW = { name: 'files', kind: 'local', state: 'on' };
const medium = (name, extra = {}) => toolCard({ name, title: null, state: 'on', effective: 'on', hint: 'writes', origin: 'default', origin_from: null }, FILES_ROW, { linked: LINKED, picked: '', folder: '', detail: { shared: 'on' }, rules: MEDIUM_RULES, projects: MEDIUM_PROJECTS, ...extra });

test("the tool panel says Permission and Reported in the mockup's words", () => {
  // push_files is off for all projects; atlas turns it on, and atlas/web follows atlas.
  const rules = rulesFor({ a: 'on', m: 'off', w: 'on' }, { shared: 'off', own: ['a'] });
  const card = toolCard(tool(), HELD_GITHUB, { linked: LINKED, picked: '', folder: '', detail: { shared: 'off', calls: { count: 12, last: TODAY_1402 } }, rules, projects: CHOICE });
  assert.deepEqual([card.kind, card.title, card.id], ['Tool', 'Push files', 'push_files']);
  assert.deepEqual(facts(card), [
    ['Server', 'github · Remote'], ['Permission', 'Off'], ['Comes from', 'All projects'], ['Reported', 'May write'], ['Clients', '2 clients'], ['Calls', '12 calls · last today 14:02']]);
  // Permission starts with the tool's mark; a tool that may write says so in amber.
  assert.deepEqual(card.facts[1].value.children.map((node) => node.className), ['mark', '']);
  assert.equal(card.facts[3].warn, true);
  // With All projects: everywhere, then each known project that decides otherwise.
  assert.equal(card.why, "Claude Code and Codex can't call this tool through Kitden, in any project. Except atlas, where it is on; web, where it is on.");
  assert.deepEqual(actionsOf(card), [['Turn on for all projects…', true], ['Turn on in some projects…', false]]);
  assert.deepEqual(card.actions[0].body, { action: 'gateway.rule', targets: [], params: { server: 'github', tool: 'push_files', state: 'on', project: null } });
  assert.equal(typeof card.actions[1].run, 'function');
  // A tool that is on has no primary action; with no project deciding otherwise, no Except.
  const on = toolCard(tool({ title: null, state: 'on', effective: 'on', hint: 'reads' }), HELD_GITHUB, { linked: LINKED, picked: '', folder: '', detail: { shared: 'on', hint_from: 'server' }, rules: rulesFor({ a: 'on', m: 'on' }), projects: CHOICE });
  assert.deepEqual([on.title, on.id, on.facts[1].text, on.facts[3].value, on.facts[3].warn, facts(on).map(([label]) => label)], ['push_files', null, 'On', 'Reads only', false, ['Server', 'Permission', 'Comes from', 'Reported', 'Clients']]);
  assert.deepEqual(on.facts[1].value.children.map((node) => node.className), ['mark on', '']);
  assert.equal(on.why, 'Claude Code and Codex can call this tool through Kitden, in every project.');
  assert.deepEqual(actionsOf(on), [['Turn off for all projects…', false], ['Turn off in some projects…', false]]);
  // Without each project's rules Kitden cannot say who decides otherwise, nor offer a project.
  const unread = toolCard(tool({ state: 'on', effective: 'on' }), HELD_GITHUB, { linked: LINKED, picked: '', folder: '', detail: { shared: 'on' }, projects: CHOICE });
  assert.equal(unread.why, 'Claude Code and Codex can call this tool through Kitden by the shared rule.');
  assert.deepEqual(actionsOf(unread), [['Turn off for all projects…', false]]);
  // No client on the gateway: the sentence says that instead.
  const alone = toolCard(tool(), HELD_GITHUB, { linked: [], picked: '', folder: '', detail: { shared: 'off' }, rules, projects: CHOICE });
  assert.deepEqual([alone.why, alone.facts[4].text], ['No client uses the Kitden gateway yet.', 'No clients yet']);
  // Without the clients' setup Kitden does not know who can call it.
  const unknown = toolCard(tool(), HELD_GITHUB, { linked: null, picked: '', folder: '', detail: { shared: 'off' } });
  assert.deepEqual([unknown.facts[4].value, unknown.why], ['Not known', 'Kitden could not read which clients use it.']);
  // What it does, in the mockup's words, and where that comes from.
  assert.equal(reported('reads', 'server'), 'Reads only');
  assert.equal(reported('writes', 'server'), 'May write');
  assert.equal(reported('may write', 'name'), 'Not reported · its name suggests it writes');
  assert.equal(reported('unknown', null), 'Not reported');
  assert.equal(reported('reads'), 'Reads only');
});

test("in a project the tool panel says what the project follows, or its own rule", () => {
  const rules = rulesFor({ a: 'on', m: 'off', w: 'on' }, { shared: 'off', own: ['a'] });
  const at = (picked, folder, fields, linked = LINKED) => toolCard(tool(fields), HELD_GITHUB, { linked, picked, folder, detail: { shared: 'off', follows: null }, rules, projects: CHOICE });
  // mcp-gateway follows the shared rule: it can turn the tool on there, or for all projects.
  const follows = at('m', 'mcp-gateway', {});
  assert.deepEqual([follows.facts[1].text, follows.facts[2].value], ['Off · from all projects', 'All projects']);
  assert.equal(follows.why, 'mcp-gateway follows the shared rule: off.');
  assert.deepEqual(actionsOf(follows), [['Turn on in mcp-gateway…', true], ['Turn on for all projects…', false]]);
  assert.deepEqual(follows.actions[0].body, { action: 'gateway.rule', targets: [], params: { server: 'github', tool: 'push_files', state: 'on', project: 'm' } });
  // "In some projects" stays, under More (D18).
  assert.deepEqual(moreOf(follows), ['Turn on in some projects…']);
  // A folder under atlas follows atlas's rule, and says so.
  const parent = at('w', 'web', { state: 'on', effective: 'on', origin: 'parent', origin_from: 'atlas' });
  assert.deepEqual([parent.facts[1].text, parent.facts[2].value], ['On · from atlas', 'From atlas']);
  assert.equal(parent.why, "web follows atlas's rule: on.");
  assert.deepEqual(actionsOf(parent), [['Turn off in web…', true], ['Turn on for all projects…', false]]);
  // atlas has a rule of its own: back to the shared rule, or the rule for all projects.
  const own = at('a', 'atlas', { state: 'on', effective: 'on', origin: 'project' });
  assert.deepEqual([own.facts[1].text, own.facts[2].value, own.facts[2].accent], ['On in this project', 'This project · atlas', true]);
  assert.equal(own.why, 'Claude Code and Codex can call this tool in atlas. Every other project still has it off, except web, where it is on.');
  assert.deepEqual(actionsOf(own), [['Use the shared rule…', true], ['Turn on for all projects…', false]]);
  assert.deepEqual(own.actions[0].body, { action: 'gateway.rule', targets: [], params: { server: 'github', tool: 'push_files', state: null, project: 'a' } });
  assert.deepEqual(moreOf(own), ['Turn on in some projects…']);
  // With every other project at the shared state, no except; a parent folder's rule leads back to it.
  const alone = toolCard(tool({ state: 'on', effective: 'on', origin: 'project' }), HELD_GITHUB, { linked: LINKED, picked: 'w', folder: 'web', detail: { shared: 'on', follows: 'atlas' }, rules: rulesFor({ a: 'on', m: 'on', w: 'off' }, { own: ['w'] }), projects: CHOICE });
  assert.equal(alone.why, "Claude Code and Codex can call this tool in web. Every other project has it on.");
  assert.equal(alone.actions[0].label, "Use atlas's rule…");
  // atlas turns the server on, which is off for all projects: other projects call the tool only
  // where they turn the server on too.
  const serverOff = { ...rulesFor({ a: 'on', m: 'on', w: 'on' }, { own: ['a'] }), shared: 'off' };
  serverOff.projects = serverOff.projects.map((p) => ({ ...p, server: p.id === 'm' ? 'off' : 'on' }));
  const atlasOn = toolCard(tool({ state: 'on', effective: 'on', origin: 'project' }), HELD_GITHUB, { linked: LINKED, picked: 'a', folder: 'atlas', detail: { shared: 'on' }, rules: serverOff, projects: CHOICE });
  assert.equal(atlasOn.why, 'Claude Code and Codex can call this tool in atlas. Every other project still has it off, except web, where it is on.');
  // A project's own rule says no client when none uses the gateway; what a project follows needs no client.
  assert.equal(at('a', 'atlas', { state: 'on', effective: 'on', origin: 'project' }, []).why, 'No client uses the Kitden gateway yet.');
  assert.equal(at('m', 'mcp-gateway', {}, []).why, 'mcp-gateway follows the shared rule: off.');
  // No Projects with a rule of their own in a project.
  assert.equal(own.list, null);
});

test('in some projects is offered only while a project would change', () => {
  // write_file is on for all projects; atlas turns it off, atlas/web follows atlas.
  const write = medium('write_file');
  assert.equal(write.why, 'Claude Code and Codex can call this tool through Kitden, in every project. Except atlas, where it is off; web, where it is off.');
  assert.deepEqual(actionsOf(write), [['Turn off for all projects…', false], ['Turn off in some projects…', false]]);
  // Every project has it off already: nothing to turn off in some projects.
  const off = { ...MEDIUM_RULES, projects: MEDIUM_RULES.projects.map((p) => ({ ...p, tools: { write_file: 'off' } })) };
  const none = medium('write_file', { rules: off });
  assert.deepEqual(actionsOf(none), [['Turn off for all projects…', false]]);
  assert.equal(none.why, 'Claude Code and Codex can call this tool through Kitden, in every project. Except atlas, where it is off; old-app, where it is off; sandbox, where it is off; web, where it is off; website, where it is off.');
});

test('Projects with a rule of their own lists each and Show picks it', async () => {
  // atlas turns write_file off; website has a rule of its own that keeps it on; web only follows atlas.
  const rules = { ...MEDIUM_RULES, projects: MEDIUM_RULES.projects.map((p) => (p.id === 'site' ? { ...p, own: ['write_file'] } : p)) };
  const card = medium('write_file', { rules });
  const [head, ...rows] = card.list.children;
  assert.deepEqual([card.list.className, head.className, textOf(head)], ['own-rules', 'sw-head', 'Projects with a rule of their own']);
  assert.deepEqual(rows.map((row) => row.children.map((part) => part.dataset.icon || textOf(part))), [['folder', 'atlas', 'Off', 'Show'], ['folder', 'website', 'On', 'Show']]);
  assert.deepEqual(rows.map((row) => row.children[2].className), ['own-state', 'own-state on']);
  // It sits between the facts and the sentence.
  const [, body] = detailsCard(card);
  assert.deepEqual(body.children.map((node) => node.className), ['facts', 'own-rules', 'why']);
  // Show names its project (what it does is tested on the page below).
  const show = rows[0].children[3];
  assert.equal(show.attributes['aria-label'], 'Show atlas');
  // None without a rule of a project's own, and none without each project's rules.
  assert.equal(medium('read_file').list, null);
  assert.equal(medium('write_file', { rules: {} }).list, null);
});

test('a tool of a server that is off says so and offers nothing', () => {
  const card = toolCard(tool({ state: 'on', effective: 'off', why: 'server_off' }), { name: 'files', kind: 'local', state: 'off' }, { linked: LINKED, picked: 'w', folder: 'web', detail: {} });
  assert.deepEqual([card.facts[0].value, card.facts[1].text], ['files · Local', 'Off · server off']);
  assert.equal(card.why, 'files is off in web, so none of its tools can be called.');
  assert.deepEqual(card.actions.map((a) => a.label), ['Open files']);
  assert.equal(typeof card.actions[0].run, 'function');
  // With All projects: off by the shared rule, and the projects that turn the server on.
  const rules = rulesFor({ a: 'on', m: 'on', w: 'on' }, { shared: 'off', server: { a: 'on', m: 'off', w: 'on' } });
  const shared = toolCard(tool({ state: 'on', effective: 'off', why: 'server_off' }), { name: 'files', kind: 'local', state: 'off' }, { linked: LINKED, picked: '', folder: '', detail: { shared: 'on' }, rules });
  assert.equal(shared.why, 'files is off by the shared rule, so none of its tools can be called. 2 projects decide otherwise.');
  // Its projects with a rule of their own still show, each with Show.
  const own = toolCard(tool({ state: 'on', effective: 'off', why: 'server_off' }), { name: 'files', kind: 'local', state: 'off' }, { linked: LINKED, picked: '', folder: '', detail: { shared: 'on' }, rules: { ...rules, projects: rules.projects.map((p) => ({ ...p, own: p.id === 'a' ? ['push_files'] : [] })) }, projects: CHOICE });
  assert.deepEqual(own.list.children.slice(1).map((row) => row.children.map((part) => part.dataset.icon || textOf(part))), [['folder', 'atlas', 'On', 'Show']]);
  // In a project there is none.
  assert.ok(!card.list);
});

test('a tool says where its state comes from', () => {
  assert.equal(toolState(tool({ effective: 'on', origin: 'project' }), ''), 'On');
  assert.equal(toolState(tool({ origin: 'project' }), 'w'), 'Off in this project');
  assert.equal(toolState(tool({ effective: 'on' }), 'w'), 'On · from all projects');
  assert.equal(toolState(tool({ origin: 'parent', origin_from: 'atlas' }), 'w'), 'Off · from atlas');
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
    'Turn off in some projects…', 'Turn strict mode on…', 'Turn off every writing tool…', 'Refresh tools',
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
  // "In some projects" steps to the projects (a test below); nothing waits under the actions.
  assert.equal(typeof card.more[0].run, 'function');
  // In a project with a rule of its own: its parent's rule back, and the rule for all projects.
  const off = { ...FILES_HELD, state: 'off', origin: 'project', on_count: 0, projects: 1 };
  const rules = rulesFor({ a: 'on', m: 'on', w: 'on' }, { server: { w: 'off' } });
  const web = held(off, { picked: 'w', folder: 'web', detail: { ...FILES_TOOLS, state: 'off', strict: true, follows: 'atlas', ...rules }, projects: CHOICE });
  // While it is off no writing tool can be called: nothing to turn off.
  assert.deepEqual(web.more.slice(0, 5).map((a) => a.label), ["Use atlas's rule…", 'Turn off for all projects…', 'Turn off in some projects…', 'Turn strict mode off…', 'Refresh tools']);
  assert.deepEqual(web.more[0].body, { action: 'gateway.rule', targets: [], params: { server: 'files', tool: null, state: null, project: 'w' } });
  assert.deepEqual(web.more[1].body, { action: 'gateway.rule', targets: [], params: { server: 'files', tool: null, state: 'off', project: null } });
  // The server's answer did not come: no switches, so the rule for all projects waits under More.
  const unread = held(FILES_HELD, { detail: {} });
  assert.equal(unread.list, null);
  assert.deepEqual(unread.more[0], { label: 'Turn off for all projects…', body: { action: 'gateway.rule', targets: [], params: { server: 'files', tool: null, state: 'off', project: null } } });
  // No client Kitden can write: no move out; without each project's rules, no choice.
  const alone = held(FILES_HELD, { clients: [], detail: { ...FILES_TOOLS, projects: undefined } });
  assert.deepEqual([alone.actions, alone.more.map((a) => a.label).includes('Turn off in some projects…')], [[], false]);
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
    assert.deepEqual([textOf(again.childNodes[0]), again.childNodes[0].attributes['aria-disabled'], again.childNodes[0].title], ['In preview', 'true', 'Connect to the gateway…']);
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

const { showHeld, showOutside, showTool } = await import('../../src/kitden/web/static/js/gateway-details.js');
const { closePanel, isPanelOpen, panelState } = await import('../../src/kitden/web/static/js/panel.js');
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
  // The project button at the top takes focus.
  page['#where'] = fakeNode('button');
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
    // Drawn again (back from a review), it still says so.
    panelState.from.draw();
    await wait(50);
    assert.ok(textOf(drawer.children[1]).includes('Could not load the details.'), textOf(drawer.children[1]));
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
// or another panel (`open`), the known `projects`, a batch preview that refuses a move into
// `refuse`, and the panel's controls following the tray. `run(drawer, sent)` gets the panel and
// every address asked.
async function onFilesPanel(run, { rules = FILES_TOOLS, refuse = null, open = () => showHeld('files'), projects = [] } = {}) {
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
    Object.assign(data, { gateway: view, projects });
    data.scope.gateway = state.project;
    const all = (node) => (node && typeof node === 'object' ? [node, ...node.childNodes.flatMap(all)] : []);
    drawer.querySelectorAll = (selector) => all(drawer).filter((node) => node.dataset && (selector === '[data-tray]' ? node.dataset.tray : selector === '[data-focus]' ? node.dataset.focus : false));
    drawer.contains = (node) => all(drawer).includes(node);
    drawer.focus = () => { globalThis.document.activeElement = drawer; };
    const stop = onTray(syncTray);
    try {
      await open();
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

test('Show opens the same tool in that project, focus inside; a tool gone there leaves focus on the project button', async () => {
  const { closeForProject } = await import('../../src/kitden/web/static/js/panel.js');
  const { setSwitcher } = await import('../../src/kitden/web/static/js/store.js');
  // As app.js does: another project closes Details, then the page reads it (`there`).
  let there = null;
  setSwitcher(async () => {
    closeForProject();
    if (there) data.gateway = there;
    data.scope.gateway = state.project;
  });
  const open = () => showTool('files', 'write_file');
  try {
    await onFilesPanel(async (drawer) => {
      const show = control(drawer, 'show:atlas');
      await click(show);
      await wait(400);
      assert.equal(state.project, 'atlas');
      assert.equal(isPanelOpen(), true);
      assert.deepEqual(panelState.current, { type: 'tool', server: 'files', tool: 'write_file' });
      assert.equal(globalThis.document.activeElement, drawer);
    }, { open, projects: MEDIUM_PROJECTS });
    state.project = '';
    // In atlas the files server no longer lists write_file: the panel closes, focus on the project button.
    there = { ...VIEW, gateways: [{ ...KITDEN, servers: [{ ...FILES_HELD, tool_list: FILES_HELD.tool_list.filter((t) => t.name !== 'write_file') }] }] };
    await onFilesPanel(async (drawer) => {
      await click(control(drawer, 'show:atlas'));
      await wait(400);
      assert.equal(isPanelOpen(), false);
      assert.equal(globalThis.document.activeElement, globalThis.document.querySelector('#where'));
    }, { open, projects: MEDIUM_PROJECTS });
  } finally {
    state.project = '';
    setSwitcher(async () => {});
  }
});
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
    assert.equal(textOf(say), 'Pick the client that keeps it. You can also drag files onto a client on the map.');
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

test('the move-out step says it can be dragged', async () => {
  await onFilesPanel(async (drawer) => {
    await click(control(drawer, MOVE));
    await wait(50);
    const [say] = drawer.children[1].children;
    assert.equal(textOf(say), 'Pick the client that keeps it. You can also drag files onto a client on the map.');
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

// "In some projects" ----------------------------------------------------------------------------

const SOME = 'action:Turn off in some projects…';
// The step's rows, each as [name, its quiet line, disabled, ticked].
const pickRows = (drawer) => drawer.children[1].children[3].children.map((row) => [textOf(row.children[1].children[0]), textOf(row.children[1].children[1]), Boolean(row.disabled), row.attributes['aria-checked']]);
const offIn = (tool, project) => ({ action: 'gateway.rule', targets: [], params: { server: 'files', tool, state: 'off', project } });

test("in some projects: a tick adds that project's row, an untick takes only it out", async () => {
  await onFilesPanel(async (drawer) => {
    // write_file is on for all projects; atlas turns it off, and atlas/web follows atlas.
    const focused = () => globalThis.document.activeElement.dataset.focus;
    control(drawer, SOME).focus();
    await click(control(drawer, SOME));
    await wait(50);
    const [head, body, footer, foot] = drawer.children;
    const [top, title] = head.children;
    assert.deepEqual(top.children.map((node) => node.attributes['aria-label'] || textOf(node)), ['Back', 'Tool · write_file', 'Close']);
    assert.equal(textOf(title), 'Turn off write_file in the projects you pick');
    const [say, follows, find, picks] = body.children;
    assert.equal(textOf(say), 'The shared rule stays on.');
    // An empty live region stays in the page (it has no height), so what it says next is heard.
    assert.deepEqual([Boolean(follows.hidden), follows.attributes['aria-live'], follows.children], [false, 'polite', []]);
    assert.deepEqual(['placeholder', 'aria-label'].map((name) => find.children.at(-1).attributes[name]), ['Find a project…', 'Find a project…']);
    // Focus goes to Find.
    assert.equal(focused(), 'find');
    // One row per known project, by folder name: what it has now, and what it has of its own.
    assert.deepEqual(pickRows(drawer), [
      ['atlas', '1 own rule · already off', true, 'false'],
      ['old-app', 'Folder missing · on now', false, 'false'],
      ['sandbox', 'on now', false, 'false'],
      ['web', '1 own rule · already off', true, 'false'],
      ['website', 'on now', false, 'false'],
    ]);
    assert.deepEqual([picks.children[2].attributes.role, picks.children[2].children.map((part) => part.dataset.icon || part.className)], ['checkbox', ['folder', 'pk-tx', 'chk']]);
    assert.equal(textOf(foot), 'Tick projects. Each one waits in preview until Apply.');
    assert.deepEqual(panelState.current, { type: 'projects', server: 'files', tool: 'write_file' });
    // Each tick adds that project's row.
    const row = (name) => picks.children.find((node) => textOf(node.children[1].children[0]) === name);
    await click(row('sandbox'));
    await click(row('website'));
    assert.deepEqual(tray.rows.map((r) => r.body), [offIn('write_file', 'sand'), offIn('write_file', 'site')]);
    assert.deepEqual(pickRows(drawer).map((r) => r[3]), ['false', 'false', 'true', 'false', 'true']);
    assert.equal(row('sandbox').className, 'pick multi on');
    assert.equal(textOf(foot), '2 projects in preview. Apply them from the tray.');
    // No known project lies inside sandbox or website: nothing follows them.
    assert.deepEqual([Boolean(follows.hidden), follows.children], [false, []]);
    // An untick takes exactly that project's row out; the other stays.
    await click(row('sandbox'));
    assert.deepEqual(tray.rows.map((r) => r.body), [offIn('write_file', 'site')]);
    assert.deepEqual(pickRows(drawer).map((r) => r[3]), ['false', 'false', 'false', 'false', 'true']);
    assert.equal(textOf(foot), '1 project in preview. Apply them from the tray.');
    // Done steps back to the tool's panel, focus on the action; the tray keeps its row.
    await click(footer.children[0]);
    await wait(50);
    assert.equal(textOf(drawer.children[0].children[1]), 'write_file');
    assert.deepEqual(panelState.current, { type: 'tool', server: 'files', tool: 'write_file' });
    assert.equal(focused(), SOME);
    assert.deepEqual(tray.rows.map((r) => r.body), [offIn('write_file', 'site')]);
  }, { open: () => showTool('files', 'write_file'), projects: MEDIUM_PROJECTS });
});

test('a project already at the value cannot be ticked, and Find narrows the rows', async () => {
  await onFilesPanel(async (drawer, sent) => {
    await click(control(drawer, SOME));
    await wait(50);
    const [, , find, picks, none] = drawer.children[1].children;
    const atlas = picks.children[0];
    assert.equal(atlas.attributes['aria-label'], 'atlas, 1 own rule · already off');
    await click(atlas);
    assert.deepEqual([tray.rows, sent.filter((url) => url === '/api/batch/preview')], [[], []]);
    // Find narrows the rows by folder name as you type; when none is left it says so.
    const input = find.children.at(-1);
    const type = (text) => {
      input.value = text;
      for (const listener of input.listeners.input) listener({});
    };
    const shown = () => picks.children.filter((node) => !node.hidden).map((node) => textOf(node.children[1].children[0]));
    type('WEB');
    assert.deepEqual([shown(), none.hidden], [['web', 'website'], true]);
    type('zzz');
    assert.deepEqual([shown(), textOf(none), none.hidden], [[], 'No project matches.', false]);
    type('');
    assert.equal(shown().length, 5);
  }, { open: () => showTool('files', 'write_file'), projects: MEDIUM_PROJECTS });
});

test('a whole server turns on or off in some projects, from More, and Back keeps the warning', async () => {
  // files is on for all projects; sandbox turns it off. Its tools answer with a problem.
  const rules = { ...FILES_TOOLS, problem: 'files did not list its tools.', projects: FILES_TOOLS.projects.map((p) => (p.id === 'sand' ? { ...p, server: 'off' } : p)) };
  await onFilesPanel(async (drawer) => {
    const says = () => textOf(drawer.children[1]).includes('files did not list its tools.');
    assert.equal(says(), true);
    const card = held(FILES_HELD, { detail: rules, projects: MEDIUM_PROJECTS, warning: rules.problem });
    await card.more.find((a) => a.label === 'Turn off in some projects…').run();
    await wait(50);
    const [head] = drawer.children;
    assert.deepEqual(head.children[0].children.map((node) => node.attributes['aria-label'] || textOf(node)), ['Back', 'Server · files', 'Close']);
    assert.equal(textOf(head.children[1]), 'Turn off files in the projects you pick');
    assert.deepEqual(pickRows(drawer).map((r) => r.slice(0, 3)), [
      ['atlas', '1 own rule · on now', false],
      ['old-app', 'Folder missing · on now', false],
      ['sandbox', 'already off', true],
      ['web', '1 own rule · on now', false],
      ['website', 'on now', false],
    ]);
    const [, follows, , picks] = drawer.children[1].children;
    await click(picks.children[0]);
    assert.deepEqual(tray.rows.map((r) => r.body), [offIn(null, 'atlas')]);
    // atlas/web has no rule of its own for files: it follows atlas, and the step says so.
    assert.deepEqual(follows.children.map(textOf), ['web follows atlas and changes with it.']);
    await click(picks.children[4]);
    assert.deepEqual(follows.children.map(textOf), ['web follows atlas and changes with it.']);
    // Unticked, atlas no longer says it.
    await click(picks.children[0]);
    assert.deepEqual([Boolean(follows.hidden), follows.children], [false, []]);
    await click(picks.children[0]);
    // Back steps to the server's panel, with its warning.
    await click(head.children[0].children[0]);
    await wait(50);
    assert.equal(textOf(drawer.children[0].children[1]), 'files');
    assert.deepEqual(panelState.current, { type: 'held', name: 'files' });
    assert.equal(says(), true);
  }, { rules, projects: MEDIUM_PROJECTS });
});

test('a step action hands its button no wait, so the button never turns busy and drops focus', async () => {
  // A button that waits more than 150 ms turns busy and disabled (dom.js busyWhile), and focus on a
  // disabled button falls to the page. A step takes 130 ms and more on a slow page: it must not wait.
  await onFilesPanel(async (drawer) => {
    const card = held(FILES_HELD, { detail: FILES_TOOLS, projects: MEDIUM_PROJECTS });
    assert.equal(card.actions[0].run(), undefined);
    await wait(50);
    assert.deepEqual(panelState.current, { type: 'moveout', name: 'files' });
    assert.equal(card.more.find((a) => a.label === 'Turn off in some projects…').run(), undefined);
    await wait(50);
    assert.deepEqual(panelState.current, { type: 'projects', server: 'files', tool: null });
    assert.equal(textOf(drawer.children[0].children[1]), 'Turn off files in the projects you pick');
  }, { projects: MEDIUM_PROJECTS });
});

test('an error after a step starts is reported, not lost', async () => {
  await onFilesPanel(async (drawer) => {
    const saved = { error: console.error, byId: globalThis.document.getElementById };
    const logged = [];
    console.error = (error) => logged.push(error);
    globalThis.document.getElementById = () => null;
    drawer.contains = () => { throw new Error('the panel broke'); };
    try {
      held(FILES_HELD, { detail: FILES_TOOLS, projects: MEDIUM_PROJECTS }).actions[0].run();
      await wait(50);
    } finally {
      Object.assign(console, { error: saved.error });
      globalThis.document.getElementById = saved.byId;
    }
    assert.deepEqual(logged.map((error) => error.message), ['the panel broke']);
  }, { projects: MEDIUM_PROJECTS });
});

test("a tick replaces a row for that project that waits with another state", async () => {
  await onFilesPanel(async (drawer) => {
    // sandbox's "Use the shared rule…" waits for write_file: same project, another state.
    await review({ action: 'gateway.rule', targets: [], params: { server: 'files', tool: 'write_file', state: null, project: 'sand' } });
    await click(control(drawer, SOME));
    await wait(50);
    const sandbox = control(drawer, 'tick:sand');
    assert.deepEqual([sandbox.attributes['aria-checked'], textOf(drawer.children[3])], ['false', 'Tick projects. Each one waits in preview until Apply.']);
    await click(sandbox);
    assert.deepEqual(tray.rows.map((r) => r.body), [offIn('write_file', 'sand')]);
    assert.equal(sandbox.attributes['aria-checked'], 'true');
  }, { open: () => showTool('files', 'write_file'), projects: MEDIUM_PROJECTS });
});

test('turning on in some projects says which have it on already', async () => {
  // delete_file is off for all projects; atlas turns it on.
  const rules = { ...FILES_TOOLS, projects: FILES_TOOLS.projects.map((p) => ({ ...p, tools: { delete_file: p.id === 'atlas' ? 'on' : 'off' }, own: p.id === 'atlas' ? ['delete_file'] : [] })) };
  await onFilesPanel(async (drawer) => {
    await click(control(drawer, 'action:Turn on in some projects…'));
    await wait(50);
    assert.equal(textOf(drawer.children[0].children[1]), 'Turn on delete_file in the projects you pick');
    assert.equal(textOf(drawer.children[1].children[0]), 'The shared rule stays off.');
    assert.deepEqual(pickRows(drawer).map((r) => r.slice(0, 3)), [
      ['atlas', '1 own rule · already on', true],
      ['old-app', 'Folder missing · off now', false],
      ['sandbox', 'off now', false],
      ['web', '1 own rule · off now', false],
      ['website', 'off now', false],
    ]);
  }, { rules, open: () => showTool('files', 'delete_file'), projects: MEDIUM_PROJECTS });
});

test('back from the tool step keeps the warning the panel had', async () => {
  await onFilesPanel(async (drawer) => {
    const says = () => textOf(drawer.children[1]).includes('files did not list its tools.');
    const write = FILES_HELD.tool_list.find((t) => t.name === 'write_file');
    const card = toolCard(write, FILES_HELD, { linked: LINKED, detail: FILES_TOOLS.tools[1], rules: FILES_TOOLS, projects: MEDIUM_PROJECTS, warning: 'files did not list its tools.' });
    card.actions.find((a) => a.label === 'Turn off in some projects…').run();
    await wait(50);
    assert.equal(textOf(drawer.children[0].children[1]), 'Turn off write_file in the projects you pick');
    await click(drawer.children[0].children[0].children[0]);
    await wait(50);
    assert.equal(textOf(drawer.children[0].children[1]), 'write_file');
    assert.equal(says(), true);
  }, { open: () => showTool('files', 'write_file'), projects: MEDIUM_PROJECTS });
});

test('a tick names the projects whose chain reaches it, as the gateway decides', async () => {
  // The gateway's chains (`up`, nearest first): web and docs sit in atlas, notes too but with a
  // server rule of its own, api in site. The home folder claims no folder under it.
  const at = (id, path, up = [], own = false) => ({ project: { id, path, own_rules: own ? 1 : 0, exists: true }, entry: { id, server: 'on', tools: {}, own: [], own_server: own, up } });
  const list = [
    at('home', '/Users/amanda'), at('atlas', '/Users/amanda/work/atlas'), at('web', '/Users/amanda/work/atlas/web', ['atlas']),
    at('docs', '/Users/amanda/work/atlas/docs', ['atlas']), at('notes', '/Users/amanda/work/atlas/notes', ['atlas'], true),
    at('site', '/Users/amanda/work/site'), at('api', '/Users/amanda/work/site/api', ['site']),
  ];
  const rules = { ...FILES_TOOLS, projects: list.map((p) => p.entry) };
  const projects = list.map((p) => p.project);
  await onFilesPanel(async (drawer) => {
    await held(FILES_HELD, { detail: rules, projects }).more.find((a) => a.label === 'Turn off in some projects…').run();
    await wait(50);
    const follows = drawer.children[1].children[1];
    const lines = () => follows.children.map(textOf);
    // The home folder: nobody follows it.
    await click(control(drawer, 'tick:home'));
    assert.deepEqual(lines(), []);
    // atlas: web and docs follow it; notes has its own rule.
    await click(control(drawer, 'tick:atlas'));
    assert.deepEqual(lines(), ['docs, web follow atlas and change with it.']);
    // Each ticked parent names its own; a ticked child no longer follows.
    await click(control(drawer, 'tick:site'));
    await click(control(drawer, 'tick:docs'));
    assert.deepEqual(lines(), ['web follows atlas and changes with it.', 'api follows site and changes with it.']);
  }, { rules, projects });
});

// Links on the map ------------------------------------------------------------------------------

const { clickLink, gatewayTree, linkParts, rowsOnMap } = await import('../../src/kitden/web/static/js/gateway.js');
const { keyFor } = await import('../../src/kitden/web/static/js/tray.js');
// The Kitden gateway holding files, and a link of its map by its "from>to" key.
const FILES_VIEW = { ...VIEW, gateways: [{ ...KITDEN, servers: [FILES_HELD] }] };
const linkFor = (key, { picked = '', setup = SETUP } = {}) => linkParts(gatewayTree(FILES_VIEW, { setup, clients: CLIENTS, picked }), key, picked);
const titleOf = (card) => card.title.map(textOf).join('');

test('a link says what it joins, where it is written and what its button does', async () => {
  // A client's link to the Kitden gateway: Disconnect.
  const client = linkCard(linkFor('client:codex>gateway:kitden'), { linked: LINKED, view: FILES_VIEW });
  assert.deepEqual([client.kind, titleOf(client), client.id], ['Connection', 'Codex → Kitden gateway', 'Route through the gateway']);
  assert.deepEqual(facts(client), [['From', 'Codex'], ['To', 'Kitden gateway'], ['State', 'In place'], ['Written in', "Codex's settings"]]);
  assert.equal(textOf(client.why), "Codex calls 1 server through Kitden, so Kitden's rules apply to them.");
  assert.deepEqual(labels(client), ['Disconnect Codex…']);
  // A tool's link, in a project: its rule is in the gateway's own file (gateway.json holds rules too).
  const tool = linkCard(linkFor('held:kitden:files>tool:files/read_file', { picked: 'p1' }), { linked: LINKED, view: FILES_VIEW, picked: 'p1', folder: 'atlas' });
  assert.deepEqual([titleOf(tool), tool.id, facts(tool).at(-1)], ['files → read_file', 'Tool on', ['Written in', "Kitden's gateway file"]]);
  assert.equal(textOf(tool.why), 'read_file is on in atlas: Claude Code and Codex can call it through Kitden.');
  assert.deepEqual(labels(tool), ['Turn off read_file…']);
  // A server's link, while Kitden does not know who uses the gateway.
  const held = linkCard(linkFor('gateway:kitden>held:kitden:files'), { linked: null, view: FILES_VIEW });
  assert.equal(textOf(held.why), 'The gateway holds files and passes its tools that are on to the clients that use it.');
  // A server a client sets up on its own: a direct route, which can lose that client's entry.
  const direct = linkCard(linkFor('client:claude_code>outside:move:github'), { linked: LINKED, view: FILES_VIEW });
  assert.deepEqual([direct.id, facts(direct).slice(2)], ['Direct route', [['State', 'In place'], ['Written in', "Claude Code's settings"]]]);
  assert.equal(textOf(direct.why), "Claude Code calls github on its own. Kitden's rules don't reach it.");
  assert.deepEqual(labels(direct), ['Remove github from Claude Code…']);
  // Its button adds the change, as the link's × does, and the panel says it waits; a second press
  // takes it out.
  await withTray(() => [client.facts[2].value, client.why, client.actions[0].node], async ([lamp, why, remove]) => {
    await click(remove);
    assert.deepEqual(tray.rows.map((r) => [r.body, r.icon]), [[DISCONNECT('codex'), 'plug']]);
    assert.deepEqual([lamp, why, remove].map(textOf), ['In preview', 'This link is a change in preview. Nothing is written until you Apply.', 'Take it out of the preview']);
    await click(remove);
    assert.deepEqual(tray.rows, []);
    assert.deepEqual([lamp, remove].map(textOf), ['In place', 'Disconnect Codex…']);
  });
});

test('a bypass, a registered and a plugin client link open their panel; only the bypass has a remove', () => {
  // A server Claude Code sets up on its own: its × removes Claude Code's own entry.
  const direct = linkFor('client:claude_code>outside:move:github');
  assert.deepEqual(direct.removal, { tip: 'Remove github from Claude Code', body: { action: 'mcp.remove_direct', targets: [{ item: 'g' }], params: {} } });
  assert.deepEqual(labels(linkCard(direct, { linked: LINKED, view: FILES_VIEW })), ['Remove github from Claude Code…']);
  // A registered gateway's links: where its tools are set, and no button.
  const meta = { id: 'gw-2', kind: 'metamcp', url: 'http://127.0.0.1:12008/metamcp/local/mcp', movable: true, managed: true };
  const view = { ...FILES_VIEW, gateways: [...FILES_VIEW.gateways, meta], used: ['gw-2', 'kitden'], connections: { ...VIEW.connections, 'gw-2': { claude_code: [], codex: ['x'], cursor: [] } } };
  const tree = gatewayTree(view, { setup: SETUP, clients: CLIENTS, held: new Map([['gw-2', { servers: [{ name: 'x', type: 'STREAMABLE_HTTP' }] }]]) });
  const route = linkCard(linkParts(tree, 'client:codex>gateway:gw-2', ''), { linked: LINKED, view });
  assert.deepEqual([titleOf(route), route.id, labels(route), facts(route).at(-1)], ['Codex → MetaMCP', 'Route through the gateway', [], ['Written in', "Codex's settings"]]);
  assert.equal(textOf(route.why), 'Tools and access are set in MetaMCP itself.');
  const held = linkCard(linkParts(tree, 'gateway:gw-2>held:gw-2:x', ''), { linked: LINKED, view });
  assert.deepEqual([held.id, labels(held), facts(held).map(([label]) => label)], ['Held by the gateway', [], ['From', 'To', 'State']]);
  // A plugin gives Cursor its entry: no Disconnect, and the panel says why.
  const plugin = linkCard(linkFor('client:cursor>gateway:kitden', { setup: [...SETUP.slice(0, 2), entry('cursor', 'plugin')] }), { linked: ['claude_code', 'codex', 'cursor'], view: FILES_VIEW });
  assert.deepEqual(labels(plugin), []);
  assert.ok(textOf(plugin.why).endsWith('Cursor gets Kitden from a plugin: turn the plugin off to disconnect it.'), textOf(plugin.why));
  // Where it is written says only what is true: a plugin's files for a plugin's entry or server;
  // nothing for a line that also, or only, comes from the Desktop Code tab.
  assert.deepEqual(facts(plugin).at(-1), ['Written in', "A plugin's files"]);
  // The same client's route to a registered gateway is its own entry: written in its settings.
  const routes = { ...view, connections: { ...view.connections, 'gw-2': { claude_code: [], codex: ['x'], cursor: ['x'] } } };
  const pluginSetup = [...SETUP.slice(0, 2), entry('cursor', 'plugin')];
  const ownTree = gatewayTree(routes, { setup: pluginSetup, clients: CLIENTS, held: new Map([['gw-2', { servers: [{ name: 'x', type: 'STREAMABLE_HTTP' }] }]]) });
  const ownRoute = linkParts(ownTree, 'client:cursor>gateway:gw-2', '');
  assert.equal(ownRoute.from.viaPlugin, true);
  assert.deepEqual(facts(linkCard(ownRoute, { linked: ['claude_code', 'codex', 'cursor'], view: routes })).at(-1), ['Written in', "Cursor's settings"]);
  const linear = row('linear', 'claude_code', [], { stays: 'with the plugin' });
  const desktop = { ...row('notion', 'claude_code', ['n']), clients: ['claude_desktop_code_tab'] };
  const both = { ...row('slack', 'claude_code', ['s1', 's2']), clients: ['claude_code', 'claude_desktop_code_tab'] };
  const more = { ...FILES_VIEW, groups: { move: [desktop, both], local: [], plugin: [linear] } };
  const lineIn = (key) => linkCard(linkParts(gatewayTree(more, { setup: SETUP, clients: CLIENTS }), key, ''), { linked: LINKED, view: more });
  assert.deepEqual(facts(lineIn('client:claude_code>outside:plugin:linear')).at(-1), ['Written in', "A plugin's files"]);
  assert.deepEqual(facts(lineIn('client:claude_code>outside:move:notion')).map(([label]) => label), ['From', 'To', 'State']);
  assert.deepEqual(facts(lineIn('client:claude_code>outside:move:slack')).map(([label]) => label), ['From', 'To', 'State']);
});

test('a second click on a picked link whose change waits lets go and keeps the change', async () => {
  const key = 'gateway:kitden>held:kitden:files';
  const REMOVE = { action: 'gateway.remove', targets: [], params: { server: 'files' } };
  const treeNow = () => gatewayTree(data.gateway, { setup: data.setupServer, clients: data.clients, rows: rowsOnMap(tray) });
  const linkIn = (tree, at) => tree.links.find((l) => `${l.from}>${l.to}` === at);
  const open = () => clickLink(treeNow(), linkIn(treeNow(), key));
  await onFilesPanel(async (drawer) => {
    await click(drawer.children[2].children[0]);
    await wait(20);
    // The row has its part: the map draws the link leaving, with its row.
    const drawn = treeNow();
    assert.equal(linkIn(drawn, key).row, keyFor(REMOVE));
    clickLink(drawn, linkIn(drawn, key));
    await wait(20);
    assert.equal(isPanelOpen(), false);
    assert.deepEqual(tray.rows.map((r) => r.body), [REMOVE]);
    // Not picked any more: a click on the leaving link takes its row out (D12).
    clickLink(drawn, linkIn(drawn, key));
    await wait(20);
    assert.deepEqual(tray.rows, []);
    // Escape closes the panel as panel.js does; a click then picks the link again.
    open();
    await wait(400);
    assert.equal(isPanelOpen(), true);
    closePanel({ instant: true });
    open();
    await wait(400);
    assert.deepEqual([isPanelOpen(), panelState.current], [true, { type: 'link', key }]);
    // A bypass link opens its own panel too.
    const bypass = 'client:claude_code>outside:move:github';
    clickLink(treeNow(), linkIn(treeNow(), bypass));
    await wait(400);
    assert.deepEqual([textOf(drawer.children[0].children[1]), textOf(drawer.children[2].children[0])], ['Claude Code → github', 'Remove github from Claude Code…']);
  }, { open });
});

test('a click on a link opens the connection panel; a second click lets go', async () => {
  const key = 'gateway:kitden>held:kitden:files';
  let tree = null;
  let link = null;
  const open = () => {
    tree = gatewayTree(data.gateway, { setup: data.setupServer, clients: data.clients });
    link = tree.links.find((l) => `${l.from}>${l.to}` === key);
    clickLink(tree, link);
  };
  await onFilesPanel(async (drawer) => {
    assert.deepEqual(panelState.current, { type: 'link', key });
    const [head, body, footer] = drawer.children;
    assert.deepEqual([head.children[0].children[0].textContent, textOf(head.children[1]), textOf(head.children[2])], ['Connection', 'Kitden gateway → files', 'Held by the gateway']);
    const [list, why] = body.children;
    assert.deepEqual(list.children.map(textOf), ['From', 'Kitden gateway', 'To', 'files', 'State', 'In place', 'Written in', "Kitden's gateway file"]);
    assert.equal(textOf(why), 'The gateway holds files and passes its tools that are on to 2 clients.');
    assert.equal(textOf(footer.children[0]), 'Remove files from the gateway…');
    // The button adds the removal; the panel says it waits, and takes it out again.
    await click(footer.children[0]);
    await wait(20);
    assert.deepEqual(tray.rows.map((r) => [r.body, r.icon]), [[{ action: 'gateway.remove', targets: [], params: { server: 'files' } }, 'x']]);
    assert.deepEqual([textOf(list.children[5]), textOf(footer.children[0])], ['In preview', 'Take it out of the preview']);
    await click(footer.children[0]);
    await wait(20);
    assert.deepEqual(tray.rows, []);
    // A second click on the same link lets go: the panel closes.
    clickLink(tree, link);
    assert.equal(isPanelOpen(), false);
  }, { open });
});
