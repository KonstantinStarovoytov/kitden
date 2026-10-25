// The map core every map page shares: a pure layout of a tree of blocks, the links' paths, what
// changes between two layouts, what a selection lights and what a search finds. It touches no
// page: map-view.js draws it.
//
// The tree model:
// - columns: [{ id, caption, add, w, h, narrowW, narrowH, colGap, top, rowGap }]. Each column has
//   its blocks' size, wide and narrow (the narrow size is the wide one unless set). `add` puts
//   "+ Add" beside the caption. Wide only: `colGap` is the space before the column (GAP unless
//   set), `top` the y of its first block (CAPTION_ROW) and `rowGap` the space between its blocks.
// - blocks: [{ id, column, parent, kind, name, meta, state, tag, count, grip, action, details, h,
//   icon, before, rowGap }]. The children of a block are the blocks whose `parent` it is. A block
//   with an `h` is that high, whatever its column says. A group block is a caption at the top of
//   its stack (a button when it has `details`), CAPTION_H high unless `h` says more (its words
//   take two lines); its children sit under it, in its column, and always show. Wide, a group
//   sits `before` more space under the block above it, its children are CAPTION_GAP under it and
//   `rowGap` apart; `icon` (a lucide name) is drawn before its words. Any other block shows its
//   children only while it is open. `state`: "on", "off", "unk" or "preview". `count`: what a
//   folded block holds. `grip`: it can be dragged. `action`: what pressing it does, in words
//   ("Set up…"). `stateInMeta`: no state word is spoken; its meta says the state already ("On in
//   2 projects") or all there is to say (a gateway's clients and servers). `dot`: a client's dot
//   when it is not its state (a client found on a first run).
// - links: [{ from, to, kind, unk }], kind "on", "faint", "direct" or "preview". The link is the
//   state: something on has a link, something off has none. `unk`: Kitden does not know whether
//   it is on, so the line is dashed; it only shows who has the entry.
import { plural } from "./dom.js";

export const GAP = 46; // between two columns
export const NARROW_GAP = 28; // between two columns in a narrow window
export const GROUP_H = 22; // narrow: a group caption's height
export const GROUP_MAX = 6; // a group with more children shows five and "N more"
export const CAPTION_H = 18; // a column's caption, at the top of its column; a group's too
export const CAPTION_ROW = 24; // the blocks of a column start under its caption
export const CAPTION_GAP = 5; // between a group's caption and its first block
export const LINK_MS = 170; // an unfold draws its links first, then its children fade in
const ROW_GAP = 8; // between two blocks of a column
const RAIL = 16; // narrow: children sit this far inside their parent, beside its rail
const TRUNK = 20; // a direct line runs down a trunk this far right of the block it leaves
const CORNER = 6; // the round corners of a direct line and of a rail
const CHILD_MS = 15; // between two children of an unfold
const ENTER_STEP = 22; // between two blocks of the entrance
const ENTER_WAVE = 440; // the entrance starts its last block by now, however many there are
const CURVE_STEPS = 16; // a curve is cut into this many straight pieces to measure it
// How many numbers each command of a link's path takes.
const COORDS = { M: 2, H: 1, V: 1, C: 6, Q: 4 };
// The links a lit path follows.
const PATH_KINDS = ["on", "direct", "faint"];
// What a screen reader hears for a block's state; the map itself shows no state word.
const STATE_SAID = { on: "On", off: "Off", unk: "Not known", preview: "Preview" };

// Narrow: under 1024 px, or under 1280 px with Details open beside the page.
export function isNarrow(width, detailsOpen) {
  return width < 1024 || (Boolean(detailsOpen) && width < 1280);
}

// When each child of an unfold starts to fade in: after its links have drawn, 15 ms apart, however
// many there are. Reduced motion starts them all at once.
export function unfoldDelays(count, reduced = false) {
  return Array.from({ length: count }, (_, i) => (reduced ? 0 : LINK_MS + i * CHILD_MS));
}

// When each block of the entrance starts to rise, in layout order: 22 ms apart while the whole
// wave fits in 440 ms (up to 21 blocks), else spread evenly so the last one starts at 440 ms.
// Reduced motion starts them all at once.
export function enterDelays(count, reduced = false) {
  const step = count > 1 ? Math.min(ENTER_STEP, ENTER_WAVE / (count - 1)) : 0;
  return Array.from({ length: count }, (_, i) => (reduced ? 0 : i * step));
}

function childrenOf(model) {
  const children = new Map();
  for (const block of model.blocks) {
    if (!block.parent) continue;
    if (!children.has(block.parent)) children.set(block.parent, []);
    children.get(block.parent).push(block);
  }
  return children;
}

// What a group always shows whole: a preview and the slot of a drag are never behind "N more".
const PINNED = ["preview", "slot"];

// The children a block shows: a group's always (past GROUP_MAX the first five and a block
// "N more", then a preview or a slot, unless the group is open), any other block's only while it
// is open.
function shownChildren(block, children, open) {
  if (block.kind !== "group") return open.has(block.id) ? children : [];
  const rest = children.filter((child) => !PINNED.includes(child.kind));
  if (rest.length <= GROUP_MAX || open.has(block.id)) return children;
  const more = { id: `more:${block.id}`, column: block.column, parent: block.id, kind: "more", name: `${rest.length - GROUP_MAX + 1} more`, ...(rest[0].h ? { h: rest[0].h } : {}) };
  return [...rest.slice(0, GROUP_MAX - 1), more, ...children.filter((child) => PINNED.includes(child.kind))];
}

// Where each shown block goes, for any tree model: `{ columns: [{id, x, w}], blocks: [{id, kind,
// x, y, w, h, opener}], links: [{from, to, kind, shape, d}], height, narrow }`. Columns sit at fixed
// x, one after the other; a block takes its column's size (or its own `h`). A column that shows a
// block has its caption at its top, a block `column:<id>` of kind "column", and its blocks start
// under it (wide, at the column's `top`, `rowGap` apart; narrow, at CAPTION_ROW, ROW_GAP apart).
// Wide, the children of an open block go to their own column, beside it, in a stack centred on it
// (never above the bottom of what the column holds already), and every column keeps its place.
// Narrow, the narrow sizes apply and they unfold down inside it, on a rail; a column with no
// block of its own (tools inside their server) then takes no room. A block that shows because a
// block of another column is open (wide) or on that block's rail (narrow) names it as its
// `opener`, and so does the caption of a column whose blocks all do. Only links between shown
// blocks are drawn: `shape` is "rail", "step" (a direct line) or "curve", and `d` its SVG path.
export function layoutTree(model, { open = new Set(), width = 0, narrow = isNarrow(width, false) } = {}) {
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  const children = childrenOf(model);
  const own = new Set(model.blocks.filter((block) => !byId.has(block.parent)).map((block) => block.column));
  const sizes = new Map();
  const columns = [];
  let x = 0;
  for (const column of model.columns) {
    const w = narrow ? column.narrowW ?? column.w : column.w;
    const h = narrow ? column.narrowH ?? column.h : column.h;
    const top = narrow ? CAPTION_ROW : column.top ?? CAPTION_ROW;
    const row = narrow ? ROW_GAP : column.rowGap ?? ROW_GAP;
    if (narrow && !own.has(column.id)) {
      sizes.set(column.id, { x, w, h, top, row });
      continue;
    }
    if (columns.length) x += narrow ? NARROW_GAP : column.colGap ?? GAP;
    sizes.set(column.id, { x, w, h, top, row });
    columns.push({ id: column.id, x, w });
    x += w;
  }

  const placed = new Map();
  const blocks = []; // in reading order: column by column, top to bottom
  // A block at (left, y), `w` wide, then the children it shows under it: those of its own
  // column, and narrow every one, inside it beside the rail (never wider than its own column).
  // `opener` is the block whose opening shows it. Returns the y of the bottom of them all.
  const stack = (block, left, w, y, opener) => {
    const size = sizes.get(block.column);
    const group = block.kind === "group";
    const h = block.h ?? (group ? (narrow ? GROUP_H : CAPTION_H) : size.h);
    const at = { id: block.id, kind: block.kind, x: left, y, w, h };
    if (opener) at.opener = opener;
    if (block.kind === "more") at.name = block.name;
    if (block.details) at.details = true;
    placed.set(block.id, at);
    blocks.push(at);
    // Wide, a group's first block is CAPTION_GAP under it, and its blocks are its own `rowGap` apart.
    const caption = group && !narrow;
    const between = caption && block.rowGap !== undefined ? block.rowGap : size.row;
    let gap = caption ? CAPTION_GAP : size.row;
    let bottom = y + h;
    for (const child of shownChildren(block, children.get(block.id) || [], open)) {
      if (child.column === block.column) bottom = stack(child, left, w, bottom + gap, opener);
      else if (narrow) bottom = stack(child, left + RAIL, Math.min(w - RAIL, sizes.get(child.column).w), bottom + gap, block.id);
      else continue;
      gap = between;
    }
    return bottom;
  };
  for (const column of model.columns) {
    const { x: left, w, top, row } = sizes.get(column.id);
    const first = blocks.length;
    const centred = new Set(); // the open blocks whose children have their place in this column
    let y = top;
    for (const block of model.blocks) {
      if (block.column !== column.id) continue;
      const parent = byId.get(block.parent);
      if (!parent) {
        // Wide, a block sits `before` more space under the one above it.
        if (!narrow && block.before && blocks.length > first) y += block.before;
        y = stack(block, left, w, y, null) + row;
        continue;
      }
      // It shows through its parent: under it, or (wide) here, beside the open parent.
      if (narrow || parent.column === column.id || !open.has(parent.id) || !placed.has(parent.id) || centred.has(parent.id)) continue;
      centred.add(parent.id);
      // All its children in this column, from 0, then the whole stack down to be centred on it.
      const from = blocks.length;
      let bottom = 0;
      (children.get(parent.id) || []).filter((child) => child.column === column.id).forEach((child, i) => {
        bottom = stack(child, left, w, i ? bottom + row : 0, parent.id);
      });
      const at = Math.max(y, middle(placed.get(parent.id)) - bottom / 2);
      for (const placing of blocks.slice(from)) placing.y += at;
      y = at + bottom + row;
    }
    if (!column.caption || blocks.length === first) continue;
    const caption = { id: `column:${column.id}`, kind: "column", column: column.id, x: left, y: 0, w, h: CAPTION_H };
    const mine = blocks.slice(first);
    if (mine.every((at) => at.opener)) caption.opener = mine[0].opener;
    blocks.splice(first, 0, caption);
  }

  const links = [];
  for (const link of model.links) {
    const from = placed.get(link.from);
    const to = placed.get(link.to);
    if (!from || !to) continue;
    const child = byId.get(link.to);
    const rail = narrow && child.parent === link.from && child.column !== byId.get(link.from).column;
    const at = { from: link.from, to: link.to, kind: link.kind, shape: rail ? "rail" : link.kind === "direct" ? "step" : "curve", ...(link.unk ? { unk: true } : {}) };
    at.d = linkPath(at, from, to);
    links.push(at);
  }
  const height = blocks.reduce((most, block) => Math.max(most, block.y + block.h), 0);
  return { columns, blocks, links, height, narrow };
}

// A link's key, "from>to": one per pair of blocks.
export function linkKey(link) {
  return `${link.from}>${link.to}`;
}

// A link's look: its kind, and dashed when Kitden does not know that it is on.
export function linkClass(link) {
  return `link ${link.kind}${link.unk ? " unk" : ""}`;
}

// A link's SVG path between the boxes of its two blocks ({ x, y, w, h }) by its shape.
export function linkPath(link, from, to) {
  if (link.shape === "rail") return railPath(from, to);
  return link.shape === "step" ? elbow(from, to) : curve(from, to);
}

// The point at t (0 to 1) of the curve through `points` (de Casteljau).
function along(points, t) {
  let now = points;
  while (now.length > 1) now = now.slice(1).map(([x, y], i) => [now[i][0] + (x - now[i][0]) * t, now[i][1] + (y - now[i][1]) * t]);
  return now[0];
}

// The point at half the length of a path of absolute M, H, V, C and Q commands, as `linkPath`
// gives them: where a link's × sits.
export function midPoint(d) {
  const words = String(d).match(/[A-Z]|-?\d*\.?\d+(?:e[-+]?\d+)?/g) || [];
  const pieces = []; // the path as straight pieces, each [x0, y0, x1, y1]
  let at = [0, 0];
  for (let i = 0; i < words.length; ) {
    const command = words[i++];
    const n = words.slice(i, i + (COORDS[command] || 0)).map(Number);
    i += n.length;
    if (command === "M") {
      at = [n[0], n[1]];
      continue;
    }
    const points = [at];
    if (command === "H") points.push([n[0], at[1]]);
    else if (command === "V") points.push([at[0], n[0]]);
    else for (let k = 0; k < n.length; k += 2) points.push([n[k], n[k + 1]]);
    const cuts = points.length > 2 ? CURVE_STEPS : 1;
    let from = at;
    for (let cut = 1; cut <= cuts; cut++) {
      const to = cut === cuts ? points.at(-1) : along(points, cut / cuts);
      pieces.push([...from, ...to]);
      from = to;
    }
    at = points.at(-1);
  }
  const lengths = pieces.map(([x0, y0, x1, y1]) => Math.hypot(x1 - x0, y1 - y0));
  let left = lengths.reduce((sum, length) => sum + length, 0) / 2;
  for (const [i, length] of lengths.entries()) {
    if (left > length && i < lengths.length - 1) {
      left -= length;
      continue;
    }
    const [x0, y0, x1, y1] = pieces[i];
    const t = length ? Math.min(1, left / length) : 0;
    return { x: x0 + (x1 - x0) * t, y: y0 + (y1 - y0) * t };
  }
  return { x: at[0], y: at[1] };
}

// What changes from the layout `before` (null: nothing drawn yet) to `after`: the block ids that
// enter, stay and leave, and the link keys likewise, in layout order (what leaves in the order of
// `before`). A block enters as an unfold when its opener showed before, and leaves as a fold when
// its opener still shows after.
export function drawPlan(before, after) {
  const was = new Map((before ? before.blocks : []).map((at) => [at.id, at]));
  const now = new Map(after.blocks.map((at) => [at.id, at]));
  const plan = { enter: [], stay: [], leave: [], unfold: [], fold: [], linksIn: [], linksStay: [], linksOut: [] };
  for (const at of after.blocks) {
    if (was.has(at.id)) plan.stay.push(at.id);
    else {
      plan.enter.push(at.id);
      if (at.opener && was.has(at.opener)) plan.unfold.push(at.id);
    }
  }
  for (const at of was.values()) {
    if (now.has(at.id)) continue;
    plan.leave.push(at.id);
    if (at.opener && now.has(at.opener)) plan.fold.push(at.id);
  }
  const drawn = new Set((before ? before.links : []).map(linkKey));
  const shown = new Set(after.links.map(linkKey));
  for (const key of shown) plan[drawn.has(key) ? "linksStay" : "linksIn"].push(key);
  for (const key of drawn) if (!shown.has(key)) plan.linksOut.push(key);
  return plan;
}

// The column under a point of the layout (x and y from its top left): the id of the column whose
// box, the whole height of the map, holds it; null between columns or outside the map.
export function dropAt(layout, x, y) {
  if (y < 0 || y > layout.height) return null;
  const column = layout.columns.find((c) => x >= c.x && x <= c.x + c.w);
  return column ? column.id : null;
}

// The box a group of `model` takes in `layout`: from its caption to its last block shown ("N more"
// too), as wide as its column; null when the group is not drawn.
export function groupBox(model, layout, id) {
  const caption = layout.blocks.find((b) => b.id === id);
  if (!caption) return null;
  const inside = new Set([...model.blocks.filter((b) => b.parent === id).map((b) => b.id), `more:${id}`]);
  const bottom = layout.blocks.filter((b) => inside.has(b.id)).reduce((most, b) => Math.max(most, b.y + b.h), caption.y + caption.h);
  return { x: caption.x, y: caption.y, w: caption.w, h: bottom - caption.y };
}

// How wide the map is when it lays out wide: every column and the gaps between them.
export function wideWidth(model) {
  return model.columns.reduce((sum, column, i) => sum + column.w + (i ? column.colGap ?? GAP : 0), 0);
}

// The blocks a person can press, in the order the map draws them, which is the reading order:
// column by column, top to bottom (narrow, a block's children right after it). A group is a
// caption, not a button, unless it has Details; a column's caption never is.
export function blockOrder(layout) {
  return layout.blocks.filter((block) => block.kind !== "column" && (block.kind !== "group" || block.details)).map((block) => block.id);
}

// The blocks that fold: any that holds something, also before its children are read (a count,
// even 0). Groups always show theirs. A block that folds says whether it is open.
export function foldable(model) {
  const parents = new Set(model.blocks.map((block) => block.parent).filter(Boolean));
  const folds = (block) => block.kind !== "group" && (typeof block.count === "number" || parents.has(block.id));
  return new Set(model.blocks.filter(folds).map((block) => block.id));
}

const middle = (block) => block.y + block.h / 2;

// A cubic from the right side of `a` to the left side of `b`.
function curve(a, b) {
  const [x1, y1, x2, y2] = [a.x + a.w, middle(a), b.x, middle(b)];
  const half = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${half} ${y1}, ${half} ${y2}, ${x2} ${y2}`;
}

// An orthogonal elbow with round corners: out of `a`, down (or up) its trunk, and into `b`.
function elbow(a, b) {
  const [x1, y1, x2, y2] = [a.x + a.w, middle(a), b.x, middle(b)];
  const trunk = x1 + TRUNK;
  const r = Math.min(CORNER, Math.abs(y2 - y1) / 2);
  if (!r) return `M ${x1} ${y1} H ${x2}`;
  const s = Math.sign(y2 - y1);
  return `M ${x1} ${y1} H ${trunk - r} Q ${trunk} ${y1} ${trunk} ${y1 + s * r} V ${y2 - s * r} Q ${trunk} ${y2} ${trunk + r} ${y2} H ${x2}`;
}

// Narrow: down the rail at the parent's left side, then into the child.
function railPath(a, b) {
  const x = a.x + RAIL / 2;
  const y = middle(b);
  return `M ${x} ${a.y + a.h} V ${y - CORNER} Q ${x} ${y} ${x + CORNER} ${y} H ${b.x}`;
}

// Open `id` and close any other open block of its column with its open children (not its own
// parents); an open `id` closes. One block per column is open.
export function toggleOpen(model, open, id) {
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  const children = childrenOf(model);
  const next = new Set(open);
  const close = (key) => {
    next.delete(key);
    for (const child of children.get(key) || []) close(child.id);
  };
  if (next.has(id)) {
    close(id);
    return next;
  }
  const above = new Set();
  for (let at = byId.get(id)?.parent; at && !above.has(at); at = byId.get(at)?.parent) above.add(at);
  const column = byId.get(id)?.column;
  for (const other of open) if (!above.has(other) && byId.get(other)?.column === column) close(other);
  next.add(id);
  return next;
}

// What the person has open after a press on `id`. A block a search holds open (`found.open`) is
// open for the view only: a press leaves what the person opened as it is.
export function pressOpen(model, open, found, id) {
  return found && found.open.has(id) ? open : toggleOpen(model, open, id);
}

// What the person has open after they select `block`, so it stays on the map when the search that
// showed it ends. A block that shows already changes nothing. Otherwise the blocks above it open,
// the outermost first, as presses would open them: one open block per column.
export function keepOpen(model, open, block) {
  const shown = (set) => layoutTree(model, { open: set, narrow: false }).blocks.some((at) => at.id === block.id);
  if (shown(open)) return open;
  const byId = new Map(model.blocks.map((b) => [b.id, b]));
  const above = [];
  for (let at = byId.get(block.parent); at && !above.includes(at.id); at = byId.get(at.parent)) above.unshift(at.id);
  let next = open;
  for (const id of above) if (!next.has(id)) next = toggleOpen(model, next, id);
  return next;
}

// The blocks reached from `starts` along the links a path follows (backwards with `back`), and
// those links as "from>to".
function reached(links, starts, back = false) {
  const along = new Map();
  for (const link of links) {
    if (!PATH_KINDS.includes(link.kind)) continue;
    const at = back ? link.to : link.from;
    if (!along.has(at)) along.set(at, []);
    along.get(at).push(link);
  }
  const found = new Set(starts);
  const queue = [...starts];
  while (queue.length) {
    for (const link of along.get(queue.shift()) || []) {
      const next = back ? link.from : link.to;
      found.add(`${link.from}>${link.to}`);
      if (!found.has(next)) {
        found.add(next);
        queue.push(next);
      }
    }
  }
  return found;
}

// What a client reaches: every block and link on its way out.
export function litFrom(model, id) {
  return reached(model.links, [id]);
}

// A selected block, and every path to it from each client that reaches it: the blocks and the
// links on the way.
export function litPath(model, id) {
  const before = reached(model.links, [id], true);
  const clients = model.blocks.filter((block) => block.kind === "client" && before.has(block.id)).map((block) => block.id);
  const lit = reached(model.links.filter((link) => before.has(link.from) && before.has(link.to)), clients);
  lit.add(id);
  return lit;
}

// The blocks whose name holds `text` (any case, trimmed), and every block above a match, so a
// folded parent opens to show it. A group's caption ("Remote") is not a thing to find, so it
// is never a match. Empty text finds nothing.
export function findIn(model, text) {
  const words = String(text || "").trim().toLowerCase();
  const matches = new Set();
  const open = new Set();
  if (!words) return { matches, open };
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  for (const block of model.blocks) {
    if (block.kind === "group" || !String(block.name || "").toLowerCase().includes(words)) continue;
    matches.add(block.id);
    for (let at = block.parent; at && byId.has(at) && !open.has(at); at = byId.get(at).parent) open.add(at);
  }
  return { matches, open };
}

// What the search chip says: nothing without a search (`found` null), "No matches", or how many
// blocks match.
export function findChip(found) {
  if (!found) return null;
  return found.matches.size ? plural(found.matches.size, "match", "matches") : "No matches";
}

// What a screen reader hears for a block: its whole name, meta, tag, the state word that matches
// its link (none where the meta says it), and its action.
export function blockLabel(block) {
  const state = block.stateInMeta ? null : STATE_SAID[block.state];
  return [block.name, block.meta, block.tag, state, block.action].filter(Boolean).join(", ");
}
