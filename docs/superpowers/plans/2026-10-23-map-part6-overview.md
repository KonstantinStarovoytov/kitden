# Part 6: Instructions, Overview and Changes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Library's Instructions tab becomes a tree (clients → files → what a file pulls in),
with Claude Code's `@` imports and its own reading of AGENTS.md; the Overview gets one card per
item and a small "Your setup" tree; Changes becomes a timeline by day with Details beside it and
"See it on the map"; then the walkthrough 2 script.

**Architecture:** The server learns two facts about Claude Code (AGENTS.md without a CLAUDE.md,
and `@path` imports) in a reader and a pure function, `views/imports.py`. A new read model,
`views/instructions.py`, joins instruction items by file path for the page only
(`GET /api/instructions`); `/api/explain` gains page-only `imports` and `lines` through
`with_page_fields`, so the MCP server's answers do not change. The three pages draw with Part 4's
map core, Details column and words. Every page helper is a pure exported function with a node test.

**Tech Stack:** Python 3.13, Starlette; plain ES modules and one CSS file; pytest on sandbox homes
and Part 1's samples; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-23-map-pages-design.md`, Part 6 (6.1–6.4), with the
shared pieces S.1–S.8, Owner decisions, Constraints and Anti-goals. Master plan:
`docs/superpowers/plans/2026-10-22-visual-management.md` (its Rules and "Names that cross part
boundaries" bind this plan). Branch `map-part6-overview`, from `main` after Part 5 is merged.

## Global Constraints

- `AGENTS.md` in full: simple English in code, comments, UI and docs; Russian with the owner;
  tests on sandbox homes only (`make_home`, `write_cursor_fixture_state`, `build_demo_home`; the
  conftest guards stay on); dated facts about other tools; short plain commit messages.
- Stack unchanged; no new runtime dependency; strict CSP; no library from another site. Maps use
  Part 4's map core (`map.js`), plain SVG under HTML blocks.
- This part adds no write. "The tab only reads." Every change still goes through preview → Apply
  with a backup → verify → Undo in `src/kitden/changes/engine.py`.
- Main pages show a name, the client, a state and an action. Paths, import paths, commands and
  first lines stay under "Technical details".
- `explain()` and `project_views()` feed the read-only MCP server. "Imports go to the page only,
  never into the MCP server's answers." Page-only fields come from `with_page_fields` and
  `/api/instructions`; `tests/unit/test_mcp_server.py` checks they stay out.
- "The page opens as fast as today." No new request at start: `/api/instructions` is read only
  when the Instructions tab opens; the Overview uses `/api/overview`, `/api/map` and
  `/api/gateway-view`, which the page reads today.
- "Sign-in (S1) waits." No sign-in card, no "Sign in…" (owner, 2026-10-23).
- Words: "On" (not "Available") and "This project" / "Only this project" come from Part 4 (S.1).
  Spec copy used here: "Pulls in", "Claude Code may ask before it reads this.", "42 lines",
  "Compare across clients", "Your setup, connected.", "Needs attention", "Can improve",
  "N more servers skip the gateway", "N projects · K have their own rules", "not tested",
  "Today", "Yesterday", "Applied and checked", "Undone", "Not applied: the file changed first",
  "Kept · Undo puts it back", "14:02 Preview → 14:02 Applied → 14:02 Checked",
  "See it on the map", "This item is no longer there.".
- `docs/design.md` changes in the same commit as the page change it describes; new words are
  pinned in `tests/unit/test_page_words.py`, a changed word changes its pin in that commit.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`,
  `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`. All pass or
  the commit waits. Stage files by name; message: a short plain subject, one to three lines, the
  session's co-author line.
- `ROADMAP.md` has the owner's uncommitted edit: no task edits or stages it (Task 10 puts the
  lines in the report). No task edits `design/` or the owner's research files.

## Review Focus

1. **An `@` that is not an import** (an email `a@b.com`, `` `@x.md` ``, a fenced block, a quoted
   path, a missing file, a folder): nothing shows under "Pulls in". Task 2
   `test_code_spans_fenced_blocks_quotes_and_emails_are_not_imports`,
   `test_a_missing_file_or_a_folder_is_left_out`.
2. **An import loop or a long chain** (A pulls in B, B pulls in A; five files deep): each file
   once, four hops at most, the page never hangs. Task 2 `test_a_loop_is_read_once`,
   `test_imports_stop_after_four_hops`.
3. **A project with AGENTS.md and a CLAUDE.local.md, or a CLAUDE.md in a folder above it:**
   Claude Code is not named under "Read by"; `~/.claude/CLAUDE.md` alone does not stop it. Task 1
   `test_claude_code_reads_agents_md_only_where_the_project_has_no_claude_md`.
4. **Two files with one name** (`~/.codex/AGENTS.md` and a project's `AGENTS.md`): two blocks,
   each with its own readers, never one row. Task 3 `test_files_join_by_path_not_by_name`.
5. **"See it on the map" for a change whose item is gone** (an applied Remove, an undone Add):
   it says "This item is no longer there." and opens nothing; an undone Remove opens the item.
   Task 8 node test "a change that removed its item has no place".

## Names this part shares

| Consumes | From | Use here |
| --- | --- | --- |
| `build_demo_home(root, size)`, `demo_page(root, size)`, the medium "Sample contract" (`code-review`, `atlas`, `api-style`, `docs`, `files`, `read_file`, `web`) | 1 | tests, walkthrough 2 |
| `goTo(view, selected)`, `go`, `parseSel`, `selFor`, `takeArrival`, `libraryChoice`, `ALL_PROJECTS` | 2 | arrivals, "See it on the map" |
| `header(...)`, `openChange`, `undoChange` (`panel.js`); `techRows`, `technical`, `linksRow`, `followLink`, `kindWord` (`details.js`); `/api/explain` `{definitions, inherits}`, `with_page_fields` | 3 | Details |
| `openPanel(content, { instant, dock })`, `DOCK_MIN`, `docksAt`; `factsBlock(rows)` (a value may be a Node); `detailsCard({ kind, title, id, facts, why, actions, more, after, technical }) -> Node[]`, each action `{label, run?, body?, primary?}`, `after` a node under the actions; `layoutTree(model, { open: Set, width, narrow })`, `toggleOpen`, `litPath` (follows `on`, `direct`, `faint`), `litFrom(model, id)`, `findIn`, `drawMap`; the tree model with `group` blocks (`group:<id>`) and client blocks `client:<id>`; `cutName`; `state.mode` (hash `view=map\|list`; a `mode` passed to `go`/`goTo` is kept), `MAP_AT`, `viewMode(state, count)`; sel kinds `tool`, `client` (lights `litFrom`) and `group` (opens List at that group); `goTo(view, selected, { project })` calling `switchProject(id)` in `store.js`; `/api/projects` `own_rules`; `--dim`, `--preview-fill`, `--preview-line`; `STATE_WORDS.on = "On"` | 4 | all three pages |
| `TABS` "Plugins and skills" \| "Instructions" and `libraryTab(kind)` (the tab is `kind=instructions`); the Instructions tab's List (today's table, "until Part 6"); the Library's Map \| List and Find wiring (`MAP_PAGES`); `linkKind(cell) -> "on" \| "faint" \| null` in `librarytree.js`; `show=diff`; "Add missing plugins and skills…" | 5 | Tasks 4, 6, walkthrough 2 |

| Produces | Used by |
| --- | --- |
| `views/imports.py`: `Import`, `imports(path, home, project, hops=4) -> list[Import]` | 6 |
| `views/instructions.py`: `instruction_files(inventory, project, home) -> list[dict]`; `GET /api/instructions` | 6, 8 (tour) |
| `changePlace(entry) -> {view, selected, project} \| null` in `changes.js` | 6, 8 |
| `docs/research/walkthrough-script-2.md` | owner, 7 |

`changePlace` returns `project` (the change's project path, or null), and "See it on the map"
passes it to Part 4's `goTo(view, selected, { project })`, so a tool rule of `website` opens the
Gateway in `website` (ruled; the master table says so).

Builder call: the master table says Part 6 makes "See it on the map" work through
`contextLinks`. There is no separate map page now, so Changes uses `changePlace` with Part 3's
`followLink`, and `contextLinks` does not change.

Builder call: Part 7's Task 2 lists Claude Code's AGENTS.md. This part builds it (Task 1); Part 7
Task 2 keeps only Cursor's agents and agents named by `name:` (as `part7-additions.md` item 44
says).

---

### Task 1: Claude Code reads AGENTS.md when a project has no CLAUDE.md

**Files:**
- Modify: `src/kitden/clients/claude_code.py` (`scan`, `_project_files`; new `agents_mode`,
  `_claude_md_above`), `src/kitden/clients/versions.py` (new `at_least`),
  `src/kitden/views/explain.py` (`reads`), `src/kitden/demo/sample.py` (`website/AGENTS.md`)
- Test: `tests/unit/test_read_claude_code.py`, `tests/unit/test_explain.py`,
  `tests/unit/test_demo_home.py`

**Interfaces:**
- Produces: `AGENTS_MD_FROM = "2.1.277"`; `AGENTS_MODES = ("claude-md-or-agents-md",
  "claude-md-and-agents-md", "claude-md", "managed-only")`; `agents_mode(settings: dict) -> str`
  (reads `pluginConfigs["cc-plugin-agents-md@builtin"].options.instructionFiles`, then the old id
  `agents-md@builtin`; a missing or unknown value is `"claude-md-or-agents-md"`);
  `_claude_md_above(root: Path, home: Path) -> bool`; `at_least(version: str, floor: str) -> bool`
  in `versions.py` (the key `is_supported` uses). A Claude Code instruction item for
  `<project>/AGENTS.md` and `<project>/.claude/AGENTS.md`, `Scope.PROJECT`, category
  `"instructions"`, its summary also holding `("agents", mode)`.

- [ ] **Step 1: Check the docs and write the date.** Read code.claude.com/docs/en/memory
  (section "AGENTS.md") and /en/settings-reference (`pluginConfigs`). On 2026-10-24 they said:
  - from v2.1.277, by default Claude reads "every `AGENTS.md` and `.claude/AGENTS.md` in your
    working directory and the directories above it" when no `CLAUDE.md`, `.claude/CLAUDE.md` or
    `CLAUDE.local.md` is "in your working directory or any directory above it";
    `~/.claude/CLAUDE.md`, a managed `CLAUDE.md` and `.claude/rules/` do not count;
  - not read: `AGENTS.local.md`, `AGENTS.override.md`, anything under `.agents/`;
  - **Project instructions** values: `claude-md-or-agents-md` (default),
    `claude-md-and-agents-md`, `claude-md`, `managed-only`; set in `~/.claude/settings.json`
    under `pluginConfigs["cc-plugin-agents-md@builtin"].options.instructionFiles`, ignored in
    project and local files; before v2.1.285 the id was `agents-md@builtin`, later versions read
    either;
  - inside an AGENTS.md Claude reads, `@path` imports expand.

  Write `# checked <day> (code.claude.com/docs/en/memory)` above the new code. What the docs no
  longer confirm on the day is "not checked" and not built. Not checked, not built: turning the
  built-in plugin off with `/plugin`; `--settings` files and managed settings.
- [ ] **Step 2: Write the failing tests** in `tests/unit/test_read_claude_code.py` (the fixture's
  project `work/website` has a `CLAUDE.md`; `_instructions(home, read_version)` is the file's
  helper):

```python
def _agents(home, read_version):
    return {(i[0], i[1], i[3]) for i in _instructions(home, read_version) if i[1] == "AGENTS.md"}


def test_claude_code_reads_agents_md_only_where_the_project_has_no_claude_md(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    site = home / "work/website"
    (site / "AGENTS.md").write_text("x")
    (site / ".claude/AGENTS.md").write_text("x")
    assert _agents(home, no_version) == set()  # website has a CLAUDE.md
    (site / "CLAUDE.md").unlink()
    paths = {i.source.path for i in ClaudeCodeAdapter(home, read_version=no_version).scan().items
             if i.name == "AGENTS.md"}
    assert paths == {str(site / "AGENTS.md"), str(site / ".claude/AGENTS.md")}
    (home / ".claude/CLAUDE.md").write_text("x")  # the user's own file does not count
    assert len(_agents(home, no_version)) == 1
    for stopper in ("CLAUDE.local.md", ".claude/CLAUDE.md", "../CLAUDE.md"):
        (site / stopper).write_text("x")
        assert _agents(home, no_version) == set(), stopper
        (site / stopper).unlink()
```

  - `test_claude_code_reads_agents_md_beside_claude_md_with_the_setting`: with website's
    `CLAUDE.md` kept and an `AGENTS.md` beside it, `pluginConfigs` in `~/.claude/settings.json`
    set to `{plugin: {"options": {"instructionFiles": mode}}}` lists AGENTS.md for
    (`cc-plugin-agents-md@builtin`, `claude-md-and-agents-md`) and (`agents-md@builtin`,
    `claude-md-and-agents-md`), and not for `claude-md` or `managed-only`; the same entry in the
    project's `.claude/settings.json` lists nothing.
  - `test_an_old_claude_code_does_not_read_agents_md`: with website's `CLAUDE.md` removed,
    `read_version=lambda: "2.1.276"` lists none and `lambda: "2.1.277"` lists it.

  In `tests/unit/test_explain.py`, `test_reads_says_why_claude_code_reads_agents_md`: `reads()`
  of that item is `"Read when a session starts, because this project has no CLAUDE.md."`, and
  with `claude-md-and-agents-md` `"Read when a session starts, after CLAUDE.md (your Project
  instructions setting)."`. In `tests/unit/test_demo_home.py`, extend
  `test_the_medium_sample_contract`: the instruction items at `work/website/AGENTS.md` belong to
  exactly `{"claude_code", "cursor"}`.
- [ ] **Step 3: Run them to see them fail:** `uv run pytest tests/unit/test_read_claude_code.py
  tests/unit/test_explain.py tests/unit/test_demo_home.py -q` → FAIL.
- [ ] **Step 4: Implement.** `scan` reads `agents_mode(settings)` once and the version once
  (`self._read_version()`); `_project_files(read, root, data, mode, version)` adds the two files
  when the version is unknown or `at_least(version, AGENTS_MD_FROM)`, and the mode is
  `claude-md-and-agents-md`, or the default with `not _claude_md_above(root, self.home)`.
  `_claude_md_above` looks in `root` and each folder above it for `CLAUDE.md`, `CLAUDE.local.md`
  and `.claude/CLAUDE.md`, skipping the home folder's `.claude/CLAUDE.md`. A home-folder project
  skips `.claude/AGENTS.md`, as it skips its other `.claude` files. The sample writes
  `work/website/AGENTS.md` ("# Website\n\nUse plain words in the page.\n").
  Builder call: only a project's own AGENTS.md and `.claude/AGENTS.md` are listed, not those in
  folders above it, as Kitden lists only a project's own CLAUDE.md today.
  Builder call: an unknown version lists them; Kitden's tested floor (2.1.283) is above 2.1.277,
  so only an untested client can be too old, and its Overview card says so.
  Builder call: `managed-only` hides AGENTS.md only; its effect on CLAUDE.md files is not modelled.
  When both plugin ids are set, `cc-plugin-agents-md@builtin` wins (not checked).
- [ ] **Step 5: Run** the three files, then `uv run pytest tests/unit/test_library.py
  tests/unit/test_mcp_server.py tests/security -q` → PASS. If the medium item count leaves Part
  1's 50–75 range, widen it in `test_demo_home.py` in this commit.
- [ ] **Step 6: Run all four checks, then commit**

```bash
git add src/kitden/clients/claude_code.py src/kitden/clients/versions.py src/kitden/views/explain.py src/kitden/demo/sample.py tests/unit/test_read_claude_code.py tests/unit/test_explain.py tests/unit/test_demo_home.py
git commit -m "Claude Code reads AGENTS.md when a project has no CLAUDE.md"
```

---

### Task 2: Read Claude Code's `@` imports

**Files:**
- Create: `src/kitden/views/imports.py`, `tests/unit/test_imports.py`
- Modify: `src/kitden/demo/sample.py` (`atlas/CLAUDE.md` pulls in `@AGENTS.md`),
  `tests/unit/test_demo_home.py`

**Interfaces:**
- Produces:

```python
READ_CAP = 64_000  # the same cap as explain.PREVIEW_READ

@dataclass(frozen=True)
class Import:
    token: str          # as written, "@AGENTS.md"
    path: str           # the real path of the file it pulls in
    hop: int            # 1 for an import in the file itself, up to `hops`
    via: int | None     # index in the list of the import that pulls this one in; None: the file
    outside: bool       # resolves outside `project`; always False when `project` is None

def imports(path: Path, home: Path, project: str | None, hops: int = 4) -> list[Import]: ...
```

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_imports.py`. A fixture makes
  `home = tmp_path / "home"` and `project = home / "work/site"`; `_write(path, text)` makes the
  folders and returns the path. Compare paths with `.resolve()`.

```python
def test_a_relative_import_resolves_from_the_importing_file(site):
    home, project = site
    _write(project / "docs/style.md", "x")
    _write(project / "docs/rules.md", "@style.md\n")
    claude = _write(project / "CLAUDE.md", "See @docs/rules.md for rules.\n")
    found = imports(claude, home, str(project))
    root = project.resolve()
    assert [(i.token, Path(i.path).relative_to(root).as_posix(), i.hop, i.via) for i in found] == [
        ("@docs/rules.md", "docs/rules.md", 1, None), ("@style.md", "docs/style.md", 2, 0)]
    assert not any(i.outside for i in found)


def test_imports_stop_after_four_hops(site):
    home, project = site
    for n in range(1, 6):
        _write(project / f"a{n}.md", f"@a{n + 1}.md\n" if n < 5 else "x")
    claude = _write(project / "CLAUDE.md", "@a1.md\n")
    assert [(i.token, i.hop) for i in imports(claude, home, str(project))] == [
        ("@a1.md", 1), ("@a2.md", 2), ("@a3.md", 3), ("@a4.md", 4)]


def test_a_loop_is_read_once(site):
    home, project = site
    claude = _write(project / "CLAUDE.md", "@a.md\n")
    _write(project / "a.md", "@CLAUDE.md @b.md\n")
    _write(project / "b.md", "@a.md\n")
    assert [i.token for i in imports(claude, home, str(project))] == ["@a.md", "@b.md"]


def test_code_spans_fenced_blocks_quotes_and_emails_are_not_imports(site):
    home, project = site
    for name in ("real", "span", "fenced", "tilde", "quoted", "single", "b.com"):
        _write(project / f"{name}.md" if name != "b.com" else project / name, "x")
    text = ("Mail a@b.com or read (@real.md).\nWrite `@span.md` to name it.\n"
            "```text\n@fenced.md\n```\n~~~\n@tilde.md\n~~~\n@\"quoted.md\" and @'single.md'\n")
    claude = _write(project / "CLAUDE.md", text)
    assert [i.token for i in imports(claude, home, str(project))] == ["@real.md"]


def test_a_missing_file_or_a_folder_is_left_out(site):
    home, project = site
    (project / "docs").mkdir()
    claude = _write(project / "CLAUDE.md", "@nothere.md @docs @octocat\n")
    assert imports(claude, home, str(project)) == []
    assert imports(project / "gone.md", home, str(project)) == []
```

  Also:
  - `test_a_home_import_and_an_absolute_import`: `- @~/.claude/mine.md` and `- @<tmp>/shared/team.md`
    in the project's CLAUDE.md give both files, both `outside`; the same absolute import in
    `~/.claude/CLAUDE.md` with `project=None` is not `outside`.
  - `test_an_escaped_space_is_part_of_the_path`: `- API @Design\ Docs/api.md.` gives
    `Design Docs/api.md` (the last "." dropped because the path with it is no file).
  - `test_a_file_is_read_only_up_to_the_cap`: 70 000 "x" then `\n@late.md\n` gives `[]`, and
    `READ_CAP == PREVIEW_READ`.

  In `test_the_medium_sample_contract`: `imports(atlas / "CLAUDE.md", home, str(atlas))` has one
  import, token `"@AGENTS.md"`, path `atlas / "AGENTS.md"`.
- [ ] **Step 2: Run them to see them fail:** `uv run pytest tests/unit/test_imports.py -q` →
  FAIL (no module).
- [ ] **Step 3: Implement `imports()`.** Read each file with `encoding="utf-8-sig",
  errors="replace"`, up to `READ_CAP`, dropping a last line the cap cut (as `preview` does); a
  file that cannot be read pulls in nothing. Walk depth-first in reading order, never visiting a
  real path twice (the starting file counts as visited). The token rule, in short:

```python
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
SPAN = re.compile(r"(`+).*?\1")                      # an inline code span
TOKEN = re.compile(r"(?:^|(?<=[\s(]))@((?:\\ |\S)+)")  # "@" at a line start, after a space or "("
END = ".,;:!?)"

def _tokens(text):
    fence = None
    for line in text.splitlines():
        mark = FENCE.match(line)
        if fence:
            if mark and mark.group(1)[0] == fence[0] and len(mark.group(1)) >= len(fence):
                fence = None
            continue
        if mark:
            fence = mark.group(1)
            continue
        for found in TOKEN.finditer(SPAN.sub("", line)):
            raw = found.group(1)
            if raw[0] not in "\"'":          # a quoted path is not imported
                yield raw.replace("\\ ", " ")

# A token resolves: "~/" from home, "/" as it is, else from the importing file's folder. When
# that is no file, try it again without trailing END marks. Keep only files.
```

  Comment block at the top: `# checked 2026-10-23 (code.claude.com/docs/en/memory)` with the
  four rules the docs give (relative to the file, `@~/…`, four hops, code spans and fenced blocks
  skipped, `\ ` in a path, a quoted path is not imported, outside imports are approved once per
  project), and `# checked 2026-10-23: Codex (learn.chatgpt.com/docs/agent-configuration/agents-md)
  and Cursor (cursor.com/docs/context/rules) have no imports.` Also: "The docs do not say what
  starts a token: not checked."
  Builder call: an `@` counts only at a line start or after a space or "(", so `a@b.com` is not
  an import; trailing sentence marks are dropped only when the path with them is no file.
  Write `atlas/CLAUDE.md` in the sample as "# Atlas\n\nRun `make test` before each
  commit.\n\nShared rules: @AGENTS.md\n".
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_imports.py tests/unit/test_demo_home.py
  tests/security -q` → PASS.
- [ ] **Step 5: Run all four checks, then commit**

```bash
git add src/kitden/views/imports.py src/kitden/demo/sample.py tests/unit/test_imports.py tests/unit/test_demo_home.py
git commit -m "Read Claude Code's @ imports, four hops at most"
```

---

### Task 3: Instruction files by path, for the page only

**Files:**
- Create: `src/kitden/views/instructions.py`, `tests/unit/test_instructions.py`
- Modify: `src/kitden/views/explain.py` (`with_page_fields`, new `line_count`),
  `src/kitden/web/app.py` (`_explain` passes `home`; new `_instructions`, route
  `/api/instructions`)
- Test: `tests/unit/test_api_views.py`, `tests/unit/test_mcp_server.py`,
  `tests/security/test_no_secrets.py`

**Interfaces:**
- Consumes: `imports()` (Task 2); `COLUMNS`, `category` (`views/load_map.py`); `_hash`
  (`model.py`).
- Produces:
  - `IMPORTING = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md")` and `takes_imports(item) -> bool`
    (a Claude Code instruction item, category `"instructions"`, with one of these names; rules,
    commands and agents are left out: whether rules expand imports is not checked).
  - `line_count(item) -> int | None` in `explain.py`: lines in the file; None when it cannot be
    read or is longer than `PREVIEW_READ`.
  - `with_page_fields(definitions, inventory, home: Path | None = None)`: an instruction
    definition also gains `"lines"`; one that `takes_imports` gains `"imports": [asdict(Import)]`.
  - `instruction_files(inventory, project: str | None, home: Path) -> list[dict]`, each:

```python
{"id": str,                # _hash("instructions", key): a file's real path, or its folder
 "name": str,              # "CLAUDE.md"; a folder ".cursor/rules"
 "group": "all" | "project",
 "category": str,          # "instructions", "command" or "agent"
 "lookup": str | None,     # the name /api/explain takes; None for a folder
 "clients": list[str],     # COLUMNS order
 "items": list[str],       # the item ids at this path (a folder: all of its files')
 "stale_at": str | None,
 "files": [{"id", "name", "lookup", "category", "items"}],  # a folder's files, else []
 "imports": [{"name": "@AGENTS.md", "hop": int, "via": int | None, "outside": bool,
              "file": str | None}],                          # file: the block it resolves to
 "through": [{"client": "claude_code", "name": "CLAUDE.md"}]}
```

  - `GET /api/instructions?project=<id>` → `{"project": ..., "files": [...]}` through
    `_read_model`.

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_instructions.py`, on the medium
  sample (`home = build_demo_home(tmp_path, "medium")`, `inventory = build_inventory(home)`,
  `atlas = str(home / "work/atlas")`):

```python
def test_files_join_by_path_not_by_name(medium):
    home, inventory = medium
    files = instruction_files(inventory, str(home / "work/atlas"), home)
    agents = [(f["group"], f["clients"]) for f in files if f["name"] == "AGENTS.md"]
    assert agents == [("all", ["codex"]), ("project", ["codex", "cursor"])]


def test_claude_code_reads_atlas_agents_md_through_its_claude_md(medium):
    home, inventory = medium
    files = instruction_files(inventory, str(home / "work/atlas"), home)
    claude = next(f for f in files if f["group"] == "project" and f["name"] == "CLAUDE.md")
    agents = next(f for f in files if f["group"] == "project" and f["name"] == "AGENTS.md")
    assert [(i["name"], i["hop"], i["file"]) for i in claude["imports"]] == [
        ("@AGENTS.md", 1, agents["id"])]
    assert agents["through"] == [{"client": "claude_code", "name": "CLAUDE.md"}]
    assert str(home) not in json.dumps(files)  # no path on the page's data
```

  Also `test_cursor_rules_fold_by_folder` (website picked: the block `.cursor/rules` has clients
  `["cursor"]`, one file, `lookup` None; website's `AGENTS.md` has clients `["claude_code",
  "cursor"]`) and `test_all_projects_shows_only_the_files_for_all_projects` (project None: every
  group is `"all"`).

  In `tests/unit/test_api_views.py`, add `"/api/instructions"` to `ENDPOINTS`, and
  `test_explain_gives_the_page_a_files_size_and_imports`: write `work/website/notes.md` and
  `work/website/CLAUDE.md` = `"Rules.\n@notes.md\n"`, ask `/api/explain?name=CLAUDE.md&kind=instructions`
  with website's project id; the definition whose `source` is that file has `lines == 2` and
  `[(i["token"], i["hop"]) for i in d["imports"]] == [("@notes.md", 1)]` (both are read when asked,
  so no rescan is needed).

  In `tests/unit/test_mcp_server.py`, `test_explain_item_has_no_page_fields` also asks
  `name="CLAUDE.md"` and asserts `"imports" not in d and "lines" not in d` for every definition.
  In `tests/security/test_no_secrets.py`, add `/api/instructions` to the endpoints its sweep reads.
- [ ] **Step 2: Run them to see them fail:** `uv run pytest tests/unit/test_instructions.py
  tests/unit/test_api_views.py tests/unit/test_mcp_server.py -q` → FAIL.
- [ ] **Step 3: Implement.** `instruction_files` keeps `ItemKind.INSTRUCTIONS` items with a path:
  with `project` None only items of no project (group "all"); with a project, those and that
  project's (group "project"). Key: the first folder above the file named `rules`, `commands` or
  `agents` whose parent is `.claude` or `.cursor`, else the file's real path. A folder's name is
  its last two parts; a file's is its file name, or its last two parts when two blocks of one
  group share a name. Order: group "all" first; files by their first client in `COLUMNS`, then
  name; folders last. `imports` runs for blocks with an item that `takes_imports`, with that
  item's project; `file` points at the block whose key is the import's path; `through` names
  the file at the start of each chain that reaches a block. `with_page_fields` reads imports with
  the item's own project.
  Builder call: files under `.claude/rules`, `.claude/commands`, `.claude/agents` and
  `.cursor/rules` fold into one block per folder; the spec names only Cursor's rules.
  Builder call: `lines` and `imports` go with every instruction definition (they are counts and
  paths, not file lines); the first-lines rule of `preview` stays as it is.
  Builder call: a file longer than the 64 KB cap gets no Size.
- [ ] **Step 4: Run** the three files and `uv run pytest tests/security -q` → PASS.
- [ ] **Step 5: Run all four checks, then commit**

```bash
git add src/kitden/views/instructions.py src/kitden/views/explain.py src/kitden/web/app.py tests/unit/test_instructions.py tests/unit/test_api_views.py tests/unit/test_mcp_server.py tests/security/test_no_secrets.py
git commit -m "Instruction files by path, with imports, for the page only"
```

---

### Task 4: The Instructions tree (I1)

**Files:**
- Create: `src/kitden/web/static/js/instructions.js`, `tests/frontend/instructions.test.mjs`
- Modify: `src/kitden/web/static/js/store.js` (`loadInstructions`, `data.instructions`),
  `src/kitden/web/static/js/library.js` (the Instructions tab draws the tree in Map),
  `src/kitden/web/static/style.css`, `docs/design.md` (Library table: "Instructions map" and
  "Instruction file Details"), `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `/api/instructions` and the page fields (Task 3); Part 4's `layoutTree`, `litPath`,
  `findIn`, `drawMap`, the tree model, `factsBlock`, `openPanel(…, { dock: true })`, `cutName`,
  `viewMode`; Part 5's Instructions tab and its List; Part 3's `header`, `techRows`, `technical`,
  `linksRow`, `kindWord`.
- Produces (all in `instructions.js`):
  - `instructionsModel(files, clients) -> model`: columns `[{id: "clients", caption:
    "Clients"}, {id: "files", caption: "Files"}, {id: "imports", caption: "Pulls in"}]`; a client
    block `client:<id>` per found client; a `group` block `group:all` ("All projects") and
    `group:project` (`Only this project · ${folder}`); a block per file or folder with that group as
    `parent` (`kind` `"file"` or `"folder"`, `meta` from `fileMeta`, `count` = hop-1 imports or
    folder files, null for none, `state` `"on"`); every hop-1 import (`kind` `"import"`, `meta`
    "Import") and folder file (`meta` "Rule", "Command" or "Agent") as a child (`parent` = its
    file) in "imports"; links client → file `"on"` for each reader, file → child `"on"`.
  - `fileMeta(file) -> string`: "Claude Code · 1 import", "Codex, Cursor", "Cursor · 2 rules".
  - `litFile(model, id) -> Set<string>`: `litPath(model, id)` plus the path of every import block
    whose `file` is `id`.
  - `fileFacts(file, definitions) -> {label, value}[]`: "Read by", "Through" ("CLAUDE.md for
    Claude Code"), "Size" ("42 lines"), "Pulls in" ("AGENTS.md", or "3 files").
  - `importNote(file, imp) -> string`.
  - `renderInstructions(main)`, `showFile(file)`, `showImport(file, index)`.
  - `store.js`: `loadInstructions()` (`guarded("instructions", "/api/instructions?project=…")`,
    scoped to the project like `loadMap`).

- [ ] **Step 1: Write the failing node tests** in `tests/frontend/instructions.test.mjs`.
  `files` is a hand-made answer of the Task 3 shape: the user `CLAUDE.md` and `AGENTS.md`;
  atlas's `CLAUDE.md` (`claudeAtlas`) with `@AGENTS.md`; atlas's `AGENTS.md` (`agentsAtlas`) read
  by Codex and Cursor, `through` Claude Code's `CLAUDE.md`; `.cursor/rules` (`rules`) with two
  rules; and `agentsOnly`, a project `AGENTS.md` Claude Code reads itself. Client block ids are
  Part 4's (`client:<id>` below stands for them).

```js
const model = instructionsModel(files, ['claude_code', 'codex', 'cursor']);
test('files are one block per path, grouped All projects then This project', () => {
  assert.deepEqual(model.columns.map((c) => c.caption), ['Clients', 'Files', 'Pulls in']);
  assert.equal(model.blocks.filter((b) => b.column === 'files' && b.name === 'AGENTS.md').length, 2);
  assert.equal(model.blocks.find((b) => b.id === rules.id).count, 2);
});
test('file meta says readers, imports and rules', () => {
  assert.equal(fileMeta(claudeAtlas), 'Claude Code · 1 import');
  assert.equal(fileMeta(agentsAtlas), 'Codex, Cursor');
  assert.equal(fileMeta(rules), 'Cursor · 2 rules');
});
test('selecting AGENTS.md lights Claude Code through the CLAUDE.md that pulls it in', () => {
  const lit = litFile(model, agentsAtlas.id);
  for (const id of ['client:codex', 'client:cursor', 'client:claude_code', claudeAtlas.id]) assert.ok(lit.has(id), id);
});
test('facts say who reads it, through what, and its size', () => {
  assert.deepEqual(fileFacts(agentsAtlas, [{ lines: 42 }]), [
    { label: 'Read by', value: 'Codex, Cursor' },
    { label: 'Through', value: 'CLAUDE.md for Claude Code' },
    { label: 'Size', value: '42 lines' }]);
});
test('an import outside the project says Claude Code may ask', () => {
  assert.equal(importNote(claudeAtlas, { outside: true }), 'Claude Code may ask before it reads this.');
  assert.equal(importNote(agentsOnly, { outside: true }), 'Claude Code reads this only if you allowed outside imports in this project.');
  assert.equal(importNote(claudeAtlas, { outside: false }), 'Claude Code reads it with CLAUDE.md.');
});
```

- [ ] **Step 2: Run** `node --test tests/frontend/instructions.test.mjs` → FAIL.
- [ ] **Step 3: Implement the model and Details.**
  - The Instructions tab (`libraryTab` `"instructions"`) in Map draws `renderInstructions(main)`:
    `loadInstructions()` once per project, then `drawMap(box, model, layoutTree(model, { open,
    width, narrow }), { onSelect, onOpen, lit })`, with `open` a Set kept by `toggleOpen`.
    Selecting a file or import lights `litFile` and opens its Details docked; a client block
    lights `litFrom`. A group's "N more" block opens List at that group (`sel=group:<id>`), as on
    the Gateway. Find (S.6) uses `findIn(model, text)`. The view choice is `viewMode(state, count)` with `count` = blocks in
    the Files column. List is Part 5's Instructions list, unchanged.
  - `showFile(file)`: `/api/explain` with `file.lookup`, kind `instructions` and its category,
    keeping the definitions whose `id` is in `file.items`; then `openPanel(detailsCard({ kind:
    kindWord(...) (a folder: "Folder"), title: file.name, id: \`${file.group === "all" ? "All
    projects" : "Only this project"} · ${STATE_WORDS.on}\`, facts: fileFacts(file, defs), why: the
    definitions' `why` lines (when each client reads it), actions: [{ label: "Compare across
    clients", run }],
    technical: technical(techRows(defs)) plus one row per import, its token as the title and its
    path }), { dock: true })`.
  - `showImport(file, index)`: `detailsCard` with kind "Import", the token, id `Pulled in by
    ${file.name}`; facts "Pulled in by" (the file, or the import that pulls it in), "Read by"
    ("Claude Code"), and "Pulls in" when deeper imports hang under it; why `importNote(file,
    imp)`; technical its path from the file's `/api/explain` `imports[index]`.
  - A quiet hint line under the tree: "Kitden only reads instruction files. It never changes
    them."
  Builder call: the map shows hop-1 imports as blocks; deeper ones are listed under "Pulls in" in
  the import's Details, so the tree stays three columns.
  Ruling (coordinator): a project's instruction files are items only that project has, not
  rules, so the caption is "Only this project · <folder>" (S.1), not I1's "This project ·
  <folder>", and their Details sub-line says "Only this project · On".
  Builder call: Details of an instruction file is its own `showFile`, not Part 5's skill Details,
  because its facts differ.
  Builder call: "Compare across clients" on the map switches the tab to List (`state.mode =
  "list"`) with the file's row selected (the List joins by name, which is the comparison).
- [ ] **Step 4: Pin the words** in `tests/unit/test_page_words.py`:

```python
def test_the_instructions_tree_names_its_columns_and_only_reads():
    text = script("instructions.js")
    for words in ('"Pulls in"', '"Read by"', '"Through"', '"Size"', "Claude Code may ask before it reads this.",
                  "Kitden only reads instruction files. It never changes them.", "Only this project · ${"):
        assert words in text, words
    assert "`This project · ${" not in text  # the caption is S.1's "Only this project"
    assert "/api/instructions" in script("store.js")
```

- [ ] **Step 5: design.md.** In the Library table, replace "Instruction file Details" and add
  "Instructions map": clients → files → "Pulls in"; one block per file path with the clients that
  read it, under "All projects" or "Only this project · <folder>"; folders of rules, commands and agents fold with a count; Claude Code's `@` imports
  one level on the map, deeper ones in Details; an import outside the project says "Claude Code
  may ask before it reads this."; Details: "Read by", "Through", "Size", "Pulls in", when each
  client reads it, "Compare across clients", and the path, import paths and first 12 lines under
  Technical details; agents asking through Kitden's MCP server get no file lines and no imports.
- [ ] **Step 6: Run** the node tests and `uv run pytest tests/unit/test_page_words.py -q` → PASS.
  Smoke check in `uv run kitden demo --size medium`: pick atlas, Library → Instructions → Map;
  select AGENTS.md; Codex and Cursor light, and Claude Code lights through CLAUDE.md.
- [ ] **Step 7: Run all four checks, then commit**

```bash
git add src/kitden/web/static/js/instructions.js src/kitden/web/static/js/store.js src/kitden/web/static/js/library.js src/kitden/web/static/style.css docs/design.md tests/frontend/instructions.test.mjs tests/unit/test_page_words.py
git commit -m "Instructions: one tree of clients, files and what they pull in"
```

---

### Task 5: Overview cards per item (server)

**Files:**
- Modify: `src/kitden/views/overview.py`
- Test: `tests/unit/test_overview.py`

**Interfaces:**
- Consumes: `gateway_view(...)` groups (`move`, `local`, `plugin`), `_kitden_card()["lacking"]`.
- Produces: every card in `attention` and `suggestions` is
  `{"id", "icon", "name", "text", "clients": list[str], "action": str | None, "target": dict | None}`
  (`title` goes). `ICONS = ("file", "client", "gateway", "mcp_server", "plugin", "skill")`;
  `OUTSIDE_CARDS = 3`. `headline`, `notes`, `clients` and `gateway` stay as they are.

| Card | icon | name | text | clients | action | target |
| --- | --- | --- | --- | --- | --- | --- |
| Unreadable file | `file` | "Could not read mcp.json" | today's | its client | — | — |
| Untested client | `client` | "Cursor 1.9 is not tested" | today's | it | — | — |
| Old Kitden entries | `gateway` | today's title | today's | theirs | "Update" | `{"view": "agents"}` |
| Duplicate | its kind | the item's name | "Loads twice in Claude Code; keep one." ("3 times") | where it does | "Keep one…" | today's |
| Server outside, first three | `mcp_server` | its name | "Skips the gateway, so Kitden's rules don't reach it." | its row's | "Move in…" | `{"view": "gateway", "kind": "mcp_server", "name": name}` |
| The rest | `mcp_server` | "N more servers skip the gateway" ("1 more server skips the gateway") | "Their calls skip Kitden's rules." ("Its calls …") | all of theirs | "Show them" | `{"view": "gateway", "list": "outside"}` |
| Client without the `kitden` entry | `client` | "Cursor" | "Not connected to the gateway yet." | it | "Set up in Cursor…" | `{"view": "gateway", "setup": "cursor"}` |

- [ ] **Step 1: Write the failing tests.** Rewrite the tests that read `title` to read `name`
  (`test_headline_counts_attention`, `test_duplicate_card_is_one_sentence_and_opens_the_item`,
  `test_unreadable_file_becomes_an_attention_card`, `test_untested_version_is_an_attention_card`,
  `test_old_kitden_entries_get_one_card_that_opens_agents`,
  `test_overview_duplicate_points_at_a_row_the_map_has`); `test_no_card_shows_a_file_path`
  checks `name + text`. Replace the "N MCP servers can move" asserts in
  `test_the_kitden_gateway_card_names_servers_and_clients`,
  `test_a_registered_gateway_still_gets_its_card_without_the_kitden_one`,
  `test_direct_servers_are_a_suggestion_not_attention`,
  `test_a_server_in_two_clients_is_one_suggestion_row` (one card, both clients),
  `test_servers_that_cannot_move_are_not_a_suggestion` and
  `test_a_server_without_a_removable_entry_is_not_counted` with per-server cards. New:

```python
def test_each_server_that_skips_the_gateway_has_a_card_up_to_three(connected):
    mcp = connected / ".cursor/mcp.json"
    data = json.loads(mcp.read_text())
    for n in range(4):
        data["mcpServers"][f"extra-{n}"] = {"command": "npx", "args": [f"extra-{n}"]}
    mcp.write_text(json.dumps(data))
    inventory = build_inventory(connected)
    groups = gateway_view(inventory, [], None, kitden=[])["groups"]
    rows = [r for r in groups["move"] + groups["local"] if r["items"]]
    cards = [c for c in overview(inventory, [], None, held=[])["suggestions"] if c["icon"] == "mcp_server"]
    assert [c["name"] for c in cards[:3]] == [r["name"] for r in rows[:3]]
    assert cards[0]["text"] == "Skips the gateway, so Kitden's rules don't reach it."
    assert (cards[0]["action"], cards[0]["target"]) == (
        "Move in…", {"view": "gateway", "kind": "mcp_server", "name": rows[0]["name"]})
    assert [c["name"] for c in cards[3:]] == [f"{len(rows) - 3} more servers skip the gateway"]
    assert cards[3]["target"] == {"view": "gateway", "list": "outside"}
```

  Also `test_a_client_without_the_kitden_entry_gets_a_set_up_card` (`connected`, `held=[]`: the
  one suggestion with icon `"client"` is exactly the table's row for Codex, `"Set up in Codex…"`,
  target `{"view": "gateway", "setup": "codex"}`) and
  `test_every_card_names_its_clients_and_icon_and_none_asks_to_sign_in` (`home`: every card has
  `icon in ICONS`, non-empty `clients`, and no "Sign in" in its name, text or action).

- [ ] **Step 2: Run them to see them fail:** `uv run pytest tests/unit/test_overview.py -q`.
- [ ] **Step 3: Implement.** Server cards come from the same rows today's suggestion counted
  (`move`, plus `local` with the Kitden gateway, rows with `items`), in their order; the Desktop
  Code tab counts as Claude Code in `clients`. Order of `suggestions`: server cards, the "more"
  card, then set-up cards in `COLUMNS` order (only with the Kitden gateway).
  Builder call: cards cover the servers a move can take, as today's suggestion did; "N more"
  counts the rest of those, with N from 1.
  Builder call: "Set up in Cursor…", not the frame's "Connect…": the same words as the Gateway's
  client Details (map spec 4.4) and today's gateway card.
  Builder call: a card opens the place to fix it ("Move in…" selects the server on the Gateway,
  whose Details leads with "Move into the gateway…").
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_overview.py tests/unit/test_api_views.py -q`
  → PASS.
- [ ] **Step 5: Run all four checks, then commit**

```bash
git add src/kitden/views/overview.py tests/unit/test_overview.py
git commit -m "Overview: one card per item, with its clients and an icon"
```

---

### Task 6: The Overview page: cards and "Your setup" (O1)

**Files:**
- Modify: `src/kitden/web/static/js/overview.js`, `src/kitden/web/static/js/library.js` (its
  `land(tile, …)` call goes), `src/kitden/web/static/style.css`, `docs/design.md` (Components:
  the Overview paragraph; Client marks; Motion "Shared tile")
- Test: `tests/frontend/overview.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 5's cards; `current("map").rows`, `current("gateway")` (held servers' `tools`),
  `data.projects[].own_rules` (Part 4); `layoutTree`, `drawMap`, the tree model, sel kinds
  `client` and `group` (Part 4); `linkKind(cell)` (Part 5, `librarytree.js`); `mark`,
  `versionWords`, `CLIENT_NAMES` (`parts.js`).
- Produces: `overviewHead(model, clients, projects) -> {none, headline, lede}`;
  `libraryCounts(rows, clientIds) -> {plugins, skills, links: {[client]: "on" | "faint"}}`
  (plugin and skill rows with a `linkKind` for some client; a client's link is `"on"` when any
  of its cells is `"on"`, else `"faint"` when any is `"faint"`, else absent);
  `gatewayLine(gateway, held) -> string`; `projectsLine(projects) -> string`;
  `setupTree(model, { map, held, projects }) -> treeModel`; `cardIcon(word) -> Element`.
  Removed: `clientsCard`, `loadsLine`, `loadCounts`, `LOAD_KINDS`, `gatewayCard`,
  `gatewayCardWords`. `clientStatus` stays (the client block uses it).

- [ ] **Step 1: Write the failing node tests** (replace the `gatewayCardWords` and `loadCounts`
  tests):

```js
test('the title is Your setup, connected. and the lede gives the counts', () => {
  const found = [{ status: 'found' }, { status: 'found' }, { status: 'found' }];
  assert.deepEqual(overviewHead({ attention: [{}, {}] }, found, 4), { none: false, headline: 'Your setup, connected.',
    lede: '2 things need your attention. Everything else looks fine: 3 clients, 4 projects.' });
  assert.equal(overviewHead({ attention: [] }, found, 1).lede, '3 clients, 1 project. Nothing needs your attention.');
  assert.deepEqual(overviewHead({ attention: [] }, [{ status: 'not_found' }], 0), { none: true, headline: 'No clients found', lede: null });
});
test('the Library block counts what found clients load, faint when only through another client', () => {
  const rows = [
    { kind: 'plugin', cells: { claude_code: { state: 'on' }, cursor: { state: 'on', route: "through Claude Code's folder" } } },
    { kind: 'skill', cells: { codex: { state: 'on' }, cursor: { state: 'via' } } },
    { kind: 'mcp_server', cells: { codex: { state: 'on' } } }];
  assert.deepEqual(libraryCounts(rows, ['claude_code', 'codex', 'cursor']),
    { plugins: 1, skills: 1, links: { claude_code: 'on', codex: 'on', cursor: 'faint' } });
});
test('the gateway block says servers and the tools Kitden knows', () => {
  const kitden = { kind: 'kitden', name: 'Kitden gateway', servers: 4, clients: [], lacking: [], problem: null };
  assert.equal(gatewayLine(kitden, [{ tools: 5 }, { tools: 6 }, { tools: null }, {}]), '4 servers · 11 tools');
  assert.equal(gatewayLine(kitden, []), '4 servers');
  assert.equal(gatewayLine({ ...kitden, servers: 0 }, []), 'No servers yet.');
  assert.equal(gatewayLine(null, []), 'No gateway yet.');
});
test('the projects line counts projects with their own rules', () => {
  assert.equal(projectsLine([{ own_rules: 1 }, { own_rules: 0 }, {}, { own_rules: 0 }]), '4 projects · 1 has its own rules');
  assert.equal(projectsLine([{ own_rules: 2 }, { own_rules: 3 }]), '2 projects · 2 have their own rules');
  assert.equal(projectsLine([{ own_rules: 0 }]), '1 project');
});
```

  Also 'Your setup joins each client to what it uses, and marks one not tested': on an
  `/api/overview` answer with three found clients, Cursor `tested: false`, and the `rows` above,
  `setupTree` has columns `["clients", "places"]`, a `"faint"` link from Cursor to `"library"`, and
  Cursor's block meta ends with "not tested".

- [ ] **Step 2: Run** `node --test tests/frontend/overview.test.mjs` → FAIL.
- [ ] **Step 3: Implement.**
  - Title `headline`, then the lede. Left column: a caption "Needs attention" over the attention
    cards (when any), "Can improve" over the suggestions, then today's notes fold
    (`Show N notes (nothing to fix)`). A card: `cardIcon(card.icon)` in a 28 px tile (warn color
    under "Needs attention", muted under "Can improve"), the name, the text, a `mark()` per client,
    and its one button (primary for a problem, plain for an option, as today). Targets:
    `view: "map"` → today's `follow`; `kind` → `goTo("gateway", { kind, name })`; `list` →
    `#gateway?view=list&sel=group:outside` (`goTo("gateway", { kind: "group", name: "outside" })`
    with `mode: "list"`, which Part 4 keeps), as Part 4's "N more" block does; `setup` → the same review
    today's gateway card opens (`kitdenClients(data.setupServer).setup`, `SETUP_NOTE`);
    `view: "agents"` → `go`.
  - Right column, caption "Your setup": `setupTree` drawn with
    `drawMap(box, tree, layoutTree(tree, { open: new Set(), width, narrow }), { onSelect })`, then
    `projectsLine(data.projects)`. Client blocks: name and `versionWords(...)`, plus " · not
    tested" with an amber mark when `clientStatus` says so ("Could not read" for an unreadable
    one). The gateway block: its name and `gatewayLine`; the Library block: "Library" and
    `${plural(plugins, "plugin", "plugins")} · ${plural(skills, "skill", "skills")}` ("Counting…"
    while `/api/map` is not read). Links: client → gateway for `gateway.clients`, client →
    Library by `libraryCounts().links`. `kitden:versions` redraws the tree in place, keeping focus.
  - A block opens its page: gateway → `go("gateway")`; Library → `go("library", { kind:
    "plugin" })`; a client → the Library map with `sel=client:<id>` (`goTo("library", { kind:
    "client", name: id })` with `mode: "map"`), which lights what it loads (`litFrom`).
  - The tile animation goes: `fly(tile, …)` leaves `overview.js` and `land(tile, …)` leaves
    `library.js`, because the Library map's client block is not the table column the tile used
    to land on (ruled: P6 decides; it removes). `fly`/`land` stay in `motion.js`.
  Builder call: Your setup uses `layoutTree` with an empty `open`; if it cannot place two blocks
  in the second column without a parent, draw the same blocks at the frame's fixed places
  (clients at 0/72/144, places at 18/126) with `drawMap`, or plain SVG if `drawMap` needs a layout.
  Builder call: icons are Part 4's block icons if it added any, else six small inline SVG
  shapes in `cardIcon`; never a picture from another site.
  Builder call: a client's Library link follows Part 5's `linkKind` (faint through another
  client's folder); "Via Claude Code" alone draws no link, as on the Library map.
- [ ] **Step 4: Update the pins** in `tests/unit/test_page_words.py`:
  - `test_client_tile_flies_to_its_library_column`: drop the `loadsLine` slice and the
    `fly`/`land` asserts; keep the `follow` order assert, and assert `"fly(" not in overview`.
  - Drop the pins on the Overview's empty client line (Part 4 made it "Nothing on here.") and
    on `loadsLine`: the counts line is gone.
  - `test_overview_offers_set_up_only_without_a_gateway`: `"gatewayLine"` replaces
    `"gatewayCardWords"`; `'"No gateway yet."'` still appears once.
  - `test_the_clients_card_hears_when_versions_arrive`: unchanged (the tree listens now).
  - New:

```python
def test_overview_has_cards_and_your_setup_and_no_sign_in():
    overview = script("overview.js")
    for words in ('"Your setup, connected."', '"Your setup"', '"Needs attention"', '"Can improve"',
                  "need your attention.", "Everything else looks fine:", "has its own rules",
                  "have their own rules", "not tested", '"No servers yet."', 'kind: "group", name: "outside"'):
        assert words in overview, words
    assert "Sign in" not in overview and "clientsCard" not in overview
```

- [ ] **Step 5: design.md.** Rewrite the Overview paragraph of Components: one card per item
  (icon tile, name, one line, client tiles, one button), "Needs attention" then "Can improve",
  up to three server cards then "N more servers skip the gateway", notes folded; "Your setup", a
  small fixed tree that never unfolds, whose blocks open their pages; no sign-in card until S1.
  In Client marks, the 28 px headline tile is the title of a Details panel only. In Motion, the
  "Shared tile" row and its example go.
- [ ] **Step 6: Run** the node tests and `uv run pytest tests/unit/test_page_words.py
  tests/unit/test_contrast.py -q` → PASS. Smoke check in the medium demo, both themes and at
  1024 px: three server cards and one "more" card, "Your setup" with the faint Cursor link.
- [ ] **Step 7: Run all four checks, then commit**

```bash
git add src/kitden/web/static/js/overview.js src/kitden/web/static/js/library.js src/kitden/web/static/style.css docs/design.md tests/frontend/overview.test.mjs tests/unit/test_page_words.py
git commit -m "Overview: cards per item and a small Your setup tree"
```

---

### Task 7: The Changes timeline (C1)

**Files:**
- Modify: `src/kitden/web/static/js/changes.js`, `src/kitden/web/static/js/parts.js`
  (`changeTitle`, new `changeClients`), `src/kitden/web/static/style.css`, `docs/design.md`
  (new "Changes" paragraph after the review table)
- Create: `tests/frontend/changes.test.mjs`
- Test: `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: `changeClients(entry) -> string[]` (the clients `changeTitle` names today, in
  `CLIENT_ORDER`); `changeTitle(entry, { names = true } = {})` (with `names: false`, no
  " · <clients>" tail); `dayGroups(entries, now = new Date()) -> [{label, entries}]` ("Today",
  "Yesterday", then `toLocaleDateString([], { month: "short", day: "numeric" })`, by local day,
  newest first); `rowState(entry) -> {word, look, over, undo}`.

- [ ] **Step 1: Write the failing node tests** in `tests/frontend/changes.test.mjs` (load like
  `overview.test.mjs` does):

```js
const at = (...parts) => new Date(...parts).toISOString();
test('changes fall on their own local day', () => {
  const now = new Date(2026, 9, 24, 9, 0);
  const groups = dayGroups([{ id: 'c', time: at(2026, 9, 24, 0, 1) }, { id: 'b', time: at(2026, 9, 23, 23, 59) },
    { id: 'a', time: at(2026, 9, 20, 12, 0) }], now);
  assert.deepEqual(groups.map((g) => g.entries.map((e) => e.id)), [['c'], ['b'], ['a']]);
  assert.deepEqual(groups.slice(0, 2).map((g) => g.label), ['Today', 'Yesterday']);
  assert.ok(!['Today', 'Yesterday'].includes(groups[2].label));
});
test('a row says its state, and only an applied change offers Undo', () => {
  assert.deepEqual(rowState({ state: 'verified' }), { word: 'Applied', look: 'badge win', over: false, undo: true });
  assert.equal(rowState({ state: 'undone' }).over, true);
  assert.equal(rowState({ state: 'cancelled' }).over, true);
  assert.deepEqual(rowState({ state: 'stale' }), { word: 'Not applied: the file changed first', look: 'badge warn', over: false, undo: false });
});
test('the row title leaves the clients to the tiles', () => {
  const entry = { action: 'mcp.add', target: { scope: 'all' }, steps: [{ client: 'codex', name: 'docs' }, { client: 'cursor', name: 'docs' }] };
  assert.deepEqual(changeClients(entry), ['codex', 'cursor']);
  assert.equal(changeTitle(entry, { names: false }), changeTitle(entry).split(' · ')[0]);
});
```

- [ ] **Step 2: Run** `node --test tests/frontend/changes.test.mjs` → FAIL.
- [ ] **Step 3: Implement.** The page: title, today's lede, then one `section` per day group
  with a quiet caption and a `ul` of rows. A row: a rail (a line and a 9 px dot), the time
  (`HH:MM`), `changeTitle(entry, { names: false })`, a `mark()` per `changeClients(entry)`, the
  state dot and word, a 64 px Undo slot (Undo only when `rowState().undo`), and `opens()`. Rows
  with `over` step back: `--dim` fill, muted title, faint dot. The row of the open Details gets
  `aria-current="true"`, an accent dot and the selection fill. `STATE_BADGES.stale` becomes
  "Not applied: the file changed first". Rows keep Enter and Space to open.
  Builder call: the row title drops the client names because the tiles show them; the toast and
  the review keep `changeTitle(entry)` as it is.
- [ ] **Step 4: Pins.** `test_changes_say_why_a_change_stopped` asserts "Not applied: the file
  changed first" and that "before Apply" is not in `changes.js`. New:

```python
def test_changes_is_a_timeline_by_day():
    text = script("changes.js")
    assert '"Today"' in text and '"Yesterday"' in text and "dayGroups(" in text
    assert "changeClients(" in text and 'aria-current' in text
```

- [ ] **Step 5: design.md.** A "Changes" paragraph: one timeline per day ("Today", "Yesterday",
  then the date); a row is a dot on the rail, the time, the title, client tiles, the state and
  Undo; undone and cancelled rows step back; the open row is lit.
- [ ] **Step 6: Run** the node tests and `uv run pytest tests/unit/test_page_words.py -q` → PASS.
- [ ] **Step 7: Run all four checks, then commit**

```bash
git add src/kitden/web/static/js/changes.js src/kitden/web/static/js/parts.js src/kitden/web/static/style.css docs/design.md tests/frontend/changes.test.mjs tests/unit/test_page_words.py
git commit -m "Changes: a timeline by day, with client tiles on each row"
```

---

### Task 8: Changes Details beside the timeline, and "See it on the map"

**Files:**
- Modify: `src/kitden/web/static/js/changes.js`, `src/kitden/web/static/js/panel.js`
  (`openChange`), `src/kitden/web/static/js/details.js` (`followLink` passes `link.project` to
  `goTo`), `src/kitden/web/static/style.css`, `docs/design.md` (the Changes paragraph)
- Test: `tests/frontend/changes.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `openPanel(content, { dock })`, `detailsCard(card)` with actions
  `{label, run?, body?, primary?}` and `after`, `docksAt`, `goTo(view, selected, { project })`
  (which calls `switchProject`) (Part 4); `followLink`, `technical` (Part 3); `failedWord`,
  `backupNote`, `CLIENT_NAMES` (`parts.js`).
- Produces (all exported from `changes.js`):
  - `TAKES_EFFECT`: each client's restart note → its short form;
    `takesEffect(steps) -> string[]` ("Claude Code: start a new session"; an unknown note whole;
    a login note "Log in: <note>"; each once, in `CLIENT_ORDER`).
  - `changeFacts(entry) -> {label, value}[]`.
  - `historyLine(id, entries, clock = hhmm) -> string`: "<clock> Preview" from the id's UTC time
    (`YYYYMMDDTHHMMSSZ`, as `model._new_change_id` writes it; a preview is not logged), then each
    log line of that id, oldest first, in `HISTORY = { verified: ["Applied", "Checked"], undone:
    ["Undone"], stale: ["Not applied"], restored: ["Failed"], undo_blocked: ["Can't undo"],
    cancelled: ["Cancelled"] }`, joined with " → ".
  - `changePlace(entry) -> {view, selected, project} | null`; `GONE = "This item is no longer there."`.
  - `openChange(card)` in `panel.js`: `panelState.current = { type: "change", id }`, then
    `openPanel(detailsCard(card), { dock: true })` (Part 4's `detailsCard`; Changes is one of
    `DOCKS`, so `docksAt("changes", width)` decides the column or the drawer).

Facts, in order (a row with no value is left out):

| Label | Value |
| --- | --- |
| Project | `target.scope` `"project"` → the folder's name; `"all"` → "All projects"; `"others"` → "All projects except <folder>"; `"mixed"` → "Several places" |
| State | verified "Applied and checked"; undone "Undone"; stale "Not applied: the file changed first"; restored `failedWord(error)`; undo_blocked "Can't undo: the file changed after this"; cancelled "Cancelled"; previewed "Preview only" |
| Backup | verified "Kept · Undo puts it back"; undo_blocked "Kept" |
| Takes effect | `takesEffect(steps).join("; ")`, only when `["verified", "undone", "undo_blocked"].includes(entry.state)` |
| Clients | `changeClients(entry)` in words ("Claude Code and Codex"); the page draws the tiles and "2 clients" in its place |

Places (`selected` null opens the page with nothing selected; `project` is `target.project`
when `target.scope` is `"project"`, else null):

| Action | View | Selected |
| --- | --- | --- |
| `plugin.*` | library | `{kind: "plugin", name}`, the first step name with "@" |
| `plugin.skills`, `skill.*` | library | `{kind: "skill", name: steps[0].name}` |
| `marketplace.add` | library | `{kind: "marketplace", name: steps[0].name}` |
| `project.align` | library | null |
| `gateway.rule` | gateway | `rule.tool` ? `{kind: "tool", name: "<server>/<tool>"}` : `{kind: "mcp_server", name: rule.server}` |
| `mcp.*`, `gateway.move`, `gateway.remove`, `gateway.put_back`, `gateway.keychain`, `gateway.strict`, `gateway.add` | gateway | `{kind: "mcp_server", name: steps[0].name}` |
| `gateway.rules`, `gateway.connect`, `gateway.switch`, `setup_server.*`, anything else | gateway | null |

`changePlace` is null when the change removed its item: `plugin.remove`, `skill.remove`,
`mcp.remove_direct` or `gateway.remove` in state verified or undo_blocked; or `plugin.install`,
`skill.install`, `plugin.skills`, `mcp.add`, `marketplace.add` or `gateway.add` in state undone.

- [ ] **Step 1: Write the failing node tests** in `tests/frontend/changes.test.mjs`:

```js
const utc = (d) => d.toISOString().slice(11, 16);
test('the history line starts at the preview, which the id holds', () => {
  const lines = [{ id: '20261024T110200Z-a1b2c3', state: 'undone', time: '2026-10-24T11:40:00+00:00' },
    { id: '20261024T110200Z-a1b2c3', state: 'verified', time: '2026-10-24T11:02:30+00:00' }];
  assert.equal(historyLine('20261024T110200Z-a1b2c3', lines.slice(1), utc), '11:02 Preview → 11:02 Applied → 11:02 Checked');
  assert.equal(historyLine('20261024T110200Z-a1b2c3', lines, utc), '11:02 Preview → 11:02 Applied → 11:02 Checked → 11:40 Undone');
});
test('takes effect says one short line per client', () => {
  const steps = [{ client: 'claude_code', restart_note: NEW_SESSION }, { client: 'claude_code', restart_note: NEW_SESSION },
    { client: 'codex', restart_note: CODEX_RESTART }, { client: 'cursor', restart_note: 'Something new.' }];
  assert.deepEqual(takesEffect(steps), ['Claude Code: start a new session', 'Codex: restart the app and open CLI sessions', 'Something new.']);
});
test('the facts of an applied change in one project', () => {
  const entry = { state: 'verified', action: 'skill.install', target: { scope: 'project', project: '/h/work/atlas' },
    steps: [{ client: 'claude_code', name: 'api-style', restart_note: NEW_SESSION }] };
  assert.deepEqual(changeFacts(entry), [
    { label: 'Project', value: 'atlas' }, { label: 'State', value: 'Applied and checked' },
    { label: 'Backup', value: 'Kept · Undo puts it back' },
    { label: 'Takes effect', value: 'Claude Code: start a new session' }, { label: 'Clients', value: 'Claude Code' }]);
});
test('a change points at its item on the map', () => {
  const rule = { action: 'gateway.rule', state: 'verified', target: { scope: 'project', project: '/h/work/atlas' },
    rule: { server: 'files', tool: 'read_file' }, steps: [] };
  assert.deepEqual(changePlace(rule), { view: 'gateway', selected: { kind: 'tool', name: 'files/read_file' }, project: '/h/work/atlas' });
  const add = { action: 'plugin.install', state: 'verified', target: { scope: 'all' }, steps: [{ name: 'demo-market' }, { name: 'superpowers@demo-market' }] };
  assert.deepEqual(changePlace(add), { view: 'library', selected: { kind: 'plugin', name: 'superpowers@demo-market' }, project: null });
  assert.deepEqual(changePlace({ action: 'gateway.connect', state: 'verified', steps: [] }), { view: 'gateway', selected: null, project: null });
});
test('a change that removed its item has no place', () => {
  const remove = { action: 'skill.remove', target: { scope: 'all' }, steps: [{ client: 'codex', name: 'code-review' }] };
  assert.equal(changePlace({ ...remove, state: 'verified' }), null);
  assert.equal(changePlace({ ...remove, state: 'undone' }).selected.name, 'code-review');
  assert.equal(changePlace({ action: 'plugin.install', state: 'undone', steps: [{ name: 'x@m' }] }), null);
});
```

  `NEW_SESSION` and `CODEX_RESTART` in the test are the two sentences copied from
  `claude_code.py` and `codex.py`.
- [ ] **Step 2: Run** `node --test tests/frontend/changes.test.mjs` → FAIL.
- [ ] **Step 3: Implement.** A row opens `openChange({ kind: "Change", title:
  changeTitle(entry, { names: false }), id: when(entry.time), facts: changeFacts(entry), why:
  historyLine(entry.id, data.changes), actions, after, technical })`: the facts (the Clients
  value is a Node, the client tiles then `plural(n, "client", "clients")`, as C1 draws it), the
  history line as the explanation (`backupNote(entry)` joins it when it says something);
  `actions`: `{ label: "Undo", run, primary: true }` (verified only; closes the panel and undoes,
  as today) and `{ label: "See it on the map", run }`; "Technical details" folded at the bottom:
  today's step rows (client, `name · scope`, path) and the error text. "See it on the map":
  `changePlace(entry)`; null → the card is drawn again with `after` = a quiet line `GONE`, focus
  stays on the button; else the project path maps to its id in `data.projects` (a project no
  longer on the list keeps the picked one) and `followLink({ label: "See it on the map", view,
  selected, project })`, which calls Part 4's `goTo(view, selected, { project })` (it switches the
  project through `switchProject`). `TAKES_EFFECT` maps `NEW_SESSION` → "start a new session", `RELOAD` → "run
  /reload-plugins or start a new session", Codex's `RESTART` → "restart the app and open CLI
  sessions", Cursor's `RESTART` → "restart the app".
  Builder call: the short forms follow each client's real note; the frame's "Codex: start a new
  session" names Claude Code's step for Codex.
  Builder call: an applied Remove counts as removing the item even when another client keeps its
  own copy (the log cannot tell); "Compare across clients" in the Library still finds that copy.
- [ ] **Step 4: Pins.** `test_changes_rows_open_the_panel_and_keep_paths_off_the_page` still
  finds `openChange`. In `test_changes_and_the_library_say_saved_settings_and_scope`, "Takes
  effect" replaces "To take effect". New:

```python
def test_changes_details_say_state_backup_history_and_place():
    from kitden.clients import claude_code, codex, cursor
    text = script("changes.js")
    for words in ("Applied and checked", "Kept · Undo puts it back", '"See it on the map"',
                  "This item is no longer there.", " Preview", '"Checked"', "{ dock: true }"):
        assert words in text + panel(), words
    for note in (claude_code.NEW_SESSION, claude_code.RELOAD, codex.RESTART, cursor.RESTART):
        assert note in text, note  # every restart note has its short form
```

- [ ] **Step 5: design.md.** The Changes paragraph gains: Details beside the timeline (the
  drawer under 1024 px), Facts (Project, State, Backup, Takes effect, Clients), the history line
  ("14:02 Preview → 14:02 Applied → 14:02 Checked"; a preview is not logged, its time comes from
  the change id), Undo and "See it on the map", which opens Gateway or Library with the item
  selected in the change's project, or says "This item is no longer there.".
- [ ] **Step 6: Run** the node tests and `uv run pytest tests/unit/test_page_words.py -q` →
  PASS. Smoke check in the medium demo: turn `read_file` off for atlas, open Changes, open the
  row: Details docks at 1280 px, Escape closes it and focus returns to the row; "See it on the
  map" opens the Gateway in atlas with `read_file` selected; after Undo, the row steps back.
- [ ] **Step 7: Run all four checks, then commit**

```bash
git add src/kitden/web/static/js/changes.js src/kitden/web/static/js/panel.js src/kitden/web/static/js/details.js src/kitden/web/static/style.css docs/design.md tests/frontend/changes.test.mjs tests/unit/test_page_words.py
git commit -m "Changes: Details beside the timeline, with history and See it on the map"
```

---

### Task 9: The walkthrough 2 script (6.4)

**Files:**
- Create: `docs/research/walkthrough-script-2.md`
- Test: `tests/unit/test_docs_words.py`

**Interfaces:**
- Consumes: `docs/research/walkthrough-script-1.md` (its shape), the medium sample contract, the
  results of walkthrough 1 (`docs/research/walkthrough-2026-10-23.md`).

- [ ] **Step 1: Write the failing test** in `tests/unit/test_docs_words.py`:

```python
def test_walkthrough_script_two_has_the_seven_tasks_on_the_new_pages():
    text = " ".join((ROOT / "docs/research/walkthrough-script-2.md").read_text().split())
    assert "kitden demo --size medium" in text
    assert all(f"## Task {n}:" in text for n in range(1, 8)) and "## Task 8" not in text
    assert "| Task | Done | Wrong turns | Time | What was confusing | Walkthrough 1 |" in text
    for name in ("code-review", "atlas", "api-style", "docs", "files", "read_file", "web"):
        assert f"`{name}`" in text, name
    assert "Part 7 makes List that page's first view" in text
```

- [ ] **Step 2: Run** `uv run pytest tests/unit/test_docs_words.py -q` → FAIL.
- [ ] **Step 3: Write the script**, in the shape of script 1 (Before; The sample, for the
  observer; seven tasks with "Start from", "Done when" and, for the observer only, "Where the
  new pages answer it"; Questions after; Results):
  - Before: `uv run kitden demo --size medium` (or `uvx kitden demo --size medium`); a window at
    least 1280 px wide, dark theme first; no help before a task; 3 minutes stuck → not done.
  - 1 Why Codex and Cursor both have `code-review`: Library map, select it; both clients light;
    Details "One folder, read by Codex and Cursor.".
  - 2 Pick `atlas`, find what differs: the picker; Library List, Differences (`api-style` has no
    Claude Code cell); or the Gateway, where atlas's own `docs` replaces Claude Code's. Either
    counts.
  - 3 Add the missing skill to `atlas` only: "+ Add" in Claude Code's `api-style` cell or "Add
    missing plugins and skills…"; done when they say "in atlas" before Apply.
  - 4 The two `docs` servers of Claude Code and Codex: the Gateway's outside group, one
    "In Claude Code" and one "In Codex"; Details shows another address and command.
  - 5 Turn off `read_file` of `files` for `atlas`: Gateway map, unfold `files`, select
    `read_file`, "Turn off in one project…"; done when they say `web` follows and a running call
    is not stopped.
  - 6 Why Cursor still reaches `files` around the gateway: the faint amber line to the outside
    `files` "In Cursor"; the group "Outside the gateway · calls skip Kitden's rules".
  - 7 Undo the change from task 5: the toast, or Changes → Today → the row → Undo; "See it on
    the map".
  - Questions after: did the map help with tasks 1, 4 and 6; did a page open in the view you
    wanted (Map or List); does "On" read right; on Instructions, where does `atlas`'s CLAUDE.md
    get the AGENTS.md rules from?
  - Results table with the column "Walkthrough 1", and: "Results go to
    `docs/research/walkthrough-<date>.md`; the controller writes them and turns each finding into
    a ruling for Part 7. If the owner finds a map page does not help, Part 7 makes List that
    page's first view (`viewMode`) and the map stays behind the switch. If the owner skips the
    walkthrough, Part 7's ledger says 'skipped'."
- [ ] **Step 4: Run** the test → PASS; the four checks.
- [ ] **Step 5: Commit**

```bash
git add docs/research/walkthrough-script-2.md tests/unit/test_docs_words.py
git commit -m "Walkthrough 2: the seven tasks on the new pages"
```

---

### Task 10: README, the release check, design.md read-through and the roadmap lines

**Files:**
- Modify: `README.md` ("See what needs attention", the Library paragraph's instructions part,
  the Changes sentence; "On" and the project words if Part 4 left them), `docs/development.md`
  (one hand check), `docs/design.md` (read-through only), `tests/unit/test_docs_words.py`

- [ ] **Step 1: Check what Part 4 left.** Part 4's words task already changed README's cell and
  project words ("On", "This project", "Only this project"). Run `grep -n '"Available"\|project
  override' README.md`: it should find nothing. If it finds a line, change it to S.1's words and
  its pin in this commit. The English word "available" in "may or may not be available" stays.
- [ ] **Step 2: Write the failing test:**

```python
def test_readme_says_what_overview_instructions_and_changes_show():
    readme = " ".join((ROOT / "README.md").read_text().split())
    for words in ('"Your setup"', "one card per item", "Pulls in",
                  "Claude Code reads an AGENTS.md when the project has no CLAUDE.md",
                  "Kitden only reads instruction files", "See it on the map"):
        assert words in readme, words
    development = " ".join((ROOT / "docs/development.md").read_text().split())
    assert "an AGENTS.md and no CLAUDE.md" in development
```

- [ ] **Step 3: Write the README lines.** Overview: "**Overview** shows one card per item that
  needs attention or can improve: its name, why, the clients it is about and one button that
  opens the fix. Each server that skips the gateway gets its own card, up to three. Notes that
  need no fix stay folded. "Your setup" is a small tree of your clients, the Kitden gateway and
  the Library; a block opens its page." Instructions: "The Instructions tab shows each file once,
  joined to every client that reads it. Claude Code reads an AGENTS.md when the project has no
  CLAUDE.md, and the files a CLAUDE.md pulls in with `@` show under "Pulls in". Kitden only reads
  instruction files." Changes: "**Changes** keeps the history by day, with Undo, what to restart,
  and "See it on the map"." Replace the sentence about the Clients card.
- [ ] **Step 4: development.md.** Under the release checks, a new group "Before a release that
  touches instruction reading", numbered after the last step: "In a test project with an
  AGENTS.md and no CLAUDE.md, start Claude Code and run `/memory`: it lists AGENTS.md, and the
  Instructions tab names Claude Code under Read by. Add a CLAUDE.md holding `@AGENTS.md`: Claude
  Code no longer reads AGENTS.md on its own, and the tab shows it under Pulls in."
- [ ] **Step 5: Read design.md through once.** Fix only what this part made untrue or said
  twice (the Clients card, "Available" on Instructions, the instruction file badge, the Overview
  shared tile). No new rules.
- [ ] **Step 6: Run** `uv run pytest tests/unit/test_docs_words.py -q` → PASS; the four checks.
- [ ] **Step 7: Commit**

```bash
git add README.md docs/development.md docs/design.md tests/unit/test_docs_words.py
git commit -m "Docs: Overview cards, the Instructions tree and the Changes timeline"
```

- [ ] **Step 8: The report** gives these roadmap lines for the owner (do not edit `ROADMAP.md`
  while `git status` shows the owner's edit):
  - under "### Not released yet": "- **Instructions:** one tree of clients, files and what each
    file pulls in; Claude Code's `@` imports, and its AGENTS.md when a project has no CLAUDE.md.";
    "- **Overview:** one card per item, each server that skips the gateway on its own card, and a
    small "Your setup" tree."; "- **Changes:** a timeline by day; Details beside it with the
    state, the backup, what to restart, the history and "See it on the map"."
  - In "## Planned", item 6 "The whole picture" is done for instructions; in "## Later", the
    "A living map …" line can go now that Parts 4–6 are built.
  - The report also gives: the AGENTS.md check date; the `/api/overview` and Instructions timings
    on the medium and large samples (`scripts/measure-start.py` and one timed
    `/api/instructions` read), which must show no slower start than before this part.

---

## Self-review

- **Coverage.** 6.1 → Tasks 1–4; 6.2 → Tasks 5–6; 6.3 → Tasks 7–8; 6.4 → Task 9; the Done list
  (import tests, Overview and Changes page tests, the removed item, the script) → Tasks 2, 6, 7,
  8, 9.
- **Not placed:** the scope bars of O1 and C1 ("All projects · 3 clients · demo workspace",
  "5 changes this week") and their hint lines; the spec names none, so only the Instructions
  hint line is built.
- **Ruled:** a project's instruction files sit under "Only this project · <folder>" (S.1), not
  I1's "This project · <folder>"; spec 6.1 is updated to match.
