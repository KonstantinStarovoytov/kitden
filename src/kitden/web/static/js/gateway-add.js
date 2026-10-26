// The Add a server panel on the Gateway (docs/mockup/add-notes.md §1–§3, §8): the MCP servers that
// the marketplaces on this computer offer, one group per marketplace, with a search and an
// All · Remote · Local pill. A click on a row only adds its change to the tray (tray.js); nothing
// is written before the tray's Apply. The panel shows no path, address or command.
import { getJson } from "./api.js";
import { $, button, el, icon, reportError, withFocusKey } from "./dom.js";
import { KIND, SERVER_ICONS } from "./gateway-details.js";
import { animateTo, glide } from "./motion.js";
import { followTray, header, loadPanel, openPanel, panelState, whenGone, whenIn } from "./panel.js";
import { addToTray, inTray, keyFor, takeOut } from "./tray.js";

export const ADD_TITLE = "Add a server";
// Its door in the Kitden gateway's Details, under More.
export const ADD_SERVER = "Add a server…";
const SEARCH = "Search the marketplaces";
const FOOT = "Click a server or drag it onto the map to preview it.";
const NO_MATCH = "No servers match.";
const NONE = "No marketplace on this computer offers an MCP server.";
const FAILED = "Could not read the marketplaces.";
export const STATUS = { added: "Added", held: "In the gateway", preview: "In preview" };
const KIND_WORDS = { remote: "Remote", local: "Local" };
const PILL = [["all", "All"], ["remote", "Remote"], ["local", "Local"]];
// The data-focus key of "+ Add" beside the map's Servers caption (map-view.js).
const ADD_KEY = "add:servers";

// The rows an Apply added since the page loaded, by row id. Nothing fills it yet.
const added = new Set();

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

// The rows the search (part of the name, any case) and the pill ("all", "remote", "local") keep.
export function matchRows(rows, query = "", kind = "all") {
  const q = String(query).trim().toLowerCase();
  return rows.filter((row) => (kind === "all" || row.kind === kind) && row.name.toLowerCase().includes(q));
}

// The map's "+ Add", if the map shows it.
function mapAddButton() {
  const main = $("#main");
  return main ? withFocusKey(main, ADD_KEY) : null;
}

// "+ Add" looks pressed while the panel is open (add-notes §9.5).
function showPressed(node, on) {
  if (!node) return;
  node.classList.toggle("primary", on);
  node.classList.toggle("ghost", !on);
  node.setAttribute("aria-expanded", String(on));
}

async function readServers() {
  try {
    const answer = await getJson("/api/market-servers");
    return Array.isArray(answer.servers) ? answer.servers : null;
  } catch {
    return null;
  }
}

// Open the panel beside the map: its skeleton, then the list read from the marketplaces. `from` is
// the button that gets focus back when it closes (the map's "+ Add"); it looks pressed until then.
// Focus goes to the search.
let opening = 0;
export async function openAdd({ from = mapAddButton() } = {}) {
  const turn = ++opening;
  if (from) from.focus({ preventScroll: true });
  const mark = loadPanel(KIND.add);
  showPressed(from, true);
  const rows = await readServers();
  if (turn !== opening) return;
  if (panelState.current !== mark) {
    showPressed(from, false);
    return;
  }
  panelState.current = { type: "add" };
  const parts = addParts(rows, () => openAdd({ from }));
  openPanel(parts.nodes);
  showPressed(from, true);
  whenGone(parts.nodes[0], () => showPressed(from, false));
  whenIn(parts.focus, parts.landed);
}

// The panel's nodes: the head, the search, the pill and the list (or why there is none), and the
// footer. `retry` reads again.
function addParts(rows, retry) {
  const head = header(KIND.add, ADD_TITLE, null);
  const body = el("div", "body add-body");
  const foot = el("p", "step-foot");
  foot.append(icon("info", 13), el("span", null, FOOT));
  if (!rows) {
    const again = button("Try again", retry, "btn ghost small");
    body.append(el("p", "muted", FAILED), again);
    return { nodes: [head, body, foot], focus: again, landed: () => again.focus() };
  }
  const list = rowList(rows);
  const input = el("input");
  input.type = "search";
  input.placeholder = `${SEARCH}…`;
  input.setAttribute("aria-label", SEARCH);
  const search = el("label", "add-search");
  search.append(icon("search", 14), input);
  const pill = kindPill((kind) => list.filter(input.value, kind));
  input.addEventListener("input", () => list.filter(input.value, pill.kind()));
  body.append(search, pill.node, list.node);
  return { nodes: [head, body, foot], focus: input, landed: () => { input.focus(); pill.place(); } };
}

// The pill All · Remote · Local: `pick(kind)` on a press; the raised mark glides to it in 280 ms
// (motion.js glide), and starts in place.
function kindPill(pick) {
  const node = el("div", "seg sm");
  let kind = "all";
  const choices = PILL.map(([id, label]) => {
    const choice = button(label, () => {
      kind = id;
      for (const other of choices) other.setAttribute("aria-pressed", String(other === choice));
      glide(node, choice, "add-kind", { duration: 280 });
      pick(kind);
    }, "");
    choice.setAttribute("aria-pressed", String(id === kind));
    return choice;
  });
  node.append(...choices);
  const place = () => glide(node, choices.find((c) => c.getAttribute("aria-pressed") === "true"), "add-kind", { animated: false });
  return { node, kind: () => kind, place };
}

// The groups, one per marketplace in the order the list has them (by name), each a caption and its
// rows. `filter(query, kind)` hides the rows that do not match and a group with none left; a row
// that comes back rises (opacity, 4 px down, 240 ms).
function rowList(rows) {
  const node = el("div", "add-list");
  const note = el("p", "muted add-none", rows.length ? NO_MATCH : NONE);
  note.hidden = rows.length > 0;
  const groups = [];
  for (const row of rows) {
    let group = groups.at(-1);
    if (!group || group.name !== row.marketplace) {
      const caption = el("div", "add-group");
      caption.append(icon("store", 13), el("span", null, row.marketplace));
      group = { name: row.marketplace, caption, items: [] };
      groups.push(group);
      node.append(caption);
    }
    const item = { row, node: rowNode(row) };
    group.items.push(item);
    node.append(item.node);
  }
  node.append(note);
  const filter = (query, kind) => {
    const kept = new Set(matchRows(rows, query, kind));
    for (const group of groups) {
      for (const item of group.items) {
        const show = kept.has(item.row);
        if (show && item.node.hidden) animateTo(item.node, [{ opacity: 0, transform: "translateY(-4px)" }, { opacity: 1, transform: "none" }], { dur: 240 });
        item.node.hidden = !show;
      }
      group.caption.hidden = !group.items.some((item) => !item.node.hidden);
    }
    note.hidden = rows.length > 0 && kept.size > 0;
  };
  return { node, filter };
}

// One row: a grip, the server's icon on a tile, its name and small line, and its status. It follows
// the tray (details.js followTray). A click, Enter or Space adds its change, or takes it out
// while it waits.
function rowNode(row) {
  const key = keyFor(addBody(row));
  const node = el("div", "res");
  node.setAttribute("role", "button");
  node.setAttribute("tabindex", "0");
  node.dataset.focus = `add-row:${row.id}`;
  const grip = icon("grip-vertical", 12, "ic grip");
  const tile = el("span", "itile");
  tile.append(icon(SERVER_ICONS[row.kind] || SERVER_ICONS.local, 14));
  const text = el("span", "tx");
  const line = el("small");
  text.append(el("b", null, row.name), line);
  const status = el("span", "st");
  node.append(grip, tile, text, status);
  followTray(node, key, (waiting) => {
    const words = addRowWords(row, { inTray: waiting, added });
    node.classList.toggle("off", words.off);
    node.classList.toggle("on", words.status === STATUS.preview);
    node.classList.toggle("done", words.status === STATUS.added);
    if (words.off) node.setAttribute("aria-disabled", "true");
    else node.removeAttribute("aria-disabled");
    grip.classList.toggle("gone", words.off);
    line.textContent = words.line;
    status.textContent = words.status;
  });
  const press = () => {
    if (addRowWords(row, { added }).off) return;
    const work = inTray(key) ? takeOut(key) : addToTray(addBody(row));
    Promise.resolve(work).catch(reportError);
  };
  node.addEventListener("click", press);
  node.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    press();
  });
  return node;
}
