# UX Audit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the trust, decision, readability and interaction problems found by the UX audit, without changing Kitden's look, navigation or safety sequence.

**Architecture:** Small changes inside the existing flows. The server adds one read route, scoped gateway data, inherited-client facts and a suggestion list. The page uses them to tell the truth about results, scope, freshness and effects. Motion and waits get simpler, and a few tokens fix contrast.

**Tech Stack:** Python 3 / Starlette (`src/kitden`), plain ES modules and one stylesheet (`src/kitden/web/static`), pytest, `node --test`.

**Spec:** `docs/research/ux-audit-2026-10-19.md` (read its "Priority recommendations", "Motion review", "Visual and accessibility refinements" and "Implementation and browser evidence" sections).

## Global Constraints

- Every change goes preview → Apply with a backup → verify → Undo. A success look appears only after the server says `verified`.
- Main pages show a name, the client and an action. Paths, addresses and commands stay behind Details.
- UI text is short, plain English. No new navigation, modes, tour, command system or animation library.
- Strict CSP: no inline scripts or styles on the real page, no CDN, no web fonts. Text is set with `textContent` only.
- The house mark stays `#C85835`. Client icons keep vendor colours; state lives beside them.
- Tests use sandbox homes and never touch the real home folder.
- Before each commit run `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .` and `node --test tests/frontend/*.test.mjs`.
- Commit messages: a short plain subject and one to three simple lines, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Do not commit `.specify/`, `.impeccable/` or `docs/research/` (other agents' files).
- Do not invent a restart detector or claim a running client reloaded a change.
- Do not promise a gateway capability by renaming a button.

## Review Focus

1. The Apply answer is lost but the server applied the change. The page must report the verified result after it reads the change back, and must never say nothing was written. Pinned by Task 1's API test, plus the browser check in Task 12.
2. The project changes while its map request fails. The page must not show the old project's rows under the new project's name. Pinned by Task 3's node test.
3. Two gateways, a disabled entry and a project-only entry. Each gateway card shows only its own, effective connections. Pinned by Task 4's test.
4. Cursor runs with Include Third-Party Plugins, or plugin import, turned off. The review must not claim Cursor loads the plugin. Pinned by Task 6's tests.
5. Two plugins share one name in two marketplaces. Each row shows its source in full, so the right one can be picked without Details. Pinned by Task 7's page-words test, plus the browser check in Task 12.

## Subagents

The four code maps behind this plan were made by read-only subagents on 2026-10-19.

For execution, use **subagent-driven development**: one fresh implementer subagent per task, then a reviewer subagent before the next task. Run the tasks **in order**. Most of them touch `panel.js` or `style.css`, so two implementers working at once would overwrite each other.

There are two exceptions:

- **Task 4 can run in parallel with Tasks 1-3.** It touches only `gateway_view.py`, `gateway.js` and their tests. Give it its own worktree and merge it before Task 5, which builds on it.
- **Task 12 is a separate verification subagent.** It is read-only on the code and works on a sandbox home. It walks the audit's acceptance checks in a browser and reports what passed and what did not.

## Out of scope

- The user study (audit, "User validation plan") is a separate piece of work for the owner.
- The 14 px text prototype and the Desktop Code tab explanation are optional ideas in the audit, not fixes.
- No telemetry, no new navigation and no mobile redesign.
- Navigation cross-fades and sliding marks stay as they are. The audit blocks further motion work until the forced waits and the focus problems are fixed (Tasks 9 and 10). Revisit them after a check with users.

---

## Phase 1: Trust and decisions

### Task 1: Tell the truth when the Apply answer is lost

**Files:**
- Modify: `src/kitden/web/app.py` (the routes list around `:661`; a new handler beside `change_action` at `:537`)
- Modify: `src/kitden/web/static/js/panel.js` (`applyChange` `:565-604`, `failed` `:512-520`)
- Test: `tests/unit/test_api_changes.py`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: `GET /api/changes/{change_id}`. It returns `change_dict(change)` when the id is in `engine.changes`, otherwise the matching entry from `engine.store.entries()`, otherwise 404 `{"detail": "Unknown change."}`.
- Produces, in panel.js: `async function readChange(id) -> object | null`. It returns null when the read fails.

- [ ] **Step 1: Write the failing API tests.** Preview and apply a change the way `test_removing_a_direct_entry_and_undo` does, then:

```python
def test_a_change_can_be_read_back_by_id(client):
    change_id = _apply_remove_direct(client)  # helper built from the existing remove test
    answer = client.get(f"/api/changes/{change_id}")
    assert answer.status_code == 200
    assert answer.json()["id"] == change_id and answer.json()["state"] == "verified"

def test_reading_an_unknown_change_is_404(client):
    answer = client.get("/api/changes/nope")
    assert answer.status_code == 404 and answer.json()["detail"] == "Unknown change."
```

- [ ] **Step 2: Write the failing page-words test.**

```python
def test_a_lost_apply_answer_is_checked_not_guessed():
    text = script("panel.js")
    assert "Nothing was changed by this page" not in text
    assert "Could not confirm the result. Check Changes before trying again." in text
    assert "readChange(" in text
```

- [ ] **Step 3: Run them.** `uv run pytest -q tests/unit/test_api_changes.py -k "read_back or unknown_change_is_404" tests/unit/test_page_words.py -k lost_apply`. Expected: 3 failures.
- [ ] **Step 4: Add the route and handler** (GET, read-only, no write lock).
- [ ] **Step 5: Change `applyChange`.** Wrap only the `postJson(.../apply)` call. When it throws, call `readChange(change.id)`:
  - `verified`: run the normal success path.
  - another final state (`restored`, `stale`, `undo_blocked`): run the existing not-verified path with that change.
  - `null`, `applying` or `previewed`: show `callout("Could not confirm the result. Check Changes before trying again.", "error")`.

  Errors thrown after a verified answer (render, toast) must not reach this message. Remove old `.callout.error` nodes before adding a new one, as `:582` already does.
- [ ] **Step 6: Run the tests.** Same command as Step 3, then the full suite. Expected: all pass.
- [ ] **Step 7: Commit.** `git commit -m "changes: read a change back when the Apply answer is lost"`

### Task 2: Saved settings, scope words and restart notes that stay

**Files:**
- Modify: `src/kitden/changes/engine.py` `_log` (`:644-668`)
- Modify: `src/kitden/views/load_map.py` `SCOPE_WORDS` (`:26-33`)
- Modify: `src/kitden/web/static/js/changes.js` (`SCOPE_WORDS` `:20`, `show()` `:72-92`)
- Modify: `src/kitden/web/static/js/map.js` (the lede)
- Test: `tests/unit/test_api_changes.py`, `tests/unit/test_load_map.py`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: each step in a log entry also has `"restart_note": str | None` and `"login_note": str | None`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_the_changes_log_keeps_each_steps_restart_note(client):
    _apply_remove_direct(client)  # a Codex entry, from Task 1
    step = client.get("/api/changes").json()[0]["steps"][0]
    from kitden.clients.codex import RESTART
    assert step["restart_note"] == RESTART

def test_changes_and_the_load_map_say_saved_settings_and_scope():
    assert "Based on saved settings." in script("map.js")
    changes = script("changes.js")
    assert "To take effect" in changes and "global settings" in changes
    assert '"everywhere"' not in changes
```

  In `tests/unit/test_load_map.py`, change the two `where == "everywhere"` assertions (`test_cursor_loading_a_plugin_twice_is_one_cell_with_count_2`, `test_cross_loaded_cells_say_via_which_client`) to `"global settings"`.
- [ ] **Step 2: Run them.** Expected: they fail.
- [ ] **Step 3: Implement.**
  - `_log` writes `restart_note` and `login_note` from each step.
  - `SCOPE_WORDS[Scope.USER] = "global settings"` in both files.
  - The Load map lede ends with `Based on saved settings.`
  - The change panel lists the step notes under an `h2` `To take effect`, when any note exists.
- [ ] **Step 4: Run the full suite.** Expected: pass. Older log entries have no notes; the panel shows none for them.
- [ ] **Step 5: Commit.** `git commit -m "changes: keep restart notes and say global settings"`

### Task 3: Show only data that belongs to the shown project, and say when it is old

**Files:**
- Modify: `src/kitden/web/static/js/store.js` (`data` `:18`, `guarded` `:84-91`, `reload` `:126-130`)
- Modify: `src/kitden/web/static/js/app.js` (`refresh` `:81-86`)
- Modify: `src/kitden/web/static/js/map.js` (`:54-59`), `overview.js` (`:13-18`), `gateway.js` (its model read)
- Modify: `src/kitden/web/static/js/parts.js` (a new `staleNote`)
- Create: `tests/frontend/store.test.mjs`
- Modify: `AGENTS.md` (the node command becomes `node --test tests/frontend/*.test.mjs`)

**Interfaces:**
- Produces in store.js:
  - `data.scope: { [name]: projectId }` and `data.readAt: { [name]: number }`, set only after a successful read.
  - `export function current(name) -> object | null`: `data[name]` when `data.scope[name] === state.project`, else null.
  - `export const freshness = { reloadStartedAt, lastGoodRead: number | null, lastReadFailed: boolean }`.
- Produces in parts.js: `staleNote(time: number) -> HTMLElement`. It is a callout reading `Could not refresh. Showing what Kitden read at HH:MM.`

- [ ] **Step 1: Write the failing node test.** Stub `matchMedia`, `document` and `location` the way `motion.test.mjs` does, and stub `globalThis.fetch`. Two test-local helpers do the stubbing:
  - `fetchAnswers(map)` answers each URL in `map` with 200 and that JSON. `/api/projects` returns `[{id: "a"}, {id: "b"}]`, so `loadShared` keeps the chosen project. Every other `/api/...` URL returns `{}`.
  - `fetchFails(url)` makes that one URL reject.

  `ALL_OK` is a map where every read succeeds.

```js
test('a failed read for a new project never shows the old project', async () => {
  fetchAnswers({ '/api/map?project=a': { rows: ['a-row'] } });
  state.project = 'a'; await reload();
  assert.equal(current('map').rows[0], 'a-row');
  fetchFails('/api/map?project=b');
  state.project = 'b'; await reload();
  assert.equal(current('map'), null);
  assert.ok(data.errors.map);
});

test('the last good read time moves only when every read worked', async () => {
  fetchAnswers(ALL_OK); await reload();
  const good = freshness.lastGoodRead;
  fetchFails('/api/overview'); await reload();
  assert.equal(freshness.lastGoodRead, good);
  assert.equal(freshness.lastReadFailed, true);
});
```

- [ ] **Step 2: Run it.** `node --test tests/frontend/store.test.mjs`. Expected: FAIL (`current` is not exported).
- [ ] **Step 3: Implement the store.**
  - `guarded(name, url, apply, scope)` records `scope` and the time on success.
  - `reload` sets `lastGoodRead` and `lastReadFailed`.
- [ ] **Step 4: Use the store in the views and the shell.**
  - Views read `current(name)`. With no current model, they show the error banner if the read failed, else the skeleton. With a current model and an error, they show `staleNote(data.readAt[name])` above it.
  - `refresh` writes the time of `lastGoodRead` to `#scanned`, and appends ` · could not refresh` when `lastReadFailed`.
- [ ] **Step 5: Run node, pytest and ruff.** Expected: all pass.
- [ ] **Step 6: Commit.** `git commit -m "page: never show old data as the chosen project"`

### Task 4: Gateway connections per gateway and scope (parallel lane)

**Files:**
- Modify: `src/kitden/views/gateway_view.py` (`gateway_view` `:54-81`)
- Modify: `src/kitden/web/static/js/gateway.js` (`:230`, `:232`, `routes()` `:302-368`)
- Test: `tests/unit/test_gateway_view.py`

**Interfaces:**
- Produces: `connections` becomes `{gateway_id: {"claude_code": [names], "codex": [names], "cursor": [names]}}`. It is built from `effective_view(inventory, client, project)`, so entries that are off and other projects' entries are left out. Desktop entries count as `claude_code`.
- Produces: `used` is the sorted ids that have at least one connection in that scope.

- [ ] **Step 1: Write the failing test.** Register gateways A and B in the fixture home. Point Codex's `neon` at A and Cursor's `Neon` at B. Turn off one more Codex entry that points at A. Add a project-only Claude Code entry in project P that points at A.

```python
def test_each_gateway_lists_only_its_own_effective_connections(home):
    view = gateway_view(build_inventory(home), [a, b], None)
    assert view["connections"] == {
        a.id: {"claude_code": [], "codex": ["neon"], "cursor": []},
        b.id: {"claude_code": [], "codex": [], "cursor": ["Neon"]},
    }
    in_project = gateway_view(build_inventory(home), [a, b], P)
    assert in_project["connections"][a.id]["claude_code"] == ["docs"]
```

  Update `test_connections_list_gateway_entries_per_client` to the new shape.
- [ ] **Step 2: Run it.** `uv run pytest -q tests/unit/test_gateway_view.py`. Expected: FAIL.
- [ ] **Step 3: Implement the server side.** Then in gateway.js, each card reads `model.connections[gateway.id] || {}` for `routes()` and `waiting`.
- [ ] **Step 4: Run the full suite.** Expected: pass.
- [ ] **Step 5: Commit.** `git commit -m "gateway: each card shows only its own connections"`

### Task 5: Direct servers are an option, and Details leads with Move

**Files:**
- Modify: `src/kitden/views/overview.py` (the gateway card `:133-157`, the return dict `:164-179`)
- Modify: `src/kitden/web/static/js/overview.js` (render `suggestions`)
- Modify: `src/kitden/views/load_map.py` (`_flag` `:136-137`, `GATEWAY_FIX`)
- Modify: `src/kitden/web/static/js/panel.js` (the item panel's primary button `:291-305`)
- Test: `tests/unit/test_overview.py`, `tests/unit/test_load_map.py`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 4's `gateway_view` and `data.gateway` (`gateways[].movable`, `groups.move[]` of `{name, items}`).
- Produces: `overview(...)["suggestions"]`, a list of `{title, text, action, target}`. The gateway card moves here from `attention`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_direct_servers_are_a_suggestion_not_attention(home):
    # same home, registered gateway and overview(...) call as the current
    # test_gateway_card_only_with_a_registered_gateway
    inv = build_inventory(home)
    data = overview(inv, ...)
    moves = len(gateway_view(inv, gateways, None)["groups"]["move"])
    assert all("gateway" not in a["title"] for a in data["attention"])
    assert data["suggestions"] == [{
        "title": f"{moves} MCP servers can move into the gateway",
        "text": "They connect to each client directly now.",
        "action": "Review", "target": {"view": "gateway"},
    }]
```

  - In `test_gateway_entries_are_state_gw`, the flag becomes `{"text": "Direct connection", "level": "info"}`.
  - In the page words, `panel.js` contains `"Move into the gateway…"` and `action: "gateway.move"`.
  - Update `test_gateway_card_only_with_a_registered_gateway` and `test_kitdens_own_server_is_not_counted_as_not_connected` to the suggestion shape.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the server side.**
  - The count is the number of unique `move` rows, the same as the Gateway page.
  - Local and plugin servers are not mentioned.
  - The headline counts `attention` only.
- [ ] **Step 4: Implement the page.**
  - Overview renders suggestions under an `h2` `Can improve`, in the same card style without the warning colour.
  - In the item panel, when `data.gateway` has a movable gateway and a `groups.move` row with this name, the primary button is `Move into the gateway…`. It runs `review({ action: "gateway.move", targets: row.items.map((item) => ({ item })), params: { gateway: target.id } })`.
  - Remove buttons stay under More.
  - Without a movable gateway, show the existing note on adding it in the gateway first. Remove is then a plain button, not primary.
- [ ] **Step 5: Run the full suite.** Expected: pass.
- [ ] **Step 6: Commit.** `git commit -m "gateway: direct servers are an option; Details offers Move first"`

### Task 6: Add and Preview show every client the change reaches

**Files:**
- Modify: `src/kitden/clients/cursor.py` (beside `reads_other_clients` `:87-91`)
- Modify: `src/kitden/views/after.py` (`after_words`)
- Modify: `src/kitden/web/app.py` (the `after_words` call `:535`; the `/api/catalog` answer)
- Modify: `src/kitden/web/static/js/discover.js` (`cell` `:213-220`, `clientChecks` `:434-449`, `addForm` `:471`, `addSkillForm` `:484`, `showOffer` `:369`, `showSkill` `:395`)
- Test: `tests/unit/test_read_cursor.py`, `tests/unit/test_api_plugin_install.py`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: `CursorAdapter.imports_claude_plugins(self) -> bool`. It is true only when `thirdPartyExtensibilityEnabled` and `importPluginsFromClaudeOnBoot` are both not `False`.
- Produces: `after_words(change, inventory, cursor_imports: bool = False)`. For `plugin.install` with a `claude_code` step and `cursor_imports`, it appends `{"client": "cursor", "state": "on", "word": "Loads", "note": "Cursor loads Claude Code plugins, so it gets this one too."}`.
- Produces: the `/api/catalog` answer (both kinds) gains `"inherits": {"plugin": bool, "skill": bool}`, read from `imports_claude_plugins()` and `reads_other_clients()`. Both are false when Cursor is not found.

- [ ] **Step 1: Write the failing tests.**

```python
def test_cursor_imports_claude_plugins_only_with_both_switches_on(tmp_path, no_version):
    # cursor_adapter(tmp_path, flags): make_home with cursor/3.21.16,
    # write_cursor_fixture_state(home, {REACTIVE_KEY: flags}), then CursorAdapter(home)
    assert cursor_adapter(tmp_path / "a", {}).imports_claude_plugins() is True
    off = {"importPluginsFromClaudeOnBoot": False}
    assert cursor_adapter(tmp_path / "b", off).imports_claude_plugins() is False
    no_third = {"thirdPartyExtensibilityEnabled": False}
    assert cursor_adapter(tmp_path / "c", no_third).imports_claude_plugins() is False

def test_adding_to_claude_code_says_cursor_loads_it_too(cursor_client):
    change = _preview(cursor_client, "linter@claude-plugins-official", ["claude_code"]).json()
    assert change["after"][-1] == {"client": "cursor", "state": "on", "word": "Loads",
                                   "note": "Cursor loads Claude Code plugins, so it gets this one too."}
    assert cursor_client.get("/api/catalog").json()["inherits"] == {"plugin": True, "skill": True}

def test_with_cursor_import_off_the_review_does_not_name_cursor(strict_cursor_client):
    change = _preview(strict_cursor_client, "linter@claude-plugins-official", ["claude_code"]).json()
    assert [e["client"] for e in change["after"]] == ["claude_code"]
```

  - `cursor_client` is the existing `client` fixture plus `cursor/3.21.16` and `write_cursor_fixture_state`.
  - `strict_cursor_client` is the same with `importPluginsFromClaudeOnBoot: False`.
  - The page-words test pins three things in discover.js: the line `Cursor will also load this through Claude Code.`, `answer.inherits` and `"Source: "`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the server side.** Pass `cursor_imports` from the found Cursor adapter in `preview`.
- [ ] **Step 4: Implement the page.**
  - The Cursor cell uses `inherits.plugin` / `inherits.skill`, not a guess.
  - The Add forms show the description, `Source: <marketplace or plugin>`, the client checkboxes, the marketplace note, and the inherited line while Claude Code is checked.
  - The checkboxes start checked only when one client is open; otherwise none are checked, and `Choose at least one client.` stays.
  - `showOffer` and `showSkill` put an `Add…` button in the panel footer when a client is open. It opens the same form.
- [ ] **Step 5: Run the full suite.** Expected: pass.
- [ ] **Step 6: Commit.** `git commit -m "discover: Add and Preview name every client the change reaches"`

## Phase 2: Readability and discovery

### Task 7: Readable item identity in Discover

**Files:**
- Modify: `src/kitden/web/static/js/discover.js` (`offerTable` `:171-177`, `offerRow` `:275-288`, `skillRow` `:316-318`)
- Modify: `src/kitden/web/static/style.css` (`.offers` rules `:305-314`)
- Test: `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: the second line of a row is `div.meta`. It holds `span.from` (the marketplace, or for a skill its plugin) and then `span.desc`. The source is never cut; the description wraps to at most two lines.

- [ ] **Step 1: Write the failing page-words test.**

```python
def test_discover_rows_keep_the_name_and_the_source_readable():
    text, css = script("discover.js"), (STATIC / "style.css").read_text()
    assert '["42%"' in text and 'el("div", "meta")' in text
    assert ".offers .desc" in css and "-webkit-line-clamp: 2" in css
    assert ".offers .from { flex: none" in css
```

- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - The item column is 42%, the client columns share 48% and the Add column keeps 10%.
  - The top line holds the name and the category flag only; the name keeps its ellipsis and its `title`.
  - Every row shows its source, not only twins.
- [ ] **Step 4: Run the full suite.** Check the page at 1280 px and at 1024 px with 125% zoom: two same-name rows (canva, figma) show different sources. Expected: pass.
- [ ] **Step 5: Commit.** `git commit -m "discover: rows show the source and two lines of description"`

### Task 8: Rows say they open Details; search says what it searches

**Files:**
- Modify: `src/kitden/web/static/style.css` (a `.sr-only` utility; `.opens` chevron)
- Modify: `src/kitden/web/static/js/map.js` (`buildRow`), `discover.js` (`tableRow` `:246`), `changes.js` (`changeRow` `:53`)
- Modify: `src/kitden/web/static/js/app.js` (`renderShell` `:61-77`), `src/kitden/web/static/index.html` (`:38`)
- Test: `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: `parts.js` `opens() -> HTMLElement`. It is a span with an aria-hidden `›` and an `.sr-only` `Open details`, placed at the end of the row's name cell (Changes: at the end of the row).

- [ ] **Step 1: Write the failing page-words test.**

```python
def test_rows_say_they_open_details_and_search_names_its_scope():
    for name in ("map.js", "discover.js", "changes.js"):
        assert "opens()" in script(name)
    assert ".sr-only" in (STATIC / "style.css").read_text()
    app = script("app.js")
    assert "Search your setup…" in app and "Search plugins and skills to add…" in app
    assert 'placeholder="Search your setup…"' in INDEX
```

  `'"Details"' not in discover.js` and `changes.js` must stay true: the word is "Open details".
- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - `renderShell` sets the placeholder and `aria-label` of `#q` per view: Discover gets the plugins text, every other place gets `Search your setup…`.
  - The chevron uses `--ink-3` and takes `--route` on row hover.
- [ ] **Step 4: Run the full suite.** Check that the search text and the filters survive opening and closing Details. Expected: pass.
- [ ] **Step 5: Commit.** `git commit -m "page: rows show they open details; search says its scope"`

### Task 9: Keyboard focus survives tabs, filters and the review

**Files:**
- Modify: `src/kitden/web/static/js/app.js` (focus keep `:33-42`)
- Modify: `src/kitden/web/static/js/map.js` (`tabs()` `:112-124`, seg `:72-79`), `discover.js` (`kindTabs` `:91`, seg `:116-123`, `picker` `:76`)
- Modify: `src/kitden/web/static/js/panel.js` (`trapFocus` `:679-697`)
- Test: `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: a `data-focus` key on each tab (`tab:<kind>`), seg button (`show:<id>`) and filter select (`filter:<key>`). After a render, app.js focuses the element with the same key as the one that had focus.

- [ ] **Step 1: Write the failing page-words test.**

```python
def test_focus_returns_to_the_control_and_the_review_reaches_its_summary():
    assert "dataset.focus" in script("app.js")
    for name in ("map.js", "discover.js"):
        assert '"ArrowRight"' in script(name) and "dataset.focus" in script(name)
    assert "summary" in script("panel.js").split("function trapFocus")[1].split("\n}")[0]
```

- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - Left and right arrows on a tab move focus to the next or previous tab and select it. Home and End go to the first and last.
  - The trap's stops add `summary` and `textarea`, and keep only visible ones (`n.getClientRects().length > 0`).
- [ ] **Step 4: Run the full suite.** With the keyboard only:
  1. change the Load map type;
  2. filter;
  3. open an item;
  4. Tab to `Show file change` and open it;
  5. Cancel;
  6. switch the Discover tabs.

  Expected: focus stays visible and never drops to the page body.
- [ ] **Step 5: Commit.** `git commit -m "page: keep keyboard focus through tabs, filters and review"`

## Phase 3: Interaction polish

### Task 10: No artificial waits; one motion per drawer

**Files:**
- Modify: `src/kitden/web/static/js/panel.js` (`applyChange` `:592-597`, `shake` `:523-525` and its calls `:518`, `:584`, `swapLabel` `:527-530`, the diff `--i` `:456`)
- Modify: `src/kitden/web/static/style.css` (`--t-panel` `:37`, the drawer stagger `:382-385`, the diff lines `:424-425`, `.socket .swap` `:200`)
- Modify: `docs/design.md` (motion tokens and patterns)
- Test: `tests/unit/test_page_words.py`

- [ ] **Step 1: Write the failing page-words test.**

```python
def test_apply_waits_for_work_not_for_a_timer():
    panel, css = script("panel.js"), (STATIC / "style.css").read_text()
    assert "520 - (performance.now()" not in panel and "wait(450)" not in panel
    assert "shake(" not in panel
    assert ".drawer.open .body > *:nth-child(2)" not in css and "line-in" not in css
    assert "--t-panel: 240ms" in css
    assert ".socket .swap { opacity: 0; }" in css
```

- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - After `verified`: mark the button done, reload, close the review, toast with the check. Nothing waits on a timer.
  - An error keeps its callout and moves focus to the Apply button; there is no shake.
  - The drawer body and the diff appear at once; the drawer slides in 240 ms.
  - The socket word swap fades without blur.
  - `busy.change` alone guards double submits.
- [ ] **Step 4: Update `docs/design.md`.**
  - The tokens table: `--t-panel` becomes 240 ms. Drop Error shake and diff Stagger. Success becomes "check draws 320 ms, never delays the next action".
  - Keep `test_apply_turns_green_only_after_verified_and_only_ok_toasts_get_a_check` and `test_reduced_motion_turns_every_animation_off` passing.
- [ ] **Step 5: Run the full suite.** Expected: pass.
- [ ] **Step 6: Commit.** `git commit -m "motion: no forced waits after Apply; one motion per drawer"`

### Task 11: Readable success label and comfortable hit areas

**Files:**
- Modify: `src/kitden/web/static/style.css` (tokens; `.btn.primary.done` `:133`; any control under 24 px)
- Create: `tests/unit/test_contrast.py`

**Interfaces:**
- Produces: the tokens `--success` and `--on-success` in light and dark. `.btn.primary.done` uses them. The `--lamp-on` sockets stay as they are.

- [ ] **Step 1: Write the failing contrast test.** Read the light tokens from `:root` and the dark ones from `:root[data-theme="dark"]` (dark falls back to light), using WCAG relative luminance:

```python
def test_success_and_action_labels_are_readable_in_both_themes():
    for theme in (LIGHT, DARK):
        assert contrast(theme["--on-success"], theme["--success"]) >= 4.5
        assert contrast(theme["--on-action"], theme["--action"]) >= 4.5
    assert ".btn.primary.done, .btn.primary.done:hover { background: var(--success); color: var(--on-success); }" in CSS
```

- [ ] **Step 2: Run it.** `uv run pytest -q tests/unit/test_contrast.py`. Expected: FAIL (`--success` is missing).
- [ ] **Step 3: Pick values that pass.** Keep the green family: a darker green in light with white text, and the dark theme's `#47c27a` with near-black text.
- [ ] **Step 4: Measure the hit areas.** On the sandbox preview, run this in the page on Overview, Load map, Discover, Gateway, Changes and an open review:

```js
[...document.querySelectorAll('button, select, input, summary, [role=tab], a[href]:not(p a):not(li a)')]
  .filter((n) => n.getClientRects().length)
  .map((n) => [n.textContent.trim().slice(0, 30) || n.getAttribute('aria-label'), n.getBoundingClientRect()])
  .filter(([, r]) => r.width < 24 || r.height < 24)
```

  Expected before: some offenders (for example `.btn.small`, the switch). Fix them with height or padding; the switch may use a larger hit area around the same visual size.
- [ ] **Step 5: Re-run the script and the full suite.** Expected: the script returns `[]` and everything passes.
- [ ] **Step 6: Commit.** `git commit -m "style: readable success label; controls at least 24 px"`

### Task 12: Final check (verification subagent)

**Files:** none changed. A read-only subagent on a sandbox home: `make_home` with Claude Code, Codex and Cursor, `add_marketplaces`, a fake Obot from `tests/unit/fake_obot.py`, and the `FakeCli` from `tests/unit/test_api_plugin_install.py`.

- [ ] **Step 1: Run every command from the Global Constraints.** Expected: all pass.
- [ ] **Step 2: Lost answer.** Patch `window.fetch` so the first `/apply` request reaches the server, then throws. Expected: the page shows the verified result after reading it back, and never a "nothing changed" claim.
- [ ] **Step 3: Failed project read.** Patch fetch so `/api/map?project=<id>` fails, then pick that project. Expected: an error banner, no old rows under the new project's name, and `Scanned` unchanged with "could not refresh".
- [ ] **Step 4: Add flow.** Add a Claude Code plugin with Cursor present. Expected: the Add form and the review both say Cursor loads it too. Two same-name plugins can be told apart from their rows.
- [ ] **Step 5: Gateway.** On the item panel of a remote direct server, Move is the first action. Overview lists it under Can improve, not under attention.
- [ ] **Step 6: Keyboard and reduced motion.** Do Task 9's keyboard walk. With reduced motion emulated, Apply returns control at once and every word stays readable.
- [ ] **Step 7: Report.** Write pass or fail per step, with the evidence, in simple Russian to the owner. Do not fix anything in this task.
