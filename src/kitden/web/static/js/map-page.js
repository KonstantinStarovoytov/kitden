// What the map pages (Gateway, Library) share around their map: the Map | List switch and how the
// view it leaves goes out.
import { $, button, el } from "./dom.js";
import { findChip } from "./map.js";
import { animateTo, D, glide } from "./motion.js";
import { go, state } from "./store.js";

// The view switch (gateway-notes 7.1). `leaving`: the view that shows is on its way out. `drawing`:
// the draw `go` starts comes from the switch, so its view comes in as one piece. `turn` counts the
// switches, so only the latest lands.
const onSwitch = { leaving: false, drawing: false, turn: 0 };

// Whether this draw of the page comes from the switch; asked once, at the start of the draw.
export function switchedNow() {
  const switched = onSwitch.drawing;
  onSwitch.drawing = false;
  return switched;
}

// The page's add button, beside Map | List: a soft-accent button that opens the add panel. It keeps
// the focus key the panel looks for (`add:servers`, `add:plugins`), so it looks pressed while the
// panel is open and gets focus back when it closes.
export function addHeadButton(label, key, onPress) {
  const add = button(label, () => onPress(add), "btn add");
  add.dataset.focus = key;
  add.setAttribute("aria-expanded", "false");
  return add;
}

// The add button and Map | List together at the head's end, so a narrow head wraps them as one.
export function headActions(...nodes) {
  const actions = el("div", "head-actions");
  actions.append(...nodes.filter(Boolean));
  return actions;
}

// The mark behind Map | List (or any pill) glides to a choice in 280 ms, under its own `key`.
export const glidePill = (seg, choice, key) => glide(seg, choice, key, { duration: 280 });

// Map or List on `place`, which shows `mode` now. The address keeps the choice (view=map|list), and
// Back switches back. `old()` is the view that shows (its box), `letGo()` lets go of a selection,
// and `shows()` says which view the page drew last.
export function modeSwitch(place, mode, { old, letGo, shows }) {
  const seg = el("div", "seg");
  seg.setAttribute("role", "group");
  seg.setAttribute("aria-label", "Show as");
  for (const [id, label] of [["map", "Map"], ["list", "List"]]) {
    const choice = button(label, () => switchView({ place, id, mode, seg, choice, old, letGo, shows }), "");
    choice.setAttribute("aria-pressed", String(mode === id));
    choice.dataset.focus = `view:${id}`;
    seg.append(choice);
  }
  return seg;
}

// The pill moves and the selection lets go; the view that shows goes up 4 px and out (120 ease-in);
// then the page draws the other, which comes in from 6 px below (260 CALM). Under reduced motion all
// of it lands at once. A second press while a view leaves does nothing, and a switch whose page went
// meanwhile (another place, Back) draws nothing.
function switchView({ place, id, mode, seg, choice, old, letGo, shows }) {
  if (id === mode || onSwitch.leaving) return;
  for (const other of seg.children) if (other.dataset.focus) other.setAttribute("aria-pressed", String(other === choice));
  glidePill(seg, choice, `${place}-view`);
  letGo();
  leaveThen(old(), () => {
    if (state.view === place && shows() === mode) goSwitched(place, { mode: id });
  });
}

// Go to the other view of `place` (`params`), which comes in as one piece (switchedNow).
function goSwitched(place, params) {
  onSwitch.drawing = true;
  try {
    go(place, params);
  } finally {
    onSwitch.drawing = false;
  }
}

// The view `node` goes up 4 px and out in 120 ms ease-in, then `land()` runs; at once with no node
// or under reduced motion. Only the latest call lands.
function leaveThen(node, land) {
  const turn = ++onSwitch.turn;
  const done = () => {
    onSwitch.leaving = false;
    if (turn === onSwitch.turn) land();
  };
  if (!node || !D(1)) {
    done();
    return;
  }
  onSwitch.leaving = true;
  const keyframes = [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(-4px)" }];
  animateTo(node, keyframes, { dur: 120, ease: "ease-in", fill: "forwards" }).then(done);
}

// The chip in the search box says how many blocks the search lights on the page shown (`found`, from
// map.js shownFound; null for no search). It is a live region: its words are set only when they
// change, so a redraw is quiet. The page draws it with each draw of the place, and the map when it
// draws again in place, or turns a page.
export function drawChip(found) {
  const chip = $("#find-chip");
  const words = findChip(found) || "";
  if (chip.textContent !== words) chip.textContent = words;
}

// A search on a map page lights its matches; when none of them is in the visible part of the page,
// the first one scrolls into view (smooth; at once under reduced motion). It never moves keyboard
// focus, never scrolls when a match is already in view, and does so once for one search text on one
// page, not on each draw again. `drawn` is true for a draw that has lit its matches.
const revealed = { key: "" };

// The part of `node` the person can see: its box cut by every scrolling ancestor's box and by the
// top bar and the hint strip that lie over the page. Null when nothing of it shows.
function seenPart(node) {
  const near = (rect) => ({ left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom });
  let seen = near(node.getBoundingClientRect());
  for (let up = node.parentElement; up && seen; up = up.parentElement) {
    const style = getComputedStyle(up);
    if ((style.overflowX === "visible" && style.overflowY === "visible") || up === document.body) continue;
    const box = up.getBoundingClientRect();
    seen = cut(seen, { left: box.left, right: box.right, top: box.top, bottom: box.bottom });
  }
  const bar = document.querySelector(".topbar");
  if (seen && bar) seen = cut(seen, { left: -Infinity, right: Infinity, top: bar.getBoundingClientRect().bottom, bottom: Infinity });
  return seen;
}

// The part of `a` inside `b`, or null.
export function cut(a, b) {
  const part = { left: Math.max(a.left, b.left), right: Math.min(a.right, b.right), top: Math.max(a.top, b.top), bottom: Math.min(a.bottom, b.bottom) };
  return part.right > part.left && part.bottom > part.top ? part : null;
}

export function revealMatch(place, box, text) {
  if (!text) {
    revealed.key = "";
    return;
  }
  const key = `${place}\n${text}`;
  if (revealed.key === key || !box || !box.isConnected) return;
  const lit = [...box.querySelectorAll(".block.found")];
  if (!lit.length) return;
  revealed.key = key;
  if (lit.some((node) => seenPart(node))) return;
  lit[0].scrollIntoView({ behavior: D(1) ? "smooth" : "auto", block: "center", inline: "nearest" });
}
