"""Real clients in a sandbox home: remove entries and undo (T049, quickstart scenario 3).

Runs the installed `claude` and `codex` commands with HOME and CODEX_HOME pointing at a copy of
the fixtures, so the owner's real settings are never touched. Run with: pytest -m contract
"""

import json
import os
import subprocess

import pytest

from kitden.changes.actions import remove_steps
from kitden.changes.backup import ChangeStore
from kitden.changes.client_cli import CommandRunner
from kitden.changes.engine import Engine
from kitden.model import ChangeState
from kitden.views.inventory import build_inventory, default_adapters
from tests.conftest import make_home, write_cursor_fixture_state
from tests.contract.conftest import need_command

pytestmark = pytest.mark.contract

FILES = [".claude.json", ".codex/config.toml", ".cursor/mcp.json", "work/website/.mcp.json"]


@pytest.fixture
def home(tmp_path, monkeypatch):
    need_command("claude", tmp_path)
    need_command("codex", tmp_path)
    for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        monkeypatch.delenv(name, raising=False)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def _bytes(home):
    return {name: (home / name).read_bytes() for name in FILES}


def _codex_servers(home) -> dict:
    env = {**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}
    out = subprocess.run(
        [need_command("codex", home), "mcp", "list", "--json"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    data = json.loads(out)
    return {s["name"]: s for s in (data if isinstance(data, list) else data.get("servers", []))}


def test_remove_and_undo_with_real_clients(home):
    original = _bytes(home)
    adapters = {a.id: a for a in default_adapters(home)}
    engine = Engine(ChangeStore(home / "data"), CommandRunner(home))

    inventory = build_inventory(home)
    local = next(i for i in inventory.items if i.name == "local-db" and str(i.scope) == "local")
    remove_local = engine.preview("mcp.remove_direct", remove_steps(adapters, local))
    engine.apply(remove_local.id)
    assert remove_local.state is ChangeState.VERIFIED, remove_local.error

    project = next(i for i in inventory.items if i.name == "docs" and str(i.scope) == "project")
    remove_project = engine.preview("mcp.remove_direct", remove_steps(adapters, project))
    engine.apply(remove_project.id)
    assert remove_project.state is ChangeState.VERIFIED, remove_project.error

    neon = next(
        i
        for i in inventory.items
        if i.client == "codex" and i.name == "neon" and str(i.scope) == "user"
    )
    remove_codex = engine.preview("mcp.remove_direct", remove_steps(adapters, neon))
    engine.apply(remove_codex.id)
    assert "neon" not in _codex_servers(home)

    for change in (remove_codex, remove_project, remove_local):
        engine.undo(change.id)
        assert change.state is ChangeState.UNDONE, change.error
    assert _bytes(home) == original
