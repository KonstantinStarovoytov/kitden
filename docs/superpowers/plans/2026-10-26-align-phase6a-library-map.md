# Phase 6A: Library map, Details and skill rules — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Library page gets the mockup's map: clients → plugins and skills by source → what a plugin holds. It also gets the mockup's Details for each block and real "Turn off…" changes for skills and plugins. Behind it are the reads the map needs: Claude Code's local settings, `skillOverrides`, and what an installed plugin holds.

**Architecture:**
- **Backend.** Two read fixes go into the client adapters. A new view, `library_map(...)` in `views/library_map.py`, is served by `GET /api/library-map`. A new change action, `skill.rule`, goes through the tray like every other row.
- **Page.**
  - `library.js` keeps today's table as the List.
  - A new `library-map.js` draws the Map through the shared `mapView` (map-view.js) and `layoutTree` (map.js), the same way the Gateway does.
  - A new `library-details.js` builds each panel with `detailsCard` (details.js).
- **Phase 6B** comes after this plan and is not part of it. It holds the drags, link ×, the "+ Add" panel for plugins and skills, the Instructions map, the new List (Installed | Differences, Add missing), and the "In preview" forms.

**Tech Stack:** Python 3.13 + Starlette, pytest on sandbox homes; plain ES modules, one CSS file, node's test runner with each file's fake DOM.

**Spec:**
- Master plan `docs/superpowers/plans/2026-10-24-mockup-alignment.md`, Phase 6 (Tasks 6.1, 6.2, and the note "Carried from Phase 2"), and decisions D23–D27.
- `docs/superpowers/specs/2026-10-23-map-pages-design.md` Part 5: 5.1 the reads, 5.2 the tabs, 5.3 the tree, 5.5 the skill and plugin actions.
- `docs/mockup/library-notes.md`: the mockup's Library digest, with exact values and words. Sections 1–3, 9, 10 and 11 apply here.
- The frames in `design/kitden.pen`: `M7·1`–`M7·7`, `L1`, `L2`, `M11·4`, and the notes `Note · M7 · Library` and `Note · Library`.

## Decisions

- **Map and List.**
  - The Library gets Map | List like the Gateway. `library` joins `MAP_PAGES` (app.js), and `store.js` already knows `view=map|list` for it.
  - **List is today's six-tab table, unchanged, until Phase 6B rebuilds it.** Nothing the page can do today is lost.
  - The Map has the tabs "Plugins and skills" | "Instructions". In this plan, "Instructions" switches to the List's Instructions tab, and Phase 6B draws its map.
  - The view the page opens in follows `viewMode` as on the Gateway.
- **What the map shows** (spec 5.3).
  - Only what is on this computer and present in some client. A marketplace plugin no client has is not on the map; Phase 6B's add panel shows it.
  - Columns: "Clients", "Plugins and skills" and "Inside", at the mockup's x values (0, 250, 500, library-notes §2.1). The sizes are: client 150×54, plugin card 180×60, skill row 180×34, inside item 200×34.
  - Sources are group captions:
    - each marketplace's name, with the `store` icon;
    - "Your skills" (`user-round`) for skills in a client's own skills folder;
    - "Your settings" (`settings`) for hooks in a client's settings;
    - "Only this project" (`folder`) for a project's own items, shown only with a project picked.
  - Captions come in that order, and marketplaces in name order.
  - A hook is a slim row with the kind word "Hook" (`webhook` icon).
  - A group over six pages in place, five at a time, with the Gateway's paging (map.js `paging`, `turnPage`). The Inside column of an open plugin pages the same way, eight at a time.
- **Plugin card** (D25): the `puzzle` tile, the name, and a lamp with "<n> items" (the count of what Kitden read inside it). The lamp is green when the plugin is on in at least one client and grey when it is off in all of them. There is a round count badge that hides while the plugin is open. There is never "N of M on".
- **Links:**
  - a solid link from a client to each plugin or skill it loads;
  - a faint line where Cursor loads it through Claude Code;
  - no link for "Via Claude Code" when it is not loaded yet;
  - a link from a plugin to each inside item.

  In a project, the tag "This project" marks an item whose state there comes from the project's own settings.
- **Select and unfold** (library-notes §3.1):
  - A click on a plugin selects it, opens its Inside column (only one plugin is open at a time), lights the path and opens Details.
  - A click on the selected open plugin folds it.
  - A click on empty map lets go.
  - The page opens with no plugin open. The mockup opens Developer kit, but a real setup has no single first plugin.
- **Details** (library-notes §3.2–3.6, with D25), one `detailsCard` each:
  - **Plugin.** Facts: State, Inside ("3 skills · 1 command"), Clients, Comes from. Then the say line, then the actions:
    - "Add to <client>…", offered only when a client that can take it lacks it. Cursor is never offered (D26). It steps forward to a checklist ("Add <name> / to the clients you pick"), and each tick is one tray row (`plugin.install` for that client).
    - "Turn off for all projects…" adds one `plugin.disable` row per client that has it on.
    - In a project, "Turn off in this project…" (Claude Code only) adds the `skill.rule` row described below for the plugin.
    - "Technical details" holds the install path and the marketplace source.
  - **Inside item.** Facts: Plugin, Kind, Source, Clients. The say line is "Follows its plugin." There is no switch and no button (D25). For a skill there is one quiet line, "Turn off <plugin> in this project…", in a project and for Claude Code only (spec 5.5).
  - **Skill on its own.** Facts: Plugin ("None, a skill on its own"), State, Comes from, Source ("Your skills"), Clients. The actions are below.
  - **Hook.** Facts and Technical details only. Hooks have no switch today.
  - **Client.** "Loads in every project", a list of plugins ("Plugin · <n> items"), skills and hooks.
  - **Connection** (a click on a link): From, To, State, Written in, and the say line.
  - **Group caption** of a marketplace: its name, its plugins on the map, and Technical details (source). It has no actions in this plan.
- **Skill rules: the new action `skill.rule`** (spec 5.5).
  - Body: `{action: "skill.rule", targets: [{client, item}], params: {scope: "all" | "project", project?: "<id>", off: bool}}`. It is keyed `skill:<client>:<item>@<project or "">`.
  - **Claude Code, a skill not in a plugin:**
    - all projects sets `skillOverrides.<name> = "off"` in `~/.claude/settings.json`;
    - one project sets the same key in `<project>/.claude/settings.local.json`. It is offered only while the user settings have no `skillOverrides`, unless the docs confirm (with a date) that it merges key by key;
    - `off: false` in a project removes the project's key ("Use the shared rule…").
  - **Claude Code, a plugin in one project:** it sets `enabledPlugins.<plugin id> = false` in `<project>/.claude/settings.local.json`. The target item is the plugin.
  - **Codex, a skill:** all projects adds `[[skills.config]]` with its `path` and `enabled = false` in `config.toml`. Codex has no project switch, and Details says so.
  - **Cursor:** no switch. Details says "Cursor has no switch to turn off one skill."
  - **Words:**
    - the title is "Turn off <name> for all projects" or "Turn off <name> in <folder>";
    - the done words are "Turned off <name> …";
    - an all-projects change says when a project keeps its own rule;
    - a project file that has its own `skillOverrides` is named: "<folder> has its own skill settings; it may keep this skill on."
  - **Skill Details actions:**
    - "Turn off for all projects…" adds one row per client that can.
    - "Turn off in some projects…" steps forward to the Gateway's project checklist (D13). Each tick is one row. The step offers only Claude Code.
- **Reads** (spec 5.1):
  - `<project>/.claude/settings.local.json` `enabledPlugins` is read. Local wins over project, and project over user.
  - `skillOverrides` is read in user, project and local settings, key by key, with the most specific file winning. A skill set to `"off"` shows Off. The code comment says the key-by-key merge is not confirmed by the docs, unless a dated check confirms it.
- **What an installed plugin holds** is read with `catalog._inside()` on the installed folder: Claude Code's `installPath`, Codex's plugin cache and Cursor's plugin folders. It is cached by the folder signature (the mtimes of the plugin files read) and gives skills, commands, agents, hooks and MCP servers, by name.
- **Words** (mockup, with D23–D25):
  - lede: "Follow the source. Connect only what you need.";
  - scope bar: "Shared setup · project overrides stay separate", or "Project <name>" with the `folder` icon;
  - hint line on the Map: "Point at a link for its Details · click a plugin to see what it holds · Turn off… waits in preview, then Apply". Phase 6B puts the mockup's drag and × words back when they work.
  - The client state words come from Kitden's own facts ("Connected", "Via Claude Code", "Off"), never from fixed text.

## Global Constraints

- `AGENTS.md` in full: simple English in code, comments and page words. Tests use sandbox homes only. Dated facts about other tools: check Claude Code's settings and skills docs and Codex's config docs, and write the date beside each claim.
- Every write is preview → Apply with a backup → verify → Undo through `src/kitden/changes/engine.py`. A press, a tick or a switch only adds a tray row (`addToTray`); nothing writes without the tray's Apply.
- Main pages show a name, the client and an action. Paths, addresses, commands, ids and file lines stay under Technical details.
- CSP stays `script-src 'self'; style-src 'self'`: no innerHTML, no inline `style=""` in strings, no `<style>`, no `cssText`. Use CSSOM properties and `setProperty` only, and icons through `icon()`. Add any missing lucide icon data to icons.js.
- Calm motion only, from `motion.js`. Every motion has a reduced-motion path that lands at once. Nothing stays at opacity 0, nothing loops, and there is one motion per change.
- `docs/design.md` changes in the same commit as the page change it describes. New page words are pinned in `tests/unit/test_page_words.py`. `tests/unit/test_contrast.py` keeps 4.5:1 (3:1 for edges and focus rings) in both themes.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`.
- `ROADMAP.md` gets its line in the same commit when a task changes what Kitden does.
- Never stage `design/`. No `git stash`. Never `pkill -f kitden`; stop only a process you started, by its pid. The owner's pages run from `/tmp/kitden-check`; leave them.
- Do not grow `gatewayTree` (gateway.js), `layoutTree` (map.js), `showDetails` (details.js), `toolsSection` (tools.js) or `mapView`'s `draw` (map-view.js). Add small named helpers instead. Pins in test_page_words.py that name library.js source strings must keep passing, or be moved with the code they pin.
- Commit messages: a short plain subject, one to three simple lines, ending with the Co-Authored-By line of the model that wrote the commit.

## Review Focus

- **The owner's real setup has a marketplace with dozens of plugins and a plugin with twenty skills.** The map pages each group and the Inside column, and nothing overflows its block. Test in Task 5 with a large sandbox home.
- **`skillOverrides` is in more than one file**, and a project's local file sets one key while the user file sets another. The skill shows the most specific one, and an all-projects change names the project that keeps its own rule. Test in Tasks 1 and 4.
- **A plugin turned off in a project's local settings but on for the user:** in that project it shows Off with the "This project" tag; under All projects it shows On. Test in Tasks 1 and 3.
- **Apply all with a skill rule and a plugin disable that edit the same `settings.json`:** both apply as one change, and Undo all puts the file back byte for byte. Test in Task 4.
- **A project switch while the map shows an open plugin and its Details:** the map changes in place for the new project, and the Details follow or let go, as on the Gateway. Test in Task 6.

---

### Task 1: Claude Code's local settings and `skillOverrides`

**Files:**
- Modify: `src/kitden/clients/claude_code.py` (read `<project>/.claude/settings.local.json` `enabledPlugins` with local > project > user; read `skillOverrides` in user, project and local settings)
- Test: `tests/unit/test_claude_code_settings.py` (create), and the fixture home helpers it needs under `tests/fixtures`

**Interfaces:**
- Consumes: `ClaudeCodeAdapter` reading of `settings.json` and `enabledPlugins` today; `Enabled`, `Scope` (model.py).
- Produces:
  - A plugin item's `enabled` and its scope source follow local > project > user in a project. With no project, only the user file counts.
  - A skill item that `skillOverrides` sets to `"off"` (key by key, the most specific file winning) has `Enabled.OFF`, and its rule source is `Scope.USER`, `Scope.PROJECT` or `Scope.LOCAL`.
  - Each item keeps where its state came from, so the map can tag "This project".
  - Unknown values in `skillOverrides` are ignored: only `"off"` turns a skill off, as the docs say. Write the date you checked beside it.

- [ ] **Step 1: Check the docs** (code.claude.com/docs/en/settings, /en/skills, /en/plugins). Date the claims about `enabledPlugins` precedence and `skillOverrides` in a code comment.
- [ ] **Step 2: Write the failing tests:**
  - `test_local_enabled_plugins_win_over_project_and_user`;
  - `test_skill_overrides_off_in_user_settings_turns_the_skill_off`;
  - `test_skill_overrides_most_specific_file_wins_key_by_key` (Review Focus);
  - `test_a_project_off_plugin_shows_on_under_all_projects` (Review Focus);
  - `test_unknown_skill_override_values_are_ignored`.
- [ ] **Step 3: Run** them — expected: FAIL.
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Run** all four checks — expected: PASS.
- [ ] **Step 6: Commit** — `Claude Code: read local settings and skillOverrides`.

### Task 2: What an installed plugin holds

**Files:**
- Modify: `src/kitden/views/catalog.py` (`installed_inside(adapters) -> dict[str, dict]`, cached by folder signature), `src/kitden/clients/claude_code.py` / `codex.py` / `cursor.py` (each adapter's `plugin_folders() -> dict[str, Path]`, plugin id → installed folder; Cursor's exists)
- Test: `tests/unit/test_installed_inside.py` (create)

**Interfaces:**
- Consumes: `_inside(folder, entry)` (catalog.py); Claude Code's `installPath` in `installed_plugins.json`; Codex's plugin cache (`_cached_plugins`); Cursor's `plugin_folders()`.
- Produces `installed_inside(adapters) -> dict[plugin_id, {skills, commands, agents, hooks, mcp_servers}]`. Each part is a sorted list of names, and `mcp_servers` keeps names only (no `runs`). Its cache is keyed by `(folder, max mtime of the plugin files read)`, so a second call without file changes reads nothing.

- [ ] **Step 1: Write the failing tests:**
  - `test_installed_inside_lists_what_each_installed_plugin_holds` (medium demo: superpowers holds its two skills, pr-review its server);
  - `test_installed_inside_reads_each_folder_once_until_it_changes`;
  - `test_installed_inside_keeps_no_command_lines`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Library: read what an installed plugin holds`.

### Task 3: The Library map's data

**Files:**
- Create: `src/kitden/views/library_map.py` (`library_map(inventory, adapters, project) -> dict`)
- Modify: `src/kitden/web/app.py` (`GET /api/library-map?project=`), `src/kitden/demo/sample.py` (only if the large sample lacks a plugin with many skills: add one with twenty skills to the large size)
- Test: `tests/unit/test_library_map.py` (create), `tests/security/test_no_secrets.py` (sweep gains `/api/library-map`)

**Interfaces:**
- Consumes: Task 1's states and rule sources; Task 2's `installed_inside`; the inventory items (`ItemKind.PLUGIN`, `SKILL`, `HOOK`); `CLIENT_WORDS`.
- Produces `library_map(...)`, which returns:
  - `{clients: [{id, name, state: "on" | "off" | "via" | "missing" | "unreadable", words}], groups: [{key, name, icon, kind: "marketplace" | "skills" | "settings" | "project", items: [...]}]}`;
  - an item is `{id, name, kind: "plugin" | "skill" | "hook", plugin?: <plugin id>, inside?: {skills, commands, agents, hooks, mcp_servers}, count?: n, by: {client: "on" | "off" | "via"}, here?: bool, source, technical: {path?, marketplace?}}`.

  Groups are ordered as in Decisions. `here` is true when the item's state in the picked project comes from the project's own settings. `technical` holds what the Technical details fold shows (paths only there).
- Produces `GET /api/library-map?project=<id>`, with the same token and origin checks as other GETs.

- [ ] **Step 1: Write the failing tests:**
  - `test_library_map_groups_by_source_in_order`;
  - `test_a_plugin_counts_what_it_holds_and_never_says_n_of_m`;
  - `test_cursor_via_claude_code_has_no_link_until_loaded`;
  - `test_a_project_rule_marks_here` (Review Focus);
  - `test_hooks_sit_under_your_settings`;
  - `test_a_marketplace_plugin_no_client_has_is_not_on_the_map`;
  - `test_library_map_answer_has_no_paths_outside_technical`;
  - and the secrets sweep.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Library: the map's data`.

### Task 4: The `skill.rule` change

**Files:**
- Modify: `src/kitden/changes/actions.py` (`SKILL_RULE = "skill.rule"`, `skill_rule_steps(adapters, inventory, home, targets, params) -> list[Step]`), `src/kitden/clients/claude_code.py` and `codex.py` (the edit steps: a JSON key in `settings.json` / `settings.local.json`, a `[[skills.config]]` table in `config.toml`, through the existing `json_splice` / `toml_edit` helpers), `src/kitden/web/app.py` (the preview branch), `src/kitden/views/after.py`, `src/kitden/views/words.py`, `src/kitden/web/static/js/review.js` (title and done words), `src/kitden/web/static/js/tray.js` (`keyFor`: `skill:<client>:<item>@<project>`), `src/kitden/web/static/js/parts.js` (the Changes line)
- Test: `tests/unit/test_skill_rule.py` (create), `tests/unit/test_api_batch.py`, `tests/frontend/tray.test.mjs`, `tests/frontend/review.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: the body and rules in Decisions ("Skill rules"); Task 1's reads (to know what is on and where a rule lives); the engine's file edit steps.
- Produces `skill.rule` for:
  - Claude Code skills (all projects, one project, or the project's key removed);
  - a Claude Code plugin in one project (`enabledPlugins` in local settings);
  - Codex skills (all projects).

  It refuses Cursor ("Cursor has no switch to turn off one skill.") and a Claude Code one-project rule while the user settings have `skillOverrides` and the docs do not confirm the merge ("Claude Code may not merge skill settings across files; turn it off for all projects instead."). Every step can Undo byte for byte.

- [ ] **Step 1: Check the docs** (Claude Code settings and skills; Codex config `[[skills.config]]`). Date the claims in the code comments.
- [ ] **Step 2: Write the failing tests:**
  - `test_turn_off_a_claude_code_skill_for_all_projects_and_undo`;
  - `test_turn_off_in_one_project_writes_the_local_settings_and_undo`;
  - `test_use_the_shared_rule_removes_the_project_key`;
  - `test_turn_off_a_plugin_in_one_project`;
  - `test_turn_off_a_codex_skill_adds_skills_config_and_undo`;
  - `test_cursor_is_refused_with_its_reason`;
  - `test_an_all_projects_change_names_a_project_that_keeps_its_own_rule` (Review Focus);
  - `test_apply_all_with_a_rule_and_a_disable_on_one_settings_file` (Review Focus, tray batch);
  - node tests for `keyFor`, the title and the done words;
  - the pins.
- [ ] **Step 3: Run** them — expected: FAIL.
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Run** all four checks — expected: PASS.
- [ ] **Step 6: Commit** — `Library: turn a skill or a plugin off, with Undo`.

### Task 5: The Library map

**Files:**
- Create: `src/kitden/web/static/js/library-map.js` (`renderLibraryMap(main)`, `libraryTree(data, { open, pages }) -> { columns, blocks, links }`)
- Modify:
  - `src/kitden/web/static/js/library.js` (the page head with Map | List; List renders today's table; Map calls `renderLibraryMap`);
  - `src/kitden/web/static/js/app.js` (`MAP_PAGES` adds `library`);
  - `src/kitden/web/static/js/map-view.js` (`mapView({ …, enterDelay })` replaces the read of `afterOldPage()` inside the entrance, carried from Phase 2, without growing `draw`);
  - `src/kitden/web/static/style.css`, `docs/design.md`.
- Test: `tests/frontend/library-map.test.mjs` (create), `tests/frontend/map-view.test.mjs`, `tests/frontend/library.test.mjs`, `tests/unit/test_page_words.py`, `tests/unit/test_contrast.py`

**Interfaces:**
- Consumes: Task 3's `/api/library-map`; `mapView`, `layoutTree`, `paging`, `turnPage`, `pagesWith` (map.js); the Gateway's block looks (lamps, ports, badges); `setHint` (parts.js); `viewMode` (store.js); `library-notes.md` §1, §2 and §10.
- Produces:
  - **The head:** title "Library", the lede, the tabs "Plugins and skills" | "Instructions" (`.seg.sm`, 280 CALM glide), the scope bar, Map | List at the right, and the hint line on the Map.
  - **The columns and blocks:** as in Decisions, at the mockup's x and sizes, with group captions, paging (five a page; Inside eight a page), the plugin card ("<n> items" and the badge), skill and hook rows, inside rows (no mark switch), the links and the "This project" tag.
  - **The entrance** (library-notes §2.7): blocks rise y 6 → 0, 260 OUT3, 22 apart, after `enterDelay`.
  - **Find** dims what does not match, as on the Gateway.
  - **"Instructions"** on the Map switches to the List's Instructions tab (`view=list&kind=instructions`).
  - **Old links** `#library?kind=mcp_server` land on the Gateway List. `kind=hook` and `kind=marketplace` land on the Map. Other kinds keep the List.
  - **Reduced motion:** everything lands at once.

- [ ] **Step 1: Write the failing tests:**
  - `the head has the tabs, the lede, the scope bar and Map | List`;
  - `List shows today's table and keeps its six tabs`;
  - `the map draws clients, captions in source order, plugin cards with n items, skill and hook rows`;
  - `no block says N of M on`;
  - `a big group and a big plugin page in place and nothing overflows` (Review Focus, large sandbox data);
  - `Cursor via Claude Code draws a faint line or none`;
  - `the entrance waits enterDelay and rises 22 apart`;
  - `find dims what does not match`;
  - `old kind links land in their new place`;
  - `under reduced motion it lands at once`;
  - pin the words;
  - contrast for any new colour.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`** (a Library map section) and `ROADMAP.md` (one Library line). Run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** on the medium and large demo at 1440×900 in both themes, beside frames `M7·1` and `M11·4` (Pencil MCP `TakeScreenshot`).
- [ ] **Step 6: Commit** — `Library: the map`.

### Task 6: Select, unfold and Details

**Files:**
- Create: `src/kitden/web/static/js/library-details.js` (one builder per block kind, each returning a `detailsCard` spec)
- Modify: `src/kitden/web/static/js/library-map.js` (select, unfold, path light, let go, project switch in place), `src/kitden/web/static/js/details.js` (only if `detailsCard` lacks a part the panels need), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/library-details.test.mjs` (create), `tests/frontend/library-map.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes:
  - Task 3's data and Task 4's `skill.rule` body;
  - `plugin.install` for one client and `plugin.disable` (their existing bodies and keys);
  - `detailsCard`, `previewButton`, `stepTo` and the Gateway's project checklist step (D13, `gateway-details.js`);
  - `holdPanel` and `followProject` for the project switch in place;
  - `library-notes.md` §3 with D25 and D26.
- Produces:
  - **The click rules and the path light** of Decisions, with the unfold (stay-blocks 260 OUT3, inside rows grow 220 OUT3 from the plugin, 15 apart, and fold back 160 IN3). One plugin is open at a time.
  - **Details:**
    - plugin, with "Add to <client>…" stepping forward to the checklist (each tick one `plugin.install` row; a ticked row says "In preview"; Cursor is never listed as a choice);
    - inside item ("Follows its plugin.");
    - skill, with "Turn off for all projects…" and "Turn off in some projects…" (the project checklist; one `skill.rule` row a tick);
    - hook, client, connection, and marketplace caption.

    All words are as in Decisions, and paths stay under Technical details.
  - **A project switch** redraws the map in place. An open plugin stays open when it is still there. Details follow the same item, or close when it is gone (Review Focus).
  - **Keyboard and focus:** Enter and Space on a block are the click. Focus moves into Details on open and back on close. Escape closes.

- [ ] **Step 1: Write the failing tests:**
  - `a click on a plugin opens its Inside column, lights the path and opens Details`;
  - `a second click on the open selected plugin folds it`;
  - `plugin Details show the facts and Add to <client>… steps to a checklist; each tick is one row`;
  - `Cursor is never a choice for a plugin`;
  - `an inside item says Follows its plugin and has no switch`;
  - `a skill's Turn off for all projects adds one skill.rule row per client that can`;
  - `Turn off in some projects… uses the project checklist`;
  - `a project switch keeps an open plugin and its Details, or lets go when it is gone` (Review Focus);
  - `Enter opens, Escape closes and focus returns`;
  - `under reduced motion the unfold lands at once`;
  - pin the words.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`;** run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** beside frames `M7·2`–`M7·5` and `M7·7`.
- [ ] **Step 6: Commit** — `Library: select, unfold and Details`.
