import assert from 'node:assert/strict';
import { test } from 'node:test';

// gateway.js (for its columns) needs only this from a browser to load.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
const { CAPTION_H, GAP, NARROW_GAP, blockOrder, drawPlan, dropAt, enterDelays, findChip, groupBox, findIn, foldable, isNarrow, layoutTree, linkClass, linkKey, litFrom, litPath, toggleOpen, unfoldDelays } = await import('../../src/kitden/web/static/js/map.js');
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

test('the find chip says how many blocks match', () => {
  const tree = model(3, 0, { tools: true });
  assert.equal(findChip(null), null);
  assert.equal(findChip(findIn(tree, 'zzz')), 'No matches');
  assert.equal(findChip(findIn(tree, 'push')), '1 match');
  assert.equal(findChip(findIn(tree, 'create_')), '3 matches');
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

test('unfold: links draw for 170 ms, then children start 15 ms apart with no cap; reduced motion starts all at once', () => {
  const d = unfoldDelays(12);
  assert.equal(d[0], 170); assert.equal(d[1] - d[0], 15); assert.equal(d[11], 170 + 11 * 15);
  assert.ok(unfoldDelays(12, true).every((t) => t === 0));
});

test('entrance: blocks start 22 ms apart, and the whole wave ends within 440 ms; reduced motion starts all at once', () => {
  const small = enterDelays(15);
  assert.equal(small.length, 15); assert.equal(small[0], 0); assert.equal(small[1] - small[0], 22); assert.equal(small.at(-1), 308);
  assert.equal(enterDelays(21).at(-1), 440);
  const big = enterDelays(41);
  assert.equal(big.length, 41); assert.equal(big[0], 0); assert.equal(big.at(-1), 440);
  assert.ok(big.every((t, i) => i === 0 || t > big[i - 1]));
  assert.deepEqual(enterDelays(0), []); assert.deepEqual(enterDelays(1), [0]);
  assert.ok(enterDelays(41, true).every((t) => t === 0) && enterDelays(15, true).length === 15);
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

test('every block is a button in reading order', () => {
  const m = model(3, 2, { open: 'github' });
  const wide = layoutTree(m, { open: new Set(['held:kitden:github']), ...WIDE });
  const order = blockOrder(wide);
  // Groups and column captions are captions, not buttons.
  assert.ok(!order.some((id) => id.startsWith('group:') || id.startsWith('column:')));
  assert.equal(order.length, wide.blocks.filter((b) => !b.id.startsWith('group:') && !b.id.startsWith('column:')).length);
  assert.deepEqual(order.slice(0, 4), ['client:claude_code', 'client:codex', 'client:cursor', 'gateway:kitden']);
  // Column by column, top to bottom.
  const at = new Map(wide.blocks.map((b) => [b.id, b]));
  for (let i = 1; i < order.length; i++) {
    const [a, b] = [at.get(order[i - 1]), at.get(order[i])];
    assert.ok(a.x < b.x || (a.x === b.x && a.y < b.y), `${order[i - 1]} before ${order[i]}`);
  }
  assert.equal(order[order.length - 1], 'tool:github/list_prs');
  // Narrow, a server's tools come right after it.
  const narrow = blockOrder(layoutTree(m, { open: new Set(['held:kitden:github']), width: 900, narrow: true }));
  assert.deepEqual(narrow.slice(narrow.indexOf('held:kitden:github'), narrow.indexOf('held:kitden:github') + 3), ['held:kitden:github', 'tool:github/read_repo', 'tool:github/push_files']);
});

test('narrow: a column with no blocks of its own takes no width', () => {
  const l = layoutTree(model(3, 2, { open: 'github' }), { open: new Set(['held:kitden:github']), width: 900, narrow: true });
  assert.deepEqual(l.columns.map((c) => c.id), ['clients', 'gateway', 'servers']);
  assert.equal(Math.max(...l.blocks.map((b) => b.x + b.w)), 140 + NARROW_GAP + 56 + NARROW_GAP + 220);
  assert.equal(l.narrow, true);
  // Wide, every column keeps its place, so nothing moves sideways when a server opens.
  assert.deepEqual(layoutTree(model(3, 2), { open: new Set(), ...WIDE }).columns.map((c) => c.id), ['clients', 'gateway', 'servers', 'tools']);
});

test('column captions are blocks at the top of their column; Tools only while a server is open', () => {
  const l = layoutTree(model(3, 0), { open: new Set(), ...WIDE });
  const caps = l.blocks.filter((b) => b.kind === 'column');
  assert.deepEqual(caps.map((b) => b.id), ['column:clients', 'column:gateway', 'column:servers']);
  assert.ok(caps.every((b) => b.y === 0 && b.h === CAPTION_H));
  const open = layoutTree(model(3, 0, { open: 'github' }), { open: new Set(['held:kitden:github']), ...WIDE });
  assert.equal(open.blocks.find((b) => b.id === 'column:tools').opener, 'held:kitden:github');
  assert.equal(open.blocks.find((b) => b.id === 'tool:github/read_repo').opener, 'held:kitden:github');
  assert.equal(open.links.find((k) => k.kind === 'on').shape, 'curve');
});

test('the draw plan says what enters, stays and leaves, and what an unfold or a fold moves', () => {
  const m = model(3, 0, { open: 'github' });
  const [closed, open] = [new Set(), new Set(['held:kitden:github'])].map((o) => layoutTree(m, { open: o, ...WIDE }));
  const tools = ['column:tools', 'tool:github/read_repo', 'tool:github/push_files', 'tool:github/create_issue', 'tool:github/list_prs'];
  const p = drawPlan(closed, open);
  assert.deepEqual(p.enter, tools); assert.deepEqual(p.unfold, tools); assert.deepEqual(p.leave, []);
  assert.ok(p.stay.includes('held:kitden:github'));
  assert.equal(p.linksIn.length, 3);  // push_files is off: no link
  assert.deepEqual(drawPlan(open, closed).fold, tools);
  assert.deepEqual(drawPlan(null, closed).enter, closed.blocks.map((b) => b.id));
  assert.deepEqual(drawPlan(null, closed).unfold, []);
});

test('an unknown direct link is dashed by its class', () => {
  assert.equal(linkClass({ from: 'a', to: 'b', kind: 'direct', unk: true }), 'link direct unk');
  assert.equal(linkClass({ from: 'a', to: 'b', kind: 'on' }), 'link on');
  assert.equal(linkKey({ from: 'a', to: 'b' }), 'a>b');
});

test('a block folds when it holds something, also before its tools are read', () => {
  const m = model(3, 0);  // no tool blocks in the model yet
  const folds = foldable(m);
  assert.ok(folds.has('held:kitden:github') && folds.has('held:kitden:files'));
  assert.ok(!folds.has('client:codex') && !folds.has('group:outside') && !folds.has('gateway:kitden'));
  // A server with no tools still folds, so it can say it is open.
  const empty = { ...m, blocks: m.blocks.map((b) => (b.id === 'held:kitden:files' ? { ...b, count: 0 } : b)) };
  assert.ok(foldable(empty).has('held:kitden:files'));
});

test('a drop names the column under the point', () => {
  const l = layoutTree(model(3, 2), { open: new Set(), ...WIDE });
  const servers = l.columns.find((c) => c.id === 'servers');
  const clients = l.columns.find((c) => c.id === 'clients');
  assert.equal(dropAt(l, servers.x + 10, l.height - 1), 'servers');
  assert.equal(dropAt(l, clients.x + clients.w / 2, 5), 'clients');
  // The whole height counts, also where the column has no block.
  assert.equal(dropAt(l, servers.x + servers.w, 0), 'servers');
  // Between two columns, above or below the map: no column.
  assert.equal(dropAt(l, servers.x - GAP / 2, 10), null);
  assert.equal(dropAt(l, servers.x + 10, -1), null);
  assert.equal(dropAt(l, servers.x + 10, l.height + 1), null);
});

test('a group takes the box from its caption to its last block shown', () => {
  const m = model(0, 9);
  const l = layoutTree(m, { open: new Set(), ...WIDE });
  const caption = l.blocks.find((b) => b.id === 'group:outside');
  const more = l.blocks.find((b) => b.id === 'more:group:outside');
  assert.deepEqual(groupBox(m, l, 'group:outside'), { x: caption.x, y: caption.y, w: caption.w, h: more.y + more.h - caption.y });
  // Open, it reaches its last server.
  const open = layoutTree(m, { open: new Set(['group:outside']), ...WIDE });
  const last = open.blocks.filter((b) => b.id.startsWith('outside:')).at(-1);
  assert.equal(groupBox(m, open, 'group:outside').h, last.y + last.h - caption.y);
  assert.equal(groupBox(m, l, 'group:none'), null);
});

test('a preview or a slot in a long group always shows, after N more', () => {
  const m = model(0, 9);
  m.blocks.push({ id: 'preview:x', column: 'servers', parent: 'group:outside', kind: 'preview', name: 'x', state: 'preview' });
  const l = layoutTree(m, { open: new Set(), ...WIDE });
  const shown = l.blocks.filter((b) => b.id.startsWith('outside:') || b.id.startsWith('more:') || b.id === 'preview:x').map((b) => b.id);
  assert.equal(shown.length, 7);
  assert.deepEqual(shown.slice(5), ['more:group:outside', 'preview:x']);
  // "N more" counts only what it hides.
  assert.equal(l.blocks.find((b) => b.id === 'more:group:outside').name, '4 more');
});
