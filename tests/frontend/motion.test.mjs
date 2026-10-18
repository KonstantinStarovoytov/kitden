import assert from 'node:assert/strict';
import { test } from 'node:test';

const classes = new Set();
const transitions = [];
globalThis.matchMedia = () => ({ matches: false });
globalThis.document = {
  hidden: false,
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
