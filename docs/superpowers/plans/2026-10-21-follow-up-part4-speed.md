# Part 4: Fast to open, and measured — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The first scan never waits for a client's version command, versions come from a disk cache and a background read, and a script reports the time to the first usable view and to complete data on a large sandbox setup.

**Architecture:** A new module `src/kitden/clients/version_cache.py` keeps `versions.json` in the data folder, keyed by the binary's path and modification time. The page's adapters read the cache instead of running a command; after the first scan, `State` refreshes stale entries in a thread and publishes a `versions` event. `kitden scan` keeps running the commands. A script under `scripts/` builds a sandbox home, starts the page and prints two numbers.

**Tech Stack:** Python 3.13, Starlette, uvicorn, httpx (dev dependency, for the script); plain ES modules; pytest; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-21-review-follow-up-design.md`, Part 4 (4.1 to 4.3). Master plan: `docs/superpowers/plans/2026-10-21-review-follow-up.md` (fixed names: `cached_version`, `refresh_versions`; review focus 4).

## Global Constraints

- Code, comments, UI text and docs in simple English (`AGENTS.md`).
- The version always comes from the binary Kitden would run (`version_command`), never from an app bundle; the Claude Desktop Code tab keeps its folder-name version (`extra_clients`).
- The cache file is found data: written directly, atomically, mode 600 in the 0700 data folder; a broken file reads as empty.
- `docs/design.md`: the start line and the "still reading" note stay; a redraw keeps focus.
- Tests on sandbox homes; no real client command runs in a test (`no_version` or a fake binary on PATH inside the sandbox).
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `node --test tests/frontend/*.test.mjs`. Commit subjects plain, no prefix.
- No new runtime dependency (httpx is already a dev dependency; the script runs with `uv run`).

## Decisions from the builder pass

Settled here so no task has to guess:

- A version command that fails or times out is **not** cached: the next start reads it again in
  the background. Only a successful read is written.
- "client versions" is a progress step of its own (`later`, between "Codex plugins" and
  "marketplaces"), so the start line can say "Still checking client versions…" and the Clients
  card says "Checking the version…" while it is open, never a false "version unknown". The pure
  words live in `parts.js` as `versionWords(version, progress) -> string` and are node-tested.
- Codex asks `codex plugin list` only once its version is known (`src/kitden/clients/codex.py:150`).
  On a cold cache the first scan skips it; the versions task then rescans and reopens the
  "Codex plugins" step (`Progress.reopen(*names)`), so the page tells the truth. The script warms
  the cache before its runs, so both numbers describe the common start.
- `kitden scan` calls `refresh_versions` first, then `build_inventory`; `kitden mcp`
  (`src/kitden/mcp_server.py:165`) reads the cache too and runs no command.
- The in-memory cache in `src/kitden/clients/base.py` (`_VERSION_CACHE`, `VERSION_CACHE_SECONDS`)
  goes; the disk cache is the one cache. The `no_version` fixture and the
  `monkeypatch.setattr(base, "read_command_version", …)` stubs across the tests become
  `version_cache.version_command → None`; Task 2 lists and removes them.
- A missed budget at Task 4 stops the part: the cause is reported to the owner, the budget is
  not changed (spec 4.2).

## Review Focus

1. The first scan with a version command that hangs: `build_inventory(home, cached_versions=True)` returns before the command would (Task 2 test `test_the_first_scan_runs_no_version_command`; the master's item 4).
2. A binary that moved or was updated: the cached version is not used; the refresh reads it again (Task 1 test `test_a_cache_entry_for_another_path_or_mtime_is_stale`).
3. A client that is not installed: no cache entry, no command, `status == not_found` as today (Task 2 test `test_a_missing_client_stays_not_found_with_the_cache`).
4. The refresh fails (command error or timeout): the page keeps "version unknown", nothing is retried in a loop, one plain line on stderr (Task 3 test `test_a_failed_refresh_keeps_unknown_and_says_so_once`).
5. The measurement script's slow source: the first usable answer arrives while `/api/progress` still lists "Codex plugins" as not done (Task 4, the script's own assertion).

---

### Task 1: The disk cache (4.1)

**Files:**
- Create: `src/kitden/clients/version_cache.py`
- Test: `tests/unit/test_version_cache.py` (new)

**Interfaces:**
- Produces: `VERSIONS_FILE = "versions.json"`; `load_versions(home: Path) -> dict[str, dict]` (`{client: {"path": str, "mtime_ns": int, "version": str | None}}`, `{}` when missing or broken); `cached_version(home: Path, client: str) -> str | None`: the cached version when `version_command(client)` names the same path and `os.stat(path).st_mtime_ns` equals the entry's, else `None`; `stale_clients(home: Path, clients: list[str]) -> list[str]`: the clients whose command exists and whose entry is missing or stale; `refresh_versions(home: Path, clients: list[str]) -> dict[str, str | None]`: runs each client's version command with `subprocess.run(..., timeout=20)` as `read_command_version` does today (reuse its parsing; move the command-running part into this module as `run_version_command(client) -> str | None` and let `read_command_version` call it), writes the file with `write_atomic` after chmod 0o700 on the folder, and returns `{client: version}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_cached_version_is_used_when_the_binary_is_unchanged(tmp_path, monkeypatch):
    binary = tmp_path / "bin/claude"; binary.parent.mkdir(); binary.write_text("#!/bin/sh\necho 2.1.300\n"); binary.chmod(0o755)
    monkeypatch.setattr("kitden.clients.version_cache.version_command", lambda c: [str(binary), "--version"] if c == "claude_code" else None)
    assert refresh_versions(tmp_path, ["claude_code"]) == {"claude_code": "2.1.300"}
    assert cached_version(tmp_path, "claude_code") == "2.1.300"
    assert stale_clients(tmp_path, ["claude_code", "codex"]) == []  # codex has no command: not stale


def test_a_cache_entry_for_another_path_or_mtime_is_stale(tmp_path, monkeypatch):
    # as above, then touch the binary with a new mtime (os.utime) → cached_version is None and stale_clients == ["claude_code"]
    # then point version_command at another path → None again


def test_a_broken_cache_reads_as_empty_and_is_private(tmp_path):
    (data_dir(tmp_path)).mkdir(parents=True); (data_dir(tmp_path) / VERSIONS_FILE).write_text("{")
    assert load_versions(tmp_path) == {} and cached_version(tmp_path, "codex") is None
    # after refresh_versions with a fake binary: oct(stat(file).st_mode)[-3:] == "600"
```

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_version_cache.py -v` → ImportError.
- [ ] **Step 3: Implement** the module; `read_command_version` in `src/kitden/clients/base.py:188-205` keeps its in-memory cache and calls `run_version_command`.
- [ ] **Step 4: Run**: `uv run pytest tests/unit/test_version_cache.py tests/unit/test_versions.py -v` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/clients/version_cache.py src/kitden/clients/base.py tests/unit/test_version_cache.py
git commit -m "Clients: a disk cache of version commands"
```

---

### Task 2: The scan reads the cache, never a command (4.1)

**Files:**
- Modify: `src/kitden/views/inventory.py:39-45` (`default_adapters(home, quick=False, on_slow_answer=None, cached_versions=False)`), `59-70` (`build_inventory(..., cached_versions: bool = False)`)
- Modify: `src/kitden/cli.py:124` (the page's `build_inventory(home, **options)` gets `cached_versions=True`; `_scan` does not)
- Test: `tests/unit/test_inventory.py`, `tests/unit/test_read_claude_code.py`

**Interfaces:**
- Produces: with `cached_versions=True` each adapter is built with `read_version=lambda: cached_version(home, adapter_id)`; the Desktop tab's `extra_clients()` is unchanged. `Client.version` is `None` and `version_supported` is `False` until the cache has it; `status` is `found` when the config root exists, as today.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_first_scan_runs_no_version_command(tmp_path, monkeypatch):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    def hang(client): time.sleep(5); return "9.9.9"
    monkeypatch.setattr("kitden.clients.base.read_command_version", hang)
    started = time.monotonic()
    inventory = build_inventory(home, cached_versions=True)
    assert time.monotonic() - started < 1
    assert {c.id: c.version for c in inventory.clients}["claude_code"] is None


def test_a_missing_client_stays_not_found_with_the_cache(tmp_path):
    inventory = build_inventory(make_home(tmp_path, "codex/0.159.2"), cached_versions=True)
    assert {c.id: str(c.status) for c in inventory.clients}["cursor"] == "not_found"


def test_the_desktop_tab_keeps_its_folder_version(tmp_path):
    # the claude_code fixture has Library/Application Support/Claude/claude-code/<version>; with cached_versions=True the Desktop client still has that version
```

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_inventory.py tests/unit/test_read_claude_code.py tests/unit/test_cli.py -v` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/views/inventory.py src/kitden/cli.py tests/unit/test_inventory.py tests/unit/test_read_claude_code.py
git commit -m "Start: the scan reads versions from the cache"
```

---

### Task 3: Versions arrive in the background (4.1)

**Files:**
- Modify: `src/kitden/web/app.py:248-345` (`State`: `refresh_versions_later()` after `_quick_first_scan` and after a plain first scan; a `versions` event), `376-470` (`create_app(..., version_refresh: Callable[[list[str]], dict[str, str | None]] | None = None)` so tests inject a fake)
- Modify: `src/kitden/web/static/js/app.js:204-224` (listen to `versions`: dispatch `kitden:versions`), `src/kitden/web/static/js/overview.js` (the Clients card re-reads `/api/clients` on `kitden:versions` and redraws itself only)
- Test: `tests/unit/test_events.py`, `tests/unit/test_api_read.py`, `tests/frontend/overview.test.mjs`

**Interfaces:**
- Produces: `State.refresh_versions_later()`: once, after the first scan, in a thread: `stale = stale_clients(home, [a.id for a in adapters])`; when non-empty, `refresh_versions(home, stale)`; when any version differs from the one the inventory holds, `await self.rescan()`; always `events.publish("versions")`. On an exception: one line `"Reading the clients' versions failed (<type>)."` on stderr, no retry. Page: `clientsCard` exported from `overview.js` as a pure `clientsWords(clients)` is not needed; the card listens to `kitden:versions` and redraws from `/api/clients`.

- [ ] **Step 1: Write the failing tests**

```python
def test_versions_come_after_the_first_scan_and_the_page_is_told(tmp_path):
    # create_app(... first_scan_later=True, quick_first=True, version_refresh=lambda clients: {"claude_code": "2.1.300"}) with a fake build;
    # open the event stream, wait for "versions"; GET /api/clients shows claude_code version "2.1.300"


def test_a_failed_refresh_keeps_unknown_and_says_so_once(tmp_path, capsys):
    # version_refresh raises OSError; after the first scan: /api/clients version None, stderr has
    # "Reading the clients' versions failed (OSError)." exactly once, and the "versions" event still came
```

Node: `tests/frontend/overview.test.mjs`: the page module listens for `kitden:versions` (assert the string is in `overview.js` via a words test instead, if the listener is not pure).

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_events.py tests/unit/test_api_read.py tests/unit/test_page_words.py -v` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/app.py src/kitden/web/static/js/app.js src/kitden/web/static/js/overview.js tests/unit tests/frontend
git commit -m "Start: versions in the background"
```

---

### Task 4: The measurement script (4.2, 4.3)

**Files:**
- Create: `scripts/measure-start.py`
- Create: `tests/unit/test_measure_start.py` (runs the script's building blocks, not the budgets)

**Interfaces:**
- Produces: `uv run python scripts/measure-start.py [--servers 40] [--plugins 10] [--skills 20] [--slow 10]`. It imports `make_home` and `write_cursor_fixture_state` from `tests/conftest.py` (sys.path), builds a sandbox home under a temporary folder, adds `--servers` MCP entries spread over `.claude.json`, `.codex/config.toml` and `.cursor/mcp.json`, `--plugins` plugin folders under `.claude/plugins/cache/<marketplace>/<name>/1.0.0` with `installed_plugins.json` entries, `--skills` skill folders under `.claude/skills`, `.agents/skills` and `.cursor/skills`; writes a fake `codex` into `<sandbox>/bin` (first on PATH for the page process) whose `--version` prints `codex-cli 0.163.0` and whose `plugin list --json` sleeps `--slow` seconds then prints `{"installed": []}`; starts `create_app(lambda **o: build_inventory(home, **o), token=..., port=<free>, home=home, first_scan_later=True, quick_first=True)` under uvicorn in a thread; with httpx: GET `/?token=` for the cookie, then polls `/api/overview` every 50 ms until 200 with `headline`: that is **first usable**; asserts `/api/progress` has the step `"Codex plugins"` not done at that moment when `--slow > 0`; then a second run with `--slow 0`, polling `/api/progress` until every step is done: that is **complete**. Prints `first usable: 1.4 s (budget 2 s)` and `complete: 3.1 s (budget 5 s)`, exit code 1 when a budget is missed. The budgets are constants at the top of the script.

- [ ] **Step 1: Write the failing test** `test_the_sandbox_builder_makes_the_counts_asked(tmp_path)`: import `build_sandbox` from the script (import by path) and assert the counts of entries, plugins and skills on disk; and `test_the_fake_codex_sleeps_then_answers(tmp_path)`.
- [ ] **Step 2: Run it to see it fail**.
- [ ] **Step 3: Write the script** with `build_sandbox(root, servers, plugins, skills, slow) -> Path` and `measure(home, slow) -> dict` as its two functions and a `main()`.
- [ ] **Step 4: Run the script**: `uv run python scripts/measure-start.py` → both numbers printed, exit 0 on this Mac. If a budget is missed, the cause goes into Task 5's notes, not into a changed budget.
- [ ] **Step 5: Commit**

```bash
git add scripts/measure-start.py tests/unit/test_measure_start.py
git commit -m "Start: a script that measures the two numbers"
```

---

### Task 5: Docs and roadmap for Part 4

**Files:**
- Modify: `docs/development.md` (a "Speed" section: the two numbers with the date and the machine, how to run the script, the budgets; the "Gateways" list gains `versions.json`)
- Modify: `README.md` (one sentence in "Why you want it" or Install: the page has its data in about two seconds; the exact number from the script)
- Modify: `ROADMAP.md` (Part 4 from "## Planned" to "### Not released yet")

- [ ] **Step 1: Run the script and write the numbers** with `checked YYYY-MM-DD`.
- [ ] **Step 2: Update README.md and ROADMAP.md**.
- [ ] **Step 3: Run all checks**: `uv run pytest -q && uv run ruff check . && node --test tests/frontend/*.test.mjs`
- [ ] **Step 4: Commit**

```bash
git add docs/development.md README.md ROADMAP.md
git commit -m "Docs: Part 4 of the review follow-up"
```
