# Phase 4B: Gateway drags, views and the last Gateway notes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Gateway page finishes matching the owner's mockup and requests: the three drags (a server into the gateway, a server onto a client, a client onto the gateway), "N more" that pages in place, Map ↔ List and find as in the mockup, a project switch that changes the map in place, the dot grid and a calm block spotlight, and every Gateway note carried from Phases 1–4A.

**Architecture:** One drag engine in `gateway-drag.js` on top of `map-view.js` (`hold`, `letGo`, a temporary wire, drop targets, a tip), each drag ending in `addToTray` with an existing change body (`gateway.move`, `gateway.move_out`, `setup_server.register` / `.update` / `.enable`). Paging lives in `map.js` (the model picks the page) with `gateway.js` holding which page each group shows. The dot grid is a canvas in the page shell driven by one module; the spotlight is CSS custom properties set from one passive pointermove.

**Tech Stack:** plain ES modules, one CSS file, node's test runner with each file's fake DOM; pytest for page-word and contrast pins.

**Spec:** master plan `docs/superpowers/plans/2026-10-24-mockup-alignment.md` Phase 4 Tasks 4.7–4.10 and every open "Carried from Phase 1/2/3/4A" note under Phase 4; decisions D9, D12, D14, D15, D28 and the owner's requests of 2026-10-25 recorded in Tasks 4.7, 4.9 and 4.10; `docs/mockup/gateway-notes.md` §6 (drags), §7 (Map ↔ List, find, project switch), §8 (page head and hint line); `docs/mockup/motion-spec.md` M1–M6; `docs/mockup/kitden-motion.html` (`dragStart`, `wireStart`, `dropIn`, `setView`, `swap`, `filter`, `project`, `dots`).

## Decisions

- **One drag engine.** Pointer events with capture on the pressed block, a 5 px start threshold, no HTML drag and drop. A drop only adds a tray row. A drop on nothing, back home, over the floating Details panel or over the dock glides home in 220 OUT3 and leaves the tray as it was. Escape and pointercancel do the same.
- **Refused drops say why before the drop** when the page knows: the tip shows the reason in its plain look, the target does not light, and on release the block goes home and the target shakes (380). Reasons the page knows: a client that already has a server of that name, a client not on this Mac, a client whose `kitden` entry comes from a plugin (for connect). Anything only the server knows is refused when the row is added, as today.
- **A server moving into the gateway leaves its place** (Task 4.7 (1)): while its row waits it is drawn once, as the preview block in its gateway group; the Outside list closes up and a server hidden behind "N more" moves up; its client's dotted line runs to the preview block. Taking the row out glides it back.
- **"N more" pages in place** (Task 4.9): five a page; the press folds the five shown away (180 IN3) and unfolds the next five (as a server's tools: 120 OUT3, 15 ms apart); the caption names the page ("Remote · 6–10 of 12"); on the last page the block says "Show the first 5" and goes back to the first page. A search match, an arrival, a selection or a moving server on another page brings its page. The List no longer opens from "N more".
- **The dot grid shows on every place**, under the page column below the top bar (Task 4.10). The block spotlight covers map blocks and Overview cards, at the calmer values of Task 4.10. No Rich link motion.
- **Gateway hint line** (§8): on the Gateway map, "Point at a link and press × to remove it · click anything for its Details · several changes wait in preview, then Apply all · drag a server onto a client"; none on the List. It stays visible under the dock, as in the mockup (the dock sits 46 px above it).
- **Link Tab order** (carried): links get two layers — the bypass lines' hits below the others in stacking, and every link in reading order for Tab (`tabindex` order by the blocks they join, top to bottom, left to right), not model order.

## Global Constraints

- `AGENTS.md` in full: simple English in code, comments and page words; tests on sandbox homes only.
- Every write is preview → Apply with a backup → verify → Undo through `src/kitden/changes/engine.py`. A drag, a press or a switch only adds a tray row (`addToTray`); nothing writes without the tray's Apply.
- Main pages show a name, the client and an action; paths, addresses and commands stay under Technical details.
- CSP stays `script-src 'self'; style-src 'self'`: no innerHTML, no inline `style=""` in strings, no `<style>`, no `cssText`; CSSOM properties and `setProperty` only. Icons through `icon()`.
- Calm motion only, from `motion.js` (`D`, `CALM`, `OUT3`, `IN3`, `SPRING`, `animateTo`, `rollTo`, `shake`); every motion has a reduced-motion path that lands at once; nothing stays at opacity 0; nothing loops.
- `docs/design.md` changes in the same commit as the page change it describes; new page words pinned in `tests/unit/test_page_words.py`; `tests/unit/test_contrast.py` keeps 4.5:1 (3:1 for edges and focus rings) in both themes.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`.
- `ROADMAP.md` gets its line in the same commit when a task changes what Kitden does. Never stage `design/`. No `git stash`. Never `pkill -f "kitden demo"`; stop only a process you started, by its pid; an owner demo may run from `/tmp/kitden-check` — leave it.
- Do not grow `gatewayTree` (gateway.js), `layoutTree` (map.js), `showDetails` (details.js), `toolsSection` (tools.js) or `mapView`'s `draw` (map-view.js): add small named helpers.
- Commit messages: a short plain subject, one to three simple lines, ending with the Co-Authored-By line of the model that wrote the commit.

## Review Focus

- A drag released over the floating Details panel, over the dock, on nothing or back home: the block goes home and the tray is unchanged. Test in Task 1.
- A server moved into the gateway, then taken out of the tray: it glides back to its own place in the Outside list and the server that moved up behind "N more" goes back behind it. Test in Task 1.
- A search match on the third page of a group: that page shows and the match lights; clearing the search keeps the page. Test in Task 4.
- A project switch while rows wait in the tray: the tray stays, every pending look (tool tags, mark rings, preview blocks, leaving links) is drawn again for the new project. Test in Task 6.
- Reduced motion with a drag, a page turn, Map ↔ List and a project switch: each lands at once, nothing left at opacity 0, the dot grid and spotlight off. Tests in Tasks 1, 4, 5, 6 and 7.

---

### Task 1: The drag engine and a server into the gateway

**Files:**
- Modify: `src/kitden/web/static/js/gateway-drag.js`, `src/kitden/web/static/js/map-view.js` (drop-target and tip helpers beside `hold` / `letGo`), `src/kitden/web/static/js/gateway.js` (the moving server drawn only in the gateway), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/map-view.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `gateway-notes.md` §6.0, §6.1; `addToTray`, `takeOut`, `inTray`, `keyFor` (tray.js); Phase 3 `rowsOnMap`.
- Produces in map-view.js: `tip(text, { on })` / `untip()` (the `.dragtip` pill: 11 px, `--panel` fill, line edge, shadow; on = select fill, accent edge and text; placed at the block's top left + (6, −28)), `lightTarget(id)` / `unlightTarget()` (`.drop`: accent edge, select fill, scale 1.05 in 260 spring), `homeIn(id, ms)` (glide home, 220 OUT3).
- Produces in gateway-drag.js: `startDrag(event, block, kind)` used by all three drags; pointer capture on the block, 5 px threshold, a finished drag swallows its click; the pressed block keeps the .98 press scale while the pointer is down (carried note).
- Drag (1): only for an outside server the Kitden gateway can take (today's grips); the gateway lights with the slot while the block's centre is over its own group's zone; drop flies onto the slot (200 OUT3) and adds the `gateway.move` row; while the row waits the server is drawn once, as the preview block in the gateway group, the Outside list closes up (a hidden server moves up), its client's dotted line runs to the preview block; take-out glides it back (260 OUT3).

- [ ] **Step 1: Write the failing tests:** `a drag starts after 5 px and swallows its click`, `a drop over Details, over the dock, on nothing or home leaves the tray as it was and glides home in 220` (Review Focus), `the gateway lights and the slot opens over the block's own group`, `a moving server is drawn once, in the gateway, and the Outside list closes up`, `a server behind N more moves up into the freed place and back after a take-out` (Review Focus), `its client's dotted line runs to the preview block`, `the dragged block keeps its press scale while the pointer is down`, `under reduced motion the drop and the way home land at once`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** on the demo home (`docs/development.md`): drag an outside server in, release over Details, over nothing, then into the gateway; take it out from the map.
- [ ] **Step 6: Commit** — `Gateway: one drag engine; a moved server leaves its place`.

### Task 2: A server onto a client

**Files:**
- Modify: `src/kitden/web/static/js/gateway-drag.js`, `src/kitden/web/static/js/map-view.js` (a temporary wire `L~drop` that follows the block), `src/kitden/web/static/js/gateway.js` (held servers can be dragged; the move-out preview is carried to its place), `src/kitden/web/static/js/gateway-details.js` (the move-out step says "You can also drag <name> onto a client on the map."), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/map-view.test.mjs`, `tests/frontend/gateway-details.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `gateway-notes.md` §6.2, §4.2; Task 1's engine; the `gateway.move_out` body (`targets: [{client}], params: {server}`, keyed `moveout:<server>`).
- Produces: a held server in the Kitden gateway is draggable (no grip icon; the whole block); on start the tip says "Drop on a client"; over a client (its box widened 24 left, 40 right, 16 up and down) the client lights, a dashed accent wire runs from the client's right port to the block's left port and follows it, the tip says "Move into <Client>"; off the client the wire fades (240 ease-out). A drop adds the move-out row; the moving preview block is carried from the drop spot to its place in the Outside list (260 OUT3) instead of fading in. Refused before the drop: a client that has a server of that name ("<Client> already has <name>."), a client not on this Mac ("<Client> is not on this Mac.").

- [ ] **Step 1: Write the failing tests:** `a held server shows the client tip and a wire that follows it`, `a drop on a client adds one move-out row and the preview is carried to the Outside list`, `a second drop on another client replaces the row`, `a client that has the name refuses before the drop, with the reason, and shakes on release`, `the move-out step says it can be dragged`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser:** drag a server onto each client, onto one that refuses, onto nothing.
- [ ] **Step 6: Commit** — `Gateway: drag a server onto a client`.

### Task 3: A client onto the gateway

**Files:**
- Modify: `src/kitden/web/static/js/gateway-drag.js`, `src/kitden/web/static/js/map-view.js` (a wire from a port to the pointer), `src/kitden/web/static/js/gateway.js`, `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/map-view.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `gateway-notes.md` §6.3; Task 1's engine; the client's connect body from `connectAction` (gateway-details.js: `setup_server.register`, `.update`, `.enable`).
- Produces: a client that can be connected and has no connect row waiting is grabbable (cursor grab); the block does not move; after 5 px a dashed accent wire (4/4, .65) runs from its right port to the pointer, curving with handles max(18, half the x distance), the tip says "Drop on the gateway"; over the Kitden gateway (its box widened 24 each side, 16 up and down) the gateway lights, the wire snaps to its left port, the tip says "Connect <Client>"; a drop adds the connect row (Phase 4A draws its preview link); a miss fades the wire (180 CALM). A connected client, or one whose entry comes from a plugin, cannot be dragged; the plugin case says why in its tip on press ("<Client> gets Kitden from a plugin.").

- [ ] **Step 1: Write the failing tests:** `a free client draws a wire to the pointer and the gateway lights under it`, `a drop on the gateway adds one connect row`, `a miss leaves the tray as it was and the wire fades`, `a connected client cannot be dragged`, `under reduced motion the wire appears and goes at once`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser:** connect Cursor by dragging, then Apply all and Undo all.
- [ ] **Step 6: Commit** — `Gateway: drag a client onto the gateway`.

### Task 4: "N more" pages in place

**Files:**
- Modify: `src/kitden/web/static/js/map.js` (`GROUP_MAX`, the "N more" block; a page per group), `src/kitden/web/static/js/gateway.js` (the page each group shows; `pressBlock` no longer opens the List), `src/kitden/web/static/js/map-view.js` (a page turn's motion, if the existing fold/unfold helpers do not cover it), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/map.test.mjs`, `tests/frontend/gateway.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: the master plan's Task 4.9 text (the Decisions above repeat it); Task 1's moving-server rule.
- Produces: `layoutTree(model, { pages })` takes `pages: Map<groupId, number>` (0-based); a group over six shows five of page n and one block: "N more" (N = the ones after this page) or, on the last page, "Show the first 5"; the caption adds "· 6–10 of 12" while it pages. Pinned blocks (a preview, a slot) always show. A search match, an arrival, a selection or a moving server on another page sets that page. Keyboard: the block is a button; after a turn focus stays on it.

- [ ] **Step 1: Write the failing tests:** `a group of 12 shows five and 7 more`, `a press turns to the next five and the caption names them`, `the last page offers the first five again`, `a search match on page 3 shows page 3 and stays after the search` (Review Focus), `a selection or an arrival on another page brings its page`, `a preview is never behind the page`, `under reduced motion a turn lands at once`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** on the large demo (`kitden demo --size large`).
- [ ] **Step 6: Commit** — `Gateway: N more pages in place`.

### Task 5: Map ↔ List, the List rows and find

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (`modeSwitch`, `gatewayList`, `drawRows`), `src/kitden/web/static/js/store.js` and `app.js` only if the view switch needs it, `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/gateway-page.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `gateway-notes.md` §7.1–§7.3.
- Produces: Map ↔ List: the old view out 120 ease-in (opacity 0, up 4 px), the new one in 260 CALM (from 6 px down); the selection lets go. The List as §7.2 (header "Name", "Used by", "Tools"; group rows with icons; server rows with client tiles and "n of m on"; tool rows with mark, name and "Read"/"Write"; outside rows with client tile and "Move in…"), keeping "Outside the gateway · calls skip Kitden's rules" and no D23/D24 words. Find as §7.3: a block that does not match gets `opacity(.3) saturate(.5) blur(1.2px)` (300 ease), every link .2, captions stay; a focused block keeps its full ring (carried note); the search chip ("N matches") is drawn again after an in-place map redraw (carried note); a hovered lit bypass link in a search is not held at .25 (carried note).

- [ ] **Step 1: Write the failing tests:** `Map to List and back move out and in`, `the List shows the mockup's columns and rows`, `find dims, desaturates and blurs what does not match`, `a focused block keeps its ring in a search`, `the chip counts again after a tray redraw`, `a hovered bypass link in a search shows at full`, `under reduced motion the switch lands at once`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Gateway: Map and List swap, the List rows and find as in the mockup`.

### Task 6: A project switch in place

**Files:**
- Modify: `src/kitden/web/static/js/app.js` (`refreshForProject`), `src/kitden/web/static/js/panel.js` (`closeForProject`), `src/kitden/web/static/js/gateway.js` (`gatewayMap` project change), `src/kitden/web/static/js/gateway-details.js` (Show switches in place; the tool and server panels step forward), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/gateway-page.test.mjs`, `tests/frontend/panel.test.mjs`, `tests/frontend/gateway-details.test.mjs`

**Interfaces:**
- Consumes: `gateway-notes.md` §7.4; Task 3 of Phase 4A (`liven`: rolls and pops).
- Produces: on the Gateway a project switch keeps the map and changes it in place: the scope line swaps and rises (4 px, 320 CALM); each server's "n of m on" rolls and its lamp pops when it flips; each tool's tag pops; a tool whose state flips pops its mark and its link draws in (240 CALM) or undraws (380 RETRACT); open servers stay open; an open tool or server panel steps forward (130 + 220) to its new project, other panels stay; the tray stays and every pending look is drawn for the new project (Review Focus). "Show" under "Projects with a rule of their own" uses this switch and keeps the tool's panel (carried note). Other places keep today's cross-fade.

- [ ] **Step 1: Write the failing tests:** `a project switch keeps the map and its open servers`, `counts roll and flipped links draw or undraw`, `the tool panel steps forward to the new project and Show switches in place`, `rows waiting in the tray keep their looks after a switch` (Review Focus), `under reduced motion the switch lands at once`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser:** switch between All projects and two projects with a tool panel open and two rows in the tray.
- [ ] **Step 6: Commit** — `Gateway: a project switch changes the map in place`.

### Task 7: The dot grid and the block spotlight

**Files:**
- Create: `src/kitden/web/static/js/glow.js` (the dot grid and the spotlight)
- Modify: `src/kitden/web/static/index.html` (the canvas in the page column), `src/kitden/web/static/js/app.js` (start it once), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: new `tests/frontend/glow.test.mjs`, `tests/unit/test_page_words.py`, `tests/unit/test_contrast.py` if colours change

**Interfaces:**
- Consumes: the master plan's Task 4.10 text (exact values); the mockup's `dots` (kitden-motion.html ~563–572) and the `.rich .blk::before/::after` rules (~176–177).
- Produces: `startGlow(column)` — a `canvas` under the page column below the top bar (no pointer, `aria-hidden`), sized to the column (device pixels), dots on a 22 px grid within 130 px of the pointer (radius .8 + 1.5 f, pushed out up to 5 px, `--glow` at f² × .55), easing in and out by 16 % a frame through requestAnimationFrame, and no frame while the pointer rests or is away; a theme switch repaints. The spotlight: one passive `pointermove` sets `--mx` / `--my` on the map block or Overview card under the pointer; CSS draws the edge glow (130 px circle at .35) and the fill glow (200 px at .04), fading in 250 on hover. Both off under reduced motion.

- [ ] **Step 1: Write the failing tests:** `the dots draw only near the pointer and stop when it rests`, `the dots ease out when the pointer leaves`, `nothing draws under reduced motion`, `a theme switch repaints`, `the spotlight follows the pointer on a block and is off under reduced motion`; pins for the CSS values.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`** (and the "nothing loops" principle's line on the dots); run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** in both themes beside the mockup in its Rich mode, and that the page stays smooth while the pointer moves over a large map.
- [ ] **Step 6: Commit** — `The dot grid and a calm spotlight under the pointer`.

### Task 8: Landing and the last motion notes

**Files:**
- Modify: `src/kitden/web/static/js/dock.js`, `src/kitden/web/static/js/gateway.js`, `src/kitden/web/static/js/map-view.js`, `src/kitden/web/static/js/review.js` (`undoChange`), `src/kitden/web/static/js/parts.js` (`stepText`), `src/kitden/web/static/js/panel.js`, `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/dock.test.mjs`, `tests/frontend/gateway-page.test.mjs`, `tests/frontend/map-view.test.mjs`, `tests/frontend/panel.test.mjs`

**Interfaces:**
- Consumes: the carried notes (Phase 2: 4.8 entrance items; Phase 3: landing, Undo order, roll, drawer bottom; Phase 4A: list room).
- Produces: after a verified Apply all the map lands each row in tray order 60 ms apart; Undo all undoes on the map in reverse order 120 ms apart and draws a link coming back in 480 CALM; "Applying 2 of 5" rolls its step number (from step 2); the modal drawer's bottom moves with the dock's room in 200 CALM and keeps a minimum height of 240 px; the list room on Library, Changes and the Gateway List opens and closes with the panel (240 / 180); the skeleton, the error banner and the "No gateway yet" card rise like the rest of a first visit; Map → List has its rise; the head does not snap when data arrives within ~440 ms of a cold visit; design.md's "First visit" row says so.

- [ ] **Step 1: Write the failing tests** for each line above (one test per behaviour, reduced motion for each).
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Gateway: rows land in turn; the last motion notes`.

### Task 9: Keyboard and focus notes

**Files:**
- Modify: `src/kitden/web/static/js/map-view.js` (link hits in two layers and reading order), `src/kitden/web/static/js/gateway.js`, `src/kitden/web/static/js/dock.js`, `src/kitden/web/static/js/tray.js`, `src/kitden/web/static/js/review.js`, `src/kitden/web/static/js/panel.js`, `src/kitden/web/static/js/details.js`, `src/kitden/web/static/style.css`, `docs/design.md`
- Test: the frontend test file of each module touched

**Interfaces:**
- Consumes: the carried notes (Phase 2 link order; Phase 3 focus, busy, chip, quiet, row review, dock z; Phase 4A focusin, `--float-top`, Tab order, bypass keys).
- Produces: link Tab order in reading order with bypass hits below solid ones in stacking (Decisions); a focused link keeps its hit while the tray writes and the hits come back after a failed Apply (tested); a focusin scrolls a block beside the panel only for keyboard focus (`:focus-visible`); Cancel of a single move from the dock gives focus to the outside server; Apply, the toast's Undo and a link's × show they wait (`aria-disabled`, busy cursor, a title "Another change is being written.") while another change is written; `undoChange`'s tool-list branch leaves focus where it was unless it was in Details; `quiet` covers only the redraw, not the awaited read, and a read never draws old Details over a row opened meanwhile; a row's review follows a row added again under the same key; `--float-top` is placed again after a render of `#main`; the dock does not paint over the open project menu (the menu above the dock) and the sticky top bar keeps its edge; a bypass line emptied by two rows takes both rows out on click.

- [ ] **Step 1: Write the failing tests** for each line above.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Gateway: links in reading order and the last focus notes`.

### Task 10: Words, small looks and docs

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (hint line; the whole-server step's map mark; the first-run duplicate word), `src/kitden/web/static/js/gateway-details.js` (gateway card count; the disconnect note once), `src/kitden/web/static/js/dock.js` (`baseNames`; a refused add after a failed Apply keeps "Nothing was changed"; a toast during a slide-out), `src/kitden/web/static/js/review.js` (the tool list's refusal callout without paths; `takeOutButton`'s listener), `src/kitden/web/static/js/parts.js` (`setHint`), `src/kitden/web/static/style.css` (`.flag.info` on a selected row; `.btn` height beside inputs), `docs/design.md` (split "Small parts"), `ROADMAP.md`
- Test: the frontend test file of each module touched, `tests/unit/test_page_words.py`, `tests/unit/test_contrast.py`

**Interfaces:**
- Consumes: the carried notes not taken by Tasks 1–9, and §8.
- Produces: the Gateway hint line (Decisions); a whole-server "in some projects" row marks the server block with the pending project tag; a first-run "Found" client with a connect row is heard "in preview" once; the gateway card counts a server that is moving out as it leaves ("1 in the gateway · 8 outside"); a review from the gateway panel's Disconnect row says the note once; `baseNames` keeps paths with spaces whole as a base name and keeps "/command" words; the tool list's refusal callout shows base names; a refused add on a failed tray keeps the failure's words and adds the reason; a toast that comes during a row's slide-out stays; `takeOutButton` drops its listener when its review closes; `.flag.info` on a selected List row uses `--ink-2` (contrast pinned); a plain `.btn` beside a 30 px input in the Add forms is 30 px; design.md's "Small parts" is split into short paragraphs; ROADMAP's Gateway lines updated for Phase 4.

- [ ] **Step 1: Write the failing tests and pins** for each line above.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** at 1440×900 in both themes beside the Gateway frames in `design/kitden.pen` (Pencil MCP) or the mockup.
- [ ] **Step 6: Commit** — `Gateway: the last words and looks`.
