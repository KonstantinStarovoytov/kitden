import assert from 'node:assert/strict';
import { test } from 'node:test';

// The pages need only these from a browser: a drawer and scrim for the panel, and a history with
// a real stack, so Back is the entry before (push adds after this one, replace overwrites it).
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
function node() {
  const classes = new Set();
  return {
    classList: {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
      toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)),
      contains: (name) => classes.has(name),
    },
    replaceChildren() {}, focus() {}, contains: () => false,
  };
}
const nodes = { '#drawer': node(), '#scrim': node(), '#main': node() };
globalThis.document = {
  activeElement: null,
  createElement: () => ({}),
  getElementById: () => ({}),
  querySelector: (selector) => nodes[selector] ?? null,
  querySelectorAll: () => [],
  addEventListener() {},
};
const entries = ['#overview?project=a'];
let at = 0;
globalThis.history = {
  pushState: (_, __, url) => { entries.splice(at + 1, Infinity, url); at += 1; },
  replaceState: (_, __, url) => { entries[at] = url; },
};
const back = () => entries[(at -= 1)];
const rows = [{ key: 'row-github', kind: 'mcp_server', name: 'github', lookup: 'github' }];
globalThis.fetch = async (url) => ({ ok: true, status: 200, json: async () => (url.startsWith('/api/map') ? { rows } : {}) });
// A drawn row, as openRow marks it.
const tr = { parentElement: { querySelectorAll: () => [] }, setAttribute() {} };

const { data, followHash, goTo, parseHash, state } = await import('../../src/kitden/web/static/js/store.js');
const { arrivalRow, openRow, rowSel } = await import('../../src/kitden/web/static/js/library.js');
const { targetSel } = await import('../../src/kitden/web/static/js/overview.js');
const { arrivalServer } = await import('../../src/kitden/web/static/js/gateway.js');
const { closePanel, isPanelOpen, openPanel } = await import('../../src/kitden/web/static/js/panel.js');
const { contextLinks, followLink } = await import('../../src/kitden/web/static/js/details.js');

const github = { kind: 'mcp_server', name: 'github' };
const files = { kind: 'mcp_server', name: 'files' };
const model = { gateways: [{ kind: 'kitden', servers: [{ name: 'files' }] }] };

test('one project and one selection go from Overview to Library to Gateway, and Back returns', async () => {
  Object.assign(state, parseHash(entries[at]));
  goTo('library', targetSel({ view: 'map', kind: 'mcp_server', name: 'github' }));
  assert.equal(entries[at], '#library?kind=mcp_server&project=a&sel=mcp_server%3Agithub');
  const opened = arrivalRow(rows);
  assert.equal(opened.key, 'row-github'); // Details opens for this row
  openRow(opened, tr, 'pointer');
  assert.deepEqual(rowSel(opened), state.selected); // the row focus returns to
  assert.equal(entries.length, 2); // opening Details adds no history entry
  assert.equal(arrivalRow(rows), null); // a redraw keeps focus in Details
  goTo('gateway', state.selected); // a link to the Gateway keeps both
  assert.equal(entries[at], '#gateway?project=a&sel=mcp_server%3Agithub');
  assert.equal((await arrivalServer(model)).row.name, 'github');
  assert.equal(followHash(back()).same, false); // Back
  assert.equal(state.view, 'library');
  assert.equal(state.project, 'a');
  assert.equal(arrivalRow(rows).key, 'row-github');
  // The address already shown changes nothing and opens nothing; #main is not a page.
  assert.equal(followHash(entries[at]).same, true);
  assert.equal(arrivalRow(rows), null);
  assert.equal(followHash('#main'), null);
});

test("the person's own pick wins over an arrival that comes late", async () => {
  // The rows come after the person opened another row: nothing opens again.
  const other = { key: 'row-other', kind: 'mcp_server', name: 'other', lookup: 'other' };
  goTo('library', github);
  openRow(other, tr, 'pointer');
  assert.equal(arrivalRow([...rows, other]), null);
  // A panel the person opened (a review, Details) drops the arrival, also once it is closed
  // with the selection kept (as a place change closes it).
  goTo('library', github);
  openPanel([]);
  closePanel({ focus: false, keepSelection: true });
  assert.equal(arrivalRow(rows), null);
  // An arrival while a panel is open (Back into the same page) never replaces it.
  openPanel([]);
  followHash('#library?kind=mcp_server&project=a&q=git&sel=mcp_server%3Agithub');
  assert.equal(arrivalRow(rows), null);
  assert.equal(isPanelOpen(), true);
  closePanel({ focus: false });
});

test('the Gateway opens a held server in its own panel, and never over a panel', async () => {
  goTo('gateway', files);
  assert.equal((await arrivalServer(model)).held.name, 'files');
  // After "No gateway yet" the arrival waits; a panel the person opens drops it, and so does
  // saving a gateway (save() in gateway.js, pinned in test_page_words.py).
  goTo('gateway', files);
  openPanel([]);
  closePanel({ focus: false, keepSelection: true });
  assert.equal(await arrivalServer(model), null);
  // While a panel is open nothing opens.
  openPanel([]);
  followHash('#gateway?project=a&sel=mcp_server%3Afiles&q=x');
  assert.equal(await arrivalServer(model), null);
  closePanel({ focus: false });
  // A panel opened while the map is read wins.
  data.scope.map = null;
  goTo('gateway', github);
  const late = arrivalServer(model);
  openPanel([]);
  assert.equal(await late, null);
  closePanel({ focus: false });
});

test('a link from open Details closes it first, so the other place opens the same item', async () => {
  // Details open in the Library: "Manage tools" opens the held server on the Gateway.
  goTo('library', files);
  openPanel([]);
  const [manage] = contextLinks({ kind: 'mcp_server', name: 'files' }, [{ via_gateway: 'kitden' }], state.view);
  assert.equal(manage.label, 'Manage tools');
  await followLink(manage);
  assert.equal(isPanelOpen(), false);
  assert.equal(entries[at], '#gateway?project=a&sel=mcp_server%3Afiles');
  assert.equal((await arrivalServer(model)).held.name, 'files');
  // Details open on the Gateway: "Compare across clients" opens the row in the Library.
  openPanel([]);
  const [compare] = contextLinks(rows[0], [], state.view);
  assert.equal(compare.label, 'Compare across clients');
  await followLink(compare);
  assert.equal(isPanelOpen(), false);
  assert.equal(entries[at], '#library?kind=mcp_server&project=a&sel=mcp_server%3Agithub');
  assert.equal(arrivalRow(rows).key, 'row-github');
});
