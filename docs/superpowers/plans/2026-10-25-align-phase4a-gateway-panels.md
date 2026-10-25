# Phase 4A: Gateway blocks, the floating panel and its actions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Gateway map's blocks look like the mockup, Details float beside the map as in the mockup, and every panel the mockup has (server, tool, client, gateway, connection, outside server) shows its facts and actions — two of them new on the server: disconnect a client and move a server out of the gateway.

**Architecture:** Two new change builders (`client.disconnect`, `gateway.move_out`) reuse today's step builders and go through the tray and the engine like every change. The page keeps its modules: blocks in `gateway.js` (`gatewayTree`) and `map-view.js` (`blockParts`); panels in `gateway-details.js` on `detailsCard` (details.js) and `tools.js`; the panel shell in `panel.js`. Every button, switch and picker only adds tray rows (Phase 3).

**Tech Stack:** Python 3.13, Starlette, pytest on sandbox homes; plain ES modules, one CSS file, node's test runner.

**Spec:** master plan `docs/superpowers/plans/2026-10-24-mockup-alignment.md` Phase 4 Tasks 4.1–4.6 with its "Carried from Phase 1/2/3" notes and decisions D5, D7, D13, D15, D17, D18, D23, D24; `docs/mockup/gateway-notes.md` (the mockup's Gateway page, section by section: §1 blocks, §3 panels, §4 disconnect and move out, §5 several projects); `docs/mockup/motion-spec.md` M1–M3; `docs/mockup/kitden-motion.html` (`Gateway`); frames D1–D5 in `design/kitden.pen` when the Pencil MCP can read them. Phase 4B (drags, Map ↔ List, find, project switch, the rest of the carried notes) is a separate plan.

## Decisions

- **Connect is the `kitden` entry.** Connecting a client to the Kitden gateway is today's `setup_server.register` (or `setup_server.update` for an old entry); disconnecting is the new `client.disconnect`, which removes that entry. Their words become "Connect <clients> to Kitden" / "Connected <clients> to Kitden" and "Disconnect <client> from Kitden" / "Disconnected <client> from Kitden" — true on the Gateway page and on Agents, where the same entry lets agents read the setup.
- **Move out = put back + remove**, as one change: `put_back_steps` for one client, then `remove_server_steps`. Its preview keeps the existing words that a Keychain secret will be written into the client file as a plain value.
- **The floating panel** replaces the docked column wherever Details docked (Gateway, Library, Changes) at 1024 px and wider; under 1024 px Details stay the modal drawer (D5). The map no longer goes narrow because Details are open: the panel floats over it.
- **Several projects (D13):** the "in some projects…" step adds one tray row per ticked project (`keyFor` keys a rule by project already); no backend change.
- **What is not shown (D23, D24):** no sign-in words, no "Running", no "New tools: stay off…", no "not tested", no tool counts on outside servers. Gateway stats say "1 client" / "1 server" in the singular.
- **Every action today's panels have stays (D18):** strict mode, every writing tool, Refresh tools, Remove from the gateway, Put back, Keychain, Move all, Add another gateway, registered gateways, Set up / Turn on / Open app, Remove direct entry, + Add to. They sit under "More" (`moreButton`) or Technical details when the mockup has no place for them.
- **Left for later:** "Add a server…" in the gateway panel comes with the Add panel (Phase 5). The client panel has no "Library" counts row: the Gateway page does not read the Library's data, and the mockup's numbers are demo; "See what it loads in Library" stays.
- **Words where the mockup has two (D7):** the tool panel's primary is "Use the shared rule…"; a project row in the server panel's tool list says "Use all projects". Both add the same rule row (`ruleBody(server, tool, null, project)`).

## Global Constraints

- `AGENTS.md` in full: simple English in code, comments and page words; tests on sandbox homes only, never the real home; dated facts about other tools.
- Every write is preview → Apply with a backup → verify → Undo through `src/kitden/changes/engine.py`. A button, switch, picker, × or drag only adds a tray row (`addToTray`); nothing writes without the tray's Apply.
- Main pages show a name, the client and an action; paths, addresses, commands and file lines stay under Technical details.
- CSP stays `script-src 'self'; style-src 'self'`: no innerHTML, no inline `style=""` in strings, no `<style>`, no `cssText`. Icons only through `icon()` in `dom.js` (names in `icons.js`; add a lucide 0.469.0 icon there with its data if one is missing).
- Calm motion only, from `motion.js` (`D`, `CALM`, `OUT3`, `IN3`, `SPRING` / `--spring`, `animateTo`, `rise`, `rollTo`); every motion has a reduced-motion path that lands at once; nothing stays at opacity 0.
- `docs/design.md` changes in the same commit as the page change it describes. New page words are pinned in `tests/unit/test_page_words.py`; `tests/unit/test_contrast.py` keeps 4.5:1 (3:1 for edges) in both themes.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`.
- `ROADMAP.md` gets its line in the same commit when a task changes what Kitden does. Never stage `design/`. No `git stash`. Never `pkill -f "kitden demo"`; stop only a process you started, by its pid.
- Do not grow `gatewayTree` (gateway.js), `layoutTree` (map.js), `showDetails` (details.js), `toolsSection` (tools.js) or `mapView`'s `draw` (map-view.js): add small named helpers beside them.
- Commit messages: a short plain subject, one to three simple lines, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- Disconnect, then Undo: every client's settings file is back byte for byte, in Claude Code, Codex and Cursor. Test in Task 1.
- Move out of a server whose secret sits in the Keychain: the preview says the secret will be written into the client file as a plain value, before Apply. Test in Task 2.
- A tool switch pressed twice in the server panel: its row leaves the tray and the switch is back as it was. Test in Task 5.
- The "in some projects…" step: unticking a project takes exactly its row out; the other projects' rows stay. Test in Task 6.
- Under 1024 px the floating panel is the modal drawer again, and the dock stays above it. Test in Task 4.

---

### Task 1: Disconnect a client

**Files:**
- Modify: `src/kitden/changes/actions.py` (constant and step builder beside `setup_server_steps`), `src/kitden/web/app.py` (`_steps_for`, imports), `src/kitden/views/words.py` (`AFTER_WORDS`), `src/kitden/web/static/js/review.js` (`DONE_WORDS`, `changeWords` titles and done words for `client.disconnect` and `setup_server.register`), `src/kitden/web/static/js/parts.js` (`ACTION_WORDS`, `changeTitle`, `PLACE_IN_TITLE`), `src/kitden/web/static/js/tray.js` (`iconFor`: `"plug"`), `ROADMAP.md`
- Test: new `tests/unit/test_client_disconnect.py`; `tests/unit/test_page_words.py`; `tests/frontend/review.test.mjs`, `parts.test.mjs`, `tray.test.mjs`

**Interfaces:**
- Produces: `CLIENT_DISCONNECT = "client.disconnect"`; `disconnect_steps(adapters, inventory, clients: list[str]) -> list[Step]` — for each client, the adapter's `remove_step` of the client's user-scope `kitden` item. Raises `ValueError` with plain words: `"<Client> gets Kitden from the Claude Code plugin. Turn the plugin off to disconnect it."` (plugin-provided entry) and `"<Client> is not connected to Kitden."` (no entry). Request body: `{"action": "client.disconnect", "targets": [{"client": "<id>"}], "params": {}}`.
- Words: `client.disconnect` title `"Disconnect <clients> from Kitden"`, done `"Disconnected <clients> from Kitden"`; `setup_server.register` title `"Connect <clients> to Kitden"`, done `"Connected <clients> to Kitden"`; both name their place (`PLACE_IN_TITLE`). `changeTitle` on Changes: `"Disconnected from Kitden · <clients>"`, `"Connected to Kitden · <clients>"`.

- [ ] **Step 1: Write the failing tests**
  - `test_disconnect_removes_the_entry_and_undo_puts_it_back` — parametrised over `claude_code` (through `FakeClaude`, as `tests/unit/test_api_changes.py` does), `codex`, `cursor`: a sandbox home where the client has the user `kitden` entry (`add_kitden` in `tests/unit/test_local_gateway_views.py`); preview through `/api/changes/preview` shows one step for that client; apply → `verified`, the entry is gone; undo → `undone`, `_files(home)` equals the bytes before the preview.
  - `test_disconnect_refuses_a_client_without_the_entry` and `test_disconnect_refuses_the_plugin_entry` — 422 with the exact words above.
  - `test_a_codex_entry_turned_off_can_be_disconnected` — `enabled = false` entry: preview works.
  - `test_disconnect_and_connect_of_one_client_clash_in_the_tray` — `/api/batch/check` with `setup_server.register` then `client.disconnect` for the same client → `ok: false`.
  - Frontend: `changeWords` titles and done words for both actions; `changeTitle` lines; `iconFor({action: "client.disconnect"}) === "plug"`; pins for the four phrases in `test_page_words.py`; the old "show my setup" title and done words are gone from review.js and parts.js.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_client_disconnect.py -q` and the node tests — expected: FAIL.
- [ ] **Step 3: Implement** the constant, `disconnect_steps`, the `_steps_for` branch (not in `ADD_ACTIONS`), `AFTER_WORDS`, the page words and the icon.
- [ ] **Step 4: Run** all four checks — expected: PASS. Add the ROADMAP line ("Disconnect a client from Kitden…").
- [ ] **Step 5: Commit** — `Gateway: disconnect a client from Kitden`.

### Task 2: Move a server out of the gateway

**Files:**
- Modify: `src/kitden/changes/actions.py` (`GATEWAY_MOVE_OUT`), `src/kitden/web/app.py` (`_steps_for`, `ADD_ACTIONS`), `src/kitden/views/after.py` (`after_words` branch), `src/kitden/web/static/js/review.js` (`ADDS`, `DONE_WORDS`, titles), `src/kitden/web/static/js/parts.js` (`ACTION_WORDS`, `changeTitle`), `src/kitden/web/static/js/tray.js` (`iconFor`: `"log-out"`), `ROADMAP.md`
- Test: new `tests/unit/test_gateway_move_out.py`; `tests/unit/test_api_changes.py` (the `ADD_ACTIONS` / `ADDS` match at ~965), `test_page_words.py`, `tests/frontend/review.test.mjs`, `parts.test.mjs`, `tray.test.mjs`

**Interfaces:**
- Produces: `GATEWAY_MOVE_OUT = "gateway.move_out"`; body `{"action": "gateway.move_out", "targets": [{"client": "<id>"}], "params": {"server": "<name>"}}` with exactly one client (else 422 `"Pick one client to move it into."`). Steps: `[*put_back_steps(adapters, home, server, [client], keychain_run), *remove_server_steps(home, server)]`. After words: the target client's row from `_put_back_words` (with its secret note) plus the other clients' rows from `_gateway_remove_words`.
- Words: title `"Move <server> out of the gateway into <Client>"`, done `"Moved <server> into <Client>"`; Changes: `"Moved out of the gateway · <server> · <Client>"`.

- [ ] **Step 1: Write the failing tests** (pattern: `tests/unit/test_gateway_remove.py`; helpers `hold`, `add_kitden`, `page_for`, `FakeClaude`)
  - `test_move_out_puts_the_entry_in_the_client_and_takes_it_out_of_the_gateway`: preview has the client's step and the `kitden` settings steps; apply → `verified`, `load_settings(home)["servers"]` lacks the server, the client file has it; undo → both files byte for byte as before.
  - `test_move_out_says_a_keychain_secret_becomes_plain` (`fake_keychain`): the preview's `after` carries the existing secret words; the value is the Keychain's.
  - `test_move_out_refuses_a_client_that_has_the_name`, `test_move_out_refuses_an_unknown_server` ("Choose a server in the Kitden gateway."), `test_move_out_needs_one_client`.
  - `test_move_out_clashes_with_a_rule_row_of_the_same_server` through `/api/batch/check`.
  - Frontend words, icon and pins as in Task 1.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement** the action, its words and the icon.
- [ ] **Step 4: Run** all four checks — expected: PASS. ROADMAP line.
- [ ] **Step 5: Commit** — `Gateway: move a server out to one client`.

### Task 3: Block looks

**Files:**
- Modify: `src/kitden/local_gateway/views.py` (`held_servers`: each `tool_list` entry gains `own_in`, the number of known projects with a rule of their own for that tool), `src/kitden/web/static/js/gateway.js` (`gatewayTree` block fields through small helpers; remove the local `icon()` / `ICONS` and use `icon()` from dom.js), `src/kitden/web/static/js/map-view.js` (`blockParts`: ports, lamp, mark, badge, ×; `.leaving` class with `tabindex="-1"`; the `"client"` kind check), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/unit/test_local_gateway_views.py`, `tests/frontend/gateway.test.mjs`, `map-view.test.mjs`, `tests/unit/test_page_words.py`, `test_contrast.py`

**Interfaces:**
- Consumes: `docs/mockup/gateway-notes.md` §1 (every size, colour token, time and word below comes from there).
- Produces in the block model: `lamp` (`"on"`, `"off"`, `"preview"`, `"out"` for outside servers), `stats: { clients, servers }` on the gateway block, `projects` on a tool (`own_in` under All projects; under a project, `"This project"` when it has its own rule), `ports: { left, right }`.
- Looks: server 170×60 — tile with its icon, sans name, lamp + "n of m on" (n rolls), count badge 20 px that hides when the server opens (opacity 200 ease, scale 300 spring), right port shown only while open; gateway 150×124 — house, "Kitden gateway", lamp + "On this Mac", stats `monitor` + "<n> clients" and `server` + "<n> servers" (singular for 1) that roll with `rollTo`; tool 200×34 — round 6 px mark (on / off / preview ring), name, project tag (`folder` 11 + "N projects" or "This project"); client 150×54 — tile, name, lamp + "Connected" / "Not connected", right port; outside 170×50 — grip only where the gateway can take it, icon, name, grey-ring lamp + "In <Client>", grey left port; caption "Outside the gateway · drag one in". Preview look: dashed `--preview-line` on `--preview-fill`, accent meta, a 18 px × badge shown on hover or keyboard focus (opacity 180 ease, scale 320 spring), title "In preview. Click to take it out." Leaving look: `filter: opacity(.45)`, dashed edge, `tabindex="-1"`. Lamp colour change 400 ease; a flip pops (server 2.2 → 1, client 2.4 → 1, mark 1.9 → 1; 200 CALM).

- [ ] **Step 1: Write the failing tests**
  - Python: `test_held_tools_count_the_projects_with_their_own_rule` — two projects with a rule for `read_file`, one without → `own_in == 2`; a tool with none → `0`.
  - gateway.test.mjs: `a server block carries its lamp and on count`, `the gateway block counts clients and servers, one in the singular`, `a tool says how many projects have their own rule, also under All projects`, `an outside block has a grey-ring lamp and a grip only where the gateway can take it`.
  - map-view.test.mjs: `a block draws its ports, and a server's right port shows only while open`, `a preview block has its × badge and its take-out title`, `a leaving block is dimmed, dashed and out of the Tab order`, `the gateway's numbers roll when they change` (reduced motion: set at once).
  - Pins: "drag one in", "In preview. Click to take it out.", "On this Mac"; contrast pairs for the lamp and mark colours.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement** the field, the model fields, the parts and the CSS.
- [ ] **Step 4: Update `docs/design.md`** (Gateway map blocks) and run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** on the demo home (`docs/development.md`) at 1440×900 in both themes beside frames D1–D3 (Pencil MCP) or the mockup.
- [ ] **Step 6: Commit** — `Gateway: blocks look like the mockup`.

### Task 4: The floating panel

**Files:**
- Modify: `src/kitden/web/static/js/panel.js` (`openPanel`, `closePanel`, `place`, `swapContent`; new `skeleton(kind)` and `stepTo(content, dir)`), `src/kitden/web/static/js/gateway.js` and `map.js` (`isNarrow` no longer counts open Details), `src/kitden/web/static/js/gateway-details.js` (`readThen` shows the skeleton first), `src/kitden/web/static/style.css` (`.drawer` floating look; the docked column rules go; the modal drawer's bottom rule from Phase 3 is replaced), `docs/design.md` ("A drawer has one motion" and the Details rows)
- Test: `tests/frontend/panel.test.mjs`, `gateway.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `gateway-notes.md` §3.1.
- Produces: at 1024 px and wider, Details float over the right of the content: right 22 px, top level with the map's first row, bottom 46 px above the content's bottom, width `min(320px, 100% - 44px)`, 10 px corners, padding 18, `--panel`, `--line` edge, `--shadow`; the panel stays in view while the page scrolls; the dock stays above it. Under 1024 px the modal drawer with its scrim and focus loop is unchanged. Motion: open 240 CALM (opacity 0, translateX 28 px scale .98 → none); close 180 ease-in (translateX 22 px); `skeleton(kind)` shows at once and the real content replaces it after `D(160)`, its children rising 6 px in 260 CALM, 20 ms apart; another block's Details while the panel is open swap through the skeleton without closing; `stepTo(content, "fwd" | "back")` — old children out 130 ease-in (translateX −18 / +18 px), new children in 220 CALM (from +22 / −22 px).

- [ ] **Step 1: Write the failing tests** in panel.test.mjs: `wide, Details float and the page keeps its width`, `under 1024 px Details are the modal drawer, with the dock above it`, `a panel shows its skeleton, then its content rises`, `another block's Details swap in place`, `a step forward and back slide the content`, `under reduced motion every panel state lands at once`; in gateway.test.mjs `opening Details no longer makes the map narrow`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** at 1440, 1100 and 900 px: Gateway, Library and Changes Details, with a tray row waiting.
- [ ] **Step 6: Commit** — `Details float beside the map`.

### Task 5: The server panel

**Files:**
- Modify: `src/kitden/web/static/js/gateway-details.js` (`heldCard`, `showHeld`, a new `moveOutStep`), `src/kitden/web/static/js/tools.js` (`toolRows` words and the per-project "Use all projects" link), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway-details.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `gateway-notes.md` §3.3 and §4.2; `toolsSection` / `toolRows` (tools.js); Task 2's `gateway.move_out` body; Task 4's `stepTo`.
- Produces: kicker "Server"; title the name, id "Remote · in the Kitden gateway" / "Local · in the Kitden gateway"; facts "Tools" ("n of m on"), "Comes from" ("All projects" or the project), "Clients" (the connected clients' tiles); head "Tools · All projects" / "Tools · <project>"; a list with "Whole server" ("n of m tools on" / "Every tool is off") and one switch per tool (name, "<Tool> · Reads only" / "May write"; under a project with its own rule, "Differs from all projects · Use all projects"). Buttons: "Move out of the gateway…" → `moveOutStep`: crumb "Server · <name>", title "Move <name> out of the gateway", "Pick the client that keeps it. You can also drag <name> onto a client on the map.", one radio row per client ("Uses the gateway now" / "Not connected to the gateway"); a pick adds the `gateway.move_out` row at once; foot "The other clients lose <name>'s tools." Under "More": strict mode, "Turn off every writing tool…", "Refresh tools", "Remove from the Kitden gateway…", "Put back in <Client>…", "Move secrets to the Keychain…" (D18). Every switch and button only adds a tray row; a second press on a pending switch takes its row out.

- [ ] **Step 1: Write the failing tests:** `the server panel lists its tools with a switch each and a Whole server row`, `a tool with its own rule in this project offers Use all projects`, `a tool switch pressed twice leaves the tray as it was` (Review Focus), `Move out steps to a client choice and a pick adds one move-out row`, `every action of today's server panel is still there, under More`; pins for the new words.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Gateway: the server panel switches tools and moves a server out`.

### Task 6: The tool panel and several projects

**Files:**
- Modify: `src/kitden/web/static/js/gateway-details.js` (`toolCard`, `showTool`, a new `projectsStep`; `projectChoice` leaves the Gateway), `src/kitden/web/static/js/gateway.js` (the tool block's pending tag), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway-details.test.mjs`, `gateway.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `gateway-notes.md` §3.4 and §5; the rules read the tool panel already makes (`/api/gateway/tools`, its `projects[]`); `ruleBody(server, tool, state, project)`; `keyFor`, `inTray`, `addToTray`, `takeOut`, `onTray` (tray.js); Task 4's `stepTo`.
- Produces: facts "Server" ("<server> · Remote|Local"), "Permission" ("On" / "Off"; in a project "On in this project" / "Off in this project" or "On · from all projects" / "Off · from all projects"), "Comes from", "Reported" ("Reads only" / "May write"), "Clients"; under All projects, "Projects with a rule of their own": one row per such project with "On" / "Off" and a "Show" button that picks that project; the sentence and buttons of §3.4 with the real client names. "Turn on|off in some projects…" → `projectsStep`: crumb "Tool · <Tool>", title "Turn on|off <Tool> in the projects you pick", "Every other project keeps the shared rule: on|off.", a "Find a project…" field, one checkbox row per project ("<n> own rule(s) · already on|off" rows disabled), "Done"; a tick adds that project's rule row, an untick takes exactly that row out; the foot says "Tick projects. Each one waits in preview until Apply." or "<n> project(s) in preview. Apply them from the tray." The map's tool block shows a pending tag (the project, or "N projects") while those rows wait.

- [ ] **Step 1: Write the failing tests:** `the tool panel says Permission and Reported in the mockup's words`, `Projects with a rule of their own lists each and Show picks it`, `in some projects: a tick adds that project's row, an untick takes only it out` (Review Focus), `a project already at the value cannot be ticked`, `the tool block shows the pending project while its rows wait`; pins.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Gateway: the tool panel and rules for several projects`.

### Task 7: Client, gateway, connection and outside panels

**Files:**
- Modify: `src/kitden/web/static/js/gateway-details.js` (`clientCard`, `kitdenCard`, `outsideCard`, a new `linkCard`), `src/kitden/web/static/js/gateway.js` (`clickLink` opens the connection panel; `linkRemoval` covers the client → gateway link with `client.disconnect`), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway-details.test.mjs`, `gateway.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `gateway-notes.md` §3.5–3.8 and §4.1; Task 1's `client.disconnect`; `kitdenClients(setup)` (parts.js) for each client's entry state.
- Produces:
  - Client: head with tile, name, "Version <v> · on this Mac"; facts "Gateway" (lamp + "Connected" / "Not connected", + " · change in preview" while a row waits), "Through Kitden" ("<n> servers · <m> tools on" / "Nothing yet"), "On its own" (chips of its outside servers / "Nothing"), "Projects"; the sentence of §3.5; buttons "Connect to the gateway…" (the client's `setup_server.register` or `setup_server.update` body) or "Disconnect from the gateway…" (`client.disconnect`), and "See what it loads in Library"; "Turn it on in <Client>…" and "Open <app>" under More (D18).
  - Gateway: head with the house, "Kitden gateway", "On this Mac"; facts "Servers" ("<n> in the gateway · <m> outside"), "Tools" ("<on> of <all> on"); "Clients" with one row per client and its "Connect…" / "Disconnect…" button; "Move all <n>…" and "Add another gateway…" under More.
  - Connection (new; a click on a link): title "<A> → <B>", the sub, facts "From", "To", "State", "Written in", the sentence of §3.7, and its remove button ("Disconnect <Client>…", "Remove <Server> from the gateway…", "Turn off <Tool>…"; "Take it out of the preview" for a tray link). A second click lets go.
  - Outside: head "Remote|Local · outside the gateway"; facts "Set up in", "Route" ("Direct, on its own"), "Kitden's rules" ("Don't reach it"); the sentence of §3.8; "Move into the gateway…" primary; "Remove direct entry…" and "+ Add to <Client>…" under More.
  - The client → gateway link's × adds `client.disconnect` ("Disconnect <Client>").

- [ ] **Step 1: Write the failing tests:** `a connected client offers Disconnect, a free one Connect`, `the client panel says what goes through Kitden and what runs on its own`, `the gateway panel lists every client with its own button`, `a click on a link opens the connection panel; a second click lets go`, `the client link's × adds a disconnect row`, `the outside panel keeps every action, the rest under More`; pins.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Gateway: client, gateway, connection and outside panels`.

### Task 8: The map shows connect, disconnect and move-out rows

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (`rowsOnMap` and the tree's tray rows), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/gateway.test.mjs`, `gateway-page.test.mjs`

**Interfaces:**
- Consumes: `gateway-notes.md` §4.1–4.2; the tray rows (`tray.rows`, Phase 3).
- Produces: a connect row draws a preview link client → gateway (accent dashes, fades in 300 CALM) and the client's meta " · in preview"; a disconnect row turns that link to leaving (muted dashes); a move-out row hides the server in the gateway, draws an outside preview block "Moves to <Client>" in the Outside list with a leaving link from the gateway and a preview bypass link from the client, and a click on that block takes the row out (D12). After Apply the map shows the server's state (Phase 3's rule: no tray rows while "applied").

- [ ] **Step 1: Write the failing tests:** `a connect row draws a dashed link to the gateway`, `a disconnect row makes the client's link leave`, `a move-out row shows the server outside, moving to its client`, `a press on the move-out block takes its row out`, `the List draws none of them`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** on the demo home: connect Cursor, disconnect Codex, move a server out to Claude Code, take one out from the map, Apply all, Undo all.
- [ ] **Step 6: Commit** — `Gateway: the map previews connect, disconnect and move out`.
