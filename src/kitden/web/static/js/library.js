// Library: what each client loads, and what you can add to it. One tab per kind, one column per
// client found on this computer. Each cell shows a state, the one action for that client, or a
// dash that says why not. The server builds the rows and cells (views/library.py).
import { getJson, query } from "./api.js";
import { button, el, tabKeys } from "./dom.js";
import { entrance, glide, land, reducedMotion } from "./motion.js";
import { marketplaceForm, projectNote, showOffer, showSkill } from "./offer.js";
import { openInfo, review } from "./panel.js";
import { banner, CLIENT_NAMES, flag, mark, morphSocket, opens, skeleton, socket, staleNote } from "./parts.js";
import { freshness, go, projectPath, render, retry, state } from "./store.js";

const KINDS = [
  ["mcp_server", "MCP servers"], ["plugin", "Plugins"], ["skill", "Skills"],
  ["hook", "Hooks"], ["marketplace", "Marketplaces"],
];
// Tabs with something to add; the others show only what is on this computer.
const CATALOG = ["plugin", "skill"];
const SHOW = [["mine", "On this Mac"], ["new", "Can add"], ["all", "All"]];
const KIND_WORDS = { plugin: "Plugin", skill: "Skill" };
// Typing waits this long after the last key before asking the server.
const TYPING_MS = 200;

// What each cell and flag showed last time, so a change can morph from the old state to the
// new one and a resolved flag can shrink away instead of vanishing.
export let previousCells = {};
let previousFlags = {};
let lastProject = null;
let morphNext = false;
export function morphOnNextRender() { morphNext = true; }

let opener = null;
export function onOpenItem(fn) { opener = fn; }

// Another place (the Overview) asks for the selected row to open in the panel once drawn.
let openNext = false;
export function openSelectedOnRender() { openNext = true; }

// Line one's small gray text: the category, then the source only when two rows share the name.
export function metaText(row) {
  return [row.category, row.same_name ? row.source : null].filter(Boolean).join(" · ");
}

// A Details title: the source too when two rows share the name ("superpowers · cursor-public").
export function rowTitle(row) {
  return row.same_name && row.source ? `${row.name} · ${row.source}` : row.name;
}

// One line when the show choice hides matches of the search, or null.
export function moreLine(answer, show) {
  if (!answer.more || show === "all") return null;
  return `${answer.more} more ${show === "mine" ? "not on this Mac" : "on this Mac"} · Show all`;
}

// What a cell's add asks the review for: that one client.
export function previewFor(add, client) {
  const params = add.action === "skill.install" ? { skill: add.skill } : { plugin: add.plugin };
  return { action: add.action, targets: [{ client }], params };
}

// The review's note: a twin it would load as well, and in a project that it is for every project.
export function noteFor(add, project) {
  return [add.warn, projectNote(project)].filter(Boolean).join(" ") || null;
}

// What a screen reader hears for a cell's button: its words first, then what, from where (when
// names repeat) and to which client.
function addName(row, client, add) {
  const name = row.same_name && row.source ? `${row.name} (${row.source})` : row.name;
  const what = { "Add skills": `Add skills from ${name}`, "Add the plugin": `Add the plugin with ${name}` }[add.label] || `Add ${name}`;
  return `${what} to ${CLIENT_NAMES[client] || client}`;
}

// One cell: a button for the one action, a state, or a dash that says why not.
export function cellNode(row, client) {
  const cell = row.cells[client];
  if (cell.add) {
    const node = button(cell.add.label, () => review(previewFor(cell.add, client), { note: noteFor(cell.add, state.project) }), "btn small add");
    node.setAttribute("aria-label", addName(row, client, cell.add));
    node.dataset.focus = `add:${row.key}:${client}`;
    return node;
  }
  const node = socket({ state: cell.state, where: cell.where, word: cell.word });
  if (cell.reason) {
    node.title = cell.reason;
    if (cell.state === "none") node.setAttribute("aria-label", cell.reason);
  }
  return node;
}

// The kind tab shown: an unknown one from an old address falls back to the first tab.
function currentKind() {
  return KINDS.some(([kind]) => kind === state.kind) ? state.kind : "mcp_server";
}

// The question for the server. Tabs without a catalog show only what is on this computer.
function asking() {
  const kind = currentKind();
  const catalog = CATALOG.includes(kind);
  return {
    project: state.project, kind, show: catalog ? state.show : "mine", q: state.q,
    category: catalog ? state.category : "", attention: state.attention,
  };
}

const cacheKey = () => JSON.stringify(asking());

// The last answer and what it was for. `at` is when its request was sent, so an answer asked for
// before a rescan or a change counts as old. A failed key is not asked again until the next reload.
let cache = { key: null, at: 0, readAt: 0, answer: null, asked: null, error: null, errorKey: null, failedAt: 0 };
let pending = null;
let timer = null;
let lastQ = null;

function needsLoad(key) {
  const since = freshness.reloadStartedAt;
  if (pending && pending.key === key && pending.at >= since) return false;
  if (cache.errorKey === key && cache.failedAt >= since) return false;
  return !(cache.key === key && cache.at >= since);
}

// Ask for the shown tab. A newer request wins: an answer for a key no longer shown is dropped.
// `draw` redraws the page when the answer is in; a caller that draws itself passes false.
function load(draw = true) {
  const key = cacheKey();
  if (pending && pending.key === key && pending.at >= freshness.reloadStartedAt) {
    if (!draw) pending.draw = false;
    return pending.promise;
  }
  const asked = asking();
  const at = performance.now();
  lastQ = asked.q;
  // Task 6 sends the hidden columns here too.
  const params = { ...asked, attention: asked.attention ? "1" : "" };
  const job = { key, at, draw };
  job.promise = getJson(`/api/library${query(params)}`).then(
    (answer) => { if (cacheKey() === key) cache = { key, at, readAt: Date.now(), answer, asked, error: null, errorKey: null, failedAt: 0 }; },
    (error) => { if (cacheKey() === key) Object.assign(cache, { error, errorKey: key, failedAt: at }); },
  ).finally(() => {
    if (pending === job) pending = null;
    if (job.draw && state.view === "library" && cacheKey() === key) render();
  });
  pending = job;
  return job.promise;
}

// Typing waits until it stops; any other choice asks at once.
function schedule(key) {
  if (!needsLoad(key)) return;
  clearTimeout(timer);
  if (lastQ === null || lastQ === state.q) {
    load();
    return;
  }
  timer = setTimeout(() => { timer = null; if (state.view === "library") load(); }, TYPING_MS);
}

// For a caller that draws the page itself once the shown tab is read (a reload, a change or a
// project switch), so the cells morph then and not before. Call it right after reload() starts.
export function loadLibrary() {
  if (state.view !== "library") return Promise.resolve();
  clearTimeout(timer);
  const key = cacheKey();
  return cache.key === key && cache.at >= freshness.reloadStartedAt ? Promise.resolve() : load(false);
}

export function renderLibrary(main) {
  main.append(el("h1", null, "Library"));
  // The project goes by its folder name; the full path stays in the project picker's hover.
  const folder = projectPath().split("/").filter(Boolean).pop();
  const lede = el("p", "lede", folder
    ? `What each client loads in the project ${folder}, and what you can add to it. Based on saved settings.`
    : "What each client loads, and what you can add to it. Based on saved settings.");
  // After a scope change the words rise in while the cells morph.
  if (lastProject !== null && lastProject !== state.project) lede.classList.add("fresh");
  lastProject = state.project;
  main.append(lede);

  const key = cacheKey();
  // The page's first reload reads the rows with everything else (app.js refresh).
  if (freshness.reloadStartedAt) schedule(key);
  const kind = currentKind();
  const sameProject = cache.answer && cache.asked.project === state.project;
  // Rows of another tab or project are never shown under this one; other filters wait in place.
  const answer = sameProject && cache.asked.kind === kind ? cache.answer : null;
  const asked = answer ? cache.asked : asking();
  const fresh = cache.key === key && cache.at >= freshness.reloadStartedAt;
  const failed = cache.errorKey === key ? cache.error : null;
  if (answer && !answer.columns.length) {
    main.append(noClients());
    return;
  }

  const tabBox = tabs(sameProject ? cache.answer.counts : null, kind);
  main.append(tabBox);
  glide(tabBox, tabBox.querySelector('[aria-selected="true"]'), "library-tabs");
  const tools = toolbar(kind, answer);
  if (tools) main.append(tools);
  const seg = tools && tools.querySelector(".seg");
  if (seg) glide(seg, seg.querySelector('[aria-pressed="true"]'), "library-show");

  if (!answer) {
    main.append(failed ? banner("the library", retry) : skeleton("table", 1));
    return;
  }
  if (failed) main.append(staleNote(cache.readAt));
  for (const note of answer.notes) main.append(el("p", "note", note));
  const more = moreLine(answer, asked.show);
  const wantOpen = fresh && openNext;
  if (fresh) openNext = false;
  if (!answer.rows.length) {
    main.append(emptyState(asked, more));
    if (fresh) finish(answer.rows);
    return;
  }
  if (more) main.append(moreNode(more));
  // Task 6 hides columns; a hidden one is still in `columns`, marked.
  const columns = answer.columns.filter((c) => !c.hidden);
  const groups = asked.show === "all" && CATALOG.includes(asked.kind);
  const table = buildTable(columns, answer.rows, groups, morphNext && fresh);
  const scroller = el("div", "table-scroll");
  scroller.append(table);
  main.append(scroller);
  if (fresh) finish(answer.rows);
  entrance("library", [table]);

  const selected = table.querySelector('tr[aria-selected="true"]');
  if (selected) requestAnimationFrame(() => selected.scrollIntoView({ block: "nearest" }));
  // Arriving from a finding: the row glows once and the clients that load it ping, so the
  // eye lands on the place the Overview talked about.
  if (selected && wantOpen) {
    selected.classList.add("arrive");
    for (const s of selected.querySelectorAll(".socket.s-on, .socket.s-gw")) s.classList.add("pulse");
  }
  const row = wantOpen && answer.rows.find((r) => r.key === state.selected);
  if (row && selected) openRow(row, selected, "pointer");
}

// A fresh answer is drawn: the next change morphs from what it shows.
function finish(rows) {
  morphNext = false;
  previousCells = Object.fromEntries(rows.map((r) => [r.key, Object.fromEntries(Object.entries(r.cells).map(([c, cell]) => [c, cellKey(cell)]))]));
  previousFlags = Object.fromEntries(rows.map((r) => [r.key, r.flags.map((f) => ({ text: f.text, level: f.level }))]));
}

const cellKey = (cell) => `${cell.state}|${cell.where || ""}|${cell.add ? cell.add.label : ""}`;

function tabs(counts, kind) {
  const box = el("div", "tabs");
  box.setAttribute("role", "tablist");
  for (const [id, label] of KINDS) {
    const tab = button(label, () => go("library", { kind: id, category: "", selected: null }), "");
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(kind === id));
    tab.dataset.kind = id;
    tab.dataset.focus = `tab:${id}`;
    if (counts) tab.append(el("span", "count", String(counts[id])));
    box.append(tab);
  }
  tabKeys(box);
  return box;
}

// Plugins and skills: what to show and a category. Any tab: "Needs attention" when something
// does. Marketplaces: a way to add one. Null when the tab has none of these.
function toolbar(kind, answer) {
  const bar = el("div", "toolbar");
  if (CATALOG.includes(kind)) {
    const seg = el("div", "seg");
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", "Show");
    for (const [id, label] of SHOW) {
      const b = button(label, () => go("library", { show: id, selected: null }), "");
      b.setAttribute("aria-pressed", String(state.show === id));
      b.dataset.focus = `show:${id}`;
      seg.append(b);
    }
    bar.append(seg);
    if (answer && (answer.categories.length || state.category)) bar.append(categoryPicker(answer.categories));
  }
  if (answer && (answer.attention || state.attention)) {
    const toggle = button(`Needs attention · ${answer.attention}`, () => go("library", { attention: !state.attention, selected: null }), "btn small toggle");
    toggle.setAttribute("aria-pressed", String(state.attention));
    toggle.dataset.focus = "filter:attention";
    bar.append(toggle);
  }
  if (kind === "marketplace") {
    const add = button("Add a marketplace…", () => marketplaceForm(), "btn small");
    add.dataset.focus = "add:marketplace";
    bar.append(el("span", "grow"), add);
  }
  return bar.children.length ? bar : null;
}

// A menu of the categories in the results, each with its count.
function categoryPicker(categories) {
  const select = el("select");
  select.setAttribute("aria-label", "Category");
  select.dataset.focus = "filter:category";
  select.append(new Option("All categories", ""));
  const chosen = state.category;
  const options = !chosen || categories.some((c) => c.name === chosen) ? categories : [{ name: chosen, count: 0 }, ...categories];
  for (const c of options) select.append(new Option(`${c.name} (${c.count})`, c.name));
  select.value = chosen;
  select.addEventListener("change", () => go("library", { category: select.value, selected: null }));
  const box = el("label", "filter");
  if (chosen) box.classList.add("on");
  box.append(select);
  return box;
}

// "3 more not on this Mac · Show all": the words, then a button for the last part.
function moreNode(line) {
  const box = el("p", "more");
  const all = button("Show all", () => go("library", { show: "all", selected: null }), "btn ghost small");
  all.dataset.focus = "more:all";
  box.append(el("span", null, `${line.split(" · ")[0]} · `), all);
  return box;
}

function noClients() {
  const box = el("div", "empty");
  box.append(el("strong", null, "Kitden found no AI coding clients."), button("Open Overview", () => go("overview"), "btn"));
  return box;
}

function emptyState(asked, more) {
  const box = el("div", "empty");
  const label = (KINDS.find(([kind]) => kind === asked.kind) || ["", "items"])[1].toLowerCase();
  if (more) {
    const where = asked.show === "mine" ? "on this Mac" : "you can add";
    box.append(el("strong", null, `Nothing ${where} matches “${asked.q}”`), moreNode(more));
  } else if (asked.q) {
    box.append(el("strong", null, `Nothing matches “${asked.q}”`), button("Clear search", () => go("library", { q: "" })));
  } else if (asked.category || asked.attention) {
    box.append(el("strong", null, "Nothing to show with this filter"), button("Show all", () => go("library", { category: "", attention: false })));
  } else if (asked.show !== "mine") {
    box.append(el("strong", null, `No ${label} to add`), el("p", null, "Add a marketplace from a link to see what it offers here."));
  } else {
    box.append(el("strong", null, `No ${label} in any client`), el("p", null, `${label[0].toUpperCase()}${label.slice(1)} you add in Claude Code, Codex or Cursor will show up here.`));
  }
  return box;
}

function buildTable(columns, rows, groups, morph) {
  const table = el("table", "map library");
  const widths = el("colgroup");
  const share = `${(58 / columns.length).toFixed(1)}%`;
  for (const width of ["42%", ...columns.map(() => share)]) {
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
    const tile = mark(column.id);
    // Coming from the Overview, the client's tile flies here from its row.
    land(tile, `client-${column.id}`);
    chip.append(tile, el("span", null, column.name));
    th.append(chip);
    headRow.append(th);
  }
  head.append(headRow);
  table.append(head);

  const body = el("tbody");
  let group = null;
  for (const row of rows) {
    // With All, what is on this computer comes first, then what is not, each under a line.
    if (groups && row.mine !== group) {
      group = row.mine;
      const tr = el("tr", "group");
      const td = el("td", null, row.mine ? "On this Mac" : "Not on this Mac yet");
      td.colSpan = columns.length + 1;
      tr.append(td);
      body.append(tr);
    }
    body.append(buildRow(columns, row, morph));
  }
  table.append(body);
  return table;
}

// Line one: the name, the quiet meta text, the flags and the chevron. Line two: what it does.
function buildRow(columns, row, morph) {
  const tr = el("tr");
  tr.tabIndex = 0;
  tr.dataset.key = row.key;
  tr.setAttribute("aria-selected", String(state.selected === row.key));
  const nameCell = el("td");
  const line = el("div", "item");
  const name = el("span", "mono", row.name);
  name.title = row.name;
  line.append(name);
  const meta = metaText(row);
  if (meta) line.append(el("small", "meta", meta));
  // One flag per wording: three clients with the same note make one flag, not three.
  const shown = row.flags.filter((f, i) => row.flags.findIndex((o) => o.text === f.text) === i);
  for (const f of shown) line.append(flag(f));
  // A flag that a verified change resolved shrinks away instead of vanishing.
  const oldFlags = morph ? previousFlags[row.key] || [] : [];
  for (const f of oldFlags.filter((o) => !shown.some((n) => n.text === o.text))) {
    const node = flag(f);
    node.classList.add("gone");
    node.setAttribute("aria-hidden", "true");
    line.append(node);
    setTimeout(() => node.remove(), 400);
  }
  line.append(opens());
  nameCell.append(line);
  if (row.description) {
    const desc = el("div", "desc", row.description);
    desc.title = row.description;
    nameCell.append(desc);
  }
  tr.append(nameCell);
  for (const column of columns) {
    const td = el("td");
    const before = morph && previousCells[row.key] && previousCells[row.key][column.id];
    td.append(settle(row, column.id, before));
    tr.append(td);
  }
  // A cell's button does its own work; the rest of the row opens Details.
  tr.addEventListener("click", (event) => { if (!event.target.closest("button")) openRow(row, tr, "pointer"); });
  tr.addEventListener("keydown", (event) => onRowKey(event, row, tr));
  return tr;
}

// A cell after a verified change: a state that changed morphs from the old one; a state where a
// button was pings once. Unchanged cells, and buttons, are drawn as they are.
function settle(row, client, before) {
  const cell = row.cells[client];
  const node = cellNode(row, client);
  if (!before || before === cellKey(cell) || cell.add) return node;
  const [was, where, label] = before.split("|");
  if (label) {
    if (!reducedMotion.matches) node.classList.add("pulse");
    return node;
  }
  const old = socket({ state: was, where: where || null });
  old.title = node.title;
  setTimeout(() => morphSocket(old, { state: cell.state, where: cell.where }), reducedMotion.matches ? 0 : 260);
  return old;
}

function openRow(row, tr, how) {
  state.selected = row.key;
  for (const other of tr.parentElement.querySelectorAll('tr[aria-selected="true"]')) other.setAttribute("aria-selected", "false");
  tr.setAttribute("aria-selected", "true");
  // A row on this computer opens what each client loads; one only in a marketplace opens the
  // marketplace's entry. Task 7 joins both into one Details.
  if (row.lookup || !row.offer) {
    if (opener) opener(row, tr, how);
  } else {
    openOffer(row);
  }
}

async function openOffer(row) {
  let offer;
  try {
    offer = await getJson(`/api/offer${query({ kind: row.kind, id: row.offer })}`);
  } catch {
    const body = el("div", "body");
    body.append(el("p", "muted", "Could not load the details."));
    openInfo(KIND_WORDS[row.kind], rowTitle(row), body, [button("Retry", () => openOffer(row), "btn")]);
    return;
  }
  if (state.selected !== row.key) return; // another row was chosen meanwhile
  (row.kind === "skill" ? showSkill : showOffer)(offer, rowTitle(row));
}

function onRowKey(event, row, tr) {
  if (event.target !== tr) return;
  if (event.key === "Enter") {
    event.preventDefault();
    openRow(row, tr, "keyboard");
  } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const step = event.key === "ArrowDown" ? "nextElementSibling" : "previousElementSibling";
    let next = tr[step];
    while (next && !next.dataset.key) next = next[step]; // skip the group lines
    if (next) next.focus();
  }
}
