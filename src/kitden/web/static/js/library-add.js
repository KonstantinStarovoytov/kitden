// The Library's add panel (decisions "The add panel for plugins and skills", frame L4): the shared
// add panel (add-panel.js) with the plugins and skills the marketplaces on this computer offer
// (/api/library-offers) and an All · Plugins · Skills pill. A click adds a row for all projects to
// every client that can take it and lacks it; a second click takes it out. A drag onto a client
// adds it there only (library-map.js). Nothing is written before the tray's Apply.
import { openAddPanel, shownList } from "./add-panel.js";
import { getJson } from "./api.js";
import { button, plural, reportError } from "./dom.js";
import { addsOf, learnOffers, letGoLibraryMap, onLibraryAdd, pressRow } from "./library-map.js";
import { marketplaceForm } from "./offer.js";
import { CLIENT_ORDER } from "./parts.js";
import { busy, onBusy } from "./store.js";
import { addToTray, keyFor, onTray, takeOut, tray } from "./tray.js";

export const LIBRARY_ADD_TITLE = "Add a plugin or skill";
const FOOT = "Click to preview, or drag onto a client.";
const NO_MATCH = "No plugins or skills match.";
const NONE = "No marketplace on this computer offers a plugin or skill.";
const ADD_MARKETPLACE = "Add a marketplace…";
export const LIBRARY_STATUS = { added: "Added", every: "In every client", preview: "In preview" };
const PILL = [["all", "All"], ["plugin", "Plugins"], ["skill", "Skills"]];
const KIND_ICONS = { plugin: "puzzle", skill: "sparkles" };
const INSTALLS = { plugin: "plugin.install", skill: "skill.install" };
// The data-focus key of "+ Add" beside the map's Plugins and skills caption (map-view.js).
const ADD_KEY = "add:plugins";

// The clients a row adds to: those that can take it and lack it, in column order.
export function lacking(row) {
  const has = new Set(row.installed || []);
  return Object.keys(row.routes || {}).filter((client) => !has.has(client)).sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
}

// A row as the map's blocks have their item, for its drag and for the adds in the tray: the
// clients that have it are on, and the ones it lacks can take it.
export function itemOf(row) {
  const by = Object.fromEntries((row.installed || []).map((client) => [client, "on"]));
  return { kind: row.kind, name: row.name, [row.kind]: row.id, by, can: { add: lacking(row) } };
}

// A click's change: the row for all projects, to every client it lacks (one tray row).
export function allBody(row) {
  return { action: INSTALLS[row.kind], targets: lacking(row).map((client) => ({ client })), params: { [row.kind]: row.id } };
}

// Its small line: what it is, and what Kitden read inside a plugin.
function lineOf(row) {
  if (row.kind !== "plugin") return "Skill";
  return row.count ? `Plugin · ${plural(row.count, row.unit, `${row.unit}s`)}` : "Plugin";
}

// The rows an Apply added since the page loaded, by id, with the clients it added them to. A read
// that says none of those clients has it now (after an Undo) frees it.
const added = new Map();
// The adds of an Apply that the page has not read again yet: they are added once the tray empties.
let applied = [];

// What a row says, first match wins: added by an Apply, in every client that can take it, refused
// (its reason is the small line), waiting in the tray, or nothing. `off`: greyed, with no click and
// no grip.
export function libraryRowWords(row, { inTray: waiting = false, added: done = new Map() } = {}) {
  const line = lineOf(row);
  if (done.has(row.id)) return { status: LIBRARY_STATUS.added, off: true, line };
  if (!lacking(row).length && !row.refusal) return { status: LIBRARY_STATUS.every, off: true, line };
  if (row.refusal) return { status: "", off: true, line: row.refusal };
  return { status: waiting ? LIBRARY_STATUS.preview : "", off: false, line };
}

async function readOffers() {
  try {
    const answer = await getJson("/api/library-offers");
    return Array.isArray(answer.offers) ? answer.offers : null;
  } catch {
    return null;
  }
}

function learn(rows) {
  learnOffers(rows);
  for (const row of rows || []) {
    const clients = added.get(row.id);
    if (clients && !clients.some((client) => (row.installed || []).includes(client))) added.delete(row.id);
  }
}

// The tray rows of the adds of a row that wait, for any client and any project.
const waiting = (row) => addsOf(itemOf(row), tray.rows).map((add) => add.key);

// The Library's panel (add-panel.js): its words, its rows and what a row does.
const LIBRARY = {
  type: "library-add",
  kicker: "Library",
  title: LIBRARY_ADD_TITLE,
  foot: FOOT,
  noMatch: NO_MATCH,
  none: NONE,
  pill: PILL,
  addKey: ADD_KEY,
  status: { added: LIBRARY_STATUS.added, preview: LIBRARY_STATUS.preview },
  read: readOffers,
  learn,
  letGo: letGoLibraryMap,
  words: (row, inTray) => libraryRowWords(row, { inTray, added }),
  icon: (row) => KIND_ICONS[row.kind],
  key: (row) => keyFor(allBody(row)),
  waits: (row) => waiting(row).length > 0,
  press: (row) => {
    const keys = waiting(row);
    return keys.length ? takeOut(keys) : addToTray(allBody(row));
  },
  drag: (event, row, node) => pressRow(event, { item: itemOf(row), node }),
  after: () => [button(ADD_MARKETPLACE, () => marketplaceForm({ back: ({ queued }) => queued && openLibraryAdd() }), "btn ghost small add-more")],
};

// Open the panel beside the map. `from` is the button that gets focus back when it closes, the
// map's "+ Add" unless said.
export function openLibraryAdd(options = {}) {
  return openAddPanel(LIBRARY, options);
}

// An open panel reads the marketplaces again and each row says what it is now.
let reads = 0;
async function readAgain() {
  const list = shownList(LIBRARY);
  if (!list) return;
  list.paint();
  const turn = ++reads;
  const rows = await readOffers();
  if (!rows || turn !== reads || !list.node.isConnected) return;
  learn(rows);
  list.update(rows);
}

// "+ Add" beside the map's caption opens the panel. An Apply's adds say Added once the page has
// read the result (the tray empties after it), and an open panel reads again after every Apply
// or Undo.
export function initLibraryAdd() {
  onLibraryAdd((node) => openLibraryAdd({ from: node }));
  onTray((t) => {
    if (t.phase === "applied") {
      applied = t.rows.filter((row) => Object.values(INSTALLS).includes(row.body.action)).map((row) => row.body);
      return;
    }
    if (!applied.length) return;
    for (const body of applied) added.set(body.params.plugin || body.params.skill, body.targets.map((target) => target.client));
    applied = [];
    readAgain().catch(reportError);
  });
  onBusy(() => busy.change || readAgain().catch(reportError));
}
