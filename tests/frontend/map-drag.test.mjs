import assert from 'node:assert/strict';
import { test } from 'node:test';

// The drag engine every map shares (map-drag.js), with a stand-in page: the document and the
// window hear the pointer, and each map records what a drag asks of its view.
globalThis.matchMedia = () => ({ matches: false });
const heard = {};
const listen = (type, fn) => { (heard[type] ||= []).push(fn); };
const unlisten = (type, fn) => { heard[type] = (heard[type] || []).filter((f) => f !== fn); };
globalThis.window = { addEventListener: listen, removeEventListener: unlisten };
const covers = {};
globalThis.document = {
  addEventListener: listen,
  removeEventListener: unlisten,
  documentElement: { classList: { add() {}, remove() {} } },
  querySelector: (selector) => (covers[selector] ? { getBoundingClientRect: () => covers[selector] } : null),
  hidden: false,
};
const { HOME_MS, startDrag } = await import('../../src/kitden/web/static/js/map-drag.js');
// The Gateway's drags go through the same engine.
const gateway = await import('../../src/kitden/web/static/js/gateway-drag.js');

// A map with one block at (100, 50), 180×60, as a page gives it to the engine.
function fakeMap() {
  const asked = [];
  const node = { dataset: { focus: 'block:a' }, getBoundingClientRect: () => ({ left: 100, top: 50 }), setPointerCapture() {} };
  const view = {
    node: () => node,
    hold: (id, at, how) => asked.push(['hold', id, at, how]),
    homeIn: (id, ms) => asked.push(['homeIn', id, ms]),
    tip() {}, untip: () => asked.push(['untip']), unlightTarget() {}, glance: (set) => asked.push(['glance', set]),
    box: { isConnected: true },
    area: { getBoundingClientRect: () => ({ left: 0, top: 0 }) },
  };
  const map = { view, model: { blocks: [{ id: 'a' }], links: [] }, layout: { blocks: [{ id: 'a', x: 100, y: 50, w: 180, h: 60 }] }, drag: null, home: null, redraw() {}, onHome: (id) => asked.push(['onHome', id]) };
  return { map, asked, node };
}
const press = (node) => ({ button: 0, pointerId: 1, target: { closest: () => node }, clientX: 110, clientY: 60 });
const fire = (type, event) => { for (const fn of [...(heard[type] || [])]) fn(event); };

test("the engine runs a page's own hooks on its own map", () => {
  const one = fakeMap();
  const other = fakeMap();
  const seen = [];
  const hooks = { item: { begin: (drag) => seen.push(['begin', drag.id]), over: (drag) => seen.push(['over', drag.at]), drop: (drag, at) => { seen.push(['drop', at]); return false; } } };
  const started = [];
  startDrag(press(one.node), { id: 'a', name: 'A' }, 'item', { hooks, map: one.map, onStart: () => started.push('start') });
  fire('pointermove', { clientX: 113, clientY: 63.99 });
  assert.deepEqual([started, seen], [[], []], 'under 5 px nothing starts');
  fire('pointermove', { clientX: 113, clientY: 64 });
  assert.deepEqual(started, ['start']);
  assert.deepEqual(one.asked[0], ['hold', 'a', { x: 103, y: 54 }, { pressed: true }]);
  assert.equal(one.map.drag.kind, 'item');
  assert.equal(other.map.drag, null, 'another map is not touched');
  fire('pointerup', { type: 'pointerup', clientX: 140, clientY: 70 });
  // The drop hears a map point; one it does not take sends the block home, the page first.
  assert.deepEqual(seen.at(-1), ['drop', { x: 140, y: 70 }]);
  assert.deepEqual(one.asked.slice(-2), [['onHome', 'a'], ['homeIn', 'a', HOME_MS]]);
  assert.equal(HOME_MS, 220);
  assert.deepEqual([one.map.drag, one.map.home, other.asked], [null, null, []]);
  assert.deepEqual(heard.pointermove, []);
});

test('a drop over Details or the dock hears no point, and a still kind holds nothing', () => {
  const { map, asked, node } = fakeMap();
  const seen = [];
  const hooks = { wire: { still: true, begin() {}, over() {}, drop: (drag, at) => { seen.push(at); return true; } } };
  covers['#dock'] = { left: 130, top: 60, right: 200, bottom: 100, width: 70, height: 40 };
  try {
    startDrag(press(node), { id: 'a', name: 'A' }, 'wire', { hooks, map });
    fire('pointermove', { clientX: 140, clientY: 70 });
    fire('pointerup', { type: 'pointerup', clientX: 140, clientY: 70 });
    assert.deepEqual(seen, [null]);
    assert.ok(!asked.some(([what]) => what === 'hold' || what === 'homeIn'));
  } finally {
    delete covers['#dock'];
  }
});

test("the Gateway's drags run through the shared engine", () => {
  // The Gateway keeps its own hooks and its own wrapper; the engine is not copied there.
  assert.deepEqual(Object.keys(gateway.DRAGS), ['in', 'out', 'client', 'add']);
  assert.equal(typeof gateway.startDrag, 'function');
  assert.equal(gateway.startDrag.length, 3);
});
