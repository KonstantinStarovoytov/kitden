# Part 5: The Library map, list and marketplace adds — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Library shows plugins and skills as one tree by source, on a map and in a List
with Differences and Add missing in four groups. It reads what Claude Code's project-local
settings and installed plugins really hold. Details turns a skill or plugin off where the client
has a switch, and "+ Add" previews a marketplace plugin, skill or gateway server on the map.

**Architecture:** Read fixes come first.
- Each key of Claude Code's `skillOverrides` becomes an item of a new kind, `skill_rule`. The
  effective view applies these items, and the load map folds them into the skill's row.
- Plugins in `.claude/settings.local.json` become `local` plugin items, which the rank table
  already orders.
- An installed plugin's parts come from `catalog._inside()` on its installed folder, cached by a
  folder signature.

The "Plugins and skills" tab (`/api/library?kind=plugin`) groups rows by source and gives each
plugin its parts. The page draws that answer as a List or through Part 4's `map.js`. Switches are
two new engine actions, `skill.rule` and `plugin.rule`. Marketplace adds are today's install
actions plus a new `gateway.add`. All of them go through preview → Apply → verify → Undo, shown
with Part 4's map review.

**Tech Stack:** Python 3.13, Starlette, tomlkit; plain ES modules and one CSS file; pytest on
sandbox homes and the Part 1 samples; node's test runner. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-23-map-pages-design.md`, Part 5 (5.1–5.6), with the
shared pieces S.1–S.8. The Rules and names table of `docs/superpowers/plans/2026-10-22-visual-management.md` bind this plan. Part 4's helpers are consumed by the
signatures in the Interfaces of `docs/superpowers/plans/2026-10-23-map-part4-gateway.md`. The old
Part 4 plan (`git show d8c05cc:docs/superpowers/plans/2026-10-22-visual-part4-compare.md`) is
cited as "old Part 4 Task N": take that task's tests and words as written, with the changes named
here.

## Global Constraints

- `AGENTS.md` in full:
  - simple English in code, comments, UI and docs;
  - every write goes through preview → Apply with a backup → verify → Undo (`changes/engine.py`);
  - tests on sandbox homes only (`make_home`, `write_cursor_fixture_state`,
    `build_demo_home(root, size)`), with no real client, MCP server, Keychain or network.
- Main pages show a name, the client, a state and an action. Paths, keys and commands stay under
  Technical details.
- `docs/design.md` changes in the same commit as its page change. New page words are pinned in
  `tests/unit/test_page_words.py`. Page logic is a pure exported function with a node test.
- `explain()` and `project_views()` feed the read-only MCP server. Run
  `tests/unit/test_mcp_server.py` after changing them. No file lines go to agents.
- Facts about other tools: each task that relies on one starts with a docs check and writes
  `checked <date>` beside the claim. What the docs do not confirm is "not checked" and not
  built.
- Words, exactly (map spec, frames L1–L4 and D6):
  - names and groups: "On", "Off", "Via Claude Code", "+ Add", "This project", "Only this
    project", "Plugins and skills", "Instructions", "Your skills", "Your settings";
  - the List: "Installed", "Differences", "Add missing plugins and skills…", "Add missing
    servers…", "Will add", "Already there another way", "Needs your decision", "Kitden cannot
    add";
  - switches: "Turn off for all projects…", "Turn off in one project…", "Use the shared rule…",
    "Turn off <plugin> in this project…", "Cursor has no switch to turn off one skill.", "<folder>
    has its own skill settings; it may keep this skill on.";
  - the add panel: "Add a marketplace…", "Add a plugin or skill", "Add a server", "Search the
    marketplaces…", "Click to preview, or drag onto a client.", "In preview", "In the gateway",
    "Added", "Remote", "Local", "signs in with OAuth; it waits for sign-in".
- Kitden never shows a tool count for a marketplace server. It sends no request to any server
  before Apply, except one `initialize` with no secret to a remote server's own address after the
  person picks it.
- Nothing new runs at start. `scripts/measure-start.py` stays within its budgets.
- Before each commit, run `uv run pytest -q`, `uv run ruff check .`,
  `uv run ruff format --check src tests` and `node --test tests/frontend/*.test.mjs`. All must
  pass.
- Commits stage files by name. Each has a short plain subject, one to three lines, and the
  session's co-author line.
- `ROADMAP.md`, `design/` and the owner's research files are never edited or staged.

## Review Focus

1. **A project's `.claude/settings.local.json` breaks while the page runs.** Its switches stay,
   kept from the last good read. A switch into it is refused with the unread words.
   - Task 1 `test_a_broken_local_settings_file_keeps_its_switches_from_the_last_good_read`
   - Task 7 `test_a_switch_into_a_broken_local_file_is_refused`
2. **A known project on another disk.** A one-project switch there previews, applies and undoes.
   - Task 7 `test_a_one_project_switch_applies_in_a_project_outside_home`
3. **The user settings already have `skillOverrides`.** "Turn off in one project…" is not
   offered, and the server refuses it with the reason. An all-projects change names each project
   file with its own `skillOverrides`.
   - Task 7 `test_one_project_switch_waits_while_the_user_file_has_skill_overrides`
   - Task 7 `test_turning_off_for_all_projects_names_projects_with_their_own_skill_settings`
4. **A marketplace server the gateway cannot run.** A reason Kitden can know without the network
   shows on the result, with no grip, and the preview refuses with the same words. OAuth is found
   at preview, and nothing is written.
   - Task 10 `test_market_servers_say_why_before_any_preview`
   - Task 10 `test_an_oauth_server_is_refused_at_preview_and_nothing_is_written`
5. **Two plugins or skills with one name from different sources.** They stay two rows and two
   blocks, each with its own parts. Differences keeps a Needs review row, and Add missing puts the
   name under "Needs your decision".
   - Task 3 `test_same_name_plugins_from_two_marketplaces_stay_apart`
   - Task 4 `test_rows_differ_by_state_class_unknown_and_needs_review`
   - Task 5 `test_a_name_with_two_sources_is_a_decision_and_never_checked`

Also pinned, from the master Review Focus: the large sample opens in List, its layout stays under
16 ms, and long names are cut (Task 6).

## Carried from Part 4 (2026-10-24)

- `app.js` calls `leaveMap()` on every place that is not the Gateway, and `mapPreview` records no
  page. Before the Library map uses `previewOnMap` (Task 9), give the preview its page, or the
  Library will drop its own preview on each render.
- With Details docked, the Library table clips words at 1024–1150 px. Task 4 replaces the table.
- The Gateway's outside server Details have no finding callouts and no "Compare across clients".
  The Library's MCP Details had both. Bring the callouts over before Task 4 takes MCP rows out of
  the Library.
- In the Gateway List, `gridKey` folds a group on Enter. The Library's marketplace captions open
  Details on Enter (Task 6), so `gridKey` needs that case.

## Names this part shares with other parts

- **Consumes from Part 4**, under the master names and Part 4's signatures:
  - `map.js`: `layoutTree`, `litPath` (which follows faint links), `litFrom` (for a selected
    client), `findIn`, `findChip`, `dropAt`, `drawMap` (with `onAdd(columnId)`, captions as
    buttons), `toggleOpen`, `unfoldDelays`, `isNarrow`; the tree model, with `group:<id>`
    captions and `client:<id>` blocks;
  - `dom.js`: `cutName`, `gridKey(rows, at, key)`;
  - `store.js`: `state.mode` (hash `view=map|list`), `MAP_AT`, `viewMode`, and the selection
    kinds `client` and `group`;
  - `parts.js`: `scopeText` and `scopeBar(folder, count)`. `library.js` keeps its own
    `scopeLine`, the quiet line about where an Add goes. `/api/projects` `own_rules`;
  - `panel.js` and `details.js`: `openPanel(…, { dock })`, `docksAt`, `factsBlock`,
    `detailsCard({ kind, title, id, facts, why, actions, technical, more, after })` with actions
    `{label, run?, body?, primary?}`, and `projectChoice(projects, picked, onPick)`;
  - `map-review.js` (it reads no Gateway module): `mapPreview`, `previewOnMap(body, redraw)`,
    `applyOnMap`, `cancelOnMap`, `showMapReview`, `barWords`, `reviewBar(change, { body,
    onApply, onCancel, onShow })`, and for a page's bar `previewBar(redraw)` and
    `redrawPreview(redraw, { same, ended })`; `review.js` keeps `appliedToast`;
  - `gateway.js`: `gatewayTree(…, { preview: {name, kind} })`; `app.js`: `MAP_PAGES`, which gains
    `"library"`;
  - `clients/entries.py`: `gateway_entry`, `reads_elsewhere`; `local_gateway/views.py`:
    `own_rules(settings, chain)`.
- **Part 4's rulings this part builds on:**
  - Until this part groups them, a Library cell for an item only one project has carries the tag
    "Only this project". The group replaces it here (Task 3).
  - A tool's `state` is its rule's own state, and `effective` adds the server's switch. Nothing in
    this part reads tool states.
- **Consumes from Parts 1–3:**
  - `build_demo_home`, `demo_build`, `demo_page`, `preview` and `POST`
    (`tests/unit/test_demo_mode.py`);
  - `kept_refusal`, `unread_refusal`, `ADD_ACTIONS` (`web/app.py`);
  - `changeWords`, `PLACE_IN_TITLE`, `ADDS`, `alignGroups`, `chosenKeys`, `showReview`
    (`review.js`);
  - `contextLinks`, `techRows`, `technical`, `whyLines`, `affectsText` (`details.js`);
  - `addForm` and `addSkillForm` (`offer.js`).
- **Produces, master names:** hash `show=diff`; align groups `will_add`, `already`, `decide`,
  `cannot`; `gateway.add`; `GET /api/market-servers?q=` → `{servers: [{id, name, plugin,
  marketplace, kind, held, refusal}]}`; the Library's share of `own_rules`.
- **Produces, which Part 6 consumes:** `TABS`, `libraryTab(kind)` (the tab is `kind=plugin` or
  `kind=instructions`), the Instructions tab's List (today's table), the Library's Map | List and
  find wiring, `linkKind(cell)`, and "Add missing plugins and skills…".
- **Produces, new here:**
  - `ItemKind.SKILL_RULE`, `EffectiveView.rules` and `.shared`, `project_rule(view, name)`;
  - `plugin_folders()`, `installed_inside(adapters)`;
  - `project_exceptions`, `library_rules`, `differs`;
  - `skill.rule`, `plugin.rule`, `switch_offers`;
  - `libraryModel`, `libraryRows`, `addpanel.js`;
  - `served(home)` in `test_demo_mode.py`.

---

### Task 1: Read Claude Code's local settings and skill switches (5.1)

**Files:**
- Modify: `src/kitden/model.py` (`ItemKind`), `src/kitden/clients/claude_code.py` (`scan`, `_project_files`; new `_skill_rules`), `src/kitden/views/effective.py`, `src/kitden/views/load_map.py` (`row_key`, `load_map`, `_cell`; new `project_rule`), `src/kitden/views/explain.py` (`_matches`, `why`)
- Test: `tests/unit/test_skill_rules.py` (create); run `tests/unit/test_mcp_server.py`

**Interfaces:**
- Produces `ItemKind.SKILL_RULE = "skill_rule"`. Each item is one key of `skillOverrides` in one
  settings file:
  - `name`: the skill's name; source `file_source(path, "claude_code", "skillOverrides.<name>")`;
  - `scope`: `USER` (`~/.claude/settings.json`), `PROJECT` (`<p>/.claude/settings.json`) or
    `LOCAL` (`<p>/.claude/settings.local.json`); `project` is set for the last two;
  - `enabled`: `OFF` for `"off"`, `ON` for `"on"`, `"name-only"` and `"user-invocable-only"`,
    and `UNKNOWN` for anything else;
  - `summary`: `(("value", <text>),)`.
- Produces `PLUGIN` items from `<p>/.claude/settings.local.json` `enabledPlugins`, with
  `Scope.LOCAL` and key `enabledPlugins.<id>`. `RANKS` already ranks `LOCAL` over `PROJECT` over
  `USER`.
- Produces, for Claude Code and its Desktop tab:
  - `RULE_RANKS = {Scope.USER: 1, Scope.PROJECT: 2, Scope.LOCAL: 3}`;
  - `EffectiveView.rules: dict[str, Item]`: the deciding rule for each skill name;
  - `EffectiveView.shared: dict[str, Item]`: the user file's rule, when there is one.

  Rules are never in `items` or `shadowed`. A Claude Code skill that is not from a plugin does
  not load when its deciding rule is `OFF`.
- Produces `project_rule(view, name) -> Item | None`. It returns the deciding rule when it is the
  view's project's and its load state differs from `view.shared`'s (default on), else None.
  `_cell` uses it in three ways:
  - origin is `"override"` for a skill that applies to all projects;
  - the rule's id joins `cell.items`, and its `stale_at` joins the cell's;
  - an `UNKNOWN` deciding rule turns "on" into "unk".
- A rule never makes a row of its own. `row_key` maps it onto `_hash(ItemKind.SKILL, name)`. A
  rule whose skill has no row is dropped.
- `explain(kind="skill")` also lists rules. `why()` for a rule says one of:
  - "Turns it off in this project." / "Turns it off for all projects.";
  - "Keeps it on in this project." / "Keeps it on for all projects.";
  - "Does not decide here: a more specific setting wins.".
- Builder calls:
  - A rule never touches a `Scope.PLUGIN` skill.
  - When a project is the home folder, no project rule is read from its `.claude/settings.json`,
    as `_project_files` already skips that folder.
  - Hooks in `settings.local.json` are not read: the spec does not ask for them.

- [ ] **Step 1: Check the docs.**
  - code.claude.com/docs/en/settings: the settings files, local over project over user, and
    `enabledPlugins` in each.
  - /en/skills: the `skillOverrides` values, which name keys an override, and "Overrides don't
    apply to plugin skills".

  Write `checked <date>` above `_skill_rules` and above the local `enabledPlugins` read. Unless the
  docs now say how `skillOverrides` merges across files, the comment says "not checked: read key
  by key, as enabledPlugins merges; the most specific file that sets a skill's key wins". If a fact
  differs from the spec's check of 2026-10-23, stop and report.
- [ ] **Step 2: Write the failing tests**

```python
# tests/unit/test_skill_rules.py
PLUGIN = "superpowers@demo-market"
# fixture `medium` = build_demo_home(tmp_path, "medium"); `_merge(path, **keys)` adds top-level keys
# to a JSON file, making it when missing.

def _loads(inventory, project, kind=ItemKind.SKILL):
    return {i.name for i in effective_view(inventory, "claude_code", project).items if i.kind is kind}

def _cell(inventory, name, project, kind="skill"):
    return next(r for r in load_map(inventory, project) if r.name == name and str(r.kind) == kind).cells["claude_code"]

def test_local_settings_win_over_project_and_user_for_a_plugin(medium):
    atlas = medium / "work/atlas"
    _merge(atlas / ".claude/settings.json", enabledPlugins={PLUGIN: True})
    _merge(atlas / ".claude/settings.local.json", enabledPlugins={PLUGIN: False})
    inventory = build_inventory(medium)
    local = [i for i in inventory.items if i.kind is ItemKind.PLUGIN and i.scope is Scope.LOCAL]
    assert [(i.name, i.project, i.enabled) for i in local] == [(PLUGIN, str(atlas), Enabled.OFF)]
    assert PLUGIN not in _loads(inventory, str(atlas), ItemKind.PLUGIN) and PLUGIN in _loads(inventory, None, ItemKind.PLUGIN)
    cell = _cell(inventory, "superpowers", str(atlas), "plugin")
    assert (cell.state, cell.origin) == ("off", "override")

def test_skill_overrides_merge_key_by_key_and_the_most_specific_file_wins(medium):
    atlas = medium / "work/atlas"
    _merge(medium / ".claude/settings.json", skillOverrides={"brandkit": "off"})
    _merge(atlas / ".claude/settings.local.json", skillOverrides={"brandkit": "on", "release-notes": "off"})
    inventory = build_inventory(medium)
    assert {"brandkit", "release-notes"} & _loads(inventory, None) == {"release-notes"}
    assert {"brandkit", "release-notes"} & _loads(inventory, str(atlas)) == {"brandkit"}
    shared = _cell(inventory, "brandkit", None)
    assert (shared.state, shared.origin) == ("off", None)
    here, notes = _cell(inventory, "brandkit", str(atlas)), _cell(inventory, "release-notes", str(atlas))
    assert (here.state, here.origin, notes.state, notes.origin) == ("on", "override", "off", "override")
    # A project rule that gives what the shared setup gives is not this project's own rule.
    (atlas / ".claude/settings.local.json").write_text('{"skillOverrides": {"brandkit": "off"}}')
    assert _cell(build_inventory(medium), "brandkit", str(atlas)).origin is None

def test_plugin_skills_and_missing_skills_ignore_skill_overrides(medium):
    _merge(medium / ".claude/settings.json", skillOverrides={"planning": "off", "ghost": "off", "brandkit": "name-only"})
    inventory = build_inventory(medium)
    assert {"planning", "brandkit"} <= _loads(inventory, None)  # planning is superpowers' skill
    assert "ghost" not in {r.name for r in load_map(inventory, None)}
    assert not any(i.kind is ItemKind.SKILL_RULE for v in project_views(inventory, None) for i in v.items)
    assert not any("ghost" in f.names for f in find_findings(inventory, None))

def test_an_override_value_kitden_cannot_read_says_unknown(medium):
    _merge(medium / ".claude/settings.json", skillOverrides={"brandkit": 3})
    assert _cell(build_inventory(medium), "brandkit", None).state == "unk"

def test_details_list_the_skill_switch_as_a_definition(medium):
    atlas = medium / "work/atlas"
    _merge(atlas / ".claude/settings.local.json", skillOverrides={"release-notes": "off"})
    rule = next(d for d in explain(build_inventory(medium), "release-notes", "skill", str(atlas)) if d["kind"] == "skill_rule")
    assert (rule["scope"], rule["enabled"], rule["loads"], rule["why"]) == ("local", "off", False, "Turns it off in this project.")

def test_a_broken_local_settings_file_keeps_its_switches_from_the_last_good_read(medium):
    atlas, last = medium / "work/atlas", LastGood()
    local = atlas / ".claude/settings.local.json"
    _merge(local, skillOverrides={"release-notes": "off"}, enabledPlugins={PLUGIN: False})
    keep_last_good(build_inventory(medium), last, "2026-10-24T14:02:00+00:00")
    local.write_text("{ not json")
    inventory = keep_last_good(build_inventory(medium), last, "2026-10-24T14:05:00+00:00")
    assert str(local) in {p.path for p in inventory.problems}
    for name, kind in (("release-notes", "skill"), ("superpowers", "plugin")):
        cell = _cell(inventory, name, str(atlas), kind)
        assert (cell.state, cell.stale_at) == ("off", "2026-10-24T14:02:00+00:00")
```

- [ ] **Step 3: Run them to see them fail.** Run `uv run pytest tests/unit/test_skill_rules.py -v`.
  Expected: FAIL (`ItemKind` has no `SKILL_RULE`).
- [ ] **Step 4: Implement** as the Interfaces say.
  - `effective_view` leaves rules out of `kept` before it picks winners, then drops each
    non-plugin Claude Code skill whose deciding rule is `OFF`.
  - `load_map` builds rows from the other items first, then joins each rule to its skill's row,
    and passes the column's view to `_cell`.
- [ ] **Step 5: Run the tests.** Run `uv run pytest tests/unit/test_skill_rules.py
  tests/unit/test_effective.py tests/unit/test_load_map.py tests/unit/test_inventory.py
  tests/unit/test_findings.py tests/unit/test_mcp_server.py -q`. Expected: PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/model.py src/kitden/clients/claude_code.py src/kitden/views/effective.py src/kitden/views/load_map.py src/kitden/views/explain.py tests/unit/test_skill_rules.py
git commit -m "Claude Code: read local settings and skill overrides" -m "A plugin or skill turned off in one project now shows Off there."
```

---

### Task 2: Read what an installed plugin holds (5.1)

**Files:**
- Modify: `src/kitden/clients/base.py`, `src/kitden/clients/claude_code.py`, `src/kitden/clients/codex.py` (`plugin_folders`), `src/kitden/views/catalog.py` (`_inside_signature`, `inside_cached`, `installed_inside`)
- Test: `tests/unit/test_plugin_parts.py` (create)

**Interfaces:**
- Produces `ClientAdapter.plugin_folders(self) -> dict[str, Path]`, by default `{}`. It maps a
  plugin id → its installed folder:
  - Claude Code: the first `installPath` in `installed_plugins.json` that is a folder;
  - Codex: `_plugin_folder(id)` when it holds a `PLUGIN_FILES` manifest, else its newest version
    folder;
  - Cursor: unchanged.
- Produces `inside_cached(folder) -> dict`: `_inside(folder, {})`, kept in `_INSIDE` by folder
  while `_inside_signature(folder)` stays the same. The signature is `(name, st_mtime_ns,
  st_size)` (or None) of the `PLUGIN_FILES`, `.mcp.json`, `mcp.json`, `hooks/hooks.json`, and
  the `skills`, `commands` and `agents` folders.
- Produces `installed_inside(adapters) -> dict[str, dict]`: a plugin id → the parts in its folder,
  taking Claude Code's folder, then Codex's, then Cursor's.
- Builder calls:
  - About ten `stat`s, not a whole tree. An edit inside a skill keeps the cache, since only names
    are kept.
  - Only `/api/library` calls `installed_inside` (Task 3), never the start.

- [ ] **Step 1: Check the docs.** Check Claude Code's `installPath`
  (code.claude.com/docs/en/plugins-reference) and Codex's `plugins/cache/<marketplace>/<plugin>/<version>`
  (learn.chatgpt.com/docs/plugins). Date the comments.
- [ ] **Step 2: Write the failing tests**

```python
# tests/unit/test_plugin_parts.py
def test_installed_plugins_say_what_they_hold(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inside = installed_inside({a.id: a for a in default_adapters(home)})
    assert inside["superpowers@demo-market"]["skills"] == ["brainstorming", "planning"]
    assert [s["name"] for s in inside["pr-review@demo-market"]["mcp_servers"]] == ["pr-index"]
    assert inside["ui-kit@cursor-public"]["skills"] == ["ui-components"]   # Cursor's cache
    assert inside["browser@openai-bundled"]["skills"] == []                 # Codex's cache
    assert "DEMO_SECRET" not in json.dumps(inside)

def test_a_plugin_folder_is_read_again_only_when_it_changes(tmp_path, monkeypatch):
    home = build_demo_home(tmp_path, "medium")
    adapters, reads, real = {a.id: a for a in default_adapters(home)}, [], catalog._inside
    monkeypatch.setattr(catalog, "_inside", lambda folder, entry: reads.append(folder) or real(folder, entry))
    installed_inside(adapters)
    first = len(reads)
    installed_inside(adapters)
    assert len(reads) == first
    skill = home / ".claude/plugins/cache/demo-market/superpowers/7.0.0/skills/new-one/SKILL.md"
    skill.parent.mkdir()
    skill.write_text("---\nname: new-one\ndescription: x\n---\n")
    assert "new-one" in installed_inside(adapters)["superpowers@demo-market"]["skills"]

def test_installed_parts_stay_fast_on_the_large_sample(tmp_path):
    adapters = {a.id: a for a in default_adapters(build_demo_home(tmp_path, "large"))}
    installed_inside(adapters)
    assert min(timeit.timeit(lambda: installed_inside(adapters), number=1) for _ in range(3)) < 0.05
```

- [ ] **Step 3: Run them to see them fail.** Run `uv run pytest tests/unit/test_plugin_parts.py -v`.
  Expected: FAIL (no `installed_inside`).
- [ ] **Step 4: Implement** as the Interfaces say.
- [ ] **Step 5: Run the tests and measure the start.** Run `uv run pytest
  tests/unit/test_plugin_parts.py tests/unit/test_catalog.py -q` (expected: PASS). Then run
  `uv run python scripts/measure-start.py`: first usable, complete and demo must be within
  budget. Put the numbers in the part's report.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/clients/base.py src/kitden/clients/claude_code.py src/kitden/clients/codex.py src/kitden/views/catalog.py tests/unit/test_plugin_parts.py
git commit -m "Plugins: read what an installed plugin holds" -m "Read again only when its folder changes."
```

---

### Task 3: The "Plugins and skills" tab on the server (5.2, 5.3, own rules)

**Files:**
- Modify: `src/kitden/views/library.py` (`KINDS`, `SHOWS`, `library()`; new `_kit_rows`, `source_group`, `_parts`), `src/kitden/views/load_map.py` (new `project_exceptions`, `library_rules`), `src/kitden/web/app.py` (`_library`; `/api/projects` `own_rules`), `tests/unit/test_demo_mode.py` (new `served(home)`)
- Test: `tests/unit/test_compare.py` (create), `tests/unit/test_library.py`, `tests/unit/test_load_map.py`, `tests/unit/test_gateway_access.py`; run `tests/security/`

**Interfaces:**
- Produces `KINDS = ("plugin", "instructions")` and `SHOWS = ("mine", "new", "all", "diff")`.
  The page uses `mine` and `diff`, and the add panel uses `all` (Task 9). `_library` answers any
  other `kind` with the `"plugin"` tab.
- The `"plugin"` tab's rows are:
  - plugins;
  - skills that are not a plugin's: your own, a project's, and map-only rows;
  - hooks;
  - with `show` `new` or `all`, also the catalog's plugin skills, for the add panel.

  Each row gains `group: {id, caption}` and `marketplace: str | None`. A plugin row also gains:
  - `parts: [{kind: "skill"|"command"|"agent"|"hook"|"mcp_server", name, row}]`, in that kind
    order, then by name. A skill part's `row` is that skill's catalog row (its own cells, key,
    lookup and offer); any other part's `row` is None.
  - `size: int | None`, which is None when no folder of the plugin is on this computer.
- Rows under "Only this project" drop the cell `where` tag, because the group says it (Part 4
  ruling 1).
- The answer gains `sources: [{id, caption, row}]`: each marketplace on this computer by name
  (`row` is its load-map row, for Details), then "Your skills", "Your settings", and in a project
  "Only this project". It also gains `own_rules: int`, which is 0 under All projects.
- `source_group(row) -> dict` takes the first rule that holds:
  - `project` "Only this project" when every cell that has the item has origin `"project"`;
  - `market:<name>` for a plugin with a marketplace;
  - `skills` "Your skills" for a skill;
  - `settings` "Your settings" for a hook, or a plugin with no marketplace.
- Produces `project_exceptions(inventory) -> dict[str, list[dict]]`, as old Part 4 Task 3 has it.
  In addition, an entry is `"override"` when `project_rule(view, name)` returns that project's
  rule.
- Produces `library_rules(inventory) -> dict[str, int]`: a project path → how many plugin and skill
  rows have an `"off"` or `"override"` entry there. `/api/library` sends `own_rules`, and
  `/api/projects` items add it to Part 4's `own_rules(settings, chain)`
  (`local_gateway/views.py`).
- Produces test helper `served(home)`: `create_app(demo_build(home), token="tok", port=47800,
  home=home, demo=True)` on a home the test changed first. `demo_page` uses it.
- Builder calls:
  - A marketplace with nothing added keeps its caption, so its Details stay reachable.
  - `_server_add`, `_server_why` and their tests stay only if Part 4's code still calls them;
    grep for them.
  - `_library(home, kind)` in `test_library.py` asks the tab that holds `kind` and keeps that
    kind's rows.

- [ ] **Step 1: Write the failing tests.** Take old Part 4 Task 3's
  `test_project_exceptions_name_the_projects_that_change_a_row` (into `test_load_map.py`) and
  `test_project_exceptions_stay_fast_on_the_large_sample` (into `test_compare.py`). Then add:

```python
# tests/unit/test_compare.py (new); fixture `medium` as in Task 1; `_merge` from tests/unit/test_skill_rules.py
def _library(home, project=None, **options):
    inventory, adapters = build_inventory(home), {a.id: a for a in default_adapters(home)}
    return library(inventory, adapters, project, gateway_registered=False, kind="plugin", **options)

def test_the_plugins_tab_groups_rows_by_source(medium):
    answer = _library(medium)
    groups = {r["name"]: r["group"]["caption"] for r in answer["rows"]}
    assert (groups["superpowers"], groups["brandkit"], groups["PreToolUse: Bash"]) == ("demo-market", "Your skills", "Your settings")
    assert "planning" not in groups and {r["kind"] for r in answer["rows"]} == {"plugin", "skill", "hook"}
    assert [s["caption"] for s in answer["sources"]][-2:] == ["Your skills", "Your settings"]
    assert next(s for s in answer["sources"] if s["caption"] == "demo-market")["row"]["kind"] == "marketplace"

def test_a_plugin_row_lists_what_it_holds(medium):
    rows = {r["name"]: r for r in _library(medium)["rows"]}
    parts = rows["superpowers"]["parts"]
    assert [(p["kind"], p["name"]) for p in parts] == [("skill", "brainstorming"), ("skill", "planning")]
    assert rows["superpowers"]["size"] == 2 and parts[0]["row"]["cells"]["claude_code"]["state"] == "on"
    assert [(p["kind"], p["name"], p["row"]) for p in rows["pr-review"]["parts"]] == [("mcp_server", "pr-index", None)]

def test_only_this_project_is_a_group_not_a_tag(medium):
    answer = _library(medium, str(medium / "work/atlas"))
    api = next(r for r in answer["rows"] if r["name"] == "api-style")
    assert api["group"] == {"id": "project", "caption": "Only this project"}
    assert api["cells"]["codex"]["where"] is None and answer["sources"][-1]["caption"] == "Only this project"

def test_old_tabs_answer_with_plugins_and_skills(medium):
    with served(medium) as page:
        rows = page.get("/api/library?kind=plugin").json()["rows"]
        for old in ("mcp_server", "skill", "hook", "marketplace"):
            assert page.get(f"/api/library?kind={old}").json()["rows"] == rows

def test_project_rules_count_what_differs_from_the_shared_setup(medium):
    atlas, website = medium / "work/atlas", str(medium / "work/website")
    _merge(atlas / ".claude/settings.local.json", skillOverrides={"release-notes": "off"})
    inventory = build_inventory(medium)
    off = {"project": str(atlas), "client": "claude_code", "how": "off"}
    assert off in project_exceptions(inventory)[_hash(ItemKind.SKILL, "release-notes")]
    assert library_rules(inventory) == {str(atlas): 1, website: 1}  # website turns superpowers off
    assert (_library(medium, str(atlas))["own_rules"], _library(medium)["own_rules"]) == (1, 0)
```

```python
# tests/unit/test_library.py (fixture `home`; OFFICIAL and `_row` are there)
def test_same_name_plugins_from_two_marketplaces_stay_apart(home):
    answer = library(build_inventory(home), {a.id: a for a in default_adapters(home)}, None, gateway_registered=False, kind="plugin")
    official, public = _row(answer, "superpowers", OFFICIAL), _row(answer, "superpowers", "cursor-public")
    assert official["key"] != public["key"] and official["same_name"] and public["same_name"]
    assert (official["group"]["id"], public["group"]["id"]) == (f"market:{OFFICIAL}", "market:cursor-public")
```

- [ ] **Step 2: Run them to see them fail.** Run `uv run pytest tests/unit/test_compare.py
  tests/unit/test_library.py tests/unit/test_load_map.py -q`. Expected: FAIL (no `group`; no
  `project_exceptions`).
- [ ] **Step 3: Implement** as the Interfaces say. Expected row dicts in `test_library.py` (search
  `"flags":`) gain `group` and `marketplace`, and plugin rows also gain `parts` and `size`. Part 4's
  `test_the_page_gets_own_rules_per_project_and_the_mcp_server_does_not`
  (`tests/unit/test_gateway_access.py`) now expects website = 1, since superpowers is off there.
- [ ] **Step 4: Run the tests.** Run `uv run pytest tests/unit/test_compare.py tests/unit/test_library.py
  tests/unit/test_load_map.py tests/unit/test_api_views.py tests/unit/test_demo_mode.py
  tests/security -q`. Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/views/library.py src/kitden/views/load_map.py src/kitden/web/app.py tests/unit/test_demo_mode.py tests/unit/test_compare.py tests/unit/test_library.py tests/unit/test_load_map.py tests/unit/test_gateway_access.py
git commit -m "Library: one tab for plugins and skills, grouped by source" -m "Each plugin lists what it holds; projects count their own rules."
```

---

### Task 4: Two tabs, old addresses, the List and Differences (5.2, 5.4)

**Files:**
- Modify: `src/kitden/web/static/js/store.js` (`SHOWS`, `parseHash`, `place`, `libraryChoice`; new `libraryTab`), `src/kitden/web/static/js/library.js` (`KINDS` → `TABS`, `SHOW`, `asking`, `toolbar`, `buildTable`, `emptyState`, `rowFor`; new `libraryRows`; the head with Map | List and `scopeBar`), `src/kitden/views/library.py` (new `differs`, `CELL_CLASS`; `_chosen`), `src/kitden/web/static/js/details.js` (`contextLinks`; the held tool list leaves Library Details), `src/kitden/web/static/js/tools.js` and `src/kitden/web/static/js/panel.js` (its `tools.js` re-export line), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/library.test.mjs`, `tests/frontend/store.test.mjs`, `tests/frontend/context.test.mjs`, `tests/frontend/panel.test.mjs`, `tests/frontend/tools.test.mjs` (if present), `tests/unit/test_library.py`, `tests/unit/test_compare.py`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 3's answer; `gridKey`, `scopeBar`, `viewMode`, `state.mode`.
- Produces in `store.js`:
  - `libraryTab(kind) -> "plugin" | "instructions"`;
  - `place()` and `parseHash`: the Library with an `mcp_server` kind or selection becomes the
    Gateway, keeping `sel`; other old kinds open `"plugin"`; `show=new|all` reads as `mine`;
  - the default Library kind is `"plugin"`, so a bare `#library` stays in the Library;
  - `libraryChoice` uses `libraryTab`.
- Produces in `library.js`:
  - `TABS = [["plugin", "Plugins and skills"], ["instructions", "Instructions"]]` and
    `SHOW = [["mine", "Installed"], ["diff", "Differences"]]`;
  - `libraryRows(answer, open: Set<string>) -> [{id, parent, depth, kind, expanded, group, row,
    source}]` (pure), in `gridKey`'s row shape: each source (`kind: "group"`, `id`
    `group:<id>`), its rows (`row:<key>`), and an open plugin's parts
    (`part:<key>:<kind>:<name>`).
- Produces in `library.py`: `differs(row, columns) -> bool` with `CELL_CLASS`, as old Part 4
  Task 1 has it (has / off / lacks; `unk`, `review` and a kept cell always differ; only shown
  columns count). In addition, a plugin row differs when any skill part's `row` differs. `_chosen`
  keeps those rows for `show == "diff"`.
- The List (L3), a `role="treegrid"` table driven by `gridKey`:
  - Group rows hold the caption. A marketplace caption opens its Details (`source.row`: today's
    marketplace Details and commands). An empty one says "Nothing added from it yet.".
  - A plugin row has a chevron and "Plugin · N items" ("Plugin" when `size` is null).
  - A skill part has its own row's cells and Details. Any other part shows its plugin's states,
    with no add, and opens the plugin's Details.
  - The toolbar holds Installed | Differences and "Needs attention", which stays because Overview
    links use `attention=1`. The category filter goes: it belonged to New and All, which the add
    panel replaces. `asking()` sends `show` as `mine` or `diff`, and `q` only in List.
  - Column heads keep `land(tile, …)` as it is; Part 6 decides the tile animation.
  - Arrivals `sel=marketplace:<name>` and `sel=hook:<name>` open that caption's or row's Details.
- The head has the title, the Map | List switch (`go("library", { mode })`, `data-focus`
  `view:map` / `view:list`), the tabs, then `scopeBar(folder, answer.own_rules)`. Map is Task 6.
- MCP server rows leave the Library. `contextLinks` gives no "Compare across clients" for an
  `mcp_server`, because the Gateway List shows who uses it, and "Manage tools" goes. Library
  Details lose the held tool list: delete from `tools.js` what nothing imports any more
  (`toolsSection`, `toolRows`, `reloadTools`, `writingToolsOn`, `callsText`; `projectLabel` and
  `tools` stay), together with `panel.js`'s re-export of it. Nothing is left importing a deleted
  name.
- Builder calls:
  - An empty cell keeps today's dash with its reason in the hover text.
  - The lede stays today's.
  - The Instructions tab stays today's table until Part 6.
  - An empty Differences list says "No differences between your clients" and offers "Show
    installed".

- [ ] **Step 1: Write the failing tests.** Take old Part 4 Task 1's
  `test_rows_differ_by_state_class_unknown_and_needs_review` (into `test_library.py`), and
  `test_differences_keep_rows_whose_shown_clients_differ` and `test_the_library_api_takes_show_diff`
  (into `test_compare.py`, with `kind="plugin"` and skills in place of the servers):
  - `kd-only-claude` is only in `~/.claude/skills`, so it differs;
  - `kd-everywhere` has the same files in `~/.claude/skills` and `~/.agents/skills`, so it does
    not.

  Then add:

```python
# tests/unit/test_library.py
def test_a_plugin_differs_when_one_of_its_skills_does():
    same, both = {"claude_code": _cell("on"), "codex": _cell("on")}, ["claude_code", "codex"]
    part = {"kind": "skill", "name": "x", "row": {"cells": {"claude_code": _cell("on"), "codex": _cell("none")}}}
    assert differs({"cells": same, "parts": [part]}, both)
    assert not differs({"cells": same, "parts": [{"kind": "command", "name": "/ship", "row": None}]}, both)
```

```js
// tests/frontend/store.test.mjs
test('old Library addresses land in the new place', () => {
  const server = parseHash('#library?kind=mcp_server&sel=mcp_server%3Agithub');
  assert.deepEqual([server.view, server.selected], ['gateway', { kind: 'mcp_server', name: 'github' }]);
  assert.equal(parseHash('#library?kind=hook&sel=hook%3APreToolUse%3A%20Bash').kind, 'plugin');
  assert.equal(parseHash('#library?kind=marketplace').kind, 'plugin');
  assert.equal(parseHash('#library?kind=skill&show=new').show, 'mine');
  assert.equal(hashFor(parseHash('#library?kind=plugin&show=diff')), '#library?kind=plugin&show=diff');
  goTo('library', { kind: 'mcp_server', name: 'github' });
  assert.equal(state.view, 'gateway');
});
```

```js
// tests/frontend/library.test.mjs
test('the List groups rows by source and folds a plugin over its parts', () => {
  const answer = { sources: [{ id: 'market:demo', caption: 'demo-market', row: null }, { id: 'skills', caption: 'Your skills', row: null }],
    rows: [{ key: 'p', kind: 'plugin', name: 'superpowers', group: { id: 'market:demo' }, size: 1, parts: [{ kind: 'skill', name: 'planning', row: null }], cells: {} },
      { key: 's', kind: 'skill', name: 'brandkit', group: { id: 'skills' }, cells: {} }] };
  assert.deepEqual(libraryRows(answer, new Set()).map((r) => [r.kind, r.id, r.depth]),
    [['group', 'group:market:demo', 0], ['plugin', 'row:p', 1], ['group', 'group:skills', 0], ['skill', 'row:s', 1]]);
  const open = libraryRows(answer, new Set(['row:p']));
  assert.deepEqual(open.map((r) => r.id).slice(1, 3), ['row:p', 'part:p:skill:planning']);
  assert.deepEqual(gridKey(open, 1, 'ArrowLeft'), { at: 1, toggle: 'row:p' });
});
```

```python
# tests/unit/test_page_words.py: replaces the six-tab and New / All pins
def test_library_has_two_tabs_and_shows_installed_or_differences():
    text = script("library.js")
    assert '[["plugin", "Plugins and skills"], ["instructions", "Instructions"]]' in text
    assert '[["mine", "Installed"], ["diff", "Differences"]]' in text and "scopeBar(" in text
    assert '"Nothing added from it yet."' in text and '"No differences between your clients"' in text
    assert '"MCP servers"' not in text and '"Marketplaces"' not in text
```

  In the same commit, update the pins that named the old tabs:
  - `test_library_adds_plugins_and_marketplaces_in_one_review` ("Add a marketplace…" stays in the
    List toolbar until Task 9);
  - `test_library_tabs_share_one_table_and_the_add_flow`;
  - `test_library_replaces_load_map_and_discover`: only its Installed / New / All lines. Part 4
    changes its `map.js` half;
  - `test_library_says_why_when_there_is_nothing_to_do` (the "in New" line goes);
  - `test_library_rows_say_what_each_client_has_or_can_add_without_details` (the category words
    go), `test_every_control_a_render_replaces_names_itself_for_focus`,
    `test_tabs_and_filters_read_first_then_the_list_settles`, and
    `test_add_a_marketplace_sits_where_the_filters_sit_on_other_tabs`;
  - the tool list's pins, which go with it: `test_a_held_server_lists_its_tools_with_a_switch_each`,
    `test_a_tool_switch_flips_only_after_the_change_is_verified`,
    `test_tool_list_reads_again_and_keeps_focus_after_a_refresh_or_an_undo`,
    `test_the_tool_list_has_a_strict_switch`, `test_all_projects_says_unknown_folders_follow_it`,
    `test_the_tool_list_says_reads_and_writes_and_has_a_batch_switch`, and the
    `"Tools · ${where…"` line of `test_changes_and_the_library_say_saved_settings_and_scope`;
  - the `"Manage tools"` pin in `test_details_say_what_the_lead_changes_and_link_to_the_other_pages`.
    The README's "Manage tools" sentence and its pins in `test_docs_words.py` change with the
    README in Task 11.

  Also update:
  - the node tests that read `KINDS` or `moreLine`, and the tool tests in `panel.test.mjs` (and in
    `tools.test.mjs`, if it is there);
  - `context.test.mjs`, whose old `#library?kind=mcp_server…` addresses now open the Gateway.

  Add a store test that a bare `#library` gives `{view: 'library', kind: 'plugin'}`.
- [ ] **Step 2: Run them to see them fail.** Run the node tests and `uv run pytest
  tests/unit/test_library.py tests/unit/test_compare.py tests/unit/test_page_words.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** as the Interfaces say. Rows still settle and morph by `data-key`, and
  group and part rows use their ids. In `docs/design.md`'s Library table:
  - Tabs replaces "Tabs split…": two tabs, MCP servers on the Gateway, old addresses land there.
  - Groups: the four sources; a caption opens the marketplace's Details.
  - Plugin rows: the chevron, "Plugin · 4 items" and its parts.
  - Show choice: Installed | Differences, and the Differences rule.
  - The "Group line" row goes.
  - Tag: "Only this project" is now a group.
- [ ] **Step 4: Run all four checks.** Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/store.js src/kitden/web/static/js/library.js src/kitden/views/library.py src/kitden/web/static/js/details.js src/kitden/web/static/js/tools.js src/kitden/web/static/js/panel.js src/kitden/web/static/style.css docs/design.md tests/frontend/library.test.mjs tests/frontend/store.test.mjs tests/frontend/context.test.mjs tests/frontend/panel.test.mjs tests/unit/test_library.py tests/unit/test_compare.py tests/unit/test_page_words.py  # plus tests/frontend/tools.test.mjs if it exists
git commit -m "Library: two tabs and a List by source, with Differences" -m "Old MCP server links open the Gateway."
```

---

### Task 5: Add missing in four groups, in the Library and on the Gateway (5.4)

**Files:**
- Modify: `src/kitden/changes/align.py` (`align_steps`; new `_another_way`, `ALIGN_KINDS`), `src/kitden/web/app.py` (the `PROJECT_ALIGN` branch), `src/kitden/views/after.py` (`_align_words`), `src/kitden/web/static/js/review.js` (`changeWords`, `alignGroups`, `chosenKeys`, `alignSection`, `lockReview`; new `alignLines`), `src/kitden/web/static/js/library.js` and `src/kitden/web/static/js/gateway.js` (the List toolbars), `docs/design.md`
- Test: `tests/unit/test_align.py`, `tests/unit/test_compare.py`, `tests/frontend/panel.test.mjs`, `tests/frontend/review.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces old Part 4 Task 6's listing and `_another_way`, as written there, and:
  - `align_steps(inventory, adapters, project: str | None, found, chosen, kinds=KINDS)`;
  - with `project` None, the views are for all projects, every `place` is `"all"`, and the empty
    case says "Nothing is missing.";
  - `ALIGN_KINDS = {"kit": (PLUGIN, SKILL), "servers": (MCP_SERVER,)}`;
  - the body is `{action: "project.align", targets: [], params: {project: <id> | null, what:
    "kit" | "servers", chosen}}`, and a missing `what` means every kind.
- Produces old Part 4 Task 7's `alignLines` and review, with these titles:
  - in a project: "Adds N items to <folder>", or "Add what <folder> is missing" with none
    checked;
  - with All projects: "Adds N items for all projects", or "Add what each client is missing";
  - done lines: "Added N items to <folder>" and "Added N items for all projects".
- Buttons, both sending `project: state.project || null`:
  - "Add missing plugins and skills…" in the Library List toolbar (`data-focus="add:missing"`,
    `what: "kit"`);
  - "Add missing servers…" in the Gateway List toolbar (`data-focus="add:missing-servers"`,
    `what: "servers"`).
- Builder call: Compare in "Needs your decision" calls `goTo` with the row's kind, so a server
  opens on the Gateway (Task 4's redirect).

- [ ] **Step 1: Write the failing tests.** Take, as written there:
  - old Part 4 Task 6's changed `test_align.py` assertions,
    `test_another_way_names_how_a_client_already_gets_it` and
    `test_a_decision_alone_still_opens_the_review`;
  - its `test_compare.py` tests: `test_will_add_says_why_and_where`,
    `test_already_lists_turned_off_and_another_clients_copy`,
    `test_a_name_with_two_sources_is_a_decision_and_never_checked`,
    `test_cannot_names_the_target_client`,
    `test_an_add_into_a_file_kitden_could_not_read_cannot_be_added`,
    `test_a_broken_project_file_holds_only_the_adds_into_it`;
  - old Task 7's node tests and its page-words pin, with this task's button words.

  `_align_on(page, chosen, folder, what=None)` sends `what`. Add old Task 1's `_server(home, name,
  clients, url)` to `test_compare.py`: it writes an http entry with that address into each named
  client (`add_claude`, `add_codex`, `add_cursor` from `test_local_gateway_move.py`). Then add:

```python
# tests/unit/test_compare.py
def test_add_missing_works_for_all_projects_and_by_page(medium):
    _server(medium, "kd-extra", ["claude_code"], "https://extra.invalid/mcp")
    skill = medium / ".claude/skills/kd-folder/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: kd-folder\ndescription: A test skill.\n---\n")
    with served(medium) as page:
        def listing(what):
            body = {"action": "project.align", "targets": [], "params": {"project": None, "what": what, "chosen": None}}
            return page.post("/api/changes/preview", json=body, headers=POST).json()["align"]
        kit, servers = listing("kit"), listing("servers")
    assert {e["kind"] for e in kit["will_add"]} <= {"plugin", "skill"} and all(e["place"] == "all" for e in kit["will_add"])
    assert {e["kind"] for e in servers["will_add"]} == {"mcp_server"}
```

```js
// tests/frontend/review.test.mjs
test('Add missing for all projects says so in its title', () => {
  const align = { will_add: [{ key: 'skill:x:codex', kind: 'skill', name: 'x', to: 'codex', place: 'all', why: 'Claude Code has it; Codex does not.', note: null, chosen: true }], already: [], decide: [], cannot: [] };
  assert.deepEqual(changeWords({ action: 'project.align', steps: [{ client: 'codex', name: 'x' }], align }, { params: { project: null } }),
    { title: 'Adds 1 item for all projects', done: 'Added 1 item for all projects' });
});
```

- [ ] **Step 2: Run them to see them fail.** Expected: FAIL (`KeyError: 'will_add'`).
- [ ] **Step 3: Implement** as above. The "Add missing" row in `docs/design.md` says:
  - where the two buttons are, in a project and in All projects;
  - the four groups;
  - the title "Adds 3 items to website";
  - an add that would make a duplicate, or has a name to decide, starts unchecked.
- [ ] **Step 4: Run all four checks.** Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/changes/align.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/review.js src/kitden/web/static/js/library.js src/kitden/web/static/js/gateway.js docs/design.md tests/unit/test_align.py tests/unit/test_compare.py tests/frontend/panel.test.mjs tests/frontend/review.test.mjs tests/unit/test_page_words.py
git commit -m "Add missing: four groups, in the Library and on the Gateway" -m "Each line says why; it also works for all projects."
```

---

### Task 6: The Library map (5.3, S.4–S.6)

**Files:**
- Create: `src/kitden/web/static/js/librarytree.js`, `tests/frontend/librarytree.test.mjs`
- Modify: `src/kitden/web/static/js/library.js` (Map or List, selection, find, unfold), `src/kitden/web/static/js/app.js` (`MAP_PAGES`), `src/kitden/web/static/style.css` (plugin and item blocks), `docs/design.md`
- Test: `tests/frontend/librarytree.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces `libraryModel(answer, columns: string[], { picked = "", preview = null } = {}) -> model`
  (pure). `picked` is the picked project's id, not `answer.project`.
  - Columns: `[{id: "clients", caption: "Clients"}, {id: "items", caption: "Plugins and skills",
    add: true}, {id: "inside", caption: "Inside"}]`.
  - Client blocks `client:<id>` (name only), and `group:<source id>` captions for sources that
    have rows. A marketplace caption is a button (`drawMap`) that opens its Details. The items
    column's "+ Add" calls `drawMap`'s `onAdd("items")`, which opens Task 9's panel.
  - Item blocks `row:<key>`, with:
    - kind `plugin`, `skill` or `hook`;
    - meta "N items", "Plugin", "Skill" or "Hook";
    - `count` the plugin's `size`, and `parent` its caption;
    - `tag` "This project" when any cell has origin `"override"` and a project is picked;
    - `state` from `blockState`.
  - Part blocks `part:<key>:<kind>:<name>` in `inside`, with parent `row:<key>` and meta "Skill",
    "Command", "Agent", "Hook" or "MCP server".
  - Links: `client → row` for each found client whose `linkKind(cell)` is not null; `row → part`
    of kind `on` while the plugin's block is `on`.
  - With `preview: {row, clients}`, a `preview` block under its marketplace caption and a
    `preview` link from each client.
- Produces `linkKind(cell) -> "on" | "faint" | null`. It is null unless the state is `on` or `gw`;
  `"faint"` when `cell.route` matches `/^through .+'s folder$/`; else `"on"`.
- Produces `blockState(row, columns) -> "on" | "off" | "unk"`: `on` with any link; `unk` with a
  cell that is `unk`, `review` or kept; else `off`.
- The page:
  - `viewMode(state, plugins + skills)` picks Map or List.
  - The map draws `drawMap(box, model, layoutTree(model, { open, width, narrow: isNarrow(width,
    detailsDocked) }), { onSelect, onOpen, … })`. Unfolding uses `toggleOpen` and
    `unfoldDelays`.
  - Selecting a block lights `litPath` (which follows faint links) and opens its Details docked:
    a part opens its skill row, or else its plugin. A selected client lights `litFrom` (what it
    loads), with `sel=client:<id>`; a caption selects `sel=group:<id>`.
  - A group's "N more" block opens List at that group (`sel=group:<id>`).
  - `MAP_PAGES` gains `"library"`. On the map, search runs `findIn(model, q)` with `findChip`
    from `map.js`.
- Builder calls:
  - Blocks under "Only this project" carry no tag, since the caption says it.
  - Client blocks show the name only.

- [ ] **Step 1: Write the failing tests**

```js
// tests/frontend/librarytree.test.mjs (stub the DOM as library.test.mjs does; layoutTree, litPath,
// findIn from map.js, viewMode from store.js, cutName from dom.js)
const cell = (state, more = {}) => ({ state, origin: null, route: null, stale_at: null, ...more });
const answer = { sources: [{ id: 'market:demo', caption: 'demo-market' }, { id: 'skills', caption: 'Your skills' }], rows: [
  { key: 'p', kind: 'plugin', name: 'superpowers', group: { id: 'market:demo' }, size: 2,
    parts: [{ kind: 'skill', name: 'planning', row: null }, { kind: 'command', name: 'ship', row: null }],
    cells: { claude_code: cell('on'), codex: cell('none'), cursor: cell('on', { route: "through Claude Code's folder" }) } },
  { key: 's', kind: 'skill', name: 'brandkit', group: { id: 'skills' },
    cells: { claude_code: cell('off', { origin: 'override' }), codex: cell('unk'), cursor: cell('via') } }] };
const ALL = ['claude_code', 'codex', 'cursor'];

test('the Library tree: captions, blocks, parts, and links that are the state', () => {
  const model = libraryModel(answer, ALL, { picked: 'p1' });
  const block = (id) => model.blocks.find((b) => b.id === id);
  assert.deepEqual(model.columns.map((c) => c.caption), ['Clients', 'Plugins and skills', 'Inside']);
  assert.deepEqual([block('row:p').meta, block('row:p').count, block('row:p').parent], ['2 items', 2, 'group:market:demo']);
  assert.deepEqual([block('part:p:command:ship').meta, block('part:p:command:ship').column], ['Command', 'inside']);
  assert.deepEqual([block('row:s').state, block('row:s').tag], ['unk', 'This project']);
  const links = model.links.map((l) => `${l.from}>${l.to}:${l.kind}`);
  for (const link of ['client:claude_code>row:p:on', 'client:cursor>row:p:faint', 'row:p>part:p:skill:planning:on']) assert.ok(links.includes(link), link);
  assert.ok(!links.some((l) => l.includes('>row:s')));  // off, unknown and "Via Claude Code" draw no link
});
test('a selected part lights its plugin and every client that loads it; find opens its plugin', () => {
  const model = libraryModel(answer, ALL);
  for (const id of ['client:claude_code', 'client:cursor', 'row:p', 'part:p:skill:planning']) assert.ok(litPath(model, 'part:p:skill:planning').has(id), id);
  const found = findIn(model, 'plan');
  assert.ok(found.matches.has('part:p:skill:planning') && found.open.has('row:p'));
});
test('a preview block sits under its marketplace with preview links', () => {
  const row = { key: 'n', kind: 'plugin', name: 'test-helper', group: { id: 'market:demo' }, size: null, parts: [], cells: {} };
  const model = libraryModel(answer, ALL, { preview: { row, clients: ['claude_code', 'codex'] } });
  assert.equal(model.blocks.find((b) => b.id === 'row:n').state, 'preview');
  assert.equal(model.links.filter((l) => l.to === 'row:n' && l.kind === 'preview').length, 2);
});
test('the large sample opens in List and lays out in time', () => {
  const rows = Array.from({ length: 160 }, (_, i) => ({ key: `k${i}`, kind: i % 2 ? 'skill' : 'plugin', group: { id: 'skills' }, size: 3, parts: [],
    name: `item-${i}-with-a-name-long-enough-that-the-page-cuts-it-short`, cells: { claude_code: cell('on') } }));
  const model = libraryModel({ sources: [{ id: 'skills', caption: 'Your skills' }], rows }, ['claude_code']);
  assert.equal(viewMode({ mode: '' }, rows.length), 'list');
  const start = performance.now();
  layoutTree(model, { open: new Set(), width: 1248, narrow: false });
  assert.ok(performance.now() - start < 16);
  assert.ok(cutName(rows[0].name).endsWith('…'));
});
```

```python
# tests/unit/test_page_words.py
def test_the_library_map_says_its_columns_and_kinds():
    text = script("librarytree.js")
    for words in ('"Clients"', '"Plugins and skills"', '"Inside"', '"Command"', '"Agent"', '"MCP server"', " items`"):
        assert words in text, words
    assert 'MAP_PAGES = ["gateway", "library"]' in script("app.js")
```

  Part 4's pin `'MAP_PAGES = ["gateway"]' in app` changes to this one in the same commit.
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL (no module).
- [ ] **Step 3: Implement** as above. Add a "Library map" row to `docs/design.md`:
  - the three columns;
  - plugins fold with "N items", never "N of M on", because a part follows its plugin;
  - the link is the state, and a faint link means through Claude Code's folder;
  - "This project" on a block when a client's state there comes from the project;
  - List first past 15 plugins and skills.
- [ ] **Step 4: Run all four checks, then look.** In `uv run kitden demo --size medium` at 1280
  px, a plugin unfolds, a selected part lights Claude Code and Cursor, and Escape clears. At
  900 px, parts unfold down. Nothing moves while idle.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/librarytree.js src/kitden/web/static/js/library.js src/kitden/web/static/js/app.js src/kitden/web/static/style.css docs/design.md tests/frontend/librarytree.test.mjs tests/unit/test_page_words.py
git commit -m "Library: a map from clients to plugins and skills to their parts"
```

---

### Task 7: Skill and plugin switches (5.5, server)

**Files:**
- Modify: `src/kitden/changes/actions.py` (`SKILL_RULE`, `PLUGIN_RULE`, `skill_rule_steps`, `plugin_rule_steps`, `switch_offers`), `src/kitden/clients/claude_code.py` and `src/kitden/clients/codex.py` (step makers), `src/kitden/changes/toml_edit.py` (the `[path=…]` selector), `src/kitden/clients/codex.py` (reader, if the docs need it), `src/kitden/web/app.py` (preview branches), `src/kitden/views/explain.py` (`with_page_fields` adds `switch`), `src/kitden/views/after.py` (`project_keeps`, `KEEPS_KINDS`, `AFTER_WORDS`), `src/kitden/views/review.py` (`step_project`), `src/kitden/web/static/js/review.js` (titles, done words)
- Test: `tests/unit/test_skill_rules.py`, `tests/unit/test_file_edits.py`, `tests/unit/test_after.py`, `tests/unit/test_compare.py`, `tests/frontend/review.test.mjs`

**Interfaces:**
- Produces `SKILL_RULE = "skill.rule"`, with body `{targets: [{item}], params: {project: <id> |
  null, state: "off" | null}}`. `skill_rule_steps(adapters, inventory, item, project, state)`
  builds `format_preserving_edit` steps:

  | Case | Steps |
  | --- | --- |
  | Claude Code, all projects | `~/.claude/settings.json` `("skillOverrides", name)` = `"off"`, or removed for null ("Turn on for all projects…"); `USER`, `NEW_SESSION` |
  | Claude Code, project P, `"off"` | `<P>/.claude/settings.local.json` key = `"off"`; `LOCAL` |
  | Claude Code, project P, null ("Use the shared rule…") | the key removed from `settings.local.json`, and from `<P>/.claude/settings.json` when it is there (`PROJECT`, `shared_file=True`) |
  | Codex, all projects | `config.toml` key `("skills", "config", f"[path={item.source.path}]")` = `{"path": …, "enabled": False}`, or removed for null |

- Refusals, in these words:
  - a Claude Code plugin skill: "Claude Code has no switch for one skill inside a plugin. Turn
    the plugin off instead.";
  - Claude Code in a project while a `USER` rule exists: "Turning one skill off in one project
    waits: your user settings have skill overrides, and Claude Code's docs do not say how a
    project's overrides join them.";
  - Codex in a project: "Codex has no switch for one skill in one project.";
  - Cursor: "Cursor has no switch to turn off one skill.".
- Produces `PLUGIN_RULE = "plugin.rule"`, with body `{targets: [{item}], params: {project: <id>,
  state: "off" | null}}`. `plugin_rule_steps(adapters, item, project, state)` sets
  `<P>/.claude/settings.local.json` `("enabledPlugins", id)` to False, or removes it.
  - It uses `LOCAL` and `RELOAD`.
  - With no project it refuses "Choose a project.".
  - For any client but Claude Code it refuses "Only Claude Code has a switch for one project.".
- `toml_edit`: a key part `[path=<value>]` picks the table, in an array of tables, whose `path`
  has the same real path.
  - `get_value` returns it as a dict, or `ABSENT`.
  - `set_value` replaces it, or appends a new `[[…]]` table.
  - `delete_value` removes it, then an empty array, then an empty super-table.
  - Everything else stays byte for byte.
- `step_project`: a `LOCAL` step whose key does not start with `"projects"` belongs to the
  project that holds its file.
- Produces `switch_offers(inventory, item) -> dict | None`, sent as `switch` on skill and plugin
  definitions: `{all, project, plugin, why}`.
  - Claude Code own skill: `all` for a user skill; `project` while no `USER` rule exists.
  - Claude Code plugin skill: `plugin` = its id (`plugin_of`), and `why` "Claude Code has no
    switch for one skill inside a plugin, so the whole plugin goes off there.".
  - Claude Code plugin: `project`.
  - Codex user skill: `all`, and `why` "Codex has no switch for one project.".
  - Cursor: `why` "Cursor has no switch to turn off one skill.".
- Produces `project_keeps(change, inventory)` as old Part 4 Task 5 has it, plus `skill.rule` →
  skill and `plugin.rule` → plugin. For a Claude Code all-projects `skill.rule`, each known
  project whose `.claude/settings.json` or `.claude/settings.local.json` has `skillOverrides`
  without that key adds "<folder> has its own skill settings; it may keep this skill on.". The
  preview appends `{"note": …}` to `after`.
- After chips: `{client, state: "off"|"on", word: "Off"|"On"}` per client.
- Titles, each followed by `target`'s scope words:
  - "Turn off <name> in <clients>";
  - "Use the shared rule for <name> in <clients>", which is null in a project;
  - "Turn on <name> in <clients>", which is null for all projects;
  - for `plugin.rule`: "Turn off <short> in <clients>" and "Use the shared rule for <short> in
    <clients>".

  Done words: "Turned off", "Turned on", "Back to the shared rule:".
- Builder calls:
  - These steps write the file and run no client command, because no command exists for
    `skillOverrides`.
  - `plugin.rule` reaches Claude Code only: Cursor's import of project settings is not checked.
  - "Use the shared rule…" for a plugin exists only for a `local` entry. A project
    `settings.json` entry keeps today's actions.

- [ ] **Step 1: Check the docs.**
  - code.claude.com/docs/en/skills: `skillOverrides` in `settings.local.json`.
  - learn.chatgpt.com/docs/build-skills and /docs/config-file/config-reference: whether
    `[[skills.config]]` `path` names `SKILL.md` or the folder. The reader in `codex.scan` then
    matches both.
  - cursor.com/docs/skills: still no switch.

  Date each claim.
- [ ] **Step 2: Write the failing tests**

```python
# tests/unit/test_skill_rules.py
def _item(page, client, name, kind="skill", scope="user"):
    return next(i["id"] for i in page.get(f"/api/items?client={client}&kind={kind}&scope={scope}").json() if i["name"] == name)

def _project(page, path):
    return next(p["id"] for p in page.get("/api/projects").json() if p["path"] == str(path))

def _post(page, action, item, **params):
    return page.post("/api/changes/preview", json={"action": action, "targets": [{"item": item}], "params": params}, headers=POST)

def _run(page, change, verb):
    return page.post(f"/api/changes/{change['id']}/{verb}", headers=POST).json()["state"]

def test_a_skill_turned_off_for_all_projects_is_written_and_undone(medium):
    settings = medium / ".claude/settings.json"
    before = settings.read_bytes()
    with served(medium) as page:
        change = _post(page, "skill.rule", _item(page, "claude_code", "brandkit"), project=None, state="off").json()
        assert change["target"]["scope"] == "all" and _run(page, change, "apply") == "verified"
        assert json.loads(settings.read_text())["skillOverrides"] == {"brandkit": "off"}
        assert _run(page, change, "undo") == "undone"
    assert settings.read_bytes() == before

def test_a_skill_turned_off_in_one_project_and_back_to_the_shared_rule(medium):
    atlas, local = medium / "work/atlas", medium / "work/atlas/.claude/settings.local.json"
    with served(medium) as page:
        item, here = _item(page, "claude_code", "release-notes"), _project(page, atlas)
        off = _post(page, "skill.rule", item, project=here, state="off").json()
        # atlas holds the known project atlas/web, so "Other projects are unchanged." is not said.
        assert off["target"] == {"scope": "project", "project": str(atlas), "others_unchanged": False}
        _run(page, off, "apply")
        assert json.loads(local.read_text()) == {"skillOverrides": {"release-notes": "off"}}
        assert _run(page, _post(page, "skill.rule", item, project=here, state=None).json(), "apply") == "verified"
        assert json.loads(local.read_text()) == {"skillOverrides": {}}

def test_one_project_switch_waits_while_the_user_file_has_skill_overrides(medium):
    _merge(medium / ".claude/settings.json", skillOverrides={"brandkit": "off"})
    with served(medium) as page:
        answer = _post(page, "skill.rule", _item(page, "claude_code", "release-notes"), project=_project(page, medium / "work/atlas"), state="off")
        assert answer.status_code == 422 and "your user settings have skill overrides" in answer.json()["detail"]
        defs = page.get("/api/explain?name=release-notes&kind=skill").json()["definitions"]
        assert next(d for d in defs if d["kind"] == "skill")["switch"]["project"] is False

def test_turning_off_for_all_projects_names_projects_with_their_own_skill_settings(medium):
    _merge(medium / "work/atlas/.claude/settings.local.json", skillOverrides={"other": "off"})
    with served(medium) as page:
        change = _post(page, "skill.rule", _item(page, "claude_code", "brandkit"), project=None, state="off").json()
        assert {"note": "atlas has its own skill settings; it may keep this skill on."} in change["after"]

def test_switches_say_why_where_a_client_has_none(medium):
    with served(medium) as page:
        atlas = _project(page, medium / "work/atlas")
        assert _post(page, "skill.rule", _item(page, "cursor", "ui-polish"), project=None, state="off").json()["detail"] == "Cursor has no switch to turn off one skill."
        planning = _item(page, "claude_code", "planning", scope="plugin")
        assert "Turn the plugin off instead." in _post(page, "skill.rule", planning, project=None, state="off").json()["detail"]
        codex = _post(page, "skill.rule", _item(page, "codex", "docker-expert"), project=atlas, state="off")
        assert codex.json()["detail"] == "Codex has no switch for one skill in one project."

def test_codex_skill_switch_keeps_comments_and_other_entries(medium):
    config = medium / ".codex/config.toml"
    config.write_text("# mine\n" + config.read_text() + '\n[[skills.config]]\npath = "/x/SKILL.md"\nenabled = false\n')
    before = config.read_text()
    with served(medium) as page:
        change = _post(page, "skill.rule", _item(page, "codex", "docker-expert"), project=None, state="off").json()
        _run(page, change, "apply")
        assert config.read_text().startswith(before) and config.read_text().count("[[skills.config]]") == 2
        _run(page, change, "undo")
    assert config.read_text() == before

def test_a_plugin_turned_off_in_one_project(medium):
    atlas = medium / "work/atlas"
    with served(medium) as page:
        change = _post(page, "plugin.rule", _item(page, "claude_code", PLUGIN, kind="plugin"), project=_project(page, atlas), state="off").json()
        assert [s["client"] for s in change["steps"]] == ["claude_code"] and _run(page, change, "apply") == "verified"
    assert json.loads((atlas / ".claude/settings.local.json").read_text()) == {"enabledPlugins": {PLUGIN: False}}

def test_a_switch_into_a_broken_local_file_is_refused(medium):
    local = medium / "work/atlas/.claude/settings.local.json"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("{ not json")
    with served(medium) as page:
        answer = _post(page, "skill.rule", _item(page, "claude_code", "release-notes"), project=_project(page, medium / "work/atlas"), state="off")
        assert answer.json()["detail"] == "Can't change this while settings.local.json can't be read."

def test_a_one_project_switch_applies_in_a_project_outside_home(medium, tmp_path):
    outside = tmp_path / "other-disk/app"
    outside.mkdir(parents=True)
    state = json.loads((medium / ".claude.json").read_text())
    state["projects"][str(outside)] = {"mcpServers": {}}
    (medium / ".claude.json").write_text(json.dumps(state))
    with served(medium) as page:
        change = _post(page, "skill.rule", _item(page, "claude_code", "brandkit"), project=_project(page, outside), state="off").json()
        assert (_run(page, change, "apply"), _run(page, change, "undo")) == ("verified", "undone")
```

```python
# tests/unit/test_file_edits.py
def test_a_toml_array_entry_is_picked_by_its_path():
    text = '# keep\n[[skills.config]]\npath = "/a/SKILL.md"\nenabled = false\n'
    key = ("skills", "config", "[path=/b/SKILL.md]")
    assert get_value(text, key) is ABSENT
    added = set_value(text, key, {"path": "/b/SKILL.md", "enabled": False})
    assert added.startswith(text) and get_value(added, key) == {"path": "/b/SKILL.md", "enabled": False}
    assert delete_value(added, key) == text
    assert delete_value(text, ("skills", "config", "[path=/a/SKILL.md]")) == "# keep\n"
```

  Take old Part 4 Task 5's `test_a_change_to_an_all_projects_item_says_which_projects_keep_their_own`
  (into `test_after.py`) and `test_removing_an_all_projects_server_keeps_the_project_override`
  (into `test_compare.py`). Add a `review.test.mjs` test for the titles, for example "Turn off
  brandkit in Claude Code for all projects" and "Use the shared rule for release-notes in Claude
  Code in atlas".
- [ ] **Step 3: Run them to see them fail.** Expected: FAIL ("This action is not offered.").
- [ ] **Step 4: Implement** as the Interfaces say. The two branches go after `preview`'s existing
  `kept` check.
- [ ] **Step 5: Run all four checks.** Expected: PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/changes/actions.py src/kitden/clients/claude_code.py src/kitden/clients/codex.py src/kitden/changes/toml_edit.py src/kitden/web/app.py src/kitden/views/explain.py src/kitden/views/after.py src/kitden/views/review.py src/kitden/web/static/js/review.js tests/unit/test_skill_rules.py tests/unit/test_file_edits.py tests/unit/test_after.py tests/unit/test_compare.py tests/frontend/review.test.mjs
git commit -m "Switches: turn a skill or plugin off for all projects or in one" -m "Each with preview, backup and Undo; a review says when a project keeps its own."
```

---

### Task 8: Library Details as a card, with the switches (5.5, S.3, L1, L2)

**Files:**
- Modify: `src/kitden/web/static/js/details.js` (new `libraryFacts`, `switchActions`, `switchAffects`, `libraryCard`; Library rows open `detailsCard`), `src/kitden/web/static/js/library.js` (parts and captions open cards), `docs/design.md`
- Test: `tests/frontend/details.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 7's `switch` and the two actions; `detailsCard` (actions `{label, run?, body?,
  primary?}`, `more`, `after`), `factsBlock`, `docksAt`, `projectChoice(projects, picked,
  onPick)`.
- Produces `libraryFacts(row, definitions, here) -> {label, value, accent?}[]`, in order:
  - Plugin (only for a part);
  - State: "On" or "Off", plus " in this project" (accent) when the picked project's rule
    decides; or "Unknown";
  - Comes from: "All projects", "This project · <folder>" (accent) or "Only this project ·
    <folder>";
  - Source: the group caption;
  - Clients.
- Produces `switchActions(row, definitions, here) -> {label, body?, run?, primary?}[]`, the
  `detailsCard` action shape, from `switch`:
  - "Use the shared rule…" first, when the picked project's rule decides (`skill.rule` or
    `plugin.rule`, that project, null);
  - "Turn off for all projects…" while on, or "Turn on for all projects…" while off for all;
  - "Turn off in one project…" when `project`: its `run` opens `projectChoice(projects, picked,
    onPick)` in the column, starting at the picked project;
  - "Turn off <plugin> in this project…" (with a project picked) or "Turn off <plugin> in one
    project…" when `plugin` is set.

  `switch.why` is a quiet line.
- Produces `switchAffects(definition, project) -> {clients, scope, project}`. A switch names only
  its own client, for example "Changes Codex. All projects.".
- Produces `libraryCard(row, definitions, here) -> card` for `detailsCard`:
  - kind `kindWord(row)`, title, and the id `row.lookup`;
  - the facts;
  - the first line of `whyLines(definitions, here)` as the explanation;
  - `actions`: the switches (the first is `primary`), then today's adds;
  - `more`: today's Removes;
  - `after`: the `contextLinks` row;
  - `technical(techRows(definitions))`.

  A marketplace caption and a hook use the same card, with facts Kind and Clients.
- Builder call: a row's warnings come first, as a callout before the facts.

- [ ] **Step 1: Write the failing tests**

```js
// tests/frontend/details.test.mjs
const def = (f) => ({ client: 'claude_code', kind: 'skill', name: 'release-notes', scope: 'user', project: null, loads: true, enabled: 'on', actions: [], ...f });
test('a skill off in this project says so and offers the shared rule first', () => {
  const here = '/w/atlas';
  const defs = [def({ loads: false, switch: { all: true, project: true, plugin: null, why: null } }), def({ kind: 'skill_rule', scope: 'local', project: here, enabled: 'off', loads: false })];
  const facts = libraryFacts({ kind: 'skill', name: 'release-notes', group: { caption: 'Your skills' } }, defs, here);
  assert.deepEqual(facts.slice(0, 2).map((f) => [f.label, f.value, Boolean(f.accent)]), [['State', 'Off in this project', true], ['Comes from', 'This project · atlas', true]]);
  assert.deepEqual(switchActions({ kind: 'skill' }, defs, here).map((a) => a.label), ['Use the shared rule…', 'Turn off for all projects…', 'Turn off in one project…']);
});
test('a plugin skill offers its plugin, and Cursor has no switch', () => {
  const why = 'Claude Code has no switch for one skill inside a plugin, so the whole plugin goes off there.';
  const defs = [def({ scope: 'plugin', switch: { all: false, project: false, plugin: 'superpowers@demo-market', why } })];
  assert.deepEqual(switchActions({ kind: 'skill' }, defs, '/w/atlas').map((a) => a.label), ['Turn off superpowers in this project…']);
  assert.deepEqual(switchActions({ kind: 'skill' }, defs, '').map((a) => a.label), ['Turn off superpowers in one project…']);
  assert.deepEqual(switchActions({ kind: 'skill' }, [def({ client: 'cursor', switch: { all: false, project: false, plugin: null, why: 'Cursor has no switch to turn off one skill.' } })], ''), []);
  assert.equal(affectsText(switchAffects(def({ client: 'codex' }), null), ''), 'Changes Codex. All projects.');
});
```

```python
# tests/unit/test_page_words.py
def test_skill_details_name_each_switch():
    details = script("details.js")
    for words in ('"Turn off for all projects…"', '"Turn on for all projects…"', '"Turn off in one project…"', '"Use the shared rule…"',
                  '" in this project"', '"Comes from"', '"Only this project · "', "detailsCard(libraryCard("):
        assert words in details, words
```

- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement** as above. A switch's review opens in the column, and Cancel comes back
  there (Part 3). Add a "Skill and plugin switches" row to `docs/design.md`:
  - the four actions;
  - the one-project switch waits while the user settings have skill overrides;
  - Codex is for all projects only;
  - Cursor has no switch, and Details says why;
  - Library Details are the Facts card.
- [ ] **Step 4: Run all four checks, then look.** In the medium demo, pick atlas and open
  release-notes. "Turn off in one project…", then Apply: the row and block say Off with "This
  project", and "Use the shared rule…" leads. Undo from the toast.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/details.js src/kitden/web/static/js/library.js docs/design.md tests/frontend/details.test.mjs tests/unit/test_page_words.py
git commit -m "Details: a skill's facts and its switches" -m "Where a client has no switch, Details says why."
```

---

### Task 9: Add a plugin or skill from a marketplace (5.6, L4)

**Files:**
- Create: `src/kitden/web/static/js/addpanel.js`, `tests/frontend/addpanel.test.mjs`
- Modify: `src/kitden/web/static/js/library.js` ("+ Add" through `onAdd("items")`; the preview; drag; "Add a marketplace…" moves to the panel), `src/kitden/web/static/js/map.js` (`dropAt`), `docs/design.md`
- Test: `tests/frontend/addpanel.test.mjs`, `tests/frontend/map.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `/api/library?kind=plugin&show=all&q=` (Task 3); `mapPreview`, `previewOnMap`,
  `applyOnMap`, `cancelOnMap`, `barWords`, `reviewBar`; Task 6's `libraryModel(…, { preview })`;
  `addForm`, `addSkillForm` and `marketplaceForm` from `offer.js`.
- Produces (pure):
  - `panelGroups(rows, marketplace = "") -> [{marketplace, results: [{key, name, meta, tag,
    grip, row}]}]`: rows with a `marketplace`, grouped and sorted. `tag` is "Added" for
    `row.mine`. `grip` is false for an added row or one `clickPreview` cannot take.
  - `resultMeta(row)`:
    - "Plugin · N skills" when every part is a skill;
    - "Plugin · N items" otherwise, or "Plugin" when `size` is null;
    - "Skill" for a skill.
  - `clickPreview(row, found, project) -> body | null`:
    - the action is `plugin.install` for a plugin and `skill.install` for a skill;
    - the targets are every found client whose cell's `add.action` is that action;
    - `params.project` is set only when each chosen add has `project_place` or `project_only`;
    - the id comes from `offer`, then `lookup`, as `previewFor` reads them;
    - null when no client can take it.
  - `dropPreview(row, client, project)`: the same for one client.
- Produces (DOM) `openAddPanel({ title, search, results, hint, head, onPick, onDrag })`, a docked
  panel with:
  - the title;
  - "Search the marketplaces…";
  - a marketplace filter (All, then each);
  - results under marketplace captions;
  - the hint;
  - `head` actions.

  The Library passes "Add a plugin or skill", "Click to preview, or drag onto a client." and
  "Add a marketplace…". Task 10 reuses it.
- The flow:
  1. A click, or Enter on a result, runs `previewOnMap(clickPreview(…), redraw)`.
  2. The map shows `libraryModel(…, { preview: { row, clients } })`, and the picked result says
     "In preview".
  3. A drop on a client block runs `dropPreview`.
  4. `reviewBar(change, { body, onApply: () => applyOnMap(redraw), onCancel: () =>
     cancelOnMap(redraw), onShow })` sits on the canvas. `onShow` first runs `cancelOnMap(redraw)`,
     so one change never has two Apply buttons. It then opens `addForm(offer, row)` (or
     `addSkillForm`) in the column, with the bar's clients checked.
  5. After `verified` the block turns solid and the result says "Added".
- Builder call: a result whose clients have only "+ Add skills" or "+ Add the plugin" shows no
  grip and its first cell's reason. Those routes stay in its Details.
- `dropAt(layout, x, y)` in `map.js` also returns `"client:<id>"` over a client block and
  `"items"` over the Plugins and skills column. A drop on `"items"` is the click. Add a
  `map.test.mjs` test for both.

- [ ] **Step 1: Write the failing tests**

```js
// tests/frontend/addpanel.test.mjs
const add = (action, more = {}) => ({ action, label: '+ Add', project_place: false, project_only: false, ...more });
const cell = (a = null, reason = null) => ({ state: 'none', add: a, reason });
const plugin = { key: 'p', kind: 'plugin', name: 'test-helper', offer: 'test-helper@demo-market', marketplace: 'demo-market', mine: false, size: 3,
  parts: [{ kind: 'skill' }, { kind: 'skill' }, { kind: 'skill' }],
  cells: { claude_code: cell(add('plugin.install', { project_place: true })), codex: cell(add('plugin.install')), cursor: cell(null, 'via') } };
test('results group by marketplace and say what each holds', () => {
  const [group] = panelGroups([plugin, { ...plugin, key: 'q', name: 'superpowers', mine: true }]);
  assert.equal(group.marketplace, 'demo-market');
  assert.deepEqual(group.results.map((r) => [r.name, r.meta, r.tag, r.grip]), [['superpowers', 'Plugin · 3 skills', 'Added', false], ['test-helper', 'Plugin · 3 skills', null, true]]);
  assert.deepEqual([resultMeta({ kind: 'plugin', size: null, parts: [] }), resultMeta({ kind: 'skill' })], ['Plugin', 'Skill']);
});
test('a click adds to every client that can take it, a drop to one', () => {
  assert.deepEqual(clickPreview(plugin, ['claude_code', 'codex', 'cursor'], ''), { action: 'plugin.install', targets: [{ client: 'claude_code' }, { client: 'codex' }], params: { plugin: 'test-helper@demo-market' } });
  assert.equal(clickPreview(plugin, ['claude_code', 'codex'], 'p1').params.project, undefined);  // Codex has no project place
  assert.deepEqual(clickPreview(plugin, ['claude_code'], 'p1').params, { plugin: 'test-helper@demo-market', project: 'p1' });
  assert.deepEqual(dropPreview(plugin, 'codex', '').targets, [{ client: 'codex' }]);
  assert.equal(dropPreview(plugin, 'cursor', ''), null);
});
```

```python
# tests/unit/test_page_words.py
def test_the_add_panel_says_where_results_come_from():
    panel, library = script("addpanel.js"), script("library.js")
    for words in ('"Search the marketplaces…"', '"In preview"', '"Added"', '" skills"', '" items"'):
        assert words in panel, words
    for words in ('"Add a plugin or skill"', '"Click to preview, or drag onto a client."', '"Add a marketplace…"', "previewOnMap("):
        assert words in library, words
```

- [ ] **Step 2: Run them to see them fail.** Expected: FAIL (no module).
- [ ] **Step 3: Implement** as above. Add an "Add from a marketplace" row to `docs/design.md`:
  - the panel opens from "+ Add";
  - results are grouped by marketplace;
  - "Added" rows are at half strength, with no grip;
  - a click reaches every client that can take the item, in the picked project only when each of
    them can;
  - a drop adds to one client;
  - "Show changes" opens the client choice;
  - nothing changes until Apply.
- [ ] **Step 4: Run all four checks, then look.** In the medium demo, "+ Add" → test-helper. The
  preview block, the links and the bar say "Add test-helper@demo-market to Claude Code and Codex
  for all projects". Apply, then Undo; Cancel leaves no block.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/addpanel.js src/kitden/web/static/js/library.js src/kitden/web/static/js/map.js docs/design.md tests/frontend/addpanel.test.mjs tests/frontend/map.test.mjs tests/unit/test_page_words.py
git commit -m "Library: add a plugin or skill from the map" -m "The preview shows on the map; Show changes opens the client choice."
```

---

### Task 10: Gateway servers from the marketplaces (5.6, D6, `gateway.add`)

**Files:**
- Modify: `src/kitden/views/catalog.py` (`market_servers`, `market_entry`, `known_refusal`), `src/kitden/changes/actions.py` (`GATEWAY_ADD`, `gateway_add_steps`), `src/kitden/web/app.py` (`GET /api/market-servers`, the preview branch, `ADD_ACTIONS`, the tools read after `verified`), `src/kitden/views/after.py`, `src/kitden/web/static/js/review.js` (`ADDS`, the title, done words), `src/kitden/web/static/js/gateway.js` ("+ Add" beside Servers, the preview block), `src/kitden/demo/sample.py` (`_plugin_files`), `docs/design.md`
- Test: `tests/unit/test_market_servers.py` (create), `tests/unit/test_demo_home.py`, `tests/frontend/addpanel.test.mjs`, `tests/frontend/map.test.mjs` (where `dropAt` is used), `tests/unit/test_page_words.py`, `tests/security/test_no_secrets.py` (its sweep gains `/api/market-servers`)

**Interfaces:**
- Produces `market_servers(inventory, adapters, held: set[str], q="") -> list[dict]`, with one
  result per server in a plugin folder on this computer (`catalog()` clone folders, then Task 2's
  installed folders). Each result is `{id: "<plugin id>/<name>", name, plugin, marketplace, kind:
  "remote" | "local", held, refusal}`, and `q` matches part of the name, plugin or marketplace.
  `GET /api/market-servers?q=` answers `{servers: [...]}`.
- Produces `market_entry(adapters, server_id) -> tuple[str, dict]`: the raw entry, read again as
  `_inside` reads it (the manifest's dict `mcpServers`, else `.mcp.json` or `mcp.json`).
- Produces `known_refusal(name, entry, inventory, held) -> str | None`. It checks in order,
  without the network, and uses Part 4's `gateway_entry` and `reads_elsewhere` from
  `clients/entries.py` to detect:

  | Holds | Refusal |
  | --- | --- |
  | `name` in `held` | "<name> is in the gateway already." |
  | a client has an MCP item of that name | "<Client> has <name> already. Move it into the gateway instead." |
  | `type` `sse` or `ws`, or the address ends in `/sse` | "<name> uses a connection the Kitden gateway does not support yet." |
  | `reads_elsewhere(entry, gateway_entry(entry))` | "<name> reads values Kitden can't fill in." |
  | a value ending in `.mcpb` | "<name> comes as a bundle; Kitden can't run it yet." |
  | the command or an argument starts with `./` or `../`, or is a bare name with a `SCRIPT_SUFFIXES` suffix | "<name> runs a file inside its plugin folder; Kitden can't run it from the gateway." |

- Produces `GATEWAY_ADD = "gateway.add"`, with body `{targets: [{client}…], params: {server:
  <id>}}`. `gateway_add_steps(adapters, inventory, home, server_id, clients, command, *,
  added_clients, sign_in=None, keychain_run=None) -> list[Step]`:
  1. It refuses `known_refusal` first.
  2. For a remote entry with no headers of its own, it makes one `sign_in(url, {})` call. No
     answer refuses: "Kitden could not reach <name>." OAuth refuses: "<name> signs in with OAuth;
     it waits for sign-in."
  3. Then come these steps:
     - `_server_step(home, name, gateway_entry(entry), None, keychain_run)`, so secrets go to the
       Keychain;
     - the `path` step when the settings have none;
     - `setup_server_steps` for target clients without the `kitden` entry, with Codex's
       timeouts, as a move gives them;
     - `_codex_timeout_steps(adapters)`.

  After `verified`, `refresh_later([name])` runs, as it does for `moved_in`. A `streamable-http`
  entry maps to `url`.
- Words:
  - title "Add <name> to the Kitden gateway", followed by `target`'s scope words;
  - done "Added <name> to the Kitden gateway";
  - `gateway.add` joins `ADDS` and `ADD_ACTIONS`;
  - after chips `{state: "gw", word: "Via gateway"}` per client whose `kitden` entry is on or
    added.
- The page:
  - The Servers column's "+ Add" (`drawMap`'s `onAdd("servers")`) runs `openAddPanel` with "Add
    a server" and "Click to preview, or drag onto the map.".
  - A result shows "Remote" or "Local", and "In the gateway" (`held`) or "Added" (verified here).
  - A result with a `refusal` has no grip, and the refusal is its meta.
  - A click previews with every found client. A drop on a client block uses that client, and a
    drop on the Servers column is the click (`dropAt` in `map.js`).
  - The preview block is `gatewayTree(…, { preview: { name, kind } })` under Remote or Local,
    with Part 4's bar. A refusal stays in the bar with "Nothing was changed." (`barWords`).
- Demo, in `_plugin_files`:
  - `db-tools` gains `.mcp.json` `{"mcpServers": {"db-query": {"command": "uvx", "args":
    ["mcp-db-query"]}}}`;
  - `test-helper` gains `{"mcpServers": {"test-status": {"type": "http", "url":
    "https://status.example.test/mcp"}}}`.
- Builder calls:
  - The gateway has no per-client server switch (spec "Later"). A drop on one client connects only
    that client, but every client whose `kitden` entry is on reaches the server. The chips name
    them.
  - The sign-in check never sends a header, so no secret leaves. A remote entry with its own
    headers signs in by them and is not checked.
  - `known_refusal` has words of its own, because "stays direct" (`entry_refusal`) does not fit a
    server no client has.

- [ ] **Step 1: Check the docs.** Read code.claude.com/docs/en/plugins-reference (`mcpServers`
  forms, `${CLAUDE_PLUGIN_ROOT}`, `.mcpb`) and Codex's plugin build page (`mcp.json`,
  `streamable-http`). Date the claims in `known_refusal`'s comment.
- [ ] **Step 2: Write the failing tests**

```python
# tests/unit/test_market_servers.py
def _servers(home):
    inventory = demo_build(home)()
    adapters = {a.id: a for a in demo_adapters(home)}
    return {s["name"]: s for s in market_servers(inventory, adapters, set(load_settings(home)["servers"]))}

def _add(page, server, clients=()):
    body = {"action": "gateway.add", "targets": [{"client": c} for c in clients], "params": {"server": server}}
    return page.post("/api/changes/preview", json=body, headers=POST)

def test_market_servers_say_why_before_any_preview(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    found = _servers(home)
    assert [(found[n]["kind"], found[n]["refusal"]) for n in ("db-query", "test-status")] == [("local", None), ("remote", None)]
    assert found["pr-index"]["refusal"] == "pr-index runs a file inside its plugin folder; Kitden can't run it from the gateway."
    assert found["db-query"]["id"] == "db-tools@demo-market/db-query" and "tools" not in found["db-query"]
    with served(home) as page:
        assert _add(page, found["pr-index"]["id"]).json()["detail"] == found["pr-index"]["refusal"]

@pytest.mark.parametrize(("entry", "words"), [
    ({"type": "sse", "url": "https://a.test/sse"}, "does not support yet."),
    ({"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/x.js"]}, "reads values Kitden can't fill in."),
    ({"url": "https://a.test/mcp", "headers": {"X": "${TOKEN}"}}, "reads values Kitden can't fill in."),
    ({"command": "./bin/server"}, "runs a file inside its plugin folder"),
    ({"command": "npx", "args": ["x.mcpb"]}, "comes as a bundle"),
])
def test_entries_the_gateway_cannot_run_are_refused(tmp_path, entry, words):
    assert words in known_refusal("x", entry, build_inventory(build_demo_home(tmp_path, "small")), set())

def test_a_name_a_client_has_offers_move_instead(tmp_path):
    inventory = build_inventory(build_demo_home(tmp_path, "small"))
    assert known_refusal("docs", {"url": "https://x.test/mcp"}, inventory, set()) == "Claude Code has docs already. Move it into the gateway instead."

def test_adding_a_marketplace_server_to_the_gateway_and_undo(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    settings = data_dir(home) / SETTINGS_FILE
    before = settings.read_bytes()
    with served(home) as page:
        [server] = page.get("/api/market-servers?q=status").json()["servers"]
        change = _add(page, server["id"], ["cursor"]).json()
        # The server's entry, then Cursor's kitden entry (the medium sample's Cursor has none); Codex's timeouts left out.
        assert [s["client"] for s in change["steps"] if s["client"] != "codex"] == [KITDEN_GATEWAY, "cursor"]
        assert page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
        assert "test-status" in load_settings(home)["servers"]
        assert page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
    assert settings.read_bytes() == before

def test_an_oauth_server_is_refused_at_preview_and_nothing_is_written(tmp_path, monkeypatch):
    monkeypatch.setattr(kitden.demo, "no_sign_in", lambda url, headers: True)  # create_app reads it
    home = build_demo_home(tmp_path, "medium")
    with served(home) as page:
        [server] = page.get("/api/market-servers?q=status").json()["servers"]
        assert _add(page, server["id"]).json()["detail"] == "test-status signs in with OAuth; it waits for sign-in."
        assert page.get("/api/changes").json() == []
```

```python
# tests/unit/test_demo_home.py: the contract gains two servers the gateway can add
def test_the_demo_marketplace_has_two_servers_the_gateway_can_add(tmp_path):
    plugins = build_demo_home(tmp_path, "medium") / ".claude/plugins/marketplaces/demo-market/plugins"
    assert json.loads((plugins / "db-tools/.mcp.json").read_text())["mcpServers"]["db-query"]["command"] == "uvx"
    assert json.loads((plugins / "test-helper/.mcp.json").read_text())["mcpServers"]["test-status"]["type"] == "http"
```

  Also:
  - add `/api/market-servers` to the sweep in `tests/security/test_no_secrets.py`;
  - add a node test for the Gateway's result meta ("Remote", "Local", the refusal, no grip when
    refused);
  - pin "Add a server", "Click to preview, or drag onto the map." and "In the gateway".
- [ ] **Step 3: Run them to see them fail.** Expected: FAIL (no `market_servers`).
- [ ] **Step 4: Implement** as above. Add an "Add a server" row to the Gateway part of
  `docs/design.md`:
  - servers come from the marketplaces on this computer;
  - a result says Remote or Local, never a tool count;
  - a known reason shows first, with no grip;
  - a remote server is asked once whether it signs in, with no secret;
  - a local server never starts before Apply.
- [ ] **Step 5: Run all four checks, then look.** In the medium demo, open the Gateway and
  "+ Add". test-status and db-query preview and apply; pr-index shows its reason.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/views/catalog.py src/kitden/changes/actions.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/review.js src/kitden/web/static/js/gateway.js src/kitden/demo/sample.py docs/design.md tests/unit/test_market_servers.py tests/unit/test_demo_home.py tests/frontend/addpanel.test.mjs tests/unit/test_page_words.py tests/security/test_no_secrets.py
git commit -m "Gateway: add a server from a marketplace" -m "Kitden says first why one cannot be added; a remote one is asked once whether it signs in."
```

---

### Task 11: Docs for Part 5

**Files:**
- Modify: `README.md` (the Library section), `docs/development.md` ("Check before a release"); read through `docs/design.md`
- Test: `tests/unit/test_docs_words.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_docs_words.py
def test_readme_says_what_the_library_shows_and_switches():
    readme = " ".join((ROOT / "README.md").read_text().split())
    for words in ("Plugins and skills", "Differences", "Add missing plugins and skills…", "Needs your decision",
                  "Kitden cannot add", "Turn off in one project…", "Use the shared rule…", "Add a server"):
        assert words in readme, words
    check = (ROOT / "docs/development.md").read_text()
    assert "skillOverrides" in check and "Add a server" in check
```

  Update `test_readme_names_the_management_actions` for the new Add missing button names.
- [ ] **Step 2: Run it to see it fail.** Expected: FAIL.
- [ ] **Step 3: Write.** The README's Library section, in plain words:
  - two tabs, with MCP servers on the Gateway;
  - the map, where the link is the state;
  - the List with Installed and Differences;
  - the two Add missing buttons and their four groups;
  - the switches, and the clients that have none;
  - "+ Add" from the marketplaces on this computer.

  Add manual checks to `docs/development.md`, each marked "Not run yet: Part 5 was built and tested
  with sandbox files only.":
  - a skill off in one project through `skillOverrides`: a new session there lacks it, one
    elsewhere has it; then Undo;
  - a plugin off in one project;
  - a Codex skill off for all projects;
  - a server added with "Add a server": a new session reaches it; then Undo.

  Read `docs/design.md` once through for repetition and stale words, and fix them in place.
- [ ] **Step 4: Run all four checks.** Expected: all pass.
- [ ] **Step 5: Roadmap lines.** While `git status --short ROADMAP.md` shows the owner's ` M`,
  leave it alone and put these lines in the report:

```markdown
- **Library map and list:** clients → plugins and skills by source → what a plugin holds, and a List
  with Differences. Add missing sorts what it finds into four groups, in the Library and on the
  Gateway. Claude Code's local plugin settings and skill overrides are read.
- **Switches:** a Claude Code skill off for all projects or in one, a plugin off in one project, a
  Codex skill off for all projects. "Skills per project" leaves Later for Claude Code only.
- **Add from a marketplace:** plugins, skills and gateway servers from the marketplaces on this
  computer, previewed on the map.
```

- [ ] **Step 6: Commit**

```bash
git add README.md docs/development.md docs/design.md tests/unit/test_docs_words.py
git commit -m "Docs: the Library map, switches and marketplace adds"
```

---

## Spec coverage

| Spec | Task |
| --- | --- |
| 5.1 local `enabledPlugins` (local > project > user); `skillOverrides` key by key, "not checked" | 1 |
| 5.1 installed parts via `_inside()`, signature cache; start time | 2 |
| 5.2 two tabs; servers to the Gateway; hooks under a source; marketplace captions with Details; old links; "Add a marketplace…" in the panel | 3, 4, 9 |
| 5.3 tree; only what is here; "N items"; links, faint links; "This project" | 3, 6 |
| 5.4 List cells; Installed / Differences (`show=diff`), plugin over parts | 4 |
| 5.4 Add missing in four groups, project and All projects; "Add missing servers…" | 5 |
| 5.5 Claude Code skill switches; plugin in one project; Codex `[[skills.config]]`; Cursor's reason; `project_keeps` and the `skillOverrides` note | 7, 8 |
| 5.6 panel, filter, groups; plugins and skills; preview on the map; clients per add; keyboard | 9 |
| 5.6 gateway servers, Remote/Local, "In the gateway"/"Added", no tool count; sign-in check; `gateway.add` refusals; demo servers | 10 |
| `own_rules` gains the Library's project rules | 3 |
| Done: tests per read fix and action with Undo; four groups on medium; refusals; node tests for tree and Differences; design.md | 1–10, read through in 11 |
