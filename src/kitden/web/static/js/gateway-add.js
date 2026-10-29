// The Add a server panel on the Gateway (docs/mockup/add-notes.md §1–§3, §8): the shared add panel
// (add-panel.js) with the MCP servers that the marketplaces on this computer offer and an
// All · Remote · Local pill. A click on a row, or a drag of it onto the map (gateway-drag.js), only
// adds its change to the tray (tray.js); nothing is written before the tray's Apply. The panel
// shows no path, address or command.
import { addModes, openDiscovery } from "./discovery.js";
import { button } from "./dom.js";
import { matchRows, openAddPanel, shownList } from "./add-panel.js";
import { getJson } from "./api.js";
import { KIND, SERVER_ICONS } from "./gateway-details.js";
import { pressRow } from "./gateway-drag.js";
import { addToTray, inTray, keyFor, onTray, takeOut } from "./tray.js";

// The search and the pill are the shared panel's (add-panel.js).
export { matchRows };

export const ADD_TITLE = "Add a server";
// Its door in the Kitden gateway's Details, under More.
export const ADD_SERVER = "Add a server…";
const FOOT = "Click a server or drag it onto the map to preview it.";
const NO_MATCH = "No servers match.";
const NONE = "No marketplace on this computer offers an MCP server.";
export const STATUS = { added: "Added", held: "In the gateway", preview: "In preview" };
const KIND_WORDS = { remote: "Remote", local: "Local" };
const PILL = [["all", "All"], ["remote", "Remote"], ["local", "Local"]];
// The data-focus key of "+ Add" beside the map's Servers caption (map-view.js).
const ADD_KEY = "add:servers";

// The rows an Apply added since the page loaded, by row id, while the gateway still holds them: a
// read that says one is not held (after an Undo) frees it.
const added = new Set();
// The rows of an Apply that the page has not read again yet: they are added once it has (pageRead).
let applied = [];
onTray((t) => {
  if (t.phase === "applied") applied = t.rows.filter((row) => row.body.action === "gateway.add").map((row) => row.body.params.server);
});
// The kind of each row read so far, by row id: the map puts a row of the tray in its group by it.
const kinds = new Map();
export const addKind = (id) => kinds.get(id) || null;
// The name of the server a row adds: its id is "<plugin>@<marketplace>/<name>".
export const addName = (id) => id.slice(id.indexOf("/") + 1);
// Whether an Apply since the page loaded added a server of this name, and the gateway holds it.
export const wasAdded = (name) => [...added].some((id) => addName(id) === name);
// What a read of the list says: each row's kind, and which added rows the gateway still holds.
function learn(rows) {
  for (const row of rows || []) {
    kinds.set(row.id, row.kind);
    if (!row.held) added.delete(row.id);
  }
}

// The change a row adds to the tray.
const addBody = (row) => ({ action: "gateway.add", targets: [], params: { server: row.id } });

// What a row says, first match wins: added by an Apply, in the gateway, refused (its reason is the
// small line), waiting in the tray, or nothing. `off`: greyed, with no click and no grip.
export function addRowWords(row, { inTray: waiting = false, added: done = new Set() } = {}) {
  const line = KIND_WORDS[row.kind] || "";
  if (done.has(row.id)) return { status: STATUS.added, off: true, line };
  if (row.held) return { status: STATUS.held, off: true, line };
  if (row.refusal) return { status: "", off: true, line: row.refusal };
  return { status: waiting ? STATUS.preview : "", off: false, line };
}

async function readServers() {
  try {
    const answer = await getJson("/api/market-servers");
    return Array.isArray(answer.servers) ? answer.servers : null;
  } catch {
    return null;
  }
}

// Both doors ("+ Add" and Details' More) let go of what the map has selected before the panel
// opens; the page says how (onOpenAdd).
let letGo = () => {};
export const onOpenAdd = (fn) => {
  letGo = fn;
};

// The Gateway's panel (add-panel.js): its words, its rows and what a row does. Its kicker is read
// when it opens: gateway-details.js may not have run yet when this module does.
const GATEWAY = {
  type: "add",
  get kicker() {
    return KIND.add;
  },
  title: ADD_TITLE,
  foot: FOOT,
  noMatch: NO_MATCH,
  none: NONE,
  pill: PILL,
  addKey: ADD_KEY,
  status: { added: STATUS.added, preview: STATUS.preview },
  read: readServers,
  learn,
  letGo: () => letGo(),
  words: (row, waiting) => addRowWords(row, { inTray: waiting, added }),
  icon: (row) => SERVER_ICONS[row.kind] || SERVER_ICONS.local,
  key: (row) => keyFor(addBody(row)),
  waits: (row) => inTray(keyFor(addBody(row))),
  press: (row) => {
    const key = keyFor(addBody(row));
    return inTray(key) ? takeOut(key) : addToTray(addBody(row));
  },
  before: () => [addModes("local", () => openAdd(), () => openLocalAdd())],
  drag: (event, row, node) => pressRow(event, { name: addName(row.id), kind: row.kind, body: addBody(row), node }),
};

// Open the panel beside the map (add-panel.js openAddPanel). `from` is the button that gets focus
// back when it closes, the map's "+ Add" unless said.
export function openAdd(options = {}) {
  letGo();
  if (options.from) options.from.focus({ preventScroll: true });
  return openDiscovery("mcp", { local: () => openLocalAdd(options) });
}

export function openLocalAdd(options = {}) {
  return openAddPanel(GATEWAY, options);
}

// The page read Kitden again (`view`, its new Gateway read; the same one again does nothing): the
// rows of an Apply say Added now, and an open panel reads the marketplaces again, so each row says
// what is held now. The panel stays open and focus stays where it is.
let seen = null;
let reads = 0;
export async function pageRead(view) {
  if (view === seen) return;
  seen = view;
  // A server an Undo took out is not marked (a closed panel does not read the list to free it).
  const held = new Set(view.gateways.filter((g) => g.kind === "kitden").flatMap((g) => (g.servers || []).map((s) => s.name)));
  for (const id of added) if (!held.has(addName(id))) added.delete(id);
  for (const id of applied) added.add(id);
  applied = [];
  const list = shownList(GATEWAY);
  if (!list) return;
  list.paint();
  const turn = ++reads;
  const rows = await readServers();
  if (!rows || turn !== reads || !list.node.isConnected) return;
  learn(rows);
  list.update(rows);
}
