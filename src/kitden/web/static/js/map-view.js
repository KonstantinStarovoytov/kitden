// The map on a page: HTML blocks over one SVG of links, where map.js lays them out. A view keeps
// one node per block, column caption and link across draws. A block moves by `transform` on one
// frame clock, and every link is drawn again from its two blocks on each frame. A link the page
// acts on takes the pointer: a wide hit stroke, a hover look and a small × on its middle. The page
// gives the hooks; the view knows nothing of servers, tools or clients.
import { button, cutName, el, icon } from "./dom.js";
import { blockLabel, drawPlan, enterDelays, foldable, LINK_MS, linkClass, linkKey, linkPath, midPoint, unfoldDelays } from "./map.js";
import { animateTo, CALM, D, IN3, OUT3 } from "./motion.js";

const SVG = "http://www.w3.org/2000/svg";
const MOVE_MS = 260; // a block that moves, or a new one that fades in at its place
const GO_MS = 180; // a block that goes, or folds back into the block that showed it
const FADE_MS = 120; // a child of an unfold fades in after its link has drawn
const FOLD_SCALE = 0.3; // how small a folded child gets as it goes
const FOLD_IN = 100; // a folded child goes this far left of its opener's right side
const ROOM = 24; // under the lowest block
const ENTER_RISE = 6; // an entering block starts this far below its place
const CAPTION_ICON = 13; // a group caption's icon
const CROSS_MS = 120; // the × fades in
const CROSS_R = 8; // half the × (16 px): it sits with its middle on the link's
const GRACE_MS = 240; // the × stays this long after the pointer leaves, so the pointer can reach it
const HIT_MIN = 0.5; // a link fainter than this takes no pointer
const NO_LINKS = { canHit: () => false }; // a page that acts on no link

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

// Everything a block's words depend on, as one key: they are drawn again only when it changes.
function wordsKey(block, open) {
  return JSON.stringify([block.kind, block.name, block.meta, block.tag, block.count, open, block.action, block.state, block.dot, block.grip]);
}

// A group's caption: its words, with its icon (a lucide name, if it has one) before them.
function captionWords(node, name, mark) {
  if (!mark) node.textContent = name;
  else node.replaceChildren(icon(mark, CAPTION_ICON), el("span", null, name));
}

// A column's caption and a group's caption without Details are words; any other block is a button.
const isWords = (place) => place.kind === "column" || (place.kind === "group" && !place.details);

// Opacity 1 leaves no inline opacity.
function fade(node, o) {
  const value = o >= 1 ? "" : String(Math.max(0, o));
  if (node.style.opacity !== value) node.style.opacity = value;
}

// Where a block shows now: a scaled block shrinks around its centre.
function boxOf({ x, y, w, h, s }) {
  return s === 1 ? { x, y, w, h } : { x: x + (w * (1 - s)) / 2, y: y + (h * (1 - s)) / 2, w: w * s, h: h * s };
}

// One map. `view.box` (div.map) goes where the page wants it and keeps every node when it is taken
// out and put back; `view.area` holds the links' SVG, the blocks in reading order, then the hits of
// the links and the ×.
// - draw(model, layout, { selected, lit, found, open, motion }): show `layout` (map.js layoutTree)
//   of `model`. `motion` "move" moves what changed; "enter" lets every block rise into its place;
//   "none" (and the first draw of a "move", reduced motion or a hidden page) shows the end at
//   once. It resolves when every motion ends.
// - hold(id, point, { glide }): the block shows at that map point until letGo; letGo(id): it
//   glides back to its place.
// - drawIn(key, ms): a link grows from its start. node(idOrKey): a block's node or a link's path.
// A press on a block opens or folds it when it folds (`onOpen(id)`), then selects it
// (`onSelect(id)`); "+ Add" beside a column's caption calls `onAdd(column)`. `tile(block)` gives
// what a block shows before its name.
// `links` are the page's hooks for the links it acts on: `canHit(link)`, `tip(link)` (what its
// × does, in words), `onClick(link)` and `onRemove(link)`. After the blocks the area holds the
// hit of each such link (a button for a keyboard: Enter opens, Delete removes) and one ×.
export function mapView({ tile, onOpen, onSelect, onAdd, links: pointer = NO_LINKS } = {}) {
  const box = el("div", "map");
  const area = el("div", "map-area");
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "map-links");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "100%");
  const hits = document.createElementNS(SVG, "svg");
  hits.setAttribute("class", "map-hits");
  hits.setAttribute("role", "group");
  hits.setAttribute("aria-label", "Connections");
  hits.setAttribute("width", "100%");
  hits.setAttribute("height", "100%");
  const cross = el("button", "link-x");
  cross.type = "button";
  cross.setAttribute("tabindex", "-1");
  cross.hidden = true;
  cross.append(icon("x", 10));
  area.append(svg, hits, cross);
  box.append(area);

  // Each block: its node, where it shows now (x, y, scale s, opacity o), its size, its place in the
  // last layout (`home`), its move, and whether it goes, is held or glides back from a hold.
  const blocks = new Map();
  // Each link: its key, its path, the hit that takes the pointer for it (if the page acts on it),
  // the layout's link, the path drawn, and until when it shows whole while it draws in (`free`).
  const links = new Map();
  let pointed = null; // the key of the link with the hover look and the ×
  let wait = 0; // the timer that ends it
  const moving = new Set(); // the blocks with a move
  const waiting = []; // what waits for every motion to end
  let last = null; // the layout drawn last
  let folds = new Set(); // the blocks that fold, as the last draw read them
  let size = { w: 0, h: 0 }; // the last layout's size
  let shown = null; // the size the area has now
  let queued = false; // a frame is asked for

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

  // A block at (x, y), scaled by s from its centre, at opacity o.
  function put(item, { x, y, s, o }) {
    Object.assign(item, { x, y, s, o });
    item.node.style.transform = `translate(${x}px, ${y}px) scale(${s})`;
    fade(item.node, o);
  }

  // A block's classes: its look from the last draw, and `.dragging` while it is held or glides back.
  function paint(item) {
    const look = item.held || item.back ? `${item.look} dragging` : item.look;
    if (item.node.className !== look) item.node.className = look;
  }

  // A block's node as this draw shows it: its look, words, size and what a screen reader hears.
  function fill(item, place, block, { selected, lit, found, open }) {
    const { node } = item;
    const name = String(block.name || "");
    const matched = Boolean(found && found.matches.has(place.id));
    if (place.kind === "column") {
      item.look = "map-caption";
      const words = JSON.stringify([block.caption, Boolean(block.add)]);
      if (words !== item.words) {
        item.words = words;
        const parts = block.caption ? [el("span", null, block.caption)] : [];
        if (block.add) {
          const add = button("+ Add", () => onAdd && onAdd(block.id), "btn small ghost");
          add.dataset.focus = `add:${block.id}`;
          parts.push(add);
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
      const opened = folding && open.has(place.id);
      item.look = [group ? "caption" : `block ${place.kind}`, place.id === selected && "selected", lit.has(place.id) && "lit", matched && "found"].filter(Boolean).join(" ");
      node.dataset.focus = `block:${place.id}`;
      if (block.state) node.dataset.state = block.state;
      else delete node.dataset.state;
      node.title = name;
      node.setAttribute("aria-label", blockLabel(block));
      const words = group ? JSON.stringify([name, block.icon]) : wordsKey(block, opened);
      if (words !== item.words) {
        item.words = words;
        if (group) captionWords(node, name, block.icon);
        else node.replaceChildren(...blockParts(block, { tile, open: opened }));
      }
      // A block that folds says whether it is open by what is open, not by what shows yet.
      if (folding) node.setAttribute("aria-expanded", String(open.has(place.id)));
      else node.removeAttribute("aria-expanded");
    }
    paint(item);
    if (item.w !== place.w) node.style.width = `${place.w}px`;
    if (item.h !== place.h) node.style.height = `${place.h}px`;
    Object.assign(item, { w: place.w, h: place.h, home: { x: place.x, y: place.y } });
  }

  // A block that is a caption now and a button later (or back) gets a new node in the same place.
  function swap(item, place) {
    const node = makeNode(place.id, isWords(place));
    if (item.node.parentNode) area.insertBefore(node, item.node);
    item.node.remove();
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
    item.path.remove();
    dropHit(item);
    links.delete(key);
  }

  // The hover look and the × go at once.
  function unpoint() {
    clearTimeout(wait);
    const item = pointed && links.get(pointed);
    if (item) item.path.classList.remove("hov");
    pointed = null;
    cross.hidden = true;
  }

  // ... or after the grace, which the clock of the motions does not scale, so a pointer that is
  // on its way to the × always has the time.
  function unpointSoon() {
    clearTimeout(wait);
    wait = setTimeout(unpoint, GRACE_MS);
  }

  // The × on the middle of the link with the hover look. It follows the link; it moves to another
  // link at once, and fades in only when it was hidden.
  function placeCross() {
    const item = pointed && links.get(pointed);
    if (!item || !item.hit || !item.d) return;
    const mid = midPoint(item.d);
    cross.style.transform = `translate(${Math.round(mid.x - CROSS_R)}px, ${Math.round(mid.y - CROSS_R)}px)`;
    if (!cross.hidden) return;
    cross.hidden = false;
    animateTo(cross, [{ opacity: 0 }, { opacity: 1 }], { dur: CROSS_MS, ease: CALM });
  }

  function pointAt(item) {
    clearTimeout(wait);
    if (pointed && pointed !== item.key) links.get(pointed)?.path.classList.remove("hov");
    pointed = item.key;
    item.path.classList.add("hov");
    const tip = pointer.tip(item.link);
    cross.title = tip;
    cross.setAttribute("aria-label", tip);
    placeCross();
  }

  // A press on a link points at it, so its × is there for what comes next.
  function pressLink(item) {
    pointAt(item);
    pointer.onClick(item.link);
  }

  function keyOnHit(event, item) {
    const press = event.key === "Enter" || event.key === " ";
    if (!press && event.key !== "Delete" && event.key !== "Backspace") return;
    event.preventDefault();
    if (press) pressLink(item);
    else pointer.onRemove(item.link);
  }

  // A link's hit: a wide stroke over it, and a button for a keyboard.
  function makeHit(item) {
    const hit = document.createElementNS(SVG, "path");
    hit.setAttribute("class", "hit");
    hit.setAttribute("tabindex", "0");
    hit.setAttribute("role", "button");
    hit.setAttribute("aria-keyshortcuts", "Delete");
    hit.dataset.focus = `link:${item.key}`; // a redraw of the page gives focus back to it
    if (item.d) hit.setAttribute("d", item.d);
    hit.addEventListener("pointerover", () => pointAt(item));
    hit.addEventListener("pointerout", unpointSoon);
    hit.addEventListener("focus", () => pointAt(item));
    hit.addEventListener("blur", unpointSoon);
    hit.addEventListener("click", () => pressLink(item));
    hit.addEventListener("keydown", (event) => keyOnHit(event, item));
    return hit;
  }

  function dropHit(item) {
    if (!item.hit) return;
    if (pointed === item.key) unpoint();
    item.hit.remove();
    item.hit = null;
  }

  // A link has a hit while the page acts on it, named for a screen reader by its two blocks.
  function syncHit(item, names) {
    if (!pointer.canHit(item.link)) {
      dropHit(item);
      return;
    }
    if (!item.hit) item.hit = makeHit(item);
    const said = { "aria-label": `${names.get(item.link.from)} to ${names.get(item.link.to)}`, "aria-description": pointer.tip(item.link) };
    for (const [name, value] of Object.entries(said)) if (item.hit.getAttribute(name) !== value) item.hit.setAttribute(name, value);
  }

  // A block that went: its node and its links leave the page.
  function drop(item) {
    if (blocks.get(item.id) !== item) return;
    stop(item);
    blocks.delete(item.id);
    item.node.remove();
    for (const [key, link] of links) if (link.link.from === item.id || link.link.to === item.id) unlink(key);
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
        item.d = d;
      }
      const o = now < item.free ? 1 : Math.min(a.o, b.o);
      fade(item.path, o);
      // A link that fades away takes no pointer.
      if (!item.hit) continue;
      const display = o < HIT_MIN ? "none" : "";
      if (item.hit.style.display !== display) item.hit.style.display = display;
      if (display && pointed === item.key) unpoint();
    }
    placeCross();
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
    requestAnimationFrame(() => {
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
    const at = new Map([...area.children].map((node, i) => [node, i]));
    const nodes = layout.blocks.map((place) => blocks.get(place.id).node);
    if (nodes.every((node, i) => i === 0 || at.get(nodes[i - 1]) < at.get(node))) return;
    const focused = document.activeElement;
    for (const node of nodes) area.insertBefore(node, hits);
    if (focused && focused !== document.activeElement && area.contains(focused)) focused.focus({ preventScroll: true });
  }

  function draw(model, layout, { selected = null, lit = new Set(), found = null, open = new Set(), motion = "move" } = {}) {
    performance.mark("kitden:map-start");
    const enters = motion === "enter" && canMove();
    const moves = enters || (motion === "move" && last !== null && canMove());
    const plan = drawPlan(last, layout);
    const before = new Map((last ? last.blocks : []).map((at) => [at.id, at]));
    const after = new Map(layout.blocks.map((at) => [at.id, at]));
    const byId = new Map(model.blocks.map((block) => [block.id, block]));
    const columns = new Map(model.columns.map((column) => [column.id, column]));
    const start = performance.now();
    folds = foldable(model);
    const unfold = new Map(plan.unfold.map((id, i) => [id, i]));
    const delays = unfoldDelays(plan.unfold.length);
    const waves = enterDelays(layout.blocks.length); // when each block of an entrance starts
    const opened = new Set(); // new blocks of an unfold: their links draw in first

    for (const [at, place] of layout.blocks.entries()) {
      const block = place.kind === "column" ? columns.get(place.column) : byId.get(place.id) || place;
      let item = blocks.get(place.id);
      const fresh = !item;
      if (fresh) {
        item = { id: place.id, node: makeNode(place.id, isWords(place)), div: isWords(place), x: place.x, y: place.y, s: 1, o: 1, w: 0, h: 0, move: null, leaving: false, held: false, back: false, look: "", words: null };
        blocks.set(place.id, item);
      } else if (item.div !== isWords(place)) swap(item, place);
      item.leaving = false;
      fill(item, place, block, { selected, lit, found, open });
      const end = { x: place.x, y: place.y, s: 1, o: 1 };
      if (item.held) continue;
      if (!moves) {
        stop(item);
        put(item, end);
      } else if (enters) {
        // The entrance: it waits below its place, unseen, then rises in its turn.
        put(item, { ...end, y: end.y + ENTER_RISE, o: 0 });
        go(item, end, { dur: D(MOVE_MS), ease: OUT3, start: start + D(waves[at]) });
      } else if (fresh && unfold.has(place.id)) {
        // An unfold: it waits at its place while its links draw, then fades in.
        opened.add(place.id);
        put(item, { ...end, o: 0 });
        go(item, end, { dur: D(FADE_MS), ease: OUT3, start: start + D(delays[unfold.get(place.id)]) });
      } else {
        if (fresh) put(item, { ...end, o: 0 });
        go(item, end, { dur: D(MOVE_MS), ease: OUT3, start });
      }
    }

    for (const id of plan.leave) {
      const item = blocks.get(id);
      if (!item) continue;
      Object.assign(item, { leaving: true, held: false, back: false });
      paint(item);
      if (!moves) {
        drop(item);
        continue;
      }
      // A child of a fold shrinks back into its opener's right side; anything else fades in place.
      const opener = plan.fold.includes(id) ? after.get(before.get(id).opener) : null;
      const to = opener ? { x: opener.x + opener.w - FOLD_IN, y: opener.y + opener.h / 2 - item.h / 2, s: FOLD_SCALE, o: 0 } : { x: item.x, y: item.y, s: item.s, o: 0 };
      go(item, to, { dur: D(GO_MS), ease: IN3, start, then: drop });
    }

    const drawsIn = [];
    const names = new Map(model.blocks.map((block) => [block.id, String(block.name || "")]));
    for (const link of layout.links) {
      const key = linkKey(link);
      let item = links.get(key);
      if (!item) {
        item = { key, path: document.createElementNS(SVG, "path"), hit: null, link, d: "", look: "", free: 0, drawing: 0 };
        svg.append(item.path);
        links.set(key, item);
        if (opened.has(link.to) && before.has(link.from)) drawsIn.push([key, start + D(delays[unfold.get(link.to)] + FADE_MS)]);
      }
      item.link = link;
      const look = `${linkClass(link)}${lit.has(key) ? " lit" : ""}`;
      if (look !== item.look) {
        item.path.setAttribute("class", look);
        item.path.classList.toggle("hov", key === pointed);
      }
      item.look = look;
      syncHit(item, names);
    }
    const shownLinks = new Set(layout.links.map(linkKey));
    for (const [key, item] of links) {
      if (shownLinks.has(key)) continue;
      // A link to a block that goes stays while it goes, and fades with it.
      const goes = [item.link.from, item.link.to].some((id) => blocks.get(id)?.leaving && blocks.get(id).move);
      if (goes) item.free = 0;
      else unlink(key);
    }
    // The hits keep the order of the links, so Tab does.
    let next = null;
    for (const link of [...layout.links].reverse()) {
      const { hit } = links.get(linkKey(link));
      if (!hit) continue;
      if (!hit.parentNode) hits.insertBefore(hit, next);
      next = hit;
    }
    // Lit links are drawn last, over the others.
    const litPaths = layout.links.filter((link) => lit.has(linkKey(link))).map((link) => links.get(linkKey(link)).path);
    const paths = [...svg.children];
    if (litPaths.some((path, i) => paths[paths.length - litPaths.length + i] !== path)) svg.append(...litPaths);

    order(layout);
    box.classList.toggle("narrow", Boolean(layout.narrow));
    box.classList.toggle("finding", Boolean(found));
    size = { w: layout.columns.reduce((most, column) => Math.max(most, column.x + column.w), 0), h: layout.height + ROOM };
    last = layout;
    for (const [key, until] of drawsIn) {
      drawIn(key, LINK_MS);
      links.get(key).free = until;
    }
    fit(moves);
    const done = run(!moves);
    performance.mark("kitden:map-drawn");
    performance.measure("kitden:map-draw", "kitden:map-start", "kitden:map-drawn");
    return done;
  }

  // Show a block at (x, y) of the map, at once or gliding there, until letGo: draws leave it
  // there, and its links follow it.
  function hold(id, { x, y }, { glide = false } = {}) {
    const item = blocks.get(id);
    if (!item || item.leaving) return Promise.resolve();
    Object.assign(item, { held: true, back: false });
    paint(item);
    const to = { x, y, s: 1, o: 1 };
    if (glide && canMove()) go(item, to, { dur: D(MOVE_MS), ease: OUT3, start: performance.now() });
    else {
      stop(item);
      put(item, to);
    }
    return run(!canMove());
  }

  // A held block glides from where it is to its place, and loses `.dragging` when it lands.
  function letGo(id) {
    const item = blocks.get(id);
    if (!item || item.leaving) return Promise.resolve();
    item.held = false;
    go(item, { ...item.home, s: 1, o: 1 }, { dur: D(MOVE_MS), ease: OUT3, start: performance.now() });
    item.back = Boolean(item.move);
    paint(item);
    return run(!canMove());
  }

  // A link grows from its start. It shows whole while it draws; its own dashes come back when it
  // ends, by time.
  function drawIn(key, ms = 260) {
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

  cross.addEventListener("pointerenter", () => clearTimeout(wait));
  cross.addEventListener("pointerleave", unpointSoon);
  cross.addEventListener("click", () => {
    const item = pointed && links.get(pointed);
    if (item) pointer.onRemove(item.link);
  });

  function node(idOrKey) {
    return blocks.get(idOrKey)?.node || links.get(idOrKey)?.path || null;
  }

  return { box, area, draw, hold, letGo, drawIn, node };
}
