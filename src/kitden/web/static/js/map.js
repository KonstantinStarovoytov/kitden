// The map core every map page shares: a pure layout of a tree of blocks, what a selection lights,
// what a search finds, and one renderer of HTML blocks over one SVG of links.
//
// The tree model:
// - columns: [{ id, caption, add, w, h, narrowW, narrowH }]. Each column has its blocks' size,
//   wide and narrow (the narrow size is the wide one unless set). `add` puts "+ Add" beside the
//   caption.
// - blocks: [{ id, column, parent, kind, name, meta, state, tag, count, grip, action, details, h }].
//   The children of a block are the blocks whose `parent` it is. A group block is a caption at
//   the top of its stack (a button when it has `details`), `h` high when its words take two lines;
//   its children sit under it, in its column, and always show. Any other block shows its children
//   only while it is open. `state`: "on", "off", "unk" or "preview". `count`: what a folded block
//   holds. `grip`: it can be dragged. `action`: what pressing it does, in words ("Set up…").
//   `stateInMeta`: its meta says its state already ("On in 2 projects"), so no state word is
//   spoken. `dot`: a client's dot when it is not its state (a client found on a first run).
// - links: [{ from, to, kind }], kind "on", "faint", "direct" or "preview". The link is the
//   state: something on has a link, something off has none.
import { button, cutName, el, plural } from "./dom.js";

export const GAP = 46; // between two columns
export const NARROW_GAP = 28; // between two columns in a narrow window
export const GROUP_H = 22; // a group caption's height
export const GROUP_MAX = 6; // a group with more children shows five and "N more"
export const LINK_MS = 150; // an unfold draws its links first, then its children fade in
const ROW_GAP = 8; // between two blocks of a column
const RAIL = 16; // narrow: children sit this far inside their parent, beside its rail
const TRUNK = 20; // a direct line runs down a trunk this far right of the block it leaves
const CORNER = 6; // the round corners of a direct line and of a rail
const CHILD_MS = 15; // between two children of an unfold
const LAST_STEP = 5; // no extra wait after the sixth child
// The links a lit path follows.
const PATH_KINDS = ["on", "direct", "faint"];
// What a screen reader hears for a block's state; the map itself shows no state word.
const STATE_SAID = { on: "On", off: "Off", unk: "Not known", preview: "Preview" };
const SVG = "http://www.w3.org/2000/svg";

// Narrow: under 1024 px, or under 1280 px with Details open beside the page.
export function isNarrow(width, detailsOpen) {
  return width < 1024 || (Boolean(detailsOpen) && width < 1280);
}

// When each child of an unfold starts to fade in (it takes 60 ms): after the links, 15 ms apart,
// with no extra wait after the sixth, so the whole unfold ends within 300 ms. Reduced motion
// shows the end at once.
export function unfoldDelays(count, reduced = false) {
  return Array.from({ length: count }, (_, i) => (reduced ? 0 : LINK_MS + Math.min(i, LAST_STEP) * CHILD_MS));
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
  const more = { id: `more:${block.id}`, column: block.column, parent: block.id, kind: "more", name: `${rest.length - GROUP_MAX + 1} more` };
  return [...rest.slice(0, GROUP_MAX - 1), more, ...children.filter((child) => PINNED.includes(child.kind))];
}

// Where each shown block goes, for any tree model: `{ columns: [{id, x, w}], blocks: [{id, kind,
// x, y, w, h}], links: [{from, to, kind, d}], height, narrow }`. Columns sit at fixed x, one after
// the other; a block takes its column's size. Wide, the children of an open block go to their own
// column, beside it, and every column keeps its place. Narrow, the narrow sizes apply and they
// unfold down inside it, on a rail; a column with no block of its own (tools inside their server)
// then takes no room. Only links between shown blocks are drawn; `d` is an SVG path.
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
    sizes.set(column.id, { x, w, h });
    if (narrow && !own.has(column.id)) continue;
    columns.push({ id: column.id, x, w });
    x += w + (narrow ? NARROW_GAP : GAP);
  }

  const placed = new Map(); // in reading order: column by column, top to bottom
  // A block at (left, y), `w` wide, then the children it shows under it: those of its own
  // column, and narrow every one, inside it beside the rail (never wider than its own column).
  // Returns the y under them.
  const stack = (block, left, w, y) => {
    const h = block.kind === "group" ? block.h || GROUP_H : sizes.get(block.column).h;
    const at = { id: block.id, kind: block.kind, x: left, y, w, h };
    if (block.kind === "more") at.name = block.name;
    if (block.details) at.details = true;
    placed.set(block.id, at);
    let below = y + h + ROW_GAP;
    for (const child of shownChildren(block, children.get(block.id) || [], open)) {
      if (child.column === block.column) below = stack(child, left, w, below);
      else if (narrow) below = stack(child, left + RAIL, Math.min(w - RAIL, sizes.get(child.column).w), below);
    }
    return below;
  };
  for (const column of model.columns) {
    const { x: left, w } = sizes.get(column.id);
    let y = 0;
    for (const block of model.blocks) {
      if (block.column !== column.id) continue;
      const parent = byId.get(block.parent);
      if (parent) {
        // It shows through its parent: under it, or (wide) here, from the open parent's top.
        if (narrow || parent.column === column.id || !open.has(parent.id) || !placed.has(parent.id)) continue;
        y = Math.max(y, placed.get(parent.id).y);
      }
      y = stack(block, left, w, y);
    }
  }

  const links = [];
  for (const link of model.links) {
    const from = placed.get(link.from);
    const to = placed.get(link.to);
    if (!from || !to) continue;
    const child = byId.get(link.to);
    const rail = narrow && child.parent === link.from && child.column !== byId.get(link.from).column;
    const d = rail ? railPath(from, to) : link.kind === "direct" ? elbow(from, to) : curve(from, to);
    links.push({ from: link.from, to: link.to, kind: link.kind, d });
  }
  const blocks = [...placed.values()];
  const height = blocks.reduce((most, block) => Math.max(most, block.y + block.h), 0);
  return { columns, blocks, links, height, narrow };
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
  return model.columns.reduce((sum, column) => sum + column.w, 0) + GAP * (model.columns.length - 1);
}

// The blocks a person can press, in the order the map draws them, which is the reading order:
// column by column, top to bottom (narrow, a block's children right after it). A group is a
// caption, not a button, unless it has Details.
export function blockOrder(layout) {
  return layout.blocks.filter((block) => block.kind !== "group" || block.details).map((block) => block.id);
}

// What is new on the map since the last draw: the links ("from>to") and the blocks (ids) of
// `layout` that `drawn` does not hold. `drawn` then holds just what shows now, so something that
// goes and comes back is new again.
export function appeared(layout, drawn) {
  const now = [...layout.links.map((link) => `${link.from}>${link.to}`), ...layout.blocks.map((block) => block.id)];
  const fresh = new Set(now.filter((key) => !drawn.has(key)));
  drawn.clear();
  for (const key of now) drawn.add(key);
  return fresh;
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
// folded parent opens to show it. Empty text finds nothing.
export function findIn(model, text) {
  const words = String(text || "").trim().toLowerCase();
  const matches = new Set();
  const open = new Set();
  if (!words) return { matches, open };
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  for (const block of model.blocks) {
    if (!String(block.name || "").toLowerCase().includes(words)) continue;
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

// A part a screen reader skips: the block's label says it already.
function quiet(node) {
  node.setAttribute("aria-hidden", "true");
  return node;
}

// What a block shows, left to right: the grip of one that can be dragged, its tile (the page's
// `tile(block)`), its name cut short with its meta line under it, the count of a folded block
// and a slot's action. A client's meta starts with its dot. A tag takes the meta line's place
// where a count pill takes the room, else it sits beside the name.
function blockParts(block, { tile, open }) {
  const parts = [];
  if (block.grip) parts.push(quiet(el("span", "block-grip")));
  const mark = tile ? tile(block) : null;
  if (mark) {
    const holder = quiet(el("span", "block-tile"));
    holder.append(mark);
    parts.push(holder);
  }
  const text = el("span", "block-text");
  const top = el("span", "block-top");
  top.append(el("span", "block-name", cutName(block.name)));
  text.append(top);
  const counted = typeof block.count === "number";
  const tag = block.tag ? el("span", "block-tag", block.tag) : null;
  if (tag && !(counted && block.meta)) top.append(tag);
  if (block.meta) {
    const line = el("span", "block-meta");
    if (block.kind === "client") line.append(quiet(el("span", `block-dot ${block.dot || block.state}`)));
    line.append(tag && counted ? tag : el("span", "block-words", block.meta));
    text.append(line);
  }
  parts.push(text);
  if (counted && !open) parts.push(quiet(el("span", "block-count", block.count)));
  if (block.action) parts.push(quiet(el("span", "block-action", block.action)));
  return parts;
}

// What a screen reader hears for a block: its whole name, meta, tag, the state word that matches
// its link (none where the meta says it), and its action.
export function blockLabel(block) {
  const state = block.stateInMeta ? null : STATE_SAID[block.state];
  return [block.name, block.meta, block.tag, state, block.action].filter(Boolean).join(", ");
}

// One block: a button with its name cut short (the whole name in its hover text and its label,
// blockLabel). A group is a caption, or a button when it has Details. A
// block that folds says whether it is open (`open`), also while its children are read. A press
// opens or folds a block that folds (`onOpen`), then selects it (`onSelect`, which draws again).
function blockNode(block, { selected, lit, found, folds, open, tile, onSelect, onOpen }) {
  const name = String(block.name || "");
  const matched = Boolean(found && found.matches.has(block.id));
  if (block.kind === "group" && !block.details) {
    const caption = el("div", matched ? "caption found" : "caption", name);
    caption.title = name;
    return caption;
  }
  const node = el("button", block.kind === "group" ? "caption" : `block ${block.kind}`);
  node.type = "button";
  node.dataset.focus = `block:${block.id}`;
  if (block.state) node.dataset.state = block.state;
  node.title = name;
  node.setAttribute("aria-label", blockLabel(block));
  const folding = folds.has(block.id);
  if (block.kind === "group") node.textContent = name;
  else node.append(...blockParts(block, { tile, open: folding && open.has(block.id) }));
  if (folding) node.setAttribute("aria-expanded", String(open.has(block.id)));
  if (block.id === selected) node.classList.add("selected");
  if (lit.has(block.id)) node.classList.add("lit");
  if (matched) node.classList.add("found");
  node.addEventListener("click", () => {
    if (folding && onOpen) onOpen(block.id);
    if (onSelect) onSelect(block.id);
  });
  return node;
}

// Draw `layout` (from layoutTree) of `model` in `box`: column captions, then one SVG of links
// under the blocks, each placed where the layout says. The DOM order is the reading order
// (blockOrder). What `drawn` does not hold yet appeared since the last draw (`appeared`): a new
// link draws once, then new blocks fade in after it (`unfoldDelays`); with `reduced` all of it
// shows at once. Lit links are drawn last, over the others. A click calls `onOpen(id)` on a block
// that folds, then `onSelect(id)`. `tile(block)` gives what a block shows before its name. `found`
// (from findIn, null for no search) lights its matches and dims the rest (`.finding`); the page
// adds `found.open` to `open` itself.
export function drawMap(box, model, layout, { onSelect, onOpen, onAdd, tile, selected = null, lit = new Set(), found = null, open = new Set(), drawn = new Set(), reduced = false } = {}) {
  performance.mark("kitden:map-start");
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  const width = layout.columns.reduce((most, column) => Math.max(most, column.x + column.w), 0);
  const fresh = appeared(layout, drawn);
  const parts = [];

  const heads = model.columns.filter((column) => column.caption || column.add);
  if (heads.length) {
    const head = el("div", "map-head");
    head.style.width = `${width}px`;
    for (const column of heads) {
      // Narrow, a column with no room of its own has no caption either.
      const at = layout.columns.find((c) => c.id === column.id);
      if (!at) continue;
      const cell = el("div", "map-caption");
      cell.style.left = `${at.x}px`;
      cell.style.width = `${at.w}px`;
      if (column.caption) cell.append(el("span", null, column.caption));
      if (column.add) {
        const add = button("+ Add", () => onAdd && onAdd(column.id), "btn small ghost");
        add.dataset.focus = `add:${column.id}`;
        cell.append(add);
      }
      head.append(cell);
    }
    parts.push(head);
  }

  const area = el("div", "map-area");
  area.style.width = `${width}px`;
  area.style.height = `${layout.height}px`;
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "map-links");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(layout.height));
  svg.setAttribute("viewBox", `0 0 ${width} ${layout.height}`);
  const keyOf = (link) => `${link.from}>${link.to}`;
  const links = [...layout.links.filter((link) => !lit.has(keyOf(link))), ...layout.links.filter((link) => lit.has(keyOf(link)))];
  for (const link of links) {
    const key = keyOf(link);
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("class", `link ${link.kind}${lit.has(key) ? " lit" : ""}`);
    path.setAttribute("d", link.d);
    if (fresh.has(key) && !reduced) {
      path.classList.add("draw");
      path.setAttribute("pathLength", "1");
    }
    svg.append(path);
  }
  area.append(svg);

  const folds = foldable(model);
  const delays = unfoldDelays(layout.blocks.filter((at) => fresh.has(at.id)).length, reduced);
  let next = 0;
  for (const at of layout.blocks) {
    const block = byId.get(at.id) || at; // "N more" is the layout's own block
    const node = blockNode(block, { selected, lit, found, folds, open, tile, onSelect, onOpen });
    Object.assign(node.style, { left: `${at.x}px`, top: `${at.y}px`, width: `${at.w}px`, height: `${at.h}px` });
    if (fresh.has(at.id) && !reduced) {
      node.classList.add("appear");
      node.style.animationDelay = `${delays[next++]}ms`;
    }
    area.append(node);
  }
  parts.push(area);

  box.classList.add("map");
  box.classList.toggle("finding", Boolean(found));
  box.classList.toggle("narrow", Boolean(layout.narrow));
  box.replaceChildren(...parts);
  performance.mark("kitden:map-drawn");
  performance.measure("kitden:map-draw", "kitden:map-start", "kitden:map-drawn");
}
