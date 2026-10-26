// The toast: a short note in the dock after a change, with Undo when it can be undone. It stands
// where the tray's bar stands (dock.js) and the two take turns: a toast takes the dock's place at
// once, and so does a bar that is drawn while a toast shows. This module imports only dom.js,
// motion.js and store.js, so panel.js can hand it on to every page without an import cycle through
// review.js.
import { $, button, el, icon, reportError, showWaits } from "./dom.js";
import { animateTo, D } from "./motion.js";
import { busy, onBusy } from "./store.js";

// How long a toast lives. Reduced motion does not shorten it: it is time to read, not motion.
const LIFE_MS = 9000;

// The toast on the page now; the one that is leaving; and what runs the life of the first: the
// timer, the ms it has left, when the timer last started, and the line along its bottom.
let shown = null;
let leaving = null;
let timer = null;
let left = 0;
let since = 0;
let line = null;
let stopWaits = () => {}; // the toast's Undo stops following the busy state (action)
// Told when a toast has gone by itself, so the tray can draw its bar again (dock.js).
let afterToast = null;

export function onToastGone(fn) {
  afterToast = fn;
}

const later = (fn, ms) => (ms > 0 ? setTimeout(fn, ms) : fn());

// Keeps room for whatever the dock shows, a bar (dock.js) or a toast: as high as it is plus the dock's
// 46 px offset. The room is `--dock-room` on the page root, so the page's bottom padding and the
// modal Details drawer's bottom both read it (style.css): nothing under the dock is hidden by it.
// An empty dock gives the room back.
export function makeRoom() {
  const root = document.documentElement;
  const node = $("#dock").lastElementChild;
  if (node) root.style.setProperty("--dock-room", `${node.offsetHeight + 46}px`);
  else root.style.removeProperty("--dock-room");
}

// A screen reader may not announce a node that arrives with a role, so the toast has none and its
// words go to a live region that is always on the page (index.html); the tray's news goes there too
// (dock.js). The region is emptied first and the words come in a later task, so the same words twice
// are a change again.
let saying = null;
export function say(text) {
  const live = $("#said");
  if (!live) return;
  clearTimeout(saying);
  if (live.textContent) live.textContent = "";
  if (text) saying = setTimeout(() => { live.textContent = text; }, 0);
}

// The toast leaves: it fades and goes down 10 px (160 ms ease-in), and is removed by time, not by
// the animation's end. `now`: at once, with no motion and no word to the tray, because a bar
// (dock.js) or another toast takes its place. Focus inside it goes to the page.
export function hideToast({ now = false } = {}) {
  if (now && leaving) {
    leaving.remove();
    leaving = null;
    makeRoom();
  }
  const node = shown;
  if (!node) return;
  shown = null;
  stopWaits();
  stopWaits = () => {};
  clearTimeout(timer);
  timer = null;
  line = null;
  say("");
  if (node.contains(document.activeElement)) $("#main").focus({ preventScroll: true });
  if (now) {
    node.remove();
    makeRoom();
    return;
  }
  animateTo(node, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(10px)" }], { dur: 160, ease: "ease-in", fill: "forwards" });
  leaving = node;
  later(() => {
    // Another toast or a bar took the place meanwhile: nothing is left to do.
    if (leaving !== node) return;
    leaving = null;
    node.remove();
    makeRoom();
    if (afterToast) afterToast();
  }, D(160));
}

// The pointer or focus on the toast holds its life; leaving lets it go on. The timer holds the
// time that is left, and the line is paused and played with it.
function pauseLife() {
  if (timer === null) return;
  clearTimeout(timer);
  timer = null;
  left -= Date.now() - since;
  if (line) line.pause();
}

function resumeLife() {
  if (timer !== null) return;
  since = Date.now();
  timer = setTimeout(hideToast, left);
  if (line) line.play();
}

// The life: a 2 px line runs down toward the left and the toast leaves at the end. Time decides,
// not the line's end: a hidden tab may never finish an animation, and a browser without one has
// no line.
function startLife(life) {
  left = D(LIFE_MS) || LIFE_MS;
  since = Date.now();
  timer = setTimeout(hideToast, left);
  line = null;
  try {
    if (typeof life.animate === "function") line = life.animate([{ transform: "scaleX(1)" }, { transform: "scaleX(0)" }], { duration: left, easing: "linear", fill: "forwards" });
  } catch (error) {
    console.error(error);
  }
}

// A button of the toast: the toast leaves and the action runs at once, not after the leaving. A
// press on a toast that is already leaving does nothing. Undo (`waits`) waits while another change
// is written: it says why, and a press does nothing. It stops following once the toast is hidden
// (`stopWaits`, hideToast).
function action(owner, label, run, iconName, waits = false) {
  const node = button(label, null);
  if (iconName) node.prepend(icon(iconName, 13));
  if (waits) {
    const follow = () => showWaits(node, busy.change);
    follow();
    stopWaits = onBusy(follow);
  }
  node.addEventListener("click", async () => {
    if (shown !== owner || (waits && busy.change)) return;
    hideToast();
    try {
      await run();
    } catch (error) {
      reportError(error);
    }
  });
  return node;
}

// A short note after a change, with Undo when it can be undone (`label`: other words for it, as
// "Undo all"), and `extra`, { label, run }, for one more button. A green check only for a state
// the server verified (applied, undone); never for an error.
export function toast(text, onUndo, { ok = false, label = "Undo", extra = null } = {}) {
  hideToast({ now: true });
  const host = $("#dock");
  const node = el("div", "toast");
  if (ok) {
    const tick = el("span", "tk");
    tick.append(icon("circle-check", 16));
    node.append(tick);
  }
  node.append(el("span", null, text));
  if (extra) node.append(action(node, extra.label, extra.run));
  if (onUndo) node.append(action(node, label, onUndo, "undo-2", true));
  const life = el("i", "life");
  life.setAttribute("aria-hidden", "true");
  node.append(life);
  // Whatever the dock showed (the tray's bar) gives way; focus in it goes to the page first.
  if (host.contains(document.activeElement)) $("#main").focus({ preventScroll: true });
  host.replaceChildren(node);
  shown = node;
  say(text);
  makeRoom();
  animateTo(node, [{ opacity: 0, transform: "translateY(14px)" }, { opacity: 1, transform: "none" }], { dur: 200 });
  startLife(life);
  const holds = new Set();
  const hold = (kind, on) => {
    if (shown !== node) return;
    if (on) holds.add(kind);
    else holds.delete(kind);
    if (holds.size) pauseLife();
    else resumeLife();
  };
  node.addEventListener("pointerenter", () => hold("pointer", true));
  node.addEventListener("pointerleave", () => hold("pointer", false));
  node.addEventListener("focusin", () => hold("focus", true));
  node.addEventListener("focusout", () => hold("focus", false));
}
