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
