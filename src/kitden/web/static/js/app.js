// Entry point: the shell (rail, top bar), routing, theme, rescan and live updates.
import { postJson } from "./api.js";
import { $, $$, reportError } from "./dom.js";
import { rollTo, transition } from "./motion.js";
import { renderAgents } from "./agents.js";
import { renderChanges } from "./changes.js";
import { renderGateway } from "./gateway.js";
import { morphOnNextRender, renderMap } from "./map.js";
import { renderOverview } from "./overview.js";
import { closePanel, initPanel, isPanelOpen } from "./panel.js";
import { latestChanges } from "./parts.js";
import {
  busy, data, followAddress, freshness, go, loadShared, onIdle, parseHash, reload, setRenderer, setState, state, VIEWS,
} from "./store.js";

const PLACES = {
  overview: { title: "Overview", render: renderOverview },
  map: { title: "Load map", render: renderMap },
  gateway: { title: "Gateway", render: renderGateway },
  changes: { title: "Changes", render: renderChanges },
  agents: { title: "Agents", render: renderAgents },
};

let shownView = null;

function renderPlace() {
  if (shownView !== state.view && isPanelOpen()) closePanel({ instant: true, keepSelection: true, focus: false });
  const samePlace = shownView === state.view;
  shownView = state.view;
  const main = $("#main");
  // A redraw of the same place keeps keyboard focus on the same row.
  const focusedRow = samePlace && main.contains(document.activeElement) ? document.activeElement.closest("tr[data-key]") : null;
  const rowKey = focusedRow ? focusedRow.dataset.key : null;
  main.replaceChildren();
  const place = PLACES[state.view] || PLACES.overview;
  place.render(main);
  if (rowKey) {
    const row = $$("tr[data-key]", main).find((tr) => tr.dataset.key === rowKey);
    if (row) row.focus({ preventScroll: true });
  }
  document.title = `${place.title} · Kitden`;
  for (const link of $$(".nav a")) {
    if (link.dataset.view === state.view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  renderShell();
}

// Rail counters and the Where list follow the data.
function renderShell() {
  const overview = data.overview;
  rollTo($("#nav-attention"), overview && overview.attention.length ? overview.attention.length : "");
  // Changes still in effect, the ones Undo can take back.
  const changes = latestChanges(data.changes || []).filter((e) => e.state === "verified").length;
  rollTo($("#nav-changes"), changes || "");

  // Keep the picker compact; full paths are available on hover.
  const where = $("#where");
  const projects = data.projects || [];
  const signature = JSON.stringify(projects.map(({ id, path, exists }) => [id, path, exists]));
  if (where.dataset.projects !== signature) {
    where.replaceChildren(new Option("Global", ""));
    for (const project of projects) {
      const name = project.path.split("/").filter(Boolean).pop() || project.path;
      const option = new Option(`${name}${project.exists ? "" : " (folder missing)"}`, project.id);
      option.title = project.path;
      where.append(option);
    }
    where.dataset.projects = signature;
  }
  where.title = projects.find((project) => project.id === state.project)?.path || "Global setup";
  where.value = state.project;
  if ($("#q") !== document.activeElement) $("#q").value = state.q;
}

async function refresh() {
  await reload();
  $("#scanned").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  renderPlace();
}

// Theme: follows the system until the switch is used; the new theme spreads in a circle.
const THEME_KEY = "kitden-theme";
const OLD_THEME_KEY = "agentsetup-theme"; // the working name; read once so the choice carries over
function currentTheme() {
  const set = document.documentElement.dataset.theme;
  if (set) return set;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
function applyTheme(theme) {
  if (theme) document.documentElement.dataset.theme = theme;
  $("#theme").textContent = currentTheme() === "dark" ? "Light theme" : "Dark theme";
}
function switchTheme(event) {
  const next = currentTheme() === "dark" ? "light" : "dark";
  try { localStorage.setItem(THEME_KEY, next); } catch { /* private window */ }
  const t = transition(() => applyTheme(next), "theme-switch");
  if (!t) return;
  const x = event.clientX || innerWidth / 2;
  const y = event.clientY || innerHeight / 2;
  const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  t.ready.then(() => document.documentElement.animate(
    { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
    { duration: 520, easing: "cubic-bezier(0.77, 0, 0.175, 1)", pseudoElement: "::view-transition-new(root)" },
  )).catch(() => {});
}

async function rescan() {
  const bar = $("#topbar");
  $("#rescan").disabled = true;
  bar.classList.add("scanning");
  try {
    await postJson("/api/rescan");
    await refresh();
  } finally {
    bar.classList.remove("scanning");
    $("#rescan").disabled = false;
  }
}

// A live rescan redraws the page, except while a change runs or someone types in a form:
// then it waits, and runs once they are done if nothing newer was loaded meanwhile.
let missedAt = 0;

function typing() {
  const active = document.activeElement;
  return Boolean(active && $("#main").contains(active) && /^(INPUT|SELECT|TEXTAREA)$/.test(active.tagName));
}

function liveRefresh() {
  if (busy.change || typing()) {
    missedAt = performance.now();
    return;
  }
  missedAt = 0;
  refresh().catch(reportError);
}

function catchUp() {
  if (missedAt && missedAt > freshness.reloadStartedAt) liveRefresh();
  else missedAt = 0;
}

function listen() {
  const events = new EventSource("/api/events");
  events.addEventListener("rescan_started", () => $("#topbar").classList.add("scanning"));
  events.addEventListener("rescan_finished", () => {
    $("#topbar").classList.remove("scanning");
    liveRefresh();
  });
  onIdle(() => setTimeout(catchUp, 800));
  $("#main").addEventListener("focusout", () => setTimeout(() => { if (!typing()) catchUp(); }, 0));
}

// Back, Forward or an edited address. Unknown places (like the skip link's #main) are ignored.
function fromAddress() {
  const view = location.hash.replace(/^#/, "").split("?")[0];
  if (!VIEWS.includes(view)) return;
  const next = parseHash(location.hash);
  if (["view", "project", "kind", "only", "q"].every((key) => next[key] === state[key])) return;
  const newProject = next.project !== state.project;
  followAddress(next);
  if (newProject) refresh().catch(reportError);
}

function start() {
  let saved = null;
  try { saved = localStorage.getItem(THEME_KEY) || localStorage.getItem(OLD_THEME_KEY); } catch { saved = null; }
  applyTheme(saved);
  Object.assign(state, parseHash(location.hash));
  setRenderer(renderPlace);

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-view]");
    if (!link) return;
    event.preventDefault();
    go(link.dataset.view);
  });
  window.addEventListener("hashchange", fromAddress);
  window.addEventListener("popstate", fromAddress);
  $(".skip").addEventListener("click", (event) => {
    event.preventDefault();
    $("#main").focus();
  });
  $("#where").addEventListener("change", (event) => {
    setState({ project: event.target.value, selected: null });
    // On the Load map, each cell turns into its state in the new scope instead of jumping.
    if (state.view === "map") morphOnNextRender();
    refresh().catch(reportError);
  });
  $("#q").addEventListener("input", (event) => {
    const q = event.target.value.trim();
    if (state.view !== "map" && q) go("map", { q });
    else go(state.view, { q });
  });
  document.addEventListener("keydown", (event) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (event.key === "/" && !typing && !isPanelOpen()) {
      event.preventDefault();
      $("#q").focus();
    }
  });
  $("#theme").addEventListener("click", switchTheme);
  $("#rescan").addEventListener("click", () => rescan().catch(reportError));
  initPanel();

  renderPlace();
  loadShared()
    .then(refresh)
    .catch(reportError);
  listen();
}

start();
