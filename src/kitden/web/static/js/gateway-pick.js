// Gateway: picking several servers outside the gateway at once, to drag them in together (Part 2 of
// the 2026-11-01 design). A band drawn from empty map space picks what it meets; Shift- or
// Cmd-click picks or unpicks one; Escape or a click on empty map clears. Only a server outside the
// gateway that has a grip can be picked. The drag itself is gateway-drag.js's `group` kind.
import { el, plural } from "./dom.js";
import { areaPoint, DRAG_START, listenPointer, swallowClick } from "./map-drag.js";
import { animateTo } from "./motion.js";

// The ids picked now, in the order they were picked, and how many servers the last band met that
// cannot move in (`stuck`).
export const pick = { ids: new Set(), stuck: 0 };

// The hint line while something is picked, or while the band left servers out: those have no grip,
// and their Details say why.
export function PICK_HINT(n, stuck = 0) {
  if (!n) return `${plural(stuck, "server", "servers")} can't move into the gateway · ${stuck === 1 ? "its Details say" : "their Details say"} why · Esc clears`;
  const left = stuck ? ` · ${stuck} can't move in, see their Details` : "";
  return `${plural(n, "server", "servers")} picked${left} · drag one onto the gateway · Esc clears`;
}

// The band fades out in 120 ms when it is let go.
const BAND_OUT = { dur: 120, ease: "ease-in" };

// Whether a block can be picked: a server outside the gateway with a grip.
export function pickable(block) {
  return Boolean(block) && block.kind === "outside" && Boolean(block.grip);
}

// The blocks for which `which(block)` holds whose place meets the box from map point `a` to map
// point `b`, in map order.
function met(model, layout, a, b, which) {
  const [left, right] = [Math.min(a.x, b.x), Math.max(a.x, b.x)];
  const [top, bottom] = [Math.min(a.y, b.y), Math.max(a.y, b.y)];
  const ids = new Set(model.blocks.filter(which).map((block) => block.id));
  return layout.blocks
    .filter((p) => ids.has(p.id) && p.x < right && p.x + p.w > left && p.y < bottom && p.y + p.h > top)
    .map((p) => p.id);
}

// The pickable blocks the band meets.
export const bandHits = (model, layout, a, b) => met(model, layout, a, b, pickable);

// How many servers outside the gateway the band meets that cannot move in (no grip).
export const bandStuck = (model, layout, a, b) => met(model, layout, a, b, (block) => block.kind === "outside" && !block.grip).length;

// Pick or unpick one block; false for a block that cannot be picked.
export function togglePick(model, id) {
  if (!pickable(model.blocks.find((block) => block.id === id))) return false;
  if (pick.ids.has(id)) pick.ids.delete(id);
  else pick.ids.add(id);
  return true;
}

// Keep only what `model` still has as pickable (after a read, an Apply, another project).
export function keepPickable(model) {
  const can = new Set(model.blocks.filter(pickable).map((block) => block.id));
  pick.ids = new Set([...pick.ids].filter((id) => can.has(id)));
}

// Clear the pick; true when it held anything.
export function clearPick() {
  const had = pick.ids.size > 0 || pick.stuck > 0;
  pick.ids = new Set();
  pick.stuck = 0;
  return had;
}

// A press on empty map space draws a band once the pointer moves 5 px (DRAG_START): it follows the
// pointer with no easing and picks what it meets, added to what was picked before. `map` is the
// page's map ({ view, model, layout }); `onPick()` runs after every change of the pick. A band that
// meets tool blocks picks those instead (`onTools(ids)`, the tool blocks it meets) and leaves the
// servers' pick alone. A let go or Escape fades the band out; the click that ends it clears nothing.
export function pressBand(event, { map, onPick, onTools = null }) {
  if (event.button !== 0 || onScrollbar(event, map.view.box)) return;
  const from = { x: event.clientX, y: event.clientY };
  const before = new Set(pick.ids);
  let band = null;
  let start = null;
  const move = (e) => {
    const at = { x: e.clientX, y: e.clientY };
    if (!band) {
      if (Math.hypot(at.x - from.x, at.y - from.y) < DRAG_START) return;
      start = areaPoint(map, from);
      if (!start) return;
      band = el("div", "map-band");
      map.view.area.append(band);
    }
    const end = areaPoint(map, at);
    if (!end) return;
    const [x, y] = [Math.min(start.x, end.x), Math.min(start.y, end.y)];
    // Its place by transform; its size as it is, so its 1 px edge stays 1 px.
    band.style.transform = `translate(${x}px, ${y}px)`;
    band.style.width = `${Math.abs(end.x - start.x)}px`;
    band.style.height = `${Math.abs(end.y - start.y)}px`;
    const tools = onTools ? met(map.model, map.layout, start, end, (block) => block.kind === "tool") : [];
    if (tools.length) {
      onTools(tools);
      return;
    }
    pick.ids = new Set([...before, ...bandHits(map.model, map.layout, start, end)]);
    pick.stuck = bandStuck(map.model, map.layout, start, end);
    onPick();
  };
  // A let go, Escape or the window losing focus (another app, a dialog) ends the band.
  const done = (e) => {
    if (!band) return;
    if (e && e.type === "pointerup") swallowClick();
    const gone = band;
    animateTo(gone, [{ opacity: 1 }, { opacity: 0 }], { ...BAND_OUT, fill: "forwards" }).then(() => gone.remove());
  };
  listenPointer({ move, done, held: () => Boolean(band) });
}

// A press on the map box's own scrollbar, past its content (clientWidth and clientHeight leave the
// scrollbars out): it scrolls the map, and draws no band.
function onScrollbar(event, box) {
  if (!box || event.target !== box || typeof event.offsetX !== "number") return false;
  return event.offsetX >= box.clientWidth || event.offsetY >= box.clientHeight;
}
