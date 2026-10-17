"""Real clients in a sandbox home (T049, quickstart scenario 3).

Runs the installed `claude` and `codex` commands with HOME and CODEX_HOME pointing at a copy of
the fixtures, so the owner's real settings are never touched. Run with: pytest -m contract
"""

import json
import os
import shutil
import subprocess

import pytest

import agentsetup.clients.base as base
from agentsetup.changes.actions import connect_steps, remove_steps
from agentsetup.changes.backup import ChangeStore
from agentsetup.changes.client_cli import CommandRunner, find_command
from agentsetup.changes.engine import Engine
from agentsetup.model import ChangeState, Gateway, GatewayAuth
from agentsetup.views.inventory import build_inventory, default_adapters
from tests.conftest import make_home, write_cursor_fixture_state

pytestmark = pytest.mark.contract

URL = "http://127.0.0.1:12008/metamcp/dev/mcp"
FILES = [".claude.json", ".codex/config.toml", ".cursor/mcp.json", "work/website/.mcp.json"]


def _codex() -> str | None:
    return shutil.which("codex") or (
        "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
        if os.path.exists("/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex")
        else None
    )


@pytest.fixture
def home(tmp_path, monkeypatch):
    if find_command("claude", tmp_path) is None or _codex() is None:
        pytest.skip("needs the claude and codex commands")
    for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def _bytes(home):
    return {name: (home / name).read_bytes() for name in FILES}


def _codex_servers(home) -> dict:
    env = {**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}
    out = subprocess.run(  # noqa: S603 - fixed test command
        [_codex(), "mcp", "list", "--json"], env=env, capture_output=True, text=True, check=True
    ).stdout
    data = json.loads(out)
    return {s["name"]: s for s in (data if isinstance(data, list) else data.get("servers", []))}


def _claude_get(home, name, cwd=None) -> str:
    env = {**os.environ, "HOME": str(home)}
    done = subprocess.run(  # noqa: S603 - fixed test command
        [find_command("claude", home), "mcp", "get", name],
        env=env,
        cwd=cwd or home,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return done.stdout + done.stderr


def test_connect_remove_and_undo_with_real_clients(home):
    original = _bytes(home)
    adapters = {a.id: a for a in default_adapters(home)}
    engine = Engine(ChangeStore(home / "data"), CommandRunner(home))
    gateway = Gateway(url=URL, auth=GatewayAuth.ENV_KEY, key_env_var="GW_KEY")

    connect = engine.preview(
        "gateway.connect",
        connect_steps(adapters, ["claude_code", "codex", "cursor"], gateway, "gateway"),
    )
    engine.apply(connect.id)
    assert connect.state is ChangeState.VERIFIED, connect.error
    codex_entry = _codex_servers(home)["gateway"]
    assert codex_entry["transport"]["bearer_token_env_var"] == "GW_KEY"
    assert "Bearer ${GW_KEY}" in _claude_get(home, "gateway")

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

    for change in (remove_codex, remove_project, remove_local, connect):
        engine.undo(change.id)
        assert change.state is ChangeState.UNDONE, change.error
    assert _bytes(home) == original
