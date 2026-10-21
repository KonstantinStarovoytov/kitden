// Library: what each client loads, and what you can add to it. One tab per kind, one column per
// client found on this computer. Each cell shows a state, the one action for that client, or a
// dash that says why not. The server builds the rows and cells (views/library.py).
import { getJson, query } from "./api.js";
import { button, el, tabKeys } from "./dom.js";
import { animate, entrance, glide, land, reducedMotion, rollTo, spring } from "./motion.js";
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
const SHOW = [["mine", "Installed"], ["new", "New"], ["all", "All"]];
const KIND_WORDS = { plugin: "Plugin", skill: "Skill" };
// The tab's name inside a sentence: "No MCP servers in any client", "No plugins to add".
const KIND_NOUNS = { mcp_server: "MCP servers", plugin: "plugins", skill: "skills", hook: "hooks", marketplace: "marketplaces" };
// Typing waits this long after the last key before asking the server.
const TYPING_MS = 200;
// A tab or filter waits this long for its rows before it changes the page; a slower answer
// dims the old list while it waits, so a skeleton never flashes between two lists.
const SWAP_WAIT_MS = 300;
// Rows on screen that move when the list changes; the rest just appear.
const SETTLE_ROWS = 40;
const RISE_ROWS = 12;

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
  return `${answer.more} more ${show === "mine" ? "in New" : "installed"} · Show all`;
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
  const what = { "+ Add skills": `Add skills from ${name}`, "+ Add the plugin": `Add the plugin with ${name}` }[add.label] || `Add ${name}`;
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
  const node = socket({ state: cell.state, where: cell.where, word: cell.word, label: cell.reason });
  if (cell.reason) node.title = cell.reason;
  return node;
}

// Columns hidden on this page. The choice stays in this browser only; a store that cannot be read
// means nothing is hidden. When it cannot be written (a private window), the choice is kept here,
// so "−" still works while the page is open.
const HIDDEN_KEY = "kitden-hidden-clients";
let hiddenHere = null;

export function hiddenClients() {
  if (hiddenHere) return [...hiddenHere];
  try {
    const list = JSON.parse(localStorage.getItem(HIDDEN_KEY));
    return Array.isArray(list) && list.every((id) => typeof id === "string") ? list : [];
  } catch {
    return [];
  }
}

export function setHidden(list) {
  try {
    localStorage.setItem(HIDDEN_KEY, JSON.stringify(list));
    hiddenHere = null;
  } catch {
    hiddenHere = [...list];
  }
}

// The kind tab shown: an unknown one from an old address falls back to the first tab.
const currentKind = () => asking().kind;

// The question for the server, for the shown tab or (`choice`) one about to show. Tabs without a
// catalog show only what is on this computer.
function asking(choice = state) {
  const kind = KINDS.some(([id]) => id === choice.kind) ? choice.kind : "mcp_server";
  const catalog = CATALOG.includes(kind);
  return {
    project: choice.project, kind, show: catalog ? choice.show : "mine", q: choice.q,
    category: catalog ? choice.category : "", attention: choice.attention,
    // Sorted, so the same choice made in another order is the same question.
    hidden: hiddenClients().sort().join(","),
  };
}

const cacheKey = () => JSON.stringify(asking());

// The last answer and what it was for. `at` is when its request was sent, so an answer asked for
// before a rescan or a change counts as old. A failed key is not asked again until the next reload.
let cache = { key: null, at: 0, readAt: 0, answer: null, asked: null, error: null, errorKey: null, failedAt: 0 };
let pending = null;
let timer = null;
let lastQ = null;
// Requests in the order they were sent: only the last one sent may change the cache.
let sent = 0;

function needsLoad(key) {
  const since = freshness.reloadStartedAt;
  if (pending && pending.key === key && pending.at >= since) return false;
  if (cache.errorKey === key && cache.failedAt >= since) return false;
  return !(cache.key === key && cache.at >= since);
}

// Ask the server (`asked`: the shown tab unless given). A newer request wins: only the answer to
// the last request sent is kept, and never over a newer answer. `draw` redraws the page when the
// answer is in; a caller that draws itself passes false.
function load(asked = asking(), draw = true) {
  const key = JSON.stringify(asked);
  if (pending && pending.key === key && pending.at >= freshness.reloadStartedAt) {
    if (!draw) pending.draw = false;
    return pending.promise;
  }
  const at = performance.now();
  const order = ++sent;
  const latest = () => order === sent && at >= cache.at;
  lastQ = asked.q;
  const params = { ...asked, attention: asked.attention ? "1" : "" };
  const job = { key, at, draw };
  job.promise = getJson(`/api/library${query(params)}`).then(
    (answer) => { if (latest()) cache = { key, at, readAt: Date.now(), answer, asked, error: null, errorKey: null, failedAt: 0 }; },
    (error) => { if (latest()) Object.assign(cache, { error, errorKey: key, failedAt: at }); },
  ).finally(() => {
    if (pending === job) pending = null;
    if (job.draw && state.view === "library" && cacheKey() === key) render();
  });
  pending = job;
  return job.promise;
}

// A row as the Library read it last, for Details drawn again after a change; null off the
// Library or when the row is gone.
export function shownRow(key) {
  if (state.view !== "library" || !cache.answer) return null;
  return cache.answer.rows.find((r) => r.key === key) || null;
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

// Read a tab (`choice`: state keys such as kind and show over the current state) without drawing,
// unless its answer is fresh already. Never rejects.
function read(choice) {
  const asked = asking({ ...state, ...choice });
  const fresh = cache.key === JSON.stringify(asked) && cache.at >= freshness.reloadStartedAt;
  return fresh ? Promise.resolve() : load(asked, false);
}

// Whether `promise` settles within `ms` (a failure counts as settled). It is not cancelled.
export function raceSlow(promise, ms) {
  return Promise.race([
    Promise.resolve(promise).then(() => true, () => true),
    new Promise((done) => setTimeout(() => done(false), ms)),
  ]);
}

// The pressed tab or Installed / New / All choice is marked at once, and its mark slides there,
// so the press answers right away; the list follows when its rows are in.
function markChoice(node) {
  const box = node && node.parentElement;
  if (!box) return;
  const attr = box.classList.contains("tabs") ? "aria-selected" : "aria-pressed";
  for (const choice of box.querySelectorAll(":scope > button")) choice.setAttribute(attr, String(choice === node));
  glide(box, node, box.classList.contains("tabs") ? "library-tabs" : "library-show");
}

// A tab or filter: read its rows first, so the list changes once, already full. The last
// choice wins when several are pressed before their rows are in.
let choosing = 0;
async function choose(params, pressed = null) {
  const mine = ++choosing;
  markChoice(pressed);
  const ready = read(params);
  if (!(await raceSlow(ready, SWAP_WAIT_MS))) {
    const list = document.querySelector("#main .table-scroll");
    if (list) list.classList.add("waiting");
    await ready;
  }
  if (mine === choosing) go("library", params);
}

// For a caller that draws the page itself once the shown tab is read (a reload, a change or a
// project switch), so the cells morph then and not before. Call it right after reload() starts.
export function loadLibrary() {
  if (state.view !== "library") return Promise.resolve();
  clearTimeout(timer);
  return read({});
}

// Read the tab another place is about to open, so it is drawn inside the place change and a
// client tile can fly to its column there (Overview counts and cards).
export function loadLibraryFor(choice) {
  return read(choice);
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
  const hidden = hiddenLine(answer.columns);
  if (hidden) main.append(hidden);
  for (const note of answer.notes) main.append(el("p", "note", note));
  const more = moreLine(answer, asked.show);
  const wantOpen = fresh && openNext;
  if (fresh) openNext = false;
  if (!answer.rows.length) {
    main.append(emptyState(asked, more));
    finish(answer.rows);
    return;
  }
  if (more) main.append(moreNode(more));
  // A hidden column is still in `columns`, marked; it is not drawn.
  const columns = answer.columns.filter((c) => !c.hidden);
  const groups = asked.show === "all" && CATALOG.includes(asked.kind);
  const table = buildTable(columns, answer.rows, groups, morphNext);
  const scroller = el("div", "table-scroll");
  scroller.append(table);
  main.append(scroller);
  finish(answer.rows);
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

// Rows are drawn: the morph is used up, and the next change morphs from what they show.
function finish(rows) {
  morphNext = false;
  previousCells = Object.fromEntries(rows.map((r) => [r.key, Object.fromEntries(Object.entries(r.cells).map(([c, cell]) => [c, cellKey(cell)]))]));
  previousFlags = Object.fromEntries(rows.map((r) => [r.key, r.flags.map((f) => ({ text: f.text, level: f.level }))]));
}

const cellKey = (cell) => `${cell.state}|${cell.where || ""}|${cell.add ? cell.add.label : ""}`;

// The counts the tabs showed last, so a new count rolls from the old one.
let lastCounts = null;

function tabs(counts, kind) {
  const box = el("div", "tabs");
  box.setAttribute("role", "tablist");
  for (const [id, label] of KINDS) {
    const tab = button(label, () => choose({ kind: id, category: "", selected: null }, tab), "");
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(kind === id));
    tab.dataset.kind = id;
    tab.dataset.focus = `tab:${id}`;
    if (counts) {
      const holder = el("span", "count roll");
      const old = lastCounts ? lastCounts[id] : undefined;
      holder.append(el("span", null, String(old === undefined ? counts[id] : old)));
      if (old !== undefined && old !== counts[id]) rollTo(holder, counts[id]);
      tab.append(holder);
    }
    box.append(tab);
  }
  if (counts) lastCounts = counts;
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
      const b = button(label, () => choose({ show: id, selected: null }, b), "");
      b.setAttribute("aria-pressed", String(state.show === id));
      b.dataset.focus = `show:${id}`;
      seg.append(b);
    }
    bar.append(seg);
    if (answer && (answer.categories.length || state.category)) bar.append(categoryPicker(answer.categories));
  }
  if (answer && (answer.attention || state.attention)) {
    const toggle = button(`Needs attention · ${answer.attention}`, () => choose({ attention: !state.attention, selected: null }), "btn small toggle");
    toggle.setAttribute("aria-pressed", String(state.attention));
    toggle.dataset.focus = "filter:attention";
    bar.append(toggle);
  }
  if (kind === "marketplace") {
    const add = button("Add a marketplace…", () => marketplaceForm(), "btn small");
    add.dataset.focus = "add:marketplace";
    bar.append(add);
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
  select.addEventListener("change", () => choose({ category: select.value, selected: null }));
  const box = el("label", "filter");
  if (chosen) box.classList.add("on");
  box.append(select);
  return box;
}

// "3 more in New · Show all": the words, then a button for the last part. The line goes
// away with the choice, so focus moves to that choice.
function moreNode(line) {
  const box = el("p", "more");
  const all = button("Show all", () => {
    go("library", { show: "all", selected: null });
    const choice = document.querySelector('#main [data-focus="show:all"]');
    if (choice) choice.focus();
  }, "btn ghost small");
  all.dataset.focus = "more:all";
  box.append(el("span", null, `${line.split(" · ")[0]} · `), all);
  return box;
}

// Save the choice, ask again (the server leaves out the rows only hidden clients have) and draw
// once the answer is in. Focus then goes to the first of `focus` that is on the page.
async function chooseHidden(list, focus) {
  setHidden(list);
  await loadLibrary();
  render();
  for (const key of focus.filter(Boolean)) {
    const node = document.querySelector(`#main [data-focus="${key}"]`);
    if (node) {
      node.focus();
      return;
    }
  }
}

// A column's small "−": hides it on this page only. The last shown column has none. Focus goes to
// the next column's "−", or to Show when there is none.
export function hideButton(column, shown) {
  if (shown.length < 2) return null;
  const at = shown.findIndex((c) => c.id === column.id);
  const next = shown[at + 1];
  const node = button("−", () => chooseHidden([...new Set([...hiddenClients(), column.id])], [next && `hide:${next.id}`, "hidden:show"]), "btn ghost small hide-col");
  node.setAttribute("aria-label", `Hide ${column.name}`);
  node.dataset.focus = `hide:${column.id}`;
  return node;
}

// "Hidden: Codex, Cursor · Show": Show brings every hidden column back. Null when none is hidden.
export function hiddenLine(columns) {
  const gone = columns.filter((c) => c.hidden);
  if (!gone.length) return null;
  const box = el("p", "more");
  const show = button("Show", () => chooseHidden([], [`hide:${gone[0].id}`]), "btn ghost small");
  show.dataset.focus = "hidden:show";
  box.append(el("span", null, `Hidden: ${gone.map((c) => c.name).join(", ")} · `), show);
  return box;
}

function noClients() {
  const box = el("div", "empty");
  box.append(el("strong", null, "Kitden found no AI coding clients."), button("Open Overview", () => go("overview"), "btn"));
  return box;
}

export function emptyState(asked, more) {
  const box = el("div", "empty");
  const label = KIND_NOUNS[asked.kind] || "items";
  if (more) {
    const where = asked.show === "mine" ? "installed" : "new";
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
    const cap = el("div", "col-head");
    const chip = el("span", "chip");
    const tile = mark(column.id);
    // Coming from the Overview, the client's tile flies here from its row.
    land(tile, `client-${column.id}`);
    chip.append(tile, el("span", null, column.name));
    cap.append(chip);
    const hide = hideButton(column, columns);
    if (hide) cap.append(hide);
    th.append(cap);
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
      tr.dataset.key = row.mine ? "group:installed" : "group:new";
      const td = el("td", null, row.mine ? "Installed" : "New");
      td.colSpan = columns.length + 1;
      tr.append(td);
      body.append(tr);
    }
    body.append(buildRow(columns, row, morph));
  }
  table.append(body);
  return table;
}

function buildRow(columns, row, morph) {
  const tr = el("tr");
  tr.tabIndex = 0;
  tr.dataset.key = row.key;
  tr.setAttribute("aria-selected", String(state.selected === row.key));
  tr.append(nameCell(row, morph));
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

// Line one: the name, the quiet meta text and the chevron, so a narrow row keeps them readable.
// Line two: the flags, then what it does; the flags have it to themselves when there is no
// description, and a row with neither has one line.
export function nameCell(row, morph) {
  const td = el("td");
  const line = el("div", "item");
  const name = el("span", "mono", row.name);
  name.title = row.name;
  line.append(name);
  const meta = metaText(row);
  if (meta) line.append(el("small", "meta", meta));
  line.append(opens());
  td.append(line);
  const sub = el("div", "sub");
  // One flag per wording: three clients with the same note make one flag, not three.
  const shown = row.flags.filter((f, i) => row.flags.findIndex((o) => o.text === f.text) === i);
  for (const f of shown) sub.append(flag(f));
  // A flag that a verified change resolved shrinks away instead of vanishing.
  const oldFlags = morph ? previousFlags[row.key] || [] : [];
  for (const f of oldFlags.filter((o) => !shown.some((n) => n.text === o.text))) {
    const node = flag(f);
    node.classList.add("gone");
    node.setAttribute("aria-hidden", "true");
    sub.append(node);
    setTimeout(() => node.remove(), 400);
  }
  if (row.description) {
    const desc = el("div", "desc", row.description);
    desc.title = row.description;
    sub.append(desc);
  }
  if (sub.children.length) td.append(sub);
  return td;
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
  const next = { state: cell.state, where: cell.where, word: cell.word, label: cell.reason };
  setTimeout(() => morphSocket(old, next), reducedMotion.matches ? 0 : 260);
  return old;
}

function openRow(row, tr, how) {
  state.selected = row.key;
  for (const other of tr.parentElement.querySelectorAll('tr[aria-selected="true"]')) other.setAttribute("aria-selected", "false");
  tr.setAttribute("aria-selected", "true");
  // A row on this computer opens what each client loads; one only in a marketplace opens the
  // marketplace's entry.
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
  (row.kind === "skill" ? showSkill : showOffer)(offer, row);
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

// Smooth changes of the list. Before the page draws again it notes where each row on screen is;
// after, rows that stay slide from there to their new place, new rows rise in, and another tab's
// list slides in from the side of that tab. Only transform and opacity move; with reduced motion
// nothing does.
let drawnKind = null;

function rowsOnScreen(table) {
  const rows = [];
  for (const tr of table.querySelectorAll("tbody tr[data-key]")) {
    const box = tr.getBoundingClientRect();
    if (box.bottom < 0) continue;
    if (box.top > innerHeight || rows.length >= SETTLE_ROWS) break;
    rows.push([tr, box.top]);
  }
  return rows;
}

export function rowMoves(before, after) {
  const moved = [];
  const entered = [];
  for (const [key, top] of after) {
    if (!before.has(key)) entered.push(key);
    else if (Math.abs(before.get(key) - top) >= 1) moved.push([key, Math.round(before.get(key) - top)]);
  }
  return { moved, entered };
}

// 1 when `to` is a tab to the right of `from`, -1 to the left, 0 for the same tab.
export function tabDirection(from, to) {
  const order = KINDS.map(([id]) => id);
  return Math.sign(order.indexOf(to) - order.indexOf(from));
}

export function snapshotRows() {
  const table = document.querySelector("#main table.library");
  if (!table) return null;
  return { kind: drawnKind, tops: new Map(rowsOnScreen(table).map(([tr, top]) => [tr.dataset.key, top])) };
}

export function settleRows(before) {
  const table = document.querySelector("#main table.library");
  drawnKind = table ? currentKind() : null;
  if (!before || !before.kind || !table || reducedMotion.matches) return;
  const direction = tabDirection(before.kind, drawnKind);
  if (direction) {
    const frames = [{ opacity: 0, transform: `translateX(${8 * direction}px)` }, { opacity: 1, transform: "none" }];
    animate(table.closest(".table-scroll"), frames, { duration: 220 });
    return;
  }
  const rows = rowsOnScreen(table);
  const byKey = new Map(rows.map(([tr]) => [tr.dataset.key, tr]));
  const { moved, entered } = rowMoves(before.tops, new Map(rows.map(([tr, top]) => [tr.dataset.key, top])));
  for (const [key, dy] of moved) {
    animate(byKey.get(key), [{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 260, easing: spring() });
  }
  entered.slice(0, RISE_ROWS).forEach((key, index) => {
    const frames = [{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }];
    animate(byKey.get(key), frames, { duration: 200, delay: index * 20, fill: "backwards" });
  });
}
