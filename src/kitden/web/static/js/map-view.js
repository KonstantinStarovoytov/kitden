// The map on a page: HTML blocks over one SVG of links, where map.js lays them out. A view keeps
// one node per block, column caption and link across draws. A block moves by its `translate` (its
// scale is the `transform`) on one frame clock, and every link is drawn again from its two blocks
// on each frame. A link the page acts on takes the pointer: a wide hit stroke, a hover look and a
// small × on its middle. A selection dims what is off its path and lays an accent line over each
// lit link. The page gives the hooks; the view knows nothing of servers, tools or clients.
import { button, byKeys, cutName, el, icon, plural, showWaits } from "./dom.js";
import { blockLabel, crossPoint, drawPlan, enterDelays, foldable, foldsInto, LINK_MS, linkClass, linkDashed, linkKey, linkPath, unfoldDelays } from "./map.js";
import { animateTo, CALM, D, IN3, OUT3, RETRACT, rollTo, unscaled } from "./motion.js";

const SVG = "http://www.w3.org/2000/svg";
const MOVE_MS = 260; // a block that moves, or a new one that fades in at its place
const HOME_MS = 220; // a dragged block that glides home
const GROW_MS = 220; // a block that grows out of another one, and every move of that draw
const GROW_SCALE = 0.4; // how small it starts, and how small it shrinks back
const TIP_AT = { x: 6, y: -28 }; // the drag tip, from the held block's top left
const TIP_POINTER = { x: 12, y: -30 }; // ... or from the pointer
const GO_MS = 180; // a block that goes, or folds back into the block that showed it
const FADE_MS = 120; // a child of an unfold fades in after its link has drawn
const FOLD_SCALE = 0.3; // how small a folded child gets as it goes
const FOLD_IN = 100; // a folded child goes this far left of its opener's right side
const GROW_STEP = 15; // between two children of an unfold that grow out of their opener
const FOLD_BACK_MS = 160; // ... and they fold back into it this fast
const ROOM = 24; // under the lowest block
const ENTER_RISE = 6; // an entering block starts this far below its place
const CAPTION_ICON = 13; // a group caption's icon
const GRIP_ICON = 13; // the grip of a block that can be dragged
const STAT_ICON = 12; // the icon of a gateway's count
const PROJECTS_ICON = 11; // the folder before a tool's projects
const TAKE_OUT_ICON = 11; // the × of a block in preview
const LABEL_ICON = 11; // the icon of a block's kind word ("Skill")
const LAMP_MS = 400; // a lamp fades to its new colour
const POP_MS = 200; // ... and pops when it turns on or off
const POP = 2.2; // from this many times its size, unless style.css says otherwise (--pop)
const TAG_POP_MS = 180; // a tool's tag of projects whose rules wait in the tray pops in
const SWITCH_POP_MS = 200; // ... and every tool's tag, as another project shows
const CROSS_MS = 120; // the × fades in
const CROSS_R = 8; // half the × (16 px): it sits with its middle on the link's
const GRACE_MS = 240; // the × stays this long after the pointer leaves, so the pointer can reach it
const HIT_MIN = 0.5; // a link fainter than this takes no pointer
const DRAW_MS = 260; // a new solid link draws in
const SWITCH_DRAW_MS = 240; // ... or in 240 ms as another project shows (a tool it turns on)
const UNDO_DRAW_MS = 480; // ... or in 480 ms as an Undo brings it back
const DRAW_BY_MOTION = { project: SWITCH_DRAW_MS, undo: UNDO_DRAW_MS };
const FADE_IN_MS = 300; // a new dashed link fades in
const FADE_OUT_MS = 240; // a dashed link that goes fades out
const UNDRAW_MS = 380; // a solid link that goes draws back to its start
const BLEND_MS = 300; // a link whose look changes blends from its old dashes to the new
const OVER_IN_MS = 180; // the accent line over a lit link fades in
const OVER_OUT_MS = 160; // ... and fades out
const NO_LINKS = { canHit: () => false, waits: () => false }; // a page that acts on no link
const COUNT_SIZE = 20; // a count's round badge
const COUNT_OUT = COUNT_SIZE / 2; // ... reaches this far past its block's right edge
const COUNT_LOOKS = ["lit", "selected", "found", "dragging", "covered", "leaving"]; // what it takes from its block

// A part a screen reader skips: the block's label says it already.
function quiet(node) {
  node.setAttribute("aria-hidden", "true");
  return node;
}

// A lamp's look by the block's `lamp` (style.css): grey is off, green on, a dashed accent ring in
// preview, a grey ring works outside the gateway, a dashed amber ring is not known. It pops when it
// turns on or off, not when it goes into a preview or comes back from one.
const LAMP_LOOKS = { on: "on", off: "", preview: "pv", out: "out", unk: "unk" };
const lampClass = (base, lamp) => [base, LAMP_LOOKS[lamp]].filter(Boolean).join(" ");
const SOLID = ["on", "off"];
const MOVES = ["move", "project", "undo"]; // the draws that move what changed

// Words whose first number rolls when it changes ("3 of 4 on", "2 clients"): the number in a holder
// of its own (kept in `nums` by its `slot`), then the rest. Other words are plain.
function rollingWords(words, nums, slot) {
  const found = /^(\d+)(.*)$/.exec(words);
  if (!found) return el("span", "block-words", words);
  const node = el("span", "block-words");
  const holder = el("span", "num roll");
  holder.append(el("span", null, found[1]));
  node.append(holder, el("span", null, found[2]));
  nums.set(slot, { holder, value: found[1] });
  return node;
}

// What a block shows, left to right: the grip of one that can be dragged, its tile (the page's
// `tile(block)`), a tool's mark, its name cut short with its meta line under it (its lamp first,
// and after its words, in the accent, what waits in the tray: `wait`) and a gateway's counts under
// that, which projects have a rule of their own for a tool, its kind word at its end (`label`,
// { icon, words }: "Skill"), a slot's action, its ports (the right one of a block that
// folds shows only while it is open), and the × of a block in preview. A tag takes the meta line's
// words where a count takes the room, else it sits beside the name; on a block with words and a
// count (a server) the folder tag of projects sits after its name too. It gives the parts, with the
// lamp and the numbers that move when they change.
function blockParts(block, { tile }) {
  const parts = [];
  const nums = new Map();
  let lamp = null;
  const withIcon = (className, name, size) => {
    const node = el("span", className);
    node.append(icon(name, size));
    return node;
  };
  if (block.grip) parts.push(quiet(withIcon("block-grip", "grip-vertical", GRIP_ICON)));
  const mark = tile ? tile(block) : null;
  if (mark) {
    const holder = quiet(el("span", "block-tile"));
    holder.append(mark);
    parts.push(holder);
  }
  // A lamp starts the meta line; a block with none (a tool) has it as a mark before its name.
  if (block.lamp && !block.meta) {
    lamp = quiet(el("span", lampClass("mark", block.lamp)));
    parts.push(lamp);
  }
  const text = el("span", "block-text");
  const top = el("span", "block-top");
  top.append(el("span", "block-name", cutName(block.name)));
  text.append(top);
  const counted = typeof block.count === "number";
  const tag = block.tag ? el("span", "block-tag", block.tag) : null;
  if (tag && !(counted && block.meta)) top.append(tag);
  // A block that has its words and a count (a server) has no room at its end: the folder tag of
  // projects goes after its name.
  const projectsTop = Boolean(block.projects && counted && block.meta);
  if (block.meta) {
    const line = el("span", "block-meta");
    if (block.lamp) {
      lamp = quiet(el("span", lampClass("lamp", block.lamp)));
      line.append(lamp);
    }
    const words = tag && counted ? tag : rollingWords(block.meta, nums, "meta");
    if (block.wait) words.append(el("span", "block-wait", block.wait));
    line.append(words);
    text.append(line);
  }
  parts.push(text);
  if (block.stats) {
    const stats = el("span", "block-stats");
    // Each count is known by its icon, so one that comes or goes before it rolls nothing.
    block.stats.forEach((stat) => {
      const one = el("span", "block-stat");
      one.append(icon(stat.icon, STAT_ICON), rollingWords(stat.words, nums, `stat:${stat.icon}`));
      stats.append(one);
    });
    parts.push(stats);
  }
  let projects = null;
  if (block.projects) {
    projects = withIcon(["block-projects", block.projects.own && "own", block.projects.pending && "pend"].filter(Boolean).join(" "), "folder", PROJECTS_ICON);
    projects.append(el("span", null, block.projects.words));
    if (projectsTop) top.append(projects);
    else parts.push(projects);
  }
  if (block.label) {
    const label = quiet(withIcon("block-label", block.label.icon, LABEL_ICON));
    label.append(el("span", null, block.label.words));
    parts.push(label);
  }
  if (block.action) parts.push(quiet(el("span", "block-action", block.action)));
  for (const side of ["left", "right"]) {
    const look = block.ports && block.ports[side];
    if (look) parts.push(quiet(el("span", [`port ${side[0]}`, look !== true && look].filter(Boolean).join(" "))));
  }
  if (block.takeOut) parts.push(quiet(withIcon("block-x", "x", TAKE_OUT_ICON)));
  return { parts, lamp, nums, projects };
}

// Everything a block's parts depend on (its tile too), as one key: they are drawn again only when
// it changes. Opening a block draws none of them again: its right port follows its aria-expanded
// in style.css, so it fades. The count of a block that folds is no part of it (countOf).
function wordsKey(block) {
  return JSON.stringify([block.kind, block.name, block.meta, block.wait, block.tag, typeof block.count, block.action, block.lamp, block.grip, block.icon, block.client, block.gateway && block.gateway.kind, block.stats, block.projects, block.label, block.ports, block.takeOut]);
}

// What a block's count says to open it or fold it ("Show 3 tools", "Hide tools"; a plugin card holds
// "items": its `unit`).
function countWords(block, open) {
  const unit = block.unit || "tool";
  return open ? `Hide ${unit}s` : `Show ${plural(block.count, unit, `${unit}s`)}`;
}

// What a block's parts showed (`drawn`, as blockParts gave them, for `block`), for its next draw:
// its lamp, the last on or off it showed (`was` keeps it through a preview), its numbers, and how
// many projects' rules its tag said wait in the tray, in which words.
function shownOf(drawn, block, was) {
  const solid = SOLID.includes(block.lamp) ? block.lamp : (was && was.solid) || null;
  const pending = (block.projects && block.projects.pending) || 0;
  return { lamp: block.lamp || null, solid, nums: new Map([...drawn.nums].map(([slot, num]) => [slot, num.value])), pending, pendingWords: pending ? block.projects.words : null };
}

// Parts drawn again (`drawn`, for `block`) move what changed since the last draw (`was`; none on a
// block's first): a lamp fades from its old colour to the new one in 400 ms ease and pops, from
// --pop times its size in 200 ms CALM, when it turns on or off; a number rolls from its old value
// (rollTo); a tool's tag of projects whose rules wait in the tray pops in, from opacity 0 and .7 of
// its size in 180 ms CALM, when it comes, names more of them, or names another at the same count.
// Web Animations, not CSS: a redraw of the page takes the map off the page and puts it back, which
// would cut a transition short and start a CSS animation again. The page calls it only while motion
// runs: reduced motion and a hidden page show the end at once.
function liven(drawn, block, was) {
  if (!was) return;
  const { lamp } = drawn;
  const pending = (block.projects && block.projects.pending) || 0;
  const other = pending && pending === was.pending && block.projects.words !== was.pendingWords;
  if (drawn.projects && (pending > (was.pending || 0) || other)) {
    animateTo(drawn.projects, [{ opacity: 0, transform: "scale(0.7)" }, { opacity: 1, transform: "none" }], { dur: TAG_POP_MS, ease: CALM });
  }
  if (lamp && was.lamp && was.lamp !== block.lamp) {
    // Both colours are read with its CSS transition off, which would give the old one for both.
    const base = lamp.classList.contains("mark") ? "mark" : "lamp";
    lamp.style.transition = "none";
    lamp.className = lampClass(base, was.lamp);
    const from = getComputedStyle(lamp).backgroundColor;
    lamp.className = lampClass(base, block.lamp);
    const now = getComputedStyle(lamp);
    const to = now.backgroundColor;
    lamp.style.transition = "";
    animateTo(lamp, [{ backgroundColor: from }, { backgroundColor: to }], { dur: LAMP_MS, ease: "ease" });
    if (SOLID.includes(block.lamp) && was.solid && was.solid !== block.lamp) {
      const scale = Number(now.getPropertyValue?.("--pop")) || POP;
      animateTo(lamp, [{ transform: `scale(${scale})` }, { transform: "none" }], { dur: POP_MS, ease: CALM });
    }
  }
  for (const [slot, { holder, value }] of drawn.nums) {
    const old = was.nums.get(slot);
    if (old === undefined || old === value) continue;
    holder.replaceChildren(el("span", null, old));
    rollTo(holder, value);
  }
}

// As another project shows, a tool's tag of projects pops in, from opacity 0 and .7 of its size in
// 200 ms CALM, whether its words changed or not (gateway-notes 7.4).
function popTag(item) {
  if (item.tag) animateTo(item.tag, [{ opacity: 0, transform: "scale(0.7)" }, { opacity: 1, transform: "none" }], { dur: SWITCH_POP_MS, ease: CALM });
}

// A group's caption: its words, with its icon (a lucide name, if it has one) before them. Words
// after a " · " are quiet ("Outside the gateway · drag one in").
function captionWords(node, name, mark) {
  const [lead, ...more] = name.split(" · ");
  if (!mark && !more.length) {
    node.textContent = name;
    return;
  }
  const words = [el("span", null, lead)];
  if (more.length) words.push(el("span", "quiet", ` · ${more.join(" · ")}`));
  node.replaceChildren(...(mark ? [icon(mark, CAPTION_ICON)] : []), ...words);
}

// A column's caption and a group's caption without Details are words; any other block is a button.
const isWords = (place) => place.kind === "column" || (place.kind === "group" && !place.details);

// A link's dashes and opacity as they show now. A solid line counts as dashes "8 0", so the gaps
// open out of it when it turns dashed.
function dashLook(path) {
  const { strokeDasharray, strokeOpacity } = getComputedStyle(path);
  return { strokeDasharray: strokeDasharray === "none" ? "8 0" : strokeDasharray, strokeOpacity };
}

// Opacity 1 leaves no inline opacity.
function fade(node, o) {
  const value = o >= 1 ? "" : String(Math.max(0, o));
  if (node.style.opacity !== value) node.style.opacity = value;
}

// Where a block shows now: a scaled block shrinks around its centre.
function boxOf({ x, y, w, h, s }) {
  return s === 1 ? { x, y, w, h } : { x: x + (w * (1 - s)) / 2, y: y + (h * (1 - s)) / 2, w: w * s, h: h * s };
}

// "+ Add" beside a column's caption, a plain small button. It opens a panel, so it says so from
// the start.
function addButton(column, onAdd) {
  const add = button("+ Add", () => onAdd && onAdd(column, add), "btn small");
  add.dataset.focus = `add:${column}`;
  add.setAttribute("aria-expanded", "false");
  return add;
}

// Runs `run` once on the next frame, or after `wait` ms when no frame comes (a browser may hold
// frames back), so a draw always lands. Whichever comes first clears the other.
export function drawSoon(run, { frame = requestAnimationFrame, wait = 120 } = {}) {
  let done = false;
  const once = () => {
    if (done) return;
    done = true;
    clearTimeout(timer);
    run();
  };
  const timer = setTimeout(once, wait);
  frame(once);
}

// One map. `view.box` (div.map) goes where the page wants it and keeps every node when it is taken
// out and put back; `view.area` holds the links' SVG, the blocks in reading order, then the hits of
// the links and the ×.
// - draw(model, layout, { selected, lit, found, open, motion }): show `layout` (map.js layoutTree)
//   of `model`. `motion` "move" moves what changed; "project" does too, for another project: a
//   tool's link it turns on draws in over 240 ms and every tool's tag pops; "undo" does too, for
//   what an Undo put back: a link that comes back draws in over 480 ms; "enter" lets every block
//   rise into its place;
//   "none" (and the first draw of a "move", reduced motion or a hidden page) shows the end at
//   once. It resolves when the motions of the blocks end; the motions of the links are not
//   waited for.
// - hold(id, point, { glide, ms, pressed, onto }): the block shows at that map point until homeIn,
//   at once or gliding there in `ms` (OUT3); `pressed` keeps the press scale on it (style.css);
//   `onto` (a block's id) hides that block at once while this one takes its spot.
//   homeIn(id, ms): it glides back to its place, 220 ms OUT3.
// - lightTarget(id) / unlightTarget(): one block at a time takes the drop look (`.drop`).
// - tip(text, { on, at }): the drag tip (`.dragtip`), 6 px right of and 28 px over the held
//   block's top left, or 12 px right of and 30 px over `at` (the pointer, a map point); plain or
//   `on` (a drop there would work). untip() takes it away.
// - wire(from, to, { plain }): a drag's wire from a block to a block or to the pointer;
//   unwire({ ms, ease }) fades it out.
// - drawIn(key, ms): a link grows from its start. node(idOrKey): a block's node or a link's path.
// A new block that takes the place of one that goes (its `from`, that block's id) starts where that
// one shows, whole, and glides to its place (260 ms OUT3); the one that goes leaves at once, its
// links fade out (240 ms ease-out), and its focus goes to the new block; one that takes a slot's
// place has its links come in as between two blocks that stay. A new block that grows out
// of another (its `growsFrom`) starts at .4 of its size, unseen, centred on that block's right side,
// and grows to its place in 220 ms OUT3 (or its `growMs`) while the other blocks of that draw glide
// as long; when it goes it shrinks back there in 180 ms IN3, and the others move as long as it grew.
// A link between two blocks that stay moves on its own: a new solid one draws in (260 ms), a new
// dashed one fades in (300 ms); a dashed one that goes fades out (240 ms), a solid one draws back to
// its start (380 ms); one that changes look (dashed or solid) blends (300 ms). One to or from a block
// that comes or goes shows as much as the fainter block. Reduced motion and a hidden page land at once.
// A press on a block opens or folds it when it folds (`onOpen(id)`), then selects it
// (`onSelect(id)`). The count of a block that folds is a button of its own, after the block in Tab
// order and over its right edge (a button cannot sit inside a button): a press on it calls
// `onFold(id)`, which opens or folds the block and draws again, and nothing else: no select, no
// Details. It stays while the block is open, to fold it again. "+ Add" beside a column's caption calls `onAdd(column, button)`. `tile(block)` gives
// what a block shows before its name. An entrance starts `enterDelay` ms late (the Gateway waits for
// the old page to leave: motion.js afterOldPage).
// `links` are the page's hooks for the links it acts on: `canHit(link)`, `tip(link)` (what its
// × does, in words; "" for a link with no removal, which gets no × and no Delete), `onClick(link)`
// and `onRemove(link)`; `waits()` says the × waits now (another change is being written: it keeps
// its place and says why, and neither it nor Delete removes anything). After the blocks the area
// holds the hit of each such link (a button for a keyboard: Enter opens, Delete removes), in
// reading order, and one ×. aimAgain() has the × say again what it does, as the hooks say now.
// A non-empty `lit` (the blocks and "from>to" links on the path of the selection) dims all else.
// When `selected` is a block, each lit link that is not a bypass line gets an accent line, in 180 ms;
// letting go takes it away in 160 ms. When `selected` is a link's key, that link is picked: it keeps
// its × and gets no accent line. glance(lit | null) lights a path the same way with no accent line,
// only while the last draw selected nothing. `onEmpty()` hears a click on the map that is on no
// block, button or link; `onHover(id | null)` the block under the pointer when it changes (null:
// the pointer left the map), never while a block is held.
export function mapView({ tile, onOpen, onSelect, onFold, onAdd, onEmpty, onHover, links: pointer = NO_LINKS, enterDelay = 0 } = {}) {
  const box = el("div", "map");
  const area = el("div", "map-area");
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "map-links");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "100%");
  // Each hit has a layer of its own in this group, so Tab can read them in one order while they
  // stack in another (makeHit).
  const hits = el("div", "map-hits");
  hits.setAttribute("role", "group");
  hits.setAttribute("aria-label", "Connections");
  hits.setAttribute("aria-hidden", "true");
  const cross = el("button", "link-x");
  cross.type = "button";
  cross.setAttribute("tabindex", "-1");
  cross.hidden = true;
  cross.append(icon("x", 10));
  // The accent lines over the lit links sit in one group after every link.
  const layer = document.createElementNS(SVG, "g");
  svg.append(layer);
  area.append(svg, hits, cross);
  box.append(area);

  // Each block: its node, where it shows now (x, y, scale s, opacity o), its size, its place in the
  // last layout (`home`), its move, and whether it goes, is held or glides back from a hold.
  const blocks = new Map();
  // Each link: its key, its path, the hit that takes the pointer for it (if the page acts on it),
  // the layout's link, the path drawn, and until when it shows whole while it draws in (`free`).
  // `exit` is the turn of the exit it runs (0: none), `drawing` the turn of its draw-in.
  const links = new Map();
  let exits = 0; // the last exit turn given
  let pointed = null; // the key of the link with the hover look and the ×
  let picked = null; // the key of the selected link: it keeps its × while none is pointed at
  let wait = 0; // the timer that ends it
  let selecting = false; // the last draw selected something
  let drawnLit = new Set(); // what the last draw lit
  let glanced = null; // what a glance lights (while nothing is selected)
  let hovered = null; // the block under the pointer, as the page was told
  const moving = new Set(); // the blocks with a move
  const waiting = []; // what waits for every motion to end
  let last = null; // the layout drawn last
  let folds = new Set(); // the blocks that fold, as the last draw read them
  let size = { w: 0, h: 0 }; // the last layout's size
  let shown = null; // the size the area has now
  let queued = false; // a frame is asked for
  let target = null; // the block with the drop look
  let tipNode = null; // the drag tip, while a drag shows one
  let tipAt = null; // the pointer it is placed by, or null: by the held block
  let wired = null; // the wire of a drag, while one shows: { from, to, path }
  let coming = new Map(); // how the new blocks of the last draw arrive (arrivals), by id
  let replacing = new Map(); // a block that goes -> the new block that takes its place
  let slotted = new Set(); // the new blocks that take a slot's place (a drop's): their links come in
  let tabPoint = null; // the point a tab's blocks grow from and shrink to, in this draw (`layout.swap`)

  const canMove = () => D(MOVE_MS) > 0 && !document.hidden;

  function press(id) {
    const item = blocks.get(id);
    if (!item || item.leaving) return;
    if (folds.has(id) && onOpen) onOpen(id);
    if (onSelect) onSelect(id);
  }

  function makeNode(id, words) {
    const node = el(words ? "div" : "button");
    if (!words) {
      node.type = "button";
      node.addEventListener("click", () => press(id));
    }
    return node;
  }

  // The count of a block that folds, as a button of its own (see the notes above mapView).
  function makeCount(id) {
    const node = el("button", "block-count");
    node.type = "button";
    node.dataset.focus = `count:${id}`;
    node.addEventListener("click", () => {
      const item = blocks.get(id);
      if (item && !item.leaving && folds.has(id) && onFold) onFold(id);
    });
    return node;
  }

  // A block's count as this draw shows it: made, worded and put in place, or taken away.
  function syncCount(item, block, open) {
    if (!block || typeof block.count !== "number") {
      dropCount(item);
      return;
    }
    if (!item.count) item.count = makeCount(item.id);
    const { count } = item;
    const words = countWords(block, open);
    if (count.textContent !== String(block.count)) count.textContent = String(block.count);
    count.setAttribute("aria-label", words);
    count.title = words;
    count.setAttribute("aria-expanded", String(open));
    paintCount(item);
    putCount(item);
  }

  function dropCount(item) {
    if (!item.count) return;
    item.count.remove();
    item.count = null;
  }

  // The count takes its block's look (the dim of a path or a search, the hold of a drag), and is a
  // Tab stop unless its block is on its way out.
  function paintCount(item) {
    const { count, node } = item;
    if (!count) return;
    const has = new Set(node.className.split(" "));
    const look = ["block-count", ...COUNT_LOOKS.filter((name) => has.has(name))].join(" ");
    if (count.className !== look) count.className = look;
    if (item.leaving) count.setAttribute("tabindex", "-1");
    else if (count.getAttribute("tabindex") !== null) count.removeAttribute("tabindex");
  }

  // The count's right side is COUNT_OUT past its block's, level with its middle: where it sits when
  // the block is scaled (about its centre) too. Its opacity is the block's.
  function putCount({ count, x, y, s, o, w, h }) {
    if (!count) return;
    count.style.translate = `calc(${x + (w * (1 + s)) / 2 + COUNT_OUT}px - 100%) ${y + h / 2 - COUNT_OUT}px`;
    count.style.transform = s === 1 ? "" : `scale(${s})`;
    fade(count, o);
  }

  // A count sits right after its block, so Tab reads it next. A count out of place is put there, and
  // focus on it goes back to it.
  function seatCounts() {
    const focused = document.activeElement;
    for (const { node, count } of blocks.values()) {
      if (!count || !node.parentNode) continue;
      const kids = [...area.children];
      const after = kids[kids.indexOf(node) + 1] || null;
      if (after !== count) area.insertBefore(count, after);
    }
    if (focused && focused !== document.activeElement && area.contains(focused)) focused.focus({ preventScroll: true });
  }

  // A block at (x, y), scaled by s from its centre, at opacity o. The place is the `translate`
  // property and only the scale is `transform`: a press scales the block with the CSS `scale`
  // property, which turns about the block's own middle only when the place is not in `transform`.
  function put(item, { x, y, s, o }) {
    Object.assign(item, { x, y, s, o });
    item.node.style.translate = `${x}px ${y}px`;
    item.node.style.transform = s === 1 ? "" : `scale(${s})`;
    fade(item.node, o);
    putCount(item);
  }

  // A block's classes: its look from the last draw, `.lit` on the lit path, `.dragging` while it is
  // held or glides back, `.pressed` while the pointer that holds it is down, `.drop` while it is the
  // drop target, `.covered` while a held block takes its spot, and `.leaving` while it leaves the map, except a child of a fold, which only
  // shrinks back into its opener, and a block of another tab (`tabPoint`). A block that leaves is no
  // Tab stop while it goes.
  function paint(item) {
    const classes = [...item.look.split(" "), item.lit && "lit", (item.held || item.back) && "dragging", item.pressed && "pressed", item.id === target && "drop", item.covered && "covered", item.leaving && !item.folds && !tabPoint && "leaving"];
    const look = [...new Set(classes.filter(Boolean))].join(" ");
    if (item.node.className !== look) item.node.className = look;
    if (item.leaving) item.node.setAttribute("tabindex", "-1");
    else if (item.node.getAttribute("tabindex") !== null) item.node.removeAttribute("tabindex");
    paintCount(item);
  }

  // A block's node as this draw shows it: its look, words, size and what a screen reader hears. The
  // layout's words win (a group that pages names which ones show).
  function fill(item, place, source, { selected, lit, found, open, motion }) {
    const block = place.name !== undefined && source !== place ? { ...source, name: place.name } : source;
    const { node } = item;
    const name = String(block.name || "");
    const matched = Boolean(found && found.matches.has(place.id));
    item.lit = lit.has(place.id);
    if (place.kind === "column") {
      item.look = "map-caption";
      const words = JSON.stringify([block.caption, Boolean(block.add)]);
      if (words !== item.words) {
        item.words = words;
        const parts = block.caption ? [el("span", null, block.caption)] : [];
        if (block.add) {
          parts.push(addButton(block.id, onAdd));
        }
        node.replaceChildren(...parts);
      }
    } else if (item.div) {
      item.look = matched ? "caption found" : "caption";
      const words = JSON.stringify([name, block.icon]);
      if (item.words !== words) captionWords(node, name, block.icon);
      item.words = words;
      node.title = name;
    } else {
      const group = place.kind === "group";
      const folding = folds.has(place.id);
      // A block whose removal waits in the tray looks leaving too, and stays a Tab stop.
      item.look = [group ? "caption" : `block ${place.kind}`, !group && folding && typeof block.count === "number" && "counted", block.leaving && "leaving", block.drags && "drags", place.id === selected && "selected", matched && "found"].filter(Boolean).join(" ");
      node.dataset.focus = `block:${place.id}`;
      if (block.state) node.dataset.state = block.state;
      else delete node.dataset.state;
      node.title = block.takeOut || block.title || name;
      node.setAttribute("aria-label", blockLabel(block));
      const words = group ? JSON.stringify([name, block.icon]) : wordsKey(block);
      if (words !== item.words) {
        item.words = words;
        if (group) captionWords(node, name, block.icon);
        else {
          const drawn = blockParts(block, { tile });
          node.replaceChildren(...drawn.parts);
          if (canMove()) liven(drawn, block, item.shown);
          item.shown = shownOf(drawn, block, item.shown);
          item.tag = drawn.projects;
        }
      }
      if (motion === "project" && canMove()) popTag(item);
      // A block that folds says whether it is open by what is open, not by what shows yet.
      if (folding) node.setAttribute("aria-expanded", String(open.has(place.id)));
      else node.removeAttribute("aria-expanded");
    }
    paint(item);
    // A group's caption in words is as wide as its words, up to what style.css lets it have.
    if (item.w !== place.w && !(item.div && place.kind === "group")) node.style.width = `${place.w}px`;
    if (item.h !== place.h) node.style.height = `${place.h}px`;
    Object.assign(item, { kind: place.kind, w: place.w, h: place.h, home: { x: place.x, y: place.y }, growsFrom: block.growsFrom || null, growMs: block.growMs || GROW_MS, grows: Boolean(block.grows) });
    const counting = place.kind !== "column" && !item.div && place.kind !== "group" && folds.has(place.id);
    syncCount(item, counting ? block : null, open.has(place.id));
  }

  // A block that is a caption now and a button later (or back) gets a new node in the same place.
  function swap(item, place) {
    const node = makeNode(place.id, isWords(place));
    if (item.node.parentNode) area.insertBefore(node, item.node);
    item.node.remove();
    dropCount(item);
    Object.assign(item, { node, div: isWords(place), words: null, look: "", w: 0, h: 0 });
    put(item, item);
  }

  // Move a block to `to` ({ x, y, s, o }) in `dur` ms from `start`, then `then(item)`. A newer
  // move takes the place of an older one; a move to where the block already goes, or rests,
  // changes nothing.
  function go(item, to, { dur, ease, start, then = null }) {
    const same = (at) => at.x === to.x && at.y === to.y && at.s === to.s && at.o === to.o;
    if (item.move ? same(item.move.to) : same(item)) return;
    item.move = { from: { x: item.x, y: item.y, s: item.s, o: item.o }, to, dur, ease, start, then };
    moving.add(item);
  }

  function stop(item) {
    item.move = null;
    moving.delete(item);
  }

  function unlink(key) {
    const item = links.get(key);
    item.exit = 0;
    item.path.remove();
    dropHit(item);
    dropOver(item);
    links.delete(key);
  }

  // A link between two blocks that stay goes: a dashed one fades out, a solid one draws back to its
  // start, and it is removed by time. It takes no pointer meanwhile.
  function retire(key) {
    const item = links.get(key);
    const { path } = item;
    const turn = ++exits;
    item.exit = turn;
    item.drawing++;
    dropHit(item);
    const faint = linkDashed(item.link);
    const ms = faint ? FADE_OUT_MS : UNDRAW_MS;
    if (faint) animateTo(path, [{ opacity: Number(path.style.opacity || 1) }, { opacity: 0 }], { dur: ms, ease: "ease-out", fill: "forwards" });
    else {
      path.setAttribute("pathLength", "1");
      path.style.strokeDasharray = "1";
      animateTo(path, [{ strokeDashoffset: 0 }, { strokeDashoffset: 1 }], { dur: ms, ease: RETRACT, fill: "forwards" });
    }
    setTimeout(() => {
      if (item.exit === turn) unlink(key);
    }, D(ms));
  }

  // The accent line over a lit link, made once for it. It follows the link, and fades in (reduced
  // motion and a hidden page just show it). One that is on its way out comes back whole at once.
  // A link that is still drawing in (`free` is a real time) gets its line when it has drawn.
  function lay(item) {
    if (item.over) {
      if (!item.overOut) return;
      item.overOut = 0;
      for (const run of item.over.getAnimations ? item.over.getAnimations() : []) run.cancel();
      return;
    }
    const over = document.createElementNS(SVG, "path");
    over.setAttribute("class", "link-over");
    if (item.d) over.setAttribute("d", item.d);
    layer.append(over);
    item.over = over;
    if (canMove()) animateTo(over, [{ opacity: 0 }, { opacity: 1 }], { dur: OVER_IN_MS, delay: unscaled(Math.max(0, item.free - performance.now())), ease: CALM });
  }

  // It fades out, and is removed by time; reduced motion and a hidden page take it away at once.
  function lift(item) {
    if (!item.over || item.overOut) return;
    if (!canMove()) {
      dropOver(item);
      return;
    }
    const turn = ++exits;
    item.overOut = turn;
    animateTo(item.over, [{ opacity: 1 }, { opacity: 0 }], { dur: OVER_OUT_MS, ease: "ease-in", fill: "forwards" });
    setTimeout(() => {
      if (item.overOut === turn) dropOver(item);
    }, D(OVER_OUT_MS));
  }

  function dropOver(item) {
    if (!item.over) return;
    item.over.remove();
    item.over = null;
    item.overOut = 0;
  }

  // A link's classes: its kind, whether it is on the lit path and whether it is the selected link.
  function linkLook(link, lit) {
    const key = linkKey(link);
    return `${linkClass(link)}${lit.has(key) ? " lit" : ""}${key === picked ? " picked" : ""}`;
  }

  // Give a link its look. With `blend`, a link whose dashes or opacity change blends from the old to
  // the new, unless it draws in or draws back right now: its dashes are the draw's then.
  function setLook(item, look, blend) {
    if (look === item.look) return;
    const draws = item.exit || item.path.style.strokeDasharray;
    const was = blend && item.look && !draws ? dashLook(item.path) : null;
    item.path.setAttribute("class", look);
    item.path.classList.toggle("hov", item.key === pointed);
    if (was) {
      const now = endLook(item.path);
      if (now.strokeDasharray !== was.strokeDasharray || now.strokeOpacity !== was.strokeOpacity) animateTo(item.path, [was, now], { dur: BLEND_MS, ease: CALM });
    }
    item.look = look;
  }

  // A link that comes back during its exit is shown whole again at once.
  function revive(item) {
    item.exit = 0;
    item.drawing++;
    for (const run of item.path.getAnimations ? item.path.getAnimations() : []) run.cancel();
    item.path.removeAttribute("pathLength");
    item.path.style.strokeDasharray = "";
  }

  // The look a link has once its transitions end. Read on a copy of it with transitions off: read on
  // the link itself, `stroke-opacity` is still the old one, as its transition has just started, and
  // switching its own transitions off would make its colour snap.
  function endLook(path) {
    const copy = document.createElementNS(SVG, "path");
    copy.setAttribute("class", path.getAttribute("class"));
    copy.style.transition = "none";
    svg.append(copy);
    try {
      return dashLook(copy);
    } finally {
      copy.remove();
    }
  }

  // What the × says is for the link it sits on.
  function aimCross(item) {
    const tip = pointer.tip(item.link);
    cross.setAttribute("aria-label", tip);
    showWaits(cross, pointer.waits?.() || false, tip);
  }

  function aimAgain() {
    const item = links.get(pointed || picked);
    if (item && item.hit) aimCross(item);
  }

  // The hover look goes at once, and the × with it, unless a link is selected: then the × goes to it.
  // A link with keyboard focus has no other mark of it, so the look goes back to it.
  function unpoint() {
    clearTimeout(wait);
    const item = pointed && links.get(pointed);
    if (item) item.path.classList.remove("hov");
    pointed = null;
    const focused = [...links.values()].find((other) => other.hit && other.hit === document.activeElement && other.hit.style.display !== "none");
    if (focused && byKeys()) {
      pointAt(focused);
      return;
    }
    const rest = picked && links.get(picked);
    if (rest && rest.hit) aimCross(rest);
    placeCross();
  }

  // ... or after the grace, which the clock of the motions does not scale, so a pointer that is
  // on its way to the × always has the time.
  function unpointSoon() {
    clearTimeout(wait);
    wait = setTimeout(unpoint, GRACE_MS);
  }

  // The × on the middle of the link with the hover look, else of the selected link, when that link
  // has a removal: of the part of it no block covers (a line that runs behind a block keeps its ×
  // off it). It follows the link; it moves to another link at once, and fades in only when it was
  // hidden.
  function placeCross() {
    const item = links.get(pointed || picked);
    if (!item || !item.hit || !item.d || !pointer.tip(item.link)) {
      cross.hidden = true;
      return;
    }
    const mid = crossPoint(item.d, blockBoxes(), CROSS_R);
    cross.style.transform = `translate(${Math.round(mid.x - CROSS_R)}px, ${Math.round(mid.y - CROSS_R)}px)`;
    if (!cross.hidden) return;
    cross.hidden = false;
    animateTo(cross, [{ opacity: 0 }, { opacity: 1 }], { dur: CROSS_MS, ease: CALM });
  }

  // Where the blocks that show are now, as boxes.
  const blockBoxes = () => [...blocks.values()].filter((item) => item.o > 0).map(boxOf);

  function pointAt(item) {
    clearTimeout(wait);
    if (pointed && pointed !== item.key) links.get(pointed)?.path.classList.remove("hov");
    pointed = item.key;
    item.path.classList.add("hov");
    aimCross(item);
    placeCross();
  }

  // A press on a link points at it, so its × is there for what comes next.
  function pressLink(item) {
    pointAt(item);
    pointer.onClick(item.link);
  }

  // Enter or Space opens the link, once: a key held down only keeps the page from scrolling.
  // Delete or Backspace removes it, once: a key held down or one with a modifier is not that.
  // A link with no removal leaves Delete and Backspace to the page.
  function keyOnHit(event, item) {
    const press = event.key === "Enter" || event.key === " ";
    const plain = !event.repeat && !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey;
    const remove = plain && (event.key === "Delete" || event.key === "Backspace") && Boolean(pointer.tip(item.link));
    if (!press && !remove) return;
    event.preventDefault();
    if (press && !event.repeat) pressLink(item);
    else if (remove && !pointer.waits?.()) pointer.onRemove(item.link);
  }

  // A link's hit: a wide stroke over it (narrower over a line that skips the gateway), and a button
  // for a keyboard. It lies in a layer of its own: a line that skips the gateway in the layer
  // under the others (`.under`, style.css), so a solid link wins where they cross.
  function makeHit(item) {
    const layer = document.createElementNS(SVG, "svg");
    layer.setAttribute("class", item.link.kind === "direct" ? "map-hit under" : "map-hit");
    layer.setAttribute("width", "100%");
    layer.setAttribute("height", "100%");
    const hit = document.createElementNS(SVG, "path");
    layer.append(hit);
    hit.setAttribute("class", item.link.kind === "direct" ? "hit direct" : "hit");
    hit.setAttribute("tabindex", "0");
    hit.setAttribute("role", "button");
    hit.dataset.focus = `link:${item.key}`; // a redraw of the page gives focus back to it
    if (item.d) hit.setAttribute("d", item.d);
    hit.addEventListener("pointerover", () => pointAt(item));
    hit.addEventListener("pointerout", unpointSoon);
    // Only focus after a key points at it (`byKeys`: Safari does not always match `:focus-visible`
    // on an SVG path). A mouse click focuses the hit too, and the panel gives that focus back when
    // it closes, long after the pointer has gone; the click itself points at it (pressLink).
    hit.addEventListener("focus", () => {
      if (byKeys()) pointAt(item);
    });
    hit.addEventListener("blur", unpointSoon);
    hit.addEventListener("click", () => pressLink(item));
    hit.addEventListener("keydown", (event) => keyOnHit(event, item));
    return hit;
  }

  function dropHit(item) {
    if (!item.hit) return;
    const { hit } = item;
    item.hit = null;
    if (pointed === item.key) unpoint();
    hit.parentNode.remove();
    showHits();
  }

  // The group of hits is there for a screen reader only while it holds a hit.
  function showHits() {
    if (hits.children.length) hits.removeAttribute("aria-hidden");
    else hits.setAttribute("aria-hidden", "true");
  }

  // A link has a hit while the page acts on it, named for a screen reader by its two blocks; its
  // removal, when it has one, is its description and Delete its key.
  function syncHit(item, names) {
    if (!pointer.canHit(item.link)) {
      dropHit(item);
      return;
    }
    if (!item.hit) item.hit = makeHit(item);
    const tip = pointer.tip(item.link);
    const said = { "aria-label": `${names.get(item.link.from)} to ${names.get(item.link.to)}`, "aria-description": tip || null, "aria-keyshortcuts": tip ? "Delete" : null };
    for (const [name, value] of Object.entries(said)) {
      if (value === null) item.hit.removeAttribute(name);
      else if (item.hit.getAttribute(name) !== value) item.hit.setAttribute(name, value);
    }
  }

  // A block that went: its node and its links leave the page.
  function drop(item) {
    if (blocks.get(item.id) !== item) return;
    stop(item);
    blocks.delete(item.id);
    item.node.remove();
    dropCount(item);
    for (const [key, link] of links) if (link.link.from === item.id || link.link.to === item.id) unlink(key);
  }

  // How the new blocks of a draw arrive (`coming`, by id): one that takes the place of a block that
  // goes (`from`, kept in `replacing`) starts where that one shows, whole; one that grows out of
  // another block (`growsFrom`) starts small on that block's right side, unseen. It gives how long
  // the blocks of the draw move: as long as a block grows or shrinks back (GROW_MS or its `growMs`),
  // else MOVE_MS. A layout with a `swap` point is another tab of the page: each new block grows
  // from there in its turn (swapIn).
  function arrivals(layout, byId, after) {
    coming = new Map();
    replacing = new Map();
    slotted = new Set();
    tabPoint = layout.swap || null;
    let pace = MOVE_MS;
    for (const place of layout.blocks) {
      if (tabPoint && !blocks.has(place.id)) {
        coming.set(place.id, swapIn(coming.size));
        continue;
      }
      const block = byId.get(place.id);
      if (!block || blocks.has(place.id)) continue;
      const was = block.from && !after.has(block.from) ? blocks.get(block.from) : null;
      const opener = block.growsFrom ? blocks.get(block.growsFrom) : null;
      if (was) {
        coming.set(place.id, { x: was.x, y: was.y, s: 1, o: 1 });
        replacing.set(was.id, place.id);
        if (was.kind === "slot") slotted.add(place.id);
      } else if (opener) {
        coming.set(place.id, sideOf(opener, place));
        pace = block.growMs || GROW_MS;
      }
    }
    for (const item of blocks.values()) if (item.growsFrom && !after.has(item.id) && !item.leaving) pace = item.growMs;
    return pace;
  }

  // Another tab (library-notes §6): a new block starts small and unseen at the swap point, and grows
  // to its place in 220 ms OUT3, the `turn`th 15 ms after the first (comeIn); one that goes shrinks
  // to the swap point's x at its own y in 160 ms IN3 (leaveTo, goneMs). The blocks that stay move as
  // in any draw.
  const swapIn = (turn) => ({ x: tabPoint.x, y: tabPoint.y, s: GROW_SCALE, o: 0, turn });

  // How a block moves to its place in this draw: in its turn, as a new block of another tab grows,
  // else in `pace` with the others.
  function comeIn(id, pace, start) {
    const turn = coming.get(id)?.turn;
    return turn === undefined ? { dur: D(pace), ease: OUT3, start } : { dur: D(GROW_MS), ease: OUT3, start: start + D(turn * GROW_STEP) };
  }

  // How long a block takes to go: a child of a fold that grew, or a block of another tab, folds
  // back fast; any other goes in GO_MS.
  const goneMs = (item) => (tabPoint || (item.grows && item.folds) ? FOLD_BACK_MS : GO_MS);

  // A block of `size` small and unseen, centred on the right side of `opener` (where it grows from).
  function sideOf(opener, size) {
    const at = opener.home || opener;
    return { x: at.x + opener.w - size.w / 2, y: at.y + opener.h / 2 - size.h / 2, s: GROW_SCALE, o: 0 };
  }

  // A child of an unfold, the `at`th. One that grows (`grows`: the Library's Inside rows) starts
  // small and unseen 100 px inside its opener's right side and grows to its place, 220 ms OUT3, 15 ms
  // apart, its links showing with it; it folds back there in 160 ms IN3 (leaveTo). Any other waits
  // at its place while its links draw (`delays`), then fades in: true, its links draw in first.
  function unfoldIn(item, place, end, { start, at, delays }) {
    const opener = item.grows && blocks.get(place.opener);
    if (opener) {
      put(item, intoOpener(opener.home || opener, opener, item));
      go(item, end, { dur: D(GROW_MS), ease: OUT3, start: start + D(at * GROW_STEP) });
      return false;
    }
    put(item, { ...end, o: 0 });
    go(item, end, { dur: D(FADE_MS), ease: OUT3, start: start + D(delays[at]) });
    return true;
  }

  // Small and unseen inside the right side of an opener of size `opener` at `at`.
  const intoOpener = (at, opener, item) => ({ x: at.x + opener.w - FOLD_IN, y: at.y + opener.h / 2 - item.h / 2, s: FOLD_SCALE, o: 0 });

  // Where a block that goes moves to: a child of a fold (its `opener`) shrinks back into the opener's
  // right side, a block that grew out of another shrinks back into it, anything else fades in place.
  function leaveTo(item, opener) {
    if (tabPoint) return { x: tabPoint.x, y: item.y, s: GROW_SCALE, o: 0 };
    if (opener) return intoOpener(opener, opener, item);
    const grew = item.growsFrom && blocks.get(item.growsFrom);
    return grew ? sideOf(grew, item) : { x: item.x, y: item.y, s: item.s, o: 0 };
  }

  // A block whose place a new block takes (arrivals) leaves at once, and its focus goes to that
  // block (to its count, when the focus was on a count and it has one), which takes its node's
  // place. Its links fade out where they are (240 ms ease-out, with `fades`) and are removed by
  // time; they are no links of the map any more. False for any other.
  function handOver(item, fades) {
    const next = blocks.get(replacing.get(item.id));
    if (!next || blocks.get(item.id) !== item) return false;
    const onCount = Boolean(item.count?.contains(document.activeElement));
    const focused = onCount || item.node.contains(document.activeElement);
    if (item.node.parentNode) area.insertBefore(next.node, item.node);
    stop(item);
    blocks.delete(item.id);
    item.node.remove();
    dropCount(item);
    if (focused) ((onCount && next.count) || next.node).focus({ preventScroll: true });
    for (const [key, link] of links) {
      if (link.link.from !== item.id && link.link.to !== item.id) continue;
      if (!fades) {
        unlink(key);
        continue;
      }
      const { path } = link;
      dropHit(link);
      dropOver(link);
      links.delete(key);
      animateTo(path, [{ opacity: Number(path.style.opacity || 1) }, { opacity: 0 }], { dur: FADE_OUT_MS, ease: "ease-out", fill: "forwards" });
      setTimeout(() => path.remove(), D(FADE_OUT_MS));
    }
    return true;
  }

  // Every link drawn again from its two blocks as they show now. Its opacity is the lower of
  // theirs, except while it draws in. The × follows its link.
  function paintLinks(now) {
    for (const item of links.values()) {
      const a = blocks.get(item.link.from);
      const b = blocks.get(item.link.to);
      if (!a || !b) continue;
      const d = linkPath(item.link, boxOf(a), boxOf(b));
      if (d !== item.d) {
        item.path.setAttribute("d", d);
        if (item.hit) item.hit.setAttribute("d", d);
        if (item.over) item.over.setAttribute("d", d);
        item.d = d;
      }
      const o = now < item.free ? 1 : Math.min(a.o, b.o);
      fade(item.path, o);
      if (item.over) fade(item.over, o);
      // A link that fades away takes no pointer.
      if (!item.hit) continue;
      const display = o < HIT_MIN ? "none" : "";
      if (item.hit.style.display !== display) item.hit.style.display = display;
      if (display && pointed === item.key) unpoint();
    }
    placeCross();
    placeTip();
    placeWire();
  }

  // The area takes the last layout's size; while blocks move, the larger of that and its own.
  function fit(grow) {
    const w = grow && shown ? Math.max(shown.w, size.w) : size.w;
    const h = grow && shown ? Math.max(shown.h, size.h) : size.h;
    area.style.width = `${w}px`;
    area.style.height = `${h}px`;
    shown = { w, h };
  }

  // One tick of the clock: each block at its own eased point of its move (opacity never past its
  // end), then every link. A move that ends does what it was for: a block that went leaves.
  function step(now) {
    for (const item of [...moving]) {
      const { from, to, dur, ease, start, then } = item.move;
      const t = dur > 0 ? Math.min(1, Math.max(0, (now - start) / dur)) : 1;
      if (t < 1) {
        const k = ease(t);
        put(item, { x: from.x + (to.x - from.x) * k, y: from.y + (to.y - from.y) * k, s: from.s + (to.s - from.s) * k, o: from.o + (to.o - from.o) * Math.min(1, k) });
        continue;
      }
      stop(item);
      put(item, to);
      if (item.back) {
        item.back = false;
        paint(item);
      }
      if (then) then(item);
    }
    paintLinks(now);
    if (moving.size) return;
    fit(false);
    for (const done of waiting.splice(0)) done();
  }

  function kick() {
    if (queued || !moving.size) return;
    queued = true;
    drawSoon(() => {
      queued = false;
      step(performance.now());
      kick();
    });
  }

  // After a change the links follow at once, and the clock runs while anything moves; `atOnce`
  // puts every motion at its end now. The promise ends with the last motion.
  function run(atOnce) {
    step(atOnce ? Infinity : performance.now());
    kick();
    return moving.size ? new Promise((done) => waiting.push(done)) : Promise.resolve();
  }

  // A new node goes before the node of the next block in reading order. Nodes that stay keep their
  // place, so focus stays on them; only a layout that reads them in another order (a narrow flip)
  // puts every node in order again, and focus goes back where it was.
  function order(layout) {
    let next = hits;
    for (let i = layout.blocks.length - 1; i >= 0; i--) {
      const { node } = blocks.get(layout.blocks[i].id);
      if (!node.parentNode) area.insertBefore(node, next);
      next = node;
    }
    const index = new Map([...area.children].map((node, i) => [node, i]));
    const nodes = layout.blocks.map((place) => blocks.get(place.id).node);
    if (!nodes.every((node, i) => i === 0 || index.get(nodes[i - 1]) < index.get(node))) {
      const focused = document.activeElement;
      for (const node of nodes) area.insertBefore(node, hits);
      if (focused && focused !== document.activeElement && area.contains(focused)) focused.focus({ preventScroll: true });
    }
    seatCounts();
  }

  // The hits in reading order, so Tab reads them so: by the blocks they join, as Tab reads the
  // blocks (from the first one, then to the first). A layer moves only when it is out of place, and
  // focus on a hit that moves goes back to it.
  function orderHits(layout) {
    const at = new Map(layout.blocks.map((place, i) => [place.id, i]));
    const rank = (link) => [at.get(link.from) ?? Infinity, at.get(link.to) ?? Infinity];
    const read = layout.links.map((link) => [rank(link), links.get(linkKey(link)).hit]).filter(([, hit]) => hit);
    read.sort(([a], [b]) => a[0] - b[0] || a[1] - b[1]);
    const focused = document.activeElement;
    for (const [i, [, hit]] of read.entries()) {
      if (hits.children[i] !== hit.parentNode) hits.insertBefore(hit.parentNode, hits.children[i] || null);
    }
    if (focused && focused !== document.activeElement && hits.contains(focused)) focused.focus({ preventScroll: true });
  }

  function draw(model, layout, { selected = null, lit = new Set(), found = null, open = new Set(), motion = "move" } = {}) {
    performance.mark("kitden:map-start");
    const enters = motion === "enter" && canMove();
    const moves = enters || (MOVES.includes(motion) && last !== null && canMove());
    const linksMove = moves && !enters; // links come, go and change look on their own
    const plan = drawPlan(last, layout);
    const before = new Map((last ? last.blocks : []).map((at) => [at.id, at]));
    const after = new Map(layout.blocks.map((at) => [at.id, at]));
    const byId = new Map(model.blocks.map((block) => [block.id, block]));
    const columns = new Map(model.columns.map((column) => [column.id, column]));
    const start = performance.now();
    // A selection that is a link's key picks that link; any other selection is a block. A selection,
    // or a lit path, ends a glance.
    picked = layout.links.some((link) => linkKey(link) === selected) ? selected : null;
    selecting = selected !== null;
    if (selecting || lit.size) glanced = null;
    drawnLit = lit;
    const shown = glanced || lit;
    box.classList.toggle("focus", shown.size > 0);
    folds = foldable(model);
    const unfold = new Map(plan.unfold.map((id, i) => [id, i]));
    const delays = unfoldDelays(plan.unfold.length);
    const waves = enterDelays(layout.blocks.length); // when each block of an entrance starts
    const opened = new Set(); // new blocks of an unfold: their links draw in first
    const pace = arrivals(layout, byId, after); // how long the blocks of this draw move

    for (const [i, place] of layout.blocks.entries()) {
      const block = place.kind === "column" ? columns.get(place.column) : byId.get(place.id) || place;
      let item = blocks.get(place.id);
      const fresh = !item;
      if (fresh) {
        item = { id: place.id, node: makeNode(place.id, isWords(place)), div: isWords(place), x: place.x, y: place.y, s: 1, o: 1, w: 0, h: 0, move: null, leaving: false, held: false, back: false, lit: false, look: "", words: null };
        blocks.set(place.id, item);
      } else if (item.div !== isWords(place)) swap(item, place);
      item.leaving = false;
      fill(item, place, block, { selected, lit: shown, found, open, motion });
      const end = { x: place.x, y: place.y, s: 1, o: 1 };
      if (item.held) continue;
      if (!moves) {
        stop(item);
        put(item, end);
        // A block that glided home lands here at once, and lets go of its drag look.
        if (item.back) {
          item.back = false;
          paint(item);
        }
      } else if (enters) {
        // The entrance: it waits below its place, unseen, then rises in its turn.
        put(item, { ...end, y: end.y + ENTER_RISE, o: 0 });
        go(item, end, { dur: D(MOVE_MS), ease: OUT3, start: start + D(waves[i] + enterDelay) });
      } else if (fresh && unfold.has(place.id)) {
        if (unfoldIn(item, place, end, { start, at: unfold.get(place.id), delays })) opened.add(place.id);
      } else {
        if (fresh) put(item, coming.get(place.id) || { ...end, o: 0 });
        go(item, end, comeIn(place.id, pace, start));
      }
    }

    for (const id of plan.leave) {
      const item = blocks.get(id);
      if (!item) continue;
      if (handOver(item, linksMove)) continue;
      Object.assign(item, { leaving: true, folds: plan.fold.includes(id), held: false, back: false });
      paint(item);
      if (!moves) {
        drop(item);
        continue;
      }
      const to = leaveTo(item, plan.fold.includes(id) ? after.get(foldsInto(before.get(id))) : null);
      go(item, to, { dur: D(goneMs(item)), ease: IN3, start, then: drop });
    }

    const drawsIn = [];
    const arrives = [];
    const names = new Map(model.blocks.map((block) => [block.id, String(block.name || "")]));
    for (const link of layout.links) {
      const key = linkKey(link);
      let item = links.get(key);
      if (item && item.exit) revive(item);
      if (!item) {
        item = { key, path: document.createElementNS(SVG, "path"), hit: null, over: null, link, d: "", look: "", free: 0, drawing: 0, exit: 0, overOut: 0 };
        svg.insertBefore(item.path, layer);
        links.set(key, item);
        if (opened.has(link.to) && before.has(link.from) && !linkDashed(link)) drawsIn.push([key, start + D(delays[unfold.get(link.to)] + FADE_MS)]);
        else if (linksMove && before.has(link.from) && (before.has(link.to) || slotted.has(link.to))) arrives.push(key);
      }
      item.link = link;
      setLook(item, linkLook(link, shown), linksMove);
      syncHit(item, names);
    }
    const shownLinks = new Set(layout.links.map(linkKey));
    for (const [key, item] of links) {
      if (shownLinks.has(key)) continue;
      // A link to a block that goes stays while it goes, and fades with it.
      const goes = [item.link.from, item.link.to].some((id) => blocks.get(id)?.leaving && blocks.get(id).move);
      if (goes) {
        item.free = 0;
        continue;
      }
      // Between two blocks that stay it goes on its own, by time; else at once.
      const stay = [item.link.from, item.link.to].every((id) => blocks.has(id) && !blocks.get(id).leaving);
      if (!linksMove || !stay) unlink(key);
      else if (!item.exit) retire(key);
    }
    orderHits(layout);
    showHits();
    // Lit links are drawn last, over the others (the accent lines sit over them all).
    const litPaths = layout.links.filter((link) => shown.has(linkKey(link))).map((link) => links.get(linkKey(link)).path);
    const paths = [...svg.children].slice(0, -1);
    if (litPaths.some((path, i) => paths[paths.length - litPaths.length + i] !== path)) for (const path of litPaths) svg.insertBefore(path, layer);
    // The × says what it does now (a removal that waits in the tray takes it out), on the link pointed
    // at, else on the picked link.
    aimAgain();

    order(layout);
    box.classList.toggle("narrow", Boolean(layout.narrow));
    box.classList.toggle("finding", Boolean(found));
    size = { w: layout.columns.reduce((most, column) => Math.max(most, column.x + column.w), 0), h: layout.height + ROOM };
    last = layout;
    for (const [key, until] of drawsIn) {
      drawIn(key, LINK_MS);
      links.get(key).free = until;
    }
    for (const key of arrives) {
      const { path, link } = links.get(key);
      if (linkDashed(link)) animateTo(path, [{ opacity: 0 }, { opacity: 1 }], { dur: FADE_IN_MS, ease: CALM });
      else drawIn(key, DRAW_BY_MOTION[motion] || DRAW_MS);
    }
    // A selected block lays an accent line over each lit link on its way, except a bypass line and
    // a link a change in preview adds or takes out (it keeps its dashes). A picked link has none.
    const lined = (link) => link.kind !== "direct" && link.kind !== "preview" && !link.leaving;
    const lines = new Set(selecting && !picked ? layout.links.filter((link) => lined(link) && shown.has(linkKey(link))).map(linkKey) : []);
    for (const key of lines) lay(links.get(key));
    for (const item of links.values()) if (item.over && !lines.has(item.key)) lift(item);
    fit(moves);
    const done = run(!moves);
    performance.mark("kitden:map-drawn");
    performance.measure("kitden:map-draw", "kitden:map-start", "kitden:map-drawn");
    return done;
  }

  // Show a block at (x, y) of the map, at once or gliding there in `ms`, until homeIn: draws leave
  // it there, and its links follow it. A block held while the pointer is down keeps its press.
  function hold(id, { x, y }, { glide = false, ms = MOVE_MS, pressed = false, onto = null } = {}) {
    const item = blocks.get(id);
    if (!item || item.leaving) return Promise.resolve();
    cover(item, onto);
    // A drag begins: a glance ends, and the page will hear of the next block the pointer is on.
    if (!item.held) {
      hovered = null;
      if (glanced) glance(null);
    }
    Object.assign(item, { held: true, back: false, pressed });
    paint(item);
    const to = { x, y, s: 1, o: 1 };
    if (glide && canMove()) go(item, to, { dur: D(ms), ease: OUT3, start: performance.now() });
    else {
      stop(item);
      put(item, to);
    }
    return run(!canMove());
  }

  // A held block glides from where it is to its place in `ms`, and loses `.dragging` when it lands.
  function homeIn(id, ms = HOME_MS) {
    const item = blocks.get(id);
    if (!item || item.leaving) return Promise.resolve();
    Object.assign(item, { held: false, pressed: false });
    cover(item, null);
    go(item, { ...item.home, s: 1, o: 1 }, { dur: D(ms), ease: OUT3, start: performance.now() });
    item.back = Boolean(item.move);
    paint(item);
    return run(!canMove());
  }

  // A held block takes the spot of another (`onto`, an id; null: none): that one hides at once
  // (`.covered`, style.css) until the held block lets go of it.
  function cover(item, onto) {
    if (item.covers === onto) return;
    const was = blocks.get(item.covers);
    if (was) {
      was.covered = false;
      paint(was);
    }
    item.covers = onto;
    const under = blocks.get(onto);
    if (!under) return;
    under.covered = true;
    paint(under);
  }

  // The drop look on one block (null: none). Its edge and fill change in 180 ms and it grows to
  // 1.05 on the spring in 260 ms (style.css).
  function lightTarget(id) {
    const was = blocks.get(target);
    target = id;
    if (was) paint(was);
    const item = blocks.get(id);
    if (item) paint(item);
  }

  function unlightTarget() {
    lightTarget(null);
  }

  // The tip of a drag: what a drop there does, in the accent when it would work (`on`). Its words
  // change at once; it follows the held block, or the pointer (`at`).
  function tip(text, { on = false, at = null } = {}) {
    tipAt = at;
    if (!tipNode) {
      tipNode = quiet(el("div", "dragtip"));
      area.append(tipNode);
    }
    tipNode.textContent = text;
    tipNode.className = on ? "dragtip on" : "dragtip";
    placeTip();
  }

  function untip() {
    if (tipNode) tipNode.remove();
    tipNode = null;
    tipAt = null;
  }

  function placeTip() {
    if (!tipNode) return;
    const held = [...blocks.values()].find((item) => item.held);
    const [from, by] = tipAt ? [tipAt, TIP_POINTER] : [held, TIP_AT];
    if (from) tipNode.style.transform = `translate(${from.x + by.x}px, ${from.y + by.y}px)`;
  }

  // The wire of a drag, from the right port of `from` to the left port of `to` (a block's id), or
  // to `to` itself (a map point: the pointer), which it reaches level. It is in the accent dashes of
  // a preview, lit, or `plain` (1.2 px, and never dimmed). It shows at once and follows its ends; a
  // new end for the same wire moves it. It is no link of the map.
  function wire(from, to, { plain = false } = {}) {
    if (!wired || wired.from !== from || wired.plain !== plain) {
      unwire();
      const path = document.createElementNS(SVG, "path");
      path.setAttribute("class", plain ? "link preview wire" : "link preview lit");
      svg.insertBefore(path, layer);
      wired = { from, plain, path };
    }
    wired.to = to;
    placeWire();
  }

  // The wire fades out (240 ms ease-out, or `ms` and `ease`) and is removed by time; no `ms`,
  // reduced motion and a hidden page take it away at once.
  function unwire({ ms = FADE_OUT_MS, ease = "ease-out" } = {}) {
    if (!wired) return;
    const { path } = wired;
    wired = null;
    if (!ms || !canMove()) {
      path.remove();
      return;
    }
    animateTo(path, [{ opacity: 1 }, { opacity: 0 }], { dur: ms, ease, fill: "forwards" });
    setTimeout(() => path.remove(), D(ms));
  }

  function placeWire() {
    const a = wired && blocks.get(wired.from);
    const b = wired && (typeof wired.to === "string" ? blocks.get(wired.to) : { ...wired.to, w: 0, h: 0, s: 1 });
    if (a && b) wired.path.setAttribute("d", linkPath({}, boxOf(a), boxOf(b)));
  }

  // A link grows from its start. It shows whole while it draws; its own dashes come back when it
  // ends, by time. So an unfold draws in only its solid links: a dotted or dashed one comes in
  // with its block.
  function drawIn(key, ms = DRAW_MS) {
    const item = links.get(key);
    const dur = D(ms);
    if (!item || !dur || document.hidden) return Promise.resolve();
    const { path } = item;
    const turn = ++item.drawing;
    path.setAttribute("pathLength", "1");
    path.style.strokeDasharray = "1";
    item.free = Math.max(item.free, performance.now() + dur);
    animateTo(path, [{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { dur: ms, ease: CALM });
    return new Promise((done) => {
      setTimeout(() => {
        if (item.drawing === turn) {
          path.removeAttribute("pathLength");
          path.style.strokeDasharray = "";
        }
        done();
      }, dur);
    });
  }

  // Light a path, or none (null), with no accent line: the box dims what is off it. It does nothing
  // while something is selected.
  function glance(set) {
    if (selecting) return;
    glanced = set && set.size ? set : null;
    const shown = glanced || drawnLit;
    box.classList.toggle("focus", shown.size > 0);
    for (const item of blocks.values()) {
      const on = shown.has(item.id);
      if (item.lit === on) continue;
      item.lit = on;
      paint(item);
    }
    // A link on its way out is left as it is.
    for (const item of links.values()) if (!item.exit) setLook(item, linkLook(item.link, shown), canMove());
  }

  // The block that holds `target`, by its focus key (or its count's), or null.
  function blockAt(target) {
    for (let at = target; at && at !== box; at = at.parentNode) {
      const focus = at.dataset && at.dataset.focus;
      if (focus && (focus.startsWith("block:") || focus.startsWith("count:"))) return focus.slice(focus.indexOf(":") + 1);
    }
    return null;
  }

  // The page hears the block under the pointer when it changes, but not while a block is held.
  function hover(id) {
    if (id === hovered || [...blocks.values()].some((item) => item.held)) return;
    hovered = id;
    if (onHover) onHover(id);
  }

  box.addEventListener("pointerover", (event) => hover(blockAt(event.target)));
  box.addEventListener("pointerleave", () => hover(null));
  // A click on the map that is on no block, button or link, where it began and where it ended: a
  // press on a block that lets go elsewhere is no click on empty map. A target the draw of a press
  // has taken out of the map (a block's words drawn again) was on that block.
  const onSomething = (node) => !box.contains(node) || Boolean(node.closest("button") || node.closest(".hit"));
  let pressedOn = null;
  box.addEventListener("pointerdown", (event) => {
    pressedOn = event.target;
  });
  box.addEventListener("click", (event) => {
    const from = pressedOn || event.target;
    pressedOn = null;
    if (onEmpty && !onSomething(from) && !onSomething(event.target)) onEmpty();
  });
  cross.addEventListener("pointerenter", () => clearTimeout(wait));
  cross.addEventListener("pointerleave", unpointSoon);
  cross.addEventListener("click", () => {
    const item = links.get(pointed || picked);
    if (item && !pointer.waits?.()) pointer.onRemove(item.link);
  });

  function node(idOrKey) {
    if (idOrKey.startsWith("count:")) return blocks.get(idOrKey.slice("count:".length))?.count || null;
    return blocks.get(idOrKey)?.node || links.get(idOrKey)?.path || null;
  }

  return { box, area, draw, aimAgain, glance, hold, homeIn, lightTarget, unlightTarget, tip, untip, wire, unwire, drawIn, node };
}
