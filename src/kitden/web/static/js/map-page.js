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
export function goSwitched(place, params) {
  onSwitch.drawing = true;
  try {
    go(place, params);
  } finally {
    onSwitch.drawing = false;
  }
}

// The view `node` goes up 4 px and out in 120 ms ease-in, then `land()` runs; at once with no node
// or under reduced motion. Only the latest call lands.
export function leaveThen(node, land) {
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
