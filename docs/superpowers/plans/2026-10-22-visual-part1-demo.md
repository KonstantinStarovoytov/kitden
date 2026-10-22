# Part 1: A sample setup and a safe demo mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `kitden demo` opens the real page on a built-in sample setup (small, medium or large)
in a temporary folder, with no real client, MCP server, Keychain or network; every change Kitden
previews stays inside the home folder, Kitden's data folder and the known projects; and the owner
gets a one-page script for the first walkthrough.

**Architecture:** A new package `kitden.demo` writes synthetic homes in the shapes the real
adapters read (the shapes of `tests/fixtures`), and holds the demo's stand-ins: a client-command
runner that edits the sample's files, a Keychain kept in a file, and a canned tool list.
`create_app(..., demo=True)` swaps each call that leaves the process for its stand-in, through
parameters that exist (`run`, `setup_command`, `version_refresh`) or small new ones
(`keychain_run`, `sign_in`), and refuses what needs the network. The engine gains one check at
preview: each path a step writes must be inside `writable_roots(home, inventory)`.

**Tech Stack:** Python 3.13, Starlette, tomlkit, `sqlite3` and `tempfile` from the standard
library; plain ES modules; pytest on sandbox homes; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-22-visual-management-design.md`, Part 1 (1.1–1.4) and
its Done line, plus Constraints, Anti-goals and Acceptance. Master plan:
`docs/superpowers/plans/2026-10-22-visual-management.md` (Rules; the names `build_demo_home`,
`SIZES`, `DEMO_SECRET_`, `create_app(..., demo)`, `GET /api/about`, `kitden demo`,
`writable_roots` and its refusal; Walkthroughs). Concept
`docs/research/visual-management-ux-concept-2026-10-22.md` §12 (fixture sizes, scenes, the
seven tasks).

## Global Constraints

- `AGENTS.md` in full: code, comments, UI text and docs in simple English, short and plain.
- Every change of a client's settings goes through `src/kitden/changes/engine.py`: preview →
  Apply with a backup → verify → Undo. The demo uses the same engine on the sample's files.
- No new runtime dependency. The sample is written by code in `src/kitden/demo/` (the wheel ships
  only `src/kitden`); `tests/fixtures/` stays as it is.
- Every fake secret in a sample starts with `DEMO_SECRET_` and sits only where the matching
  fixture keeps a `SENTINEL_SECRET_` (places the existing sweep proves hidden).
- The demo never touches the real home, runs a real client or `security`, starts an MCP server,
  reads `CODEX_HOME` or `/Applications`, or opens a network connection (spec Anti-goals).
- Exact copy: the boundary refusal is "Kitden writes only in your home folder and your known
  projects."; the demo's refusal is "Not part of the demo."
- Names from the master plan's table are used exactly: `kitden.demo.build_demo_home(root: Path,
  size: str) -> Path`, `kitden.demo.SIZES = ("small", "medium", "large")`, the prefix
  `DEMO_SECRET_`, `create_app(..., demo: bool = False)`, `GET /api/about` →
  `{"version": str, "demo": bool}`, `kitden demo [--size small|medium|large]`,
  `writable_roots(home: Path, inventory) -> list[Path]`.
- Page changes follow `docs/design.md` and update it in the same commit; new page words are
  pinned in `tests/unit/test_page_words.py`; page helper logic is a pure function in a module
  under `src/kitden/web/static/js/` with a node test.
- Tests use sandbox homes only (`make_home`, `write_cursor_fixture_state`, or `build_demo_home`);
  the conftest guards that refuse real `claude`, `codex`, `cursor` and `security` stay on.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src
  tests`, `node --test tests/frontend/*.test.mjs`. Stage files by name only. Messages: a short
  plain subject without a prefix, one to three lines, ending with the co-author line the session
  gives.
- `ROADMAP.md`: while `git status` shows it modified by the owner, no task edits or stages it;
  Task 8 writes the roadmap lines into the part's report instead.
- Line numbers are hints; find code by name.

## Review Focus

1. A known project on another disk (outside the home folder): an add into it still previews and
   applies (Task 3, `test_a_known_project_outside_home_stays_writable`).
2. A settings file that is a link (a dotfiles setup): a link to a file inside the home folder
   still changes; a link that leads out of it is refused with the sentence, before the file is
   read (Task 3, `test_a_link_out_of_home_is_refused_and_one_inside_is_not`).
3. `CODEX_HOME` set in the person's shell: in real use a Codex folder outside the home folder
   stays writable; in the demo it is ignored and only the sample shows (Task 3,
   `test_a_codex_home_outside_home_stays_writable`; Task 5, `test_the_demo_ignores_codex_home`).
4. Stopping the demo (Ctrl+C, or the server failing) while the real page may also run: the sample
   folder is deleted, the real home is untouched (no data-folder copy, no page record), and the
   demo listens on its own port (Task 6, `test_demo_serves_the_sample_and_deletes_it_on_exit`,
   `test_demo_deletes_its_folder_when_the_server_fails`, `test_demo_never_touches_the_real_home`).
5. The buttons a person presses most in the demo (Rescan, Refresh tools, a move into the gateway,
   strict mode) start no program and open no connection, not even to `localhost` (Task 7,
   `test_moving_servers_in_and_strict_mode_start_nothing`).

---

### Task 1: Small and medium sample homes (spec 1.1)

**Files:**
- Create: `src/kitden/demo/__init__.py` (the public names below), `src/kitden/demo/sample.py`
  (the writer)
- Test: `tests/unit/test_demo_home.py`

**Interfaces:**
- Produces:
  - `SIZES = ("small", "medium", "large")`; `DEMO_SECRET = "DEMO_SECRET_"`;
    `VERSIONS = {"claude_code": "2.1.283", "codex": "0.159.2", "cursor": "3.21.16"}`.
  - `build_demo_home(root: Path, size: str) -> Path`: writes `root / "home"` (fails when it
    exists) and `keychain_file(home)`, returns the home. Any other size:
    `ValueError("Choose small, medium or large.")`. The same size writes the same files every
    time; paths inside files use the home's absolute path. Until Task 2, `"large"` writes the
    medium sample.
  - `demo_command(home: Path) -> str`: `str(home / ".local/bin/kitden")`.
  - `keychain_file(home: Path) -> Path`: `home.parent / "keychain.json"`.
  - `demo_adapters(home: Path) -> list[ClientAdapter]`: `ClaudeCodeAdapter`, `CodexAdapter`
    (`codex_home=home / ".codex"`, `list_plugins=lambda: {"installed": []}`) and `CursorAdapter`,
    each with `read_version` giving `VERSIONS[id]` only when `home / adapter.config_root` exists.
  - `demo_build(home: Path) -> Callable[..., Inventory]`:
    `lambda **options: build_inventory(home, demo_adapters(home), [], **options)` (no app folder).
  - The samples below. Later parts test on these names; keep them.

Medium (`~` is the sample home, `A` is `~/work/atlas`):

| File | Holds |
| --- | --- |
| `~/.claude.json` | `mcpServers`: `github` (`type http`, `url https://api.github.example.test/mcp`, header `Authorization: Bearer DEMO_SECRET_GITHUB`), `docs` (`type http`, `url https://docs.example.test/mcp`), `kitden` (`demo_command(home)`, `args ["mcp"]`). `projects`: `A` (`enabledMcpjsonServers ["docs"]`), `A/web`, `~/work/website` (local server `local-db`: `uvx mcp-db --password DEMO_SECRET_DB`), `~/work/old-app` (no folder). `oauthAccount.emailAddress = DEMO_SECRET_EMAIL` |
| `A/.mcp.json` | `docs` (`type http`, `url http://localhost:9000/mcp`): Atlas overrides the user's `docs` |
| `~/.claude/settings.json` | `enabledPlugins`: `superpowers@demo-market` true, `pr-review@demo-market` false; hook `PreToolUse` / `Bash` → `echo check`; `extraKnownMarketplaces.demo-market` |
| `~/work/website/.claude/settings.json` | `enabledPlugins.superpowers@demo-market = false`: a project turns a plugin off |
| `~/.claude/plugins/` | `installed_plugins.json` and `cache/demo-market/`: `superpowers` 7.0.0 (skills `brainstorming`, `planning`), `pr-review` 1.0.0 (`.mcp.json` server `pr-index`); `known_marketplaces.json`: `demo-market` at `~/.claude/plugins/marketplaces/demo-market`, whose `.claude-plugin/marketplace.json` lists `superpowers`, `pr-review`, `test-helper`, `db-tools` with local folders (the last two not installed) |
| `~/.claude/skills/` | `brandkit`, `release-notes`, and `shared-style` → `../../shared/style` (the one relative link) |
| Instruction files | `~/.claude/CLAUDE.md` (a line `token: DEMO_SECRET_INSTRUCTIONS`), `~/.claude/commands/review.md`, `~/.claude/agents/reviewer.md` (front matter `name: reviewer`, `description: Reviews changes.`: Part 7 lists a Claude Code agent only by its `name:`), `A/CLAUDE.md`, `A/AGENTS.md`, `~/.codex/AGENTS.md`, `~/work/website/.cursor/rules/style.mdc` |
| `~/.codex/config.toml` | `mcp_servers`: `docs` (`command "npx"`, `args ["docs-mcp"]`: Claude Code's name, another source), `analytics` (`url https://analytics.example.test/mcp`, `http_headers = { Authorization = "Basic DEMO_SECRET_ANALYTICS" }`), `sqlite` (`uvx mcp-server-sqlite`, `enabled = false`), `kitden` (`demo_command(home)`, `args ["mcp"]`, `startup_timeout_sec = 30`, `tool_timeout_sec = 300`); `plugins."browser@openai-bundled".enabled = true` with its cache folder; `marketplaces.demo-market` (`source_type "local"`, the folder above); `projects.A.trust_level "trusted"`; `projects."~/work/sandbox".trust_level "untrusted"` |
| Skills Codex reads | `~/.agents/skills/code-review` and `~/.agents/skills/docker-expert` (the shared folder; Cursor reads it too), `~/.codex/skills/langfuse`, `A/.agents/skills/api-style` (Atlas only; Claude Code lacks it) |
| `~/work/sandbox/.codex/config.toml` | `mcp_servers.scratch` (`command "curl"`): not loaded, Codex does not trust the folder |
| `~/.cursor/mcp.json` | `files` (`npx files-mcp`: a direct route beside the gateway's `files`), `n8n` (`npx n8n-mcp`, `env.N8N_API_KEY = DEMO_SECRET_N8N`), `browser-tools` (`npx browser-tools-mcp`, no secret) |
| Cursor state (SQLite, as `tests/conftest.py write_cursor_state` writes it) | `cursor.plugins.installedIds.*` rows for no workspace, for `A` and for `~/work/website` (key shapes as in `tests/fixtures/cursor/3.21.16/cursor-state.json`); plugin id `"501"`, named `ui-kit@cursor-public` by a workspace snapshot and a folder in `~/.cursor/plugins/cache/cursor-public/ui-kit/<hash>/`; row `mcpOAuth.files = {"access_token": "DEMO_SECRET_OAUTH"}`; no reactive-storage row, so Cursor keeps its defaults (it reads Claude Code's and Codex's skill folders and imports Claude Code's plugins) |
| Cursor's own | `~/.cursor/skills/ui-polish`; `~/.cursor/hooks.json` `afterFileEdit` → `./format.sh` |
| `~/work/website/.cursor/mcp.json` | cut short, not valid JSON: the unreadable file |
| `data_dir(home)/gateway.json` | `path "/usr/local/bin:/usr/bin:/bin"`; `servers.files` (`npx files-mcp`, `env.FILES_TOKEN = DEMO_SECRET_FILES` kept plain), `servers.tracker` (`url https://tracker.example.test/mcp`, `headers.Authorization = {"keychain": "tracker/Authorization"}`); `rules.global`: `files.tools.delete_file "off"`, `tracker.mode "strict"`, `tracker.tools.list_issues` and `create_issue` `"on"`; `rules.projects`: `A` → `files.tools.write_file "off"`, `A/web` → `files.tools.search_files "off"` |
| `data_dir(home)/gateway-tools.json` | `files`: `read_file` (`readOnlyHint true`), `write_file` (`destructiveHint true`), `delete_file`, `search_files` (no hints); `tracker`: `list_issues` (`readOnlyHint true`), `create_issue`, `export_report` (no hints) |
| `data_dir(home)/gateway-calls.json` | `files.read_file` 12, `files.search_files` 3, `tracker.list_issues` 5, each with a fixed `last` such as `2026-10-21T09:30Z` |
| `keychain_file(home)` | `{"kitden tracker/Authorization": "Bearer DEMO_SECRET_TRACKER"}` |

**Sample contract (medium).** Later parts refer to these items by name; Task 1's contract test
pins each one, read with plain `build_inventory(home)` under the conftest guards:

| Case | Item |
| --- | --- |
| An unreadable settings file with a known path | `~/work/website/.cursor/mcp.json`, problem `parse_error` |
| A same-name MCP server from two sources, loading in both | `docs`: Claude Code user (`url https://docs.example.test/mcp`) and Codex user (`npx docs-mcp`), both in each client's all-projects view |
| A project item that overrides an all-projects one (Claude Code) | `docs` in `A/.mcp.json` over the user `docs`; also `superpowers@demo-market` turned off in `~/work/website` |
| A skill folder two clients read | `~/.claude/skills/brandkit` (Claude Code, and Cursor by its default third-party reading); `~/.agents/skills/code-review` (Codex and Cursor) |
| A known project inside another, the outer one with a gateway rule | `A/web` inside `A`; `A` sets `files.write_file` off |
| A held tool with an unknown hint, on for all projects | `files.search_files` (no rule for all projects; only `A/web` turns it off) |
| A held tool that waits under strict mode | `tracker.export_report` |
| A direct route beside a gateway route | Cursor's own `files` entry, while the gateway holds `files` |
| A Claude Code agent named by its front matter | `~/.claude/agents/reviewer.md` (`name: reviewer`) |

Which parts lean on which case: the unreadable file (Part 2 Task 3), `docs` (Parts 2, 4, 8: Needs
review, Differences in `atlas`, the tour), the override in `atlas` (Parts 2, 4, 8), `code-review`
(Parts 6 and 8, both walkthroughs), `A/web` and `files.write_file` (Parts 5, 8), `files.search_files`
(Part 5), `tracker.export_report` (Parts 5, 8), Cursor's direct `files` (Part 8, both walkthroughs),
`reviewer` (Part 7). A later part that needs a case not in this table adds it here and to the
contract test, in its own branch, before it relies on it.

Small: Claude Code only. `~/.claude.json` with `github` and `docs` as above and the one project
`A`; `~/.claude/settings.json` with `superpowers@demo-market` on and `demo-market`; the
`superpowers` cache and the marketplace folder; skills `brandkit` and `release-notes`;
`~/.claude/CLAUDE.md` with its secret line; `A/CLAUDE.md`. No `.codex`, `.cursor` or gateway
files; `keychain_file(home)` holds `{}`.

Builder call: the medium sample has no Claude Desktop config, so the page shows three clients
(concept §12).
Builder call: the sample's `gateway.json` has a `path`, so a move into the gateway never writes
this computer's `PATH` into the sample (no personal path in a picture, spec 8.4).
Builder call: the sample's `kitden` entries run `demo_command(home)`; nothing runs that path and
it does not exist.
Builder call: Codex's plugin list in the demo answers `{"installed": []}`.
Builder call: the Keychain stand-in's file sits beside the home (`root/keychain.json`), so no scan
of the home ever reads it.

- [ ] **Step 1: Write the failing tests**

```python
import json
from pathlib import Path

import pytest

from kitden.demo import (
    DEMO_SECRET, VERSIONS, build_demo_home, demo_adapters, demo_build, keychain_file,
)
from kitden.local_gateway.project import project_chain
from kitden.local_gateway.settings import deciding_project, load_calls, load_settings, load_tools
from kitden.local_gateway.views import held_servers, tools_view
from kitden.model import ClientStatus, ItemKind, Scope
from kitden.views.effective import effective_view
from kitden.views.inventory import build_inventory
from kitden.views.setup_server import setup_server_state


def _found(inventory):
    return {c.id for c in inventory.clients if c.status is ClientStatus.FOUND}


def _rel(home, path):
    return Path(path).relative_to(home).as_posix()


def test_the_small_sample_is_claude_code_and_one_project(tmp_path):
    home = build_demo_home(tmp_path, "small")
    inventory = demo_build(home)()
    assert home == tmp_path / "home"
    assert _found(inventory) == {"claude_code"}
    assert [_rel(home, p.path) for p in inventory.projects] == ["work/atlas"]
    kinds = [i.kind for i in inventory.items]
    assert kinds.count(ItemKind.MCP_SERVER) >= 2 and kinds.count(ItemKind.SKILL) >= 2
    assert ItemKind.PLUGIN in kinds


def test_the_medium_sample_has_three_clients_five_projects_and_about_60_items(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inventory = demo_build(home)()
    assert {c.id: c.version for c in inventory.clients} == VERSIONS
    assert 50 <= len(inventory.items) <= 75
    assert {_rel(home, p.path): p.exists for p in inventory.projects} == {
        "work/atlas": True, "work/atlas/web": True, "work/website": True,
        "work/sandbox": True, "work/old-app": False,
    }
    codex = next(a for a in demo_adapters(home) if a.id == "codex")
    assert codex.trusts(str(home / "work/atlas"))
    assert not codex.trusts(str(home / "work/sandbox"))


def test_the_medium_sample_contract(tmp_path):
    """The cases later parts name; read as any test reads a home, under the conftest guards."""
    home = build_demo_home(tmp_path, "medium")
    inventory = build_inventory(home)
    items = inventory.items
    assert _found(inventory) == {"claude_code", "codex", "cursor"}
    for name, clients in (("code-review", {"codex", "cursor"}),
                          ("brandkit", {"claude_code", "cursor"})):
        shared = [i for i in items if i.kind is ItemKind.SKILL and i.name == name]
        assert {i.client for i in shared} == clients
        assert len({i.source.path for i in shared}) == 1  # one folder, read by two clients
    docs = [i for i in items if i.kind is ItemKind.MCP_SERVER and i.name == "docs"
            and i.scope is Scope.USER]
    assert sorted(i.client for i in docs) == ["claude_code", "codex"]
    fields = {tuple(p for p in i.summary if p[0] in ("command", "args", "url")) for i in docs}
    assert len(fields) == 2  # same name, two sources
    for client in ("claude_code", "codex"):  # and it loads in both, for all projects
        assert "docs" in {i.name for i in effective_view(inventory, client, None).items}
    view = effective_view(inventory, "claude_code", str(home / "work/atlas"))
    assert [(w.scope, lo.scope, m) for w, lo, m in view.shadowed if w.name == "docs"] == [
        (Scope.PROJECT, Scope.USER, "override")
    ]
    settings, tools = load_settings(home), load_tools(home)
    search = next(t for t in tools_view(settings, tools, "files", [])["tools"]
                  if t["name"] == "search_files")
    assert (search["hint"], search["state"]) == ("unknown", "on")
    assert [(_rel(home, p.path), str(p.unknown_reason)) for p in inventory.problems] == [
        ("work/website/.cursor/mcp.json", "parse_error")
    ]
    names = {i.name for i in items if i.kind is ItemKind.INSTRUCTIONS}
    assert {"CLAUDE.md", "AGENTS.md", "review", "reviewer"} <= names
    agent = (home / ".claude/agents/reviewer.md").read_text()
    assert "name: reviewer" in agent and "description:" in agent
    states = {s["client"]: s["state"] for s in setup_server_state(inventory)}
    assert states == {"claude_code": "added", "codex": "added", "cursor": "missing"}
    assert any(i.client == "cursor" and i.name == "files" and i.via_gateway is None for i in items)


def test_the_medium_sample_has_a_kitden_gateway_with_rules_and_tools(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inventory = demo_build(home)()
    settings, tools = load_settings(home), load_tools(home)
    held = {s["name"]: (s["kind"], s["plain_secrets"]) for s in held_servers(settings, [], tools)}
    assert held == {"files": ("local", True), "tracker": ("remote", False)}
    hints = {t["name"]: t["hint"] for t in tools_view(settings, tools, "files", [])["tools"]}
    assert hints == {"read_file": "reads", "write_file": "writes",
                     "delete_file": "may write", "search_files": "unknown"}
    new = {t["name"]: t["new"] for t in tools_view(settings, tools, "tracker", [])["tools"]}
    assert new == {"list_issues": False, "create_issue": False, "export_report": True}
    web, atlas = str(home / "work/atlas/web"), str(home / "work/atlas")
    chain = project_chain(web, home, [p.path for p in inventory.projects])
    assert chain == [web, atlas]
    assert deciding_project(settings, chain, "files", "write_file") == atlas  # parent's rule
    assert deciding_project(settings, chain, "files", "search_files") == web  # its own rule
    assert settings.get("path")
    assert load_calls(home)["files"]["read_file"]["count"] == 12
    assert json.loads(keychain_file(home).read_text()) == {
        "kitden tracker/Authorization": "Bearer DEMO_SECRET_TRACKER"
    }


@pytest.mark.parametrize("size", ["small", "medium"])
def test_a_sample_holds_demo_secrets_and_no_sentinel(tmp_path, size):
    build_demo_home(tmp_path, size)
    files = [p for p in tmp_path.rglob("*") if p.is_file() and not p.is_symlink()]
    text = "".join(p.read_text(errors="ignore") for p in files)
    assert text.count(DEMO_SECRET) >= (2 if size == "small" else 6)
    assert "SENTINEL" not in text


def test_the_same_size_writes_the_same_files(tmp_path):
    def files(home):
        return {
            p.relative_to(home.parent).as_posix(): p.read_text().replace(str(home), "~")
            for p in sorted(home.parent.rglob("*"))
            if p.is_file() and not p.is_symlink() and p.suffix != ".vscdb"
        }

    assert files(build_demo_home(tmp_path / "a", "medium")) == files(
        build_demo_home(tmp_path / "b", "medium")
    )


def test_an_unknown_size_is_refused(tmp_path):
    with pytest.raises(ValueError, match="Choose small, medium or large."):
        build_demo_home(tmp_path, "huge")
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_demo_home.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'kitden.demo'`.

- [ ] **Step 3: Implement** `src/kitden/demo/sample.py` (one private writer per client and one for
the gateway files, a `_skill(folder, name)` helper) and the names in `__init__.py`. Copy each
file's shape from the fixture file of the same client (`tests/fixtures/claude_code/2.1.283`,
`codex/0.159.2`, `cursor/3.21.16`), write JSON with `json.dumps(..., indent=2)` and TOML as plain
text, and the Cursor databases with `sqlite3` exactly as `write_cursor_state` does (table
`ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)`). Module docstring: the sample is
synthetic, for `kitden demo` and tests; no real client wrote it.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/unit/test_demo_home.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/demo/__init__.py src/kitden/demo/sample.py tests/unit/test_demo_home.py
git commit -m "Demo: small and medium sample homes"
```

---

### Task 2: The large sample; the start measurement uses it (spec 1.1)

**Files:**
- Modify: `src/kitden/demo/sample.py` (`_bulk(home: Path) -> None`, called for `"large"` after
  the medium sample)
- Modify: `scripts/measure-start.py` (`build_sandbox(root: Path, slow: float) -> Path`; drop
  `--servers`, `--plugins`, `--skills` and `_skill`; docstring and usage)
- Test: `tests/unit/test_demo_home.py`, `tests/unit/test_measure_start.py`

**Interfaces:**
- Consumes: `build_demo_home`, `demo_build`, `load_settings` (Task 1).
- Produces: `build_demo_home(root, "large")`: the medium sample plus 150 MCP servers
  `bench-server-NNN` (50 in each client's user file, every second one a `url` on
  `https://example.test/<name>`), 30 Claude Code plugins `plugin-NN@bench-market` (installed,
  cached, one skill each), 120 skills `bench-skill-NNN` (40 each in `~/.claude/skills`,
  `~/.agents/skills`, `~/.cursor/skills`), 12 more projects `~/work/bench-project-NN` known to
  Claude Code, each with a `.mcp.json` of one server, and 10 more held servers
  `bench-held-NN` in `gateway.json` (local and remote by turns, no secret), each with four to six
  cached tools in `gateway-tools.json`. `scripts/measure-start.py`
  `build_sandbox(root, slow)` = `build_demo_home(root, "large")` plus the fake `claude`, `codex`
  and `cursor` in `root / "bin"`, as today.

Builder call: every tenth bulk server, every fourth bulk project and one bulk held server get a
long name of at least 60 characters, so the page's cutting with "…" is always exercised.
Builder call: the script's count flags go; the sizes come from the sample (one copy of the
generator).

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_demo_home.py`, add `"large"` to the secrets test's parameters (at least 6),
and:

```python
def test_the_large_sample_has_hundreds_of_items_long_names_and_many_projects(tmp_path):
    home = build_demo_home(tmp_path, "large")
    inventory = demo_build(home)()
    assert len(inventory.items) >= 300
    assert len(inventory.projects) > 10
    assert max(len(i.name) for i in inventory.items) >= 60
    assert max(len(Path(p.path).name) for p in inventory.projects) >= 60
    servers = [i for i in inventory.items
               if i.kind is ItemKind.MCP_SERVER and i.name.startswith("bench-server-")]
    assert len(servers) == 150 and {i.client for i in servers} == {"claude_code", "codex", "cursor"}
    plugins = [i for i in inventory.items if i.kind is ItemKind.PLUGIN
               and i.client == "claude_code" and i.name.endswith("@bench-market")]
    assert len(plugins) == 30
    folders = (".claude/skills", ".agents/skills", ".cursor/skills")
    skills = [p for f in folders for p in (home / f).glob("bench-skill-*/SKILL.md")]
    assert len(skills) == 120 and all(list((home / f).glob("bench-skill-*")) for f in folders)
    direct = {i.name for i in inventory.items
              if i.kind is ItemKind.MCP_SERVER and i.via_gateway is None}
    held = load_settings(home)["servers"]
    assert len(direct) > 6 and len(held) > 6
    assert {"files", "tracker"} <= set(held)  # medium's cases stay
    assert max(len(name) for name in held) > 40
    assert all(load_tools(home).get(name) for name in held)
```

In `tests/unit/test_measure_start.py`, replace `test_the_sandbox_builder_makes_the_counts_asked`:

```python
def test_the_sandbox_is_the_large_sample_with_fake_clients(tmp_path):
    home = measure_start.build_sandbox(tmp_path, slow=0)
    assert home == tmp_path / "home"
    servers = json.loads((home / ".claude.json").read_text())["mcpServers"]
    assert len([n for n in servers if n.startswith("bench-server-")]) == 50
    assert {p.name for p in (tmp_path / "bin").iterdir()} == {"claude", "codex", "cursor"}
```

and call `measure_start.build_sandbox(tmp_path, slow=0.5)` in
`test_the_fake_codex_sleeps_then_answers` (its assertions stay).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_demo_home.py tests/unit/test_measure_start.py -v`
Expected: FAIL (the large sample has medium's size; `build_sandbox` takes other arguments).

- [ ] **Step 3: Implement** `_bulk` and the script change. The script imports
`from kitden.demo import build_demo_home` and no longer imports `make_home` or
`write_cursor_fixture_state`.

- [ ] **Step 4: Run them to see them pass**, then the budgets:

Run: `uv run pytest tests/unit/test_demo_home.py tests/unit/test_measure_start.py -v`
Expected: PASS.
Run: `uv run python scripts/measure-start.py`
Expected: exit 0, `first usable` under 2 s and `complete` under 5 s. Note both numbers for Task 8.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/demo/sample.py scripts/measure-start.py tests/unit/test_demo_home.py tests/unit/test_measure_start.py
git commit -m "Demo: the large sample; the start measurement uses it"
```

---

### Task 3: Kitden writes only in the home folder and known projects (spec 1.3)

**Files:**
- Modify: `src/kitden/changes/engine.py` (`OUTSIDE`, `writable_roots`, `Engine(..., roots=)`, the
  check at the start of `preview`)
- Modify: `src/kitden/clients/codex.py` (`CodexAdapter.detect`)
- Modify: `src/kitden/web/app.py` (`create_app` passes `roots`)
- Test: `tests/unit/test_write_boundary.py`

**Interfaces:**
- Produces:
  - `OUTSIDE = "Kitden writes only in your home folder and your known projects."` (engine.py).
  - `writable_roots(home: Path, inventory) -> list[Path]` (engine.py): the real paths
    (`os.path.realpath`) of `home`, `data_dir(home)`, every `inventory.projects` path (its folder
    there or not) and every `config_roots` folder of a client whose status is found; each once,
    in that order.
  - `Engine.__init__(store, run, on_write=None, gateway_clients=None, *, roots: Callable[[],
    list[Path]] | None = None)`. With `roots`, `preview` raises `ChangeRefusedError(OUTSIDE)`
    before it reads any file when a step's edit path, copy target, removal path or command folder
    (`cwd`), taken as a real path, is not a root or inside one. Gateway API steps (an address) and
    Keychain items are not paths. Without `roots` nothing is checked (engine unit tests).
  - `CodexAdapter.detect()` returns the base answer with `config_roots=(str(self.codex_home),)`.
  - `create_app` builds `Engine(..., roots=lambda: writable_roots(home, state.inventory))`
    (`writable_roots` looked up at call time, so a test can patch `kitden.web.app.writable_roots`).

Builder call: `writable_roots` and `OUTSIDE` live in `changes/engine.py`, and the check also covers
a client command's working folder.
Builder call: the roots also take each found client's config folders, and Codex names its
`codex_home` there, so a `CODEX_HOME` outside the home folder stays writable (the spec's three
roots alone would refuse it).

- [ ] **Step 1: Write the failing tests**

```python
import os
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import kitden.web.app as page_app
from kitden.changes.backup import ChangeStore
from kitden.changes.engine import OUTSIDE, ChangeRefusedError, Engine, writable_roots
from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.clients.codex import CodexAdapter
from kitden.gateways import data_dir
from kitden.model import (
    ChangeState, Client, ClientStatus, FileEdit, Project, Scope, Step,
)
from kitden.views.inventory import Inventory, build_inventory
from tests.conftest import make_home

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}


def real(path):
    return Path(os.path.realpath(path))


def no_run(command, cwd):
    raise AssertionError("no command in this test")


def test_writable_roots_are_home_data_projects_and_found_client_folders(tmp_path):
    home, other = tmp_path / "home", tmp_path / "disk2/atlas"
    home.mkdir()
    found = Client("codex", "Codex", ClientStatus.FOUND, config_roots=(str(tmp_path / "codex"),))
    gone = Client("cursor", "Cursor", ClientStatus.NOT_FOUND, config_roots=(str(tmp_path / "x"),))
    inventory = Inventory(clients=[found, gone], projects=[Project(path=str(other), exists=False)])
    assert writable_roots(home, inventory) == [
        real(home), real(data_dir(home)), real(other), real(tmp_path / "codex")
    ]


def test_a_path_outside_every_root_is_refused_before_it_is_read(tmp_path):
    home, outside = tmp_path / "home", tmp_path / "elsewhere/settings.json"
    home.mkdir()
    outside.parent.mkdir()
    outside.write_text("not json")  # a read would fail differently
    engine = Engine(ChangeStore(tmp_path / "store"), no_run, roots=lambda: [real(home)])
    edit = FileEdit(path=str(outside), fmt="json", key=("mcpServers", "x"), after={"url": "u"})
    with pytest.raises(ChangeRefusedError) as refused:
        engine.preview("mcp.add", [Step(client="cursor", scope=Scope.USER, name="x", edit=edit)])
    assert str(refused.value) == OUTSIDE


def test_a_known_project_outside_home_stays_writable(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    project = tmp_path / "disk2/atlas"
    project.mkdir(parents=True)
    inventory = Inventory(projects=[Project(path=str(project), exists=True)])
    engine = Engine(
        ChangeStore(data_dir(home)), no_run, roots=lambda: writable_roots(home, inventory)
    )
    step = ClaudeCodeAdapter(home).skill_copy_step(
        home / ".claude/skills/brandkit", ["claude_code"], str(project)
    )
    change = engine.preview("skill.install", [step])
    assert engine.apply(change.id).state is ChangeState.VERIFIED
    assert (project / ".claude/skills/brandkit/SKILL.md").is_file()


def test_a_link_out_of_home_is_refused_and_one_inside_is_not(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    settings = home / ".claude/settings.json"
    kept = home / "dotfiles/claude-settings.json"
    kept.parent.mkdir()
    kept.write_text(settings.read_text())
    settings.unlink()
    settings.symlink_to(kept)
    engine = Engine(
        ChangeStore(data_dir(home)), no_run, roots=lambda: writable_roots(home, Inventory())
    )

    def turn_off():
        key = ("enabledPlugins", "superpowers@claude-plugins-official")
        edit = FileEdit(path=str(settings), fmt="json", key=key, after=False)
        return [Step(client="claude_code", scope=Scope.USER, name=key[1], edit=edit)]

    engine.preview("plugin.disable", turn_off())  # the file itself is in the home folder
    away = tmp_path / "elsewhere/claude-settings.json"
    away.parent.mkdir()
    away.write_text(kept.read_text())
    settings.unlink()
    settings.symlink_to(away)
    with pytest.raises(ChangeRefusedError) as refused:
        engine.preview("plugin.disable", turn_off())
    assert str(refused.value) == OUTSIDE


def test_a_codex_home_outside_home_stays_writable(tmp_path):
    home, moved = tmp_path / "home", tmp_path / "codex-home"
    home.mkdir()
    moved.mkdir()
    client = CodexAdapter(home, read_version=lambda: "0.159.2", codex_home=moved).detect()
    assert client.config_roots == (str(moved),)
    assert real(moved) in writable_roots(home, Inventory(clients=[client]))


def test_the_page_refuses_a_change_outside_with_the_sentence(tmp_path, monkeypatch):
    home = make_home(tmp_path, "claude_code/2.1.283")
    data_dir(home).mkdir(parents=True, exist_ok=True)
    (data_dir(home) / "gateway.json").write_text('{"servers": {"files": {"command": "npx"}}}')
    monkeypatch.setattr(page_app, "writable_roots", lambda home, inventory: [tmp_path / "nowhere"])
    app = page_app.create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        body = {"action": "gateway.rule", "params": {"server": "files", "state": "off"}}
        answer = page.post("/api/changes/preview", json=body, headers=POST)
    assert answer.status_code == 422 and answer.json() == {"detail": OUTSIDE}
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_write_boundary.py -v`
Expected: FAIL, `ImportError: cannot import name 'OUTSIDE'`.

- [ ] **Step 3: Implement.** "Inside" is `path == root or root in path.parents` on real paths. The
check runs first in `preview`, right after the "Nothing to change." check.

- [ ] **Step 4: Run the tests, then the whole suite**

Run: `uv run pytest tests/unit/test_write_boundary.py -v` → PASS.
Run: `uv run pytest -q` → PASS. If an existing API test now gets the sentence, its sandbox writes
into a folder no client knows: make the project known in that test; never widen the roots.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/changes/engine.py src/kitden/clients/codex.py src/kitden/web/app.py tests/unit/test_write_boundary.py
git commit -m "Changes: write only in the home folder and known projects"
```

---

### Task 4: The demo's stand-ins (spec 1.2)

**Files:**
- Create: `src/kitden/demo/runner.py` (`DemoRunner`), `src/kitden/demo/keychain.py`
  (`DemoKeychain`)
- Modify: `src/kitden/demo/__init__.py` (`NOT_IN_DEMO`, `CANNED_TOOLS`, `canned_refresh`,
  `no_sign_in`, and the two classes)
- Test: `tests/unit/test_demo_stand_ins.py`

**Interfaces:**
- Consumes: `build_demo_home`, `keychain_file` (Task 1); `CommandResult`
  (`kitden.changes.client_cli`); `json_splice` and `toml_edit` `set_value` / `delete_value`;
  `save_tools`, `load_settings`, `load_tools` (`kitden.local_gateway.settings`).
- Produces:
  - `NOT_IN_DEMO = "Not part of the demo."`
  - `DemoRunner(home: Path)`, called as the engine's `Runner`:
    `(command: list[str], cwd: str | None) -> CommandResult`. It answers `CommandResult(0, "")`
    after writing only the entry the step checks, format kept:
    - `claude mcp add-json -s user <name> <json>` → `~/.claude.json` `mcpServers.<name>`;
    - `claude mcp remove -s <scope> <name>` → `user`: `~/.claude.json` `mcpServers.<name>`;
      `local`: `~/.claude.json` `projects.<cwd>.mcpServers.<name>`; `project`:
      `<cwd>/.mcp.json` `mcpServers.<name>`;
    - `claude plugin install|uninstall|enable|disable <id> -s <scope> …` → `enabledPlugins.<id>`
      in `~/.claude/settings.json` (`user`), `<cwd>/.claude/settings.json` (`project`) or
      `<cwd>/.claude/settings.local.json` (`local`): install and enable write `true`, disable
      `false`, uninstall removes the key;
    - `codex plugin add <id> --json` → `~/.codex/config.toml` `plugins.<id>.enabled = true`;
      `codex plugin remove <id>` → removes `plugins.<id>`.

    A file that is not there yet starts as `{}` (JSON) or empty (TOML), its folder made. Any
    other command (both clients' `plugin marketplace add|remove`, any other program), and any
    `cwd` whose real path is not inside the home folder, answers `CommandResult(1, NOT_IN_DEMO)`
    and writes nothing.
  - `DemoKeychain(path: Path)`, called as `keychain.Runner`:
    `(args: list[str], stdin: str | None = None) -> tuple[int, str]`. The part of `security` that
    `src/kitden/local_gateway/keychain.py` uses, with the rules of
    `tests/fixtures/fake_security.py` (`-i` lines of `add-generic-password -U -s S -a "A" -X HEX`;
    `find-generic-password -w`; `delete-generic-password`; a missing item exits 44). Items are a
    JSON object `{"<service> <account>": value}` in `path`, written atomically with mode 600.
  - `CANNED_TOOLS: tuple[dict, ...]`: `search` (`readOnlyHint true`: reads), `create_item` (no
    hints: may write by its name), `summarize` (no hints: unknown), each with a one-line
    description.
  - `async canned_refresh(home: Path, names: Iterable[str] | None = None) -> dict[str, str |
    None]`: the answer shape of `refresh_tools`. Each held server asked (all when `names` is None)
    maps to None; one without a cached list gets `list(CANNED_TOOLS)` through `save_tools`; a
    cached list stays. Names the gateway does not hold are left out. Starts nothing.
  - `no_sign_in(url: str, headers: dict) -> bool`: False (the sample's remote servers send a
    header and need no sign-in).

Builder call: the runner covers the Claude Code and Codex commands Kitden's own changes use, so
Add, Add missing, plugin switches, Remove and the gateway move all work in the demo; only the
marketplace commands are refused (and their preview is refused before, Task 5).
Builder call: `DemoKeychain` repeats the rules of `tests/fixtures/fake_security.py` in the package
instead of importing it, because the spec keeps `tests/fixtures/` as it is.

- [ ] **Step 1: Write the failing tests**

```python
import asyncio
import json
import stat
import tomllib

import pytest

from kitden.changes.client_cli import CommandResult
from kitden.demo import (
    CANNED_TOOLS, NOT_IN_DEMO, DemoKeychain, DemoRunner, build_demo_home, canned_refresh,
    keychain_file,
)
from kitden.gateways import data_dir
from kitden.local_gateway import keychain
from kitden.local_gateway.settings import load_tools


def test_the_runner_adds_and_removes_a_claude_code_server(tmp_path):
    home = build_demo_home(tmp_path, "small")
    before = (home / ".claude.json").read_bytes()
    run = DemoRunner(home)
    entry = {"type": "http", "url": "https://notes.example.test/mcp"}
    add = ["claude", "mcp", "add-json", "-s", "user", "notes", json.dumps(entry)]
    assert run(add, None) == CommandResult(0, "")
    assert json.loads((home / ".claude.json").read_text())["mcpServers"]["notes"] == entry
    assert run(["claude", "mcp", "remove", "-s", "user", "notes"], None).returncode == 0
    assert (home / ".claude.json").read_bytes() == before


def test_the_runner_removes_a_local_and_a_project_server(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    website, atlas = str(home / "work/website"), str(home / "work/atlas")
    run = DemoRunner(home)
    assert run(["claude", "mcp", "remove", "-s", "local", "local-db"], website).returncode == 0
    state = json.loads((home / ".claude.json").read_text())
    assert "local-db" not in state["projects"][website]["mcpServers"]
    assert run(["claude", "mcp", "remove", "-s", "project", "docs"], atlas).returncode == 0
    assert "docs" not in json.loads((home / "work/atlas/.mcp.json").read_text())["mcpServers"]


def test_the_runner_sets_plugins_in_the_scope_it_is_given(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    atlas, run = str(home / "work/atlas"), DemoRunner(home)
    plugin = "test-helper@demo-market"
    run(["claude", "plugin", "install", plugin, "-s", "project", "--json"], atlas)
    project = json.loads((home / "work/atlas/.claude/settings.json").read_text())
    assert project["enabledPlugins"][plugin] is True
    run(["claude", "plugin", "uninstall", plugin, "-s", "project", "--json"], atlas)
    project = json.loads((home / "work/atlas/.claude/settings.json").read_text())
    assert plugin not in project.get("enabledPlugins", {})
    run(["claude", "plugin", "disable", "superpowers@demo-market", "-s", "user", "--json"], None)
    user = json.loads((home / ".claude/settings.json").read_text())
    assert user["enabledPlugins"]["superpowers@demo-market"] is False
    run(["codex", "plugin", "add", "db-tools@demo-market", "--json"], None)
    config = tomllib.loads((home / ".codex/config.toml").read_text())
    assert config["plugins"]["db-tools@demo-market"]["enabled"] is True
    run(["codex", "plugin", "remove", "db-tools@demo-market"], None)
    config = tomllib.loads((home / ".codex/config.toml").read_text())
    assert "db-tools@demo-market" not in config["plugins"]


@pytest.mark.parametrize(
    "command",
    [
        ["claude", "plugin", "marketplace", "add", "team/market"],
        ["codex", "plugin", "marketplace", "add", "team/market", "--json"],
        ["cursor", "--version"],
        ["security", "find-generic-password"],
    ],
)
def test_the_runner_refuses_everything_else(tmp_path, command):
    home = build_demo_home(tmp_path, "small")
    before = {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}
    assert DemoRunner(home)(command, None) == CommandResult(1, NOT_IN_DEMO)
    assert {p: p.read_bytes() for p in home.rglob("*") if p.is_file()} == before


def test_the_runner_refuses_a_folder_outside_the_sample(tmp_path):
    home = build_demo_home(tmp_path, "small")
    command = ["claude", "plugin", "install", "x@y", "-s", "project", "--json"]
    assert DemoRunner(home)(command, str(tmp_path)) == CommandResult(1, NOT_IN_DEMO)


def test_the_stand_in_keychain_keeps_values_in_its_file(tmp_path):
    path = tmp_path / "keychain.json"
    run = DemoKeychain(path)
    ref = keychain.store("files", "FILES_TOKEN", "DEMO_SECRET_X", run=run)
    assert ref == {"keychain": "files/FILES_TOKEN"}
    assert keychain.read(ref, run=run) == "DEMO_SECRET_X"
    assert json.loads(path.read_text()) == {"kitden files/FILES_TOKEN": "DEMO_SECRET_X"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    keychain.delete(ref, run=run)
    assert keychain.read(ref, run=run) is None


def test_the_stand_in_reads_the_sample_reference(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    ref = {"keychain": "tracker/Authorization"}
    assert keychain.read(ref, run=DemoKeychain(keychain_file(home))) == "Bearer DEMO_SECRET_TRACKER"


def test_a_canned_refresh_fills_only_servers_without_tools(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    path = data_dir(home) / "gateway.json"
    settings = json.loads(path.read_text())
    settings["servers"]["notes"] = {"command": "npx", "args": ["notes-mcp"]}
    path.write_text(json.dumps(settings))
    before = load_tools(home)
    assert asyncio.run(canned_refresh(home)) == {"files": None, "tracker": None, "notes": None}
    tools = load_tools(home)
    assert [t["name"] for t in tools["notes"]] == [t["name"] for t in CANNED_TOOLS]
    assert tools["files"] == before["files"]
    assert asyncio.run(canned_refresh(home, ["not-held"])) == {}
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_demo_stand_ins.py -v`
Expected: FAIL, `ImportError: cannot import name 'CANNED_TOOLS'`.

- [ ] **Step 3: Implement** the runner (parse the command words; pick the file and the key; edit
with `json_splice` or `toml_edit`; `write_atomic`), the Keychain stand-in and the three helpers.
The runner's docstring says it stands in for the client commands in `kitden demo` only and names
the commands it knows.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/unit/test_demo_stand_ins.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/demo/__init__.py src/kitden/demo/runner.py src/kitden/demo/keychain.py tests/unit/test_demo_stand_ins.py
git commit -m "Demo: stand-ins for client commands, the Keychain and tool lists"
```

---

### Task 5: Demo mode in the page server, and `/api/about` (spec 1.2)

**Files:**
- Modify: `src/kitden/web/app.py` (`create_app(..., demo=False)`, the `/api/about` route,
  `WaitForFirstScan`)
- Modify: `src/kitden/changes/engine.py` (`Engine(..., keychain_run=)`)
- Modify: `src/kitden/changes/actions.py` (`local_move_steps`, `_server_step`, `put_back_steps`)
- Test: `tests/unit/test_demo_mode.py`

**Interfaces:**
- Consumes: Task 1 (`build_demo_home`, `demo_build`, `demo_adapters`, `demo_command`,
  `keychain_file`, `VERSIONS`); Task 3 (`Engine(..., roots=)`); Task 4 (`DemoRunner`,
  `DemoKeychain`, `CANNED_TOOLS`, `canned_refresh`, `no_sign_in`, `NOT_IN_DEMO`).
- Produces:
  - `create_app(build, token, port, ..., version_refresh=None, demo: bool = False) -> Starlette`.
    With `demo`: `home` None raises `ValueError("Demo mode needs the sample's home folder.")`; the
    changes use `demo_adapters(home)`; the engine gets `run or DemoRunner(home)`,
    `keychain_run=DemoKeychain(keychain_file(home))` and no gateway clients; the setup command is
    `setup_command or (lambda: demo_command(home))`; no version read runs (the real
    `read_versions` default applies only when not a demo); a tool refresh calls `canned_refresh`;
    `_read_tools` answers `list(CANNED_TOOLS)`; a move passes `sign_in=no_sign_in`; a preview of
    `marketplace.add` and `POST /api/gateways` answer 422 `{"detail": NOT_IN_DEMO}`. `kitden.demo`
    is imported inside `create_app` only when `demo` is true.
  - `GET /api/about` → `{"version": kitden.__version__, "demo": bool}`; `WaitForFirstScan` lets
    it through like `/api/progress`.
  - `Engine.__init__(..., *, roots=None, keychain_run: keychain.Runner | None = None)`; every
    Keychain read, store and delete passes `run=self.keychain_run or keychain.run_security`.
  - `local_move_steps(adapters, items, home, known_projects, command, *, added_clients,
    sign_in: Callable[[str, dict], bool] | None = None, keychain_run: Runner | None = None)`;
    `_server_step(home, name, server, old, keychain_run=None)`;
    `put_back_steps(adapters, home, server, clients, keychain_run: Runner | None = None)`. None
    means `needs_sign_in` and `run_security`, looked up when called, so
    `tests/unit/test_after.py`, which patches `kitden.changes.actions.needs_sign_in`, keeps
    working. `create_app` passes the demo stand-ins and nothing otherwise.

Builder call: every refusal of something that would go online in the demo uses the one sentence
"Not part of the demo." (a marketplace link or folder, registering a gateway).
Builder call: the Keychain and sign-in seams are parameters (`keychain_run`, `sign_in`), not a
module-wide switch, so one test's demo app never changes another test's Keychain.
Builder call: `kitden.demo` is imported inside `create_app` only for a demo, so a normal start
loads nothing more.
Builder call: the refresh picks `canned_refresh` or `refresh_tools` when the pass runs, so tests
that patch `kitden.web.app.refresh_tools` keep working.

- [ ] **Step 1: Write the failing tests**

```python
import json
import threading
import time
from contextlib import contextmanager

import pytest
from starlette.testclient import TestClient

import kitden
from kitden.changes.actions import KITDEN_GATEWAY
from kitden.clients import version_cache
from kitden.demo import (
    CANNED_TOOLS, NOT_IN_DEMO, VERSIONS, build_demo_home, demo_build, keychain_file,
)
from kitden.gateways import data_dir
from kitden.local_gateway.settings import load_settings
from kitden.views import inventory as inventory_module
from kitden.views.inventory import Inventory, build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}


@contextmanager
def demo_page(root, size="medium"):
    home = build_demo_home(root, size)
    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        page.home = home
        yield page


def until(ready, seconds=5.0):
    end = time.monotonic() + seconds
    while not ready():
        assert time.monotonic() < end, "gave up waiting"
        time.sleep(0.05)


def preview(page, action, targets, params):
    body = {"action": action, "targets": targets, "params": params}
    answer = page.post("/api/changes/preview", json=body, headers=POST)
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_about_says_the_version_and_whether_it_is_a_demo(tmp_path):
    with demo_page(tmp_path / "demo") as page:
        assert page.get("/api/about").json() == {"version": kitden.__version__, "demo": True}
    home = make_home(tmp_path, "claude_code/2.1.283")
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN) as page:
        page.get("/?token=tok")
        assert page.get("/api/about").json() == {"version": kitden.__version__, "demo": False}


def test_about_answers_before_the_first_scan(tmp_path):
    gate = threading.Event()

    def slow(**options):
        gate.wait(10)
        return Inventory()

    app = create_app(slow, token="tok", port=47800, first_scan_later=True)
    with TestClient(app, base_url=ORIGIN) as page:
        page.get("/?token=tok")
        assert page.get("/api/about").json()["demo"] is False
        gate.set()


def test_a_demo_needs_the_sample_home():
    with pytest.raises(ValueError, match="Demo mode needs the sample's home folder."):
        create_app(lambda: Inventory(), token="tok", port=47800, demo=True)


def test_the_demo_shows_the_sample_versions_and_reads_none(tmp_path, monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("the demo read a version on this computer")

    monkeypatch.setattr(version_cache, "refresh_versions", never)
    monkeypatch.setattr(version_cache, "cached_version", never)
    with demo_page(tmp_path) as page:
        assert {c["id"]: c["version"] for c in page.get("/api/clients").json()} == VERSIONS


def test_the_demo_ignores_codex_home(tmp_path, monkeypatch):
    real = tmp_path / "real-codex"
    real.mkdir()
    (real / "config.toml").write_text('[mcp_servers.from-real-codex]\nurl = "https://r.test/mcp"\n')
    monkeypatch.setenv("CODEX_HOME", str(real))
    with demo_page(tmp_path / "demo") as page:
        assert "from-real-codex" not in page.get("/api/items").text


def test_the_demo_reads_no_app_folder(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(inventory_module, "app_url", lambda client, roots: seen.append(roots))
    with demo_page(tmp_path) as page:
        page.get("/api/clients")
    assert seen and all(list(roots) == [] for roots in seen)


def test_a_marketplace_and_a_registered_gateway_are_not_part_of_the_demo(tmp_path):
    with demo_page(tmp_path) as page:
        body = {"action": "marketplace.add", "targets": [{"client": "claude_code"}],
                "params": {"source": "team/market"}}
        market = page.post("/api/changes/preview", json=body, headers=POST)
        gateway = page.post(
            "/api/gateways", json={"url": "http://127.0.0.1:12008/mcp", "auth": "none"}, headers=POST
        )
    for answer in (market, gateway):
        assert (answer.status_code, answer.json()) == (422, {"detail": NOT_IN_DEMO})


def test_moving_a_remote_server_in_uses_the_stand_ins(tmp_path):
    with demo_page(tmp_path) as page:
        home = page.home
        files = [home / ".claude.json", data_dir(home) / "gateway.json"]
        before = {p: p.read_bytes() for p in files}
        github = next(i for i in page.get("/api/items?kind=mcp_server").json()
                      if (i["client"], i["name"]) == ("claude_code", "github"))
        change = preview(page, "gateway.move", [{"item": github["id"]}],
                         {"gateway": KITDEN_GATEWAY})
        done = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert done["state"] == "verified"
        stored = json.loads(keychain_file(home).read_text())
        assert stored["kitden github/Authorization"].startswith("Bearer DEMO_SECRET_")
        held = load_settings(home)["servers"]["github"]
        assert held["headers"]["Authorization"] == {"keychain": "github/Authorization"}
        names = [t["name"] for t in CANNED_TOOLS]
        until(lambda: [t["name"] for t in
                       page.get("/api/gateway/tools?server=github").json()["tools"]] == names)
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
        assert "kitden github/Authorization" not in json.loads(keychain_file(home).read_text())
        assert {p: p.read_bytes() for p in files} == before


def test_put_back_reads_the_stand_in_keychain(tmp_path):
    with demo_page(tmp_path) as page:
        change = preview(page, "gateway.put_back", [{"client": "cursor"}], {"server": "tracker"})
    assert [s["client"] for s in change["steps"]] == ["cursor"]
    assert "DEMO_SECRET_" not in json.dumps(change)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_demo_mode.py -v`
Expected: FAIL, `TypeError: create_app() got an unexpected keyword argument 'demo'`.

- [ ] **Step 3: Implement** the engine and actions parameters, then the `create_app` branch and
the route.

- [ ] **Step 4: Run the new tests and the ones that touch moves, Keychain and refreshes**

Run: `uv run pytest tests/unit/test_demo_mode.py tests/unit/test_local_gateway_move.py tests/unit/test_keychain.py tests/unit/test_after.py tests/unit/test_local_gateway_views.py tests/unit/test_engine.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/app.py src/kitden/changes/engine.py src/kitden/changes/actions.py tests/unit/test_demo_mode.py
git commit -m "Demo mode in the page server"
```

---

### Task 6: `kitden demo`, with a quiet Demo flag (spec 1.2, Done)

**Files:**
- Modify: `src/kitden/cli.py` (`DEMO_PORT`, `_demo`, the `demo` subcommand, dispatched before
  `ensure_data_folder`)
- Modify: `src/kitden/web/static/js/parts.js` (`demoTag`), `src/kitden/web/static/js/app.js`
  (read `/api/about` once in `start()`, append the flag to `.brand`)
- Modify: `docs/design.md` (Components: one paragraph on the flag)
- Modify: `scripts/measure-start.py` (`measure_demo`, `DEMO_BUDGET`, a third line)
- Test: `tests/unit/test_cli.py`, `tests/frontend/parts.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `build_demo_home`, `demo_build`, `SIZES`, `VERSIONS` (Task 1); `create_app(...,
  demo=True)`, `/api/about` (Task 5).
- Produces:
  - `kitden demo [--size small|medium|large] [--no-browser]`, size `medium` by default. It builds
    the sample in `tempfile.TemporaryDirectory(prefix="kitden-demo-")`, takes
    `pick_port(DEMO_PORT)` (none: the "No free port" message, exit 2), creates the app with
    `demo_build(home)`, watch folders `[home / name for name in WATCHED]`, `flat_folders=[home]`,
    `first_scan_later=True`, `quick_first=True`, `demo=True`, prints
    `Kitden demo is running on a sample setup. Open: <url>` and
    `Press Ctrl+C to stop. The sample folder is deleted then.`, opens the browser once started
    (unless `--no-browser`), and deletes the folder when the server stops, also after an error.
    No page lock, no page record, no data-folder copy.
  - `DEMO_PORT = 47900` (cli.py).
  - `demoTag(about) -> HTMLElement | null` (parts.js): for `about.demo`, a
    `span.flag.info` "Demo" (built with `el`) whose `title`, set with `setAttribute`, is "A sample
    setup in a temporary folder. Your own settings are not read or changed."; otherwise null.
  - `measure_demo(root: Path, size: str = "medium") -> float` (script): seconds from before
    `build_demo_home` to the first `/api/overview` answer with a `headline`, on uvicorn in a
    thread as `measure` does; `DEMO_BUDGET = 2.0`; printed as
    `demo (medium): 0.4 s (budget 2 s)`; a miss also gives exit code 1.

Builder call: `kitden demo` takes the medium size when none is given.
Builder call: the tag is the existing quiet `.flag.info` after the wordmark, with its words in the
hover text, not a banner.
Builder call: the "under two seconds" check is a third line of `scripts/measure-start.py`, as the
other start budgets are checked there, not in pytest.
Builder call: the demo's ports start at 47900, so its browser storage (theme, hidden columns)
never mixes with the real page's at 47800.
Builder call: `/api/about` is read once at start, not in `loadShared()`, so a reload asks nothing
more.

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_cli.py`:

```python
import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import kitden.cli as cli
import kitden.demo
from kitden.cli import main
from kitden.demo import VERSIONS


def _demo_run(monkeypatch, seen, server=None):
    real = kitden.demo.build_demo_home
    monkeypatch.setattr(
        kitden.demo, "build_demo_home",
        lambda root, size: seen.setdefault("home", real(root, size)),
    )
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: start)
    monkeypatch.setattr(cli, "run_server", server or (lambda app, host, port, **kw: None))


def test_demo_serves_the_sample_and_deletes_it_on_exit(monkeypatch, capsys):
    seen = {}

    def server(app, host, port, **kw):
        assert seen["home"].is_dir() and port == cli.DEMO_PORT
        link = re.search(r"http://127\.0\.0\.1:\d+/\?token=\S+", capsys.readouterr().out)
        with TestClient(app, base_url=f"http://127.0.0.1:{port}") as page:
            page.get(link.group(0))
            assert page.get("/api/about").json()["demo"] is True
            assert {c["id"]: c["version"] for c in page.get("/api/clients").json()} == VERSIONS

    _demo_run(monkeypatch, seen, server)
    assert main(["demo", "--no-browser"]) == 0
    assert not seen["home"].parent.exists()


def test_demo_deletes_its_folder_when_the_server_fails(monkeypatch):
    seen = {}

    def server(app, host, port, **kw):
        raise RuntimeError("the server broke")

    _demo_run(monkeypatch, seen, server)
    with pytest.raises(RuntimeError):
        main(["demo", "--no-browser", "--size", "small"])
    assert not seen["home"].parent.exists()


def test_demo_never_touches_the_real_home(monkeypatch):
    real = Path.home()  # the fake home conftest gives every test
    old = real / "Library/Application Support/agentsetup/settings.json"
    old.parent.mkdir(parents=True)
    old.write_text("{}")
    before = sorted(p.relative_to(real) for p in real.rglob("*"))
    _demo_run(monkeypatch, {})
    assert main(["demo", "--no-browser", "--size", "small"]) == 0
    assert sorted(p.relative_to(real) for p in real.rglob("*")) == before


def test_demo_opens_the_browser_once_started(monkeypatch):
    opened = []
    _demo_run(monkeypatch, {}, lambda app, host, port, on_started, **kw: on_started())
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    main(["demo", "--size", "small"])
    assert len(opened) == 1 and opened[0].startswith("http://127.0.0.1:47900/?token=")


def test_demo_takes_only_the_three_sizes():
    with pytest.raises(SystemExit) as stopped:
        main(["demo", "--size", "huge"])
    assert stopped.value.code == 2
```

In `tests/frontend/parts.test.mjs`, import `demoTag` with the others, and:

```js
test('a demo shows a quiet Demo flag; a real page shows none', () => {
  const tag = demoTag({ version: '0.2.0', demo: true });
  assert.equal(tag.textContent, 'Demo');
  assert.equal(tag.className, 'flag info');
  assert.equal(tag.attributes.title, 'A sample setup in a temporary folder. Your own settings are not read or changed.');
  assert.equal(demoTag({ version: '0.2.0', demo: false }), null);
  assert.equal(demoTag(null), null);
});
```

In `tests/unit/test_page_words.py`:

```python
def test_a_demo_says_so_quietly_in_the_rail():
    assert 'getJson("/api/about")' in script("app.js")
    assert '"Demo"' in script("parts.js")
    assert "Demo" not in INDEX  # only a demo's answer adds it
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_cli.py tests/unit/test_page_words.py -v` and
`node --test tests/frontend/parts.test.mjs`
Expected: FAIL (`invalid choice: 'demo'`; `demoTag` is not exported).

- [ ] **Step 3: Implement** the command, the flag and `measure_demo`. In `main`, return
`_demo(args)` right after `--version` is handled, before `ensure_data_folder`. Add `demo` to the
subparsers that take `--no-browser`. In `docs/design.md` Components, after the search box
sentence: "In `kitden demo` a quiet "Demo" flag (`.flag.info`) follows the wordmark; its hover
text says the setup is a sample in a temporary folder. The page reads `/api/about` once to
know."

- [ ] **Step 4: Run the tests and the measurement**

Run: `uv run pytest tests/unit/test_cli.py tests/unit/test_page_words.py -v` and
`node --test tests/frontend/*.test.mjs` → PASS.
Run: `uv run python scripts/measure-start.py` → exit 0, the third line under 2 s (spec 1 Done:
"`kitden demo` opens in under two seconds on `medium`"). Note the number for Task 8.
Run by hand once: `uv run kitden demo --size medium`; the browser opens on the sample with
"Demo" after the wordmark; Ctrl+C; the printed folder is gone.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/cli.py src/kitden/web/static/js/parts.js src/kitden/web/static/js/app.js docs/design.md scripts/measure-start.py tests/unit/test_cli.py tests/frontend/parts.test.mjs tests/unit/test_page_words.py
git commit -m "kitden demo: the page on a sample setup, with a quiet Demo flag"
```

---

### Task 7: The demo starts nothing and shows no secret (spec 1 Done)

**Files:**
- Create: `tests/security/test_demo_safety.py`
- Modify: `tests/security/test_no_secrets.py` (a sweep for each size)

**Interfaces:**
- Consumes: everything above; `KINDS` (`kitden.views.library`); `create_server`
  (`kitden.mcp_server`).
- Produces: two guards local to `test_demo_safety.py`: `no_programs` (every `subprocess.Popen`
  raises and is recorded) and `no_connections` (every `socket.socket.connect`, `connect_ex`,
  `socket.create_connection` and `socket.getaddrinfo` raises and is recorded, `localhost`
  included).

Builder call: the sweep reads each Library tab for All projects and for the first project only,
and explains only items with a secret and the instruction files, so the `large` run stays short.

- [ ] **Step 1: Write the tests**

`tests/security/test_demo_safety.py` (with `demo_page`, `preview` and `until` as in Task 5's test
file, imported from `tests.unit.test_demo_mode`):

```python
@pytest.fixture
def no_programs(monkeypatch):
    started = []

    class Refused(subprocess.Popen):
        def __init__(self, args, *rest, **options):
            started.append(args)
            raise AssertionError(f"the demo started a program: {args}")

    monkeypatch.setattr(subprocess, "Popen", Refused)
    return started


@pytest.fixture
def no_connections(monkeypatch):
    tried = []

    def refuse(*args, **kwargs):
        tried.append(args)
        raise OSError("the demo stays offline")

    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    return tried


def test_an_add_a_tool_switch_and_undo_run_no_program_and_go_nowhere(
    tmp_path, no_programs, no_connections
):
    with demo_page(tmp_path) as page:
        home = page.home
        files = [home / ".claude.json", data_dir(home) / "gateway.json"]
        before = {p: p.read_bytes() for p in files}
        tools = next(i for i in page.get("/api/items?kind=mcp_server").json()
                     if (i["client"], i["name"]) == ("cursor", "browser-tools"))
        add = preview(page, "mcp.add", [{"client": "claude_code"}], {"item": tools["id"]})
        assert page.post(f"/api/changes/{add['id']}/apply", headers=POST).json()["state"] == "verified"
        assert "browser-tools" in json.loads((home / ".claude.json").read_text())["mcpServers"]
        atlas = next(p["id"] for p in page.get("/api/projects").json()
                     if p["path"] == str(home / "work/atlas"))
        rule = preview(page, "gateway.rule", [],
                       {"server": "files", "tool": "read_file", "state": "off", "project": atlas})
        assert page.post(f"/api/changes/{rule['id']}/apply", headers=POST).json()["state"] == "verified"
        assert page.post("/api/rescan", headers=POST).status_code == 200
        assert page.post("/api/gateway/tools/refresh", headers=POST).status_code == 202
        for change in (rule, add):
            undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
            assert undone["state"] == "undone"
        assert {p: p.read_bytes() for p in files} == before
    assert no_programs == [] and no_connections == []


def test_moving_servers_in_and_strict_mode_start_nothing(tmp_path, no_programs, no_connections):
    with demo_page(tmp_path) as page:
        analytics = next(i for i in page.get("/api/items?kind=mcp_server").json()
                         if (i["client"], i["name"]) == ("codex", "analytics"))
        move = preview(page, "gateway.move", [{"item": analytics["id"]}],
                       {"gateway": KITDEN_GATEWAY})
        strict = preview(page, "gateway.strict", [], {"server": "files", "state": "on"})
        for change in (move, strict):
            done = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
            assert done["state"] == "verified"
        until(lambda: page.get("/api/gateway/tools?server=analytics").json()["tools"])
        for change in (strict, move):
            page.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert no_programs == [] and no_connections == []
```

In `tests/security/test_no_secrets.py`, add `_demo_outputs(home) -> list[str]` and:

```python
@pytest.mark.anyio
@pytest.mark.parametrize("size", SIZES)
async def test_no_demo_secret_in_any_output_of_a_sample(tmp_path, size, network_attempts):
    home = build_demo_home(tmp_path, size)
    written = "".join(p.read_text(errors="ignore") for p in tmp_path.rglob("*")
                      if p.is_file() and not p.is_symlink())
    assert written.count(DEMO_SECRET) >= {"small": 2, "medium": 6, "large": 6}[size]
    outputs = _demo_outputs(home)
    store = data_dir(home)
    outputs.append((store / "changes.log").read_text())
    outputs += [p.read_text() for p in store.glob("changes/*/manifest.json")]
    for record in store.glob("changes/*/change.json"):
        outputs.append(json.dumps([s["command"] for s in json.loads(record.read_text())["steps"]]))
    outputs += await _mcp_outputs_of(demo_build(home), home)
    assert [text for text in outputs if DEMO_SECRET in text] == []
    assert network_attempts == []
```

`_demo_outputs(home)` runs the demo app (`demo=True`) and collects the text of:
`/api/clients`, `/api/items`, `/api/projects`, `/api/problems`, `/api/changes`, `/api/gateways`,
`/api/about`; for All projects and each project: `/api/overview`, `/api/map`, `/api/gateway-view`,
`/api/findings`; `/api/library?kind=<k>` for each of `KINDS`, for All projects and the first
project; `/api/explain` for each item with `secret_present` and each instruction file;
`/api/gateway/tools?server=<s>` for each held server; preview, apply and undo of
`mcp.remove_direct` for each user-level item with `secret_present` that offers it; the preview of
`gateway.keychain` for `files` (medium and large). `_mcp_outputs_of(build, home)` is today's
`_mcp_outputs` with the build passed in and `explain_item` asked for the items with a secret.

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/security -v`
Expected: PASS. A failure is a finding: a leaked `DEMO_SECRET_` or a guard that tripped points at
a path the demo did not cover. Fix it in the code that owns it (Tasks 1, 4 or 5), never by
loosening a guard or skipping an output.

- [ ] **Step 3: Commit**

```bash
git add tests/security/test_demo_safety.py tests/security/test_no_secrets.py
git commit -m "Tests: the demo starts nothing, goes nowhere and shows no secret"
```

---

### Task 8: Docs and roadmap for Part 1

**Files:**
- Modify: `README.md` (Install; How it works, step 2; "Check every change before it is written")
- Modify: `docs/development.md` (Develop, the folder table, Commands, Speed)
- Test: `tests/unit/test_docs_words.py`
- `ROADMAP.md`: only by the rule below. (`docs/design.md` changed in Task 6.)

**Interfaces:**
- Consumes: the numbers measured in Tasks 2 and 6.

- [ ] **Step 1: Write the failing test**

```python
def test_docs_name_the_demo_and_the_write_boundary():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert "uvx kitden demo" in readme
    assert "Kitden writes only in your home folder and your known projects." in readme
    development = (ROOT / "docs/development.md").read_text()
    assert "kitden demo" in development and "build_demo_home" in development
```

- [ ] **Step 2: Run it to see it fail**: `uv run pytest tests/unit/test_docs_words.py -v`.

- [ ] **Step 3: Write the docs.**
  - README Install, after `uvx kitden`: "To try it first on a sample setup, with nothing on your
    computer read or changed: `uvx kitden demo`." How it works, step 2: the measurement is on the
    large sample setup (`kitden demo --size large`), not "40 servers, 10 plugins and 20 skills".
    "Check every change before it is written": add "Kitden writes only in your home folder and
    your known projects."
  - `docs/development.md`: the folder table gains `src/kitden/demo/` ("Sample setups for
    `kitden demo` and the tests, and the demo's stand-ins"); Develop gains "Tests can build a
    sample home with `kitden.demo.build_demo_home(root, size)`."; Commands gains
    `kitden demo [--size small|medium|large]` ("Opens the page on a sample setup in a temporary
    folder; it runs no client, starts no server, uses no Keychain and stays offline; the folder
    is deleted when it stops"); Speed describes the large sample and the third line, with the
    numbers from Tasks 2 and 6 and the date (`checked YYYY-MM-DD`). No real-client hand check is
    added: the demo uses none.
- [ ] **Step 4: Run all checks**: `uv run pytest -q && uv run ruff check . && uv run ruff format
  --check src tests && node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Roadmap.** Run `git status --short ROADMAP.md`. While it shows `M` from the
  owner's edit, do not touch it; put these lines in the part's report. Once the owner has
  committed it, add them under "### Not released yet" and replace the "Measured start" bullet's
  numbers:
  - **Try it on a sample:** `kitden demo` opens the page on a sample setup (small, medium or
    large) in a temporary folder. It runs no client, starts no server, uses no Keychain and stays
    offline; the folder is deleted when it stops.
  - **Writes stay in place:** Kitden refuses a change outside your home folder and your known
    projects.
  - **Measured start:** on the large sample setup, first usable N s and complete N s; the demo
    opens in N s.
- [ ] **Step 6: Commit**

```bash
git add README.md docs/development.md tests/unit/test_docs_words.py
git commit -m "Docs: kitden demo and the write boundary"
```

(Add `ROADMAP.md` to this commit only when Step 5 edited it.)

---

### Task 9: The first walkthrough script (spec 1.4)

**Files:**
- Create: `docs/research/walkthrough-script-1.md`
- Test: `tests/unit/test_docs_words.py`

**Interfaces:**
- Consumes: the medium sample's names (Task 1).
- Produces: the script the owner runs on today's page (master plan, Walkthroughs). The controller
  writes the results to `docs/research/walkthrough-<date>.md` afterwards; this task does not.

- [ ] **Step 1: Write the failing test**

```python
def test_walkthrough_script_one_has_the_seven_tasks_and_a_results_table():
    text = (ROOT / "docs/research/walkthrough-script-1.md").read_text()
    assert "kitden demo --size medium" in text
    assert all(f"## Task {n}:" in text for n in range(1, 8)) and "## Task 8" not in text
    assert "| Task | Done | Wrong turns | Time | What was confusing |" in text
    assert '"Loads" or "Available"' in text
    assert '"On" and "Off" or "Allowed" and "Blocked"' in text
```

- [ ] **Step 2: Run it to see it fail**: `uv run pytest tests/unit/test_docs_words.py -v`.
- [ ] **Step 3: Write the script**, one page, simple English:
  - Before: about 15 minutes; run `uvx kitden demo --size medium` (from the repository:
    `uv run kitden demo --size medium`); a normal desktop window; nobody explains the page first;
    the observer only writes things down.
  - Seven sections `## Task N: <goal>`, each with "Start from" and "Done when" (for the observer,
    from concept §12):
    1. Explain why Codex and Cursor both have the skill `code-review`. Done when: names the one
       shared folder and does not say two copies.
    2. Pick Atlas and find what differs between the clients there. Done when: finds a real
       difference (`api-style` missing in Claude Code, or `docs` overridden in Atlas) and tells it
       from what comes from all projects.
    3. Add the missing skill to Atlas only. Done when: says the scope (this project, Atlas) before
       Apply.
    4. Look at the two `docs` servers of Claude Code and Codex. Done when: notices they come from
       different sources and does not treat them as one.
    5. Turn off the tool `read_file` of `files` for Atlas. Done when: says it applies to Atlas and
       its folder `web`, and to new calls, not to a call already running.
    6. Explain why Cursor still reaches `files` around the gateway. Done when: says Cursor has its
       own direct entry, so the gateway's switches do not apply to its calls.
    7. Undo the change from task 5. Done when: finds Undo and says what it puts back.
  - Words to settle, asked after the tasks: for a cell, "Loads" or "Available"? For a tool, "On"
    and "Off" or "Allowed" and "Blocked"?
  - The results table `| Task | Done | Wrong turns | Time | What was confusing |` with rows 1–7,
    and a line for any wrong belief about scope or protection.
- [ ] **Step 4: Run it to see it pass**, then all checks as in Task 8, Step 4.
- [ ] **Step 5: Commit**

```bash
git add docs/research/walkthrough-script-1.md tests/unit/test_docs_words.py
git commit -m "Docs: the first walkthrough script"
```

---

## Self-review

- **Spec coverage.** 1.1 sizes and fake secrets: Tasks 1, 2 (sweep: Task 7). 1.1 one generator:
  Task 2. 1.2 command, temporary folder, browser, deletion: Task 6; runner, no server, no
  Keychain, no network, sample versions, no `CODEX_HOME` or `/Applications`: Tasks 4, 5; Demo tag:
  Task 6; changes through the engine inside the demo folder: Tasks 3, 5, 7. 1.3: Task 3. 1.4
  script: Task 9. Done: under two seconds (Task 6 measurement), Popen and socket guard driving an
  Add, a tool switch and Undo (Task 7), sweep on three sizes (Task 7).
- **Not placed here.** 1.4's "all state words stay in one table" (`STATE_WORDS` and its Python
  twin) belongs to Part 2 by the master plan's table. The walkthrough's results file is the
  controller's, after the owner runs the script.
- **Sample contract for later parts.** Medium: the nine cases in Task 1's contract table, pinned
  by `test_the_medium_sample_contract` with plain `build_inventory(home)` under the conftest
  guards. Large: more than six direct MCP servers, more than six held servers, names longer than
  40 characters (`test_the_large_sample_has_hundreds_of_items_long_names_and_many_projects`).
- **Names.** `build_demo_home`, `SIZES`, `DEMO_SECRET_`, `create_app(..., demo)`, `/api/about`,
  `kitden demo`, `writable_roots` and the refusal match the master plan. `keychain_run` and
  `sign_in` are used with the same names in Tasks 5 and 7.
