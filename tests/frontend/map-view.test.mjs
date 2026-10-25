import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';

// A small browser for the map view: elements, a frame queue and a clock that only the tests move.
// A motion starts at the clock's `now` when it is called. `tick(ms)` moves the clock and runs the
// frames queued so far once; `settle()` ticks 10 s at a time until no frame is queued.
const media = { matches: false };
globalThis.matchMedia = () => media;
delete globalThis.navigator;
const reduce = (flag) => { media.matches = flag; };
let now = 0;
let frames = [];
Object.defineProperty(globalThis, 'performance', { value: { now: () => now, mark() {}, measure() {} }, configurable: true, writable: true });
globalThis.requestAnimationFrame = (fn) => frames.push(fn);
const tick = (ms) => {
  now += ms;
  const run = frames;
  frames = [];
  for (const fn of run) fn(now);
};
const settle = () => { while (frames.length) tick(10000); };
// Every node under a root.
const walk = (root) => root.children.flatMap((n) => [n, ...walk(n)]);
const near = (a, b) => Math.abs(a - b) < 1e-6;

// A node leaves its parent; one that holds focus loses it, as in a browser.
function detach(node) {
  const parent = node.parentNode;
  if (!parent) return;
  if (globalThis.document.activeElement && node.contains(globalThis.document.activeElement)) globalThis.document.activeElement = null;
  parent.children.splice(parent.children.indexOf(node), 1);
  node.parentNode = null;
}

// "tag", ".class" or "tag.class".
function matches(node, selector) {
  const [tag, ...classes] = selector.split('.');
  return (!tag || node.tagName.toLowerCase() === tag.toLowerCase()) && classes.every((name) => node.classList.contains(name));
}

function element(tagName) {
  let names = [];
  const attributes = new Map();
  const node = {
    tagName, style: {}, dataset: {}, children: [], parentNode: null, textContent: '', listeners: {}, animations: [],
    get className() { return names.join(' '); },
    set className(value) { names = String(value).split(' ').filter(Boolean); },
    classList: {
      add: (...add) => { for (const name of add) if (!names.includes(name)) names.push(name); },
      remove: (...gone) => { names = names.filter((name) => !gone.includes(name)); },
      toggle: (name, force = !names.includes(name)) => { node.classList[force ? 'add' : 'remove'](name); return force; },
      contains: (name) => names.includes(name),
    },
    setAttribute(name, value) { if (name === 'class') node.className = value; else attributes.set(name, String(value)); },
    getAttribute: (name) => (name === 'class' ? node.className : attributes.has(name) ? attributes.get(name) : null),
    removeAttribute(name) { attributes.delete(name); },
    get firstElementChild() { return node.children[0] || null; },
    get lastElementChild() { return node.children.at(-1) || null; },
    append(...nodes) { for (const n of nodes) node.insertBefore(n, null); },
    prepend(...nodes) { const first = node.children[0] || null; for (const n of nodes) node.insertBefore(n, first); },
    insertBefore(n, ref) {
      detach(n);
      node.children.splice(ref ? node.children.indexOf(ref) : node.children.length, 0, n);
      n.parentNode = node;
      return n;
    },
    remove() { detach(node); },
    replaceChildren(...nodes) { for (const n of [...node.children]) detach(n); node.append(...nodes); },
    contains(other) { for (let at = other; at; at = at.parentNode) if (at === node) return true; return false; },
    focus() { globalThis.document.activeElement = node; node.dispatch('focus'); },
    blur() { if (globalThis.document.activeElement === node) globalThis.document.activeElement = null; },
    closest(selector) { for (let at = node; at; at = at.parentNode) if (matches(at, selector)) return at; return null; },
    addEventListener(type, fn) { (node.listeners[type] ||= []).push(fn); },
    // An event that bubbles from this node to its parents.
    dispatch(type, init = {}) {
      const event = { type, target: node, stopped: false, defaultPrevented: false, stopPropagation() { this.stopped = true; }, preventDefault() { this.defaultPrevented = true; }, ...init };
      for (let at = node; at && !event.stopped; at = at.parentNode) for (const fn of at.listeners[type] || []) fn(event);
      return event;
    },
    animate(keyframes, options) {
      node.animations.push({ keyframes, options });
      return { finished: Promise.resolve(), cancel() {} };
    },
  };
  return node;
}
globalThis.document = { hidden: false, activeElement: null, createElement: (tag) => element(tag.toUpperCase()), createElementNS: (namespace, tag) => element(tag) };

beforeEach(() => {
  now = 0;
  frames = [];
  reduce(false);
  globalThis.document.hidden = false;
  globalThis.document.activeElement = null;
});

const { blockOrder, layoutTree, linkKey, linkPath, midPoint } = await import('../../src/kitden/web/static/js/map.js');
const { CALM } = await import('../../src/kitden/web/static/js/motion.js');
const { mapView } = await import('../../src/kitden/web/static/js/map-view.js');

const TREE = {
  columns: [{ id: 'a', caption: 'A', w: 150, h: 54 }, { id: 'b', caption: 'B', w: 170, h: 60 }, { id: 'c', caption: 'C', w: 200, h: 34 }],
  blocks: [
    { id: 'c1', column: 'a', kind: 'client', name: 'Codex', state: 'on' },
    { id: 's1', column: 'b', kind: 'held', name: 'github', state: 'on', count: 2 },
    { id: 's2', column: 'b', kind: 'held', name: 'files', state: 'on', count: 0 },
    { id: 't1', column: 'c', parent: 's1', kind: 'tool', name: 'read', state: 'on' },
    { id: 't2', column: 'c', parent: 's1', kind: 'tool', name: 'push', state: 'on' },
  ],
  links: [{ from: 'c1', to: 's1', kind: 'on' }, { from: 'c1', to: 's2', kind: 'on' }, { from: 's1', to: 't1', kind: 'on' }, { from: 's1', to: 't2', kind: 'on' }],
};
const lay = (open = [], narrow = false) => layoutTree(TREE, { open: new Set(open), narrow });
const view = (hooks = {}) => mapView({ tile: () => null, onOpen() {}, onSelect() {}, ...hooks });
const pos = (n) => { const m = n.style.transform.match(/translate\(([-\d.]+)px, ([-\d.]+)px\) scale\(([-\d.]+)\)/); return { x: +m[1], y: +m[2], s: +m[3] }; };
const place = (layout, id) => layout.blocks.find((b) => b.id === id);
const without = (id) => ({ ...TREE, blocks: TREE.blocks.filter((b) => b.id !== id), links: TREE.links.filter((l) => l.to !== id) });

test('drawing twice keeps the same node for every block and link that stays', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), {});
  const [s1, link] = [v.node('s1'), v.node('c1>s1')];
  await v.draw(TREE, lay(), { selected: 's1' });
  assert.equal(v.node('s1'), s1);
  assert.equal(v.node('c1>s1'), link);
  assert.ok(s1.classList.contains('selected'));
});

test('a block sits where the layout says, by transform only', async () => {
  reduce(true);
  const v = view(); const layout = lay();
  await v.draw(TREE, layout, {});
  const at = place(layout, 's2');
  assert.equal(v.node('s2').style.transform, `translate(${at.x}px, ${at.y}px) scale(1)`);
  assert.equal(v.node('s2').style.left, undefined);
});

test('a block that moves glides 260 ms with OUT3', async () => {
  const v = view();
  await v.draw(TREE, lay([], true), { motion: 'none' });
  const from = pos(v.node('s2')).y; const to = place(lay(['s1'], true), 's2').y;
  v.draw(TREE, lay(['s1'], true), {});
  tick(130); assert.ok(near(pos(v.node('s2')).y, from + (to - from) * 0.875));
  tick(130); assert.equal(pos(v.node('s2')).y, to);
});

test('a block that goes fades out in 180 ms with IN3, then its node is gone', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  const node = v.node('s2');
  v.draw(without('s2'), layoutTree(without('s2'), { open: new Set(), narrow: false }), {});
  tick(90); assert.equal(node.style.opacity, '0.875');
  assert.equal(v.node('c1>s2').style.opacity, '0.875');  // a link fades with the fainter of its blocks
  tick(90); assert.equal(v.node('s2'), null); assert.equal(node.parentNode, null);
});

test('an opened block: its links draw in 170 ms, then its column caption and children fade in, 15 ms apart', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(TREE, lay(['s1']), {});
  const draw = v.node('s1>t1').animations[0];
  assert.deepEqual(draw.keyframes, [{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }]);
  assert.deepEqual([draw.options.duration, draw.options.easing], [170, CALM]);
  tick(170); assert.equal(v.node('column:c').style.opacity, '0');
  tick(75); assert.equal(v.node('t1').style.opacity, '0.875');  // 60 ms into its fade, which starts at 185
  tick(75); assert.equal(v.node('t2').style.opacity, '');       // 200 + 120
});

test("a folded block's children shrink toward its right side in 180 ms, then go", async () => {
  const v = view();
  await v.draw(TREE, lay(['s1']), { motion: 'none' });
  const t1 = v.node('t1');
  v.draw(TREE, lay(), {});
  tick(90); assert.ok(near(pos(t1).s, 0.9125)); assert.equal(t1.style.opacity, '0.875');
  tick(90); assert.equal(v.node('t1'), null);
});

test('a link is drawn again from its blocks every frame', async () => {
  const v = view();
  await v.draw(TREE, lay([], true), { motion: 'none' });
  const layout = lay(['s1'], true);
  v.draw(TREE, layout, {});
  tick(130);
  const box = (id) => ({ ...pos(v.node(id)), w: parseFloat(v.node(id).style.width), h: parseFloat(v.node(id).style.height) });
  const link = layout.links.find((l) => linkKey(l) === 'c1>s2');
  assert.equal(v.node('c1>s2').getAttribute('d'), linkPath(link, box('c1'), box('s2')));
});

test('at rest no block or link keeps an inline opacity', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(TREE, lay(['s1']), {}); settle(); await v.draw(TREE, lay(['s1']), {});
  for (const n of walk(v.area)) assert.equal(n.style?.opacity ?? '', '');
});

test('block nodes keep the reading order in the DOM, so Tab follows it', async () => {
  reduce(true);
  const v = view(); const layout = lay(['s1']);
  await v.draw(TREE, lay(), {}); await v.draw(TREE, layout, {});
  const order = v.area.children.filter((n) => n.dataset?.focus).map((n) => n.dataset.focus.slice('block:'.length));
  assert.deepEqual(order, blockOrder(layout));
});

test("a block's words are drawn again only when they change", async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), {});
  const words = v.node('s1').firstElementChild;
  await v.draw(TREE, lay(), { selected: 's1' });
  assert.equal(v.node('s1').firstElementChild, words);
  const renamed = { ...TREE, blocks: TREE.blocks.map((b) => (b.id === 's1' ? { ...b, meta: '1 of 2 on' } : b)) };
  await v.draw(renamed, layoutTree(renamed, { open: new Set(), narrow: false }), {});
  assert.notEqual(v.node('s1').firstElementChild, words);
});

test("a group's caption draws its icon before its words, 13 px; a caption with no icon is words only", async () => {
  reduce(true);
  const groups = { columns: TREE.columns, blocks: [{ id: 'g1', column: 'b', kind: 'group', name: 'Remote', icon: 'cloud' }, { id: 'g2', column: 'b', kind: 'group', name: 'Local' }], links: [] };
  const v = view();
  await v.draw(groups, layoutTree(groups, { open: new Set(), narrow: false }), {});
  const [mark, words] = v.node('g1').children;
  assert.deepEqual([mark.dataset.icon, mark.getAttribute('width'), words.textContent], ['cloud', '13', 'Remote']);
  assert.deepEqual([v.node('g2').children.length, v.node('g2').textContent], [0, 'Local']);
  // The same caption drawn again keeps its icon node; a new icon replaces it.
  await v.draw(groups, layoutTree(groups, { open: new Set(), narrow: false }), {});
  assert.equal(v.node('g1').children[0], mark);
  const changed = { ...groups, blocks: [{ ...groups.blocks[0], icon: 'info' }, groups.blocks[1]] };
  await v.draw(changed, layoutTree(changed, { open: new Set(), narrow: false }), {});
  assert.equal(v.node('g1').children[0].dataset.icon, 'info');
});

test('a held block stays where it is put across draws, and glides home when let go', async () => {
  const v = view();
  await v.draw(TREE, lay([], true), { motion: 'none' });
  v.hold('s2', { x: 500, y: 300 });
  assert.deepEqual(pos(v.node('s2')), { x: 500, y: 300, s: 1 });
  assert.ok(v.node('s2').classList.contains('dragging'));
  v.draw(TREE, lay(['s1'], true), {}); settle();
  assert.deepEqual(pos(v.node('s2')), { x: 500, y: 300, s: 1 });
  v.letGo('s2'); tick(260);
  assert.equal(pos(v.node('s2')).y, place(lay(['s1'], true), 's2').y);
  assert.ok(!v.node('s2').classList.contains('dragging'));
});

// Review Focus
test('a draw during a move ends at the newer layout, one node per id', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(TREE, lay(['s1']), {}); tick(50);
  v.draw(TREE, lay(), {}); tick(10);
  v.draw(TREE, lay(['s1']), {}); settle();
  const ids = v.area.children.map((n) => n.dataset?.focus).filter(Boolean);
  assert.equal(new Set(ids).size, ids.length);
  assert.equal(v.node('t1').style.opacity, '');
  assert.deepEqual(pos(v.node('t1')), { x: place(lay(['s1']), 't1').x, y: place(lay(['s1']), 't1').y, s: 1 });
});

test('under reduced motion every block and link is at its end at once', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), {});
  await v.draw(TREE, lay(['s1']), {});
  assert.equal(v.node('t1').style.opacity, '');
  assert.ok(walk(v.area).every((n) => !n.animations?.length));
  await v.draw(TREE, lay(), {});
  assert.equal(v.node('t1'), null);
});

test('a hidden page jumps every motion to its end', async () => {
  document.hidden = true;
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  await v.draw(TREE, lay(['s1']), {});  // resolves with no frame run
  assert.equal(v.node('t1').style.opacity, '');
  document.hidden = false;
});

test('a block with keyboard focus keeps it through a draw that moves it', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay([], true), {});
  v.node('s2').focus();
  await v.draw(TREE, lay(['s1'], true), {});
  assert.equal(document.activeElement, v.node('s2'));
});

test('a new width that reads the blocks in another order puts their nodes in that order; focus stays', async () => {
  reduce(true);
  const v = view(); const wide = lay(['s1']);
  await v.draw(TREE, lay(['s1'], true), {});
  v.node('s2').focus();
  await v.draw(TREE, wide, { motion: 'none' });
  const order = v.area.children.filter((n) => n.dataset?.focus).map((n) => n.dataset.focus.slice('block:'.length));
  assert.deepEqual(order, blockOrder(wide));
  assert.equal(document.activeElement, v.node('s2'));
});

test('a press opens a block that folds, then selects it; any other block is only selected', async () => {
  reduce(true);
  const heard = [];
  const v = view({ onOpen: (id) => heard.push(`open ${id}`), onSelect: (id) => heard.push(`select ${id}`) });
  await v.draw(TREE, lay(), {});
  v.node('s1').dispatch('click');
  v.node('c1').dispatch('click');
  assert.deepEqual(heard, ['open s1', 'select s1', 'select c1']);
});

test('the entrance: each block rises 6 px in 260 ms OUT3, 22 ms apart in layout order', async () => {
  const v = view(); const layout = lay();
  v.draw(TREE, layout, { motion: 'enter' });
  const ids = layout.blocks.map((b) => b.id); const last = v.node(ids.at(-1)); const end = 22 * (ids.length - 1);
  assert.equal(pos(v.node(ids[0])).y, place(layout, ids[0]).y + 6); assert.equal(v.node(ids[0]).style.opacity, '0');
  tick(end); assert.equal(last.style.opacity, '0');
  tick(130); assert.ok(near(pos(last).y, place(layout, ids.at(-1)).y + 6 * 0.125));
  tick(130); assert.equal(pos(last).y, place(layout, ids.at(-1)).y); assert.equal(last.style.opacity, '');
});

test('in the entrance a link shows only as much as the fainter of its two blocks', async () => {
  const v = view(); const layout = lay();
  v.draw(TREE, layout, { motion: 'enter' });
  const later = layout.blocks.findIndex((b) => b.id === 's2');
  tick(22 * later + 130);
  assert.equal(v.node('c1>s2').style.opacity, v.node('s2').style.opacity);
});

test('under reduced motion the entrance leaves every block and link visible at once', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(['s1']), { motion: 'enter' });
  for (const n of walk(v.area)) { assert.ok(!n.animations?.length); if (n.style) assert.equal(n.style.opacity ?? '', ''); }
});

test('a big entrance starts its last block at 440 ms, not 22 ms per block', async () => {
  const blocks = Array.from({ length: 40 }, (_, i) => ({ id: `x${i}`, column: 'b', kind: 'held', name: `x${i}`, state: 'on', count: 0 }));
  const big = { columns: TREE.columns, blocks, links: [] };
  const layout = layoutTree(big, { open: new Set(), narrow: false });
  const v = view();
  v.draw(big, layout, { motion: 'enter' });
  const last = v.node(layout.blocks.at(-1).id);
  assert.ok(layout.blocks.length > 21);
  tick(440); assert.equal(last.style.opacity, '0');
  tick(260); assert.equal(last.style.opacity, '');
});

const clicked = []; const removed = [];
const LINKS = { canHit: (l) => l.to === 's1', tip: (l) => `Remove ${l.to}`, onClick: (l) => clicked.push(l), onRemove: (l) => removed.push(l) };
const hitOf = (v) => walk(v.area).find((n) => n.classList?.contains('hit'));
const xOf = (v) => walk(v.area).find((n) => n.classList?.contains('link-x'));

test('only a link the page acts on takes the pointer, after the blocks, named for keyboards', async () => {
  reduce(true);
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), {});
  const hits = walk(v.area).filter((n) => n.classList?.contains('hit'));
  assert.equal(hits.length, 1);
  const h = hits[0];
  assert.deepEqual(['tabindex', 'role', 'aria-label', 'aria-description', 'aria-keyshortcuts'].map((a) => h.getAttribute(a)), ['0', 'button', 'Codex to github', 'Remove s1', 'Delete']);
  const svg = h.parentNode;
  assert.equal(svg.getAttribute('aria-label'), 'Connections');
  assert.ok(v.area.children.indexOf(svg) > v.area.children.findLastIndex((n) => n.dataset?.focus));
});

test('pointing at a link gives it the hover look and puts the × on its middle', async () => {
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), { motion: 'none' });
  hitOf(v).dispatch('pointerover');
  const m = midPoint(v.node('c1>s1').getAttribute('d')); const x = xOf(v);
  assert.ok(v.node('c1>s1').classList.contains('hov'));
  assert.equal(x.hidden, false);
  assert.equal(x.style.transform, `translate(${Math.round(m.x - 8)}px, ${Math.round(m.y - 8)}px)`);
  assert.equal(x.getAttribute('aria-label'), 'Remove s1');
  assert.deepEqual([x.animations[0].options.duration, x.animations[0].options.easing], [120, CALM]);
});

test('the × waits 240 ms after the pointer leaves, also under reduced motion, and the pointer on it keeps it', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  reduce(true);
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), {});
  const [h, x] = [hitOf(v), xOf(v)];
  h.dispatch('pointerover'); h.dispatch('pointerout');
  t.mock.timers.tick(239); assert.equal(x.hidden, false);
  t.mock.timers.tick(1); assert.equal(x.hidden, true); assert.ok(!v.node('c1>s1').classList.contains('hov'));
  h.dispatch('pointerover'); h.dispatch('pointerout'); x.dispatch('pointerenter');
  t.mock.timers.tick(500); assert.equal(x.hidden, false);
  x.dispatch('pointerleave'); t.mock.timers.tick(240); assert.equal(x.hidden, true);
});

test('Enter on a link is its click, Delete and the × are its removal', async () => {
  reduce(true); clicked.length = 0; removed.length = 0;
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), {});
  const h = hitOf(v);
  h.dispatch('keydown', { key: 'Enter' }); h.dispatch('click');
  h.dispatch('keydown', { key: 'Delete' }); h.dispatch('keydown', { key: 'Backspace' }); xOf(v).dispatch('click');
  assert.deepEqual([clicked.length, removed.length], [2, 3]);
  h.focus(); assert.ok(v.node('c1>s1').classList.contains('hov'));
});

test('a link fainter than half takes no pointer', async () => {
  const v = view({ links: { ...LINKS, canHit: (l) => l.to === 's2' } });
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(without('s2'), layoutTree(without('s2'), { open: new Set(), narrow: false }), {});
  tick(90); assert.equal(hitOf(v).style.display, '');
  tick(60); assert.equal(hitOf(v).style.display, 'none');
});

test('a link takes the × to another link at once, and a hit has a focus key for the page to restore', async () => {
  reduce(true);
  const v = view({ links: { ...LINKS, canHit: () => true, tip: (l) => `Remove ${l.to}` } });
  await v.draw(TREE, lay(), {});
  const [a, b] = walk(v.area).filter((n) => n.classList?.contains('hit'));
  assert.deepEqual([a.dataset.focus, b.dataset.focus], ['link:c1>s1', 'link:c1>s2']);
  a.dispatch('pointerover'); b.dispatch('pointerover');
  assert.equal(xOf(v).getAttribute('aria-label'), 'Remove s2');
  assert.deepEqual([v.node('c1>s1').classList.contains('hov'), v.node('c1>s2').classList.contains('hov')], [false, true]);
});

test('blocks that come or flip order still sit before the hits and the ×', async () => {
  reduce(true);
  const v = view({ links: LINKS });
  const smaller = without('s2');
  await v.draw(smaller, layoutTree(smaller, { open: new Set(), narrow: false }), {});
  await v.draw(TREE, lay(['s1'], true), {});
  await v.draw(TREE, lay(['s1']), {});
  const svg = hitOf(v).parentNode;
  assert.ok(v.area.children.indexOf(svg) > v.area.children.findLastIndex((n) => n.dataset?.focus));
  assert.equal(v.area.children.at(-1), xOf(v));
});

test('a hit follows its link while blocks move, and goes with it', async () => {
  const v = view({ links: { ...LINKS, canHit: (l) => l.to === 's2' } });
  await v.draw(TREE, lay([], true), { motion: 'none' });
  const first = hitOf(v).getAttribute('d');
  v.draw(TREE, lay(['s1'], true), {});
  tick(130);
  assert.notEqual(hitOf(v).getAttribute('d'), first);
  assert.equal(hitOf(v).getAttribute('d'), v.node('c1>s2').getAttribute('d'));
  hitOf(v).dispatch('pointerover');
  settle();
  const gone = without('s2');
  await v.draw(gone, layoutTree(gone, { open: new Set(), narrow: false }), { motion: 'none' });
  assert.equal(hitOf(v), undefined);
  assert.equal(xOf(v).hidden, true);
});

test('focus that is not for a keyboard does not give the link its hover look; a press still does', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  reduce(true);
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), {});
  const [h, x, link] = [hitOf(v), xOf(v), v.node('c1>s1')];
  // A mouse click focused it, the panel took the focus, and closing the panel gives it back.
  h.matches = () => false;
  h.focus();
  assert.ok(!link.classList.contains('hov')); assert.equal(x.hidden, true);
  // A press (the click itself) still points at it.
  h.dispatch('click');
  assert.ok(link.classList.contains('hov')); assert.equal(x.hidden, false);
  h.dispatch('blur'); t.mock.timers.tick(240);
  assert.ok(!link.classList.contains('hov')); assert.equal(x.hidden, true);
  // Focus from the keyboard points at it.
  h.matches = () => true;
  h.focus();
  assert.ok(link.classList.contains('hov')); assert.equal(x.hidden, false);
});

test('Delete with a modifier, or held down, removes nothing; a plain Delete removes once', async () => {
  reduce(true); removed.length = 0;
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), {});
  const h = hitOf(v);
  for (const init of [{ ctrlKey: true }, { metaKey: true }, { altKey: true }, { shiftKey: true }, { repeat: true }]) {
    const event = h.dispatch('keydown', { key: 'Delete', ...init });
    assert.equal(event.defaultPrevented, false);
  }
  h.dispatch('keydown', { key: 'Backspace', metaKey: true });
  assert.equal(removed.length, 0);
  h.dispatch('keydown', { key: 'Delete' });
  assert.equal(removed.length, 1);
});
