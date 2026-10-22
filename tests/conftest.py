"""Shared test helpers: fake home folders built from tests/fixtures."""

import json
import os
import shlex
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _never_the_real_home(tmp_path_factory, monkeypatch):
    """Tests never read or write the developer's real home folder, even by accident."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("real-home")))


CLIENT_BINARIES = {"claude", "codex", "cursor"}  # compared in lower case, so "Cursor" too
KEYCHAIN_BINARIES = {"security"}  # macOS's Keychain command
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


@pytest.fixture(autouse=True)
def _no_client_commands(tmp_path_factory, monkeypatch):
    """No test finds or runs a real client; a test that needs one uses a fake in its tmp folder."""
    import subprocess

    from kitden.clients import codex, version_cache

    monkeypatch.setattr(version_cache, "version_command", lambda client: None)
    monkeypatch.setattr(codex, "version_command", lambda client: None)
    monkeypatch.setattr(codex, "_LIST_CACHE", {})
    sandbox = tmp_path_factory.getbasetemp().resolve()

    class Guarded(subprocess.Popen):
        def __init__(self, args, *rest, **options):
            for word in _words(args):
                path = Path(word).resolve() if Path(word).is_absolute() else Path(word)
                if path.is_relative_to(sandbox):
                    continue
                if path.name.lower() in CLIENT_BINARIES:
                    raise AssertionError(f"a test tried to run a real client: {word}")
                if path.name.lower() in KEYCHAIN_BINARIES:
                    raise AssertionError(f"a test tried to run the real Keychain: {word}")
            super().__init__(args, *rest, **options)

    monkeypatch.setattr(subprocess, "Popen", Guarded)


@pytest.fixture(autouse=True)
def _never_the_real_keychain(tmp_path_factory, monkeypatch):
    """Kitden's Keychain calls go to a path that does not exist, unless a test uses
    `fake_keychain`. Child processes such as `kitden mcp` get the same env."""
    missing = tmp_path_factory.getbasetemp().resolve() / "no-security"
    monkeypatch.setenv("KITDEN_SECURITY", str(missing))


def install_fake_security(folder: Path) -> Path:
    """Put a `security` stand-in in folder/bin and return the JSON file that holds its items."""
    items = folder / "fake-keychain.json"
    binary = folder / "bin" / "security"
    binary.parent.mkdir(parents=True, exist_ok=True)
    script = FIXTURES / "fake_security.py"
    binary.write_text(
        f'#!/bin/sh\nexec {shlex.join([sys.executable, str(script), str(items)])} "$@"\n'
    )
    binary.chmod(0o755)
    return items


@pytest.fixture
def fake_keychain(tmp_path, monkeypatch) -> Path:
    """Kitden's Keychain calls, in this process and its children, go to the stand-in.
    Returns the JSON file of its items."""
    items = install_fake_security(tmp_path / "keychain")
    monkeypatch.setenv("KITDEN_SECURITY", str(tmp_path / "keychain/bin/security"))
    return items


CURSOR_DB = "Library/Application Support/Cursor/User/globalStorage/state.vscdb"
CURSOR_WORKSPACES = "Library/Application Support/Cursor/User/workspaceStorage"


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
    return home


def write_cursor_state(home: Path, rows: dict, db_path: str = CURSOR_DB) -> Path:
    """Create a Cursor state database with the given key → value rows."""
    db = home / db_path
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as con:
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
        write_cursor_state(home, rows, f"{CURSOR_WORKSPACES}/{workspace}/state.vscdb")


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
    """Tests must never read the real ~/.codex through CODEX_HOME."""
    monkeypatch.delenv("CODEX_HOME", raising=False)


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
