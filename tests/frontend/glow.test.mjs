import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';

// Reduced motion is flipped per test, like a live MediaQueryList.
const motionQuery = { matches: false, listeners: [], addEventListener(type, fn) { this.listeners.push(fn); } };
const schemeQuery = { matches: true, listeners: [], addEventListener(type, fn) { this.listeners.push(fn); } };
globalThis.matchMedia = (query) => (/reduced-motion/.test(query) ? motionQuery : schemeQuery);
globalThis.devicePixelRatio = 2;

// Frames run only when the test ticks them: the dots must not ask for one at rest.
let frames = [];
globalThis.requestAnimationFrame = (fn) => frames.push(fn);
const tick = () => {
  const run = frames;
  frames = [];
  for (const fn of run) fn(0);
};
const settle = () => { for (let i = 0; i < 500 && frames.length; i += 1) tick(); };

// The page's glow colour: R G B numbers, per theme.
const theme = { glow: ' 240 154 124' };
globalThis.getComputedStyle = () => ({ getPropertyValue: (name) => (name === '--glow' ? theme.glow : '') });
const observers = [];
globalThis.MutationObserver = class { constructor(fn) { this.fn = fn; observers.push(this); } observe(target, options) { this.target = target; this.options = options; } };
const resizers = [];
globalThis.ResizeObserver = class { constructor(fn) { this.fn = fn; this.seen = []; resizers.push(this); } observe(node) { this.seen.push(node); } };
globalThis.document = { documentElement: { dataset: {} } };

const { startGlow } = await import('../../src/kitden/web/static/js/glow.js');

// A canvas whose 2D context records every dot: where, how big, and the colour at the moment of fill.
function fakeCanvas() {
  const drawn = [];
  const ctx = {
    clears: 0, transform: null, fillStyle: '',
    setTransform(...args) { this.transform = args; },
    clearRect() { this.clears += 1; drawn.length = 0; },
    beginPath() {},
    arc(x, y, r) { this.at = { x, y, r }; },
    fill() { drawn.push({ ...this.at, style: this.fillStyle }); },
  };
  return {
    drawn, ctx, width: 0, height: 0,
    style: { setProperty(name, value) { this[name] = String(value); } },
    getContext: () => ctx,
    getBoundingClientRect: () => ({ left: 200, top: 66, width: 800, height: 600 }),
  };
}

let column;
let canvas;
let topbar;
let listeners;
beforeEach(() => {
  frames = [];
  observers.length = 0;
  resizers.length = 0;
  motionQuery.matches = false;
  motionQuery.listeners = [];
  schemeQuery.listeners = [];
  theme.glow = ' 240 154 124';
  canvas = fakeCanvas();
  topbar = { offsetHeight: 66 };
  listeners = {};
  column = {
    clientWidth: 800, clientHeight: 666,
    addEventListener(type, fn) { listeners[type] = fn; },
    querySelector: (selector) => ({ '#dots': canvas, '.topbar': topbar })[selector] || null,
  };
});

// A pointer at a place in the canvas (the canvas sits at 200, 66 in the window), over `target`.
const move = (x, y, target = { closest: () => null }) => listeners.pointermove({ clientX: x + 200, clientY: y + 66, target });
// The last frame's dots: alpha of each fill.
const alpha = (dot) => Number(dot.style.match(/\/ ([\d.]+)\)/)[1]);

test('the canvas follows the column: device pixels, below the top bar', () => {
  startGlow(column);
  assert.equal(canvas.width, 1600);
  assert.equal(canvas.height, 1200);
  assert.deepEqual(canvas.ctx.transform, [2, 0, 0, 2, 0, 0]);
  assert.equal(canvas.style['--glow-top'], '66px');
  assert.equal(canvas.style['--glow-h'], '600px');
  // The column and the top bar are watched: a new size draws the canvas again.
  assert.deepEqual(resizers[0].seen, [column, topbar]);
  column.clientWidth = 500;
  column.clientHeight = 566;
  resizers[0].fn();
  assert.equal(canvas.width, 1000);
  assert.equal(canvas.style['--glow-h'], '500px');
});

test('nothing is asked for, and nothing drawn, before the pointer moves', () => {
  startGlow(column);
  assert.equal(frames.length, 0);
  assert.equal(canvas.drawn.length, 0);
});

test('the dots draw only near the pointer and stop when it rests', () => {
  startGlow(column);
  // The pointer sits exactly on the dot at grid 5, 5 (11 + 5 * 22 = 121).
  move(121, 121);
  assert.equal(frames.length, 1);
  tick();
  assert.ok(canvas.drawn.length > 20, 'a circle of dots');
  for (const dot of canvas.drawn) assert.ok(Math.hypot(dot.x - 121, dot.y - 121) <= 130 + 5, 'within 130 px');
  // On the pointer: f = 1, radius 2.3, no push, colour at f squared x .55 x the ease (16 % on frame one).
  const centre = canvas.drawn.find((dot) => dot.x === 121 && dot.y === 121);
  assert.equal(centre.r.toFixed(3), '2.300');
  assert.equal(centre.style, 'rgb(240 154 124 / 0.088)');
  // One step right (22 px): f = 1 - 22 / 130, radius .8 + 1.5 f, pushed out f squared x 5 px.
  const f = 1 - 22 / 130;
  const right = canvas.drawn.find((dot) => Math.abs(dot.y - 121) < 1e-9 && dot.x > 143);
  assert.ok(Math.abs(right.r - (0.8 + 1.5 * f)) < 1e-9);
  assert.ok(Math.abs(right.x - (143 + f * f * 5)) < 1e-9);
  assert.equal(alpha(right), Number((f * f * 0.55 * 0.16).toFixed(3)));
  // No dot beyond 130 px, and the far corner stays empty.
  assert.ok(!canvas.drawn.some((dot) => dot.x > 121 + 135));
  // The dots ease in, and when the pointer rests the frames stop by themselves.
  settle();
  assert.equal(frames.length, 0);
  const centred = canvas.drawn.find((dot) => dot.x === 121 && dot.y === 121);
  assert.ok(alpha(centred) > 0.5 && alpha(centred) <= 0.55);
  const clears = canvas.ctx.clears;
  tick();
  assert.equal(canvas.ctx.clears, clears, 'no frame at rest');
});

test('a moving pointer keeps the frames coming and the dots follow it', () => {
  startGlow(column);
  move(121, 121);
  settle();
  move(341, 121);
  assert.equal(frames.length, 1);
  tick();
  assert.ok(canvas.drawn.some((dot) => dot.x === 341 && dot.y === 121));
  assert.ok(!canvas.drawn.some((dot) => dot.x < 341 - 135));
  settle();
  assert.equal(frames.length, 0);
});

test('the dots ease out when the pointer leaves', () => {
  startGlow(column);
  move(121, 121);
  settle();
  const strong = alpha(canvas.drawn.find((dot) => dot.x === 121 && dot.y === 121));
  listeners.pointerleave();
  assert.equal(frames.length, 1);
  tick();
  const next = alpha(canvas.drawn.find((dot) => dot.x === 121 && dot.y === 121));
  assert.ok(next < strong && next > strong * 0.8, 'a step of 16 %');
  settle();
  assert.equal(canvas.drawn.length, 0, 'cleared at the end');
  assert.equal(frames.length, 0);
  // A pointer that was never there asks for nothing.
  const clears = canvas.ctx.clears;
  listeners.pointerleave();
  assert.equal(frames.length, 0);
  assert.equal(canvas.ctx.clears, clears);
});

test('nothing draws under reduced motion', () => {
  motionQuery.matches = true;
  startGlow(column);
  move(121, 121);
  assert.equal(frames.length, 0);
  assert.equal(canvas.drawn.length, 0);
  // A setting turned on while the dots show clears them at the next frame and stops.
  motionQuery.matches = false;
  move(121, 121);
  settle();
  assert.ok(canvas.drawn.length > 0);
  motionQuery.matches = true;
  motionQuery.listeners.forEach((fn) => fn());
  assert.equal(frames.length, 1);
  tick();
  assert.equal(canvas.drawn.length, 0);
  assert.equal(frames.length, 0);
});

test('a theme switch repaints the dots in the new colour', () => {
  startGlow(column);
  move(121, 121);
  settle();
  assert.ok(canvas.drawn.every((dot) => dot.style.startsWith('rgb(240 154 124 /')));
  const watch = observers[0];
  assert.equal(watch.target, globalThis.document.documentElement);
  assert.deepEqual(watch.options, { attributes: true, attributeFilter: ['data-theme'] });
  theme.glow = ' 196 84 50';
  watch.fn();
  assert.ok(canvas.drawn.length > 20);
  assert.ok(canvas.drawn.every((dot) => dot.style.startsWith('rgb(196 84 50 /')));
  assert.equal(frames.length, 0, 'a repaint is one paint, not a loop');
  // The system theme counts too, while the page follows it.
  theme.glow = ' 240 154 124';
  schemeQuery.listeners.forEach((fn) => fn());
  assert.ok(canvas.drawn.every((dot) => dot.style.startsWith('rgb(240 154 124 /')));
});

// A block or card with a rect; the column's "closest" finds it for a pointer over it.
function fakeBlock() {
  return {
    selector: null,
    style: { setProperty(name, value) { this[name] = String(value); } },
    getBoundingClientRect: () => ({ left: 300, top: 150, width: 170, height: 60 }),
  };
}

test('the spotlight follows the pointer on a block and is off under reduced motion', () => {
  startGlow(column);
  const block = fakeBlock();
  const over = { closest: (selector) => { block.selector = selector; return block; } };
  move(150, 100, over);
  // Window point (350, 166) inside a block at (300, 150).
  assert.equal(block.style['--mx'], '50px');
  assert.equal(block.style['--my'], '16px');
  // Only map blocks and Overview cards take it.
  assert.match(block.selector, /div\.map \.block/);
  assert.match(block.selector, /\[data-place="overview"\]/);
  assert.doesNotMatch(block.selector, /^\.card$/);
  // Elsewhere on the page: nothing is set, and the dots still follow.
  const other = fakeBlock();
  move(160, 100, { closest: () => null });
  assert.equal(other.style['--mx'], undefined);
  assert.equal(frames.length, 1);
  // Off under reduced motion: no value is set.
  motionQuery.matches = true;
  const quiet = fakeBlock();
  move(150, 100, { closest: () => quiet });
  assert.equal(quiet.style['--mx'], undefined);
});

test('an empty read of the glow colour keeps the last good one', () => {
  startGlow(column);
  move(121, 121);
  settle();
  theme.glow = '';
  observers[0].fn();
  assert.ok(canvas.drawn.length > 20);
  assert.ok(canvas.drawn.every((dot) => dot.style.startsWith('rgb(240 154 124 /')));
});

test('a new pixel ratio sizes the canvas again when the pointer next moves', () => {
  startGlow(column);
  assert.equal(canvas.width, 1600);
  globalThis.devicePixelRatio = 1;
  try {
    move(121, 121);
    assert.equal(canvas.width, 800);
    assert.equal(canvas.height, 600);
    assert.deepEqual(canvas.ctx.transform, [1, 0, 0, 1, 0, 0]);
    tick();
    assert.ok(canvas.drawn.length > 20);
    // The same ratio again is no new size.
    canvas.width = 1;
    settle();
    move(130, 121);
    assert.equal(canvas.width, 1);
  } finally {
    globalThis.devicePixelRatio = 2;
  }
});
