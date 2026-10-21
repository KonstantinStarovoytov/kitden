# Part 7: Linux and Windows — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kitden installs, opens and works on Linux, then on Windows, with every OS-specific path in one module and the macOS behavior unchanged.

**Architecture:** A new module `src/kitden/paths.py` answers every OS-specific question (data folder, each client's roots and state files, app folders, version command fallbacks) from a `system` value that tests can set. Every caller that holds a hard-coded path today delegates to it. The page lock and the background start get OS branches in `page.py`; the Keychain module gets an OS twin; the install scripts and CI grow one OS at a time.

**Tech Stack:** Python 3.13 (`fcntl` on POSIX, `msvcrt` on Windows), Starlette, uvicorn; shell and PowerShell install scripts; GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-21-review-follow-up-design.md`, Part 7 (7.1, 7.2). Master plan: `docs/superpowers/plans/2026-10-21-review-follow-up.md` (fixed name: `kitden.paths`; `data_dir` delegates; the Keychain reference shape stays; review focus 5).

## Global Constraints

- Code, comments, UI text and docs in simple English (`AGENTS.md`).
- macOS values stay exactly as today; a test pins each one.
- Every path on Linux and Windows is checked against the client's docs with the date in a comment in `paths.py`.
- Tests run on macOS too: `paths.py` takes `system` explicitly and tests pass each value; no test depends on the host OS.
- Tests on sandbox homes. Before each commit: `uv run pytest -q`, `uv run ruff check .`, `node --test tests/frontend/*.test.mjs`. Commit subjects plain, no prefix.
- No new runtime dependency.

## Review Focus

1. `$XDG_DATA_HOME` set to a relative path or empty: Linux falls back to `~/.local/share/kitden` (Task 1 test `test_a_bad_xdg_data_home_falls_back`).
2. A Linux home with `~/.config/Cursor` but no Cursor binary: Cursor is found from its files and its version is unknown, as on macOS (Task 2 test `test_cursor_is_found_from_its_files_on_linux`).
3. The data folder unreadable or missing on any OS: the page and the gateway still start and say so (Task 1 test `test_data_dir_is_computed_without_touching_the_disk`; the master's item 5 stays covered by the existing tests, run on each CI OS).
4. Windows: two `kitden` commands at once on one home: the second sees the lock and opens the first page, as on macOS (Task 7 test `test_the_page_lock_works_with_msvcrt`, run under a `sys.platform` monkeypatch with a fake `msvcrt`).
5. A secret stored in the file fallback: the review says so in the exact sentence and the file is mode 600 where modes exist (Task 5 test `test_the_file_fallback_warns_and_is_private`).

---

### Task 1: One module for every OS path (7.1)

**Files:**
- Create: `src/kitden/paths.py`
- Modify: `src/kitden/gateways.py:20-25` (`DATA_DIR`, `OLD_DATA_DIR`, `data_dir` delegate; the old folder exists on macOS only), `src/kitden/cli.py:22` (`WATCHED` from `paths.watched_folders(system)`)
- Test: `tests/unit/test_paths.py` (new), `tests/unit/test_data_folder.py`

**Interfaces:**
- Produces: `System = Literal["macos", "linux", "windows"]`; `current_system() -> System` from `sys.platform` (`darwin`, `win32`, else `linux`); `data_dir(home: Path, system: System | None = None, env: Mapping[str, str] = os.environ) -> Path`: macOS `home/Library/Application Support/kitden`; Linux `$XDG_DATA_HOME/kitden` when `XDG_DATA_HOME` is an absolute path, else `home/.local/share/kitden`; Windows `%APPDATA%\kitden` when `APPDATA` is absolute, else `home/AppData/Roaming/kitden`; `old_data_dir(home, system) -> Path | None` (macOS only); `watched_folders(system) -> tuple[str, ...]` (relative to home; macOS as today); `client_root(client, system) -> str` (`.claude`, `.codex`, `.cursor` on every OS); `cursor_state_db(home, system) -> Path` and `cursor_workspace_storage(home, system) -> Path` (macOS as today; Linux `home/.config/Cursor/User/globalStorage/state.vscdb` and `.../workspaceStorage`; Windows `%APPDATA%\Cursor\User\globalStorage\state.vscdb`); `claude_desktop_config(home, system) -> Path | None` and `claude_desktop_bundled(home, system) -> Path | None` (macOS as today; Linux `None` unless Claude Desktop's docs name a Linux folder; Windows `%APPDATA%\Claude\...`); `app_roots(home, system) -> list[Path]` (macOS as today; Linux and Windows `[]`); `version_fallbacks(client, system) -> tuple[str, ...]` (macOS as today; others `()`).

- [ ] **Step 1: Check the docs** for each non-macOS location (Cursor, Claude Desktop, Codex, Claude Code) and write the dates in `paths.py`.
- [ ] **Step 2: Write the failing tests**

```python
def test_macos_paths_are_unchanged(tmp_path):
    assert data_dir(tmp_path, "macos") == tmp_path / "Library/Application Support/kitden"
    assert cursor_state_db(tmp_path, "macos") == tmp_path / "Library/Application Support/Cursor/User/globalStorage/state.vscdb"
    assert watched_folders("macos") == (".claude", ".codex", ".cursor", ".agents", "Library/Application Support/Claude")


def test_linux_paths_follow_xdg_and_dot_config(tmp_path):
    assert data_dir(tmp_path, "linux", {"XDG_DATA_HOME": "/xdg"}) == Path("/xdg/kitden")
    assert data_dir(tmp_path, "linux", {}) == tmp_path / ".local/share/kitden"
    assert cursor_state_db(tmp_path, "linux") == tmp_path / ".config/Cursor/User/globalStorage/state.vscdb"


def test_a_bad_xdg_data_home_falls_back(tmp_path):
    assert data_dir(tmp_path, "linux", {"XDG_DATA_HOME": "relative"}) == tmp_path / ".local/share/kitden"


def test_windows_paths_use_appdata(tmp_path):
    assert data_dir(tmp_path, "windows", {"APPDATA": r"C:\Users\x\AppData\Roaming"}) == Path(r"C:\Users\x\AppData\Roaming") / "kitden"


def test_data_dir_is_computed_without_touching_the_disk(tmp_path):
    assert not data_dir(tmp_path / "missing", "linux", {}).exists()
```

- [ ] **Step 3: Run them to see them fail**.
- [ ] **Step 4: Implement**; `gateways.data_dir(home)` becomes `paths.data_dir(home)`; the existing tests keep passing on macOS.
- [ ] **Step 5: Run** `uv run pytest tests/unit/test_paths.py tests/unit/test_data_folder.py tests/unit/test_cli.py -v` → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/paths.py src/kitden/gateways.py src/kitden/cli.py tests/unit/test_paths.py
git commit -m "Paths: one module for every OS"
```

---

### Task 2: The adapters and apps use the paths module (7.1)

**Files:**
- Modify: `src/kitden/clients/claude_code.py:55-57` (`DESKTOP_CONFIG`, `DESKTOP_BUNDLED` → `paths`), `src/kitden/clients/cursor.py:49-50` (`STATE_DB`, `WORKSPACE_STATE` → `paths`), `src/kitden/clients/codex.py:50` (`BUILT_IN_FOLDERS` checked per OS), `src/kitden/clients/versions.py:17-21` (`_COMMANDS` fallbacks from `paths.version_fallbacks`), `src/kitden/apps.py:21-24` (`app_roots` from `paths`), `src/kitden/changes/client_cli.py:22-33` (`find_command` fallbacks from `paths`)
- Test: `tests/unit/test_read_cursor.py`, `tests/unit/test_read_claude_code.py`, `tests/unit/test_versions.py`, `tests/unit/test_apps.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_cursor_is_found_from_its_files_on_linux(tmp_path, no_version, monkeypatch):
    monkeypatch.setattr("kitden.paths.current_system", lambda: "linux")
    home = tmp_path / "home"; (home / ".cursor").mkdir(parents=True)
    write_cursor_state(home, cursor_state_rows(home), db_path=".config/Cursor/User/globalStorage/state.vscdb")
    client = CursorAdapter(home).detect()
    assert str(client.status) == "found" and client.version is None


def test_no_desktop_client_on_linux(tmp_path, no_version, monkeypatch):
    monkeypatch.setattr("kitden.paths.current_system", lambda: "linux")
    assert ClaudeCodeAdapter(make_home(tmp_path, "claude_code/2.1.283")).extra_clients() == []


def test_no_app_links_outside_macos(tmp_path, monkeypatch):
    monkeypatch.setattr("kitden.paths.current_system", lambda: "linux")
    assert app_url("cursor", app_roots(tmp_path)) is None
```

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**; every module reads `paths.current_system()` at call time, not import time, so the monkeypatch works.
- [ ] **Step 4: Run** `uv run pytest tests/unit -q` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/clients src/kitden/apps.py src/kitden/changes/client_cli.py tests/unit
git commit -m "Clients: paths per OS"
```

---

### Task 3: Install on Linux (7.1)

**Files:**
- Modify: `install.sh:12-16` (remove the Darwin stop; the git check becomes `command -v git`; the message names the uv docs), `README.md` (Install: macOS and Linux; the Linux line), `pyproject.toml` (classifiers: `Operating System :: POSIX :: Linux`), `docs/development.md` ("Linux and Windows": Linux is supported; Windows not yet)
- Test: `tests/unit/test_install_script.py` (`test_on_linux_it_installs_nothing_and_says_so` becomes `test_on_linux_it_installs_like_on_macos`; `test_without_the_command_line_tools_it_says_how_to_get_git` becomes a `git` check)

- [ ] **Step 1: Write the failing tests** (the `box` fixture fakes `uname`; add a fake `git` to it).
- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Change the script and the docs**.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_install_script.py tests/unit/test_release_files.py -v` → PASS.
- [ ] **Step 5: Commit**

```bash
git add install.sh README.md pyproject.toml docs/development.md tests/unit/test_install_script.py
git commit -m "Install: Linux"
```

---

### Task 4: CI on Linux (7.1)

**Files:**
- Modify: `.github/workflows/release.yml:17` (the checks job runs on a matrix `[macos-latest, ubuntu-latest]`; the build and publish jobs stay as they are)
- Test: `tests/unit/test_release_workflow.py`

- [ ] **Step 1: Write the failing test**: the checks job has a `matrix.os` that includes `ubuntu-latest` and `macos-latest`.
- [ ] **Step 2: Run it to see it fail**.
- [ ] **Step 3: Edit the workflow**.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_release_workflow.py -v` → PASS. Push a branch and watch the Linux job once; fix what it finds (file modes and `realpath` are the usual suspects) in this task.
- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release.yml tests/unit/test_release_workflow.py
git commit -m "CI: run the checks on Linux too"
```

---

### Task 5: The Keychain's twin (7.1)

**Files:**
- Modify: `src/kitden/local_gateway/keychain.py` (a backend chosen by `paths.current_system()` and `shutil.which`: macOS `security`; Linux `secret-tool` when present (`secret-tool store --label=kitden service kitden account <account>` with the value on stdin; `secret-tool lookup service kitden account <account>`; `secret-tool clear ...`); else and on Windows a file `<data folder>/secrets.json`, mode 600 where modes exist, `{account: value}`, written atomically); `store` returns the same reference shape; a new `backend_name() -> "keychain" | "secret-tool" | "file"`
- Modify: `src/kitden/views/after.py` (the move and keychain reviews say, with the file backend: `"This computer has no keychain; the secret is kept in a private file."`), `docs/development.md` (where secrets live per OS)
- Test: `tests/unit/test_keychain.py`, `tests/unit/test_after.py`

- [ ] **Step 1: Check `secret-tool`'s usage** (libsecret docs) and write the date.
- [ ] **Step 2: Write the failing tests**: the file backend round trip; `test_the_file_fallback_warns_and_is_private` (the review line and `oct(mode)[-3:] == "600"` on POSIX); the `secret-tool` backend with a fake `secret-tool` on PATH that reads stdin.
- [ ] **Step 3: Run them to see them fail**.
- [ ] **Step 4: Implement**.
- [ ] **Step 5: Run** `uv run pytest tests/unit/test_keychain.py tests/unit/test_after.py tests/security -v` → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/local_gateway/keychain.py src/kitden/views/after.py docs/development.md tests/unit
git commit -m "Gateway: secrets on Linux and in a private file where there is no keychain"
```

---

### Task 6: Hand check on Linux and the roadmap (7.1)

**Files:**
- Modify: `docs/development.md` (the Linux hand check: install with the one-line script on a Linux machine with Claude Code and Codex, open the page, move a server into the gateway, see it in a new session; note the date and the distribution), `ROADMAP.md` ("Linux" under "### Not released yet"; Windows stays under "## Planned")

- [ ] **Step 1: Do the hand check** on a Linux machine or a VM; note the date.
- [ ] **Step 2: Update the docs**.
- [ ] **Step 3: Run all checks** and commit:

```bash
git add docs/development.md ROADMAP.md
git commit -m "Docs: Linux"
```

---

### Task 7: The page on Windows (7.2)

**Files:**
- Modify: `src/kitden/page.py:30-56` (`PageLock`: `_lock(fd)` and `_unlock(fd)` use `fcntl.flock` where `fcntl` imports, else `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)`; the module imports neither at the top), `130-157` (`start_background`: on Windows `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS` instead of `start_new_session`), `src/kitden/changes/backup.py` and `atomic.py` (modes: keep the calls; they are harmless on Windows; one sentence in the docs says Windows has no modes)
- Test: `tests/unit/test_page.py`

- [ ] **Step 1: Write the failing tests**: `test_the_page_lock_works_with_msvcrt` (monkeypatch `kitden.page._posix_lock` to `None` and a fake `msvcrt` module with `locking` that records calls and raises `OSError` on the second lock); `test_the_background_start_uses_a_process_group_on_windows` (monkeypatch `subprocess.Popen` and `paths.current_system` to `"windows"`; assert `creationflags` is set and `start_new_session` is not).
- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_page.py -v` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/page.py src/kitden/changes/backup.py src/kitden/changes/atomic.py docs/development.md tests/unit/test_page.py
git commit -m "Page: the lock and the background start on Windows"
```

---

### Task 8: Windows paths, install and CI (7.2)

**Files:**
- Modify: `src/kitden/paths.py` (the Windows values from Task 1, re-checked against the clients' docs with dates: Claude Code `%USERPROFILE%\.claude` and `.claude.json`; Codex `%USERPROFILE%\.codex`; Cursor `%USERPROFILE%\.cursor` and `%APPDATA%\Cursor\User\...`; Claude Desktop `%APPDATA%\Claude\claude_desktop_config.json`), `src/kitden/clients/versions.py` (`claude.cmd` / `codex.cmd` through `shutil.which`, which honors `PATHEXT`), `src/kitden/changes/client_cli.py` (same)
- Modify: `install.ps1:11-16` (`$WindowsSupported = $true`; the rest runs), `README.md` (Install: Windows line), `pyproject.toml` (`Operating System :: Microsoft :: Windows`), `.github/workflows/release.yml` (matrix adds `windows-latest`; the checks use `uv run` so no shell differences)
- Test: `tests/unit/test_paths.py`, `tests/unit/test_install_script.py` (`test_windows_script_names_the_same_release_and_stops_for_now` becomes `..._and_installs`), `tests/unit/test_release_workflow.py`

- [ ] **Step 1: Check the docs** for each Windows location; write the dates.
- [ ] **Step 2: Write the failing tests** (as Task 1's Windows test, one per location; the script test; the workflow test for `windows-latest`).
- [ ] **Step 3: Run them to see them fail**.
- [ ] **Step 4: Implement**. Push a branch and watch the Windows job once; fix what it finds (path separators in tests, `realpath` of symlinks, `tomllib` newlines) in this task.
- [ ] **Step 5: Run** the three test files → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/paths.py src/kitden/clients/versions.py src/kitden/changes/client_cli.py install.ps1 README.md pyproject.toml .github/workflows/release.yml tests/unit
git commit -m "Windows: paths, install and CI"
```

---

### Task 9: Hand check on Windows and the roadmap (7.2)

**Files:**
- Modify: `docs/development.md` (the Windows hand check as Task 6's, with the note that the Keychain's twin is the private file; the date), `README.md` ("Linux and Windows are not supported yet" line removed), `ROADMAP.md` (Part 7 whole from "## Planned" to "### Not released yet")

- [ ] **Step 1: Do the hand check** on a Windows machine or a VM; note the date.
- [ ] **Step 2: Update the docs**.
- [ ] **Step 3: Run all checks** and commit:

```bash
git add docs/development.md README.md ROADMAP.md
git commit -m "Docs: Windows"
```
