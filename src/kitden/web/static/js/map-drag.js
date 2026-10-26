// The drag engine every map shares (gateway-notes 6, library-notes §4). A page gives it its own
// map (`map`) and its drags by kind (`hooks`); a drop only adds a row to the tray.
//
// `map` is the page's map state: `view` (map-view.js), `model` (the tree) and `layout` as drawn
// last, `redraw()` to draw the map again in place, `drag` (the drag that runs, or null), `home` (the
// id of the block the map holds off its place) and, if the page needs it, `onHome(id)`, which runs
// as that block goes home.
//
// Each kind in `hooks` says what it does as the drag starts (`begin(drag)`), as the pointer moves
// (`over(drag)`; `drag.at` is the pointer in the page) and on a let go (`drop(drag, at)`, true when
// it took the drop; `at` is a map point, null for Escape, a lost pointer, a blur of the window or a
// point over Details or the dock). The engine holds the block with the pointer, unless the kind is
// `still` (the block stays where it is, as a client's wire does).
import { animateTo } from "./motion.js";

// How far a pointer moves on a block before the drag starts: less is a click.
export const DRAG_START = 5;
// A block let go where nothing took it glides home.
export const HOME_MS = 220;
// What a drop never lands on: the floating Details and the dock.
const COVERS = ["#drawer.open", "#dock"];
// A block dragged onto a client: what its tip says until it is over one, and where a client takes
// it: the pointer in the client's box, widened 24 px left, 40 right, 16 up and down.
export const ON_CLIENT = "Drop on a client";
export const NEAR_CLIENT = { left: 24, right: 40, up: 16, down: 16 };

const onCount = (node) => Boolean(node.dataset && node.dataset.focus && node.dataset.focus.startsWith("count:"));

// One drag of `block` (`kind`, one of `hooks`). The block takes the pointer (pointer capture) at the
// press; once it moves 5 px the block follows it 1:1 and keeps its press scale while the pointer is
// down. A let go asks the drag; one it does not take, Escape or a lost pointer glides the block home
// in 220 ms and leaves the tray as it was. A drag that ran swallows the click that ends it; a press
// that moved less is a click. The page hears the pointer on the document too, so a redraw that
// puts the map back on the page loses no move. A row of an Add panel brings its own `node`.
// `onStart()` runs when the drag starts, before the map holds the block.
export function startDrag(event, block, kind, { hooks, map, onStart = () => {} }) {
  const kindHooks = hooks[kind];
  // A press on a block's count holds the count, which hears the click that ends it; the block is what moves.
  const pressed = block.node || event.target.closest("button.block, button.block-count");
  const node = onCount(pressed) ? map.view.node(block.id) : pressed;
  try {
    pressed.setPointerCapture(event.pointerId);
  } catch {
    // A pointer that is gone already: the document still hears it.
  }
  const from = { x: event.clientX, y: event.clientY };
  const box = node.getBoundingClientRect();
  const grab = { x: from.x - box.left, y: from.y - box.top };
  // Where on the block the press is, as a share of its size: a layout that gives the block another
  // size under the drag (the map turns wide when Details close) keeps the pointer on it.
  const place = map.layout && map.layout.blocks.find((b) => b.id === block.id);
  const share = place && place.w && place.h ? { x: grab.x / place.w, y: grab.y / place.h } : null;
  const move = (e) => {
    const at = { x: e.clientX, y: e.clientY };
    const starts = !map.drag;
    if (starts) {
      if (Math.hypot(at.x - from.x, at.y - from.y) < DRAG_START) return;
      onStart();
      map.drag = { kind, id: block.id, name: block.name, block, grab, share, at, open: false };
      document.documentElement.classList.add("grabbing");
    }
    map.drag.at = at;
    if (!kindHooks.still) follow(map);
    if (starts) kindHooks.begin(map.drag);
    kindHooks.over(map.drag);
  };
  const stop = () => {
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", done);
    document.removeEventListener("pointercancel", done);
    document.removeEventListener("keydown", escape, true);
    window.removeEventListener("blur", lost);
  };
  // A let go where the last move was not lands where it is.
  const done = (e) => {
    stop();
    if (!map.drag) return;
    const up = e && e.type === "pointerup";
    if (up) move(e);
    letGo(map, kindHooks, up ? { x: e.clientX, y: e.clientY } : null);
  };
  // Escape puts the block back before Details or the map hear it. The pointer is still down: the
  // click of its release, which the captured block would hear, selects nothing either.
  const escape = (e) => {
    if (e.key !== "Escape" || !map.drag) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    done(null);
    document.addEventListener("pointerup", swallowClick, { capture: true, once: true });
  };
  // A window that loses focus (another app, a dialog) ends the drag: nothing stays held.
  const lost = () => done(null);
  document.addEventListener("pointermove", move);
  document.addEventListener("pointerup", done);
  document.addEventListener("pointercancel", done);
  document.addEventListener("keydown", escape, true);
  window.addEventListener("blur", lost);
}

// The map's block area while the map is on the page, else null.
export const mapArea = (map) => (map.view && map.view.box.isConnected ? map.view.area : null);

// The pointer of a drag in the map, also over Details or the dock (for its tip).
export function pointOf(map, drag) {
  return areaPoint(map, drag.at);
}

// A point of the page (`at`) in the map area's own terms; null with no map.
export function areaPoint(map, at) {
  const area = mapArea(map);
  if (!area || !at) return null;
  const origin = area.getBoundingClientRect();
  return { x: at.x - origin.left, y: at.y - origin.top };
}

// The same, but null over the floating Details or the dock, where nothing lands.
function mapPoint(map, at) {
  return at && !covered(at) ? areaPoint(map, at) : null;
}

// Whether a point of the page is over the floating Details or the dock.
export function covered(at) {
  return COVERS.some((selector) => {
    const node = document.querySelector(selector);
    const box = node && node.getBoundingClientRect();
    return Boolean(box && box.width && box.height) && at.x >= box.left && at.x <= box.right && at.y >= box.top && at.y <= box.bottom;
  });
}

// Where the pointer holds the dragged block, from its top left: the spot of the press, in the size
// the layout gives the block now.
function grabOf(map, drag) {
  const place = drag.share && map.layout.blocks.find((b) => b.id === drag.id);
  return place ? { x: drag.share.x * place.w, y: drag.share.y * place.h } : drag.grab;
}

// The dragged block's top left at the pointer, in the map, and its centre. Null where the map is
// gone. Over Details or the dock the block still follows the pointer.
export function heldAt(map, drag) {
  const area = mapArea(map);
  if (!area) return null;
  const origin = area.getBoundingClientRect();
  const grab = grabOf(map, drag);
  const at = { x: drag.at.x - origin.left - grab.x, y: drag.at.y - origin.top - grab.y };
  const place = map.layout.blocks.find((b) => b.id === drag.id);
  return { at, centre: place ? { x: at.x + place.w / 2, y: at.y + place.h / 2 } : at };
}

// The dragged block where the pointer holds it, pressed.
export function follow(map) {
  const { drag, view } = map;
  const held = heldAt(map, drag);
  if (!held || !view.node(drag.id)) return;
  view.hold(drag.id, held.at, { pressed: true });
  map.home = drag.id;
}

// Back to its place: the map lets go of the block, and it glides there from where it was.
export function goHome(map) {
  const { view, home } = map;
  map.home = null;
  if (map.onHome) map.onHome(home);
  view.homeIn(home, HOME_MS);
}

// The client block a map point is near: the first in order whose box, widened by NEAR_CLIENT,
// holds it; null for none.
export function clientAt(map, point) {
  const { model, layout } = map;
  const near = (place) => Boolean(place) && point.x > place.x - NEAR_CLIENT.left && point.x < place.x + place.w + NEAR_CLIENT.right && point.y > place.y - NEAR_CLIENT.up && point.y < place.y + place.h + NEAR_CLIENT.down;
  return model.blocks.find((b) => b.kind === "client" && near(layout.blocks.find((place) => place.id === b.id))) || null;
}

// A box of the map (x, y, w, h) on the page.
export function pageBox(map, place) {
  const origin = mapArea(map).getBoundingClientRect();
  return { left: origin.left + place.x, top: origin.top + place.y, width: place.w, height: place.h };
}

// A row of an Add panel lifts: it fades (.dragging) and a copy of it (the ghost, style.css
// `.res.ghost`) goes on the page over it, to follow the pointer over the panel and the dock too.
// The ghost is only a picture: no focus, no role. Gives { ghost, box }, `box` the row's place.
export function liftGhost(node) {
  const box = node.getBoundingClientRect();
  const ghost = node.cloneNode(true);
  ghost.classList.add("ghost");
  for (const name of ["role", "tabindex", "aria-disabled"]) ghost.removeAttribute(name);
  delete ghost.dataset.focus;
  ghost.setAttribute("aria-hidden", "true");
  Object.assign(ghost.style, { left: `${box.left}px`, top: `${box.top}px`, width: `${box.width}px`, height: `${box.height}px` });
  document.body.append(ghost);
  node.classList.add("dragging");
  return { ghost, box };
}

// The ghost keeps the spot of the press under the pointer.
export function moveGhost(drag) {
  const { ghost, box, grab, at } = drag;
  ghost.style.transform = `translate(${at.x - box.left - grab.x}px, ${at.y - box.top - grab.y}px)`;
}

// A panel row's ghost flies from where it is onto `to` (a page box), or back onto its row, then
// goes, and the row comes back to full strength. Under reduced motion, and on a hidden page, it
// lands at once.
export function flyGhost({ ghost, box, block }, to, { dur, ease }) {
  const size = (b) => ({ width: `${b.width}px`, height: `${b.height}px` });
  const end = to ? { transform: `translate(${to.left - box.left}px, ${to.top - box.top}px)`, ...size(to) } : { transform: "none", ...size(box) };
  animateTo(ghost, [{ transform: ghost.style.transform || "none", ...size(box) }, end], { dur: document.hidden ? 0 : dur, ease, fill: "forwards" }).then(() => {
    ghost.remove();
    block.node.classList.remove("dragging");
  });
}

// The pointer lets go at `point` (page coordinates), or Escape, a lost pointer or a blur (null).
// The tip, the target's light and the glance go; the drag takes the drop, or the block glides
// home. A slot that was open closes as the map draws again.
function letGo(map, kindHooks, point) {
  const drag = map.drag;
  map.drag = null;
  document.documentElement.classList.remove("grabbing");
  swallowClick();
  const { view } = map;
  view.untip();
  view.unlightTarget();
  view.glance(null);
  if (kindHooks.drop(drag, point && mapPoint(map, point))) return;
  if (drag.open) map.redraw();
  if (map.home) goHome(map);
}

// The click that ends a drag selects nothing.
export function swallowClick() {
  const swallow = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };
  document.addEventListener("click", swallow, { capture: true, once: true });
  setTimeout(() => document.removeEventListener("click", swallow, { capture: true }), 0);
}
