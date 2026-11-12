// The map core every map page shares: a pure layout of a tree of blocks, the links' paths, what
// changes between two layouts, what a selection lights and what a search finds. It touches no
// page: map-view.js draws it.
//
// The tree model:
// - columns: [{ id, caption, w, h, narrowW, narrowH, colGap, top, rowGap }]. Each column has
//   its blocks' size, wide and narrow (the narrow size is the wide one unless set).
//   Wide only: `colGap` is the space before the column (GAP unless
//   set), `top` the y of its first block (CAPTION_ROW) and `rowGap` the space between its blocks.
// - blocks: [{ id, column, parent, kind, name, meta, state, tag, count, grip, action, details, h,
//   icon, before, rowGap, lamp, wait, stats, projects, ports, takeOut, title, leaving, pageName }]. The
//   children of a block are the blocks whose `parent` it is. A block with an `h` is that high,
//   whatever its column says. A group block is a caption at the top of its stack (a button when it
//   has `details`), CAPTION_H high unless `h` says otherwise; its words after a " · " are quiet;
//   `pageName`, its words while it pages (layoutTree); its children sit under it, in its column,
//   and always show, or with `folds` (a group of servers, plugins or skills) in a stack of cards
//   until the group is open (`spread`, layoutTree). Wide, a group
//   sits `before` more space under the block above it, its children are CAPTION_GAP under it and
//   `rowGap` apart; `icon` (a lucide name) is drawn before its words. Any other block shows its
//   children only while it is open. `state`: "on", "off", "unk" or "preview". `count`: what a
//   folded block holds, in a round button that opens and folds it; `unit` ("tool" unless set) is its
//   word. `grip`: it can be dragged. `action`: what pressing it does, in words
//   ("Set up…"). `stateInMeta`: no state word is spoken; its meta says the state already ("On in
//   2 projects") or all there is to say (a gateway's clients and servers). How it looks
//   (map-view.js): `lamp` "on", "off", "preview" or "out" (works outside the gateway), at the start
//   of its meta line, or as a tool's mark; `wait`, words after the meta, in the accent, while a
//   change for it waits in the tray; `stats`, a gateway's counts, [{ icon, words }]; `projects`,
//   a tool's { words, said, own }; `ports`, { left, right }, each true or a look ("out"); `takeOut`, the
//   words of a block in preview, which a press takes out (it shows an ×); `title`, its hover words
//   when they are more than its name (a meta the card may cut); `leaving`, a change in the
//   tray takes it out; `pinned`, a group never pages it away (a card the tray adds).
// - links: [{ from, to, kind, unk, leaving, preview }], kind "on", "faint", "direct" or "preview".
//   The link is the state: something on has a link, something off has none. `unk`: Kitden does not
//   know whether it is on, so the line is dashed; it only shows who has the entry. `leaving`: a
//   change in preview takes it out, so the line is dashed and quiet. `preview`: a change in preview
//   adds this direct line, so it has a preview's dashes.
import { plural } from "./dom.js";

export const GAP = 46; // between two columns
export const NARROW_GAP = 28; // between two columns in a narrow window
const GROUP_H = 22; // narrow: a group caption's height
const PAGE = 5; // the children a page of a group shows, unless the group has a `pageSize`
export const COLLAPSE_W = 74; // Collapse, under an open group at its column's right edge
export const COLLAPSE_H = 20;
const COLLAPSE_GAP = 6; // between an open group's last block and its Collapse
const COLLAPSE = "Collapse";
const STACK_SHOWS = 3; // a stack shows the first three of its cards: two strips, one whole
const ONE_EDGE = 4; // a stack of one card shows this much of an edge under it
export const CAPTION_H = 18; // a column's caption, at the top of its column; a group's too
const CAPTION_ROW = 24; // the blocks of a column start under its caption
const CAPTION_GAP = 5; // between a group's caption and its first block
export const LINK_MS = 170; // an unfold draws its links first, then its children fade in
const CHANNELS = [16, 24, 32]; // wide: how far right of its client a direct line turns
const NARROW_CHANNEL = 14; // narrow: the same, in the smaller gap between columns
const ROW_GAP = 8; // between two blocks of a column
const RAIL = 16; // narrow: children sit this far inside their parent, beside its rail
const CORNER = 6; // the round corners of a rail
const BEND = 8; // the round corners of a direct line
const MIN_HANDLE = 18; // a curve leaves and enters level for at least this far
const CHILD_MS = 15; // between two children of an unfold
const ENTER_STEP = 22; // between two blocks of the entrance
const ENTER_WAVE = 440; // the entrance starts its last block by now, however many there are
const CURVE_STEPS = 16; // a curve is cut into this many straight pieces to measure it
// How many numbers each command of a link's path takes.
const COORDS = { M: 2, H: 1, V: 1, C: 6, Q: 4 };
// The links a lit path follows.
const PATH_KINDS = ["on", "direct", "faint"];
// What a screen reader hears for a block's state; the map itself shows no state word.
const STATE_SAID = { on: "On", off: "Off", unk: "Not known", preview: "In preview" };
// What a link's look carries over from the model to the layout.
const LINK_FLAGS = ["unk", "leaving", "preview"];

// Narrow: under 1024 px. Details float over the map (panel.js), so they never make it narrow.
export function isNarrow(width) {
  return width < 1024;
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

// What a group always shows whole: a preview, the slot of a drag, a block marked `pinned` (a card
// the tray adds), a block a change in the tray waits for (`leaving`, `wait`) and the end of a link a
// change adds or takes out (`flagged`, flaggedOf) are never in a stack.
const PINNED = ["preview", "slot"];
const NONE = new Set();
const pinned = (child, flagged = NONE) => Boolean(child.pinned || child.leaving || child.wait) || PINNED.includes(child.kind) || flagged.has(child.id);
// The blocks at either end of a link in preview: a link a change adds (`preview`) or takes out
// (`leaving`), so a server whose tool a change turns off is pinned too.
const flaggedOf = (model) => new Set(model.links.filter((link) => link.leaving || link.preview || link.kind === "preview").flatMap((link) => [link.from, link.to]));
// How strong a link to a stack is: the strongest of those it stands for wins (on, then faint, then
// a line that skips the gateway).
const STRENGTH = ["on", "faint", "direct"];
const strength = (kind) => (STRENGTH.includes(kind) ? STRENGTH.indexOf(kind) : STRENGTH.length);

// How a group pages: past one more than a page (six for five a page), its `pageSize` (PAGE
// unless set) at a time. It gives the children that page (none pinned), the page size, how many
// pages, and the page it shows (`pages`, from 0; past the last, the last). Null for any other block.
function paging(block, children, pages = new Map(), flagged = NONE) {
  if (block.kind !== "group") return null;
  const size = block.pageSize || PAGE;
  const rest = children.filter((child) => !pinned(child, flagged));
  if (rest.length <= size + 1) return null;
  const count = Math.ceil(rest.length / size);
  return { rest, size, count, page: Math.min(Math.max(0, pages.get(block.id) || 0), count - 1) };
}

// The cards of a group that can go into a stack, when the group folds (`folds`) and has two or
// more of them; null for any other block. A group of one card never folds.
function stackable(block, children, flagged) {
  if (block.kind !== "group" || !block.folds) return null;
  const rest = children.filter((child) => !pinned(child, flagged));
  return rest.length > 1 ? rest : null;
}

// A stack of `cards` of `group` in the role "all" (the group folded), "before" or "after" (the
// pages on either side of the one shown, `size` a page). Its name says what is inside and what a
// press does ("Show 5 more: figma, vercel, stripe").
function stackOfCards(group, role, cards, size) {
  // The stack above shows first the page a press brings back.
  if (role === "before") cards = [...cards.slice(-size), ...cards.slice(0, -size)];
  const first = cards.slice(0, STACK_SHOWS).map((card) => card.name).join(", ");
  const label = group.pageName || group.name;
  const name = role === "all" ? `Open ${label}, ${cards.length}: ${first}` : role === "after" ? `Show ${Math.min(size, cards.length)} more: ${first}` : `Show the ${size} before: ${first}`;
  return { id: `stack:${group.id}:${role}`, column: group.column, parent: group.id, kind: "stack", role, group: group.id, holds: cards.map((card) => card.id), more: Math.max(0, cards.length - STACK_SHOWS), firstH: cards[0].h, name };
}

// The children a block shows: a group's always, any other block's only while it is open. A group
// that folds shows one stack while it is not in `spread`. A group past six shows the cards of its
// page between a stack of the cards before and one of the cards after; a pinned block shows where
// it stands among them. A group that folds ends with Collapse. A card on a page, or of a group that
// folds, is marked as turning with its group.
function shownChildren(block, children, open, pages, spread = NONE, flagged = NONE) {
  if (block.kind !== "group") return open.has(block.id) ? children : [];
  const kept = children.filter((child) => pinned(child, flagged));
  const cards = stackable(block, children, flagged);
  if (cards && !spread.has(block.id)) return [stackOfCards(block, "all", cards), ...kept];
  const collapse = cards ? [{ id: `collapse:${block.id}`, column: block.column, parent: block.id, kind: "collapse", group: block.id, name: COLLAPSE }] : [];
  const paged = paging(block, children, pages, flagged);
  if (!paged) return [...(cards ? children.map((child) => (kept.includes(child) ? child : { ...child, turns: block.id })) : children), ...collapse];
  const { rest, size, page } = paged;
  const onPage = new Set(rest.slice(page * size, (page + 1) * size));
  const shown = children.filter((child) => onPage.has(child) || kept.includes(child)).map((child) => (onPage.has(child) ? { ...child, turns: block.id } : child));
  const before = rest.slice(0, page * size);
  const after = rest.slice((page + 1) * size);
  return [
    ...(before.length ? [stackOfCards(block, "before", before, size)] : []),
    ...shown,
    ...(after.length ? [stackOfCards(block, "after", after, size)] : []),
    ...collapse,
  ];
}

// What the layout says of a block beyond its place: a stack's role, group,
// cards and name; Collapse's group; a group that folds, whether it is open (`spread`), and folded,
// its caption with its count ("Remote · 12"); a group that pages, the page it shows and its caption
// with which ones ("Remote · 6–10 of 12", from its `pageName` when it has one); a block on a page or
// in a group that folds, the group it turns with.
function pageParts(block, children, pages, spread = NONE, flagged = NONE) {
  if (block.kind === "stack") return { role: block.role, group: block.group, holds: block.holds, more: block.more, name: block.name };
  if (block.kind === "collapse") return { group: block.group, name: block.name };
  const parts = block.turns ? { turns: block.turns } : {};
  const cards = stackable(block, children, flagged);
  if (cards) {
    parts.spread = spread.has(block.id);
    if (!parts.spread) return { ...parts, name: `${block.pageName || block.name} · ${cards.length}` };
  }
  const paged = paging(block, children, pages, flagged);
  if (!paged) return parts;
  return { ...parts, page: paged.page, name: pageWords(block, paged) };
}

// How high a stack is when its first card is `h` high: one card shows a thin edge under it; more
// show the tops of all but the last of the first three (a strip each), then the last one whole.
function stackHeight(count, h) {
  if (count === 1) return h + ONE_EDGE;
  const peek = h >= 60 ? 20 : h >= 44 ? 18 : 15;
  return (Math.min(count, STACK_SHOWS) - 1) * peek + h;
}

// A paged group's caption: its name and which ones show ("Remote · 6–10 of 12").
function pageWords(block, { rest, size, page }) {
  return `${block.pageName || block.name} · ${page * size + 1}–${Math.min(rest.length, (page + 1) * size)} of ${rest.length}`;
}

// What the caption of the group of a stack (`stack:<group id>:<role>`) says with `pages`, or ""
// when it does not page: a turn says it to a screen reader.
export function turnWords(model, pages, id) {
  const groupId = groupOfStack(id);
  const group = model.blocks.find((block) => block.id === groupId);
  const paged = group && paging(group, childrenOf(model).get(group.id) || [], pages, flaggedOf(model));
  return paged ? pageWords(group, paged) : "";
}

// The pages of the groups that page now: a group that stopped paging (or went) forgets its page, so
// it starts on its first page when it pages again. `pages` itself when every group still pages.
export function pagesNow(model, pages) {
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  const children = childrenOf(model);
  const flagged = flaggedOf(model);
  const kept = [...pages].filter(([id]) => byId.has(id) && paging(byId.get(id), children.get(id) || [], new Map(), flagged));
  return kept.length === pages.size ? pages : new Map(kept);
}

// The pages that show `ids` (a search's matches, a selection): a group that pages turns to the page
// of the first one it holds, or holds a block above, unless the page shown holds one already. An
// id that is no block turns nothing. `pages` itself when nothing turns.
export function pagesWith(model, pages, ids) {
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  const children = childrenOf(model);
  const flagged = flaggedOf(model);
  const wanted = new Map(); // group id -> the pages that hold one of `ids`
  for (const id of ids) {
    for (let at = byId.get(id); at; at = byId.get(at.parent)) {
      const group = byId.get(at.parent);
      const paged = group && paging(group, children.get(group.id) || [], pages, flagged);
      const i = paged ? paged.rest.indexOf(at) : -1;
      if (i < 0) continue;
      if (!wanted.has(group.id)) wanted.set(group.id, { shown: paged.page, holds: [] });
      wanted.get(group.id).holds.push(Math.floor(i / paged.size));
    }
  }
  let next = pages;
  for (const [group, { shown, holds }] of wanted) {
    if (holds.includes(shown)) continue;
    if (next === pages) next = new Map(pages);
    next.set(group, holds[0]);
  }
  return next;
}

// The group of a stack ("stack:<group>:<role>") or of a Collapse ("collapse:<group>"). A group's id
// may hold colons itself ("group:kitden:remote").
export function groupOfStack(id) {
  if (id.startsWith("collapse:")) return id.slice("collapse:".length);
  return id.slice("stack:".length, id.lastIndexOf(":"));
}

// What shows after a press on a stack: "all" opens its group on its first page, "after" turns to
// the next page and "before" to the one before, never past the first or the last. New sets; the
// ones given stay as they are.
export function pressStack(model, { spread, pages }, id) {
  const group = groupOfStack(id);
  const role = id.slice(id.lastIndexOf(":") + 1);
  const next = { spread: new Set(spread), pages: new Map(pages) };
  if (role === "all") {
    next.spread.add(group);
    next.pages.delete(group);
    return next;
  }
  const block = model.blocks.find((b) => b.id === group);
  const paged = block && paging(block, childrenOf(model).get(group) || [], pages, flaggedOf(model));
  if (paged) next.pages.set(group, Math.min(Math.max(0, paged.page + (role === "after" ? 1 : -1)), paged.count - 1));
  return next;
}

// What shows after a press on Collapse: its group folds, and opens again on its first page.
export function collapseGroup({ spread, pages }, id) {
  const group = groupOfStack(id);
  const next = { spread: new Set(spread), pages: new Map(pages) };
  next.spread.delete(group);
  next.pages.delete(group);
  return next;
}

// The groups open with `ids` shown (a search's matches, a selection): `spread` and every folded
// group that holds one of them in its stack. `spread` itself when none is added.
export function groupsWith(model, spread, ids) {
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  const children = childrenOf(model);
  const flagged = flaggedOf(model);
  let next = spread;
  for (const id of ids) {
    for (let card = byId.get(id), at = card && byId.get(card.parent); at; card = at, at = byId.get(at.parent)) {
      const cards = next.has(at.id) ? null : stackable(at, children.get(at.id) || [], flagged);
      if (!cards || !cards.includes(card)) continue;
      if (next === spread) next = new Set(spread);
      next.add(at.id);
    }
  }
  return next;
}

// The cards a change or a rescan brought into a folding group that was there already: the ids of
// the blocks `now` has and `was` did not, whose group `was` had. A group that came with its cards
// (a gateway read later) and a block deeper down (a new tool) bring none.
export function newCards(was, now) {
  const had = new Set(was.blocks.map((block) => block.id));
  const folding = new Set(now.blocks.filter((block) => block.kind === "group" && block.folds && had.has(block.id)).map((block) => block.id));
  return now.blocks.filter((block) => !had.has(block.id) && folding.has(block.parent)).map((block) => block.id);
}

// The stack of a layout that holds `id`, or null.
export function stackOf(layout, id) {
  return layout.blocks.find((at) => at.kind === "stack" && at.holds.includes(id)) || null;
}

// What lights with `lit` on a layout with stacks: also each stack that holds a lit card, and each
// link to a stack that stands for a lit link. `lit` itself when nothing is added.
export function withStacks(lit, layout) {
  let next = lit;
  const add = (id) => {
    if (next.has(id)) return;
    if (next === lit) next = new Set(lit);
    next.add(id);
  };
  for (const at of layout.blocks) if (at.kind === "stack" && at.holds.some((id) => lit.has(id))) add(at.id);
  for (const link of layout.links) if (link.stack && link.stands.some((key) => lit.has(key))) add(linkKey(link));
  return next;
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
// blocks are drawn: `shape` is "rail", "step" (a direct line) or "curve", and `d` its SVG path. A
// direct line carries the `chan` it turns on, how far right of its client: wide, one of CHANNELS by
// the place of its block among those with a direct line, so the lines to blocks one after the other
// run side by side; narrow, NARROW_CHANNEL. A group of more than six shows five a page, the
// page `pages` names (group id -> from 0), between stacks. A group that folds is one stack unless
// `spread` holds it; a link to a card in a stack is drawn to the stack, one from each block
// (`stack`, with the keys it `stands` for), as strong as the strongest of them.
export function layoutTree(model, { open = new Set(), pages = new Map(), spread = new Set(), width = 0, narrow = isNarrow(width) } = {}) {
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  const children = childrenOf(model);
  const flagged = flaggedOf(model);
  const heldBy = new Map(); // a card in a stack -> the stack
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
    let h = block.h ?? (group ? (narrow ? GROUP_H : CAPTION_H) : size.h);
    if (block.kind === "stack") h = stackHeight(block.holds.length, block.firstH ?? size.h);
    const cardH = block.kind === "stack" ? block.firstH ?? size.h : undefined;
    if (block.kind === "collapse") [h, left, w] = [COLLAPSE_H, left + w - COLLAPSE_W, COLLAPSE_W];
    const at = { id: block.id, kind: block.kind, x: left, y, w, h };
    if (opener) at.opener = opener;
    Object.assign(at, pageParts(block, children.get(block.id) || [], pages, spread, flagged));
    if (cardH !== undefined) at.cardH = cardH;
    for (const id of block.holds || []) heldBy.set(id, block.id);
    if (block.details) at.details = true;
    placed.set(block.id, at);
    blocks.push(at);
    // Wide, a group's first block is CAPTION_GAP under it, and its blocks are its own `rowGap` apart.
    const wideGroup = group && !narrow;
    const between = wideGroup && block.rowGap !== undefined ? block.rowGap : size.row;
    let gap = wideGroup ? CAPTION_GAP : size.row;
    let bottom = y + h;
    for (const child of shownChildren(block, children.get(block.id) || [], open, pages, spread, flagged)) {
      if (child.column === block.column) bottom = stack(child, left, w, bottom + (child.kind === "collapse" ? COLLAPSE_GAP : gap), opener);
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
      const base = Math.max(y, middle(placed.get(parent.id)) - bottom / 2);
      for (const placing of blocks.slice(from)) placing.y += base;
      y = base + bottom + row;
    }
    if (!column.caption || blocks.length === first) continue;
    const caption = { id: `column:${column.id}`, kind: "column", column: column.id, x: left, y: 0, w, h: CAPTION_H };
    const mine = blocks.slice(first);
    if (mine.every((at) => at.opener)) caption.opener = mine[0].opener;
    blocks.splice(first, 0, caption);
  }

  // The place of each block with a direct line, in layout order, picks its channel; a stack takes
  // the place of its cards.
  const lined = new Set(model.links.filter((link) => link.kind === "direct").map((link) => heldBy.get(link.to) || link.to));
  const places = blocks.map((at) => at.id).filter((id) => lined.has(id));
  const links = [];
  const merged = new Map(); // "from>stack" -> the one link drawn for all it stands for
  for (const link of model.links) {
    const from = placed.get(link.from);
    const into = placed.has(link.to) ? null : heldBy.get(link.to);
    const to = placed.get(into || link.to);
    if (!from || !to) continue;
    if (into) {
      const was = merged.get(`${link.from}>${into}`);
      if (!was) {
        const drawn = { from: link.from, to: into, kind: link.kind, stack: true, stands: [linkKey(link)], ...(link.unk ? { unk: true } : {}) };
        merged.set(`${link.from}>${into}`, drawn);
        links.push(drawn);
        continue;
      }
      was.stands.push(linkKey(link));
      if (strength(link.kind) < strength(was.kind)) was.kind = link.kind;
      if (!link.unk) delete was.unk;
      continue;
    }
    const child = byId.get(link.to);
    const rail = narrow && child.parent === link.from && child.column !== byId.get(link.from).column;
    const drawn = { from: link.from, to: link.to, kind: link.kind, shape: rail ? "rail" : link.kind === "direct" ? "step" : "curve", ...flagsOf(link) };
    if (link.kind === "direct") drawn.chan = narrow ? NARROW_CHANNEL : CHANNELS[places.indexOf(link.to) % CHANNELS.length];
    drawn.d = linkPath(drawn, from, to);
    links.push(drawn);
  }
  for (const drawn of merged.values()) {
    drawn.shape = drawn.kind === "direct" ? "step" : "curve";
    if (drawn.kind === "direct") drawn.chan = narrow ? NARROW_CHANNEL : CHANNELS[places.indexOf(drawn.to) % CHANNELS.length];
    drawn.d = linkPath(drawn, placed.get(drawn.from), placed.get(drawn.to));
  }
  const height = blocks.reduce((most, block) => Math.max(most, block.y + block.h), 0);
  return { columns, blocks, links, height, narrow };
}

// The flags of a link's look that it has (LINK_FLAGS), each true.
const flagsOf = (link) => Object.fromEntries(LINK_FLAGS.filter((flag) => link[flag]).map((flag) => [flag, true]));

// A link's key, "from>to": one per pair of blocks.
export function linkKey(link) {
  return `${link.from}>${link.to}`;
}

// A link's look: its kind, dashed when Kitden does not know that it is on, quiet while a change in
// preview takes it out, and a preview's dashes on a direct line a change in preview adds.
export function linkClass(link) {
  return ["link", link.kind, ...LINK_FLAGS.filter((flag) => link[flag])].join(" ");
}

// Whether a link is drawn in dashes or dots: one that skips the gateway, a preview, one not known
// to be on and one that is leaving. A dashed link fades in and out; a solid one draws and undraws.
export function linkDashed(link) {
  return link.kind === "direct" || link.kind === "preview" || Boolean(link.unk) || Boolean(link.leaving);
}

// A link's SVG path between the boxes of its two blocks ({ x, y, w, h }) by its shape.
export function linkPath(link, from, to) {
  if (link.shape === "rail") return railPath(from, to);
  return link.shape === "step" ? elbow(from, to, link.chan) : curve(from, to);
}

// The point at t (0 to 1) of the curve through `points` (de Casteljau).
function along(points, t) {
  let now = points;
  while (now.length > 1) now = now.slice(1).map(([x, y], i) => [now[i][0] + (x - now[i][0]) * t, now[i][1] + (y - now[i][1]) * t]);
  return now[0];
}

// A path of absolute M, H, V, C and Q commands, as `linkPath` gives them, as straight pieces, each
// [x0, y0, x1, y1] (a curve cut in CURVE_STEPS), with their lengths.
function pathPieces(d) {
  const words = String(d).match(/[A-Z]|-?\d*\.?\d+(?:e[-+]?\d+)?/g) || [];
  const pieces = [];
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
  return { pieces, lengths, end: { x: at[0], y: at[1] }, total: lengths.reduce((sum, length) => sum + length, 0) };
}

// The point `left` px along a path's pieces.
function pointAlong({ pieces, lengths, end }, left) {
  for (const [i, length] of lengths.entries()) {
    if (left > length && i < lengths.length - 1) {
      left -= length;
      continue;
    }
    const [x0, y0, x1, y1] = pieces[i];
    const t = length ? Math.min(1, left / length) : 0;
    return { x: x0 + (x1 - x0) * t, y: y0 + (y1 - y0) * t };
  }
  return end;
}

// The point at half the length of a path.
export function midPoint(d) {
  const path = pathPieces(d);
  return pointAlong(path, path.total / 2);
}

// Where a link's × sits: the middle of the longest stretch of its path that no block covers
// (`boxes`, { x, y, w, h }, each widened by `pad`, the ×'s half, so the × does not touch one); a
// path that runs behind a block keeps its × off it. With no such stretch, the same without the
// widening; with none at all, the middle of the path.
const CROSS_STEP = 2; // px between the points tried along a path
export function crossPoint(d, boxes = [], pad = 0) {
  const path = pathPieces(d);
  for (const grow of pad ? [pad, 0] : [0]) {
    const covered = (p) => boxes.some((b) => p.x > b.x - grow && p.x < b.x + b.w + grow && p.y > b.y - grow && p.y < b.y + b.h + grow);
    let best = null;
    let from = null;
    const steps = Math.max(1, Math.ceil(path.total / CROSS_STEP));
    for (let k = 0; k <= steps; k++) {
      const at = (path.total * k) / steps;
      const free = !covered(pointAlong(path, at));
      if (free && from === null) from = at;
      if (from !== null && (!free || k === steps)) {
        const to = free ? at : (path.total * (k - 1)) / steps;
        if (!best || to - from > best.to - best.from) best = { from, to };
        from = null;
      }
    }
    if (best) return pointAlong(path, (best.from + best.to) / 2);
  }
  return pointAlong(path, path.total / 2);
}

// What changes from the layout `before` (null: nothing drawn yet) to `after`: the block ids that
// enter, stay and leave, and the link keys likewise, in layout order (what leaves in the order of
// `before`). A block enters as an unfold when its opener showed before, and leaves as a fold when
// its opener still shows after; a block of a group that turned its page does the same.
export function drawPlan(before, after) {
  const was = new Map((before ? before.blocks : []).map((at) => [at.id, at]));
  const now = new Map(after.blocks.map((at) => [at.id, at]));
  const plan = { enter: [], stay: [], leave: [], unfold: [], fold: [], linksIn: [], linksStay: [], linksOut: [] };
  const turned = (at) => Boolean(at.turns) && turnedPage(was.get(at.turns), now.get(at.turns));
  for (const at of after.blocks) {
    if (was.has(at.id)) plan.stay.push(at.id);
    else {
      plan.enter.push(at.id);
      if ((at.opener && was.has(at.opener)) || turned(at)) plan.unfold.push(at.id);
    }
  }
  for (const at of was.values()) {
    if (now.has(at.id)) continue;
    plan.leave.push(at.id);
    if ((at.opener && now.has(at.opener)) || turned(at)) plan.fold.push(at.id);
  }
  const drawn = new Set((before ? before.links : []).map(linkKey));
  const shown = new Set(after.links.map(linkKey));
  for (const key of shown) plan[drawn.has(key) ? "linksStay" : "linksIn"].push(key);
  for (const key of drawn) if (!shown.has(key)) plan.linksOut.push(key);
  return plan;
}

// Landing (motion-spec M4 step 6): a change of many tray rows, applied or undone, shows on the map
// one row at a time. These two say which row each part of the tree belongs to, and what the tree
// looks like while some rows still wait.

// A block that changes into another one as its row lands has a twin: the other tree's block of the
// same column and name that only that tree has (a move's preview block and the server it becomes).
// Tools and groups have none.
const NO_TWIN = ["tool", "group"];
function twinOf(block, mine, other) {
  if (NO_TWIN.includes(block.kind)) return null;
  return other.blocks.find((b) => !mine.has(b.id) && !NO_TWIN.includes(b.kind) && b.column === block.column && b.name === block.name) || null;
}

// The tray row each part of the map belongs to (a block by its id, a link by its key): `from` is
// the tree drawn before, `to` the tree after, `keys` the rows. A part a row draws says so: `row` on
// a link or a preview block, `landsWith` on a block it changes; `known` is what an earlier landing
// found (an Undo plays an Apply back). A part only one tree has then takes the row of one of its
// links, of its parent or of its twin; a link only one tree has, the row of one of its ends. Any
// other part belongs to no row: it changes at once.
export function landOwners(from, to, keys, known = new Map()) {
  const rows = new Set(keys);
  const owners = new Map();
  const own = (id, row) => {
    if (!row || !rows.has(row) || owners.has(id)) return false;
    owners.set(id, row);
    return true;
  };
  for (const [id, row] of known) own(id, row);
  for (const block of [...from.blocks, ...to.blocks]) own(block.id, block.landsWith || (typeof block.row === "string" ? block.row : null));
  for (const link of [...from.links, ...to.links]) own(linkKey(link), link.row);
  const sides = [[from, to], [to, from]].map(([tree, other]) => ({
    tree, other, mine: new Set(tree.blocks.map((b) => b.id)), there: new Set(other.blocks.map((b) => b.id)), linked: new Set(other.links.map(linkKey)),
  }));
  for (let grew = true; grew; ) {
    grew = false;
    for (const { tree, other, mine, there, linked } of sides) {
      for (const block of tree.blocks) {
        if (owners.has(block.id) || there.has(block.id)) continue;
        const link = tree.links.find((l) => (l.from === block.id || l.to === block.id) && owners.has(linkKey(l)));
        const twin = twinOf(block, mine, other);
        grew = own(block.id, (link && owners.get(linkKey(link))) || owners.get(block.parent) || (twin && owners.get(twin.id))) || grew;
      }
      for (const link of tree.links) {
        const key = linkKey(link);
        if (!owners.has(key) && !linked.has(key)) grew = own(key, owners.get(link.from) || owners.get(link.to)) || grew;
      }
    }
  }
  return owners;
}

// The tree while the rows in `waiting` have not landed: each part of theirs as `from` has it (none,
// where only `to` has it), every other part as `to` has it. Blocks keep `to`'s order; one only
// `from` has goes after the block before it there, with its parent; a group left with no block in
// it goes. A block that lands in its twin's place starts where the twin shows (`from`,
// map-view.js).
export function landStage(from, to, owners, waiting = new Set()) {
  const waits = (id) => waiting.has(owners.get(id));
  const was = new Map(from.blocks.map((b) => [b.id, b]));
  const now = new Set(to.blocks.map((b) => b.id));
  const blocks = [];
  for (const block of to.blocks) {
    if (waits(block.id)) {
      if (was.has(block.id)) blocks.push(was.get(block.id));
      continue;
    }
    const twin = !was.has(block.id) && owners.has(block.id) ? twinOf(block, now, from) : null;
    blocks.push(twin && owners.get(twin.id) === owners.get(block.id) ? { ...block, from: twin.id } : block);
  }
  const placed = new Set(blocks.map((b) => b.id));
  const keep = (block) => {
    if (placed.has(block.id)) return;
    if (was.has(block.parent)) keep(was.get(block.parent));
    const i = from.blocks.indexOf(block);
    const before = from.blocks.slice(0, i).findLast((b) => placed.has(b.id));
    blocks.splice(before ? blocks.findIndex((b) => b.id === before.id) + 1 : 0, 0, block);
    placed.add(block.id);
  };
  for (const block of from.blocks) if (!now.has(block.id) && waits(block.id)) keep(block);
  const parents = new Set(blocks.map((b) => b.parent));
  const shown = blocks.filter((b) => b.kind !== "group" || parents.has(b.id));
  const ids = new Set(shown.map((b) => b.id));
  const wasLinks = new Map(from.links.map((l) => [linkKey(l), l]));
  const nowLinks = new Set(to.links.map(linkKey));
  const links = [];
  for (const link of to.links) {
    const key = linkKey(link);
    if (!waits(key)) links.push(link);
    else if (wasLinks.has(key)) links.push(wasLinks.get(key));
  }
  for (const [key, link] of wasLinks) if (!nowLinks.has(key) && waits(key)) links.push(link);
  return { ...to, blocks: shown, links: links.filter((l) => ids.has(l.from) && ids.has(l.to)) };
}

// Whether a group shows another page now (`now`) than before (`was`): both show, and both page, or
// both fold and one is open (`spread`).
function turnedPage(was, now) {
  if (!was || !now) return false;
  const turned = was.page !== undefined && now.page !== undefined && was.page !== now.page;
  return turned || (was.spread !== undefined && now.spread !== undefined && was.spread !== now.spread);
}

// The block a block of a fold goes back into: its opener, or the group whose page turned.
export function foldsInto(at) {
  return at.opener || at.turns;
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

// A cubic from the right side of `a` to the left side of `b`, level at both ends: its handles are
// half the gap long, and never under MIN_HANDLE.
function curve(a, b) {
  const [x1, y1, x2, y2] = [a.x + a.w, middle(a), b.x, middle(b)];
  const handle = Math.max(MIN_HANDLE, Math.abs(x2 - x1) / 2);
  return `M ${x1} ${y1} C ${x1 + handle} ${y1}, ${x2 - handle} ${y2}, ${x2} ${y2}`;
}

// Right angles with round corners: out of `a`, right to its channel, down (or up) and into `b`.
// Level with `b` it is one straight line.
function elbow(a, b, chan = CHANNELS[0]) {
  const [x1, y1, x2, y2] = [a.x + a.w, middle(a), b.x, middle(b)];
  const turn = x1 + chan;
  if (Math.abs(y2 - y1) < 1) return `M ${x1} ${y1} H ${x2}`;
  const r = Math.min(BEND, Math.abs(y2 - y1) / 2);
  const s = Math.sign(y2 - y1);
  return `M ${x1} ${y1} H ${turn - r} Q ${turn} ${y1} ${turn} ${y1 + s * r} V ${y2 - s * r} Q ${turn} ${y2} ${turn + r} ${y2} H ${x2}`;
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

// What the person has open after a press on the count of `id`. The count opens and folds, also a
// block a search holds open: it leaves `found.open` and folds for the rest of that search.
// `folded` keeps those ids for the search (keepFolded).
export function pressCount(model, open, found, id, folded = new Set()) {
  if (!found || !found.open.has(id)) return toggleOpen(model, open, id);
  found.open.delete(id);
  folded.add(id);
  return open.has(id) ? toggleOpen(model, open, id) : open;
}

// A search's `found` again after a full redraw, with the blocks the count folded during that search
// (`folded`) folded still. It changes `found` and returns it.
export function keepFolded(found, folded) {
  if (found) for (const id of folded) found.open.delete(id);
  return found;
}

// What the person has open after they select `block`, so it stays on the map when the search that
// showed it ends. A block that shows already (on the `pages` shown) changes nothing. Otherwise the
// blocks above it open, the outermost first, as presses would open them: one open block per
// column. A group never opens: it always shows its page.
export function keepOpen(model, open, block, pages = new Map()) {
  const shown = (set) => layoutTree(model, { open: set, pages, narrow: false }).blocks.some((at) => at.id === block.id);
  if (shown(open)) return open;
  const byId = new Map(model.blocks.map((b) => [b.id, b]));
  const above = [];
  for (let at = byId.get(block.parent); at && !above.includes(at.id); at = byId.get(at.parent)) above.unshift(at.id);
  let next = open;
  for (const id of above) if (!next.has(id) && byId.get(id).kind !== "group") next = toggleOpen(model, next, id);
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

// What a selection lights: a link's key lights its two ends and itself, a client what it reaches,
// any other block every client's path to it and what it holds on (a gateway's servers, a server's
// tools, a plugin's parts). Nothing selected, or a selection the model no longer has, lights nothing.
export function litFor(model, selected) {
  if (!selected) return new Set();
  const link = model.links.find((l) => linkKey(l) === selected);
  if (link) return new Set([link.from, link.to, selected]);
  const block = model.blocks.find((b) => b.id === selected);
  if (!block) return new Set();
  if (block.kind === "client") return litFrom(model, block.id);
  const lit = litPath(model, block.id);
  for (const own of model.links.filter((l) => l.from === block.id && l.kind === "on")) {
    lit.add(own.to);
    lit.add(linkKey(own));
  }
  return lit;
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
// folded parent opens to show it. A group's caption ("Remote") and an add card are not things to
// find, so they are never a match. Empty text finds nothing.
export function findIn(model, text) {
  const words = String(text || "").trim().toLowerCase();
  const matches = new Set();
  const open = new Set();
  if (!words) return { matches, open };
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  for (const block of model.blocks) {
    if (block.kind === "group" || block.kind === "addslot" || !String(block.name || "").toLowerCase().includes(words)) continue;
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

// `found` with only the matches the shown page (a `layout` of layoutTree) holds, which are the ones
// that light. A match on another page is named by the group's caption ("Remote · 6–10 of 12").
export function shownFound(found, layout) {
  if (!found || !layout) return found;
  const shown = new Set(layout.blocks.map((block) => block.id));
  return { ...found, matches: new Set([...found.matches].filter((id) => shown.has(id))) };
}

// What a screen reader hears for a block: its whole name, its kind word ("Skill"), meta, what
// waits for it ("in preview", its `wait` words without the dot), counts, tag, projects, the state word that matches
// its link (none where the meta says it), "Leaving" while a change in the tray takes it out, and
// its action.
export function blockLabel(block) {
  const state = block.stateInMeta ? null : STATE_SAID[block.state];
  const wait = block.wait ? block.wait.replace(/^[\s·]+/, "") : null;
  const stats = block.stats ? block.stats.map((stat) => stat.words).join(" · ") : null;
  return [block.name, block.label && block.label.words, block.meta, wait, stats, block.tag, block.projects && block.projects.said, state, block.leaving && "Leaving", block.action].filter(Boolean).join(", ");
}
