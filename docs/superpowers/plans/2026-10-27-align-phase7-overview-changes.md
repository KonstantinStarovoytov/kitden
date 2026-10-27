# Phase 7: Overview and Changes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the Overview and Changes pages in line with the mockup.

- **Overview:** the title "Your setup, connected.", a lede with the counts, cards with one action each, notes that fold, and a small "Your setup" map. Each card's action adds a preview to the tray (D22).
- **Changes:** a timeline by day, a Details card with the change's facts and history, "See it on the map", and an Undo toast that offers "Redo…" as a fresh preview (D21).

**Architecture.**
- **Backend.** `views/overview.py` gains the card and map fields. A new `views/changes_view.py` turns the change log into one entry per change, with its facts and history.
- **Page.** `overview.js` and `changes.js` are rebuilt.
  - The "Your setup" map uses the shared `mapView` and `layoutTree` with a small fixed tree of its own.
  - Change Details use `detailsCard` in the floating panel that Changes already has.
  - Every action goes through `addToTray`, or opens a page; nothing writes before Apply.

**Tech Stack:** Python 3.13 + Starlette, pytest on sandbox homes; plain ES modules, one CSS file, node's test runner with each file's fake DOM.

**Spec:**
- **Master plan:** `docs/superpowers/plans/2026-10-24-mockup-alignment.md` Phase 7 (Tasks 7.1, 7.2, the note "Carried from Phase 3"), and decisions D18 and D21–D24.
- **Earlier design:** `docs/superpowers/specs/2026-10-23-map-pages-design.md` Part 6: 6.2 Overview and 6.3 Changes.
- **Mockup digest:** `docs/mockup/overview-changes-notes.md`. It holds the exact values, words and motion; its §2.4 explains the collapse jump to avoid.
- **The mockup decides behaviour, words and motion where the two disagree**, as the master plan's Global Constraints say.

## Decisions

### Overview head
- **Title:** "Your setup, connected."
- **Lede:**
  - With cards: "<n> things need your attention. Everything else looks fine: <c> clients, <p> projects." ("1 thing needs").
  - With none: "Everything looks fine: <c> clients, <p> projects."
  - The numbers count up (700 OUT3, 200 / 260 / 320 delay) on the first visit only.
- **Scope bar:** "All projects" with the `layers` icon, or "Project <name>" with `folder` in the accent.
- **Hint line:** "Hover a card to see it on the map · a button adds a preview · click Kitden gateway or Library to open it".

### Overview cards
- **Groups:** "Needs attention" (`triangle-alert` in `--warn`) and "Can improve" (`sparkles`). A group with no card hides its caption.
- **The card:**
  - a 28 px icon tile;
  - the name (12 px / 600);
  - one line (11 px `--muted`);
  - 20 px client tiles;
  - one button: primary in "Needs attention", plain in "Can improve".
- **Card kinds, from what Kitden already finds:**

  | Kind | Group | Line | Button | What it does |
  | --- | --- | --- | --- | --- |
  | An item set up twice | Needs attention | today's sentence | "Keep one…" | Opens the item in the Library (a choice is needed) |
  | A settings file Kitden cannot read | Needs attention | today's sentence | none | — |
  | An untested client version | Needs attention | today's sentence | none | — |
  | Old Kitden entries | Needs attention | today's sentence | "Update…" | Adds today's update row to the tray |
  | A server that skips the gateway | Can improve | "Skips the gateway, so Kitden's rules don't reach it." | "Move in…" | Adds its `gateway.move` row to the tray |
  | A client not connected to the Kitden gateway | Can improve | "Not connected to the gateway yet." | "Connect…" | Adds today's connect row to the tray |

  - At most three server cards. After that, one card "<n> more servers skip the gateway", whose button "Show…" opens the Gateway List at the outside group.
  - The card's icon comes from the item: the server's kind, the plugin's tile, or the client's mark.
- **The tray decides when a card leaves.**
  - A card whose row waits in the tray says "In preview" on its button (`showInPreview`).
  - It leaves only after Apply is verified: out 180 ease-in (opacity, x 28), then it collapses (height, margin, padding and border to 0, 160 CALM).
  - There is no sibling slide afterwards (the mockup's FLIP jump, §2.4).
  - The count in the lede rolls.
  - Undo brings the card back: in 220 CALM from y -8 and scale .98.
- **Map focus.** Hover, or keyboard focus on a card, focuses the "Your setup" map on the card's path: the clients and the block it is about. Leaving lets go (300 ms dim, as the maps do).

### Notes
- **The toggle:** "Show <n> notes (nothing to fix)" / "Hide <n> notes", with a chevron that turns 90°. It is hidden at 0 notes.
- **Opening:** the box opens 280 CALM, and the notes rise 40 ms apart.
- **A note** is one plain sentence with an `info` icon. A click on it opens its item, as today.

### "Your setup" map
- Caption "Your setup", a `mapView` of 470 × 250:
  - **Clients** at x 0 (160 × 54), with the version as meta (today's `versionWords`).
  - **"Kitden gateway"** at x 250, y 40 (220 × 60): `house` tile, meta "<n> servers · <m> tools".
  - **"Library"** at x 250, y 148 (220 × 60): `library` tile, meta "<n> plugins · <m> skills".
  - The two page blocks carry an `arrow-up-right` mark.
- **Links:** each client to the Kitden gateway while its `kitden` entry is on, and to the Library when it loads a plugin or skill. Links have no ×.
- **Foot:** "<n> projects · <k> have their own rules" ("1 has its own rules"), with the `folder` icon.
- **Presses:**
  - The Kitden gateway or the Library block opens its page.
  - A client block focuses its links.
  - Enter and Space do the same.
- **Replaces** today's Clients and Gateway side cards. Every action they had stays reachable:
  - set up is the "Connect…" card;
  - versions are on the client blocks;
  - per-client counts go to the Library through its block.

### Changes timeline
- **Head:**
  - Title "Changes".
  - Lede: "Every change made from this page. Each one has a backup; Undo puts the previous file back."
  - Scope: "All projects · <n> changes this week".
  - Hint: "Click a row · Undo · See it on the map".
- **Day groups:** "Today", "Yesterday", then a date such as "Mon 21 Oct" in the person's own language setting. Pin one test.
- **Rail and dots:** a rail per group, and a 9 px dot per row (accent on the selected row).
- **A row:**
  - columns `52px 1fr auto auto auto`, 46 px high;
  - parts: time, title, client tiles, lamp and state word, and Undo on an applied row.
- **State words:**
  - "Applied" (green);
  - "Undone" (grey);
  - "Cancelled" (grey);
  - "Not applied: the file changed first" (amber);
  - "Failed, put back" or "Failed" (amber);
  - "Can't undo: the file changed after this" (amber).
- **Undone and Cancelled rows:** a muted title with a strike line. Failed rows keep only their amber phrase.
- **On open,** the first row is selected and its Details are open.
- **A change of several tray rows** is titled by its rows: the first row's title plus " and <n> more". This replaces "batch …", and Details list every row's title.

### Change Details (`detailsCard`)
- **Kicker and title:** kicker "Change". The title is the row title, with "Today 14:02" under it.
- **Facts:**
  - Project: the folder name, or "All projects".
  - State: "Applied and checked", "Undone", "Cancelled", "Not applied: the file changed first", "Failed, put back".
  - Backup: "Kept · Undo puts it back" while it can undo, "Back in place" after Undo, "None, nothing was written" when nothing was.
  - Takes effect: per client, from the steps' restart notes ("Codex: start a new session"), or "Nothing to do".
  - Clients: tiles and "<n> clients".
  - History: each state change of that change in order, joined by `arrow-right`, for example "14:02 Preview → 14:02 Applied → 14:02 Checked".
- **Actions:**
  - "Undo", on an applied change.
  - "See it on the map": opens the Gateway or the Library with the item the change touched selected. When that item is no longer there it says "This item is no longer there."
  - "Redo…", on an undone change: adds a fresh preview of the same request to the tray (D21). It is offered only when the change kept its request.
- **Technical details:** the paths, the backup files and the commands. They are never shown on the list or in the facts.

### Undo toast
- **Words:** "Undid “<title>”. The backup is back in place." with "Redo…" (which does the same as Details' Redo…).
- **The row:** its strike draws in 200 ms `cubic-bezier(.6,0,.2,1)`, its lamp goes grey (400), and its word rolls.
- **Truth first:** the toast shows only after Undo is verified.

### What the backend keeps for a change
- **The request.** A new change keeps its request (the tray rows' bodies), so "Redo…" can preview it again. An old log line without it gets no Redo….
- **Clients and project.** Each change entry carries its clients and its project (from `target` and the rows).
- **Map target.** The entry also carries a `map` target, `{view, sel}`, when one item or server is touched, so "See it on the map" knows where to go.

## Global Constraints

- **AGENTS.md in full.** Simple English in code, comments and page words. Tests use sandbox homes only. Dated facts about other tools.
- **Every write** goes preview → Apply with a backup → verify → Undo through `src/kitden/changes/engine.py`.
  - A card button, Redo… or Undo only adds a tray row or runs today's Undo. Nothing writes without the tray's Apply (D21, D22).
- **Main pages** show a name, the client and an action. Paths, addresses, commands and file lines stay under Technical details.
  - The notes avoid paths: a sentence names a file by its name only.
- **CSP** stays `script-src 'self'; style-src 'self'`.
  - No innerHTML, no inline `style=""` in strings, no `<style>`, no `cssText`.
  - CSSOM properties and `setProperty` only.
  - Icons go through `icon()`; add any missing lucide data to icons.js.
- **Calm motion only**, from `motion.js`.
  - Every motion has a reduced-motion path that lands at once.
  - Nothing stays at opacity 0, nothing loops, and there is one motion per change.
- **Docs and tests.**
  - `docs/design.md` changes in the same commit as the page change it describes.
  - New page words are pinned in `tests/unit/test_page_words.py`, and pins that name changed source strings move with the code.
  - `tests/unit/test_contrast.py` keeps 4.5:1 (3:1 for edges and focus rings) in both themes.
- **Before each commit:** `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`.
- **ROADMAP.md** gets its line in the same commit when a task changes what Kitden does.
- **Git and processes.**
  - Never stage `design/`. Stage only your own files, by name. No `git stash`.
  - Never `pkill` in any form; stop only your own process, by its pid. The owner's pages run from `/tmp/kitden-check`; leave them.
- **Another session's logo work stays as it is:** `--hearth`, `.brand`, `.brand-mark`, `startLogo`, the Identity paragraph, the Logo row.
- **Guarded functions.** Do not grow `gatewayTree`, `layoutTree`, `mapView`'s `draw` or `detailsCard`; add small named helpers.
- **Commit messages:** a short plain subject, one to three simple lines, ending with the Co-Authored-By line of the model that wrote the commit.

## Review Focus

- **A card's action through Apply.** It is applied from the tray, then Undone from the toast. The card leaves after verify and comes back after Undo. The lede's count rolls both ways, and nothing jumps (no FLIP). Tests in Tasks 2 and 4.
- **"See it on the map" for a removed item.** It says "This item is no longer there." and opens nothing. Test in Task 4.
- **"Redo…" on an old change** (a log line with no request) is not offered. On a new one, it adds a fresh preview and writes nothing. Test in Task 4.
- **A change made of several tray rows** is titled by its rows, never "batch …", and its Details list each row. Test in Task 3.
- **The owner's real setup has dozens of outside servers.** Overview shows three server cards and one "<n> more" card, and nothing overflows. Test in Task 2 with the large sample.

---

### Task 1: Overview data

**Files:**
- Modify: `src/kitden/views/overview.py`
- Test: `tests/unit/test_overview.py`, `tests/security/test_no_secrets.py`

**Interfaces:**
- **Consumes:** today's `overview()` and its findings; the Gateway view, for outside servers and clients; the Library map data (`library_map`), for counts and project rules; today's change bodies for update, move and connect (find how the Gateway builds them).
- **Produces** extra fields on `/api/overview`:
  - A card gains:
    - `group: "attention" | "improve"`;
    - `icon`: a lucide name or `{client}`;
    - `name`;
    - `line`;
    - `clients: [ids]`;
    - `action: {label, body?} | {label, go: {view, sel?, mode?}} | null`;
    - `focus: {clients: [ids], block: "gateway" | "library" | null}`.

    Keep today's `title`/`text` only while the page still needs them, then drop them.
  - Cards for servers that skip the gateway: up to three, then one "<n> more servers skip the gateway" card with `action.go` to the Gateway List's outside group.
  - A card for a client not connected to the Kitden gateway, when the gateway holds servers.
  - `map: {clients: [{id, name, version, tested, on}], gateway: {servers, tools}, library: {plugins, skills}, links: [{client, to: "gateway" | "library"}], projects, own_rules}`.
  - `counts: {attention, clients, projects}`.

  There are no paths in any field.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_server_that_skips_the_gateway_is_a_move_in_card_with_its_body`;
  - `test_more_than_three_servers_give_one_more_card` (Review Focus, large sample);
  - `test_a_client_not_connected_gets_a_connect_card`;
  - `test_old_kitden_entries_card_adds_the_update_row`;
  - `test_a_duplicate_card_opens_the_item`;
  - `test_the_map_counts_servers_tools_plugins_skills_and_own_rules`;
  - `test_no_card_or_map_field_holds_a_path`;
  - the secrets sweep.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Overview: cards with one action and the setup map's data`.

### Task 2: The Overview page

**Files:**
- Modify: `src/kitden/web/static/js/overview.js` (rebuilt), `src/kitden/web/static/style.css`, `docs/design.md`, `ROADMAP.md`
- Test: `tests/frontend/overview.test.mjs`, `tests/unit/test_page_words.py`, `tests/unit/test_contrast.py`

**Interfaces:**
- **Consumes:**
  - Task 1's fields;
  - `addToTray`, `onTray`, `showInPreview` and `followTray`;
  - `mapView` and `layoutTree`;
  - `rollTo`, `animateTo`, `rise` and `D`;
  - `docs/mockup/overview-changes-notes.md` §1–§3 and §7.
- **Produces:**
  - the head, groups, cards, notes and "Your setup" map in Decisions;
  - a card that leaves only after its row is verified, with no sibling slide, and comes back on Undo;
  - map focus on card hover and focus;
  - presses on the map blocks;
  - reduced motion that lands at once.

- [ ] **Step 1: Write the failing tests:**
  - `the head says Your setup, connected. and the lede counts`;
  - `a card shows its icon, name, line, client tiles and one button`;
  - `Move in… adds its row; the button says In preview while it waits`;
  - `after Apply is verified the card leaves and the count rolls; Undo brings it back`;
  - `no sibling slides after a card collapses`;
  - `three server cards and one more card` (Review Focus);
  - `hover or focus on a card focuses the setup map on its path`;
  - `the notes fold opens and closes and is hidden at 0`;
  - `the setup map draws clients, Kitden gateway and Library with their counts and the foot`;
  - `the Kitden gateway and Library blocks open their pages; a client block focuses its links`;
  - `under reduced motion everything lands at once`;
  - the pins and the contrast checks.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md` and `ROADMAP.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** on the medium and large demo, at 1440×900 in both themes, beside the mockup's Overview.
- [ ] **Step 6: Commit** — `Overview: your setup, connected`.

### Task 3: Change entries

**Files:**
- Create: `src/kitden/views/changes_view.py` (`change_entries(log, engine, inventory, projects) -> list[dict]`)
- Modify:
  - `src/kitden/changes/engine.py` (a change keeps its request);
  - `src/kitden/changes/batch.py` (the tray's rows' bodies as the request);
  - `src/kitden/web/app.py` (`GET /api/changes` answers entries; the old log lines stay readable);
  - `src/kitden/web/static/js/parts.js` (a several-row change is titled by its rows).
- Test: `tests/unit/test_changes_view.py` (create), `tests/unit/test_api_changes.py`, `tests/frontend/parts.test.mjs`, `tests/security/test_no_secrets.py`

**Interfaces:**
- **Consumes:** the log lines (`_log`: `id, time, action, state, error, target, rows, steps`), the record (`_record`), `ChangeState`, and today's `changeTitle`.
- **Produces:**
  - **`change_entries`:** one entry per change id, newest first, as `{id, time, day, title_parts, state, clients, project, backup: "kept" | "back" | "none", takes_effect: [{client, note}], history: [{time, state}], rows: [{title}], redo: request | null, map: {view, sel, gone: bool} | null, technical: {paths, backups, commands}}`.
    - `map.gone` is true when the item is no longer in the inventory.
    - Paths appear only under `technical`.
  - **A new change keeps its request** (`request`) in its record and its log line, with secrets kept out exactly as the rows' bodies are.
  - **A several-row change's title** is the first row's title plus " and <n> more".

- [ ] **Step 1: Write the failing tests:**
  - `test_one_entry_per_change_with_its_history_in_order`;
  - `test_a_several_row_change_is_titled_by_its_rows` (Review Focus);
  - `test_backup_words_follow_the_state`;
  - `test_takes_effect_is_per_client_from_restart_notes`;
  - `test_a_new_change_keeps_its_request_and_an_old_one_has_no_redo`;
  - `test_map_target_and_gone_for_a_removed_item`;
  - `test_entries_hold_no_paths_outside_technical`;
  - the secrets sweep;
  - a node test for the title.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Changes: one entry per change, with its history`.

### Task 4: The Changes page

**Files:**
- Modify:
  - `src/kitden/web/static/js/changes.js` (rebuilt);
  - `src/kitden/web/static/js/review.js` (`undoChange`: the Undid toast with Redo…);
  - `src/kitden/web/static/js/panel.js` (`openChange` gives way to `detailsCard`, or goes when nothing else uses it);
  - `src/kitden/web/static/style.css`, `docs/design.md`, `ROADMAP.md`.
- Test: `tests/frontend/changes.test.mjs` (create), `tests/frontend/review.test.mjs`, `tests/frontend/toast.test.mjs`, `tests/unit/test_page_words.py`, `tests/unit/test_contrast.py`

**Interfaces:**
- **Consumes:**
  - Task 3's entries;
  - `detailsCard` and the floating panel;
  - `goTo` and the arrival plumbing (`sel`);
  - `addToTray`, for Redo… (the request's bodies);
  - today's Undo;
  - `toast(text, onUndo, { label, extra })`;
  - `docs/mockup/overview-changes-notes.md` §4–§7.
- **Produces:**
  - the timeline, the rows, the Details, the actions and the toast in Decisions;
  - the Undo motion (strike, lamp, word roll, button out);
  - "See it on the map" and "This item is no longer there.";
  - Redo… as a fresh preview;
  - reduced motion that lands at once.

- [ ] **Step 1: Write the failing tests:**
  - `the timeline groups by Today, Yesterday and a date, with a rail and a dot per row`;
  - `a row shows time, title, client tiles, state and Undo`;
  - `undone and cancelled rows are muted with a strike; failed rows keep their phrase`;
  - `the first row is selected with its Details open`;
  - `Details show Project, State, Backup, Takes effect, Clients and History`;
  - `See it on the map opens the item; a removed item says This item is no longer there.` (Review Focus);
  - `Undo draws the strike and the toast says Undid “…”. The backup is back in place. with Redo…`;
  - `Redo… adds a fresh preview and writes nothing; an old change offers none` (Review Focus);
  - `Technical details hold the paths`;
  - `under reduced motion everything lands at once`;
  - the pins and the contrast checks.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md` and `ROADMAP.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** on the demo: apply a change, Undo it from Details, Redo… it, and open "See it on the map".
- [ ] **Step 6: Commit** — `Changes: the timeline, Details and Redo…`.
