import assert from 'node:assert/strict';
import { test } from 'node:test';

// gateway.js (for its columns) needs only this from a browser to load.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
const { GAP, layoutTree, toggleOpen, litPath, litFrom, findIn, isNarrow, unfoldDelays } = await import('../../src/kitden/web/static/js/map.js');
const { cutName } = await import('../../src/kitden/web/static/js/dom.js');
const { GATEWAY_COLUMNS } = await import('../../src/kitden/web/static/js/gateway.js');

const CLIENTS = ['claude_code', 'codex', 'cursor'];
const LINKED = ['claude_code', 'codex'];
const HELD = ['github', 'files', 'linear'];
const OUTSIDE = ['docs', 'analytics', 'n8n'];
const LONG = '-with-a-name-long-enough-that-the-page-cuts-it-short';
// [name, state]: github has one tool off; every other server has six tools, one off.
const GITHUB_TOOLS = [['read_repo', 'on'], ['push_files', 'off'], ['create_issue', 'on'], ['list_prs', 'on']];
const OTHER_TOOLS = ['list_items', 'get_item', 'create_item', 'summarize', 'delete_item', 'export_items'].map((name, i) => [name, i === 4 ? 'off' : 'on']);

// The Gateway as a tree: 3 clients (claude_code and codex linked), the gateway, `held` servers
// in Remote and Local groups, `outside` rows. `open`: the server whose tools are in the model;
// `tools`: every server's tools are; `long`: every tenth outside name is long.
function model(held, outside, { open = null, tools = false, long = false } = {}) {
  const blocks = [];
  const links = [];
  for (const id of CLIENTS) blocks.push({ id: `client:${id}`, column: 'clients', kind: 'client', name: id, state: LINKED.includes(id) ? 'on' : 'off' });
  blocks.push({ id: 'gateway:kitden', column: 'gateway', kind: 'gateway', name: 'Kitden gateway', state: 'on' });
  for (const id of LINKED) links.push({ from: `client:${id}`, to: 'gateway:kitden', kind: 'on' });
  const names = Array.from({ length: held }, (_, i) => (i < HELD.length ? HELD[i] : `held-${i - HELD.length}`));
  for (const kind of ['remote', 'local']) {
    const group = `group:kitden:${kind}`;
    blocks.push({ id: group, column: 'servers', kind: 'group', name: kind === 'remote' ? 'Remote' : 'Local' });
    names.forEach((name, i) => {
      if ((i % 2 === 0) !== (kind === 'remote')) return;
      const id = `held:kitden:${name}`;
      const list = name === 'github' ? GITHUB_TOOLS : OTHER_TOOLS;
      blocks.push({ id, column: 'servers', parent: group, kind: 'held', name, state: 'on', count: list.length });
      links.push({ from: 'gateway:kitden', to: id, kind: 'on' });
      if (!tools && name !== open) return;
      for (const [tool, state] of list) {
        const toolId = `tool:${name}/${tool}`;
        blocks.push({ id: toolId, column: 'tools', parent: id, kind: 'tool', name: tool, state });
        if (state === 'on') links.push({ from: id, to: toolId, kind: 'on' });
      }
    });
  }
  blocks.push({ id: 'group:outside', column: 'servers', kind: 'group', name: 'Outside the gateway' });
  for (let i = 0; i < outside; i++) {
    const name = (i < OUTSIDE.length ? OUTSIDE[i] : `direct-${i}`) + (long && i % 10 === 0 ? LONG : '');
    const id = `outside:${i % 2 ? 'local' : 'move'}:${name}`;
    blocks.push({ id, column: 'servers', parent: 'group:outside', kind: 'outside', name, state: 'on' });
    links.push({ from: `client:${CLIENTS[i % 3]}`, to: id, kind: 'direct' });
  }
  return { columns: GATEWAY_COLUMNS, blocks, links };
}

// Cursor loads an item through Claude Code: a faint link.
const FAINT_MODEL = {
  columns: [{ id: 'clients', w: 150, h: 54 }, { id: 'items', w: 170, h: 54 }],
  blocks: [{ id: 'client:cursor', column: 'clients', kind: 'client', name: 'Cursor' }, { id: 'item:x', column: 'items', kind: 'skill', name: 'x' }],
  links: [{ from: 'client:cursor', to: 'item:x', kind: 'faint' }],
};

const WIDE = { width: 1248, narrow: false };
const key = (link) => `${link.from}>${link.to}`;

test('columns sit at fixed x and blocks take their column size', () => {
  const l = layoutTree(model(3, 2), { open: new Set(), width: 1248, narrow: false });
  const at = (id) => l.blocks.find((b) => b.id === id);
  assert.deepEqual([at('client:codex').x, at('gateway:kitden').x], [0, 150 + GAP]);
  assert.deepEqual([at('held:kitden:github').w, at('held:kitden:github').h], [170, 54]);
  assert.ok(l.blocks.every((b) => b.w >= 132 && b.w <= 220 && (b.h <= 54 || b.id === 'gateway:kitden')));
});

test('any tree lays out by its own columns, wide and narrow', () => {
  // two columns, not the Gateway's: sources 180×54 and items 200×34
  const m = { columns: [{ id: 'a', w: 180, h: 54 }, { id: 'b', w: 200, h: 34 }], blocks: [{ id: 'p', column: 'a' }, { id: 'i1', column: 'b', parent: 'p' }, { id: 'i2', column: 'b', parent: 'p' }], links: [{ from: 'p', to: 'i1', kind: 'on' }] };
  const wide = layoutTree(m, { open: new Set(['p']), width: 900, narrow: false });
  assert.equal(wide.blocks.find((b) => b.id === 'i1').x, 180 + GAP);
  const narrow = layoutTree(m, { open: new Set(['p']), width: 600, narrow: true });
  const [p, i1] = ['p', 'i1'].map((id) => narrow.blocks.find((b) => b.id === id));
  assert.ok(i1.y > p.y && i1.x >= p.x && i1.x + i1.w <= p.x + p.w);
});

test('a folded server shows its count; opening it shows its tools and links', () => {
  const m = model(3, 0, { open: 'github' });
  assert.equal(m.blocks.find((b) => b.id === 'held:kitden:github').count, 4);
  const folded = layoutTree(m, { open: new Set(), ...WIDE });
  assert.ok(!folded.blocks.some((b) => b.id.startsWith('tool:')));
  assert.ok(!folded.links.some((link) => link.to.startsWith('tool:')));
  const opened = layoutTree(m, { open: new Set(['held:kitden:github']), ...WIDE });
  const tools = opened.blocks.filter((b) => b.id.startsWith('tool:github/'));
  const column = opened.columns.find((c) => c.id === 'tools');
  assert.equal(tools.length, 4);
  assert.ok(tools.every((b) => b.x === column.x && b.w === 190 && b.h === 34));
  // The tools start beside their server.
  assert.ok(tools[0].y >= opened.blocks.find((b) => b.id === 'held:kitden:github').y);
  const link = opened.links.find((l) => key(l) === 'held:kitden:github>tool:github/read_repo');
  assert.ok(link && link.d.startsWith('M ') && link.d.includes(' C '));
});

test('the link is the state: an off tool has no link', () => {
  const l = layoutTree(model(3, 0, { open: 'github' }), { open: new Set(['held:kitden:github']), ...WIDE });
  assert.ok(l.blocks.some((b) => b.id === 'tool:github/push_files'));
  assert.ok(!l.links.some((link) => key(link) === 'held:kitden:github>tool:github/push_files'));
  assert.ok(l.links.some((link) => key(link) === 'held:kitden:github>tool:github/read_repo'));
});

test('a direct line is an elbow with round corners on a trunk at x 170', () => {
  const l = layoutTree(model(0, 2), { open: new Set(), ...WIDE });
  const line = l.links.find((link) => key(link) === 'client:claude_code>outside:move:docs');
  assert.equal(line.kind, 'direct');
  assert.match(line.d, /^M 150 \d+ H 164 Q 170 \d+ 170 \d+ V \d+ Q 170 \d+ 176 \d+ H 392$/);
});

test('one block per column is open', () => {
  const m = model(3, 0);
  const open = toggleOpen(m, toggleOpen(m, new Set(), 'held:kitden:github'), 'held:kitden:linear');
  assert.deepEqual([...open], ['held:kitden:linear']);
  assert.deepEqual([...toggleOpen(m, open, 'held:kitden:linear')], []);
});

test('a group with more than six servers shows five and N more', () => {
  const l = layoutTree(model(0, 9), { open: new Set(), width: 1248, narrow: false });
  assert.equal(l.blocks.filter((b) => b.id.startsWith('outside:')).length, 5);
  assert.ok(l.blocks.some((b) => b.id === 'more:group:outside'));
  assert.equal(l.blocks.find((b) => b.id === 'more:group:outside').name, '4 more');
  // A line to a hidden server is not drawn; six or fewer show whole.
  assert.equal(l.links.filter((link) => link.kind === 'direct').length, 5);
  assert.ok(!layoutTree(model(0, 6), { open: new Set(), ...WIDE }).blocks.some((b) => b.id.startsWith('more:')));
});

test('selecting a tool lights the path from every client that reaches it', () => {
  const lit = litPath(model(3, 0, { open: 'github' }), 'tool:github/read_repo');
  for (const id of ['client:claude_code', 'client:codex', 'gateway:kitden', 'held:kitden:github', 'client:claude_code>gateway:kitden', 'client:codex>gateway:kitden']) assert.ok(lit.has(id), id);
  assert.ok(!lit.has('client:cursor'));
  assert.ok(litPath(model(0, 2), 'outside:move:docs').has('client:claude_code>outside:move:docs'));  // direct
  assert.ok(litPath(FAINT_MODEL, 'item:x').has('client:cursor>item:x'));  // faint
});

test('a client lights what it reaches', () => {
  const lit = litFrom(model(3, 1, { open: 'github' }), 'client:codex');
  for (const id of ['gateway:kitden', 'held:kitden:github', 'tool:github/read_repo', 'client:codex>gateway:kitden']) assert.ok(lit.has(id), id);
  assert.ok(!lit.has('tool:github/push_files'));  // off: no link
});

test('find lights matches and opens the folded parent', () => {
  assert.deepEqual(findIn(model(3, 0, { tools: true }), ' PUSH '), { matches: new Set(['tool:github/push_files']), open: new Set(['held:kitden:github', 'group:kitden:remote']) });
  assert.deepEqual(findIn(model(3, 0), '  '), { matches: new Set(), open: new Set() });
});

test('narrow: tools unfold down inside the server; the gateway is a small tile', () => {
  assert.equal(isNarrow(1023, false), true); assert.equal(isNarrow(1279, true), true); assert.equal(isNarrow(1280, true), false);
  assert.equal(isNarrow(1100, false), false);
  const l = layoutTree(model(3, 0, { open: 'github' }), { open: new Set(['held:kitden:github']), width: 900, narrow: true });
  const server = l.blocks.find((b) => b.id === 'held:kitden:github');
  const tool = l.blocks.find((b) => b.id === 'tool:github/read_repo');
  assert.ok(tool.x >= server.x && tool.y > server.y && tool.x + tool.w <= server.x + server.w);
  assert.deepEqual([l.blocks.find((b) => b.id === 'gateway:kitden').w, l.blocks.find((b) => b.id === 'gateway:kitden').h], [56, 56]);
  assert.equal(tool.h, 30);
  // The server under it moves down to make room.
  const linear = l.blocks.find((b) => b.id === 'held:kitden:linear');
  assert.ok(linear.y > l.blocks.find((b) => b.id === 'tool:github/list_prs').y);
});

test('unfold: links first, children 15 ms apart, nothing past 300 ms; reduced motion shows the end at once', () => {
  const d = unfoldDelays(12);
  assert.equal(d[1] - d[0], 15); assert.equal(d[11], d[5]); assert.ok(d.every((t) => t + 60 <= 300));
  assert.ok(unfoldDelays(12, true).every((t) => t === 0));
});

test('the layout of 20 servers and of the large sample stays under 16 ms', () => {
  for (const m of [model(2, 18, { open: 'files' }), model(12, 157, { open: 'held-0', long: true })]) {
    const times = Array.from({ length: 20 }, () => { const t = performance.now(); layoutTree(m, { open: new Set(['held:kitden:held-0', 'held:kitden:files']), width: 1248, narrow: false }); return performance.now() - t; }).sort((a, b) => a - b);
    assert.ok(times[10] < 16, `median ${times[10]} ms`);
  }
});

test('a long name is cut and keeps its whole name in its label', () => {
  const name = 'a-very-long-server-name-from-the-large-sample-0001';
  assert.equal(cutName(name).length, 24); assert.ok(cutName(name).endsWith('…')); assert.equal(cutName('files'), 'files');
});
