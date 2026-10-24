// Entry point: the shell (rail, top bar), routing, theme, rescan and live updates.
import { getJson, postJson } from "./api.js";
import { $, $$, busyWhile, el, focusKey, icon, reportError } from "./dom.js";
import { glide, rollTo, transition } from "./motion.js";
import { renderAgents } from "./agents.js";
import { renderChanges } from "./changes.js";
import { renderGateway } from "./gateway.js";
import { loadLibrary, loadLibraryFor, morphOnNextRender, raceSlow, renderLibrary, settleRows, showSources, snapshotRows } from "./library.js";
import { leaveMap } from "./map-review.js";
import { findChip } from "./map.js";
import { renderOverview } from "./overview.js";
import { closeForProject, closePanel, initPanel, isPanelOpen } from "./panel.js";
import { callout, demoTag, GONE_PROJECT, latestChanges, projectMenu, scanLine, setHint, versionsOpened } from "./parts.js";
import {
  arrival, busy, current, data, followHash, freshness, go, loadShared, OLD_VIEWS, onIdle, parseHash, projectGone, reload, setRenderer, setState, setSwitcher, state,
  switchProject,
} from "./store.js";

const PLACES = {
  overview: { title: "Overview", render: renderOverview },
  library: { title: "Library", render: renderLibrary, snapshot: snapshotRows, settle: settleRows },
  gateway: { title: "Gateway", render: renderGateway },
  changes: { title: "Changes", render: renderChanges },
  agents: { title: "Agents", render: renderAgents },
};

let shownView = null;
// What a redraw can hand focus back to: controls with a data-focus key, and table rows.
const FOCUSABLE = "[data-focus], tr[data-key]";
// Places that show one project's setup. For a picked project no longer on the list they say so
// instead; Changes and Agents draw as usual.
const PROJECT_PLACES = ["overview", "library", "gateway"];
// Places where the top search finds on the page itself (Part 5 adds "library"). On the others it
// sends the search to the Library. A map page's render returns what the search found there.
const MAP_PAGES = ["gateway"];

function renderPlace() {
  if (shownView !== state.view && isPanelOpen()) closePanel({ instant: true, keepSelection: true, focus: false });
  // A preview started on the Gateway map stays there: another place cancels one only previewed.
  if (state.view !== "gateway") leaveMap();
  const samePlace = shownView === state.view;
  shownView = state.view;
  const main = $("#main");
  // A redraw of the same place keeps keyboard focus on the same row, tab, filter or menu.
  const focused = samePlace && main.contains(document.activeElement) ? document.activeElement.closest(FOCUSABLE) : null;
  const key = focused ? focusKey(focused) : null;
  const place = PLACES[state.view] || PLACES.overview;
  // A redraw of the same place notes where its rows were, so they can move from there.
  const before = samePlace && place.snapshot ? place.snapshot() : null;
  main.replaceChildren();
  // A page sets its own hint line while it draws; none inherits the last page's.
  setHint("");
  let found = null;
  if (PROJECT_PLACES.includes(state.view) && projectGone()) main.append(el("h1", null, place.title), callout(GONE_PROJECT));
  else found = place.render(main);
  if (place.settle) place.settle(before);
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
  drawChip(MAP_PAGES.includes(state.view) ? found : null);
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

  drawPicker();
  if ($("#q") !== document.activeElement) $("#q").value = state.q;
}

// The chip in the search box says how many blocks the search found on a map page (`found`, else
// null). It is a live region: its words are set only when they change, so a redraw is quiet.
function drawChip(found) {
  const chip = $("#find-chip");
  const words = findChip(found) || "";
  if (chip.textContent !== words) chip.textContent = words;
}

// The project picker (parts.js projectMenu), drawn again when the list, a count or the pick
// changes. A picked project no longer on the list has a row of its own, so the picker never says
// All projects for it. While the list is unread, a picked project keeps the page's "…".
function drawPicker() {
  const box = $("#where-box");
  box.classList.toggle("project", Boolean(state.project));
  if (data.projects === null && state.project) return;
  const projects = data.projects || [];
  const signature = JSON.stringify([projects.map(({ id, path, exists, own_rules }) => [id, path, exists, own_rules]), state.project]);
  if (box.dataset.projects === signature) return;
  box.dataset.projects = signature;
  const had = box.contains(document.activeElement);
  box.replaceChildren(projectMenu(projects, state.project, (id) => switchProject(id).catch(reportError)));
  if (had) $("#where").focus({ preventScroll: true });
}

// A scope change cross-fades the page (the Library morphs its cells instead). The Library's
// rows are read beside everything else, so the page draws once with both.
async function refresh({ fade = false } = {}) {
  await Promise.all([reload(), loadLibrary()]);
  if (fade) transition(renderPlace);
  else renderPlace();
}

// Another project is picked (store.js switchProject): Details close, the old page waits faded
// until the new project is read, and the Library's cells turn into their new states.
function refreshForProject() {
  closeForProject();
  drawPicker();
  // On the Library, each cell turns into its state in the new scope instead of jumping.
  if (state.view === "library") morphOnNextRender();
  const main = $("#main");
  main.classList.add("pending");
  main.setAttribute("aria-busy", "true");
  return refresh({ fade: state.view !== "library" }).catch(reportError).finally(() => {
    main.classList.remove("pending");
    main.removeAttribute("aria-busy");
  });
}

// The icons of the rail, the project button and the search box. The page holds only their words.
function drawIcons() {
  $('.nav [data-view="overview"]').prepend(icon("house"));
  $('.nav [data-view="library"]').prepend(icon("library"));
  $('.nav [data-view="gateway"]').prepend(icon("network"));
  $('.nav [data-view="changes"]').prepend(icon("history"));
  $("#theme").prepend(icon("sun-moon", 14));
  $(".search").prepend(icon("search", 14));
  // Until the project list is read, the button keeps these; projectMenu draws its own.
  $("#where").prepend(icon("folder", 14));
  $("#where").append(icon("chevron-down", 13, "ic where-caret"));
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
  // The button always says "Appearance"; its hover text names the theme a press gives.
  $("#theme").title = currentTheme() === "dark" ? "Switch to light theme" : "Switch to dark theme";
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
// It shows only when the wait is long enough to notice, so a quick start never blinks; the
// words appear with it (a screen reader hears them then, not before), and at the end the bar
// fills up before it goes.
const SCAN_LINE_DELAY_MS = 1000;
const SCAN_LINE_END_MS = 400;
let scanLineTimer = null;
let scanning = null; // the last line, while the first scan still reads something

// The Library's lines about sources still read show and change with this line (library.js).
function drawScan() {
  const bar = $("#topbar");
  bar.style.setProperty("--scan-done", String(scanning.share));
  $("#scan-status").textContent = scanning.text;
  bar.classList.add("progress");
  showSources(data.progress);
}

function showScan(view) {
  const bar = $("#topbar");
  // The Clients card may be drawn before the first progress came: it draws again to say
  // "Checking the version…".
  const opened = versionsOpened(data.progress, view);
  data.progress = view;
  if (opened) document.dispatchEvent(new CustomEvent("kitden:versions"));
  scanning = scanLine(view);
  if (scanning) {
    if (bar.classList.contains("progress")) drawScan();
    else if (!scanLineTimer) {
      scanLineTimer = setTimeout(() => {
        scanLineTimer = null;
        if (scanning) drawScan();
      }, SCAN_LINE_DELAY_MS);
    }
    return;
  }
  clearTimeout(scanLineTimer);
  scanLineTimer = null;
  showSources(view);
  if (!bar.classList.contains("progress")) return;
  bar.style.setProperty("--scan-done", "1");
  setTimeout(() => {
    if (scanning) return;
    bar.classList.remove("progress");
    $("#scan-status").textContent = "";
  }, SCAN_LINE_END_MS);
}

function readScan() {
  getJson("/api/progress").then(showScan).catch(() => {});
}

// A rail link opens its place fresh: the project stays, and no Details opens. The Library's rows
// are read first (up to a moment), so the page changes once, already full, instead of a skeleton
// turning into a table after the change.
async function openPlace(view) {
  if (view === "library" && state.view !== "library") await raceSlow(loadLibraryFor({}), 300);
  go(view);
}

function listen() {
  const events = new EventSource("/api/events");
  // Read where the first scan is on every (re)connect: steps sent while not connected are lost.
  events.addEventListener("open", readScan);
  events.addEventListener("scan_progress", (event) => {
    try { showScan(JSON.parse(event.data)); } catch { /* a broken message changes nothing */ }
  });
  // While the first scan's line runs, it already says that a scan runs: no sweep on top.
  events.addEventListener("rescan_started", () => { if (!scanning) $("#topbar").classList.add("scanning"); });
  // How many steps of a running change are done; the review's Apply button counts them.
  events.addEventListener("change_progress", (event) => {
    let detail = null;
    try { detail = JSON.parse(event.data); } catch { return; }
    document.dispatchEvent(new CustomEvent("kitden:progress", { detail }));
  });
  // A refresh of the Kitden gateway's tool lists ended, also after a failure: an open tool
  // list reads them again.
  events.addEventListener("gateway_tools", () => document.dispatchEvent(new CustomEvent("kitden:tools")));
  // The clients' versions were read in the background, also after a failure: the Clients card
  // reads them again.
  events.addEventListener("versions", () => document.dispatchEvent(new CustomEvent("kitden:versions")));
  // An open review asks whether its files changed (review.js checkStale), also while someone
  // types: only the page's redraw waits.
  events.addEventListener("rescan_finished", () => {
    $("#topbar").classList.remove("scanning");
    document.dispatchEvent(new CustomEvent("kitden:rescanned"));
    liveRefresh();
  });
  onIdle(() => setTimeout(catchUp, 800));
  $("#main").addEventListener("focusout", () => setTimeout(() => { if (!typing()) catchUp(); }, 0));
}

// Back, Forward or an edited address (store.js followHash). Unknown places (like the skip link's
// #main) are ignored; another project closes the panel and is read.
function fromAddress() {
  const change = followHash(location.hash);
  if (!change) return;
  closeForProject();
  if (!change.same && change.newProject) refresh().catch(reportError);
}

function start() {
  drawIcons();
  let saved = null;
  try { saved = localStorage.getItem(THEME_KEY) || localStorage.getItem(OLD_THEME_KEY); } catch { saved = null; }
  applyTheme(saved);
  Object.assign(state, parseHash(location.hash));
  // A link with a selection opens that item once its place has drawn it.
  arrival.pending = Boolean(state.selected);
  if (OLD_VIEWS[location.hash.replace(/^#/, "").split("?")[0]]) setState({});
  setRenderer(renderPlace);
  setSwitcher(refreshForProject);

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-view]");
    if (!link) return;
    event.preventDefault();
    openPlace(link.dataset.view).catch(reportError);
  });
  window.addEventListener("hashchange", fromAddress);
  window.addEventListener("popstate", fromAddress);
  $(".skip").addEventListener("click", (event) => {
    event.preventDefault();
    $("#main").focus();
  });
  // The search stays on the place: it replaces the address entry and draws again, and the focus
  // stays in the box (only the page is drawn again).
  $("#q").addEventListener("input", (event) => {
    const q = event.target.value.trim();
    // A map page finds on itself and the Library searches what is set up and the marketplaces;
    // other places send a search to the Library.
    const here = state.view === "library" || MAP_PAGES.includes(state.view);
    if (!here && q) go("library", { q });
    else go(state.view, { q });
  });
  // Escape clears a search on a map page. Details stay open: only the next Escape closes them.
  $("#q").addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !MAP_PAGES.includes(state.view) || !state.q) return;
    event.preventDefault();
    event.stopPropagation();
    event.target.value = "";
    go(state.view, { q: "" });
  });
  document.addEventListener("keydown", (event) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    // Details beside the page leave the page usable; only the drawer over it is modal.
    const modal = isPanelOpen() && !$("#drawer").classList.contains("docked");
    if (event.key === "/" && !typing && !modal) {
      event.preventDefault();
      $("#q").focus();
    }
  });
  $("#theme").addEventListener("click", switchTheme);
  $("#rescan").addEventListener("click", () => rescan().catch(reportError));
  initPanel();

  renderPlace();
  // Once per start: whether this is the demo. It answers before the first scan.
  getJson("/api/about")
    .then((about) => {
      const tag = demoTag(about);
      if (tag) $(".brand").append(tag);
    })
    .catch(() => {});
  loadShared()
    .then(refresh)
    .catch(reportError);
  listen();
}

start();
