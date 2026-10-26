import assert from 'node:assert/strict';
import { afterEach, beforeEach, mock, test } from 'node:test';

// logo.js needs only these from a browser: elements that know their children, attributes, a
// style with custom properties, a class selector and `animate`; `media` is reduced motion.
const media = { matches: false };
globalThis.matchMedia = () => media;
function element(tag) {
  const node = {
    tag, className: '', textContent: '', children: [], attributes: {}, animations: [],
    style: { setProperty(name, value) { node.style[name] = value; } },
    classList: { contains: (name) => node.className.split(' ').includes(name) },
    append(...nodes) { node.children.push(...nodes.map((n) => (typeof n === 'string' ? { tag: '#text', textContent: n } : n))); },
    replaceChildren(...nodes) { node.children = []; node.append(...nodes); },
    setAttribute(name, value) { node.attributes[name] = value; },
    querySelector: (selector) => node.children.find((c) => c.classList && c.classList.contains(selector.slice(1))) || null,
    animate(keyframes, options) { node.animations.push({ keyframes, options }); return {}; },
    addEventListener(type, listener) { node.listeners = { ...node.listeners, [type]: listener }; },
  };
  return node;
}
globalThis.document = { createElement: element, createElementNS: (ns, tag) => element(tag) };
const { startLogo, TOTAL } = await import('../../src/kitden/web/static/js/logo.js');

// The rail's logo as index.html has it: the mark and the word.
function brand() {
  const node = element('div');
  const mark = element('span');
  mark.className = 'brand-mark';
  const label = element('span');
  label.className = 'label';
  label.textContent = 'Kitden';
  node.append(mark, label);
  return { node, mark, label };
}
const puffsOf = (label) => label.children[1].children[0].children;

beforeEach(() => mock.timers.enable({ apis: ['setTimeout'] }));
afterEach(() => { mock.timers.reset(); media.matches = false; });

test('the word still reads Kitden, with the smoke in the d and the light in the door', () => {
  const { node, mark, label } = brand();
  startLogo(node);
  assert.equal(label.children.map((c) => c.textContent).join(''), 'Kitden');
  const d = label.children[1];
  assert.equal(d.className, 'd');
  const puffs = puffsOf(label);
  assert.equal(puffs.length, 12);
  assert.ok(puffs.every((p) => p.className === 'puff' && p.children[0].attributes.viewBox === '0 -5 28 20'));
  assert.deepEqual(puffs.slice(0, 6).map((p) => p.style['--w']), ['0.3em', '0.32em', '0.34em', '0.36em', '0.38em', '0.3em']);
  assert.deepEqual(mark.children.map((c) => c.className), ['step', 'door']);
});

test('twelve puffs 110 ms apart on one path; the door lights first and goes out after the last puff', () => {
  const { node, mark, label } = brand();
  const play = startLogo(node);
  play();
  const flights = puffsOf(label).map((p) => p.animations[0]);
  assert.deepEqual(flights.map((a) => a.options.delay), Array.from({ length: 12 }, (_, i) => 500 + i * 110));
  assert.ok(flights.every((a) => a.options.duration === 2600 && a.options.easing === 'linear'));
  const frames = flights[0].keyframes;
  assert.deepEqual(frames.map((f) => f.opacity), [0, 0.31, 0.22, 0]);
  assert.deepEqual(frames.map((f) => f.offset), [0, 0.2, 0.6, 1]);
  assert.match(frames[3].transform, /^translate\(0\.900em, -0\.368em\) scale\(1\.400\)$/);
  const [step, door] = mark.children;
  const light = door.animations[0];
  assert.equal(light.options.duration, TOTAL);
  assert.equal(TOTAL, 4510);
  assert.equal(Math.round(light.keyframes[1].offset * TOTAL), 1200);
  assert.equal(light.keyframes[0].easing, 'cubic-bezier(.45, 0, .25, 1)');
  assert.equal(Math.round(light.keyframes[2].offset * TOTAL), TOTAL - 700);
  assert.equal(500 + 11 * 110 + 2600, TOTAL - 200);
  assert.deepEqual(light.keyframes.map((f) => f.opacity), [0, 0.92, 0.92, 0]);
  assert.deepEqual(step.animations[0].keyframes.map((f) => f.opacity), [0, 0.42, 0.42, 0]);
});

test('the gesture plays by itself once, 400 ms after the page opens', () => {
  const { node, label } = brand();
  startLogo(node);
  mock.timers.tick(399);
  assert.equal(puffsOf(label)[0].animations.length, 0);
  mock.timers.tick(1);
  assert.equal(puffsOf(label)[0].animations.length, 1);
  mock.timers.tick(10000);
  assert.equal(puffsOf(label)[0].animations.length, 1);
});

test('the pointer or focus that stays 200 ms plays the gesture again, but never while it still plays', () => {
  const { node, label } = brand();
  startLogo(node);
  mock.timers.tick(400);
  const count = () => puffsOf(label)[0].animations.length;
  assert.equal(count(), 1);
  node.listeners.pointerenter();
  mock.timers.tick(200);
  assert.equal(count(), 1); // the first gesture still plays
  mock.timers.tick(TOTAL - 200); // now it is over
  node.listeners.pointerenter();
  mock.timers.tick(199);
  assert.equal(count(), 1); // the wait is not over
  node.listeners.pointerleave();
  mock.timers.tick(1);
  assert.equal(count(), 1); // the pointer only passed
  node.listeners.focus();
  mock.timers.tick(200);
  assert.equal(count(), 2);
});

test('under reduced motion nothing moves and the door stays dark', () => {
  media.matches = true;
  const { node, mark, label } = brand();
  const play = startLogo(node);
  mock.timers.tick(1000);
  play();
  assert.equal(puffsOf(label)[0].animations.length, 0);
  assert.equal(mark.children[1].animations.length, 0);
});
