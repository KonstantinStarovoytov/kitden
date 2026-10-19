// Page state, data cache and navigation. The URL hash keeps the state, so links and Back work:
// #<view>?kind=<kind>&only=<filter>&project=<id>&q=<text>
import { getJson, query } from "./api.js";
import { transition } from "./motion.js";

export const VIEWS = ["overview", "map", "discover", "gateway", "changes", "agents"];
export const state = { view: "overview", kind: "mcp_server", only: "all", project: "", q: "", selected: null };
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
  errors: {}, scope: {}, readAt: {}, errorScope: {},
};

// A project's data only while that project is shown, so another project's data never shows.
export function current(name) {
  return data.scope[name] === state.project ? data[name] : null;
}

// The same for a failed read: another project's error is not this project's.
export function currentError(name) {
  return data.errorScope[name] === state.project ? data.errors[name] || null : null;
}

let renderPlace = () => {};
export function setRenderer(fn) { renderPlace = fn; }
export function render() { renderPlace(); }

export function parseHash(hash) {
  const [view, rest] = String(hash || "").replace(/^#/, "").split("?");
  const params = new URLSearchParams(rest || "");
  return {
    view: VIEWS.includes(view) ? view : "overview",
    kind: params.get("kind") || "mcp_server",
    only: params.get("only") || "all",
    project: params.get("project") || "",
    q: params.get("q") || "",
  };
}

export function hashFor(s) {
  const params = { project: s.project, q: s.q };
  if (s.view === "map") Object.assign(params, { kind: s.kind, only: s.only === "all" ? "" : s.only });
  if (s.view === "discover") params.kind = s.kind === "skill" ? "skill" : "";
  return `#${s.view}${query(params)}`;
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
  if (moving) transition(() => { renderPlace(); document.getElementById("content").scrollTop = 0; });
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
  if (state.project && !(data.projects || []).some((p) => p.id === state.project)) {
    state.project = "";
    writeHash();
  }
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

// Everything the current place shows, after a scan or a change.
export async function loadSetupServer() {
  await guarded("setupServer", "/api/setup-server", (v) => { data.setupServer = v; });
}

export async function reload() {
  freshness.reloadStartedAt = performance.now();
  await loadShared();
  await Promise.all([loadOverview(), loadMap(), loadGateway(), loadSetupServer()]);
  freshness.lastReadFailed = Object.keys(data.errors).length > 0;
  if (!freshness.lastReadFailed) freshness.lastGoodRead = Date.now();
}
