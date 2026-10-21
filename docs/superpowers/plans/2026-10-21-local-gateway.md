# Kitden Gateway (part 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `kitden mcp` becomes a local gateway: servers moved into it are offered to every
client as one server, with tools turned on or off per project from the Kitden page.

**Architecture:** A settings file in Kitden's data folder holds servers and rules (changed only
through the change engine); a cache file holds each server's tool list. `kitden mcp` keeps its
read-only tools and adds the allowed tools of the project it finds, starting upstream servers
on first use. The page moves servers in with the existing "Move into the gateway" flow and shows
tool switches in a server's Details.

**Tech Stack:** Python 3.14, Starlette, MCP Python SDK 2.3 (`mcp`), plain ES modules, pytest,
node:test.

**Spec:** docs/superpowers/specs/2026-10-21-local-gateway-design.md

## Global Constraints

- Every change to a client or to the gateway settings: preview → Apply with a backup → verify →
  Undo, through `changes/engine.py`. The tool cache is found data and is written directly.
- Secrets (env values, header values) never reach the page, a review, a log or a test snapshot.
- Main pages show name, client, action; commands, paths and env stay in Details.
- UI text, code, comments and docs in simple English.
- Tests use sandbox homes and fake MCP servers; never the real home folder.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`,
  `node --test tests/frontend/*.test.mjs`. All green.
- Commit messages: short plain subject, one to three simple lines, ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- The page process must not import the MCP SDK at start (`test_the_page_does_not_load_the_mcp_sdk`);
  import it inside the functions that need it.
- Client limits (checked 2026-10-21): Cursor server + tool name ≤ 60 characters; Claude Code
  MCP_TIMEOUT 30 s; Codex clears env except HOME, LOGNAME, PATH, SHELL, USER, LANG, LC_ALL, TERM,
  TMPDIR, TZ.

## Review Focus

1. A session started in a subfolder of a known project gets that project's rules.
2. An upstream server that hangs on start: `tools/list` still answers at once from the cache;
   the call returns a plain error after the timeout; other servers keep working.
3. Two servers with a tool of the same name: both callable, names stable between sessions.
4. A rule for a tool the server no longer has is ignored; a new tool appears (on).
5. A server name held by two clients with different entries: the move is refused with the
   reason, nothing half-moved.

Tests for these are in Tasks 1, 2, 3 and 4.

---

### Task 1: Settings, rules and the tool cache

**Files:**
- Create: `src/kitden/local_gateway/__init__.py`, `src/kitden/local_gateway/settings.py`
- Test: `tests/unit/test_local_gateway_settings.py`

**Interfaces:**
- Produces: `SETTINGS_FILE = "gateway.json"`, `TOOLS_FILE = "gateway-tools.json"` in
  `data_dir(home)`.
- Produces: `load_settings(home: Path) -> dict` (missing file → `{"servers": {}, "rules":
  {"global": {}, "projects": {}}}`), `load_tools(home) -> dict[str, list[dict]]`,
  `save_tools(home, server: str, tools: list[dict]) -> None` (atomic, mode 600; each tool dict
  is `{"name", "description", "inputSchema"}`).
- Produces: `allowed_tools(settings: dict, tools: dict, project: str | None) -> dict[str,
  list[dict]]`: per server that is on, its tools that are on. Rule shape:
  `rules.global[server] = {"server": "on"|"off", "tools": {tool: "off"}}`,
  `rules.projects[path][server] = {"server": "on"|"off", "tools": {tool: "on"|"off"}}`.
  Server on = project value, else global value, else "on"; tool the same.
- Produces: `rule_step(home: Path, project: str | None, server: str, tool: str | None, state:
  str | None) -> Step`: a `FileEdit` (fmt "json", check "entry") on the settings file, key
  `("rules", "global" | "projects", [path,] server, "server" | ("tools", tool))`; `state=None`
  removes the project's own value (follow global). `client` of the step is `"kitden"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_tools_follow_global_then_project_rules(tmp_path): ...
    # global: github tool "delete_repo" off; project /p: github "delete_repo" on, linear off.
    # allowed_tools(..., None)["github"] lacks delete_repo; for "/p" it has it, and no "linear".
def test_a_rule_for_a_missing_tool_is_ignored_and_a_new_tool_is_on(tmp_path): ...  # Review Focus 4
def test_a_missing_settings_file_reads_as_empty(tmp_path): ...
def test_rule_step_edits_one_entry_and_can_go_back_to_global(tmp_path): ...
    # preview + apply through Engine on a sandbox data folder; state=None removes the key.
def test_the_tool_cache_is_private(tmp_path): ...  # mode 0o600
```

- [ ] **Step 2: Run, expect FAIL** — `uv run pytest tests/unit/test_local_gateway_settings.py -q`
- [ ] **Step 3: Implement** the module (use `json_splice` through the engine's `FileEdit`;
  `changes/atomic.py` for the cache).
- [ ] **Step 4: Full checks, expect PASS.**
- [ ] **Step 5: Commit** — "Gateway: settings, rules and the tool cache"

### Task 2: Finding the project

**Files:**
- Create: `src/kitden/local_gateway/project.py`
- Test: `tests/unit/test_local_gateway_project.py`

**Interfaces:**
- Produces: `main_checkout(path: Path) -> Path`: a git worktree (`.git` file with `gitdir:`
  under `<main>/.git/worktrees/`) maps to `<main>`; anything else to itself.
- Produces: `find_project(env: Mapping[str, str], roots: list[str], cwd: Path, home: Path,
  known: list[str]) -> str | None`. Order: `CLAUDE_PROJECT_DIR`; first root (a `file://` URI);
  first entry of `WORKSPACE_FOLDER_PATHS` (comma separated); `cwd` unless it is `home` or `/`.
  The first candidate wins, is mapped with `main_checkout`, and returns the known project that
  is it or contains it (longest match); otherwise None.

- [ ] **Step 1: Write the failing tests**

```python
def test_claude_project_dir_wins_over_roots_and_cwd(tmp_path): ...
def test_a_subfolder_belongs_to_its_project(tmp_path): ...            # Review Focus 1
def test_a_worktree_maps_to_its_main_checkout(tmp_path): ...
def test_home_or_an_unknown_folder_gives_no_project(tmp_path): ...    # e.g. a Codex chat folder
def test_cursor_workspace_paths_are_read(tmp_path): ...
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** No git command: read the `.git` file.
- [ ] **Step 4: Full checks, expect PASS.**
- [ ] **Step 5: Commit** — "Gateway: find the project of a session"

### Task 3: The gateway inside `kitden mcp`

**Files:**
- Create: `src/kitden/local_gateway/proxy.py`
- Modify: `src/kitden/mcp_server.py` (add the gateway's tools), `src/kitden/cli.py` only if the
  `mcp` command needs the home folder passed
- Create: `tests/fixtures/fake_mcp/echo_server.py` (a tiny stdio MCP server with `MCPServer`:
  tools `echo`, `slow` (sleeps), `clash`), `tests/unit/test_local_gateway_proxy.py`

**Interfaces:**
- Consumes: Task 1 `load_settings`, `load_tools`, `save_tools`, `allowed_tools`; Task 2
  `find_project`; `inventory.projects` for `known`.
- Produces: `exposed_names(allowed: dict[str, list[dict]]) -> dict[str, tuple[str, str]]`:
  exposed name → (server, tool). Servers in sorted order; a tool keeps its name unless an
  earlier server has it, then `<server>_<tool>`; any name over 54 characters (60 minus
  "kitden") becomes its first 45 characters + "_" + the first 8 hex of its SHA-1.
- Produces: `class Upstreams` (one per gateway process): `async call(server, tool, arguments)
  -> CallToolResult`, `async list_tools(server) -> list[dict]`; connects on first use. Stdio:
  `command`, `args` (with `${workspaceFolder}` / `${CLAUDE_PROJECT_DIR}` / `${CLAUDE_PROJECT_DIR:-.}`
  replaced by the project path, or the home folder when there is none), env = HOME, USER, LANG,
  `settings["path"]` as PATH, plus the server's `env`; cwd = the project folder or home.
  HTTP: streamable HTTP with the server's `url` and `headers`. Start timeout 20 s; call
  timeout 300 s. A failure returns `CallToolResult(isError=True)` with one plain sentence.
- Behaviour of `kitden mcp`: on `tools/list`, find the project once (env, `list_roots()` when
  the client has roots, cwd), then return the read-only tools plus the allowed upstream tools
  under their exposed names, with each server's cached schema. A server on with no cache is
  listed at that moment (within 20 s) and the cache is written. `tools/call` on an upstream
  name forwards to it. The read-only tools are unchanged. The MCP SDK's `MCPServer` keeps the
  read-only tools; add the two request handlers on its low-level server, or build a low-level
  `Server` that serves both — whichever needs no private attribute; say which in the report.

- [ ] **Step 1: Write the failing tests** (spawn the gateway with the SDK's stdio client on a
  sandbox home whose settings hold the fake server)

```python
def test_upstream_tools_are_offered_beside_the_read_only_ones(tmp_path): ...
def test_project_rules_decide_the_tools_of_a_session(tmp_path): ...   # CLAUDE_PROJECT_DIR set
def test_a_call_reaches_the_upstream_server(tmp_path): ...
def test_a_slow_server_does_not_hold_up_the_list_or_other_servers(tmp_path): ...  # Focus 2
def test_two_servers_with_one_tool_name_both_work_with_stable_names(tmp_path): ... # Focus 3
def test_exposed_names_stay_within_cursors_limit(): ...
def test_secrets_stay_out_of_errors_and_logs(tmp_path): ...
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Full checks, expect PASS** (keep `test_the_page_does_not_load_the_mcp_sdk` green).
- [ ] **Step 5: Commit** — "Gateway: kitden mcp offers the tools of moved servers"

### Task 4: Move a server into the Kitden gateway

**Files:**
- Modify: `src/kitden/changes/actions.py` (new function), `src/kitden/web/app.py` (`preview`:
  `gateway.move` with gateway id `"kitden"`), `src/kitden/views/after.py` (words)
- Test: `tests/unit/test_local_gateway_move.py`

**Interfaces:**
- Consumes: Task 1 `SETTINGS_FILE`, rule shape; `remove_steps`, `_raw_entry`,
  `setup_server_steps`, `installed_command`.
- Produces: `KITDEN_GATEWAY = "kitden"`; `local_move_steps(adapters, items: list[Item],
  home: Path, known_projects: list[str], command: str | None) -> list[Step]`:
  1. refuses, before any step, with these words:
     - a project-file entry: "{name} is in the project's own files; it stays there."
     - a value from elsewhere (`${…}`, `envFile`, `env_vars`, `bearer_token_env_var`,
       `env_http_headers`, a headers helper): "{name} reads values from your shell; it stays
       direct for now."
     - an OAuth server: `needs_sign_in(url: str, headers: dict) -> bool` sends one MCP
       `initialize` POST (5 s timeout); a 401 answer means OAuth: "{name} signs in with OAuth;
       it stays direct for now." No answer → refuse with "Kitden could not reach {name}."
     - same name, different entries in two clients: "{name} is set up differently in {A} and
       {B}; keep one first." (Review Focus 5)
  2. one settings step per server (key `("servers", name)`, the entry without client-only keys),
     plus `("path",)` = the PATH of the page process when the file has none;
  3. carried rules in the same change: Codex `enabled = false` → global server "off";
     `enabled_tools` → global "off" for the cached tools not listed; `disabled_tools` → "off";
     Claude Code `permissions.deny` `mcp__<name>__<tool>` in `~/.claude/settings.json` (global)
     and in `<project>/.claude/settings.json` / `settings.local.json` of known projects
     (that project); a Claude local-scope entry → global server "off" and its project "on";
  4. the client remove steps;
  5. the `kitden` entry for each affected client that lacks it (`setup_server_steps`; refuse with
     today's wording when `command` is None).
- The review names each Cursor client: "Cursor's own switches for these tools do not carry
  over." and says "Applies to new sessions."

- [ ] **Step 1: Write the failing tests** (sandbox home with fixtures)

```python
def test_moving_adds_the_server_removes_the_entries_and_adds_kitden_where_missing(tmp_path): ...
def test_apply_then_undo_puts_every_file_back(tmp_path): ...
def test_project_file_entries_and_shell_values_are_refused_with_reasons(tmp_path): ...
def test_two_different_entries_with_one_name_are_refused(tmp_path): ...   # Focus 5
def test_an_oauth_server_is_refused_after_a_401(tmp_path): ...  # a local fake HTTP server
def test_codex_and_claude_rules_carry_over(tmp_path): ...
def test_a_local_scope_server_is_on_only_in_its_project(tmp_path): ...
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Full checks, expect PASS.**
- [ ] **Step 5: Commit** — "Gateway: move servers into the Kitden gateway"

### Task 5: The gateway in Kitden's views

**Files:**
- Create: `src/kitden/local_gateway/views.py`
- Modify: `src/kitden/web/app.py` (`build_marked`, routes), `src/kitden/views/gateway_view.py`
- Test: `tests/unit/test_local_gateway_views.py`

**Interfaces:**
- Consumes: Tasks 1, 3, 4; `setup_server_state`.
- Produces: `gateway_items(inventory, settings: dict, home: Path) -> list[Item]`: for each
  client with the `kitden` entry, one `mcp_server` item per held server, `via_gateway="kitden"`,
  source = the settings file (key `servers.<name>`), so the Library and Overview count them.
  Added in `build_marked` when `home` is set.
- Produces: in `gateway_view`, a first gateway `{"id": "kitden", "kind": "kitden", "name":
  "Kitden gateway", "where": "On this Mac", "movable": true}`; its `connections` from those
  items; servers of the "local" group become movable when this gateway exists.
- Produces: `GET /api/gateway/tools?server=&project=` → `{"server", "tools": [{"name",
  "description", "state": "on"|"off", "differs": bool}]}` from the cache and rules;
  `POST /api/gateway/tools/refresh` (background) and the manual Rescan refresh the cache by
  listing each held server (lazy SDK import); watcher rescans do not.
- Preview action `gateway.rule` with `params: {server, tool|null, state, project|null}` →
  `rule_step` (Task 1); after words "On" / "Off" / "Follows all projects"; the review says
  "Applies to new sessions."
- After a verified move into the Kitden gateway, the moved servers' tool lists are refreshed in
  the background.

- [ ] **Step 1: Write the failing tests**

```python
def test_held_servers_show_via_kitden_gateway_in_connected_clients(tmp_path): ...
def test_the_kitden_gateway_is_listed_and_local_servers_can_move(tmp_path): ...
def test_tools_api_marks_project_differences(tmp_path): ...
def test_a_rule_change_previews_applies_and_undoes(tmp_path): ...
def test_watcher_rescans_never_start_servers(tmp_path): ...
def test_a_verified_move_refreshes_the_tool_list(tmp_path): ...
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Full checks, expect PASS.**
- [ ] **Step 5: Commit** — "Gateway: show it on the page and change tool rules"

### Task 6: The page

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (Kitden gateway card), `panel.js` (tool
  switches in Details), `library.js` / `parts.js` if a word changes, `style.css`
- Test: `tests/frontend/*.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 5 API and `gateway.rule` preview.
- Gateway page: a "Kitden gateway · On this Mac" card first: connected clients, held servers
  (name, Details), and "Set up in {client}…" where the `kitden` entry is missing. "Move into the
  gateway…" on direct servers offers the Kitden gateway; local servers can now move.
- A held server's Details: its tools, one switch each, for the project picked at the top (or
  "All projects" with Global). A tool whose project state differs from all projects shows
  "Differs from all projects" and a "Use all projects" button (state null). Each switch opens
  the review; the switch flips only after verify. "Refresh tools" refreshes the cache.
- Library MCP rows: held servers show the gateway socket and "Kitden gateway" as `where`.

- [ ] **Step 1: Write the failing frontend tests** (pure helpers: tool row state, labels).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Build**, keeping today's patterns (busy buttons, focus keys, motion rules).
- [ ] **Step 4: Full checks, expect PASS.** Check on the sandbox preview (fake upstream server
  as a held server): move, switch a tool for a project, Undo; light and dark; phone width.
- [ ] **Step 5: Commit** — "Gateway: tools per project on the page"

### Task 7: Docs

**Files:** `README.md`, `docs/design.md`, `ROADMAP.md`, `docs/development.md` (a manual check
per client before release: Claude Code, Codex, Cursor on a test project).

- [ ] **Step 1: Edit.** README: a short "Kitden gateway" section (no deploy; tools per project;
  what stays direct and why). ROADMAP: "Not released yet" line; Later: "Logins in one place",
  "Skills per project".
- [ ] **Step 2: Full checks, expect PASS.**
- [ ] **Step 3: Commit** — "Docs: the Kitden gateway"
