import assert from 'node:assert/strict';
import { test } from 'node:test';

// offer.js needs only this from a browser to load; the tests call its pure parts.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
const { addFormBody, projectNote } = await import('../../src/kitden/web/static/js/offer.js');
const { syncTray } = await import('../../src/kitden/web/static/js/details.js');
const { review } = await import('../../src/kitden/web/static/js/review.js');
const { cancelTray, keyFor, onTray, takeOut, tray } = await import('../../src/kitden/web/static/js/tray.js');

test('an add in a project view says it is for every project', () => {
  assert.equal(projectNote('p1'), 'Adds for all projects.');
  assert.equal(projectNote(''), null);
});

// A page whose Details hold `controls`, and a stand-in server for the tray: a batch preview answers
// with one row per request (as details.test.mjs's trayPage). `sent` keeps every address asked.
function formPage() {
  const page = { controls: [], sent: [] };
  const node = (tag) => {
    const classes = new Set();
    const made = {
      tag, textContent: '', childNodes: [], attributes: {}, dataset: {}, listeners: {}, title: '', disabled: false,
      get className() { return [...classes].join(' '); },
      set className(value) { classes.clear(); String(value).split(/\s+/).filter(Boolean).forEach((name) => classes.add(name)); },
      classList: { add: (name) => classes.add(name), remove: (name) => classes.delete(name), toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)), contains: (name) => classes.has(name) },
      append(...nodes) { made.childNodes.push(...nodes); },
      setAttribute(name, value) { made.attributes[name] = String(value); },
      getAttribute: (name) => (name in made.attributes ? made.attributes[name] : null),
      removeAttribute(name) { delete made.attributes[name]; },
      addEventListener(type, listener) { (made.listeners[type] ||= []).push(listener); },
      // An event on this node, and what it set off.
      async fire(type) { (made.listeners[type] || []).forEach((listener) => listener({ preventDefault() {} })); await new Promise((resolve) => setTimeout(resolve, 0)); },
    };
    return made;
  };
  const drawer = { querySelectorAll: (selector) => (selector === '[data-tray]' ? page.controls.filter((c) => c.dataset.tray) : []) };
  globalThis.document = { createElement: node, getElementById: () => null, querySelector: (selector) => (selector === '#drawer' ? drawer : null), querySelectorAll: () => [] };
  globalThis.fetch = async (url, options = {}) => {
    page.sent.push(url);
    if (url !== '/api/batch/preview') return Response.json({});
    const { requests } = JSON.parse(options.body);
    return Response.json({
      id: `c${page.sent.length}`, action: 'batch', state: 'previewed', error: null, undo_note: null,
      steps: requests.map(() => ({ client: 'codex', name: 'x' })),
      rows: requests.map((r, at) => ({ id: r.id, kind: r.kind, title: r.title, detail: '', project: null, steps: [at], after: [] })),
    });
  };
  // What initPanel does: the looks follow every change of the tray.
  page.stop = onTray(syncTray);
  return page;
}

test('an add form says In preview while its row waits and goes back after', async () => {
  const page = formPage();
  try {
    const chosen = new Set(['codex']);
    const bodyOf = () => ({ action: 'skill.install', targets: [...chosen].map((client) => ({ client })), params: { skill: 'tidy@toolbox' } });
    const form = addFormBody(document.createElement('fieldset'), chosen, bodyOf, (body) => review(body, { note: 'Adds for all projects.' }));
    const submit = form.childNodes.find((n) => n.tag === 'button');
    page.controls.push(submit);
    const words = () => submit.childNodes.map((n) => n.textContent).join('');
    assert.deepEqual([words(), submit.attributes['aria-disabled']], ['Preview', undefined]);
    await form.fire('submit');
    assert.deepEqual(tray.rows.map((r) => [r.key, r.note]), [[keyFor(bodyOf()), 'Adds for all projects.']]);
    // While its row waits it says so and takes no press.
    assert.deepEqual([words(), submit.attributes['aria-disabled']], ['In preview', 'true']);
    const asked = page.sent.length;
    await form.fire('submit');
    assert.equal(page.sent.length, asked);
    // Another tick is another change: Preview again, and back to In preview with the first.
    chosen.add('claude_code');
    await form.fire('change');
    assert.deepEqual([words(), submit.attributes['aria-disabled']], ['Preview', undefined]);
    chosen.delete('claude_code');
    await form.fire('change');
    assert.equal(words(), 'In preview');
    // Out of the tray, the form is back.
    await takeOut(keyFor(bodyOf()));
    assert.deepEqual([words(), submit.attributes['aria-disabled']], ['Preview', undefined]);
  } finally {
    await cancelTray();
    page.stop();
    delete globalThis.document;
    delete globalThis.fetch;
  }
});
