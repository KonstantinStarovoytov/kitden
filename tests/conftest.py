"""Shared test helpers: fake home folders built from tests/fixtures."""

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _never_the_real_home(tmp_path_factory, monkeypatch):
    """Tests never read or write the developer's real home folder, even by accident."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("real-home")))


@pytest.fixture(autouse=True)
def _no_client_commands(monkeypatch):
    """No test finds or runs a real client command; a test that needs one points this at a fake."""
    from kitden.clients import version_cache

    monkeypatch.setattr(version_cache, "version_command", lambda client: None)


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
