// Page state, data cache and navigation. The URL hash keeps the state, so links and Back work:
// #library?kind=<plugin|instructions>&show=<mine|diff>&attention=1&view=<map|list>&project=<id>&q=<text>&sel=<kind>:<name>
import { getJson, query } from "./api.js";
import { transition } from "./motion.js";

export const VIEWS = ["overview", "library", "gateway", "changes", "agents"];
// Places the Library replaced: they open it on what is installed.
export const OLD_VIEWS = ["map", "discover"];
// The List shows what is installed, or only what differs between the clients. An old New or All
// gives way to the add panel: it opens on what is installed.
const SHOWS = ["mine", "diff"];
// The places with a Map and a List. The address keeps the choice as `view=map|list`; the state
// keeps it as `mode`, because `view` names the place.
const MODE_PLACES = ["gateway", "library"];
const MODES = ["map", "list"];
// An old Library address names a kind and no view (`#library?kind=hook`): the Library had one
// table then. Each kind now lives here: MCP servers on the Gateway's List, hooks and marketplaces on
// the Library's map, the rest on its List. The Library's tabs are Plugins and skills ("plugin", for
// every kind but instructions) and Instructions (libraryKind).
const OLD_KINDS = { mcp_server: { view: "gateway", mode: "list" }, hook: { mode: "map" }, marketplace: { mode: "map" } };
// With no choice in the address, a page opens in List past this many blocks in its middle column.
export const MAP_AT = 15;
// The kinds of item the address can select: `sel=mcp_server:github`, `sel=tool:github/push_files`,
// `sel=client:codex`, `sel=group:outside` (a map's group block, its id without `group:`).
export const SEL_KINDS = ["mcp_server", "plugin", "skill", "hook", "marketplace", "instructions", "tool", "client", "group"];
// `selected` is the item picked on any page, { kind, name }, or null. `mode`: "map", "list" or
// "" (no choice).
export const state = {
  view: "overview", kind: "plugin", show: "mine", category: "", attention: false, mode: "", project: "", q: "", selected: null,
};

// The Library's tab for a kind: Instructions, or Plugins and skills for any other.
export const libraryKind = (kind) => (kind === "instructions" ? "instructions" : "plugin");

// What a page shows: the choice in the address, else List past MAP_AT blocks, else Map.
export function viewMode(s, count) {
  if (s.mode) return s.mode;
  return count > MAP_AT ? "list" : "map";
}

// Map or List, as the Gateway page drew it last ("" before it drew either): Details and the
// effect of an Apply ask which one shows.
export const gatewayShows = { mode: "" };
// The same for the Library: its address names that view with a kind (hashFor).
export const libraryShows = { mode: "" };

// A change is being applied or undone: live rescans wait so the result can morph in.
export const busy = { change: false };
let idleListener = () => {};
export function onIdle(fn) { idleListener = fn; }
// `fn()` each time a change starts or stops being written. Returns the way to stop.
const busyListeners = new Set();
export function onBusy(fn) {
  busyListeners.add(fn);
  return () => busyListeners.delete(fn);
}
export function setBusy(value) {
  busy.change = value;
  // A drawing that breaks must not stop the change.
  for (const fn of [...busyListeners]) {
    try { fn(); } catch (error) { console.error(error); }
  }
  if (!value) idleListener();
}
// When the last full reload started, so a skipped rescan can tell whether it was covered;
// when the last reload with no failed read ended, and whether the latest one had a failure.
export const freshness = { reloadStartedAt: 0, lastGoodRead: null, lastReadFailed: false };
// scope: the project each read was for. readAt: when each read last worked.
// errorScope: the project each failed read was for.
export const data = {
  clients: null, projects: null, overview: null, map: null, gateway: null, changes: null, setupServer: null, libraryMap: null, instructionsMap: null,
  progress: null, // where the first scan is, from /api/progress and its events
  errors: {}, scope: {}, readAt: {}, errorScope: {},
};

// A project's data only while that project is shown, so another project's data never shows.
// A project no longer on the list shows none.
export function current(name) {
  return data.scope[name] === state.project && !projectGone() ? data[name] : null;
}

// The picked project is no longer on the list Kitden read. It stays picked, and the page says
// so: it is never silently swapped for All projects.
export function projectGone() {
  return Boolean(state.project) && data.projects !== null && !data.projects.some((p) => p.id === state.project);
}

// The same for a failed read: another project's error is not this project's.
export function currentError(name) {
  return data.errorScope[name] === state.project ? data.errors[name] || null : null;
}

let renderPlace = () => {};
export function setRenderer(fn) { renderPlace = fn; }
export function render() { renderPlace(); }

// What app.js does once another project is picked: close Details, read the project, draw it.
let readProject = async () => {};
export function setSwitcher(fn) { readProject = fn; }

// Pick another project (All projects is ""). The selection goes, the address gets a new entry so
// Back returns, and the page reads the new project. It is done when that read is.
export async function switchProject(id) {
  if (id === state.project) return;
  setState({ project: id, selected: null });
  await readProject();
}

// "mcp_server:github" as { kind, name }: a known kind, then a name that is not empty (it may hold
// ":" too). Anything else is null.
export function parseSel(text) {
  const [kind, ...rest] = String(text || "").split(":");
  const name = rest.join(":");
  return SEL_KINDS.includes(kind) && name ? { kind, name } : null;
}

export function selFor(selected) {
  return selected ? `${selected.kind}:${selected.name}` : "";
}

// A selected tool's name, "github/push_files", as { server, tool }: split at the first "/", so a
// tool name may hold "/" too. Null without both parts.
export function toolSel(name) {
  const text = String(name || "");
  const at = text.indexOf("/");
  return at > 0 && at < text.length - 1 ? { server: text.slice(0, at), tool: text.slice(at + 1) } : null;
}

export function sameSel(a, b) {
  return selFor(a) === selFor(b);
}

// Old #map and #discover addresses open the Library on "Installed" and "New"; the Load
// map's "Needs attention" filter (only=problems) carries over.
export function parseHash(hash) {
  const [place, rest] = String(hash || "").replace(/^#/, "").split("?");
  const params = new URLSearchParams(rest || "");
  const old = OLD_VIEWS.includes(place);
  const show = params.get("show");
  const moved = oldLibraryLink(place, params);
  const view = moved ? moved.view || "library" : old ? "library" : VIEWS.includes(place) ? place : "overview";
  const mode = moved ? moved.mode : params.get("view");
  return {
    view,
    kind: libraryKind(params.get("kind")),
    show: !old && SHOWS.includes(show) ? show : "mine",
    category: params.get("category") || "",
    attention: params.get("attention") === "1" || (place === "map" && params.get("only") === "problems"),
    mode: MODE_PLACES.includes(view) && MODES.includes(mode) ? mode : "",
    project: params.get("project") || "",
    q: params.get("q") || "",
    selected: parseSel(params.get("sel")),
  };
}

// Where an old Library address (oldLibraryLink above) lands, or null for any other address.
function oldLibraryLink(place, params) {
  if (place !== "library" || !params.get("kind") || params.get("view")) return null;
  return OLD_KINDS[params.get("kind")] || { mode: "list" };
}

// An address that is an old one: the page writes its new form in its place.
export function isOldAddress(hash) {
  const [place, rest] = String(hash || "").replace(/^#/, "").split("?");
  return Boolean(OLD_VIEWS.includes(place) || oldLibraryLink(place, new URLSearchParams(rest || "")));
}

// The Library's address reads back as it is: a kind with no view is an old address, so a kind
// always comes with a view. With no choice made, the first tab (Plugins and skills) is left out,
// and Instructions names the view the page drew last (the List before it drew either).
export function hashFor(s) {
  const library = s.view === "library" ? libraryWords(s) : {};
  const mode = MODE_PLACES.includes(s.view) ? s.mode || library.view || "" : "";
  return `#${s.view}${query({ ...library, view: mode, project: s.project, q: s.q, sel: selFor(s.selected) })}`;
}

function libraryWords(s) {
  const kind = s.kind === "plugin" && s.mode !== "list" ? "" : s.kind;
  const view = kind && !s.mode ? libraryShows.mode || "list" : "";
  return { kind, show: s.show === "mine" ? "" : s.show, category: s.category, attention: s.attention ? "1" : "", view };
}

// A new place or project gets its own history entry, so Back returns to it; tabs, filters
// and search only replace the current one.
function writeHash(addEntry = false) {
  try {
    if (addEntry) history.pushState(null, "", hashFor(state));
    else history.replaceState(null, "", hashFor(state));
  } catch { /* not a normal page */ }
}

// A place change keeps the rail and the top bar still. The Gateway rises on its own (head, then its
// map or List), so its change only fades the old page out (style.css).
// The Library's map rises the same way; its List does not.
const RISES_ON_ITS_OWN = (s) => s.view === "gateway" || (s.view === "library" && s.mode !== "list");
function show(moving) {
  if (moving) transition(() => { renderPlace(); document.getElementById("content").scrollTop = 0; }, RISES_ON_ITS_OWN(state) ? "map-entrance" : "place-change");
  else renderPlace();
  if (moving && state.view === "library") openLibraryMap();
}

// A place opened with a selection (goTo, Back, Forward or a link) opens that item's Details once,
// when the place has drawn it. Any other change of place or filter opens nothing, and a panel the
// person opens first drops it (panel.js).
export const arrival = { pending: false };

// The selection to open now, or null. It is used up either way, so a redraw never opens Details
// again and takes the focus.
export function takeArrival() {
  const selected = arrival.pending ? state.selected : null;
  arrival.pending = false;
  return selected;
}

// Change place or filters. The selection stays for the next page, but nothing opens.
export function go(view, params = {}) {
  arrival.pending = false;
  place(view, params);
}

// The Library tab and choice that show a selected item: its kind (place() turns it into its tab,
// or the Gateway for an MCP server), under Installed, no search, on the List.
export function libraryChoice(selected) {
  return { kind: selected.kind, show: "mine", category: "", attention: false, q: "", mode: "list" };
}

// Open a place with an item selected; the place opens its Details. The project stays, unless
// `project` names another one: it is switched to and read first. `mode` picks Map or List there.
export async function goTo(view, selected, { project, mode } = {}) {
  if (project !== undefined && project !== state.project) await switchProject(project);
  arrival.pending = Boolean(selected);
  place(view, { selected, ...(view === "library" && selected ? libraryChoice(selected) : {}), ...(mode ? { mode } : {}) });
}

// Place changes cross-fade; filter changes are instant. The Map or List choice belongs to its
// place: another place starts without one, unless `params` brings one. A switch between Map and
// List gets its own history entry, so Back switches back.
function place(view, params) {
  ({ view, params } = newPlace(view, params));
  const moving = view !== state.view;
  const newProject = params.project !== undefined && params.project !== state.project;
  const newMode = params.mode !== undefined && params.mode !== state.mode;
  Object.assign(state, { view }, moving ? { mode: "" } : {}, params);
  writeHash(moving || newProject || newMode);
  show(moving);
}

// Where a place change lands: the Library's MCP servers are on the Gateway's List now, and any
// other kind opens its Library tab.
function newPlace(view, params) {
  if (view !== "library" || params.kind === undefined) return { view, params };
  if (params.kind === "mcp_server") return { view: "gateway", params: { ...params, kind: "plugin", mode: "list" } };
  return { view, params: { ...params, kind: libraryKind(params.kind) } };
}

export function setState(params) {
  const newProject = params.project !== undefined && params.project !== state.project;
  Object.assign(state, params);
  writeHash(newProject);
}

// Back, Forward or an edited address: take the state from the address without a new entry. Its
// selection opens as an arrival does.
export function followAddress(next, { draw = true } = {}) {
  const moving = next.view !== state.view;
  Object.assign(state, next);
  arrival.pending = Boolean(next.selected);
  if (draw) show(moving);
}

// The same from the address itself. Null for one that is not a page (like the skip link's
// #main); else whether it is the state shown already, whether the project changed, and whether
// that is a project switch in place: on the Gateway, staying there, the page is drawn once the
// project is read (app.js refreshForProject), not before. An old #map or #discover address opens
// the Library and the address says so.
export function followHash(hash) {
  const view = String(hash || "").replace(/^#/, "").split("?")[0];
  const old = isOldAddress(hash);
  if (!VIEWS.includes(view) && !OLD_VIEWS.includes(view)) return null;
  const next = parseHash(hash);
  const same = ["view", "project", "kind", "show", "category", "attention", "mode", "q"].every((key) => next[key] === state[key])
    && sameSel(next.selected, state.selected);
  const newProject = next.project !== state.project;
  const inPlace = !same && newProject && next.view === "gateway" && state.view === "gateway";
  if (!same) followAddress(next, { draw: !inPlace });
  if (old) setState({});
  return { same, newProject, inPlace };
}

export function projectPath() {
  const found = (data.projects || []).find((p) => p.id === state.project);
  return found ? found.path : "";
}

// A read for a project (scope) is dropped if another project is shown by the time it answers, or
// if `outdated()` says a newer read has begun. It says whether its answer was taken.
async function guarded(name, url, apply, scope, outdated = () => false) {
  const notShown = () => (scope !== undefined && scope !== state.project) || outdated();
  try {
    const value = await getJson(url);
    if (notShown()) return false;
    apply(value);
    data.scope[name] = scope;
    data.readAt[name] = Date.now();
    delete data.errors[name];
    delete data.errorScope[name];
    return true;
  } catch (error) {
    if (notShown()) return false;
    data.errors[name] = error;
    data.errorScope[name] = scope;
    return false;
  }
}

// The shared read while it runs: a read for the picked project waits for it, to learn whether
// the project is still on the list.
let sharedRead = null;

export async function loadShared() {
  const read = Promise.all([
    guarded("clients", "/api/clients", (v) => { data.clients = v; }),
    guarded("projects", "/api/projects", (v) => { data.projects = v; }),
    guarded("changes", "/api/changes", (v) => { data.changes = v; }),
  ]);
  sharedRead = read;
  await read;
  if (sharedRead === read) sharedRead = null;
}

// Run `read` once a shared read that is running has answered (at once when none runs), and
// not at all for a project no longer on the list.
export function afterShared(read) {
  const run = () => (projectGone() ? undefined : read());
  return sharedRead ? sharedRead.then(run) : Promise.resolve(run());
}

export async function loadOverview() {
  const { project } = state;
  await guarded("overview", `/api/overview${query({ project })}`, (v) => { data.overview = v; }, project);
}

export async function loadMap() {
  const { project } = state;
  await guarded("map", `/api/map${query({ project })}`, (v) => { data.map = v; }, project);
}

export async function loadGateway() {
  const { project } = state;
  await guarded("gateway", `/api/gateway-view${query({ project })}`, (v) => { data.gateway = v; }, project);
  markGatewayData();
}

// A performance mark for the map probe (Part 4.1): both reads the Gateway draws from have
// answered, once per page load.
function markGatewayData() {
  if (data.gateway && data.setupServer && !performance.getEntriesByName("kitden:gateway-data").length) {
    performance.mark("kitden:gateway-data");
  }
}

// The Library's maps (its tabs: plugins and skills, and instruction files) are read only while the
// Library shows (reload) and when it opens. `fresh`: no reload ran without them since they were
// last read, and both reads worked. `turn` counts the reads and the reloads that skip them: an
// answer to an older turn is dropped, so it never replaces or marks newer data.
const libraryMapRead = { fresh: false, running: null, turn: 0 };
const LIBRARY_READS = ["libraryMap", "instructionsMap"];

export async function loadLibraryMap() {
  const { project } = state;
  const turn = ++libraryMapRead.turn;
  const outdated = () => turn !== libraryMapRead.turn;
  const worked = await Promise.all([
    guarded("libraryMap", `/api/library-map${query({ project })}`, (v) => { data.libraryMap = v; }, project, outdated),
    guarded("instructionsMap", `/api/instructions-map${query({ project })}`, (v) => { data.instructionsMap = v; }, project, outdated),
  ]);
  if (!outdated()) libraryMapRead.fresh = worked.every(Boolean);
}

// Read the Library's map when it may be out of date (one read at a time); null when it is not.
export function readLibraryMap() {
  if (libraryMapRead.fresh && LIBRARY_READS.every((name) => current(name))) return null;
  if (!libraryMapRead.running) {
    const read = afterShared(loadLibraryMap).finally(() => { if (libraryMapRead.running === read) libraryMapRead.running = null; });
    libraryMapRead.running = read;
  }
  return libraryMapRead.running;
}

// The Library opens: a map that may be out of date is read, and the page is drawn again with the
// answer while the Library still shows.
function openLibraryMap() {
  const read = readLibraryMap();
  if (read) read.then(() => { if (state.view === "library") renderPlace(); }).catch((error) => console.error(error));
}

export async function loadChanges() {
  await guarded("changes", "/api/changes", (v) => { data.changes = v; });
}

export async function loadSetupServer() {
  await guarded("setupServer", "/api/setup-server", (v) => { data.setupServer = v; });
  markGatewayData();
}

// Everything the current place shows, after a scan or a change (the Library's map only on the
// Library). Nothing is read for a project no longer on the list.
export async function reload() {
  freshness.reloadStartedAt = performance.now();
  await loadShared();
  const library = state.view === "library";
  if (!library) Object.assign(libraryMapRead, { fresh: false, turn: libraryMapRead.turn + 1, running: null });
  const reads = projectGone() ? [] : [loadOverview(), loadMap(), loadGateway(), ...(library ? [loadLibraryMap()] : [])];
  await Promise.all([...reads, loadSetupServer()]);
  // The Library's maps count only while the Library shows: they are not read elsewhere.
  freshness.lastReadFailed = Object.keys(data.errors).some((name) => !LIBRARY_READS.includes(name) || state.view === "library");
  if (!freshness.lastReadFailed) freshness.lastGoodRead = Date.now();
}

// A page's Retry reads everything again, so the rail's time and its note are right after it.
export async function retry() {
  await reload();
  render();
}
