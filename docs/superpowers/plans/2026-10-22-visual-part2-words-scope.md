# Part 2: Shared words, scope and selection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every page speaks the same words: "Available" and "Off" in cells, "All projects" for the
shared baseline, a scope word on every cell of a project view with the route moved to the hover
text, Unknown and Needs review that never look like Missing or equal, "+ Add" wherever Kitden can
add (a project's own skill into that project), Overview notes grouped by item with their clients,
an add that names its scope before Apply, and a project and selected item that stay in the
address from page to page.

**Architecture:** The server keeps one table of words (`views/words.py`, twin of `parts.js
STATE_WORDS`). `load_map` gains cell facts (origin, route, reason, last good read) and a
`"review"` state built from one match module (`views/match.py`) that Add missing and the findings
share. The page server keeps the last good read of each source in memory (`keep_last_good`). On
the page, `store.js` carries `sel=<kind>:<name>` in every address and `goTo(view, selected)` opens
a place with the selection, which the Library and the Gateway open in Details once.

**Tech Stack:** Python 3.13, Starlette; plain ES modules, one CSS file; pytest on sandbox homes;
node's test runner. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-22-visual-management-design.md`, Part 2 (2.1–2.5, with
walkthrough 1's 2.2, 2.2a, 2.3, 2.3a), its Constraints, Anti-goals and Acceptance. Master plan:
`docs/superpowers/plans/2026-10-22-visual-management.md` (its Rules, "Names that cross part
boundaries" and "Walkthrough 1 rulings" bind this part). Walkthrough results:
`docs/research/walkthrough-2026-10-23.md`. Rulings: the "Preflight rulings" in
`.superpowers/sdd/2026-10-22-visual-part2-words-scope/progress.md`.

## Global Constraints

- `AGENTS.md` in full: code, comments, UI text and docs in simple English; tests on sandbox homes
  only (`make_home`, `write_cursor_fixture_state`, `build_demo_home`); never the real home, a real
  client command, a real MCP server, the Keychain or the network.
- Stack unchanged: Python 3.13, Starlette, MCP SDK 2.3, tomlkit, watchfiles; plain ES modules, one
  CSS file; no framework, no bundler, no library from another site; strict CSP. No new runtime
  dependency.
- Main pages show a name, the client, a state and an action. A file appears on a main page only
  by its name (`mcp.json`), never its path. The scope word on every cell of a project view is the
  owner's ruling (walkthrough 1, F3); the `where` slot already cuts with "…".
- `docs/design.md` governs look and motion. A changed word changes its pin in
  `tests/unit/test_page_words.py` (or the node test) and its `docs/design.md` line in the same
  commit (master Rules): each task below names its design.md lines. Task 11 writes the README and
  reads design.md through once.
- Sample facts come from Part 1's "Sample contract" (medium): the override is `docs` in
  `~/work/atlas`, the same-name server is `docs` (Claude Code and Codex), the unreadable file is
  `~/work/website/.cursor/mcp.json`; Codex's `api-style` skill is only in `~/work/atlas/.agents/skills`.
- Nothing moves while idle. A new look is a resting CSS style; no new animation.
- The last good read lives in memory only, never on disk (spec 2.3).
- `explain()`, `project_views()` and `finding_dict` feed the MCP server: a task that changes the
  inventory's items or the findings runs `tests/unit/test_mcp_server.py`; file lines never go to
  agents.
- No test posts `/api/rescan` on a sample (`build_demo_home`) outside `demo_page`: it would ask
  the servers the Kitden gateway holds for their tools. A test that rescans uses a fixture home
  with no held servers.
- A hand check runs `uv run kitden demo --size medium --no-browser` in the background, opens the
  printed link in the Browser pane, then stops the demo so its folder is deleted. Never `kitden
  open` or `kitden serve` on the real home.
- `ROADMAP.md`: while `git status` shows it modified by the owner, no task edits or stages it;
  Task 11 writes the roadmap lines into its report instead.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`,
  `node --test tests/frontend/*.test.mjs`. All pass or the commit waits.
- Commits stage files by name (never `git add -A`, `.` or `-a`); the message is a short plain
  subject, one to three simple lines, ending with the session's co-author line.
- Line numbers are hints; find code by name.
- Exact copy this part adds (spec 2.1–2.4 and walkthrough 1; "Builder" marks this plan's choice):

| Where | Words |
| --- | --- |
| Picker's empty choice, tools heading, Details scope | `All projects` (`ALL_PROJECTS` in `parts.js`) |
| Scope inside a sentence | `all projects`, `this project` |
| Cell states | `Available`, `Off`, `Unknown`, `Needs review`, `—` (After chips `Loads twice` and `Loads once` stay: they warn about a count) |
| Cell scope word in a project view (CSS adds the "· ") | `all projects`, `this project`, `project override`; none with All projects picked |
| Cell route: hover text and Details only | `through Codex's folder`, `through Claude Code's folder`, `from a plugin`, `through the Kitden gateway`, `from the Desktop app`; hover `<Route>. <reason>` with the first letter upper-cased (Builder) |
| Details lede | `Available in Claude Code and Codex.`, `Unknown in Codex.` (Builder, was "May load in"), `Needs review in Codex: same name, another source.`, `Not available here.` |
| Overview client counts with none | `Nothing available here.` |
| A client that could not be read | column note `Could not read`; cell reason `Could not read Codex.` |
| A file that failed on its first read | `Could not read mcp.json; its items are not shown.` |
| An item kept from the last good read | row flag `From the last good read at 14:02` |
| A change into a file that failed to read | an add: `Can't add while mcp.json can't be read.`; any other change: `Can't change this while settings.json can't be read.` |
| Needs review reason (Builder: the spec 2.3a phrase) | `Same name, another source.` |
| An empty cell of a Needs review row | `Same name, another source: decide first.` |
| Overview note for two sources | `Same name, another source` |
| A project-only MCP server's dash | `Kitden adds MCP servers for all projects only.` |
| A project skill add without its project | `This skill is in one project only. Pick that project to add it.` |
| A project skill for Codex in an untrusted project | `To add it to atlas, trust atlas in Codex first.` |
| Library line with a project's own skill to add | `This project's own skills add into this project.` |
| A project no longer known | `This project is no longer on the list.` |
| An add's review | title ends ` for all projects` (or ` in website`); lede starts `Adds for all projects.` with All projects picked |

## Review Focus

1. **A settings file that breaks while the page runs** (a stray comma in `~/.claude.json`): its
   items stay, marked "From the last good read at …", no "+ Add" into that file (adds into other,
   readable files stay), and no "its items are not shown" line (it would be false). Task 4,
   `test_a_file_that_breaks_keeps_its_items_from_the_last_good_read`.
2. **A client whose scan throws:** its column stays with "Could not read", every cell is Unknown
   with the reason, never "Not installed", "—" or "+ Add"; the Overview's client row says "Could
   not read". Task 3, `test_a_client_that_could_not_be_read_keeps_its_column_as_unknown` and the
   node test `a client that could not be read says so, not Not installed`.
3. **Same name, other source, against a plain copy or a newer version:** a server with another
   address and a skill with other files need review, and the other cells of that row offer no
   add; a skill folder Kitden copied, an item one client loads twice, and a plugin's own skill
   after its marketplace moved on do not. Task 5, `test_a_copied_skill_is_the_same_skill`,
   `test_a_duplicate_in_one_client_is_not_review`,
   `test_a_plugin_skill_is_not_review_after_the_marketplace_moves_on`.
4. **A picked project that leaves the list, or changes while a review is prepared:** it stays
   picked, the place says "This project is no longer on the list.", nothing is read or offered
   for it, the picker does not pretend All projects; a review that answers after the project
   changed opens nothing and is cancelled. Task 7, node tests `a project no longer on the list
   stays picked and is said` and `a review that answers after the project changed is dropped`.
5. **A broken or stale `sel` in the address** (`sel=nope`, `sel=mcp_server:`, `sel=wizard:x`, a
   removed item, a skill selected while on the Gateway, an old selection reached by Back): nothing
   opens unasked, nothing fails, the list shows; a selection the page cannot open stays for the
   next page. Task 9, `parseSel takes only kind:name` and `a plain place change opens no
   selection`; Task 10, `the Gateway opens only a selected server`.

---

### Task 1: One table of state words, "Available" and "All projects" (2.1, 2.3 words)

Walkthrough 1 (W1): "Available" replaces "Loads" in cells, the Details badge and lede, the After
chips and the Overview count line, and replaces "Has it" on Instructions. "Loads twice" and "Loads
once" stay. `explain.py` "Loads." stays (agent text; `layerState` drops it).

**Files:**
- Create: `src/kitden/views/words.py`
- Modify: `src/kitden/views/after.py` (drop `WORDS`; `CURSOR_IMPORT["word"]` and every plain
  `"Loads"` entry word (the dict literals near lines 138, 592, 620, 658) from `STATE_WORDS["on"]`)
- Modify: `src/kitden/views/library.py` ("Via Claude Code", "Has its skills" from `words.py`;
  `HAS_IT` goes; `_instruction_rows` sets no word, so Instructions cells use the state words as
  every tab does)
- Modify: `src/kitden/web/static/js/parts.js` (`ALL_PROJECTS`; `STATE_WORDS.on`),
  `src/kitden/web/static/index.html` (picker option), `src/kitden/web/static/js/app.js`
  (`renderShell` picker option and title), `src/kitden/web/static/js/panel.js` (`scopeWords`
  exported, tools heading, `layerState`, `loadsLede`), `src/kitden/web/static/js/changes.js`
  (`SCOPE_WORDS.user`), `src/kitden/web/static/js/overview.js` (`loadsLine` empty words)
- Modify: `docs/design.md` (Components: the picker's first choice is "All projects". "Cell state"
  row: "like Loads" becomes "like Available", and the Instructions sentence becomes "On
  Instructions a cell that has the file says "Available", as on every tab; Details says when each
  client reads it." "Instruction file Details" row: the badge says "Available", or "In a project"
  for another project's file, never "Not loaded"; "With no project picked only global files show
  lines" becomes "With All projects picked only the files for all projects show lines")
- Test: `tests/unit/test_page_words.py`, `tests/frontend/panel.test.mjs`, `tests/frontend/parts.test.mjs`,
  `tests/frontend/library.test.mjs`, `tests/unit/test_library.py`, `tests/unit/test_after.py`,
  `tests/unit/test_add_server.py`, `tests/unit/test_align.py`, `tests/unit/test_api_skill_install.py`,
  `tests/unit/test_api_plugin_install.py`, `tests/unit/test_gateway_remove.py`

**Interfaces:**
- Produces (Python, `kitden.views.words`): `STATE_WORDS: dict[str, str]` =
  `{"on": "Available", "off": "Off", "unk": "Unknown", "gw": "Via gateway", "via": "Via Claude Code", "done": "Has its skills"}`;
  `AFTER_WORDS: dict[str, tuple[str, str]]` — `after.py`'s old `WORDS`, same keys, each state word
  read from `STATE_WORDS` ("Removed", "Added", "Updated", "Via the new gateway" stay literal: they
  are action words). Later tasks add keys to both tables.
- Produces (JS, `parts.js`): `export const ALL_PROJECTS = "All projects";`; `STATE_WORDS.on = "Available"`.
- Produces (JS, `panel.js`): `export function scopeWords(def, picked = projectPath()) -> string`:
  `user` → `ALL_PROJECTS`; `project` → `"This project"` when `def.project === picked`, else
  `Project <folder>`; the other scopes and the ` · via <client>` suffix as today (Task 2 changes the
  suffix). `loadsLede(row, columns)` has one form for every kind, instructions included:
  `Available in <clients>.` (states `on`, `gw`), then `Unknown in <clients>.` (`unk`), else
  `Not available here.`. `layerState(def).badge` is `STATE_WORDS.on` wherever it said "Loads" or
  "Has it".

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
    assert AFTER_WORDS["plugin.enable"] == ("on", "Available")
    assert AFTER_WORDS["gateway.move"] == ("gw", STATE_WORDS["gw"])
    assert after.CURSOR_IMPORT["word"] == "Available"
```

Update `test_project_picker_says_project_not_where`: `'new Option(ALL_PROJECTS, "")' in app`,
`'<option value="">All projects</option>' in INDEX`, `"Global" not in app` and
`"Global" not in INDEX`, `'export const ALL_PROJECTS = "All projects";' in script("parts.js")`.
Update `test_changes_and_the_library_say_saved_settings_and_scope`: `'user: "all projects"' in changes`
and `"global settings" not in changes`. Add to it: ``'Tools · ${where || ALL_PROJECTS}' in script("panel.js")``,
`'"Nothing available here."' in script("overview.js")` and `"Loads nothing" not in script("overview.js")`.

```js
// tests/frontend/panel.test.mjs
test('Details names the scope with the same phrases as the cells', () => {
  assert.equal(scopeWords({ scope: 'user' }, ''), 'All projects');
  assert.equal(scopeWords({ scope: 'project', project: '/w/website' }, '/w/website'), 'This project');
  assert.equal(scopeWords({ scope: 'project', project: '/w/api' }, '/w/website'), 'Project api');
  assert.equal(scopeWords({ scope: 'user', client: 'cursor', owner_client: 'claude_code' }, ''), 'All projects · via Claude Code');
});
// tests/frontend/library.test.mjs
test('one word for a cell that has it, on every tab', () => {
  const word = (kind) => cellNode({ key: 'k', kind, name: 'x', cells: { codex: cell({ state: 'on' }) } }, 'codex').children[1].textContent;
  assert.equal(word('instructions'), 'Available');
  assert.equal(word('mcp_server'), 'Available');
});
```

Change these pins to the new words, nothing else in them:
- `panel.test.mjs` "the Details lede says where it loads, and where it may":
  `'Available in Claude Code and Codex.'`, `'Unknown in Codex.'`,
  `'Available in Claude Code. Unknown in Codex.'`, `'Not available here.'`; "an instruction file
  never says Loads": `'Available in Codex and Cursor.'`, `'Available in Codex.'`; "an instruction
  file layer never says Loads or Not loaded": badge `'Available'`.
- `parts.test.mjs` line 74 and `library.test.mjs` line 90: `'Available'`.
- `test_library.py`: line 667 `== {None}` and line 683 `(None, None)` (no word: the page says the
  state word).
- `"word": "Loads"` → `"word": "Available"` in `test_after.py` (81, 98, 329, 333, 338),
  `test_add_server.py` (73), `test_align.py` (123–124), `test_api_skill_install.py` (92, 93, 100,
  119, 222, 223, 263, 264, 296, 297, 312), `test_api_plugin_install.py` (208),
  `test_gateway_remove.py` (135, 176).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_page_words.py -q` and `node --test tests/frontend/panel.test.mjs tests/frontend/library.test.mjs`
Expected: FAIL (`kitden.views.words` missing, `scopeWords` not exported, "Global" found, "Loads" drawn).

- [ ] **Step 3: Implement** `views/words.py`, the imports in `after.py` and `library.py`, and the
  JS words. The picker's title with no project is `ALL_PROJECTS` (was "Global setup").
  `panel.js` imports `projectPath` for `scopeWords`'s default.

- [ ] **Step 4: Run** `uv run pytest tests/unit -q` and `node --test tests/frontend/*.test.mjs` → PASS.

- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/views/words.py src/kitden/views/after.py src/kitden/views/library.py \
  src/kitden/web/static/index.html src/kitden/web/static/js/parts.js src/kitden/web/static/js/app.js \
  src/kitden/web/static/js/panel.js src/kitden/web/static/js/changes.js src/kitden/web/static/js/overview.js \
  docs/design.md tests/unit/test_page_words.py tests/unit/test_library.py tests/unit/test_after.py \
  tests/unit/test_add_server.py tests/unit/test_align.py tests/unit/test_api_skill_install.py \
  tests/unit/test_api_plugin_install.py tests/unit/test_gateway_remove.py \
  tests/frontend/panel.test.mjs tests/frontend/parts.test.mjs tests/frontend/library.test.mjs
git commit -m "Words: Available, All projects, and one table of state words"
```

---

### Task 2: Where a cell applies, and the route out of its word slot (2.2, 2.2a)

Walkthrough 1 (W2, W3): in a project view every cell built from items says where it applies; how
the client gets the item moves to the hover text and Details.

**Files:**
- Modify: `src/kitden/views/load_map.py` (`Cell.origin`, `Cell.route`; `_where` becomes `_route`;
  `_cell`; `load_map`; `map_dict`; `SCOPE_WORDS` goes)
- Modify: `src/kitden/views/words.py` (`ORIGIN_WORDS`, `ROUTE_WORDS`)
- Modify: `src/kitden/views/library.py` (`_cell` takes `origin` and `route`; `_map_cell` copies
  them; `_skill_cell`'s installed branch: scope word from the view, route from the installed word)
- Modify: `src/kitden/web/static/js/library.js` (`cellHint`; `cellNode` hover text),
  `src/kitden/web/static/js/panel.js` (`scopeWords` suffix uses the route words)
- Modify: `docs/design.md` (Library table, "Cell state" row, add: "In a project every cell with an
  item adds where it applies: "· all projects", "· this project" or "· project override" (a project
  item that wins over an all-projects one); with All projects picked, none. How the client gets it
  ("through Claude Code's folder", "from a plugin", "through the Kitden gateway", "from the Desktop
  app") is in the hover text, before the reason, and in Details; never beside the state.")
- Test: `tests/unit/test_load_map.py`, `tests/unit/test_library.py`, `tests/unit/test_local_gateway_views.py`,
  `tests/frontend/library.test.mjs`, `tests/frontend/panel.test.mjs`

**Interfaces:**
- Consumes: `kitden.demo.build_demo_home(root: Path, size: str) -> Path` (Part 1; in the `medium`
  sample `~/work/atlas/.mcp.json` overrides Claude Code's user `docs`).
- Produces: `Cell.origin: str | None` — `None`, `"project"` or `"override"` (master plan name);
  `Cell.route: str | None` (master plan name, new). `map_dict` and every Library cell carry
  `"origin"` and `"route"`.
- Produces (`words.py`): `ORIGIN_WORDS = {None: "all projects", "project": "this project", "override": "project override"}`;
  `ROUTE_WORDS = {"desktop": "from the Desktop app", "kitden": "through the Kitden gateway", "plugin": "from a plugin", "folder": "through {}'s folder"}`.
- Rule (origin): over the cell's items (the loaded ones, or the present ones when none loads):
  `"override"` when one is a winner in some client's `EffectiveView.shadowed` (any mode, Codex's
  "merged" included) whose loser has `project is None` while the winner has a project; else
  `"project"` when any has a project; else `None`. `overrides` is one set built next to `winners`
  in `load_map`, passed to `_cell`. With a project picked, a cell with items has
  `where = ORIGIN_WORDS[origin]`; with All projects picked, `where` is `None`. Cells with no item
  ("none", "missing", and the Library's "+ Add", "Via Claude Code", "Has its skills") carry no
  scope word.
- Rule (route): `_route(item, column) -> str | None` on the item that names the cell today
  (`loaded[0]` after `_own_first`, or `present[0]` after the winners sort): the Desktop client →
  `ROUTE_WORDS["desktop"]`; `via_gateway == KITDEN_GATEWAY` → `ROUTE_WORDS["kitden"]`; another
  client's folder (`owner_client` in `NAMES` and not the column) →
  `ROUTE_WORDS["folder"].format(NAMES[owner])`; `Scope.PLUGIN` → `ROUTE_WORDS["plugin"]`; else
  `None`. Builder call: the route list is the ruling's five words; an account, managed or local
  entry and a registered gateway get no route (the cell state or Details already says it).
- Produces (`library.py`): `_installed_route(word: str) -> str | None` — the skill catalog's
  installed word: `"Installed"` → `None`; `"Via plugin"` → `ROUTE_WORDS["plugin"]`; `"Via <Client>"`
  → `ROUTE_WORDS["folder"].format(<Client>)`. `_skill_rows(..., in_project: bool = False)` passes
  `where=ORIGIN_WORDS[None] if in_project else None` to `_skill_cell(..., where: str | None = None)`,
  whose installed branch returns `_cell("on", where=where, route=_installed_route(word))` (the
  catalog's installed words come from all-projects items).
- Produces (JS, `library.js`): `export function cellHint(cell) -> string` —
  `[cell.route, cell.reason].filter(Boolean).join(". ")`, first letter upper-cased; `""` for
  neither. `cellNode` sets `node.title = cellHint(cell)` when it is not empty; the `socket(...)`
  call and its `label: cell.reason` stay.
- Produces (JS, `panel.js`): `scopeWords`'s suffix becomes ` · through <client>'s folder`.

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
    assert (github.where, github.origin) == ("all projects", None)


def test_every_item_cell_in_a_project_says_where_it_applies(home):
    rows = load_map(build_inventory(home), str(home / "work/website"))
    cells = [c for r in rows for c in r.cells.values() if c.items]
    assert cells and {c.where for c in cells} <= {"all projects", "this project", "project override"}


def test_all_projects_cells_carry_no_scope_word(home):
    rows = load_map(build_inventory(home), None)
    assert all(c.origin is None and c.where is None for r in rows for c in r.cells.values())


def test_the_route_leaves_the_word_slot(home):
    rows = load_map(build_inventory(home), None)
    brandkit = rows_by(rows, "skill", "brandkit").cells
    assert (brandkit["cursor"].where, brandkit["cursor"].route) == (None, "through Claude Code's folder")
    assert brandkit["claude_code"].route is None
    assert rows_by(rows, "mcp_server", "metamcp-local").cells["claude_code"].route == "from the Desktop app"
    assert rows_by(rows, "mcp_server", "md-index").cells["claude_code"].route == "from a plugin"


def test_the_medium_sample_says_where_each_atlas_cell_applies(tmp_path):
    home = build_demo_home(tmp_path, "medium")  # Part 1: atlas/.mcp.json overrides the user docs
    rows = load_map(build_inventory(home), str(home / "work/atlas"))
    docs = rows_by(rows, "mcp_server", "docs").cells
    assert (docs["claude_code"].where, docs["claude_code"].origin) == ("project override", "override")
    assert docs["codex"].where == "all projects"
    assert rows_by(rows, "skill", "api-style").cells["codex"].where == "this project"
```

```js
// tests/frontend/library.test.mjs
test("a cell's route is in its hover text, not beside the state", () => {
  const node = cellNode(row({ cursor: cell({ state: 'on', where: 'all projects', route: "through Claude Code's folder" }) }), 'cursor');
  assert.deepEqual(node.children.map((c) => c.textContent), ['', 'Available', 'all projects']);
  assert.equal(node.title, "Through Claude Code's folder");
  assert.equal(cellHint({ route: 'from a plugin', reason: 'From the last good read at 14:02' }), 'From a plugin. From the last good read at 14:02');
  assert.equal(cellHint({ reason: 'Could not read Codex.' }), 'Could not read Codex.');
  assert.equal(cellHint({}), '');
});
```

Update the pins that held the old word slot:
- `test_load_map.py`: `test_cell_states_for_the_website_project` → `("off", "project override")`;
  `test_cursor_loading_a_plugin_twice…` → `own…where` is `None`, `claudes…(count, route)` is
  `(1, "through Claude Code's folder")`; `test_cross_loaded_cells_say_via_which_client` → Cursor's
  `route` is `"through Claude Code's folder"`, Claude Code's `where` is `None`;
  `test_desktop_items_show_in_the_claude_code_column` → `(state, route) == ("on", "from the Desktop app")`;
  `test_raw_names_are_returned_unchanged` key set adds `"origin"` and `"route"`.
- `test_library.py`: the `_cell` helper adds `"origin": None, "route": None`; line 313 →
  `("off", None)`; line 317 → `None`; line 318 → `["route"] == "through Claude Code's folder"`;
  line 322 → `{**_cell("on"), "route": "from a plugin"}`.
- `test_local_gateway_views.py` (135–139, 475–486, 511): compare `cell["route"]` with
  `"through the Kitden gateway"` where they compared `cell["where"]` with `"Kitden gateway"`; the
  states stay.
- `panel.test.mjs` `scopeWords` pin: `"All projects · through Claude Code's folder"`.

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_load_map.py -q`,
  `node --test tests/frontend/library.test.mjs` → FAIL.
- [ ] **Step 3: Implement** the rules above.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_load_map.py tests/unit/test_library.py tests/unit/test_local_gateway_views.py tests/unit/test_api_views.py tests/unit/test_explain.py tests/unit/test_project_add.py -q`
  and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/views/load_map.py src/kitden/views/words.py src/kitden/views/library.py \
  src/kitden/web/static/js/library.js src/kitden/web/static/js/panel.js docs/design.md \
  tests/unit/test_load_map.py tests/unit/test_library.py tests/unit/test_local_gateway_views.py \
  tests/frontend/library.test.mjs tests/frontend/panel.test.mjs
git commit -m "Library: in a project every cell says where it applies; the route is in the hover text"
```

---

### Task 3: Unknown when Kitden could not read (2.3, first part)

A client whose scan failed keeps its column; a file that failed on its first read is named
above the table; no add goes into a file that cannot be read.

**Files:**
- Modify: `src/kitden/views/words.py` (`STATE_WORDS["unread"] = "Could not read"`,
  `CLIENT_UNREAD = "Could not read {}."`, `NOT_SHOWN = "Could not read {}; its items are not shown."`,
  `NO_ADD_UNREAD = "Can't add while {} can't be read."`,
  `CHANGE_UNREAD = "Can't change this while {} can't be read."`)
- Modify: `src/kitden/views/load_map.py` (`Cell.reason`; a client with `ClientStatus.UNREADABLE`
  gets `"unk"` cells), `src/kitden/views/library.py` (columns, unread cells, read notes, held adds,
  `_add_file`), `src/kitden/web/app.py` (`ADD_ACTIONS`, `unread_refusal`; `preview` refuses a step
  into a file that failed to read)
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
  `tests/unit/test_api_changes.py`, `tests/frontend/overview.test.mjs`

**Interfaces:**
- Consumes: `build_demo_home` (Part 1; in the `medium` sample `~/work/website/.cursor/mcp.json` is
  cut short, problem `parse_error`); `Cell.origin`, `Cell.route` (Task 2).
- Produces: `Cell.reason: str | None = None` (in `map_dict` as `"reason"`; `library._map_cell`
  copies it into the Library cell). An UNREADABLE client's cells are computed from its items as
  for a found one (Task 4 brings kept items), and any `"none"` result becomes
  `Cell("unk", reason=CLIENT_UNREAD.format(NAMES[client]))`; NOT_FOUND stays `"missing"`.
- Produces (Library answer): `columns` lists found and unreadable clients in `COLUMNS` order, each
  with `"note": STATE_WORDS["unread"]` for an unreadable one, else `None`. Builders still work on
  found clients only; one pass after them gives each row a cell per unreadable client (the load map
  row's cell when the row has one, else `_cell("unk", reason=…)`), never an add, and an unreadable
  column never makes a row visible.
- Produces: `notes` starts with one `NOT_SHOWN.format(<file name>)` per read problem in this view
  (deduped by text). Builder call: a problem is in this view when it has a path and that path is
  not inside the folder of a known project (`inventory.projects`) other than the picked one. The
  `MANAGED` problem with `path=None` that `views/inventory.py build_inventory` appends for an
  unreadable client gives no line (the column says it).
- Produces: held adds. Owner ruling (2026-10-22): a file Kitden could not read holds only the
  adds that would write into that file. `_add_file(adapters, client, add, project) -> str | None`
  (library.py): the settings file the add's step edits, from the adapter's own step maker, built
  and never run (`adapters[client].add_server_step(name, {})` for `mcp.add`,
  `adapters[client].plugin_install_step(plugin_id, project)` for `plugin.install`; not
  `add_server_steps`, which reads the source entry); one build per client, action and place, kept
  for the call. An add whose file is a problem path (`inventory.problems`) becomes
  `reason=NO_ADD_UNREAD.format(<file name>)`. An add into a readable file stays offered, even while
  another file of the same client is broken: in `website`, Cursor's adds into `~/.cursor/mcp.json`
  stay; an add into `~/work/website/.cursor/mcp.json` is held. An add that lets the person choose
  this project or all projects is held only when both places are broken. Skill copies
  (`skill.install`, `plugin.skills`) stay; they write only folders.
- Produces (`web/app.py`, module level): `ADD_ACTIONS = frozenset({MCP_ADD, SKILL_INSTALL, PLUGIN_INSTALL, PLUGIN_SKILLS, PROJECT_ALIGN, GATEWAY_CONNECT, SETUP_SERVER, SETUP_SERVER_UPDATE, GATEWAY_PUT_BACK})`;
  `unread_refusal(action: str, path: str) -> str` — `NO_ADD_UNREAD` for an action in
  `ADD_ACTIONS`, else `CHANGE_UNREAD`, with `Path(path).name`. `preview` checks every step's
  `edit.path` against the problem paths after the steps are built and before the engine, and
  answers 422 with `unread_refusal(...)`, so a place chosen after the add opens says it too. Part
  4's Add missing lists such an add under "Kitden cannot add" with this sentence.
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


def test_a_preview_into_a_broken_codex_config_is_refused_not_a_crash(home):
    (home / ".codex/config.toml").write_text("not = [toml\n")  # Codex stays found; the file is a problem
    with page_for(home) as page:
        github = next(i for i in page.get("/api/items?kind=mcp_server").json()
                      if (i["client"], i["name"]) == ("claude_code", "github"))
        body = {"action": "mcp.add", "targets": [{"client": "codex"}], "params": {"item": github["id"]}}
        answer = page.post("/api/changes/preview", json=body, headers=POST)
    assert (answer.status_code, answer.json()) == (422, {"detail": "Can't add while config.toml can't be read."})


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

```python
# tests/unit/test_api_changes.py
def test_a_refusal_into_an_unreadable_file_follows_the_action():
    assert unread_refusal("mcp.add", "/h/.cursor/mcp.json") == "Can't add while mcp.json can't be read."
    assert unread_refusal("plugin.disable", "/h/.claude/settings.json") == (
        "Can't change this while settings.json can't be read."
    )
```

(`page_for` and `POST` come from `tests/unit/test_local_gateway_views.py`; that home holds no
gateway servers.) Also: `test_only_found_clients_are_columns` adds `"note": None` to both column
dicts; `test_raw_names_are_returned_unchanged`'s key set adds `"reason"`; `test_page_words.py`
gains `"column.note" in script("library.js")`.

```js
// tests/frontend/overview.test.mjs
test('a client that could not be read says so, not Not installed', () => {
  assert.deepEqual(clientStatus({ status: 'unreadable' }), { state: 'unk', word: 'Could not read' });
  assert.deepEqual(clientStatus({ status: 'not_found' }), { state: 'missing' });
  assert.deepEqual(clientStatus({ status: 'found', version: '1.0', tested: false }), { state: 'unk', word: 'Not tested' });
  assert.equal(clientStatus({ status: 'found', version: '1.0', tested: true }), null);
});
```

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_library.py tests/unit/test_load_map.py tests/unit/test_api_changes.py -q`,
  `node --test tests/frontend/overview.test.mjs` → FAIL.
- [ ] **Step 3: Implement** as the Interfaces say. A file name is `Path(problem.path).name`.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_library.py tests/unit/test_load_map.py tests/unit/test_api_changes.py tests/unit/test_overview.py tests/unit/test_page_words.py -q`
  and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/views/words.py src/kitden/views/load_map.py src/kitden/views/library.py \
  src/kitden/web/app.py src/kitden/web/static/js/parts.js src/kitden/web/static/js/library.js \
  src/kitden/web/static/js/overview.js docs/design.md tests/unit/test_load_map.py \
  tests/unit/test_library.py tests/unit/test_api_changes.py tests/unit/test_page_words.py \
  tests/frontend/overview.test.mjs
git commit -m "Library: a client or file Kitden could not read is Unknown, not missing"
```

---

### Task 4: The last good read, kept in memory (2.3, second part)

**Files:**
- Modify: `src/kitden/model.py` (`Item.stale_at: str | None = None`, last field; not in `Item.id`)
- Modify: `src/kitden/views/inventory.py` (`LastGood`, `keep_last_good`)
- Modify: `src/kitden/web/app.py` (`create_app`: one `LastGood()` made above `state = State(...)`,
  because `State.__init__` builds at once; `build_marked` calls `keep_last_good` right after
  `build(**options)`, before `mark_gateways`)
- Modify: `src/kitden/views/words.py` (`STALE = "From the last good read at {}"`),
  `src/kitden/views/load_map.py` (`Cell.stale_at`, the row flag), `src/kitden/views/library.py`
  (`_cell` takes `stale_at`; stale rows hold their adds; no `NOT_SHOWN` line for a file whose
  items are kept)
- Modify: `src/kitden/web/static/js/library.js` (`cellNode`: class `stale` when `cell.stale_at`),
  `src/kitden/web/static/style.css` (`.socket.stale .dot { border-style: dashed; }`)
- Modify: `docs/design.md` (Library table, "Cell state": a cell kept from the last good read has a
  dashed dot and its row's first flag says "From the last good read at 14:02")
- Test: `tests/unit/test_inventory.py`, `tests/unit/test_library.py`, `tests/unit/test_load_map.py`,
  `tests/unit/test_page_words.py`, `tests/frontend/library.test.mjs`

**Interfaces:**
- Consumes: Task 3's held-add rule (`_add_file`, `NO_ADD_UNREAD`) and `NOT_SHOWN`; Task 2's
  `cellHint` (a stale cell's hover is `<Route>. <reason>` like any cell).
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
  Known limit, named in the task report: when `~/.claude.json` breaks, the project `.mcp.json`
  items it lists also vanish, unmarked (their source key is not a failed one).
- Produces: `Cell.stale_at: str | None` (in `map_dict` and, through `_map_cell`, in the Library
  cell) — the earliest `stale_at` of the cell's items; a stale cell's `reason` is the flag text,
  and it keeps its scope word and route like any cell. A row with a stale cell gets the first flag
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
# tests/unit/test_library.py — this home holds no gateway servers, so the rescan starts none
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
`test_raw_names_are_returned_unchanged` adds `"stale_at"`; the `_cell` helper in
`test_library.py` adds `"stale_at": None`.

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
  and `SERVER_FIELDS` move to `match.py`; `_not_same` uses `source_keys` and `odd_ones`)
- Modify: `src/kitden/views/words.py` (`STATE_WORDS["review"] = "Needs review"`,
  `NOT_SAME = "Same name, another source."`, `NO_ADD_REVIEW = "Same name, another source: decide first."`),
  `src/kitden/views/load_map.py` (review pass), `src/kitden/views/library.py`
  (`_skill_rows`/`_skill_cell`: a catalog skill against the client's own; `_no_add_in_review`)
- Modify: `src/kitden/web/static/js/parts.js` (`STATE_WORDS.review`), `src/kitden/web/static/style.css`
  (`.s-review`), `src/kitden/web/static/js/panel.js` (`loadsLede`), `src/kitden/web/static/js/overview.js`
  (`loadCounts` counts `"review"` with `"on"` and `"gw"`)
- Modify: `docs/design.md` (Library table, "Cell state": "Needs review" (amber ring, small dot) is
  a same-name item from another source: another command, address or skill files. In a row with a
  Needs review cell no cell offers "+ Add"; its hover says "Same name, another source: decide
  first.")
- Test: `tests/unit/test_match.py` (new), `tests/unit/test_load_map.py`, `tests/unit/test_library.py`,
  `tests/unit/test_align.py` (unchanged, must pass), `tests/unit/test_page_words.py`,
  `tests/frontend/panel.test.mjs`, `tests/frontend/overview.test.mjs`

**Interfaces:**
- Consumes: `build_demo_home` (Part 1; in the `medium` sample `docs` is Claude Code's
  `https://docs.example.test/mcp` and Codex's `npx docs-mcp`, both for all projects, and Cursor
  lacks it); `loadsLede` (Task 1).
- Produces (`kitden.views.match`, used again by Task 6 and Part 4):
  - `SERVER_FIELDS = ("command", "args", "url")`.
  - `plugin_of(item: Item) -> str | None` — for a `Scope.PLUGIN` item, the parts of its source
    path after the last `plugins/cache`: `<marketplace>/<plugin>/…` → `f"{plugin}@{marketplace}"`;
    else `None`. All three clients keep a plugin's files in `plugins/cache/<marketplace>/<plugin>/<version>/`
    (Claude Code's `installPath` in fixture 2.1.283; Codex in the sample; Cursor in
    `cursor.py plugin_folders`, checked 2026-10-20).
  - `folder_key(folder: Path) -> str` — `skill_digest` of the real folder, or the real folder's
    path when that is `None`.
  - `source_keys(item: Item) -> frozenset` — an MCP server: one key, its `summary` pairs in
    `SERVER_FIELDS`, the url through `normalize_url`; a skill: `folder_key(<folder of its SKILL.md>)`,
    plus `f"plugin:{plugin_of(item)}"` when that is not `None`; anything else: `{item.name}`. Two
    items are the same when their keys meet.
  - `catalog_keys(skill: dict) -> frozenset` — a skill catalog row the same way:
    `folder_key(Path(skill["path"]))`, plus `f"plugin:{skill['plugin']}"` when it has a plugin.
  - `odd_ones(keys: dict[str, frozenset]) -> set[str]`:

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
  copied is the same skill; and a plugin's skill matches by its plugin (ruling P13), so a newer
  marketplace or cache version is not review.
- Produces: `Cell.state == "review"` (master plan name). Pass in `load_map` after the cells: for
  rows of kind MCP server or skill with two or more `"on"` cells, each column's keys are the union
  of `source_keys(i)` over the items of its `"on"` cell, leaving out items with `via_gateway`, the
  setup entry (`SETUP_NAME`), `Scope.ACCOUNT` and the Desktop client; each client in `odd_ones`
  gets `state="review", reason=NOT_SAME`. Only `"on"` cells are compared and marked; review
  changes `state` and `reason` only (scope word and route stay).
- Produces (Library skill rows): when a client has the row (`_has`) and its map cell is `"on"`,
  the cell is `"review"` with `NOT_SAME` when `catalog_keys(skill)` does not meet the union of
  `source_keys` of the cell's items. A review cell has no add.
- Produces (`library.py`): `_no_add_in_review(rows: list[dict]) -> None` — on MCP server and skill
  rows with a `"review"` cell, every cell with an add gets `add=None, reason=NO_ADD_REVIEW`
  (ruling C3: an add would silently copy one side). Runs after the builders and Task 3's unread
  pass.
- `align._not_same` lists a name when `odd_ones` of the per-client key unions is not empty (was:
  when the per-client sets differ), so a copy with the same files is now the same. Say it in the
  commit body.
- Produces (JS): `STATE_WORDS.review = "Needs review"`;
  `.s-review { color: var(--lamp-warn); } .s-review .dot::after { transform: scale(0.5); border-radius: 50%; }`
  (an amber ring with a small dot, apart from Unknown's dashed ring); `loadsLede` adds
  `Needs review in <clients>: same name, another source.` after the Available line.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_match.py
def test_the_odd_one_needs_review_and_a_tie_keeps_the_first():
    a, b = frozenset({"a"}), frozenset({"b"})
    assert odd_ones({"claude_code": a, "codex": b, "cursor": b}) == {"claude_code"}
    assert odd_ones({"claude_code": a, "codex": b}) == {"codex"}
    assert odd_ones({"claude_code": frozenset({"a", "b"}), "codex": b}) == set()
    assert odd_ones({"claude_code": a, "codex": a}) == set()


def test_a_plugin_skill_is_known_by_its_plugin():
    path = "/h/.claude/plugins/cache/claude-plugins-official/superpowers/7.0.0/skills/x/SKILL.md"
    skill = Item(client="claude_code", kind=ItemKind.SKILL, name="x", scope=Scope.PLUGIN,
                 source=Source(kind=SourceKind.PLUGIN, path=path, owner_client="claude_code"))
    assert plugin_of(skill) == "superpowers@claude-plugins-official"
    assert plugin_of(replace(skill, scope=Scope.USER)) is None
```

```python
# tests/unit/test_load_map.py  (add_claude, add_cursor from tests/unit/test_local_gateway_move.py)
def test_a_same_name_server_from_another_source_needs_review(home):
    add_claude(home, "neon", {"type": "http", "url": "https://other.invalid/mcp"})
    neon = rows_by(load_map(build_inventory(home), None), "mcp_server", "neon")
    assert (neon.cells["claude_code"].state, neon.cells["codex"].state) == ("on", "review")
    assert neon.cells["codex"].reason == "Same name, another source."


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


def test_a_plugin_skill_is_not_review_after_the_marketplace_moves_on(home):
    # The marketplace copy says "Think first."; Claude Code's cache copy is another version.
    row = _row(_library(home, "skill", show="all"), "brainstorming", f"superpowers@{OFFICIAL}")
    assert (row["cells"]["claude_code"]["state"], row["cells"]["claude_code"]["route"]) == ("on", "from a plugin")


def test_review_rows_on_the_medium_sample_offer_no_add(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    answer = library(build_inventory(home), {a.id: a for a in default_adapters(home)}, None,
                     gateway_registered=False, kind="mcp_server")
    docs = _row(answer, "docs")["cells"]  # Part 1: same name, two sources; a tie keeps Claude Code
    assert (docs["claude_code"]["state"], docs["codex"]["state"]) == ("on", "review")
    assert (docs["cursor"]["add"], docs["cursor"]["reason"]) == (None, "Same name, another source: decide first.")
    review = [c for r in answer["rows"] for c in r["cells"].values() if c["state"] == "review"]
    assert all(c["add"] is None for c in review)
```

```js
// tests/frontend/panel.test.mjs (inside the loadsLede test, with its lede() helper)
assert.equal(lede({ claude_code: 'on', codex: 'review' }), 'Available in Claude Code. Needs review in Codex: same name, another source.');
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
  and `node --test tests/frontend/*.test.mjs` → PASS. Then `uv run python scripts/measure-start.py`:
  the three numbers stay within their budgets (`docs/development.md`, Speed); put them in the
  task report.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/views/match.py src/kitden/views/skills.py src/kitden/changes/align.py \
  src/kitden/views/words.py src/kitden/views/load_map.py src/kitden/views/library.py \
  src/kitden/web/static/js/parts.js src/kitden/web/static/style.css src/kitden/web/static/js/panel.js \
  src/kitden/web/static/js/overview.js docs/design.md tests/unit/test_match.py tests/unit/test_load_map.py \
  tests/unit/test_library.py tests/unit/test_page_words.py tests/frontend/panel.test.mjs tests/frontend/overview.test.mjs
git commit -m "Library: Needs review for a same name from another source" \
  -m "Add missing now treats a copy with the same files as the same item."
```

---

### Task 6: Overview notes that do not overstate, grouped by item (2.3a)

Walkthrough 1 (W5; F7, F8): two entries from different sources are "Same name, another source",
not "Set up in more than one client"; every note row shows its clients; one row per name.

**Files:**
- Modify: `src/kitden/model.py` (`FindingType.SAME_NAME_OTHER_SOURCE`; `Finding.clients`)
- Modify: `src/kitden/views/findings.py` (`_finding` fills `clients`; the cross-client note splits
  by `source_keys`; `finding_dict` adds `"clients"`)
- Modify: `src/kitden/views/overview.py` (`note_count`; `notes` counts item groups)
- Modify: `src/kitden/web/static/js/overview.js` (`NOTE_WORDS.same_name_other_source`,
  `noteGroups`, `noteRow` draws a group)
- Modify: `docs/design.md` (after the Overview "Can improve" paragraph: "Overview's notes are
  grouped by item: one row per name with the mark of every client it is about, and each note as a
  quiet flag. "Same name, another source" says two entries differ; "Set up in more than one
  client" says the same one is set up twice.")
- Test: `tests/unit/test_findings.py`, `tests/unit/test_overview.py`, `tests/unit/test_mcp_server.py`,
  `tests/unit/test_page_words.py`, `tests/frontend/overview.test.mjs`

**Interfaces:**
- Consumes: `source_keys`, `odd_ones` (`kitden.views.match`, Task 5).
- Produces: `FindingType.SAME_NAME_OTHER_SOURCE = "same_name_other_source"` (severity info);
  `Finding.clients: tuple[str, ...] = ()` (master plan names; not in `Finding.id`).
  `_finding(kind, severity, items, text, client=None, clients=())` sets
  `clients = clients or ((client,) if client else ())`. The cross-client note (today's
  `SAME_IN_OTHER_CLIENTS` loop) passes `clients=tuple(sorted(by_client))` and keeps its type when
  `not odd_ones({c: source_keys(i) for c, i in by_client.items()})`; else it is
  `SAME_NAME_OTHER_SOURCE` with the text
  `f"{kind.replace('_', ' ')} '{name}' has the same name in {', '.join(sorted(by_client))} but comes from another source"`.
  `finding_dict` adds `"clients": list(f.clients)`; the MCP tool `list_findings` gains the type
  and the field.
- Produces (`views/overview.py`): `note_count(findings: list[Finding]) -> int` — the number of
  distinct names across the findings (the page's grouping key); `overview()["notes"]` is
  `note_count(info)`.
- Produces (JS, `overview.js`): `NOTE_WORDS.same_name_other_source = "Same name, another source"`;
  `export function noteGroups(findings) -> [{ name, clients, notes, first }]` — one group per name
  in first-seen order; a finding with several names (unknown state) joins each name's group;
  `clients` is the union of the findings' `clients` in first-seen order; `notes` the distinct
  `NOTE_WORDS[type] || type.replaceAll("_", " ")`; `first` the group's first finding. `notesBlock`
  draws one `noteRow(group)` per group of the info findings: every client's `mark`, the name, one
  info `flag` per note, and "Details" calling `showNote(group.first)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_findings.py
def test_a_same_name_from_another_source_is_its_own_note():
    a = replace(item("codex", ItemKind.MCP_SERVER, "docs", "/h/.codex/config.toml"), summary=(("command", "npx"),))
    b = replace(item("claude_code", ItemKind.MCP_SERVER, "docs", "/h/.claude.json"),
                summary=(("url", "https://docs.example.test/mcp"),))
    (finding,) = find_findings(Inventory(items=[a, b]))
    assert (str(finding.type), finding.clients) == ("same_name_other_source", ("claude_code", "codex"))
    assert finding_dict(finding)["clients"] == ["claude_code", "codex"]


def test_the_same_server_in_two_clients_keeps_its_note_and_names_both():
    a = item("codex", ItemKind.MCP_SERVER, "Neon", "/h/.codex/config.toml")
    b = item("cursor", ItemKind.MCP_SERVER, "Neon", "/h/.cursor/mcp.json")
    (finding,) = find_findings(Inventory(items=[a, b]))
    assert (str(finding.type), finding.clients) == ("same_in_other_clients", ("codex", "cursor"))


def test_every_finding_names_its_clients(tmp_path):
    assert all(f.clients for f in find_findings(build_inventory(real_home(tmp_path))))
```

```python
# tests/unit/test_overview.py
def test_notes_count_items_not_findings(tmp_path):
    home = build_demo_home(tmp_path, "medium")  # 16 notes about 14 names: docs has three
    assert overview(build_inventory(home), [], None)["notes"] == 14
```

`test_headline_counts_attention` keeps `data["notes"] == 14`; its comment becomes "14 names with
notes (each note here is about another name)". `test_mcp_server.py`
`test_findings_include_gateway_bypasses` adds `assert all(f["clients"] for f in data["findings"])`.
`test_page_words.py`: `'same_name_other_source: "Same name, another source"' in script("overview.js")`.

```js
// tests/frontend/overview.test.mjs
test('notes are grouped by item, each with its clients', () => {
  const note = (type, names, clients) => ({ type, names, clients, items: ['i'], severity: 'info' });
  const groups = noteGroups([
    note('same_name_other_source', ['docs', 'docs'], ['claude_code', 'codex']),
    note('bypasses_gateway', ['docs'], ['claude_code']),
    note('bypasses_gateway', ['docs'], ['codex']),
    note('unknown_state', ['a', 'b'], ['codex']),
  ]);
  assert.deepEqual(groups.map((g) => [g.name, g.clients, g.notes]), [
    ['docs', ['claude_code', 'codex'], ['Same name, another source', 'Not connected to the gateway']],
    ['a', ['codex'], ['On/off state not readable']],
    ['b', ['codex'], ['On/off state not readable']],
  ]);
});
```

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_findings.py tests/unit/test_overview.py -q`,
  `node --test tests/frontend/overview.test.mjs` → FAIL.
- [ ] **Step 3: Implement** as the Interfaces say.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_findings.py tests/unit/test_overview.py tests/unit/test_mcp_server.py tests/unit/test_load_map.py tests/unit/test_page_words.py tests/security -q`
  and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/model.py src/kitden/views/findings.py src/kitden/views/overview.py \
  src/kitden/web/static/js/overview.js docs/design.md tests/unit/test_findings.py tests/unit/test_overview.py \
  tests/unit/test_mcp_server.py tests/unit/test_page_words.py tests/frontend/overview.test.mjs
git commit -m "Overview: notes grouped by item, with their clients; two sources are not one item"
```

---

### Task 7: Every add names its scope; a removed project is said (2.4)

Also the Part 1 deferred item (W6): a review still being prepared when the project changes is
dropped.

**Files:**
- Modify: `src/kitden/web/static/js/panel.js` (`changeWords`; `showReview` lede via `reviewLede`;
  `review` drops an answer for another project)
- Modify: `src/kitden/web/static/js/library.js` (`startAdd` body, `scopeLine`, `loadLibrary` skips
  a gone project), `src/kitden/web/static/js/offer.js` (`PROJECT_NOTE`), `src/kitden/views/library.py`
  (`_cursor_in_project` and `_no_skill_place` hints)
- Modify: `src/kitden/web/static/js/store.js` (`loadShared` keeps the project; `projectGone`;
  `reload` reads no project data for a gone project), `src/kitden/web/static/js/parts.js`
  (`GONE_PROJECT`), `src/kitden/web/static/js/app.js` (`renderPlace`, `renderShell` picker)
- Modify: `docs/design.md` (Components, two lines: a picked project that leaves the list stays
  picked while Overview, Library and Gateway say "This project is no longer on the list."; an
  add's review names its scope in the title ("… for all projects", "… in website") and, with All
  projects picked, in the lede. "Tool switches" row: "closes the panel and cancels an open review,"
  becomes "closes the panel, cancels an open review and drops one still being prepared,")
- Test: `tests/frontend/panel.test.mjs`, `tests/frontend/library.test.mjs`, `tests/frontend/offer.test.mjs`,
  `tests/frontend/store.test.mjs`, `tests/unit/test_page_words.py`, `tests/unit/test_project_add.py`

**Interfaces:**
- Consumes: `ALL_PROJECTS` and the picker in `app.js renderShell` (Task 1).
- Produces (`panel.js`): `export const ADDS = ["mcp.add", "skill.install", "plugin.install", "plugin.skills"]`;
  `export function addScope(action, into) -> string | null` — `null` when `action` is not in
  `ADDS`, `` ` in ${projectLabel(into)}` `` with a project, else `" for all projects"`.
  `changeWords` appends it to the title and to `done` (replacing today's
  skill/plugin-only " in <folder>"; the restart notes still follow `done`).
  `export function reviewLede(action, picked) -> string`: `"Adds for all projects. "` first when
  `action` is in `ADDS` and `picked` is empty, then
  `"Nothing is written until you press Apply. A backup is kept, so you can undo."`. Builder call:
  in a project the existing note callout already says the scope, so the lede does not repeat it.
- Produces (`panel.js review`): it notes `state.project` before the POST; when the answer comes
  and `state.project` differs, it opens nothing, calls no `back`, and, when the answer has an id,
  posts `/api/changes/<id>/cancel` once.
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
  out. The picker's redraw signature (`where.dataset.projects`) also holds
  `projectGone() ? state.project : ""`, so the option comes and goes.

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

// `review` joins this file's panel.js import.
test('a review that answers after the project changed is dropped', async () => {
  fakePanelPage();
  const posted = [];
  let answer;
  globalThis.fetch = (url) => {
    posted.push(url);
    if (url.endsWith('/preview')) return new Promise((resolve) => { answer = resolve; });
    return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
  };
  try {
    state.project = 'atlas';
    const pending = review({ action: 'mcp.add', targets: [{ client: 'codex' }], params: {} });
    state.project = 'web';
    answer({ ok: true, status: 200, json: async () => ({ id: 'c1', action: 'mcp.add', steps: [{ client: 'codex', name: 'github' }], after: [] }) });
    await pending;
    assert.equal(isPanelOpen(), false);
    assert.deepEqual(posted.filter((url) => url.includes('/cancel')), ['/api/changes/c1/cancel']);
  } finally {
    state.project = '';
    delete globalThis.document;
    delete globalThis.fetch;
  }
});
```

Update the `changeWords` pins that now end in ` for all projects` (the `tidy` add without a
project, `mcp.add`, the plugin skills title and `done`). Update every "all your projects" pin in
`library.test.mjs` (401, 402, 405), `offer.test.mjs` (70, 83, 84), `test_page_words.py` (597,
784, 792) and `tests/unit/test_project_add.py` (182) to the new words, and pin
`"Adds for all projects. "`, `GONE_PROJECT` and `"No longer on the list"` (in `app.js`) in
`test_page_words.py`.

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
def test_a_skill_add_into_a_known_project_on_another_disk_previews(client, tmp_path):
    site = tmp_path / "other-disk/site"  # outside the home folder
    site.mkdir(parents=True)
    settings_path = client.home / ".claude.json"
    settings = json.loads(settings_path.read_text())
    settings.setdefault("projects", {})[str(site)] = {"hasTrustDialogAccepted": True}
    settings_path.write_text(json.dumps(settings))
    client.post("/api/rescan", headers=POST)  # a fixture home: no held servers to ask
    change = _preview(client, "skill.install", ["claude_code"], {"skill": TIDY, "project": pid(client, str(site))})
    assert change.status_code == 200
    assert all(step["path"].startswith(str(site)) for step in change.json()["steps"])
```

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
git commit -m "Reviews name the scope of an add; a removed project is said, not swapped" \
  -m "A review that answers after the project changed is dropped."
```

---

### Task 8: "+ Add" wherever Kitden can add; a project's own skill adds into it (2.3, F6)

Walkthrough 1 (W4): a cell Kitden can fill shows "+ Add", and Details offers the same add (it
mirrors the cells through `offer.js addOptions`). A skill only this project has adds into this
project. A server only this project has keeps "—" with a reason: a project MCP write needs dated
client facts, so it goes to the roadmap as Later.

**Files:**
- Modify: `src/kitden/views/skills.py` (`project_skills`; every catalog row gains `"project": None`)
- Modify: `src/kitden/views/words.py` (`NO_PROJECT_SERVER = "Kitden adds MCP servers for all projects only."`,
  `ONLY_IN_PROJECT = "This skill is in one project only. Pick that project to add it."`,
  `PROJECT_TRUST = "To add it to {name}, trust {name} in Codex first."`)
- Modify: `src/kitden/views/library.py` (`_add` takes `project_only`; `_skill_rows` takes the
  project rows; `_skill_cell` for a project row; `_server_why` for a project-only server)
- Modify: `src/kitden/web/app.py` (`preview`, `SKILL_INSTALL`: a `project/` skill comes from
  `project_skills` and needs its project)
- Modify: `src/kitden/web/static/js/library.js` (`startAdd`, `addName`, `scopeLine` for
  `project_only`)
- Modify: `docs/design.md` ("Cell button" row, add: "In a project, a skill only that project has
  offers "+ Add" for the clients that lack it; it adds into that project with no choice. A server
  only that project has keeps "—", saying "Kitden adds MCP servers for all projects only."")
- Test: `tests/unit/test_skills_catalog.py`, `tests/unit/test_library.py`, `tests/unit/test_project_add.py`,
  `tests/unit/test_page_words.py`, `tests/frontend/library.test.mjs`, `tests/frontend/offer.test.mjs`

**Interfaces:**
- Consumes: Task 5's review and `_no_add_in_review` (a project skill row with a review cell offers
  no add); Task 7's add words; `noteFor(add, project, scope)` and `previewFor(add, client, scope)`
  (`library.js`, as they are).
- Produces (`kitden.views.skills`): `project_skills(inventory, adapters, project: str) -> list[dict]`
  — one catalog row (the same keys as `skill_catalog`'s rows) per skill name that a client loads
  from `project` (`Scope.PROJECT` items with `item.project == project`): `"id": f"project/{name}"`
  (a folder name has no "/", so it never meets a catalog id), `"from": Path(project).name`,
  `"plugin": None`, `"path"`: the first such item's folder, `"project": project`, `"installed"`:
  `{client: "Installed"}` for each client with such an item, `"routes"` as `_row` makes them.
- Produces (`library.py`): `_add(..., project_only: bool = False)` adds the key `"project_only"`
  to every add. `library()` passes `project_skills(inventory, adapters, project)` when a project
  is picked, else `[]`, as `_skill_rows(..., project_rows: list[dict] = ())`, which adds a project
  row only when no catalog row has its name
  (Builder call: the all-projects row already covers that name). A project row's cell for a client
  that can take it is `_add(SKILL_INSTALL, "+ Add", skill=<id>, project_only=True)`; Codex, when
  `_no_skill_place` says it does not trust the project, gets
  `reason=PROJECT_TRUST.format(name=<folder>)` and no add.
- Produces (`library.py _server_why`): a dash in a row whose loaded items all have a project and
  that has no all-projects source (`_server_add` found none) says `NO_PROJECT_SERVER`.
- Produces (`web/app.py preview`): for `params.skill` starting with `"project/"`: no project →
  422 `ONLY_IN_PROJECT`; else the skill is looked up in
  `project_skills(state.inventory, adapters, _project_param(params))` (not found → "This skill is
  not on this computer.") and goes through `skill_steps(..., project)` as today.
- Produces (JS, `library.js`): `startAdd` with `add.project_only` opens
  `review(previewFor(add, client, "project"), { note: noteFor(add, state.project, "project") })`
  at once, no choice; `addName(row, client, add, project)` with `project_only` returns
  `` `${to} in ${projectLabel(project)}` `` (no "…"); `scopeLine` ends with
  `" This project's own skills add into this project."` when a row has a `project_only` add.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_skills_catalog.py
def test_a_project_skill_is_a_catalog_row_of_its_project(tmp_path):
    home = build_demo_home(tmp_path, "medium")  # Part 1: atlas/.agents/skills/api-style
    atlas = str(home / "work/atlas")
    inventory = build_inventory(home)
    rows = project_skills(inventory, {a.id: a for a in default_adapters(home)}, atlas)
    style = next(r for r in rows if r["name"] == "api-style")
    assert (style["id"], style["project"], style["from"]) == ("project/api-style", atlas, "atlas")
    assert set(style["installed"]) == {"codex", "cursor"} and style["routes"] == {"claude_code": "ready"}
    assert all(r["project"] is None for r in skill_catalog(inventory, {a.id: a for a in default_adapters(home)}))
```

```python
# tests/unit/test_library.py
def test_a_project_only_skill_adds_into_the_project(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inventory, adapters = build_inventory(home), {a.id: a for a in default_adapters(home)}
    atlas = library(inventory, adapters, str(home / "work/atlas"), gateway_registered=False, kind="skill")
    add = _row(atlas, "api-style")["cells"]["claude_code"]["add"]
    assert (add["action"], add["skill"], add["project_only"]) == ("skill.install", "project/api-style", True)
    everywhere = library(inventory, adapters, None, gateway_registered=False, kind="skill", show="all")
    assert not any(r["name"] == "api-style" for r in everywhere["rows"])


def test_a_project_only_server_says_why_it_has_no_add(home):
    answer = library(build_inventory(home), {a.id: a for a in default_adapters(home)},
                     str(home / "work/website"), gateway_registered=False, kind="mcp_server")
    docs = _row(answer, "docs")["cells"]  # only website's own .mcp.json has docs
    assert (docs["codex"]["add"], docs["codex"]["reason"]) == (None, "Kitden adds MCP servers for all projects only.")
```

The `_add` helper in `test_library.py` adds `project_only=False` and its key.

```python
# tests/unit/test_project_add.py
HOUSE = "---\nname: house-style\ndescription: Our style.\n---\nKeep it plain.\n"


def _project_skill(client, project):
    folder = client.home / f"work/{project}/.claude/skills/house-style"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(HOUSE)
    client.post("/api/rescan", headers=POST)  # a fixture home: no held servers to ask


def test_a_project_skill_copies_into_the_same_project(client):
    _project_skill(client, "api")  # Codex trusts api
    api = str(client.home / "work/api")
    change = _preview(client, "skill.install", ["codex"], {"skill": "project/house-style", "project": pid(client, api)})
    assert change.json()["steps"][0]["path"] == f"{api}/.agents/skills/house-style"
    refused = _preview(client, "skill.install", ["codex"], {"skill": "project/house-style"})
    assert (refused.status_code, refused.json()["detail"]) == (
        422, "This skill is in one project only. Pick that project to add it."
    )


def test_a_project_skill_for_codex_in_an_untrusted_project_says_trust_first(client):
    _project_skill(client, "untrusted")
    untrusted = pid(client, str(client.home / "work/untrusted"))
    rows = client.get(f"/api/library?kind=skill&project={untrusted}").json()["rows"]
    codex = next(r for r in rows if r["name"] == "house-style")["cells"]["codex"]
    assert (codex["add"], codex["reason"]) == (None, "To add it to untrusted, trust untrusted in Codex first.")
```

```js
// tests/frontend/library.test.mjs
test("a project's own skill adds into the project, with no choice", () => {
  state.project = 'p1';
  data.projects = [{ id: 'p1', path: '/w/atlas' }];
  const own = add({ action: 'skill.install', skill: 'project/api-style', project_only: true });
  const style = { kind: 'skill', name: 'api-style' };
  assert.deepEqual(previewFor(own, 'claude_code', 'project').params, { skill: 'project/api-style', project: 'p1' });
  assert.equal(addName(style, 'claude_code', own, 'p1'), 'Add api-style to Claude Code in atlas');
  assert.ok(scopeLine('p1', [{ cells: { claude_code: cell({ add: own }) } }]).endsWith(" This project's own skills add into this project."));
  state.project = '';
  data.projects = null;
});
// tests/frontend/offer.test.mjs
test('Details offers the add the cell offers', () => {
  const own = { action: 'skill.install', label: '+ Add', skill: 'project/api-style', project_only: true };
  const row = { kind: 'skill', cells: { claude_code: { add: own }, codex: { add: null }, cursor: { add: null } } };
  assert.deepEqual(addOptions(row, null).map((o) => [o.client, o.label]), [['claude_code', 'Add to Claude Code…']]);
});
```

`test_page_words.py`: `"add.project_only" in script("library.js")`.

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_skills_catalog.py tests/unit/test_library.py tests/unit/test_project_add.py -q`,
  `node --test tests/frontend/library.test.mjs tests/frontend/offer.test.mjs` → FAIL.
- [ ] **Step 3: Implement** as the Interfaces say.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_skills_catalog.py tests/unit/test_library.py tests/unit/test_project_add.py tests/unit/test_api_skill_install.py tests/unit/test_align.py tests/unit/test_page_words.py -q`
  and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/views/skills.py src/kitden/views/words.py src/kitden/views/library.py src/kitden/web/app.py \
  src/kitden/web/static/js/library.js docs/design.md tests/unit/test_skills_catalog.py tests/unit/test_library.py \
  tests/unit/test_project_add.py tests/unit/test_page_words.py tests/frontend/library.test.mjs tests/frontend/offer.test.mjs
git commit -m "Library: + Add wherever Kitden can add; a project's own skill adds into the project"
```

---

### Task 9: The selection in the address: Overview and Library (2.5, first part)

**Files:**
- Modify: `src/kitden/web/static/js/store.js` (selection, `goTo`, arrival, `place`, `parseHash`,
  `hashFor`, `followAddress`)
- Modify: `src/kitden/web/static/js/app.js` (`start`, `fromAddress`, `openPlace`)
- Modify: `src/kitden/web/static/js/library.js` (`rowSel`, `rowFor`; `buildRow`, `openRow`,
  `openOffer`, `renderLibrary` use them; `openSelectedOnRender` and `openNext` go)
- Modify: `src/kitden/web/static/js/panel.js` (`closePanel` clears the selection through
  `setState`; `openPanel`'s `openerKey` falls back to the row marked `aria-selected`)
- Modify: `src/kitden/web/static/js/overview.js` (`targetSel`; `follow` uses `goTo`; `showNote`
  passes the row's name), `src/kitden/views/overview.py` (`_duplicates` target
  `{"view": "map", "kind": kind, "name": <first item's name>}`, no `"row"`)
- Modify: `docs/design.md` (Components: the address keeps the project and the selected item
  (`sel=<kind>:<name>`) on every page, and the Library opens that row's Details once)
- Test: `tests/frontend/store.test.mjs`, `tests/frontend/library.test.mjs`, `tests/frontend/overview.test.mjs`,
  `tests/unit/test_overview.py`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `showNote` and `noteRow` (Task 6).
- Produces (`store.js`, master plan names): `parseSel(text) -> {kind, name} | null` — `kind` is one
  of `SEL_KINDS = ["mcp_server", "plugin", "skill", "hook", "marketplace", "instructions"]`, split at
  the first ":", `name` not empty; `selFor(selected) -> string` (`""` for `null`).
  Also `sameSel(a, b) -> boolean`.
- `state.selected` is `{kind, name} | null` (was a row key). `parseHash` returns
  `selected: parseSel(params.get("sel"))`; `hashFor` writes `sel` last, on every view:
  `#library?kind=mcp_server&project=a&sel=mcp_server%3Agithub`. `OLD_VIEWS` and the `#map` redirect
  stay as they are.
- Produces: `export const arrival = { pending: false }`; `takeArrival() -> {kind, name} | null` —
  `state.selected` when pending, else `null`; always clears `pending` (so a redraw never opens
  Details again and takes focus). Only `goTo`, `followAddress` and `start` set `pending` (ruling
  P17): `go(view, params)` clears it, then calls `place(view, params)` (today's body of `go`).
- Produces: `goTo(view: string, selected: {kind, name} | null)` (master plan name). Builder call:
  it lives in `store.js`, not `app.js`: `app.js` starts the page when imported, so page modules
  and node tests cannot import it. It sets `arrival.pending = Boolean(selected)` and calls
  `place(view, { selected, ...(view === "library" && selected ? libraryChoice(selected) : {}) })`.
  `libraryChoice(selected) -> { kind: selected.kind, show: "mine", category: "", attention: false, q: "" }`
  (Builder call: what the Overview cards use today; it resets `show` and the search).
- `followAddress(next)` keeps `next.selected` and sets `arrival.pending = Boolean(next.selected)`;
  `fromAddress` compares `selFor` too; `start` sets `arrival.pending` from the first address;
  `openPlace(view)` reads `libraryChoice(state.selected)` first when it has one, then
  `goTo(view, state.selected)`. The project picker still clears the selection. The Clients card's
  count buttons keep `go("library", choice)`, so they never open a stale selection (F2, a count
  that opens the tab with that client's items selected, is Part 6's: ruling W7).
- Produces (`library.js`): `rowSel(row) -> {kind: row.kind, name: row.lookup || row.offer || row.name}`;
  `rowFor(rows, selected) -> row | null` (first match; Builder call: `sel=instructions:review`
  opens the first row of that name). `openRow` calls `setState({ selected: rowSel(row) })`
  (replaces the address entry). `renderLibrary` calls `takeArrival()` only when its answer is
  fresh (else the arrival is used up before the rows come), then opens `rowFor(answer.rows, …)`
  with the `.arrive` glow as today.
- Produces (`overview.js`): `targetSel(target) -> {kind, name} | null` from a card target
  (`{view: "map", kind, name}`); `follow` reads `libraryChoice(sel)` first, then
  `goTo("library", sel)`. `showNote` calls `follow({ view: "map", kind: row.kind, name: row.lookup })`
  (ruling P10), so a note's Details opens the item.

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

test('a plain place change opens no selection', () => {
  goTo('library', { kind: 'skill', name: 'tidy' });
  go('overview');
  go('library', { kind: 'mcp_server' });
  assert.equal(takeArrival(), null);
  assert.deepEqual(state.selected, { kind: 'skill', name: 'tidy' }); // it stays for the next page
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
through `transition`). In `library.test.mjs`, add `selected: null` to the `library()` helper of
`old map and discover addresses open the Library` (its other asserts stay: `#map` still opens the
Library).

```js
// tests/frontend/overview.test.mjs
test('a card about an item selects it by kind and name', () => {
  assert.deepEqual(targetSel({ view: 'map', kind: 'skill', name: 'tidy' }), { kind: 'skill', name: 'tidy' });
  assert.equal(targetSel({ view: 'agents' }), null);
});
```

`tests/unit/test_overview.py` (around lines 231–232): the duplicate card's `target` is
`{"view": "map", "kind": …, "name": by_id[twice.items[0]].name}` and that name is the `lookup` of
a `load_map(inventory, None)` row. `test_page_words.py`:
`'follow({ view: "map", kind: row.kind, name: row.lookup })' in script("overview.js")`.

- [ ] **Step 2: Run them to see them fail**: `node --test tests/frontend/*.test.mjs`,
  `uv run pytest tests/unit/test_overview.py tests/unit/test_page_words.py -q` → FAIL.
- [ ] **Step 3: Implement** as the Interfaces say.
- [ ] **Step 4: Run** the same commands → PASS.
- [ ] **Step 5: Run all checks, then commit**

```bash
git add src/kitden/web/static/js/store.js src/kitden/web/static/js/app.js src/kitden/web/static/js/library.js \
  src/kitden/web/static/js/panel.js src/kitden/web/static/js/overview.js src/kitden/views/overview.py \
  docs/design.md tests/frontend/store.test.mjs tests/frontend/library.test.mjs tests/frontend/overview.test.mjs \
  tests/unit/test_overview.py tests/unit/test_page_words.py
git commit -m "The address keeps the selected item; the Library opens its Details"
```

---

### Task 10: The Gateway opens the selected server; one walk across the pages (2.5, Done)

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (`serverFor`, `heldServer`; `showServer` and
  `showKitdenServer` set the selection; `renderGateway` takes the arrival)
- Create: `tests/frontend/context.test.mjs`
- Modify: `docs/design.md` (the Components line of Task 9 adds: the Gateway opens the selected
  server's Details once, in the gateway's own panel for a server it holds)
- Test: `tests/frontend/gateway.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `goTo`, `takeArrival`, `parseHash`, `followAddress`, `state` (`store.js`, Task 9);
  `rowFor`, `rowSel` (`library.js`, Task 9); `targetSel` (`overview.js`, Task 9).
- Produces (`gateway.js`): `export function serverFor(map, selected) -> row | null` — the map row of
  kind `mcp_server` whose `name` is `selected.name`; `null` for another kind, no map or no row.
  `export function heldServer(model, selected) -> server | null` — from the gateway model's
  `kind === "kitden"` gateway, the entry of `servers` whose `name` is `selected.name` when the
  kind is `mcp_server`; else `null`.
- `showServer(name)` calls `setState({ selected: { kind: "mcp_server", name } })` before
  `openItem`; `showKitdenServer(server)` calls `setState({ selected: { kind: "mcp_server", name: server.name } })`
  (ruling P16). `renderGateway` takes the arrival only after it has drawn a model with gateways
  (its early returns leave the arrival pending): `heldServer(...)` opens with `showKitdenServer`;
  else it loads the map if needed and opens `serverFor(...)` with `openItem`; without either it
  opens nothing and says nothing. Builder call: a selection of another kind stays in the address
  for the next page.

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

test('a selected server the Kitden gateway holds opens in its own panel', () => {
  const model = { gateways: [{ kind: 'kitden', servers: [{ name: 'files' }] }, { kind: 'metamcp', servers: [{ name: 'x' }] }] };
  assert.equal(heldServer(model, { kind: 'mcp_server', name: 'files' }).name, 'files');
  assert.equal(heldServer(model, { kind: 'mcp_server', name: 'x' }), null);
  assert.equal(heldServer(model, { kind: 'skill', name: 'files' }), null);
  assert.equal(heldServer(null, { kind: 'mcp_server', name: 'files' }), null);
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

`test_page_words.py`: `'setState({ selected: { kind: "mcp_server", name: server.name } })' in script("gateway.js")`.

- [ ] **Step 2: Run them to see them fail**: `node --test tests/frontend/gateway.test.mjs tests/frontend/context.test.mjs` → FAIL.
- [ ] **Step 3: Implement** as the Interfaces say.
- [ ] **Step 4: Run** `node --test tests/frontend/*.test.mjs` and `uv run pytest tests/unit/test_page_words.py -q` → PASS.
- [ ] **Step 5: Hand check on the demo.** Run `uv run kitden demo --size medium --no-browser` in the
  background, open the printed link in the Browser pane, pick atlas, open `github` from an
  Overview note or card, go to Gateway by the rail, open `files` there, press Back: the address,
  the open Details and the project match each time. Stop the demo (its folder is deleted). Note
  it in the task report.
- [ ] **Step 6: Run all checks, then commit**

```bash
git add src/kitden/web/static/js/gateway.js docs/design.md tests/frontend/gateway.test.mjs \
  tests/frontend/context.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway opens the selected server; a test walks the three pages"
```

---

### Task 11: Docs and roadmap for Part 2

**Files:**
- Modify: `docs/design.md`, `README.md`, `tests/unit/test_docs_words.py`
- `ROADMAP.md` only if the owner has committed their edit (see Step 3)

- [ ] **Step 1: Read `docs/design.md` through once.** Tasks 1–10 each wrote their lines with
  their page change (master Rules). Check the part's lines read as one voice with no repeats and
  that every new word is pinned; fix only what that reading finds.
- [ ] **Step 2: Update `README.md`** (Library section, after "Pick a project at the top to see what
  loads in that folder."): "All projects shows what every project shares. In a project, each cell
  also says where the item applies: "all projects", "this project" or "project override"; how a
  client gets it, such as "through Claude Code's folder", is in the cell's hover text and in
  Details. "Available" means the client has it. "Unknown" means Kitden could not read it, so it
  may or may not be available; it never means missing. "Needs review" means another client has an
  item with the same name from another source. Where Kitden can add an item the cell says "+ Add";
  a skill only this project has adds into this project. Overview's notes are grouped by item. The
  address keeps the project and the item you opened, so a link or Back returns to it." Pin it:

```python
def test_readme_says_unknown_is_not_missing():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert '"Unknown" means Kitden could not read it, so it may or may not be available; it never means missing' in readme
```

  `docs/development.md` is unchanged: this part adds no real-client hand check.
- [ ] **Step 3: Roadmap.** If `git status` still shows `ROADMAP.md` modified by the owner, do not
  touch it; put these lines in the report. For "### Not released yet": "- **Shared words, scope
  and selection:** cells say "Available" or "Off"; "All projects" on every page; in a project
  every cell says "all projects", "this project" or "project override", and how a client gets an
  item is in the hover text; Unknown, Needs review and the last good read; "+ Add" wherever Kitden
  can add, and a project's own skill adds into that project; Overview notes grouped by item with
  their clients; every add names its scope; the project and the selected item stay in the
  address." For "## Later": "- Add a project's own MCP server to another client in that project
  (needs each client's project file, checked with a date)." Otherwise move Part 2's line from
  "## Planned" to "### Not released yet" with that text and add the Later line.
- [ ] **Step 4: Run all checks**: `uv run pytest -q && uv run ruff check . && uv run ruff format --check src tests && node --test tests/frontend/*.test.mjs`.
- [ ] **Step 5: Commit**

```bash
git add README.md tests/unit/test_docs_words.py
git commit -m "Docs: shared words, scope and selection"
```

(Add `docs/design.md` only when Step 1 changed it, and `ROADMAP.md` only when Step 3 edited it.)
