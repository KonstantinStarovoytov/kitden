// Gateway: drag a server from outside the gateway onto the map to preview its move (4.6, S.8).
import { el, reportError } from "./dom.js";
import { mapPreview, previewOnMap } from "./map-review.js";
import { dropAt, groupBox } from "./map.js";
import { moveBody } from "./panel.js";
import { busy, current, render } from "./store.js";

// How far a pointer moves on a block with a grip before the block follows it.
const DRAG_START = 4;

// The map as gateway.js drew it last, as it gives it (placeMoved): its view (map-view.js), the tree
// and the layout, and how the page draws again for the move's preview. A move started on the map:
// the block being dragged (`drag`), the server whose preview it started (`moving`, { id, name,
// kind }), and the block the map holds off its place (`home`, its id).
const onMap = { view: null, model: null, layout: null, redraw: () => {}, drag: null, moving: null, home: null };

// What a move started on the map shows (gatewayTree's `drop` or `preview`): the slot once the
// dragged block left its own group, and while its preview is prepared; the preview block while
// the preview is open (also from Details); else nothing.
export function movingOn() {
  const shown = onMap.drag || onMap.moving;
  const move = shown ? { name: shown.name, kind: shown.kind } : null;
  if (onMap.drag) return onMap.drag.open ? { drop: move } : {};
  // A preview that ended elsewhere (the List, another place) leaves nothing to show.
  if (mapPreview.phase === "idle") onMap.moving = null;
  if (!onMap.moving) return {};
  if (mapPreview.phase === "loading") return { drop: move };
  return mapPreview.change ? { preview: move } : {};
}

// The move whose preview ended ({ id, name, kind }), once: the map forgets it. Null while its
// preview runs, or with no move.
export function endedMove() {
  const ended = mapPreview.phase === "idle" ? onMap.moving : null;
  if (ended) onMap.moving = null;
  return ended;
}

// gateway.js drew the map in `view`, from `model` laid out as `layout`; `redraw` draws the page
// again for the move's preview. A block off its place stays where the map holds it: with the
// pointer, or on the slot while its preview is prepared. Let go, it glides back to its place.
export function placeMoved({ view, model, layout, redraw }) {
  Object.assign(onMap, { view, model, layout, redraw });
  if (onMap.drag) follow();
  else if (mapPreview.phase === "loading" && onMap.moving) park();
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
// amber line hides (so a click that wobbles moves nothing on the map). Let go on the Servers
// column, away from its own group, it starts the same preview as "Move into the gateway…";
// Escape, or a drop anywhere else, puts it back. Nothing is written before Apply. A click without
// a move selects the block as before; a grip press while a change is written does nothing.
export function pressGrip(event) {
  if (event.button !== 0 || busy.change || onMap.drag) return;
  const node = event.target.closest("button.block");
  const block = node && onMap.model.blocks.find((b) => node.dataset.focus === `block:${b.id}`);
  if (!block || !block.grip) return;
  const from = { x: event.clientX, y: event.clientY };
  const box = node.getBoundingClientRect();
  const grab = { x: from.x - box.left, y: from.y - box.top };
  const move = (e) => {
    const at = { x: e.clientX, y: e.clientY };
    if (!onMap.drag) {
      if (Math.hypot(at.x - from.x, at.y - from.y) < DRAG_START) return;
      onMap.drag = { id: block.id, name: block.name, kind: block.groupKey === "local" ? "local" : "remote", row: block.row, grab, at, open: false };
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

// The dragged block where the pointer holds it; the slot lights while a drop there would preview.
function follow() {
  const { drag, view } = onMap;
  const point = mapPoint(drag.at);
  if (!point || !view.node(drag.id)) return;
  view.hold(drag.id, { x: point.x - drag.grab.x, y: point.y - drag.grab.y });
  onMap.home = drag.id;
  view.box.classList.toggle("dropping", dropTarget(onMap.model, onMap.layout, point.x, point.y) === "servers");
}

// While its preview is prepared, the block waits on the slot (it glides there from where it was
// let go), and after a moment a spinner says the server is asked. The page draws again meanwhile,
// so the spinner is added once.
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
// Servers column, away from its own group, the preview of the move into the Kitden gateway
// starts; else the block goes back.
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
    onMap.moving = { id: drag.id, name: drag.name, kind: drag.kind };
    previewOnMap(body, onMap.redraw).catch(reportError);
    if (mapPreview.phase === "loading") return;
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
