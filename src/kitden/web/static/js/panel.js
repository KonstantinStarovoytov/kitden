// Side panel: the shell that opens, swaps and closes it, and the wiring. Item details are in
// details.js, a held server's tools in tools.js, the change review in review.js and the toast in
// toast.js. The names other pages imported from here before the split still come from here.
// Every change waits in the tray (tray.js), so closing the panel or drawing something else in it
// never touches a change. The one write the panel starts is Undo, in a change from the Changes page.
import { openItem, syncTray } from "./details.js";
import { $, $$, button, el, focusKey } from "./dom.js";
import { onOpenItem } from "./library.js";
import { finishTransition } from "./motion.js";
import { arrival, setState, state } from "./store.js";
import { reloadTools } from "./tools.js";
import { onTray, tray } from "./tray.js";

export { backToDetails, contextLinks, countedDefinition, detailsCard, footerActions, footerButtons, heldActions, heldButtons, keepFrom, kindWord, layerState, linksRow, loadsLede, moveBody, moveFor, moveInto, moveTargets, offerLabel, openItem, plainSecrets, projectChoice, scopeWords, techRows, technical } from "./details.js";
export { callsText, projectLabel, refreshTools, toolRows, toolsSection, writingToolsOn } from "./tools.js";
export { ADDS, addScope, afterParts, alignGroups, canShowReview, changeOutcome, changeWords, chosenKeys, leftOutText, review, reviewLede, undoChange } from "./review.js";
export { hideToast, toast } from "./toast.js";

// What is open now (`current`): Details ("item", or a Gateway card), a row's review ("row-review"),
// Add missing's list ("align"), and so on. `from` is the Details drawn last (details.js keepFrom):
// Add missing's Cancel goes back there, and Apply all draws it again. A closed panel forgets it.
export const panelState = { current: null, from: null };
// Details drawn again by the page itself, not by a press (after Apply all or an Undo): while
// `quiet`, focus and the way back stay where the person has them, unless focus was in Details.
let quiet = false;
// Beside the page: on these places, in a window this wide, Details are a 320 px column with no
// scrim and no focus trap, and the page stays usable. Anywhere else they are the drawer.
export const DOCK_MIN = 1024;
export const DOCKS = ["gateway", "library", "changes"];
export const docksAt = (view, width) => DOCKS.includes(view) && width >= DOCK_MIN;
const isWide = () => matchMedia(`(min-width: ${DOCK_MIN}px)`).matches;
// How the open panel sits: `docked` beside the page, else the drawer. `wantsDock` is what the opener
// asked for, so a window that changes size while the panel is open can pick again.
let docked = false;
let wantsDock = false;
let opener = null;
// What finds the opener again after a redraw: its data-focus key, and its row's key.
let openerKeys = [];
// The project the panel's content was drawn in: its switches and reviews are for that project.
let openedIn = null;

export function isPanelOpen() {
  return $("#drawer").classList.contains("open");
}

// New content for an open panel; focus stays inside it (the old buttons are gone). Beside the
// page focus may be on the page, and a redraw does not take it from there.
export function swapContent(content) {
  const drawer = $("#drawer");
  const had = drawer.contains(document.activeElement);
  drawer.replaceChildren(...content);
  if (isPanelOpen() && (had || (!docked && !quiet)) && !drawer.contains(document.activeElement)) drawer.focus();
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

// The panel as a column beside the page (`on`) or as the drawer over it. The column is a region:
// the page stays usable, so it is not modal. The page makes room for it.
function place(on) {
  docked = on;
  const drawer = $("#drawer");
  drawer.classList.toggle("docked", on);
  $(".shell").classList.toggle("docked", on);
  if (on) {
    drawer.setAttribute("role", "region");
    drawer.removeAttribute("aria-modal");
    drawer.removeAttribute("aria-labelledby");
  } else {
    drawer.setAttribute("role", "dialog");
    drawer.setAttribute("aria-modal", "true");
    drawer.setAttribute("aria-labelledby", "panel-title");
  }
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
// `dock`: sit beside the page where the window is wide enough. An open panel keeps how it sits,
// so a review opened from the column stays in the column.
export function openPanel(content, { instant = false, dock = DOCKS.includes(state.view) } = {}) {
  arrival.pending = false;
  finishTransition();
  const drawer = $("#drawer");
  openedIn = state.project;
  if (isPanelOpen()) {
    // Beside the page another row may be pressed: the way back is to that row, and focus moves in.
    const active = document.activeElement;
    const elsewhere = !quiet && docked && active && active !== document.body && !drawer.contains(active);
    if (elsewhere) rememberOpener();
    swapContent(content);
    if (elsewhere) drawer.focus();
    return;
  }
  drawer.replaceChildren(...content);
  rememberOpener();
  wantsDock = dock;
  place(dock && isWide());
  for (const node of docked ? [drawer] : [drawer, $("#scrim")]) {
    node.classList.toggle("instant", instant);
    node.classList.add("open");
  }
  drawer.focus();
}

// The tray keeps its rows: they wait for the bar's Apply or Cancel, whatever the panel shows.
export function closePanel({ instant = false, keepSelection = false, focus = true } = {}) {
  if (!isPanelOpen()) return;
  panelState.current = null;
  panelState.from = null;
  for (const node of [$("#drawer"), $("#scrim")]) {
    node.classList.toggle("instant", instant);
    node.classList.remove("open");
  }
  // The page takes its room back at once; the column slides out as it was.
  $(".shell").classList.remove("docked");
  docked = false;
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

// The drawer keeps Tab inside it; the column beside the page does not.
function trapFocus(event) {
  if (event.key !== "Tab" || !isPanelOpen() || docked) return;
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
  // A window that grows or shrinks while the panel is open switches the column and the drawer.
  matchMedia(`(min-width: ${DOCK_MIN}px)`).addEventListener("change", (event) => {
    if (!isPanelOpen()) return;
    place(wantsDock && event.matches);
    $("#scrim").classList.toggle("open", !docked);
    if (!docked && !drawer.contains(document.activeElement)) drawer.focus();
  });
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
