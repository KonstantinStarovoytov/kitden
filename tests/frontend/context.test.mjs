import assert from 'node:assert/strict';
import { test } from 'node:test';

// The pages need only these from a browser to load. Each address written goes into `addresses`.
globalThis.matchMedia = () => ({ matches: false });
delete globalThis.navigator;
globalThis.document = {
  createElement: () => ({}),
  getElementById: () => ({}),
  querySelector: () => null,
  addEventListener() {},
};
const addresses = [];
globalThis.history = {
  pushState: (_, __, url) => addresses.push(url),
  replaceState: (_, __, url) => addresses.push(url),
};
const { followAddress, goTo, parseHash, state, takeArrival } = await import('../../src/kitden/web/static/js/store.js');
const { rowFor, rowSel } = await import('../../src/kitden/web/static/js/library.js');
const { targetSel } = await import('../../src/kitden/web/static/js/overview.js');
const { serverFor } = await import('../../src/kitden/web/static/js/gateway.js');

test('one project and one selection go from Overview to Library to Gateway, and Back returns', () => {
  const rows = [{ key: 'row-github', kind: 'mcp_server', name: 'github', lookup: 'github' }];
  Object.assign(state, parseHash('#overview?project=a'));
  goTo('library', targetSel({ view: 'map', kind: 'mcp_server', name: 'github' }));
  assert.equal(addresses.at(-1), '#library?kind=mcp_server&project=a&sel=mcp_server%3Agithub');
  const opened = rowFor(rows, takeArrival());
  assert.equal(opened.key, 'row-github'); // Details opens for this row
  assert.deepEqual(rowSel(opened), state.selected); // the row focus returns to
  assert.equal(takeArrival(), null); // a redraw keeps focus in Details
  goTo('gateway', state.selected); // the rail link keeps both
  assert.equal(addresses.at(-1), '#gateway?project=a&sel=mcp_server%3Agithub');
  assert.equal(serverFor({ rows }, takeArrival()).name, 'github');
  followAddress(parseHash(addresses.at(-2))); // Back
  assert.equal(state.view, 'library');
  assert.equal(state.project, 'a');
  assert.deepEqual(takeArrival(), { kind: 'mcp_server', name: 'github' });
});
