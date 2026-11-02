// Gateway: picking several servers outside the gateway at once, to drag them in together (Part 2 of
// the 2026-11-01 design). A band drawn from empty map space picks what it meets; Shift- or
// Cmd-click picks or unpicks one; Escape or a click on empty map clears. Only a server outside the
// gateway that has a grip can be picked. The drag itself is gateway-drag.js's `group` kind.
import { el, plural } from "./dom.js";
import { areaPoint, DRAG_START, swallowClick } from "./map-drag.js";
import { animateTo } from "./motion.js";

// The ids picked now, in the order they were picked.
export const pick = { ids: new Set() };

// The hint line while something is picked.
export const PICK_HINT = (n) => `${plural(n, "server", "servers")} picked · drag one onto the gateway · Esc clears`;

// The band fades out in 120 ms when it is let go.
const BAND_OUT = { dur: 120, ease: "ease-in" };

// Whether a block can be picked: a server outside the gateway with a grip.
export function pickable(block) {
  return Boolean(block) && block.kind === "outside" && Boolean(block.grip);
}

// The pickable blocks whose place meets the box from map point `a` to map point `b`, in map order.
export function bandHits(model, layout, a, b) {
  const [left, right] = [Math.min(a.x, b.x), Math.max(a.x, b.x)];
  const [top, bottom] = [Math.min(a.y, b.y), Math.max(a.y, b.y)];
  const can = new Set(model.blocks.filter(pickable).map((block) => block.id));
  return layout.blocks
    .filter((p) => can.has(p.id) && p.x < right && p.x + p.w > left && p.y < bottom && p.y + p.h > top)
    .map((p) => p.id);
}

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
  const had = pick.ids.size > 0;
  pick.ids = new Set();
  return had;
}

// A press on empty map space draws a band once the pointer moves 5 px (DRAG_START): it follows the
// pointer with no easing and picks what it meets, added to what was picked before. `map` is the
// page's map ({ view, model, layout }); `onPick()` runs after every change of the pick. A let go or
// Escape fades the band out; the click that ends it clears nothing.
export function pressBand(event, { map, onPick }) {
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
    pick.ids = new Set([...before, ...bandHits(map.model, map.layout, start, end)]);
    onPick();
  };
  // The window losing focus (another app, a dialog) ends the band as a let go would.
  const blur = () => done(null);
  const stop = () => {
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", done);
    document.removeEventListener("pointercancel", done);
    document.removeEventListener("keydown", escape, true);
    window.removeEventListener("blur", blur);
  };
  const done = (e) => {
    stop();
    if (!band) return;
    if (e && e.type === "pointerup") swallowClick();
    const gone = band;
    animateTo(gone, [{ opacity: 1 }, { opacity: 0 }], { ...BAND_OUT, fill: "forwards" }).then(() => gone.remove());
  };
  const escape = (e) => {
    if (e.key !== "Escape" || !band) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    done(null);
  };
  document.addEventListener("pointermove", move);
  document.addEventListener("pointerup", done);
  document.addEventListener("pointercancel", done);
  document.addEventListener("keydown", escape, true);
  window.addEventListener("blur", blur);
}

// A press on the map box's own scrollbar, past its content (clientWidth and clientHeight leave the
// scrollbars out): it scrolls the map, and draws no band.
function onScrollbar(event, box) {
  if (!box || event.target !== box || typeof event.offsetX !== "number") return false;
  return event.offsetX >= box.clientWidth || event.offsetY >= box.clientHeight;
}
