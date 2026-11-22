import assert from 'node:assert/strict';
import { test } from 'node:test';

// The clients panel and the places that draw all three clients. A stand-in document keeps the nodes
// the builders make; no page is drawn.
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
const posted = [];
globalThis.fetch = async (url, init) => { posted.push([url, init && init.body]); return { ok: true, status: 200, json: async () => ({}) }; };

const { choiceCard, choiceRows, CHOICE_NOTE, CHOICE_TITLE, LAST_ON } = await import('../../src/kitden/web/static/js/clients-choice.js');
const { gatewayTree } = await import('../../src/kitden/web/static/js/gateway.js');
const { clientRows } = await import('../../src/kitden/web/static/js/gateway-details.js');
const { lookFor, shownClients } = await import('../../src/kitden/web/static/js/parts.js');
const { noClients } = await import('../../src/kitden/web/static/js/library.js');
const { data } = await import('../../src/kitden/web/static/js/store.js');

const NAMES = { claude_code: 'Claude Code', codex: 'Codex', cursor: 'Cursor' };
const client = (id, status, version = null) => ({ id, display_name: NAMES[id], status, version, config_roots: [`/home/me/.${id}`] });
const ALL = [client('claude_code', 'found', '2.1.311'), client('codex', 'found', '0.159.2'), client('cursor', 'not_found')];
const entry = (id, state) => ({ client: id, state, item: null, command_exists: null, enabled: state === 'added' ? true : null, moved: false });
const words = (node) => (node.children && node.children.length ? node.children.map(words).join('|') : node.textContent);
const walk = (node) => (node.children || []).flatMap((child) => [child, ...walk(child)]);

test('the panel has a row per client: its words, and a switch that shows whether it is read', () => {
  const rows = choiceRows(ALL, [entry('claude_code', 'missing'), entry('codex', 'missing'), entry('cursor', 'not_installed')]);
  assert.deepEqual(rows.map((r) => [r.id, r.name, r.words, r.on, r.last, r.gateway]), [
    ['claude_code', 'Claude Code', '2.1.311', true, false, null],
    ['codex', 'Codex', '0.159.2', true, false, null],
    ['cursor', 'Cursor', 'Not found on this computer', true, false, null],
  ]);
  const off = choiceRows([ALL[0], client('codex', 'off'), ALL[2]], []);
  assert.deepEqual(off.map((r) => [r.words, r.on]), [['2.1.311', true], ['Off', false], ['Not found on this computer', true]]);
});

test('the last client that is on has a disabled switch with the same words as its hover text', () => {
  const clients = [client('claude_code', 'found', '2.1.311'), client('codex', 'off'), client('cursor', 'off')];
  const rows = choiceRows(clients, []);
  assert.deepEqual(rows.map((r) => r.last), [true, false, false]);
  const card = choiceCard(clients, [], () => {});
  const switches = walk(card.list).filter((n) => n.attributes.role === 'switch');
  assert.deepEqual(switches.map((n) => [n.attributes['aria-checked'], Boolean(n.disabled)]), [['true', true], ['false', false], ['false', false]]);
  assert.equal(switches[0].title, LAST_ON);
  assert.equal(LAST_ON, 'Keep at least one client on.');
  // With another client on, no switch is disabled.
  const two = choiceCard(ALL, [], () => {});
  assert.deepEqual(walk(two.list).filter((n) => n.attributes.role === 'switch').map((n) => Boolean(n.disabled)), [false, false, false]);
});

test('the card says what the panel is for, and a press turns that client the other way', () => {
  const pressed = [];
  const card = choiceCard(ALL, [], (id, on) => pressed.push([id, on]));
  assert.equal(card.kind, 'Clients');
  assert.equal(card.title, 'Which clients Kitden reads');
  assert.equal(CHOICE_TITLE, card.title);
  assert.equal(card.text.textContent, "Kitden stops reading a client that is off. Nothing in the client's own settings changes.");
  assert.equal(CHOICE_NOTE, card.text.textContent);
  const switches = walk(card.list).filter((n) => n.attributes.role === 'switch');
  assert.deepEqual(switches.map((n) => n.dataset.focus), ['client:claude_code', 'client:codex', 'client:cursor']);
  switches[1].listeners.click[0]();
  assert.deepEqual(pressed, [['codex', false]]);
  const off = choiceCard([ALL[0], client('codex', 'off'), ALL[2]], [], (id, on) => pressed.push([id, on]));
  walk(off.list).filter((n) => n.attributes.role === 'switch')[1].listeners.click[0]();
  assert.deepEqual(pressed.at(-1), ['codex', true]);
});

test('a client that uses the Kitden gateway says so before its switch is pressed', () => {
  const rows = choiceRows(ALL, [entry('claude_code', 'missing'), entry('codex', 'added'), entry('cursor', 'not_installed')]);
  assert.deepEqual(rows.map((r) => r.gateway), [null, 'Codex uses the Kitden gateway. Turning it off here does not disconnect it.', null]);
  const card = choiceCard(ALL, [entry('codex', 'added')], () => {});
  assert.ok(walk(card.list).some((n) => n.textContent.startsWith('Codex uses the Kitden gateway.')));
  // An entry that is turned off does not start it.
  assert.equal(choiceRows(ALL, [{ ...entry('codex', 'added'), enabled: false }])[1].gateway, null);
});

test('shownClients and lookFor leave out a client that is off, and keep one that is only not installed', () => {
  assert.deepEqual(shownClients(undefined), ['claude_code', 'codex', 'cursor']);
  const clients = [ALL[0], client('codex', 'off'), ALL[2]];
  assert.deepEqual(shownClients(clients), ['claude_code', 'cursor']);
  assert.deepEqual(lookFor(clients).map((c) => c.name), ['Claude Code', 'Cursor']);
});

test('no clients found names only the clients that are on', () => {
  data.clients = [client('claude_code', 'not_found'), client('codex', 'off'), client('cursor', 'not_found')];
  const sentence = walk(noClients()).find((n) => n.textContent.startsWith('It looks for'));
  assert.equal(sentence.textContent, 'It looks for Claude Code and Cursor.');
  data.clients = undefined;
});

test('the Gateway map has no block for a client that is off, and one for a client not installed', () => {
  const view = { gateways: [{ id: 'kitden', kind: 'kitden', name: 'Kitden gateway', servers: [] }], connections: {}, used: [], groups: { move: [], local: [], plugin: [] } };
  const setup = [entry('claude_code', 'missing'), entry('cursor', 'not_installed')];
  const clients = [client('claude_code', 'found', '2.1.311'), client('codex', 'off'), client('cursor', 'not_found')];
  const ids = (tree) => tree.blocks.filter((b) => b.kind === 'client').map((b) => b.id);
  assert.deepEqual(ids(gatewayTree(view, { setup, clients })), ['client:claude_code', 'client:cursor']);
  assert.deepEqual(ids(gatewayTree(view, { setup, clients: [clients[0], client('codex', 'found', '1'), clients[2]] })), ['client:claude_code', 'client:codex', 'client:cursor']);
});

test('the Gateway panel lists no client that is off', () => {
  const clients = [client('claude_code', 'found', '2.1.311'), client('codex', 'off'), client('cursor', 'not_found')];
  const section = clientRows([entry('claude_code', 'missing'), entry('cursor', 'not_installed')], clients);
  const names = walk(section).filter((n) => n.tag === 'b').map((n) => n.textContent);
  assert.deepEqual(names, ['Claude Code', 'Cursor']);
});
