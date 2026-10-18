// Load map: items in rows, Claude Code, Codex and Cursor in columns.
import { button, el, shortPath } from "./dom.js";
import { animate, entrance, EASE_IN_OUT } from "./motion.js";
import { banner, flag, mark, morphSocket, skeleton, socket } from "./parts.js";
import { data, go, loadMap, projectPath, render, setState, state } from "./store.js";

const KINDS = [
  ["mcp_server", "MCP servers"], ["plugin", "Plugins"], ["skill", "Skills"],
  ["hook", "Hooks"], ["marketplace", "Marketplaces"],
];
const FILTERS = [["all", "All"], ["problems", "Needs attention"], ["diff", "Differs between clients"]];

// What each cell showed last time, so a change can morph from the old state to the new one.
export let previousCells = {};
let morphNext = false;
export function morphOnNextRender() { morphNext = true; }

let opener = null;
export function onOpenItem(fn) { opener = fn; }

// Another place (the Overview) asks for the selected row to open in the panel once drawn.
let openNext = false;
export function openSelectedOnRender() { openNext = true; }

let inkFrom = null;

const cellKey = (cell) => `${cell.state}|${cell.where || ""}`;

function matches(row) {
  return !state.q || row.name.toLowerCase().includes(state.q.toLowerCase());
}

function passesFilter(row) {
  if (state.only === "problems") return row.flags.some((f) => f.level === "warning");
  if (state.only === "diff") {
    const states = Object.values(row.cells).map((c) => c.state).filter((s) => s !== "missing");
    return new Set(states).size > 1;
  }
  return true;
}

export function renderMap(main) {
  main.append(el("h1", null, "Load map"));
  const path = projectPath();
  main.append(el("p", "lede", path
    ? `What each client loads in ${shortPath(path)}.`
    : "What each client loads in the global setup, with no project open."));
  const model = data.map;
  if (!model) {
    if (data.errors.map) main.append(banner("the load map", async () => { await loadMap(); render(); }));
    else main.append(skeleton("table", 1));
    return;
  }

  const found = model.rows.filter(matches);
  const counts = Object.fromEntries(KINDS.map(([kind]) => [kind, found.filter((r) => r.kind === kind).length]));
  if (state.q && !counts[state.kind]) {
    const first = KINDS.find(([kind]) => counts[kind]);
    if (first) setState({ kind: first[0] });
  }
  main.append(tabs(counts));

  const bar = el("div", "toolbar");
  const seg = el("div", "seg");
  seg.setAttribute("role", "group");
  seg.setAttribute("aria-label", "Show");
  for (const [id, label] of FILTERS) {
    const b = button(label, () => go("map", { only: id }), "");
    b.setAttribute("aria-pressed", String(state.only === id));
    seg.append(b);
  }
  bar.append(seg);
  main.append(bar);

  const rows = found.filter((r) => r.kind === state.kind).filter(passesFilter);
  const wantOpen = openNext;
  openNext = false;
  if (!rows.length) {
    main.append(emptyState(counts));
    snapshot(model.rows);
    return;
  }
  const table = buildTable(model.columns, rows);
  const scroller = el("div", "table-scroll");
  scroller.append(table);
  main.append(scroller);
  snapshot(model.rows);
  morphNext = false;
  entrance("map", [table]);

  const selected = table.querySelector('tr[aria-selected="true"]');
  if (selected) requestAnimationFrame(() => selected.scrollIntoView({ block: "nearest" }));
  // Arriving from a finding: the row glows once and the clients that load it ping, so the
  // eye lands on the place the Overview talked about.
  if (selected && wantOpen) {
    selected.classList.add("arrive");
    for (const s of selected.querySelectorAll(".socket.s-on, .socket.s-gw")) s.classList.add("pulse");
  }
  const row = wantOpen && rows.find((r) => r.key === state.selected);
  if (row && selected) openRow(row, selected, "pointer");
}

function tabs(counts) {
  const box = el("div", "tabs");
  box.setAttribute("role", "tablist");
  for (const [kind, label] of KINDS) {
    const tab = button(label, () => go("map", { kind, selected: null }), "");
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(state.kind === kind));
    tab.dataset.kind = kind;
    tab.append(el("span", "count", String(counts[kind])));
    box.append(tab);
  }
  const ink = el("span", "tab-ink");
  ink.setAttribute("aria-hidden", "true");
  box.append(ink);
  requestAnimationFrame(() => placeInk(box, ink));
  return box;
}

// One underline glides from the previous tab to the new one.
function placeInk(box, ink) {
  const active = box.querySelector('[aria-selected="true"]');
  if (!active) return;
  const to = `translateX(${active.offsetLeft}px) scaleX(${active.offsetWidth})`;
  ink.style.transform = to;
  if (inkFrom && inkFrom !== to) animate(ink, [{ transform: inkFrom }, { transform: to }], { duration: 260, easing: EASE_IN_OUT });
  inkFrom = to;
}

function buildTable(columns, rows) {
  const table = el("table", "map");
  const widths = el("colgroup");
  for (const width of ["38%", "20.6%", "20.6%", "20.6%"]) {
    const col = el("col");
    col.style.width = width;
    widths.append(col);
  }
  table.append(widths);
  const head = el("thead");
  const headRow = el("tr");
  headRow.append(el("th", null, "Name"));
  for (const column of columns) {
    const th = el("th");
    const chip = el("span", "chip");
    chip.append(mark(column.id), el("span", null, column.name));
    th.append(chip);
    headRow.append(th);
  }
  head.append(headRow);
  table.append(head);

  const body = el("tbody");
  for (const row of rows) body.append(buildRow(columns, row));
  table.append(body);
  return table;
}

function buildRow(columns, row) {
  const tr = el("tr");
  tr.tabIndex = 0;
  tr.dataset.key = row.key;
  tr.setAttribute("aria-selected", String(state.selected === row.key));
  const nameCell = el("td");
  const box = el("div", "item");
  const name = el("span", "mono", row.name);
  name.title = row.name;
  box.append(name);
  for (const f of row.flags) box.append(flag(f));
  nameCell.append(box);
  tr.append(nameCell);
  for (const column of columns) {
    const cell = row.cells[column.id];
    const td = el("td");
    const before = previousCells[row.key] && previousCells[row.key][column.id];
    const changed = morphNext && before && before !== cellKey(cell);
    const shown = changed ? { state: before.split("|")[0], where: before.split("|")[1] || null } : cell;
    const node = socket({ state: shown.state, where: shown.where });
    td.append(node);
    if (changed) setTimeout(() => morphSocket(node, { state: cell.state, where: cell.where }), 260);
    tr.append(td);
  }
  tr.addEventListener("click", () => openRow(row, tr, "pointer"));
  tr.addEventListener("keydown", (event) => onRowKey(event, row, tr));
  return tr;
}

function openRow(row, tr, how) {
  state.selected = row.key;
  for (const other of tr.parentElement.querySelectorAll('tr[aria-selected="true"]')) other.setAttribute("aria-selected", "false");
  tr.setAttribute("aria-selected", "true");
  if (opener) opener(row, tr, how);
}

function onRowKey(event, row, tr) {
  if (event.key === "Enter") {
    event.preventDefault();
    openRow(row, tr, "keyboard");
  } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const next = event.key === "ArrowDown" ? tr.nextElementSibling : tr.previousElementSibling;
    if (next) next.focus();
  }
}

function snapshot(rows) {
  previousCells = Object.fromEntries(rows.map((r) => [r.key, Object.fromEntries(Object.entries(r.cells).map(([c, cell]) => [c, cellKey(cell)]))]));
}

function emptyState(counts) {
  const box = el("div", "empty");
  const label = (KINDS.find(([kind]) => kind === state.kind) || ["", "items"])[1].toLowerCase();
  if (state.q && !counts[state.kind]) {
    box.append(el("strong", null, `Nothing matches “${state.q}”`), button("Clear search", () => go("map", { q: "" })));
  } else if (state.only !== "all") {
    box.append(el("strong", null, "Nothing to show with this filter"), button("Show all", () => go("map", { only: "all" })));
  } else {
    box.append(el("strong", null, `No ${label} in any client`), el("p", null, `${label[0].toUpperCase()}${label.slice(1)} you add in Claude Code, Codex or Cursor will show up here.`));
  }
  return box;
}
