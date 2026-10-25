import assert from 'node:assert/strict';
import { test } from 'node:test';

// Reduced motion is switched per test (D() reads it at every call). Any other query is a wide window.
const motionQuery = { matches: true };
globalThis.matchMedia = (query) => (/reduced-motion/.test(query) ? motionQuery : { matches: false, addEventListener() {} });
delete globalThis.navigator;
const reduce = (flag) => { motionQuery.matches = flag; };

// Stand-in nodes: enough of the DOM for the dock, the toast in it and the page around.
const textNode = (value) => ({ nodeType: 3, textContent: String(value), parent: null });
// How animate behaves: it works, it is missing from the node, or it throws.
let animation = 'works';
function fakeNode(tag) {
  const classes = new Set();
  const node = {
    nodeType: 1, tag, parent: null, childNodes: [], attributes: {}, dataset: {}, listeners: {}, animations: [], height: 40,
    style: { setProperty(name, value) { this[name] = String(value); }, removeProperty(name) { delete this[name]; } },
    get offsetHeight() { return node.height; },
    [Symbol.for('nodejs.util.inspect.custom')]: () => `<${tag}>`,
    get className() { return [...classes].join(' '); },
    set className(value) { classes.clear(); String(value).split(/\s+/).filter(Boolean).forEach((name) => classes.add(name)); },
    classList: {
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      contains: (name) => classes.has(name),
    },
    get textContent() { return node.childNodes.map((child) => child.textContent).join(''); },
    set textContent(value) { node.replaceChildren(...(String(value) === '' ? [] : [String(value)])); },
    get children() { return node.childNodes.filter((child) => child.nodeType === 1); },
    get lastElementChild() { return node.children.at(-1) || null; },
    get isConnected() { let up = node; while (up.parent) up = up.parent; return up.root === true; },
    adopt(items) {
      return items.map((item) => (typeof item === 'string' ? textNode(item) : item)).map((child) => {
        if (child.parent) child.parent.childNodes = child.parent.childNodes.filter((other) => other !== child);
        child.parent = node;
        return child;
      });
    },
    append(...items) { node.childNodes.push(...node.adopt(items)); },
    prepend(...items) { node.childNodes.unshift(...node.adopt(items)); },
    replaceChildren(...items) { for (const child of node.childNodes) { leave(child); child.parent = null; } node.childNodes = []; node.childNodes = node.adopt(items); },
    remove() { leave(node); if (node.parent) node.parent.childNodes = node.parent.childNodes.filter((child) => child !== node); node.parent = null; },
    contains(other) { return other === node || node.children.some((child) => child.contains(other)); },
    setAttribute(name, value) { node.attributes[name] = String(value); },
    getAttribute: (name) => (name in node.attributes ? node.attributes[name] : null),
    addEventListener(type, listener) { (node.listeners[type] ||= []).push(listener); },
    focus(options) { node.focusOptions = options; globalThis.document.activeElement = node; },
    animate(frames, options) {
      if (animation === 'throws') throw new Error('animate failed');
      const run = { frames, options, paused: 0, played: 0, cancelled: false };
      run.handle = { finished: Promise.resolve(), pause() { run.paused += 1; }, play() { run.played += 1; }, cancel() { run.cancelled = true; } };
      node.animations.push(run);
      return run.handle;
    },
  };
  if (animation === 'missing') delete node.animate;
  return node;
}
// A node that leaves the page takes focus with it.
const leave = (node) => { if (node.nodeType === 1 && node.contains(globalThis.document.activeElement)) globalThis.document.activeElement = null; };
const all = (node) => [node, ...node.children.flatMap(all)];
const fire = (node, type) => (node.listeners[type] || []).forEach((listener) => listener({}));

const pages = {};
for (const id of ['#dock', '#main']) {
  pages[id] = fakeNode('div');
  pages[id].root = true;
}
// The live region keeps what was set and when, so a test can tell a change from a repeat.
const saidLog = [];
pages['#said'] = Object.assign(fakeNode('div'), { root: true });
Object.defineProperty(pages['#said'], 'textContent', { get: () => saidLog.at(-1) ?? '', set: (value) => { saidLog.push(String(value)); } });
const rootStyle = { setProperty(name, value) { this[name] = String(value); }, removeProperty(name) { delete this[name]; } };
globalThis.document = {
  activeElement: null,
  documentElement: { style: rootStyle },
  createElement: fakeNode,
  createElementNS: (namespace, tag) => fakeNode(tag),
  getElementById: () => null,
  querySelector: (selector) => pages[selector] ?? null,
};

const { hideToast, makeRoom, onToastGone, toast } = await import('../../src/kitden/web/static/js/toast.js');
const dock = pages['#dock'];

const toastNode = () => dock.children.find((node) => node.classList.contains('toast')) || null;
const shape = (node) => node.children.map((child) => `${child.tag}${child.className ? `.${child.className}` : ''}`);
const buttonOf = (label) => all(toastNode()).find((node) => node.tag === 'button' && node.textContent === label);
const room = () => rootStyle['--dock-room'];
const quietly = (fn) => {
  const log = console.error;
  console.error = () => {};
  try { return fn(); } finally { console.error = log; }
};

// An empty dock, no toast, a quiet page and no motion in every test; a test that looks at motion turns it on.
function fresh() {
  animation = 'works';
  reduce(true);
  hideToast({ now: true });
  onToastGone(null);
  dock.replaceChildren();
  rootStyle.removeProperty('--dock-room');
  saidLog.length = 0;
  globalThis.document.activeElement = null;
}

test('the toast replaces the bar and offers Undo', () => {
  fresh();
  const bar = fakeNode('section');
  bar.className = 'bar tray';
  dock.append(bar);
  const pressed = [];
  toast('Turned off github in Claude Code.', () => pressed.push('undo'), { ok: true });
  assert.deepEqual(dock.children, [toastNode()]);
  assert.equal(bar.isConnected, false);
  const node = toastNode();
  // The page's live region speaks it; the toast is not a second one.
  assert.deepEqual([node.className, node.attributes.role], ['toast', undefined]);
  assert.deepEqual(shape(node), ['span.tk', 'span', 'button.btn small', 'i.life']);
  const [tick, words, undo] = node.children;
  assert.equal(tick.children[0].dataset.icon, 'circle-check');
  assert.equal(words.textContent, 'Turned off github in Claude Code.');
  assert.deepEqual([undo.children[0].dataset.icon, undo.children[0].attributes.width, undo.textContent], ['undo-2', '13', 'Undo']);
  undo.listeners.click[0]();
  assert.deepEqual(pressed, ['undo']);
});

test('an error toast has no check', () => {
  fresh();
  toast('Undo stopped: the file changed after the change was applied.');
  assert.deepEqual(shape(toastNode()), ['span', 'i.life']);
  // The extra button comes before Undo; Undo all is Undo with other words.
  toast('Applied 3 changes', () => {}, { ok: true, label: 'Undo all', extra: { label: 'Show website', run() {} } });
  assert.deepEqual(shape(toastNode()), ['span.tk', 'span', 'button.btn small', 'button.btn small', 'i.life']);
  assert.deepEqual(toastNode().children.slice(2, 4).map((node) => node.textContent), ['Show website', 'Undo all']);
  assert.equal(toastNode().children[2].children.length, 0);
});

test('the toast comes in with the mockup\'s look and its life runs 9 s, linear, toward the left', () => {
  fresh();
  reduce(false);
  toast('Applied', () => {}, { ok: true });
  const node = toastNode();
  const [enter] = node.animations;
  assert.deepEqual(enter.frames, [{ opacity: 0, transform: 'translateY(14px)' }, { opacity: 1, transform: 'none' }]);
  assert.deepEqual([enter.options.duration, enter.options.easing], [200, 'cubic-bezier(.2,.8,.2,1)']);
  const [life] = node.children.at(-1).animations;
  assert.deepEqual(life.frames, [{ transform: 'scaleX(1)' }, { transform: 'scaleX(0)' }]);
  assert.deepEqual([life.options.duration, life.options.easing, life.options.fill], [9000, 'linear', 'forwards']);
  assert.equal(node.children.at(-1).attributes['aria-hidden'], 'true');
});

test('under reduced motion the toast still lives 9 s', (t) => {
  fresh();
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  toast('Applied', () => {}, { ok: true });
  const node = toastNode();
  // No motion of its own: it is there at once, and the life line still runs the whole 9 s.
  assert.equal(node.animations.length, 0);
  assert.equal(node.children.at(-1).animations[0].options.duration, 9000);
  t.mock.timers.tick(8999);
  assert.equal(node.isConnected, true);
  // It is gone at the end, with no leaving motion to wait for.
  t.mock.timers.tick(1);
  assert.equal(node.isConnected, false);
});

test('the life pauses under the pointer and resumes after', (t) => {
  fresh();
  reduce(false);
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  toast('Applied', () => {}, { ok: true });
  const node = toastNode();
  const life = node.children.at(-1).animations[0];
  t.mock.timers.tick(4000);
  fire(node, 'pointerenter');
  assert.deepEqual([life.paused, life.played], [1, 0]);
  // Held, it does not end, however long the pointer stays.
  t.mock.timers.tick(60000);
  assert.equal(node.isConnected, true);
  fire(node, 'pointerleave');
  assert.deepEqual([life.paused, life.played], [1, 1]);
  // The 5 s it had left (not 9) run out; then it leaves in 160 ms.
  t.mock.timers.tick(4999);
  assert.equal(node.animations.length, 1, 'it left too early');
  t.mock.timers.tick(1);
  assert.equal(node.animations.length, 2);
  assert.equal(node.isConnected, true);
  t.mock.timers.tick(160);
  assert.equal(node.isConnected, false);
});

test('focus on the toast pauses the life too, and the pointer leaving does not let go of it', (t) => {
  fresh();
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  toast('Applied', () => {}, { ok: true });
  const node = toastNode();
  const life = node.children.at(-1).animations[0];
  fire(node, 'focusin');
  fire(node, 'pointerenter');
  fire(node, 'pointerleave');
  assert.deepEqual([life.paused, life.played], [1, 0]);
  t.mock.timers.tick(20000);
  assert.equal(node.isConnected, true);
  fire(node, 'focusout');
  assert.equal(life.played, 1);
  t.mock.timers.tick(9000);
  assert.equal(node.isConnected, false);
});

test('Undo makes the toast leave at once, down 10 px in 160 ms, and runs the action without waiting', (t) => {
  fresh();
  reduce(false);
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  const pressed = [];
  toast('Applied', () => pressed.push('undo'), { ok: true });
  const node = toastNode();
  const undo = buttonOf('Undo');
  undo.focus();
  undo.listeners.click[0]();
  assert.deepEqual(pressed, ['undo']);
  const out = node.animations.at(-1);
  assert.deepEqual(out.frames, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(10px)' }]);
  assert.deepEqual([out.options.duration, out.options.easing, out.options.fill], [160, 'ease-in', 'forwards']);
  // Focus was on Undo: it goes to the page, with no scroll.
  assert.equal(globalThis.document.activeElement, pages['#main']);
  assert.deepEqual(pages['#main'].focusOptions, { preventScroll: true });
  // Still on the page while it leaves; a second press does nothing.
  assert.equal(node.isConnected, true);
  undo.listeners.click[0]();
  assert.deepEqual(pressed, ['undo']);
  t.mock.timers.tick(160);
  assert.equal(node.isConnected, false);
  assert.equal(room(), undefined);
});

test('the extra button leaves the toast and runs its action', () => {
  fresh();
  const pressed = [];
  toast('Gateway saved.', null, { extra: { label: 'Open Changes', run: () => pressed.push('changes') } });
  assert.equal(buttonOf('Undo'), undefined);
  buttonOf('Open Changes').listeners.click[0]();
  assert.deepEqual(pressed, ['changes']);
  assert.equal(toastNode(), null);
});

test('an action that fails is reported, and the toast has gone', async () => {
  fresh();
  toast('Applied', () => Promise.reject(new Error('broken')), { ok: true });
  const reported = [];
  const log = console.error;
  console.error = (error) => reported.push(error.message);
  try {
    await buttonOf('Undo').listeners.click[0]();
  } finally {
    console.error = log;
  }
  assert.deepEqual(reported, ['broken']);
  assert.equal(toastNode(), null);
});

test('a new toast replaces the old one at once, and a screen reader hears each', (t) => {
  fresh();
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  toast('Applied', () => {}, { ok: true });
  const first = toastNode();
  t.mock.timers.tick(1);
  assert.equal(pages['#said'].textContent, 'Applied');
  const undo = buttonOf('Undo');
  undo.focus();
  toast('Undone. The previous settings are back.', null, { ok: true });
  assert.equal(first.isConnected, false);
  assert.deepEqual(dock.children, [toastNode()]);
  t.mock.timers.tick(1);
  assert.equal(pages['#said'].textContent, 'Undone. The previous settings are back.');
  // Focus that was in the old one goes to the page, not nowhere.
  assert.equal(globalThis.document.activeElement, pages['#main']);
  hideToast();
  assert.equal(pages['#said'].textContent, '');
});

test('the same words twice are a change again: the region is emptied, and the words come in a later task', (t) => {
  fresh();
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  toast('Undone. The previous settings are back.', null, { ok: true });
  t.mock.timers.tick(1);
  toast('Undone. The previous settings are back.', null, { ok: true });
  // Still the same task: the region is empty, so the words that come next are a change.
  assert.equal(pages['#said'].textContent, '');
  t.mock.timers.tick(1);
  assert.equal(pages['#said'].textContent, 'Undone. The previous settings are back.');
  assert.deepEqual(saidLog, ['Undone. The previous settings are back.', '', 'Undone. The previous settings are back.']);
  // A toast that has gone before its words came never says them.
  hideToast();
  toast('Applied', () => {}, { ok: true });
  hideToast();
  t.mock.timers.tick(5);
  assert.equal(pages['#said'].textContent, '');
});

test('the page keeps room under the toast and gives it back when the dock is empty', (t) => {
  fresh();
  reduce(false);
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  toast('Applied', () => {}, { ok: true });
  assert.equal(room(), '86px'); // the toast's 40 px and the dock's 46 px
  toastNode().height = 52;
  makeRoom();
  assert.equal(room(), '98px');
  hideToast();
  assert.equal(room(), '98px', 'the room stays while it leaves');
  t.mock.timers.tick(160);
  assert.equal(room(), undefined);
});

test('the bar takes the toast\'s place with hideToast({ now: true }): at once, and nothing is told', () => {
  fresh();
  let told = 0;
  onToastGone(() => { told += 1; });
  toast('Applied', () => {}, { ok: true });
  const node = toastNode();
  node.children[2].focus();
  hideToast({ now: true });
  assert.equal(node.isConnected, false);
  assert.equal(globalThis.document.activeElement, pages['#main']);
  assert.equal(told, 0);
  // Gone by itself (here: Cancel-like hide), the tray is told, once, when the toast has left.
  toast('Applied', () => {}, { ok: true });
  hideToast();
  assert.equal(told, 1);
  hideToast();
  assert.equal(told, 1);
});

test('a toast that is replaced while it leaves does not tell the tray it is gone', (t) => {
  fresh();
  reduce(false);
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  let told = 0;
  onToastGone(() => { told += 1; });
  toast('Applied', () => {}, { ok: true });
  hideToast();
  toast('Undone.', null, { ok: true });
  t.mock.timers.tick(160);
  assert.equal(told, 0);
  assert.equal(toastNode().children[1].textContent, 'Undone.');
});

test('with no animation in the browser, or one that fails, the toast still goes at the end of its life', (t) => {
  for (const mode of ['missing', 'throws']) {
    fresh();
    reduce(false);
    animation = mode;
    t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
    // A failing animation is logged, as motion.js does; the page goes on.
    quietly(() => {
      toast('Applied', () => {}, { ok: true });
      const node = toastNode();
      assert.equal(node.isConnected, true, mode);
      t.mock.timers.tick(8999);
      assert.equal(node.isConnected, true, mode);
      t.mock.timers.tick(1);
      t.mock.timers.tick(160);
      assert.equal(node.isConnected, false, mode);
    });
    t.mock.timers.reset();
  }
});
