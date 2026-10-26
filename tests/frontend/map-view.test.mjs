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
      const animation = { keyframes, options, cancelled: false, finished: Promise.resolve(), cancel() { animation.cancelled = true; } };
      node.animations.push(animation);
      return animation;
    },
    getAnimations: () => node.animations.filter((a) => !a.cancelled),
  };
  return node;
}
// The dash look of a link, read from its class: leaving and preview are dashed, the rest solid.
globalThis.getComputedStyle = (node) => {
  if (node.classList.contains('leaving')) return { strokeDasharray: '4 4', strokeOpacity: '0.4' };
  if (node.classList.contains('preview')) return { strokeDasharray: '4 4', strokeOpacity: '0.65' };
  return { strokeDasharray: 'none', strokeOpacity: '1' };
};
globalThis.document = { hidden: false, activeElement: null, createElement: (tag) => element(tag.toUpperCase()), createElementNS: (namespace, tag) => element(tag) };

beforeEach(() => {
  now = 0;
  frames = [];
  reduce(false);
  globalThis.document.hidden = false;
  globalThis.document.activeElement = null;
});

const { blockOrder, layoutTree, linkKey, linkPath, midPoint } = await import('../../src/kitden/web/static/js/map.js');
const { CALM, RETRACT, finishTransition, transition } = await import('../../src/kitden/web/static/js/motion.js');
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
// Where a block shows: its place is the `translate` property, its scale the `transform`.
const pos = (n) => { const [x, y] = n.style.translate.split(' ').map(parseFloat); const m = n.style.transform.match(/^scale\(([-\d.]+)\)$/); return { x, y, s: m ? +m[1] : 1 }; };
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

test('a block sits where the layout says, by the translate property; the transform is only its scale', async () => {
  reduce(true);
  const v = view(); const layout = lay();
  await v.draw(TREE, layout, {});
  const at = place(layout, 's2');
  // A press scales the block with the CSS `scale` property. That property turns about the box's own
  // middle only when the place is not in `transform`: it would pull the place 2 % toward the corner.
  assert.equal(v.node('s2').style.translate, `${at.x}px ${at.y}px`);
  assert.equal(v.node('s2').style.transform, '');
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

test("a block's tile is drawn again when its icon, client or gateway kind changes", async () => {
  reduce(true);
  const mark = (b) => { const n = document.createElement('i'); n.dataset.look = [b.icon, b.client, b.gateway && b.gateway.kind].join('/'); return n; };
  const v = view({ tile: mark });
  const as = (fields) => ({ ...TREE, blocks: TREE.blocks.map((b) => (b.id === 's1' || b.id === 'c1' ? { ...b, ...fields[b.id] } : b)) });
  const tileOf = (id) => v.node(id).children[0].children[0];
  const show = (m) => v.draw(m, layoutTree(m, { open: new Set(), narrow: false }), {});
  await show(as({ s1: { icon: 'remote', gateway: { kind: 'kitden' } }, c1: { client: 'codex' } }));
  assert.deepEqual([tileOf('s1').dataset.look, tileOf('c1').dataset.look], ['remote//kitden', '/codex/']);
  await show(as({ s1: { icon: 'local', gateway: { kind: 'kitden' } }, c1: { client: 'codex' } }));
  assert.equal(tileOf('s1').dataset.look, 'local//kitden');
  await show(as({ s1: { icon: 'local', gateway: { kind: 'metamcp' } }, c1: { client: 'codex' } }));
  assert.equal(tileOf('s1').dataset.look, 'local//metamcp');
  await show(as({ s1: { icon: 'local', gateway: { kind: 'metamcp' } }, c1: { client: 'cursor' } }));
  assert.equal(tileOf('c1').dataset.look, '/cursor/');
  // Nothing changed: the tile stays.
  const kept = tileOf('s1');
  await show(as({ s1: { icon: 'local', gateway: { kind: 'metamcp' } }, c1: { client: 'cursor' } }));
  assert.equal(tileOf('s1'), kept);
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

test('a held block stays where it is put across draws, and glides home in 220 ms OUT3', async () => {
  const v = view();
  await v.draw(TREE, lay([], true), { motion: 'none' });
  v.hold('s2', { x: 500, y: 300 });
  assert.deepEqual(pos(v.node('s2')), { x: 500, y: 300, s: 1 });
  assert.ok(v.node('s2').classList.contains('dragging'));
  v.draw(TREE, lay(['s1'], true), {}); settle();
  assert.deepEqual(pos(v.node('s2')), { x: 500, y: 300, s: 1 });
  const home = place(lay(['s1'], true), 's2').y;
  v.homeIn('s2'); tick(110);
  assert.ok(near(pos(v.node('s2')).y, 300 + (home - 300) * 0.875));
  tick(110);
  assert.equal(pos(v.node('s2')).y, place(lay(['s1'], true), 's2').y);
  assert.ok(!v.node('s2').classList.contains('dragging'));
});

test('a block that glides home when a draw shows the end at once keeps no .dragging', async () => {
  // A narrow flip or a project change draws with no motion; a hidden page jumps every motion.
  for (const how of ['none', 'hidden']) {
    const v = view();
    await v.draw(TREE, lay([], true), { motion: 'none' });
    v.hold('s2', { x: 500, y: 300 });
    v.homeIn('s2'); tick(100);
    assert.ok(v.node('s2').classList.contains('dragging'), 'it still glides');
    const layout = lay(['s1'], true);
    if (how === 'hidden') document.hidden = true;
    v.draw(TREE, layout, how === 'none' ? { motion: 'none' } : {});
    assert.ok(!v.node('s2').classList.contains('dragging'), how);
    assert.deepEqual(pos(v.node('s2')), { x: place(layout, 's2').x, y: place(layout, 's2').y, s: 1 }, how);
    settle(); document.hidden = false;
    assert.ok(!v.node('s2').classList.contains('dragging'), how);
  }
});

test('a block held with a glide arrives held; letting go of a block the map does not have does nothing', async () => {
  const v = view();
  await v.draw(TREE, lay([], true), { motion: 'none' });
  const from = pos(v.node('s2'));
  v.hold('s2', { x: 500, y: 300 }, { glide: true });
  assert.ok(v.node('s2').classList.contains('dragging'));
  tick(130); assert.ok(near(pos(v.node('s2')).x, from.x + (500 - from.x) * 0.875));
  tick(130); assert.deepEqual(pos(v.node('s2')), { x: 500, y: 300, s: 1 });
  assert.ok(v.node('s2').classList.contains('dragging'), 'held until let go');
  await v.homeIn('nope');
  assert.equal(v.node('nope'), null);
  assert.ok(v.node('s2').classList.contains('dragging'));
  v.homeIn('s2'); settle();
  assert.ok(!v.node('s2').classList.contains('dragging'));
  assert.equal(v.node('s2').style.opacity, '');
});

test('the dragged block keeps its press scale while the pointer is down', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.hold('s2', { x: 500, y: 300 }, { pressed: true });
  assert.ok(v.node('s2').classList.contains('pressed') && v.node('s2').classList.contains('dragging'));
  // A draw while it is held keeps it.
  await v.draw(TREE, lay(), {});
  assert.ok(v.node('s2').classList.contains('pressed'));
  // Let go, it flies on with no press: onto a slot, or home.
  v.hold('s2', { x: 400, y: 300 }, { glide: true, ms: 200 });
  assert.ok(!v.node('s2').classList.contains('pressed') && v.node('s2').classList.contains('dragging'));
  v.hold('s2', { x: 500, y: 300 }, { pressed: true });
  v.homeIn('s2', 220);
  assert.ok(!v.node('s2').classList.contains('pressed'));
});

test('a drop flies onto its spot in 200 ms OUT3', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.hold('s2', { x: 500, y: 300 }, { pressed: true });
  v.hold('s2', { x: 400, y: 200 }, { glide: true, ms: 200 });
  tick(100); assert.ok(near(pos(v.node('s2')).x, 500 - 100 * 0.875));
  tick(100); assert.deepEqual(pos(v.node('s2')), { x: 400, y: 200, s: 1 });
});

test('under reduced motion the drop and the way home land at once', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), {});
  v.hold('s2', { x: 500, y: 300 }, { pressed: true });
  v.hold('s2', { x: 400, y: 200 }, { glide: true, ms: 200 });
  assert.deepEqual([pos(v.node('s2')), frames.length], [{ x: 400, y: 200, s: 1 }, 0]);
  v.homeIn('s2', 220);
  const home = place(lay(), 's2');
  assert.deepEqual([pos(v.node('s2')), frames.length], [{ x: home.x, y: home.y, s: 1 }, 0]);
  assert.ok(!v.node('s2').classList.contains('dragging'));
});

test('a drop target lights with .drop, one at a time, and lets go', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.lightTarget('s1');
  assert.ok(v.node('s1').classList.contains('drop'));
  // A draw keeps it lit.
  await v.draw(TREE, lay(), {});
  assert.ok(v.node('s1').classList.contains('drop'));
  v.lightTarget('c1');
  assert.ok(!v.node('s1').classList.contains('drop') && v.node('c1').classList.contains('drop'));
  v.unlightTarget();
  assert.ok(!v.node('c1').classList.contains('drop'));
});

test('the drag tip sits 6 px right of and 28 px over the held block, plain or on', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.hold('s2', { x: 500, y: 300 }, { pressed: true });
  v.tip('Drop on a client');
  const tip = v.area.children.find((n) => n.classList.contains('dragtip'));
  assert.deepEqual([tip.textContent, tip.className, tip.getAttribute('aria-hidden')], ['Drop on a client', 'dragtip', 'true']);
  assert.equal(tip.style.transform, 'translate(506px, 272px)');
  // It follows the block, and turns on where a drop would work.
  v.hold('s2', { x: 520, y: 310 }, { pressed: true });
  v.tip('Move into Codex', { on: true });
  assert.deepEqual([tip.textContent, tip.className, tip.style.transform], ['Move into Codex', 'dragtip on', 'translate(526px, 282px)']);
  assert.equal(v.area.children.filter((n) => n.classList.contains('dragtip')).length, 1);
  v.untip();
  assert.ok(!v.area.children.some((n) => n.classList.contains('dragtip')));
});

test('a block that takes the place of one that goes starts where that one shows and glides to its place', async () => {
  const v = view();
  const tree = { ...TREE, blocks: TREE.blocks.filter((b) => b.id !== 's2'), links: TREE.links.filter((l) => l.to !== 's2') };
  const withS2 = layoutTree(TREE, { open: new Set(), narrow: false });
  await v.draw(TREE, withS2, { motion: 'none' });
  // s2 is held somewhere and has focus; it turns into p2, which belongs at the bottom of column b.
  v.hold('s2', { x: 500, y: 300 });
  const old = v.node('s2');
  old.focus();
  const turned = { ...tree, blocks: [...tree.blocks, { id: 'p2', column: 'b', kind: 'preview', name: 'files', state: 'preview', from: 's2' }], links: [...tree.links, { from: 'c1', to: 'p2', kind: 'direct' }] };
  const layout = layoutTree(turned, { open: new Set(), narrow: false });
  v.draw(turned, layout, {});
  // The old block is gone at once, the new one is where it was, whole, and has its focus.
  assert.equal(v.node('s2'), null);
  assert.equal(old.parentNode, null);
  assert.deepEqual([pos(v.node('p2')), v.node('p2').style.opacity], [{ x: 500, y: 300, s: 1 }, '']);
  assert.equal(document.activeElement, v.node('p2'));
  const end = place(layout, 'p2');
  tick(130); assert.ok(near(pos(v.node('p2')).x, 500 + (end.x - 500) * 0.875));
  tick(130); assert.deepEqual(pos(v.node('p2')), { x: end.x, y: end.y, s: 1 });
  // Back the other way under reduced motion: at its place at once.
  reduce(true);
  const back = { ...TREE, blocks: TREE.blocks.map((b) => (b.id === 's2' ? { ...b, from: 'p2' } : b)) };
  v.draw(back, withS2, {});
  assert.equal(v.node('p2'), null);
  assert.deepEqual([pos(v.node('s2')), frames.length], [{ x: place(withS2, 's2').x, y: place(withS2, 's2').y, s: 1 }, 0]);
});

// TREE with a slot `g1` that grows out of the client c1, in column b after s1.
const withSlot = () => ({ ...TREE, blocks: [...TREE.blocks.slice(0, 2), { id: 'g1', column: 'b', kind: 'slot', name: 'Drop to add', state: 'preview', growsFrom: 'c1' }, ...TREE.blocks.slice(2)] });

test('a block that grows out of another starts small on its right side and grows in 220 ms OUT3; the rest glide 220 too', async () => {
  const v = view();
  const plain = layoutTree(TREE, { open: new Set(), narrow: false });
  await v.draw(TREE, plain, { motion: 'none' });
  const grown = layoutTree(withSlot(), { open: new Set(), narrow: false });
  v.draw(withSlot(), grown, {});
  const c1 = place(plain, 'c1');
  const g1 = place(grown, 'g1');
  const from = { x: c1.x + c1.w - g1.w / 2, y: c1.y + c1.h / 2 - g1.h / 2 };
  assert.deepEqual([pos(v.node('g1')), v.node('g1').style.opacity], [{ ...from, s: 0.4 }, '0']);
  const [s2From, s2To] = [place(plain, 's2').y, place(grown, 's2').y];
  tick(110);
  assert.ok(near(pos(v.node('g1')).y, from.y + (g1.y - from.y) * 0.875));
  assert.ok(near(pos(v.node('s2')).y, s2From + (s2To - s2From) * 0.875), 'the block below makes room in the same time');
  tick(110);
  assert.deepEqual([pos(v.node('g1')), v.node('g1').style.opacity, pos(v.node('s2')).y], [{ x: g1.x, y: g1.y, s: 1 }, '', s2To]);
});

test('a block that grew out of another shrinks back into it in 180 ms IN3, then goes', async () => {
  const v = view();
  const grown = layoutTree(withSlot(), { open: new Set(), narrow: false });
  await v.draw(withSlot(), grown, { motion: 'none' });
  const node = v.node('g1');
  const plain = layoutTree(TREE, { open: new Set(), narrow: false });
  v.draw(TREE, plain, {});
  const c1 = place(plain, 'c1');
  const g1 = place(grown, 'g1');
  tick(90);
  assert.ok(near(pos(node).s, 1 - 0.6 * 0.125));
  assert.equal(node.style.opacity, '0.875');
  // The block below moves up in 220, as the slot goes.
  const [s2From, s2To] = [place(grown, 's2').y, place(plain, 's2').y];
  assert.ok(near(pos(v.node('s2')).y, s2From + (s2To - s2From) * (1 - (1 - 90 / 220) ** 3)));
  tick(90);
  assert.equal(v.node('g1'), null);
  assert.deepEqual([pos(node).x, pos(node).y], [c1.x + c1.w - g1.w / 2, c1.y + c1.h / 2 - g1.h / 2]);
});

test('under reduced motion a block grows and shrinks back at once', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), {});
  const grown = layoutTree(withSlot(), { open: new Set(), narrow: false });
  v.draw(withSlot(), grown, {});
  assert.deepEqual([pos(v.node('g1')), v.node('g1').style.opacity, frames.length], [{ x: place(grown, 'g1').x, y: place(grown, 'g1').y, s: 1 }, '', 0]);
  v.draw(TREE, lay(), {});
  assert.deepEqual([v.node('g1'), frames.length], [null, 0]);
});

test('a block dropped onto another hides that one at once, until it goes home', async () => {
  const v = view();
  const grown = layoutTree(withSlot(), { open: new Set(), narrow: false });
  await v.draw(withSlot(), grown, { motion: 'none' });
  const g1 = place(grown, 'g1');
  v.hold('s2', { x: 500, y: 300 }, { pressed: true });
  v.hold('s2', { x: g1.x, y: g1.y }, { glide: true, ms: 200, onto: 'g1' });
  assert.ok(v.node('g1').classList.contains('covered'));
  // A draw keeps it hidden, also once the block has landed.
  v.draw(withSlot(), grown, {}); settle();
  assert.ok(v.node('g1').classList.contains('covered'));
  v.homeIn('s2');
  assert.ok(!v.node('g1').classList.contains('covered'));
});

test("a drag's wire runs from a client's right port to the held block's left port, follows it, and fades out in 240 ms", async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const v = view();
  const layout = lay();
  await v.draw(TREE, layout, { motion: 'none' });
  const svg = v.area.children.find((n) => n.className === 'map-links');
  const wires = () => svg.children.filter((n) => n.className === 'link preview lit');
  const c1 = place(layout, 'c1');
  const s2 = place(layout, 's2');
  v.hold('s2', { x: 500, y: 300 }, { pressed: true });
  v.wire('c1', 's2');
  // The accent dashes of a preview, lit; at once, with no fade in.
  assert.equal(wires().length, 1);
  const wire = wires()[0];
  assert.deepEqual([wire.getAttribute('d'), wire.animations], [linkPath({}, c1, { x: 500, y: 300, w: s2.w, h: s2.h }), []]);
  // It follows the held block; the same wire again is the same one.
  v.hold('s2', { x: 520, y: 340 }, { pressed: true });
  assert.equal(wire.getAttribute('d'), linkPath({}, c1, { x: 520, y: 340, w: s2.w, h: s2.h }));
  v.wire('c1', 's2');
  assert.deepEqual(wires(), [wire]);
  // Off the client it fades out in 240 ms ease-out, then goes.
  v.unwire();
  const fade = wire.animations.at(-1);
  assert.deepEqual([fade.keyframes, fade.options.duration, fade.options.easing], [[{ opacity: 1 }, { opacity: 0 }], 240, 'ease-out']);
  assert.equal(wire.parentNode, svg);
  t.mock.timers.tick(240);
  assert.equal(wire.parentNode, null);
  // Under reduced motion it goes at once.
  reduce(true);
  v.wire('c1', 's2');
  const again = wires()[0];
  v.unwire();
  assert.deepEqual([again.parentNode, again.animations], [null, []]);
});

// A client's wire (gateway-notes 6.3): to the pointer, plain, and snapped onto a block.
test("a client's wire runs to the pointer, snaps to a block's left port, and a miss fades it in 180 CALM", async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const v = view();
  const layout = lay();
  await v.draw(TREE, layout, { motion: 'none' });
  const svg = v.area.children.find((n) => n.className === 'map-links');
  const wires = () => svg.children.filter((n) => n.className === 'link preview wire');
  const c1 = place(layout, 'c1');
  const s2 = place(layout, 's2');
  // From its right port to the pointer, level at both ends, with handles of at least 18 px.
  v.wire('c1', { x: 300, y: 40 }, { plain: true });
  const wire = wires()[0];
  const [x0, y0] = [c1.x + c1.w, c1.y + c1.h / 2];
  const k = Math.max(18, (300 - x0) / 2);
  assert.equal(wire.getAttribute('d'), `M ${x0} ${y0} C ${x0 + k} ${y0}, ${300 - k} 40, 300 40`);
  // It follows the pointer and stays one wire; over a block it ends on that block's left port.
  v.wire('c1', { x: x0 + 10, y: y0 }, { plain: true });
  assert.equal(wire.getAttribute('d'), `M ${x0} ${y0} C ${x0 + 18} ${y0}, ${x0 + 10 - 18} ${y0}, ${x0 + 10} ${y0}`);
  v.wire('c1', 's2', { plain: true });
  assert.deepEqual([wires(), wire.getAttribute('d')], [[wire], linkPath({}, c1, s2)]);
  // A miss fades it out in 180 ms CALM, then it goes.
  v.unwire({ ms: 180, ease: CALM });
  const fade = wire.animations.at(-1);
  assert.deepEqual([fade.keyframes, fade.options.duration, fade.options.easing], [[{ opacity: 1 }, { opacity: 0 }], 180, CALM]);
  t.mock.timers.tick(180);
  assert.equal(wire.parentNode, null);
  // A drop takes it away at once.
  v.wire('c1', { x: 300, y: 40 }, { plain: true });
  const dropped = wires()[0];
  v.unwire({ ms: 0 });
  assert.deepEqual([dropped.parentNode, dropped.animations], [null, []]);
});

test('under reduced motion the wire appears and goes at once', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  const svg = v.area.children.find((n) => n.className === 'map-links');
  v.wire('c1', { x: 300, y: 40 }, { plain: true });
  const wire = svg.children.find((n) => n.className === 'link preview wire');
  assert.deepEqual([wire.parentNode, wire.animations], [svg, []]);
  v.unwire({ ms: 180, ease: CALM });
  assert.deepEqual([wire.parentNode, wire.animations], [null, []]);
});

test('the drag tip can go by the pointer: 12 px right of it and 30 px over it', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.tip('Drop on the gateway', { at: { x: 100, y: 200 } });
  const tip = v.area.children.find((n) => n.classList.contains('dragtip'));
  assert.equal(tip.style.transform, 'translate(112px, 170px)');
  v.tip('Connect Cursor', { on: true, at: { x: 140, y: 210 } });
  assert.deepEqual([tip.className, tip.style.transform], ['dragtip on', 'translate(152px, 180px)']);
  // Without a pointer it goes by the held block again.
  v.hold('s2', { x: 500, y: 300 }, { pressed: true });
  v.tip('Drop on a client');
  assert.equal(tip.style.transform, 'translate(506px, 272px)');
  v.untip();
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

// A group of twelve servers that pages five at a time; a client reaches s0 and s5, and s6 directly.
const PAGED = {
  columns: [{ id: 'a', w: 150, h: 54 }, { id: 'b', w: 170, h: 50 }],
  blocks: [
    { id: 'c1', column: 'a', kind: 'client', name: 'Codex' },
    { id: 'g', column: 'b', kind: 'group', name: 'Remote' },
    ...Array.from({ length: 12 }, (_, i) => ({ id: `s${i}`, column: 'b', parent: 'g', kind: 'held', name: `s${i}` })),
  ],
  links: [{ from: 'c1', to: 's0', kind: 'on' }, { from: 'c1', to: 's5', kind: 'on' }, { from: 'c1', to: 's6', kind: 'direct' }],
};
const paged = (page) => layoutTree(PAGED, { open: new Set(), pages: new Map([['g', page]]), narrow: false });
const words = (n) => walk(n).map((child) => child.textContent).join('');

test('a page turn folds the five shown into their caption in 180 ms IN3 and unfolds the next five as tools do', async () => {
  const v = view();
  await v.draw(PAGED, paged(0), { motion: 'none' });
  const [s0, more] = [v.node('s0'), v.node('more:g')];
  const from = pos(s0);
  const cap = place(paged(1), 'g');
  v.draw(PAGED, paged(1), {});
  // Each of the five shown shrinks toward its caption.
  tick(90);
  assert.ok(near(pos(s0).s, 0.9125)); assert.equal(s0.style.opacity, '0.875');
  assert.ok(near(pos(s0).y, from.y + (cap.y + cap.h / 2 - 25 - from.y) * 0.125));
  // The next five wait while their solid links draw (170 ms), then fade in 120 ms OUT3, 15 ms apart.
  tick(80);
  assert.equal(v.node('s5').style.opacity, '0');
  assert.deepEqual(v.node('c1>s5').animations[0].keyframes, [{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }]);
  tick(60);
  assert.equal(v.node('s0'), null);
  assert.equal(v.node('s5').style.opacity, '0.875');
  // A dotted line comes in with its block: it is not drawn as a solid line first.
  assert.equal(v.node('c1>s6').animations.length, 0);
  settle();
  assert.deepEqual([v.node('s6').style.opacity, v.node('more:g'), words(v.node('g'))], ['', more, 'Remote · 6–10 of 12']);
});

test('under reduced motion a turn lands at once', async () => {
  reduce(true);
  const v = view();
  await v.draw(PAGED, paged(0), {});
  const more = v.node('more:g');
  more.focus();
  await v.draw(PAGED, paged(1), {});
  assert.deepEqual([v.node('s0'), v.node('s5').style.opacity, v.node('s5').style.transform], [null, '', '']);
  assert.ok(walk(v.area).every((n) => !n.animations?.length));
  // "N more" is the same button, with its new words, and keeps focus.
  assert.deepEqual([v.node('more:g'), document.activeElement], [more, more]);
  assert.equal(more.getAttribute('aria-label'), '2 more');
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

test('an entrance that comes with a Gateway place change starts after the old page has left, 120 ms later', async () => {
  globalThis.document.documentElement = { classList: { add() {}, remove() {} } };
  globalThis.document.startViewTransition = (change) => { change(); return { ready: Promise.resolve(), finished: new Promise(() => {}), skipTransition() {} }; };
  try {
    const v = view(); const layout = lay();
    transition(() => { v.draw(TREE, layout, { motion: 'enter' }); }, 'map-entrance');
    const first = v.node(layout.blocks[0].id); const at = layout.blocks[0].y;
    tick(110); assert.equal(pos(first).y, at + 6); assert.equal(first.style.opacity, '0');
    tick(140); assert.ok(near(pos(first).y, at + 6 * 0.125));  // 130 ms into its rise, which starts at 120
  } finally {
    finishTransition();
    delete globalThis.document.documentElement;
    delete globalThis.document.startViewTransition;
  }
});

test('in the entrance a link shows only as much as the fainter of its two blocks', async () => {
  const v = view(); const layout = lay();
  v.draw(TREE, layout, { motion: 'enter' });
  const later = layout.blocks.findIndex((b) => b.id === 's2');
  tick(22 * later + 130);
  assert.notEqual(v.node('s2').style.opacity, '', 'the block is still on its way');
  assert.equal(v.node('c1>s2').style.opacity, v.node('s2').style.opacity);
});

test('a hidden page shows the entrance at once: nothing rises, no frame is asked for', async () => {
  document.hidden = true;
  const v = view(); const layout = lay();
  const done = v.draw(TREE, layout, { motion: 'enter' });
  assert.equal(frames.length, 0);
  for (const { id } of layout.blocks) {
    assert.deepEqual(pos(v.node(id)), { x: place(layout, id).x, y: place(layout, id).y, s: 1 }, id);
    assert.equal(v.node(id).style.opacity, '', id);
  }
  assert.ok(walk(v.area).every((n) => !n.animations?.length));
  for (const n of walk(v.area)) assert.equal(n.style?.opacity ?? '', '');
  await done;
});

test('an entrance that is drawn over keeps one node per id and leaves nothing half-way', async () => {
  const v = view();
  v.draw(TREE, lay(), { motion: 'enter' });
  tick(50);
  // The layout changes while the blocks still rise, and then the same layout is drawn again.
  v.draw(TREE, lay(['s1']), {});
  tick(30);
  v.draw(TREE, lay(['s1']), {});
  settle();
  const ids = v.area.children.map((n) => n.dataset?.focus).filter(Boolean);
  assert.equal(new Set(ids).size, ids.length);
  assert.deepEqual(ids.map((id) => id.slice('block:'.length)).sort(), blockOrder(lay(['s1'])).sort());
  for (const { id } of lay(['s1']).blocks) {
    assert.deepEqual(pos(v.node(id)), { x: place(lay(['s1']), id).x, y: place(lay(['s1']), id).y, s: 1 }, id);
    assert.equal(v.node(id).style.opacity, '', id);
  }
  for (const n of walk(v.area)) assert.equal(n.style?.opacity ?? '', '');
  // And back to the first layout, which also has to settle.
  v.draw(TREE, lay(), {}); settle();
  assert.equal(v.node('t1'), null);
  for (const n of walk(v.area)) assert.equal(n.style?.opacity ?? '', '');
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

test('a link the page opens but cannot remove takes the pointer with no × and no Delete', async () => {
  reduce(true); clicked.length = 0; removed.length = 0;
  const v = view({ links: { ...LINKS, canHit: () => true, tip: (l) => (l.to === 's1' ? 'Remove s1' : '') } });
  await v.draw(TREE, lay(), {});
  const [a, b] = walk(v.area).filter((n) => n.classList?.contains('hit'));
  assert.deepEqual([b.getAttribute('aria-label'), b.getAttribute('aria-description'), b.getAttribute('aria-keyshortcuts')], ['Codex to files', null, null]);
  assert.equal(a.getAttribute('aria-keyshortcuts'), 'Delete');
  b.dispatch('pointerover');
  assert.ok(v.node('c1>s2').classList.contains('hov'));
  assert.equal(xOf(v).hidden, true);
  // Delete on it does nothing, and leaves the key to the page.
  const del = b.dispatch('keydown', { key: 'Delete' }); b.dispatch('keydown', { key: 'Enter' });
  assert.deepEqual([clicked.length, removed.length, del.defaultPrevented], [1, 0, false]);
  a.dispatch('pointerover');
  assert.equal(xOf(v).hidden, false);
});

test('the hits of lines that skip the gateway sit under the others, so a solid link wins where they cross', async () => {
  reduce(true);
  // c1 sets up a server on its own (a direct line) and reaches s1 and s2 (solid links).
  const direct = { from: 'c1', to: 's2', kind: 'direct' };
  const tree = { ...TREE, links: [{ from: 'c1', to: 's1', kind: 'on' }, direct] };
  const v = view({ links: { ...LINKS, canHit: () => true } });
  await v.draw(tree, layoutTree(tree, { open: new Set(), narrow: false }), {});
  const order = () => walk(v.area).filter((n) => n.classList?.contains('hit')).map((n) => [n.dataset.focus, n.getAttribute('class')]);
  assert.deepEqual(order(), [['link:c1>s2', 'hit direct'], ['link:c1>s1', 'hit']]);
  // A solid link drawn later still goes after the direct one, and a direct line drawn later before
  // every solid one.
  const later = { ...tree, links: [...tree.links, { from: 's1', to: 't1', kind: 'on' }, { from: 'c1', to: 't2', kind: 'direct' }] };
  await v.draw(later, layoutTree(later, { open: new Set(['s1']), narrow: false }), {});
  assert.deepEqual(order().map(([key]) => key), ['link:c1>s2', 'link:c1>t2', 'link:c1>s1', 'link:s1>t1']);
});

test("the × of the link pointed at says what it does after a draw, as its change joins the tray", async () => {
  reduce(true);
  let waits = false;
  const v = view({ links: { ...LINKS, tip: (l) => (waits ? 'Take it out of the preview' : `Remove ${l.to}`) } });
  await v.draw(TREE, lay(), {});
  hitOf(v).dispatch('pointerover');
  assert.equal(xOf(v).getAttribute('aria-label'), 'Remove s1');
  waits = true;
  await v.draw(TREE, lay(), {});
  assert.deepEqual([xOf(v).getAttribute('aria-label'), hitOf(v).getAttribute('aria-description')], ['Take it out of the preview', 'Take it out of the preview']);
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

test('the link with keyboard focus keeps its look when the pointer passes over another link', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  reduce(true);
  const v = view({ links: { ...LINKS, canHit: () => true } });
  await v.draw(TREE, lay(), {});
  const [a, b] = walk(v.area).filter((n) => n.classList?.contains('hit'));
  const [one, two, x] = [v.node('c1>s1'), v.node('c1>s2'), xOf(v)];
  a.matches = () => true;
  a.focus();
  b.dispatch('pointerover'); b.dispatch('pointerout'); t.mock.timers.tick(240);
  // Its hover look is its only focus mark: it comes back, with the × on it.
  assert.deepEqual([one.classList.contains('hov'), two.classList.contains('hov')], [true, false]);
  assert.deepEqual([x.hidden, x.getAttribute('aria-label')], [false, 'Remove s1']);
  // Focus that is no keyboard focus (a mouse click) has no look to come back.
  a.matches = () => false;
  b.dispatch('pointerover'); b.dispatch('pointerout'); t.mock.timers.tick(240);
  assert.deepEqual([one.classList.contains('hov'), x.hidden], [false, true]);
});

test('a link that goes while it has keyboard focus does not come back as the focus look', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const v = view({ links: { ...LINKS, canHit: (l) => l.to === 's2' } });
  await v.draw(TREE, drawn(TREE), { motion: 'none' });
  const h = hitOf(v);
  h.matches = () => true;
  h.focus();
  assert.ok(v.node('c1>s2').classList.contains('hov'));
  v.draw(NO_LINK, drawn(NO_LINK), {});
  assert.equal(xOf(v).hidden, true);
  assert.ok(!v.node('c1>s2').classList.contains('hov'));
  t.mock.timers.tick(500);
  assert.equal(xOf(v).hidden, true);
});

test('a link that fades away under the pointer takes its look and × and does not take them back', async () => {
  const v = view({ links: { ...LINKS, canHit: (l) => l.to === 's2' } });
  await v.draw(TREE, lay(), { motion: 'none' });
  const h = hitOf(v);
  h.matches = () => true;
  h.focus();
  v.draw(without('s2'), layoutTree(without('s2'), { open: new Set(), narrow: false }), {});
  tick(90); tick(60);
  assert.equal(h.style.display, 'none');
  assert.equal(xOf(v).hidden, true);
  assert.ok(!v.node('c1>s2').classList.contains('hov'));
});

test('the look of a pointed link survives its look being written again', async () => {
  reduce(true);
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), {});
  hitOf(v).dispatch('pointerover');
  await v.draw(TREE, lay(), { selected: 's1', lit: LIT });
  const link = v.node('c1>s1');
  assert.ok(link.classList.contains('lit') && link.classList.contains('hov'));
  await v.draw(TREE, lay(), {});
  assert.ok(!link.classList.contains('lit') && link.classList.contains('hov'));
});

test('Enter or Space held down opens a link once; the key does not scroll the page', async () => {
  reduce(true); clicked.length = 0;
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), {});
  const h = hitOf(v);
  h.dispatch('keydown', { key: 'Enter' });
  assert.equal(clicked.length, 1);
  for (const key of ['Enter', ' ']) {
    const event = h.dispatch('keydown', { key, repeat: true });
    assert.equal(event.defaultPrevented, true, key);
  }
  assert.equal(clicked.length, 1);
  h.dispatch('keydown', { key: ' ' });
  assert.equal(clicked.length, 2);
});

test('the group of hits is hidden from a screen reader while it holds no hit', async () => {
  reduce(true);
  const v = view({ links: LINKS });
  const hidden = () => v.area.children.find((n) => n.getAttribute('aria-label') === 'Connections').getAttribute('aria-hidden');
  await v.draw(TREE, lay(), {});
  assert.equal(hidden(), null);
  const bare = { ...TREE, blocks: TREE.blocks.filter((b) => b.id !== 's1' && b.id !== 't1' && b.id !== 't2'), links: TREE.links.filter((l) => l.to === 's2') };
  await v.draw(bare, layoutTree(bare, { open: new Set(), narrow: false }), {});
  assert.equal(hitOf(v), undefined);
  assert.equal(hidden(), 'true');
  await v.draw(TREE, lay(), {});
  assert.equal(hidden(), null);
  // A page that acts on no link never shows the group.
  const none = view();
  await none.draw(TREE, lay(), {});
  assert.equal(none.area.children.find((n) => n.getAttribute('aria-label') === 'Connections').getAttribute('aria-hidden'), 'true');
});

const NO_LINK = { ...TREE, links: TREE.links.filter((l) => l.to !== 's2') };
const withLink = (fields) => ({ ...TREE, links: TREE.links.map((l) => (l.to === 's2' ? { ...l, ...fields } : l)) });
const drawn = (m) => layoutTree(m, { open: new Set(), narrow: false });

test('a new link between two blocks that stay draws from its start in 260 ms', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const v = view();
  await v.draw(NO_LINK, drawn(NO_LINK), { motion: 'none' });
  v.draw(TREE, drawn(TREE), {});
  const link = v.node('c1>s2'); const a = link.animations[0];
  assert.equal(link.getAttribute('pathLength'), '1');
  assert.deepEqual([a.keyframes, a.options.duration, a.options.easing], [[{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], 260, CALM]);
  t.mock.timers.tick(260); assert.equal(link.getAttribute('pathLength'), null); assert.equal(link.style.strokeDasharray, '');
});

test('in an Undo a link that comes back draws in over 480 ms; under reduced motion it shows at once', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const v = view();
  await v.draw(NO_LINK, drawn(NO_LINK), { motion: 'none' });
  v.draw(TREE, drawn(TREE), { motion: 'undo' });
  const link = v.node('c1>s2'); const a = link.animations[0];
  assert.deepEqual([a.keyframes, a.options.duration, a.options.easing], [[{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], 480, CALM]);
  t.mock.timers.tick(480); assert.equal(link.getAttribute('pathLength'), null);
  // The rest of an Undo's draw moves as any other: a block that goes fades out.
  v.draw(without('s2'), drawn(without('s2')), { motion: 'undo' });
  assert.ok(v.node('s2').classList.contains('leaving'));
  reduce(true);
  const calm = view();
  await calm.draw(NO_LINK, drawn(NO_LINK), { motion: 'none' });
  await calm.draw(TREE, drawn(TREE), { motion: 'undo' });
  assert.deepEqual([calm.node('c1>s2').animations.length, calm.node('c1>s2').style.opacity || ''], [0, '']);
});

test('a new preview link fades in over 300 ms', async () => {
  const v = view();
  await v.draw(NO_LINK, drawn(NO_LINK), { motion: 'none' });
  const m = withLink({ kind: 'preview' }); v.draw(m, drawn(m), {});
  const a = v.node('c1>s2').animations[0];
  assert.deepEqual([a.keyframes, a.options.duration, a.options.easing], [[{ opacity: 0 }, { opacity: 1 }], 300, CALM]);
});

test('a dashed link that goes fades out in 240 ms; a solid one draws back to its start in 380 ms', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  for (const [kind, keyframes, ms, ease] of [['preview', [{ opacity: 1 }, { opacity: 0 }], 240, 'ease-out'], ['on', [{ strokeDashoffset: 0 }, { strokeDashoffset: 1 }], 380, RETRACT]]) {
    const v = view(); const m = withLink({ kind });
    await v.draw(m, drawn(m), { motion: 'none' });
    const link = v.node('c1>s2');
    v.draw(NO_LINK, drawn(NO_LINK), {});
    const a = link.animations.at(-1);
    assert.deepEqual([a.keyframes, a.options.duration, a.options.easing, a.options.fill], [keyframes, ms, ease, 'forwards']);
    t.mock.timers.tick(ms); assert.equal(link.parentNode, null);
  }
});

test('a link that turns dashed blends in 300 ms, a solid line counting as "8 0"', async () => {
  const v = view();
  await v.draw(TREE, drawn(TREE), { motion: 'none' });
  const m = withLink({ leaving: true }); v.draw(m, drawn(m), {});
  const link = v.node('c1>s2'); const a = link.animations.at(-1);
  assert.ok(link.classList.contains('leaving'));
  assert.deepEqual(a.keyframes, [{ strokeDasharray: '8 0', strokeOpacity: '1' }, { strokeDasharray: '4 4', strokeOpacity: '0.4' }]);
  assert.deepEqual([a.options.duration, a.options.easing], [300, CALM]);
});

test('under reduced motion links come and go at once', async () => {
  reduce(true);
  const v = view();
  await v.draw(NO_LINK, drawn(NO_LINK), {});
  await v.draw(TREE, drawn(TREE), {});
  const link = v.node('c1>s2');
  assert.equal(link.animations.length, 0);
  await v.draw(NO_LINK, drawn(NO_LINK), {});
  assert.equal(link.parentNode, null);
});

// More cases.
test('a link that goes and comes back during its exit is shown again at once', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  for (const kind of ['preview', 'on']) {
    const v = view(); const m = withLink({ kind });
    await v.draw(m, drawn(m), { motion: 'none' });
    const link = v.node('c1>s2');
    v.draw(NO_LINK, drawn(NO_LINK), {});
    t.mock.timers.tick(100);
    v.draw(m, drawn(m), {});
    assert.equal(v.node('c1>s2'), link);
    assert.equal(link.getAnimations().length, 0);  // the exit is cancelled and no new motion runs
    assert.deepEqual([link.getAttribute('pathLength'), link.style.strokeDasharray, link.style.opacity], [null, '', '']);
    t.mock.timers.tick(1000);  // the old timer removes nothing
    assert.equal(v.node('c1>s2'), link); assert.ok(link.parentNode);
  }
});

test('a link that goes takes no pointer and its hit is gone at once; the link stays until it has gone', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const v = view({ links: { ...LINKS, canHit: (l) => l.to === 's2' } });
  await v.draw(TREE, drawn(TREE), { motion: 'none' });
  assert.ok(hitOf(v));
  v.draw(NO_LINK, drawn(NO_LINK), {});
  assert.equal(hitOf(v), undefined);
  assert.ok(v.node('c1>s2'));
  t.mock.timers.tick(380); assert.equal(v.node('c1>s2'), null);
});

test('a link whose block goes with it keeps fading with the block; no exit of its own runs', async () => {
  const v = view();
  await v.draw(TREE, drawn(TREE), { motion: 'none' });
  const link = v.node('c1>s2');
  v.draw(without('s2'), drawn(without('s2')), {});
  assert.equal(link.animations.length, 0);
  tick(180); assert.equal(link.parentNode, null);
});

test('the blend ends at the look the class gives, though a browser still reads the old opacity on the link itself', async () => {
  const real = globalThis.getComputedStyle; const reads = [];
  // A browser: while a node's transitions are on, its transition has just started and it reads the old look.
  globalThis.getComputedStyle = (node) => { reads.push([node, node.style.transition]); return node.style.transition === 'none' ? real(node) : { strokeDasharray: 'none', strokeOpacity: '1' }; };
  try {
    const v = view();
    await v.draw(TREE, drawn(TREE), { motion: 'none' });
    const link = v.node('c1>s2'); const svg = link.parentNode; const count = svg.children.length;
    const m = withLink({ leaving: true }); v.draw(m, drawn(m), {});
    assert.deepEqual(link.animations.at(-1).keyframes, [{ strokeDasharray: '8 0', strokeOpacity: '1' }, { strokeDasharray: '4 4', strokeOpacity: '0.4' }]);
    // The end look is read with transitions off, never on the link itself, which keeps its own.
    const off = reads.filter(([, transition]) => transition === 'none');
    assert.ok(off.length > 0 && off.every(([node]) => node !== link));
    assert.ok(!link.style.transition);
    assert.equal(svg.children.length, count);
  } finally { globalThis.getComputedStyle = real; }
});

test('the copy that gives the end look is taken away even when the read fails', async () => {
  const real = globalThis.getComputedStyle;
  globalThis.getComputedStyle = (node) => {
    if (node.style.transition === 'none') throw new Error('no style');
    return real(node);
  };
  try {
    const v = view();
    await v.draw(TREE, drawn(TREE), { motion: 'none' });
    const svg = v.node('c1>s2').parentNode; const count = svg.children.length;
    const m = withLink({ leaving: true });
    assert.throws(() => v.draw(m, drawn(m), {}), /no style/);
    assert.equal(svg.children.length, count);
  } finally { globalThis.getComputedStyle = real; }
});

test('a pointed link that goes takes its hover look and its × with it', async () => {
  const v = view({ links: { ...LINKS, canHit: (l) => l.to === 's2' } });
  await v.draw(TREE, drawn(TREE), { motion: 'none' });
  const link = v.node('c1>s2');
  hitOf(v).dispatch('pointerover');
  assert.ok(link.classList.contains('hov')); assert.equal(xOf(v).hidden, false);
  v.draw(NO_LINK, drawn(NO_LINK), {});
  assert.equal(xOf(v).hidden, true);
  assert.ok(!link.classList.contains('hov'));
  assert.equal(hitOf(v), undefined);
});

test('a link whose look changes without a new dash or opacity does not blend', async () => {
  const v = view();
  await v.draw(TREE, drawn(TREE), { motion: 'none' });
  v.draw(TREE, drawn(TREE), { lit: new Set(['c1>s2']) });
  assert.ok(v.node('c1>s2').classList.contains('lit'));
  assert.equal(v.node('c1>s2').animations.length, 0);
});

// A browser reads a link's dashes as they are now (an inline `stroke-dasharray` first) and dims a link
// that is off the path of a map with `.focus`.
async function inBrowser(run) {
  const real = globalThis.getComputedStyle;
  globalThis.getComputedStyle = (node) => {
    const base = real(node);
    let dim = false;
    for (let at = node.parentNode; at; at = at.parentNode) if (at.classList?.contains('focus')) dim = true;
    return { strokeDasharray: node.style.strokeDasharray || base.strokeDasharray, strokeOpacity: dim && !node.classList.contains('lit') ? '0.16' : base.strokeOpacity };
  };
  try { await run(); } finally { globalThis.getComputedStyle = real; }
}

test('a link that draws in does not blend when its look changes meanwhile', async () => {
  await inBrowser(async () => {
    const v = view();
    await v.draw(NO_LINK, drawn(NO_LINK), { motion: 'none' });
    v.draw(TREE, drawn(TREE), {});
    const link = v.node('c1>s2');
    assert.equal(link.style.strokeDasharray, '1');
    const m = withLink({ leaving: true }); v.draw(m, drawn(m), {});
    assert.ok(link.classList.contains('leaving'));
    assert.deepEqual(link.animations.map((a) => a.keyframes), [[{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }]]);
  });
});

test('a glance does not blend a link that draws back to its start', async () => {
  await inBrowser(async () => {
    const v = view();
    await v.draw(TREE, drawn(TREE), { motion: 'none' });
    const link = v.node('c1>s2');
    v.draw(NO_LINK, drawn(NO_LINK), {});
    const runs = link.animations.length;
    assert.equal(runs, 1);
    v.glance(new Set(['c1>s2']));
    assert.equal(link.animations.length, runs);
    assert.ok(!link.classList.contains('lit'), 'a link on its way out is left as it is');
  });
});

test('a link whose look changes when it is at rest still blends in a browser', async () => {
  await inBrowser(async () => {
    const v = view();
    await v.draw(TREE, drawn(TREE), { motion: 'none' });
    const m = withLink({ leaving: true }); v.draw(m, drawn(m), {});
    assert.equal(v.node('c1>s2').animations.length, 1);
  });
});

const LIT = new Set(['c1', 's1', 'c1>s1']);
const overs = (v) => walk(v.area).filter((n) => n.classList?.contains('link-over'));

test('a selection dims what is off its path and lays an overlay on each lit link', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(TREE, lay(), { selected: 's1', lit: LIT });
  assert.ok(v.box.classList.contains('focus'));
  assert.ok(v.node('s1').classList.contains('selected') && v.node('c1').classList.contains('lit') && !v.node('s2').classList.contains('lit'));
  assert.ok(v.node('c1>s1').classList.contains('lit'));
  const [o] = overs(v); const a = o.animations[0];
  assert.equal(overs(v).length, 1);
  assert.deepEqual([a.keyframes, a.options.duration, a.options.easing], [[{ opacity: 0 }, { opacity: 1 }], 180, CALM]);
});

test('a selection lays no overlay on a link that a change in preview takes out or adds', async () => {
  // The link keeps its dashed look, so the tray's change shows also on the selection's path.
  for (const fields of [{ leaving: true }, { kind: 'preview' }]) {
    const m = { ...TREE, links: TREE.links.map((l) => (l.to === 's1' ? { ...l, ...fields } : l)) };
    const v = view();
    await v.draw(m, drawn(m), { motion: 'none' });
    v.draw(m, drawn(m), { selected: 's1', lit: LIT });
    assert.ok(v.node('c1>s1').classList.contains('lit'));
    assert.equal(overs(v).length, 0, JSON.stringify(fields));
  }
});

test('a selected block with nothing lit dims nothing and lays no line; a later draw lights its path', async () => {
  // The page draws a press that opens a server this way, and lights the path when its tools are in.
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(TREE, lay(), { selected: 's1', lit: new Set() });
  assert.ok(v.node('s1').classList.contains('selected'));
  assert.ok(!v.box.classList.contains('focus') && !v.node('s2').classList.contains('lit'));
  assert.equal(overs(v).length, 0);
  v.draw(TREE, lay(), { selected: 's1', lit: LIT });
  assert.ok(v.box.classList.contains('focus') && v.node('s1').classList.contains('selected'));
  assert.equal(overs(v).length, 1);
});

test('letting go fades the overlays out in 160 ms, then removes them', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const v = view();
  await v.draw(TREE, lay(), { selected: 's1', lit: LIT, motion: 'none' });
  const [o] = overs(v);
  v.draw(TREE, lay(), {});
  assert.ok(!v.box.classList.contains('focus'));
  assert.deepEqual([o.animations.at(-1).keyframes, o.animations.at(-1).options.duration, o.animations.at(-1).options.easing], [[{ opacity: 1 }, { opacity: 0 }], 160, 'ease-in']);
  t.mock.timers.tick(160); assert.equal(o.parentNode, null);
});

test('a selected link is picked, keeps its ×, and lays no overlay', async () => {
  reduce(true);
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), { selected: 'c1>s1', lit: LIT });
  assert.ok(v.node('c1>s1').classList.contains('picked'));
  assert.equal(xOf(v).hidden, false);
  assert.equal(overs(v).length, 0);
});

test('a glance lights a path with no overlay, only while nothing is selected', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), {});
  v.glance(LIT); assert.ok(v.box.classList.contains('focus')); assert.equal(overs(v).length, 0);
  v.glance(null); assert.ok(!v.box.classList.contains('focus'));
  await v.draw(TREE, lay(), { selected: 's2', lit: new Set(['c1', 's2', 'c1>s2']) });
  v.glance(LIT); assert.ok(v.node('s2').classList.contains('lit') && !v.node('s1').classList.contains('lit'));
});

test('a click on empty map lets go; a click on a block or a link does not', async () => {
  reduce(true);
  let empty = 0;
  const v = view({ onEmpty: () => { empty += 1; }, links: LINKS });
  await v.draw(TREE, lay(), {});
  v.area.dispatch('click'); v.node('s1').dispatch('click'); hitOf(v).dispatch('click');
  assert.equal(empty, 1);
});

test('a click whose target the press has drawn away was on a block, not on empty map', async () => {
  reduce(true);
  let empty = 0;
  const v = view({ onEmpty: () => { empty += 1; }, onSelect: () => v.node('s1').replaceChildren() });
  await v.draw(TREE, lay(), {});
  v.node('s1').firstElementChild.dispatch('click');
  assert.equal(empty, 0);
});

test('a press that began on a block or a link is no click on empty map, wherever it ended', async () => {
  reduce(true);
  let empty = 0;
  const v = view({ onEmpty: () => { empty += 1; }, links: LINKS });
  await v.draw(TREE, lay(), {});
  v.node('s1').dispatch('pointerdown'); v.area.dispatch('click');
  hitOf(v).dispatch('pointerdown'); v.area.dispatch('click');
  assert.equal(empty, 0);
  v.area.dispatch('pointerdown'); v.area.dispatch('click');
  assert.equal(empty, 1);
});

test('the page hears which block the pointer is on, and null when it leaves the map', async () => {
  reduce(true);
  const heard = [];
  const v = view({ onHover: (id) => heard.push(id) });
  await v.draw(TREE, lay(), {});
  v.node('s1').dispatch('pointerover'); v.node('s1').firstElementChild.dispatch('pointerover'); v.box.dispatch('pointerleave');
  v.hold('s2', { x: 0, y: 0 }); v.node('s2').dispatch('pointerover');
  assert.deepEqual(heard, ['s1', null]);
});

test('an overlay is made once per lit link, follows it, and sits over every link', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(TREE, lay(), { selected: 's1', lit: LIT });
  const [o] = overs(v);
  v.draw(TREE, lay(), { selected: 's1', lit: LIT });
  assert.deepEqual(overs(v), [o]);
  assert.equal(o.animations.length, 1);
  assert.equal(o.getAttribute('d'), v.node('c1>s1').getAttribute('d'));
  const svg = v.node('c1>s1').parentNode;
  assert.ok(svg.children.indexOf(o.parentNode) > svg.children.indexOf(v.node('c1>s1')));
  v.draw(TREE, lay(['s1']), { selected: 's1', lit: LIT });
  tick(130); settle();
  assert.equal(o.getAttribute('d'), v.node('c1>s1').getAttribute('d'));
});

test('a bypass line gets no overlay, and lit links go last, under the overlays', async () => {
  reduce(true);
  const m = { ...TREE, links: TREE.links.map((l) => (l.to === 's2' ? { ...l, kind: 'direct' } : l)) };
  const v = view();
  await v.draw(m, layoutTree(m, { open: new Set(['s1']), narrow: false }), { selected: 's1', lit: new Set(['c1', 's1', 's2', 'c1>s1', 'c1>s2']) });
  assert.equal(overs(v).length, 1);
  const svg = v.node('c1>s1').parentNode;
  const last = svg.children.slice(-3);
  assert.ok([v.node('c1>s1'), v.node('c1>s2'), overs(v)[0].parentNode].every((n, i) => last[i] === n));
});

test('under reduced motion an overlay shows and goes at once', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), { selected: 's1', lit: LIT });
  const [o] = overs(v);
  assert.equal(o.animations.length, 0);
  await v.draw(TREE, lay(), {});
  assert.equal(o.parentNode, null);
});

test('a path that is lit again during its overlay\'s exit shows whole at once', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const v = view();
  await v.draw(TREE, lay(), { selected: 's1', lit: LIT, motion: 'none' });
  const [o] = overs(v);
  v.draw(TREE, lay(), {});
  t.mock.timers.tick(100);
  v.draw(TREE, lay(), { selected: 's1', lit: LIT });
  assert.ok(o.animations.every((a) => a.cancelled || a === o.animations[0]));
  t.mock.timers.tick(200);
  assert.deepEqual(overs(v), [o]);
});

test('a selection ends a glance; so does the start of a drag', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), {});
  v.glance(LIT);
  await v.draw(TREE, lay(), { selected: 's2', lit: new Set(['c1', 's2', 'c1>s2']) });
  await v.draw(TREE, lay(), {});
  assert.ok(!v.box.classList.contains('focus'));
  v.glance(LIT); assert.ok(v.node('s1').classList.contains('lit'));
  await v.draw(TREE, lay(), {});
  assert.ok(v.box.classList.contains('focus'), 'a draw with no selection keeps a glance');
  v.hold('s2', { x: 0, y: 0 });
  assert.ok(!v.box.classList.contains('focus') && !v.node('s1').classList.contains('lit'));
});

test('the × goes back to the picked link when the pointer leaves another link', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  reduce(true);
  const v = view({ links: { ...LINKS, canHit: () => true } });
  await v.draw(TREE, lay(), { selected: 'c1>s1', lit: LIT });
  const [a, b] = walk(v.area).filter((n) => n.classList?.contains('hit'));
  const x = xOf(v);
  b.dispatch('pointerover');
  assert.equal(x.getAttribute('aria-label'), 'Remove s2');
  b.dispatch('pointerout'); t.mock.timers.tick(240);
  assert.deepEqual([x.hidden, x.getAttribute('aria-label')], [false, 'Remove s1']);
  assert.ok(a.parentNode && v.node('c1>s1').classList.contains('picked') && !v.node('c1>s2').classList.contains('hov'));
  await v.draw(TREE, lay(), {});
  assert.ok(x.hidden && !v.node('c1>s1').classList.contains('picked'));
});

test('the overlay of a link that draws in as a block unfolds waits until the block it leads to is in', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(TREE, lay(['s1']), { selected: 's1', lit: new Set(['c1', 's1', 't1', 'c1>s1', 's1>t1']) });
  assert.deepEqual(overs(v).map((o) => o.animations[0].options.delay), [0, 305]);
});

test('a hidden page shows an overlay at once, with no fade', async () => {
  globalThis.document.hidden = true;
  const v = view();
  await v.draw(TREE, lay(), { selected: 's1', lit: LIT });
  const [o] = overs(v);
  assert.ok(o);
  assert.equal(o.animations.length, 0);
});

// The parts of a block, by class.
const parts = (node, name) => walk(node).filter((n) => n.classList?.contains(name));
const part = (node, name) => parts(node, name)[0];
const LOOKS = {
  columns: TREE.columns,
  blocks: [
    { id: 'c1', column: 'a', kind: 'client', name: 'Codex', meta: 'Connected', lamp: 'on', state: 'on', ports: { right: true } },
    { id: 's1', column: 'b', kind: 'held', name: 'github', meta: '1 of 2 on', lamp: 'on', state: 'on', count: 2, ports: { left: true, right: true } },
    { id: 'o1', column: 'b', kind: 'outside', name: 'docs', meta: 'In Codex', lamp: 'out', state: 'on', ports: { left: 'out' } },
    { id: 't1', column: 'c', parent: 's1', kind: 'tool', name: 'read', lamp: 'on', state: 'on', projects: { words: '2 projects', said: 'own rule in 2 projects', own: false }, ports: { left: true } },
    { id: 't2', column: 'c', parent: 's1', kind: 'tool', name: 'push', lamp: 'off', state: 'off', projects: { words: 'This project', said: 'own rule in this project', own: true }, ports: { left: true } },
  ],
  links: [{ from: 'c1', to: 's1', kind: 'on' }, { from: 's1', to: 't1', kind: 'on' }],
};
const looks = (open = []) => layoutTree(LOOKS, { open: new Set(open), narrow: false });

test("a block draws its ports, and a server's right port shows only while open", async () => {
  reduce(true);
  const v = view();
  await v.draw(LOOKS, looks(), {});
  const ports = (id) => parts(v.node(id), 'port').map((n) => [n.className, n.getAttribute('aria-hidden')]);
  assert.deepEqual([ports('c1'), ports('s1'), ports('o1')], [[['port r', 'true']], [['port l', 'true'], ['port r', 'true']], [['port l out', 'true']]]);
  // Opening the server draws none of its parts again: its right port and its count only change
  // their look by its aria-expanded (style.css), so they can fade.
  const [right, count] = [parts(v.node('s1'), 'port')[1], part(v.node('s1'), 'block-count')];
  assert.deepEqual([v.node('s1').getAttribute('aria-expanded'), count.textContent], ['false', '2']);
  await v.draw(LOOKS, looks(['s1']), { open: new Set(['s1']) });
  assert.equal(v.node('s1').getAttribute('aria-expanded'), 'true');
  assert.deepEqual([parts(v.node('s1'), 'port')[1], part(v.node('s1'), 'block-count')], [right, count]);
  // A tool: its round mark, its name, which projects have a rule of their own (a folder, in the
  // accent for this project), and its port on the left. It has no meta line.
  const tool = (id) => v.node(id).children.map((n) => n.className);
  assert.deepEqual(tool('t1'), ['mark on', 'block-text', 'block-projects', 'port l']);
  assert.deepEqual(tool('t2'), ['mark', 'block-text', 'block-projects own', 'port l']);
  const tag = part(v.node('t1'), 'block-projects');
  assert.deepEqual([tag.children[0].dataset.icon, tag.children[0].getAttribute('width'), tag.children[1].textContent], ['folder', '11', '2 projects']);
  // Any other block has its lamp at the start of its meta line.
  assert.deepEqual(['c1', 's1', 'o1'].map((id) => part(v.node(id), 'block-meta').children[0].className), ['lamp on', 'lamp on', 'lamp out']);
});

test('a preview block has its × badge and its take-out title', async () => {
  reduce(true);
  const words = 'In preview. Click to take it out.';
  const model = { columns: TREE.columns, links: [], blocks: [
    { id: 'p1', column: 'b', kind: 'preview', name: 'github', meta: 'Preview', lamp: 'preview', state: 'preview', takeOut: words, ports: { left: true } },
    { id: 's2', column: 'b', kind: 'held', name: 'files', meta: '0 of 1 on', lamp: 'off', state: 'on' },
  ] };
  const v = view();
  await v.draw(model, layoutTree(model, { open: new Set(), narrow: false }), {});
  const node = v.node('p1');
  assert.equal(node.title, words);
  const cross = part(node, 'block-x');
  assert.equal(cross.getAttribute('aria-hidden'), 'true');
  assert.deepEqual([cross.children[0].dataset.icon, cross.children[0].getAttribute('width')], ['x', '11']);
  assert.equal(part(node, 'lamp').className, 'lamp pv');
  // Any other block has no × and its own name as its title.
  assert.equal(part(v.node('s2'), 'block-x'), undefined);
  assert.equal(v.node('s2').title, 'files');
});

test('a leaving block is dimmed, dashed and out of the Tab order', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  const node = v.node('s2');
  v.draw(without('s2'), layoutTree(without('s2'), { open: new Set(), narrow: false }), {});
  // While it fades out it has the leaving look (style.css) and no Tab stop.
  tick(90);
  assert.ok(node.classList.contains('leaving'));
  assert.equal(node.getAttribute('tabindex'), '-1');
  // Drawn again before it has gone, it is a block like any other.
  v.draw(TREE, lay(), {}); settle();
  assert.equal(v.node('s2'), node);
  assert.deepEqual([node.classList.contains('leaving'), node.getAttribute('tabindex')], [false, null]);
  // A block whose removal waits in the tray has the same look, and stays a Tab stop: a press still
  // opens its Details.
  const removing = { ...TREE, blocks: TREE.blocks.map((b) => (b.id === 's2' ? { ...b, leaving: true } : b)) };
  v.draw(removing, lay(), {}); settle();
  assert.deepEqual([node.classList.contains('leaving'), node.getAttribute('tabindex')], [true, null]);
});

test('the tools of a server that folds shrink back with no leaving look, and no Tab stop', async () => {
  const v = view();
  await v.draw(TREE, lay(['s1']), { motion: 'none' });
  const t1 = v.node('t1');
  v.draw(TREE, lay(), {});
  tick(90);
  assert.deepEqual([t1.classList.contains('leaving'), t1.getAttribute('tabindex')], [false, '-1']);
  settle();
  assert.equal(v.node('t1'), null);
});

test("the gateway's numbers roll when they change", async () => {
  const gate = (clients, servers, on) => ({ columns: TREE.columns, links: [], blocks: [
    { id: 'g1', column: 'a', kind: 'gateway', name: 'Kitden gateway', meta: 'On this Mac', lamp: 'on', stats: [{ icon: 'monitor', words: clients }, { icon: 'server', words: servers }] },
    { id: 's1', column: 'b', kind: 'held', name: 'github', meta: on, lamp: 'on', state: 'on' },
  ] });
  const v = view();
  const show = (m, motion) => v.draw(m, layoutTree(m, { open: new Set(), narrow: false }), { motion });
  const nums = () => [...parts(v.node('g1'), 'num'), ...parts(v.node('s1'), 'num')];
  const shown = () => nums().map((n) => n.children.map((c) => c.textContent));
  // The first draw shows the numbers as they are; the words after each number stay as they are.
  await show(gate('2 clients', '3 servers', '1 of 4 on'), 'none');
  assert.deepEqual(shown(), [['2'], ['3'], ['1']]);
  assert.ok(nums().every((n) => n.children.every((c) => !c.animations.length)));
  const stats = parts(v.node('g1'), 'block-stat').map((s) => [s.children[0].dataset.icon, s.children[0].getAttribute('width'), s.children[1].children[1].textContent]);
  assert.deepEqual(stats, [['monitor', '12', ' clients'], ['server', '12', ' servers']]);
  // A number that changed rolls from the old one: a bigger one goes up, a smaller one down. One
  // that did not change stays.
  await show(gate('3 clients', '3 servers', '0 of 4 on'));
  assert.deepEqual(shown(), [['2', '3'], ['3'], ['1', '0']]);
  const [old, next] = nums()[0].children;
  assert.deepEqual([old.animations[0].keyframes[1], old.animations[0].options.duration], [{ transform: 'translateY(-70%)', opacity: 0 }, 140]);
  assert.deepEqual([next.animations[0].options.duration, next.animations[0].options.delay], [200, 140]);
  assert.deepEqual(nums()[2].children[0].animations[0].keyframes[1], { transform: 'translateY(70%)', opacity: 0 });
  assert.ok(!nums()[1].children[0].animations.length);
  // Under reduced motion each is set at once.
  reduce(true);
  await show(gate('1 client', '1 server', '2 of 4 on'));
  assert.deepEqual(shown(), [['1'], ['1'], ['2']]);
});

test('a count rolls only from its own old value, when another count comes or goes before it', async () => {
  const gate = (stats) => ({ columns: TREE.columns, links: [], blocks: [{ id: 'g1', column: 'a', kind: 'gateway', name: 'Kitden gateway', meta: 'On this Mac', lamp: 'on', stats }] });
  const servers = { icon: 'server', words: '2 servers' };
  const v = view();
  const show = (m, motion) => v.draw(m, layoutTree(m, { open: new Set(), narrow: false }), { motion });
  // The setup is read later: the clients' count comes before the servers' one.
  await show(gate([servers]), 'none');
  await show(gate([{ icon: 'monitor', words: '3 clients' }, servers]));
  const nums = parts(v.node('g1'), 'num');
  assert.deepEqual(nums.map((n) => n.children.map((c) => c.textContent)), [['3'], ['2']]);
  assert.ok(nums.every((n) => n.children.every((c) => !c.animations.length)));
});

test("a tool's pending tag pops in when it comes, grows or names another project, not when it shrinks or goes", async () => {
  const as = (projects) => ({ ...LOOKS, blocks: LOOKS.blocks.map((b) => (b.id === 't1' ? { ...b, projects } : b)) });
  const usual = { words: '2 projects', said: 'own rule in 2 projects', own: false };
  const pending = (words, n) => ({ words, said: `in preview for ${words}`, own: true, pending: n });
  const v = view();
  const tag = () => part(v.node('t1'), 'block-projects');
  const pops = () => tag().animations.map((a) => [a.keyframes, a.options.duration, a.options.easing]);
  const pop = [[{ opacity: 0, transform: 'scale(0.7)' }, { opacity: 1, transform: 'none' }], 180, CALM];
  const open = { open: new Set(['s1']) };
  await v.draw(as(usual), looks(['s1']), { ...open, motion: 'none' });
  assert.deepEqual([tag().className, pops()], ['block-projects', []]);
  await v.draw(as(pending('atlas', 1)), looks(['s1']), open);
  assert.deepEqual([tag().className, pops()], ['block-projects own pend', [pop]]);
  await v.draw(as(pending('2 projects', 2)), looks(['s1']), open);
  assert.deepEqual(pops(), [pop]);
  await v.draw(as(pending('atlas', 1)), looks(['s1']), open);
  assert.deepEqual(pops(), []);
  // Another project at the same count pops too.
  await v.draw(as(pending('website', 1)), looks(['s1']), open);
  assert.deepEqual(pops(), [pop]);
  await v.draw(as(usual), looks(['s1']), open);
  assert.deepEqual([tag().className, pops()], ['block-projects', []]);
  // Under reduced motion it shows at once.
  reduce(true);
  await v.draw(as(pending('atlas', 1)), looks(['s1']), open);
  assert.deepEqual([tag().className, pops()], ['block-projects own pend', []]);
  await v.draw(as(pending('website', 1)), looks(['s1']), open);
  assert.deepEqual(pops(), []);
});

test('a lamp fades to its new colour, and pops when it turns on or off', async () => {
  const as = (lamp) => ({ ...TREE, blocks: TREE.blocks.map((b) => (b.id === 's2' ? { ...b, meta: 'Local', lamp } : b)) });
  const v = view();
  const lampOf = () => part(v.node('s2'), 'lamp');
  // Its colours as style.css gives them, read from its look; a client's lamp pops from 2.4.
  const COLOURS = { 'lamp on': 'green', lamp: 'grey', 'lamp pv': 'clear' };
  const style = globalThis.getComputedStyle;
  globalThis.getComputedStyle = (node) => (node.classList.contains('lamp') ? { backgroundColor: COLOURS[node.className], getPropertyValue: (name) => (name === '--pop' ? ' 2.4' : '') } : style(node));
  const moves = () => lampOf().animations.map((a) => [a.keyframes, a.options.duration, a.options.easing]);
  const fade = (from, to) => [[{ backgroundColor: from }, { backgroundColor: to }], 400, 'ease'];
  const pop = [[{ transform: 'scale(2.4)' }, { transform: 'none' }], 200, CALM];
  try {
    await v.draw(as('on'), lay(), { motion: 'none' });
    assert.deepEqual([lampOf().className, moves()], ['lamp on', []]);
    await v.draw(as('off'), lay(), {});
    assert.deepEqual([lampOf().className, moves()], ['lamp', [fade('green', 'grey'), pop]]);
    // A preview ring does not pop; nor does going back to the state it had before its preview (a
    // row taken out). Turning the other way after a preview does.
    await v.draw(as('preview'), lay(), {});
    assert.deepEqual([lampOf().className, moves()], ['lamp pv', [fade('grey', 'clear')]]);
    await v.draw(as('off'), lay(), {});
    assert.deepEqual(moves(), [fade('clear', 'grey')]);
    await v.draw(as('preview'), lay(), {});
    await v.draw(as('on'), lay(), {});
    assert.deepEqual([lampOf().className, moves()], ['lamp on', [fade('clear', 'green'), pop]]);
    // Under reduced motion it changes at once.
    reduce(true);
    await v.draw(as('off'), lay(), {});
    assert.deepEqual([lampOf().className, moves()], ['lamp', []]);
  } finally {
    globalThis.getComputedStyle = style;
  }
});
