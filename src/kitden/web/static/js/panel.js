// Side panel: the shell that opens, swaps and closes it, and the wiring. Item details are in
// details.js, a held server's tools in tools.js, the change review in review.js and the toast in
// toast.js. The names other pages imported from here before the split still come from here.
// Every change waits in the tray (tray.js), so closing the panel or drawing something else in it
// never touches a change. The one write the panel starts is Undo, in a change from the Changes page.
import { openItem, syncTray } from "./details.js";
import { $, $$, button, el, focusKey } from "./dom.js";
import { onOpenItem } from "./library.js";
import { animateTo, D, finishTransition, rise } from "./motion.js";
import { arrival, setState, state } from "./store.js";
import { reloadTools } from "./tools.js";
import { onTray, tray } from "./tray.js";

export { backToDetails, contextLinks, countedDefinition, detailsCard, followTray, footerActions, footerButtons, heldActions, heldButtons, keepFrom, kindWord, layerState, linksRow, loadsLede, moveBody, moveFor, moveInto, moveTargets, offerLabel, openItem, plainSecrets, previewButton, scopeWords, techRows, technical } from "./details.js";
export { callsText, NO_TOOLS, offNote, projectLabel, refreshTools, switchList, toolRows, toolsHead, toolsSection, writingToolsOn } from "./tools.js";
export { ADDS, addScope, afterParts, alignGroups, canShowReview, changeOutcome, changeWords, chosenKeys, leftOutText, review, reviewLede, undoChange } from "./review.js";
export { hideToast, toast } from "./toast.js";

// What is open now (`current`): Details ("item", or a Gateway card), a row's review ("row-review"),
// Add missing's list ("align"), and so on. `from` is the Details drawn last (details.js keepFrom):
// Add missing's Cancel goes back there, and Apply all draws it again. A closed panel forgets it.
export const panelState = { current: null, from: null };
// Details drawn again by the page itself, not by a press (after Apply all or an Undo): while
// `quiet`, focus and the way back stay where the person has them, unless focus was in Details.
let quiet = false;
// Beside the page: on these places, in a window this wide, Details float over the right of the
// page with no scrim and no focus trap; the page keeps its width and stays usable. Anywhere else
// they are the drawer.
export const FLOAT_MIN = 1024;
export const FLOATS = ["gateway", "library", "changes"];
export const floatsAt = (view, width) => FLOATS.includes(view) && width >= FLOAT_MIN;
const isWide = () => matchMedia(`(min-width: ${FLOAT_MIN}px)`).matches;
// How the open panel sits: `floating` beside the page, else the drawer. `wantsFloat` is what the
// opener asked for, so a window that changes size while the panel is open can pick again.
let floating = false;
let wantsFloat = false;
let opener = null;
// What finds the opener again after a redraw: its data-focus key, and its row's key.
let openerKeys = [];
// The project the panel's content was drawn in: its switches and reviews are for that project.
let openedIn = null;
// A panel that loads (loadPanel): when its skeleton came, the content that waits to replace it and
// the timer that brings it.
let loading = null;
// How many times the panel's content was put in, and the last step asked: a step whose parts went
// out while other content came, or another step, does not come in.
let drawn = 0;
let stepping = 0;
// The timer that stops showing the floating panel once it has gone out (floatOut), and the frame
// that places it again while the page scrolls (placeSoon).
let leaving = null;
let placing = 0;

export function isPanelOpen() {
  return $("#drawer").classList.contains("open");
}

// New content for an open panel; focus stays inside it (the old buttons are gone). Beside the
// page focus may be on the page, and a redraw does not take it from there. It also takes the
// place of content a loading panel waits for.
export function swapContent(content) {
  stopLoading();
  put(content);
}

function put(content) {
  const drawer = $("#drawer");
  const had = drawer.contains(document.activeElement);
  drawn += 1;
  drawer.replaceChildren(...content);
  if (isPanelOpen() && (had || (!floating && !quiet)) && !drawer.contains(document.activeElement)) drawer.focus();
}

// Draw open Details again (`draw`, which may read first) without taking focus from the dock or the
// page: only focus that was in Details stays in them.
export async function drawQuietly(draw) {
  quiet = true;
  try {
    await draw();
  } finally {
    quiet = false;
  }
}

// The panel floating beside the page (`on`) or as the drawer over it. Floating it is a region
// beside the map: the page stays usable, so it is not modal.
function place(on) {
  floating = on;
  const drawer = $("#drawer");
  drawer.classList.toggle("floating", on);
  if (!on) $("#main").classList.remove("floats");
  if (on) {
    drawer.setAttribute("role", "complementary");
    drawer.removeAttribute("aria-modal");
    drawer.removeAttribute("aria-labelledby");
    placeFloat();
  } else {
    drawer.setAttribute("role", "dialog");
    drawer.setAttribute("aria-modal", "true");
    drawer.setAttribute("aria-labelledby", "panel-title");
  }
}

// The page's head: its title, lede and scope line, and the Library's tabs. What comes after it is
// the stage (the map, a list); the floating panel starts level with its top.
const HEAD = "h1, .page-head, .lede, .scope-bar, .tabs";
const UNDER_BAR = 22;

// The floating panel's top in the window: level with the stage's top (`stage`), so it follows the
// stage while the page scrolls, and it stops 22 px under the top bar's bottom (`bar`).
export function floatTop(stage, bar) {
  return Math.round(Math.max(stage, bar + UNDER_BAR));
}

// The page's right padding while Details float: a list or a table ends 16 px before the panel's
// left edge (`left`), counted from the page's right edge (`right`); never less than its own 22 px.
export function floatRoom(right, left) {
  return Math.max(22, Math.round(right - left + 16));
}

// Where the floating panel sits: the room a list or a table keeps on its right (`--float-room` and
// `.floats` on the page, style.css; the Gateway map keeps its width), then its top (floatTop), read
// with that room in place. Read when the panel floats, then at most once a frame while the page
// scrolls or the window changes (placeSoon).
function placeFloat() {
  placing = 0;
  if (!floating) return;
  const drawer = $("#drawer");
  const main = $("#main");
  main.style.setProperty("--float-room", `${floatRoom(main.getBoundingClientRect().right, drawer.offsetLeft)}px`);
  main.classList.add("floats");
  const bar = $("#topbar").getBoundingClientRect().bottom;
  const stage = [...main.children].find((node) => !node.matches(HEAD));
  const top = stage ? stage.getBoundingClientRect().top : bar;
  drawer.style.setProperty("--float-top", `${floatTop(top, bar)}px`);
}

function placeSoon() {
  if (floating && !placing) placing = requestAnimationFrame(placeFloat);
}

// The floating panel comes in from 28 px to the right, a little smaller, in 240 ms; a keyboard
// open is instant.
function floatIn(drawer, instant) {
  if (!instant) animateTo(drawer, [{ opacity: 0, transform: "translateX(28px) scale(.98)" }, { opacity: 1, transform: "none" }], { dur: 240 });
}

// It goes 22 px to the right in 180 ms ease-in. `.leaving` keeps it seen until then, taking no
// press and no Tab (inert), and is taken off by time, not by the animation's end. With no motion
// (a keyboard close, reduced motion) it is gone at once.
function floatOut(drawer, instant) {
  const dur = instant ? 0 : D(180);
  if (!dur) {
    drawer.classList.remove("floating");
    return;
  }
  drawer.classList.add("leaving");
  drawer.inert = true;
  animateTo(drawer, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateX(22px)" }], { dur: 180, ease: "ease-in", fill: "forwards" });
  leaving = setTimeout(() => settleLeaving(drawer), dur);
}

// The floating panel has gone out, or opens again while it goes: it lets go of its last motion and
// stops floating, with no transition, so the next drawer slides in as a drawer.
function settleLeaving(drawer) {
  if (!leaving) return;
  clearTimeout(leaving);
  leaving = null;
  drawer.inert = false;
  drawer.classList.add("instant");
  drawer.classList.remove("leaving", "floating");
  for (const motion of drawer.getAnimations()) motion.cancel();
}

// What opened the panel, so closing it can give focus back. A redraw makes new nodes: the opener's
// data-focus key, or its row's key, finds the new one. With no focus on the page (an arrival from
// another place) it is the selected row.
function rememberOpener() {
  opener = document.activeElement === document.body ? null : document.activeElement;
  const named = opener && opener.closest ? opener.closest("[data-focus], tr[data-key]") : null;
  const row = (opener && opener.closest ? opener.closest("tr[data-key]") : null) || $('tr[aria-selected="true"]');
  openerKeys = [named, row].filter(Boolean).map(focusKey);
}

// Put content in the panel and slide it in. Keyboard opens are instant. New content belongs to
// the project picked now: Details drawn again after an Apply is for the project picked during it.
// A panel the person opens wins over an arrival still waiting for its page (store.js).
// `float`: float beside the page where the window is wide enough. An open panel keeps how it sits,
// so a review opened from the floating panel stays in it. A loading panel takes its content when
// its skeleton has shown long enough (loadPanel).
export function openPanel(content, { instant = false, float = FLOATS.includes(state.view) } = {}) {
  arrival.pending = false;
  finishTransition();
  const drawer = $("#drawer");
  openedIn = state.project;
  if (isPanelOpen()) {
    // Beside the page another row may be pressed: the way back is to that row, and focus moves in.
    const active = document.activeElement;
    const elsewhere = !quiet && floating && active && active !== document.body && !drawer.contains(active);
    if (elsewhere) rememberOpener();
    if (loading) settle(content);
    else put(content);
    if (elsewhere) drawer.focus();
    return;
  }
  settleLeaving(drawer);
  drawn += 1;
  drawer.replaceChildren(...content);
  rememberOpener();
  wantsFloat = float;
  place(float && isWide());
  for (const node of floating ? [drawer] : [drawer, $("#scrim")]) {
    node.classList.toggle("instant", instant);
    node.classList.add("open");
  }
  if (floating) floatIn(drawer, instant);
  drawer.focus();
}

// A panel that loads: its kind and Close at once, and still bars where its title, facts, sentence
// and first button will be.
export function skeleton(kind) {
  const head = el("header");
  const top = el("div", "top");
  top.append(el("span", "kicker", kind), button("Close", () => closePanel(), "btn ghost small"));
  head.append(top, bars("sk-title", [62, 38]));
  const body = el("div", "body sk-body");
  body.append(bars("sk-facts", [70, 54, 80, 46, 60]), bars("sk-line", [90]), bars("sk-button", [55]));
  return [head, body];
}

function bars(className, widths) {
  const box = el("div", className);
  box.setAttribute("aria-hidden", "true");
  for (const width of widths) {
    const bar = el("span", "sk");
    bar.style.width = `${width}%`;
    box.append(bar);
  }
  return box;
}

// Details that load: the skeleton of `kind` shows at once (the panel opens, or keeps its place and
// shows it), and the content openPanel brings next takes its place no sooner than 160 ms after it.
// Meanwhile `panelState.current` is the mark this returns, so a read that ends after the panel
// closed, or after something else opened, draws nothing. Only the floating panel loads this way:
// under reduced motion, and in the drawer (one motion, its blocks there at once), no skeleton
// shows and the panel keeps what it shows until the content comes.
export function loadPanel(kind) {
  stopLoading();
  const mark = { type: "loading", kind };
  if (D(160) && floatsNow()) {
    openPanel(skeleton(kind));
    loading = { since: performance.now(), content: null, timer: null };
  }
  panelState.current = mark;
  return mark;
}

// Content for a loading panel lands once the skeleton has shown 160 ms, or at once when it came
// later; its parts rise in, 20 ms apart. Content that comes meanwhile takes its place.
function settle(content) {
  loading.content = content;
  const rest = loading.since + D(160) - performance.now();
  if (rest <= 0) land();
  else loading.timer ||= setTimeout(land, rest);
}

function land() {
  const { content } = loading;
  loading = null;
  put(content);
  if (floating) rise([...$("#drawer").children], { step: 20 });
}

// Whether a panel opened now floats: the open one as it sits, else by the place and the window.
const floatsNow = () => (isPanelOpen() ? floating : FLOATS.includes(state.view) && isWide());

function stopLoading() {
  if (loading) clearTimeout(loading.timer);
  loading = null;
}

// The next step inside one panel (a choice, then what it asks): the parts shown go out together,
// 18 px to the left in 130 ms ease-in, then the new ones come in from 22 px to the right in 220 ms.
// "back" is the mirror. In the drawer the new parts are there at once. Done once the new content
// is in; a step, other content or a close that comes meanwhile wins.
export async function stepTo(content, dir = "fwd") {
  const drawer = $("#drawer");
  const sign = dir === "back" ? -1 : 1;
  const step = ++stepping;
  const at = drawn;
  const moves = floating;
  stopLoading();
  const out = [{ opacity: 1, transform: "none" }, { opacity: 0, transform: `translateX(${-18 * sign}px)` }];
  if (moves) await Promise.all([...drawer.children].map((node) => animateTo(node, out, { dur: 130, ease: "ease-in", fill: "forwards" })));
  if (step !== stepping || at !== drawn || !isPanelOpen()) return;
  put(content);
  if (!moves) return;
  for (const node of drawer.children) animateTo(node, [{ opacity: 0, transform: `translateX(${22 * sign}px)` }, { opacity: 1, transform: "none" }], { dur: 220 });
}

// The tray keeps its rows: they wait for the bar's Apply or Cancel, whatever the panel shows.
export function closePanel({ instant = false, keepSelection = false, focus = true } = {}) {
  if (!isPanelOpen()) return;
  panelState.current = null;
  panelState.from = null;
  stopLoading();
  const drawer = $("#drawer");
  for (const node of [drawer, $("#scrim")]) {
    node.classList.toggle("instant", instant);
    node.classList.remove("open");
  }
  // The floating panel goes as it was; a list takes its room back at once.
  if (floating) floatOut(drawer, instant);
  floating = false;
  $("#main").classList.remove("floats");
  if (!keepSelection) {
    setState({ selected: null });
    for (const row of $$('tr[aria-selected="true"], [role="row"][aria-selected="true"]')) row.setAttribute("aria-selected", "false");
  }
  if (focus) restoreFocus();
}

// Another project picked (at the top, or by Back or an edited address) closes the panel: a switch
// in it never acts on a project it does not name. The tray keeps its rows: each keeps the project
// it was asked in. The selection is the caller's: the picker clears it, an address brings its own.
export function closeForProject() {
  if (isPanelOpen() && openedIn !== state.project) closePanel({ focus: false, keepSelection: true });
}

export function restoreFocus() {
  if (opener && opener.isConnected) { opener.focus(); return; }
  const nodes = [...$$("[data-focus]"), ...$$("tr[data-key]")];
  for (const key of openerKeys) {
    const node = nodes.find((candidate) => focusKey(candidate) === key);
    if (node) { node.focus(); return; }
  }
  $("#main").focus();
}

// A review has no close button up here: its footer holds the one Cancel.
export function header(kicker, title, lede, closeLabel = "Close", mono = false) {
  const head = el("header");
  const top = el("div", "top");
  top.append(el("span", "kicker", kicker));
  if (closeLabel) top.append(button(closeLabel, () => closePanel(), "btn ghost small"));
  const h1 = el("h1", mono ? "title-mono" : null, title);
  h1.id = "panel-title";
  head.append(top, h1);
  if (lede) head.append(el("p", "muted", lede));
  return head;
}

// A note in the panel, for example a server the gateway holds; `actions` go in its footer.
// The title is a name in mono, unless `mono` is false (a sentence).
export function openInfo(kicker, title, body, actions = [], { mono = true } = {}) {
  panelState.current = { type: "info" };
  const footer = el("footer");
  footer.append(...actions);
  openPanel([header(kicker, title, null, "Close", mono), body, footer]);
}

// A change from the Changes page: the Changes page builds the body (steps with their files,
// history, error); the panel frames it. Undo stays with the row that opened it.
export function openChange(title, body, onUndo) {
  panelState.current = { type: "change" };
  const footer = el("footer");
  if (onUndo) footer.append(button("Undo", onUndo, "btn primary"));
  openPanel([header("Change", title, null), body, footer]);
}

// Wiring ---------------------------------------------------------------------------------

// The drawer keeps Tab inside it; the floating panel does not.
function trapFocus(event) {
  if (event.key !== "Tab" || !isPanelOpen() || floating) return;
  const drawer = $("#drawer");
  // Only what is drawn: a closed Details hides everything but its summary. The dock stands above
  // the scrim and the drawer, so what it shows (the tray's bar, or a toast after a tool switch) is
  // in the loop too, and its Apply or Undo can be reached. The page has the dock before the
  // drawer, so the loop does too: Tab leaves the drawer's last button for the dock's first.
  const dock = $("#dock");
  const visible = (node) => node.getClientRects().length > 0;
  const own = $$("button:not([disabled]), a[href], select, input, textarea, summary, [tabindex]:not([tabindex='-1'])", drawer).filter(visible);
  const stops = [...(dock ? $$("button:not([disabled])", dock).filter(visible) : []), ...own];
  const inside = drawer.contains(document.activeElement) || Boolean(dock && dock.contains(document.activeElement));
  if (!stops.length || !inside) {
    event.preventDefault();
    (own[0] || stops[0] || drawer).focus();
    return;
  }
  const first = stops[0];
  const last = stops[stops.length - 1];
  if (event.shiftKey && (document.activeElement === first || document.activeElement === drawer)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

export function initPanel() {
  const drawer = $("#drawer");
  drawer.setAttribute("role", "dialog");
  drawer.setAttribute("aria-modal", "true");
  drawer.setAttribute("aria-labelledby", "panel-title");
  // A window that grows or shrinks while the panel is open switches the floating panel and the
  // drawer.
  matchMedia(`(min-width: ${FLOAT_MIN}px)`).addEventListener("change", (event) => {
    if (!isPanelOpen()) return;
    place(wantsFloat && event.matches);
    $("#scrim").classList.toggle("open", !floating);
    if (!floating && !drawer.contains(document.activeElement)) drawer.focus();
  });
  // The floating panel follows the page's stage as it scrolls, and the window as it changes.
  $("#content").addEventListener("scroll", placeSoon, { passive: true });
  addEventListener("resize", placeSoon);
  onOpenItem((row, tr, how) => openItem(row, { instant: how === "keyboard" }));
  // A refresh of the gateway's tool lists ended: an open tool list reads them again.
  document.addEventListener("kitden:tools", reloadTools);
  // The tray changed: switches and buttons in Details show whether their change waits there.
  onTray(syncTray);
  $("#scrim").addEventListener("click", () => closePanel());
  document.addEventListener("keydown", trapFocus);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      pressApply(event);
    } else if (event.key === "Escape" && isPanelOpen()) {
      // Keyboard closes are instant: an action done many times a day must not wait.
      event.preventDefault();
      closePanel({ instant: true });
    }
  });
}

// ⌘ or Ctrl Enter in Details or in the dock presses the tray's Apply, once its preview is ready:
// the same as a press on the button (Preview again, when the files changed since).
function pressApply(event) {
  const active = document.activeElement;
  const dock = $("#dock");
  const inside = (isPanelOpen() && $("#drawer").contains(active)) || Boolean(dock && dock.contains(active));
  const apply = $("#dock .apply");
  if (tray.phase !== "ready" || !inside || !apply) return;
  event.preventDefault();
  apply.click();
}
