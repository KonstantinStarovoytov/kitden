// Gateway: the drags of the map (4.7, gateway-notes 6). One engine (`startDrag`) runs each of
// them; a drop only adds a row to the tray. Today: a server from outside the gateway into it, a
// server in the Kitden gateway onto a client, a wire from a client that is not connected onto
// the gateway, and a row of the Add a server panel onto the map.
import { el, pageWaits, reportError } from "./dom.js";
import { foundClients } from "./gateway-details.js";
import { linkKey } from "./map.js";
import { CALM, animateTo, shake } from "./motion.js";
import { moveBody } from "./panel.js";
import { CLIENT_NAMES } from "./parts.js";
import { busy, current, data } from "./store.js";
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
// A server dragged out of the gateway: what its tip says until it is over a client, and where a
// client takes it: the pointer in the client's box, widened 24 px left, 40 right, 16 up and down.
const ON_CLIENT = "Drop on a client";
const NEAR_CLIENT = { left: 24, right: 40, up: 16, down: 16 };
// A client's wire: what its tip says until it is over the gateway, where the gateway takes it (the
// pointer in the gateway's box, widened 24 px each side and 16 up and down), and how a wire that
// misses fades.
const ON_GATEWAY = "Drop on the gateway";
const NEAR_GATEWAY = { side: 24, up: 16, down: 16 };
const MISS = { ms: 180, ease: CALM };
// A row of the Add a server panel (add-notes §4): where the pointer opens the slot, in map points,
// from 16 px left of the Gateway column to 194 px right of the Servers column (the mockup's 180 to
// 760, with the columns at 196 and 396 to 566), and from 20 px over the map's top to 4 px over the
// Outside caption. Its ghost flies onto the slot, or back onto its row.
const ADD_ZONE = { left: 16, right: 194, top: 20, above: 4 };
const ONTO_SLOT = { dur: 200, ease: CALM };
const BACK_HOME = { dur: 180, ease: CALM };

// The map as gateway.js drew it last, as it gives it (placeMoved): its view (map-view.js), the tree,
// the layout and how to draw the map again in place (`redraw`). A drag on the map (`drag`), the
// server whose move was dropped and is still being asked (`moving`, { id, name, key, at }: `key` is
// its row's in the tray, `at` where it waits, or none: on its slot), the block the map holds off
// its place (`home`, its id), and a dropped row of the Add panel whose row is still asked (`adding`,
// { key, name, kind }).
const onMap = { view: null, model: null, layout: null, redraw: () => {}, drag: null, moving: null, home: null, adding: null };

// What a drag shows (gatewayTree's `drop`): the slot, while the block or the row is over the
// gateway, and while a dropped row of the Add panel is asked.
export function movingOn() {
  const { drag, adding } = onMap;
  if (drag && drag.open) return { drop: { name: drag.name, kind: drag.group } };
  return adding && asked(adding.key) ? { drop: { name: adding.name, kind: adding.kind } } : {};
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
  if (onMap.adding && !asked(onMap.adding.key)) onMap.adding = null;
  if (onMap.home && !model.blocks.some((b) => b.id === onMap.home)) onMap.home = null;
  if (onMap.drag) {
    if (!DRAGS[onMap.drag.kind].still) follow();
  } else if (onMap.moving) park();
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
  out: { begin: beginOut, over: overOut, drop: dropOut },
  client: { still: true, begin: beginClient, over: overClient, drop: dropClient },
  add: { still: true, begin: beginAdd, over: overAdd, drop: dropAdd },
};

// A pointer goes down on the map. A server outside the gateway with a grip starts a drag into it,
// a server in the Kitden gateway (the whole block: it has no grip) a drag onto a client, and a
// client that can be connected (`drags`), whose connect is not in the tray, a wire to the gateway;
// a client a plugin connects says why it cannot. A press while a change is written, while another
// server's dropped move is asked, while another project is read, or on anything else, does
// nothing here. `onStart()` runs when the drag starts, before the map holds the block: the page
// lets go of its selection there.
export function pressGrip(event, onStart = () => {}) {
  if (event.button !== 0 || busy.change || pageWaits() || onMap.drag || !onMap.model) return;
  const node = event.target.closest("button.block");
  const block = node && onMap.model.blocks.find((b) => node.dataset.focus === `block:${b.id}`);
  if (!block || (onMap.moving && onMap.moving.id !== block.id)) return;
  if (block.grip) startDrag(event, block, "in", onStart);
  else if (leavesGateway(block)) startDrag(event, block, "out", onStart);
  else if (block.drags && kitdenGateway() && !inTray(keyFor(block.connect))) startDrag(event, block, "client", onStart);
  else if (block.kind === "client" && block.viaPlugin) sayWhy(event, block);
}

// A press on a free row of the Add a server panel (gateway-add.js gives its server's `name` and
// `kind`, the change it adds, `body`, and its `node`) starts a drag onto the map, while the map
// shows. The same waits as a press on the map hold it back.
export function pressRow(event, row) {
  if (event.button !== 0 || busy.change || pageWaits() || onMap.drag || !onMap.model || !mapArea()) return;
  startDrag(event, { id: `add:${row.name}`, ...row }, "add");
}

// The Kitden gateway's block on the map, or null (none, or a first run's slot).
const kitdenGateway = () => onMap.model.blocks.find((b) => b.kind === "gateway" && b.gateway.kind === "kitden") || null;

// A client a plugin connects cannot be dragged (nor one whose plugin entry is off): once the
// pointer moves as far as a drag would start, the tip says why in its plain look, by the pointer,
// until the pointer lets go. A click shows nothing.
function sayWhy(event, block) {
  const { view } = onMap;
  const name = CLIENT_NAMES[block.client];
  // An entry that is off says what the client's panel says.
  const words = block.pluginOff ? `${name}'s entry is off.` : `${name} gets Kitden from a plugin.`;
  const start = { x: event.clientX, y: event.clientY };
  let shown = false;
  const show = (e) => {
    if (!shown && Math.hypot(e.clientX - start.x, e.clientY - start.y) < DRAG_START) return;
    shown = true;
    view.tip(words, { at: areaPoint({ x: e.clientX, y: e.clientY }) });
  };
  const done = () => {
    document.removeEventListener("pointermove", show);
    document.removeEventListener("pointerup", done);
    document.removeEventListener("pointercancel", done);
    window.removeEventListener("blur", done);
    if (shown) view.untip();
  };
  document.addEventListener("pointermove", show);
  document.addEventListener("pointerup", done);
  document.addEventListener("pointercancel", done);
  window.addEventListener("blur", done);
}

// A server the Kitden gateway holds can move out to a client, unless a change takes it out.
const leavesGateway = (block) => block.kind === "held" && block.gateway.kind === "kitden" && !block.leaving;

// Why `client` cannot take the server `name`, when the page knows: the client is not on this Mac
// (or its settings cannot be read, as its panel says), or it sets up a server of that name on its
// own. Null when it can (the server may still refuse).
function whyNot(name, client) {
  const who = CLIENT_NAMES[client];
  if (data.clients && !foundClients().includes(client)) {
    const unreadable = data.clients.some((c) => c.id === client && c.status === "unreadable");
    return unreadable ? `${who}'s settings are not readable.` : `${who} is not on this Mac.`;
  }
  const view = current("gateway");
  const rows = Object.values((view && view.groups) || {}).flat();
  if (rows.some((row) => row.name === name && (row.columns || row.clients || []).includes(client))) return `${who} already has ${name}.`;
  return null;
}

// One drag of `block` (`kind`, DRAGS). The block takes the pointer (pointer capture) at the press;
// once it moves 5 px the block follows it 1:1 and keeps its press scale while the pointer is down.
// A let go asks the drag; one it does not take, Escape or a lost pointer glides the block home in
// 220 ms and leaves the tray as it was. A drag that ran swallows the click that ends it; a press
// that moved less is a click. The page hears the pointer on the document too, so a redraw that
// puts the map back on the page loses no move. A row of the Add panel brings its own `node`.
export function startDrag(event, block, kind, onStart = () => {}) {
  const hooks = DRAGS[kind];
  const node = block.node || event.target.closest("button.block");
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
      onMap.drag = { kind, id: block.id, name: block.name, block, grab, share, at, open: false };
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

// While its move is asked, the block waits where it was let go (`at`), or on the slot (it flies
// there from where it was let go, and the slot hides at once under it), and after a moment a
// spinner says the server is asked. The page draws again meanwhile, so the spinner is added once.
function park() {
  const { moving, layout, view } = onMap;
  const node = view.node(moving.id);
  const slot = moving.at ? null : layout.blocks.find((b) => b.id === `slot:${moving.name}`);
  if (!node || !(slot || moving.at)) return;
  if (slot) view.hold(moving.id, { x: slot.x, y: slot.y }, { glide: true, ms: DROP_MS, onto: slot.id });
  else view.hold(moving.id, moving.at);
  onMap.home = moving.id;
  if (node.querySelector(".spinner")) return;
  node.setAttribute("aria-busy", "true");
  node.append(el("span", "spinner late"));
}

// Back to its place: the map lets go of the block, and it glides there from where it was.
function goHome() {
  const { view, home } = onMap;
  onMap.home = null;
  unpark(home);
  view.homeIn(home, HOME_MS);
}

// A block that waited while its move was asked loses its spinner.
function unpark(id) {
  const node = onMap.view.node(id);
  if (!node) return;
  node.removeAttribute("aria-busy");
  for (const spinner of node.querySelectorAll(".spinner")) spinner.remove();
}

// A server in the Kitden gateway: the block, every client and its link from the gateway light, as a
// glance does, and the tip asks for a client. One whose dropped move is still asked is with the
// pointer again, so it waits nowhere now; a second drop replaces its row.
function beginOut(drag) {
  const { model, view } = onMap;
  if (onMap.moving && onMap.moving.id === drag.id) {
    onMap.moving = null;
    unpark(drag.id);
  }
  Object.assign(drag, { target: null, why: null });
  const clients = model.blocks.filter((b) => b.kind === "client").map((b) => b.id);
  const lines = model.links.filter((l) => l.to === drag.id && l.from.startsWith("gateway:")).map(linkKey);
  view.glance(new Set([drag.id, ...clients, ...lines]));
  tipOut(drag);
}

// The pointer over a client, and not over Details or the dock: a client that can take the server
// lights, and a wire runs from it to the block and follows it; one that cannot stays as it is and
// the tip says why. Off a client the light goes and the wire fades.
function overOut(drag) {
  const { view } = onMap;
  const point = covered(drag.at) ? null : pointOf(drag);
  const client = point ? clientAt(point) : null;
  if ((client && client.id) !== (drag.target && drag.target.id)) {
    drag.target = client;
    drag.why = client ? whyNot(drag.name, client.client) : null;
    view.unlightTarget();
    view.unwire();
    if (client && !drag.why) {
      view.lightTarget(client.id);
      view.wire(client.id, drag.id);
    }
  }
  tipOut(drag);
}

// What a drop does there: nothing yet, the reason a client cannot take it (plain), or the move.
function tipOut(drag) {
  const client = drag.target;
  const words = client ? drag.why || `Move into ${CLIENT_NAMES[client.client]}` : ON_CLIENT;
  onMap.view.tip(words, { on: Boolean(client && !drag.why) });
}

// The client block a map point is near: the first in order whose box, widened by NEAR_CLIENT,
// holds it; null for none.
function clientAt(point) {
  const { model, layout } = onMap;
  const near = (place) => Boolean(place) && point.x > place.x - NEAR_CLIENT.left && point.x < place.x + place.w + NEAR_CLIENT.right && point.y > place.y - NEAR_CLIENT.up && point.y < place.y + place.h + NEAR_CLIENT.down;
  return model.blocks.find((b) => b.kind === "client" && near(layout.blocks.find((place) => place.id === b.id))) || null;
}

// A drop on a client that can take the server adds its move out to the tray, the same change as
// the server panel's step (one row per server: a second drop replaces it), and the block waits
// where it was let go while the move is asked; its answer draws the preview, which glides from
// there into the Outside list. A drop on a client that cannot take it shakes the client, and the
// block goes home. The wire fades on any let go.
function dropOut(drag, at) {
  const { view } = onMap;
  view.unwire();
  const client = at && drag.target;
  if (!client) return false;
  if (drag.why) {
    const node = view.node(client.id);
    if (node) shake(node);
    return false;
  }
  const held = heldAt(drag);
  const body = { action: "gateway.move_out", targets: [{ client: client.client }], params: { server: drag.name } };
  onMap.moving = { id: drag.id, name: drag.name, key: keyFor(body), at: held && held.at };
  addToTray(body).catch(reportError);
  if (inTray(onMap.moving.key)) {
    park();
    return true;
  }
  onMap.moving = null;
  return false;
}

// A client that is not connected: it stays where it is; it and the gateway light, as a glance does
// (no links), and a plain wire runs from its right port to the pointer.
function beginClient(drag) {
  drag.gateway = kitdenGateway().id;
  drag.on = false;
  onMap.view.glance(new Set([drag.id, drag.gateway]));
}

// The pointer near the gateway (NEAR_GATEWAY), and not over Details or the dock: the gateway
// lights, the wire ends on its left port and the tip says a drop connects the client. Elsewhere the
// wire ends at the pointer and the tip asks for the gateway. The tip goes by the pointer.
function overClient(drag) {
  const { view, layout } = onMap;
  const pointer = pointOf(drag);
  const place = layout.blocks.find((b) => b.id === drag.gateway);
  const near = (at) => at.x > place.x - NEAR_GATEWAY.side && at.x < place.x + place.w + NEAR_GATEWAY.side && at.y > place.y - NEAR_GATEWAY.up && at.y < place.y + place.h + NEAR_GATEWAY.down;
  const on = Boolean(pointer && place && !covered(drag.at) && near(pointer));
  if (on !== drag.on) {
    drag.on = on;
    if (on) view.lightTarget(drag.gateway);
    else view.unlightTarget();
  }
  if (!pointer) return;
  view.wire(drag.id, on ? drag.gateway : pointer, { plain: true });
  view.tip(on ? `Connect ${CLIENT_NAMES[drag.block.client]}` : ON_GATEWAY, { on, at: pointer });
}

// A drop on the gateway takes the wire away at once and adds the client's connect to the tray (the
// map then draws its preview link); a miss fades the wire (180 ms CALM) and leaves the tray as it
// was.
function dropClient(drag, at) {
  const { view } = onMap;
  if (!at || !drag.on) {
    view.unwire(MISS);
    return false;
  }
  view.unwire({ ms: 0 });
  addToTray(drag.block.connect).catch(reportError);
  return true;
}

// A row of the Add panel: it fades (.dragging) and a copy of it (the ghost, style.css `.res.ghost`)
// follows the pointer on the page, over the panel and the dock too. The ghost is only a picture:
// no focus, no role. The Outside caption's top is where the gateway's room ends.
function beginAdd(drag) {
  const { node, kind } = drag.block;
  const box = node.getBoundingClientRect();
  const ghost = node.cloneNode(true);
  ghost.classList.add("ghost");
  for (const name of ["role", "tabindex", "aria-disabled"]) ghost.removeAttribute(name);
  delete ghost.dataset.focus;
  ghost.setAttribute("aria-hidden", "true");
  Object.assign(ghost.style, { left: `${box.left}px`, top: `${box.top}px`, width: `${box.width}px`, height: `${box.height}px` });
  document.body.append(ghost);
  node.classList.add("dragging");
  const caption = onMap.layout.blocks.find((b) => b.id === "group:outside");
  const kitden = kitdenGateway();
  Object.assign(drag, { ghost, box, line: caption ? caption.y : Infinity, group: kind === "local" ? "local" : "remote", gateway: kitden ? kitden.id : null });
}

// The ghost keeps the spot of the press under the pointer. With the pointer in the zone (inAddZone)
// and not over Details or the dock, the ghost takes the drop look (`.over`), the Kitden gateway
// lights and the slot opens in the row's own group, wherever the pointer is; off it, all three go.
function overAdd(drag) {
  const { ghost, box, grab } = drag;
  ghost.style.transform = `translate(${drag.at.x - box.left - grab.x}px, ${drag.at.y - box.top - grab.y}px)`;
  const point = covered(drag.at) ? null : pointOf(drag);
  const open = Boolean(point && drag.gateway && inAddZone(onMap.layout, point, drag.line));
  ghost.classList.toggle("over", open);
  if (open === drag.open) return;
  drag.open = open;
  if (open) onMap.view.lightTarget(drag.gateway);
  else onMap.view.unlightTarget();
  onMap.redraw();
}

// Whether a map point is where a row of the Add panel opens the slot (ADD_ZONE), with `line` the
// top of the Outside caption.
function inAddZone(layout, point, line) {
  const gateway = layout.columns.find((c) => c.id === "gateway");
  const servers = layout.columns.find((c) => c.id === "servers");
  if (!gateway || !servers) return false;
  return point.x > gateway.x - ADD_ZONE.left && point.x < servers.x + servers.w + ADD_ZONE.right && point.y > -ADD_ZONE.top && point.y < line - ADD_ZONE.above;
}

// A drop while the slot is open adds the same row as a click on the row: the slot stays while it
// is asked (movingOn), and the ghost flies onto it (200 ms CALM). Its answer turns the slot into the
// preview block, on the same spot (gateway.js addPreview, `from`). Any other let go, or a row the
// tray does not take, flies the ghost back onto its row (180 ms CALM) and leaves the tray as it was.
function dropAdd(drag, at) {
  const { body, name } = drag.block;
  const key = keyFor(body);
  if (drag.open && at) {
    onMap.adding = { key, name, kind: drag.group };
    addToTray(body).catch(reportError);
    if (inTray(key)) {
      const slot = onMap.layout.blocks.find((b) => b.id === `slot:${name}`);
      flyGhost(drag, slot && pageBox(slot), ONTO_SLOT);
      return true;
    }
    onMap.adding = null;
  }
  flyGhost(drag, null, BACK_HOME);
  return false;
}

// A box of the map (x, y, w, h) on the page.
function pageBox(place) {
  const origin = mapArea().getBoundingClientRect();
  return { left: origin.left + place.x, top: origin.top + place.y, width: place.w, height: place.h };
}

// The ghost flies from where it is onto `to` (a page box), or back onto its row, then goes, and the
// row comes back to full strength. Under reduced motion, and on a hidden page, it lands at once.
function flyGhost({ ghost, box, block }, to, { dur, ease }) {
  const size = (b) => ({ width: `${b.width}px`, height: `${b.height}px` });
  const end = to ? { transform: `translate(${to.left - box.left}px, ${to.top - box.top}px)`, ...size(to) } : { transform: "none", ...size(box) };
  animateTo(ghost, [{ transform: ghost.style.transform || "none", ...size(box) }, end], { dur: document.hidden ? 0 : dur, ease, fill: "forwards" }).then(() => {
    ghost.remove();
    block.node.classList.remove("dragging");
  });
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
