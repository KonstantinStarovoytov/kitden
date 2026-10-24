# Alignment Phase 2: Map engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The map keeps its blocks and links between draws and moves them the way the mockup does: blocks glide, unfold and fold, the page enters, links take the pointer, links draw, blend, fade and undraw, and a selection dims the rest.

**Architecture:** `map.js` stays pure (layout, paths, lighting, find, the draw plan) and is tested in node with no DOM. A new `map-view.js` holds the one renderer, `mapView(options)`: it keeps one node per block, caption and link, moves blocks by `transform` on one frame clock, and recomputes link paths from the blocks every frame. The page gives hooks (open, select, empty click, hover, and for links: can act, tip, click, remove); the engine has no Gateway logic. `gateway.js` keeps one view per visit and re-attaches the same box on every page render. Library (Phase 6) uses the same `mapView` and `layoutTree`.

**Tech Stack:** plain ES modules, one CSS file, Web Animations for strokes and fades, `requestAnimationFrame` for block moves, node's test runner with a fake DOM, pytest page-word pins.

**Spec:** `docs/superpowers/plans/2026-10-24-mockup-alignment.md` Phase 2 (and its "Carried from Phase 1"), decisions D8, D9, D28; the mockup `docs/mockup/kitden-motion.html` (`MapView`: `place`, `move`, `link`, `drawLink`, `draw`, `drawIn`, `unlink`, `dash`, `undraw`, `focus`, `unfocus`, `lit`, `pick`, `showX`, `hoverLink`, `unhoverSoon`; Gateway `layout`, `relayout`, `enter`, `origin`, `hover`; CSS lines 108–172 and 315–380); `docs/mockup/motion-spec.md` M0–M3; spec `docs/superpowers/specs/2026-10-23-map-pages-design.md` "Owner decisions (2026-10-24, the mockup)".

## Global Constraints

- Everything in the master plan's Global Constraints (AGENTS.md, CSP, Calm only, reduced motion, docs and word pins with the code, the four checks before each commit).
- `map.js` has no `document`, no timers and no frames. Everything that touches the DOM, a timer or a frame lives in `map-view.js`.
- The engine knows only the generic kinds `"group"`, `"column"` and `"more"` and the link kinds `"on"`, `"faint"`, `"direct"`, `"preview"`. Anything about servers, tools, clients or the gateway is the page's, through hooks.
- Calm values (ms): move 260 OUT3 · new block in place 260 OUT3 (opacity) · block leaves 180 IN3 · unfold: links draw 170 CALM, then children fade 120 OUT3, 15 apart, no cap (D9) · fold: children go to (opener right − 100, opener middle − h/2), scale .3, opacity 0, 180 IN3 · entrance: from y + 6, opacity 0, 260 OUT3, 22 apart in layout order · head: 260 CALM, 6 px, at 0 / 120 / 180 · × in 120 CALM · hover grace 240 · new solid link draws 260 CALM · new dashed link fades in 300 CALM · dashed link out 240 ease-out · solid link out (undraw) 380 RETRACT · dash blend 300 CALM, a solid line read as "8 0" · overlay in 180 CALM, out 160 ease-in · dims 300 ease · link hover look: stroke and width 220, stroke-opacity 300, ease.
- Every time goes through `D(ms)`, except the 240 ms grace (not scaled, and it runs under reduced motion too). Under reduced motion, or while `document.hidden`, every motion lands at once.
- The engine owns `transform` and inline `opacity` of map blocks and links. At rest no block or link keeps an inline opacity (`style.opacity === ""`). CSS looks never set `opacity` or `transform` on them: dims use `filter: opacity()` and `stroke-opacity`, a press uses `scale`.
- Kitden's names stay: `.block`, `.caption`, `.map-caption`, `.link`, `.selected`, `.lit`, `.found`, `.finding`, `.narrow`, `data-focus="block:<id>"`. New: `.map-hits`, `.hit`, `.link-x`, `.link-over`, `.focus`, `.hov`, `.picked`, `.leaving`.
- Map CSS stays in the `/* Map (map.js)` block with every rule starting `div.map` (`test_the_map_rules_never_reach_the_library_table`). A rule that starts `html.`, `.grabbing` or `.page` goes outside that block.
- Removed timers wait by time (`setTimeout(…, D(ms))`), never on `animationend` or `.finished` (design.md Conventions).
- `git add` names each file. Never `git stash`. Never stage `design/` or `docs/research/*`. If `ROADMAP.md` holds changes you did not make, do not stage it; Task 7 hands the owner the line.

## Review Focus

- Reduced motion: every draw, the entrance, an unfold, a fold, a hold, a link that comes or goes lands at once; no `animate()` runs and nothing is left at opacity 0. Tests in Tasks 1, 2 and 5.
- A draw that starts while another still moves (a double click on a server, a live rescan during the entrance, a search key during an unfold): the newest layout wins, one node per id, nothing left half-way. Test in Task 1.
- A page render (live rescan, `setState`, the review bar's redraw) re-attaches the same map: a block with keyboard focus keeps it, and no listener is added twice. Test in Task 1 (focus); Task 7 checks the rest by hand.
- A hidden tab (a live rescan in the background): frames do not run, so every motion jumps to its end at once instead of waiting half-way. Test in Task 1.
- Today's drag of an outside server: the block follows the pointer with its links, a drop on Servers parks it on the slot, Escape or a drop elsewhere glides it home, and no hold, spinner or `.dragging` is left after. Test in Task 1 (`hold`, `letGo`); Task 7 checks the drag by hand.

## Out of Phase 2

- Tray rows, Apply all, a click on a preview block taking it out (Phase 3). A preview block still opens its review.
- The Connection panel and the floating Details (Phase 4.3). In Phase 2 a link click opens the Details of its far block.
- A × on client → gateway (Disconnect, Phase 4.4) and on a bypass link (removal per client, Phase 4). Phase 2 wires × only where today's actions exist: a server out of the Kitden gateway, a tool off.
- Block looks: icons, lamps, ports, badge, house and stats, tool marks, grip block, preview and leaving block looks (Phase 4.1). Server specifics of unfold: badge out, right port in, a click on an open server whose tool is selected (Phase 4.2). Origins for a server that enters from or leaves into the gateway, an outside server that leaves 24 px left (Phase 4).
- Drags 2–4, drop-target looks, the 220 ms way home (Phase 4.7). Find's new look, Map ↔ List motion, the project switch in place (Phase 4.8). Words (D7) and the one-line outside caption (Phase 4.1). Hint line text (Phase 4).
- Rich mode, beams, ripples, marching dashes (D28): never.

---

### Task 1: Blocks and links that stay (master 2.1)

**Files:**
- Create: `src/kitden/web/static/js/map-view.js`, `tests/frontend/map-view.test.mjs`
- Modify: `src/kitden/web/static/js/map.js` (column caption blocks, `opener`, link `shape`, new pure helpers; `drawMap`, `blockNode`, `blockParts`, `quiet` and `appeared` leave), `src/kitden/web/static/js/motion.js` (`animateTo`), `src/kitden/web/static/js/gateway.js`, `src/kitden/web/static/js/gateway-drag.js`, `src/kitden/web/static/js/app.js` (render argument), `src/kitden/web/static/style.css` (map block)
- Modify: `tests/frontend/map.test.mjs`, `tests/frontend/motion.test.mjs`, `tests/unit/test_page_words.py`, `docs/design.md`

**Interfaces:**
- Produces in `map.js`:
  - `CAPTION_H = 18`, `CAPTION_ROW = 24` (blocks start under the captions), `LINK_MS = 170`.
  - `layoutTree(model, opts)` as today, plus: a caption block `{ id: "column:<id>", kind: "column", column, x, y: 0, w, h: CAPTION_H }` first in each column that has a `caption` and shows a block (narrow: only columns that take room); blocks start at `CAPTION_ROW`; a block shown by an open block in another column (wide) or on a rail (narrow) carries `opener: <that block's id>`, and so does the caption of a column whose blocks are all such; every link carries `shape` (`"curve"`, `"step"` for `direct`, `"rail"`), and `d`.
  - `linkKey(link) → "from>to"`; `linkClass(link) → "link <kind>[ unk]"`; `linkPath(link, from, to) → string` (`from`, `to`: `{ x, y, w, h }`; today's three shapes, same numbers).
  - `drawPlan(before, after) → { enter, stay, leave, unfold, fold, linksIn, linksStay, linksOut }`: ids and link keys in layout order (`leave` and `linksOut` in `before`'s order); `before` null → everything enters; `unfold` ⊂ `enter` (an `opener` that was shown before), `fold` ⊂ `leave` (an `opener` still shown after).
  - `unfoldDelays(count, reduced = false)`: `170 + i * 15`, no cap; all 0 when reduced.
  - `blockOrder(layout)` leaves out `"column"` blocks too.
- Produces in `map-view.js`: `export function mapView({ tile, onOpen, onSelect, onAdd } = {})` → `view`:
  - `view.box` (`div.map`, made once) and `view.area` (`div.map-area`): the area holds one `svg.map-links` (aria-hidden, no pointer), then the block and caption nodes in layout order. The page appends `view.box` where it wants; taken out and put back, it keeps every node.
  - `view.draw(model, layout, { selected = null, lit = new Set(), found = null, open = new Set(), motion = "move" }) → Promise<void>` (resolves when every motion ends). `motion`: `"move"` (the paths below) or `"none"` (everything at its end at once). With no earlier draw, `"move"` acts as `"none"`.
  - `view.hold(id, { x, y }, { glide = false } = {}) → Promise<void>`: the block shows at that map point (at once, or 260 OUT3 with `glide`), gets `.dragging`, and draws keep it there until `letGo`; its links follow.
  - `view.letGo(id) → Promise<void>`: the block glides from where it is to its layout place, 260 OUT3, and loses `.dragging`. An id not on the map does nothing.
  - `view.drawIn(key, ms = 260) → Promise<void>`: the link grows from its start (`pathLength="1"`, `stroke-dasharray: 1`, `stroke-dashoffset` 1 → 0, CALM); `pathLength` and the inline dash go when it ends (by time).
  - `view.node(idOrKey) → Element | null`: a block's node, or a link's path for a `"from>to"` key.
- Produces in `motion.js`: `animateTo` resolves at once and logs with `console.error` when `node.animate()` throws or `.finished` rejects with anything but an `AbortError`; a cancelled animation stays silent.
- Produces in `app.js`: `place.render(main, { again })`, `again` true when the same place draws again.
- Produces in `gateway.js`: `renderGateway(main, { again = false } = {})`. In `gateway-drag.js`: `placeMoved({ view, model, layout, redraw })`.

- [ ] **Step 1: Write the failing tests**

`tests/frontend/map-view.test.mjs` starts with a fake DOM in the file, in the style of the other frontend tests. It needs: elements from `createElement` and `createElementNS` with `tagName`, `className` kept in step with `classList` (`add`, `remove`, `toggle(name, force)`, `contains`), `style` (a plain object), `dataset`, `setAttribute` / `getAttribute` / `removeAttribute`, `children`, `parentNode`, `append`, `prepend`, `insertBefore`, `remove`, `replaceChildren`, `firstElementChild`, `lastElementChild`, `textContent`, `focus()` (sets `document.activeElement`, fires `focus`), `blur()`, `closest(tag or .class)`, `addEventListener`, a `dispatch(type, init)` that bubbles to parents, and `animate(keyframes, options)` that pushes `{ keyframes, options }` to `node.animations` and returns `{ finished: Promise.resolve(), cancel() {} }`. `requestAnimationFrame` queues; `performance.now()` returns `now`, which starts at 0 in each test; a motion starts at the `now` of its call; `tick(ms)` adds `ms` to `now` and runs the queued frames once; `settle()` ticks 10 s at a time until no frame is queued. `reduce(flag)` flips the shared `matchMedia` result. A `walk(root)` helper lists every node under a root; `near(a, b)` is `Math.abs(a - b) < 1e-6`. Inline opacity is written as `String(o)`.

```js
const TREE = {
  columns: [{ id: 'a', caption: 'A', w: 150, h: 54 }, { id: 'b', caption: 'B', w: 170, h: 60 }, { id: 'c', caption: 'C', w: 200, h: 34 }],
  blocks: [
    { id: 'c1', column: 'a', kind: 'client', name: 'Codex', state: 'on' },
    { id: 's1', column: 'b', kind: 'held', name: 'github', state: 'on', count: 2 },
    { id: 's2', column: 'b', kind: 'held', name: 'files', state: 'on', count: 0 },
    { id: 't1', column: 'c', parent: 's1', kind: 'tool', name: 'read', state: 'on' },
    { id: 't2', column: 'c', parent: 's1', kind: 'tool', name: 'push', state: 'on' },
  ],
  links: [{ from: 'c1', to: 's1', kind: 'on' }, { from: 'c1', to: 's2', kind: 'on' }, { from: 's1', to: 't1', kind: 'on' }, { from: 's1', to: 't2', kind: 'on' }],
};
const lay = (open = [], narrow = false) => layoutTree(TREE, { open: new Set(open), narrow });
const view = (hooks = {}) => mapView({ tile: () => null, onOpen() {}, onSelect() {}, ...hooks });
const pos = (n) => { const m = n.style.transform.match(/translate\(([-\d.]+)px, ([-\d.]+)px\) scale\(([-\d.]+)\)/); return { x: +m[1], y: +m[2], s: +m[3] }; };
const place = (layout, id) => layout.blocks.find((b) => b.id === id);
const without = (id) => ({ ...TREE, blocks: TREE.blocks.filter((b) => b.id !== id), links: TREE.links.filter((l) => l.to !== id) });

test('drawing twice keeps the same node for every block and link that stays', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), {});
  const [s1, link] = [v.node('s1'), v.node('c1>s1')];
  await v.draw(TREE, lay(), { selected: 's1' });
  assert.equal(v.node('s1'), s1);
  assert.equal(v.node('c1>s1'), link);
  assert.ok(s1.classList.contains('selected'));
});

test('a block sits where the layout says, by transform only', async () => {
  reduce(true);
  const v = view(); const layout = lay();
  await v.draw(TREE, layout, {});
  const at = place(layout, 's2');
  assert.equal(v.node('s2').style.transform, `translate(${at.x}px, ${at.y}px) scale(1)`);
  assert.equal(v.node('s2').style.left, undefined);
});

test('a block that moves glides 260 ms with OUT3', async () => {
  const v = view();
  await v.draw(TREE, lay([], true), { motion: 'none' });
  const from = pos(v.node('s2')).y; const to = place(lay(['s1'], true), 's2').y;
  v.draw(TREE, lay(['s1'], true), {});
  tick(130); assert.ok(near(pos(v.node('s2')).y, from + (to - from) * 0.875));
  tick(130); assert.equal(pos(v.node('s2')).y, to);
});

test('a block that goes fades out in 180 ms with IN3, then its node is gone', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  const node = v.node('s2');
  v.draw(without('s2'), layoutTree(without('s2'), { open: new Set(), narrow: false }), {});
  tick(90); assert.equal(node.style.opacity, '0.875');
  assert.equal(v.node('c1>s2').style.opacity, '0.875');  // a link fades with the fainter of its blocks
  tick(90); assert.equal(v.node('s2'), null); assert.equal(node.parentNode, null);
});

test('an opened block: its links draw in 170 ms, then its column caption and children fade in, 15 ms apart', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(TREE, lay(['s1']), {});
  const draw = v.node('s1>t1').animations[0];
  assert.deepEqual(draw.keyframes, [{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }]);
  assert.deepEqual([draw.options.duration, draw.options.easing], [170, CALM]);
  tick(170); assert.equal(v.node('column:c').style.opacity, '0');
  tick(75); assert.equal(v.node('t1').style.opacity, '0.875');  // 60 ms into its fade, which starts at 185
  tick(75); assert.equal(v.node('t2').style.opacity, '');       // 200 + 120
});

test("a folded block's children shrink toward its right side in 180 ms, then go", async () => {
  const v = view();
  await v.draw(TREE, lay(['s1']), { motion: 'none' });
  const t1 = v.node('t1');
  v.draw(TREE, lay(), {});
  tick(90); assert.ok(near(pos(t1).s, 0.9125)); assert.equal(t1.style.opacity, '0.875');
  tick(90); assert.equal(v.node('t1'), null);
});

test('a link is drawn again from its blocks every frame', async () => {
  const v = view();
  await v.draw(TREE, lay([], true), { motion: 'none' });
  const layout = lay(['s1'], true);
  v.draw(TREE, layout, {});
  tick(130);
  const box = (id) => ({ ...pos(v.node(id)), w: parseFloat(v.node(id).style.width), h: parseFloat(v.node(id).style.height) });
  const link = layout.links.find((l) => linkKey(l) === 'c1>s2');
  assert.equal(v.node('c1>s2').getAttribute('d'), linkPath(link, box('c1'), box('s2')));
});

test('at rest no block or link keeps an inline opacity', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(TREE, lay(['s1']), {}); settle(); await v.draw(TREE, lay(['s1']), {});
  for (const n of walk(v.area)) assert.equal(n.style?.opacity ?? '', '');
});

test('block nodes keep the reading order in the DOM, so Tab follows it', async () => {
  reduce(true);
  const v = view(); const layout = lay(['s1']);
  await v.draw(TREE, lay(), {}); await v.draw(TREE, layout, {});
  const order = v.area.children.filter((n) => n.dataset?.focus).map((n) => n.dataset.focus.slice('block:'.length));
  assert.deepEqual(order, blockOrder(layout));
});

test("a block's words are drawn again only when they change", async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), {});
  const words = v.node('s1').firstElementChild;
  await v.draw(TREE, lay(), { selected: 's1' });
  assert.equal(v.node('s1').firstElementChild, words);
  const renamed = { ...TREE, blocks: TREE.blocks.map((b) => (b.id === 's1' ? { ...b, meta: '1 of 2 on' } : b)) };
  await v.draw(renamed, layoutTree(renamed, { open: new Set(), narrow: false }), {});
  assert.notEqual(v.node('s1').firstElementChild, words);
});

test('a held block stays where it is put across draws, and glides home when let go', async () => {
  const v = view();
  await v.draw(TREE, lay([], true), { motion: 'none' });
  v.hold('s2', { x: 500, y: 300 });
  assert.deepEqual(pos(v.node('s2')), { x: 500, y: 300, s: 1 });
  assert.ok(v.node('s2').classList.contains('dragging'));
  v.draw(TREE, lay(['s1'], true), {}); settle();
  assert.deepEqual(pos(v.node('s2')), { x: 500, y: 300, s: 1 });
  v.letGo('s2'); tick(260);
  assert.equal(pos(v.node('s2')).y, place(lay(['s1'], true), 's2').y);
  assert.ok(!v.node('s2').classList.contains('dragging'));
});

// Review Focus
test('a draw during a move ends at the newer layout, one node per id', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(TREE, lay(['s1']), {}); tick(50);
  v.draw(TREE, lay(), {}); tick(10);
  v.draw(TREE, lay(['s1']), {}); settle();
  const ids = v.area.children.map((n) => n.dataset?.focus).filter(Boolean);
  assert.equal(new Set(ids).size, ids.length);
  assert.equal(v.node('t1').style.opacity, '');
  assert.deepEqual(pos(v.node('t1')), { x: place(lay(['s1']), 't1').x, y: place(lay(['s1']), 't1').y, s: 1 });
});

test('under reduced motion every block and link is at its end at once', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), {});
  await v.draw(TREE, lay(['s1']), {});
  assert.equal(v.node('t1').style.opacity, '');
  assert.ok(walk(v.area).every((n) => !n.animations?.length));
  await v.draw(TREE, lay(), {});
  assert.equal(v.node('t1'), null);
});

test('a hidden page jumps every motion to its end', async () => {
  document.hidden = true;
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  await v.draw(TREE, lay(['s1']), {});  // resolves with no frame run
  assert.equal(v.node('t1').style.opacity, '');
  document.hidden = false;
});

test('a block with keyboard focus keeps it through a draw that moves it', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay([], true), {});
  v.node('s2').focus();
  await v.draw(TREE, lay(['s1'], true), {});
  assert.equal(document.activeElement, v.node('s2'));
});
```

In `tests/frontend/map.test.mjs`: replace the `appeared` test and the `unfoldDelays` test; add:

```js
test('column captions are blocks at the top of their column; Tools only while a server is open', () => {
  const l = layoutTree(model(3, 0), { open: new Set(), ...WIDE });
  const caps = l.blocks.filter((b) => b.kind === 'column');
  assert.deepEqual(caps.map((b) => b.id), ['column:clients', 'column:gateway', 'column:servers']);
  assert.ok(caps.every((b) => b.y === 0 && b.h === CAPTION_H));
  const open = layoutTree(model(3, 0, { open: 'github' }), { open: new Set(['held:kitden:github']), ...WIDE });
  assert.equal(open.blocks.find((b) => b.id === 'column:tools').opener, 'held:kitden:github');
  assert.equal(open.blocks.find((b) => b.id === 'tool:github/read_repo').opener, 'held:kitden:github');
  assert.equal(open.links.find((k) => k.kind === 'on').shape, 'curve');
});

test('the draw plan says what enters, stays and leaves, and what an unfold or a fold moves', () => {
  const m = model(3, 0, { open: 'github' });
  const [closed, open] = [new Set(), new Set(['held:kitden:github'])].map((o) => layoutTree(m, { open: o, ...WIDE }));
  const tools = ['column:tools', 'tool:github/read_repo', 'tool:github/push_files', 'tool:github/create_issue', 'tool:github/list_prs'];
  const p = drawPlan(closed, open);
  assert.deepEqual(p.enter, tools); assert.deepEqual(p.unfold, tools); assert.deepEqual(p.leave, []);
  assert.ok(p.stay.includes('held:kitden:github'));
  assert.equal(p.linksIn.length, 3);  // push_files is off: no link
  assert.deepEqual(drawPlan(open, closed).fold, tools);
  assert.deepEqual(drawPlan(null, closed).enter, closed.blocks.map((b) => b.id));
  assert.deepEqual(drawPlan(null, closed).unfold, []);
});

test('unfold: links draw for 170 ms, then children start 15 ms apart with no cap; reduced motion starts all at once', () => {
  const d = unfoldDelays(12);
  assert.equal(d[0], 170); assert.equal(d[1] - d[0], 15); assert.equal(d[11], 170 + 11 * 15);
  assert.ok(unfoldDelays(12, true).every((t) => t === 0));
});

test('an unknown direct link is dashed by its class', () => {
  assert.equal(linkClass({ from: 'a', to: 'b', kind: 'direct', unk: true }), 'link direct unk');
  assert.equal(linkClass({ from: 'a', to: 'b', kind: 'on' }), 'link on');
  assert.equal(linkKey({ from: 'a', to: 'b' }), 'a>b');
});
```

`every block is a button in reading order` keeps its assertions (columns are not buttons). In `tests/frontend/motion.test.mjs`:

```js
test('animateTo reports a throwing animate() and still resolves', async () => {
  const logged = []; const error = console.error; console.error = (e) => logged.push(e);
  try {
    await animateTo({ animate() { throw new TypeError('bad keyframes'); } }, [{ opacity: 0 }, { opacity: 1 }]);
    assert.equal(logged.length, 1); assert.equal(logged[0].name, 'TypeError');
  } finally { console.error = error; }
});
```

and `animateTo resolves when the animation is cancelled` rejects with `Object.assign(new Error('cancelled'), { name: 'AbortError' })` and asserts nothing was logged.

- [ ] **Step 2:** `node --test tests/frontend/map-view.test.mjs tests/frontend/map.test.mjs tests/frontend/motion.test.mjs` → FAIL (no `map-view.js`, no `drawPlan`).

- [ ] **Step 3: Implement the pure parts in `map.js`** (signatures above). `linkPath` keeps today's `curve`, `elbow` (now `"step"`) and `railPath` output exactly; `layoutTree` builds every `d` with it. `blockLabel`, `STATE_SAID`, `foldable` and the lighting and find helpers stay here.

- [ ] **Step 4: Implement `mapView` in `map-view.js`.** One `draw`:
  - box classes `narrow` and `finding`; the area's size is the layout's width and `height + 24`, the larger of old and new while blocks move, the new one when they end;
  - blocks from `drawPlan(lastLayout, layout)`: a staying node gets its classes, attributes, size and target (content rebuilt only when a key of what it shows changes: name, meta, tag, count and open, action, state, dot, grip); an entering node is inserted before the next staying node in layout order, else after the last block node (staying nodes never move in the DOM); a leaving node keeps its id until removed, so a newer draw reuses it;
  - paths for `"move"`: a staying block whose target differs glides 260 OUT3 (one at its target does not move); `unfold` blocks wait at their place at opacity 0 while their links draw in 170 (`drawIn`), then fade in 120 OUT3 with `unfoldDelays`; any other new block fades in at its place 260 OUT3; `fold` blocks go to (opener right − 100, opener middle − h/2), scale .3, opacity 0, 180 IN3, then are removed; any other leaving block fades out in place 180 IN3, then is removed; links between staying blocks come and go at once (Task 5 gives them motion); a link's opacity is the lower of its two blocks', except while it draws in;
  - one frame clock per `draw` (`requestAnimationFrame`, start at `performance.now()`), each block with its own eased progress k for x, y and scale, opacity with `min(1, k)`; a newer move of a node replaces the older one; each frame writes `transform: translate(Xpx, Ypx) scale(S)` and inline opacity (cleared at 1) and redraws every link `d` with `linkPath` from the blocks' boxes now (a scaled block's box shrinks around its centre); `D(total) === 0` or `document.hidden` runs the last frame at once;
  - the block node is today's (`button.block <kind>` with `blockParts`, `div.caption` or `button.caption`, the `div.map-caption` with "+ Add" when `column.add`), with `data-focus`, `aria-label` (`blockLabel`), `aria-expanded` from `open`, `.selected`, `.lit` and `.found`; one click listener per node calls `onOpen(id)` for a block that folds, then `onSelect(id)`;
  - `performance.mark("kitden:map-start")`, `"kitden:map-drawn"` and the measure stay, in `draw`.

- [ ] **Step 5: Narrow `animateTo`** (Interfaces). It must never throw or hang a caller.

- [ ] **Step 6: Wire the Gateway.**
  - `app.js`: `found = place.render(main, { again: samePlace })`.
  - `gateway.js`: `onMap.view` is one `mapView({ tile, onOpen, onSelect })` per visit. `renderGateway` sets it to null when `again` is false or the List shows; `gatewayMap` makes one when it is null and then adds the box's Escape `keydown`, the `pointerdown` → `pressGrip` and the ResizeObserver once; every render appends `onMap.view.box` to `main`. `drawOnMap` draws with `motion: "move"`, or `"none"` when the view is new, the project changed or the narrow flag flipped (Task 2 adds the entrance). `appeared`, `onMap.drawn` and `onMap.seeded` go. `drawAgain` draws in place; focus stays on its node.
  - `gateway-drag.js`: `mapArea()` is `onMap.view.area`; `lift` and `follow` call `view.hold(id, point)`; `park` calls `view.hold(id, slot, { glide: true })` and adds the late spinner and `aria-busy` once (only if the node has none); `goHome` calls `view.letGo(id)` and removes the spinner and `aria-busy`; `onMap.home` holds the id; `glideFrom` and every read of `style.left` / `style.top` go.

- [ ] **Step 7: CSS.** `div.map .block`, `div.map .caption`, `div.map .map-caption`: `position: absolute; left: 0; top: 0; z-index: 1; transform-origin: center; will-change: transform`. `.block`'s transition loses `transform` and gains `filter 300ms ease` and `scale 260ms var(--spring)`; `.block:active` is `scale: 0.98`. `div.map .map-links { position: absolute; inset: 0; z-index: 0; overflow: visible; pointer-events: none; }`. `.dragging` gets `z-index: 3`. `.map-head`, `.appear`, `.link.draw`, `@keyframes wire-draw` and `@keyframes block-in` go. Find dims become `div.map.finding .block:not(.found), div.map.finding .caption:not(.found) { filter: opacity(0.35); }` and `div.map.finding .link { stroke-opacity: 0.25; }`; `div.map .link.faint` and `.direct` use `stroke-opacity`, not `opacity`.

- [ ] **Step 8:** Run the three node files → PASS; `node --test tests/frontend/*.test.mjs` → PASS (gateway tests keep passing on the same pure helpers).

- [ ] **Step 9: Pins and docs.** In `tests/unit/test_page_words.py`: `"kitden:map-drawn"` and `setAttribute("aria-expanded", String(open.has(` are read from `map-view.js`; the `${link.unk ? " unk" : ""}` pin goes (the `linkClass` node test holds it); `test_gateway_wires_do_not_fake_traffic` also reads `map-view.js`; the find pins read the new `filter: opacity(0.35)` and `stroke-opacity: 0.25` rules. In `docs/design.md` Motion: Principle 6 adds "a map link redrawn as its blocks move" to its exceptions; Patterns replaces the "Unfold" and "Link" rows with one "Map draw" row (`mapView().draw` in map-view.js: nodes stay; a block that moves glides 260 ms OUT3, a new one fades in at its place in 260 ms, one that goes fades out in 180 ms IN3; an opened block's links draw in 170 ms, then its children fade in 120 ms, 15 ms apart; a folded block's children shrink back to its right side in 180 ms; links follow their blocks every frame; a new project or width shows the map at once; reduced motion and a hidden page land at once); "Map preview" says the dragged block is held (`hold`) and glides home 260 ms OUT3 (`letGo`).

- [ ] **Step 10:** The four checks; commit "Map: blocks and links stay and move".

### Task 2: The entrance (master 2.2)

**Files:**
- Modify: `src/kitden/web/static/js/map-view.js` (`motion: "enter"`), `src/kitden/web/static/js/motion.js` (`riseHead`), `src/kitden/web/static/js/gateway.js`, `src/kitden/web/static/js/store.js`, `src/kitden/web/static/style.css` (view transition rules)
- Modify: `tests/frontend/map-view.test.mjs`, `tests/frontend/motion.test.mjs`, `tests/frontend/gateway.test.mjs`, `tests/unit/test_page_words.py`, `docs/design.md`

**Interfaces:**
- Consumes: `view.draw` (Task 1).
- Produces: `motion: "enter"` in `view.draw`: every block and caption starts at (x, y + 6), opacity 0, and moves to its place 260 OUT3, 22 ms apart in layout order; links follow the fainter of their two blocks. `export function riseHead(title, lede, scope)` in `motion.js` (any may be null): each rises 6 px, 260 CALM, at 0, 120 and 180 ms. `export function mapMotion({ fresh, projectChanged, narrowChanged })` in `gateway.js` → `"enter" | "none" | "move"`. In `store.js`, a place change into the Gateway runs `transition(…, "map-entrance")`; any other place keeps `"place-change"`.

- [ ] **Step 1: Write the failing tests**

```js
// map-view.test.mjs
test('the entrance: each block rises 6 px in 260 ms OUT3, 22 ms apart in layout order', async () => {
  const v = view(); const layout = lay();
  v.draw(TREE, layout, { motion: 'enter' });
  const ids = layout.blocks.map((b) => b.id); const last = v.node(ids.at(-1)); const end = 22 * (ids.length - 1);
  assert.equal(pos(v.node(ids[0])).y, place(layout, ids[0]).y + 6); assert.equal(v.node(ids[0]).style.opacity, '0');
  tick(end); assert.equal(last.style.opacity, '0');
  tick(130); assert.ok(near(pos(last).y, place(layout, ids.at(-1)).y + 6 * 0.125));
  tick(130); assert.equal(pos(last).y, place(layout, ids.at(-1)).y); assert.equal(last.style.opacity, '');
});

test('in the entrance a link shows only as much as the fainter of its two blocks', async () => {
  const v = view(); const layout = lay();
  v.draw(TREE, layout, { motion: 'enter' });
  const later = layout.blocks.findIndex((b) => b.id === 's2');
  tick(22 * later + 130);
  assert.equal(v.node('c1>s2').style.opacity, v.node('s2').style.opacity);
});

test('under reduced motion the entrance leaves every block and link visible at once', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(['s1']), { motion: 'enter' });
  for (const n of walk(v.area)) { assert.ok(!n.animations?.length); if (n.style) assert.equal(n.style.opacity ?? '', ''); }
});
```

```js
// motion.test.mjs
test('riseHead lifts the title at once, the lede after 120 ms and the scope line after 180 ms', () => {
  const [t, l, s] = [fakeNode(), fakeNode(), fakeNode()];
  riseHead(t, l, s);
  assert.deepEqual([t, l, s].map((n) => n.animations[0].options.delay), [0, 120, 180]);
  assert.ok([t, l, s].every((n) => n.animations[0].options.duration === 260 && n.animations[0].options.easing === CALM));
  assert.deepEqual(t.animations[0].keyframes, [{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }]);
  riseHead(t, l, null);  // no scope line: nothing breaks
});
```

```js
// gateway.test.mjs
test('the map enters when it is new, jumps for a new project or width, and moves otherwise', () => {
  assert.equal(mapMotion({ fresh: true, projectChanged: true, narrowChanged: true }), 'enter');
  assert.equal(mapMotion({ fresh: false, projectChanged: true, narrowChanged: false }), 'none');
  assert.equal(mapMotion({ fresh: false, projectChanged: false, narrowChanged: true }), 'none');
  assert.equal(mapMotion({ fresh: false, projectChanged: false, narrowChanged: false }), 'move');
});
```

```python
def test_the_gateway_rises_on_its_own_when_the_place_changes():
    assert "html.map-entrance::view-transition-new(page) { animation: none; }" in CSS
    assert '"map-entrance"' in script("store.js")
    assert "riseHead(" in script("gateway.js")
```

- [ ] **Step 2:** Run the four test files → FAIL.
- [ ] **Step 3: Implement.**
  - `map-view.js`: `"enter"` places every node at (x, y + 6), opacity 0, then one move of all blocks in layout order with `stagger: 22`, `dur: 260`, OUT3.
  - `gateway.js`: `drawOnMap` takes its motion from `mapMotion`. When `again` is false, `renderGateway` calls `riseHead(head, lede, scopeLine)`; the List then rises with `rise([grid])` instead of the first-visit `entrance()`.
  - `store.js`: `show(moving)` passes `"map-entrance"` when `state.view` is `"gateway"`.
  - `style.css` (view transition section): `html.place-change #main, html.map-entrance #main { view-transition-name: page; }`; the root animations are none for both classes; `html.map-entrance::view-transition-new(page) { animation: none; }`. The old page still fades out in 120 ms.
- [ ] **Step 4:** PASS. `docs/design.md` Patterns: "Place change" says the Gateway rises on its own (title, lede at 120 ms, scope line at 180 ms, then its map or List); a new row "Map entrance": `draw(…, { motion: "enter" })`, each block and caption rises 6 px in 260 ms OUT3, 22 ms apart in layout order, links follow the fainter of their blocks; on every visit, and when the List gives way to the Map; reduced motion shows the end at once.
- [ ] **Step 5:** The four checks; commit "Map: the entrance".

### Task 3: Layout numbers (master 2.3)

**Files:**
- Modify: `src/kitden/web/static/js/map.js` (`layoutTree`), `src/kitden/web/static/js/map-view.js` (caption icons), `src/kitden/web/static/js/gateway.js` (`GATEWAY_COLUMNS`, group and outside fields), `src/kitden/web/static/js/app.js` (`main.dataset.place`), `src/kitden/web/static/style.css`
- Modify: `tests/frontend/map.test.mjs`, `tests/frontend/gateway.test.mjs`, `tests/unit/test_page_words.py`, `docs/design.md`

**Interfaces:**
- Consumes: column caption blocks and `opener` (Task 1).
- Produces in `layoutTree` (wide only; narrow keeps today's rules under the caption row: top `CAPTION_ROW`, row gap 8, column gap `NARROW_GAP`):
  - a column may set `colGap` (space before it, default `GAP`), `top` (y of its first block, default `CAPTION_ROW`) and `rowGap` (between its blocks, default 8);
  - a group caption may set `h` (default `CAPTION_H`), `before` (more space above it when a block is above it in its column) and `rowGap` (between its children); `CAPTION_GAP = 5` lies between a group caption and its first child;
  - any block may set `h` (it beats its column's height, wide and narrow);
  - wide children of an open block are centred on the opener's middle: their first top is `max(column top, opener middle − stack height / 2)`, and never above the bottom of what the column already holds;
  - a caption's `icon` (a lucide name) is drawn before its words, 13 px.
- Produces in `gateway.js`: `GATEWAY_COLUMNS` = clients `{ w: 150, h: 54, top: 124, rowGap: 18, narrowW: 140 }`, gateway `{ w: 150, h: 124, colGap: 46, top: 124, rowGap: 18, narrowW: 56, narrowH: 56 }`, servers `{ w: 170, h: 60, colGap: 50, top: 58, rowGap: 10, narrowW: 220, narrowH: 54 }`, tools `{ w: 200, h: 34, colGap: 70, narrowH: 30 }`, captions as today. Remote and Local groups get `before: 3`, `icon` `"cloud"` / `"hard-drive"`; the outside group gets `h: OUTSIDE_H` (36, its words take two lines until Phase 4), `before: 21`, `rowGap: 6`, `icon: "info"`; outside blocks get `h: 50`.
- Produces: `#main` carries `data-place` = the place shown; the Gateway's page has no max width.

- [ ] **Step 1: Write the failing tests**

```js
// gateway.test.mjs (MEDIUM_VIEW: tracker in Remote, files in Local, four outside rows)
test('the Gateway map has the mockup numbers', () => {
  const l = layoutTree(gatewayTree(MEDIUM_VIEW, OPTS), { open: new Set(), narrow: false });
  const y = (id) => l.blocks.find((b) => b.id === id).y;
  assert.deepEqual(l.columns.map((c) => c.x), [0, 196, 396, 636]);
  assert.deepEqual(['client:claude_code', 'client:codex', 'client:cursor'].map(y), [124, 196, 268]);
  assert.deepEqual([y('gateway:kitden'), l.blocks.find((b) => b.id === 'gateway:kitden').h], [124, 124]);
  assert.deepEqual(['group:kitden:remote', 'held:kitden:tracker', 'group:kitden:local', 'held:kitden:files'].map(y), [58, 81, 154, 177]);
  assert.equal(y('group:outside'), 268);
  const outside = l.blocks.filter((b) => b.kind === 'outside');
  assert.deepEqual([outside[0].y, outside[1].y, outside[0].h], [309, 365, 50]);
  assert.equal(wideWidth(gatewayTree(MEDIUM_VIEW, OPTS)), 836);
});

test('group captions carry their icons', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.deepEqual(['group:kitden:remote', 'group:kitden:local', 'group:outside'].map((id) => block(tree, id).icon), ['cloud', 'hard-drive', 'info']);
});
```

```js
// map.test.mjs
test('tools are 200×34, 42 apart, centred on their server, never above y 24', () => {
  const l = layoutTree(model(3, 0, { open: 'github' }), { open: new Set(['held:kitden:github']), ...WIDE });
  const tools = l.blocks.filter((b) => b.id.startsWith('tool:github/'));
  assert.deepEqual(tools.map((b) => [b.y, b.w, b.h]), [[31, 200, 34], [73, 200, 34], [115, 200, 34], [157, 200, 34]]);
  const tall = { columns: GATEWAY_COLUMNS, blocks: [{ id: 'g', column: 'servers', kind: 'group', name: 'Remote' }, { id: 's', column: 'servers', parent: 'g', kind: 'held', name: 's', count: 8 },
    ...Array.from({ length: 8 }, (_, i) => ({ id: `t${i}`, column: 'tools', parent: 's', kind: 'tool', name: `t${i}` }))], links: [] };
  assert.equal(layoutTree(tall, { open: new Set(['s']), ...WIDE }).blocks.find((b) => b.id === 't0').y, 24);
});
```

Update the existing map tests to the new numbers: held servers are 170×60 (`b.h <= 60`), tools 200 wide, the tools start where the centring puts them, the direct line ends at `H 396`. "N more", the preview after "N more", narrow (tools inside their server, the 56 px gateway tile, the 472 px narrow width) and `narrowFor` keep their assertions.

```python
def test_the_gateway_page_takes_the_whole_width():
    assert '.page[data-place="gateway"] { max-width: none; }' in CSS
    assert "main.dataset.place = state.view" in script("app.js")
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** the layout rules and the Gateway fields (Interfaces). `app.js` `renderPlace` sets `main.dataset.place = state.view` before the page draws.
- [ ] **Step 4: CSS.** `div.map { margin: 22px 0 12px -6px; padding: 6px 6px 10px; overflow-x: auto; overflow-y: hidden; }` (the mockup's `.stage`). `div.map .map-caption`: 18 px tall, flex, gap 6, 11 px `--ink-3`, no wrap. `div.map .caption` (a group): 11 px / 600 `--ink-2`, flex, gap 6, its icon in `--ink-3` (the outside group's in `--lamp-warn`). Outside the map block: `.page[data-place="gateway"] { max-width: none; }`, so the head's Map | List pill sits at the main's right edge as in the mockup; other pages keep 1180 px until their phases.
- [ ] **Step 5:** PASS. `docs/design.md`: the Gateway map row gives the columns (x 0, 196, 396, 636; 836 px wide), the captions inside the map at the top of each column ("Tools" only while a server is open), the starts (clients and gateway at y 124, servers at 58), the pitches (clients 72, servers 70, outside 56, tools 42, centred on their server) and the group icons; the Shell or Page section says the Gateway page has no max width.
- [ ] **Step 6:** The four checks; commit "Map: the mockup's layout numbers".

### Task 4: Links take the pointer (master 2.4)

**Files:**
- Modify: `src/kitden/web/static/js/map.js` (`midPoint`), `src/kitden/web/static/js/map-view.js` (hits, ×, grace, keys), `src/kitden/web/static/js/gateway.js` (hooks), `src/kitden/web/static/js/gateway-details.js` (export `ruleBody`), `src/kitden/web/static/style.css`
- Modify: `tests/frontend/map.test.mjs`, `tests/frontend/map-view.test.mjs`, `tests/frontend/gateway.test.mjs`, `tests/unit/test_page_words.py`, `docs/design.md`

**Interfaces:**
- Consumes: `view.draw`, `linkKey` (Task 1).
- Produces in `map.js`: `midPoint(d) → { x, y }`, the point at half the length of a path made of absolute `M`, `H`, `V`, `C` and `Q` commands.
- Produces in `map-view.js`: the option `links: { canHit(link) → boolean, tip(link) → string, onClick(link), onRemove(link) }`. After the blocks, the area holds `svg.map-hits` (`role="group"`, `aria-label="Connections"`), with one `path.hit` per link where `canHit` is true (it comes and goes with its link): its `d` follows the link every frame; it is hidden (`display: none`) while the link is under .5 opacity; `tabindex="0"`, `role="button"`, `aria-label` "<from name> to <to name>", `aria-description` = `tip(link)`, `aria-keyshortcuts="Delete"`. Then one `button.link-x` (`tabindex="-1"`, hidden, `icon("x", 10)`). Pointer over or focus on a hit: its link gets `.hov`, the × moves (no motion) to `translate(round(mid.x − 8)px, round(mid.y − 8)px)` with `title` and `aria-label` = tip, and if it was hidden fades in 120 CALM. Pointer out or blur: after 240 ms (plain `setTimeout`) `.hov` goes and the × hides; the pointer on the × cancels the wait. A click on a hit or Enter / Space → `onClick(link)`; Delete / Backspace on a hit or a click on the × → `onRemove(link)`.
- Produces in `gateway.js`: `export function linkRemoval(model, link, picked) → { tip, body } | null`: Kitden gateway → its server: `{ tip: "Remove <name> from the gateway", body: { action: "gateway.remove", targets: [], params: { server } } }`; a Kitden server → its tool: `{ tip: "Turn off <tool>", body: ruleBody(server, tool, "off", picked || null) }`; anything else null. The view's hooks: `canHit` = a removal exists; `tip` = its tip; `onRemove` = `review(body)`; `onClick` = select the link (`onMap.selected = linkKey(link)`, draw) and open the Details of its far block (`openDetails`), until Phase 4's Connection panel.

- [ ] **Step 1: Write the failing tests**

```js
// map.test.mjs
test('the middle of a path is the point at half its length', () => {
  assert.deepEqual(midPoint('M 0 0 H 100'), { x: 50, y: 0 });
  assert.deepEqual(midPoint('M 0 0 H 10 V 100 H 20'), { x: 10, y: 50 });
  const c = midPoint('M 0 0 C 50 0, 50 100, 100 100');
  assert.ok(Math.abs(c.x - 50) < 0.5 && Math.abs(c.y - 50) < 0.5);
});
```

```js
// map-view.test.mjs
const clicked = []; const removed = [];
const LINKS = { canHit: (l) => l.to === 's1', tip: (l) => `Remove ${l.to}`, onClick: (l) => clicked.push(l), onRemove: (l) => removed.push(l) };
const hitOf = (v) => walk(v.area).find((n) => n.classList?.contains('hit'));
const xOf = (v) => walk(v.area).find((n) => n.classList?.contains('link-x'));

test('only a link the page acts on takes the pointer, after the blocks, named for keyboards', async () => {
  reduce(true);
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), {});
  const hits = walk(v.area).filter((n) => n.classList?.contains('hit'));
  assert.equal(hits.length, 1);
  const h = hits[0];
  assert.deepEqual(['tabindex', 'role', 'aria-label', 'aria-description', 'aria-keyshortcuts'].map((a) => h.getAttribute(a)), ['0', 'button', 'Codex to github', 'Remove s1', 'Delete']);
  const svg = h.parentNode;
  assert.equal(svg.getAttribute('aria-label'), 'Connections');
  assert.ok(v.area.children.indexOf(svg) > v.area.children.findLastIndex((n) => n.dataset?.focus));
});

test('pointing at a link gives it the hover look and puts the × on its middle', async () => {
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), { motion: 'none' });
  hitOf(v).dispatch('pointerover');
  const m = midPoint(v.node('c1>s1').getAttribute('d')); const x = xOf(v);
  assert.ok(v.node('c1>s1').classList.contains('hov'));
  assert.equal(x.hidden, false);
  assert.equal(x.style.transform, `translate(${Math.round(m.x - 8)}px, ${Math.round(m.y - 8)}px)`);
  assert.equal(x.getAttribute('aria-label'), 'Remove s1');
  assert.deepEqual([x.animations[0].options.duration, x.animations[0].options.easing], [120, CALM]);
});

test('the × waits 240 ms after the pointer leaves, also under reduced motion, and the pointer on it keeps it', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  reduce(true);
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), {});
  const [h, x] = [hitOf(v), xOf(v)];
  h.dispatch('pointerover'); h.dispatch('pointerout');
  t.mock.timers.tick(239); assert.equal(x.hidden, false);
  t.mock.timers.tick(1); assert.equal(x.hidden, true); assert.ok(!v.node('c1>s1').classList.contains('hov'));
  h.dispatch('pointerover'); h.dispatch('pointerout'); x.dispatch('pointerenter');
  t.mock.timers.tick(500); assert.equal(x.hidden, false);
  x.dispatch('pointerleave'); t.mock.timers.tick(240); assert.equal(x.hidden, true);
});

test('Enter on a link is its click, Delete and the × are its removal', async () => {
  reduce(true); clicked.length = 0; removed.length = 0;
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), {});
  const h = hitOf(v);
  h.dispatch('keydown', { key: 'Enter' }); h.dispatch('click');
  h.dispatch('keydown', { key: 'Delete' }); h.dispatch('keydown', { key: 'Backspace' }); xOf(v).dispatch('click');
  assert.deepEqual([clicked.length, removed.length], [2, 3]);
  h.focus(); assert.ok(v.node('c1>s1').classList.contains('hov'));
});

test('a link fainter than half takes no pointer', async () => {
  const v = view({ links: { ...LINKS, canHit: (l) => l.to === 's2' } });
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(without('s2'), layoutTree(without('s2'), { open: new Set(), narrow: false }), {});
  tick(90); assert.equal(hitOf(v).style.display, '');
  tick(60); assert.equal(hitOf(v).style.display, 'none');
});
```

```js
// gateway.test.mjs
test('a link the map can act on says what its × does', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const link = (key) => tree.links.find((l) => `${l.from}>${l.to}` === key);
  assert.deepEqual(linkRemoval(tree, link('gateway:kitden>held:kitden:files'), ''),
    { tip: 'Remove files from the gateway', body: { action: 'gateway.remove', targets: [], params: { server: 'files' } } });
  assert.deepEqual(linkRemoval(tree, link('held:kitden:files>tool:files/read_file'), 'website'),
    { tip: 'Turn off read_file', body: { action: 'gateway.rule', targets: [], params: { server: 'files', tool: 'read_file', state: 'off', project: 'website' } } });
  assert.equal(linkRemoval(tree, link('client:codex>gateway:kitden'), ''), null);
  assert.equal(linkRemoval(tree, link('client:codex>outside:local:docs'), ''), null);
});
```

```python
def test_a_link_says_what_its_x_does():
    assert "} from the gateway`" in gw() and "`Turn off ${" in gw()
    view = script("map-view.js")
    assert "} to ${" in view and '"Connections"' in view and '"aria-keyshortcuts", "Delete"' in view
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** `midPoint` (walk the commands; sample each `C` and `Q` into 16 straight steps; stop at half the total length) and the view's hit layer, ×, grace and keys (Interfaces); the × follows its link every frame. Export `ruleBody` from `gateway-details.js`; add `linkRemoval` and the hooks to `gateway.js`.
- [ ] **Step 4: CSS.** `div.map .map-hits { position: absolute; inset: 0; z-index: 0; overflow: visible; pointer-events: none; }` (after the blocks in the DOM, painted under them, so a block wins where they meet). `div.map .hit { fill: none; stroke: transparent; stroke-width: 14; pointer-events: stroke; cursor: pointer; outline: none; }`. `div.map .link.hov, div.map .link.picked { stroke: var(--route); stroke-width: 2.4; stroke-opacity: 1; }`. `div.map .link-x`: absolute at 0 0, `z-index: 2`, 16 px circle, `--panel` fill, 1 px `--route` border, `--route` colour, `::before` with `inset: -6px` (a 28 px target), hover `--route` fill with `--panel` colour (120 ms ease), `:focus-visible` outline 2 px `--focus`. Outside the map block: `.grabbing .map-hits .hit { pointer-events: none; }` (no link hover while a block is dragged).
- [ ] **Step 5:** PASS. `docs/design.md`: Accessibility gains "A link the page can act on is a button after the blocks, named '<from> to <to>'; focus gives it the hover look and its ×; Enter opens it, Delete does what its × does". Patterns gains "Link pointer": a 14 px hit stroke, hover 2.4 px accent, the 16 px × at half the path's length, in 120 ms, 240 ms grace that does not scale and runs under reduced motion. The Gateway map row says which links take the pointer in this phase (a server in the Kitden gateway, a tool) and what a click on a link opens.
- [ ] **Step 6:** The four checks; commit "Map: links take the pointer".

### Task 5: Link looks and motion (master 2.5)

**Files:**
- Modify: `src/kitden/web/static/js/map.js` (`linkPath` shapes, channels, `linkDashed`, `linkClass` gains `leaving`), `src/kitden/web/static/js/map-view.js` (links that come, go and change), `src/kitden/web/static/style.css`
- Modify: `tests/frontend/map.test.mjs`, `tests/frontend/map-view.test.mjs`, `tests/unit/test_page_words.py`, `docs/design.md`

**Interfaces:**
- Consumes: `drawPlan`, `linkPath`, `view.drawIn` (Task 1).
- Produces in `map.js`: `CHANNELS = [16, 24, 32]`, `NARROW_CHANNEL = 14`. A `"curve"` has horizontal handles of `max(18, |x1 − x0| / 2)`. A `"step"` (a link that skips the gateway) leaves its client's right side, goes right by its channel, turns down or up with corners of `min(8, |dy| / 2)` and goes right into the block; a straight one when `|dy| < 1`. Each direct link carries `chan`: wide, its target's place among the blocks with direct links in layout order picks `CHANNELS[i % 3]`; narrow, `NARROW_CHANNEL`. `linkDashed(link) → boolean`: kind `direct` or `preview`, or `unk`, or `leaving`. `linkClass` adds `" leaving"` for `link.leaving` (Phase 3 and 4 set it on a removal in preview).
- Produces in `map-view.js`, for a link whose two blocks stay: a new solid link draws in (`drawIn`, 260); a new dashed link fades in, opacity 0 → 1, 300 CALM; a dashed link that goes fades out from its opacity now (1 at rest) to 0, 240 ease-out, `fill: "forwards"`, then is removed; a solid link that goes undraws (`pathLength="1"`, `stroke-dashoffset` 0 → 1, 380 RETRACT, `fill: "forwards"`), then is removed; a staying link whose class changes blends, `[{ strokeDasharray, strokeOpacity }]` read from `getComputedStyle` before and after, `"none"` read as `"8 0"`, 300 CALM. A link that leaves and comes back during its exit is shown again at once. Under reduced motion, or on a hidden page, all of it lands at once: a link that goes is removed in the same draw, with no timer.

- [ ] **Step 1: Write the failing tests**

```js
// map.test.mjs
test('a link that skips the gateway turns at right angles on its own channel, 16, 24 or 32 px out, with corners of 8', () => {
  const l = layoutTree(model(0, 4), { open: new Set(), ...WIDE });
  const lines = l.blocks.filter((b) => b.kind === 'outside').map((b) => l.links.find((k) => k.to === b.id));
  assert.deepEqual(lines.map((k) => k.chan), [16, 24, 32, 16]);
  assert.match(lines[0].d, /^M 150 (\d+) H 158 Q 166 \1 166 \d+ V \d+ Q 166 (\d+) 174 \2 H 396$/);
  const narrow = layoutTree(model(0, 2), { open: new Set(), width: 900, narrow: true });
  assert.ok(narrow.links.filter((k) => k.kind === 'direct').every((k) => k.chan === 14));
});

test('a curve keeps its handles level, half the gap long and at least 18 px', () => {
  assert.equal(linkPath({ shape: 'curve' }, { x: 0, y: 0, w: 150, h: 54 }, { x: 196, y: 0, w: 150, h: 124 }), 'M 150 27 C 173 27, 173 62, 196 62');
  assert.equal(linkPath({ shape: 'curve' }, { x: 0, y: 0, w: 100, h: 20 }, { x: 110, y: 40, w: 10, h: 20 }), 'M 100 10 C 118 10, 92 50, 110 50');
});

test('a link is dashed when it skips the gateway, is a preview, is leaving or is not known', () => {
  assert.deepEqual([{ kind: 'direct' }, { kind: 'preview' }, { kind: 'on', leaving: true }, { kind: 'on', unk: true }, { kind: 'on' }, { kind: 'faint' }].map(linkDashed), [true, true, true, true, false, false]);
  assert.equal(linkClass({ from: 'a', to: 'b', kind: 'on', leaving: true }), 'link on leaving');
});
```

```js
// map-view.test.mjs — getComputedStyle reads the dash look from the class: "leaving" → '4 4' / '0.4', "preview" → '4 4' / '0.65', else 'none' / '1'
const NO_LINK = { ...TREE, links: TREE.links.filter((l) => l.to !== 's2') };
const withLink = (fields) => ({ ...TREE, links: TREE.links.map((l) => (l.to === 's2' ? { ...l, ...fields } : l)) });
const drawn = (m) => layoutTree(m, { open: new Set(), narrow: false });

test('a new link between two blocks that stay draws from its start in 260 ms', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const v = view();
  await v.draw(NO_LINK, drawn(NO_LINK), { motion: 'none' });
  v.draw(TREE, drawn(TREE), {});
  const link = v.node('c1>s2'); const a = link.animations[0];
  assert.equal(link.getAttribute('pathLength'), '1');
  assert.deepEqual([a.keyframes, a.options.duration, a.options.easing], [[{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], 260, CALM]);
  t.mock.timers.tick(260); assert.equal(link.getAttribute('pathLength'), null); assert.equal(link.style.strokeDasharray, '');
});

test('a new preview link fades in over 300 ms', async () => {
  const v = view();
  await v.draw(NO_LINK, drawn(NO_LINK), { motion: 'none' });
  const m = withLink({ kind: 'preview' }); v.draw(m, drawn(m), {});
  const a = v.node('c1>s2').animations[0];
  assert.deepEqual([a.keyframes, a.options.duration, a.options.easing], [[{ opacity: 0 }, { opacity: 1 }], 300, CALM]);
});

test('a dashed link that goes fades out in 240 ms; a solid one draws back to its start in 380 ms', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  for (const [kind, keyframes, ms, ease] of [['preview', [{ opacity: 1 }, { opacity: 0 }], 240, 'ease-out'], ['on', [{ strokeDashoffset: 0 }, { strokeDashoffset: 1 }], 380, RETRACT]]) {
    const v = view(); const m = withLink({ kind });
    await v.draw(m, drawn(m), { motion: 'none' });
    const link = v.node('c1>s2');
    v.draw(NO_LINK, drawn(NO_LINK), {});
    const a = link.animations.at(-1);
    assert.deepEqual([a.keyframes, a.options.duration, a.options.easing, a.options.fill], [keyframes, ms, ease, 'forwards']);
    t.mock.timers.tick(ms); assert.equal(link.parentNode, null);
  }
});

test('a link that turns dashed blends in 300 ms, a solid line counting as "8 0"', async () => {
  const v = view();
  await v.draw(TREE, drawn(TREE), { motion: 'none' });
  const m = withLink({ leaving: true }); v.draw(m, drawn(m), {});
  const link = v.node('c1>s2'); const a = link.animations.at(-1);
  assert.ok(link.classList.contains('leaving'));
  assert.deepEqual(a.keyframes, [{ strokeDasharray: '8 0', strokeOpacity: '1' }, { strokeDasharray: '4 4', strokeOpacity: '0.4' }]);
  assert.deepEqual([a.options.duration, a.options.easing], [300, CALM]);
});

test('under reduced motion links come and go at once', async () => {
  reduce(true);
  const v = view();
  await v.draw(NO_LINK, drawn(NO_LINK), {});
  await v.draw(TREE, drawn(TREE), {});
  const link = v.node('c1>s2');
  assert.equal(link.animations.length, 0);
  await v.draw(NO_LINK, drawn(NO_LINK), {});
  assert.equal(link.parentNode, null);
});
```

In `tests/unit/test_page_words.py` `test_the_map_says_the_link_is_the_state`, the amber pin becomes the D8 look:

```python
    direct = rule("div.map .link.direct")
    assert "var(--lamp-off)" in direct and "stroke-dasharray: 1.5 4" in direct and "stroke-opacity: 0.8" in direct
    assert "var(--lamp-warn)" in rule("div.map .link.direct.hov, div.map .link.direct.picked")
    assert "stroke-dasharray: 4 4" in rule("div.map .link.preview") and "stroke-opacity: 0.65" in rule("div.map .link.preview")
    assert "stroke-opacity: 0.4" in rule("div.map .link.leaving")
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** the shapes and channels in `map.js` and the link paths in `map-view.js` (Interfaces). Removal waits by time (`setTimeout(…, D(ms))`).
- [ ] **Step 4: CSS** (link looks, Kitden tokens): `div.map .link { fill: none; stroke: var(--link); stroke-width: 1.2; stroke-linecap: round; transition: stroke 220ms ease, stroke-width 220ms ease, stroke-opacity 300ms ease; }`; `.link.direct { stroke: var(--lamp-off); stroke-opacity: 0.8; stroke-dasharray: 1.5 4; }`; `.link.direct.unk { stroke-dasharray: 3 3; }` (kept); `.link.faint { stroke-opacity: 0.5; }`; `.link.preview { stroke: var(--route); stroke-opacity: 0.65; stroke-dasharray: 4 4; }`; `.link.leaving { stroke: var(--ink-3); stroke-opacity: 0.4; stroke-dasharray: 4 4; }`; `.link.lit { stroke: var(--route); stroke-width: 1.7; }`; `.link.direct.lit { stroke: var(--ink-3); stroke-opacity: 1; }`; `div.map .link.direct.hov, div.map .link.direct.picked { stroke: var(--lamp-warn); }` (after Task 4's hover rule).
- [ ] **Step 5:** PASS. `docs/design.md`: the Gateway map row's "an amber elbow" becomes "a grey dotted line at right angles, amber under the pointer"; a "Link looks" paragraph (base, lit, preview, leaving, bypass, hover, with these values); Patterns "Link motion": draw-in 260 ms, preview fades in 300 ms, a dashed link fades out 240 ms, a solid one undraws 380 ms, a change of look blends 300 ms; reduced motion shows the end at once.
- [ ] **Step 6:** The four checks; commit "Map: link looks and motion".

### Task 6: Focus and select (master 2.6)

**Files:**
- Modify: `src/kitden/web/static/js/map-view.js` (focus, overlays, pick, glance, `onEmpty`, `onHover`), `src/kitden/web/static/js/gateway.js`, `src/kitden/web/static/style.css`
- Modify: `tests/frontend/map-view.test.mjs`, `tests/frontend/gateway.test.mjs`, `tests/unit/test_page_words.py`, `docs/design.md`

**Interfaces:**
- Consumes: `view.draw` with `selected` and `lit` (Task 1), the × (Task 4).
- Produces in `map-view.js`:
  - `draw` with a non-empty `lit`: the box gets `.focus`; blocks in `lit` get `.lit`, links in `lit` get `.lit`. When `selected` is a block, each lit link that is not `direct` gets a `path.link-over` in the links SVG (its `d` follows every frame) that fades in 180 CALM; overlays no longer lit fade out 160 ease-in and are removed by time. When `selected` is a link key, that link gets `.picked`, keeps its × and gets no overlay. An empty `lit` takes `.focus` away.
  - `view.glance(lit | null)`: the same focus with no overlays, only while the last draw selected nothing; a draw with a selection ends a glance.
  - options `onEmpty()`: a click in the box that is not on a block, a caption button, a hit, the × or another button; `onHover(id | null)`: the id of the block under the pointer when it changes, null when the pointer leaves the box; never while a block is held.
- Produces in `gateway.js`: `export function litFor(model, selected) → Set` (a link key: its two ends and itself; a client: `litFrom`; any other block: `litPath`; none: empty); `export function glanceFor(model, id) → Set | null` (a client: `litFrom`; a server outside the gateway: `litPath`; else null); `export function afterPress({ selected, id, opened }) → "select" | "letGo"`. `pressBlock` lets go (closes Details, clears `onMap.selected`, draws) on `"letGo"`; `onEmpty` lets go when something is selected; `onHover` calls `view.glance(glanceFor(model, id))`.

- [ ] **Step 1: Write the failing tests**

```js
// map-view.test.mjs
const LIT = new Set(['c1', 's1', 'c1>s1']);
const overs = (v) => walk(v.area).filter((n) => n.classList?.contains('link-over'));

test('a selection dims what is off its path and lays an overlay on each lit link', async () => {
  const v = view();
  await v.draw(TREE, lay(), { motion: 'none' });
  v.draw(TREE, lay(), { selected: 's1', lit: LIT });
  assert.ok(v.box.classList.contains('focus'));
  assert.ok(v.node('s1').classList.contains('selected') && v.node('c1').classList.contains('lit') && !v.node('s2').classList.contains('lit'));
  assert.ok(v.node('c1>s1').classList.contains('lit'));
  const [o] = overs(v); const a = o.animations[0];
  assert.equal(overs(v).length, 1);
  assert.deepEqual([a.keyframes, a.options.duration, a.options.easing], [[{ opacity: 0 }, { opacity: 1 }], 180, CALM]);
});

test('letting go fades the overlays out in 160 ms, then removes them', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const v = view();
  await v.draw(TREE, lay(), { selected: 's1', lit: LIT, motion: 'none' });
  const [o] = overs(v);
  v.draw(TREE, lay(), {});
  assert.ok(!v.box.classList.contains('focus'));
  assert.deepEqual([o.animations.at(-1).keyframes, o.animations.at(-1).options.duration, o.animations.at(-1).options.easing], [[{ opacity: 1 }, { opacity: 0 }], 160, 'ease-in']);
  t.mock.timers.tick(160); assert.equal(o.parentNode, null);
});

test('a selected link is picked, keeps its ×, and lays no overlay', async () => {
  reduce(true);
  const v = view({ links: LINKS });
  await v.draw(TREE, lay(), { selected: 'c1>s1', lit: LIT });
  assert.ok(v.node('c1>s1').classList.contains('picked'));
  assert.equal(xOf(v).hidden, false);
  assert.equal(overs(v).length, 0);
});

test('a glance lights a path with no overlay, only while nothing is selected', async () => {
  reduce(true);
  const v = view();
  await v.draw(TREE, lay(), {});
  v.glance(LIT); assert.ok(v.box.classList.contains('focus')); assert.equal(overs(v).length, 0);
  v.glance(null); assert.ok(!v.box.classList.contains('focus'));
  await v.draw(TREE, lay(), { selected: 's2', lit: new Set(['c1', 's2', 'c1>s2']) });
  v.glance(LIT); assert.ok(v.node('s2').classList.contains('lit') && !v.node('s1').classList.contains('lit'));
});

test('a click on empty map lets go; a click on a block or a link does not', async () => {
  reduce(true);
  let empty = 0;
  const v = view({ onEmpty: () => { empty += 1; }, links: LINKS });
  await v.draw(TREE, lay(), {});
  v.area.dispatch('click'); v.node('s1').dispatch('click'); hitOf(v).dispatch('click');
  assert.equal(empty, 1);
});

test('the page hears which block the pointer is on, and null when it leaves the map', async () => {
  reduce(true);
  const heard = [];
  const v = view({ onHover: (id) => heard.push(id) });
  await v.draw(TREE, lay(), {});
  v.node('s1').dispatch('pointerover'); v.node('s1').firstElementChild.dispatch('pointerover'); v.box.dispatch('pointerleave');
  v.hold('s2', { x: 0, y: 0 }); v.node('s2').dispatch('pointerover');
  assert.deepEqual(heard, ['s1', null]);
});
```

```js
// gateway.test.mjs
test('a second press on the selected block lets go, unless the press opened it', () => {
  assert.equal(afterPress({ selected: 'client:codex', id: 'client:codex', opened: false }), 'letGo');
  assert.equal(afterPress({ selected: 'held:kitden:files', id: 'held:kitden:files', opened: true }), 'select');
  assert.equal(afterPress({ selected: null, id: 'client:codex', opened: false }), 'select');
});

test('pointing at a client or a server outside the gateway previews its paths; a selected link lights its two ends', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  assert.ok(glanceFor(tree, 'client:codex').has('client:codex>gateway:kitden'));
  assert.deepEqual([...glanceFor(tree, 'outside:local:files')].sort(), ['client:cursor', 'client:cursor>outside:local:files', 'outside:local:files']);
  assert.equal(glanceFor(tree, 'held:kitden:files'), null);
  assert.deepEqual([...litFor(tree, 'gateway:kitden>held:kitden:files')].sort(), ['gateway:kitden', 'gateway:kitden>held:kitden:files', 'held:kitden:files']);
  assert.equal(litFor(tree, null).size, 0);
});
```

```python
def test_a_selection_dims_what_is_off_its_path():
    assert "filter: opacity(0.4) saturate(0.6)" in rule("div.map.focus .block:not(.lit):not(.selected)")
    assert "stroke-opacity: 0.16" in rule("div.map.focus .link:not(.lit)")
    assert "stroke-width: 2.1" in rule("div.map .link-over")
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** (Interfaces). In `gateway.js`, `drawOnMap` passes `lit: litFor(model, onMap.selected)`; `pressBlock` asks `afterPress({ selected: onMap.selected, id, opened: foldable(model).has(id) && onMap.open.has(id) })` first; the view gets `onEmpty` and `onHover` (no glance while something is selected).
- [ ] **Step 4: CSS.** `div.map.focus .block:not(.lit):not(.selected), div.map.focus .caption, div.map.focus .map-caption` → the block rule is `filter: opacity(0.4) saturate(0.6)` (captions keep their look); `div.map.focus .link:not(.lit) { stroke-opacity: 0.16; }`; `div.map.focus .link.hov, div.map.focus .link.picked { stroke-opacity: 1; }`; `div.map .link-over { fill: none; stroke: var(--route); stroke-width: 2.1; stroke-linecap: round; }`. The `filter` and `stroke-opacity` transitions (300 ease) are already on `.block` and `.link`.
- [ ] **Step 5:** PASS. `docs/design.md`: the Gateway map row says a click or Enter selects and dims everything off the path (blocks to 40 % and less colour, links to 16 %), with a 2.1 px accent line over each lit link; one thing is selected at a time; a second click or a click on empty map lets go; while nothing is selected, pointing at a client or a server outside the gateway lights its paths without the accent line. Patterns gains "Focus": dims 300 ms ease, overlay in 180 ms `--calm`, out 160 ms ease-in.
- [ ] **Step 6:** The four checks; commit "Map: focus and select".

### Task 7: Check on the demo home

- [ ] **Step 1:** `uv run kitden demo --size medium` (a sample home in a temporary folder; nothing real is touched). Open the Gateway at 1440×900, both themes.
- [ ] **Step 2:** Walk the mockup's M1–M3 against the page with `?slow=4`: the entrance (head, then blocks 22 ms apart), a server unfold and fold, a block that moves, link hover, × and grace, link draw-in and undraw (Apply, then Undo, a tool rule from its Details), select and let go (second click, empty map, Escape), hover preview on a client and on an outside server.
- [ ] **Step 3:** Today's Gateway still works: drag an outside server onto Servers (the block follows with its links, parks on the slot, the review bar shows), Cancel (it glides home, no spinner left), Escape during a drag, the List, a search (matches lit, the rest dim), the narrow layout (window under 1024 px), "N more" opening the List. Tab: blocks in reading order, then the links; Enter and Delete on a link.
- [ ] **Step 4:** Reduced motion (the browser's emulation): every state at once, nothing at opacity 0. A live rescan (`Rescan`) during the entrance and with a block focused: one node per block, focus kept.
- [ ] **Step 5:** Fix what differs; run the four checks; commit "Map: fixes from the check" if anything changed. Tell the owner the ROADMAP line if `ROADMAP.md` could not be staged: "Gateway map: blocks glide and unfold in place, links take the pointer (× to remove, by keyboard too), and a selection dims the rest."
