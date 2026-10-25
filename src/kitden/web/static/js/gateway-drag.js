// Gateway: the drags of the map (4.7, gateway-notes 6). One engine (`startDrag`) runs each of
// them; a drop only adds a row to the tray. Today: a server from outside the gateway into it.
import { el, reportError } from "./dom.js";
import { linkKey } from "./map.js";
import { moveBody } from "./panel.js";
import { busy, current } from "./store.js";
import { addToTray, inTray, keyFor, tray } from "./tray.js";

// How far a pointer moves on a block before the drag starts: less is a click.
const DRAG_START = 5;
// A dropped block flies onto its slot; one let go anywhere else glides home.
const DROP_MS = 200;
const HOME_MS = 220;
// Where a server outside the gateway goes in: its centre between 66 px left of the Servers column
// and 134 px right of it (the mockup's 330 to 700, with the column at 396 to 566), and above 4 px
// over the Outside caption as it was when the drag started.
const ZONE = { left: 66, right: 134, above: 4 };
// What a drop never lands on: the floating Details and the dock.
const COVERS = ["#drawer.open", "#dock"];

// The map as gateway.js drew it last, as it gives it (placeMoved): its view (map-view.js), the tree,
// the layout and how to draw the map again in place (`redraw`). A drag on the map (`drag`), the
// server whose move was dropped and is still being asked (`moving`, { id, name, key }: `key` is its
// row's in the tray), and the block the map holds off its place (`home`, its id).
const onMap = { view: null, model: null, layout: null, redraw: () => {}, drag: null, moving: null, home: null };

// What a drag shows (gatewayTree's `drop`): the slot, while the block is over the gateway.
export function movingOn() {
  const { drag } = onMap;
  return drag && drag.open ? { drop: { name: drag.name, kind: drag.group } } : {};
}

// The row of a dropped move is still being asked: in the tray without its part yet, while the tray
// asks. After a refused preview it may have no part while nothing is asked.
const asked = (key) => tray.phase === "asking" && tray.rows.some((row) => row.key === key && !row.part);

// gateway.js drew the map in `view`, from `model` laid out as `layout`. A block off its place stays
// where the map holds it: with the pointer, or on the slot while its move is asked. Once its row
// answers it has turned into the preview block (map-view.js hands its place over); once its row
// leaves the tray, it glides back to its place.
export function placeMoved({ view, model, layout, redraw = () => {} }) {
  Object.assign(onMap, { view, model, layout, redraw });
  if (onMap.moving && !asked(onMap.moving.key)) onMap.moving = null;
  if (onMap.home && !model.blocks.some((b) => b.id === onMap.home)) onMap.home = null;
  if (onMap.drag) follow();
  else if (onMap.moving) park();
  else if (onMap.home) goHome();
}

// The preview request of a server dragged into the gateway: the same as "Move into the gateway…"
// with the Kitden gateway chosen, for the entries of its own row only. Null without a Kitden
// gateway.
export function dropBody(row, view) {
  const kitden = view.gateways.find((g) => g.kind === "kitden");
  return kitden ? moveBody(kitden, row.items) : null;
}

// Whether a block whose centre is at `centre` (map point) is over the gateway: by the Servers
// column and above `line`, the top of the Outside caption when the drag started.
export function inZone(layout, centre, line) {
  const column = layout.columns.find((c) => c.id === "servers");
  if (!column) return false;
  return centre.x > column.x - ZONE.left && centre.x < column.x + column.w + ZONE.right && centre.y < line - ZONE.above;
}

// The drags, by kind. Each says what it does as the drag starts (`begin(drag)`), as the pointer
// moves (`over(drag)`; `drag.at` is the pointer in the page) and on a let go (`drop(drag, at)`, true
// when it took the drop; `at` is a map point, null for Escape, a lost pointer, a blur of the window
// or a point over Details or the dock). The engine holds the block with the pointer, unless the
// kind is `still` (the block stays where it is, as a client's wire does). A kind's tip goes by the
// block (`view.tip(text)`) or by the pointer (`view.tip(text, { at: pointOf(drag) })`).
export const DRAGS = {
  in: { begin: beginIn, over: overIn, drop: dropIn },
};

// A pointer goes down on the map. A server outside the gateway with a grip starts a drag into it;
// a press while a change is written, or on anything else, does nothing here. `onStart()` runs when
// the drag starts, before the map holds the block: the page lets go of its selection there.
export function pressGrip(event, onStart = () => {}) {
  if (event.button !== 0 || busy.change || onMap.drag || !onMap.model) return;
  const node = event.target.closest("button.block");
  const block = node && onMap.model.blocks.find((b) => node.dataset.focus === `block:${b.id}`);
  if (block && block.grip) startDrag(event, block, "in", onStart);
}

// One drag of `block` (`kind`, DRAGS). The block takes the pointer (pointer capture) at the press;
// once it moves 5 px the block follows it 1:1 and keeps its press scale while the pointer is down.
// A let go asks the drag; one it does not take, Escape or a lost pointer glides the block home in
// 220 ms and leaves the tray as it was. A drag that ran swallows the click that ends it; a press
// that moved less is a click. The page hears the pointer on the document too, so a redraw that
// puts the map back on the page loses no move.
export function startDrag(event, block, kind, onStart = () => {}) {
  const hooks = DRAGS[kind];
  const node = event.target.closest("button.block");
  try {
    node.setPointerCapture(event.pointerId);
  } catch {
    // A pointer that is gone already: the document still hears it.
  }
  const from = { x: event.clientX, y: event.clientY };
  const box = node.getBoundingClientRect();
  const grab = { x: from.x - box.left, y: from.y - box.top };
  // Where on the block the press is, as a share of its size: a layout that gives the block another
  // size under the drag (the map turns wide when Details close) keeps the pointer on it.
  const place = onMap.layout && onMap.layout.blocks.find((b) => b.id === block.id);
  const share = place && place.w && place.h ? { x: grab.x / place.w, y: grab.y / place.h } : null;
  const move = (e) => {
    const at = { x: e.clientX, y: e.clientY };
    const starts = !onMap.drag;
    if (starts) {
      if (Math.hypot(at.x - from.x, at.y - from.y) < DRAG_START) return;
      onStart();
      onMap.drag = { id: block.id, name: block.name, block, grab, share, at, open: false };
      document.documentElement.classList.add("grabbing");
    }
    onMap.drag.at = at;
    if (!hooks.still) follow();
    if (starts) hooks.begin(onMap.drag);
    hooks.over(onMap.drag);
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
    if (!onMap.drag) return;
    const up = e && e.type === "pointerup";
    if (up) move(e);
    letGo(hooks, up ? { x: e.clientX, y: e.clientY } : null);
  };
  // Escape puts the block back before Details or the map hear it. The pointer is still down: the
  // click of its release, which the captured block would hear, selects nothing either.
  const escape = (e) => {
    if (e.key !== "Escape" || !onMap.drag) return;
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

// The map's block area, and a point of the page (`at`) in the area's own terms (`pointOf` for a
// drag's pointer): null over the floating Details or the dock, where nothing lands.
const mapArea = () => (onMap.view && onMap.view.box.isConnected ? onMap.view.area : null);
// The pointer of a drag in the map, also over Details or the dock (for its tip).
export function pointOf(drag) {
  return areaPoint(drag.at);
}

function areaPoint(at) {
  const area = mapArea();
  if (!area || !at) return null;
  const origin = area.getBoundingClientRect();
  return { x: at.x - origin.left, y: at.y - origin.top };
}

function mapPoint(at) {
  return at && !covered(at) ? areaPoint(at) : null;
}

function covered(at) {
  return COVERS.some((selector) => {
    const node = document.querySelector(selector);
    const box = node && node.getBoundingClientRect();
    return Boolean(box && box.width && box.height) && at.x >= box.left && at.x <= box.right && at.y >= box.top && at.y <= box.bottom;
  });
}

// Where the pointer holds the dragged block, from its top left: the spot of the press, in the size
// the layout gives the block now.
function grabOf(drag) {
  const place = drag.share && onMap.layout.blocks.find((b) => b.id === drag.id);
  return place ? { x: drag.share.x * place.w, y: drag.share.y * place.h } : drag.grab;
}

// The dragged block's top left at the pointer, in the map, and its centre. Null where the map is
// gone. Over Details or the dock the block still follows the pointer.
function heldAt(drag) {
  const area = mapArea();
  if (!area) return null;
  const origin = area.getBoundingClientRect();
  const grab = grabOf(drag);
  const at = { x: drag.at.x - origin.left - grab.x, y: drag.at.y - origin.top - grab.y };
  const place = onMap.layout.blocks.find((b) => b.id === drag.id);
  return { at, centre: place ? { x: at.x + place.w / 2, y: at.y + place.h / 2 } : at };
}

// The dragged block where the pointer holds it, pressed.
function follow() {
  const { drag, view } = onMap;
  const held = heldAt(drag);
  if (!held || !view.node(drag.id)) return;
  view.hold(drag.id, held.at, { pressed: true });
  onMap.home = drag.id;
}

// A server from outside the gateway: the block, the gateway and its dotted lines light, as a glance
// does; the Outside caption's top is where the gateway's room ends.
function beginIn(drag) {
  const { model, layout, view } = onMap;
  const caption = layout.blocks.find((b) => b.id === "group:outside");
  drag.line = caption ? caption.y : Infinity;
  drag.group = drag.block.groupKey === "local" ? "local" : "remote";
  const kitden = model.blocks.find((b) => b.kind === "gateway" && b.gateway.kind === "kitden");
  drag.gateway = kitden ? kitden.id : null;
  const lines = model.links.filter((l) => l.to === drag.id).map(linkKey);
  view.glance(new Set([drag.id, ...(drag.gateway ? [drag.gateway] : []), ...lines]));
}

// Its centre over the gateway (inZone), and not over Details or the dock: the gateway lights and the
// slot opens at the end of the block's own group (the map draws again in place); off it, both go.
function overIn(drag) {
  const held = heldAt(drag);
  const open = Boolean(held && drag.gateway && !covered(drag.at) && inZone(onMap.layout, held.centre, drag.line));
  if (open === drag.open) return;
  drag.open = open;
  if (open) onMap.view.lightTarget(drag.gateway);
  else onMap.view.unlightTarget();
  onMap.redraw();
}

// A drop while the slot is open adds the same move as "Move into the gateway…" to the tray, and the
// block flies onto the slot (200 ms OUT3) and waits there while the move is asked.
function dropIn(drag, at) {
  if (!drag.open || !at) return false;
  const body = dropBody(drag.block.row, current("gateway"));
  if (!body) return false;
  onMap.moving = { id: drag.id, name: drag.name, key: keyFor(body) };
  addToTray(body).catch(reportError);
  if (inTray(onMap.moving.key)) {
    park();
    return true;
  }
  onMap.moving = null;
  return false;
}

// While its move is asked, the block waits on the slot (it flies there from where it was let go,
// and the slot hides at once under it), and after a moment a spinner says the server is asked. The page draws again meanwhile, so the
// spinner is added once.
function park() {
  const { moving, layout, view } = onMap;
  const node = view.node(moving.id);
  const slot = layout.blocks.find((b) => b.id === `slot:${moving.name}`);
  if (!node || !slot) return;
  view.hold(moving.id, { x: slot.x, y: slot.y }, { glide: true, ms: DROP_MS, onto: slot.id });
  onMap.home = moving.id;
  if (node.querySelector(".spinner")) return;
  node.setAttribute("aria-busy", "true");
  node.append(el("span", "spinner late"));
}

// Back to its place: the map lets go of the block, and it glides there from where it was.
function goHome() {
  const { view, home } = onMap;
  onMap.home = null;
  const node = view.node(home);
  if (node) {
    node.removeAttribute("aria-busy");
    for (const spinner of node.querySelectorAll(".spinner")) spinner.remove();
  }
  view.homeIn(home, HOME_MS);
}

// The pointer lets go at `point` (page coordinates), or Escape, a lost pointer or a blur (null). The tip, the
// target's light and the glance go; the drag takes the drop, or the block glides home. A slot that
// was open closes as the map draws again.
function letGo(hooks, point) {
  const drag = onMap.drag;
  onMap.drag = null;
  document.documentElement.classList.remove("grabbing");
  swallowClick();
  const { view } = onMap;
  view.untip();
  view.unlightTarget();
  view.glance(null);
  if (hooks.drop(drag, point && mapPoint(point))) return;
  if (drag.open) onMap.redraw();
  if (onMap.home) goHome();
}

// The click that ends a drag selects nothing.
function swallowClick() {
  const swallow = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };
  document.addEventListener("click", swallow, { capture: true, once: true });
  setTimeout(() => document.removeEventListener("click", swallow, { capture: true }), 0);
}
