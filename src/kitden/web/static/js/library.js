// Library: what each client loads, as a Map (library-map.js) or a List. The List (spec 5.4, frame
// L3) has the Map's two tabs. Plugins and skills: one row per source, then its plugins, skills and
// hooks; a plugin folds over what it holds. Instructions: one row per file. There is one column per
// client found on this computer, and a cell says On, Off, Via Claude Code, + Add, or nothing. The
// server builds the rows and cells (views/library.py library_list). A row opens the same Details as
// the map (library-details.js); a cell's "+ Add" only adds a row to the tray.
import { getJson, query } from "./api.js";
import { button, el, gridKey, icon, plural } from "./dom.js";
import { filesGroup, INSTRUCTIONS_HINT, LEDE, leaveLibraryMap, letGoLibraryMap, libraryDetails, libraryMode, libraryThing, renderLibraryMap, setListOnly } from "./library-map.js";
import { glidePill, modeSwitch, switchedNow } from "./map-page.js";
import { CALM, afterOldPage, animate, entrance, glide, land, reducedMotion, rise } from "./motion.js";
import { projectNote } from "./offer.js";
import { isPanelOpen, openInfo, panelState, previewButton, projectLabel, review } from "./panel.js";
import { banner, CLIENT_NAMES, flag, folderName, lookFor, mark, morphSocket, scopeBar, setHint, skeleton, socket, sourceLines, staleNote } from "./parts.js";
import { afterShared, arrival, current, currentError, data, freshness, go, libraryKind, libraryShows, projectPath, render, retry, sameSel, setState, state, takeArrival } from "./store.js";

// The List's tabs, as on the Map, and what it shows of Plugins and skills.
const TABS = [["plugin", "Plugins and skills"], ["instructions", "Instructions"]];
const SHOW = [["mine", "Installed"], ["diff", "Differences"]];
const LIST_HINT = "One row per item, one column per client. Right opens a plugin, Enter opens Details.";
// The quiet word after a row's name, and after a part's: what kind of thing it is.
const KIND_WORDS = { skill: "Skill", hook: "Hook" };
// A row of "Commands and agents" (its `category`).
const COMMAND_WORDS = { command: "Command", agent: "Agent" };
const PART_WORDS = { skill: "Skill", command: "Command", agent: "Agent", hook: "Hook", mcp_server: "MCP server" };
// A client's column is this wide; the name takes the rest.
const CELL_W = 150;
const NO_DIFFERENCES = "No differences between your clients";
const ADD_MISSING = "Add missing plugins and skills…";
// An empty tab: what is missing, and where it comes from.
const NOTHING = {
  plugin: ["No plugins or skills in any client", "Plugins and skills you add in Claude Code, Codex or Cursor will show up here."],
  instructions: ["No instruction files in any client", "Instruction files you add for Claude Code, Codex or Cursor will show up here."],
};
// Tabs where Kitden adds nothing: no "Add missing plugins and skills…" and no line about where
// an add goes.
export const hasAdds = (kind) => libraryKind(kind) !== "instructions";
// Typing waits this long after the last key before asking the server.
const TYPING_MS = 200;
// A tab or filter waits this long for its rows before it changes the page; a slower answer
// dims the old list while it waits, so a skeleton never flashes between two lists.
const SWAP_WAIT_MS = 300;
// Rows on screen that move when the list changes; the rest just appear.
const SETTLE_ROWS = 40;
const RISE_ROWS = 12;

// What each cell showed last time, so a change can morph from the old state to the new one.
export let previousCells = {};
let morphNext = false;
export function morphOnNextRender() { morphNext = true; }

// A Details title: the source too when two rows share the name ("superpowers · cursor-public").
export function rowTitle(row) {
  return row.same_name && row.source ? `${row.name} · ${row.source}` : row.name;
}

// What a cell's add asks the review for: that one client, and with scope "project" only the
// project picked at the top.
export function previewFor(add, client, scope = "all") {
  const params = add.action === "skill.install" ? { skill: add.skill }
    : add.action === "mcp.add" ? { item: add.item } : { plugin: add.plugin };
  if (scope === "project") params.project = state.project;
  return { action: add.action, targets: [{ client }], params };
}

// The review's note: a twin it would load as well, and in a project where the add goes: that
// project only, every project, or where the client keeps it instead (`project_hint`).
export function noteFor(add, project, scope = "all") {
  const where = scope === "project" ? `Adds to ${projectLabel(project)} only.`
    : project ? add.project_hint || projectNote(project) : null;
  return [add.warn, where].filter(Boolean).join(" ") || null;
}

// The two places an add with a project place can go, the project first (as the move choice).
export function addChoices() {
  return [
    { label: "Add to this project…", scope: "project", look: "btn primary" },
    { label: "Add for all projects…", scope: "all", look: "btn" },
  ];
}

// The two choices of an add that asks where it goes, as buttons. Each says "In preview" while
// its row waits in the tray, and takes no press then.
export function addChoiceButtons(add, client) {
  return addChoices().map((choice) => previewButton(choice.label, previewFor(add, client, choice.scope), {
    note: noteFor(add, state.project, choice.scope), look: choice.look,
  }));
}

// An add: in a project, one that can go into the project asks where first; a project's own
// skill goes into the project with no choice; any other goes to the tray at once.
export function startAdd(add, client, row) {
  if (add.project_only) {
    return review(previewFor(add, client, "project"), { note: noteFor(add, state.project, "project") });
  }
  if (!state.project || !add.project_place) {
    return review(previewFor(add, client), { note: noteFor(add, state.project) });
  }
  const folder = projectLabel(state.project);
  const body = el("div", "body");
  body.append(el("p", "muted", `${CLIENT_NAMES[client] || client} can load it in ${folder} only, or in all projects.`));
  // The primary button sits last, as the move choice draws it.
  openInfo("Add", rowTitle(row), body, addChoiceButtons(add, client).reverse());
  return null;
}

// What a screen reader hears for a cell's button: its words first, then what, from where (when
// names repeat) and to which client. In a project an add that asks where ends with "…"; a
// project's own skill names the project.
export function addName(row, client, add, project) {
  const name = row.same_name && row.source ? `${row.name} (${row.source})` : row.name;
  const what = { "+ Add skills": `Add skills from ${name}`, "+ Add the plugin": `Add the plugin with ${name}` }[add.label] || `Add ${name}`;
  const to = `${what} to ${CLIENT_NAMES[client] || client}`;
  if (add.project_only) return `${to} in ${projectLabel(project)}`;
  if (project && add.project_place) return `${to}…`;
  return `${to}${project ? " for all projects" : ""}`;
}

// A quiet line above the List: in a project, where an Add goes. Null on a tab with no adds.
export function scopeLine(project, rows, kind = null) {
  if (!project || rows.length === 0 || !hasAdds(kind)) return null;
  const adds = rows.flatMap((r) => Object.values(r.cells || {}).map((c) => c.add).filter(Boolean));
  const own = "This project's own skills add into this project.";
  if (adds.length && adds.every((add) => add.project_only)) return own;
  const line = adds.some((add) => add.project_place)
    ? "An Add asks: this project, or all projects. Adds without that choice go to all projects."
    : "Adding puts an item in all projects.";
  return adds.some((add) => add.project_only) ? `${line} ${own}` : line;
}

// One cell: a button for the one action, a state, or nothing. An empty cell says why in its hover
// text, and a screen reader hears it.
export function cellNode(row, client) {
  const cell = row.cells[client];
  if (cell.add) {
    const node = button(cell.add.label, () => startAdd(cell.add, client, row), "btn small add");
    node.setAttribute("aria-label", addName(row, client, cell.add, state.project));
    node.dataset.focus = `add:${row.key}:${client}`;
    return node;
  }
  if (cell.state === "none") {
    const node = el("span", "socket s-none");
    node.append(el("span", "sr-only", cell.reason || "Not added"));
    if (cell.reason) node.title = cellHint(cell);
    return node;
  }
  // Kept from the last good read of a file that now fails: a dashed dot, and the hover says when.
  const node = socket({ state: cell.state, where: cell.where, word: cell.word, label: cell.reason, stale: Boolean(cell.stale_at) });
  const hint = cellHint(cell);
  if (hint) node.title = hint;
  return node;
}

// A cell's hover text: where it applies (in full, where the cell may cut it), how the client
// gets the item, then why: "This project. Through Codex's folder. <reason>".
export function cellHint(cell) {
  return [cell.where, cell.route, cell.reason].filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(". ");
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

// The tab shown: Instructions, or Plugins and skills for any other kind.
const currentKind = () => libraryKind(state.kind);

// The question for the server, for the shown tab or (`choice`) one about to show. Instructions has
// no Differences.
function asking(choice = state) {
  const kind = libraryKind(choice.kind);
  return {
    project: choice.project, kind, show: kind === "plugin" && choice.show === "diff" ? "diff" : "mine",
    q: choice.q, attention: kind === "plugin" && choice.attention,
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
  job.promise = getJson(`/api/library-list${query(params)}`).then(
    (answer) => { if (latest()) cache = { key, at, readAt: Date.now(), answer, asked, error: null, errorKey: null, failedAt: 0 }; },
    (error) => { if (latest()) Object.assign(cache, { error, errorKey: key, failedAt: at }); },
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

// The pressed tab or Installed / Differences choice is marked at once, and its mark slides there,
// so the press answers right away; the list follows when its rows are in.
function markChoice(node) {
  const box = node && node.parentElement;
  if (!box) return;
  for (const choice of box.children) if (choice.tagName === "BUTTON") choice.setAttribute("aria-pressed", String(choice === node));
  if (box.classList.contains("map-tabs")) glidePill(box, node, "library-tabs-map");
  else glide(box, node, "library-show", { duration: 280 });
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
// Nothing is read for a project no longer on the list (afterShared).
export function loadLibrary() {
  if (state.view !== "library") return Promise.resolve();
  clearTimeout(timer);
  return afterShared(() => read({}));
}

// Read the tab another place is about to open, so it is drawn inside the place change and a
// client tile can fly to its column there (Overview counts and cards).
export function loadLibraryFor(choice) {
  return afterShared(() => read(choice));
}

// The page: its head (the title, and Map | List at its right), then the Map or the List. The Map
// returns what the top search found there (app.js shows the chip); the List searches its rows.
// A view that Map | List brings comes in from 6 px below.
export function renderLibrary(main, { again = false } = {}) {
  const switched = switchedNow();
  const mode = libraryMode();
  // The view drawn, so a switch that lands late draws nothing; with no choice in the address, the
  // address names it with the tab (hashFor), so a reload or Back shows the same view.
  libraryShows.mode = mode;
  if (!state.mode) setState({});
  const head = el("div", "page-head");
  head.append(el("h1", null, "Library"));
  const letGo = () => { letGoLibraryMap(); letGoList(); };
  const seg = modeSwitch("library", mode, { old: () => main.querySelector(mode === "map" ? ":scope > div.map" : ":scope > .table-scroll"), letGo, shows: () => libraryShows.mode });
  head.append(seg);
  main.append(head);
  let found = null;
  if (mode === "map") found = renderLibraryMap(main, { head, again, switched });
  else {
    leaveLibraryMap();
    renderList(main);
    if (switched) rise([...main.children].slice(1), { delay: afterOldPage() });
  }
  glidePill(seg, seg.querySelector('[aria-pressed="true"]'), "library-view");
  return found;
}

// The List: the Map's lede, tabs and scope bar, then the filters and the rows.
function renderList(main) {
  const kind = currentKind();
  const tabs = listTabs(kind);
  main.append(el("p", "lede", LEDE), tabs, scopeBar(folderName(projectPath())));
  glidePill(tabs, tabs.querySelector('[aria-pressed="true"]'), "library-tabs-map");
  setHint(kind === "plugin" ? LIST_HINT : INSTRUCTIONS_HINT);

  const key = cacheKey();
  // The page's first reload reads the rows with everything else (app.js refresh).
  if (freshness.reloadStartedAt) schedule(key);
  const sameProject = cache.answer && cache.asked.project === state.project;
  // Rows of another tab or project are never shown under this one; other filters wait in place.
  const answer = sameProject && cache.asked.kind === kind ? cache.answer : null;
  const asked = answer ? cache.asked : asking();
  const fresh = cache.key === key && cache.at >= freshness.reloadStartedAt;
  const failed = cache.errorKey === key ? cache.error : null;
  // Before any early return: an empty List after a project switch still moves its Details on.
  followProject(kind);
  if (answer && !answer.columns.length) {
    main.append(noClients());
    return;
  }
  const tools = toolbar(kind, answer);
  if (tools) main.append(tools);
  const show = tools && tools.querySelector(".seg");
  if (show) glide(show, show.querySelector('[aria-pressed="true"]'), "library-show", { duration: 280 });

  if (!answer) {
    main.append(failed ? banner("the library", retry) : skeleton("table", 1));
    return;
  }
  if (failed) main.append(staleNote(cache.readAt));
  const hidden = hiddenLine(answer.columns);
  if (hidden) main.append(hidden);
  for (const note of answer.notes) main.append(el("p", "note", note));
  main.append(sourceBox());
  // A selection that arrived (from another place, Back, Forward or a link) opens once its rows
  // are in; its group unfolds for it.
  const arrived = fresh ? arrivalIn(answer) : null;
  const rows = listRows(answer, searchOpen(answer, asked.q), onList.folded);
  if (!rows.length) {
    main.append(emptyState(asked));
    finish(rows);
    return;
  }
  const line = scopeLine(state.project, rows.filter((r) => r.cells), asked.kind);
  if (line) main.append(el("p", "group-note", line));
  // A hidden column is still in `columns`, marked; it is not drawn.
  const columns = answer.columns.filter((c) => !c.hidden);
  const grid = listGrid(rows, columns, kind);
  const scroller = el("div", "table-scroll");
  scroller.append(grid);
  main.append(scroller);
  finish(rows);
  entrance("library", [grid]);
  if (arrived) showArrived(arrived);
}

// Another project drawn in place: Details a row opened follow the same item, drawn for that
// project, or close when it is gone (library-details.js). It waits for the tab's map read of that
// project, which the Details are drawn from (app.js reads it beside the List's rows).
function followProject(kind) {
  const read = kind === "plugin" ? "libraryMap" : "instructionsMap";
  const failed = Boolean(currentError(read));
  if (onList.project === state.project || (!current(read) && !failed)) return;
  const had = onList.project !== null && onList.selected;
  onList.project = state.project;
  if (!had) return;
  // A map read that failed for this project gives nothing to draw them from: they let go.
  const id = !failed && libraryThing(onList.selected) ? onList.selected : null;
  if (!id) onList.selected = null;
  libraryDetails(id, { follow: true });
}

// "Plugins and skills" | "Instructions", as on the Map: a press lets go of the row whose Details
// show, and reads the other tab first.
function listTabs(kind) {
  const box = el("div", "seg sm map-tabs");
  box.setAttribute("role", "group");
  box.setAttribute("aria-label", "Show");
  for (const [id, label] of TABS) {
    const choice = button(label, () => id !== currentKind() && toTab(id, choice), "");
    choice.setAttribute("aria-pressed", String(kind === id));
    choice.dataset.focus = `tab:${id}`;
    box.append(choice);
  }
  return box;
}

function toTab(id, choice) {
  letGoList();
  return choose({ kind: id, selected: null }, choice);
}

// Plugins and skills: Installed | Differences, "Needs attention" when something does (Overview
// links use it), and "Add missing plugins and skills…". Instructions has none of these.
function toolbar(kind, answer) {
  if (kind !== "plugin") return null;
  const bar = el("div", "toolbar");
  const seg = el("div", "seg");
  seg.setAttribute("role", "group");
  seg.setAttribute("aria-label", "Show");
  for (const [id, label] of SHOW) {
    const b = button(label, () => choose({ show: id, selected: null }, b), "");
    b.setAttribute("aria-pressed", String(asking().show === id));
    b.dataset.focus = `show:${id}`;
    seg.append(b);
  }
  bar.append(seg);
  if (answer && (answer.attention || state.attention)) {
    const toggle = button(`Needs attention · ${answer.attention}`, () => choose({ attention: !state.attention, selected: null }), "btn small toggle");
    toggle.setAttribute("aria-pressed", String(state.attention));
    toggle.dataset.focus = "filter:attention";
    bar.append(toggle);
  }
  // One review that adds what one client loads in the project and another lacks; under All
  // projects, what one client has for all projects and another lacks.
  const missing = button(ADD_MISSING, () => review({ action: "project.align", targets: [], params: { project: state.project || null, chosen: null } }), "btn small");
  missing.dataset.focus = "add:missing";
  bar.append(missing);
  return bar;
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

// A column's small "−": hides it on this page only. There is none when no other client Kitden
// could read (no `note`) would stay shown: the server would show every column again. Focus goes
// to the next column's "−", or to Show when there is none.
export function hideButton(column, shown) {
  if (!shown.some((c) => !c.note && c.id !== column.id)) return null;
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

// No client found: which clients Kitden looks for; their folders and the demo command wait
// behind Details, as paths and commands do on every page. The Overview leaves out its own link.
export function noClients({ overview = true } = {}) {
  const box = el("div", "empty");
  box.append(el("strong", null, "Kitden found no AI coding clients."), el("p", null, "It looks for Claude Code, Codex and Cursor."));
  box.append(button("Details", showLookFor, "btn"));
  if (overview) box.append(button("Open Overview", () => go("overview"), "btn"));
  return box;
}

function showLookFor() {
  const body = el("div", "body");
  const list = el("ul", "looks-for");
  for (const { name, where } of lookFor(data.clients)) {
    const item = el("li", null, `${name} · `);
    item.append(el("span", "mono", where));
    list.append(item);
  }
  const where = el("section");
  where.append(list, el("p", "muted", "It finds a client by that folder or by its command."));
  const demo = el("section");
  demo.append(el("p", null, "To try Kitden on a sample setup, run this in a terminal:"), el("pre", "command", "kitden demo"));
  body.append(where, demo);
  openInfo("Clients", "What Kitden looks for", body, [], { mono: false });
}

// The first scan's progress while the top bar shows its line (app.js), else null: a source
// line shows with that line and after the same wait, so a quick start never blinks one here.
let sources = null;

// The sources still read that change this tab (parts.js), one quiet line each above the List,
// after the files Kitden could not read.
function sourceBox() {
  const box = el("div", "source-lines");
  for (const line of sourceLines(sources, currentKind())) box.append(el("p", "note", line));
  return box;
}

// The top bar's line shows, changes or goes (app.js showScan). When this tab's lines change,
// only they are drawn again, so no row slides. A line that goes fades and keeps its place until
// the page next draws (a rescan comes with every source that ends), so the List does not jump
// for it. True when this tab's lines changed.
export function showSources(progress) {
  const kind = currentKind();
  const before = sourceLines(sources, kind);
  const after = sourceLines(progress, kind);
  sources = progress;
  if (state.view !== "library" || after.join("\n") === before.join("\n")) return false;
  const box = document.querySelector("#main .source-lines");
  if (box && after.length) box.replaceWith(sourceBox());
  else if (box) box.classList.add("gone");
  return true;
}

// Nothing to show: a search, a filter or Differences that found nothing says how to go back;
// an empty tab says what shows up here.
export function emptyState(asked) {
  const box = el("div", "empty");
  if (asked.q) {
    box.append(el("strong", null, `Nothing matches “${asked.q}”`), button("Clear search", () => go("library", { q: "" })));
  } else if (asked.attention) {
    box.append(el("strong", null, "Nothing to show with this filter"), button("Show all", () => go("library", { attention: false })));
  } else if (asked.show === "diff") {
    box.append(el("strong", null, NO_DIFFERENCES), button("Show installed", () => go("library", { show: "mine" })));
  } else {
    const [title, line] = NOTHING[libraryKind(asked.kind)];
    box.append(el("strong", null, title), el("p", null, line));
  }
  return box;
}

// The List's rows, in order, from the answer: each group's row, then (unless it is `folded`) its
// items, and an open plugin's (`open`) parts under it. Each row: { id (the map's block id, so
// Details are the map's), key, parent, depth, kind, name, meta (the quiet words after the name),
// flags, cells (none on a group), sel (what the address selects it by), expanded (only on a row
// that folds), group (Enter folds it: a group with no Details), icon (a group's), source and
// same_name (an add's names) }.
export function listRows(answer, open = new Set(), folded = new Set()) {
  const rows = [];
  for (const group of answer.groups) {
    const id = groupId(group);
    const details = group.kind === "marketplace";
    const expanded = !folded.has(id);
    rows.push({ id, key: id, parent: null, depth: 0, kind: "group", name: group.name, meta: null, flags: [], cells: null, sel: details ? { kind: "marketplace", name: group.name } : null, expanded, group: !details, icon: group.icon });
    if (!expanded) continue;
    for (const item of group.items) {
      const itemId = `${item.kind === "file" ? "file" : "item"}:${item.id}`;
      const parts = item.parts || [];
      const opened = parts.length ? open.has(itemId) : undefined;
      const sel = item.lookup ? { kind: item.kind, name: item.lookup } : (item.names || []).length ? { kind: "instructions", name: item.names[0] } : null;
      rows.push({ id: itemId, key: itemId, parent: id, depth: 1, kind: item.kind, name: item.name, meta: itemWords(item), flags: item.flags || [], cells: item.cells, sel, expanded: opened, group: false, source: item.source, same_name: item.same_name, account: Boolean(item.account), reason: item.reason || null });
      if (!opened) continue;
      for (const part of parts) {
        const partId = `part:${item.id}:${part.key}:${part.name}`;
        rows.push({ id: partId, key: partId, parent: itemId, depth: 2, kind: "part", name: part.name, meta: PART_WORDS[part.kind], flags: part.flags || [], cells: part.cells, sel: null, group: false, source: part.source, same_name: part.same_name });
      }
    }
  }
  return rows;
}

// "Plugin · 4 items" (what Kitden read inside it; "Plugin" when it read nothing), "Skill", "Hook",
// "Command" or "Agent"; an instruction file has none.
function itemWords(item) {
  if (item.kind === "plugin") return item.count ? `Plugin · ${plural(item.count, "item", "items")}` : "Plugin";
  return KIND_WORDS[item.kind] || COMMAND_WORDS[item.category] || null;
}

// A group row's id: the map's (a group of files is the Instructions tab's own: library-map.js
// filesGroup), so folds stay per tab.
const groupId = (group) => (group.kind === "files" ? filesGroup(group.key) : `group:${group.key}`);

// The plugins open for this draw: the person's, and while searching, every plugin a part of which
// the search found (it stays as the person left it once the search ends).
function searchOpen(answer, q) {
  const text = (q || "").trim().toLowerCase();
  if (!text) return onList.open;
  const found = answer.groups.flatMap((g) => g.items).filter((i) => (i.parts || []).some((p) => p.name.toLowerCase().includes(text)));
  return new Set([...onList.open, ...found.map((i) => `item:${i.id}`)]);
}

// The List as the person left it: the open plugins, the folded groups, the row that takes the
// Tab key and the one whose Details show, kept across draws; and the rows drawn now, by id.
const onList = { open: new Set(), folded: new Set(), current: null, selected: null, project: null, nodes: new Map(), rows: new Map() };

// The Details of the row the List opened let go (Map | List).
function letGoList() {
  if (!onList.selected) return;
  onList.selected = null;
  libraryDetails(null);
}

// The tree grid: a head row with Name and the clients, then a row each. The arrows move, Right
// opens and Left folds, Enter opens Details (dom.js gridKey).
function listGrid(rows, columns, kind) {
  if (!rows.some((r) => r.id === onList.current)) onList.current = rows[0].id;
  const showing = isPanelOpen() && panelState.current && panelState.current.type === "library" ? panelState.current.id : null;
  if (onList.selected !== showing) onList.selected = null;
  const grid = el("div", "treegrid library-list");
  grid.setAttribute("role", "treegrid");
  grid.setAttribute("aria-label", kind === "plugin" ? "Plugins and skills by client" : "Instruction files by client");
  grid.style.setProperty("--tg-cols", `minmax(0, 1fr) repeat(${columns.length}, ${CELL_W}px)`);
  grid.append(headRow(columns));
  onList.nodes = new Map();
  onList.rows = new Map(rows.map((row) => [row.id, row]));
  setListOnly(rows.filter((row) => row.account).map(accountBlock));
  for (const row of rows) {
    const node = listRow(row, columns, { current: row.id === onList.current, selected: row.id === onList.selected });
    onList.nodes.set(row.id, node);
    grid.append(node);
  }
  // Keys on a row's own button stay that button's.
  grid.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey || !event.target.dataset.row) return;
    const next = gridKey(rows, rows.findIndex((r) => r.id === event.target.dataset.row), event.key);
    if (!next) return;
    event.preventDefault();
    const row = rows[next.at];
    if (next.toggle) toggleRow(row);
    else if (next.details) openRow(row);
    else focusRow(row.id);
  });
  return grid;
}

// Name, then each client: its tile (coming from the Overview, it flies here from its row), its
// name and its "−"; a client Kitden could not read says so under its name.
function headRow(columns) {
  const head = el("div", "tg-head");
  head.setAttribute("role", "row");
  head.append(gridCell("columnheader", null, "Name"));
  for (const column of columns) {
    const th = gridCell("columnheader", "col-head");
    const who = el("span", "who");
    const tile = mark(column.id);
    land(tile, `client-${column.id}`);
    who.append(tile, el("span", null, column.name));
    th.append(who);
    const hide = hideButton(column, columns);
    if (hide) th.append(hide);
    if (column.note) th.append(el("span", "muted", column.note));
    head.append(th);
  }
  return head;
}

function gridCell(role, className, text) {
  const node = el("div", className, text);
  node.setAttribute("role", role);
  return node;
}

// One row: a fold mark where it folds, a group's icon, the name, its flags and quiet words, then a
// cell per client. A click opens its Details, or folds it on the fold mark; a group with no
// Details folds.
function listRow(row, columns, { current, selected }) {
  const node = el("div", row.kind === "group" ? "tg-row group" : `tg-row ${row.kind === "part" ? "part" : "item"}`);
  node.setAttribute("role", "row");
  node.setAttribute("aria-level", String(row.depth + 1));
  if (row.expanded !== undefined) node.setAttribute("aria-expanded", String(row.expanded));
  node.setAttribute("aria-selected", String(selected));
  node.tabIndex = current ? 0 : -1;
  node.dataset.row = row.id;
  node.dataset.focus = `row:${row.id}`;
  const name = gridCell("gridcell", "tg-name");
  name.style.setProperty("--depth", String(row.depth));
  const caret = el("span", row.expanded === undefined ? "caret none" : "caret", "▸");
  caret.setAttribute("aria-hidden", "true");
  name.append(caret);
  if (row.icon) name.append(icon(row.icon, 13));
  const words = el("span", row.kind === "group" ? "words" : "words mono", row.name);
  words.title = row.name;
  name.append(words);
  // One flag per wording: three clients with the same note make one flag, not three.
  for (const f of row.flags.filter((f, i) => row.flags.findIndex((o) => o.text === f.text) === i)) name.append(flag(f));
  if (row.meta) name.append(el("span", "meta", row.meta));
  node.append(name);
  if (row.kind === "group") name.setAttribute("aria-colspan", String(columns.length + 1));
  else for (const column of columns) {
    const cell = gridCell("gridcell", "tg-cell");
    const before = morphNext && previousCells[row.key] && previousCells[row.key][column.id];
    cell.append(settle(row, column.id, before, current));
    node.append(cell);
  }
  node.addEventListener("click", (event) => {
    if (event.target.closest("button")) return;
    if (row.expanded !== undefined && (row.group || event.target.closest(".caret"))) toggleRow(row);
    else openRow(row);
  });
  return node;
}

// A cell after a verified change: a state that changed morphs from the old one; a state where a
// button was pings once. Unchanged cells, buttons and empty cells are drawn as they are. A cell's
// button takes the Tab key with its row.
function settle(row, client, before, current) {
  const cell = row.cells[client];
  const node = cellNode(row, client);
  if (cell.add) node.tabIndex = current ? 0 : -1;
  if (!before || before === cellKey(cell) || cell.add || cell.state === "none") return node;
  const [was, where, label] = before.split("|");
  if (label) {
    if (!reducedMotion.matches) node.classList.add("pulse");
    return node;
  }
  const old = socket({ state: was, where: where || null });
  old.title = node.title;
  const next = { state: cell.state, where: cell.where, word: cell.word, label: cell.reason, stale: Boolean(cell.stale_at) };
  setTimeout(() => morphSocket(old, next), reducedMotion.matches ? 0 : 260);
  return old;
}

// Rows are drawn: the morph is used up, and the next change morphs from what they show.
function finish(rows) {
  morphNext = false;
  previousCells = Object.fromEntries(rows.filter((r) => r.cells).map((r) => [r.key, Object.fromEntries(Object.entries(r.cells).map(([c, cell]) => [c, cellKey(cell)]))]));
}

const cellKey = (cell) => `${cell.state}|${cell.where || ""}|${cell.add ? cell.add.label : ""}`;

// Move the Tab key, and focus, to another row (and to its own buttons).
function focusRow(id) {
  onList.current = id;
  for (const [rowId, node] of onList.nodes) {
    const on = rowId === id;
    node.tabIndex = on ? 0 : -1;
    for (const cell of [...node.children].slice(1)) for (const control of [...cell.children]) if (control.tagName === "BUTTON") control.tabIndex = on ? 0 : -1;
    if (on) node.focus();
  }
}

// Fold or unfold a row: a plugin shows its parts; a group hides its rows.
function toggleRow(row) {
  const set = row.kind === "group" ? onList.folded : onList.open;
  if (set.has(row.id)) set.delete(row.id);
  else set.add(row.id);
  onList.current = row.id;
  render();
}

// A row's Details, beside the page: the same as the map's for that block. The address keeps the
// row's selection (no new history entry), so Back and a link return to it. The person's pick
// wins: an arrival whose rows come later opens nothing.
export function openRow(row) {
  arrival.pending = false;
  const id = detailsId(onList.rows.get(row.id) || row);
  onList.current = row.id;
  onList.selected = id;
  for (const [rowId, node] of onList.nodes) node.setAttribute("aria-selected", String(rowId === row.id));
  setState({ selected: row.sel });
  libraryDetails(id);
}

// The block whose Details a row opens: its own; a part the map does not draw (Kitden read nothing
// inside its plugin) opens its plugin's; a plugin Claude Code keeps in the account opens a small
// card of its own (accountCard).
function detailsId(row) {
  if (libraryThing(row.id)) return row.id;
  if (row.kind === "part") return row.parent;
  return row.id;
}

// The account card of a row Claude Code keeps in the account, for its Details.
function accountBlock(row) {
  const by = Object.fromEntries(Object.entries(row.cells || {}).filter(([, cell]) => cell.state !== "none").map(([client, cell]) => [client, BY_WORDS[cell.state] || cell.state]));
  return { id: row.id, kind: "account", name: row.name, reason: row.reason, item: { by } };
}
const BY_WORDS = { unk: "unknown" };

// The row an arrival names, or null (none, a panel is open, or the List has no such row): an item
// by its kind and full name, a skill inside a plugin by its own (its plugin opens for it), a
// marketplace by its name. Its group unfolds for it.
export function arrivalIn(answer) {
  const arrived = takeArrival();
  if (!arrived || isPanelOpen()) return null;
  const named = (kind, name) => Boolean(name) && sameSel({ kind, name }, arrived);
  // A file, a command or an agent goes by the names of the items it stands for.
  const isItem = (item) => named(item.kind, item.lookup) || (item.names || []).some((name) => named("instructions", name));
  for (const group of answer.groups) {
    const fold = groupId(group);
    if (group.kind === "marketplace" && named("marketplace", group.name)) {
      onList.folded.delete(fold);
      return fold;
    }
    for (const item of group.items) {
      const part = (item.parts || []).find((p) => named(p.kind, p.lookup));
      if (!isItem(item) && !part) continue;
      onList.folded.delete(fold);
      if (!part) return `${item.kind === "file" ? "file" : "item"}:${item.id}`;
      onList.open.add(`item:${item.id}`);
      return `part:${item.id}:${part.key}:${part.name}`;
    }
  }
  return null;
}

// An arrival: the row glows once and comes into view, and its Details open.
function showArrived(id) {
  const node = onList.nodes.get(id);
  if (!node) return;
  node.classList.add("arrive");
  if (node.scrollIntoView) requestAnimationFrame(() => node.scrollIntoView({ block: "nearest" }));
  const row = { id, sel: state.selected };
  focusRow(id);
  openRow(row);
}

// Smooth changes of the List. Before the page draws again it notes where each row on screen is;
// after, rows that stay slide from there to their new place, new rows rise in, and the other
// tab's list slides in from its side. Only transform and opacity move; with reduced motion
// nothing does.
let drawnKind = null;

function rowsOnScreen() {
  const rows = [];
  for (const [id, node] of onList.nodes) {
    if (!node.isConnected) continue;
    const box = node.getBoundingClientRect();
    if (box.bottom < 0) continue;
    if (box.top > innerHeight || rows.length >= SETTLE_ROWS) break;
    rows.push([id, node, box.top]);
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
  const order = TABS.map(([id]) => id);
  return Math.sign(order.indexOf(libraryKind(to)) - order.indexOf(libraryKind(from)));
}

const listShown = () => document.querySelector("#main .table-scroll");

export function snapshotRows() {
  if (!listShown()) return null;
  return { kind: drawnKind, tops: new Map(rowsOnScreen().map(([id, , top]) => [id, top])) };
}

export function settleRows(before) {
  const scroller = listShown();
  drawnKind = scroller ? currentKind() : null;
  if (!before || !before.kind || !scroller || reducedMotion.matches) return;
  const direction = tabDirection(before.kind, drawnKind);
  if (direction) {
    const frames = [{ opacity: 0, transform: `translateX(${8 * direction}px)` }, { opacity: 1, transform: "none" }];
    animate(scroller, frames, { duration: 220 });
    return;
  }
  const rows = rowsOnScreen();
  const byId = new Map(rows.map(([id, node]) => [id, node]));
  const { moved, entered } = rowMoves(before.tops, new Map(rows.map(([id, , top]) => [id, top])));
  for (const [id, dy] of moved) {
    animate(byId.get(id), [{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 260, easing: CALM });
  }
  entered.slice(0, RISE_ROWS).forEach((id, index) => {
    const frames = [{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }];
    animate(byId.get(id), frames, { duration: 200, delay: index * 20, fill: "backwards" });
  });
}
