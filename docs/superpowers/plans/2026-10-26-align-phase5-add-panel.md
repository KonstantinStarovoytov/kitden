# Phase 5: Add a server from a marketplace — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the Gateway map, "+ Add" opens the mockup's "Add a server" panel. It lists the MCP servers in the plugins of the marketplaces on this computer. A click or a drag onto the map adds a preview of that server to the Kitden gateway. Apply writes it, and Undo takes it out.

**Architecture:**
- Backend: `market_servers` and `known_refusal` read the plugin folders that `catalog()` already finds; nothing touches the network. `GET /api/market-servers` answers the list.
- A new change action, `gateway.add`, is built from the same steps as a local move (`_server_step`, the path step, Codex's timeouts). It goes through the tray and `/api/batch/preview` like every other row.
- Page: one new module, `gateway-add.js`, draws the panel in the floating Details panel. Its drag is a fourth kind in the existing drag engine (`DRAGS.add`). The map draws an add row the way it draws a move row today: a preview block in its gateway group.

**Tech Stack:** Python 3.13 + Starlette, pytest on sandbox homes; plain ES modules, one CSS file, node's test runner with each file's fake DOM.

**Spec:**
- Master plan `docs/superpowers/plans/2026-10-24-mockup-alignment.md`, Phase 5 (Tasks 5.1, 5.2, and the note "Carried from Phase 3").
- Decisions D14, D20, D23 and D24.
- `docs/mockup/add-notes.md`, which digests the mockup's `openAdd`, `resRow`, `preview`, `resDrag`, `commitAdd` and `removeServer`.
- The frames `M5·1`–`M5·4` and the note `Note · M5 · Add a server` in `design/kitden.pen`.
- The earlier, never-built plan `docs/superpowers/plans/2026-10-23-map-part5-library.md` Task 10. Its refusal table, demo servers and tests are reused here, with the changes listed under Decisions.

## Decisions

- **What is listed.** One row per MCP server inside a plugin folder that a marketplace on this computer offers (`catalog()`'s offers whose `inside` is read).
  - Row id: `"<plugin id>/<server name>"`.
  - Kind: an entry with `url` (or `type` `http` or `streamable-http`) is **Remote**; one with `command` is **Local**.
  - No tool count and no sign-in words (D23, D24). The pen frames' "8 tools" and "Sign-in" are not built.
- **Groups and filter.**
  - Rows are grouped by marketplace, in name order. Each group has a caption with the `store` icon and the marketplace's name.
  - The mockup's All / Community / Team pill does nothing, and Kitden has no community or team kinds. So the pill is **All · Remote · Local**, a real filter on the row's kind. It keeps the mockup's look and its glide (280 CALM).
- **Search** matches part of the row's name, ignoring case (as the mockup does).
  - A group with no row left hides its caption.
  - With no row left at all, the list says "No servers match." A list with no servers at all says "No marketplace on this computer offers an MCP server."
- **A row's status** (first match wins):
  1. A known refusal: greyed (`.off`), with the reason as its small line, no grip, no click.
  2. The server is in the gateway: "In the gateway", greyed.
  3. It was added by an Apply since the page loaded: "Added", in `--ok`, greyed.
  4. Its row waits in the tray: "In preview", in the accent.
  5. Otherwise: empty.
- **A click** on a free row adds one `gateway.add` row to the tray, keyed `add:<row id>`. A click on an "In preview" row takes that row out. Enter or Space on a row is the click.
- **A drag** of a free row works as in add-notes §4:
  - A 5 px threshold, then a ghost card follows the pointer.
  - The zone is the gateway and servers columns, not over the panel. While the pointer is in the zone, the gateway lights and a slot opens in the row's own group (Remote or Local).
  - A drop in the zone flies the ghost to the slot (200 CALM) and adds the same row as a click. Any other drop flies it back (180 CALM) and leaves the tray as it was. Escape and pointercancel are a miss.
- **Clients are not changed.**
  - `gateway.add` writes only Kitden's gateway settings, plus Codex's timeouts when Codex already has a `kitden` entry (as a move does). It never adds a `kitden` entry to a client.
  - When no client is connected to the Kitden gateway, the tray row's line says "No client uses the Kitden gateway yet." This changes the old plan, whose click connected every found client: a click that edits three client files would be a surprise.
- **Refusals.** The old plan's table, checked without the network when the list is built:
  - in the gateway already;
  - a client has a server of that name ("Move it into the gateway instead.");
  - SSE or WebSocket;
  - values Kitden can't fill in (`${…}`);
  - a `.mcpb` bundle;
  - a file inside the plugin folder.

  At preview, a remote entry with no headers of its own gets the one sign-in check a move already makes. OAuth is then refused: "<name> signs in with OAuth; Kitden can't add it yet." No answer is refused too: "Kitden could not reach <name>." These two refusals show in the tray as every other refused row does.
- **Words**, with the mockup's words where Kitden can keep them:
  - panel title: "Add a server";
  - search placeholder: "Search the marketplaces…";
  - footer: "Click a server or drag it onto the map to preview it.";
  - tray and review title: "Add <name> to the Kitden gateway";
  - toast and done words: "Added <name> to the Kitden gateway";
  - preview block meta: "Preview";
  - after Apply, the block is an ordinary gateway server, with today's words.
- **The panel** is the floating Details panel with a new kind, `add`. It opens with the skeleton and its children rise, as other panels do.
  - Focus goes to the search when it opens.
  - Escape or Close closes it, and focus goes back to the "+ Add" button.
  - "+ Add" shows as pressed (`.primary`) while the panel is open and loses that on every close (add-notes §9.5).
  - "Add a server…" in the Kitden gateway's Details (its "More" list) opens the same panel.

## Global Constraints

- `AGENTS.md` in full: simple English in code, comments and page words. Tests use sandbox homes only. Dated facts about other tools.
- Every write is preview → Apply with a backup → verify → Undo through `src/kitden/changes/engine.py`. A click, a drag or a press only adds a tray row (`addToTray`); nothing writes without the tray's Apply.
- Main pages show a name, the client and an action. Paths, addresses, commands and file lines stay under Technical details, and the Add panel shows none of them.
- CSP stays `script-src 'self'; style-src 'self'`: no innerHTML, no inline `style=""` in strings, no `<style>`, no `cssText`. Use CSSOM properties and `setProperty` only, and icons through `icon()`.
- Calm motion only, from `motion.js` (`D`, `CALM`, `OUT3`, `IN3`, `animateTo`, `rise`). Every motion has a reduced-motion path that lands at once. Nothing stays at opacity 0, and nothing loops.
- `docs/design.md` changes in the same commit as the page change it describes. New page words are pinned in `tests/unit/test_page_words.py`. `tests/unit/test_contrast.py` keeps 4.5:1 (3:1 for edges and focus rings) in both themes.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`.
- `ROADMAP.md` gets its line in the same commit when a task changes what Kitden does.
- Never stage `design/`. No `git stash`. Never `pkill -f kitden`; stop only a process you started, by its pid. The owner's pages run from `/tmp/kitden-check`; leave them.
- Do not grow `gatewayTree` (gateway.js), `layoutTree` (map.js), `showDetails` (details.js), `toolsSection` (tools.js) or `mapView`'s `draw` (map-view.js). Add small named helpers instead.
- Commit messages: a short plain subject, one to three simple lines, ending with the Co-Authored-By line of the model that wrote the commit.

## Review Focus

- **Two rows for one server name** (two plugins or two marketplaces offer `github`): adding one refuses the other at add time, with the reason, never at Apply. Test in Task 2.
- **A row added, then Apply all fails:** every file is back, the row still says "In preview", and the preview block stays. Test in Task 2.
- **A drop over the Add panel itself, over the dock or on nothing:** the ghost goes back, and the tray and the map are as they were. Test in Task 5.
- **The panel open while the tray applies and the page reads again:** the row turns to "Added" without closing the panel, and focus stays where it was. Test in Task 4.
- **Reduced motion** with open, search, a click, a drag, Apply and Undo: each lands at once and nothing is left at opacity 0. Tests in Tasks 3, 4 and 5.

---

### Task 1: List the marketplace servers

**Files:**
- Modify: `src/kitden/views/catalog.py` (`market_servers`, `market_entry`, `known_refusal`), `src/kitden/web/app.py` (`GET /api/market-servers`), `src/kitden/demo/sample.py` (`_plugin_files`)
- Test: `tests/unit/test_market_servers.py` (create), `tests/unit/test_demo_home.py`, `tests/security/test_no_secrets.py`

**Interfaces:**
- Consumes: `catalog(inventory, adapters)`, `_inside`, `_plugin_dir`, `_first` (catalog.py); `gateway_entry`, `reads_elsewhere` (clients/entries.py); `SCRIPT_SUFFIXES` (views/skills.py); `load_settings` (local_gateway/settings.py) for the held names.
- Produces `market_servers(inventory, adapters, held: set[str]) -> list[dict]`. Each item is `{id, name, plugin, marketplace, kind: "remote" | "local", held: bool, refusal: str | None}`, sorted by marketplace and then by name (ignoring case). It has no tool count and no address.
- Produces `market_entry(adapters, server_id) -> tuple[str, dict]`: the raw entry, read again as `_inside` reads it. It raises `ValueError("This server is no longer offered.")` when the entry is gone.
- Produces `known_refusal(name, entry, inventory, held) -> str | None`, checked in this order:

  | Holds | Refusal |
  | --- | --- |
  | `name` in `held` | "<name> is in the gateway already." |
  | a client has an MCP item of that name | "<Client> has <name> already. Move it into the gateway instead." |
  | `type` `sse` or `ws`, or the address ends in `/sse` | "<name> uses a connection the Kitden gateway does not support yet." |
  | `reads_elsewhere(entry, gateway_entry(entry))` | "<name> reads values Kitden can't fill in." |
  | a value ending in `.mcpb` | "<name> comes as a bundle; Kitden can't run it yet." |
  | the command or an argument starts with `./` or `../`, or is a bare name with a `SCRIPT_SUFFIXES` suffix | "<name> runs a file inside its plugin folder; Kitden can't run it from the gateway." |

- Produces `GET /api/market-servers` → `{servers: [...]}`, with the same token and origin checks as the other GETs.
- Demo, in `_plugin_files`:
  - `db-tools` gains `.mcp.json` `{"mcpServers": {"db-query": {"command": "uvx", "args": ["mcp-db-query"]}}}`;
  - `test-helper` gains `{"mcpServers": {"test-status": {"type": "http", "url": "https://status.example.test/mcp"}}}`.

- [ ] **Step 1: Check the docs.** Read code.claude.com/docs/en/plugins-reference (`mcpServers` forms, `${CLAUDE_PLUGIN_ROOT}`, `.mcpb`) and Codex's plugin build docs (`mcp.json`, `streamable-http`). Write the date you checked in `known_refusal`'s comment.
- [ ] **Step 2: Write the failing tests:**
  - `test_market_servers_say_why_before_any_preview`: in the medium demo, db-query is `("local", None)`, test-status is `("remote", None)`, and pr-index is refused with the plugin-folder words. The id is `"db-tools@demo-market/db-query"`, and the item has no `"tools"` key.
  - `test_entries_the_gateway_cannot_run_are_refused`: parametrized over the five entry forms of the old Task 10 (sse, `${CLAUDE_PLUGIN_ROOT}`, a `${TOKEN}` header, `./bin/server`, `x.mcpb`).
  - `test_a_name_a_client_has_offers_move_instead`.
  - `test_a_held_name_is_in_the_gateway_already`.
  - `test_the_demo_marketplace_has_two_servers_the_gateway_can_add`, in test_demo_home.py.
  - `/api/market-servers` in the secrets sweep of test_no_secrets.py.
- [ ] **Step 3: Run** them — expected: FAIL (no `market_servers`).
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Run** all four checks — expected: PASS.
- [ ] **Step 6: Commit** — `Gateway: list the servers the marketplaces offer`.

### Task 2: The `gateway.add` change

**Files:**
- Modify: `src/kitden/changes/actions.py` (`GATEWAY_ADD`, `gateway_add_steps`), `src/kitden/web/app.py` (the preview branch, `ADD_ACTIONS`, the tools read after `verified`), `src/kitden/views/after.py`, `src/kitden/views/words.py`, `src/kitden/web/static/js/review.js` (`ADDS`, the title, the done words), `src/kitden/web/static/js/tray.js` (`keyFor`, `ADDS` for the icon)
- Test: `tests/unit/test_market_servers.py`, `tests/unit/test_api_batch.py`, `tests/frontend/review.test.mjs`, `tests/frontend/tray.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 1's `market_entry` and `known_refusal`; `_server_step`, the path step and `_codex_timeout_steps` as `local_move_steps` uses them; `needs_sign_in` (or the demo's `no_sign_in` stand-in, as create_app passes it today); `refresh_later` in app.py.
- Produces `GATEWAY_ADD = "gateway.add"`, with the body `{action: "gateway.add", targets: [], params: {server: "<row id>"}}`. Its key is `add:<row id>` (`keyFor`), and its icon is `plus`.
- Produces `gateway_add_steps(adapters, inventory, home, server_id, *, sign_in=None, keychain_run=None) -> list[Step]`:
  1. It refuses `known_refusal` first.
  2. For a remote entry with no headers of its own, it makes one sign-in check. No answer refuses with "Kitden could not reach <name>." OAuth refuses with "<name> signs in with OAuth; Kitden can't add it yet."
  3. Then come these steps: `_server_step(home, name, gateway_entry(entry), None, keychain_run)` (secrets go to the Keychain), the path step when the settings have none, and `_codex_timeout_steps(adapters)` only when Codex has a `kitden` entry.
  4. A `streamable-http` entry maps to `url`.
- After `verified`, `refresh_later([name])` runs, as it does after a move.
- Words:
  - title and done words as in Decisions;
  - after chips `{state: "gw", word: "Via gateway"}` for each client whose `kitden` entry is on;
  - with none, the line "No client uses the Kitden gateway yet.";
  - `gateway.add` joins `ADDS` (review.js, tray.js) and `ADD_ACTIONS` (app.py).
- Two add rows for one server name: the second is refused when it is added, with "<name> waits in preview already." (Review Focus).

- [ ] **Step 1: Write the failing tests:**
  - `test_adding_a_marketplace_server_to_the_gateway_and_undo`: the medium demo, test-status, steps only for the gateway (and Codex timeouts if Codex has `kitden`), verified, held, then undone, with the settings bytes as before.
  - `test_an_oauth_server_is_refused_at_preview_and_nothing_is_written` (the stand-in says it signs in).
  - `test_an_unreachable_server_is_refused`.
  - `test_add_changes_no_client_file`: every client file has the same bytes after Apply.
  - `test_two_add_rows_for_one_name_refuse_the_second` (Review Focus, through the tray batch).
  - `test_a_failed_apply_all_with_an_add_puts_every_file_back` (Review Focus).
  - In node: `keyFor` gives `add:<id>`, the icon is `plus`, and the review title and done words are right.
  - Pin the new words.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Gateway: add a marketplace server, with Undo`.

### Task 3: The Add panel

**Files:**
- Create: `src/kitden/web/static/js/gateway-add.js`
- Modify: `src/kitden/web/static/js/gateway.js` ("+ Add" on the Servers caption, through `mapView`'s `onAdd`, on the Gateway map only), `src/kitden/web/static/js/gateway-details.js` ("Add a server…" in the Kitden gateway's "More" list), `src/kitden/web/static/js/panel.js` (the `add` kind's skeleton), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway-add.test.mjs` (create), `tests/frontend/gateway.test.mjs`, `tests/unit/test_page_words.py`, `tests/unit/test_contrast.py`

**Interfaces:**
- Consumes: Task 1's `GET /api/market-servers`; Task 2's body and `add:` key; `openPanel`, `skeleton`, `loadPanel`, `closePanel`, `header`, `restoreFocus` (panel.js); `addToTray`, `takeOut`, `inTray`, `onTray` (tray.js); `rise`, `D`, `CALM` (motion.js); `add-notes.md` §1, §2, §3 (the panel and click parts) and §8.
- Produces `openAdd({ from })` in gateway-add.js, where `from` is the button that gets focus back. It also produces `addRowWords(row, { inTray, added })`, which returns `{ status, off, line }` for the status rules in Decisions, and `matchRows(rows, query, kind)` for the search and the pill.
- The panel, top to bottom:
  - the header "Add a server" with Close;
  - the search (14 px icon, placeholder "Search the marketplaces…", aria-label "Search the marketplaces");
  - the pill All · Remote · Local (`.seg.sm`, `aria-pressed`, the mark glides in 280 CALM);
  - the groups, each a caption (`store` icon 13 and the marketplace name, 11 px, 600, `--ink-2`) and its rows;
  - the footer (an `info` icon and "Click a server or drag it onto the map to preview it.").
- A row has a grip (`grip-vertical` 12, not on an `.off` row), a 26 px tile with the server icon (`globe` for remote, `hard-drive` for local, as the map's outside blocks), the name (12 px, 700), the small line ("Remote", "Local", or the refusal) and the status on the right.
  - Row looks as add-notes §2: hover edge, `.on` select fill and accent edge, `.off` at opacity .55 with no hover.
  - A row that comes back into a search rises (opacity, y −4, 240 CALM).
  - A row is `role="button"`, `tabindex="0"`, and Enter or Space clicks it.
- Loading uses the panel skeleton. A failed read says "Could not read the marketplaces." with a quiet "Try again".

- [ ] **Step 1: Write the failing tests:**
  - `+ Add opens the panel, focus goes to the search, and + Add looks pressed`.
  - `Close and Escape close it, focus goes back to + Add, and + Add looks plain again`, including after a close by another selection.
  - `the groups follow the marketplaces and the pill filters Remote and Local`.
  - `a search hides rows and empty groups and says No servers match.`.
  - `a refused row is greyed, shows its reason and has no grip`.
  - `a click adds one gateway.add row; the row says In preview; a second click takes it out`.
  - `Enter and Space click a row`.
  - `the Kitden gateway's More list opens the same panel`.
  - `under reduced motion it opens and rises at once`.
  - Pin every new word and the contrast of the `.on`, `.off` and status colours in both themes.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`** (an "Add a server" section: what is listed, the status words, no counts, nothing written before Apply). Run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** on the medium demo at 1440×900 in both themes, beside frame `M5·1` in `design/kitden.pen` (Pencil MCP `TakeScreenshot`).
- [ ] **Step 6: Commit** — `Gateway: the Add a server panel`.

### Task 4: The added server on the map

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (an add row draws a preview block in its gateway group, as a move row does), `src/kitden/web/static/js/gateway-add.js` (rows follow the tray and the page's reads), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/gateway-page.test.mjs`, `tests/frontend/gateway-add.test.mjs`

**Interfaces:**
- Consumes: Task 2's rows (`rowsOnMap`); today's move preview block (`preview:<name>`, gateway.js ~555) and its take-out paths (the × of the block, the tray ×, Cancel); the landing after Apply (`landRows`) and the playback after Undo.
- Produces:
  - An add row with its part draws `preview:<name>` at the end of its Kitden gateway group (Remote or Local), with meta "Preview" and the dashed preview link from the gateway.
  - A click comes in from the gateway's right side (scale .4 and opacity 0 to its place, 260 OUT3) while the blocks below make room (260). A take-out shrinks it back (180 IN3).
  - After Apply it lands as the other rows do, and the panel's row turns to "Added" (it slides in from x 6 px, opacity 0, 280 CALM) without closing the panel or moving focus (Review Focus).
  - Undo plays it back. The panel's row is free again.

- [ ] **Step 1: Write the failing tests:**
  - `an add row draws a preview block in its own group with a dashed link`.
  - `a click grows it from the gateway and a take-out shrinks it back`.
  - `Apply lands it and the open panel's row says Added, with focus kept` (Review Focus).
  - `Undo takes it out and the row is free again`.
  - `a project switch keeps the preview block`.
  - `under reduced motion each lands at once`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** beside frames `M5·3` and `M5·4`: click test-status, Apply, Undo; click db-query and take it out from the map.
- [ ] **Step 6: Commit** — `Gateway: an added server waits in preview on the map`.

### Task 5: Drag a server from the panel

**Files:**
- Modify: `src/kitden/web/static/js/gateway-drag.js` (`DRAGS.add`), `src/kitden/web/static/js/gateway-add.js` (a press on a row's grip or body starts it), `src/kitden/web/static/js/map-view.js` (only if a helper is missing: the slot and `lightTarget` exist), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway-add.test.mjs`, `tests/frontend/gateway.test.mjs`

**Interfaces:**
- Consumes: the drag engine (`startDrag`, the 5 px threshold, the click swallowed after a drag, `covered()`), `lightTarget` / `unlightTarget`, the slot of a move drag; `add-notes.md` §4.
- Produces `DRAGS.add`:
  - On start, the row fades to .4 and a ghost copy of the row follows the pointer (fixed, under the pointer, `--shadow`, no pointer events).
  - In the zone (the gateway and servers columns, from the top of the map to 4 px above the Outside caption, not over the panel or the dock), the ghost gets `.over` (accent edge, select fill, 180), the Kitden gateway lights, and a slot opens in the row's group (220).
  - A drop in the zone flies the ghost to the slot (200 CALM) and adds the row (Task 2's body). The preview block then stands where the slot was, and its link fades in (300).
  - A miss flies the ghost back to its row (180 CALM), and the row comes back to full strength.
  - Escape and pointercancel are a miss.
  - An `.off` or `.on` row does not drag.
  - With reduced motion, every flight lands at once.

- [ ] **Step 1: Write the failing tests:**
  - `a drag starts after 5 px, the row fades and a ghost follows`.
  - `in the zone the gateway lights and the slot opens in the row's group`.
  - `a drop in the zone adds one row and the block stands in the slot`.
  - `a drop over the panel, over the dock or on nothing leaves the tray and the map as they were` (Review Focus).
  - `Escape cancels a drag`.
  - `a greyed or previewed row does not drag`.
  - `under reduced motion the ghost lands at once`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** beside frame `M5·2`: drag db-query over the panel and release, then into the gateway.
- [ ] **Step 6: Commit** — `Gateway: drag a marketplace server onto the map`.

### Task 6: "In preview" on the forms, and the docs

**Files:**
- Modify: `src/kitden/web/static/js/gateway-details.js` (`addForm`, the tool and server project choice ~451 and ~503, the Connect clients form ~716), `src/kitden/web/static/js/details.js` (`previewButton`, reused), `docs/design.md`, `ROADMAP.md`, `docs/mockup/README.md` (lists add-notes.md)
- Test: `tests/frontend/gateway-details.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: the note "Carried from Phase 3" in the master plan; `previewButton` (details.js).
- Produces:
  - Each of the three forms shows "In preview" with the `previewButton` look while its row waits in the tray, and goes back to its plain button when the row leaves.
  - ROADMAP gets one Gateway line: "Add a server from a marketplace: a click or a drag previews it in the Kitden gateway; Apply adds it, Undo takes it out."
  - docs/mockup/README.md lists add-notes.md.

- [ ] **Step 1: Write the failing tests:** `each form says In preview while its row waits and goes back after`.
- [ ] **Step 2: Run** it — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Gateway: forms say In preview; Add a server in the docs`.
