# Part 1: Truth on the page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The page and the docs say only what the code does: Overview knows the Kitden gateway, an Add says its scope before the click, useless notes stay out, the gateway says what it governs, and the Gateway page stays short.

**Architecture:** Small changes in the existing view models (`src/kitden/views/overview.py`, `findings.py`, `after.py`) and the page modules (`overview.js`, `library.js`, `gateway.js`), each with a unit test or a node test, plus word fixes in `security.py`, `README.md` and `docs/development.md`. No new module.

**Tech Stack:** Python 3.13, Starlette; plain ES modules; pytest; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-21-review-follow-up-design.md`, Part 1 (1.1 to 1.6). Master plan: `docs/superpowers/plans/2026-10-21-review-follow-up.md`.

## Global Constraints

- Code, comments, UI text and docs in simple English, short and plain (`AGENTS.md`).
- Main pages show a name, the client and an action; paths, addresses and commands stay in Details.
- Every client-settings change goes through preview → Apply with a backup → verify → Undo; this part changes no client file.
- `docs/design.md` rules: new page text is tested in `tests/unit/test_page_words.py`; page logic is a pure exported function tested with `node --test tests/frontend/*.test.mjs`; a quiet line is `el("p", "group-note", …)` or `el("p", "muted", …)`, never a warning.
- Tests use sandbox homes from `tests/conftest.py` (`make_home`, `write_cursor_fixture_state`, `no_version`); secrets in fixtures are `SENTINEL_SECRET_*`.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `node --test tests/frontend/*.test.mjs`.
- Commit messages: a short plain subject, one to three lines, no prefix.
- No new runtime dependency.

## Review Focus

1. The Kitden gateway's settings file is there but broken: Overview must say "Kitden could not read the gateway settings." and not "No gateway yet." (Task 1 test `test_overview_says_when_the_gateway_settings_are_unreadable`).
2. A client with the old `agentsetup` entry is neither connected nor offered "Set up in …": its fix is the existing "Old Kitden entry" card (Task 1 test `test_an_old_entry_is_not_connected_and_gets_no_set_up_button`).
3. A project is picked but the table is empty: the scope line is not shown (Task 2 test `the scope line needs rows`).
4. A server that the gateway holds and that one client also has as a direct entry: the direct entries still get their cross-client note; only the gateway items are skipped (Task 3 test `test_direct_entries_beside_a_held_server_keep_their_note`).
5. A group with exactly six rows shows no "Show all"; with seven it shows six and "Show all 7"; "Show all" survives a redraw of the page (Task 6 tests in `tests/frontend/gateway.test.mjs`).

---

### Task 1: Overview knows the Kitden gateway (1.1)

**Files:**
- Modify: `src/kitden/views/overview.py:124-173` (`overview()`)
- Modify: `src/kitden/web/app.py:615-616` (`_overview`)
- Modify: `src/kitden/web/static/js/overview.js:63-64` and `229-235` (`gatewayCard`)
- Create: `tests/frontend/overview.test.mjs`
- Test: `tests/unit/test_overview.py`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `held_servers(settings, chain) -> list[dict]` (`src/kitden/local_gateway/views.py:87`), `settings_unreadable(home)` and `load_settings(home)` (`settings.py`), `setup_server_state(inventory) -> list[dict]` with `state` in `added`, `plugin`, `old`, `missing` and `client` (`src/kitden/views/setup_server.py:55`), `gateway_view(inventory, gateways, project, kitden=…)["groups"]` (`gateway_view.py`).
- Produces: `overview(inventory, gateways, project, held: list[dict] | None = None, problem: str | None = None) -> dict` whose `gateway` is `None`, or `{"kind": "kitden", "name": "Kitden gateway", "servers": int, "clients": list[str], "lacking": list[str], "problem": str | None}`, or the registered gateway's `{"name": …}` as today; `suggestions[0]["title"]` is `"N MCP servers can move into the Kitden gateway"` when `held` is not None. Exported from `overview.js`: `gatewayCardWords(gateway) -> {title: str, line: str, action: str | null}`.

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_overview.py`, replace `test_gateway_card_only_with_a_registered_gateway` with:

```python
def test_the_kitden_gateway_card_names_servers_and_clients(home):
    # claude_code and cursor have the kitden entry; codex does not (see test_setup_server.py for
    # how the fixture gets the entry: add {"command": "kitden", "args": ["mcp"]} as "kitden").
    inventory = build_inventory(home)
    held = [{"name": "github", "kind": "local", "state": "on", "differs": False}]
    data = overview(inventory, [], None, held=held)
    assert data["gateway"] == {
        "kind": "kitden", "name": "Kitden gateway", "servers": 1,
        "clients": ["claude_code", "cursor"], "lacking": ["codex"], "problem": None,
    }
    assert data["suggestions"][0]["title"].endswith("can move into the Kitden gateway")


def test_without_held_servers_or_connected_clients_there_is_no_gateway(home):
    data = overview(build_inventory(home), [], None, held=[])
    assert data["gateway"] is None  # no client has the entry in the plain fixture
    assert data["suggestions"] == []


def test_overview_says_when_the_gateway_settings_are_unreadable(home):
    data = overview(build_inventory(home), [], None, held=[], problem="Kitden could not read the gateway settings.")
    assert data["gateway"]["problem"] == "Kitden could not read the gateway settings."


def test_an_old_entry_is_not_connected_and_gets_no_set_up_button(home):
    # give codex the old agentsetup entry (see is_old_entry in views/setup_server.py)
    ...
    data = overview(inventory, [], None, held=[])
    assert "codex" not in data["gateway"]["clients"]
    assert "codex" not in data["gateway"]["lacking"]


def test_a_registered_gateway_still_gets_its_card_without_the_kitden_one(home):
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp")
    mark_gateways(inventory, [gateway])
    data = overview(inventory, [gateway], None, held=[])
    assert data["gateway"] == {"name": "mcp.neon.tech"}
    assert [s["title"] for s in data["suggestions"]] == ["2 MCP servers can move into the gateway"]
```

In `tests/frontend/overview.test.mjs` (new; import like `panel.test.mjs` does):

```js
test('the Kitden gateway card says servers, clients and the client to set up', () => {
  const words = gatewayCardWords({ kind: 'kitden', name: 'Kitden gateway', servers: 2, clients: ['claude_code', 'cursor'], lacking: ['codex'], problem: null });
  assert.equal(words.title, 'Kitden gateway');
  assert.equal(words.line, '2 servers · Claude Code, Cursor');
  assert.equal(words.action, 'Set up in Codex…');
});
test('without a gateway the card offers Set up', () => {
  assert.deepEqual(gatewayCardWords(null), { title: 'Gateway', line: 'No gateway yet.', action: 'Set up' });
});
test('an unreadable settings file is said on the card', () => {
  assert.equal(gatewayCardWords({ kind: 'kitden', name: 'Kitden gateway', servers: 0, clients: [], lacking: [], problem: 'Kitden could not read the gateway settings.' }).line, 'Kitden could not read the gateway settings.');
});
```

In `tests/unit/test_page_words.py` add `test_overview_offers_set_up_only_without_a_gateway`: `overview.js` contains `"No gateway yet."` exactly once and `gatewayCardWords`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/unit/test_overview.py -v` and `node --test tests/frontend/overview.test.mjs`
Expected: FAIL: `overview()` has no `held` parameter; `gatewayCardWords` is not exported.

- [ ] **Step 3: Implement `overview(inventory, gateways, project, held=None, problem=None)` in `src/kitden/views/overview.py`**

Connected clients: `[s["client"] for s in setup_server_state(inventory) if s["state"] in ("added", "plugin")]`; lacking: found clients (`found_clients(inventory)`, without the Desktop tab) that are neither connected nor `old`. The Kitden card exists when `held is not None` and (`held` or connected or `problem`). The move count comes from `gateway_view(inventory, gateways, project, kitden=held)["groups"]`, rows of `move` plus `local`, each server once. Keep the registered-gateway branch as it is for the case without a Kitden card.

- [ ] **Step 4: Pass `held` and `problem` from `_overview` in `src/kitden/web/app.py:615-616`**

Reuse the two lines `_gateway_view` computes (`held_servers(load_settings(home), _chain(path))`, `UNREADABLE if settings_unreadable(home) else None`); move them into a small helper `_kitden(path) -> tuple[list[dict] | None, str | None]` used by both routes.

- [ ] **Step 5: Implement `gatewayCardWords(gateway)` in `overview.js` and draw the card from it**

The card is always drawn (replace the `if (!model.gateway)` at line 64). Its button: for `action === 'Set up'`, `go("gateway")` as today; for `'Set up in <client>…'`, the same call the Gateway page's `kitdenCard` makes for its "Set up in …" button (read `gateway.js:255-280` and call the same function). `line` uses `CLIENT_NAMES` from `parts.js` and `plural` for servers.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/unit/test_overview.py tests/unit/test_page_words.py -v` and `node --test tests/frontend/overview.test.mjs`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/kitden/views/overview.py src/kitden/web/app.py src/kitden/web/static/js/overview.js tests/unit/test_overview.py tests/unit/test_page_words.py tests/frontend/overview.test.mjs
git commit -m "Overview: know the Kitden gateway"
```

---

### Task 2: An Add says its scope before the click (1.2)

**Files:**
- Modify: `src/kitden/web/static/js/library.js:75-80` (`addName`), `253-328` (`renderLibrary`, where the table scroller is appended at line 309)
- Test: `tests/frontend/library.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: `export function addName(row, client, add, project)`; `export function scopeLine(project, rows) -> string | null` returning `"Adding puts an item in all your projects."` when `project` is set and `rows.length > 0`, else `null`.

- [ ] **Step 1: Write the failing tests** in `tests/frontend/library.test.mjs`

```js
test('an Add names its scope when a project is picked', () => {
  const row = { name: 'brandkit', kind: 'skill' };
  assert.ok(addName(row, 'codex', { label: '+ Add' }, 'p1').endsWith(' for all projects'));
  assert.ok(!addName(row, 'codex', { label: '+ Add' }, null).endsWith(' for all projects'));
});
test('the scope line needs a project and rows', () => {
  assert.equal(scopeLine('p1', [{}]), 'Adding puts an item in all your projects.');
  assert.equal(scopeLine('p1', []), null);
  assert.equal(scopeLine(null, [{}]), null);
});
```

In `test_page_words.py`: `test_library_says_the_add_scope_in_a_project`: `library.js` contains `"Adding puts an item in all your projects."`.

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/frontend/library.test.mjs`
Expected: FAIL: `addName` and `scopeLine` are not exported.

- [ ] **Step 3: Implement**

Export `addName` with the fourth parameter; `cellNode` (line 82-86) passes `state.project`. Add `scopeLine` and, in `renderLibrary`, append `el("p", "group-note", line)` right before the table scroller when it is not null. Part 3's Task "Add into one project" replaces this line when a project place exists; keep it a single function so that is one edit.

- [ ] **Step 4: Run the tests**

Run: `node --test tests/frontend/library.test.mjs` and `uv run pytest tests/unit/test_page_words.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/library.js tests/frontend/library.test.mjs tests/unit/test_page_words.py
git commit -m "Library: say the scope of an Add before the click"
```

---

### Task 3: Notes that help nobody stay out (1.3)

**Files:**
- Modify: `src/kitden/views/findings.py:112-114` (where `own[...]` is filled) and the imports
- Test: `tests/unit/test_findings.py`

**Interfaces:**
- Consumes: `is_own_entry(item) -> bool` (`src/kitden/views/setup_server.py:38`), `KITDEN_GATEWAY` (already imported), `gateway_items(inventory, settings, home)` (`src/kitden/local_gateway/views.py:32`) to make held items in a test.

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_findings.py`

```python
def test_kitden_entries_make_no_cross_client_note(home):
    # put a "kitden" entry ({"command": "kitden", "args": ["mcp"]}) into .claude.json and
    # .cursor/mcp.json of the sandbox home, then:
    inventory = build_inventory(home)
    names = [f.names for f in find_findings(inventory) if f.type is FindingType.SAME_IN_OTHER_CLIENTS]
    assert all("kitden" not in n for n in names)


def test_held_servers_make_no_cross_client_note(home):
    # the kitden entry in two clients plus gateway.json holding "github" (write it with
    # settings_step or json.dumps under data_dir(home)); append gateway_items(...) to inventory.items
    ...
    assert all("github" not in n for n in names)


def test_direct_entries_beside_a_held_server_keep_their_note(home):
    # as above, and a direct "github" entry in .claude.json and .codex/config.toml too
    ...
    assert any(n == ("github", "github") for n in names)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_findings.py -v -k "cross_client_note or keep_their_note"`
Expected: the first two FAIL (a note names kitden / github).

- [ ] **Step 3: Implement**

At `findings.py:112-114`, before `own[(item.kind, item.name)][client] = item`, skip the item when `is_own_entry(item) or item.via_gateway == KITDEN_GATEWAY`. Import `is_own_entry` from `kitden.views.setup_server`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/test_findings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/kitden/views/findings.py tests/unit/test_findings.py
git commit -m "Findings: no cross-client note for Kitden's own entries"
```

---

### Task 4: Words match the code (1.4)

**Files:**
- Modify: `src/kitden/web/security.py:1-10` (the module docstring, line 4)
- Modify: `README.md` ("Why you want it", last paragraph; "Let your agents ask")
- Modify: `src/kitden/views/after.py:197-275` (`_kitden_move_words`)
- Create: `tests/unit/test_docs_words.py`
- Test: `tests/unit/test_after.py`

**Interfaces:**
- Consumes: the move change made by `local_move_steps` (`tests/unit/test_local_gateway_move.py` shows how to build one on a sandbox home with a remote entry).

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_docs_words.py`:

```python
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_the_start_link_is_not_called_one_time():
    text = (ROOT / "src/kitden/web/security.py").read_text()
    assert "one-time" not in text and "The link works while the page runs" in text


def test_readme_says_where_secrets_go_and_what_the_agents_server_does():
    readme = (ROOT / "README.md").read_text()
    assert "Secrets stay on this Mac and go only to the server they belong to." in readme
    assert "Servers moved into the gateway add their tools, which do what those servers do." in readme
```

`tests/unit/test_after.py`:

```python
def test_a_remote_move_says_kitden_asked_the_server_once(home, monkeypatch):
    # a remote entry "linear" in .claude.json; monkeypatch kitden.changes.actions.needs_sign_in to return False
    ...
    note = after_words(change, inventory, home=home)[0]["note"]
    assert "Kitden asked linear once whether it needs a sign-in." in note


def test_an_update_move_names_the_kept_switches(home, monkeypatch):
    # gateway.json already holds "linear" with a rule; move it again from a client whose own
    # switch for it is off (a Claude Code deny rule in ~/.claude/settings.json)
    ...
    assert "keeps its" in note and "do not carry over" in note
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_docs_words.py tests/unit/test_after.py -v`
Expected: FAIL on the three new assertions (the update-move test may already pass; keep it).

- [ ] **Step 3: Change the words**

`security.py` line 4: "A start link with a random token sets an HttpOnly, SameSite=Strict session cookie. The link works while the page runs; `kitden open` reuses it." README: add the two sentences in the named places. `after.py` `_kitden_move_words`: for every moved server with a `url`, one sentence "Kitden asked <name> once whether it needs a sign-in." in the note, before "Applies to new sessions." For the update case, read lines 258-275 and make sure the note has the sentence the test asserts; if it does, leave it.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/test_docs_words.py tests/unit/test_after.py tests/unit/test_local_gateway_views.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/security.py README.md src/kitden/views/after.py tests/unit/test_docs_words.py tests/unit/test_after.py
git commit -m "Words: the start link, the agents server, where secrets go"
```

---

### Task 5: The gateway says what it governs (1.5)

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js:255-280` (`kitdenCard`)
- Test: `tests/unit/test_page_words.py`

- [ ] **Step 1: Write the failing test**

```python
def test_the_kitden_card_says_what_the_gateway_governs():
    text = script("gateway.js")
    assert "The gateway controls only the servers in it. Direct entries and terminal tools are outside it." in text
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/unit/test_page_words.py::test_the_kitden_card_says_what_the_gateway_governs -v`
Expected: FAIL

- [ ] **Step 3: Implement**

In `kitdenCard`, after `kitdenHeld(gateway)`, append `el("p", "group-note", "The gateway controls only the servers in it. Direct entries and terminal tools are outside it.")`.

- [ ] **Step 4: Run the test**

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/gateway.js tests/unit/test_page_words.py
git commit -m "Gateway: say what the gateway governs"
```

---

### Task 6: The Gateway page stays short (1.6)

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js:105-131` (the group loop) and the `draft` object near the top of the file
- Test: `tests/frontend/gateway.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: `export function visibleRows(rows, expanded, limit = 6) -> {shown: array, cut: number}` where `cut` is the number of hidden rows (0 when none).

- [ ] **Step 1: Write the failing tests** in `tests/frontend/gateway.test.mjs`

```js
test('a group shows six rows and says how many more there are', () => {
  const rows = Array.from({ length: 7 }, (_, i) => ({ name: `s${i}` }));
  assert.deepEqual(visibleRows(rows, false), { shown: rows.slice(0, 6), cut: 1 });
  assert.deepEqual(visibleRows(rows.slice(0, 6), false), { shown: rows.slice(0, 6), cut: 0 });
  assert.deepEqual(visibleRows(rows, true), { shown: rows, cut: 0 });
});
```

In `test_page_words.py`: `test_gateway_groups_fold`: `gateway.js` contains `"Show all "` and `draft.expanded`.

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/frontend/gateway.test.mjs`
Expected: FAIL: `visibleRows` is not exported.

- [ ] **Step 3: Implement**

`draft.expanded = {}` (per group key, kept across redraws like `draft.addOpen`). In the group loop: `const { shown, cut } = visibleRows(rows, draft.expanded[key])`; draw `shown`; when `cut > 0`, append `button(\`Show all ${rows.length}\`, …, "btn small ghost")` that sets `draft.expanded[key] = true` and redraws the place. "Move all" stays in the group head and counts every row, not only the shown ones.

- [ ] **Step 4: Run the tests**

Run: `node --test tests/frontend/gateway.test.mjs` and `uv run pytest tests/unit/test_page_words.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/gateway.js tests/frontend/gateway.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: fold long groups"
```

---

### Task 7: Docs and roadmap for Part 1

**Files:**
- Modify: `README.md` (Overview paragraph: the gateway card; Library paragraph: the scope line; Gateway paragraph: what it governs)
- Modify: `ROADMAP.md` ("### Not released yet": one line per shipped item of this part; remove the "## Under review" section)

- [ ] **Step 1: Write the README lines** in the three paragraphs, one sentence each, plain.
- [ ] **Step 2: Update ROADMAP.md** and remove "## Under review".
- [ ] **Step 3: Run all checks**

Run: `uv run pytest -q && uv run ruff check . && node --test tests/frontend/*.test.mjs`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add README.md ROADMAP.md
git commit -m "Docs: Part 1 of the review follow-up"
```
