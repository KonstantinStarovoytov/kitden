# Phase 3 page: the preview tray in the dock — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every change waits in one tray at the bottom left of the page until Apply all, as in the mockup: rows come and go, Apply all writes them as ONE change, and a toast in the same dock offers Undo all.

**Architecture:** A new `tray.js` holds the rows and talks to the tray backend (`POST /api/batch/preview`, then the change's own `apply`, `cancel`, `undo`); it draws nothing. A new `dock.js` draws the tray bar in `#dock` from the tray's state, with the M4 motion; a new `toast.js` draws the toast in the same place. `review()` stays the one way a page asks for a change, but it now adds a tray row; the full review in Details becomes the read-only "Show changes" of one row. `map-review.js` (one preview on the map) goes; the Gateway map draws every tray row instead.

**Tech Stack:** plain ES modules, one CSS file; node's test runner with each file's own fake DOM; Python 3.13 + Starlette for one small backend step; pytest on sandbox homes.

**Spec:** master plan `docs/superpowers/plans/2026-10-24-mockup-alignment.md` (Phase 3, Tasks 3.4–3.6, its "Carried from Phase 2" note; decisions D10, D11, D12, D15, D16, D20, D22), `docs/mockup/motion-spec.md` M4, the `dock` and `tray` objects in `docs/mockup/kitden-motion.html`, the backend plan `docs/superpowers/plans/2026-10-24-align-phase3-tray-backend.md` (its API), and the M4 frames in `design/kitden.pen` when the Pencil MCP can read them.

## Decisions

- **One tray for the whole app.** It lives in `#dock` and stays across places and project switches (D15); each row keeps the project it was asked in. Cost if wrong: one line to cancel it on a place change.
- **Every `review()` adds a row.** "Add missing…" still opens its chooser in Details first (the server has no change before something is ticked); its button "Add to preview" adds the row.
- **A row's words come from its own part of the preview:** title `changeWords(part, body).title`, line `outcomeLine(part)` or the caller's note. The request's `title` is the row's last shown title, and `"New change"` before its first answer. The server only keeps it (and names an earlier row by it in a clash reason); Phase 7's Changes page names rows by their steps.
- **Each row keeps its own `picked` project** (Task 1), so a row asked in one project keeps its words after the person picks another.
- **A refused add never joins.** The tray stays as it was; the bar shakes and says why until the next action. A refused re-preview (after a row is taken out, or Try again) leaves the rows with no change: Cancel all and Try again.
- **Apply waits while a preview is on its way** (`aria-disabled`), so Apply always writes what the bar shows.
- **Rows spin, then all check together (D20).** A row spins from its first finished step (the first row from the start) until the whole change is `verified`. On a failure no row gets a ×: the engine does not say which step failed.
- **Try again makes a fresh preview of the same rows (D16)**; the person presses Apply again.
- **"Show changes" (D11):** one row has a small text button "Show changes" under its line; in the list each row has a `file-text` icon button labelled "Show changes: <title>". Both open the row's full review in Details with no Apply of its own ("Take it out" and Close), so one change never has two Apply buttons.
- **Undo all is one Undo** of the combined change (`undoChange`). The map's per-row landing (tray order, 60 ms apart), Undo's reverse order (120 ms apart), Undo's 480 ms link draw-in and the review floating over the lowest blocks at a 900 px window are Phase 4; here the page is drawn again once after the reload.
- **Focus stays where it was when a row is added**; the bar's line is a status and is read out. Focus moves only to Try again or Open Changes after a failure.
- **The toast is its own small module** (`toast.js`, importing only dom.js and motion.js), so panel.js can re-export it without an import cycle through review.js.

## Global Constraints

- `AGENTS.md` in full: simple English in code, comments and page words; tests on sandbox homes only, never the real home.
- Every write is preview → Apply with a backup → verify → Undo through `src/kitden/changes/engine.py`. A button, switch, ×, drag or card only adds a tray row. Nothing writes without Apply.
- Main pages show a name, the client and an action; paths, addresses and commands stay under Technical details. Tray words name no path, address or command.
- CSP stays `script-src 'self'; style-src 'self'`: no innerHTML, no inline `style=""` in strings, no `<style>`, no `cssText`. Icons come from `icon()` in `dom.js` (the names in `icons.js`; `file-text`, `x`, `rotate-cw`, `check`, `circle-check`, `undo-2`, `arrow-right`, `plug`, `plus`, `folder`, `toggle-right` are there).
- Motion uses `motion.js` (`D`, `CALM`, `DRAW`, `animateTo`, `rollTo`). Every motion has a reduced-motion path that lands on the same final state at once; nothing stays at opacity 0.
- `docs/design.md` changes in the same commit as the page change it describes. New page words are pinned in `tests/unit/test_page_words.py`; `tests/unit/test_contrast.py` keeps 4.5:1 in both themes.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`.
- Never stage `ROADMAP.md` (it holds the owner's own edit), `design/` or `docs/research/`. No `git stash`. Never `pkill -f "kitden demo"`; stop only a process you started, by its pid.
- Commit messages: a short plain subject, one to three simple lines, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- Two adds in quick succession, the second before the first answers: one change holds both rows, and the server keeps no previewed change from the first ask (it is cancelled). Test in Task 2.
- A row asked with project A picked, then B picked and another row added: the first row still says A's place. Tests in Tasks 1 and 2.
- A row taken out while Apply is pressed: Apply waits until the new preview answers, so the row is never written. Test in Task 2.
- Apply all ends `stale`: "Nothing was changed", the rows stay, Try again asks a fresh preview and does not apply it. Tests in Tasks 2 and 3.
- Escape, Close or other Details never take a row out of the tray. Test in Task 6.

---

### Task 1: Each row keeps its own project

**Files:**
- Modify: `src/kitden/changes/batch.py` (`requests_in`), `src/kitden/web/app.py` (`batch_preview`)
- Test: `tests/unit/test_batch.py`, `tests/unit/test_api_batch.py`

**Interfaces:**
- Produces: a request may carry `picked` (a project id); `requests_in` returns `picked` as that string, or `None` when it is missing or not a non-empty string. `batch_preview` calls `_review(part, made, _picked(request) if request["picked"] else _picked(body))` for each row; the combined `change.target` keeps the body's `picked`.

- [ ] **Step 1: Write the failing tests**
  - `test_requests_in_keeps_each_picked` (test_batch.py): requests `a` with `"picked": "p1"`, `b` without, `c` with `"picked": 7` → `[r["picked"] for r in requests_in(body)] == ["p1", None, None]`.
  - `test_each_row_keeps_the_project_it_was_asked_in` (test_api_batch.py): set up as `test_a_server_the_picked_project_defines_itself_goes_to_every_other_project` in `tests/unit/test_api_changes.py` (website gets its own Claude Code `github`; import its `_home` and `_app_client`). Requests: `a` removes the user `github` from Claude Code with `"picked": website["id"]`; `b` removes the user `neon` from Codex with no `picked`; no body `picked`. → `rows[0]["target"] == {"scope": "others", "project": website["path"], "others_unchanged": False}`, `rows[1]["target"]["scope"] == "all"`. Cancel the change at the end.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_batch.py tests/unit/test_api_batch.py -q` — expected: FAIL on the two new tests.
- [ ] **Step 3: Implement** the `picked` field and its use in `batch_preview`.
- [ ] **Step 4: Run** all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Tray: each row keeps the project it was asked in`.

### Task 2: The tray's state

**Files:**
- Create: `src/kitden/web/static/js/tray.js`
- Modify: `src/kitden/web/static/js/review.js` (move `changeOutcome`, `readChange`, `readOutcome`, `ENDED`, `LOST` into `tray.js`; review.js imports and re-exports `changeOutcome`)
- Test: `tests/frontend/tray.test.mjs`

**Interfaces:**
- Consumes: `postJson`, `getJson` (api.js); `busy`, `setBusy`, `state` (store.js); the `kitden:progress` document event (`detail`: `{ id, done, total, row }`); the backend's `POST /api/batch/preview` (200: the change with `rows: [{ id, kind, title, detail, project, steps, target, after, undo_note, left_out?, align? }]`; 422: `{ detail, row }`).
- Produces (tray.js imports only api.js and store.js, so it never joins an import cycle):
  - `export const tray` — `{ rows, change, phase, refused, failure, done, total, stale }`. `phase`: `"idle"`, `"asking"`, `"ready"`, `"applying"`, `"applied"`, `"failed"`. A row: `{ id, key, body, note, icon, picked, title, detail, project, part, status }`, `status` `""`, `"busy"` or `"done"`. `refused`: `{ reason }` or null. `failure`: `{ state, error }` or null (state null when the end is not known).
  - `PENDING_TITLE = "New change"`.
  - `keyFor(body) -> string`: `switch:<targets[0].item>` for `plugin.enable` / `plugin.disable`; `rule:<server>/<tool>@<project or "">` for `gateway.rule`; `strict:<server>` for `gateway.strict`; `align:<project>` for `project.align`; otherwise `JSON.stringify` of `{ action, targets, params }` with object keys sorted.
  - `iconFor(body) -> string`: `"folder"` when `params.project` is set or the action is `project.align`; `"x"` for `mcp.remove_direct`, `plugin.remove`, `skill.remove`, `gateway.remove`; `"toggle-right"` for `gateway.rule`, `gateway.rules`, `gateway.strict`, `plugin.enable`, `plugin.disable`, `setup_server.enable`; `"arrow-right"` for `gateway.move`, `gateway.put_back`, `gateway.keychain`; `"plug"` for `gateway.connect`, `gateway.switch`, `setup_server.register`, `setup_server.update`; `"plus"` for the other adds; else `"file-text"`.
  - `inTray(key) -> boolean`; `partOf(change, answerRow) -> object` (the change with the row's `kind` as `action`, only its `steps` by index, and its `target`, `after`, `undo_note`, `left_out`, `align`).
  - `setTrayWords(fn)`: `fn(part, body, note) -> { title, detail }`, set once by dock.js. `onTray(fn) -> unsubscribe`: `fn(tray)` after every change of state.
  - `addToTray(body, { key = keyFor(body), note = null, icon = iconFor(body) } = {}) -> Promise<boolean>`; `takeOut(key) -> Promise<void>`; `cancelTray() -> Promise<void>`; `tryAgain() -> Promise<void>`; `applyTray() -> Promise<void>`; `endApplied() -> void`; `checkTrayStale() -> Promise<void>`; `changeOutcome(id, verb)` (moved, unchanged).
- Behaviour the tests pin:
  - Each ask (add, take out, try again, cancel) bumps one counter; an answer to an older ask is dropped and its change cancelled on the server. A new preview replaces the old change only once it answers; the old one is then cancelled.
  - A request is `{ id, kind: body.action, title: row.title || PENDING_TITLE, detail: row.detail || "", targets, params, picked: row.picked }`; `row.picked` is `state.project || null` when the row is added.
  - An add while `phase === "applying"` or `"applied"`, or while `busy.change`, does nothing and answers false. A row with the same key is replaced and goes to the end.
  - `applyTray` runs only from `"ready"`; the first row is `"busy"` at once, and each progress event for the change sets `done`, `total` and its `row`'s status to `"busy"`. `verified` → every row `"done"`, `phase "applied"`, `tray.change` is the verified change. Any other end → `phase "failed"`, rows `""`, `failure` set. `setBusy(true)` while it runs, `false` after.

- [ ] **Step 1: Write the failing tests** in `tests/frontend/tray.test.mjs` (fake `globalThis.fetch` that records each URL and body and answers from a queue; a fake `document` with `addEventListener`, `removeEventListener` and a `fire(type, detail)` helper; `globalThis.matchMedia = () => ({ matches: false })`; reset `tray` with `cancelTray()` and a fresh queue between tests):
  - `keyFor names a switch by what it switches`: `keyFor({ action: "plugin.disable", targets: [{ item: "i1" }] }) === keyFor({ action: "plugin.enable", targets: [{ item: "i1" }] })`; two `gateway.rule` bodies for `files/read_file` with states on and off share a key; `project: "p1"` and none differ; two bodies whose params differ only in key order share a key.
  - `iconFor picks the mockup's icon`: `gateway.remove` → `"x"`, `gateway.rule` with `project` → `"folder"`, `gateway.move` → `"arrow-right"`, `plugin.install` → `"plus"`.
  - `an add previews every row as one change`: two adds → the second POST to `/api/batch/preview` carries both requests in order, the first with its shown title; `tray.phase === "ready"`, `tray.rows.map((r) => r.title)` are the words from `setTrayWords`; the first change is cancelled (`/api/changes/c1/cancel` asked).
  - `an older answer is dropped and its change cancelled`: the first add's answer arrives after the second add's → `tray.change.id` is the second's; `/api/changes/<first>/cancel` asked.
  - `a refused add does not join`: 422 `{ detail: "Choose a server in the Kitden gateway.", row: "r2" }` → rows unchanged, `tray.change` unchanged, `tray.refused.reason` is the detail, `addToTray` answered false; the next add clears `refused`.
  - `a row keeps the project it was asked in`: `state.project = "p1"`, add; `state.project = "p2"`, add → the second POST's requests have `picked` `"p1"` then `"p2"`.
  - `taking out the last row cancels the change` and `taking out one of two previews the rest`: the POST after `takeOut` has only the other request; `applyTray()` called before that answer does nothing (no `/apply` asked).
  - `apply names each row as its steps end`: fire `kitden:progress` `{ id, done: 1, total: 3, row: "r2" }` → `tray.done === 1`, `r2` `"busy"`; answer `verified` → both rows `"done"`, `phase "applied"`, `busy.change === false`.
  - `a stale apply keeps the rows`: answer `{ id, state: "stale" }` → `phase "failed"`, `failure.state === "stale"`, rows kept with status `""`; `tryAgain()` POSTs a fresh batch preview and ends `"ready"`, with no `/apply` asked.
  - `an add while applying does nothing`: during apply, `addToTray(...)` answers false and asks nothing.
  - `checkTrayStale marks a stale preview`: GET answers `{ id, state: "previewed", stale: true }` → `tray.stale === true`; a ready tray with a fresh read stays false.
- [ ] **Step 2: Run** `node --test tests/frontend/tray.test.mjs` — expected: FAIL (module not found).
- [ ] **Step 3: Implement** `tray.js` and move `changeOutcome` with its helpers out of `review.js` (review.js re-exports it; panel.js's re-export keeps working).
- [ ] **Step 4: Run** all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Tray: one tray of rows, previewed as one change`.

### Task 3: The tray bar in the dock

**Files:**
- Create: `src/kitden/web/static/js/dock.js`
- Modify: `src/kitden/web/static/index.html` (`<div class="dock" id="dock"></div>` inside `.hint-dock`), `src/kitden/web/static/js/app.js` (call `initDock()` once at start), `src/kitden/web/static/js/review.js` (export `showEffect`), `src/kitden/web/static/js/map-review.js` (imports `outcomeLine` and `writingLine` from dock.js until Task 5 deletes it), `src/kitden/web/static/js/motion.js` (`shake`), `src/kitden/web/static/style.css`, `docs/design.md`, `tests/unit/test_page_words.py`
- Test: `tests/frontend/dock.test.mjs`, `tests/frontend/motion.test.mjs`, `tests/frontend/review.test.mjs` (its `outcomeLine` and `writingLine` tests move to dock.test.mjs)

**Interfaces:**
- Consumes: Task 2's `tray`, `onTray`, `setTrayWords`, `takeOut`, `cancelTray`, `applyTray`, `tryAgain`, `endApplied`; `changeWords`, `stoppedWords`, `reloadAll` (review.js); `stepText` (parts.js); `icon` (dom.js).
- Produces in dock.js:
  - `outcomeLine(change)` and `writingLine(steps)`, moved from map-review.js unchanged.
  - `rowWords(part, body, note) -> { title, detail }`: `changeWords(part, body).title`; `outcomeLine(part)`, else `note`, else `""`.
  - `barWords(tray, { onMap }) -> { head, line, cancel, apply, applyWaits, retry, changes }` — the pure words of the bar; exact words below.
  - `initDock()`: `setTrayWords(rowWords)`, subscribes `drawTray` to `onTray`.
  - `appliedToast(done)` (`done` = `{ change, rows }`, kept before `endApplied()`): one row → `changeWords(row.part, row.body).done` with "Undo"; many → `"Applied <n> changes"` with "Undo all"; both call `undoChange(change)` (review.js) on the combined change, through panel.js's `toast(text, onUndo, { ok: true, label })`.
  - review.js exports `showEffect` (today private) for the page's redraw after Apply.
  - In motion.js: `shake(node)` — `translateX` 0 → −7 → 6 → −3 → 0 px, `D(380)`, ease-out; nothing under reduced motion.
- Words (`barWords`), `n` = rows:
  - ready, one row: head = its title, line = its detail, cancel "Cancel", apply "Apply". Many: head `"<n> changes in preview"`, line `"Nothing is written until you Apply."` plus `" Click one on the map to take it out."` when `onMap`, cancel "Cancel all", apply "Apply all".
  - asking: as ready, `applyWaits: true`. Stale: line `"Settings changed since this preview."`, apply `"Preview again"`.
  - refused add: as ready, line = the reason; with no rows: head `"Could not prepare this change"`, line = the reason, cancel `"Close"`, apply null.
  - applying: line = `writingLine(change.steps)`, apply = `stepText("Applying", done, total)`, `applyWaits: true`.
  - applied: apply `"Applied"` (one) or `"All applied"` (many).
  - failed after Apply: `stale` → head `"Nothing was changed"`, line `"Settings changed since this preview."`, apply `"Try again"`; `restored` with every file put back → head `"Nothing was changed"`, line `"The change did not check out. Kitden put the files back."`, apply `"Try again"`; `restored` otherwise → head `"Not everything was put back"`, line `"Check Changes before trying again."`, `changes: true`, apply null; unknown end → head `"Could not confirm the result"`, same line, `changes: true`, apply null. A refused re-preview → head `"Could not prepare the preview"`, line = the reason, apply `"Try again"`. Cancel says "Cancel" or "Cancel all" by `n`. `changes` adds an "Open Changes" button.
- The bar (`drawTray`): `section.bar.tray` (`.many` for 2+, `.err` after a failure), `role="region"`, `aria-label` = head. One row: `.tx` with `b`, `small[role=status]` and the small "Show changes" text button; `.acts` with Cancel and `button.btn.primary.apply` (`span.lbl`, the `arrow-right` icon, `i.meter`). Many: `.tray-head` (`b` with `span.num`, `small[role=status]`), `ul.tray-list` of `li[data-key]` (`.ti` row icon 13, `.tt` with `b` and `small`, the `file-text` button, `.ts` status, `button.x` "Take it out of the preview"), `.acts`. While Apply runs: Cancel and every × `disabled` (opacity .5 and .35), Apply `aria-disabled="true"`, the icon becomes the `rotate-cw` spinner (`.spin`), the meter scales `done/total` in `D(480)` ease-out; `.ts` shows the spinner for `"busy"` and a green `check` for `"done"`. Applied: Apply gets `.ok` (green fill, 180 ms ease) and the `check` icon draws in `D(300)` DRAW; after `D(200)`, `reloadAll()`, `showEffect()`, `endApplied()`, then `appliedToast` replaces the bar after `D(n × 60)`. Failure: `.err`, `shake`, focus on Try again (or Open Changes). A refused add: `shake` and the reason in the line until the next action.
- Motion (M4, Calm): bar in 220 CALM (opacity 0, translateY 18 px scale .97 → none); size change 200 CALM (old to new width and height); new row 200 CALM after 80 (opacity 0, translateY 10 px scale .98 → none); count rolls with `rollTo` while 2+; row out 180 ease-in (translateX 18 px, then removed); last row out or Cancel all: bar out 160 ease-in (translateY 10 px). Going from one to two rows rebuilds the bar and both rows enter.
- CSS (from the mockup, in Kitden tokens): `.dock` absolute, left 0, bottom 46 px inside `.hint-dock`, `pointer-events: auto`, z-index above the map, `max-width: calc(100% - 44px)`; `.bar` 380 px wide, padding 14/14/14/16, 10 px corners, `--panel` fill, `--line` edge, `--shadow`; `.bar.err` accent edge; `.tray-list` max-height 212 px, scrolls; rows: dashed `--preview-line` edge on `--preview-fill`, 8 px corners, padding 7/6/7/10; `.btn .meter` 2 px, white at .75, from the left; `.btn.ok` `--ok-fill` with `--on-ok` text; `.spin` turns in .8 s linear (none under reduced motion).

- [ ] **Step 1: Write the failing tests**
  - In `tests/frontend/dock.test.mjs` (fake DOM as in `gateway-details.test.mjs`):
    - `barWords says one change by its title`, `barWords counts many changes`, `barWords waits while a preview is asked` (`applyWaits`), `barWords counts the steps while Apply runs` (`"Applying 2 of 5"`), `barWords says Nothing was changed only when true` (each failed case above, exact words), `barWords shows a refusal with no rows` (`"Could not prepare this change"`, cancel `"Close"`, apply null), `barWords says the preview went stale`.
    - `outcomeLine` and `writingLine` keep their tests from `review.test.mjs` (move them here).
    - `appliedToast says Applied 3 changes with Undo all`, `appliedToast says one change's own words with Undo`.
    - `drawTray draws one row with Show changes and Apply`, `drawTray draws a list with a take-out button per row` (labels "Take it out of the preview" and "Show changes: <title>"), `drawTray disables Cancel and × while Apply runs`, `under reduced motion the bar and rows end at opacity 1` (no animation left at opacity 0).
  - In `tests/frontend/motion.test.mjs`: `shake does nothing under reduced motion`.
  - In `tests/unit/test_page_words.py`: pin `"Applied "`, `"Undo all"`, `"changes in preview"`, `"Nothing is written until you Apply."`, `"Click one on the map to take it out."`, `"Take it out of the preview"`, `"Show changes"`, `"Cancel all"`, `"Apply all"`, `"All applied"`, `"Could not prepare the preview"`, `"Not everything was put back"`, `"Kitden put the files back."` in `dock.js`; `id="dock"` in index.html; `.dock {` and `.tray-list {` in style.css.
- [ ] **Step 2: Run** `node --test tests/frontend/dock.test.mjs tests/frontend/motion.test.mjs` and `uv run pytest tests/unit/test_page_words.py -q` — expected: FAIL.
- [ ] **Step 3: Implement** dock.js, `shake`, the dock element, CSS and `initDock()`.
- [ ] **Step 4: Update `docs/design.md`**: a "Preview tray" paragraph (what it holds, one and many, Show changes, Apply all and its count, the words of each end, focus) and the M4 rows in the motion table.
- [ ] **Step 5: Run** all four checks — expected: PASS.
- [ ] **Step 6: Commit** — `Tray: the bar in the dock, one change or many`.

### Task 4: The toast in the dock

**Files:**
- Create: `src/kitden/web/static/js/toast.js`
- Modify: `src/kitden/web/static/js/panel.js` (drop its toast; re-export toast.js's `toast` and `hideToast`; the focus trap reads the toast from `#dock`), `src/kitden/web/static/js/dock.js` (the bar and the toast take turns in `#dock`), `src/kitden/web/static/index.html` (remove `#toast`), `src/kitden/web/static/style.css` (remove the centred toast), `docs/design.md`, `tests/unit/test_page_words.py`
- Test: `tests/frontend/toast.test.mjs`, `tests/frontend/panel.test.mjs`

**Interfaces:**
- Produces in toast.js (imports only dom.js and motion.js): `toast(text, onUndo, { ok = false, label = "Undo", extra = null } = {})` — same call as today's, so every caller keeps working; `extra` is `{ label, run }` for one more button. `hideToast()`.
- The toast: `div.toast` in `#dock`, `role="status"`; the `circle-check` icon in green only when `ok`; the text; `extra`; the Undo button with the `undo-2` icon 13; `i.life` (2 px `--ok` line at .7 along the bottom). It replaces whatever the dock shows, at once. In: 200 CALM (opacity 0, translateY 14 px → 0). Life: `scaleX` 1 → 0 toward the left, linear, 9000 ms (not shortened under reduced motion); the pointer or focus on it pauses the life, leaving resumes it; at the end it leaves in 160 ease-in (translateY 10 px). A new tray row while the toast shows replaces it at once.

- [ ] **Step 1: Write the failing tests** in `tests/frontend/toast.test.mjs`:
  - `the toast replaces the bar and offers Undo`; `the life pauses under the pointer and resumes after` (the fake animation's `pause`/`play` were called); `an error toast has no check`; `under reduced motion the toast still lives 9 s`.
  - In `tests/frontend/panel.test.mjs`: replace the tests of the old centred toast with `panel.js re-exports the dock's toast`.
  - In `tests/unit/test_page_words.py`: `id="toast"` no longer in index.html.
- [ ] **Step 2: Run** the node tests and the page-word test — expected: FAIL.
- [ ] **Step 3: Implement** toast.js and switch panel.js, dock.js and the shell to it.
- [ ] **Step 4: Update `docs/design.md`**: the toast lines (where, life, pause, Undo all).
- [ ] **Step 5: Run** all four checks — expected: PASS.
- [ ] **Step 6: Commit** — `Tray: the toast lives in the dock`.

### Task 5: The Gateway map draws the tray

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (`gatewayTree`, `LINK_HOOKS`, `pressBlock`, `redrawMove`), `gateway-drag.js` (a drop adds a row), `review.js` (remove `setMapReview`, `mapReview` and their uses in `review` and `showApplied`), `panel.js` and `app.js` (drop their map-review.js imports: `leaveMap`, `mapPreview`, `mapReviewLeft`), `docs/design.md`, `tests/unit/test_page_words.py`
- Delete: `src/kitden/web/static/js/map-review.js`
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/review.test.mjs`

**Interfaces:**
- Consumes: `tray`, `onTray`, `addToTray`, `takeOut`, `inTray`, `keyFor` (Task 2).
- Produces:
  - `gatewayTree(view, { …, rows = [] })`: `rows` are the tray rows (`{ key, body }`). For each `gateway.move` into the Kitden gateway: a preview block `preview:<name>` in its group with a preview link, and its outside row hides its direct lines, as today's one `preview`. For each `gateway.remove`: the gateway → `held:kitden:<server>` link gets `leaving: true`. For each `gateway.rule` with `state: "off"` on a tool of a held server: that server → tool link gets `leaving: true`. The `preview` option goes.
  - A press on a preview block, or a click on a preview or leaving link, takes its row out (D12). The × of a link whose row is in the tray takes it out; otherwise it adds `linkRemoval(...).body` with icon `"x"`. The map is drawn again on every tray change (`onTray`) while the Gateway shows.
  - The drag (`gateway-drag.js`) adds the move with `addToTray(body)` in place of `previewOnMap`; the "Drop to add" slot shows until the row answers.
- Carried from Phase 2 (master plan): `letGoOnMap` during Apply clears the selection while Details wait; after an applied removal, focus goes to the gateway block, not `#main`.
- Until Task 6, Details still open their own review with its own Apply; only the map's previews (×, drag, preview block) go to the tray here.

- [ ] **Step 1: Write the failing tests** in `tests/frontend/gateway.test.mjs`:
  - `two moves in the tray show two preview blocks`; `a removal in the tray makes its link leave`; `a tool turned off in the tray makes its link leave`; `a press on a preview block takes its row out`; `a click on a leaving link takes its row out`; `the × of a link in the tray takes it out, else adds it`; `a drop adds a move to the tray`; `focus goes to the gateway after an applied removal`.
  - Move any test of map-review.js that still matters to `tray.test.mjs` or `dock.test.mjs`; delete the rest with the module.
- [ ] **Step 2: Run** `node --test tests/frontend/gateway.test.mjs` — expected: FAIL.
- [ ] **Step 3: Implement**, then delete `map-review.js` and every import of it; update the page-word pins that read it (`panel()`, `reviews()` and the tests around line 1842 of `test_page_words.py` read dock.js in its place).
- [ ] **Step 4: Update `docs/design.md`**: the "Review bar" paragraph becomes the tray on the map (rows draw preview blocks and leaving links; a press takes a row out); the "Map preview" motion row names the tray.
- [ ] **Step 5: Check in a real browser** on the demo home (`docs/development.md`; stop only the server you started): add three rows (two link ×, a drag), take one out from the map, Apply all, then Undo all from the toast.
- [ ] **Step 6: Run** all four checks — expected: PASS.
- [ ] **Step 7: Commit** — `Tray: the Gateway map shows every row`.

### Task 6: Every change goes to the tray

**Files:**
- Modify: `src/kitden/web/static/js/review.js` (`review`, `showReview`; remove `applyChange`, `showApplied`, `checkStale`, `setMapReview` and the one-preview turns), `panel.js` (closing Details never cancels a tray row; ⌘/Ctrl Enter presses the tray's Apply when it is ready), `details.js` and `tools.js` (switch pending looks), `app.js` (the stale check after a rescan asks `checkTrayStale`), `docs/design.md`, `tests/unit/test_page_words.py`
- Test: `tests/frontend/review.test.mjs`, `tests/frontend/panel.test.mjs`, `tests/frontend/details.test.mjs`, `tests/frontend/gateway-details.test.mjs`

**Interfaces:**
- Consumes: `addToTray`, `takeOut`, `inTray`, `keyFor`, `tray`, `applyTray`, `checkTrayStale` (Task 2).
- Produces:
  - `review(body, { note = null, back = null } = {})`: `project.align` with no `chosen` asks `/api/changes/preview` and shows its chooser in Details as today, whose button says "Add to preview" and adds the row with `params.chosen`; every other body is `addToTray(body, { note })`. `back`, when given, is called with `{ queued: true }` after the add (and `{ error }` after a refusal), so a tool list draws its switch in the pending look.
  - `showRowReview(row)`: `showReview(row.part, row.body, row.note)` without Apply and without the "⌘ Enter to apply" note; its footer has "Take it out" (`takeOut(row.key)`, then Details close) and "Close". A project.align row shows its chooser; a changed tick adds the row again (same key, so it is replaced).
  - A switch whose key is in the tray shows its pending look (`.pending`) and a press takes the row out. `previewButton(label, body, { note, look })` in details.js: a Details button that adds `body`; while `keyFor(body)` is in the tray it says `"In preview"` and is disabled. details.js and gateway-details.js use it for every button that called `review(body)`.
- Remove: the review branch of `cancelPreview` (a row's review must never cancel the tray's change on the server), `applyChange`, `showApplied`, `lockReview`, `resetApply`, `APPLY_KEY`, `checkStale`, `staleCheckWanted`, and review.js's `appliedToast` (dock.js has its own, Task 3).
- Carried from Phase 2 (master plan): a click on empty map or a second click clears only the map's selection while a row's review shows in Details.

- [ ] **Step 1: Write the failing tests**
  - review.test.mjs: `review adds a row and opens nothing`; `Add missing opens its chooser and adds the row`; `a refused add calls back with the reason`; `showRowReview has no Apply and takes the row out`. Delete the tests of the removed functions (`applyChange` paths, map turns).
  - panel.test.mjs: `Escape and other Details keep every tray row` (open Details over a ready tray, close; `tray.rows.length` unchanged, no `/cancel` asked); `Ctrl Enter presses the tray's Apply when ready`.
  - details.test.mjs / gateway-details.test.mjs: `a switch in the tray shows the pending look and a press takes it out`; `a button in the tray says In preview`.
  - test_page_words.py: `"Add to preview"`, `"In preview"`, `"Take it out"` pinned; `"⌘ Enter to apply"` gone.
  - gateway.test.mjs: `a click on empty map keeps a row's review in Details`.
- [ ] **Step 2: Run** the node tests and the page-word test — expected: FAIL.
- [ ] **Step 3: Implement** the changes above. Every caller of `review()` keeps its call; only tools.js passes `back` and reads `{ queued }`.
- [ ] **Step 4: Update `docs/design.md`**: Principle "one preview at a time" becomes the tray; the review in Details is "Show changes" of one row; switches' pending look.
- [ ] **Step 5: Check in a real browser** on the demo home (stop only the server you started): a Details switch, a Details button and an Overview card each add a row; Show changes opens and Take it out works; Escape keeps the rows; Apply all, then Undo all. At 1440×900 in both themes, compare the bar and toast with the M4 frames in `design/kitden.pen` when the Pencil MCP can read them.
- [ ] **Step 6: Run** all four checks — expected: PASS.
- [ ] **Step 7: Commit** — `Tray: every change waits in the tray`.

