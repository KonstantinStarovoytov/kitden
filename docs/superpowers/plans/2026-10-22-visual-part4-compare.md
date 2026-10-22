# Part 4: Compare, differences you can act on — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Library shows only the rows where the clients differ, says which projects change an all-projects item, and Add missing sorts what it finds into four honest groups.

**Architecture:** The Differences filter is a fourth `show` value (`show=diff`) that the server applies with one pure rule over the shown cells, so the address, the cache key and the tab counts follow it for free. Project exceptions come from one new function in `views/load_map.py` that compares each project's effective view with the all-projects one; the Library rows carry them, and the preview of a change to an all-projects item uses them for one note. Add missing keeps its loop in `changes/align.py` and splits its answer into `will_add`, `already`, `decide` and `cannot`; the review in `review.js` (Part 3 split `panel.js` into `panel.js`, `details.js`, `tools.js` and `review.js`) draws them in that order.

**Tech Stack:** Python 3.13, Starlette; plain ES modules and one CSS file; pytest on sandbox homes and the Part 1 samples; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-22-visual-management-design.md`, Part 4 (4.1, 4.2, 4.3), built on concept §4 and §6 of `docs/research/visual-management-ux-concept-2026-10-22.md`. Master plan: `docs/superpowers/plans/2026-10-22-visual-management.md` (fixed names: Library hash `show=diff`; align answer groups `will_add`, `already`, `decide`, `cannot`).

## Global Constraints

- `AGENTS.md` in full: simple English in code, comments, UI and docs; every write goes through preview → Apply with a backup → verify → Undo (`changes/engine.py`); tests on sandbox homes only.
- Main pages show a name, the client, a state and an action. "2 project exceptions" is a count only; project names and paths stay in Details.
- "Unknown or stale information never shows as absent or as a guarantee"; "a same-name item from another source never looks equal" (spec Goals, Acceptance).
- `docs/design.md` governs look and motion. A task that changes page words changes their pin in `tests/unit/test_page_words.py` and `docs/design.md` in the same commit (master Rules).
- `explain()` and `project_views()` feed the read-only MCP server. This part does not change them: exceptions are computed in `library()` and in the preview only.
- No slower start: exceptions ride on `/api/library` only, never on `/api/map` or `/api/overview`.
- Tests: `make_home(...)` and `write_cursor_fixture_state(home)` from `tests/conftest.py`, or `build_demo_home(root, size)` (Part 1). Never the real home, a real client command, a real MCP server, the Keychain or the network. Sample facts are Part 1's "Sample contract": the override is `docs` in `~/work/atlas`; `docs` is one name from two sources (Claude Code, Codex); `superpowers@demo-market` is off in `~/work/website`; Add missing runs in `~/work/atlas`.
- Page code after Part 3: Details functions live in `details.js`, review functions in `review.js`; new node tests go in `tests/frontend/details.test.mjs` or `review.test.mjs`, while the existing tests in `panel.test.mjs` are edited where they are.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`. All pass or the commit waits.
- Commits stage files by name (never `git add -A`, `.` or `-a`); a short plain subject, one to three simple lines, no prefix, ending with the co-author line the session gives.
- `ROADMAP.md`: while `git status` shows it modified by the owner, no task edits or stages it; Task 8 puts the lines in its report.

## Review Focus

1. **An add into a file Kitden could not read**: Add missing lists it under "Kitden cannot add" with Part 2's reason and the review still opens; today the whole preview fails. The test breaks Cursor's `~/.cursor/mcp.json`, because Add missing puts MCP entries in all projects, so the sample's own unreadable file (`~/work/website/.cursor/mcp.json`, a project file) is never an add's target. Only adds into the broken file are held (owner ruling): in `website`, Cursor's adds into the readable `~/.cursor/mcp.json` stay. Task 6, `test_an_add_into_a_file_kitden_could_not_read_cannot_be_added`, `test_a_broken_project_file_holds_only_the_adds_into_it`.
2. **Unknown cells and cells kept from the last good read** (a source or client Kitden could not read, now or since its last good read): Differences always keeps those rows, never treats them as equal, even when the kept states match (owner ruling); hiding that column compares the others. Task 1, `test_rows_differ_by_state_class_unknown_and_needs_review` and `test_differences_keep_rows_whose_shown_clients_differ`.
3. **One name from two sources and a third client that lacks it:** it is under "Needs your decision", and the third client's add starts unchecked with a note, so nothing is added silently. Task 6, `test_a_name_with_two_sources_is_a_decision_and_never_checked`.
4. **A project that turns an all-projects item off or overrides it:** the row counts it, Details names it, and removing the all-projects item says the project keeps its own and leaves the project's entry as it was. Tasks 3 and 5, `test_all_projects_rows_carry_their_project_exceptions` and `test_removing_an_all_projects_server_keeps_the_project_override`.
5. **The `large` sample:** Differences and exceptions add no wait a person notices (under 50 ms and 100 ms). Tasks 1 and 3, `test_differences_stay_fast_on_the_large_sample` and `test_project_exceptions_stay_fast_on_the_large_sample`.

---

### Task 1: Differences on the server (4.1)

**Files:**
- Modify: `src/kitden/views/library.py` (`SHOWS` near line 29; `_chosen` near 546; `library()` near 593: `show_for`, `more`, the docstring; a new `differs`)
- Test: `tests/unit/test_library.py`, `tests/unit/test_compare.py` (create)

**Interfaces:**
- Consumes: Part 1 `kitden.demo.build_demo_home(root: Path, size: str) -> Path`; Part 2 cell state `"review"` (Needs review), the Unknown cells of a source or client Kitden could not read (`"unk"`), and the Library cell's `stale_at` (a cell kept from the last good read).
- Produces: `SHOWS = ("mine", "new", "all", "diff")` (so `web/app.py _library` accepts `show=diff` with no change of its own). `differs(row: dict, columns: list[str]) -> bool`. `library(..., show="diff")` keeps the rows `differs` keeps on every tab, the tab counts follow it, and `more` is 0.

The rule (spec 4.1: "one Loads and one —, Off vs Loads, Needs review, Unknown"). Each shown cell's `state` falls in a class:

| Class | States |
| --- | --- |
| has | `on` (Loads, "Has it", "via Claude Code"), `gw` (Via gateway), `done` (Has its skills) |
| off | `off` |
| lacks | `none` (—, "+ Add", a reason), `via` (Via Claude Code: not there yet), `missing` |

A row differs when two or more columns are shown and either any shown cell is `unk` or `review`, or any shown cell has `stale_at` (kept from the last good read), or the shown cells are not all in one class. A state not in the table is its own class.

- Owner ruling (2026-10-22): a cell kept from the last good read counts as a difference, as Unknown does; Differences never hides a row only because its kept cells match.

- Builder call: compare the shown columns (found minus hidden), not every found client; with fewer than two shown, no row differs.
- Builder call: a gateway route against a direct one (`gw` vs `on`) is not a difference; routes are the Gateway page's question (Part 5).
- Builder call: the filter sits in `_chosen` (which the tab counts use), not `_narrowed`, so each tab's count says how many rows differ there.
- Builder call: one rule on every tab, Instructions included: a CLAUDE.md only Claude Code reads is a real difference (Codex does not see those rules).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_library.py
def test_rows_differ_by_state_class_unknown_and_needs_review():
    def row(**states):
        return {"cells": {c: _cell(state) for c, state in states.items()}}

    two = ["claude_code", "codex"]
    assert differs(row(claude_code="on", codex="none"), two)
    assert differs(row(claude_code="on", codex="off"), two)
    assert differs(row(claude_code="off", codex="none"), two)
    assert differs(row(claude_code="on", codex="unk"), two)
    assert differs(row(claude_code="unk", codex="unk"), two)
    assert differs(row(claude_code="review", codex="on"), two)
    assert not differs(row(claude_code="on", codex="gw"), two)
    assert not differs(row(claude_code="on", codex="done"), two)
    assert not differs(row(claude_code="none", codex="via"), two)
    assert not differs(row(claude_code="off", codex="off"), two)
    # A cell kept from the last good read differs, even when its state matches.
    kept = row(claude_code="on", codex="on", cursor="on")
    kept["cells"]["claude_code"]["stale_at"] = "2026-10-22T14:02:00+00:00"
    assert differs(kept, two)
    assert not differs(kept, ["codex", "cursor"])  # its column hidden: the others are compared
    # Only the shown columns count; one shown column has nothing to compare.
    shown = ["claude_code", "cursor"]
    assert not differs(row(claude_code="on", codex="none", cursor="on"), shown)
    assert not differs(row(claude_code="on", codex="unk"), ["claude_code"])
```

```python
# tests/unit/test_compare.py (new): Part 4 on the Part 1 samples.
@pytest.fixture
def medium(tmp_path):
    return build_demo_home(tmp_path, "medium")


def _library(home, kind="mcp_server", project=None, **options):
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}
    return library(inventory, adapters, project, gateway_registered=False, kind=kind, **options)


def _server(home, name, clients, url):
    """An http MCP entry with the same address in each named client (add_claude, add_codex,
    add_cursor from test_local_gateway_move; ~/.cursor/mcp.json is made when missing)."""


def test_differences_keep_rows_whose_shown_clients_differ(medium):
    _server(medium, "kd-only-claude", ["claude_code"], "https://one.invalid/mcp")
    _server(medium, "kd-everywhere", ["claude_code", "codex", "cursor"], "https://same.invalid/mcp")
    diff = _library(medium, show="diff")
    names = {r["name"] for r in diff["rows"]}
    assert "kd-only-claude" in names and "kd-everywhere" not in names
    shown = [c["id"] for c in diff["columns"] if not c["hidden"]]
    assert all(differs(r, shown) for r in diff["rows"])
    assert names <= {r["name"] for r in _library(medium, show="mine")["rows"]}
    assert diff["counts"]["mcp_server"] == len(diff["rows"]) and diff["more"] == 0
    # With one shown column there is nothing to compare.
    alone = _library(medium, show="diff", hidden=frozenset({"codex", "cursor"}))
    assert alone["rows"] == []


def test_differences_cover_every_tab_with_one_rule(medium):
    # Part 1's medium sample has ~/.claude/CLAUDE.md.
    rows = _library(medium, "instructions", show="diff")["rows"]
    assert "CLAUDE.md" in {r["name"] for r in rows}  # only Claude Code reads it
    # Tabs without a catalog keep Differences; New and All fall back to Installed there.
    assert _library(medium, "hook", show="new")["rows"] == _library(medium, "hook")["rows"]


def test_the_library_api_takes_show_diff(medium):
    with served(medium) as page:
        answer = page.get("/api/library?kind=mcp_server&show=diff").json()
        shown = [c["id"] for c in answer["columns"] if not c["hidden"]]
        assert all(differs(r, shown) for r in answer["rows"])
        assert page.get("/api/library?kind=mcp_server&show=nope").status_code == 200


def test_differences_stay_fast_on_the_large_sample(tmp_path):
    home = build_demo_home(tmp_path, "large")
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}

    def best(show):
        def run():
            library(inventory, adapters, None, gateway_registered=False, kind="mcp_server", show=show)

        run()  # the catalogs are read once
        return min(timeit.timeit(run, number=1) for _ in range(3))

    assert best("diff") - best("mine") < 0.05
```

`served(home)` is a context manager in `test_compare.py` that serves `create_app(demo_build(home), token="tok", port=47800, home=home, demo=True)` through a `TestClient` with base URL `http://127.0.0.1:47800` after `GET /?token=tok`, as `page_for` in `test_local_gateway_views.py` does. Part 1's `demo_page(root, size)` (`tests/unit/test_demo_mode.py`) builds a fresh sample; these tests change the sample first, so they serve the home they changed. `demo_build` runs no client command, and demo mode keeps held servers from starting.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_library.py::test_rows_differ_by_state_class_unknown_and_needs_review tests/unit/test_compare.py -v`
Expected: FAIL with `ImportError: cannot import name 'differs'`.

- [ ] **Step 3: Implement** `differs(row: dict, columns: list[str]) -> bool` with the class table as a module constant (`CELL_CLASS`), `("unk", "review")` as the states that always differ, and a shown cell with `stale_at` that always differs. `_chosen(rows, kind, show, q, visible)` keeps `differs(r, visible)` rows when `show == "diff"`. In `library()`: `show_for(k)` returns `show` on catalog tabs and `"diff"` or `"mine"` on the others; `more` is computed only for `show in ("mine", "new")`; the docstring names Differences.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/test_library.py tests/unit/test_compare.py tests/unit/test_api_views.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/views/library.py tests/unit/test_library.py tests/unit/test_compare.py
git commit -m "Library: a Differences filter on the server" -m "It keeps rows whose shown clients differ, Unknown and Needs review included."
```

---

### Task 2: Differences on the page (4.1)

**Files:**
- Modify: `src/kitden/web/static/js/store.js` (`SHOWS` line 9; the comment on line 2)
- Modify: `src/kitden/web/static/js/library.js` (`SHOW` line 21; `asking()` near 169; `toolbar()` near 410; `emptyState()` near 520)
- Modify: `docs/design.md` (Library table: a "Show choice" row; Motion "Ready, then swap" row)
- Test: `tests/frontend/library.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 1 (`show=diff` on `/api/library`); Part 2's hash (`sel=`) stays as Part 2 left it.
- Produces: `SHOWS = ["mine", "new", "all", "diff"]` in `store.js`; `export function showChoices(kind: string): [string, string][]` in `library.js`: on Plugins and Skills `[["mine", "Installed"], ["new", "New"], ["all", "All"], ["diff", "Differences"]]`, on every other tab `[["mine", "Installed"], ["diff", "Differences"]]`.

- Builder call: the other tabs get the same group with two choices ("Installed | Differences"), so one word means one thing everywhere.
- Builder call: no "N more" line under Differences; an empty list says `No differences in <kind>` with a "Show installed" button.

- [ ] **Step 1: Write the failing tests**

```js
// tests/frontend/library.test.mjs
test('Differences is in the address and on every tab', () => {
  const hash = '#library?kind=mcp_server&show=diff&project=p1';
  assert.equal(parseHash(hash).show, 'diff');
  assert.equal(hashFor(parseHash(hash)), hash);
  assert.deepEqual(showChoices('plugin').map(([id]) => id), ['mine', 'new', 'all', 'diff']);
  assert.deepEqual(showChoices('mcp_server'), [['mine', 'Installed'], ['diff', 'Differences']]);
  assert.deepEqual(showChoices('instructions'), showChoices('hook'));
});

test('a tab without a catalog asks for Differences, not New', () => {
  Object.assign(state, { view: 'overview', kind: 'mcp_server', show: 'mine', category: '', attention: false, project: '', q: '' });
  freshness.reloadStartedAt = performance.now();
  requests.length = 0;
  loadLibraryFor({ kind: 'hook', show: 'diff', category: '', attention: false, q: '' });
  loadLibraryFor({ kind: 'marketplace', show: 'new', category: '', attention: false, q: '' });
  assert.match(requests[0].url, /^\/api\/library\?kind=hook&show=diff$/);
  assert.match(requests[1].url, /^\/api\/library\?kind=marketplace&show=mine$/);
});

test('an empty Differences list says so and offers Installed', () => {
  const box = emptyState({ kind: 'mcp_server', show: 'diff', q: '' }, null);
  assert.deepEqual(box.children.map((c) => c.textContent), ['No differences in MCP servers', 'Show installed']);
});
```

```python
# tests/unit/test_page_words.py: change the pin in test_library_replaces_load_map_and_discover
    assert '[["mine", "Installed"], ["new", "New"], ["all", "All"], ["diff", "Differences"]]' in text


def test_library_offers_differences_on_every_tab():
    text = script("library.js")
    assert "`No differences in ${label}`" in text and '"Show installed"' in text
    assert 'const SHOWS = ["mine", "new", "all", "diff"];' in script("store.js")
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/frontend/library.test.mjs` and `uv run pytest tests/unit/test_page_words.py -v`
Expected: FAIL (`showChoices` is not exported; the words are not there).

- [ ] **Step 3: Implement.** `asking()` sends `show` as is on catalog tabs, and `"diff"` or else `"mine"` on the others (the cache key follows, since it is `JSON.stringify(asking())`). `toolbar()` draws the `.seg` group on every tab from `showChoices(kind)`; a choice is pressed when it equals `asking().show`, so "New" left over from the Plugins tab shows Installed pressed on MCP servers. `emptyState()` gets a Differences branch after the category/attention branch: `strong` `No differences in ${label}` and `button("Show installed", () => go("library", { show: "mine" }))`. Add `showChoices` to the test's import line. In `docs/design.md`: a Library table row "Show choice": Plugins and Skills show Installed / New / All / Differences, the other tabs Installed / Differences; Differences keeps the rows whose shown clients differ (one loads it and one does not, Off against Loads, or a cell that is Unknown, Needs review or kept from the last good read); a route through a gateway is not a difference; tab counts follow it. In the Motion table, "Ready, then swap" lists "Installed / New / All / Differences".

- [ ] **Step 4: Run the tests**

Run: `node --test tests/frontend/*.test.mjs` and `uv run pytest tests/unit/test_page_words.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/store.js src/kitden/web/static/js/library.js docs/design.md tests/frontend/library.test.mjs tests/unit/test_page_words.py
git commit -m "Library: a Differences choice on every tab" -m "It is kept in the address, so a link or Back returns to it."
```

---

### Task 3: Project exceptions in the data (4.2)

**Files:**
- Modify: `src/kitden/views/load_map.py` (a new `project_exceptions` after `load_map`)
- Modify: `src/kitden/views/library.py` (`_row` gains `"exceptions": []`; `library()` fills it under All projects)
- Test: `tests/unit/test_load_map.py`, `tests/unit/test_library.py`, `tests/unit/test_compare.py`

**Interfaces:**
- Consumes: `effective_view(inventory, client, project)` and `row_key(item)` (exist).
- Produces: `project_exceptions(inventory) -> dict[str, list[dict]]`: row key → `[{"project": <project path>, "client": <client id>, "how": "override" | "off" | "added"}]`, sorted by project path, then client in `COLUMNS` order. Every Library row has `"exceptions": list[dict]`: these entries under All projects (`project is None`), `[]` with a project picked. Part 6 may read `project_exceptions` for its "overrides" lines.

The algorithm (the signature does not settle it). For each found client `c` in `COLUMNS`: `base = effective_view(inventory, c, None)` and the row keys it loads. For each project `p` among `c`'s items with `item.project` set (sorted): `view = effective_view(inventory, c, p)` and the row keys it loads. For each row key `k` of `c`'s own items in `p`, the first rule that holds names the entry; none holding means no entry:

| how | When |
| --- | --- |
| `off` | `k` loads in `base` and not in `view` (the project turns it off) |
| `override` | an item of `p` with key `k` wins over an all-projects one in `view.shadowed` (either mode) |
| `added` | `k` does not load in `base` and loads in `view` (a project-only item with the same name) |

- Builder call: only rows of a project's own items get entries; a project that turns a plugin off does not mark that plugin's skill rows.
- Builder call: the row shows the number of projects, not of entries (one project changing two clients is "1 project exception").
- Builder call: exceptions ride on Library rows only (not `/api/map`), so the start does not pay for them; a Details opened from the Gateway page shows none.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_load_map.py
def test_project_exceptions_name_the_projects_that_change_a_row():
    def item(client, kind, name, scope, project=None, enabled=Enabled.ON):
        source = Source(kind=SourceKind.FILE, path=f"/{client}/{scope}/{project}.json", owner_client=client)
        return Item(client=client, kind=kind, name=name, source=source, scope=scope, project=project, enabled=enabled)

    mcp, plugin, skill = ItemKind.MCP_SERVER, ItemKind.PLUGIN, ItemKind.SKILL
    items = [
        item("claude_code", mcp, "x", Scope.USER),
        item("claude_code", mcp, "x", Scope.LOCAL, "/w/a"),  # wins in a
        item("claude_code", plugin, "p@m", Scope.USER),
        item("claude_code", plugin, "p@m", Scope.PROJECT, "/w/b", Enabled.OFF),  # off in b
        item("claude_code", mcp, "y", Scope.USER),
        item("codex", mcp, "y", Scope.PROJECT, "/w/c"),  # Codex has y only in c
        item("claude_code", skill, "s", Scope.USER),
        item("claude_code", skill, "s", Scope.PROJECT, "/w/a"),  # the user skill wins: no change
    ]
    clients = [Client(id=c, display_name=c, status=ClientStatus.FOUND) for c in ("claude_code", "codex")]
    found = project_exceptions(Inventory(clients=clients, items=items))
    assert found == {
        row_key(items[0]): [{"project": "/w/a", "client": "claude_code", "how": "override"}],
        row_key(items[2]): [{"project": "/w/b", "client": "claude_code", "how": "off"}],
        row_key(items[4]): [{"project": "/w/c", "client": "codex", "how": "added"}],
    }
```

```python
# tests/unit/test_library.py
def test_all_projects_rows_carry_their_project_exceptions(home):
    # The fixture turns superpowers off in work/website.
    row = _row(_library(home, "plugin"), "superpowers", OFFICIAL)
    website = str(home / "work/website")
    assert row["exceptions"] == [{"project": website, "client": "claude_code", "how": "off"}]
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}
    picked = library(inventory, adapters, website, gateway_registered=False, kind="plugin")
    assert all(r["exceptions"] == [] for r in picked["rows"])
```

```python
# tests/unit/test_compare.py
def test_the_medium_project_override_is_an_exception(medium):
    inventory = build_inventory(medium)
    found = project_exceptions(inventory)

    def key(kind, name):
        return row_key(next(i for i in inventory.items if (i.client, i.kind, i.name, i.scope)
                            == ("claude_code", kind, name, Scope.USER)))

    # Part 1: atlas/.mcp.json overrides the user docs; website turns superpowers off.
    atlas, website = str(medium / "work/atlas"), str(medium / "work/website")
    docs = found[key(ItemKind.MCP_SERVER, "docs")]
    assert {"project": atlas, "client": "claude_code", "how": "override"} in docs
    plugin = found[key(ItemKind.PLUGIN, "superpowers@demo-market")]
    assert {"project": website, "client": "claude_code", "how": "off"} in plugin


def test_project_exceptions_stay_fast_on_the_large_sample(tmp_path):
    inventory = build_inventory(build_demo_home(tmp_path, "large"))
    assert min(timeit.timeit(lambda: project_exceptions(inventory), number=1) for _ in range(3)) < 0.1
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_load_map.py tests/unit/test_library.py tests/unit/test_compare.py -v`
Expected: FAIL with `ImportError: cannot import name 'project_exceptions'`.

- [ ] **Step 3: Implement** `project_exceptions` as the table says, and in `library()` set `row["exceptions"] = exceptions.get(row["key"], [])` on every built row, with `exceptions = project_exceptions(inventory) if project is None else {}` computed once per call. Update the exact row dicts other tests compare (search `tests/unit/test_library.py` for `"flags":` in expected rows) with `"exceptions": []`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/test_load_map.py tests/unit/test_library.py tests/unit/test_compare.py tests/unit/test_mcp_server.py -v`
Expected: PASS (the MCP server's answers are unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/kitden/views/load_map.py src/kitden/views/library.py tests/unit/test_load_map.py tests/unit/test_library.py tests/unit/test_compare.py
git commit -m "Library: know which projects change an all-projects item"
```

---

### Task 4: Project exceptions on the page (4.2)

**Files:**
- Modify: `src/kitden/web/static/js/library.js` (`nameCell` near line 608: line two)
- Modify: `src/kitden/web/static/js/details.js` (Part 3's module: `showDetails` gains an "exceptions" block; `DETAILS_ORDER`)
- Modify: `src/kitden/web/static/style.css` (`.sub .exceptions`, quiet like the meta text)
- Modify: `docs/design.md` (Library table: a "Project exceptions" row)
- Test: `tests/frontend/library.test.mjs`, `tests/frontend/details.test.mjs` (Part 3's), `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 3 (`row.exceptions`); Part 3's `DETAILS_ORDER` and `detailsOrder` in `details.js` (the list belongs to question 2, "why and from where").
- Produces: `export function exceptionsText(row): string | null` (library.js): `"1 project exception"`, `"N project exceptions"` (distinct `project` values), or `null`. `export const EXCEPTION_WORDS = { override: "project override", off: "off there", added: "added there" }` and `export function exceptionLines(exceptions): string[]` (details.js): one line per entry, `${folder} · ${client name} · ${EXCEPTION_WORDS[how]}`, where `folder` is the last part of the project path; order as given. `DETAILS_ORDER` gains `"exceptions"` right after `"clients"`: `["warnings", "about", "why", "clients", "exceptions", "tools", "secret", "next", "links", "technical"]`; Part 3's node test 'Details keeps the five questions in order' takes the new list in this commit.

- Builder call: the count is quiet text on line two of the row (after the flags, before the description), not a second control: the row already opens Details, so Tab keeps one stop per row.

- [ ] **Step 1: Write the failing tests**

```js
// tests/frontend/library.test.mjs
test('a row changed by projects says how many, quietly', () => {
  const at = (project, client) => ({ project, client, how: 'override' });
  assert.equal(exceptionsText({ exceptions: [] }), null);
  assert.equal(exceptionsText({ exceptions: [at('/w/a', 'claude_code'), at('/w/a', 'codex')] }), '1 project exception');
  assert.equal(exceptionsText({ exceptions: [at('/w/a', 'codex'), at('/w/b', 'codex')] }), '2 project exceptions');
  // Line two: flags, then the count, then what it does.
  const changed = row({}, { flags: [], description: 'Draw things', exceptions: [at('/w/a', 'codex'), at('/w/b', 'codex')] });
  assert.deepEqual(nameCell(changed, false).children[1].children.map((c) => [c.className, c.textContent]), [['exceptions', '2 project exceptions'], ['desc', 'Draw things']]);
});
```

```js
// tests/frontend/details.test.mjs (import exceptionLines from details.js)
test('Details lists each project exception by folder, client and effect', () => {
  assert.deepEqual(exceptionLines([
    { project: '/Users/me/work/api', client: 'codex', how: 'off' },
    { project: '/Users/me/work/website', client: 'claude_code', how: 'override' },
    { project: '/Users/me/work/website', client: 'cursor', how: 'added' },
  ]), ['api · Codex · off there', 'website · Claude Code · project override', 'website · Cursor · added there']);
});
```

```python
# tests/unit/test_page_words.py
def test_project_exceptions_show_as_a_count_and_in_details():
    assert '"project exception", "project exceptions"' in script("library.js")
    details = script("details.js")
    assert '"Project exceptions"' in details
    assert 'override: "project override", off: "off there", added: "added there"' in details
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/frontend/library.test.mjs tests/frontend/details.test.mjs` and `uv run pytest tests/unit/test_page_words.py -v`
Expected: FAIL (`exceptionsText` and `exceptionLines` are not exported).

- [ ] **Step 3: Implement.** `nameCell` appends `el("small", "exceptions", text)` to `.sub` when `exceptionsText(row)` is not null. Details: when `row.exceptions && row.exceptions.length`, `showDetails` puts the block `"exceptions"` in its map of blocks: a `section.exceptions` with `h2` "Project exceptions" and a `ul.checklist` of `exceptionLines(row.exceptions)`; `detailsOrder` places it after the per-client sections. The per-client sections stay as they are. Add the two names to the tests' import lines. `docs/design.md`, Library table, row "Project exceptions": with All projects, a row a project changes says "2 project exceptions" in quiet text on line two; Details lists each as "website · Claude Code · project override" (or "off there", "added there").

- [ ] **Step 4: Run the tests**

Run: `node --test tests/frontend/*.test.mjs` and `uv run pytest tests/unit/test_page_words.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/library.js src/kitden/web/static/js/details.js src/kitden/web/static/style.css docs/design.md tests/frontend/library.test.mjs tests/frontend/details.test.mjs tests/unit/test_page_words.py
git commit -m "Library: show project exceptions under All projects"
```

---

### Task 5: The review says a project keeps its own (4.2)

**Files:**
- Modify: `src/kitden/views/after.py` (a new `project_keeps` and `KEEPS_KINDS`)
- Modify: `src/kitden/web/app.py` (`preview` near line 1036: append the note to `after`)
- Modify: `docs/design.md` (one sentence in the "Project exceptions" row)
- Test: `tests/unit/test_after.py`, `tests/unit/test_compare.py`

**Interfaces:**
- Consumes: Task 3 `project_exceptions(inventory)`.
- Produces: `KEEPS_KINDS: dict[str, ItemKind]` = `mcp.remove_direct`, `mcp.add`, `gateway.move` → MCP server; `plugin.enable`, `plugin.disable`, `plugin.remove`, `plugin.install` → plugin; `skill.remove`, `skill.install` → skill. `project_keeps(change: Change, inventory) -> str | None`: for each step with `scope is Scope.USER` whose action is in `KEEPS_KINDS`, the row key is `_hash(kind, step.name)` (equal to `row_key` for these kinds); the projects are those with an exception entry for that key and `step.client`. One sentence per item name, joined by a space; `None` when there is none. The preview answer's `after` list gains `{"note": <sentence>}`, which the review already shows as a callout (`afterParts`).

Exact copy, the name being the part before `@`: one project, `"website has its own setting for github. It stays."`; several, `"api and website have their own setting for github. They stay."` (folder names in path order, joined by `_join`).

- Builder call: Add missing does not get this note; each of its lines names its scope (this project or all projects).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_after.py
def test_a_change_to_an_all_projects_item_says_which_projects_keep_their_own():
    def server(scope, project=None):
        source = Source(kind=SourceKind.FILE, path=f"/{scope}/{project}.json", owner_client="claude_code")
        return Item(client="claude_code", kind=ItemKind.MCP_SERVER, name="x", source=source, scope=scope, project=project)

    two = inventory(server(Scope.USER), server(Scope.LOCAL, "/w/website"), server(Scope.LOCAL, "/w/api"))
    remove = Change(action="mcp.remove_direct", steps=[Step(client="claude_code", scope=Scope.USER, name="x")])
    assert project_keeps(remove, two) == "api and website have their own setting for x. They stay."
    one = inventory(server(Scope.USER), server(Scope.LOCAL, "/w/website"))
    assert project_keeps(remove, one) == "website has its own setting for x. It stays."
    in_project = Change(action="mcp.remove_direct", steps=[Step(client="claude_code", scope=Scope.LOCAL, name="x")])
    assert project_keeps(in_project, two) is None
    assert project_keeps(Change(action="gateway.rule", steps=remove.steps), two) is None
```

```python
# tests/unit/test_compare.py
def test_removing_an_all_projects_server_keeps_the_project_override(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    website = home / "work/website"
    add_claude(home, "github", {"type": "http", "url": "https://own.invalid/mcp"}, project=website)
    claude = home / ".claude.json"
    with page_for(home, run=runner(home)) as page:
        users = page.get("/api/items?client=claude_code&kind=mcp_server&scope=user").json()
        target = next(i["id"] for i in users if i["name"] == "github")
        body = {"action": "mcp.remove_direct", "targets": [{"item": target}], "params": {}}
        change = page.post("/api/changes/preview", json=body, headers=POST).json()
        assert {"note": "website has its own setting for github. It stays."} in change["after"]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        kept = json.loads(claude.read_text())["projects"][str(website)]["mcpServers"]["github"]
        assert kept == {"type": "http", "url": "https://own.invalid/mcp"}
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
```

(`runner` comes from `tests/unit/test_align.py`; `page_for`, `POST` from `tests/unit/test_local_gateway_views.py`; `add_claude` from `tests/unit/test_local_gateway_move.py`.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_after.py tests/unit/test_compare.py -v`
Expected: FAIL with `ImportError: cannot import name 'project_keeps'`.

- [ ] **Step 3: Implement** `project_keeps`, and in `preview` after `after_words(...)`: `keeps = project_keeps(change, state.inventory)`; when set, `after.append({"note": keeps})`. In `docs/design.md`, the "Project exceptions" row adds: a change to the all-projects item says when a project keeps its own setting.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/test_after.py tests/unit/test_compare.py tests/unit/test_api_changes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/views/after.py src/kitden/web/app.py docs/design.md tests/unit/test_after.py tests/unit/test_compare.py
git commit -m "Review: say when a project keeps its own setting"
```

---

### Task 6: Add missing in four groups, on the server (4.3)

**Files:**
- Modify: `src/kitden/changes/align.py` (`align_steps` near line 122; new `_another_way`; constants)
- Test: `tests/unit/test_align.py` (update every `candidates`, `not_same`, `left_out`), `tests/unit/test_compare.py`

**Interfaces:**
- Consumes: today's `_build`, `_place`, `_not_same`, `_words`, `has`, `skill_catalog` (find by name). After Part 2 Task 5, `_source` and `SERVER_FIELDS` live in `views/match.py` and `_not_same` stays in `align.py`, built on `match.source_key`.
- Produces: `align_steps(...)` returns `(steps, listing)` with `listing = {"will_add": [...], "already": [...], "decide": [...], "cannot": [...]}`:
  - `will_add`: today's candidate (`key`, `kind`, `name`, `from`, `to`, `place`, `note`, `chosen`) plus `"why": str`.
  - `already`: `{"kind", "name", "to", "why"}`, one per name and client, in loop order.
  - `decide`: today's `_not_same(views)` entries, `{"kind", "name", "clients"}`.
  - `cannot`: `{"kind", "name", "to", "why"}`, one per name and target client (the old dedupe by name and reason goes).
  - `_another_way(client: str, items: list[Item], from_plugin: bool) -> str | None`: why `client` has the name without its own copy, or `None` when it has its own copy that loads.

The loop stays as today with these changes, in this order, for each `(kind, base_name, client)` once (`seen` is set before the `has` check):

1. The client has the name (`has`): `why = _another_way(client, its items of that kind and name in the project or for all projects, the skill_catalog says "Via plugin" for it)`; a `why` goes to `already`; then next.
2. `_build` raises: `cannot` with `str(error)`.
3. A built step edits a file in `{p.path for p in inventory.problems}`: `cannot` with Part 2's `NO_ADD_UNREAD.format(<file name>)` (`views/words.py`), the sentence the Library and the preview use. Owner ruling (2026-10-22): only an add that writes into the broken file goes here; an add into the same client's other, readable file stays in `will_add`.
4. Otherwise `will_add`, with today's notes, then the decide note last when `(kind.value, base_name)` is in `decide` (that note also makes it start unchecked, like the others).

`_another_way` takes the first that holds:

| Holds | Returns |
| --- | --- |
| an item not off, not through a gateway, not in a plugin, owner the client or `"shared"` | `None` |
| an item through a gateway, not off | `f"{who} gets it through a gateway."` |
| an item with `Scope.PLUGIN`, not off, or `from_plugin` | `f"{who} gets it from a plugin."` |
| an item from another client's folder (`SourceKind.OTHER_CLIENT_FOLDER`), not off | `f"{who} reads it from {other}'s folder."` |
| an item whose owner is another client (a `CLIENT_WORDS` key other than `client`; `"shared"` is not one), not off | `f"{who} loads {other}'s copy."` |
| an item that is off | `f"{who} has it turned off."` |
| none | `None` |

Exact copy: `will_add` why `f"{_words(holders)} {'has' if len(holders) == 1 else 'have'} it; {target} does not."`, where `holders` are the clients whose `views` load that kind and name, in `CLIENTS` order. Decide note `f"{_words(clients)} have different {name}; this adds {source}'s."`. (The unread reason is Part 2's `NO_ADD_UNREAD`, e.g. "Can't add while mcp.json can't be read."). "Nothing is missing in <folder>." is raised only when `will_add`, `decide` and `cannot` are all empty.

- Builder call: `will_add`'s reason names every client that loads it ("Claude Code and Cursor have it; Codex does not.").
- Builder call: an add whose name is in `decide` starts unchecked with the decide note (spec: "never added silently").
- Builder call: `~/.agents/skills` (owner `"shared"`) counts as the client's own folder, as `_is_source` already says; the spec's "shared folder" is another client's folder that this client reads.
- Builder call: an add into a file Kitden could not read goes to `cannot`, so the rest of the review still opens; only that add, never the client's adds into its readable files (owner ruling).
- Builder call: with nothing to add but something to decide or that Kitden cannot add, the review still opens (`steps: []`, Apply waits).

- [ ] **Step 1: Update the existing tests and write the new ones**

In `tests/unit/test_align.py`: read `listing["will_add"]` where it read `candidates`, `decide` for `not_same`, `cannot` for `left_out`. Changed assertions:

```python
# test_add_missing_lists_what_each_client_lacks
    assert keys["mcp_server:github:codex"]["why"] == "Claude Code has it; Codex does not."
    assert {"kind": "skill", "name": "brandkit", "to": "cursor", "why": "Cursor reads it from Claude Code's folder."} in listing["already"]
    assert {"kind": "skill", "name": "pixel-art", "to": "codex", "why": "Codex has it turned off."} in listing["already"]
    assert keys["mcp_server:neon:cursor"]["note"] == (
        "Cursor already has Neon; this adds neon beside it. "
        "Claude Code and Codex have different neon; this adds Claude Code's."
    )
    assert {"kind": "mcp_server", "name": "shelled", "to": "codex", "why": "Codex cannot read `${TOKEN}` from your shell; put the value in."} in listing["cannot"]
    browser = [(e["to"], e["why"]) for e in listing["cannot"] if e["name"] == "browser@openai-bundled"]
    assert browser == [("claude_code", NO_OFFER), ("cursor", NO_OFFER)]  # one line per client
# test_a_copy_another_client_reads_is_not_made_twice_and_nothing_is_overwritten
    assert {"kind": "skill", "name": "langfuse", "to": "claude_code", "why": "Claude Code already has a skill named langfuse"} in listing["cannot"]
# test_plugins_go_where_each_client_can_take_them
    assert {"kind": "plugin", "name": "linter@claude-plugins-official", "to": "cursor", "why": CURSOR_VIA} in change["align"]["cannot"]
```

```python
# tests/unit/test_align.py
def test_another_way_names_how_a_client_already_gets_it():
    def item(client, owner, kind=SourceKind.FILE, scope=Scope.USER, enabled=Enabled.ON, via=None):
        source = Source(kind=kind, path="/x", owner_client=owner)
        return Item(client=client, kind=ItemKind.SKILL, name="x", source=source, scope=scope, enabled=enabled, via_gateway=via)

    assert _another_way("codex", [item("codex", "codex")], False) is None
    assert _another_way("codex", [item("codex", "shared")], False) is None
    assert _another_way("codex", [item("codex", "codex", via="kitden")], False) == "Codex gets it through a gateway."
    assert _another_way("codex", [item("codex", "codex", scope=Scope.PLUGIN)], False) == "Codex gets it from a plugin."
    assert _another_way("codex", [], True) == "Codex gets it from a plugin."
    folder = item("cursor", "claude_code", SourceKind.OTHER_CLIENT_FOLDER)
    assert _another_way("cursor", [folder], False) == "Cursor reads it from Claude Code's folder."
    assert _another_way("cursor", [item("cursor", "claude_code", SourceKind.PLUGIN)], False) == "Cursor loads Claude Code's copy."
    assert _another_way("codex", [item("codex", "codex", enabled=Enabled.OFF)], False) == "Codex has it turned off."
    # A way that loads wins over a copy that is off.
    off = item("cursor", "cursor", enabled=Enabled.OFF)
    assert _another_way("cursor", [off, folder], False) == "Cursor reads it from Claude Code's folder."


def test_a_decision_alone_still_opens_the_review(tmp_path):
    # As test_when_every_add_makes_a_duplicate_the_review_still_lists_them, but Codex names its
    # entry neon too, at another address: nothing to add, one name to decide.
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2")
    api = home / "work/api"
    api.mkdir(parents=True, exist_ok=True)
    claude = {"projects": {str(api): {}}, "mcpServers": {"neon": {"url": "https://a.invalid/mcp"}}}
    (home / ".claude.json").write_text(json.dumps(claude))
    (home / ".codex/config.toml").write_text('[mcp_servers.neon]\nurl = "https://b.invalid/mcp"\n')
    for folder in (".claude/skills", ".agents/skills", ".codex/skills", ".claude/plugins"):
        shutil.rmtree(home / folder, ignore_errors=True)
    with page_for(home, run=runner(home)) as page:
        change = _align(page, project_id(page, str(api))).json()
        assert change["steps"] == [] and change["align"]["will_add"] == []
        assert change["align"]["decide"] == [{"kind": "mcp_server", "name": "neon", "clients": ["claude_code", "codex"]}]
```

```python
# tests/unit/test_compare.py: each test adds its own names to the medium sample, then asks.
def _align_on(page, chosen=None, folder="work/atlas"):
    """The Add missing preview response for the Part 1 project at ~/<folder> (its id from
    /api/projects; POST /api/changes/preview, action project.align, as _align in test_align.py)."""


def _align_medium(home, chosen=None):
    """_align_on(...).json() on served(home)."""


def test_will_add_says_why_and_where(medium):
    _server(medium, "kd-extra", ["claude_code"], "https://extra.invalid/mcp")
    listing = _align_medium(medium)["align"]
    entry = next(e for e in listing["will_add"] if e["key"] == "mcp_server:kd-extra:codex")
    assert (entry["why"], entry["place"], entry["chosen"]) == ("Claude Code has it; Codex does not.", "all", True)


def test_already_lists_turned_off_and_another_clients_copy(medium):
    add_claude(medium, "kd-off", {"type": "stdio", "command": "uvx", "args": ["kd-off"]})
    add_codex(medium, "kd-off", 'command = "uvx"\nargs = ["kd-off"]\nenabled = false')
    skill = medium / ".claude/skills/kd-folder/SKILL.md"  # Cursor reads Claude Code's folder
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: kd-folder\ndescription: A test skill.\n---\n")
    listing = _align_medium(medium)["align"]
    assert {"kind": "mcp_server", "name": "kd-off", "to": "codex", "why": "Codex has it turned off."} in listing["already"]
    assert {"kind": "skill", "name": "kd-folder", "to": "cursor", "why": "Cursor reads it from Claude Code's folder."} in listing["already"]
    codex = next(e for e in listing["will_add"] if e["key"] == "skill:kd-folder:codex")
    assert codex["why"] == "Claude Code and Cursor have it; Codex does not."


def test_a_name_with_two_sources_is_a_decision_and_never_checked(medium):
    _server(medium, "kd-two", ["claude_code"], "https://a.invalid/mcp")
    _server(medium, "kd-two", ["codex"], "https://b.invalid/mcp")
    listing = _align_medium(medium)["align"]
    assert {"kind": "mcp_server", "name": "kd-two", "clients": ["claude_code", "codex"]} in listing["decide"]
    cursor = next(e for e in listing["will_add"] if e["key"] == "mcp_server:kd-two:cursor")
    assert cursor["chosen"] is False
    assert cursor["note"] == "Claude Code and Codex have different kd-two; this adds Claude Code's."


def test_cannot_names_the_target_client(medium):
    add_claude(medium, "kd-shell", {"type": "stdio", "command": "npx", "args": ["x", "${TOKEN}"]})
    listing = _align_medium(medium)["align"]
    why = "Codex cannot read `${TOKEN}` from your shell; put the value in."
    assert {"kind": "mcp_server", "name": "kd-shell", "to": "codex", "why": why} in listing["cannot"]


def test_an_add_into_a_file_kitden_could_not_read_cannot_be_added(medium):
    (medium / ".cursor").mkdir(exist_ok=True)
    (medium / ".cursor/mcp.json").write_text("{ not json")
    _server(medium, "kd-extra", ["claude_code"], "https://extra.invalid/mcp")
    with served(medium) as page:
        problems = {p["path"] for p in page.get("/api/problems").json()}
        assert str(medium / ".cursor/mcp.json") in problems
        answer = _align_on(page)
        assert answer.status_code == 200
        listing = answer.json()["align"]
        why = "Can't add while mcp.json can't be read."  # Part 2's NO_ADD_UNREAD
        assert {"kind": "mcp_server", "name": "kd-extra", "to": "cursor", "why": why} in listing["cannot"]
        assert not any(e["to"] == "cursor" and e["kind"] == "mcp_server" for e in listing["will_add"])


def test_a_broken_project_file_holds_only_the_adds_into_it(medium):
    # Part 1: ~/work/website/.cursor/mcp.json is cut short. Add missing puts MCP entries in all
    # projects, so Cursor's adds go into ~/.cursor/mcp.json, which reads well (owner ruling).
    _server(medium, "kd-extra", ["claude_code"], "https://extra.invalid/mcp")
    with served(medium) as page:
        listing = _align_on(page, folder="work/website").json()["align"]
    assert any(e["key"] == "mcp_server:kd-extra:cursor" for e in listing["will_add"])
    assert not any("can't be read" in e["why"] for e in listing["cannot"])
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_align.py tests/unit/test_compare.py -v`
Expected: FAIL (`KeyError: 'will_add'`; `_another_way` is not defined).

- [ ] **Step 3: Implement** the listing as the Interfaces and the two tables say. `app.py` needs no change: it passes `align` through, and its "nothing chosen" branch already returns the list with `steps: []`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/test_align.py tests/unit/test_compare.py tests/unit/test_after.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/changes/align.py tests/unit/test_align.py tests/unit/test_compare.py
git commit -m "Add missing: four groups, each line with its reason" -m "Kitden cannot add keeps the target client; a file Kitden could not read is listed there."
```

---

### Task 7: Add missing in four groups, on the page (4.3)

**Files:**
- Modify: `src/kitden/web/static/js/review.js` (Part 3's module: `changeWords` `project.align` branch; `alignGroups`; `chosenKeys`; `alignSection`; `lockReview`)
- Modify: `docs/design.md` (Library table: the "Add missing" row)
- Test: `tests/frontend/panel.test.mjs` (the existing align test, edited where it is), `tests/frontend/review.test.mjs` (Part 3's: the new `alignLines` test), `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 6 listing; Part 2 `goTo(view: string, selected: {kind, name} | null)` in `store.js`; `KIND_WORDS` from `details.js`; Part 3's review: the title stays in `changeWords` (review.js), and `project.align` is in Part 3's `PLACE_IN_TITLE`, so no scope words are added to the title below; the lede is Part 3's `reviewLede(change, picked)`, unchanged here.
- Produces: `alignGroups(align)` reads `align.will_add`; each item is `{key, label, why, note, chosen}` with `label` `${name} · ${KIND_WORDS[kind]} · ${PLACE_WORDS[place]}`. `export function alignLines(align): {already: string[], decide: {kind, name, text}[], cannot: string[]}` (review.js): already `${name} · ${kind word} · ${why}`; decide text `${name} · ${kind word} · ${joinWords(client names)} load it from different sources.`; cannot `${name} · ${kind word} · ${client name}: ${why}`. `chosenKeys(align, key, checked)` reads `align.will_add`.

The review, top to bottom: `h2` "Will add" with one fieldset per client (legend "Add to Codex", as today), each line a box, the label and a muted part with `why` and `note`; or, with nothing to add, a muted "Nothing to add."; the "Choose at least one item." note as today; `h2` "Already there another way"; `h2` "Needs your decision", each line with a small "Compare" button (`btn ghost small`) that closes the panel without focus (`closePanel({ focus: false })`, which cancels the preview) and calls `goTo("library", { kind, name })`; `h2` "Kitden cannot add". An empty group is not drawn. `lockReview` disables the boxes and the Compare buttons while a change is written.

Title: `Adds ${plural(n, "item", "items")} to ${folder}` with `n` checked lines, or `Add what ${folder} is missing` when none is checked; the done line `Added ${plural(n, "item", "items")} to ${folder}`. When the last box is unchecked, `#panel-title` takes the none-checked title at once.

- Builder call: one review, four headed groups in this order; Will add is grouped by client, the other three are one line each that names the client.
- Builder call: Compare leaves the review (the preview is cancelled) and opens that row's Details in the Library.
- Builder call: N counts the checked lines; with none checked the title keeps today's "Add what <project> is missing". MCP entries and Codex plugins still go to all projects (`align._place`): the title keeps the spec's words and each line names its scope.

- [ ] **Step 1: Write the failing tests**

```js
// tests/frontend/panel.test.mjs: replaces the body of 'the align review groups what each client lacks and keeps the choice'
  const align = { will_add: [
    { key: 'mcp_server:github:codex', kind: 'mcp_server', name: 'github', from: 'claude_code', to: 'codex', place: 'all', why: 'Claude Code has it; Codex does not.', note: null, chosen: true },
    { key: 'skill:brandkit:cursor', kind: 'skill', name: 'brandkit', from: 'claude_code', to: 'cursor', place: 'project', why: 'Claude Code has it; Cursor does not.', note: 'Cursor already has Brandkit; this adds brandkit beside it.', chosen: false },
  ], already: [], decide: [], cannot: [] };
  assert.deepEqual(alignGroups(align), [
    { client: 'codex', name: 'Codex', items: [{ key: 'mcp_server:github:codex', label: 'github · MCP server · all projects', why: 'Claude Code has it; Codex does not.', note: null, chosen: true }] },
    { client: 'cursor', name: 'Cursor', items: [{ key: 'skill:brandkit:cursor', label: 'brandkit · Skill · this project', why: 'Claude Code has it; Cursor does not.', note: 'Cursor already has Brandkit; this adds brandkit beside it.', chosen: false }] },
  ]);
  assert.deepEqual(chosenKeys(align, 'skill:brandkit:cursor', true), ['mcp_server:github:codex', 'skill:brandkit:cursor']);
  data.projects = [{ id: 'p1', path: '/Users/me/work/website' }];
  const body = { params: { project: 'p1' } };
  assert.deepEqual(changeWords({ action: 'project.align', steps: [{ client: 'codex', name: 'github' }], align }, body), { title: 'Adds 1 item to website', done: 'Added 1 item to website' });
  const none = { ...align, will_add: align.will_add.map((c) => ({ ...c, chosen: false })) };
  assert.equal(changeWords({ action: 'project.align', steps: [], align: none }, body).title, 'Add what website is missing');
  data.projects = null;
```

```js
// tests/frontend/review.test.mjs (import alignLines from review.js)
test('the other three groups are one line each that names the client', () => {
  assert.deepEqual(alignLines({ will_add: [],
    already: [{ kind: 'skill', name: 'pixel-art', to: 'codex', why: 'Codex has it turned off.' }],
    decide: [{ kind: 'mcp_server', name: 'neon', clients: ['claude_code', 'codex'] }],
    cannot: [{ kind: 'plugin', name: 'browser@openai-bundled', to: 'cursor', why: 'not in a marketplace on this computer' }],
  }), {
    already: ['pixel-art · Skill · Codex has it turned off.'],
    decide: [{ kind: 'mcp_server', name: 'neon', text: 'neon · MCP server · Claude Code and Codex load it from different sources.' }],
    cannot: ['browser@openai-bundled · Plugin · Cursor: not in a marketplace on this computer'],
  });
});
```

```python
# tests/unit/test_page_words.py: replaces test_a_project_can_be_aligned_in_one_review
def test_a_project_can_be_aligned_in_one_review():
    library = script("library.js")
    assert "Add missing…" in library and '"add:missing"' in library
    review = script("review.js")
    for words in ('"Will add"', '"Already there another way"', '"Needs your decision"', '"Kitden cannot add"', '"Compare"', '"Nothing to add."'):
        assert words in review, words
    assert "Not the same; not touched" not in panel() and '"project.align"' in review
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/frontend/panel.test.mjs tests/frontend/review.test.mjs` and `uv run pytest tests/unit/test_page_words.py -v`
Expected: FAIL (`alignLines` is not exported; the old title and words).

- [ ] **Step 3: Implement** as the Interfaces say; `leftOutText` stays for Add skills (`change.left_out`). Import `alignLines` in `review.test.mjs` from `review.js`. `docs/design.md`, the "Add missing" row: in a project, a small plain "Add missing…" (not on Instructions). Its review is titled "Adds 3 items to website" and has four groups: Will add (checkboxes, one group per client, each line with where it goes and why it is missing, "Claude Code has it; Codex does not."), Already there another way (a plugin, another client's folder or copy, a gateway, or turned off), Needs your decision (same name, different sources, with Compare), Kitden cannot add (the client and the reason). An add that would make a duplicate or that has a name to decide starts unchecked and says why; a change previews again; with none checked, Apply waits.

- [ ] **Step 4: Run the tests**

Run: `node --test tests/frontend/*.test.mjs` and `uv run pytest tests/unit/test_page_words.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/review.js docs/design.md tests/frontend/panel.test.mjs tests/frontend/review.test.mjs tests/unit/test_page_words.py
git commit -m "Add missing: the review shows four groups" -m "Its title says how many items it adds and to which project."
```

---

### Task 8: Docs and roadmap for Part 4

**Files:**
- Modify: `README.md` ("See what each client has, and add what it lacks", near lines 43–62)
- Modify: `ROADMAP.md` only if the owner has committed their edit (see Step 3)
- Test: `tests/unit/test_docs_words.py`

**Interfaces:**
- Consumes: Tasks 1–7 (the words they pinned).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_docs_words.py
def test_readme_says_what_compare_shows():
    readme = " ".join((ROOT / "README.md").read_text().split())
    for words in ("Differences", "project exceptions", "Needs your decision", "Kitden cannot add"):
        assert words in readme, words
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/unit/test_docs_words.py -v`
Expected: FAIL on "Differences".

- [ ] **Step 3: Write the README sentences and the roadmap lines.** README, in the Library section: "On every tab, Differences shows only the rows where the clients on the page differ: one has it and one does not, one has it off, or Kitden is not sure. With All projects picked, a row that a project changes says how many project exceptions it has, and Details lists them." Replace the last Add missing sentence with: "Add missing… lists, in one review, what it will add (with why each is missing), what a client already has another way, what Needs your decision (the same name from different sources, with Compare), and what Kitden cannot add, with the reason." Check `docs/design.md` once more against the page (Tasks 2, 4, 5, 7 changed it). Then `git status --short ROADMAP.md`: if it shows ` M` (the owner's edit), do not touch the file and put these lines in the report; otherwise move Part 4's line from "## Planned" (if there) to "### Not released yet" with this text:

```markdown
- **Compare:** the Library's Differences filter shows only the rows where the clients differ.
  With All projects, a row a project changes says how many project exceptions it has. Add
  missing sorts what it finds into Will add, Already there another way, Needs your decision and
  Kitden cannot add, each line with its reason.
```

- [ ] **Step 4: Run all checks**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check src tests && node --test tests/frontend/*.test.mjs`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/unit/test_docs_words.py
git commit -m "Docs: Compare, project exceptions and Add missing groups"
```

(Add `ROADMAP.md` to the `git add` only when Step 3 edited it.)

---

## Spec coverage

| Spec | Task |
| --- | --- |
| 4.1 Differences beside Installed / New / All; rows whose cells differ in the picked context (Loads vs —, Off vs Loads, Needs review, Unknown); a hash filter | 1, 2 |
| 4.2 "2 project exceptions" on a row changed by a project; Details lists them | 3, 4 |
| 4.2 changing an all-projects item never removes a project override; the review says so | 5 |
| 4.3 Will add with scope and reason; Already there another way; Needs your decision with Compare; Kitden cannot add with client and reason | 6, 7 |
| 4.3 duplicate-making adds start unchecked; nothing checked → the list shows and Apply waits | 6, 7 (kept, tests updated) |
| Done: tests for each group on `medium`; "Adds N items to <project>"; Differences in the hash and the node tests | 6, 7, 2 |
