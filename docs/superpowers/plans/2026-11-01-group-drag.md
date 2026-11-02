# Group Drag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select several outside servers on the Gateway map (rubber band, or Shift/Cmd-click) and
drag them onto the gateway together. Each one becomes a preview change in the tray.

**Architecture:**
- **Selection.** A new module, `gateway-pick.js`, owns the picked set: the rubber band, the
  toggle clicks and clearing.
- **Drawing.** `map-view.js` learns one draw option, `picked`, which draws each picked block
  with the selected look.
- **Drag.** `gateway-drag.js` gets a fourth drag kind, `group`. It is built like the Add-panel
  drag: a ghost on the page, the original blocks stay, the gateway lights. On a drop it adds
  one `gateway.move` per server to the tray, one after another, with the same body a single
  drag uses (`dropBody`).
- **Preview.** No new preview code. The tray rows draw the preview blocks as today (`movesIn`).

**Tech Stack:** vanilla JS modules, CSS, `node --test` with the fake DOM in `tests/frontend`.

**Spec:** `docs/superpowers/specs/2026-11-01-add-select-sign-in-design.md`, Part 2, with
"Settled after the builder check" items 1 and 6.

## Global Constraints

- Only blocks of kind `outside` that have a grip (`block.grip`) can be picked. Nothing else is
  touched by the band or the toggle.
- Band look: a solid 1 px `--route` edge at 40% on `--route-soft`, not dashed. It follows the
  pointer with no easing. It appears after 5 px of movement (`DRAG_START`). On release or
  Escape it fades out in 120 ms.
- Picked look: the same as `.block.selected`.
- A group pick replaces the single selection: picking lets go of open Details (`letGoIfSelected`).
- Group ghost:
  - up to 3 visible layers, 4 px apart, back layers at opacity .7 and .4;
  - a small accent count pill, "3 servers";
  - the originals go to .4 while the drag runs;
  - the count pill fades in over 120 ms.
- A drop that misses, Escape, or a lost pointer: the ghost flies back in 180 ms `--calm` and the
  pick is kept.
- A drop on the gateway adds one tray row per server. A server the tray refuses stays where it is.
  The dock shows the refusal as today.
- Two outside rows with different names stay two servers (spec item 6: "same" means the same
  entry; one outside row already joins the same name across clients).
- Reduced motion: the band, ghost and flights land at once.
- UI text in simple English. Update `docs/design.md` and `ROADMAP.md` in the same change.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `node --test tests/frontend/*.test.mjs`.

## Decisions this plan makes (within the spec)

- **No per-group "Drop to add" slot for a group drag.** The gateway and the Add a server card
  light up, and the ghost flies onto the gateway box. Each server's preview block then grows in its
  own group as its row answers, the same as after "Move into the gateway…".
  - Why: the map's tree takes one `drop` slot, and a slot per server would mean N slots.
  - Cost if wrong: one more `drop` shape in `movesIn` later.
- **Rows are added one by one** (`await addToTray` in a loop), so a refused server leaves the rest
  in. Their answers arrive one after another, so the blocks appear one after another. There is no
  timed stagger.

## Review Focus

1. **A pick goes stale.** The page reads again (Rescan, Apply, another project) and a picked
   server is gone or is no longer outside. The pick drops ids that are no longer pickable on every
   draw.
2. **The tray is busy** (applying, or a change is being written). A group drop does nothing, and the
   ghost flies back.
3. **Only one server is picked.** Pressing it starts today's single `in` drag, not a group drag.
4. **A drag starts on a block that is not picked** while others are. It drags that one block
   alone, and the pick is cleared.
5. **The band runs over Details or the dock, or the map scrolls.** Hit testing uses map points
   (`areaPoint`), so a scrolled map still picks the blocks under the band.

---

### Task 1: `picked` draw option in map-view

**Files:**
- Modify: `src/kitden/web/static/js/map-view.js` (`draw` options ~1087, `fill` look ~542, the doc
  comment ~286)
- Test: `tests/frontend/map-view.test.mjs`

**Interfaces:**
- Produces: `view.draw(model, layout, { …, picked: Set<string> })`. Each id in `picked` gets the
  `selected` class. The default is an empty set.

- [ ] **Step 1: Failing test** — `test('picked blocks take the selected look, several at once')`:
  draw `TREE` with `picked: new Set(['s1','s2'])` and assert both nodes' classes include
  `selected`, and a block not in the set does not.
- [ ] **Step 2: Run** `node --test tests/frontend/map-view.test.mjs`. Expected: FAIL.
- [ ] **Step 3: Implement.** `fill` gets `picked`, and the look adds `"selected"` when
  `place.id === selected || picked.has(place.id)`.
- [ ] **Step 4: Run** all frontend tests. Expected: PASS.
- [ ] **Step 5: Commit** — "Let the map draw several selected blocks"

### Task 2: Picking — band, toggle, clear (`gateway-pick.js`)

**Files:**
- Create: `src/kitden/web/static/js/gateway-pick.js`
- Modify: `src/kitden/web/static/js/gateway.js`:
  - `newMap` ~1030: pointerdown and capture-click listeners, and Escape;
  - the draw ~1174: pass `picked`;
  - the hint;
  - `letGoIfSelected` clears the pick.
- Modify: `src/kitden/web/static/style.css` (`.map-band`)
- Test: `tests/frontend/gateway.test.mjs` (pure parts), `tests/frontend/gateway-page.test.mjs` (wiring)

**Interfaces:**
- Produces, in `gateway-pick.js`:
  - `export const pick = { ids: new Set() }`
  - `pickable(block): boolean` — `block.kind === "outside" && Boolean(block.grip)`
  - `bandHits(model, layout, a, b): string[]` — ids of pickable blocks whose layout box meets
    the rectangle from map point `a` to map point `b` (either corner order)
  - `togglePick(model, id): boolean` — toggles a pickable id; returns false for anything else
  - `keepPickable(model)` — drops ids no longer pickable in `model`
  - `clearPick(): boolean` — true when something was picked
  - `pressBand(event, { view, layout, model, onPick })` — the band, run on pointerdown on empty
    map space. It uses the same document listeners as `startDrag`, swallows the click that ends
    it (`swallowClick`), and calls `onPick()` after every change.
  - `PICK_HINT(n)` → `"${n} servers picked · drag one onto the gateway · Esc clears"`
    (`"1 server picked · …"` when n is 1)

- [ ] **Step 1: Failing tests**

```js
test('the band picks only outside servers with a grip, whatever way it is drawn', () => {
  const tree = gatewayTree(MEDIUM_VIEW, OPTS);
  const layout = layoutTree(tree, { open: new Set(), narrow: false });
  const outside = layout.blocks.filter((b) => b.id.startsWith('outside:'));
  const [top, bottom] = [outside[0], outside.at(-1)];
  const all = bandHits(tree, layout, { x: 0, y: top.y }, { x: 2000, y: bottom.y + bottom.h });
  assert.deepEqual(all, tree.blocks.filter((b) => pickable(b)).map((b) => b.id));
  assert.deepEqual(bandHits(tree, layout, { x: 2000, y: bottom.y + bottom.h }, { x: 0, y: top.y }), all);
  assert.deepEqual(bandHits(tree, layout, { x: 0, y: 0 }, { x: 10, y: 10 }), []);
});
test('a toggle picks and unpicks; a held server or a client cannot be picked', () => { /* togglePick on outside → true twice → set empty; on 'held:kitden:files' and 'client:codex' → false */ });
test('a pick drops servers that are no longer outside', () => { /* pick.ids has 'outside:move:github' + 'outside:move:gone'; keepPickable(tree) leaves only the first */ });
test('the hint counts what is picked', () => { assert.equal(PICK_HINT(3), '3 servers picked · drag one onto the gateway · Esc clears'); assert.equal(PICK_HINT(1), '1 server picked · drag one onto the gateway · Esc clears'); });
```

In `gateway-page.test.mjs`:
- **A band from empty space.** A pointerdown on the map box at an empty spot, a move of more than
  5 px across two outside blocks, then up. Both nodes take `selected`, the hint shows
  `PICK_HINT(2)`, and the following click on empty space does not clear them.
- **Shift-click and Meta-click.** Each toggles one outside block, and no Details open.
- **Escape, then an empty click.** Each clears the pick.

- [ ] **Step 2: Run** `node --test tests/frontend/gateway.test.mjs tests/frontend/gateway-page.test.mjs`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement.**
  - **The band.** One absolutely placed `div.map-band` inside the map area. Each move sets
    `transform: translate(x,y) scale(w,h)` on a 1×1 px box with `transform-origin: 0 0`. The
    edge comes from an inset `box-shadow`, so the scale does not thicken it. The ids under it
    are recomputed every move. On release it fades out over 120 ms (`animateTo`, ease-in) and
    is removed.
  - **Pointerdown on empty space** (not a button, not a `.hit`) starts the band. It lets go of
    the single selection first.
  - **Shift or Meta + click** on a pickable block toggles it. The capture listener runs before
    `onSelect`, and it stops the click.
  - **Escape** with a pick clears it before the single-selection Escape runs.
  - **`onEmpty`** clears the pick.
  - **On each draw**, `keepPickable(model)` runs first, and the draw passes `picked: pick.ids`.
  - **The hint** shows `PICK_HINT(n)` while n > 0, and `MAP_HINT` otherwise.
  - **CSS:**
    - `.map-band { position: absolute; left: 0; top: 0; width: 1px; height: 1px; transform-origin: 0 0; background: var(--route-soft); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--route) 40%, transparent); pointer-events: none; z-index: 3; }`
    - Reduced motion: no fade.
- [ ] **Step 4: Run** all frontend tests. Expected: PASS.
- [ ] **Step 5: Commit** — "Pick several outside servers with a band or Shift-click"

### Task 3: Group drag onto the gateway

**Files:**
- Modify: `src/kitden/web/static/js/gateway-drag.js` (`DRAGS.group`, `pressGrip`)
- Modify: `src/kitden/web/static/js/map-drag.js` (`liftGhost` reused; stack layers added by the group begin)
- Modify: `src/kitden/web/static/style.css` (`.res.ghost.stack` or `.block-ghost.stack` layers, `.ghost-count`, `div.map.lifting .block.selected { opacity: .4 }`)
- Test: `tests/frontend/gateway.test.mjs` (the `dragMap` harness)

**Interfaces:**
- Consumes: `pick.ids`, `clearPick()` from Task 2; `dropBody(row, view)`, `addToTray`,
  `inAddZone`, `liftGhost`, `flyGhost`, `pageBox`.
- Produces:
  - `DRAGS.group = { still: true, begin: beginGroup, over: overGroup, drop: dropGroup }`.
  - `movingOn()` returns no `drop` for a group drag.

- [ ] **Step 1: Failing tests** (built on `dragMap()`, with `pick.ids` set first)

```js
test('pressing a picked server drags the whole pick: one ghost with a count, the gateway lights', ...);
// Assert:
// - drag.kind is 'group';
// - the ghost has class 'stack' and a '.ghost-count' child with text '2 servers';
// - the glance holds 'gateway:kitden' and 'addslot:servers';
// - the map box has class 'lifting'.
test('a drop on the gateway adds one gateway.move per picked server, in pick order, and clears the pick', ...);
// Assert:
// - tray.rows bodies equal [dropBody(rowA), dropBody(rowB)];
// - pick.ids is empty;
// - the ghost flew to the gateway box.
test('a miss or Escape flies the ghost back and keeps the pick', ...);
test('a server the tray refuses stays outside; the others go in', ...);
// Queue a refused preview for the 2nd body. Assert:
// - one row is in the tray;
// - the refusal reason is in tray.refused.
test('with one server picked, or a press on an unpicked server, today\'s single drag runs and the pick clears', ...);
```

- [ ] **Step 2: Run** `node --test tests/frontend/gateway.test.mjs`. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - `pressGrip`:
    - `block.grip && pick.ids.has(block.id) && pick.ids.size > 1` → `startDrag(event, block, "group", onStart)`;
    - a grip press on an unpicked block clears the pick first.
  - `beginGroup`:
    - `liftGhost` of the pressed node;
    - add class `stack` and the pill `el("span", "ghost-count", plural(n, "server", "servers"))`;
    - the map box gets `lifting`;
    - glance `[gateway, ...addCard]`;
    - set `drag.line` as `beginAdd` does.
  - `overGroup`: as `overAdd`, but it does not redraw for a slot.
  - `dropGroup`:
    - If open and the tray is free, fly the ghost onto the gateway's page box (`ONTO_SLOT`).
    - Then, for each picked row in pick order, `await addToTray(dropBody(row, view))`.
    - Then `clearPick()` and redraw.
    - Otherwise fly it back (`BACK_HOME`).
    - Every end removes `lifting`.
  - The rows: `model.blocks.find(b => b.id === id).row`.
- [ ] **Step 4: Run** all frontend tests. Expected: PASS.
- [ ] **Step 5: Commit** — "Drag several picked servers onto the gateway"

### Task 4: Docs, roadmap, and a look

**Files:** `docs/design.md` (Gateway drag rows; the hint; Controls; the motion table), `ROADMAP.md`.

- [ ] **Step 1:** Add a "Pick several servers" row and a "Drag a pick" row to design.md in the
  style of the "Drag a server from the panel" row. Use the exact values from this plan's Global
  Constraints. In ROADMAP, mark Part 2 done under the 2026-11-01 design.
- [ ] **Step 2: Full checks.** `uv run pytest -q && uv run ruff check . && node --test tests/frontend/*.test.mjs`. Expected: all pass.
- [ ] **Step 3: Look** in the sandbox at http://127.0.0.1:47977.
  - Run a band over the four outside servers.
  - Shift-click one off.
  - Drag the rest onto the gateway, then Apply.
  - Check both themes, a narrow window, and reduced motion (no flights).
  - A real drag needs the owner's hand; the browser tool cannot run one. Say so if it was not
    seen.
- [ ] **Step 4: Commit** — "Describe picking and group drag"
