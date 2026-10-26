# Mockup alignment — Master Plan

> **For agentic workers:** this is a master plan. Before a phase is built, write its own task-by-task plan with superpowers:writing-plans (tests first, exact names), then build it with superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kitden looks, moves and behaves like the owner's motion mockup (version 11, 2026-10-24), everywhere the clients and Kitden's own rules allow it.

**Architecture:** Keep the stack. The mockup's look moves into `style.css` tokens, local font files and one icon data module. Its map behaviour moves into `map.js` (blocks that stay and move, links that take the pointer). Its preview tray needs one new backend piece: many tray requests become ONE change, so Apply all and Undo all stay all-or-nothing through the change engine. Pages then follow one by one: Gateway, Add panel, Library, Overview, Changes.

**Tech Stack:** Python 3.13, Starlette; plain ES modules, one CSS file; pytest on sandbox homes; node's test runner. New static files only: the woff2 fonts and one icon data module. No library, no bundler, no network at run time.

**Spec:** the mockup itself, `docs/mockup/kitden-motion.html` (behaviour and words), `docs/mockup/motion-spec.md` (every motion, Calm values), the frames in `design/kitden.pen` (look; the owner is moving the whole mockup there), and the owner decisions in Phase 0 below, recorded in the spec's "Owner decisions (2026-10-24, the mockup)". Older rules: `docs/superpowers/specs/2026-10-23-map-pages-design.md`, `docs/design.md`. Where they disagree with the mockup, Phase 0 says which one stands.

## Where things stand (2026-10-24, main at 0270e9f)

- Part 4 (Gateway map and list, shared pieces S.1–S.8) is built: all 11 tasks are on main, although its checkboxes are not ticked.
- Parts 5 (Library), 6 (Instructions, Overview, Changes), 7 (leftovers) and 8 are not started. This plan replaces their page work with the mockup's version. Their backend tasks stay and are reused (named per phase below).
- Already there and reusable: the change engine (all-or-nothing inside one change, progress events), connect a client (`SETUP_SERVER`), remove a server (`GATEWAY_REMOVE`), move an outside server in (`GATEWAY_MOVE`, `local_move_steps`), tool rules (`rule_steps`, `rules_steps`), plugin install and remove for Claude Code and Codex, the drag of an outside server into the gateway (`gateway-drag.js`), the one-preview review bar (`map-review.js`).

## Global Constraints

- Where a frame exists in `design/kitden.pen`, build from the frame with Pencil's design-to-code guide (Pencil MCP `read_skill` → `guide/code.md`): read the frame's nodes for exact sizes, colours (as Kitden tokens) and SVG geometry, reuse Kitden's existing parts, and compare the frame's `TakeScreenshot` with the page. The mockup decides behaviour, words and motion. No young third-party tools.

- `AGENTS.md` in full. Simple English in code, UI and docs. Tests on sandbox homes only. Dated facts about other tools.
- Every write is preview → Apply with a backup → verify → Undo through `src/kitden/changes/engine.py`. A drag, a ×, a card button or a tray row only adds a preview. Nothing writes without Apply.
- Main pages show a name, the client and an action. Paths, addresses, commands and file lines stay under Technical details.
- CSP stays `script-src 'self'; style-src 'self'` (`src/kitden/web/security.py:24-26`). So: no inline `style=""` in HTML strings, no `<style>` blocks, no `cssText`. Set styles with classes, `el.style.prop = …` or `animate()`. Nothing loads from another site.
- Calm motion only (owner, 2026-10-24). Rich, "Slow ×4", "Fail next Apply", "Replay" and the "Demo data" chip are study controls and are not built.
- Every motion has a reduced-motion path that lands on the same final state at once. Use the mockup's `D(ms)` idea: one helper returns 0 under `prefers-reduced-motion`.
- `docs/design.md` changes in the same commit as the page change it describes. Every new page word is pinned in `tests/unit/test_page_words.py`. `tests/unit/test_contrast.py` keeps 4.5:1 in both themes.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`.
- When a phase changes what Kitden does, update `ROADMAP.md` in the same change.

## Review Focus

- A tray with two changes to the same file (Cursor `mcp.json`, Codex `config.toml`): both apply as one change; neither goes stale. Test in Phase 3.
- A tray request that clashes with one already there (remove GitHub, then turn off a GitHub tool): refused when it is added, with the reason, never at Apply. Test in Phase 3.
- Apply all fails on the last step: every file is back, the bar says "Nothing was changed", the map stays in preview. Test in Phase 3.
- Reduced motion: every state is reached at once and nothing is left at opacity 0 (the mockup itself had this bug in a capture). Test in Phase 2.
- A drag released over nothing, over the Details panel or back at home: the block goes home and the tray is unchanged. Test in Phase 4.

---

## Phase 0: Owner decisions (before any code)

The mockup breaks several written rules. Each line gives the rule, what the mockup does, and the recommended call. The owner confirms or changes each one. Then the answers go into the spec and `docs/design.md` in one docs commit.

### A. Look: the mockup wins (recommended for all)

| # | Today's rule (where) | Mockup | Recommended |
|---|---|---|---|
| D1 | System fonts (`docs/design.md:117`, spec Non-goals) | Inter + JetBrains Mono | Ship `InterVariable.woff2` (~344 KB) and `JetBrainsMono[wght].woff2` (~111 KB) in `static/fonts/` with their OFL texts |
| D2 | 3 inline SVGs and text glyphs | ~40 lucide icons from a CDN | One icon data module (`static/js/icons.js`) with only the used icons (lucide is ISC), drawn by `icon()` with createElementNS, no innerHTML |
| D3 | `--wire` as rgba, `--lamp-*` names, 24 px buttons | The mockup's `:root` tokens and sizes | The mockup's tokens, renamed into Kitden's names; the contrast test decides any change |
| D4 | `--spring` "no overshoot" (`docs/design.md:161`) | SPRING overshoots 3.4 % (press, switch knob, ports, badge, tick) | Allow it for those small parts only |
| D5 | Details is a docked 320 px column; "a drawer has one motion" (`docs/design.md:60, 197`) | Panel floats over the map; skeleton 160 ms, then children rise | Floating panel, as the mockup; keep the narrow layout under 1024 px |
| D6 | Dashed amber ring = Unknown; grey ring = Via Claude Code (`docs/design.md:91`) | Dashed accent ring = in preview; grey ring = outside the gateway | Mockup meanings. Grey ring = "works, but not through Kitden here" (covers Via Claude Code too). Unknown = solid amber ring |
| D7 | Pinned words: "Read only", "State", "Use the shared rule…", "Outside the gateway · calls skip Kitden's rules", "by the shared rule" | "Reads only", "Permission", "Use all projects", "· drag one in", "in every project" | Mockup words, except the ones in group C |
| D8 | Amber elbow for links that skip the gateway (`docs/design.md:40`) | Grey dots 1.5/4 at .8, amber only on hover or when picked | Mockup |
| D9 | Unfold at most 300 ms (spec S.4) | 170 + 120 + 15 per tool | Mockup timing, no cap |

### B. Behaviour: the mockup wins, the docs change (recommended)

| # | Today's rule | Mockup | Recommended |
|---|---|---|---|
| D10 | One preview at a time (`docs/design.md:83`, commit 99e66be) | A tray holds many changes; Apply all; Undo all | Tray, built as ONE combined change (Phase 3) |
| D11 | "The full review is one click away" (spec Anti-goals) | No "Show changes" in the tray | Each tray row keeps a small "Show changes" that opens the full review in Details |
| D12 | A press on a preview block opens the review (`docs/design.md:83`) | A click takes it out of the tray | Mockup; the review stays reachable through D11 |
| D13 | "Turn on in one project…" | Checkboxes, several projects at once | Mockup ("Turn on in some projects…"); each ticked project is one tray row |
| D14 | "No drag to connect" (spec:66); grips only where the gateway can take a server | A free client drags a wire to the gateway; every server has a grip | Allow the client wire. Grips stay only where the gateway can take the server; a refused drop says why |
| D15 | Project switch closes the panel and cancels a preview (`docs/design.md:112`) | Panel steps forward, tray stays | Mockup; tray rows show their project |
| D16 | Error: red edge, "Try again" asks for a new preview | Accent edge, shake, "Try again" | Mockup look; "Try again" still makes a fresh preview (truth first) |
| D17 | Tool switches never flip on the Gateway (`docs/design.md:113`) | Server panel has a switch per tool and "Whole server" | Mockup; a switch only adds a tray row (pending look), never writes |
| D18 | "No action today's Gateway page has is lost" (spec 4.4) | Panels drop strict mode, writing-tools batch, Refresh, Put back, Keychain, Move all, Add another gateway, Set up / Turn on / Open app | Keep every one of them, under the panel's Technical details or a "More" row |
| D19 | Narrow layout, "N more", first-run slot, registered gateways | Not in the mockup | Keep them, styled with the new tokens |

### C. Truth and safety: the product rule stays (recommended)

| # | Mockup | Why it can't ship as drawn | Recommended instead |
|---|---|---|---|
| D20 | Each tray row gets a check as its step ends | "Truth first": a check only after the server says verified | Rows spin; all checks appear together when the combined change is verified |
| D21 | Changes: "Redo" re-applies with no preview | Breaks preview → Apply | "Redo…" adds a fresh preview to the tray |
| D22 | Overview "Fix…" / "Connect…" apply in place | A write without preview | The card button adds a preview to the tray; Apply from the tray |
| D23 | "Sign in needed", "Sign in…", "Signed in there" | The gateway has no OAuth (S1 waits); client token stores are undocumented; `claude mcp list` contacts every server | No sign-in words until S1 |
| D24 | "Running", "New tools: stay off until you turn them on", "not tested with Kitden", tool counts on outside or marketplace servers | Kitden does not know these | Only what Kitden knows: today's words and counts |
| D25 | A skill turned off inside a plugin ("3 of 4 on", plugin→skill ×) | No client can (see Hard parts) | Plugin shows "4 items"; no switch or × on an item inside a plugin; its panel says "Follows its plugin" |
| D26 | Add a plugin to Cursor, remove it from Cursor | Cursor installs plugins only from its UI (see Hard parts) | Cursor is never a drop target for plugins; the drag says why |
| D27 | "AGENTS.md · Codex → imports docs/development.md" | Only Claude Code follows `@` imports | Import links only from Claude Code files |
| D28 | Rich mode, marching dashes, beams | Owner chose Calm; "nothing loops" (`docs/design.md` Principle 2) | Not built |

- [x] **Step 1:** Owner answers D1–D28: all accepted (2026-10-24), "as close to the mockup as possible, and not fragile".
- [x] **Step 2:** The answers are in the spec ("Owner decisions (2026-10-24, the mockup)"); `docs/design.md` points to this plan. Each phase rewrites its own `docs/design.md` sections and page-word pins with its code.
- [x] **Step 3:** The reference is tracked in `docs/mockup/` (the mockup, its client images, the motion spec). `design/` stays the owner's and is never staged.

---

## Phase 1: Look and shared tokens

**Files:** `src/kitden/web/static/style.css`, `static/index.html`, new `static/fonts/` and `static/js/icons.js`, `static/js/motion.js`, `static/js/dom.js`, `static/js/parts.js`, `src/kitden/web/security.py` (`font-src 'self'` if needed). **Mockup:** `:root` tokens and the CSS from `.app` to `.btn`, `.seg`, `.lamp`, `.mark`, `.port`, `.chip`, `.tg`; motion-spec M0.

- [x] **Task 1.1 Fonts and icons.** `@font-face` for both fonts; `icon(name, size)` in `dom.js` draws an `<svg>` from the icon data module (`static/js/icons.js`) with createElementNS, no innerHTML. Test: every icon name used in `static/js` exists in the module.
- [x] **Task 1.2 Tokens.** Colour, line, wire, faint, warn, out, shadow, select, preview fill/line, ok-fill, on-ok, dark and light. Test: `test_contrast.py` passes; new pairs added.
- [x] **Task 1.3 Motion tokens.** In `motion.js`: `CALM = 'cubic-bezier(.2,.8,.2,1)'`, `SPRING` (the `linear()` curve with its cubic-bezier fallback), `OUT3`, `IN3`, `DRAW`, `RETRACT`, `D(ms)` (0 under reduced motion), `animateTo(el, keyframes, {dur, delay, ease})` (the mockup's `A()`), `roll(el, value)` (number roll 140 + 200), `rise(els, {delay, step, y})`. Test: node tests for `D()` under reduced motion and for `roll` landing on the final text.
- [x] **Task 1.4 Shell.** 16 px gutter on `--out`; app frame with 12 px corners; rail 148 px with icons, 38 px items, logo 28, nav marker glides 300 CALM; top bar 66 px with "Project **All projects** ˅" and the search field; hint line at the page bottom. Keep Rescan and the agents link. **Mockup:** `.rail`, `.nav`, `.topbar`, `glideNav`, `go()`. Done when a screenshot at 1440×900 on the demo home matches frame M1·1 within the text and data differences.
- [x] **Task 1.5 Small parts.** Buttons (padding 7×12, press .97 SPRING, primary), pill/segmented control (glide 280 CALM), chip, lamp and mark (6 px, colour 400 ease, pop 2.2 → 1), port (9 px ring), switch (knob 340 SPRING, pending look), checkbox and radio. Test: a node test that `switchHTML(state)` returns the on, off and pending looks.
- [x] **Task 1.6 Project picker.** Menu grows 180 CALM from the button, icons, accent "N own rules", a check on the current one, the name rolls after a pick. **Mockup:** `projBtn` click, `setProject`.

## Phase 2: Map engine

**Carried from Phase 1:** `animateTo` swallows a throwing `animate()`: report or narrow it before the map leans on it. `.page` has `max-width: 1180px`, so the head's Map | List pill sits about 76 px left of the mockup's right edge; settle the page and map width here.

**Files:** `static/js/map.js` (core), `static/js/gateway.js` and `library.js` callers, `tests/frontend/map.test.mjs`. **Mockup:** `MapView` (`place`, `move`, `link`, `draw`, `unlink`, `dash`, `undraw`, `drawIn`, `focus`, `unfocus`, `showX`, `hoverLink`); motion-spec M1–M3.

- [x] **Task 2.1 Blocks that stay.** Replace the full rebuild (`map.js:410-485`, `replaceChildren`) with keyed blocks moved by `transform`; `relayout()` tweens moved blocks 260 OUT3; new blocks enter, leaving blocks leave 180 IN3. Test: drawing twice keeps the same DOM nodes for unchanged ids.
- [x] **Task 2.2 Entrance.** Each block and caption rises 6 px, 260 OUT3, 22 ms apart in layout order; a link's opacity follows the lower of its two blocks; title, lede and scope rise 260, 120 and 180 ms after. Test: under reduced motion every block ends at opacity 1.
- [x] **Task 2.3 Layout numbers.** Clients and gateway start at y 124; pitch 70/72; server 170×60, tool 200×34, outside block with grip; captions with icons; "Tools" caption only while a server is open. Keep "N more" and the narrow layout.
- [x] **Task 2.4 Links take the pointer.** Each removable link gets a 14 px invisible hit stroke (off below .5 opacity); hover = accent 2.4 px (bypass: amber); the 16 px × sits at half the path's length, appears 120 CALM, 240 ms grace, jumps with no motion. Remove `pointer-events:none` and `aria-hidden` from the link layer (`map.js:442-444`) and give each hit path a label for keyboard and screen readers. Test: `midPoint(path)` and the grace timer.
- [x] **Task 2.5 Link motion.** Draw-in from start port (CALM, 240–280 by kind); preview link = accent dashes 4/4 at .65; leaving = muted dashes at .4; blend between them 300 CALM ("8 0" for solid); on Apply a dashed link fades 240 ease-out and is removed; undraw 380 RETRACT. Bypass shape: right angles, channels 16/24/+8, corner radius 8 (`map.js:203-210`).
- [x] **Task 2.6 Focus and select.** One active element; a second click or a click on empty map lets go; off-path blocks `opacity .4 saturate(.6)` and links `.16`, 300 ease; path overlay 2.1 px accent fades in 180 CALM; hover preview on clients and outside servers while nothing is selected.

## Phase 3: Preview tray (backend + page)

**Carried from Phase 2:** an empty-map click or a second click lets go with `closePanel`, which also cancels a review Details hold (the move's "Show changes", a × review); with the tray, clear only the map's selection while a review shows. `letGoOnMap` during a write clears the selection while Details wait. Undo draws a link back in 260 ms where the mockup says 480 (the engine cannot tell the cause; the tray can pass it). The review floats over the lowest blocks at a 900 px window. After an applied removal, focus falls to `#main`.

**Phase plans:** backend `2026-10-24-align-phase3-tray-backend.md` (Tasks 3.1–3.3, built on its own branch), page `2026-10-25-align-phase3-tray-page.md` (Tasks 3.4–3.6).

**Files:** new `src/kitden/changes/batch.py`, `src/kitden/web/app.py` (route), `src/kitden/changes/engine.py` (progress per row), new `static/js/tray.js`, `static/js/panel.js` (toast), `static/js/map-review.js` (replaced by the tray), tests `tests/unit/test_batch.py`, `tests/frontend/tray.test.mjs`. **Mockup:** `tray`, `dock`; motion-spec M4. **Decisions:** D10, D11, D12, D20.

- [x] **Task 3.1 One change from many requests.** `POST /api/batch/preview` takes `{"requests": [ {id, kind, …} ]}` and returns one previewed change with `rows: [{id, title, detail, project, steps: [int]}]`. It uses each request's existing step builder and the engine's own merge. Tests: two requests on the same Cursor `mcp.json` apply without going stale; a failing last step puts every file back.
- [x] **Task 3.2 Refuse clashes at add time.** `POST /api/batch/check` with the current rows plus the new one returns `{ok}` or `{reason}` (same entry twice, one entry inside another, two registered gateways). The tray shakes the new row and shows the reason. Test: "remove GitHub" + "turn off a GitHub tool" is refused with a plain reason.
- [x] **Task 3.3 Apply all and Undo all.** Apply and Undo use today's `change_action` verbs on the combined change. Progress events carry the row id, so each row spins in turn; checks show only on `verified` (D20). Undo all is one undo; rows undo in reverse order on the map, 120 ms apart.
- [x] **Task 3.4 Tray UI.** One change: title, detail, Cancel, Apply. Two or more: "N changes in preview", list rows (dashed preview look, row ×, "Show changes"), Cancel all, Apply all with "Applying i of N", meter (480 ease-out per step), spinner. Failure: accent edge, shake 380, "Nothing was changed", Try again (fresh preview). Bar in 220 CALM, resize 200, row in 200 with 80 delay, out 160. **Mockup:** `tray.render`, `tray.apply`.
- [x] **Task 3.5 Toast in the dock.** Bottom left, "Applied N changes" + "Undo all" (+ an optional second button), 9 s green life bar that pauses under the pointer, leaves 160. Replaces the centred 6 s toast (`panel.js:229-268`).
- [x] **Task 3.6 Wire every action to the tray.** Details buttons, switches, ×, drags and cards add tray rows instead of opening a review. A click on a preview block or link takes its row out (D12). Remove the one-preview rule (`review.js:234-253`, `map-review.js:24`).

## Phase 4: Gateway page

**Carried from Phase 2:**
- `blockParts` in map-view.js still checks kind `"client"`; the block looks replace it.
- Leaving block nodes stay focusable for their 180 ms fade; give `.leaving` nodes `tabindex="-1"`.
- Link Tab order follows the model (a server's tool links before its gateway link), and hits never re-sort; sort them by reading order.
- A hovered, lit bypass link in a search stays at 0.25 once bypass links take the pointer; add a hover rule.
- 4.8: the skeleton, the error banner and the "No gateway yet" card show without a rise; Map → List has no rise; the head snaps when data arrives within ~440 ms of a cold visit; the "First visit" row in design.md.
- 4.7: a dragged block keeps the 0.98 press scale while the pointer is down.

**Carried from Phase 3:**
- The map's per-row landing in tray order, 60 ms apart, and Undo all's reverse order, 120 ms apart; Undo's 480 ms link draw-in (the tray can pass the cause). Today the page is drawn again once after the reload.
- The review floats over the lowest blocks at a 900 px window.
- The step number in "Applying 2 of 5" changes without rolling.
- The modal drawer's bottom jumps with no transition when the dock's bar or toast comes and goes, and it has no minimum height in a short window.
- The dock (z 22) paints over the sticky top bar and the project menu in a short window.
- While the tray writes, every link loses its hit for a few seconds (keyboard focus on a link hit is dropped); no test yet that the hits come back after a failed Apply.
- Cancel of a single move from the dock hands focus to `#main` (the old bar gave it to the outside server).
- Apply, the toast's Undo and a link's × give no sign when pressed while another change is written; they do nothing.
- The search chip's count can go stale when the tray redraws the map in place during a search.
- `undoChange`'s tool-list branch moves focus to `tools.flipped` whatever had focus.
- `quiet` stays set across `detailsAgain`'s awaited re-read (a docked-column press in that window skips `rememberOpener`), and a re-read can draw old Details over a row opened during the await.
- A row's review keeps the row it was opened with: a row added again under the same key shows its old part until the review is opened again.
- With the dock empty the modal drawer's bottom is 25 px from the window, not 16 px (`style.css` ~771: `max(16px, var(--dock-room, 0px) + 25px)`); a default of `-9px` fixes it, or Task 4.3's floating panel replaces the rule.
- `#said` sits outside the `aria-modal` drawer, so the tray's spoken words may go unheard while the modal drawer is open (Task 4.3's floating panel may drop `aria-modal`).
- `baseNames` (dock.js) leaves part of a path that holds a space and drops the slash of a "/command"; the tool list's refusal callout (review.js ~252) still shows the full words.
- A refused add on a tray whose Apply failed shows "Could not prepare the preview" and loses the "Nothing was changed" line.
- A toast that comes during a row's 180 ms slide-out is replaced by the bar (`slideOut` draws in full); `takeOutButton` keeps its `onTray` listener until the next tray change after its review closes.

**Carried from Phase 1:**
- `gateway.js` has its own local `icon()` and `ICONS` (~line 543). Remove them before importing `icon` from `dom.js`, or the module fails to parse.
- Docked Details: the opaque top bar now shows a 17 px canvas notch beside the column, and the column covers the frame line. The floating panel (D5) fixes it.
- In light, `.flag.info` text on a selected row (`--route-soft`) is 4.45:1. Give it `--ink-2` there.
- The hint line has no fill and shares the bottom band with the review bar or tray. Decide whether a hint hides while a tray shows; set each page's hint text when its features exist.
- The Details project choice row is always `aria-selected`, so it shows the tint and ring though it picks nothing. The tool picker's own look replaces it.
- A plain `.btn` is 33 px beside 30 px inputs in the Add forms.
- Split the dense "Small parts" paragraph in `docs/design.md`.

**Carried from Phase 4A** (the final review, for Phase 4B; all done in Phase 4B):
- Find dims a focused block's ring with the block.
- A focusin scrolls the block beside the panel also on a mouse press, not only from the keyboard.
- The list room snaps when the panel opens or closes.
- `--float-top` goes stale after a redraw of `#main`: call `placeSoon` after a render.
- Link Tab order: bypass hits come first today; every bypass hit should be a Tab stop.
- The move-out preview fades in; it should be carried there, with drag (2).
- A bypass line emptied by two rows takes out only one key.
- The whole-server step ("in some projects…" for a server) leaves no mark on the map.
- "Show" under "Projects with a rule of their own" closes Details and opens the tool again in that project; it should switch in place.
- A first-run "Found" client with a Connect row is heard "in preview" twice (the state word and the wait words).
- The gateway's Details card still counts a server that is moving out ("2 in the gateway"), while its block says "1 server".
- A review from the gateway panel's Disconnect row says the disconnect note twice (the row's note and the client's line).

**Notes from Phase 4B** (plan `2026-10-25-align-phase4b-gateway-drags-views.md`, done 2026-10-26; drag (4) of Task 4.7 is Phase 5). Left for later:
- A long `.block-stat` or `.block-tag` can still run out of its block; the name and words lines end in "…".
- While blocks move, a link's × can jump from one free stretch of the link to another.
- At three digits the Overview label in the rail gives way with "…" (the count stays whole; the rail keeps 148 px).
- The Map | List pill takes a key while another project is read; the map and the List do not.
- The add-gateway form closes on a quiet redraw (after a project switch or an Apply).
- Links that run behind a gateway block look as if they enter it; routing them around blocks is a design question for the owner.
- Kitden cannot yet disconnect a client from a registered gateway (Obot, MetaMCP) or forget a registered gateway (owner, 2026-10-26).

**Files:** `static/js/gateway.js`, `gateway-details.js`, `gateway-drag.js`, `style.css`; backend `src/kitden/changes/actions.py`, `local_gateway/views.py`, client adapters. **Mockup:** `Gateway` (`spec`, `layout`, `toggle`, `select*`, `*Panel`, `wire*Panel`, `linkRemove`, `linkClick`, `linkPanel`, `dragStart`, `wireStart`, `connect`, `setConn`, `project`, `listHTML`, `filter`); motion-spec M2, M3, M5, M6. **Frames:** M1·1–M4·4 in `design/kitden.pen`.

- [x] **Task 4.1 Block looks.** Server: icon, sans name, lamp + "n of m on", ports, count badge that hides when open; gateway: house, lamp, stats with icons and rolling numbers; tool: round mark, "N projects" tag also under All projects; outside block: grip, grey-ring lamp; preview look (dashed edge, × on hover); leaving look (.45, dashed edge). Fix `gateway.js:212, 254, 537-541`, `style.css:525, 546, 550-553, 578`.
- [x] **Task 4.2 Server unfold and fold.** (Its motion was built in Phase 2; the ports came in Phase 4A.) Tool links draw 170 CALM from the right port, tools fade in 120 OUT3, 15 ms apart (D9: no cap); fold shrinks back 180 IN3; other blocks glide 260. (`map.js:47-49`.)
- [x] **Task 4.3 Details panels.** Floating panel (open 240 CALM from x+28, close 180, skeleton 160, children rise 260 / 20 ms, step forward/back 130 + 220). Server: facts, "Whole server" + one switch per tool, "Move out of the gateway…". Tool: "Projects with a rule of their own" with Show, "Turn … for all projects…", "Turn … in some projects…" (checkbox step, D13). Client: Through Kitden, On its own, Library counts, Connect…/Disconnect…. Gateway: facts, a Connect…/Disconnect… row per client, "Add a server…". Connection: the two ends and its remove action. Every Technical details row from today stays (D18).
- [x] **Task 4.4 Disconnect (backend).** A `client.disconnect` action = the `kitden` entry's `REMOVE_DIRECT` step through each adapter's `remove_step`. Test on all three sandbox clients; Undo puts the entry back.
- [x] **Task 4.5 Move out to one client (backend).** `gateway.move_out` = `put_back_steps` + `remove_server_steps` as one change. Its preview warns when a Keychain secret would be written into the client file as a plain value. Test: Apply then Undo restores both files.
- [x] **Task 4.6 Several projects at once.** `rule_steps` takes a list of projects, or one tray row per project (choose in the phase plan; the tray makes both all-or-nothing).
- [x] **Task 4.7 The four drags.** (1) Outside server into its group: the gateway lights (`.drop`, scale 1.05) with the slot; the block flies into the slot. While the move waits in the tray the server is drawn only once, as the preview block in the gateway (as the mockup's `dropIn`, gateway-notes §6.1): it leaves the Outside list, which closes up, so a server hidden behind "N more" moves up into the freed place; its client's dotted line runs to the preview block, because the client still calls it directly until Apply. Taking the row out glides it back (owner, 2026-10-25). (2) Gateway server onto a client: client lights, dashed wire `L~drop`, tip "Move into <client>". (3) Free client onto the gateway: dashed wire follows the pointer, gateway lights, tip "Connect <client>" (D14). (4) Marketplace row onto the map: Phase 5. Drop on nothing → home 220. Pointer events with capture, 5 px start threshold, no HTML drag and drop.
- [x] **Task 4.9 "N more" in place (owner, 2026-10-25; not in the mockup).** A group over six on the map shows five and "N more"; a press no longer opens the List. Instead the five shown fold away (180 IN3) and the next five unfold in the same place (as a server's tools do); the caption says which ones show ("Remote · 6–10 of 12"). On the last page the block offers the first five again. A search match, an arrival, a selection or a dragged server on another page brings its page. The List stays one click away through Map | List.
- [x] **Task 4.10 The dot grid under the page (owner, 2026-10-25: the one Rich effect taken into Calm, an exception to D28).** As the mockup's `dots` (kitden-motion.html ~563-572, motion-spec M0 "Rich-only effects"): a canvas under the page column, below the top bar, takes no pointer; while the pointer moves over the column, dots on a 22 px grid within 130 px of it show (radius .8 + 1.5 f, pushed out up to 5 px, colour `--glow` at f² × .55, f = 1 − distance / 130) and fade in or out by 16 % a frame; nothing draws while the pointer rests or is away, so nothing loops. Off under reduced motion; a theme switch repaints it; the canvas follows the column's size. Also the spotlight on blocks and cards (owner, 2026-10-25: "calmer than the mockup"): under the pointer a block's edge takes a soft glow (130 px circle of `--glow`, at .35 where the mockup has .85) and its fill a faint one (200 px circle at .04 where the mockup has .08), fading in 250 on hover and out on leave; set by CSS custom properties from one passive pointermove, no inline style strings; off under reduced motion. Not built, as before (owner, 2026-10-25): every Rich link motion — beams, marching dashes, the Rich draw-in, ripples, sparks, sheen, blur.
- [x] **Task 4.8 Map ↔ List, find, project switch.** View switch: out 120 ease-in, in 260 CALM (`store.js:188-195`). Find: dim to 35 %, blur 1.2 px, desaturate. Project switch in place: scope rises, counts roll, marks pop, links draw or undraw, panel steps forward (`app.js:120`, `panel.js:159`).

## Phase 5: Add panel and marketplace servers

**Files:** backend `gateway.add` and `/api/market-servers` (Part 5 Task 10, reused), `static/js/gateway-add.js` (new), `style.css`. **Mockup:** `openAdd`, `resRow`, `preview`, `resDrag`, `commitAdd`; motion-spec M6.

**Carried from Phase 3:** "In preview" is missing on the add-gateway form (`addForm`), the tool and server project choice (`gateway-details.js` ~451, ~503) and the Connect clients form (~716): none says it while its row waits in the tray. Give each the `previewButton` look (details.js).

- [ ] **Task 5.1 Backend.** List marketplace MCP servers; `gateway.add` writes the gateway entry for all projects. It refuses OAuth servers, SSE/WebSocket and any `${…}` value, with a plain reason; such rows show greyed with the reason. No tool counts (D24).
- [ ] **Task 5.2 Panel.** "+ Add" opens the panel: search, All/Community/Team pill, rows grouped by source, "In the gateway" rows greyed. A click adds a preview block in its group (slot, link fade, tray row). A drag flies a ghost card onto the map; the gateway and the slot light; a drop over the panel cancels.

## Phase 6: Library

**Carried from Phase 2:** `map-view.js` reads `afterOldPage()` from motion.js to delay its entrance after a place change; give `draw` an `enterDelay` option when the Library reuses `mapView`.

**Carried from Phase 3:** "In preview" is missing on the Library's add choice and the `offer.js` add forms: neither says it while its row waits in the tray. Give each the `previewButton` look (details.js).

Reuses Part 5 backend Tasks 1, 2, 7 (local settings, plugin parts, `skill.rule`) and Part 6 Tasks 1–3 (imports). **Files:** `static/js/library.js`, `details.js` (move to `detailsCard`), `style.css`, `app.js:35` (`MAP_PAGES` adds `library`). **Mockup:** `Library` (`plugin`, `pluginPanel`, `wirePlugin`, `add`, `pickClient`, `dropWhy`, `dragStart`, `select`, `skill`, `file`, `imp`, `removeFrom`); motion-spec M7.

- [ ] **Task 6.1 Two tabs and the map.** "Plugins and skills" | "Instructions" pill; Map | List; lede "Follow the source. Connect only what you need." + scope bar. Map: Clients → source captions → plugin cards (180×60) and slim skill rows → Inside column. A plugin nobody has shows only in the add panel (spec call #3 stays unless the owner says otherwise).
- [ ] **Task 6.2 Select, unfold, Details.** Click a plugin: select, open Inside, light the path, Plugin Details ("Add to <client>…" with a checklist, several clients → tray rows; "Turn off for all projects…"). Skill on its own: "Turn off for all projects…" / "in some projects…" via `skillOverrides` (Claude Code) and `[[skills.config]]` (Codex). Items inside a plugin: no switch (D25).
- [ ] **Task 6.3 Drag a plugin onto a client.** Client lights + dashed wire; a blocked client (already has it, Cursor per D26) gives the reason and shakes.
- [ ] **Task 6.4 Link ×.** client→plugin = remove from that client (`plugin.remove`; note that Claude Code's reinstall on Undo loses the plugin's saved options); client→skill = turn off; no × inside a plugin; instruction links read-only.
- [ ] **Task 6.5 Instructions map.** Clients → files → imports; import links only where the client follows them (D27); file lines under Technical details.
- [ ] **Task 6.6 List view.** Keep Differences and "Add missing" per the 2026-10-23 ruling, in the new look.

## Phase 7: Overview and Changes

**Carried from Phase 3:** the Changes page names a change of many tray rows "batch …": name each row by its steps (`changeTitle(part)`) before any release from this branch. The server keeps "New change" as the request title of a row's first preview.

Reuses Part 6 backend Task 5 (cards with `icon`, `name`, `clients`). **Files:** `static/js/overview.js`, `changes.js`, `review.js` (undo toast), `src/kitden/views/overview.py`. **Mockup:** `Overview`, `Changes`; motion-spec M8.

- [ ] **Task 7.1 Overview.** "Your setup, connected." + counted lede + scope; cards with icon tile, name, one line, client tiles, one button (adds a tray preview, D22); hover a card focuses the mini-map; "Your setup" mini-map with foot "N projects · N have their own rules"; notes fold open as sentences. Fix the mockup's collapse jump: collapse the card and skip FLIP.
- [ ] **Task 7.2 Changes.** Today / Yesterday groups with a rail and a dot per row; row = time, title, client tiles, lamp + word, Undo; undone row gets the strike line and muted title; first row selected with its panel open; Details card (Project, State, Backup, Takes effect, client tiles, history arrows, Technical details); "See it on the map"; Undo toast "Undid “…”. The backup is back in place." with "Redo…" as a fresh preview (D21).

## Phase 8: Check and finish

**Carried from Phase 2:** Safari's `:focus-visible` on SVG link paths; the Gateway view transition in both themes; the 39-server long-task check with a selection and a glance; a timer backstop so a draw lands even if frames stall while the page is visible.

**Carried from Phase 3:** README still describes the old one-change review (README.md ~169). ROADMAP.md needs the tray line once the owner settles their own edit to it.

**Carried from Phase 1:** `docs/images/how-it-works-dark.svg:47` still uses the old amber #E0A347. The active-option ring in the project menu also shows on the picked row when the menu opens by mouse; the mockup has no ring (owner to judge).

- [ ] **Task 8.1 Side-by-side check.** For every frame in `design/kitden.pen`: run Kitden on the demo home (`docs/development.md`), set the same state, compare at 1440×900 in both themes. Use the Pencil MCP: `browser` `load-page` on the local Kitden URL and `return-screenshot`, next to `TakeScreenshot` of the frame. Note: Pencil's browser node swallows synthetic clicks, so set states through the page's own functions or check interactions in a normal browser.
- [ ] **Task 8.2 Motion check.** Walk motion-spec M1–M8 with the page at "slow" (a dev-only `?slow=4` URL flag that multiplies `D()`; not shown in the UI) and confirm each duration and curve.
- [ ] **Task 8.3 Docs.** `docs/design.md` sections, README screenshots, `ROADMAP.md`, release notes (`docs/development.md`). Tick the Part 4 checkboxes that are done.

---

## Hard parts (tell the owner)

1. **One skill off inside a plugin — not possible.** Claude Code: "Plugin skills are not affected by `skillOverrides`. Manage those through `/plugin` instead." (code.claude.com/docs/en/skills, checked 2026-10-24). Codex `[[skills.config]]` covers local skills only. Cursor has no per-skill switch. Only the whole plugin turns off.
2. **Cursor plugins — no official way to write them.** Cursor installs plugins only from its Customize UI and keeps them in its own database (cursor.com/docs/plugins, checked 2026-10-24). Its import of Claude Code plugins is one all-or-nothing setting. A folder in `~/.cursor/plugins/local` is a developer path that needs a window reload; not recommended for the product.
3. **Sign-in states — not now.** The gateway cannot hold OAuth servers yet (S1), and the clients do not document where their tokens live.
4. **Apply all — doable, with limits.** It must be one combined change. Some pairs are refused (same entry twice, two registered gateways), and the tray says so when the second is added. Undo of a Claude Code plugin removal reinstalls it and loses its saved options.
5. **Imports — Claude Code only.** Codex's AGENTS.md has no import syntax; Cursor reads `@file` on demand. The mockup's Codex import link would be false.
6. **Small costs:** about 455 KB of fonts; a moved-out server's Keychain secret ends up as plain text in the client file (the preview must say so); servers that use OAuth, project files or plugin roots cannot move into the gateway, so their blocks have no grip.

## Order and size

| Phase | Depends on | Size |
|---|---|---|
| 0 Decisions | — | S (owner) |
| 1 Look | 0 | M |
| 2 Map engine | 1 | L |
| 3 Tray | 0 | L (backend + page) |
| 4 Gateway | 2, 3 | L |
| 5 Add panel | 3, 4 | M |
| 6 Library | 2, 3 | L |
| 7 Overview, Changes | 3 | M |
| 8 Check | all | M |

Phases 1 and 3 can run side by side (page vs backend). Phases 6 and 7 can run side by side after 4.
