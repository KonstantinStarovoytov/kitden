import assert from 'node:assert/strict';
import { test } from 'node:test';

// The line under the version, as startUpdate draws it, on a small stand-in DOM. A line that shows
// is 18 px tall; one that is hidden, or has nothing to show, is 0.
class Node {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.nodeType = 1;
    this.children = [];
    this.hidden = false;
    this.dataset = {};
    this.style = {};
    this.className = '';
    this.classList = { add() {}, remove() {} };
    this.anims = [];
    this.text = '';
  }
  get textContent() { return this.text + this.children.map((c) => c.textContent).join(''); }
  set textContent(value) { this.text = String(value); this.children = []; }
  get lastElementChild() { return this.children.at(-1) ?? null; }
  get offsetHeight() { return this.hidden ? 0 : this.scrollHeight; }
  get scrollHeight() { return this.text || this.children.some((c) => c.offsetHeight) ? 18 : 0; }
  append(...nodes) { for (const n of nodes) { n.parent = this; this.children.push(n); } }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this); }
  setAttribute() {}
  removeAttribute() {}
  addEventListener() {}
  querySelector() { return null; }
  contains() { return false; }
  focus() {}
  getAnimations() { return [...this.anims]; }
  animate(keyframes) {
    const anim = { keyframes, finished: new Promise(() => {}), cancel: () => { this.anims = this.anims.filter((a) => a !== anim); } };
    this.anims.push(anim);
    return anim;
  }
}

let timers = [];
globalThis.setTimeout = (fn, ms = 0) => { const t = { fn, ms }; timers.push(t); return t; };
globalThis.clearTimeout = (t) => { timers = timers.filter((x) => x !== t); };
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
globalThis.document = {
  createElement: (tag) => new Node(tag),
  createElementNS: (_, tag) => new Node(tag),
  querySelector: () => null,
  addEventListener() {},
  removeEventListener() {},
};
globalThis.sessionStorage = { getItem: () => null, removeItem() {}, setItem() {} };
let answers = [];
globalThis.fetch = async () => ({ ok: true, json: async () => answers.shift() });

const { startUpdate } = await import('../../src/kitden/web/static/js/update.js');

const settle = () => new Promise((done) => setImmediate(done));
const SAME = { version: '0.7.2', latest: null, notes_url: null, can_update: true, state: 'same', step: null, tail: [] };
const IDLE = { ...SAME, state: 'idle' };

// The next look at the server (every 3 s while the latest version is not known yet).
async function poll(answer) {
  answers.push(answer);
  const look = timers.find((t) => t.ms === 3000);
  timers = timers.filter((t) => t !== look);
  look.fn();
  await settle();
}

function runTimers(ms) {
  const due = timers.filter((t) => t.ms === ms);
  timers = timers.filter((t) => t.ms !== ms);
  for (const t of due) t.fn();
}

async function spotWith(first) {
  timers = [];
  answers = [first];
  const spot = new Node('div');
  startUpdate(spot);
  await settle();
  return spot.children[1]; // the line under the version
}

test('a page with nothing to say draws no line and does not move the version', async () => {
  const line = await spotWith({ ...IDLE, latest: '0.7.2' });
  assert.equal(line.hidden, true);
  assert.equal(line.anims.length, 0);
});

test('a line that shuts keeps its words until it is gone, so it shrinks from its height', async () => {
  const line = await spotWith(SAME);
  assert.equal(line.hidden, false);
  await poll(IDLE);
  assert.equal(line.anims.at(-1).keyframes[0].height, '18px');
  runTimers(260);
  assert.equal(line.hidden, true);
});

test('shut, open and shut again quickly: only the last shut hides the line', async () => {
  const line = await spotWith(SAME);
  await poll(IDLE);
  const first = timers.filter((t) => t.ms === 260);
  await poll(SAME);
  await poll(IDLE);
  for (const t of first) { timers = timers.filter((x) => x !== t); t.fn(); }
  assert.equal(line.hidden, false, 'the first shut hid the line early');
  runTimers(260);
  assert.equal(line.hidden, true);
});
