# Part 2: Shared words, scope and selection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every page speaks the same words: "All projects" for the shared baseline, one short
origin label where it decides, Unknown and Needs review that never look like Missing or equal,
an add that names its scope before Apply, and a project and selected item that stay in the
address from page to page.

**Architecture:** The server keeps one table of state words (`views/words.py`, twin of
`parts.js STATE_WORDS`). `load_map` gains three cell facts (origin, reason, last good read) and a
`"review"` state built from one match module (`views/match.py`) that Add missing shares. The
page server keeps the last good read of each source in memory (`keep_last_good`). On the page,
`store.js` carries `sel=<kind>:<name>` in every address and `goTo(view, selected)` opens a place
with the selection, which the Library and the Gateway open in Details once.

**Tech Stack:** Python 3.13, Starlette; plain ES modules, one CSS file; pytest on sandbox homes;
node's test runner. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-22-visual-management-design.md`, Part 2 (2.1–2.5), with
its Constraints, Anti-goals and Acceptance. Master plan:
`docs/superpowers/plans/2026-10-22-visual-management.md` (its Rules and "Names that cross part
boundaries" bind this part). Concept §3, §4, §6.2, §6.3, §9, §11.

## Global Constraints

- `AGENTS.md` in full: code, comments, UI text and docs in simple English; tests on sandbox homes
  only (`make_home`, `write_cursor_fixture_state`, `build_demo_home`); never the real home, a real
  client command, a real MCP server, the Keychain or the network.
- Stack unchanged: Python 3.13, Starlette, MCP SDK 2.3, tomlkit, watchfiles; plain ES modules, one
  CSS file; no framework, no bundler, no library from another site; strict CSP. No new runtime
  dependency.
- Main pages show a name, the client, a state and an action. A file appears on a main page only
  by its name (`mcp.json`), never its path.
- `docs/design.md` governs look and motion. A changed word changes its pin in
  `tests/unit/test_page_words.py` (or the node test) and its `docs/design.md` line in the same
  commit (master Rules): each task below names its design.md lines. Task 9 writes the README and
  reads design.md through once.
- Sample facts come from Part 1's "Sample contract" (medium): the override is `docs` in
  `~/work/atlas`, the same-name server is `docs` (Claude Code and Codex), the unreadable file is
  `~/work/website/.cursor/mcp.json`.
- Nothing moves while idle. A new look is a resting CSS style; no new animation.
- The last good read lives in memory only, never on disk (spec 2.3).
- `explain()` and `project_views()` feed the MCP server: a task that changes the inventory's items
  runs `tests/unit/test_mcp_server.py`; file lines never go to agents.
- `ROADMAP.md`: while `git status` shows it modified by the owner, no task edits or stages it;
  Task 9 writes the roadmap line into its report instead.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`,
  `node --test tests/frontend/*.test.mjs`. All pass or the commit waits.
- Commits stage files by name (never `git add -A`, `.` or `-a`); the message is a short plain
  subject, one to three simple lines, ending with the session's co-author line.
- Line numbers are hints; find code by name.
- Exact copy this part adds (spec 2.1–2.4; the ones marked "Builder" are this plan's choice):

| Where | Words |
| --- | --- |
| Picker's empty choice, tools heading, Details scope | `All projects` (`ALL_PROJECTS` in `parts.js`) |
| Scope inside a sentence | `all projects`, `this project` |
| Cell origin (CSS adds the "· ") | `this project`, `project override`; nothing for all projects |
| Cell states | `Loads`, `Off`, `Unknown`, `Needs review`, `—` |
| A client that could not be read | column note `Could not read`; cell reason `Could not read Codex.` |
| A file that failed on its first read | `Could not read mcp.json; its items are not shown.` |
| An item kept from the last good read | row flag `From the last good read at 14:02` |
| An add into a file that failed to read (owner ruling: only adds into that file) | `Can't add while mcp.json can't be read.` |
| Needs review reason (Builder) | `Same name, from another source.` |
| Details lede for review (Builder) | `Needs review in Codex: same name, another source.` |
| A project no longer known | `This project is no longer on the list.` |
| An add's review | title ends ` for all projects` (or ` in website`); lede starts `Adds for all projects.` with All projects picked |

## Review Focus

1. **A settings file that breaks while the page runs** (a stray comma in `~/.claude.json`): its
   items stay, marked "From the last good read at …", no "+ Add" into that file (adds into other,
   readable files stay), and no "its items
   are not shown" line (it would be false). Task 4,
   `test_a_file_that_breaks_keeps_its_items_from_the_last_good_read`.
2. **A client whose scan throws:** its column stays with "Could not read", every cell is Unknown
   with the reason, never "Not installed", "—" or "+ Add"; the Overview's client row says "Could
   not read". Task 3, `test_a_client_that_could_not_be_read_keeps_its_column_as_unknown` and the
   node test `a client that could not be read says so, not Not installed`.
3. **Same name, other source, against a plain copy:** a server with another address and a skill
   with other files need review; a skill folder Kitden copied (same files, other place) and an
   item one client loads twice do not. Task 5, `test_a_copied_skill_is_the_same_skill` and
   `test_a_duplicate_in_one_client_is_not_review`.
4. **A picked project that leaves the list** (or an old link to one): it stays picked, the place
   says "This project is no longer on the list.", nothing is read or offered for it, and the
   picker does not pretend All projects. Task 6, node test
   `a project no longer on the list stays picked and is said`.
5. **A broken or stale `sel` in the address** (`sel=nope`, `sel=mcp_server:`, `sel=wizard:x`, a
   removed item, a skill selected while on the Gateway): nothing opens, nothing fails, the list
   shows; a selection the page cannot open stays for the next page. Task 7,
   `parseSel takes only kind:name`, and Task 8, `the Gateway opens only a selected server`.

---

### Task 1: One table of state words, and "All projects" (2.1)

> If walkthrough 1 changed the words, the controller's ruling gives the new values; only
> `STATE_WORDS` (both tables) and their pins change.

**Files:**
- Create: `src/kitden/views/words.py`
- Modify: `src/kitden/views/after.py` (drop `WORDS`; `CURSOR_IMPORT["word"]` from the table),
  `src/kitden/views/library.py` ("Via Claude Code", "Has its skills", `HAS_IT` from `words.py`)
- Modify: `src/kitden/web/static/js/parts.js` (`ALL_PROJECTS`), `src/kitden/web/static/index.html`
  (picker option), `src/kitden/web/static/js/app.js` (`renderShell` picker option and title),
  `src/kitden/web/static/js/panel.js` (`scopeWords`, tools heading),
  `src/kitden/web/static/js/changes.js` (`SCOPE_WORDS.user`)
- Modify: `docs/design.md` (Components: the picker's first choice is "All projects"; the
  Instruction file Details row: "With no project picked only global files show lines" becomes
  "With All projects picked only the files for all projects show lines")
- Test: `tests/unit/test_page_words.py`, `tests/frontend/panel.test.mjs`

**Interfaces:**
- Produces (Python, `kitden.views.words`): `STATE_WORDS: dict[str, str]` =
  `{"on": "Loads", "off": "Off", "unk": "Unknown", "gw": "Via gateway", "via": "Via Claude Code", "done": "Has its skills"}`;
  `HAS_IT = "Has it"`; `AFTER_WORDS: dict[str, tuple[str, str]]` — `after.py`'s old `WORDS`,
  same keys and values, each state word read from `STATE_WORDS` ("Removed", "Added", "Updated",
  "Via the new gateway" stay literal: they are action words). Later tasks add keys to both tables.
- Produces (JS, `parts.js`): `export const ALL_PROJECTS = "All projects";`.
- Produces (JS, `panel.js`): `export function scopeWords(def, picked = projectPath()) -> string`:
  `user` → `ALL_PROJECTS`; `project` → `"This project"` when `def.project === picked`, else
  `Project <folder>`; the other scopes and the ` · via <client>` suffix as today.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_page_words.py
from kitden.views.words import AFTER_WORDS, STATE_WORDS


def test_python_and_page_state_words_agree():
    parts = script("parts.js")
    for state, word in STATE_WORDS.items():
        assert f'{state}: "{word}"' in parts, state


def test_after_words_come_from_the_one_table():
    from kitden.views import after

    assert not hasattr(after, "WORDS")
    assert AFTER_WORDS["plugin.enable"] == ("on", STATE_WORDS["on"])
    assert AFTER_WORDS["gateway.move"] == ("gw", STATE_WORDS["gw"])
```

Update `test_project_picker_says_project_not_where`: `'new Option(ALL_PROJECTS, "")' in app`,
`'<option value="">All projects</option>' in INDEX`, `"Global" not in app` and
`"Global" not in INDEX`, `'export const ALL_PROJECTS = "All projects";' in script("parts.js")`.
Update `test_changes_and_the_library_say_saved_settings_and_scope`: `'user: "all projects"' in changes`
and `"global settings" not in changes`. Add to it: ``'Tools · ${where || ALL_PROJECTS}' in script("panel.js")``.

```js
// tests/frontend/panel.test.mjs
test('Details names the scope with the same phrases as the cells', () => {
  assert.equal(scopeWords({ scope: 'user' }, ''), 'All projects');
  assert.equal(scopeWords({ scope: 'project', project: '/w/website' }, '/w/website'), 'This project');
  assert.equal(scopeWords({ scope: 'project', project: '/w/api' }, '/w/website'), 'Project api');
  assert.equal(scopeWords({ scope: 'user', client: 'cursor', owner_client: 'claude_code' }, ''), 'All projects · via Claude Code');
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_page_words.py -q` and `node --test tests/frontend/panel.test.mjs`
Expected: FAIL (`kitden.views.words` missing, `scopeWords` not exported, "Global" found).

- [ ] **Step 3: Implement** `views/words.py`, the imports in `after.py` and `library.py`, and the
  JS words. The picker's title with no project is `ALL_PROJECTS` (was "Global setup").

- [ ] **Step 4: Run** `uv run pytest tests/unit/test_page_words.py tests/unit/test_after.py tests/unit/test_library.py -q`
  and `node --test tests/frontend/*.test.mjs` → PASS.

- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/views/words.py src/kitden/views/after.py src/kitden/views/library.py \
  src/kitden/web/static/index.html src/kitden/web/static/js/parts.js src/kitden/web/static/js/app.js \
  src/kitden/web/static/js/panel.js src/kitden/web/static/js/changes.js docs/design.md \
  tests/unit/test_page_words.py tests/frontend/panel.test.mjs
git commit -m "Words: All projects, and one table of state words"
```

---

### Task 2: The origin in one short label (2.2)

**Files:**
- Modify: `src/kitden/views/load_map.py` (`Cell.origin`; `_where`; `_cell`; `load_map`; `map_dict`)
- Modify: `src/kitden/views/words.py` (`ORIGIN_WORDS`), `src/kitden/views/library.py`
  (`_cell` and `_map_cell` carry `origin`)
- Modify: `docs/design.md` (Library table, "Cell state": in a project a cell adds "· this
  project" when the item comes from the project and "· project override" when a project item
  wins over an all-projects one, nothing when it comes from all projects)
- Test: `tests/unit/test_load_map.py`, `tests/unit/test_library.py`

**Interfaces:**
- Consumes: `kitden.demo.build_demo_home(root: Path, size: str) -> Path` (Part 1; in the `medium`
  sample `~/work/atlas/.mcp.json` overrides Claude Code's user `docs`).
- Produces: `Cell.origin: str | None` — `None`, `"project"` or `"override"` (master plan name);
  `ORIGIN_WORDS = {"project": "this project", "override": "project override"}`; `map_dict` and
  every Library cell carry `"origin"`.
- Rule: the deciding item of a cell is the one that names it today (`loaded[0]` after
  `_own_first`, or `present[0]` after the winners sort). `"override"` when that item is a winner in
  some client's `EffectiveView.shadowed` whose loser has `project is None` and the winner has a
  project; else `"project"` when the item has a project; else `None`. With an origin, the cell's
  `where` is `ORIGIN_WORDS[origin]`; without one, `_where` as today, except that `Scope.USER`,
  `Scope.PROJECT` and `Scope.LOCAL` give `None` (drop them from `SCOPE_WORDS`). Builder call: "· global
  settings" leaves every cell; "this Mac" for a local entry moves to Details only.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_load_map.py
def test_a_project_item_says_this_project_and_a_project_win_says_project_override(home):
    rows = load_map(build_inventory(home), str(home / "work/website"))
    docs = rows_by(rows, "mcp_server", "docs").cells["claude_code"]
    assert (docs.where, docs.origin) == ("this project", "project")
    plugin = plugin_row(rows, "superpowers@claude-plugins-official").cells["claude_code"]
    assert (plugin.state, plugin.where, plugin.origin) == ("off", "project override", "override")
    github = rows_by(rows, "mcp_server", "github").cells["claude_code"]
    assert (github.where, github.origin) == (None, None)


def test_all_projects_cells_carry_no_origin_and_no_scope_word(home):
    rows = load_map(build_inventory(home), None)
    assert all(c.origin is None for r in rows for c in r.cells.values())
    assert all(c.where != "global settings" for r in rows for c in r.cells.values())


def test_the_medium_sample_has_a_project_override(tmp_path):
    home = build_demo_home(tmp_path, "medium")  # Part 1: atlas/.mcp.json overrides the user docs
    rows = load_map(build_inventory(home), str(home / "work/atlas"))
    docs = rows_by(rows, "mcp_server", "docs").cells["claude_code"]
    assert (docs.where, docs.origin) == ("project override", "override")
```

Update the pins that held the old scope word: `test_cell_states_for_the_website_project`
(`("off", "project override")`), `test_cursor_loading_a_plugin_twice…` (`own…where` is `None`),
`test_cross_loaded_cells_say_via_which_client` (`claude_code` where is `None`), the key set in
`test_raw_names_are_returned_unchanged` (adds `"origin"`), and in `tests/unit/test_library.py` the
two `"global settings"` asserts (now `None`).

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_load_map.py -q` → FAIL.
- [ ] **Step 3: Implement** the rule above; `overrides` is one set built next to `winners` in
  `load_map`, passed to `_cell`.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_load_map.py tests/unit/test_library.py tests/unit/test_api_views.py tests/unit/test_explain.py -q` → PASS.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/views/load_map.py src/kitden/views/words.py src/kitden/views/library.py \
  docs/design.md tests/unit/test_load_map.py tests/unit/test_library.py
git commit -m "Library: a cell says this project or project override when that decides"
```

---

### Task 3: Unknown when Kitden could not read (2.3, first part)

A client whose scan failed keeps its column; a file that failed on its first read is named
above the table; no add goes into a client while one of its files cannot be read.

**Files:**
- Modify: `src/kitden/views/words.py` (`STATE_WORDS["unread"] = "Could not read"`,
  `CLIENT_UNREAD = "Could not read {}."`, `NOT_SHOWN = "Could not read {}; its items are not shown."`,
  `NO_ADD_UNREAD = "Can't add while {} can't be read."`)
- Modify: `src/kitden/views/load_map.py` (`Cell.reason`; a client with `ClientStatus.UNREADABLE`
  gets `"unk"` cells), `src/kitden/views/library.py` (columns, unread cells, read notes, held adds,
  `_add_file`), `src/kitden/web/app.py` (`preview`: refuse a step into a file that failed to read)
- Modify: `src/kitden/web/static/js/parts.js` (`STATE_WORDS.unread`),
  `src/kitden/web/static/js/library.js` (`buildTable`: `column.note` under the name),
  `src/kitden/web/static/js/overview.js` (`clientStatus`, used by `clientsCard`)
- Modify: `docs/design.md` (Library table: "Cell state" adds "Unknown" (dashed amber ring) says why
  in its hover text; "Column head": a client Kitden could not read keeps its column, with "Could
  not read" under its name; a new row "Read problem": one quiet line above the table per file that
  failed on its first read, "Could not read mcp.json; its items are not shown.", and no "+ Add"
  that would write into a settings file Kitden cannot read; adds into the client's other files
  stay)
- Test: `tests/unit/test_load_map.py`, `tests/unit/test_library.py`, `tests/unit/test_page_words.py`,
  `tests/frontend/overview.test.mjs`

**Interfaces:**
- Consumes: `build_demo_home` (Part 1; in the `medium` sample `~/work/website/.cursor/mcp.json` is
  cut short, problem `parse_error`).
- Produces: `Cell.reason: str | None = None` (in `map_dict` as `"reason"`; `library._map_cell`
  copies it into the Library cell). An UNREADABLE client's
  cells are computed from its items as for a found one (Task 4 brings kept items), and any
  `"none"` result becomes `Cell("unk", reason=CLIENT_UNREAD.format(NAMES[client]))`;
  NOT_FOUND stays `"missing"`.
- Produces (Library answer): `columns` lists found and unreadable clients in `COLUMNS` order, each
  with `"note": STATE_WORDS["unread"]` for an unreadable one, else `None`. Builders still work on
  found clients only; one pass after them gives each row a cell per unreadable client (the load map
  row's cell when the row has one, else `_cell("unk", reason=…)`), never an add, and an unreadable
  column never makes a row visible.
- Produces: `notes` starts with one `NOT_SHOWN.format(<file name>)` per read problem in this view
  (deduped by text). Builder call: a problem is in this view when it has a path and that path is
  not inside the folder of a known project (`inventory.projects`) other than the picked one.
- Produces: held adds. Owner ruling (2026-10-22): a file Kitden could not read holds only the
  adds that would write into that file. `_add_file(adapters, client, add, project) -> str | None`
  (library.py): the settings file the add's step edits, from the same adapter step the preview
  builds (built, never run; one build per client, action and place, kept for the call). An
  `mcp.add` or `plugin.install` add whose file is a problem path (`inventory.problems`) becomes
  `reason=NO_ADD_UNREAD.format(<file name>)`. An add into a readable file stays offered, even
  while another file of the same client is broken: in `website`, Cursor's adds into
  `~/.cursor/mcp.json` stay; an add into `~/work/website/.cursor/mcp.json` is held. An add that
  lets the person choose this project or all projects is held only when both places are broken.
  Skill copies (`skill.install`, `plugin.skills`) stay; they write only folders.
- Produces: the preview refuses a step whose edit path is a problem path with the same
  sentence, `NO_ADD_UNREAD.format(<file name>)` (422; one check in `web/app.py preview` before
  the engine), so a place chosen after the add opens says it too. Part 4's Add missing lists such
  an add under "Kitden cannot add" with this sentence.
- Produces (JS, `overview.js`): `export function clientStatus(client) -> {state, word} | null` —
  `"unreadable"` → `{ state: "unk", word: STATE_WORDS.unread }`; not found → `{ state: "missing" }`;
  found with an untested version → `{ state: "unk", word: "Not tested" }`; else `null`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_library.py
class _BrokenCodex(CodexAdapter):
    def scan(self):
        raise ValueError("a format Kitden does not know")


def test_a_client_that_could_not_be_read_keeps_its_column_as_unknown(home):
    inventory = build_inventory(
        home, adapters=[ClaudeCodeAdapter(home), _BrokenCodex(home), CursorAdapter(home)]
    )
    rows = load_map(inventory, None)
    assert {r.cells["codex"].state for r in rows} == {"unk"}
    assert {r.cells["codex"].reason for r in rows} == {"Could not read Codex."}
    adapters = {a.id: a for a in default_adapters(home)}
    answer = library(inventory, adapters, None, gateway_registered=False, kind="mcp_server")
    assert [(c["id"], c["note"]) for c in answer["columns"]] == [
        ("claude_code", None), ("codex", "Could not read"), ("cursor", None)
    ]
    cells = [r["cells"]["codex"] for r in answer["rows"]]
    assert cells and all(c["state"] == "unk" and c["add"] is None for c in cells)


def test_no_add_goes_into_a_settings_file_that_could_not_be_read(home):
    (home / ".cursor/mcp.json").write_text("{ not json")
    answer = _library(home, "mcp_server")
    github = _row(answer, "github")["cells"]
    assert github["cursor"]["add"] is None  # its add writes into the broken file
    assert github["cursor"]["reason"] == "Can't add while mcp.json can't be read."
    assert github["codex"]["add"]["action"] == "mcp.add"  # Codex's own file reads well
    assert "Could not read mcp.json; its items are not shown." in answer["notes"]


def test_a_preview_into_a_file_that_could_not_be_read_says_why(home):
    (home / ".cursor/mcp.json").write_text("{ not json")
    with page_for(home) as page:
        github = next(i for i in page.get("/api/items?kind=mcp_server").json()
                      if (i["client"], i["name"]) == ("claude_code", "github"))
        body = {"action": "mcp.add", "targets": [{"client": "cursor"}], "params": {"item": github["id"]}}
        answer = page.post("/api/changes/preview", json=body, headers=POST)
    assert (answer.status_code, answer.json()) == (422, {"detail": "Can't add while mcp.json can't be read."})


def test_the_medium_sample_names_its_unreadable_file_above_the_table(tmp_path):
    home = build_demo_home(tmp_path, "medium")  # Part 1: work/website/.cursor/mcp.json is cut short
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}

    def answer(project):
        return library(inventory, adapters, project, gateway_registered=False, kind="mcp_server")

    website = answer(str(home / "work/website"))
    assert "Could not read mcp.json; its items are not shown." in website["notes"]
    # Cursor's add of github writes into ~/.cursor/mcp.json, which reads well: it stays offered.
    assert _row(website, "github")["cells"]["cursor"]["add"]["action"] == "mcp.add"
    # The file belongs to website, so All projects and the other projects do not name it.
    assert not any(n.startswith("Could not read mcp.json") for n in answer(None)["notes"])
```

(`page_for` and `POST` come from `tests/unit/test_local_gateway_views.py`.) Also:
`test_raw_names_are_returned_unchanged`'s key set adds `"reason"`; `test_page_words.py` gains
`"column.note" in script("library.js")`.

```js
// tests/frontend/overview.test.mjs
test('a client that could not be read says so, not Not installed', () => {
  assert.deepEqual(clientStatus({ status: 'unreadable' }), { state: 'unk', word: 'Could not read' });
  assert.deepEqual(clientStatus({ status: 'not_found' }), { state: 'missing' });
  assert.deepEqual(clientStatus({ status: 'found', version: '1.0', tested: false }), { state: 'unk', word: 'Not tested' });
  assert.equal(clientStatus({ status: 'found', version: '1.0', tested: true }), null);
});
```

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_library.py tests/unit/test_load_map.py -q`,
  `node --test tests/frontend/overview.test.mjs` → FAIL.
- [ ] **Step 3: Implement.** `ClientStatus.UNREADABLE` is already set by
  `views/inventory.py:_read` with a `SourceKind.MANAGED` problem (path `None`): that problem gives
  no note line (the column says it). A file name is `Path(problem.path).name`.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_library.py tests/unit/test_load_map.py tests/unit/test_overview.py tests/unit/test_page_words.py -q`
  and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/views/words.py src/kitden/views/load_map.py src/kitden/views/library.py \
  src/kitden/web/app.py src/kitden/web/static/js/parts.js src/kitden/web/static/js/library.js \
  src/kitden/web/static/js/overview.js docs/design.md tests/unit/test_load_map.py \
  tests/unit/test_library.py tests/unit/test_page_words.py tests/frontend/overview.test.mjs
git commit -m "Library: a client or file Kitden could not read is Unknown, not missing"
```

---

### Task 4: The last good read, kept in memory (2.3, second part)

**Files:**
- Modify: `src/kitden/model.py` (`Item.stale_at: str | None = None`, last field; not in `Item.id`)
- Modify: `src/kitden/views/inventory.py` (`LastGood`, `keep_last_good`)
- Modify: `src/kitden/web/app.py` (`create_app`: one `LastGood()`; `build_marked` calls
  `keep_last_good` right after `build(**options)`, before `mark_gateways`)
- Modify: `src/kitden/views/words.py` (`STALE = "From the last good read at {}"`),
  `src/kitden/views/load_map.py` (`Cell.stale_at`, the row flag), `src/kitden/views/library.py`
  (stale rows hold their adds; no `NOT_SHOWN` line for a file whose items are kept)
- Modify: `src/kitden/web/static/js/library.js` (`cellNode`: class `stale` when `cell.stale_at`),
  `src/kitden/web/static/style.css` (`.socket.stale .dot { border-style: dashed; }`)
- Modify: `docs/design.md` (Library table, "Cell state": a cell kept from the last good read has a
  dashed dot and its row's first flag says "From the last good read at 14:02")
- Test: `tests/unit/test_inventory.py`, `tests/unit/test_library.py`, `tests/unit/test_page_words.py`,
  `tests/frontend/library.test.mjs`

**Interfaces:**
- Produces: `Item.stale_at: str | None` (master plan name): ISO time of the last good read of a
  kept item.
- Produces: `@dataclass class LastGood: sources: dict[str, tuple[str, list[Item]]]` (source key →
  time read, items) and `projects: list[Project]`, both empty by default.
- Produces: `keep_last_good(inventory: Inventory, last: LastGood, now: str) -> Inventory` — adds
  the kept items to `inventory.items` and updates `last`. A source key is `item.source.path` for a
  file and `client:<id>` for a whole client (a problem with no path). Algorithm (the signature
  does not decide it):

```python
failed = {p.path or f"client:{p.owner_client}" for p in inventory.problems}
gone = {k.removeprefix("client:") for k in failed if k.startswith("client:")}
have = {i.id for i in inventory.items}
kept = [replace(i, stale_at=at, actions=())        # a kept item offers no action
        for key in failed if key in last.sources
        for at, items in [last.sources[key]] for i in items if i.id not in have]
fresh: dict[str, list[Item]] = {}
for item in inventory.items:
    fresh.setdefault(item.source.path or "", []).append(item)
    fresh.setdefault(f"client:{item.client}", []).append(item)
new = {k: (now, v) for k, v in fresh.items() if k and k not in failed}
for key, (at, items) in last.sources.items():      # a failed source, or a file of a failed client
    if key in failed or (items and items[0].client in gone):
        new.setdefault(key, (at, items))
last.sources = new
inventory.items += kept
if kept:                                            # a broken ~/.claude.json must not drop projects
    known = {p.path for p in inventory.projects}
    inventory.projects = sorted([*inventory.projects, *(p for p in last.projects if p.path not in known)], key=lambda p: p.path)
elif not failed:
    last.projects = list(inventory.projects)
return inventory
```

  Builder calls: a whole client's items are kept like a file's; a kept item has no actions (a
  Remove would be refused); while a source is kept, the project list of the last good read stays.
- Produces: `Cell.stale_at: str | None` (in `map_dict` and, through `_map_cell`, in the Library
  cell) — the earliest `stale_at` of the cell's items; a stale cell's
  `reason` is the flag text. A row with a stale cell gets the first flag
  `{"text": STALE.format(<HH:MM>), "level": "info"}`, the clock being
  `datetime.fromisoformat(at).astimezone().strftime("%H:%M")` (the page runs on this Mac). Adds
  follow Task 3's rule (owner ruling): only an add that writes into the file that broke is held,
  with `NO_ADD_UNREAD.format(<its name>)`; an add into another, readable file stays offered. A
  problem whose path has kept items gives no `NOT_SHOWN` line.
- `now` in `build_marked` is `datetime.now(UTC).isoformat(timespec="seconds")`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_inventory.py
AT, LATER = "2026-10-22T14:02:00+00:00", "2026-10-22T14:05:00+00:00"
# item(name, path, client="claude_code") and problem(path, client="claude_code") build an Item
# from a file source and a Reader-style unreadable Source.


def test_a_source_that_fails_keeps_its_last_good_items():
    last = LastGood()
    keep_last_good(Inventory(items=[item("github", "/h/.claude.json")]), last, AT)
    kept = keep_last_good(Inventory(problems=[problem("/h/.claude.json")]), last, LATER)
    assert [(i.name, i.stale_at, i.actions) for i in kept.items] == [("github", AT, ())]


def test_a_source_read_well_again_is_fresh():
    last = LastGood()
    keep_last_good(Inventory(items=[item("github", "/h/.claude.json")]), last, AT)
    keep_last_good(Inventory(problems=[problem("/h/.claude.json")]), last, LATER)
    again = keep_last_good(Inventory(items=[item("github", "/h/.claude.json")]), last, LATER)
    assert [i.stale_at for i in again.items] == [None]


def test_a_first_read_that_fails_keeps_nothing():
    assert keep_last_good(Inventory(problems=[problem("/h/.claude.json")]), LastGood(), AT).items == []


def test_a_file_emptied_on_purpose_does_not_come_back():
    last = LastGood()
    keep_last_good(Inventory(items=[item("github", "/h/.claude.json")]), last, AT)
    keep_last_good(Inventory(), last, AT)
    assert keep_last_good(Inventory(problems=[problem("/h/.claude.json")]), last, LATER).items == []


def test_a_client_that_fails_keeps_its_items_and_the_projects():
    last = LastGood()
    keep_last_good(Inventory(items=[item("neon", "/h/.codex/config.toml", "codex")],
                             projects=[Project("/h/work/api", True)]), last, AT)
    kept = keep_last_good(Inventory(problems=[problem(None, "codex")]), last, LATER)
    assert [(i.name, i.stale_at) for i in kept.items] == [("neon", AT)]
    assert [p.path for p in kept.projects] == ["/h/work/api"]
```

```python
# tests/unit/test_library.py
def test_a_file_that_breaks_keeps_its_items_from_the_last_good_read(home):
    with page_for(home) as page:
        before = page.get("/api/library?kind=mcp_server").json()
        assert _row(before, "github")["cells"]["claude_code"]["state"] == "on"
        (home / ".claude.json").write_text("{ broken")
        page.post("/api/rescan", headers=POST)
        answer = page.get("/api/library?kind=mcp_server").json()
    row = _row(answer, "github")
    assert row["cells"]["claude_code"]["state"] == "on" and row["cells"]["claude_code"]["stale_at"]
    assert row["flags"][0]["text"].startswith("From the last good read at ")
    neon = _row(answer, "neon")["cells"]["claude_code"]  # Claude Code lacks neon; its add writes .claude.json
    assert neon["add"] is None and neon["reason"] == "Can't add while .claude.json can't be read."
    assert not any(n.startswith("Could not read .claude.json") for n in answer["notes"])
```

(`page_for` and `POST` come from `tests/unit/test_local_gateway_views.py`.)

```js
// tests/frontend/library.test.mjs
test('a cell kept from the last good read is marked and says when', () => {
  const words = 'From the last good read at 14:02';
  const node = cellNode({ key: 'k', name: 'github', cells: { codex: cell({ state: 'on', stale_at: '2026-10-22T14:02:00+00:00', reason: words }) } }, 'codex');
  assert.ok(node.classList.contains('stale'));
  assert.equal(node.title, words);
});
```

`test_page_words.py`: `".socket.stale .dot { border-style: dashed; }" in CSS`. The key set in
`test_raw_names_are_returned_unchanged` adds `"stale_at"`.

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_inventory.py tests/unit/test_library.py -q`,
  `node --test tests/frontend/library.test.mjs` → FAIL.
- [ ] **Step 3: Implement** as the Interfaces say.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_inventory.py tests/unit/test_library.py tests/unit/test_load_map.py tests/unit/test_mcp_server.py tests/unit/test_api_read.py tests/security -q`
  and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/model.py src/kitden/views/inventory.py src/kitden/web/app.py src/kitden/views/words.py \
  src/kitden/views/load_map.py src/kitden/views/library.py src/kitden/web/static/js/library.js \
  src/kitden/web/static/style.css docs/design.md tests/unit/test_inventory.py tests/unit/test_library.py \
  tests/unit/test_load_map.py tests/unit/test_page_words.py tests/frontend/library.test.mjs
git commit -m "Library: a file that breaks keeps its items from the last good read"
```

---

### Task 5: Needs review for a same name from another source (2.3, third part)

**Files:**
- Create: `src/kitden/views/match.py`
- Modify: `src/kitden/views/skills.py` (`skill_digest`), `src/kitden/changes/align.py` (`_source`
  and `SERVER_FIELDS` move to `match.py`; `_not_same` uses `source_key`)
- Modify: `src/kitden/views/words.py` (`STATE_WORDS["review"] = "Needs review"`,
  `NOT_SAME = "Same name, from another source."`), `src/kitden/views/load_map.py` (review pass),
  `src/kitden/views/library.py` (`_skill_rows`/`_skill_cell`: a catalog skill against the client's
  own)
- Modify: `src/kitden/web/static/js/parts.js` (`STATE_WORDS.review`), `src/kitden/web/static/style.css`
  (`.s-review`), `src/kitden/web/static/js/panel.js` (`loadsLede`), `src/kitden/web/static/js/overview.js`
  (`loadCounts` counts `"review"` with `"on"` and `"gw"`)
- Modify: `docs/design.md` (Library table, "Cell state": "Needs review" (amber ring, small dot) is
  a same-name item from another source: another command, address or skill files)
- Test: `tests/unit/test_match.py` (new), `tests/unit/test_load_map.py`, `tests/unit/test_library.py`,
  `tests/unit/test_align.py` (unchanged, must pass), `tests/unit/test_page_words.py`,
  `tests/frontend/panel.test.mjs`, `tests/frontend/overview.test.mjs`

**Interfaces:**
- Consumes: `build_demo_home` (Part 1; in the `medium` sample `docs` is Claude Code's
  `https://docs.example.test/mcp` and Codex's `npx docs-mcp`, both loading for all projects).
- Produces (`kitden.views.match`): `SERVER_FIELDS = ("command", "args", "url")`;
  `source_key(item: Item) -> object` — an MCP server: its `summary` pairs in `SERVER_FIELDS` (as
  `align._source` today); a skill: `folder_key(<folder of its SKILL.md>)`; anything else:
  `item.name`. `folder_key(folder: Path) -> str` — `skill_digest` of the real folder, or the real
  folder's path when that is `None`. `odd_ones(keys: dict[str, frozenset]) -> set[str]`:

```python
values = list(keys.values())
if len(set(values)) < 2:
    return set()
counts = Counter(values)
reference = max(values, key=lambda k: (counts[k], -values.index(k)))  # tie: first client
return {client for client, k in keys.items() if k.isdisjoint(reference)}
```

- Produces (`kitden.views.skills`): `skill_digest(folder: Path) -> str | None` —
  `copy_folder.digest` of the real folder, cached like `read_skill` (same `_signature` check);
  `None` when `list_files` refuses or the folder cannot be read.
- Builder call (spec 2.3 says "skill real path"): skills match by their files, so a folder Kitden
  copied is the same skill; the real path alone would mark every copy as Needs review.
- Produces: `Cell.state == "review"` (master plan name). Pass in `load_map` after the cells: for
  rows of kind MCP server or skill, the keys per column are `frozenset(source_key(i))` over the
  items of each `"on"` cell, leaving out items with `via_gateway`, the setup entry (`SETUP_NAME`),
  `Scope.ACCOUNT` and the Desktop client; each client in `odd_ones` gets
  `state="review", reason=NOT_SAME`. Builder call: only `"on"` cells are compared and marked; the
  odd one is the client with no source in common with the most common one (a tie keeps the first
  column), so one client's duplicate copy is never review.
- Produces (Library skill rows): when a client has the row (`_has`) and its map cell is `"on"`,
  the cell is `"review"` with `NOT_SAME` unless one of its items' `source_key` equals
  `folder_key(Path(skill["path"]))`. A review cell has no add.
- Produces (JS): `STATE_WORDS.review = "Needs review"`;
  `.s-review { color: var(--lamp-warn); } .s-review .dot::after { transform: scale(0.5); border-radius: 50%; }`
  (an amber ring with a small dot, apart from Unknown's dashed ring); `loadsLede` adds the line
  `Needs review in <clients>: same name, another source.` after the Loads line.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_match.py
def test_the_odd_one_needs_review_and_a_tie_keeps_the_first():
    a, b = frozenset({"a"}), frozenset({"b"})
    assert odd_ones({"claude_code": a, "codex": b, "cursor": b}) == {"claude_code"}
    assert odd_ones({"claude_code": a, "codex": b}) == {"codex"}
    assert odd_ones({"claude_code": frozenset({"a", "b"}), "codex": b}) == set()
    assert odd_ones({"claude_code": a, "codex": a}) == set()
```

```python
# tests/unit/test_load_map.py  (add_claude, add_cursor from tests/unit/test_local_gateway_move.py)
def test_a_same_name_server_from_another_source_needs_review(home):
    add_claude(home, "neon", {"type": "http", "url": "https://other.invalid/mcp"})
    neon = rows_by(load_map(build_inventory(home), None), "mcp_server", "neon")
    assert (neon.cells["claude_code"].state, neon.cells["codex"].state) == ("on", "review")
    assert neon.cells["codex"].reason == "Same name, from another source."


def test_the_two_that_agree_stay_and_the_odd_one_needs_review(home):
    add_claude(home, "neon", {"type": "http", "url": "https://other.invalid/mcp"})
    add_cursor(home, "neon", {"url": "https://mcp.neon.tech/mcp"})  # loads: not turned off in Cursor
    neon = rows_by(load_map(build_inventory(home), None), "mcp_server", "neon")
    assert {c: neon.cells[c].state for c in COLUMNS} == {"claude_code": "review", "codex": "on", "cursor": "on"}


def test_a_copied_skill_is_the_same_skill(home):
    shutil.copytree(home / ".claude/skills/brandkit", home / ".codex/skills/brandkit")
    row = rows_by(load_map(build_inventory(home), None), "skill", "brandkit")
    assert "review" not in {c.state for c in row.cells.values()}


def test_a_same_name_skill_with_other_files_needs_review(home):
    folder = home / ".codex/skills/brandkit"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("---\nname: brandkit\n---\nSomething else.\n")
    row = rows_by(load_map(build_inventory(home), None), "skill", "brandkit")
    assert row.cells["codex"].state == "review"


def test_a_duplicate_in_one_client_is_not_review(home):
    row = rows_by(load_map(build_inventory(home), None), "skill", "docker-expert")
    assert "review" not in {c.state for c in row.cells.values()}
```

```python
# tests/unit/test_library.py
def test_a_marketplace_skill_named_like_a_clients_own_is_not_shown_as_loaded(home):
    add_skills_marketplace(home)
    _skill(home / ".codex/skills", "tidy", "Not the toolbox one.")
    tidy = _row(_library(home, "skill", show="all"), "tidy")
    assert tidy["cells"]["codex"]["state"] == "review" and tidy["cells"]["codex"]["add"] is None


def test_review_cells_on_the_medium_sample_offer_no_add(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    answer = library(build_inventory(home), {a.id: a for a in default_adapters(home)}, None,
                     gateway_registered=False, kind="mcp_server")
    docs = _row(answer, "docs")["cells"]  # Part 1: same name, two sources; a tie keeps Claude Code
    assert (docs["claude_code"]["state"], docs["codex"]["state"]) == ("on", "review")
    review = [c for r in answer["rows"] for c in r["cells"].values() if c["state"] == "review"]
    assert all(c["add"] is None for c in review)
```

```js
// tests/frontend/panel.test.mjs (inside the loadsLede test, with its lede() helper)
assert.equal(lede({ claude_code: 'on', codex: 'review' }), 'Loads in Claude Code. Needs review in Codex: same name, another source.');
// tests/frontend/overview.test.mjs
test('a client whose same-name item needs review still counts it', () => {
  const rows = [{ kind: 'mcp_server', cells: { codex: { state: 'review' } } }];
  assert.deepEqual(loadCounts(rows, 'codex'), [['mcp_server', 1, '1 MCP server']]);
});
```

`test_page_words.py`: the `.s-review` rule is in CSS. `test_python_and_page_state_words_agree`
now covers `review`.

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_match.py tests/unit/test_load_map.py tests/unit/test_library.py -q`,
  `node --test tests/frontend/panel.test.mjs tests/frontend/overview.test.mjs` → FAIL.
- [ ] **Step 3: Implement.** `load_map` imports from `match.py` (no import of `changes.align`, which
  would loop through `views`). Only rows where two or more columns are `"on"` are compared, so
  `skill_digest` runs for few folders.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_match.py tests/unit/test_load_map.py tests/unit/test_library.py tests/unit/test_align.py tests/unit/test_skills_catalog.py tests/unit/test_page_words.py -q`
  and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/views/match.py src/kitden/views/skills.py src/kitden/changes/align.py \
  src/kitden/views/words.py src/kitden/views/load_map.py src/kitden/views/library.py \
  src/kitden/web/static/js/parts.js src/kitden/web/static/style.css src/kitden/web/static/js/panel.js \
  src/kitden/web/static/js/overview.js docs/design.md tests/unit/test_match.py tests/unit/test_load_map.py \
  tests/unit/test_library.py tests/unit/test_page_words.py tests/frontend/panel.test.mjs tests/frontend/overview.test.mjs
git commit -m "Library: Needs review for a same name from another source"
```

---

### Task 6: Every add names its scope; a removed project is said (2.4)

**Files:**
- Modify: `src/kitden/web/static/js/panel.js` (`changeWords`; `showReview` lede via `reviewLede`)
- Modify: `src/kitden/web/static/js/library.js` (`startAdd` body, `scopeLine`, `loadLibrary` skips
  a gone project), `src/kitden/web/static/js/offer.js` (`PROJECT_NOTE`), `src/kitden/views/library.py`
  (`_cursor_in_project` and `_no_skill_place` hints)
- Modify: `src/kitden/web/static/js/store.js` (`loadShared` keeps the project; `projectGone`;
  `reload` reads no project data for a gone project), `src/kitden/web/static/js/parts.js`
  (`GONE_PROJECT`), `src/kitden/web/static/js/app.js` (`renderPlace`, `renderShell` picker)
- Modify: `docs/design.md` (Components, two lines: a picked project that leaves the list stays
  picked while Overview, Library and Gateway say "This project is no longer on the list."; an
  add's review names its scope in the title ("… for all projects", "… in website") and, with All
  projects picked, in the lede)
- Test: `tests/frontend/panel.test.mjs`, `tests/frontend/library.test.mjs`, `tests/frontend/offer.test.mjs`,
  `tests/frontend/store.test.mjs`, `tests/unit/test_page_words.py`, `tests/unit/test_project_add.py`

**Interfaces:**
- Produces (`panel.js`): `export const ADDS = ["mcp.add", "skill.install", "plugin.install", "plugin.skills"]`;
  `export function addScope(action, into) -> string | null` — `null` when `action` is not in
  `ADDS`, `` ` in ${projectLabel(into)}` `` with a project, else `" for all projects"`.
  `changeWords` appends it to the title and to `done` (replacing today's
  skill/plugin-only " in <folder>"; the restart notes still follow `done`).
  `export function reviewLede(action, picked) -> string`: `"Adds for all projects. "` first when
  `action` is in `ADDS` and `picked` is empty, then
  `"Nothing is written until you press Apply. A backup is kept, so you can undo."`. Builder call:
  in a project the existing note callout already says the scope, so the lede does not repeat it.
- Words: "all your projects" becomes "all projects" everywhere: `startAdd` (`… only, or in all projects.`),
  `scopeLine` (`An Add asks: this project, or all projects. Adds without that choice go to all projects.`
  and `Adding puts an item in all projects.`), `PROJECT_NOTE = "Adds for all projects."`, the
  Cursor hint `Adds its skills for all projects. {CURSOR_PROJECT}` and the Codex hint
  `Adds for all projects. To add it to {name} only, trust {name} in Codex first.`
- Produces (`store.js`): `export function projectGone() -> boolean` — a project is picked,
  `data.projects` is read, and the project is not in it. `loadShared` no longer resets the project.
  `reload` reads only shared data and `/api/setup-server` while `projectGone()`; `loadLibrary`
  returns at once.
- Produces (`parts.js`): `export const GONE_PROJECT = "This project is no longer on the list.";`.
  `renderPlace` draws, for Overview, Library and Gateway while `projectGone()`, the place's `h1` and
  one `callout` (`role="note"`) with `GONE_PROJECT`, instead of the place. Changes and Agents draw
  as usual. Builder call: the picker keeps one extra selected option, "No longer on the list", with
  the gone project's id, so it never shows All projects for it; picking another project is the way
  out.

- [ ] **Step 1: Write the failing tests**

```js
// tests/frontend/panel.test.mjs
test('an add names its scope in the title and, with All projects, in the lede', () => {
  const add = { action: 'skill.install', steps: [{ client: 'codex', name: 'tidy' }] };
  assert.deepEqual(changeWords(add, { params: { skill: 'x' } }), { title: 'Add tidy to Codex for all projects', done: 'Added tidy to Codex for all projects' });
  assert.equal(changeWords({ action: 'mcp.add', steps: [{ client: 'codex', name: 'github' }] }).title, 'Add github to Codex for all projects');
  assert.equal(reviewLede('mcp.add', ''), 'Adds for all projects. Nothing is written until you press Apply. A backup is kept, so you can undo.');
  assert.equal(reviewLede('mcp.add', 'p1'), 'Nothing is written until you press Apply. A backup is kept, so you can undo.');
  assert.equal(reviewLede('plugin.disable', ''), 'Nothing is written until you press Apply. A backup is kept, so you can undo.');
});

test('an add into a known project on another disk names that project', () => {
  data.projects = [{ id: 'p9', path: '/Volumes/Other/site' }];
  const add = { action: 'skill.install', steps: [{ client: 'codex', name: 'tidy' }] };
  assert.equal(changeWords(add, { params: { skill: 'x', project: 'p9' } }).title, 'Add tidy to Codex in site');
  data.projects = null;
});
```

Update the `changeWords` pins that now end in ` for all projects` (the `tidy` add without a
project, `mcp.add`, the plugin skills title and `done`). Update every "all your projects" pin in
`library.test.mjs`, `offer.test.mjs`, `test_page_words.py` and `tests/unit/test_project_add.py`
to the new words, and pin `"Adds for all projects. "`, `GONE_PROJECT` and `"No longer on the list"`
(in `app.js`) in `test_page_words.py`.

```js
// tests/frontend/store.test.mjs (the fetch stub also records each url in `asked`)
test('a project no longer on the list stays picked and is said', async () => {
  asked.length = 0;
  state.project = 'gone';
  await reload();
  assert.equal(state.project, 'gone');
  assert.equal(projectGone(), true);
  assert.ok(!asked.some((url) => url.includes('project=gone')));
  state.project = 'a';
  assert.equal(projectGone(), false);
});
```

```python
# tests/unit/test_project_add.py — master plan Review Focus 1, with Part 1's write boundary
def test_a_skill_add_into_a_known_project_on_another_disk_previews(tmp_path):
    # A project outside the home folder, known to Claude Code (its .claude.json "projects"):
    # a skill.install preview with that project's id answers 200 and every step's path is in it.
```

(Build it as this file's other project-add tests do, with the project at `tmp_path / "other-disk/site"`.)

- [ ] **Step 2: Run them to see them fail**: `node --test tests/frontend/*.test.mjs`,
  `uv run pytest tests/unit/test_page_words.py tests/unit/test_project_add.py -q` → FAIL.
- [ ] **Step 3: Implement.** `showReview` calls `reviewLede(change.action, state.project)` for the
  header lede.
- [ ] **Step 4: Run** the same commands → PASS.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/web/static/js/panel.js src/kitden/web/static/js/library.js src/kitden/web/static/js/offer.js \
  src/kitden/views/library.py src/kitden/web/static/js/store.js src/kitden/web/static/js/parts.js \
  src/kitden/web/static/js/app.js docs/design.md tests/frontend/panel.test.mjs tests/frontend/library.test.mjs \
  tests/frontend/offer.test.mjs tests/frontend/store.test.mjs tests/unit/test_page_words.py tests/unit/test_project_add.py
git commit -m "Reviews name the scope of an add; a removed project is said, not swapped"
```

---

### Task 7: The selection in the address: Overview and Library (2.5, first part)

**Files:**
- Modify: `src/kitden/web/static/js/store.js` (selection, `goTo`, arrival, `parseHash`, `hashFor`,
  `followAddress`)
- Modify: `src/kitden/web/static/js/app.js` (`start`, `fromAddress`, `openPlace`)
- Modify: `src/kitden/web/static/js/library.js` (`rowSel`, `rowFor`; `buildRow`, `openRow`,
  `openOffer`, `renderLibrary` use them; `openSelectedOnRender` and `openNext` go)
- Modify: `src/kitden/web/static/js/panel.js` (`closePanel` clears the selection through
  `setState`; `openPanel`'s `openerKey` falls back to the row marked `aria-selected`)
- Modify: `src/kitden/web/static/js/overview.js` (`targetSel`; `follow` uses `goTo`),
  `src/kitden/views/overview.py` (`_duplicates` target `{"view": "map", "kind": kind, "name": <first item's name>}`, no `"row"`)
- Modify: `docs/design.md` (Components: the address keeps the project and the selected item
  (`sel=<kind>:<name>`) on every page, and the Library opens that row's Details once)
- Test: `tests/frontend/store.test.mjs`, `tests/frontend/library.test.mjs`, `tests/frontend/overview.test.mjs`,
  `tests/unit/test_overview.py`

**Interfaces:**
- Produces (`store.js`, master plan names): `parseSel(text) -> {kind, name} | null` — `kind` is one
  of `SEL_KINDS = ["mcp_server", "plugin", "skill", "hook", "marketplace", "instructions"]`, split at
  the first ":", `name` not empty; `selFor(selected) -> string` (`""` for `null`).
  Also `sameSel(a, b) -> boolean`.
- `state.selected` is `{kind, name} | null` (was a row key). `parseHash` returns
  `selected: parseSel(params.get("sel"))`; `hashFor` writes `sel` last, on every view:
  `#library?kind=mcp_server&project=a&sel=mcp_server%3Agithub`. `OLD_VIEWS` and the `#map` redirect
  stay as they are.
- Produces: `goTo(view: string, selected: {kind, name} | null)` (master plan name). Builder call:
  it lives in `store.js`, not `app.js`: `app.js` starts the page when imported, so page modules
  and node tests cannot import it. It sets `arrival.pending = Boolean(selected)` and calls
  `go(view, { selected, ...(view === "library" && selected ? libraryChoice(selected) : {}) })`.
- Produces: `export const arrival = { pending: false }`; `takeArrival() -> {kind, name} | null` —
  `state.selected` when pending, else `null`; always clears `pending` (so a redraw never opens
  Details again and takes focus). `libraryChoice(selected) -> { kind: selected.kind, show: "mine", category: "", attention: false, q: "" }`
  (Builder call: what the Overview cards use today).
- `followAddress(next)` keeps `next.selected` and sets `arrival.pending = Boolean(next.selected)`;
  `fromAddress` compares `selFor` too; `start` sets `arrival.pending` from the first address;
  `openPlace(view)` reads `libraryChoice(state.selected)` first when it has one, then
  `goTo(view, state.selected)`. The project picker still clears the selection.
- Produces (`library.js`): `rowSel(row) -> {kind: row.kind, name: row.lookup || row.offer || row.name}`;
  `rowFor(rows, selected) -> row | null` (first match; Builder call: `sel=instructions:review`
  opens the first row of that name). `openRow` calls `setState({ selected: rowSel(row) })`
  (replaces the address entry). `renderLibrary` opens `rowFor(answer.rows, takeArrival())` only
  when its answer is fresh, with the `.arrive` glow as today.
- Produces (`overview.js`): `targetSel(target) -> {kind, name} | null` from a card target
  (`{view: "map", kind, name}`); `follow` reads `libraryChoice(sel)` first, then `goTo("library", sel)`.

- [ ] **Step 1: Write the failing tests**

```js
// tests/frontend/store.test.mjs
test('parseSel takes only kind:name', () => {
  assert.deepEqual(parseSel('mcp_server:github'), { kind: 'mcp_server', name: 'github' });
  assert.deepEqual(parseSel('mcp_server:a:b'), { kind: 'mcp_server', name: 'a:b' });
  for (const bad of [null, '', 'nope', 'mcp_server:', 'wizard:x', ':github']) assert.equal(parseSel(bad), null);
  assert.equal(selFor(null), '');
  assert.equal(selFor({ kind: 'skill', name: 'tidy' }), 'skill:tidy');
});

test('every place writes the selection and the project into the address', () => {
  const s = { ...parseHash('#gateway?project=a&sel=mcp_server%3Agithub') };
  assert.deepEqual(s.selected, { kind: 'mcp_server', name: 'github' });
  assert.equal(hashFor(s), '#gateway?project=a&sel=mcp_server%3Agithub');
  assert.equal(hashFor({ ...s, view: 'library', kind: 'mcp_server', show: 'mine' }), '#library?kind=mcp_server&project=a&sel=mcp_server%3Agithub');
});

test('an arrival opens once', () => {
  goTo('library', { kind: 'skill', name: 'tidy' });
  assert.equal(state.kind, 'skill');
  assert.deepEqual(takeArrival(), { kind: 'skill', name: 'tidy' });
  assert.equal(takeArrival(), null);
});
```

```js
// tests/frontend/library.test.mjs
test('the selection finds its row by kind and full name, and nothing when it is gone', () => {
  const rows = [{ key: 'k1', kind: 'plugin', name: 'figma', lookup: 'figma@a' }, { key: 'k2', kind: 'plugin', name: 'figma', lookup: 'figma@b' }];
  assert.equal(rowFor(rows, { kind: 'plugin', name: 'figma@b' }).key, 'k2');
  assert.equal(rowFor(rows, { kind: 'skill', name: 'figma@b' }), null);
  assert.equal(rowFor(rows, { kind: 'plugin', name: 'gone@a' }), null);
  assert.equal(rowFor(rows, null), null);
  assert.deepEqual(rowSel(rows[0]), { kind: 'plugin', name: 'figma@a' });
});
```

`store.test.mjs` gains `globalThis.document = { getElementById: () => ({}) }` (a place change draws
through `transition`). Add `selected: null` to the `library()` helper of `old map and discover addresses open the Library`
(its other asserts stay: `#map` still opens the Library).

```js
// tests/frontend/overview.test.mjs
test('a card about an item selects it by kind and name', () => {
  assert.deepEqual(targetSel({ view: 'map', kind: 'skill', name: 'tidy' }), { kind: 'skill', name: 'tidy' });
  assert.equal(targetSel({ view: 'agents' }), null);
});
```

`tests/unit/test_overview.py`: the duplicate card's `target` is
`{"view": "map", "kind": …, "name": by_id[twice.items[0]].name}` and that name is the `lookup` of
a `load_map(inventory, None)` row.

- [ ] **Step 2: Run them to see them fail**: `node --test tests/frontend/*.test.mjs`,
  `uv run pytest tests/unit/test_overview.py -q` → FAIL.
- [ ] **Step 3: Implement** as the Interfaces say.
- [ ] **Step 4: Run** the same commands → PASS.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/web/static/js/store.js src/kitden/web/static/js/app.js src/kitden/web/static/js/library.js \
  src/kitden/web/static/js/panel.js src/kitden/web/static/js/overview.js src/kitden/views/overview.py \
  docs/design.md tests/frontend/store.test.mjs tests/frontend/library.test.mjs tests/frontend/overview.test.mjs tests/unit/test_overview.py
git commit -m "The address keeps the selected item; the Library opens its Details"
```

---

### Task 8: The Gateway opens the selected server; one walk across the pages (2.5, Done)

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (`serverFor`; `showServer` sets the selection;
  `renderGateway` takes the arrival)
- Create: `tests/frontend/context.test.mjs`
- Modify: `docs/design.md` (the Components line of Task 7 adds: the Gateway opens the selected
  server's Details once)
- Test: `tests/frontend/gateway.test.mjs`

**Interfaces:**
- Consumes: `goTo`, `takeArrival`, `parseHash`, `followAddress`, `state` (`store.js`, Task 7);
  `rowFor`, `rowSel` (`library.js`); `targetSel` (`overview.js`).
- Produces (`gateway.js`): `export function serverFor(map, selected) -> row | null` — the map row of
  kind `mcp_server` whose `name` is `selected.name`; `null` for another kind, no map or no row.
  `showServer(name)` calls `setState({ selected: { kind: "mcp_server", name } })` before
  `openItem`. After `renderGateway` draws its model it takes the arrival: with a target, it loads
  the map if needed and opens `serverFor(...)` with `openItem`; without a row it opens nothing and
  says nothing. Builder call: a selection of another kind stays in the address for the next page.

- [ ] **Step 1: Write the failing tests**

```js
// tests/frontend/gateway.test.mjs
test('the Gateway opens only a selected server', () => {
  const map = { rows: [{ kind: 'mcp_server', name: 'github' }, { kind: 'skill', name: 'github' }] };
  assert.equal(serverFor(map, { kind: 'mcp_server', name: 'github' }), map.rows[0]);
  assert.equal(serverFor(map, { kind: 'skill', name: 'github' }), null);
  assert.equal(serverFor(map, { kind: 'mcp_server', name: 'gone' }), null);
  assert.equal(serverFor(null, { kind: 'mcp_server', name: 'github' }), null);
});
```

```js
// tests/frontend/context.test.mjs — stubs: matchMedia; delete navigator; document { createElement,
// getElementById: () => ({}), querySelector: () => null, addEventListener() {} };
// history { pushState, replaceState } push each url into `addresses`.
test('one project and one selection go from Overview to Library to Gateway, and Back returns', () => {
  const rows = [{ key: 'row-github', kind: 'mcp_server', name: 'github', lookup: 'github' }];
  Object.assign(state, parseHash('#overview?project=a'));
  goTo('library', targetSel({ view: 'map', kind: 'mcp_server', name: 'github' }));
  assert.equal(addresses.at(-1), '#library?kind=mcp_server&project=a&sel=mcp_server%3Agithub');
  const opened = rowFor(rows, takeArrival());
  assert.equal(opened.key, 'row-github');                          // Details opens for this row
  assert.deepEqual(rowSel(opened), state.selected);                // the row focus returns to
  assert.equal(takeArrival(), null);                               // a redraw keeps focus in Details
  goTo('gateway', state.selected);                                 // the rail link keeps both
  assert.equal(addresses.at(-1), '#gateway?project=a&sel=mcp_server%3Agithub');
  assert.equal(serverFor({ rows }, takeArrival()).name, 'github');
  followAddress(parseHash(addresses.at(-2)));                      // Back
  assert.equal(state.view, 'library');
  assert.equal(state.project, 'a');
  assert.deepEqual(takeArrival(), { kind: 'mcp_server', name: 'github' });
});
```

- [ ] **Step 2: Run them to see them fail**: `node --test tests/frontend/gateway.test.mjs tests/frontend/context.test.mjs` → FAIL.
- [ ] **Step 3: Implement** as the Interfaces say.
- [ ] **Step 4: Run** `node --test tests/frontend/*.test.mjs` → PASS. Then on the `medium` demo
  (`uv run kitden demo --size medium`): open a server from an Overview card, go to Gateway by the
  rail, press Back; the address, the open Details and the project match each time. Note it in the
  task report.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/web/static/js/gateway.js docs/design.md tests/frontend/gateway.test.mjs tests/frontend/context.test.mjs
git commit -m "Gateway opens the selected server; a test walks the three pages"
```

---

### Task 9: Docs and roadmap for Part 2

**Files:**
- Modify: `docs/design.md`, `README.md`, `tests/unit/test_docs_words.py`
- `ROADMAP.md` only if the owner has committed their edit (see Step 3)

- [ ] **Step 1: Read `docs/design.md` through once.** Tasks 1–8 each wrote their lines with
  their page change (master Rules). Check the part's lines read as one voice with no repeats and
  that every new word is pinned; fix only what that reading finds.
- [ ] **Step 2: Update `README.md`** (Library section, after "Pick a project at the top to see what
  loads in that folder."): "All projects shows what every project shares; in a project, a cell
  says "this project" or "project override" when that decides it. "Unknown" means Kitden could not
  read where the item lives, never that it is missing; "Needs review" means another client has an
  item with the same name from another source. The address keeps the project and the item you
  opened, so a link or Back returns to it." Pin it:

```python
def test_readme_says_unknown_is_not_missing():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert '"Unknown" means Kitden could not read where the item lives, never that it is missing' in readme
```

  `docs/development.md` is unchanged: this part adds no real-client hand check.
- [ ] **Step 3: Roadmap.** If `git status` still shows `ROADMAP.md` modified by the owner, do not
  touch it; put this line in the report for "### Not released yet": "- **Shared words, scope and
  selection:** "All projects" on every page; a cell says "this project" or "project override";
  Unknown, Needs review and the last good read; every add names its scope; the project and the
  selected item stay in the address." Otherwise move Part 2's line from "## Planned" to
  "### Not released yet" with that text.
- [ ] **Step 4: Run all checks**: `uv run pytest -q && uv run ruff check . && uv run ruff format --check src tests && node --test tests/frontend/*.test.mjs`.
- [ ] **Step 5: Commit**

```bash
git add README.md tests/unit/test_docs_words.py
git commit -m "Docs: shared words, scope and selection"
```

(Add `docs/design.md` only when Step 1 changed it, and `ROADMAP.md` only when Step 3 edited it.)
