"""The setup server with real clients in a sandbox home (T062, quickstart scenario 5).

Adds `kitden mcp` to Codex and Claude Code, checks their own listings, starts the server over
stdio the way a client does, calls `show_setup`, then undoes. Run with: pytest -m contract
"""

import json
import os
import shutil
import subprocess

import pytest
from mcp import Client, StdioServerParameters

import kitden.clients.base as base
from kitden.changes.actions import setup_server_steps
from kitden.changes.backup import ChangeStore
from kitden.changes.client_cli import CommandRunner, find_command
from kitden.changes.engine import Engine
from kitden.mcp_server import installed_command
from kitden.model import ChangeState
from kitden.views.inventory import default_adapters
from tests.conftest import make_home

pytestmark = [pytest.mark.contract, pytest.mark.anyio]
CODEX_APP = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _codex() -> str | None:
    return shutil.which("codex") or (CODEX_APP if os.path.exists(CODEX_APP) else None)


@pytest.fixture
def home(tmp_path, monkeypatch):
    if _codex() is None or find_command("claude", tmp_path) is None or installed_command() is None:
        pytest.skip("needs codex, claude and the kitden command")
    for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    return make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2")


def _env(home) -> dict[str, str]:
    return {**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}


async def test_register_handshake_and_undo(home):
    files = [home / ".codex/config.toml", home / ".claude.json"]
    original = [f.read_bytes() for f in files]
    command = installed_command()
    adapters = {a.id: a for a in default_adapters(home)}
    engine = Engine(ChangeStore(home / "data"), CommandRunner(home))

    change = engine.preview(
        "setup_server.register", setup_server_steps(adapters, ["codex", "claude_code"], command)
    )
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED, change.error

    listed = subprocess.run(  # noqa: S603 - fixed test command
        [_codex(), "mcp", "list", "--json"],
        env=_env(home),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    servers = {s["name"]: s for s in json.loads(listed)}
    assert servers["kitden"]["transport"]["command"] == command

    # Start the server the way a client does, with the sandbox as home.
    params = StdioServerParameters(command=command, args=["mcp"], env=_env(home), cwd=str(home))
    async with Client(params, read_timeout_seconds=60) as client:
        tools = {t.name for t in (await client.list_tools()).tools}
        result = await client.call_tool("show_setup", {"client": "codex"})
    assert tools == {"show_setup", "list_findings", "explain_item", "list_projects"}
    names = {i["name"] for i in result.structured_content["views"][0]["items"]}
    assert {"neon", "kitden"} <= names
    assert "SENTINEL" not in json.dumps(result.structured_content)

    engine.undo(change.id)
    assert change.state is ChangeState.UNDONE, change.error
    assert [f.read_bytes() for f in files] == original


async def test_old_entries_update_to_kitden_with_real_clients(home):
    """Feature 002: old entries become `kitden`, and Undo brings them back."""
    from kitden.changes import json_splice, toml_edit
    from kitden.changes.actions import update_steps
    from kitden.views.inventory import build_inventory
    from kitden.views.setup_server import is_old_entry

    old = {"type": "stdio", "command": "/opt/old/bin/agentsetup", "args": ["mcp"]}
    claude = find_command("claude", home)
    subprocess.run(  # noqa: S603 - fixed test command
        [claude, "mcp", "add-json", "-s", "user", "agentsetup", json.dumps(old)],
        env=_env(home),
        capture_output=True,
        check=True,
    )
    config = home / ".codex/config.toml"
    codex_old = {"command": "/opt/old/bin/agentsetup", "args": ["mcp"]}
    config.write_text(
        toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), codex_old)
    )
    codex_before = config.read_bytes()

    items = [i for i in build_inventory(home).items if is_old_entry(i)]
    assert {i.client for i in items} == {"claude_code", "codex"}
    adapters = {a.id: a for a in default_adapters(home)}
    command = installed_command()
    engine = Engine(ChangeStore(home / "data"), CommandRunner(home))
    change = engine.preview("setup_server.update", update_steps(adapters, items, set(), command))
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED, change.error

    got = subprocess.run(  # noqa: S603 - fixed test command
        [claude, "mcp", "get", "kitden"], env=_env(home), capture_output=True, text=True
    )
    assert got.returncode == 0 and command in got.stdout
    listed = subprocess.run(  # noqa: S603 - fixed test command
        [_codex(), "mcp", "list", "--json"],
        env=_env(home),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    names = {s["name"] for s in json.loads(listed)}
    assert "kitden" in names and "agentsetup" not in names

    engine.undo(change.id)
    assert change.state is ChangeState.UNDONE, change.error
    assert config.read_bytes() == codex_before
    text = (home / ".claude.json").read_text()
    assert json_splice.get_value(text, ("mcpServers", "agentsetup")) == old
    assert json_splice.get_value(text, ("mcpServers", "kitden")) is json_splice.ABSENT
