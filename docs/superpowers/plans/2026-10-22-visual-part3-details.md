# Part 3: One Details panel and one change flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Details answers five questions in order (what it is and its state; why; what the lead action changes; what to do; the evidence, folded), with links that keep the project and the item; every review leads with its outcome and scope, promises only the Undo it can keep, notices settings that changed under it, and Cancel goes back to the Details it came from.

**Architecture:** First the side panel (`panel.js`, 1366 lines) splits into four modules with no change in behaviour. The server then adds what a change to each definition reaches (`affects`, built from the same reader functions the review's steps use) and, in each preview, what the steps target (`target`) and the known Undo limit (`undo_note`). The page turns these into words with small pure functions tested in node. A stale review is found by asking the server after each rescan; the server reuses the engine's own Apply-time check.

**Tech Stack:** Python 3.13, Starlette; plain ES modules and one CSS file; pytest on sandbox homes; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-22-visual-management-design.md`, Part 3 (3.1–3.4), from concept §8 and §9. Master plan: `docs/superpowers/plans/2026-10-22-visual-management.md`; its Rules and "Names that cross part boundaries" bind this plan.

## Global Constraints

- `AGENTS.md` in full: simple English in code, UI and docs; Russian with the owner; tests on sandbox homes only (`make_home(...)`, `write_cursor_fixture_state(home)` from `tests/conftest.py`; the conftest guards stay on); dated facts about other tools.
- Stack unchanged: Python 3.13, Starlette, MCP SDK 2.3, tomlkit, watchfiles; plain ES modules, one CSS file; no framework, no bundler, no library from another site; strict CSP. No new runtime dependency.
- `docs/design.md` governs look and motion. "A part that changes a word changes its test and `docs/design.md` in the same commit." New page words are pinned in `tests/unit/test_page_words.py`; page helper logic is a pure exported function tested with `node --test tests/frontend/*.test.mjs`.
- Main pages show a name, the client, a state and an action. Paths, file keys and commands stay in Details (here: under "Technical details", or in a Details panel of their own).
- Every change of a client's settings: preview → Apply with a backup → verify → Undo, through `src/kitden/changes/engine.py`. This part adds no new kind of write.
- `explain()` and `project_views()` feed the read-only MCP server. This part does not change their output: page-only fields come from a separate function, and `tests/unit/test_mcp_server.py` checks they stay out.
- Exact words from the spec: the Affects line has the shape "Changes Codex and Cursor (Cursor reads Codex's folder). All projects."; "Compare across clients", "Manage tools", "Show on the map", "Technical details", "Other projects are unchanged.", "A backup is kept.", "Settings changed since this preview.", "Preview again". Scope phrases from Part 2: "all projects", "this project".
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`. All pass or the commit waits.
- Commits stage files by name (never `git add -A`, `git add .` or `git commit -a`); a short plain subject, no prefix, one to three lines, ending with the session's co-author line.
- `ROADMAP.md`: while `git status` shows the owner's uncommitted edit there, no task edits or stages it (Task 9 puts the lines in its report).

## Review Focus

1. A skill in a folder two clients read (Codex's `~/.agents/skills`, read by Cursor): Details names both clients and why, before any button is pressed. Task 2 `test_a_skill_in_a_shared_folder_reaches_every_reader`; Task 4 node test "the Affects line names every client the lead changes, and why".
2. A known project inside the target project (a parent folder holding a child project): the review never says "Other projects are unchanged.", because a parent's rules and files can reach the child. Task 5 `test_a_parent_project_with_a_known_project_inside_is_not_contained`.
3. Two project folders whose names only start alike (`work/web` and `work/website`): neither counts as inside the other. Task 5 `test_folders_that_only_start_alike_are_not_nested`.
4. The client itself rewrites a file while its review is open: the review says "Settings changed since this preview." and Apply gives way to "Preview again"; a review whose files did not change stays as it is. Task 7 `test_a_change_says_it_is_stale_once_its_file_changes`, `test_an_untouched_preview_is_not_stale`.
5. Cancel from a review started by a button under More, or a preview the server refuses: back to the same Details, focus on the pressed button or on More, the reason in a callout. Task 6 node tests "Cancel goes back to where the review came from" and "focus comes back to the pressed control, or to More when it was under More".

## Names this part shares with other parts

- Consumes (Part 1): the command `kitden demo`, named in the no-clients Details (Task 8); `kitden demo --size medium` for smoke checks.
- Consumes (Part 2): `goTo(view: string, selected: {kind, name} | null)` from `store.js` and `rowSel(row)` from `library.js` (Task 4); the phrases "all projects" / "this project"; `scopeWords(def, picked)` with its new words ("All projects", "This project", "Project api"); `ADDS`, `addScope(action, into)` and `reviewLede(action, picked)` in the review code (Task 5 widens `reviewLede`); the failed-source line in the Library answer's `notes` (2.3), beside which Task 8 puts the loading line; `clientStatus(client)` in overview.js, which already shows an unreadable client as "Could not read".
- Produces: `affects: {clients: string[], scope: "all" | "project", note: str | None}` in the `/api/explain` answer, on each definition Kitden can change (`definitions[i].affects`), with the master plan's name and shape; the answer becomes `{definitions, inherits}`. Builder call: on each definition, not one field at the top of the answer, because the lead action is chosen by the page (`footerActions`) from row flags, the Gateway model and the Library's adds, which `/api/explain` does not see (the master table says so).
- Produces for Part 6: `contextLinks(row, definitions, view)` in `details.js`; Part 6 adds its "Show on the map" entry last, and Part 7 leaves it out if walkthrough 2 hides the map.
- Produces for Parts 4 and 5: `PLACE_IN_TITLE` in `review.js` (Task 5), the actions whose title already names its place; Part 5 adds `gateway.forget`.
- Later parts edit these modules, not `panel.js`, for the functions that move here (Task 1 lists them); their new node tests go in `details.test.mjs`, `review.test.mjs` or a new `tools.test.mjs`.

---

### Task 1: Split the side panel into four modules (no behaviour change)

**Files:**
- Modify: `src/kitden/web/static/js/panel.js` (keeps the shell: `isPanelOpen`, `swapContent`, `openPanel`, `closePanel`, `cancelPreview`, `restoreFocus`, `header`, `callout`, `openInfo`, `openChange`, `checkMark`, the toast, `trapFocus`, `initPanel`; re-exports the rest)
- Create: `src/kitden/web/static/js/details.js` (the "Item details" block through `showCommands`: `KIND_WORDS`, `kindWord`, `ACTION_BUTTONS`, `openItem`, `loadsLede`, `itemHeader`, `sideEffect`, the move and held helpers, `footerActions`, `footerButtons`, `offerLabel`, `scopeWords`, `layerState`, `layer`, `switchNode`, `pluginSwitch`, `countedDefinition`, `showDetails`, `showCommands`)
- Create: `src/kitden/web/static/js/tools.js` (`projectLabel`, `toolRows`, `callsText`, `writingToolsOn`, `reloadTools`, `refreshTools`, `toolsSection`)
- Create: `src/kitden/web/static/js/review.js` (the "Change review" block through `undoChange`: `DONE_WORDS`, `changeWords`, `alignGroups`, `chosenKeys`, `alignSection`, `leftOutText`, `canShowReview`, `review`, `afterParts`, `showReview`, `lockReview`, Apply, `changeOutcome`, `undoChange`; and Part 2's `ADDS`, `addScope`, `reviewLede`)
- Modify: `src/kitden/web/static/js/dom.js` (`withFocusKey` moves here from panel.js)
- Test: `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: `panel.js` `export const panelState = { current: null, from: null }`: `current` is the old module variable `current` (what is open); `from` is filled in Task 6. `swapContent(content)`, `header(kicker, title, lede, closeLabel = "Close", mono = false)`, `callout(text, level = "warn")`, `cancelPreview()`, `restoreFocus()`, `checkMark()` become exports. Every name that another module or a node test imports from `panel.js` when this task starts (Part 2's `scopeWords`, `ADDS`, `addScope`, `reviewLede` included) is re-exported from there (`export { … } from "./details.js";` and so on), so no importer and no node test changes. `tools.js`: `export let tools` (a live binding; `undoChange` in review.js reads it as before). `dom.js`: `withFocusKey(box, key) -> Element | null`.

- [ ] **Step 1: Write the failing test** in `tests/unit/test_page_words.py`, and in the same edit replace every other `script("panel.js")` in the file with `panel()` (the assertions stay as they are):

```python
PANEL = ("panel.js", "details.js", "tools.js", "review.js")


def panel() -> str:
    """The side panel's modules as one text, so a pin does not depend on which file holds it."""
    return "\n".join(script(name) for name in PANEL)


def test_the_side_panel_is_four_modules():
    shell = script("panel.js")
    for name in PANEL[1:]:
        assert (STATIC / "js" / name).exists() and f'from "./{name}"' in shell, name
    assert "function trapFocus" in shell and "function showReview" not in shell
    assert "function showDetails" in script("details.js")
    assert "function showReview" in script("review.js")
```

- [ ] **Step 2: Run it to see it fail:** `uv run pytest tests/unit/test_page_words.py -q` → FAIL (no `details.js`).
- [ ] **Step 3: Move the code.** Each function moves as it is. `current` becomes `panelState.current` everywhere. Inside the four modules, import a name from the module that defines it, never through the re-exports. The modules import each other in a cycle (details ↔ review ↔ tools ↔ panel); that is fine because no module calls an import at load time. `APPLY_KEY` and `WRITING` go with review.js; take `CLIENT_ORDER` and `CLIENT_NAMES` from parts.js.
- [ ] **Step 4: Run all four checks.** Expected: PASS, and no test file changed except `test_page_words.py`.
- [ ] **Step 5: Smoke check** in `uv run kitden demo --size medium` (Part 1): open a Details, a tool switch, a review, Apply, Undo from the toast. Everything behaves as before.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/web/static/js/panel.js src/kitden/web/static/js/details.js src/kitden/web/static/js/tools.js src/kitden/web/static/js/review.js src/kitden/web/static/js/dom.js tests/unit/test_page_words.py
git commit -m "Panel: split Details, tools and review into their own files"
```

---

### Task 2: What a change to a definition reaches (server)

**Files:**
- Create: `src/kitden/views/affects.py`
- Modify: `src/kitden/views/explain.py` (new `with_page_fields`; `explain()` itself unchanged), `src/kitden/web/app.py` (`_explain`)
- Test: `tests/unit/test_affects.py` (create), `tests/unit/test_api_views.py`, `tests/unit/test_mcp_server.py`

**Interfaces:**
- Consumes: `skill_readers(inventory, item)`, `CLIENTS`, `CLIENT_WORDS` from `views/skills.py` (`skill_readers` gives the `readers` a skill removal step carries, which `_readers` in app.py sends as `reaches`); `_inherits()` in app.py (the flags `/api/offer` sends).
- Produces: `affects(inventory, item: Item) -> dict` returning `{"clients": list[str], "scope": "all" | "project", "note": str | None}`. `with_page_fields(definitions: list[dict], inventory) -> list[dict]`: every definition gains `"key": str | None` (`item.source.key_path`); one with actions gains `"affects"`. `/api/explain` answers `{"definitions": [...], "inherits": {"plugin": bool, "skill": bool}}`.

The rule (the review's reader logic, per definition):

```
clients = [item.client]; notes = []
a skill: each other client in skill_readers(inventory, item)
         → add it; note "<Reader> reads <Client>'s folder"
any other kind in user scope: each other client with an item of the same kind and name whose
         source.owner_client == item.client (Cursor's import of a Claude Code user plugin; the
         `via` of a row's warning, which sideEffect names) → add it; note "<Other> loads <Client>'s copy"
clients in CLIENTS order, each once; note = "; ".join(notes) or None
scope = "project" if item.project and item.scope in (Scope.PROJECT, Scope.LOCAL) else "all"
```

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_affects.py: the base fixture, as tests/unit/test_explain.py builds it
@pytest.fixture
def inventory(tmp_path):
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return build_inventory(home)


def _item(inventory, client, name, scope):
    return next(i for i in inventory.items if (i.client, i.name, i.scope) == (client, name, scope))


def test_a_skill_in_a_shared_folder_reaches_every_reader(inventory):
    item = _item(inventory, "codex", "docker-expert", Scope.USER)
    assert affects(inventory, item) == {
        "clients": ["codex", "cursor"], "scope": "all", "note": "Cursor reads Codex's folder",
    }


def test_a_claude_code_user_plugin_reaches_cursor_which_loads_its_copy(inventory):
    item = _item(inventory, "claude_code", "superpowers@claude-plugins-official", Scope.USER)
    assert affects(inventory, item) == {
        "clients": ["claude_code", "cursor"], "scope": "all", "note": "Cursor loads Claude Code's copy",
    }


def test_a_project_plugin_does_not_reach_cursor(inventory):
    item = _item(inventory, "claude_code", "superpowers@claude-plugins-official", Scope.PROJECT)
    assert affects(inventory, item) == {"clients": ["claude_code"], "scope": "project", "note": None}


def test_a_local_entry_reaches_one_project(inventory):
    item = _item(inventory, "claude_code", "local-db", Scope.LOCAL)
    assert affects(inventory, item) == {"clients": ["claude_code"], "scope": "project", "note": None}
```

```python
# tests/unit/test_api_views.py
def test_explain_says_what_a_change_reaches(client):
    answer = client.get("/api/explain?kind=skill&name=docker-expert").json()
    codex = next(d for d in answer["definitions"] if d["client"] == "codex")
    assert codex["affects"]["clients"] == ["codex", "cursor"]
    assert all("key" in d for d in answer["definitions"])
    assert all("affects" not in d for d in answer["definitions"] if not d["actions"])
    assert set(answer["inherits"]) == {"plugin", "skill"}
```

```python
# tests/unit/test_mcp_server.py
async def test_explain_item_has_no_page_fields(home):
    data = await call(server_for(home), "explain_item", name="docker-expert")
    assert data["definitions"]
    assert all("affects" not in d and "key" not in d for d in data["definitions"])
```

- [ ] **Step 2: Run them to see them fail:** `uv run pytest tests/unit/test_affects.py tests/unit/test_api_views.py tests/unit/test_mcp_server.py -q`.
- [ ] **Step 3: Implement** `affects` and `with_page_fields` (find each definition's item by `id` in one dict), and in `_explain` return `{"definitions": with_page_fields(definitions, state.inventory), "inherits": _inherits()}`.
  Builder call: an add's reach is worked out on the page from `inherits` (Task 4), the rule `alsoLoads` in offer.js already follows, so the Library's add cells keep their shape and the exact cells in `tests/unit/test_library.py` stay.
- [ ] **Step 4: Run** the three files and `uv run pytest tests/security -q` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/views/affects.py src/kitden/views/explain.py src/kitden/web/app.py tests/unit/test_affects.py tests/unit/test_api_views.py tests/unit/test_mcp_server.py
git commit -m "Details: say which clients a change to each definition reaches"
```

---

### Task 3: Details in order: why first, evidence folded (3.1 steps 1, 2 and 5)

**Files:**
- Modify: `src/kitden/web/static/js/details.js` (`showDetails`, `layer`; new pure functions), `src/kitden/web/static/style.css` (`.why-lines`, `details.tech`), `docs/design.md`
- Test: `tests/frontend/details.test.mjs` (create; the same `matchMedia` and `navigator` stubs as `panel.test.mjs`), `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `def.key` (Task 2); `fold(details)` from motion.js.
- Produces:
  - `DETAILS_ORDER = ["warnings", "about", "why", "clients", "tools", "secret", "next", "links", "technical"]` and `detailsOrder(present: Set<string>) -> string[]` (the ids in that order). "next" is the Affects line (Task 4) or why nothing can be done, then the move notes; "links" is Task 4's.
  - `originWords(def, here: string | null) -> string`: `through <Owner>` when `owner_client` is another known client; else by scope: project or local → "from this project" when `def.project === here`, else `from <folder>`; user → "from all projects"; plugin → "from a plugin"; managed → "from your organization"; account → "from your Claude account".
  - `whyLines(definitions, here) -> string[]`, at most two lines; none for instruction files (their own lines say when they are read). Line one: the clients whose definition loads (state known), grouped by `originWords`, in client order: "Codex and Cursor load it from all projects." / "Claude Code loads it from all projects; Cursor through Claude Code." Line two, the first rule that applies: a definition overridden by another of the same client ("In Claude Code, the one from this project overrides the one from all projects."); merged ("In Claude Code, the ones from this project and from all projects are merged."); turned off ("Turned off in Codex."); state unknown ("Codex keeps its on/off state where Kitden cannot read it."); only in other projects, with All projects picked ("It is in 2 projects; it loads only there.").
  - `fileScopeWords(def) -> string`: the file-scope words `scopeWords(def)` used before Part 2 ("Global settings", "Project website", "Only on this Mac · website", "From a plugin", "Claude account", "Managed by your organization", plus " · via <Owner>"). Part 2's `scopeWords(def, picked)` keeps titling the client sections; this old table lives on only in the fold, since spec 2.1 keeps "global settings" only in the technical evidence.
  - `techRows(definitions) -> Array<{ client, title, path, key, summary, preview }>`: one per definition with a path (a `source` with a "/"), key, summary or preview, in client order; `title` is `<Client> · <fileScopeWords>`.

- [ ] **Step 1: Write the failing tests**

```js
const def = (fields) => ({ kind: 'skill', scope: 'user', project: null, enabled: 'on', owner_client: fields.client, loads: true, overridden: false, merged: false, ...fields });
const site = '/Users/me/work/website';

test('Details keeps the five questions in order', () => {
  assert.deepEqual(detailsOrder(new Set(DETAILS_ORDER)), ['warnings', 'about', 'why', 'clients', 'tools', 'secret', 'next', 'links', 'technical']);
  assert.deepEqual(detailsOrder(new Set(['technical', 'why', 'next'])), ['why', 'next', 'technical']);
});

test('why says where it loads from and the rule that decides', () => {
  assert.deepEqual(whyLines([def({ client: 'codex' }), def({ client: 'cursor', owner_client: 'shared' })], null), ['Codex and Cursor load it from all projects.']);
  assert.deepEqual(whyLines([def({ client: 'claude_code', scope: 'project', project: site }), def({ client: 'claude_code', loads: false, overridden: true })], site),
    ['Claude Code loads it from this project.', 'In Claude Code, the one from this project overrides the one from all projects.']);
  assert.deepEqual(whyLines([def({ client: 'claude_code', kind: 'plugin' }), def({ client: 'cursor', kind: 'plugin', owner_client: 'claude_code' })], null),
    ['Claude Code loads it from all projects; Cursor through Claude Code.']);
  assert.deepEqual(whyLines([def({ client: 'codex', loads: false, enabled: 'off' })], null), ['Turned off in Codex.']);
  assert.deepEqual(whyLines([def({ client: 'codex', loads: false, enabled: 'unknown' })], null), ['Codex keeps its on/off state where Kitden cannot read it.']);
  assert.deepEqual(whyLines([def({ client: 'claude_code', scope: 'project', project: '/a/site', loads: false }), def({ client: 'claude_code', scope: 'project', project: '/a/api', loads: false })], null),
    ['It is in 2 projects; it loads only there.']);
  assert.deepEqual(whyLines([def({ client: 'codex', kind: 'instructions' })], null), []);
});

test('technical details keep the path, the key, the command and the first lines', () => {
  const rows = techRows([
    { client: 'cursor', scope: 'user', project: null, source: '/Users/me/.cursor/mcp.json', key: 'mcpServers.github', summary: 'npx -y github-mcp', preview: null },
    { client: 'claude_code', scope: 'user', project: null, source: '/Users/me/.claude/CLAUDE.md', key: null, summary: null, preview: ['# rules'] },
    { client: 'claude_code', scope: 'account', project: null, source: 'account', key: null, summary: null, preview: null },
  ]);
  assert.deepEqual(rows.map((r) => [r.client, r.path, r.key, r.summary, r.preview]), [
    ['claude_code', '/Users/me/.claude/CLAUDE.md', null, null, ['# rules']],
    ['cursor', '/Users/me/.cursor/mcp.json', 'mcpServers.github', 'npx -y github-mcp', null],
  ]);
  assert.equal(rows[1].title, 'Cursor · Global settings');
});
```

```python
def test_details_answer_in_order_and_fold_the_evidence():
    details = script("details.js")
    assert "for (const id of detailsOrder(" in details
    assert '"Technical details"' in details and "fold(" in details
    assert 'el("pre", "preview"' in details  # the first lines, now inside the fold
    assert "details.tech" in CSS and ".why-lines" in CSS
```

- [ ] **Step 2: Run them to see them fail:** `node --test tests/frontend/details.test.mjs` and `uv run pytest tests/unit/test_page_words.py -q`.
- [ ] **Step 3: Implement.** `showDetails` builds a `Map` of block id → nodes and appends them with `for (const id of detailsOrder(new Set(blocks.keys())))`. "about" is `about(offer)`; "why" is `whyLines(definitions, projectPath())` as quiet lines; "next" holds the `whyNoAction` line when nothing can be done (it used to come first) and the two move notes. `layer(def)` loses its path, summary and preview lines. "technical" is a `<details class="tech">` with `<summary>Technical details</summary>` and one block per `techRows` row (title; path with `shortPath` and the whole path in `title`; key and command in mono; the preview as `el("pre", "preview", …)`), passed through `fold()`; it is left out when `techRows` is empty.
  Builder call: the secret note ("This entry holds a secret…") stays in the body as "secret", not in the fold.
- [ ] **Step 4: Update `docs/design.md`:** a "Details" table under Components with rows Order (the five steps, the block ids in words), Why (one or two quiet lines) and Technical details (folded, the `<details>` look of "Show file change"); the "Instruction file Details" row says the path and the first 12 lines sit under Technical details.
- [ ] **Step 5: Run** all four checks → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/web/static/js/details.js src/kitden/web/static/style.css docs/design.md tests/frontend/details.test.mjs tests/unit/test_page_words.py
git commit -m "Details: say why first and fold paths and commands"
```

---

### Task 4: The Affects line and links that keep context (3.1 step 3, 3.2)

**Files:**
- Modify: `src/kitden/web/static/js/details.js` (`openItem` keeps `inherits`; `showDetails` fills "next" and "links"), `src/kitden/web/static/style.css` (`.affects`, `.links`), `docs/design.md`
- Test: `tests/frontend/details.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `definitions[i].affects` and `answer.inherits` (Task 2); the lead shapes `footerActions` returns (an offer `{def, action}`, the string `"move"`, an add option `{client, add, label}`, the form option `{form: true}`); `moveFor(...)` (`move.items` are definition ids); Part 2's `goTo(view, selected)`, imported from `store.js` (never from app.js, which runs `start()` when loaded), and `rowSel(row)` from `library.js`.
- Produces:
  - `addReach(client, action, inherits, found: string[], asks: boolean) -> { clients: string[], note: string | null }`: a skill copy (`skill.install`, `plugin.skills`) to Codex reaches Cursor when Cursor is found ("Cursor reads Codex's folder"); to Claude Code when Cursor is found and `inherits.skill` ("Cursor reads Claude Code's folder"); `plugin.install` to Claude Code reaches Cursor when Cursor is found, `inherits.plugin` and not `asks` ("Cursor loads Claude Code's plugins"); anything else only `client`.
  - `affectsFor(lead, { definitions, move, inherits, found, project }) -> { clients, note, scope: "all" | "project", project: string | null, asks: boolean } | null`: an offer → its definition's `affects` and `def.project` (null when the server sent none); `"move"` → the union over the definitions in `move.items` (scope "project" only if all are, notes joined with "; "); an add → `addReach(...)`, scope "all", `asks = Boolean(project && add.project_place)`; the form or no lead → null.
  - `affectsText(affects, here: string | null) -> string`: `Changes <clients joined>` + ` (<note>)` + `.` then one of: "You choose this project or all projects next." (asks), "This project only." (scope project and `project === here`), `Only in <folder>.` (scope project, another folder), "All projects.".
  - `contextLinks(row, definitions, view) -> Array<{ label, view, selected: { kind, name } }>`: "Compare across clients" → `library` unless `view` is library; "Manage tools" → `gateway` when a definition has `via_gateway === "kitden"`, unless `view` is gateway. `selected` is Part 2's `rowSel(row)` for the Library and `{ kind: "mcp_server", name: row.name }` for the Gateway (its `showServer` finds a server by name).

- [ ] **Step 1: Write the failing tests**

```js
const codexDef = { id: 'd1', client: 'codex', project: null, affects: { clients: ['codex', 'cursor'], scope: 'all', note: "Cursor reads Codex's folder" } };

test('the Affects line names every client the lead changes, and why', () => {
  const affects = affectsFor({ def: codexDef, action: 'skill.remove' }, { definitions: [codexDef] });
  assert.equal(affectsText(affects, null), "Changes Codex and Cursor (Cursor reads Codex's folder). All projects.");
});

test('a project definition names its project', () => {
  const local = { id: 'd2', client: 'claude_code', project: site, affects: { clients: ['claude_code'], scope: 'project', note: null } };
  const affects = affectsFor({ def: local, action: 'mcp.remove_direct' }, { definitions: [local] });
  assert.equal(affectsText(affects, site), 'Changes Claude Code. This project only.');
  assert.equal(affectsText(affects, null), 'Changes Claude Code. Only in website.');
});

test('a move names every client whose entry moves', () => {
  const cc = { id: 'e1', client: 'claude_code', project: null, affects: { clients: ['claude_code'], scope: 'all', note: null } };
  const cx = { id: 'e2', client: 'codex', project: null, affects: { clients: ['codex'], scope: 'all', note: null } };
  assert.equal(affectsText(affectsFor('move', { definitions: [cc, cx], move: { items: ['e1', 'e2'], gateways: [{}] } }), null), 'Changes Claude Code and Codex. All projects.');
});

test('an add names what its copy reaches, and says when the place is chosen next', () => {
  const inherits = { plugin: true, skill: true };
  const found = ['claude_code', 'codex', 'cursor'];
  assert.deepEqual(addReach('codex', 'skill.install', inherits, found, false), { clients: ['codex', 'cursor'], note: "Cursor reads Codex's folder" });
  assert.deepEqual(addReach('claude_code', 'plugin.install', inherits, found, false), { clients: ['claude_code', 'cursor'], note: "Cursor loads Claude Code's plugins" });
  assert.deepEqual(addReach('claude_code', 'plugin.install', inherits, found, true), { clients: ['claude_code'], note: null });
  assert.deepEqual(addReach('codex', 'skill.install', inherits, ['codex'], false), { clients: ['codex'], note: null });
  const add = { client: 'codex', add: { action: 'skill.install', project_place: true }, label: 'Add to Codex…' };
  assert.equal(affectsText(affectsFor(add, { definitions: [], inherits, found, project: 'p1' }), site),
    "Changes Codex and Cursor (Cursor reads Codex's folder). You choose this project or all projects next.");
});

test('nothing to lead, the Add form, or no answer from the server: no Affects line', () => {
  assert.equal(affectsFor(null, { definitions: [] }), null);
  assert.equal(affectsFor({ form: true, label: 'Add…' }, { definitions: [] }), null);
  assert.equal(affectsFor({ def: { id: 'x', client: 'codex' }, action: 'plugin.disable' }, { definitions: [] }), null);
});

test('links lead to another page with the same item', () => {
  const row = { kind: 'mcp_server', name: 'files' };
  const held = [{ via_gateway: 'kitden' }];
  assert.deepEqual(contextLinks(row, held, 'overview').map((l) => [l.label, l.view]), [['Compare across clients', 'library'], ['Manage tools', 'gateway']]);
  assert.deepEqual(contextLinks(row, held, 'library').map((l) => l.label), ['Manage tools']);
  assert.deepEqual(contextLinks(row, [{ via_gateway: null }], 'gateway').map((l) => l.label), ['Compare across clients']);
  assert.deepEqual(contextLinks(row, held, 'overview')[0].selected, { kind: 'mcp_server', name: 'files' });
});
```

```python
def test_details_say_what_the_lead_changes_and_link_to_the_other_pages():
    details = script("details.js")
    for words in ('"Compare across clients"', '"Manage tools"', '"This project only."',
                  '"You choose this project or all projects next."', '"All projects."'):
        assert words in details, words
    assert "affectsText(affectsFor(" in details
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** `openItem` keeps the whole answer: `definitions` and `inherits` (default `{ plugin: false, skill: false }`) go on `panelState.current` and into `showDetails(row, definitions, offer, toolsNext, inherits)`. "next" starts with `affectsText(affectsFor(actions.lead, …), projectPath())` as `p.affects` when `affectsFor` is not null. "links" is one quiet row of `btn small ghost` buttons, each with `dataset.focus = "link:<view>"`; pressing one closes the panel (`keepSelection: true, focus: false`) and calls `goTo(link.view, link.selected)`.
  Builder call: "Show on the map" is added to `contextLinks` by Part 6, once the map exists; no feature switch now.
  Builder call: a link shows only where it leads elsewhere, and "Manage tools" only for a server in the Kitden gateway (the only servers with tool switches).
  Builder call: an add that asks "this project or all projects" names only what both choices reach, and the review after the choice names the rest.
- [ ] **Step 4: Update `docs/design.md`:** Details table rows Affects (one quiet line above the footer, in the words above, only when something leads) and Links (quiet ghost buttons; they keep project and item).
- [ ] **Step 5: Run** all four checks → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/web/static/js/details.js src/kitden/web/static/style.css docs/design.md tests/frontend/details.test.mjs tests/unit/test_page_words.py
git commit -m "Details: name what the lead action changes, and link to Library and Gateway"
```

---

### Task 5: The review leads with the outcome (3.3)

**Files:**
- Create: `src/kitden/views/review.py`
- Modify: `src/kitden/views/after.py` (`REMOVE_NOTE` moves to review.py and leaves the After chips), `src/kitden/web/app.py` (`preview`: the answer gains `target` and `undo_note`), `src/kitden/web/static/js/review.js` (`changeWords`, `showReview`, `applyChange` copies `target` to the applied change as it copies `align`), `docs/design.md`
- Test: `tests/unit/test_review_scope.py` (create), `tests/unit/test_after.py`, `tests/unit/test_remove_plugin.py`, `tests/unit/test_api_changes.py`, `tests/frontend/review.test.mjs` (create), `tests/frontend/panel.test.mjs` (Part 2's `reviewLede` asserts), `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `Step.scope`, `Step.edit.key`, `copy.target`, `removal.path`; the known project paths (`state.inventory.projects`); Part 2's `ADDS`, `addScope(action, into)` (an add's " for all projects" / " in <folder>", from the request) and `reviewLede(action, picked)` ("Adds for all projects. " first for an add with All projects picked).
- Produces (Python): `step_project(step: Step, projects: list[str]) -> str | None`; `change_target(change: Change, projects: list[str]) -> {"scope": "project" | "all" | "mixed", "project": str | None, "others_unchanged": bool}`; `undo_note(change: Change) -> str | None`; `REMOVE_NOTE` lives in `views/review.py`. The preview answer has `"target"` and `"undo_note"` (the Add missing list with no steps has neither).
- Produces (JS, review.js): `targetWords(target, folder) -> string` (`" in <folder>"`, `" for all projects"` or `""`); `export const PLACE_IN_TITLE = ["gateway.rule", "gateway.rules", "gateway.strict", "project.align"]` (their titles name their place already, so `changeWords` adds no scope words; Part 5 adds `gateway.forget`). Part 2's `reviewLede` widens to `reviewLede(change, picked) -> string`, reading `change.action`, `change.target` and `change.undo_note`: "Adds for all projects. " (Part 2's rule) or "Other projects are unchanged. ", then "Nothing is written until you press Apply. A backup is kept.", then the Undo note when there is one.

The rule ("only when the steps guarantee it"):

```
step_project(step, projects), each folder compared by os.path.realpath and Path.is_relative_to:
  key[:3] == ("rules", "projects", P)               → P   (a Kitden gateway rule for one project)
  step.scope is LOCAL and key[:2] == ("projects", P) → P   (Claude Code's entry for one project in ~/.claude.json)
  step.scope is PROJECT → the deepest known project folder holding the step's target
                          (edit path, copied folder target, removed folder)
  otherwise None; a P that is not a known project is None; the result is the project's path
  as the known list spells it
change_target:
  "project" when every step has the same project; "all" when no step has PROJECT or LOCAL
  scope and none is a project rule; "mixed" otherwise (a project step outside known projects too)
  others_unchanged = scope == "project" and no other known project folder lies inside it
undo_note: REMOVE_NOTE when the action is plugin.remove and a step is Claude Code's; else None
```

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_review_scope.py: synthetic steps, folders under tmp_path
def test_one_project_file_is_that_project_and_others_are_unchanged(tmp_path): ...
    # a PROJECT step editing <web>/.mcp.json, projects [<web>, <api>]
    # → {"scope": "project", "project": str(web), "others_unchanged": True}
def test_a_parent_project_with_a_known_project_inside_is_not_contained(tmp_path): ...
    # projects [<work>, <work>/site]; a gateway rule step with key ("rules", "projects", str(work), "github", "server")
    # → scope "project", project str(work), others_unchanged False
def test_folders_that_only_start_alike_are_not_nested(tmp_path): ...
    # projects [<work>/web, <work>/website]; a PROJECT step in <work>/web → others_unchanged True;
    # step_project of a file in <work>/website/.mcp.json is <work>/website, never <work>/web
def test_a_local_entry_in_claude_json_counts_as_its_project(tmp_path): ...
    # LOCAL step on <home>/.claude.json, key ("projects", str(web), "mcpServers", "db") → project str(web)
def test_user_files_are_all_projects_and_a_mix_is_mixed(tmp_path): ...
    # USER step only → "all"; USER + PROJECT → "mixed"; a PROJECT step outside every known project → "mixed"
def test_a_project_reached_through_a_link_still_matches(tmp_path): ...
    # the known project is a symlink to the real folder; the step's path is the real one → that project
def test_removing_a_claude_code_plugin_names_the_undo_limit():
    assert undo_note(Change(action="plugin.remove", steps=[step("claude_code", "x@a")])) == (
        "Undo installs it again; its saved options are not brought back."
    )
    assert undo_note(Change(action="plugin.disable", steps=[step("claude_code", "x@a")])) is None
```

```python
# tests/unit/test_api_changes.py
def test_a_preview_names_its_target(client):
    local = next(i for i in client.get("/api/items?client=claude_code&kind=mcp_server").json() if i["name"] == "local-db")
    body = {"action": "mcp.remove_direct", "targets": [{"item": local["id"]}], "params": {}}
    answer = client.post("/api/changes/preview", json=body, headers=POST).json()
    # No other known project lies inside work/website in the base fixture.
    assert answer["target"] == {"scope": "project", "project": str(client.home / "work/website"), "others_unchanged": True}
    assert answer["undo_note"] is None
```

In `tests/unit/test_remove_plugin.py` and `tests/unit/test_after.py`, the Claude Code After entry loses its `"note"`, and the removal tests in test_remove_plugin.py also assert `change["undo_note"] == "Undo installs it again; its saved options are not brought back."`.

```js
// tests/frontend/review.test.mjs
const target = (scope, project = null, others = false) => ({ scope, project, others_unchanged: others });
const remove = { action: 'mcp.remove_direct', steps: [{ client: 'codex', name: 'neon' }] };
const add = { action: 'skill.install', steps: [{ client: 'codex', name: 'tidy', reaches: ['codex'] }] };
const NOTE = 'Undo installs it again; its saved options are not brought back.';

test('the title names the scope the steps target', () => {
  assert.deepEqual(changeWords({ ...remove, target: target('project', '/Users/me/work/website', true) }), { title: 'Remove neon from Codex in website', done: 'Removed neon from Codex in website' });
  assert.equal(changeWords({ ...remove, target: target('all') }).title, 'Remove neon from Codex for all projects');
  assert.equal(changeWords(remove).title, 'Remove neon from Codex'); // no target (an old change): today's words
  // The steps decide over the request: a mix says no scope, even for an add.
  assert.equal(changeWords({ ...add, target: target('mixed') }, { params: { skill: 'x' } }).title, 'Add tidy to Codex');
  assert.equal(changeWords(add, { params: { skill: 'x' } }).title, 'Add tidy to Codex for all projects'); // no target: Part 2's addScope
  // A title that names its place keeps it once.
  const rule = { action: 'gateway.rule', steps: [{ client: 'kitden', name: 'slow' }], target: target('all') };
  assert.equal(changeWords(rule, { params: { server: 'echo', tool: 'slow', state: 'off', project: null } }).title, 'Turn off slow of echo in all projects');
});

test('the lede promises only the Undo it can keep', () => {
  assert.equal(reviewLede({ ...remove, target: target('project', '/a/web', true), undo_note: null }, 'p1'), 'Other projects are unchanged. Nothing is written until you press Apply. A backup is kept.');
  assert.equal(reviewLede({ action: 'plugin.remove', target: target('all'), undo_note: NOTE }, ''), `Nothing is written until you press Apply. A backup is kept. ${NOTE}`);
  assert.equal(reviewLede({ ...add, target: target('all'), undo_note: null }, ''), 'Adds for all projects. Nothing is written until you press Apply. A backup is kept.');
  assert.equal(reviewLede(remove, ''), 'Nothing is written until you press Apply. A backup is kept.');
});
```

Part 2's `reviewLede(action, picked)` asserts in `panel.test.mjs` move to the new signature and lose ", so you can undo".

```python
def test_the_review_leads_with_the_outcome_and_keeps_undo_honest():
    review = script("review.js")
    assert "Other projects are unchanged." in review and "A backup is kept." in review
    assert "so you can undo" not in panel()
    assert "after.target = change.target" in review
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** `preview` adds `target = change_target(change, [p.path for p in state.inventory.projects])` and `undo_note(change)` to the answer. `changeWords` adds the scope words to title and done: `targetWords(change.target, folder)` when `change.target` is set and the action is not in `PLACE_IN_TITLE`, else Part 2's `addScope(action, into)` as today. `showReview` passes `reviewLede(change, state.project)` to `header` as the lede.
  Builder call: "Other projects are unchanged." also needs no other known project inside the target folder: a gateway rule passes down to a child project, and a client may read a parent's files.
  Builder call: the title keeps naming the clients the steps write to or reach (today's `clients`); a client reached only through an import (Cursor loading a Claude Code plugin) stays in its After chip with its note.
  Builder call: the only known Undo limit today is a removed Claude Code plugin's saved options; it moves from the After chip to the lede so it is said once.
- [ ] **Step 4: Update `docs/design.md`:** a "Review" table under Components: Title (the outcome, its scope, its clients), Lede (the sentences above, in order), then After chips and the folded file change as today.
- [ ] **Step 5: Run** all four checks → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/views/review.py src/kitden/views/after.py src/kitden/web/app.py src/kitden/web/static/js/review.js docs/design.md tests/unit/test_review_scope.py tests/unit/test_after.py tests/unit/test_remove_plugin.py tests/unit/test_api_changes.py tests/frontend/review.test.mjs tests/frontend/panel.test.mjs tests/unit/test_page_words.py
git commit -m "Review: lead with the outcome and its scope, promise only the Undo it keeps"
```

---

### Task 6: Cancel goes back to the Details it came from (3.4)

**Files:**
- Modify: `src/kitden/web/static/js/details.js` (`showDetails` sets `panelState.from` and records the pressed control; `backToDetails`; focus keys on its controls), `src/kitden/web/static/js/review.js` (Cancel; a refused preview), `src/kitden/web/static/js/panel.js` (`closePanel` sets `panelState.from = null`), `docs/design.md`
- Test: `tests/frontend/details.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `panelState` (Task 1), `withFocusKey` (dom.js).
- Produces: `panelState.from = { row, definitions, offer, inherits, focus: string | null } | null`; `cancelTarget({ back, from }) -> "back" | "details" | "close"`; `focusAfterBack(key, keys: string[]) -> string | null` (the key when present, else `"more"` when present, else null); `backToDetails({ error = null } = {}) -> void`. Focus keys (`dataset.focus`) in Details: `offer:<def id>:<action>`, `move`, `add:<client>`, `add:form`, `held:<label>`, `more`, `commands`, `switch:<def id>`, `link:<view>`.

- [ ] **Step 1: Write the failing tests**

```js
test('Cancel goes back to where the review came from', () => {
  assert.equal(cancelTarget({ back: () => {}, from: { row: {} } }), 'back'); // a tool switch's own way back
  assert.equal(cancelTarget({ back: null, from: { row: {} } }), 'details');
  assert.equal(cancelTarget({ back: null, from: null }), 'close');
});

test('focus comes back to the pressed control, or to More when it was under More', () => {
  assert.equal(focusAfterBack('offer:d1:skill.remove', ['offer:d1:skill.remove', 'more']), 'offer:d1:skill.remove');
  assert.equal(focusAfterBack('offer:d2:plugin.disable', ['more', 'move']), 'more');
  assert.equal(focusAfterBack(null, ['move']), null);
});
```

```python
def test_cancel_and_a_refused_preview_go_back_to_details():
    review, shell = script("review.js"), script("panel.js")
    assert "cancelTarget(" in review and "backToDetails({ error: reason })" in review
    assert "panelState.from = null" in shell
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** `showDetails` sets `panelState.from` and adds one capture click listener to its body and one to its footer that store the nearest `[data-focus]` key in `from.focus`. Cancel follows `cancelTarget`: `back()` as today, `backToDetails()`, or `closePanel()`; `cancelPreview()` runs first in every case. `backToDetails` redraws Details from `from` (no new read), puts an error callout first when given one, and focuses `focusAfterBack(from.focus, keys in the drawer)`, else the drawer. In `review()`, a refused preview with no `back` and with `from` set calls `backToDetails({ error: reason })` instead of opening the "Could not prepare this change" panel. An info panel between Details and the review (the Move or Add choice) keeps `from`, so Cancel still lands on Details.
  Builder call: a refused preview from Details returns there with the reason, as tool switches already do (design.md "A switch changes").
- [ ] **Step 4: Update `docs/design.md`:** the "A switch changes" row's Cancel sentence moves to a Details row "Cancel" that covers every review opened from Details.
- [ ] **Step 5: Run** all four checks → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/web/static/js/details.js src/kitden/web/static/js/review.js src/kitden/web/static/js/panel.js docs/design.md tests/frontend/details.test.mjs tests/unit/test_page_words.py
git commit -m "Review: Cancel goes back to Details, focus where it was"
```

---

### Task 7: A review notices settings that changed (3.4)

**Files:**
- Modify: `src/kitden/changes/engine.py` (`stale_reason`; `_apply` uses the same checks), `src/kitden/web/app.py` (`change_view`), `src/kitden/web/static/js/app.js` (`listen`), `src/kitden/web/static/js/review.js` (`staleCheckWanted`, `checkStale`), `src/kitden/web/static/js/panel.js` (`initPanel` listens), `docs/design.md`
- Test: `tests/unit/test_engine.py`, `tests/unit/test_api_changes.py`, `tests/frontend/review.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: `Engine.stale_reason(change_id: str) -> str | None`: why Apply would stop as stale now, or None; it reads the targets and changes nothing; None unless the change is previewed. `Engine._first_stale(change, current: dict[str, bytes | None]) -> str | None`: the checks `_apply` runs today (`_stale`, `_stale_copy`, `_stale_removal`), now shared by both. `GET /api/changes/{id}` gains `"stale": bool` for a change the engine holds (checked in a thread). Page event `kitden:rescanned`, sent by app.js on `rescan_finished` before `liveRefresh()`. `staleCheckWanted(current, busy) -> boolean`: true only for an open review whose change has an id and state `previewed`, while no change is being written.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_engine.py (make_engine, toml_step, config as the file has them)
def test_stale_reason_sees_a_file_changed_after_preview(tmp_path, config):
    engine = make_engine(tmp_path)
    change = engine.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])
    config.write_text(CONFIG + "# edited by hand\n")
    assert "changed since preview" in engine.stale_reason(change.id)
    assert change.state is ChangeState.PREVIEWED  # only looked


def test_an_untouched_preview_is_not_stale(tmp_path, config):
    engine = make_engine(tmp_path)
    change = engine.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])
    assert engine.stale_reason(change.id) is None
```

```python
# tests/unit/test_api_changes.py
def test_a_change_says_it_is_stale_once_its_file_changes(client):
    # preview removing Codex's direct `neon` entry (as the file's other tests find items), then:
    assert client.get(f"/api/changes/{change['id']}").json()["stale"] is False
    config = client.home / ".codex/config.toml"
    config.write_text(config.read_text() + "\n# edited by hand\n")
    assert client.get(f"/api/changes/{change['id']}").json()["stale"] is True
```

```js
test('only an open, previewed review is checked, never while a change is written', () => {
  const review = { type: 'review', change: { id: 'c1', state: 'previewed' } };
  assert.equal(staleCheckWanted(review, { change: false }), true);
  assert.equal(staleCheckWanted(review, { change: true }), false);
  assert.equal(staleCheckWanted({ type: 'review', change: { id: 'c1', state: 'verified' } }, { change: false }), false);
  assert.equal(staleCheckWanted({ type: 'review', change: { state: 'previewed' } }, { change: false }), false); // Add missing with nothing chosen
  assert.equal(staleCheckWanted({ type: 'item' }, { change: false }), false);
});
```

```python
def test_a_review_says_when_its_settings_changed():
    assert '"kitden:rescanned"' in script("app.js") and '"kitden:rescanned"' in script("panel.js")
    review = script("review.js")
    assert "Settings changed since this preview." in review and '"Preview again"' in review
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** `checkStale()` (registered in `initPanel` for `kitden:rescanned`): when `staleCheckWanted(panelState.current, busy)`, read `GET /api/changes/{id}`; if `stale` is true and the same review is still open, put the callout "Settings changed since this preview." first in the body (role `alert`) and replace Apply with a primary "Preview again" that cancels this preview (`cancelPreview()`) and calls `review(previewBody, { note, back })`; focus moves to it only if it was on Apply.
  Builder call: the page asks the server about the open change after each rescan; the server compares the files with the preview's own hashes, so no list of changed files goes over the event stream.
  Builder call: the check runs on every `rescan_finished`, also while someone types in the review (only the page redraw waits for typing).
- [ ] **Step 4: Update `docs/design.md`:** a Review row "Settings changed": the callout stays until the next action (Motion principle 4), Apply gives way to "Preview again".
- [ ] **Step 5: Run** all four checks → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/changes/engine.py src/kitden/web/app.py src/kitden/web/static/js/app.js src/kitden/web/static/js/review.js src/kitden/web/static/js/panel.js docs/design.md tests/unit/test_engine.py tests/unit/test_api_changes.py tests/frontend/review.test.mjs tests/unit/test_page_words.py
git commit -m "Review: say when the settings changed since the preview"
```

---

### Task 8: No clients, and sources still being read (3.4)

**Files:**
- Modify: `src/kitden/web/static/js/library.js` (`noClients` exported and given a Details button; the loading line above the table), `src/kitden/web/static/js/overview.js` (the no-clients box), `src/kitden/web/static/js/parts.js` (`lookFor`, `sourceLines`), `src/kitden/web/static/js/app.js` (`showScan` redraws the Library when its lines change), `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/parts.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `/api/clients` rows (`id`, `display_name`, `status`, `config_roots`); the first scan's steps (`name`, `done`, `later`) in `data.progress`; Part 1's `kitden demo`; Part 2's failed-source line above the Library table.
- Produces: `lookFor(clients) -> Array<{ name, where }>`: Claude Code, Codex and Cursor in that order, `where` = `shortPath(config_roots[0])`; `sourceLines(progress, kind) -> string[]`: `Still checking <step name>…` for each open later step that changes this tab (`LATER_KINDS = { "Codex plugins": ["plugin"] }`); `noClients({ overview = true } = {}) -> Element`.

- [ ] **Step 1: Write the failing tests**

```js
test('no clients: the page names each client and where Kitden looks', () => {
  const client = (id, display_name, root) => ({ id, display_name, status: 'not_found', config_roots: [`/Users/me/${root}`] });
  const clients = [client('claude_code', 'Claude Code', '.claude'), client('codex', 'Codex', '.codex'), client('cursor', 'Cursor', '.cursor'),
    { id: 'claude_desktop_code_tab', display_name: 'Claude Desktop (Code tab)', status: 'found', config_roots: ['/x'] }];
  assert.deepEqual(lookFor(clients), [{ name: 'Claude Code', where: '~/.claude' }, { name: 'Codex', where: '~/.codex' }, { name: 'Cursor', where: '~/.cursor' }]);
});

test('a source still being read says so on the tab it changes', () => {
  const open = { ready: true, steps: [{ name: 'Codex plugins', done: false, later: true }, { name: 'marketplaces', done: false, later: true }] };
  assert.deepEqual(sourceLines(open, 'plugin'), ['Still checking Codex plugins…']);
  assert.deepEqual(sourceLines(open, 'mcp_server'), []);
  assert.deepEqual(sourceLines({ ready: true, steps: [{ name: 'Codex plugins', done: true, later: true }] }, 'plugin'), []);
  assert.deepEqual(sourceLines(null, 'plugin'), []);
});
```

```python
def test_no_clients_says_what_kitden_looks_for_and_offers_the_demo():
    library = script("library.js")
    assert "Kitden found no AI coding clients." in library and '"Open Overview"' in library
    assert "It looks for Claude Code, Codex and Cursor." in library
    assert "kitden demo" in library and "lookFor(" in library
    assert "noClients(" in script("overview.js")
    assert "sourceLines(" in library and "sourceLines(" in script("app.js")
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** `noClients()`: "Kitden found no AI coding clients.", the quiet line "It looks for Claude Code, Codex and Cursor.", a "Details" button, and "Open Overview" when `overview` is true. Details (`openInfo("Clients", "What Kitden looks for", …)`): one line per `lookFor` row (`<name> · <where>`), "It finds a client by that folder or by its command.", "To try Kitden on a sample setup, run this in a terminal:" and a `pre` with `kitden demo`. The Overview shows `noClients({ overview: false })` above its all-clear line when `data.clients` is read and no client is found. The Library draws `sourceLines(data.progress, kind)` as quiet `p.note` lines above the table, beside Part 2's failed-source line; `showScan` calls `render()` when the Library is shown and `sourceLines` for its tab differs before and after.
  Builder call: the folders and the command sit behind Details, as AGENTS.md asks for paths and commands on main pages.
  Builder call: the command shown is `kitden demo`, as the spec words it.
  Builder call: only the Codex plugins step changes what a Library tab shows (the marketplaces step only reads ahead), so only it gets a line.
- [ ] **Step 4: Update `docs/design.md`:** Components rows "No clients" and "Still checking" (a quiet line above the table on the tab it changes; the top bar keeps its own line).
- [ ] **Step 5: Run** all four checks → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/web/static/js/library.js src/kitden/web/static/js/overview.js src/kitden/web/static/js/parts.js src/kitden/web/static/js/app.js src/kitden/web/static/style.css docs/design.md tests/frontend/parts.test.mjs tests/unit/test_page_words.py
git commit -m "Page: say what Kitden looks for, and which source is still read"
```

---

### Task 9: Docs and roadmap for Part 3

**Files:**
- Modify: `README.md` (the Library paragraph on Details; "Check every change before it is written"), `docs/development.md` ("Check before a release": one more hand check), `docs/design.md` (one read-through), `tests/unit/test_docs_words.py`
- `ROADMAP.md` only under the master plan's rule below.

- [ ] **Step 1: Write the failing test**

```python
def test_readme_says_what_details_and_a_review_start_with():
    readme = " ".join((ROOT / "README.md").read_text().split())
    for words in ("Technical details", "Other projects are unchanged.", "Settings changed since this preview."):
        assert words in readme, words
```

- [ ] **Step 2: Run it to see it fail.**
- [ ] **Step 3: Write the README sentences** (short, plain): Details says why an item loads and which clients and projects its action changes before you press it; paths and commands wait under Technical details; links open the same item in the Library or the Gateway. Every review starts with what will happen, where and in which clients, says "Other projects are unchanged." only when that is sure, and names what Undo cannot bring back; if the file changes while the review is open, it says "Settings changed since this preview." and offers Preview again; Cancel goes back to Details.
- [ ] **Step 4: Add the hand check** to `docs/development.md`, after step 22: "23. Open a review (Remove for a Claude Code plugin), then turn that plugin off in Claude Code itself. After the rescan the review says "Settings changed since this preview." and offers "Preview again"; Apply is gone." and the line "Not run yet for step 23: Part 3 of visual management was tested with sandbox files only."
- [ ] **Step 5: Read `docs/design.md`** once for this part's rows (Details, Review, No clients, Still checking): one voice, no repeats, every new word in a test.
- [ ] **Step 6: ROADMAP.** If `git status` still shows `ROADMAP.md` modified by the owner, do not touch it; the report gives this line for "### Not released yet": "Details answer five questions in order: what it is, why, what an action changes before you press it, what to do, and the paths and commands folded; links open the same item in the Library or the Gateway. Reviews start with the outcome and its scope, promise only the Undo they keep, notice settings that changed, and Cancel goes back to Details." Once the owner has committed it, move Part 3's line from "## Planned" to "### Not released yet" with these words, and stage `ROADMAP.md` too.
- [ ] **Step 7: Run all four checks** → PASS.
- [ ] **Step 8: Commit**

```bash
git add README.md docs/development.md docs/design.md tests/unit/test_docs_words.py
git commit -m "Docs: Part 3 of visual management"
```

---

## Self-review

| Spec | Where |
| --- | --- |
| 3.1 step 1, kind, name, state (today's lede) | unchanged header; Task 3 keeps warnings and `about` first |
| 3.1 step 2, Why from `why()`, `shadowed`, origin; then per-client sections | Task 3 `whyLines` (from `loads`, `overridden`, `merged`, `enabled`, `owner_client`, scope) |
| 3.1 step 3, Affects from `_readers`, `CURSOR_IMPORT` | Task 2 server (`skill_readers`, the Claude Code copy rule), Task 4 line |
| 3.1 step 4, lead action and More | unchanged footer; its `data-focus` keys in Task 6 |
| 3.1 step 5, Technical details folded | Task 3 |
| 3.2 Compare across clients, Manage tools | Task 4; "Show on the map" goes to Part 6 (`contextLinks`) |
| 3.3 outcome first, scope, clients; "Other projects are unchanged."; lede and Undo limit | Task 5 |
| 3.4 Cancel back to Details with focus | Task 6 |
| 3.4 stale review, "Preview again" | Task 7 |
| 3.4 no clients, `kitden demo` | Task 8 |
| 3.4 partial scan and failed source | Task 8 (loading line); the failed-source line is Part 2's (2.3) |
| Done: node tests for order and Affects; a stale test; page words | Tasks 3, 4, 7; every task pins its words |
