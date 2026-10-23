// Page state, data cache and navigation. The URL hash keeps the state, so links and Back work:
// #library?kind=<kind>&show=<mine|new|all>&category=<name>&attention=1&project=<id>&q=<text>
import { getJson, query } from "./api.js";
import { transition } from "./motion.js";

export const VIEWS = ["overview", "library", "gateway", "changes", "agents"];
// Places the Library replaced, and the choice each one opens it on.
export const OLD_VIEWS = { map: "mine", discover: "new" };
const SHOWS = ["mine", "new", "all"];
export const state = {
  view: "overview", kind: "mcp_server", show: "mine", category: "", attention: false, project: "", q: "", selected: null,
};
// A change is being applied or undone: live rescans wait so the result can morph in.
export const busy = { change: false };
let idleListener = () => {};
export function onIdle(fn) { idleListener = fn; }
export function setBusy(value) {
  busy.change = value;
  if (!value) idleListener();
}
// When the last full reload started, so a skipped rescan can tell whether it was covered;
// when the last reload with no failed read ended, and whether the latest one had a failure.
export const freshness = { reloadStartedAt: 0, lastGoodRead: null, lastReadFailed: false };
// scope: the project each read was for. readAt: when each read last worked.
// errorScope: the project each failed read was for.
export const data = {
  clients: null, projects: null, overview: null, map: null, gateway: null, changes: null, setupServer: null,
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

// Old #map and #discover addresses open the Library on "Installed" and "New"; the Load
// map's "Needs attention" filter (only=problems) carries over.
export function parseHash(hash) {
  const [place, rest] = String(hash || "").replace(/^#/, "").split("?");
  const params = new URLSearchParams(rest || "");
  const old = OLD_VIEWS[place];
  const show = params.get("show");
  let kind = params.get("kind") || "mcp_server";
  if (place === "discover") kind = kind === "skill" ? "skill" : "plugin";
  return {
    view: old ? "library" : VIEWS.includes(place) ? place : "overview",
    kind,
    show: old || (SHOWS.includes(show) ? show : "mine"),
    category: params.get("category") || "",
    attention: params.get("attention") === "1" || (place === "map" && params.get("only") === "problems"),
    project: params.get("project") || "",
    q: params.get("q") || "",
  };
}

export function hashFor(s) {
  const library = s.view === "library"
    ? { kind: s.kind, show: s.show === "mine" ? "" : s.show, category: s.category, attention: s.attention ? "1" : "" }
    : {};
  return `#${s.view}${query({ ...library, project: s.project, q: s.q })}`;
}

// A new place or project gets its own history entry, so Back returns to it; tabs, filters
// and search only replace the current one.
function writeHash(addEntry = false) {
  try {
    if (addEntry) history.pushState(null, "", hashFor(state));
    else history.replaceState(null, "", hashFor(state));
  } catch { /* not a normal page */ }
}

function show(moving) {
  if (moving) transition(() => { renderPlace(); document.getElementById("content").scrollTop = 0; }, "place-change");
  else renderPlace();
}

// Change place or filters. Place changes cross-fade; filter changes are instant.
export function go(view, params = {}) {
  const moving = view !== state.view;
  const newProject = params.project !== undefined && params.project !== state.project;
  Object.assign(state, { view }, params);
  writeHash(moving || newProject);
  show(moving);
}

export function setState(params) {
  const newProject = params.project !== undefined && params.project !== state.project;
  Object.assign(state, params);
  writeHash(newProject);
}

// Back, Forward or an edited address: take the state from the address without a new entry.
export function followAddress(next) {
  const moving = next.view !== state.view;
  Object.assign(state, next, { selected: null });
  show(moving);
}

export function projectPath() {
  const found = (data.projects || []).find((p) => p.id === state.project);
  return found ? found.path : "";
}

// A read for a project (scope) is dropped if another project is shown by the time it answers.
async function guarded(name, url, apply, scope) {
  const notShown = () => scope !== undefined && scope !== state.project;
  try {
    const value = await getJson(url);
    if (notShown()) return;
    apply(value);
    data.scope[name] = scope;
    data.readAt[name] = Date.now();
    delete data.errors[name];
    delete data.errorScope[name];
  } catch (error) {
    if (notShown()) return;
    data.errors[name] = error;
    data.errorScope[name] = scope;
  }
}

export async function loadShared() {
  await Promise.all([
    guarded("clients", "/api/clients", (v) => { data.clients = v; }),
    guarded("projects", "/api/projects", (v) => { data.projects = v; }),
    guarded("changes", "/api/changes", (v) => { data.changes = v; }),
  ]);
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
}

export async function loadChanges() {
  await guarded("changes", "/api/changes", (v) => { data.changes = v; });
}

export async function loadSetupServer() {
  await guarded("setupServer", "/api/setup-server", (v) => { data.setupServer = v; });
}

// Everything the current place shows, after a scan or a change. Nothing is read for a project
// no longer on the list.
export async function reload() {
  freshness.reloadStartedAt = performance.now();
  await loadShared();
  const reads = projectGone() ? [] : [loadOverview(), loadMap(), loadGateway()];
  await Promise.all([...reads, loadSetupServer()]);
  freshness.lastReadFailed = Object.keys(data.errors).length > 0;
  if (!freshness.lastReadFailed) freshness.lastGoodRead = Date.now();
}

// A page's Retry reads everything again, so the rail's time and its note are right after it.
export async function retry() {
  await reload();
  render();
}
