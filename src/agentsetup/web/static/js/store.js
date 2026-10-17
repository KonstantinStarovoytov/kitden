// Page state, data cache and navigation. The URL hash keeps the state, so links and Back work:
// #<view>?kind=<kind>&only=<filter>&project=<id>&q=<text>
import { getJson, query } from "./api.js";
import { transition } from "./motion.js";

export const VIEWS = ["overview", "map", "gateway", "changes", "agents"];
export const state = { view: "overview", kind: "mcp_server", only: "all", project: "", q: "", selected: null };
// A change is being applied or undone: live rescans wait so the result can morph in.
export const busy = { change: false };
export const data = { clients: null, projects: null, overview: null, map: null, gateway: null, changes: null, errors: {} };

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

function writeHash() {
  try { history.replaceState(null, "", hashFor(state)); } catch { /* not a normal page */ }
}

// Change place or filters. Place changes cross-fade; filter changes are instant.
export function go(view, params = {}) {
  const moving = view !== state.view;
  Object.assign(state, { view }, params);
  writeHash();
  if (moving) transition(() => { renderPlace(); document.getElementById("content").scrollTop = 0; });
  else renderPlace();
}

export function setState(params) {
  Object.assign(state, params);
  writeHash();
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
  if (state.project && !(data.projects || []).some((p) => p.id === state.project)) state.project = "";
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
export async function reload() {
  await loadShared();
  await Promise.all([loadOverview(), loadMap(), loadGateway()]);
}
