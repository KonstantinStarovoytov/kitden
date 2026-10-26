import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { afterEach, test } from 'node:test';

const classes = new Set();
const transitions = [];
// One object for every matchMedia call: reduce(flag) flips it, like a live MediaQueryList.
const motionQuery = { matches: false };
globalThis.matchMedia = () => motionQuery;
const reduce = (flag) => { motionQuery.matches = flag; };
afterEach(() => reduce(false));
function fakeNode() {
  return {
    style: { opacity: '', transform: '' },
    textContent: '',
    animations: [],
    removed: false,
    animate(keyframes, options) {
      this.animations.push({ keyframes, options });
      return { finished: Promise.resolve() };
    },
    remove() { this.removed = true; },
  };
}
globalThis.document = {
  hidden: false,
  createElement: () => fakeNode(),
  documentElement: { classList: {
    add: (name) => classes.add(name),
    remove: (name) => classes.delete(name),
  } },
  startViewTransition(change) {
    change();
    let finish;
    const transition = {
      ready: Promise.resolve(),
      finished: new Promise((resolve) => { finish = resolve; }),
      skipped: false,
      skipTransition() { this.skipped = true; finish(); },
    };
    transitions.push(transition);
    return transition;
  },
};
const { transition, finishTransition } = await import('../../src/kitden/web/static/js/motion.js');

test('opening a drawer drops the snapshot and theme class', async () => {
  let changed = false;
  transition(() => { changed = true; }, 'theme-switch');
  finishTransition();
  await Promise.resolve();
  assert.equal(changed, true);
  assert.equal(transitions.at(-1).skipped, true);
  assert.equal(classes.has('theme-switch'), false);
});

test('an interrupted transition cannot remove the new transition class', async () => {
  const old = transition(() => {}, 'theme-switch');
  const next = transition(() => {}, 'theme-switch');
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(old.skipped, true);
  assert.equal(next.skipped, false);
  assert.equal(classes.has('theme-switch'), true);
  finishTransition();
});

const { fly, land } = await import('../../src/kitden/web/static/js/motion.js');

test('a tile named before a place change lands on its twin, then the name is cleared', async () => {
  const from = { style: {} };
  const to = { style: {} };
  fly(from, 'client-codex');
  assert.equal(from.style.viewTransitionName, 'client-codex');
  transition(() => land(to, 'client-codex'));
  assert.equal(to.style.viewTransitionName, 'client-codex');
  finishTransition();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(to.style.viewTransitionName, '');
});

test('a flight is used once: the next place change does not name a twin', () => {
  const from = { style: {} };
  const late = { style: {} };
  fly(from, 'client-cursor');
  transition(() => {});
  land(late, 'client-cursor');
  assert.equal(late.style.viewTransitionName, undefined);
  finishTransition();
});

test('land() ignores a tile with another name', () => {
  const other = { style: {} };
  fly({ style: {} }, 'client-codex');
  land(other, 'client-cursor');
  assert.equal(other.style.viewTransitionName, undefined);
  transition(() => {});
  finishTransition();
});

const { diffCounts } = await import('../../src/kitden/web/static/js/parts.js');

test('the diff count skips the header lines', () => {
  const diff = '--- before\n+++ after\n@@ -1,3 +1,3 @@\n   "a": {\n-  "x": true\n+  "x": false\n+  "y": 1\n   }';
  assert.deepEqual(diffCounts(diff), { added: 2, removed: 1 });
  assert.deepEqual(diffCounts(''), { added: 0, removed: 0 });
});

const motion = await import('../../src/kitden/web/static/js/motion.js');
const { D, animateTo, rise, riseHead, rollTo, glide, shake, CALM, OUT3, IN3, DRAW, RETRACT } = motion;

test('the curves have the mockup values', () => {
  assert.equal(CALM, 'cubic-bezier(.2,.8,.2,1)');
  assert.equal(DRAW, 'cubic-bezier(.3,.7,.2,1)');
  assert.equal(RETRACT, 'cubic-bezier(.4,0,.2,1)');
  assert.equal(OUT3(0), 0);
  assert.equal(OUT3(1), 1);
  assert.equal(OUT3(0.5), 0.875);
  assert.equal(IN3(0), 0);
  assert.equal(IN3(1), 1);
  assert.equal(IN3(0.5), 0.125);
});

test('D is zero under reduced motion', () => {
  reduce(true);
  assert.equal(D(300), 0);
  reduce(false);
  assert.equal(D(300), 300);
});

test('D scales by ?slow= and ignores a value that is not a positive number', async () => {
  const slowD = async (search) => {
    globalThis.location = { search };
    try { return (await import(`../../src/kitden/web/static/js/motion.js?${search}`)).D; }
    finally { delete globalThis.location; }
  };
  assert.equal((await slowD('?slow=2'))(100), 200);
  assert.equal((await slowD('?a=1&slow=0.5'))(100), 50);
  for (const bad of ['?slow=0', '?slow=-2', '?slow=abc', '?slow=', '?slow=Infinity', '?other=3']) {
    assert.equal((await slowD(bad))(100), 100, bad);
  }
});

test('unscaled gives back the ms that D scales to a real time, so a delay is scaled once', async () => {
  const slow = async (search) => {
    globalThis.location = { search };
    try { return await import(`../../src/kitden/web/static/js/motion.js?${search}`); }
    finally { delete globalThis.location; }
  };
  const two = await slow('?slow=2');
  assert.equal(two.unscaled(300), 150);
  assert.equal(two.D(two.unscaled(300)), 300);
  assert.equal((await slow('?slow=0.5')).unscaled(100), 200);
  assert.equal(motion.unscaled(100), 100);
  reduce(true);
  assert.equal(motion.unscaled(100), 0);
});

test('animateTo resolves at once under reduced motion and never animates', async () => {
  reduce(true);
  let called = false;
  await animateTo({ animate() { called = true; } }, [{ opacity: 0 }, { opacity: 1 }]);
  assert.equal(called, false);
  reduce(false);
});

test('animateTo resolves with no node, and with a node that cannot animate', async () => {
  await animateTo(null, [{ opacity: 0 }, { opacity: 1 }]);
  await animateTo({}, [{ opacity: 0 }, { opacity: 1 }]);
});

test('animateTo starts a calm 300 ms animation by default and resolves when it ends', async () => {
  const node = fakeNode();
  const keyframes = [{ opacity: 0 }, { opacity: 1 }];
  await animateTo(node, keyframes);
  assert.deepEqual(node.animations, [{
    keyframes,
    options: { duration: 300, delay: 0, easing: CALM, fill: 'backwards' },
  }]);
  await animateTo(node, keyframes, { dur: 200, delay: 40, ease: DRAW, fill: 'forwards' });
  assert.deepEqual(node.animations[1].options, { duration: 200, delay: 40, easing: DRAW, fill: 'forwards' });
});

test('animateTo resolves when the animation is cancelled', async () => {
  const logged = []; const error = console.error; console.error = (e) => logged.push(e);
  try {
    const node = { animate: () => ({ finished: Promise.reject(Object.assign(new Error('cancelled'), { name: 'AbortError' })) }) };
    await animateTo(node, [{ opacity: 0 }, { opacity: 1 }]);
    assert.equal(logged.length, 0);
  } finally { console.error = error; }
});

test('animateTo reports a throwing animate() and still resolves', async () => {
  const logged = []; const error = console.error; console.error = (e) => logged.push(e);
  try {
    await animateTo({ animate() { throw new TypeError('bad keyframes'); } }, [{ opacity: 0 }, { opacity: 1 }]);
    assert.equal(logged.length, 1); assert.equal(logged[0].name, 'TypeError');
  } finally { console.error = error; }
});

test('rise leaves every node visible', () => {
  const n = fakeNode();
  rise([n]);
  assert.equal(n.style.opacity, '');
  reduce(true);
  const m = fakeNode();
  rise([m], { step: 45 });
  assert.equal(m.animations.length, 0);
  assert.equal(m.style.opacity, '');
  assert.equal(m.style.transform, '');
  reduce(false);
});

test('rise fades and lifts each node, one step after the other', () => {
  const [a, b] = [fakeNode(), fakeNode()];
  rise([a, b], { delay: 10, step: 45 });
  assert.deepEqual(a.animations[0].keyframes, [
    { opacity: 0, transform: 'translateY(6px)' },
    { opacity: 1, transform: 'none' },
  ]);
  assert.equal(a.animations[0].options.duration, 260);
  assert.equal(a.animations[0].options.delay, 10);
  assert.equal(b.animations[0].options.delay, 55);
  rise([a], { y: 12, dur: 100 });
  assert.equal(a.animations[1].keyframes[0].transform, 'translateY(12px)');
  assert.equal(a.animations[1].options.duration, 100);
});

test('riseHead lifts the title at once, the lede after 120 ms and the scope line after 180 ms', () => {
  const [t, l, s] = [fakeNode(), fakeNode(), fakeNode()];
  riseHead(t, l, s);
  assert.deepEqual([t, l, s].map((n) => n.animations[0].options.delay), [0, 120, 180]);
  assert.ok([t, l, s].every((n) => n.animations[0].options.duration === 260 && n.animations[0].options.easing === CALM));
  assert.deepEqual(t.animations[0].keyframes, [{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }]);
  riseHead(t, l, null);  // no scope line: nothing breaks
});

test('a Gateway place change by view transition lets the old page leave first: the head starts 120 ms later', () => {
  const lift = (name) => { const [t, l, s] = [fakeNode(), fakeNode(), fakeNode()]; transition(() => riseHead(t, l, s), name); finishTransition(); return [t, l, s].map((n) => n.animations[0].options.delay); };
  assert.deepEqual(lift('map-entrance'), [120, 240, 300]);
  assert.deepEqual(lift('place-change'), [0, 120, 180]);
  const [t, l, s] = [fakeNode(), fakeNode(), fakeNode()];
  riseHead(t, l, s);  // no place change: no wait
  assert.deepEqual([t, l, s].map((n) => n.animations[0].options.delay), [0, 120, 180]);
});

function holderWith(text) {
  const old = fakeNode();
  old.textContent = text;
  const holder = { lastElementChild: old, append(node) { this.lastElementChild = node; } };
  return { holder, old };
}

test('a number that grows rolls up: the old one leaves upward, the new one comes from below', () => {
  const { holder, old } = holderWith('3');
  rollTo(holder, 5);
  const next = holder.lastElementChild;
  assert.equal(next.textContent, '5');
  assert.deepEqual(old.animations[0].keyframes, [
    { transform: 'translateY(0)', opacity: 1 },
    { transform: 'translateY(-70%)', opacity: 0 },
  ]);
  assert.deepEqual(old.animations[0].options, { duration: 140, delay: 0, easing: 'ease-in', fill: 'forwards' });
  assert.deepEqual(next.animations[0].keyframes, [
    { transform: 'translateY(70%)', opacity: 0 },
    { transform: 'translateY(0)', opacity: 1 },
  ]);
  assert.equal(next.animations[0].options.duration, 200);
  assert.equal(next.animations[0].options.delay, 140);
  assert.equal(next.animations[0].options.easing, CALM);
});

test('a number that shrinks, and any text, roll down', () => {
  for (const [from, to] of [['5', '3'], ['Undone', 'Applied'], ['5', 'Applied']]) {
    const { holder, old } = holderWith(from);
    rollTo(holder, to);
    assert.equal(old.animations[0].keyframes[1].transform, 'translateY(70%)', `${from} to ${to}`);
    assert.equal(holder.lastElementChild.animations[0].keyframes[0].transform, 'translateY(-70%)');
  }
});

test('rollTo leaves the same value alone, and draws the first value without motion', () => {
  const same = holderWith('4');
  rollTo(same.holder, 4);
  assert.equal(same.holder.lastElementChild, same.old);
  const first = { lastElementChild: null, append(node) { this.lastElementChild = node; } };
  rollTo(first, 2);
  assert.equal(first.lastElementChild.textContent, '2');
  assert.equal(first.lastElementChild.animations.length, 0);
});

test('rollTo drops the old value by time, and under reduced motion shows the new one at once', async () => {
  const { holder, old } = holderWith('1');
  rollTo(holder, 2);
  assert.equal(old.removed, false);
  await new Promise((resolve) => setTimeout(resolve, 250));
  assert.equal(old.removed, true);
  reduce(true);
  const calm = holderWith('1');
  rollTo(calm.holder, 2);
  assert.equal(calm.holder.lastElementChild.animations.length, 0);
  assert.equal(calm.old.animations.length, 0);
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(calm.old.removed, true);
});

test('shake moves a bar 7 px left, 6 right, 3 left and back in 380 ms', async () => {
  const node = fakeNode();
  await shake(node);
  assert.deepEqual(node.animations[0].keyframes.map((frame) => frame.transform), [
    'translateX(0)', 'translateX(-7px)', 'translateX(6px)', 'translateX(-3px)', 'translateX(0)',
  ]);
  assert.equal(node.animations[0].options.duration, 380);
  assert.equal(node.animations[0].options.easing, 'ease-out');
});

test('shake does nothing under reduced motion', async () => {
  reduce(true);
  const node = fakeNode();
  await shake(node);
  assert.equal(node.animations.length, 0);
  await shake(null);
});

test('glide slides the mark with the calm curve, 300 ms by default and 280 ms when asked', () => {
  const ink = fakeNode();
  const box = { querySelector: () => ink };
  const at = (left) => ({ offsetLeft: left, offsetTop: 0, offsetWidth: 40, offsetHeight: 24 });
  glide(box, at(0), 'glide-test');
  assert.equal(ink.animations.length, 0);
  glide(box, at(50), 'glide-test');
  assert.equal(ink.animations.length, 1);
  assert.equal(ink.animations[0].options.easing, CALM);
  assert.equal(ink.animations[0].options.duration, 300);
  glide(box, at(100), 'glide-test', { duration: 280 });
  assert.equal(ink.animations[1].options.duration, 280);
  glide(box, at(150), 'glide-test', { animated: false });
  assert.equal(ink.animations.length, 2);
  assert.equal(ink.style.transform, 'translate(150px, 0px)');
});

// The spring overshoots a little: only presses, the chevron, switch knobs, ports, a server's count
// badge, the × of a block in preview and the tick of a check may use it. Rows, blocks that move,
// tiles, panels, marks and the dragged block move with CALM.
test('only presses and small parts use the spring in CSS', () => {
  const file = new URL('../../src/kitden/web/static/style.css', import.meta.url);
  const css = readFileSync(file, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
  const users = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .filter(([, , body]) => body.includes('var(--spring)'))
    .map(([, selector]) => selector.trim().replace(/\s+/g, ' '));
  assert.deepEqual(users.sort(), [
    '.brand', '.btn', '.chevron', '.chk .ic', '.dock .ib, .dock .x', '.nav a', '.port', '.seg button', '.switch .thumb', '.switch.flipped .thumb', '.tabs button', 'div.map .block', 'div.map .block-count', 'div.map .block-x',
  ]);
});
