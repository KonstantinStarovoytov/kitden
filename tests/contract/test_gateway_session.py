"""The Kitden gateway through the installed `kitden mcp`, as each client starts it.

Each test moves the fake server tests/fixtures/fake_mcp/echo_server.py into the gateway with
the change engine and the real `claude` and `codex` commands, as the page does, in a sandbox
home. Sessions are the stand-in of tests/contract/conftest.py: no client is signed in, and
Cursor, which no machine running these has, is only its file and the stand-in session. Run
with: pytest -m contract
"""

import json
import os
import subprocess
import sys
from functools import cache
from pathlib import Path

import pytest

from kitden.changes.actions import local_move_steps, put_back_steps
from kitden.changes.backup import ChangeStore
from kitden.changes.client_cli import CommandRunner
from kitden.changes.engine import Engine
from kitden.gateways import data_dir
from kitden.local_gateway.settings import remove_server_steps, rule_step, strict_step
from kitden.model import Change, ChangeState
from kitden.views.inventory import build_inventory, default_adapters
from kitden.views.setup_server import with_entry
from tests.conftest import make_home, write_cursor_fixture_state
from tests.contract.conftest import SIGNALS, need_command, need_kitden, session

pytestmark = [pytest.mark.contract, pytest.mark.anyio]

ECHO = Path(__file__).parents[1] / "fixtures/fake_mcp/echo_server.py"
SERVER = "echo"
ENTRY = {"command": sys.executable, "args": [str(ECHO), SERVER]}
TOOLS = {"echo", "slow", "clash", "refuse", "where"}
READ_ONLY = {"show_setup", "list_findings", "explain_item", "list_projects"}
FILES = [".claude.json", ".codex/config.toml", ".cursor/mcp.json"]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def home(tmp_path, monkeypatch):
    need_command("claude", tmp_path)
    need_command("codex", tmp_path)
    need_kitden()
    for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        monkeypatch.delenv(name, raising=False)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def _env(home: Path) -> dict[str, str]:
    return {**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}


def _client(home: Path, name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [need_command(name, home), *args],
        env=_env(home),
        cwd=home,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def claude_get(home: Path, server: str) -> subprocess.CompletedProcess:
    return _client(home, "claude", "mcp", "get", server)


def codex_servers(home: Path) -> dict:
    done = _client(home, "codex", "mcp", "list", "--json")
    assert done.returncode == 0, done.stderr
    data = json.loads(done.stdout)
    return {s["name"]: s for s in (data if isinstance(data, list) else data.get("servers", []))}


def add_entries(home: Path) -> None:
    """The echo server as a user entry of each client, written in each client's file."""
    path = home / ".claude.json"
    data = json.loads(path.read_text())
    data.setdefault("mcpServers", {})[SERVER] = {"type": "stdio", **ENTRY}
    path.write_text(json.dumps(data, indent=2))
    config = home / ".codex/config.toml"
    args = ", ".join(json.dumps(a) for a in ENTRY["args"])
    lines = f"command = {json.dumps(ENTRY['command'])}\nargs = [{args}]"
    config.write_text(config.read_text() + f"\n[mcp_servers.{SERVER}]\n{lines}\n")
    path = home / ".cursor/mcp.json"
    data = json.loads(path.read_text())
    data["mcpServers"][SERVER] = ENTRY
    path.write_text(json.dumps(data, indent=2))


@cache
def engine(home: Path) -> Engine:
    """One engine per home: it keeps its changes, so Undo finds them."""
    return Engine(ChangeStore(data_dir(home)), CommandRunner(home))


def run(home: Path, action: str, steps) -> Change:
    change = engine(home).preview(action, steps)
    engine(home).apply(change.id)
    assert change.state is ChangeState.VERIFIED, change.error
    return change


def move(home: Path) -> Change:
    """Give each client the echo server, then move it into the gateway."""
    add_entries(home)
    return move_in(home)


def move_in(home: Path) -> Change:
    """Move the echo server out of all three clients into the gateway, as the page does."""
    inventory = build_inventory(home)
    items = [i for i in inventory.items if str(i.kind) == "mcp_server" and i.name == SERVER]
    assert {i.client for i in items} == {"claude_code", "codex", "cursor"}
    steps = local_move_steps(
        {a.id: a for a in default_adapters(home)},
        items,
        home,
        [p.path for p in inventory.projects],
        need_kitden(),
        added_clients=with_entry(inventory),
    )
    return run(home, "gateway.move", steps)


def project(home: Path) -> Path:
    """The fixture's project work/website, as Kitden knows it."""
    paths = [p.path for p in build_inventory(home).projects if p.path.endswith("work/website")]
    assert len(paths) == 1, paths
    return Path(paths[0])


def elsewhere(home: Path) -> Path:
    folder = home / "work/elsewhere"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


async def offered(home: Path, folder: Path, client: str) -> set[str]:
    async with session(home, folder, client) as opened:
        return {t.name for t in (await opened.list_tools()).tools} - READ_ONLY


def text(result) -> str:
    return result.content[0].text


async def test_a_moved_server_is_what_each_client_lists_and_its_tools_come_through(home):
    command = need_kitden()
    move(home)

    got = claude_get(home, "kitden")
    assert got.returncode == 0 and command in got.stdout, got.stdout + got.stderr
    assert claude_get(home, SERVER).returncode != 0
    servers = codex_servers(home)
    assert servers["kitden"]["transport"]["command"] == command
    assert SERVER not in servers
    cursor = json.loads((home / ".cursor/mcp.json").read_text())["mcpServers"]
    assert cursor["kitden"]["command"] == command and SERVER not in cursor

    for client in SIGNALS:
        async with session(home, project(home), client) as opened:
            names = {t.name for t in (await opened.list_tools()).tools}
            said = await opened.call_tool("echo", {"text": "hello"})
        assert names == READ_ONLY | TOOLS, client
        assert not said.is_error and text(said) == "hello", client


@pytest.mark.parametrize("client", list(SIGNALS))
async def test_a_tool_off_for_the_project_is_gone_there_and_stays_elsewhere(home, client):
    move(home)
    website = project(home)
    run(home, "gateway.rule", [rule_step(home, str(website), SERVER, "clash", "off")])

    assert await offered(home, website, client) == TOOLS - {"clash"}
    assert await offered(home, elsewhere(home), client) == TOOLS


@pytest.mark.parametrize("client", list(SIGNALS))
async def test_strict_mode_offers_only_the_tools_set_on(home, client):
    move(home)
    steps = [
        strict_step(home, SERVER, True),
        rule_step(home, None, SERVER, "echo", "on"),
        rule_step(home, None, SERVER, "where", "on"),
    ]
    run(home, "gateway.strict", steps)

    async with session(home, project(home), client) as opened:
        names = {t.name for t in (await opened.list_tools()).tools} - READ_ONLY
        allowed = await opened.call_tool("echo", {"text": "hi"})
        refused = await opened.call_tool("clash", {})
    assert names == {"echo", "where"}
    assert not allowed.is_error and text(allowed) == "hi"
    # A tool strict mode leaves off is not offered, and a call to it gets Kitden's words.
    assert refused.is_error and text(refused) == "clash is turned off in Kitden."


async def test_an_open_session_is_refused_a_tool_turned_off_and_gets_it_back(home):
    move(home)
    async with session(home, project(home), "claude_code") as opened:
        await opened.list_tools()
        before = await opened.call_tool("echo", {"text": "hi"})
        off = run(home, "gateway.rule", [rule_step(home, None, SERVER, "echo", "off")])
        refused = await opened.call_tool("echo", {"text": "hi"})
        engine(home).undo(off.id)
        assert off.state is ChangeState.UNDONE, off.error
        back = await opened.call_tool("echo", {"text": "hi"})

    assert not before.is_error and text(before) == "hi"
    assert refused.is_error and text(refused) == "echo is turned off in Kitden."
    assert not back.is_error and text(back) == "hi"


async def test_undo_puts_every_file_back_and_the_clients_list_the_server_again(home):
    add_entries(home)
    before = {name: (home / name).read_bytes() for name in FILES}
    change = move_in(home)
    assert {name: (home / name).read_bytes() for name in FILES} != before

    engine(home).undo(change.id)
    assert change.state is ChangeState.UNDONE, change.error
    assert {name: (home / name).read_bytes() for name in FILES} == before

    got = claude_get(home, SERVER)
    assert got.returncode == 0 and str(ECHO) in got.stdout, got.stdout + got.stderr
    servers = codex_servers(home)
    assert SERVER in servers and "kitden" not in servers


async def test_a_server_put_back_and_removed_from_the_gateway(home):
    move(home)
    adapters = {a.id: a for a in default_adapters(home)}
    async with session(home, project(home), "claude_code") as opened:
        await opened.list_tools()
        before = await opened.call_tool("echo", {"text": "hi"})
        steps = [
            *put_back_steps(adapters, home, SERVER, ["claude_code"]),
            *remove_server_steps(home, SERVER),
        ]
        run(home, "gateway.move_out", steps)
        refused = await opened.call_tool("echo", {"text": "hi"})

    assert not before.is_error and text(before) == "hi"
    assert refused.is_error and text(refused) == "echo is turned off in Kitden."
    got = claude_get(home, SERVER)
    assert got.returncode == 0 and str(ECHO) in got.stdout, got.stdout + got.stderr
    assert SERVER not in codex_servers(home)
