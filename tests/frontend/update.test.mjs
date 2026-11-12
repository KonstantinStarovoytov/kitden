import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

// motion.js reads matchMedia when it loads.
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
const { STEPS, failedWords, pollMs, twiceWords, updateView, watchStep } = await import('../../src/kitden/web/static/js/update.js');

const NOTES = 'https://github.com/KonstantinStarovoytov/kitden/releases/tag/v0.7.3';
const OUT = { version: '0.7.2', latest: '0.7.3', can_update: true, notes_url: NOTES, state: 'idle', step: null, tail: [] };

test('only the version when nothing is newer', () => {
  assert.deepEqual(updateView({ version: '0.7.2', latest: null, state: 'idle' }, null),
    { version: 'Kitden 0.7.2', button: null, tip: '', ring: 0 });
});

test('available names the new version', () => {
  const v = updateView(OUT, null);
  assert.equal(v.button, 'available');
  assert.equal(v.tip, 'Update available: 0.7.3');
});

test('a latest version that is not newer shows no button', () => {
  // The server sends notes_url only when the latest version is newer than this one.
  const v = updateView({ ...OUT, latest: '0.7.2', notes_url: null }, null);
  assert.deepEqual(v, { version: 'Kitden 0.7.2', button: null, tip: '', ring: 0 });
});

test('the confirm keeps the button as it is', () => {
  assert.deepEqual(updateView(OUT, 'confirm'), updateView(OUT, null));
});

test('running follows the real step', () => {
  const v = updateView({ ...OUT, state: 'running', step: 1 }, null);
  assert.equal(v.button, 'running');
  assert.equal(v.tip, 'Installing…');
  assert.equal(v.ring, 0.55);
  assert.equal(updateView({ ...OUT, state: 'running', step: 0 }, null).ring, 0.25);
  assert.equal(updateView({ ...OUT, state: 'running', step: 2 }, null).tip, 'Restarting Kitden…');
});

test('a page that handed over waits on the restart step', () => {
  const v = updateView({ ...OUT, state: 'done', step: 2 }, null);
  assert.deepEqual(v, { version: 'Kitden 0.7.2', button: 'running', tip: 'Restarting Kitden…', ring: 0.8 });
  assert.deepEqual(updateView({ ...OUT, state: 'running', step: 1 }, 'waiting'), v);
});

test('the new page answered: the last step, then the page reloads', () => {
  const v = updateView({ ...OUT, state: 'done', step: 2 }, 'reloading');
  assert.equal(v.tip, 'Reloading the page…');
  assert.equal(v.ring, 1);
});

test('after the reload the button goes and only the version changes; the words are only heard', () => {
  const v = updateView({ ...OUT, version: '0.7.3', latest: '0.7.3', notes_url: null }, 'updated');
  assert.deepEqual(v, { version: 'Kitden 0.7.3', button: null, tip: 'Updated to 0.7.3', ring: 0, quiet: true });
});

test('the reloaded page starts from the full ring with no words', () => {
  const v = updateView({ ...OUT, version: '0.7.2' }, 'landing');
  assert.deepEqual(v, { version: 'Kitden 0.7.2', button: 'running', tip: '', ring: 1, quiet: true });
});

test('no button when Kitden cannot update itself', () => {
  const v = updateView({ ...OUT, can_update: false, command: 'uv tool upgrade kitden' }, null);
  assert.equal(v.button, null);
  assert.equal(v.tip, '0.7.3 is out');
});

test('the demo shows only the version', () => {
  const v = updateView({ version: '0.7.2', latest: null, can_update: false, notes_url: null, state: 'idle', step: null, tail: [] }, null);
  assert.deepEqual(v, { version: 'Kitden 0.7.2', button: null, tip: '', ring: 0 });
});

test('an installer that changed nothing says so and the button goes', () => {
  const v = updateView({ ...OUT, state: 'same', step: 1, tail: ['Nothing to upgrade'] }, null);
  assert.deepEqual(v, { version: 'Kitden 0.7.2', button: null, tip: 'Already up to date', ring: 0 });
});

test('a failed installer shows the red button', () => {
  const v = updateView({ ...OUT, state: 'failed', step: 1, tail: ['error: no network'] }, null);
  assert.deepEqual(v, { version: 'Kitden 0.7.2', button: 'failed', tip: 'Update failed', ring: 0 });
});

test('files replaced but the new page could not start: this old page still runs', () => {
  const api = { ...OUT, state: 'failed', step: 2, tail: ['Updated kitden', 'No such file'] };
  const v = updateView(api, null);
  assert.equal(v.button, 'failed');
  assert.equal(v.tip, 'The new version did not start');
  assert.deepEqual(failedWords(api, null), {
    title: 'The new version did not start',
    text: 'Kitden was updated, but the new page could not start. Close this tab: the old page stops within 10 minutes. Then run this in a terminal:',
    command: 'kitden open',
  });
});

test('no new page and no old page: it did not start again', () => {
  assert.deepEqual(failedWords({ ...OUT, state: 'done', step: 2 }, 'gone'), {
    title: 'Kitden did not start again',
    text: 'Run this in a terminal to open it:',
    command: 'kitden open',
  });
});

test('a failed installer keeps the old version and names the command', () => {
  const api = { ...OUT, state: 'failed', step: 1, command: 'uv tool upgrade kitden' };
  assert.deepEqual(failedWords(api, null), {
    title: 'Update failed',
    text: 'The old version keeps running.',
    command: 'uv tool upgrade kitden',
  });
});

test('the watch reads every 500 ms, and every 3 s once no page came back', () => {
  assert.equal(pollMs(null), 500);
  assert.equal(pollMs('waiting'), 500);
  assert.equal(pollMs('reloading'), 500);
  assert.equal(pollMs('gone'), 3000);
});

test('waiting more than 30 s says it did not start', () => {
  const v = updateView({ ...OUT, state: 'done', step: 2 }, 'gone');
  assert.deepEqual(v, { version: 'Kitden 0.7.2', button: 'failed', tip: 'Kitden did not start again', ring: 0 });
});

test('the steps are the server\'s own words', () => {
  const run = readFileSync(new URL('../../src/kitden/update/run.py', import.meta.url), 'utf8');
  const line = run.match(/^STEPS = \((.+)\)$/m)[1];
  assert.deepEqual(STEPS, [...line.matchAll(/"([^"]+)"/g)].map((m) => m[1]));
});

// The page's watch while an update runs: GET /api/update every 500 ms (answer null: no page answered).
const running = (step) => ({ ...OUT, state: 'running', step });

test('the watch follows the old page, then waits for the new one and reloads', () => {
  let w = { mine: '0.7.2', since: null };
  w = watchStep(w, running(1), 0);
  assert.equal(w.phase, null);
  assert.ok(!w.stop && !w.reload);
  w = watchStep(w, { ...OUT, state: 'done', step: 2 }, 500);
  assert.equal(w.phase, 'waiting');
  w = watchStep(w, null, 1000);
  assert.equal(w.phase, 'waiting');
  w = watchStep(w, { ...OUT, version: '0.7.3', notes_url: null }, 6000);
  assert.equal(w.phase, 'reloading');
  assert.equal(w.reload, true);
});

test('a missed read during the installer keeps the real step', () => {
  let w = { mine: '0.7.2', since: null };
  w = watchStep(w, running(1), 0);
  w = watchStep(w, null, 500);
  assert.notEqual(w.phase, 'waiting');
  assert.equal(updateView(running(1), w.phase).tip, 'Installing…');
  assert.equal(updateView(running(1), w.phase).ring, 0.55);
  // The old page answers again: the miss changed nothing.
  w = watchStep(w, running(1), 1000);
  assert.equal(w.phase, null);
  assert.equal(w.since, null);
});

test('a missed read after the restart step waits for the new page', () => {
  let w = { mine: '0.7.2', since: null };
  w = watchStep(w, running(2), 0);
  w = watchStep(w, null, 500);
  assert.equal(w.phase, 'waiting');
});

test('30 s of silence says it did not start, also before the restart step', () => {
  let w = { mine: '0.7.2', since: null };
  w = watchStep(w, running(1), 0);
  w = watchStep(w, null, 500);
  w = watchStep(w, null, 30000);
  assert.equal(w.phase, null);
  w = watchStep(w, null, 30500);
  assert.equal(w.phase, 'gone');
});

test('no new page within 30 s: it did not start again', () => {
  let w = { mine: '0.7.2', since: null };
  w = watchStep(w, { ...OUT, state: 'done', step: 2 }, 1000);
  w = watchStep(w, null, 30500);
  assert.equal(w.phase, 'waiting');
  w = watchStep(w, null, 31000);
  assert.equal(w.phase, 'gone');
  assert.ok(!w.stop);
  // A new page that comes later still reloads this one.
  w = watchStep(w, { ...OUT, version: '0.7.3' }, 40000);
  assert.equal(w.reload, true);
});

test('an update that ended on the old page stops the watch', () => {
  for (const state of ['failed', 'same']) {
    const w = watchStep({ mine: '0.7.2', since: 3000 }, { ...OUT, state, step: 1 }, 4000);
    assert.equal(w.stop, true);
    assert.equal(w.phase, null);
  }
});

test('two tabs both reach the new page and neither says it did not start', () => {
  // Each tab reads on its own clock; the new page answers 25 s after the old one stopped.
  const answer = (t) => (t < 4000 ? running(1) : t < 5000 ? { ...OUT, state: 'done', step: 2 } : t < 30000 ? null : { ...OUT, version: '0.7.3' });
  for (const offset of [0, 230]) {
    let w = { mine: '0.7.2', since: null };
    const seen = new Set();
    for (let t = offset; !w.reload; t += 500) {
      w = watchStep(w, answer(t), t);
      seen.add(w.phase);
      assert.ok(t < 40000, 'never reloaded');
    }
    assert.ok(!seen.has('gone'));
    assert.ok(seen.has('waiting'));
  }
});

test('two copies: names both and says which one this page runs', () => {
  const api = { ...OUT, method: 'uv', installs: [
    { method: 'uv', remove: 'uv tool uninstall kitden' },
    { method: 'brew', remove: 'brew uninstall kitden' },
  ] };
  assert.deepEqual(twiceWords(api), {
    line: 'Installed twice: uv and Homebrew',
    title: 'Kitden is installed twice',
    text: 'This page runs the uv copy. Each copy updates only itself. Keep one and remove the other:',
    commands: ['uv tool uninstall kitden', 'brew uninstall kitden'],
  });
});

test('one copy or none: no word', () => {
  assert.equal(twiceWords({ ...OUT, installs: [{ method: 'uv', remove: 'uv tool uninstall kitden' }] }), null);
  assert.equal(twiceWords({ ...OUT, installs: [] }), null);
  assert.equal(twiceWords(OUT), null);
});
