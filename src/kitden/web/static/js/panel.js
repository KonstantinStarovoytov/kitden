// Side panel: the shell that opens, swaps and closes it, the toast with Undo, and the wiring.
// Item details are in details.js, a held server's tools in tools.js and the change review in
// review.js. The names other pages imported from here before the split still come from here.
import { postJson } from "./api.js";
import { openItem } from "./details.js";
import { $, $$, button, el } from "./dom.js";
import { onOpenItem } from "./library.js";
import { finishTransition } from "./motion.js";
import { arrival, busy, setState, state } from "./store.js";
import { reloadTools } from "./tools.js";

export { contextLinks, countedDefinition, footerActions, footerButtons, heldActions, heldButtons, kindWord, layerState, linksRow, loadsLede, moveFor, moveInto, moveTargets, offerLabel, openItem, plainSecrets, scopeWords, technical } from "./details.js";
export { callsText, projectLabel, toolRows, toolsSection, writingToolsOn } from "./tools.js";
export { ADDS, addScope, afterParts, alignGroups, canShowReview, changeOutcome, changeWords, chosenKeys, leftOutText, review, reviewLede, undoChange } from "./review.js";

// What is open now (`current`): "item" or "review", and for a review the change and the request
// behind it. `from` is the Details a review was opened from; nothing sets it yet.
export const panelState = { current: null, from: null };
let opener = null;
let openerKey = null;
// The project the panel's content was drawn in: its switches and reviews are for that project.
let openedIn = null;

export function isPanelOpen() {
  return $("#drawer").classList.contains("open");
}

// New content for an open panel; focus stays inside it (the old buttons are gone).
export function swapContent(content) {
  const drawer = $("#drawer");
  drawer.replaceChildren(...content);
  if (isPanelOpen() && !drawer.contains(document.activeElement)) drawer.focus();
}

// Put content in the panel and slide it in. Keyboard opens are instant. New content belongs to
// the project picked now: Details drawn again after an Apply is for the project picked during it.
// A panel the person opens wins over an arrival still waiting for its page (store.js).
export function openPanel(content, { instant = false } = {}) {
  arrival.pending = false;
  finishTransition();
  const drawer = $("#drawer");
  openedIn = state.project;
  if (isPanelOpen()) { swapContent(content); return; }
  drawer.replaceChildren(...content);
  // Opened on arrival from another place, nothing on this page has focus: it goes back to the
  // selected row.
  opener = document.activeElement === document.body ? null : document.activeElement;
  const row = opener && opener.closest ? opener.closest("tr[data-key]") : null;
  const selected = $('tr[aria-selected="true"]');
  openerKey = row ? row.dataset.key : selected ? selected.dataset.key : null;
  for (const node of [drawer, $("#scrim")]) {
    node.classList.toggle("instant", instant);
    node.classList.add("open");
  }
  drawer.focus();
}

// While a change is being applied the panel stays open: closing it could not stop the change.
export function closePanel({ instant = false, keepSelection = false, focus = true, force = false } = {}) {
  if (!isPanelOpen() || (busy.change && !force)) return;
  cancelPreview();
  panelState.current = null;
  for (const node of [$("#drawer"), $("#scrim")]) {
    node.classList.toggle("instant", instant);
    node.classList.remove("open");
  }
  if (!keepSelection) {
    setState({ selected: null });
    for (const row of $$('tr[aria-selected="true"]')) row.setAttribute("aria-selected", "false");
  }
  if (focus) restoreFocus();
}

// Another project picked (at the top, or by Back or an edited address) closes the panel, and an
// open review is cancelled as Cancel does: a switch in it never acts on a project it does not name.
// The selection is the caller's: the picker clears it, an address brings its own.
export function closeForProject() {
  if (isPanelOpen() && openedIn !== state.project) closePanel({ focus: false, keepSelection: true });
}

// A review left without Apply: the server forgets its preview.
export function cancelPreview() {
  if (panelState.current && panelState.current.type === "review" && panelState.current.change && panelState.current.change.state === "previewed") {
    postJson(`/api/changes/${encodeURIComponent(panelState.current.change.id)}/cancel`).catch(() => {});
  }
}

export function restoreFocus() {
  if (opener && opener.isConnected) { opener.focus(); return; }
  const row = openerKey && $$("tr[data-key]").find((tr) => tr.dataset.key === openerKey);
  if (row) row.focus();
  else $("#main").focus();
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
export function openInfo(kicker, title, body, actions = []) {
  panelState.current = { type: "info" };
  const footer = el("footer");
  footer.append(...actions);
  openPanel([header(kicker, title, null, "Close", true), body, footer]);
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

// A short note after a change, with Undo when it can be undone. Hides after 6 s; the
// countdown pauses while the pointer or focus is on it.
// A check mark only for a state the server verified (applied, undone); never for an error.
export function toast(text, onUndo, { ok = false } = {}) {
  const node = $("#toast");
  node.classList.remove("show");
  node.replaceChildren(el("span", null, text));
  if (ok) node.prepend(checkMark());
  if (onUndo) node.append(button("Undo", () => onUndo()));
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

function trapFocus(event) {
  if (event.key !== "Tab" || !isPanelOpen()) return;
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
  onOpenItem((row, tr, how) => openItem(row, { instant: how === "keyboard" }));
  // A refresh of the gateway's tool lists ended: an open tool list reads them again.
  document.addEventListener("kitden:tools", reloadTools);
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
