// Page state, data cache and navigation. The URL hash keeps the state, so links and Back work:
// #<view>?kind=<kind>&only=<filter>&project=<id>&q=<text>
import { getJson, query } from "./api.js";
import { transition } from "./motion.js";

export const VIEWS = ["overview", "map", "gateway", "changes", "agents"];
export const state = { view: "overview", kind: "mcp_server", only: "all", project: "", q: "", selected: null };
// A change is being applied or undone: live rescans wait so the result can morph in.
export const busy = { change: false };
let idleListener = () => {};
export function onIdle(fn) { idleListener = fn; }
export function setBusy(value) {
  busy.change = value;
  if (!value) idleListener();
}
// When the last full reload started, so a skipped rescan can tell whether it was covered.
export const freshness = { reloadStartedAt: 0 };
export const data = { clients: null, projects: null, overview: null, map: null, gateway: null, changes: null, setupServer: null, errors: {} };

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

async function guarded(name, url, apply) {
  try {
    apply(await getJson(url));
    delete data.errors[name];
  } catch (error) {
    data.errors[name] = error;
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
  await guarded("overview", `/api/overview${query({ project: state.project })}`, (v) => { data.overview = v; });
}

export async function loadMap() {
  await guarded("map", `/api/map${query({ project: state.project })}`, (v) => { data.map = v; });
}

export async function loadGateway() {
  await guarded("gateway", `/api/gateway-view${query({ project: state.project })}`, (v) => { data.gateway = v; });
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
}
