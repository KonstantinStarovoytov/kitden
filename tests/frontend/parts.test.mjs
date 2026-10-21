import assert from 'node:assert/strict';
import { test } from 'node:test';

// parts.js needs only these from a browser to load. The stub element knows classes,
// attributes, children and class selectors (".word, .where"); `media` is reduced motion.
const media = { matches: false };
globalThis.matchMedia = () => media;
function element(tag) {
  const node = {
    tag, className: '', textContent: '', children: [], attributes: {}, dataset: {}, parent: null,
    get childNodes() { return node.children; },
    classList: {
      contains: (name) => node.className.split(' ').includes(name),
      add: (name) => { if (!node.classList.contains(name)) node.className = `${node.className} ${name}`.trim(); },
      remove: (name) => { node.className = node.className.split(' ').filter((c) => c !== name).join(' '); },
    },
    append(...nodes) { for (const n of nodes) { n.parent = node; node.children.push(n); } },
    replaceChildren(...nodes) { node.children = []; node.append(...nodes); },
    replaceWith(other) { node.parent.children[node.parent.children.indexOf(node)] = other; other.parent = node.parent; },
    matches: (selector) => selector.split(',').some((s) => node.classList.contains(s.trim().slice(1))),
    querySelectorAll: (selector) => node.children.flatMap((c) => [...(c.matches(selector) ? [c] : []), ...c.querySelectorAll(selector)]),
    querySelector: (selector) => node.querySelectorAll(selector)[0] || null,
    setAttribute(name, value) { node.attributes[name] = value; },
    getAttribute: (name) => node.attributes[name] ?? null,
    hasAttribute: (name) => name in node.attributes,
    removeAttribute(name) { delete node.attributes[name]; },
    addEventListener(type, listener) { node.listeners = { ...node.listeners, [type]: listener }; },
  };
  return node;
}
globalThis.document = { createElement: element };
const { banner, changeTitle, clientCheck, gatewayName, morphSocket, opens, socket } = await import('../../src/kitden/web/static/js/parts.js');

test('a row that opens Details ends with a chevron for the eye and words for a screen reader', () => {
  const node = opens();
  assert.equal(node.className, 'opens');
  const [chevron, words] = node.children;
  assert.equal(chevron.textContent, '›');
  assert.equal(chevron.attributes['aria-hidden'], 'true');
  assert.equal(words.className, 'sr-only');
  assert.equal(words.textContent, 'Open details');
});

test('a client checkbox is named for its client and keeps the client id as its value', () => {
  const heard = [];
  const label = clientCheck('codex', true, null, (checked) => heard.push(checked));
  const [box, name] = label.children;
  assert.equal(label.tag, 'label');
  assert.equal(box.type, 'checkbox');
  assert.equal(box.value, 'codex');
  assert.equal(box.checked, true);
  assert.equal(box.attributes['aria-label'], 'Codex');
  assert.equal(name.textContent, 'Codex');
  box.checked = false;
  box.listeners.change();
  assert.deepEqual(heard, [false]);
});

test('a note after the client name is read as part of its name', () => {
  const label = clientCheck('claude_code', false, 'adds the marketplace first');
  const [box, name, note] = label.children;
  assert.equal(box.checked, false);
  assert.equal(box.attributes['aria-label'], 'Claude Code · adds the marketplace first');
  assert.equal(name.textContent, 'Claude Code');
  assert.equal(note.textContent, ' · adds the marketplace first');
});

test('with reduced motion a changed socket shows its new word at once, never faded', () => {
  media.matches = true;
  try {
    const node = socket({ state: 'off' });
    morphSocket(node, { state: 'on', where: 'global' });
    assert.equal(node.className, 'socket s-on');
    assert.equal(node.querySelector('.word').textContent, 'Loads');
    assert.equal(node.querySelector('.where').textContent, 'global');
    assert.equal(node.querySelectorAll('.swap').length, 0);
  } finally {
    media.matches = false;
  }
});

test('a socket that morphs into a dash keeps the reason it was given', () => {
  media.matches = true;
  try {
    const reason = "Codex can't install this plugin, and it has no skills to copy.";
    const node = socket({ state: 'on' });
    morphSocket(node, { state: 'none', label: reason });
    assert.equal(node.className, 'socket s-none');
    assert.equal(node.attributes['aria-label'], reason);
    // Without a reason it says what it always said.
    const plain = socket({ state: 'on' });
    morphSocket(plain, { state: 'none' });
    assert.equal(plain.attributes['aria-label'], 'Not set up');
    // The words the server sent stay through the morph.
    const done = socket({ state: 'off' });
    morphSocket(done, { state: 'done', word: 'Has its skills' });
    assert.equal(done.querySelector('.word').textContent, 'Has its skills');
  } finally {
    media.matches = false;
  }
});

// A page with the banner on it; `focused` says what got keyboard focus after the Retry.
function retryOn({ failsAgain, focusKept = false }) {
  const focused = [];
  const control = (name) => ({ focus: () => focused.push(name) });
  const main = {
    contains: () => focusKept,
    querySelector: (selector) => (selector === '.banner button' ? (failsAgain ? control('new Retry') : null) : control('first control')),
    focus: () => focused.push('main'),
  };
  globalThis.document.querySelector = (selector) => (selector === '#main' ? main : null);
  let retried = 0;
  const node = banner('the load map', async () => { retried += 1; });
  const retry = node.children.find((c) => c.tag === 'button');
  return { focused, press: async () => { await retry.listeners.click(); return retried; } };
}

test('after a Retry that works, focus goes to the first control on the page', async () => {
  const page = retryOn({ failsAgain: false });
  assert.equal(await page.press(), 1);
  assert.deepEqual(page.focused, ['first control']);
});

test('after a Retry that fails again, focus goes to the new Retry button', async () => {
  const page = retryOn({ failsAgain: true });
  await page.press();
  assert.deepEqual(page.focused, ['new Retry']);
});

test('a redraw that kept focus on the page is left alone', async () => {
  const page = retryOn({ failsAgain: false, focusKept: true });
  await page.press();
  assert.deepEqual(page.focused, []);
});

test('an Add skills entry on the Changes page counts the skills, not every name', () => {
  const step = (name) => ({ client: 'codex', name, reaches: ['codex', 'cursor'] });
  assert.equal(changeTitle({ action: 'plugin.skills', steps: [step('a'), step('b'), step('c')] }), 'Added 3 skills · Codex, Cursor');
  assert.equal(changeTitle({ action: 'plugin.skills', steps: [step('a')] }), 'Added 1 skill · Codex, Cursor');
});

test('the Changes page names what moved into the Kitden gateway and which rule changed', () => {
  const steps = [
    { client: 'kitden', name: 'files' }, { client: 'kitden', name: 'PATH' },
    { client: 'claude_code', name: 'files' }, { client: 'cursor', name: 'files' },
    { client: 'cursor', name: 'kitden' }, { client: 'codex', name: 'kitden' },
  ];
  assert.equal(changeTitle({ action: 'gateway.move', steps }), 'Moved files into the Kitden gateway · Claude Code, Cursor');
  const obot = [{ client: 'gateway', name: 'docs' }, { client: 'cursor', name: 'docs' }];
  assert.equal(changeTitle({ action: 'gateway.move', steps: obot }), 'Moved into the gateway docs · Cursor');
  // The Kitden gateway holds files as it is already: only the client's entry goes.
  const held = [{ client: 'cursor', name: 'files' }];
  assert.equal(changeTitle({ action: 'gateway.move', steps: held }), 'Moved files into the Kitden gateway · Cursor');
  // A rule names its tool, server, project and new state, as the review did.
  const slow = [{ client: 'kitden', name: 'slow' }];
  const rule = (fields) => changeTitle({ action: 'gateway.rule', steps: slow, rule: { server: 'echo', tool: 'slow', project: 'website', state: 'off', ...fields } });
  assert.equal(rule({}), 'Turned off slow of echo in website');
  assert.equal(rule({ tool: null, project: null, state: 'on' }), 'Turned on echo in all projects');
  assert.equal(rule({ state: null }), 'slow of echo in website follows all projects');
  // An old record without the rule's parts names what it has.
  assert.equal(changeTitle({ action: 'gateway.rule', steps: slow }), 'Changed the rule for slow · Kitden gateway');
});

test('a gateway goes by its own name, its kind, or its address', () => {
  assert.equal(gatewayName({ kind: 'kitden', name: 'Kitden gateway' }), 'Kitden gateway');
  assert.equal(gatewayName({ kind: 'obot', url: 'http://127.0.0.1:8080/mcp-connect/x' }), 'Obot');
  assert.equal(gatewayName({ url: 'http://127.0.0.1:12008/metamcp/local/mcp' }), 'MetaMCP');
  assert.equal(gatewayName({ url: 'https://tools.example.com/mcp' }), 'tools.example.com');
});

// The first scan: one quiet line that says what is still read, and how much is done.
const { scanLine } = await import('../../src/kitden/web/static/js/parts.js');

test('the scan line names what is still read, and how far it got', () => {
  const steps = (done) => ['Claude Code', 'Codex', 'Cursor', 'Codex plugins', 'marketplaces'].map((name, i) => ({ name, done: done.includes(i), later: i >= 3 }));
  assert.equal(scanLine(null), null);
  assert.equal(scanLine({ ready: true, steps: [] }), null);
  assert.equal(scanLine({ ready: true, steps: steps([0, 1, 2, 3, 4]) }), null);
  assert.deepEqual(scanLine({ ready: false, steps: steps([0]) }), { text: 'Reading Codex and Cursor…', share: 0.2 });
  assert.deepEqual(scanLine({ ready: true, steps: steps([0, 1, 2]) }), { text: 'Still checking Codex plugins and marketplaces…', share: 0.6 });
});
