// The add panel the map pages share (add-notes §1–§4, library-notes §2–§4): the rows the
// marketplaces on this computer offer, one group per marketplace, with a search and a pill that
// keeps one kind. A page gives its own words, rows and what a row does (`config`). A click on a
// row, or a drag of it onto the map, only adds its change to the tray (tray.js); nothing is
// written before the tray's Apply. The panel shows no path, address or command.
//
// `config`:
// - `type`: what panelState says while it shows; `kicker`, `title`, `foot`, `noMatch`, `none`: its
//   words; `pill`: [[kind, words]], "all" first; `addKey`: the data-focus key of the map's "+ Add".
// - `read()`: the rows ({ id, kind, name, marketplace, … } by marketplace), or null when they cannot
//   be read; `learn(rows)` hears each read (null too).
// - `words(row, waiting)`: { status, off, line }; `status`: { added, preview }, the words that look
//   done and in preview. `icon(row)`: its tile's icon. `key(row)`: its tray row's key. `waits(row)`:
//   its change waits in the tray. `press(row)`: add its change, or take it out. `drag(event, row,
//   node)`: a press that may drag it onto the map. `after()`: nodes under the list, or none.
// - `letGo()`: the page lets go of what its map selected, before the panel opens.
import { $, button, el, icon, reportError, withFocusKey } from "./dom.js";
import { animateTo, glide } from "./motion.js";
import { followTray, header, isPanelOpen, loadPanel, openPanel, panelState, whenGone, whenIn } from "./panel.js";

const SEARCH = "Search the marketplaces";
const FAILED = "Could not read the marketplaces.";

// The rows the search (part of the name, any case) and the pill ("all", or a kind) keep.
export function matchRows(rows, query = "", kind = "all") {
  const q = String(query).trim().toLowerCase();
  return rows.filter((row) => (kind === "all" || row.kind === kind) && row.name.toLowerCase().includes(q));
}

// The map's "+ Add", if the map shows it.
function mapAddButton(key) {
  const main = $("#main");
  return main && key ? withFocusKey(main, key) : null;
}

// "+ Add" looks pressed while the panel is open (add-notes §9.5).
function showPressed(node, on) {
  if (!node) return;
  node.classList.toggle("primary", on);
  node.classList.toggle("ghost", !on);
  node.setAttribute("aria-expanded", String(on));
}

// The panel that shows now: its config, its list and its search.
let open = null;
let opening = 0;

// The list the panel of `config` shows now, else null.
export function shownList(config) {
  return open && open.config === config && open.list && open.list.node.isConnected ? open.list : null;
}

// Open the panel beside the map: its skeleton, then the rows read. `from` is the button that gets
// focus back when it closes (the map's "+ Add"); it looks pressed until then. Focus goes to the
// search. Opened again while it shows its list, it stays as it is (its search and its pill too)
// and focus goes to the search.
export async function openAddPanel(config, { from = mapAddButton(config.addKey) } = {}) {
  config.letGo();
  if (isPanelOpen() && panelState.current && panelState.current.type === config.type && shownList(config)) {
    open.search.focus();
    return;
  }
  const turn = ++opening;
  if (from) from.focus({ preventScroll: true });
  const mark = loadPanel(config.kicker);
  showPressed(from, true);
  const rows = await config.read();
  if (turn !== opening) return;
  if (panelState.current !== mark) {
    showPressed(from, false);
    return;
  }
  if (config.learn) config.learn(rows);
  panelState.current = { type: config.type };
  const parts = addParts(config, rows, () => openAddPanel(config, { from }));
  open = { config, list: parts.list, search: parts.focus };
  openPanel(parts.nodes);
  showPressed(from, true);
  whenGone(parts.nodes[0], () => showPressed(from, false));
  whenIn(parts.focus, parts.landed);
}

// The panel's nodes: the head, the search, the pill and the list (or why there is none), what the
// page puts under it, and the footer. `retry` reads again.
function addParts(config, rows, retry) {
  const head = header(config.kicker, config.title, null);
  const body = el("div", "body add-body");
  const foot = el("p", "step-foot");
  foot.append(icon("info", 13), el("span", null, config.foot));
  if (!rows) {
    const again = button("Try again", retry, "btn ghost small");
    body.append(el("p", "muted", FAILED), again);
    return { nodes: [head, body, foot], focus: again, landed: () => again.focus(), list: null };
  }
  const list = rowList(rows, config);
  const input = el("input");
  input.type = "search";
  input.placeholder = `${SEARCH}…`;
  input.setAttribute("aria-label", SEARCH);
  const search = el("label", "add-search");
  search.append(icon("search", 14), input);
  const pill = kindPill(config.pill, (kind) => list.filter(input.value, kind));
  input.addEventListener("input", () => list.filter(input.value, pill.kind()));
  body.append(search, pill.node, list.node, ...(config.after ? config.after() : []));
  return { nodes: [head, body, foot], focus: input, landed: () => { input.focus(); pill.place(); }, list };
}

// The pill (All, then one choice per kind): `pick(kind)` on a press; the raised mark glides to it
// in 280 ms (motion.js glide), and starts in place.
function kindPill(choicesOf, pick) {
  const node = el("div", "seg sm");
  let kind = "all";
  const choices = choicesOf.map(([id, label]) => {
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
// that comes back rises (opacity, 4 px down, 240 ms). `update(rows)` gives each row what a new read
// says of it, and `paint()` draws every row again in place.
function rowList(rows, config) {
  const node = el("div", "add-list");
  const note = el("p", "muted add-none", rows.length ? config.noMatch : config.none);
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
    const item = rowNode(row, config);
    group.items.push(item);
    node.append(item.node);
  }
  node.append(note);
  const items = groups.flatMap((group) => group.items);
  const filter = (query, kind) => {
    const kept = new Set(matchRows(items.map((item) => item.row), query, kind).map((row) => row.id));
    for (const group of groups) {
      for (const item of group.items) {
        const show = kept.has(item.row.id);
        if (show && item.node.hidden) animateTo(item.node, [{ opacity: 0, transform: "translateY(-4px)" }, { opacity: 1, transform: "none" }], { dur: 240 });
        item.node.hidden = !show;
      }
      group.caption.hidden = !group.items.some((item) => !item.node.hidden);
    }
    note.hidden = rows.length > 0 && kept.size > 0;
  };
  const paint = () => {
    for (const item of items) item.paint();
  };
  const update = (fresh) => {
    const byId = new Map(fresh.map((row) => [row.id, row]));
    for (const item of items) if (byId.has(item.row.id)) item.row = byId.get(item.row.id);
    paint();
  };
  return { node, filter, paint, update };
}

// One row: a grip, its icon on a tile, its name and small line, and its status. It follows the
// tray (details.js followTray). A click, Enter or Space runs its press (add, or take out while it
// waits); a key held down does it once. A press on a free row that moves 5 px drags it onto the
// map instead (`config.drag`). The added status slides in from 6 px to the right (280 ms CALM) when
// a row turns to it.
// Gives `{ row, node, paint }`: `row` is what the last read said of it.
function rowNode(row, config) {
  const item = { row, node: null, paint: null };
  const node = el("div", "res");
  node.setAttribute("role", "button");
  node.setAttribute("tabindex", "0");
  node.dataset.focus = `add-row:${row.id}`;
  const grip = icon("grip-vertical", 12, "ic grip");
  const tile = el("span", "itile");
  tile.append(icon(config.icon(row), 14));
  const text = el("span", "tx");
  const line = el("small");
  text.append(el("b", null, row.name), line);
  const status = el("span", "st");
  node.append(grip, tile, text, status);
  let painted = false;
  const look = () => {
    const words = config.words(item.row, config.waits(item.row));
    const { added, preview } = config.status;
    const turns = painted && words.status === added && status.textContent !== added;
    painted = true;
    node.classList.toggle("off", words.off);
    node.classList.toggle("on", words.status === preview);
    node.classList.toggle("done", words.status === added);
    if (words.off) node.setAttribute("aria-disabled", "true");
    else node.removeAttribute("aria-disabled");
    grip.classList.toggle("gone", words.off);
    line.textContent = words.line;
    status.textContent = words.status;
    if (turns) animateTo(status, [{ opacity: 0, transform: "translateX(6px)" }, { opacity: 1, transform: "none" }], { dur: 280 });
  };
  followTray(node, config.key(row), look);
  Object.assign(item, { node, paint: look });
  const off = () => config.words(item.row, false).off;
  const press = () => {
    if (off()) return;
    Promise.resolve(config.press(item.row)).catch(reportError);
  };
  node.addEventListener("click", press);
  node.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    if (!event.repeat) press();
  });
  node.addEventListener("pointerdown", (event) => {
    if (off() || config.waits(item.row)) return;
    config.drag(event, item.row, node);
  });
  return item;
}
