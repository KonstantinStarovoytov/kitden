// Gateway: drag a server from outside the gateway onto the map to add its move to the tray (4.6,
// S.8).
import { el, reportError } from "./dom.js";
import { dropAt, groupBox } from "./map.js";
import { moveBody } from "./panel.js";
import { busy, current, render } from "./store.js";
import { addToTray, inTray, keyFor, tray } from "./tray.js";

// How far a pointer moves on a block with a grip before the block follows it.
const DRAG_START = 4;

// The map as gateway.js drew it last, as it gives it (placeMoved): its view (map-view.js), the tree
// and the layout. A move started on the map: the block being dragged (`drag`), the server whose
// move was dropped and is still being asked (`moving`, { id, name, key }: `key` is its row's in
// the tray), and the block the map holds off its place (`home`, its id).
const onMap = { view: null, model: null, layout: null, drag: null, moving: null, home: null };

// What a drag shows (gatewayTree's `drop`): the slot once the dragged block left its own group.
// A move dropped and still being asked shows its slot from its row in the tray.
export function movingOn() {
  const { drag } = onMap;
  return drag && drag.open ? { drop: { name: drag.name, kind: drag.kind } } : {};
}

// The row of a dropped move is still being asked: in the tray without its part yet, while the tray
// asks. After a refused preview it may have no part while nothing is asked.
const asked = (key) => tray.phase === "asking" && tray.rows.some((row) => row.key === key && !row.part);

// gateway.js drew the map in `view`, from `model` laid out as `layout`. A block off its place stays
// where the map holds it: with the pointer, or on the slot while its move is asked. Once its row
// answers or leaves the tray, it glides back to its place.
export function placeMoved({ view, model, layout }) {
  Object.assign(onMap, { view, model, layout });
  if (onMap.moving && !asked(onMap.moving.key)) onMap.moving = null;
  if (onMap.drag) follow();
  else if (onMap.moving) park();
  else if (onMap.home) goHome();
}

// The group outside the gateway, from its caption to its last block, holds (x, y) of the map: a
// dragged server is still at home there.
function atHome(model, layout, x, y) {
  const box = groupBox(model, layout, "group:outside");
  return Boolean(box) && x >= box.x && x <= box.x + box.w && y >= box.y && y <= box.y + box.h;
}

// Where a dragged server lands at (x, y) of the map: "servers" on the Servers column, else null and
// it goes back, as it does on its own group outside the gateway.
export function dropTarget(model, layout, x, y) {
  if (atHome(model, layout, x, y)) return null;
  return dropAt(layout, x, y) === "servers" ? "servers" : null;
}

// The preview request of a server dragged onto the map's Servers column: the same as "Move into
// the gateway…" with the Kitden gateway chosen, for the entries of its own row only. Null without
// a Kitden gateway.
export function dropBody(row, view) {
  const kitden = view.gateways.find((g) => g.kind === "kitden");
  return kitden ? moveBody(kitden, row.items) : null;
}

// A pointer goes down on a block with a grip. Once it moves 4 px the block follows it; once it
// leaves its own group, the slot "Drop to add" opens in its group of the Kitden gateway and its
// dotted line hides (so a click that wobbles moves nothing on the map). Let go on the Servers
// column, away from its own group, it adds the same move as "Move into the gateway…" to the tray;
// Escape, or a drop anywhere else, puts it back. Nothing is written before Apply. A click without
// a move selects the block as before; a grip press while a change is written does nothing. When
// the block first follows the pointer, `onStart()` runs before the map holds it: the page lets go
// of its selection there, so nothing it dims is left under the drag or its preview.
export function pressGrip(event, onStart = () => {}) {
  if (event.button !== 0 || busy.change || onMap.drag) return;
  const node = event.target.closest("button.block");
  const block = node && onMap.model.blocks.find((b) => node.dataset.focus === `block:${b.id}`);
  if (!block || !block.grip) return;
  const from = { x: event.clientX, y: event.clientY };
  const box = node.getBoundingClientRect();
  const grab = { x: from.x - box.left, y: from.y - box.top };
  // Where on the block the press is, as a share of its size: a layout that gives the block another
  // size under the drag (the map turns wide when Details close) keeps the pointer on it.
  const place = onMap.layout && onMap.layout.blocks.find((b) => b.id === block.id);
  const share = place && place.w && place.h ? { x: grab.x / place.w, y: grab.y / place.h } : null;
  const move = (e) => {
    const at = { x: e.clientX, y: e.clientY };
    if (!onMap.drag) {
      if (Math.hypot(at.x - from.x, at.y - from.y) < DRAG_START) return;
      onStart();
      onMap.drag = { id: block.id, name: block.name, kind: block.groupKey === "local" ? "local" : "remote", row: block.row, grab, share, at, open: false };
      document.documentElement.classList.add("grabbing");
    }
    onMap.drag.at = at;
    const point = mapPoint(at);
    if (!onMap.drag.open && point && !atHome(onMap.model, onMap.layout, point.x, point.y)) {
      onMap.drag.open = true;
      render(); // the slot opens; the block follows again once it is drawn
      return;
    }
    follow();
  };
  const stop = () => {
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", done);
    document.removeEventListener("pointercancel", done);
    document.removeEventListener("keydown", escape, true);
  };
  const done = (e) => {
    stop();
    if (onMap.drag) letGo(e && e.type === "pointerup" ? { x: e.clientX, y: e.clientY } : null);
  };
  // Escape puts the block back before Details or the map hear it.
  const escape = (e) => {
    if (e.key !== "Escape" || !onMap.drag) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    done(null);
  };
  document.addEventListener("pointermove", move);
  document.addEventListener("pointerup", done);
  document.addEventListener("pointercancel", done);
  document.addEventListener("keydown", escape, true);
}

// The map's block area, and a point of the page (`at`) in the area's own terms.
const mapArea = () => (onMap.view && onMap.view.box.isConnected ? onMap.view.area : null);
function mapPoint(at) {
  const area = mapArea();
  if (!area || !at) return null;
  const origin = area.getBoundingClientRect();
  return { x: at.x - origin.left, y: at.y - origin.top };
}

// Where the pointer holds the dragged block, from its top left: the spot of the press, in the size
// the layout gives the block now.
function grabOf(drag) {
  const place = drag.share && onMap.layout.blocks.find((b) => b.id === drag.id);
  return place ? { x: drag.share.x * place.w, y: drag.share.y * place.h } : drag.grab;
}

// The dragged block where the pointer holds it; the slot lights while a drop there would preview.
function follow() {
  const { drag, view } = onMap;
  const point = mapPoint(drag.at);
  if (!point || !view.node(drag.id)) return;
  const grab = grabOf(drag);
  view.hold(drag.id, { x: point.x - grab.x, y: point.y - grab.y });
  onMap.home = drag.id;
  view.box.classList.toggle("dropping", dropTarget(onMap.model, onMap.layout, point.x, point.y) === "servers");
}

// While its move is asked, the block waits on the slot (it glides there from where it was let go),
// and after a moment a spinner says the server is asked. The page draws again meanwhile, so the
// spinner is added once.
function park() {
  const { moving, layout, view } = onMap;
  const node = view.node(moving.id);
  const slot = layout.blocks.find((b) => b.id === `slot:${moving.name}`);
  if (!node || !slot) return;
  view.hold(moving.id, { x: slot.x, y: slot.y }, { glide: true });
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
  view.letGo(home);
}

// The pointer lets go at `point` (page coordinates), or Escape or a lost pointer (null). On the
// Servers column, away from its own group, the move into the Kitden gateway joins the tray at once
// (the map draws again as it joins, and the block waits on the slot); else, or when nothing can
// join now, the block goes back.
function letGo(point) {
  const drag = onMap.drag;
  onMap.drag = null;
  document.documentElement.classList.remove("grabbing");
  if (onMap.view) onMap.view.box.classList.remove("dropping");
  swallowClick();
  const at = mapPoint(point);
  const target = at ? dropTarget(onMap.model, onMap.layout, at.x, at.y) : null;
  const body = target === "servers" ? dropBody(drag.row, current("gateway")) : null;
  if (body) {
    onMap.moving = { id: drag.id, name: drag.name, key: keyFor(body) };
    addToTray(body).catch(reportError);
    if (inTray(onMap.moving.key)) return;
    onMap.moving = null;
  }
  render();
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
