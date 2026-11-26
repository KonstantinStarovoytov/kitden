import assert from 'node:assert/strict';
import { test } from 'node:test';

// Context's groups as numbers and words (context-groups.js): what each group takes of the list the
// page draws, in which order, and what its header says; and the Library's line for a plugin.
const { FOLD_ABOVE, factsOf, groupLine, groupsOf, takesLine } = await import('../../src/kitden/web/static/js/context-groups.js');

const skill = (name, group, side, extra = {}) => ({ name, shown: name.split(':').at(-1), plugin: name.includes(':') ? name.split(':')[0] : null, group, side, size: 100, state: 'on', item: `i-${name}`, ...extra });
// The last chat: a and b sent, c only a name, p:x sent and p:y only a name; q:z (off now) was sent.
const FACT = { sent: { a: 300, b: 200, 'p:x': 600, 'q:z': 400 }, over: { c: 120, 'p:y': 90 }, used: 1500 };
const CARD = {
  client: 'claude_code', unit: 'characters', now: null,
  windows: [{ result: FACT }],
  skills: [skill('a', 'own', 0), skill('b', 'own', 0), skill('c', 'own', 1), skill('p:x', 'plugin:p@m', 0), skill('p:y', 'plugin:p@m', 1), skill('q:z', 'plugin:q@m', 0, { state: 'off' })],
  groups: [
    { key: 'own', kind: 'own', name: 'Your skills', skills: ['a', 'b', 'c'], lookup: null },
    { key: 'plugin:p@m', kind: 'plugin', name: 'p', from: 'm', skills: ['p:x', 'p:y'], lookup: 'p@m', switch: { item: 'pp', action: 'plugin.disable', label: 'Turn off p' } },
    { key: 'plugin:q@m', kind: 'plugin', name: 'q', from: 'm', skills: ['q:z'], lookup: 'q@m', switch: { item: 'qq', action: 'plugin.enable', label: 'Turn on q' } },
  ],
};
const factView = (states = {}) => ({ result: FACT, base: FACT, fact: FACT, estimate: false, planned: false, states });
const keys = (all) => all.map((f) => f.group.key);

test('a group takes what its pieces take on the bar, and says how many showed only a name', () => {
  const [p, own, q] = groupsOf(CARD, factView());
  assert.deepEqual([own.n, own.size, own.short, own.state], [3, 500, 1, 'on']);
  assert.deepEqual(groupLine(CARD, own, false), ['3 skills', '500 characters', '1 showed only a name']);
  assert.deepEqual([p.n, p.size, p.short], [2, 600, 1]);
  // In an estimate it says "would".
  assert.deepEqual(groupLine(CARD, p, true), ['2 skills', '600 characters', '1 would show only a name']);
  // Off now, also on the last chat's list, which still held it: said as off, with what it took.
  assert.equal(q.state, 'off');
  assert.deepEqual(groupLine(CARD, q, false), ['Off', 'was 1 skill, 400 characters in your last chat']);
});

test('the groups go largest first, those off now last; the size without the tray orders them', () => {
  assert.deepEqual(keys(groupsOf(CARD, factView())), ['plugin:p@m', 'own', 'plugin:q@m']);
  // The plugin's switch waits: the group keeps its place and says what Apply frees.
  const after = { sent: { a: 300, b: 200, c: 130 }, over: {}, used: 700 };
  const view = { result: after, base: FACT, fact: FACT, estimate: true, planned: true, states: { 'p:x': 'off', 'p:y': 'off' } };
  const all = groupsOf(CARD, view);
  assert.deepEqual(keys(all), ['plugin:p@m', 'own', 'plugin:q@m']);
  assert.equal(all[0].state, 'going');
  assert.deepEqual(groupLine(CARD, all[0], true), ['Off after Apply', 'frees about 600 characters']);
  // c gets its description after Apply: none of Your skills would show only a name.
  assert.deepEqual(groupLine(CARD, all[1], true), ['3 skills', '630 characters']);
});

test('a group the tray turns on again says so and counts in the estimate after Apply', () => {
  const after = { sent: { a: 300, b: 200, 'p:x': 500, 'q:z': 400 }, over: { c: 120, 'p:y': 90 }, used: 1900 };
  const view = { result: after, base: FACT, fact: FACT, estimate: true, planned: true, states: { 'q:z': 'on' } };
  const q = factsOf(CARD, CARD.groups[2], view);
  assert.equal(q.state, 'back');
  assert.deepEqual(groupLine(CARD, q, true), ['On after Apply', '1 skill', '400 characters']);
});

test('a skill turned off in a group of its own counts as off there, and Name only by choice is no misfit', () => {
  const card = { ...CARD, skills: CARD.skills.map((s) => (s.name === 'c' ? { ...s, state: 'name-only' } : s.name === 'b' ? { ...s, state: 'off' } : s)) };
  const now = { sent: { a: 300, 'p:x': 500 }, over: { 'p:y': 90 }, used: 900 };
  const own = factsOf(card, card.groups[0], { result: now, base: now, fact: FACT, estimate: true, planned: false, states: {} });
  assert.deepEqual(groupLine(card, own, true), ['2 skills', '300 characters', '1 off']);
});

test('Codex says cut short, in tokens', () => {
  const card = { ...CARD, client: 'codex', unit: 'tokens' };
  const p = factsOf(card, card.groups[1], factView());
  assert.deepEqual(groupLine(card, p, false), ['2 skills', '600 tokens', '1 cut short']);
});

test('more than a few groups start closed', () => {
  assert.equal(FOLD_ABOVE, 3);
});

test("the Library's line says what a plugin or a skill takes now, and which group it opens", () => {
  assert.deepEqual(takesLine(CARD, { plugin: 'p@m' }), { group: 'plugin:p@m', client: 'claude_code', say: "Takes 600 characters of Claude Code's skill list." });
  assert.deepEqual(takesLine(CARD, { plugin: 'q@m' }), { group: 'plugin:q@m', client: 'claude_code', say: "Off now. Took 400 characters of Claude Code's skill list in your last chat." });
  assert.equal(takesLine(CARD, { plugin: 'r@m' }), null);
  assert.equal(takesLine(CARD, { items: ['i-a'] }).say, "Takes 300 characters of Claude Code's skill list.");
  assert.equal(takesLine(CARD, { items: ['i-c'] }).say, "Shows only its name in Claude Code's skill list.");
  // The estimate for the setup now wins over the last chat.
  const now = { sent: { a: 310, 'p:x': 520 }, over: {} };
  assert.equal(takesLine({ ...CARD, now }, { plugin: 'p@m' }).say, "Takes 520 characters of Claude Code's skill list.");
});
