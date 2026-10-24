// Side panel: the shell that opens, swaps and closes it, the toast with Undo, and the wiring.
// Item details are in details.js, a held server's tools in tools.js and the change review in
// review.js. The names other pages imported from here before the split still come from here.
import { postJson } from "./api.js";
import { openItem } from "./details.js";
import { $, $$, button, el, focusKey, reportError } from "./dom.js";
import { onOpenItem } from "./library.js";
import { finishTransition } from "./motion.js";
import { checkStale, leaveMap, mapPreview } from "./review.js";
import { arrival, busy, setState, state } from "./store.js";
import { reloadTools } from "./tools.js";

export { backToDetails, contextLinks, countedDefinition, detailsCard, footerActions, footerButtons, heldActions, heldButtons, keepFrom, kindWord, layerState, linksRow, loadsLede, moveBody, moveFor, moveInto, moveTargets, offerLabel, openItem, plainSecrets, projectChoice, scopeWords, techRows, technical } from "./details.js";
export { callsText, projectLabel, refreshTools, toolRows, toolsSection, writingToolsOn } from "./tools.js";
export { ADDS, addScope, afterParts, alignGroups, canShowReview, cancelTarget, changeOutcome, changeWords, chosenKeys, leftOutText, review, reviewLede, undoChange } from "./review.js";

// What is open now (`current`): "item" or "review", and for a review the change and the request
// behind it. `from` is the Details a review was opened from (details.js sets it): Cancel goes
// back there. A closed panel forgets it.
export const panelState = { current: null, from: null };
// What the panel shows now, as panelState.current was when it was drawn. A caller sets
// panelState.current to its new content before it calls openPanel, so the review still showing is
// kept here: other content must not replace it unseen.
let showing = null;
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
  if (isPanelOpen() && (had || !docked) && !drawer.contains(document.activeElement)) drawer.focus();
  showing = panelState.current;
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
// Beside the page a press elsewhere can reach here while a review shows. While its change is
// written nothing replaces it: this returns false, panelState.current is the review again, and
// the caller stops. A review that is only previewed is cancelled on the server first, as closing
// it would. A review handing back after its change was verified (`handingBack`) is let go.
export function openPanel(content, { instant = false, dock = DOCKS.includes(state.view) } = {}) {
  arrival.pending = false;
  finishTransition();
  const drawer = $("#drawer");
  if (isPanelOpen()) {
    const review = showing && showing.type === "review" ? showing : null;
    if (review && busy.change && !review.handingBack) {
      panelState.current = review;
      return false;
    }
    if (review) {
      // A caller that has no state of its own leaves the review's as current: it is gone now.
      const next = panelState.current === review ? null : panelState.current;
      const previewed = review.change && review.change.state === "previewed";
      cancelPreview(review);
      if (!next) panelState.current = null;
      if (previewed && !(next && next.type === "review")) panelState.from = null;
    }
    openedIn = state.project;
    // Beside the page another row may be pressed: the way back is to that row, and focus moves in.
    const active = document.activeElement;
    const elsewhere = docked && active && active !== document.body && !drawer.contains(active);
    if (elsewhere) rememberOpener();
    swapContent(content);
    if (elsewhere) drawer.focus();
    return true;
  }
  openedIn = state.project;
  drawer.replaceChildren(...content);
  rememberOpener();
  wantsDock = dock;
  place(dock && isWide());
  for (const node of docked ? [drawer] : [drawer, $("#scrim")]) {
    node.classList.toggle("instant", instant);
    node.classList.add("open");
  }
  showing = panelState.current;
  drawer.focus();
  return true;
}

// While a change is being applied the panel stays open: closing it could not stop the change.
export function closePanel({ instant = false, keepSelection = false, focus = true, force = false } = {}) {
  if (!isPanelOpen() || (busy.change && !force)) return;
  cancelPreview();
  panelState.current = null;
  panelState.from = null;
  showing = null;
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

// Another project picked (at the top, or by Back or an edited address) closes the panel, and an
// open review is cancelled as Cancel does: a switch in it never acts on a project it does not name.
// So is a preview on the Gateway map. The selection is the caller's: the picker clears it, an
// address brings its own.
export function closeForProject() {
  if (isPanelOpen() && openedIn !== state.project) closePanel({ focus: false, keepSelection: true });
  if (mapPreview.project !== state.project) leaveMap();
}

// A review left without Apply: the server forgets its preview. Sent once: the change is marked
// cancelled, so a panel closed after Cancel does not send it again. `current` is the review shown
// now, or one that is being replaced.
export function cancelPreview(current = panelState.current) {
  const change = current && current.type === "review" ? current.change : null;
  if (change && change.state === "previewed") {
    postJson(`/api/changes/${encodeURIComponent(change.id)}/cancel`).catch(() => {});
    change.state = "cancelled";
  }
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
// The title is a name in mono, unless `mono` is false (a sentence). False when openPanel kept a
// review whose change is being written.
export function openInfo(kicker, title, body, actions = [], { mono = true } = {}) {
  panelState.current = { type: "info" };
  const footer = el("footer");
  footer.append(...actions);
  return openPanel([header(kicker, title, null, "Close", mono), body, footer]);
}

// A change from the Changes page: the Changes page builds the body (steps with their files,
// history, error); the panel frames it. Undo stays with the row that opened it.
export function openChange(title, body, onUndo) {
  panelState.current = { type: "change" };
  const footer = el("footer");
  if (onUndo) footer.append(button("Undo", onUndo, "btn primary"));
  openPanel([header("Change", title, null), body, footer]);
}

export function checkMark() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  for (const [key, value] of Object.entries({ viewBox: "0 0 14 14", width: "12", height: "12", class: "check", "aria-hidden": "true" })) svg.setAttribute(key, value);
  const path = document.createElementNS(ns, "path");
  for (const [key, value] of Object.entries({ d: "M2.5 7.5 L5.8 10.5 L11.5 3.5", fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round" })) path.setAttribute(key, value);
  svg.append(path);
  return svg;
}

// Toast ----------------------------------------------------------------------------------

const TOAST_MS = 6000;
let hideTimer = null;
let remaining = TOAST_MS;
let shownAt = 0;

function scheduleHide(ms) {
  clearTimeout(hideTimer);
  remaining = ms;
  shownAt = performance.now();
  hideTimer = setTimeout(hideToast, ms);
}

function pauseHide() {
  clearTimeout(hideTimer);
  remaining = Math.max(800, remaining - (performance.now() - shownAt));
}

export function hideToast() {
  clearTimeout(hideTimer);
  $("#toast").classList.remove("show");
}

// A short note after a change, with Undo when it can be undone (or another action, `label`).
// Hides after 6 s; the countdown pauses while the pointer or focus is on it.
// A check mark only for a state the server verified (applied, undone); never for an error.
export function toast(text, onUndo, { ok = false, label = "Undo" } = {}) {
  const node = $("#toast");
  node.classList.remove("show");
  node.replaceChildren(el("span", null, text));
  if (ok) node.prepend(checkMark());
  if (onUndo) node.append(button(label, () => onUndo()));
  node.append(el("span", "timer"));
  void node.offsetWidth;
  node.classList.add("show");
  node.onmouseenter = pauseHide;
  node.onmouseleave = () => scheduleHide(remaining);
  node.onfocusin = pauseHide;
  node.onfocusout = () => scheduleHide(remaining);
  scheduleHide(TOAST_MS);
}

// Wiring ---------------------------------------------------------------------------------

// The drawer keeps Tab inside it; the column beside the page does not.
function trapFocus(event) {
  if (event.key !== "Tab" || !isPanelOpen() || docked) return;
  const drawer = $("#drawer");
  // Only what is drawn: a closed Details hides everything but its summary. A toast shown while
  // the panel stays open (after a tool switch) is in the loop too, so its Undo can be reached.
  const shown = $("#toast").classList.contains("show") ? $$("button", $("#toast")) : [];
  const stops = [...$$("button:not([disabled]), a[href], select, input, textarea, summary, [tabindex]:not([tabindex='-1'])", drawer), ...shown]
    .filter((node) => node.getClientRects().length > 0);
  const inside = drawer.contains(document.activeElement) || $("#toast").contains(document.activeElement);
  if (!stops.length || !inside) {
    event.preventDefault();
    (stops[0] || drawer).focus();
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
  // A rescan ended: an open review checks that its files did not change since the preview.
  document.addEventListener("kitden:rescanned", () => checkStale().catch(reportError));
  $("#scrim").addEventListener("click", () => { if (!busy.change) closePanel(); });
  document.addEventListener("keydown", trapFocus);
  document.addEventListener("keydown", (event) => {
    if (!isPanelOpen()) return;
    // Keyboard closes are instant: an action done many times a day must not wait.
    if (event.key === "Escape" && !busy.change) {
      event.preventDefault();
      closePanel({ instant: true });
    } else if (event.key === "Enter" && (event.metaKey || event.ctrlKey) && panelState.current && panelState.current.type === "review") {
      const apply = $("#drawer .apply");
      if (apply && !apply.disabled) { event.preventDefault(); apply.click(); }
    }
  });
}
