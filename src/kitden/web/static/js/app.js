// Entry point: the shell (rail, top bar), routing, theme, rescan and live updates.
import { getJson, postJson } from "./api.js";
import { $, $$, busyWhile, focusKey, reportError } from "./dom.js";
import { glide, rollTo, transition } from "./motion.js";
import { renderAgents } from "./agents.js";
import { renderChanges } from "./changes.js";
import { renderGateway } from "./gateway.js";
import { loadLibrary, morphOnNextRender, renderLibrary } from "./library.js";
import { renderOverview } from "./overview.js";
import { closePanel, initPanel, isPanelOpen } from "./panel.js";
import { latestChanges, scanLine } from "./parts.js";
import {
  busy, current, data, followAddress, freshness, go, loadShared, OLD_VIEWS, onIdle, parseHash, reload, setRenderer, setState, state, VIEWS,
} from "./store.js";

const PLACES = {
  overview: { title: "Overview", render: renderOverview },
  library: { title: "Library", render: renderLibrary },
  gateway: { title: "Gateway", render: renderGateway },
  changes: { title: "Changes", render: renderChanges },
  agents: { title: "Agents", render: renderAgents },
};

let shownView = null;
// What a redraw can hand focus back to: controls with a data-focus key, and table rows.
const FOCUSABLE = "[data-focus], tr[data-key]";

function renderPlace() {
  if (shownView !== state.view && isPanelOpen()) closePanel({ instant: true, keepSelection: true, focus: false });
  const samePlace = shownView === state.view;
  shownView = state.view;
  const main = $("#main");
  // A redraw of the same place keeps keyboard focus on the same row, tab, filter or menu.
  const focused = samePlace && main.contains(document.activeElement) ? document.activeElement.closest(FOCUSABLE) : null;
  const key = focused ? focusKey(focused) : null;
  main.replaceChildren();
  const place = PLACES[state.view] || PLACES.overview;
  place.render(main);
  if (key) {
    const same = $$(FOCUSABLE, main).find((node) => focusKey(node) === key);
    if (same) same.focus({ preventScroll: true });
  }
  document.title = `${place.title} · Kitden`;
  for (const link of $$(".nav a")) {
    if (link.dataset.view === state.view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  glide($(".nav"), $('.nav a[aria-current="page"]'), "nav");
  renderShell();
}

// Rail counters and the Where list follow the data.
function renderShell() {
  const overview = current("overview");
  rollTo($("#nav-attention"), overview && overview.attention.length ? overview.attention.length : "");
  // Changes still in effect, the ones Undo can take back.
  const changes = latestChanges(data.changes || []).filter((e) => e.state === "verified").length;
  rollTo($("#nav-changes"), changes || "");
  // The time of the last reload where every read worked, and a note when the latest one failed.
  const { lastGoodRead, lastReadFailed } = freshness;
  const time = lastGoodRead ? new Date(lastGoodRead).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "…";
  $("#scanned").textContent = `${time}${lastReadFailed ? " · could not refresh" : ""}`;

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
  where.closest(".where-box").classList.toggle("project", Boolean(state.project));
  if ($("#q") !== document.activeElement) $("#q").value = state.q;
}

// A scope change cross-fades the page (the Library morphs its cells instead). The Library's
// rows are read beside everything else, so the page draws once with both.
async function refresh({ fade = false } = {}) {
  await Promise.all([reload(), loadLibrary()]);
  if (fade) transition(renderPlace);
  else renderPlace();
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
  if ($("#rescan").dataset.working) return;
  await busyWhile($("#rescan"), (async () => {
    await postJson("/api/rescan");
    await refresh();
  })());
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

// The first scan says what it still reads, and a bar under the top bar fills as each step ends.
// It shows only when the wait is long enough to notice, so a quick start never blinks.
const SCAN_LINE_DELAY_MS = 1000;
let scanLineTimer = null;

function showScan(view) {
  const line = scanLine(view);
  const bar = $("#topbar");
  const status = $("#scan-status");
  if (!line) {
    clearTimeout(scanLineTimer);
    scanLineTimer = null;
    bar.classList.remove("progress");
    status.textContent = "";
    return;
  }
  status.textContent = line.text;
  bar.style.setProperty("--scan-done", String(line.share));
  if (!bar.classList.contains("progress") && !scanLineTimer) {
    scanLineTimer = setTimeout(() => {
      scanLineTimer = null;
      if ($("#scan-status").textContent) bar.classList.add("progress");
    }, SCAN_LINE_DELAY_MS);
  }
}

function listen() {
  const events = new EventSource("/api/events");
  events.addEventListener("scan_progress", (event) => {
    try { showScan(JSON.parse(event.data)); } catch { /* a broken message changes nothing */ }
  });
  events.addEventListener("rescan_started", () => $("#topbar").classList.add("scanning"));
  // How many steps of a running change are done; the review's Apply button counts them.
  events.addEventListener("change_progress", (event) => {
    let detail = null;
    try { detail = JSON.parse(event.data); } catch { return; }
    document.dispatchEvent(new CustomEvent("kitden:progress", { detail }));
  });
  events.addEventListener("rescan_finished", () => {
    $("#topbar").classList.remove("scanning");
    liveRefresh();
  });
  onIdle(() => setTimeout(catchUp, 800));
  $("#main").addEventListener("focusout", () => setTimeout(() => { if (!typing()) catchUp(); }, 0));
}

// Back, Forward or an edited address. Unknown places (like the skip link's #main) are ignored;
// an old #map or #discover address opens the Library and the address says so.
function fromAddress() {
  const view = location.hash.replace(/^#/, "").split("?")[0];
  const old = Boolean(OLD_VIEWS[view]);
  if (!VIEWS.includes(view) && !old) return;
  const next = parseHash(location.hash);
  const same = ["view", "project", "kind", "show", "category", "attention", "q"].every((key) => next[key] === state[key]);
  const newProject = next.project !== state.project;
  if (!same) followAddress(next);
  if (old) setState({});
  if (!same && newProject) refresh().catch(reportError);
}

function start() {
  let saved = null;
  try { saved = localStorage.getItem(THEME_KEY) || localStorage.getItem(OLD_THEME_KEY); } catch { saved = null; }
  applyTheme(saved);
  Object.assign(state, parseHash(location.hash));
  if (OLD_VIEWS[location.hash.replace(/^#/, "").split("?")[0]]) setState({});
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
    // On the Library, each cell turns into its state in the new scope instead of jumping.
    if (state.view === "library") morphOnNextRender();
    // The old project's page stays until the new one is read, faded and marked as waiting.
    const main = $("#main");
    main.classList.add("pending");
    main.setAttribute("aria-busy", "true");
    refresh({ fade: state.view !== "library" }).catch(reportError).finally(() => {
      main.classList.remove("pending");
      main.removeAttribute("aria-busy");
    });
  });
  $("#q").addEventListener("input", (event) => {
    const q = event.target.value.trim();
    // The Library searches what is set up and the marketplaces; other places send a search there.
    if (state.view !== "library" && q) go("library", { q });
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
  getJson("/api/progress").then(showScan).catch(() => {});
  loadShared()
    .then(refresh)
    .catch(reportError);
  listen();
}

start();
