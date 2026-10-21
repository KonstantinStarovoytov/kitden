# Part 6: The whole picture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Library shows the instruction files, commands and agents each client loads, globally and per project, read-only; and the page says how many tools a server adds.

**Architecture:** One new `ItemKind.INSTRUCTIONS`, read by the three adapters with the same `Reader` and `Item` shapes the skills use, shown by the existing load map and Library as a sixth tab with no actions. Details shows the path and the first lines through `redact`. Tool counts come from the gateway's tool cache.

**Tech Stack:** Python 3.13, Starlette; plain ES modules; pytest on sandbox homes; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-21-review-follow-up-design.md`, Part 6 (6.1, 6.2). Master plan: `docs/superpowers/plans/2026-10-21-review-follow-up.md` (fixed name: `ItemKind.INSTRUCTIONS = "instructions"` with `summary` `("category", …)`; review focus 2).

## Global Constraints

- Code, comments, UI text and docs in simple English (`AGENTS.md`).
- Reading never writes; this part adds no action.
- Main pages: a name, the client and an action; the path and the file's first lines stay in Details.
- `docs/design.md`: the Library row's line one is the name in mono then a quiet word (here the category); tabs get a count; new words tested in `tests/unit/test_page_words.py`.
- Every file location is checked against the client's docs with the date in a comment.
- Everything shown passes `redact` or `redact_text`; a fixture file holds a `SENTINEL_SECRET_` line so `tests/security/test_no_secrets.py` would catch a leak.
- Tests on sandbox homes. Before each commit: `uv run pytest -q`, `uv run ruff check .`, `node --test tests/frontend/*.test.mjs`. Commit subjects plain, no prefix.

## Review Focus

1. A huge or binary `CLAUDE.md`: Details shows at most the first 12 lines, each cut at 200 characters, and never fails on bytes that are not text (Task 5 test `test_the_preview_is_short_and_survives_bytes`).
2. A project the client knows but whose folder is gone: no instruction rows for it, no error (Task 2 test `test_a_missing_project_gives_no_instruction_rows`).
3. The same name in two clients (`AGENTS.md` for Codex and Cursor): one row, two cells, and no duplicate finding (Task 4 test `test_agents_md_is_one_row_for_codex_and_cursor_without_a_finding`).
4. A `commands` folder with a file that is not `.md` or a sub-folder: skipped (Task 2 test `test_only_markdown_files_are_commands`).
5. A server's tool count when the cache has an empty list: "0 tools" is not shown; nothing is (Task 6 test `test_an_empty_tool_list_shows_no_count`).

---

### Task 1: The kind, the helper and the fixtures (6.1)

**Files:**
- Modify: `src/kitden/model.py:54-59` (`ItemKind.INSTRUCTIONS = "instructions"`)
- Modify: `src/kitden/clients/base.py:109-140` (after `skill_items`: `instruction_items`)
- Create fixtures: `tests/fixtures/claude_code/2.1.283/home/.claude/CLAUDE.md`, `.claude/commands/review.md`, `.claude/agents/reviewer.md`, `work/website/CLAUDE.md`, `work/website/.claude/commands/deploy.md`; `tests/fixtures/codex/0.159.2/home/.codex/AGENTS.md`, `work/api/AGENTS.md`; `tests/fixtures/cursor/3.21.16/home/work/site/.cursor/rules/style.mdc`, `work/site/.cursorrules`. One of them (`.claude/CLAUDE.md`) holds the line `token: SENTINEL_SECRET_INSTRUCTIONS`.
- Test: `tests/unit/test_model.py`, `tests/unit/test_read_claude_code.py` (the existing "every item" assertions gain the new rows)

**Interfaces:**
- Produces: `instruction_items(client: str, files: list[tuple[Path, str]], scope: Scope, owner: str, project: str | None = None) -> list[Item]`: for each `(path, category)` whose file exists, an `Item(kind=ItemKind.INSTRUCTIONS, name=<file name for "instructions", the stem for "command" and "agent">, source=file_source(path, owner), scope=scope, project=project, summary=(("category", category),))`. `expand(folder: Path, category) -> list[tuple[Path, str]]`: every `*.md` file directly in `folder`, sorted, no sub-folders.

- [ ] **Step 1: Write the failing tests**

```python
def test_instruction_items_name_files_and_stems(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# rules\n")
    (tmp_path / "commands").mkdir(); (tmp_path / "commands/review.md").write_text("x"); (tmp_path / "commands/notes.txt").write_text("x")
    items = instruction_items("claude_code", [(tmp_path / "CLAUDE.md", "instructions"), *expand(tmp_path / "commands", "command")], Scope.USER, "claude_code")
    assert [(i.name, dict(i.summary)["category"]) for i in items] == [("CLAUDE.md", "instructions"), ("review", "command")]
    assert all(i.kind is ItemKind.INSTRUCTIONS for i in items)
```

- [ ] **Step 2: Run it to see it fail**.
- [ ] **Step 3: Implement** the kind and the helper; add the fixture files (short, two or three lines each).
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_model.py tests/unit/test_read_claude_code.py tests/unit/test_read_codex.py tests/unit/test_read_cursor.py -v`: the helper test passes; the read tests still pass (the adapters do not read the new files yet).
- [ ] **Step 5: Commit**

```bash
git add src/kitden/model.py src/kitden/clients/base.py tests/fixtures tests/unit/test_model.py
git commit -m "Model: an instructions kind"
```

---

### Task 2: Claude Code reads its instructions, commands and agents (6.1)

**Files:**
- Modify: `src/kitden/clients/claude_code.py` (the user scan near the skills read; `_project(...)` near line 416)
- Test: `tests/unit/test_read_claude_code.py`

**Interfaces:**
- Produces: user scope: `~/.claude/CLAUDE.md` (instructions), `~/.claude/commands/*.md` (command), `~/.claude/agents/*.md` (agent); project scope for each known project: `<p>/CLAUDE.md`, `<p>/.claude/CLAUDE.md`, `<p>/CLAUDE.local.md` (instructions), `<p>/.claude/commands/*.md`, `<p>/.claude/agents/*.md`.

- [ ] **Step 1: Check the Claude Code docs** (memory: CLAUDE.md locations; slash commands; subagents) and write `# checked YYYY-MM-DD` with each location.
- [ ] **Step 2: Write the failing tests**

```python
def test_scan_reads_instructions_commands_and_agents(tmp_path, no_version):
    home = make_home(tmp_path, "claude_code/2.1.283")
    found = {(i.scope, i.name, dict(i.summary)["category"]) for i in ClaudeCodeAdapter(home).scan().items if i.kind is ItemKind.INSTRUCTIONS}
    assert found == {(Scope.USER, "CLAUDE.md", "instructions"), (Scope.USER, "review", "command"), (Scope.USER, "reviewer", "agent"), (Scope.PROJECT, "CLAUDE.md", "instructions"), (Scope.PROJECT, "deploy", "command")}


def test_a_missing_project_gives_no_instruction_rows(tmp_path, no_version):
    # .claude.json names a project folder that does not exist → no INSTRUCTIONS items for it, scan succeeds


def test_only_markdown_files_are_commands(tmp_path, no_version):
    # add .claude/commands/notes.txt and .claude/commands/sub/x.md → neither is an item
```

- [ ] **Step 3: Run them to see them fail**.
- [ ] **Step 4: Implement**; update the expected sets of the existing read tests that count every item.
- [ ] **Step 5: Run** the file → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/clients/claude_code.py tests/unit/test_read_claude_code.py
git commit -m "Claude Code: read CLAUDE.md, commands and agents"
```

---

### Task 3: Codex and Cursor read their instructions (6.1)

**Files:**
- Modify: `src/kitden/clients/codex.py:355-390` (user: `~/.codex/AGENTS.md`; project: `<p>/AGENTS.md`), `src/kitden/clients/cursor.py:160-200` (project: `<p>/.cursor/rules/*.mdc` as category `instructions`, `<p>/.cursorrules`; `<p>/AGENTS.md` only if Cursor's docs say it reads it)
- Test: `tests/unit/test_read_codex.py`, `tests/unit/test_read_cursor.py`

- [ ] **Step 1: Check the Codex docs** (AGENTS.md discovery: home and project) and the Cursor docs (rules folder, `.cursorrules`, AGENTS.md); write the dates. User-level Cursor rules live in Cursor's settings and are not read: say so in the docstring.
- [ ] **Step 2: Write the failing tests** (as Task 2's, with the fixture names: Codex `AGENTS.md` user and project; Cursor `style` with category `instructions` from `.cursor/rules/style.mdc`, `.cursorrules`).
- [ ] **Step 3: Run them to see them fail**.
- [ ] **Step 4: Implement**; update existing expected sets.
- [ ] **Step 5: Run** both files → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/clients/codex.py src/kitden/clients/cursor.py tests/unit/test_read_codex.py tests/unit/test_read_cursor.py
git commit -m "Codex and Cursor: read their instruction files"
```

---

### Task 4: The Instructions tab (6.1)

**Files:**
- Modify: `src/kitden/views/library.py:18` (`KINDS = (..., "instructions")`), `465-535` (`built["instructions"] = _map_rows(map_rows, "instructions", found)`), `src/kitden/views/load_map.py` (nothing to rank: a row per name; the cell's `where` as for hooks), `src/kitden/views/effective.py` (no `RANKS` entry: nothing to change, add a test), `src/kitden/views/findings.py:27` (`DUPLICATE_KINDS` unchanged: add a test), `src/kitden/views/explain.py:27-46` (`brief` carries `category`), `src/kitden/mcp_server.py:36-45` (`ABOUT` and `show_setup`'s description name instruction files)
- Modify: `src/kitden/web/static/js/library.js` (the `KINDS` list the tabs draw: `["instructions", "Instructions"]`; `metaText(row)` shows the category as the quiet word)
- Test: `tests/unit/test_library.py`, `tests/unit/test_findings.py`, `tests/unit/test_mcp_server.py`, `tests/unit/test_page_words.py`, `tests/frontend/library.test.mjs`

- [ ] **Step 1: Write the failing tests**

```python
def test_the_instructions_tab_lists_files_per_client_and_project(home):
    answer = library(inventory, adapters(home), None, gateway_registered=False, kind="instructions")
    names = {(r["name"], r["category"]) for r in answer["rows"]}
    assert ("CLAUDE.md", "instructions") in names and ("AGENTS.md", "instructions") in names
    assert all(c["add"] is None for r in answer["rows"] for c in r["cells"].values())


def test_agents_md_is_one_row_for_codex_and_cursor_without_a_finding(home):
    # with the Cursor fixture's work/site/AGENTS.md (only if Task 3 reads it) or the Codex one in two projects:
    # one row named AGENTS.md; find_findings has no DUPLICATE_IN_CLIENT for kind instructions


def test_show_setup_names_instruction_files():
    assert "instruction files" in create_server(lambda: Inventory()).instructions
```

```js
test('an instructions row shows its category as the quiet word', () => {
  assert.equal(metaText({ kind: 'instructions', name: 'review', category: 'command', source: null }), 'command');
});
```

Words test: `library.js` has `"Instructions"` as a tab label.

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_library.py tests/unit/test_findings.py tests/unit/test_mcp_server.py tests/unit/test_page_words.py -v` and `node --test tests/frontend/library.test.mjs` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/views src/kitden/mcp_server.py src/kitden/web/static/js/library.js tests
git commit -m "Library: an Instructions tab"
```

---

### Task 5: Details shows the path and the first lines (6.1)

**Files:**
- Modify: `src/kitden/views/explain.py:72-120` (`explain(...)`: for `ItemKind.INSTRUCTIONS` each definition gains `"preview": list[str]`: the first 12 lines of the file, each cut at 200 characters, read with `errors="replace"`, each through `redact_text`)
- Modify: `src/kitden/web/static/js/panel.js:286-320` (`layer(def)`: a `<pre class="preview">` under the path when `def.preview`)
- Test: `tests/unit/test_explain.py`, `tests/security/test_no_secrets.py` (already scans `/api/explain`; add the instructions name to its list of queries), `tests/unit/test_page_words.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_the_preview_is_short_and_survives_bytes(home):
    path = home / ".claude/CLAUDE.md"
    path.write_bytes(b"# rules\n" + b"x" * 500 + b"\n" + b"\xff\xfe\n" + b"line\n" * 20)
    definitions = explain(build_inventory(home), "CLAUDE.md", "instructions", None)
    preview = definitions[0]["preview"]
    assert len(preview) == 12 and len(preview[1]) == 200 and "�" in preview[2]


def test_the_preview_hides_a_secret_line(home):
    definitions = explain(build_inventory(home), "CLAUDE.md", "instructions", None)
    assert any("[secret]" in line for d in definitions for line in d["preview"])
    assert not any("SENTINEL_SECRET" in line for d in definitions for line in d["preview"])
```

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**; `redact_text` hides only token shapes, so the fixture's secret line uses a token shape (`token: sk-SENTINEL_SECRET_INSTRUCTIONS_0000000000`) or `redact` of a `key: value` pair is used per line; choose the one that makes the test pass and keep the sentinel in the fixture.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_explain.py tests/security -v` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/views/explain.py src/kitden/web/static/js/panel.js tests
git commit -m "Library: Details shows an instruction file's first lines"
```

---

### Task 6: Tool counts (6.2)

**Files:**
- Modify: `src/kitden/local_gateway/views.py:87-99` (`held_servers(settings, chain, tools: dict | None = None)`: each row gains `"tools": int | None`, `None` when the server is not in the cache or its list is empty), `src/kitden/web/app.py:618-623` (`_gateway_view` passes `load_tools(home)`), `src/kitden/views/explain.py` (an MCP server definition gains `"tools": int | None` from the cache when the name is there)
- Modify: `src/kitden/web/static/js/gateway.js:222-236` (`heldRow`: the quiet `12 tools` after the Local/Remote flag), `panel.js:286-320` (`layer(def)`: `12 tools` line for an MCP server definition)
- Test: `tests/unit/test_local_gateway_views.py`, `tests/unit/test_explain.py`, `tests/frontend/gateway.test.mjs`

- [ ] **Step 1: Write the failing tests**

```python
def test_held_rows_count_known_tools(home):
    rows = held_servers(settings, [], {"github": [tool("a"), tool("b")]})
    assert {r["name"]: r["tools"] for r in rows} == {"github": 2, "notion": None}


def test_an_empty_tool_list_shows_no_count(home):
    assert held_servers(settings, [], {"github": []})[0]["tools"] is None
```

```js
test('a held row says how many tools when it knows', () => {
  assert.equal(toolsWord({ name: 'github', tools: 12 }), '12 tools');
  assert.equal(toolsWord({ name: 'github', tools: 1 }), '1 tool');
  assert.equal(toolsWord({ name: 'github', tools: null }), null);
});
```

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement** (`export function toolsWord(server)` in `gateway.js`).
- [ ] **Step 4: Run the tests** → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/local_gateway/views.py src/kitden/web/app.py src/kitden/views/explain.py src/kitden/web/static/js tests
git commit -m "Gateway: say how many tools a server adds"
```

---

### Task 7: Docs and roadmap for Part 6

**Files:**
- Modify: `README.md` (Library: the Instructions tab, one or two sentences; the "Let your agents ask" line names instruction files), `ROADMAP.md` (Part 6 from "## Planned" to "### Not released yet")

- [ ] **Step 1: Write the README sentences**.
- [ ] **Step 2: Update ROADMAP.md**.
- [ ] **Step 3: Run all checks**: `uv run pytest -q && uv run ruff check . && node --test tests/frontend/*.test.mjs`
- [ ] **Step 4: Commit**

```bash
git add README.md ROADMAP.md
git commit -m "Docs: Part 6 of the review follow-up"
```
