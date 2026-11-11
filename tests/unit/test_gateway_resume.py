"""The gateway moves to a new Kitden in the same process, so the agent's pipe stays open.

The Tap tests feed it over plain OS pipes and play the MCP server by hand. The last tests start
a real `kitden mcp` and restart it in place once, through a marker as the page writes it.
"""

import json
import os
import shlex
import stat
import subprocess
import sys
from pathlib import Path

import anyio
import mcp_types as types
import pytest
from mcp import Client, StdioServerParameters
from mcp.shared.message import SessionMessage
from mcp_types import ListRootsResult, Root

from kitden import __version__, mcp_server
from kitden.gateways import data_dir, private_data_dir
from kitden.local_gateway import resume
from kitden.local_gateway.resume import Tap, wait_for_update
from kitden.local_gateway.settings import SETTINGS_FILE
from kitden.update import install
from kitden.update.run import write_marker
from tests.conftest import make_home

pytestmark = pytest.mark.anyio
ECHO = Path(__file__).parents[1] / "fixtures/fake_mcp/echo_server.py"
INIT = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "agent", "version": "1"},
    },
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
LIST_CHANGED = {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}


@pytest.fixture
def anyio_backend():
    return "asyncio"


def request(id, method="tools/list"):
    return {"jsonrpc": "2.0", "id": id, "method": method}


def reply(id):
    return SessionMessage(types.JSONRPCResponse(jsonrpc="2.0", id=id, result={}))


class Agent:
    """The agent's ends of the two pipes, with a Tap on the other ends."""

    def __init__(self, saved=None):
        self.tap_in, self.send_fd = os.pipe()
        self.read_fd, self.tap_out = os.pipe()
        self.tap = Tap(self.tap_in, self.tap_out, saved)
        self.got = b""

    def send(self, *messages, raw=b""):
        data = b"".join(json.dumps(m).encode() + b"\n" for m in messages) + raw
        os.write(self.send_fd, data)

    async def receive(self):
        """The next line the Tap wrote to the agent."""
        with anyio.fail_after(5):
            while b"\n" not in self.got:
                await anyio.wait_readable(self.read_fd)
                self.got += os.read(self.read_fd, 65536)
        line, self.got = self.got.split(b"\n", 1)
        return json.loads(line)

    async def to_server(self):
        """The next message the server reads."""
        with anyio.fail_after(5):
            item = await self.tap.server_read.receive()
        assert isinstance(item, SessionMessage)
        return item.message

    async def answer(self, id):
        await self.tap.server_write.send(reply(id))
        assert (await self.receive())["id"] == id

    def unread(self):
        """What is still waiting in the pipe to the Tap."""
        os.set_blocking(self.tap_in, False)
        try:
            return os.read(self.tap_in, 65536)
        except BlockingIOError:
            return b""


async def running(agent, body):
    async with anyio.create_task_group() as group:
        group.start_soon(agent.tap.read_pipe)
        group.start_soon(agent.tap.write_pipe)
        await body()
        group.cancel_scope.cancel()


async def test_a_request_is_busy_until_its_reply():
    agent = Agent()

    async def body():
        agent.send(INIT)
        assert (await agent.to_server()).method == "initialize"
        assert agent.tap.busy == 1
        await agent.answer(0)
        assert agent.tap.busy == 0
        agent.send(request(1), request(2))
        await agent.to_server()
        await agent.to_server()
        assert agent.tap.busy == 2
        await agent.tap.server_write.send(
            SessionMessage(
                types.JSONRPCError(
                    jsonrpc="2.0", id=1, error=types.ErrorData(code=-1, message="no")
                )
            )
        )
        assert (await agent.receive())["id"] == 1
        assert agent.tap.busy == 1
        # A cancelled request is never answered.
        agent.send(
            {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 2}}
        )
        await agent.to_server()
        assert agent.tap.busy == 0

    await running(agent, body)


async def test_the_tap_keeps_the_first_initialize_and_initialized():
    agent = Agent()

    async def body():
        agent.send(INIT, INITIALIZED, request(1), {**INIT, "id": 9})
        for _ in range(4):
            await agent.to_server()
        saved = agent.tap.saved()
        assert json.loads(saved["init"]) == INIT
        assert json.loads(saved["initialized"]) == INITIALIZED

    await running(agent, body)


async def test_a_resumed_tap_replays_the_handshake_and_drops_only_its_reply():
    saved = {"init": json.dumps(INIT), "initialized": json.dumps(INITIALIZED)}
    agent = Agent(saved)

    async def body():
        assert (await agent.to_server()).method == "initialize"
        assert (await agent.to_server()).method == "notifications/initialized"
        assert agent.tap.busy == 0
        await agent.tap.server_write.send(reply(0))
        assert await agent.receive() == LIST_CHANGED
        agent.send(request(0, "ping"), request(5))
        await agent.to_server()
        await agent.to_server()
        await agent.answer(0)  # a later reply with the same id reaches the agent
        await agent.answer(5)
        # The next image gets the same handshake again.
        assert agent.tap.saved() == saved

    await running(agent, body)


async def test_stop_waits_for_open_requests_and_answers_those_that_come_meanwhile():
    agent = Agent()

    async def body():
        agent.send(INIT)
        await agent.to_server()
        async with anyio.create_task_group() as group:
            group.start_soon(agent.tap.stop_when_idle)
            await anyio.sleep(0.05)
            agent.send(request(1))  # comes while the restart waits: this image answers it
            assert (await agent.to_server()).id == 1
            await agent.answer(0)
            await anyio.sleep(0.05)
            assert not agent.tap.stopped.is_set()
            await agent.answer(1)
        assert agent.tap.stopped.is_set()
        with pytest.raises(anyio.EndOfStream):
            await agent.tap.server_read.receive()
        # After the stop the pipe is not read: the next image reads what comes now.
        agent.send(request(2))
        await anyio.sleep(0.05)
        assert json.loads(agent.unread()) == request(2)

    await running(agent, body)


async def test_stop_waits_for_a_whole_line():
    agent = Agent()

    async def body():
        agent.send(raw=b'{"jsonrpc": "2.0", "method": "notifications/')
        await anyio.sleep(0.05)
        async with anyio.create_task_group() as group:
            group.start_soon(agent.tap.stop_when_idle)
            await anyio.sleep(0.05)
            assert not agent.tap.stopped.is_set()
            agent.send(raw=b'roots/list_changed"}\n')
        assert (await agent.to_server()).method == "notifications/roots/list_changed"
        assert agent.tap.saved() == {"init": None, "initialized": None}

    await running(agent, body)


async def test_the_agent_leaving_ends_the_server():
    agent = Agent()

    async def body():
        os.close(agent.send_fd)
        with pytest.raises(anyio.EndOfStream):
            with anyio.fail_after(5):
                await agent.tap.server_read.receive()
        assert agent.tap.ended
        assert not agent.tap.stopped.is_set()

    await running(agent, body)


async def test_replies_still_go_out_after_the_agent_closes_its_input():
    agent = Agent()

    async def body():
        agent.send(INIT, request(1))
        os.close(agent.send_fd)  # as `printf ... | kitden mcp` does
        await agent.to_server()
        await agent.to_server()
        with pytest.raises(anyio.EndOfStream):
            with anyio.fail_after(5):
                await agent.tap.server_read.receive()
        await agent.answer(0)
        await agent.answer(1)
        with anyio.move_on_after(0.1):
            await agent.tap.stop_when_idle()
        assert not agent.tap.stopped.is_set()  # no restart once the input ended

    await running(agent, body)


def launcher_at(path):
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


async def test_wait_for_update_returns_the_launcher_of_a_new_version(tmp_path):
    launcher = launcher_at(tmp_path / "kitden")
    agent = Agent()
    found = []

    async def body():
        async with anyio.create_task_group() as group:

            async def watch():
                found.append(await wait_for_update(tmp_path, __version__, agent.tap, every=0.01))

            group.start_soon(watch)
            await anyio.sleep(0.05)
            write_marker(tmp_path, "99.0.0", launcher)
        assert found == [str(launcher)]
        assert agent.tap.stopped.is_set()

    await running(agent, body)


async def test_wait_for_update_waits_while_a_request_is_open(tmp_path):
    launcher = launcher_at(tmp_path / "kitden")
    agent = Agent()
    found = []

    async def body():
        agent.send(INIT)
        await agent.to_server()
        async with anyio.create_task_group() as group:

            async def watch():
                found.append(await wait_for_update(tmp_path, __version__, agent.tap, every=0.01))

            group.start_soon(watch)
            await anyio.sleep(0.05)
            write_marker(tmp_path, "99.0.0", launcher)
            await anyio.sleep(0.1)
            assert found == []
            await agent.answer(0)
        assert found == [str(launcher)]

    await running(agent, body)


@pytest.mark.parametrize("case", ["no launcher", "same version", "there at start", "broken"])
async def test_wait_for_update_keeps_running(tmp_path, case):
    launcher = launcher_at(tmp_path / "kitden")
    if case == "there at start":
        write_marker(tmp_path, "99.0.0", launcher)
    agent = Agent()

    async def body():
        async with anyio.create_task_group() as group:
            group.start_soon(wait_for_update, tmp_path, __version__, agent.tap, 0.01)
            await anyio.sleep(0.05)
            if case == "no launcher":
                write_marker(tmp_path, "99.0.0", tmp_path / "gone")
            elif case == "same version":
                write_marker(tmp_path, __version__, launcher)
            elif case == "broken":
                (private_data_dir(tmp_path) / "updated.json").write_text("{")
            await anyio.sleep(0.15)
            assert not agent.tap.stopped.is_set()
            group.cancel_scope.cancel()

    await running(agent, body)


@pytest.mark.parametrize("read_only", [False, True])
def test_without_an_install_kitden_mcp_runs_as_before(tmp_path, monkeypatch, read_only):
    monkeypatch.setattr(install, "detect", lambda: None)
    monkeypatch.delenv(resume.RESUME, raising=False)
    ran = []
    monkeypatch.setattr(resume, "serve_stdio", lambda *args: ran.append("resumable"))
    monkeypatch.setattr(mcp_server.MCPServer, "run", lambda self: ran.append("plain"))
    mcp_server.run(make_home(tmp_path, "claude_code/2.1.283"), read_only=read_only)
    assert ran == ["plain"]


@pytest.mark.parametrize("held", [False, True])
def test_with_an_install_kitden_mcp_watches_for_updates(tmp_path, monkeypatch, held):
    home = make_home(tmp_path, "claude_code/2.1.283")
    if held:
        write_settings(home, "echo-unused")
    monkeypatch.setattr(install, "detect", lambda: install.Install("uv", tmp_path / "k", ()))
    monkeypatch.setattr(sys, "argv", ["kitden", "mcp"])
    monkeypatch.setattr(resume, "stdin_can_wait", lambda: True)  # pytest's stdin is no pipe
    calls = []
    monkeypatch.setattr(resume, "serve_stdio", lambda *args: calls.append(args))
    mcp_server.run(home)
    [(make, root, argv, watch)] = calls
    server = make()
    assert (root, argv, watch) == (home, ["mcp"], True)
    options = server.create_initialization_options()
    assert options.server_name == "kitden"


# The first image: `kitden mcp` as a uv tool install would run it, checking every 0.05 s.
FIRST = """
import os, sys
from pathlib import Path
from kitden.local_gateway import resume
from kitden.update import install
pid_file, launcher, *args = sys.argv[1:]
Path(pid_file).write_text(str(os.getpid()))
install.detect = lambda: install.Install("uv", Path(launcher), ())
resume.EVERY = 0.05
sys.argv = ["kitden", *args]
from kitden.cli import main
sys.exit(main(args))
"""


def write_settings(home, tag):
    path = data_dir(home) / SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"command": sys.executable, "args": [str(ECHO), tag]}
    path.write_text(json.dumps({"servers": {"echo": entry}, "rules": {}}))


def children_named(tag):
    found = subprocess.run(["pgrep", "-f", tag], capture_output=True, text=True).stdout
    return found.split()


def restartable(tmp_path, home, shebang=None):
    """A client for `kitden mcp` on `home`, a launcher that starts the same code, and the files
    that hold the pid before and after the restart."""
    before, after = tmp_path / "pid-before", tmp_path / "pid-after"
    launcher = tmp_path / "bin/kitden"
    launcher.parent.mkdir()
    launcher.write_text(
        f"{shebang or '#!/bin/sh'}\necho $$ > {shlex.quote(str(after))}\n"
        f'exec {shlex.quote(sys.executable)} -m kitden "$@"\n'
    )
    launcher.chmod(0o755)
    changed = anyio.Event()

    async def listen(message):
        if getattr(message, "method", "") == "notifications/tools/list_changed":
            changed.set()

    async def roots(context):
        return ListRootsResult(roots=[Root(uri=(home / "work/website").as_uri())])

    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", FIRST, str(before), str(launcher), "mcp", "--home", str(home)],
        cwd=home,
    )
    client = Client(
        params,
        mode="legacy",
        message_handler=listen,
        list_roots_callback=roots,
        read_timeout_seconds=30,
    )
    return client, launcher, before, after, changed


def text(result):
    return result.content[0].text


async def test_the_plain_gateway_restarts_in_place(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    client, launcher, before, after, changed = restartable(tmp_path, home)
    async with client:
        tools = client.server_capabilities.tools
        assert tools is not None and tools.list_changed  # so the agent heeds the note
        names = {t.name for t in (await client.list_tools()).tools}
        write_marker(home, "99.0.0", launcher)
        with anyio.fail_after(15):
            await changed.wait()
        assert after.read_text().strip() == before.read_text()
        assert {t.name for t in (await client.list_tools()).tools} == names
        assert not (await client.call_tool("list_projects", {})).is_error


async def test_the_gateway_with_servers_restarts_after_a_running_call(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    tag = f"echo-{os.getpid()}-{tmp_path.name}"
    write_settings(home, tag)
    client, launcher, before, after, changed = restartable(tmp_path, home)
    waiting = tmp_path / "waiting"
    async with client:
        assert text(await client.call_tool("echo", {"text": "hi"})) == "hi"
        assert children_named(tag)
        async with anyio.create_task_group() as group:
            answers = []

            async def slow():
                answers.append(
                    text(await client.call_tool("slow", {"seconds": 1, "note": str(waiting)}))
                )

            group.start_soon(slow)
            with anyio.fail_after(10):
                while not waiting.exists():
                    await anyio.sleep(0.02)
            write_marker(home, "99.0.0", launcher)
            await anyio.sleep(0.3)
            assert not changed.is_set()  # the call still runs in the old image
        assert answers == ["done"]
        with anyio.fail_after(15):
            await changed.wait()
        assert after.read_text().strip() == before.read_text()
        assert children_named(tag) == []  # the held server stopped before the exec
        assert text(await client.call_tool("echo", {"text": "again"})) == "again"


async def test_a_launcher_that_cannot_start_keeps_the_gateway_running(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    client, launcher, _, after, changed = restartable(tmp_path, home, "#!/no/such/shell")
    async with client:
        await client.list_tools()
        write_marker(home, "99.0.0", launcher)
        with anyio.fail_after(15):
            await changed.wait()
        assert not after.exists()
        assert not (await client.call_tool("list_projects", {})).is_error


def run_first(tmp_path, stdin=None, data=None):
    """`kitden mcp` from a uv tool install, with the given stdin (or `data` through a pipe that
    closes at once), until it ends by itself."""
    home = make_home(tmp_path, "claude_code/2.1.283")
    launcher = launcher_at(tmp_path / "kitden")
    args = ["-c", FIRST, str(tmp_path / "pid"), str(launcher), "mcp", "--home", str(home)]
    done = subprocess.run(
        [sys.executable, *args], stdin=stdin, input=data, capture_output=True, timeout=30, cwd=home
    )
    return done.returncode, [json.loads(line) for line in done.stdout.splitlines()]


HANDSHAKE = b"".join(json.dumps(m).encode() + b"\n" for m in (INIT, INITIALIZED, request(1)))


# At the end of input the SDK's server ends and cancels what still runs (mcp 2.3.0, checked
# 2026-11-11: as before, tools/list here is mostly not answered). `initialize` runs inline, so
# its reply always comes; the Tap test above covers a reply the server sends after the end.
def test_input_closed_at_once_still_gets_its_replies(tmp_path):
    code, replies = run_first(tmp_path, data=HANDSHAKE)
    assert code == 0
    assert [r.get("id") for r in replies][:1] == [0]
    assert replies[0]["result"]["capabilities"]["tools"]["listChanged"] is True


def test_stdin_from_dev_null_ends_quietly(tmp_path):
    with open(os.devnull, "rb") as nothing:
        assert run_first(tmp_path, nothing) == (0, [])


def test_stdin_from_a_file_is_answered(tmp_path):
    requests = tmp_path / "requests.jsonl"
    requests.write_bytes(HANDSHAKE)
    with requests.open("rb") as given:
        code, replies = run_first(tmp_path, given)
    assert code == 0
    assert [r.get("id") for r in replies][:1] == [0]
    assert replies[0]["result"]["capabilities"]["tools"]["listChanged"] is False  # as before
