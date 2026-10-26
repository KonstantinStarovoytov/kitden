import assert from 'node:assert/strict';
import { beforeEach, mock, test } from 'node:test';

// parts.js needs only these from a browser to load. The stub element knows classes,
// attributes, children and class selectors (".word, .tag"); `media` is reduced motion.
const media = { matches: false };
globalThis.matchMedia = () => media;
function element(tag) {
  const node = {
    tag, className: '', textContent: '', children: [], attributes: {}, dataset: {}, parent: null,
    get childNodes() { return node.children; },
    get lastElementChild() { return node.children[node.children.length - 1] || null; },
    remove() { if (node.parent) node.parent.children = node.parent.children.filter((c) => c !== node); },
    classList: {
      contains: (name) => node.className.split(' ').includes(name),
      add: (name) => { if (!node.classList.contains(name)) node.className = `${node.className} ${name}`.trim(); },
      remove: (name) => { node.className = node.className.split(' ').filter((c) => c !== name).join(' '); },
      toggle: (name, on) => node.classList[on ? 'add' : 'remove'](name),
    },
    focus() { globalThis.document.activeElement = node; },
    contains(other) { for (let at = other; at; at = at.parent) if (at === node) return true; return false; },
    scrollIntoView() {},
    append(...nodes) { for (const n of nodes) { n.parent = node; node.children.push(n); } },
    replaceChildren(...nodes) { node.children = []; node.append(...nodes); },
    replaceWith(other) { node.parent.children[node.parent.children.indexOf(node)] = other; other.parent = node.parent; },
    matches: (selector) => selector.split(',').some((s) => {
      const one = s.trim();
      return one.startsWith('.') ? node.classList.contains(one.slice(1)) : node.tag === one;
    }),
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
// Each test starts with motion on; a test that needs reduced motion sets it itself.
beforeEach(() => { media.matches = false; });
globalThis.document = { createElement: element, createElementNS: (namespace, tag) => element(tag) };
const { backupNote, banner, baseNames, changeTitle, checkBox, clientCheck, demoTag, folderName, gatewayName, menuItems, morphSocket, opens, optionAfter, originText, PLACE_IN_TITLE, projectButton, projectMenu, scopeBar, scopeText, setHint, socket, strictText, TOOL_ORIGIN_WORDS } = await import('../../src/kitden/web/static/js/parts.js');
const { CALM } = await import('../../src/kitden/web/static/js/motion.js');
// details.js builds the switch and loads with the same stand-in.
const { switchNode } = await import('../../src/kitden/web/static/js/details.js');

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
  const [box, tick, name] = label.children;
  assert.equal(label.tag, 'label');
  assert.equal(tick.className, 'chk');
  assert.equal(box.type, 'checkbox');
  assert.equal(box.value, 'codex');
  assert.equal(box.checked, true);
  assert.equal(box.attributes['aria-label'], 'Codex');
  assert.equal(name.textContent, 'Codex');
  box.checked = false;
  box.listeners.change();
  assert.deepEqual(heard, [false]);
});

test('a checkbox keeps its real input and draws the mockup box with a check in it', () => {
  const [input, box] = checkBox();
  assert.equal(input.tag, 'input');
  assert.equal(input.type, 'checkbox');
  assert.equal(box.className, 'chk');
  assert.equal(box.children.length, 1);
  assert.equal(box.children[0].dataset.icon, 'check');
  assert.equal(box.children[0].attributes['aria-hidden'], 'true');
});

test('switch looks: off and on, and a press runs its change', () => {
  assert.equal(switchNode(false).getAttribute('aria-checked'), 'false');
  assert.equal(switchNode(true).getAttribute('aria-checked'), 'true');
  assert.equal(switchNode(true).getAttribute('role'), 'switch');
  // The knob is the .thumb; the track and the looks are drawn by CSS from the state.
  assert.equal(switchNode(true).children[0].className, 'thumb');
  // A press runs `press`, which adds the change to the tray; the pending look follows the tray
  // (details.test.mjs), and the switch is not flipped.
  let presses = 0;
  const node = switchNode(false, () => { presses += 1; });
  assert.equal(node.title, 'Off. Press to preview turning it on.');
  node.listeners.click();
  assert.equal(presses, 1);
  assert.equal(node.classList.contains('pending'), false);
  assert.equal(node.getAttribute('aria-checked'), 'false');
});

test('a note after the client name is read as part of its name', () => {
  const label = clientCheck('claude_code', false, 'adds the marketplace first');
  const [box, , name, note] = label.children;
  assert.equal(box.checked, false);
  assert.equal(box.attributes['aria-label'], 'Claude Code · adds the marketplace first');
  assert.equal(name.textContent, 'Claude Code');
  assert.equal(note.textContent, ' · adds the marketplace first');
});

test('with reduced motion a changed socket shows its new word at once, never faded', () => {
  media.matches = true;
  try {
    const node = socket({ state: 'off' });
    morphSocket(node, { state: 'on', where: 'This project' });
    assert.equal(node.className, 'socket s-on');
    assert.equal(node.querySelector('.word').textContent, 'On');
    assert.equal(node.querySelector('.tag').textContent, 'This project');
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

test('a plugin removal on the Changes page uses the short name', () => {
  assert.equal(changeTitle({ action: 'plugin.remove', steps: [{ client: 'codex', name: 'browser@openai-bundled' }] }), 'Removed browser · Codex');
});

test('a skill removal on the Changes page names every client that read the folder', () => {
  assert.equal(changeTitle({ action: 'skill.remove', steps: [{ client: 'codex', name: 'tidy', reaches: ['codex', 'cursor'] }] }), 'Removed tidy · Codex, Cursor');
});

test('a skill removal on the Changes page never says removed where a copy still loads', () => {
  const all = { action: 'skill.remove', steps: [{ client: 'codex', name: 'docker-expert', reaches: ['codex', 'cursor'], keeps: ['codex', 'cursor'] }] };
  assert.equal(changeTitle(all), 'Removed one copy of docker-expert · Codex, Cursor');
  const some = { action: 'skill.remove', steps: [{ client: 'claude_code', name: 'tidy', reaches: ['claude_code', 'cursor'], keeps: ['cursor'] }] };
  assert.equal(changeTitle(some), 'Removed tidy · Claude Code');
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
  // A removed rule: what it follows then is not known when the line is read.
  assert.equal(rule({ state: null }), 'slow of echo in website: own setting removed');
  // An old record without the rule's parts names what it has.
  assert.equal(changeTitle({ action: 'gateway.rule', steps: slow }), 'Changed the rule for slow · Kitden gateway');
  // The kitden entry turned on again names its client.
  assert.equal(changeTitle({ action: 'setup_server.enable', steps: [{ client: 'codex', name: 'kitden' }] }), 'Turned on the kitden entry · Codex');
});

test('the Changes page names a client connected to or disconnected from Kitden', () => {
  const entry = (action, ...clients) => ({ action, steps: clients.map((client) => ({ client, name: 'kitden' })), target: { scope: 'all' } });
  assert.equal(changeTitle(entry('client.disconnect', 'codex')), 'Disconnected from Kitden · Codex');
  assert.equal(changeTitle(entry('setup_server.register', 'claude_code', 'cursor')), 'Connected to Kitden · Claude Code, Cursor');
  // A line from before Kitden kept the target reads the same.
  assert.equal(changeTitle({ ...entry('setup_server.register', 'cursor'), target: undefined }), 'Connected to Kitden · Cursor');
  for (const action of ['setup_server.register', 'client.disconnect']) assert.ok(PLACE_IN_TITLE.includes(action), action);
});

test('the Changes page names a server moved out of the gateway and the client it went to', () => {
  const steps = [{ client: 'cursor', name: 'files' }, { client: 'kitden', name: 'files' }, { client: 'kitden', name: 'files' }];
  assert.equal(changeTitle({ action: 'gateway.move_out', steps, target: { scope: 'all' } }), 'Moved out of the gateway · files · Cursor');
  assert.equal(changeTitle({ action: 'gateway.move_out', steps }), 'Moved out of the gateway · files · Cursor');
  assert.ok(PLACE_IN_TITLE.includes('gateway.move_out'));
});

test('a rule says where its state comes from', () => {
  assert.equal(originText({ origin: 'project' }, 'website'), 'This project · website');
  assert.equal(originText({ origin: 'parent', origin_from: 'atlas' }, 'web'), 'From atlas');
  assert.equal(originText({ origin: 'strict' }), 'New · waits');
  assert.equal(originText({ origin: 'global' }), 'All projects');
  assert.equal(originText({ origin: 'default' }), 'On by default');
  assert.equal(originText({}), null);
  assert.deepEqual(TOOL_ORIGIN_WORDS, { global: 'All projects', default: 'On by default', strict: 'New · waits' });
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

// A client's version on the Clients card: while the versions are still read, never "unknown".
const { versionWords, versionsOpened } = await import('../../src/kitden/web/static/js/parts.js');

test('the version says checking while the client versions step is open', () => {
  const progress = (done) => ({ ready: true, steps: [{ name: 'Codex plugins', done: true, later: true }, { name: 'client versions', done, later: true }] });
  assert.equal(versionWords('2.1.300', progress(false), true), '2.1.300');
  assert.equal(versionWords(null, progress(false), true), 'Checking the version…');
  assert.equal(versionWords(null, progress(true), true), 'version unknown');
  assert.equal(versionWords(null, null, true), 'version unknown');
  assert.equal(versionWords(null, { ready: true, steps: [] }, true), 'version unknown');
  // A client that is not installed keeps its own word whatever the step says.
  assert.equal(versionWords(null, progress(false), false), 'version unknown');
});

test('the Clients card is drawn again when the versions step first shows open', () => {
  const progress = (done) => ({ ready: true, steps: [{ name: 'client versions', done, later: true }] });
  assert.equal(versionsOpened(null, progress(false)), true);
  assert.equal(versionsOpened({ ready: false, steps: [] }, progress(false)), true);
  assert.equal(versionsOpened(progress(false), progress(false)), false);
  assert.equal(versionsOpened(progress(false), progress(true)), false);
  assert.equal(versionsOpened(null, progress(true)), false);
  assert.equal(versionsOpened(null, null), false);
});

test('the strict switch names its server and that it is for all projects, in the review and in the log', () => {
  // Strict mode has no project rule: it applies in every project, also from a project view.
  assert.deepEqual(strictText({ server: 'github', state: 'on' }), { title: 'Turn strict mode on for github in all projects', done: 'Turned strict mode on for github in all projects' });
  const steps = [{ client: 'kitden', name: 'github' }, { client: 'kitden', name: 'list_issues' }];
  assert.equal(changeTitle({ action: 'gateway.strict', steps }), 'Changed strict mode for github in all projects · Kitden gateway');
});

test('the Changes page names the tools a batch switch changed', () => {
  const steps = [{ client: 'kitden', name: 'create_issue' }, { client: 'kitden', name: 'delete_issue' }];
  assert.equal(changeTitle({ action: 'gateway.rules', steps }), 'Changed the rules for create_issue, delete_issue · Kitden gateway');
});

test('the Changes page names a server removed from or put back from the Kitden gateway', () => {
  assert.equal(changeTitle({ action: 'gateway.remove', steps: [{ client: 'kitden', name: 'files' }] }), 'Removed files from the Kitden gateway');
  assert.equal(changeTitle({ action: 'gateway.put_back', steps: [{ client: 'codex', name: 'files' }] }), 'Put back files · Codex');
});

test('the Changes page names a server added to the Kitden gateway', () => {
  const steps = [{ client: 'kitden', name: 'test-status' }, { client: 'kitden', name: 'PATH' }, { client: 'codex', name: 'kitden' }];
  assert.equal(changeTitle({ action: 'gateway.add', steps, target: { scope: 'all' } }), 'Added test-status to the Kitden gateway');
});

test('the Changes page names a held server whose secrets moved to the Keychain', () => {
  assert.equal(changeTitle({ action: 'gateway.keychain', steps: [{ client: 'kitden', name: 'files' }] }), 'Moved the secrets of files to the Keychain');
});

test('a change whose backup holds a secret says so', () => {
  assert.equal(backupNote({ holds_secret: true }), "This change's backup or record holds a secret.");
  assert.equal(backupNote({ holds_secret: false }), null);
  assert.equal(backupNote({}), null);
});

test('the Changes page names a server added to another client', () => {
  assert.equal(changeTitle({ action: 'mcp.add', steps: [{ client: 'codex', name: 'github' }] }), 'Added github · Codex');
});

test('Add missing on the Changes page names every client it reached', () => {
  const steps = [{ client: 'codex', name: 'github' }, { client: 'codex', name: 'brandkit', reaches: ['codex', 'cursor'] }];
  assert.equal(changeTitle({ action: 'project.align', steps }), 'Added missing items · Codex, Cursor');
});

const { failedWord } = await import('../../src/kitden/web/static/js/parts.js');

test('a failed change says "put back" only when the engine restored everything', () => {
  assert.equal(failedWord('`claude mcp add` failed: x The original settings were restored.'), 'Failed, put back');
  assert.equal(failedWord('boom `claude plugin install a` failed; a was not put back.'), 'Failed');
  assert.equal(failedWord(null), 'Failed');
});

const { toolsWord } = await import('../../src/kitden/web/static/js/parts.js');

test('a held server says how many tools when it knows', () => {
  assert.equal(toolsWord({ name: 'github', tools: 12 }), '12 tools');
  assert.equal(toolsWord({ name: 'github', tools: 1 }), '1 tool');
  assert.equal(toolsWord({ name: 'github', tools: null }), null);
  assert.equal(toolsWord({ name: 'github' }), null);
});

const { toolsNode } = await import('../../src/kitden/web/static/js/parts.js');

test('the tool count is drawn when it is a number and left out when it is not', () => {
  const row = toolsNode({ name: 'github', tools: 12 }, true);
  assert.equal(row.textContent, '12 tools');
  assert.equal(row.className, 'meta');
  const details = toolsNode({ name: 'github', tools: 1 });
  assert.equal(details.textContent, '1 tool');
  assert.equal(details.className, 'why');
  assert.equal(toolsNode({ name: 'github', tools: null }, true), null);
  assert.equal(toolsNode({ name: 'github' }), null);
});

test('a demo shows a quiet Demo flag; a real page shows none', () => {
  const tag = demoTag({ version: '0.2.0', demo: true });
  assert.equal(tag.textContent, 'Demo');
  assert.equal(tag.className, 'flag info');
  assert.equal(tag.attributes.title, 'A sample setup in a temporary folder. Your own settings are not read or changed.');
  assert.equal(demoTag({ version: '0.2.0', demo: false }), null);
  assert.equal(demoTag(null), null);
});

test('a socket kept from the last good read keeps its dashed dot through a morph', () => {
  media.matches = true;
  try {
    assert.equal(socket({ state: 'on', stale: true }).className, 'socket s-on stale');
    const node = socket({ state: 'off' });
    morphSocket(node, { state: 'on', stale: true });
    assert.equal(node.className, 'socket s-on stale');
  } finally {
    media.matches = false;
  }
});

test('the Changes page names the place a change went, as its review did', () => {
  const neon = { client: 'codex', name: 'neon' };
  const at = (scope, project = null) => ({ action: 'mcp.remove_direct', steps: [neon], target: { scope, project, others_unchanged: false } });
  assert.equal(changeTitle(at('project', '/Users/me/work/website')), 'Removed neon in website · Codex');
  assert.equal(changeTitle(at('all')), 'Removed neon for all projects · Codex');
  assert.equal(changeTitle(at('others', '/Users/me/work/website')), 'Removed neon for all projects except website · Codex');
  assert.equal(changeTitle(at('mixed')), 'Removed neon · Codex');
  // A line from before Kitden kept the place says none; a title that names its place keeps it.
  assert.equal(changeTitle({ action: 'mcp.remove_direct', steps: [neon] }), 'Removed neon · Codex');
  const keychain = { action: 'gateway.keychain', steps: [{ client: 'kitden', name: 'files' }], target: { scope: 'all', project: null } };
  assert.equal(changeTitle(keychain), 'Moved the secrets of files to the Keychain');
});

test('a folder name is the last part of its path, and / stays /', () => {
  assert.equal(folderName('/Users/me/work/website'), 'website');
  assert.equal(folderName('/Users/me/work/website/'), 'website');
  assert.equal(folderName('/'), '/');
  assert.equal(folderName(null), '');
});

const { lookFor, sourceLines } = await import('../../src/kitden/web/static/js/parts.js');

test('no clients: the page names each client and where Kitden looks', () => {
  const client = (id, display_name, root) => ({ id, display_name, status: 'not_found', config_roots: [`/Users/me/${root}`] });
  const clients = [client('claude_code', 'Claude Code', '.claude'), client('codex', 'Codex', '.codex'), client('cursor', 'Cursor', '.cursor'),
    { id: 'claude_desktop_code_tab', display_name: 'Claude Desktop (Code tab)', status: 'found', config_roots: ['/x'] }];
  assert.deepEqual(lookFor(clients), [{ name: 'Claude Code', where: '~/.claude' }, { name: 'Codex', where: '~/.codex' }, { name: 'Cursor', where: '~/.cursor' }]);
  // In client order, whatever order they come in; none read yet, none named.
  assert.deepEqual(lookFor([...clients].reverse()).map((c) => c.name), ['Claude Code', 'Codex', 'Cursor']);
  assert.deepEqual(lookFor(undefined), []);
});

test('a source still being read says so on the tab it changes, not in the top bar words', () => {
  const open = { ready: true, steps: [{ name: 'Codex plugins', done: false, later: true }, { name: 'marketplaces', done: false, later: true }] };
  const LINE = "Codex plugins are still being read, so Codex's column may change.";
  assert.deepEqual(sourceLines(open, 'plugin'), [LINE]);
  assert.deepEqual(sourceLines(open, 'mcp_server'), []);
  assert.deepEqual(sourceLines({ ready: true, steps: [{ name: 'Codex plugins', done: true, later: true }] }, 'plugin'), []);
  assert.deepEqual(sourceLines(null, 'plugin'), []);
  // The top bar keeps "Still checking …"; the line says what it means here, not the same words.
  assert.ok(scanLine(open).text.startsWith('Still checking Codex plugins'));
  assert.ok(!LINE.includes('Still checking'));
});

// The project menu ----------------------------------------------------------------------------

const PROJECTS = [
  { id: 'w', path: '/u/work/website', exists: true, own_rules: 3 },
  { id: 'a', path: '/u/work/api', exists: false, own_rules: 0 },
  { id: 'm', path: '/u/mcp-gateway', exists: true, own_rules: 1 },
];

test('the project menu lists All projects first, then projects by name with their own rules', () => {
  assert.deepEqual(menuItems(PROJECTS, 'm').map((i) => [i.name, i.count, i.sub, i.picked]), [
    ['All projects', null, 'What applies in every project', false], ['api', null, 'Folder missing', false],
    ['mcp-gateway', '1 own rule', null, true], ['website', '3 own rules', null, false]]);
  assert.deepEqual(menuItems(PROJECTS, '').map((i) => i.picked), [true, false, false, false]);
  assert.deepEqual(menuItems(PROJECTS, '', 'WEB').map((i) => i.name), ['All projects', 'website']);
  assert.deepEqual(menuItems([], 'gone').map((i) => i.name), ['All projects', 'No longer on the list']);
  assert.deepEqual(menuItems([], 'gone').map((i) => [i.id, i.picked]), [['', false], ['gone', true]]);
  // No path reaches the menu.
  assert.ok(!JSON.stringify(menuItems(PROJECTS, 'm')).includes('/u/'));
});

test('the scope bar says what the page shows', () => {
  assert.equal(scopeText('', 0), 'Shared setup · project overrides stay separate');
  assert.equal(scopeText('mcp-gateway', 1), 'Project mcp-gateway · 1 rule differs from the shared setup');
  assert.equal(scopeText('mcp-gateway', 3), 'Project mcp-gateway · 3 rules differ from the shared setup');
  // Kitden counts only the gateway's rules: none of its own is not "follows the shared setup".
  assert.equal(scopeText('api', 0), 'Project api · no rules of its own');
  // The gateway settings could not be read (`null`): no count.
  assert.equal(scopeText('api', null), 'Project api · rules not known');
  assert.equal(scopeText('', 4), 'Shared setup · project overrides stay separate');
  assert.equal(scopeText('', null), 'Shared setup · project overrides stay separate');
  const shared = scopeBar('', 0);
  assert.equal(shared.querySelector('span').textContent, 'Shared setup · project overrides stay separate');
  assert.equal(shared.classList.contains('project'), false);
  const project = scopeBar('api', 2);
  assert.equal(project.querySelector('span').textContent, 'Project api · 2 rules differ from the shared setup');
  assert.equal(project.classList.contains('project'), true);
});

test('the scope bar leads with the layers icon, or folder in a project', () => {
  assert.equal(scopeBar(null).querySelector('svg').dataset.icon, 'layers');
  assert.equal(scopeBar('website').querySelector('svg').dataset.icon, 'folder');
  assert.equal(Number(scopeBar('website').querySelector('svg').attributes.width), 14);
});

test('baseNames keeps a file name, also when a folder has a space, and keeps a command', () => {
  const same = 'mcp.json has a hard link; so has config.toml.';
  assert.equal(baseNames('/Users/me/.cursor/mcp.json has a hard link; so has ~/.codex/config.toml.'), same);
  // A folder with a space stays whole inside the path, so only the file name is left.
  assert.equal(baseNames('Could not write /Users/me/Library/Application Support/Claude/claude_desktop_config.json.'), 'Could not write claude_desktop_config.json.');
  assert.equal(baseNames('Copy /a/b.json to /c/d.json now'), 'Copy b.json to d.json now');
  // A "/command" is no path: it stays with its slash.
  assert.equal(baseNames('Run /mcp to see it, or /plugin install x.'), 'Run /mcp to see it, or /plugin install x.');
  // Words that only look like a path stay as they are.
  const plain = 'Turn a tool on and/or off (read/write) in "/" here.';
  assert.equal(baseNames(plain), plain);
});

test('the hint line shows its words with an info icon, and an empty text hides it', () => {
  const line = globalThis.document.createElement('p');
  line.hidden = true;
  const find = globalThis.document.getElementById;
  globalThis.document.getElementById = (id) => (id === 'hint' ? line : null);
  try {
    setHint('Drag a server onto a client.');
    assert.equal(line.hidden, false);
    assert.deepEqual(line.children.map((c) => c.dataset.icon || c.textContent), ['info', 'Drag a server onto a client.']);
    // New words replace the old at once.
    setHint('Another line.');
    assert.deepEqual(line.children.map((c) => c.dataset.icon || c.textContent), ['info', 'Another line.']);
    setHint('');
    assert.equal(line.hidden, true);
    assert.equal(line.children.length, 0);
  } finally {
    globalThis.document.getElementById = find;
  }
});

test('arrows, Home and End move through the options and stop at the ends', () => {
  assert.equal(optionAfter('ArrowDown', 0, 4), 1);
  assert.equal(optionAfter('ArrowDown', 3, 4), 3);
  assert.equal(optionAfter('ArrowUp', 2, 4), 1);
  assert.equal(optionAfter('ArrowUp', 0, 4), 0);
  assert.equal(optionAfter('Home', 3, 4), 0);
  assert.equal(optionAfter('End', 0, 4), 3);
  // Nothing active yet: Down starts at the first option, Up at the last.
  assert.equal(optionAfter('ArrowDown', -1, 4), 0);
  assert.equal(optionAfter('ArrowUp', -1, 4), 3);
  assert.equal(optionAfter('a', 1, 4), null);
  assert.equal(optionAfter('ArrowDown', 0, 0), null);
});

// A project menu on the stub page: `press` sends a key to the find box; `type` fills it. Motion is
// off (reduced) unless `motion` is set, so a closed menu is hidden at once; `from` is the name the
// button showed before a pick. The menu's animations are recorded in `moves`.
function menuOn(picked = 'm', { motion = false, from = null } = {}) {
  media.matches = !motion;
  const document = globalThis.document;
  const outside = {};
  document.activeElement = null;
  document.addEventListener = (type, listener) => { outside[type] = listener; };
  document.removeEventListener = (type) => { delete outside[type]; };
  const picks = [];
  const root = projectMenu(PROJECTS, picked, (id) => picks.push(id), from);
  const [trigger, menu] = root.children;
  const find = menu.querySelector('.where-find');
  const options = () => menu.querySelectorAll('.where-option');
  const active = () => options().findIndex((o) => o.classList.contains('active'));
  const keys = [];
  const moves = [];
  const running = [];
  menu.animate = (keyframes, timing) => {
    const move = { keyframes, timing, finished: Promise.resolve(), cancel() { running.splice(running.indexOf(move), 1); } };
    moves.push(move);
    running.push(move);
    return move;
  };
  menu.getAnimations = () => [...running];
  return {
    root, trigger, menu, find, picks, outside, options, active, keys, moves, running,
    open: () => trigger.listeners.click(),
    toggle: () => trigger.listeners.click(),
    press(key) {
      let stopped = false;
      find.listeners.keydown({ key, preventDefault() { stopped = true; keys.push(`default ${key}`); }, stopPropagation() { keys.push(`stop ${key}`); } });
      return stopped;
    },
    type(text) { find.value = text; find.listeners.input(); },
  };
}

// What an option says, in order: its name, its count and its sub line.
const words = (option) => ['.where-label', '.where-count', '.where-sub'].map((c) => option.querySelector(c)).filter(Boolean).map((n) => n.textContent);
const iconsOf = (node) => node.querySelectorAll('svg').map((n) => n.dataset.icon);

test('the project menu is a button with the picked name, closed until it is pressed', () => {
  const m = menuOn('m');
  assert.equal(m.trigger.tag, 'button');
  assert.equal(m.trigger.attributes['aria-label'], 'Project');
  assert.equal(m.trigger.attributes['aria-haspopup'], 'listbox');
  assert.equal(m.trigger.attributes['aria-expanded'], 'false');
  assert.equal(m.trigger.querySelector('.where-name').textContent, 'mcp-gateway');
  assert.equal(m.menu.hidden, true);
  // The button reads: folder icon, "Project", the name, chevron.
  assert.deepEqual(m.trigger.querySelectorAll('svg').map((node) => node.dataset.icon), ['folder', 'chevron-down']);
  assert.equal(m.trigger.querySelector('.where-word').textContent, 'Project');
  assert.equal(Number(m.trigger.querySelector('svg').attributes.width), 14);
  assert.equal(Number(m.trigger.querySelectorAll('svg')[1].attributes.width), 13);
  assert.equal(m.find.attributes.placeholder, 'Find a project…');
  assert.equal(projectMenu(PROJECTS, '', () => {}).children[0].querySelector('.where-name').textContent, 'All projects');
  assert.equal(projectMenu([], 'gone', () => {}).children[0].querySelector('.where-name').textContent, 'No longer on the list');
});

test('the menu shows before it scrolls the picked project into view', () => {
  // A hidden list has no layout, so a scroll before it shows does nothing.
  const make = globalThis.document.createElement;
  const hidden = [];
  let menu = null;
  globalThis.document.createElement = (tag) => {
    const node = make(tag);
    node.scrollIntoView = () => hidden.push(menu.hidden);
    return node;
  };
  try {
    const m = menuOn('m');
    menu = m.menu;
    m.open();
  } finally {
    globalThis.document.createElement = make;
  }
  assert.deepEqual(hidden, [false]);
});

test('the button keeps the picked name for a screen reader, which its label would hide', () => {
  const m = menuOn('m');
  const name = m.trigger.querySelector('.where-name');
  assert.ok(name.id);
  assert.equal(m.trigger.attributes['aria-describedby'], name.id);
});

test('opening the menu moves focus into the find box, with the picked option active', () => {
  const m = menuOn('m');
  m.open();
  assert.equal(m.menu.hidden, false);
  assert.equal(m.trigger.attributes['aria-expanded'], 'true');
  assert.equal(globalThis.document.activeElement, m.find);
  assert.deepEqual(m.options().map((o) => o.attributes.role), ['option', 'option', 'option', 'option']);
  assert.deepEqual(m.options().map((o) => o.attributes['aria-selected']), ['false', 'false', 'true', 'false']);
  assert.equal(m.active(), 2);
  assert.equal(m.find.attributes['aria-activedescendant'], m.options()[2].id);
  assert.equal(m.menu.querySelector('.where-list').attributes.role, 'listbox');
  // A row says its count and its sub line, never a path.
  assert.deepEqual(words(m.options()[3]), ['website', '3 own rules']);
  assert.deepEqual(words(m.options()[0]), ['All projects', 'What applies in every project']);
  assert.deepEqual(words(m.options()[1]), ['api', 'Folder missing']);
});

test('Down, Up, Home and End move the active option, and Enter picks it', () => {
  const m = menuOn('m');
  m.open();
  assert.equal(m.press('ArrowDown'), true);
  assert.equal(m.active(), 3);
  assert.equal(m.find.attributes['aria-activedescendant'], m.options()[3].id);
  m.press('ArrowDown');
  assert.equal(m.active(), 3);
  m.press('Home');
  assert.equal(m.active(), 0);
  m.press('ArrowUp');
  assert.equal(m.active(), 0);
  m.press('End');
  assert.equal(m.active(), 3);
  m.press('ArrowUp');
  assert.equal(m.active(), 2);
  assert.equal(m.press('Enter'), true);
  assert.deepEqual(m.picks, ['m']);
  assert.equal(m.menu.hidden, true);
  assert.equal(globalThis.document.activeElement, m.trigger);
  assert.equal(m.trigger.attributes['aria-expanded'], 'false');
});

test('Enter on All projects picks the empty id', () => {
  const m = menuOn('m');
  m.open();
  m.press('Home');
  m.press('Enter');
  assert.deepEqual(m.picks, ['']);
});

test('typing filters the projects, keeps All projects first and makes the first match active', () => {
  const m = menuOn('');
  m.open();
  m.type('WEB');
  assert.deepEqual(m.options().map((o) => words(o)[0]), ['All projects', 'website']);
  assert.equal(m.active(), 1);
  m.press('Enter');
  assert.deepEqual(m.picks, ['w']);
  // The text is gone the next time the menu opens.
  m.open();
  assert.equal(m.find.value, '');
  assert.equal(m.options().length, 4);
});

test('a find that matches no project leaves Enter with nothing to pick', () => {
  const m = menuOn('m');
  m.open();
  m.type('zzz');
  assert.deepEqual(m.options().map((o) => words(o)[0]), ['All projects']);
  assert.equal(m.active(), -1);
  assert.equal(m.find.attributes['aria-activedescendant'], undefined);
  m.press('Enter');
  assert.deepEqual(m.picks, []);
  assert.equal(m.menu.hidden, false);
});

test('Escape closes the menu, gives focus back to the button and stays out of Details', () => {
  const m = menuOn('m');
  m.open();
  m.press('Escape');
  assert.equal(m.menu.hidden, true);
  assert.equal(globalThis.document.activeElement, m.trigger);
  assert.deepEqual(m.keys, ['default Escape', 'stop Escape']);
  assert.deepEqual(m.picks, []);
});

test('a press outside the menu closes it, a press inside does not, and Tab lets focus go', () => {
  const m = menuOn('m');
  m.open();
  assert.ok(m.outside.pointerdown);
  m.outside.pointerdown({ target: m.options()[0] });
  assert.equal(m.menu.hidden, false);
  m.outside.pointerdown({ target: { parent: null } });
  assert.equal(m.menu.hidden, true);
  assert.equal(m.outside.pointerdown, undefined);
  m.open();
  m.press('Tab');
  assert.equal(m.menu.hidden, true);
  assert.equal(globalThis.document.activeElement, m.find);
});

test('pressing the open button closes the menu, and Down on the button opens it', () => {
  const m = menuOn('m');
  m.trigger.listeners.keydown({ key: 'ArrowDown', preventDefault() {} });
  assert.equal(m.menu.hidden, false);
  m.open();
  assert.equal(m.menu.hidden, true);
  assert.equal(globalThis.document.activeElement, m.trigger);
});

test('a press on an option picks it', () => {
  const m = menuOn('');
  m.open();
  m.options()[1].listeners.click();
  assert.deepEqual(m.picks, ['a']);
  assert.equal(m.menu.hidden, true);
});

test('the picked project carries a check, the others none', () => {
  const m = menuOn('w');
  m.open();
  const picked = m.options().filter((o) => o.attributes['aria-selected'] === 'true');
  assert.equal(picked.length, 1);
  assert.deepEqual(iconsOf(picked[0]).filter((name) => name === 'check'), ['check']);
  assert.equal(iconsOf(m.menu).filter((name) => name === 'check').length, 1);
  // The check sits last in its row, 14 px.
  const check = picked[0].children[picked[0].children.length - 1];
  assert.equal(check.dataset.icon, 'check');
  assert.equal(Number(check.attributes.width), 14);
  // With All projects picked, the check moves to it.
  const all = menuOn('');
  all.open();
  assert.equal(iconsOf(all.options()[0]).includes('check'), true);
  assert.equal(iconsOf(all.menu).filter((name) => name === 'check').length, 1);
});

test('an option leads with layers for All projects and with a folder for a project, 14 px', () => {
  const m = menuOn('w');
  m.open();
  assert.deepEqual(m.options().map((o) => iconsOf(o)[0]), ['layers', 'folder', 'folder', 'folder']);
  for (const option of m.options()) assert.equal(Number(option.querySelector('svg').attributes.width), 14);
  // The icon is first in its row, before the words.
  assert.equal(m.options()[1].children[0].dataset.icon, 'folder');
});

test('the own-rules count is a part of its own, the sub line sits under the name', () => {
  const m = menuOn('m');
  m.open();
  assert.deepEqual(m.options().map((o) => (o.querySelector('.where-count') || {}).textContent), [undefined, undefined, '1 own rule', '3 own rules']);
  const tx = m.options()[1].querySelector('.where-tx');
  assert.deepEqual(tx.children.map((c) => c.className), ['where-label', 'where-sub']);
});

test('the menu grows in over 180 ms and fades out over 140 ms, hidden by time and not by an event', () => {
  mock.timers.enable({ apis: ['setTimeout'] });
  try {
    const m = menuOn('m', { motion: true });
    m.open();
    assert.equal(m.menu.hidden, false);
    const [grow] = m.moves;
    assert.deepEqual(grow.keyframes, [{ opacity: 0, transform: 'translateY(-8px) scale(.96)' }, { opacity: 1, transform: 'none' }]);
    assert.equal(grow.timing.duration, 180);
    assert.equal(grow.timing.easing, CALM);
    m.press('Escape');
    // Focus is back and the button says closed at once; the menu stays while it fades.
    assert.equal(globalThis.document.activeElement, m.trigger);
    assert.equal(m.trigger.attributes['aria-expanded'], 'false');
    assert.equal(m.menu.hidden, false);
    const fade = m.moves[1];
    assert.deepEqual(fade.keyframes, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-4px) scale(.98)' }]);
    assert.equal(fade.timing.duration, 140);
    assert.equal(fade.timing.easing, 'ease-in');
    assert.equal(fade.timing.fill, 'forwards');
    mock.timers.tick(139);
    assert.equal(m.menu.hidden, false);
    mock.timers.tick(1);
    assert.equal(m.menu.hidden, true);
  } finally {
    mock.timers.reset();
  }
});

test('opening again while the menu fades out keeps it open', () => {
  mock.timers.enable({ apis: ['setTimeout'] });
  try {
    const m = menuOn('m', { motion: true });
    m.open();
    m.toggle();
    mock.timers.tick(60);
    m.toggle();
    // The fade is cancelled; only the new grow runs. The first fade's timer does not hide the menu.
    assert.deepEqual(m.running, [m.moves[2]]);
    assert.equal(m.moves[2].keyframes[0].opacity, 0);
    assert.equal(m.menu.hidden, false);
    mock.timers.tick(200);
    assert.equal(m.menu.hidden, false);
    assert.equal(m.trigger.attributes['aria-expanded'], 'true');
    assert.equal(m.root.fading, null);
    // A close after that fades and hides as before.
    m.toggle();
    mock.timers.tick(140);
    assert.equal(m.menu.hidden, true);
  } finally {
    mock.timers.reset();
  }
});

test('an earlier fade does not hide a menu that is fading out a second time', () => {
  mock.timers.enable({ apis: ['setTimeout'] });
  try {
    const m = menuOn('m', { motion: true });
    m.open();
    m.toggle(); // the first fade ends at 140 ms
    mock.timers.tick(50);
    m.toggle();
    mock.timers.tick(50);
    m.toggle(); // the second fade starts at 100 ms and ends at 240 ms
    mock.timers.tick(40);
    assert.equal(m.menu.hidden, false);
    mock.timers.tick(99);
    assert.equal(m.menu.hidden, false);
    mock.timers.tick(1);
    assert.equal(m.menu.hidden, true);
  } finally {
    mock.timers.reset();
  }
});

test('while the menu fades out, a press on an option picks nothing more', () => {
  mock.timers.enable({ apis: ['setTimeout'] });
  try {
    const m = menuOn('', { motion: true });
    m.open();
    const [, api] = m.options();
    api.listeners.click();
    api.listeners.click();
    assert.deepEqual(m.picks, ['a']);
    mock.timers.tick(140);
  } finally {
    mock.timers.reset();
  }
});

test('the picker says when its menu has faded out, so the page can draw it again after', async () => {
  mock.timers.enable({ apis: ['setTimeout'] });
  try {
    const m = menuOn('m', { motion: true });
    assert.equal(m.root.fading, null);
    m.open();
    m.press('Escape');
    const waiting = m.root.fading;
    assert.ok(waiting instanceof Promise);
    mock.timers.tick(140);
    await waiting;
    assert.equal(m.root.fading, null);
  } finally {
    mock.timers.reset();
  }
});

test('with reduced motion the menu shows and hides at once, with no animation', () => {
  const m = menuOn('m');
  m.open();
  assert.equal(m.menu.hidden, false);
  m.press('Escape');
  assert.equal(m.menu.hidden, true);
  assert.equal(m.root.fading, null);
  assert.deepEqual(m.moves, []);
});

test('after a pick the old name rolls out of the button and the new one rolls in', () => {
  mock.timers.enable({ apis: ['setTimeout'] });
  try {
    const m = menuOn('w', { motion: true, from: 'All projects' });
    const name = m.trigger.querySelector('.where-name');
    assert.equal(name.classList.contains('roll'), true);
    assert.deepEqual(name.children.map((c) => c.textContent), ['All projects', 'website']);
    // The old name leaves by time, not by an animation event.
    mock.timers.tick(140);
    assert.deepEqual(name.children.map((c) => c.textContent), ['website']);
  } finally {
    mock.timers.reset();
  }
});

test('the name is plain text when nothing was picked, the name did not change, or motion is reduced', () => {
  for (const m of [menuOn('w', { motion: true }), menuOn('w', { motion: true, from: 'website' }), menuOn('w', { from: 'All projects' })]) {
    const name = m.trigger.querySelector('.where-name');
    assert.equal(name.classList.contains('roll'), false);
    assert.equal(name.textContent, 'website');
    assert.equal(name.children.length, 0);
  }
});

test('the project button reads the same wherever the page draws it', () => {
  const button = projectButton('…');
  assert.equal(button.tag, 'button');
  assert.equal(button.className, 'where');
  assert.equal(button.id, 'where');
  assert.deepEqual(iconsOf(button), ['folder', 'chevron-down']);
  const classes = (node) => node.children.map((c) => c.className || c.attributes.class);
  assert.deepEqual(classes(button), ['ic', 'where-word', 'where-name', 'ic where-caret']);
  assert.equal(button.querySelector('.where-name').textContent, '…');
  assert.equal(button.attributes['aria-describedby'], button.querySelector('.where-name').id);
  assert.equal(button.attributes['aria-label'], 'Project');
  // projectMenu's own button is this one.
  assert.deepEqual(classes(menuOn('m').trigger), classes(button));
});
