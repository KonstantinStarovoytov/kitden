// Entry point: the shell (rail, top bar), routing, theme, rescan and live updates.
import { postJson } from "./api.js";
import { $, $$, reportError, shortPath } from "./dom.js";
import { rollTo, transition } from "./motion.js";
import { renderAgents } from "./agents.js";
import { renderChanges } from "./changes.js";
import { renderGateway } from "./gateway.js";
import { renderMap } from "./map.js";
import { renderOverview } from "./overview.js";
import { closePanel, initPanel, isPanelOpen } from "./panel.js";
import { latestChanges } from "./parts.js";
import { busy, data, go, loadShared, parseHash, reload, setRenderer, setState, state } from "./store.js";

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
  shownView = state.view;
  const main = $("#main");
  main.replaceChildren();
  const place = PLACES[state.view] || PLACES.overview;
  place.render(main);
  document.title = `${place.title} · Agent setup`;
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
  $("#nav-items").textContent = data.map ? String(data.map.rows.length) : "";
  const gateway = overview && overview.gateway;
  $("#nav-around").textContent = gateway && gateway.total > gateway.through ? `${gateway.total - gateway.through} around` : "";
  // Changes still in effect, the ones Undo can take back.
  const changes = latestChanges(data.changes || []).filter((e) => e.state === "verified").length;
  rollTo($("#nav-changes"), changes || "");

  const where = $("#where");
  const projects = data.projects || [];
  if (where.options.length !== projects.length + 1) {
    where.replaceChildren(new Option("Everywhere", ""));
    for (const project of projects) {
      const label = `${shortPath(project.path)}${project.exists ? "" : " (folder missing)"}`;
      where.append(new Option(label, project.id));
    }
  }
  where.value = state.project;
  if ($("#q") !== document.activeElement) $("#q").value = state.q;
}

async function refresh() {
  await reload();
  $("#scanned").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  renderPlace();
}

// Theme: follows the system until the switch is used; the new theme spreads in a circle.
const THEME_KEY = "agentsetup-theme";
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

function listen() {
  const events = new EventSource("/api/events");
  events.addEventListener("rescan_started", () => $("#topbar").classList.add("scanning"));
  events.addEventListener("rescan_finished", () => {
    $("#topbar").classList.remove("scanning");
    if (!busy.change) refresh().catch(reportError);
  });
}

function start() {
  let saved = null;
  try { saved = localStorage.getItem(THEME_KEY); } catch { saved = null; }
  applyTheme(saved);
  Object.assign(state, parseHash(location.hash));
  setRenderer(renderPlace);

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-view]");
    if (!link) return;
    event.preventDefault();
    go(link.dataset.view);
  });
  window.addEventListener("hashchange", () => {
    const next = parseHash(location.hash);
    if (next.view !== state.view || next.project !== state.project) go(next.view, next);
  });
  $("#where").addEventListener("change", (event) => {
    setState({ project: event.target.value, selected: null });
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
