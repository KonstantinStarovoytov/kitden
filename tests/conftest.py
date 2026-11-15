"""Shared test helpers: fake home folders built from tests/fixtures."""

import contextlib
import json
import os
import shlex
import shutil
import sqlite3
import sys
import time
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SET_ASIDE = Path(__file__).parent / "set-aside.txt"


def set_aside_ids(path: Path = SET_ASIDE) -> list[str]:
    """The tests listed in the file, without comments, blank lines, dates and reasons."""
    ids = []
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            ids.append(line.split("  #")[0].strip())
    return ids


def split(ids: list[str], listed: list[str], mode: str) -> tuple[list[str], list[str]]:
    """The tests this mode keeps, and the ones it leaves out. `skip` leaves out the listed
    tests, `only` keeps just them, `run` keeps all."""
    if mode == "run":
        return ids, []
    inside = [i for i in ids if i in listed]
    outside = [i for i in ids if i not in listed]
    return (outside, inside) if mode == "skip" else (inside, outside)


def pytest_addoption(parser):
    parser.addoption(
        "--set-aside",
        choices=["skip", "only", "run"],
        default="skip",
        help="Tests listed in tests/set-aside.txt: skip them (default), run only them, or all.",
    )


def pytest_collection_modifyitems(config, items):
    kept, left_out = split(
        [item.nodeid for item in items], set_aside_ids(), config.getoption("--set-aside")
    )
    if left_out:
        keep = set(kept)
        config.hook.pytest_deselected(items=[item for item in items if item.nodeid not in keep])
        items[:] = [item for item in items if item.nodeid in keep]


@pytest.fixture(autouse=True)
def _never_the_real_home(tmp_path_factory, monkeypatch):
    """Tests never read or write the developer's real home folder, even by accident. The XDG
    folders would point Linux paths outside the sandbox home, so they go too."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("real-home")))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


@pytest.fixture(autouse=True)
def _watch_by_polling(monkeypatch):
    """The file watcher checks the folders itself in tests instead of asking macOS. On a busy
    Mac, macOS can report a change 10 to 40 seconds late, and a write made before watching
    as a new change, so the tests timed out or saw a change twice."""
    monkeypatch.setenv("WATCHFILES_FORCE_POLLING", "1")


def aged(path: Path) -> Path:
    """Date a file 10 seconds back. The polling watcher only sees a change when a file's time
    moves to a new second, so a file written just before watching must look older."""
    then = time.time() - 10
    os.utime(path, (then, then))
    return path


@pytest.fixture
def system(monkeypatch):
    """`system("linux")` makes this test, and the commands it starts, run as that system."""
    import kitden.system

    def use(name: str) -> None:
        monkeypatch.setenv("KITDEN_SYSTEM", name)
        monkeypatch.setattr(kitden.system, "SYSTEM", name)

    return use


CLIENT_BINARIES = {"claude", "codex", "cursor"}  # compared in lower case, so "Cursor" too
# Only the nightly sets these, each for its own system: KITDEN_REAL_KEYRING on Linux lets tests
# run the real `secret-tool` (tests/unit/test_real_keyring.py, test_real_secrets.py), and
# KITDEN_REAL_KEYCHAIN on macOS, with a keychain made for the run, the real `security`
# (test_real_secrets.py). Judged by the real platform, not KITDEN_SYSTEM.
REAL_SECRET_TOOLS = (
    {"secret-tool"}
    if sys.platform == "linux" and os.environ.get("KITDEN_REAL_KEYRING") == "1"
    else {"security"}
    if sys.platform == "darwin" and os.environ.get("KITDEN_REAL_KEYCHAIN") == "1"
    else set()
)
KEYCHAIN_BINARIES = {"security", "secret-tool"}  # the Keychain on macOS, the keyring on Linux
WRAPPERS = {"env", "sh", "bash", "zsh", "dash"}


def _words(args) -> list[str]:
    """The words of a command that could name the program it runs: every word of a shell
    string, every word behind a wrapper such as env or sh -c, else only the first."""
    if isinstance(args, str | bytes):
        args = os.fsdecode(args)
        try:
            return shlex.split(args)
        except ValueError:
            return args.split()
    words = [os.fsdecode(args)] if isinstance(args, os.PathLike) else [os.fsdecode(a) for a in args]
    if not words or Path(words[0]).name not in WRAPPERS:
        return words[:1]
    return [w for word in words for w in _words(word)]


def refused(words: list[str], home: str | None, sandbox: Path, contract: bool) -> str | None:
    """Why a test must not run this command, or None. A program inside the sandbox may run.
    This process never runs the Keychain command, but a real client may read the Keychain
    itself. A real client may run only in a contract test, and only with its home folder
    inside the sandbox. A full path is judged by both its names, as written and as resolved:
    Claude Code's launcher `claude` is a link to a file named after its version."""
    sandbox = sandbox.resolve()
    for word in words:
        path = Path(word).resolve() if Path(word).is_absolute() else Path(word)
        if path.is_relative_to(sandbox):
            continue
        names = {Path(word).name.lower(), path.name.lower()}
        if names & KEYCHAIN_BINARIES:
            return f"a test tried to run the real Keychain: {word}"
        if names & CLIENT_BINARIES:
            if not contract:
                return f"a test tried to run a real client: {word}"
            if home is None or not Path(home).resolve().is_relative_to(sandbox):
                return (
                    f"a contract test tried to run {word} with its home or settings folder "
                    f"outside the sandbox: {home}"
                )
    return None


def client_homes(env: Mapping[str, str]) -> list[str | None]:
    """Every folder a client could take as its home: HOME, then Claude Code's and Codex's own."""
    homes: list[str | None] = [env.get("HOME")]
    homes += [env[name] for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME") if name in env]
    return homes


@pytest.fixture(autouse=True)
def _no_client_commands(request, tmp_path_factory, monkeypatch):
    """No test runs a real client: a test that needs one uses a fake in its tmp folder. Only a
    contract test may find and run a real client, with HOME, CLAUDE_CONFIG_DIR and CODEX_HOME in
    the sandbox."""
    import subprocess

    from kitden.clients import codex, version_cache

    contract = request.node.get_closest_marker("contract") is not None
    if not contract:
        monkeypatch.setattr(version_cache, "version_command", lambda client: None)
        monkeypatch.setattr(codex, "version_command", lambda client: None)
        monkeypatch.setattr(codex, "_LIST_CACHE", {})
    sandbox = tmp_path_factory.getbasetemp().resolve()

    class Guarded(subprocess.Popen):
        def __init__(self, args, *rest, **options):
            words = _words(args)
            if REAL_SECRET_TOOLS:
                words = [w for w in words if Path(w).name.lower() not in REAL_SECRET_TOOLS]
            env = options.get("env")
            for home in client_homes(os.environ if env is None else env):
                message = refused(words, home, sandbox, contract)
                if message:
                    raise AssertionError(message)
            super().__init__(args, *rest, **options)

    monkeypatch.setattr(subprocess, "Popen", Guarded)


@pytest.fixture(autouse=True)
def _never_the_real_keychain(tmp_path_factory, monkeypatch):
    """Kitden's Keychain calls go to a path that does not exist, unless a test uses
    `fake_keychain`. Child processes such as `kitden mcp` get the same env: the MCP SDK starts a
    stdio server with only a few env values of this process, so KITDEN_SECURITY joins them."""
    from mcp.client import stdio

    missing = tmp_path_factory.getbasetemp().resolve() / "no-security"
    monkeypatch.setenv("KITDEN_SECURITY", str(missing))
    monkeypatch.setenv("KITDEN_SECRET_TOOL", str(missing))
    inherited = [
        *stdio.DEFAULT_INHERITED_ENV_VARS,
        "KITDEN_SECURITY",
        "KITDEN_SECRET_TOOL",
        "KITDEN_SYSTEM",
    ]
    monkeypatch.setattr(stdio, "DEFAULT_INHERITED_ENV_VARS", inherited)


def install_fake_security(folder: Path) -> Path:
    """Put `security` and `secret-tool` stand-ins in folder/bin, sharing one JSON file of items,
    and return that file."""
    items = folder / "fake-keychain.json"
    for name, script in (("security", "fake_security.py"), ("secret-tool", "fake_secret_tool.py")):
        binary = folder / "bin" / name
        binary.parent.mkdir(parents=True, exist_ok=True)
        command = shlex.join([sys.executable, str(FIXTURES / script), str(items)])
        binary.write_text(f'#!/bin/sh\nexec {command} "$@"\n')
        binary.chmod(0o755)
    return items


@pytest.fixture
def fake_keychain(tmp_path, monkeypatch) -> Path:
    """Kitden's Keychain and keyring calls, in this process and its children, go to the
    stand-ins. Returns the JSON file of their items."""
    items = install_fake_security(tmp_path / "keychain")
    monkeypatch.setenv("KITDEN_SECURITY", str(tmp_path / "keychain/bin/security"))
    monkeypatch.setenv("KITDEN_SECRET_TOOL", str(tmp_path / "keychain/bin/secret-tool"))
    return items


@pytest.fixture
def as_mac(system):
    """For a test module about macOS's words and `security` command lines:
    `pytestmark = pytest.mark.usefixtures("as_mac")`."""
    system("mac")


def cursor_db(home: Path) -> Path:
    """Cursor's global state database in this system's folder."""
    from kitden.system import cursor_state_dir

    return cursor_state_dir(home) / "globalStorage/state.vscdb"


def cursor_workspaces(home: Path) -> Path:
    from kitden.system import cursor_state_dir

    return cursor_state_dir(home) / "workspaceStorage"


# Fixture homes keep macOS's Library folders; on Linux they move to that system's places.
MAC_FOLDERS = {
    "Library/Application Support/Claude": "claude_desktop_dir",
    "Library/Application Support/Cursor/User": "cursor_state_dir",
}


def make_home(tmp_path: Path, *fixtures: str) -> Path:
    """Copy fixture homes (e.g. 'codex/0.159.2') into one fake home and fill in {HOME}."""
    home = tmp_path / "home"
    for name in fixtures:
        shutil.copytree(FIXTURES / name / "home", home, symlinks=True, dirs_exist_ok=True)
    for path in home.rglob("*"):
        if path.is_file() and not path.is_symlink():
            text = path.read_text()
            if "{HOME}" in text:
                path.write_text(text.replace("{HOME}", str(home)))
    import kitden.system

    if kitden.system.SYSTEM != "mac":
        for mac, helper in MAC_FOLDERS.items():
            if (home / mac).is_dir():
                target = getattr(kitden.system, helper)(home)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(home / mac, target)
        shutil.rmtree(home / "Library/Application Support", ignore_errors=True)
        with contextlib.suppress(OSError):
            (home / "Library").rmdir()
    return home


def write_cursor_state(home: Path, rows: dict, db: Path | None = None) -> Path:
    """Create a Cursor state database with the given key → value rows (the global one by
    default)."""
    db = db or cursor_db(home)
    db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as con, con:
        con.execute("CREATE TABLE ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
        for key, value in rows.items():
            text = value if isinstance(value, str) else json.dumps(value)
            con.execute(
                "INSERT INTO ItemTable VALUES (?, ?)", (key.replace("{HOME}", str(home)), text)
            )
    return db


def _cursor_fixture(home: Path, name: str) -> dict:
    text = (FIXTURES / "cursor/3.21.16" / name).read_text()
    return json.loads(text.replace("{HOME}", str(home)))


def cursor_state_rows(home: Path) -> dict:
    return _cursor_fixture(home, "cursor-state.json")


def write_cursor_fixture_state(home: Path, extra_rows: dict | None = None) -> None:
    """Write the fixture's global and per-workspace Cursor state databases."""
    write_cursor_state(home, {**cursor_state_rows(home), **(extra_rows or {})})
    for workspace, rows in _cursor_fixture(home, "cursor-workspace-state.json").items():
        write_cursor_state(home, rows, cursor_workspaces(home) / workspace / "state.vscdb")


def rows(items, home: Path) -> set[tuple]:
    """Compact view of items for assertions: (client, kind, name, scope, enabled, project)."""
    out = set()
    for item in items:
        project = str(Path(item.project).relative_to(home)) if item.project else None
        out.add(
            (item.client, str(item.kind), item.name, str(item.scope), str(item.enabled), project)
        )
    return out


def all_text(value) -> str:
    """Everything a scan could show, as one string, for secret checks."""
    return json.dumps(value, default=lambda o: getattr(o, "__dict__", str(o)))


@pytest.fixture(autouse=True)
def _no_real_client_homes(monkeypatch):
    """Tests must never reach the real ~/.codex or Claude Code folder through CODEX_HOME or
    CLAUDE_CONFIG_DIR."""
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)


@pytest.fixture(autouse=True)
def _kitden_paths_count_as_present(monkeypatch):
    """Tests write `kitden` entries with made-up paths such as /opt/kitden/bin/kitden. They count
    as present, so an entry is not taken for one whose program is gone. `real_programs` undoes
    it."""
    from kitden.views import setup_server

    monkeypatch.setattr(setup_server, "_gone", lambda command: False)


@pytest.fixture
def real_programs(monkeypatch):
    from kitden.views import setup_server

    monkeypatch.setattr(setup_server, "_gone", setup_server.gone)


@pytest.fixture
def no_version():
    return lambda: None


def fake_client_command(folder: Path, name: str, body: str) -> Path:
    """A shell script in the sandbox that stands in for a client command (never the real one)."""
    binary = folder / "bin" / name
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text(f"#!/bin/sh\n{body}\n")
    binary.chmod(0o755)
    return binary
