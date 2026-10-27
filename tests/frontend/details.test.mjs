import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';

// details.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
// Node before 21 has no navigator; details.js must load there too.
delete globalThis.navigator;
const { backToDetails, fileScopeWords, focusAfterBack, keepFrom, offerLabel, previewButton, scopeWords, switchNode, syncTray, techRows } = await import('../../src/kitden/web/static/js/details.js');
const { review } = await import('../../src/kitden/web/static/js/review.js');
const { cancelTray, keyFor, onTray, takeOut, tray } = await import('../../src/kitden/web/static/js/tray.js');
const { panelState } = await import('../../src/kitden/web/static/js/panel.js');

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

test('a section title names only a known client as the owner of a folder', () => {
  assert.equal(scopeWords({ scope: 'user', client: 'cursor', owner_client: 'shared' }, null), 'All projects');
  assert.equal(scopeWords({ scope: 'user', client: 'cursor', owner_client: 'kitden', via_gateway: 'kitden' }, null), 'All projects');
  assert.equal(fileScopeWords({ scope: 'user', client: 'cursor', owner_client: 'shared' }), 'Global settings');
  assert.equal(fileScopeWords({ scope: 'user', client: 'cursor', owner_client: 'claude_code' }), 'Global settings · via Claude Code');
  assert.equal(fileScopeWords({ scope: 'local', client: 'claude_code', owner_client: 'claude_code', project: site }), 'Only on this Mac · website');
  assert.equal(fileScopeWords({ scope: 'project', client: 'claude_code', owner_client: 'claude_code', project: site }), 'Project website');
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

test('focus comes back to the pressed control, or to More when it was under More', () => {
  assert.equal(focusAfterBack('offer:d1:skill.remove', ['offer:d1:skill.remove', 'more']), 'offer:d1:skill.remove');
  assert.equal(focusAfterBack('offer:d2:plugin.disable', ['more', 'move']), 'more');
  assert.equal(focusAfterBack(null, ['move']), null);
  // Nothing under More and the control gone: the panel itself takes focus.
  assert.equal(focusAfterBack('add:codex', ['move']), null);
});

test('a panel keeps how to draw itself again and the control pressed last', () => {
  const listeners = [];
  const node = () => ({ addEventListener: (type, listener, capture) => listeners.push({ type, listener, capture }) });
  const draw = () => {};
  const read = async () => {};
  const from = keepFrom(draw, [node(), node(), null], read);
  assert.equal(panelState.from, from);
  assert.deepEqual({ draw: from.draw, read: from.read, focus: from.focus }, { draw, read, focus: null });
  // Without its own way to read again, it draws again.
  assert.equal(keepFrom(draw, []).read, draw);
  // One capture listener on the body and one on the footer: it hears a press before the button.
  assert.deepEqual(listeners.map((l) => [l.type, l.capture]), [['click', true], ['click', true]]);
  const press = (key) => ({ target: { closest: () => (key ? { dataset: { focus: key } } : null) } });
  listeners[1].listener(press('held:Remove from the Kitden gateway…'));
  assert.equal(from.focus, 'held:Remove from the Kitden gateway…');
  listeners[0].listener(press(null)); // a press on plain text keeps the last control
  assert.equal(from.focus, 'held:Remove from the Kitden gateway…');
  panelState.from = null;
});

// A drawer in a stub page: its body, the controls a redraw puts in it, and what got focus.
function stubDrawer() {
  const page = { focused: [], controls: [], open: true };
  page.body = { children: [], prepend(node) { this.children.unshift(node); } };
  page.control = (key) => ({ dataset: { focus: key }, focus: () => page.focused.push(key) });
  const drawer = {
    focus: () => page.focused.push('drawer'),
    classList: { contains: (name) => name === 'open' && page.open },
    querySelector: (selector) => (selector === '.body' ? page.body : null),
    querySelectorAll: (selector) => (selector === '[data-focus]' ? page.controls : []),
  };
  const element = (tag) => ({ tag, className: '', textContent: '', children: [], attributes: {}, append(...nodes) { this.children.push(...nodes); }, setAttribute(name, value) { this.attributes[name] = value; } });
  globalThis.document = { createElement: element, querySelector: (selector) => (selector === '#drawer' ? drawer : null), querySelectorAll: () => [] };
  return page;
}

test('back from a review, Details is drawn again from what it read, the reason first, focus restored', () => {
  const page = stubDrawer();
  const { body, control, focused } = page;
  const controls = { set value(list) { page.controls = list; } };
  try {
    let drawn = 0;
    // The pressed Remove waits under More again once Details is drawn.
    panelState.from = { draw: () => { drawn += 1; controls.value = [control('more'), control('move')]; }, focus: 'offer:d1:mcp.remove_direct' };
    backToDetails({ error: 'Choose one known item.' });
    assert.equal(drawn, 1);
    assert.equal(body.children[0].className, 'callout error');
    assert.equal(body.children[0].children[1].textContent, 'Choose one known item.');
    assert.deepEqual(focused, ['more']);
    // Cancel: no callout; focus on the control itself when it is drawn.
    focused.length = 0;
    body.children = [];
    panelState.from = { draw: () => { controls.value = [control('move')]; }, focus: 'move' };
    backToDetails();
    assert.deepEqual([body.children.length, focused], [0, ['move']]);
  } finally {
    panelState.from = null;
    delete globalThis.document;
  }
});

test('back from a review whose settings changed, Details reads them again', async () => {
  const page = stubDrawer();
  try {
    const drawn = [];
    const from = {
      draw: () => drawn.push('old read'),
      read: async () => { drawn.push('new read'); page.controls = [page.control('move')]; },
      focus: 'move',
      stale: true,
    };
    panelState.from = from;
    await backToDetails();
    assert.deepEqual([drawn, page.focused], [['new read'], ['move']]);
    // Closed while it read: focus stays where the person put it.
    page.focused.length = 0;
    from.read = async () => { page.open = false; };
    panelState.from = from;
    await backToDetails();
    assert.deepEqual(page.focused, []);
  } finally {
    panelState.from = null;
    delete globalThis.document;
  }
});

// A page whose Details hold `controls`, and a stand-in server for the tray: a batch preview answers
// with one row per request. `sent` keeps every request's address.
function trayPage() {
  const page = { controls: [], sent: [] };
  const node = (tag) => {
    const classes = new Set();
    const made = {
      tag, textContent: '', childNodes: [], attributes: {}, dataset: {}, listeners: [], title: '', disabled: false,
      get className() { return [...classes].join(' '); },
      set className(value) { classes.clear(); String(value).split(/\s+/).filter(Boolean).forEach((name) => classes.add(name)); },
      classList: { add: (name) => classes.add(name), remove: (name) => classes.delete(name), toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)), contains: (name) => classes.has(name) },
      get firstElementChild() { return made.childNodes[0] || null; },
      append(...nodes) { made.childNodes.push(...nodes); },
      setAttribute(name, value) { made.attributes[name] = String(value); },
      getAttribute: (name) => (name in made.attributes ? made.attributes[name] : null),
      removeAttribute(name) { delete made.attributes[name]; },
      addEventListener(type, listener) { if (type === 'click') made.listeners.push(listener); },
      // A press, and what it set off.
      async click() { made.listeners.forEach((listener) => listener({})); await new Promise((resolve) => setTimeout(resolve, 0)); },
      focus() { globalThis.document.activeElement = made; },
    };
    return made;
  };
  const drawer = { querySelectorAll: (selector) => (selector === '[data-tray]' ? page.controls.filter((c) => c.dataset.tray) : []) };
  globalThis.document = { createElement: node, getElementById: () => null, querySelector: (selector) => (selector === '#drawer' ? drawer : null), querySelectorAll: () => [] };
  globalThis.fetch = async (url, options = {}) => {
    page.sent.push(url);
    if (page.hold) await page.hold;
    if (url !== '/api/batch/preview') return Response.json({});
    const { requests } = JSON.parse(options.body);
    return Response.json({
      id: `c${page.sent.length}`, action: 'batch', state: 'previewed', error: null, undo_note: null,
      steps: requests.map(() => ({ client: 'codex', name: 'x' })),
      rows: requests.map((r, at) => ({ id: r.id, kind: r.kind, title: r.title, detail: '', project: null, steps: [at], after: [] })),
    });
  };
  // What initPanel does: the looks follow every change of the tray.
  page.stop = onTray(syncTray);
  return page;
}

async function leaveTrayPage(page) {
  await cancelTray();
  page.stop();
  delete globalThis.document;
  delete globalThis.fetch;
}

test('a switch in the tray shows the pending look and a press takes it out', async () => {
  const page = trayPage();
  const body = { action: 'plugin.disable', targets: [{ item: 'i1' }], params: {} };
  try {
    const toggle = switchNode(true, () => review(body), keyFor(body));
    page.controls.push(toggle);
    assert.deepEqual([toggle.className, toggle.attributes['aria-checked'], toggle.title], ['switch', 'true', 'On. Press to preview turning it off.']);
    // A press adds the change: the switch rests half-way, its real state unchanged until Apply.
    await toggle.click();
    assert.deepEqual(tray.rows.map((r) => r.key), ['switch:i1']);
    assert.deepEqual([toggle.className, toggle.attributes['aria-checked'], toggle.title], ['switch pending', 'true', 'In preview. Press to take it out.']);
    // Drawn again while its change waits, it starts pending.
    assert.equal(switchNode(true, () => review(body), keyFor(body)).className, 'switch pending');
    // A second press takes the change out: the switch is as it was, and the server forgets it.
    await toggle.click();
    assert.deepEqual([tray.rows.length, toggle.className, toggle.title], [0, 'switch', 'On. Press to preview turning it off.']);
    assert.ok(page.sent.includes('/api/changes/c1/cancel'));
    // Taken out anywhere else (the bar's ×, Cancel), the switch comes back too.
    await toggle.click();
    assert.equal(toggle.className, 'switch pending');
    await takeOut(keyFor(body));
    assert.equal(toggle.className, 'switch');
  } finally {
    await leaveTrayPage(page);
  }
});

test('a switch whose change waits in the tray says so in its name', async () => {
  const page = trayPage();
  const body = { action: 'plugin.disable', targets: [{ item: 'i3' }], params: {} };
  try {
    const toggle = switchNode(true, () => review(body), keyFor(body), 'Turn off in Codex…');
    page.controls.push(toggle);
    assert.equal(toggle.attributes['aria-label'], 'Turn off in Codex…');
    // Its checked state stays the real one, so the name tells a screen reader the press was heard.
    await toggle.click();
    assert.equal(toggle.attributes['aria-label'], 'Turn off in Codex… (in preview)');
    assert.equal(switchNode(true, () => review(body), keyFor(body), 'Turn off in Codex…').attributes['aria-label'], 'Turn off in Codex… (in preview)');
    await toggle.click();
    assert.equal(toggle.attributes['aria-label'], 'Turn off in Codex…');
  } finally {
    await leaveTrayPage(page);
  }
});

test('a button in the tray says In preview', async () => {
  const page = trayPage();
  const body = { action: 'mcp.remove_direct', targets: [{ item: 'e1' }], params: {} };
  const words = (node) => node.childNodes.map((child) => child.textContent).join('');
  try {
    const remove = previewButton('Remove from Codex…', body, { note: 'Codex only.', look: 'btn primary' });
    page.controls.push(remove);
    assert.deepEqual([words(remove), remove.title, remove.className, remove.attributes['aria-disabled']], ['Remove from Codex…', 'Remove from Codex…', 'btn primary', undefined]);
    await remove.click();
    assert.deepEqual(tray.rows.map((r) => [r.key, r.note]), [[keyFor(body), 'Codex only.']]);
    // While its change waits it says so and takes no press; the hover text still says what it does.
    assert.deepEqual([words(remove), remove.title, remove.attributes['aria-disabled']], ['In preview', 'Remove from Codex…', 'true']);
    const asked = page.sent.length;
    await remove.click();
    assert.equal(page.sent.length, asked);
    // Drawn again while it waits, it says so at once.
    assert.equal(words(previewButton('Remove from Codex…', body)), 'In preview');
    // Out of the tray, the button is back.
    await takeOut(keyFor(body));
    assert.deepEqual([words(remove), remove.attributes['aria-disabled']], ['Remove from Codex…', undefined]);
  } finally {
    await leaveTrayPage(page);
  }
});

test('a preview button keeps focus while its add is asked', async () => {
  const page = trayPage();
  const body = { action: 'mcp.remove_direct', targets: [{ item: 'e2' }], params: {} };
  let release;
  page.hold = new Promise((resolve) => { release = resolve; });
  try {
    const remove = previewButton('Remove from Cursor…', body);
    page.controls.push(remove);
    remove.focus();
    await remove.click();
    await new Promise((resolve) => setTimeout(resolve, 200));
    // Slow: the spinner shows, but the button is never :disabled, so focus stays on it.
    assert.deepEqual([remove.disabled, remove.className, remove.attributes['aria-busy'], globalThis.document.activeElement === remove], [false, 'btn busy', 'true', true]);
    // A second press while it is asked sends nothing more.
    const asked = page.sent.length;
    await remove.click();
    assert.equal(page.sent.length, asked);
    release();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.deepEqual([remove.className, remove.attributes['aria-busy'], remove.attributes['aria-disabled'], globalThis.document.activeElement === remove], ['btn', undefined, 'true', true]);
  } finally {
    page.hold = null;
    await leaveTrayPage(page);
  }
});
