"""`kitden mcp` moves to a new Kitden in the same process, so the agent's pipe stays open.

After an update from the page, the page writes `updated.json` in Kitden's data folder. A gateway
from a uv tool or Homebrew install checks that file every 5 seconds. When it names another
version and its launcher exists, the gateway waits until no request is open, stops its MCP
server (the servers it runs behind the gateway stop with it), and execs the launcher with the
same arguments. The new image gets the saved `initialize` request and `initialized` note in
KITDEN_RESUME, replays them to its own server, drops the reply, sends
`notifications/tools/list_changed` and then reads the pipe as usual.

Requests that come while the gateway waits are answered by the old image. The pipe is not read
after the stop, so what the agent sends then waits in the pipe for the new image.

The SDK's `stdio_server()` cannot do this (mcp 2.3.0, checked 2026-11-11): its reader runs in a
thread that cannot be stopped, it keeps read bytes in a hidden buffer, and it gives the wire back
to fd 0 and 1 only when it exits. So this file has its own stdio transport, the Tap. Like the
SDK, it serves the wire from private copies of fd 0 and 1, and points 0 at /dev/null and 1 at
stderr so that stray output and child servers cannot reach the wire.
"""

import fcntl
import json
import math
import os
import stat
import sys
from collections.abc import Callable
from pathlib import Path

import anyio
import anyio.to_thread
import mcp_types as types
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.shared.message import SessionMessage

from kitden import __version__
from kitden.gateways import data_dir
from kitden.update.run import MARKER

RESUME = "KITDEN_RESUME"
EVERY = 5.0  # seconds between two looks at the marker
LIST_CHANGED = types.JSONRPCNotification(jsonrpc="2.0", method="notifications/tools/list_changed")


class Tap:
    """The stdio transport between the agent's pipe and the MCP server.

    It keeps the first `initialize` request and `initialized` note, and counts the agent's
    requests that have no reply yet (`busy`). Given the saved two, it replays them and drops the
    reply to the replayed `initialize`, sending `notifications/tools/list_changed` instead.
    """

    def __init__(self, wire_in: int, wire_out: int, saved: dict | None = None) -> None:
        self.wire_in = wire_in
        self.wire_out = wire_out
        self.to_server, self.server_read = anyio.create_memory_object_stream[
            SessionMessage | Exception
        ](math.inf)
        self.server_write, self.from_server = anyio.create_memory_object_stream[SessionMessage](0)
        self.init: str | None = None
        self.initialized: str | None = None
        self.open: set[types.RequestId] = set()  # the agent's requests without a reply
        self.rest = b""  # read bytes that are not a whole line yet
        self.want_stop = False
        self.stopped = anyio.Event()
        self.written = anyio.Event()  # the server ended and its output is on the wire
        self.ended = False  # the agent's input ended (or its output broke): no restart now
        self.broken = False  # writing to the agent failed: nothing more goes out
        self.drop: types.RequestId | None = None
        if saved and saved.get("init"):
            self.init, self.initialized = saved["init"], saved.get("initialized")
            message = _parse(saved["init"])
            self.drop = getattr(message, "id", None)
            # The SDK runs `initialize` inline and parks what comes before it is done
            # (mcp/server/runner.py, checked 2026-11-11), so the note can follow at once.
            self.to_server.send_nowait(SessionMessage(message))
            if self.initialized:
                self.to_server.send_nowait(SessionMessage(_parse(self.initialized)))

    @property
    def busy(self) -> int:
        return len(self.open)

    def saved(self) -> dict:
        """What the next image needs: the handshake, nothing else."""
        return {"init": self.init, "initialized": self.initialized}

    async def stop_when_idle(self) -> None:
        """End the server's input as soon as no request is open and no line is half read."""
        self.want_stop = True
        self._maybe_stop()
        await self.stopped.wait()

    async def read_pipe(self) -> None:
        """Read the pipe in the event loop, so nothing is read after the stop."""
        while True:
            await anyio.wait_readable(self.wire_in)
            if self.stopped.is_set():
                return
            data = os.read(self.wire_in, 65536)
            if not data:
                if self.rest.strip():
                    self._take(self.rest.decode("utf-8", "replace"))
                self.ended = True  # the server still answers what it has
                self.to_server.close()
                return
            *lines, self.rest = (self.rest + data).split(b"\n")
            for line in lines:
                if line.strip():
                    self._take(line.decode("utf-8", "replace"))
            self._maybe_stop()

    async def write_pipe(self) -> None:
        async with self.from_server:
            async for item in self.from_server:
                message = item.message
                if isinstance(message, types.JSONRPCResponse | types.JSONRPCError):
                    if self.drop is not None and message.id == self.drop:
                        self.drop = None
                        message = LIST_CHANGED
                    else:
                        self.open.discard(message.id)
                await self._write(message)
                self._maybe_stop()
        self.written.set()

    def _take(self, line: str) -> None:
        try:
            message = _parse(line)
        except Exception as error:  # noqa: BLE001 - as the SDK's reader: the server answers it
            self.to_server.send_nowait(error)
            return
        if isinstance(message, types.JSONRPCRequest):
            if message.method == "initialize" and self.init is None:
                self.init = line
            self.open.add(message.id)
        elif isinstance(message, types.JSONRPCNotification):
            if message.method == "notifications/initialized" and self.initialized is None:
                self.initialized = line
            elif message.method == "notifications/cancelled":
                # The SDK never answers a cancelled request (shared/jsonrpc_dispatcher.py).
                self.open.discard((message.params or {}).get("requestId"))
        self.to_server.send_nowait(SessionMessage(message))

    def _maybe_stop(self) -> None:
        idle = not self.open and not self.rest.strip()
        if self.want_stop and idle and not self.ended and not self.stopped.is_set():
            self.stopped.set()
            self.to_server.close()  # the server ends as on EOF

    async def _write(self, message: types.JSONRPCMessage) -> None:
        if self.broken:
            return
        # The same form as the SDK's stdio writer (mcp/server/stdio.py, checked 2026-11-11).
        data = (message.model_dump_json(by_alias=True, exclude_unset=True) + "\n").encode()
        try:
            await anyio.to_thread.run_sync(self._write_all, data)
        except OSError:
            self.broken = self.ended = True  # the agent is gone; the server ends
            self.to_server.close()

    def _write_all(self, data: bytes) -> None:
        while data:
            data = data[os.write(self.wire_out, data) :]


def _parse(line: str) -> types.JSONRPCMessage:
    return types.jsonrpc_message_adapter.validate_json(line, by_name=False)


async def wait_for_update(home: Path, running: str, tap: Tap, every: float = EVERY) -> str:
    """The launcher of the new version, once `updated.json` changes to name a version other
    than `running` with a launcher that exists, and the Tap has stopped with no request open.
    A marker that is already there at the start does not count."""
    path = data_dir(home) / MARKER
    first = _read(path)
    while True:
        await anyio.sleep(every)
        now = _read(path)
        launcher = _launcher(now, running) if now != first else None
        if launcher:
            break
    await tap.stop_when_idle()
    return launcher


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _launcher(raw: bytes | None, running: str) -> str | None:
    try:
        record = json.loads(raw or b"")
        version, launcher = record["version"], record["launcher"]
    except (ValueError, TypeError, KeyError):
        return None
    if not isinstance(launcher, str) or version == running:
        return None
    return launcher if os.path.isfile(launcher) and os.access(launcher, os.X_OK) else None


def stdin_can_wait(fd: int = 0) -> bool:
    """An agent gives a pipe or a socket, which the Tap waits on in the event loop. A terminal,
    /dev/null or a file runs as before (kqueue and epoll refuse the last two)."""
    try:
        mode = os.fstat(fd).st_mode
    except OSError:
        return False
    return stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode)


def serve_stdio(
    make_server: Callable[[], Server], home: Path, argv: list[str], watch: bool
) -> None:
    """Serve over stdio until the agent closes the pipe. With `watch`, move to a new version
    when the page updates Kitden. If the launcher cannot start, go on in this process."""
    saved_text = os.environ.pop(RESUME, None)  # the servers it starts must not get it
    saved = json.loads(saved_text) if saved_text else None
    while True:
        wire_in = _claim(0, os.open(os.devnull, os.O_RDONLY))
        wire_out = _claim(1, os.dup(2))
        tap, launcher = anyio.run(_serve, make_server(), wire_in, wire_out, saved, home, watch)
        _give_back(wire_in, wire_out)
        if launcher is None:
            return
        env = {**os.environ, RESUME: json.dumps(tap.saved())}
        try:
            os.execve(launcher, [launcher, *argv], env)  # noqa: S606 - Kitden's own launcher
        except OSError as error:
            print(f"Kitden could not start {launcher}: {error}", file=sys.stderr, flush=True)
            saved, watch = tap.saved(), False


async def _serve(
    server: Server, wire_in: int, wire_out: int, saved: dict | None, home: Path, watch: bool
) -> tuple[Tap, str | None]:
    tap = Tap(wire_in, wire_out, saved)
    found: list[str] = []
    done = anyio.Event()

    async def watch_marker() -> None:
        found.append(await wait_for_update(home, __version__, tap, EVERY))
        done.set()

    async with anyio.create_task_group() as group:
        group.start_soon(tap.read_pipe)
        group.start_soon(tap.write_pipe)
        if watch:
            group.start_soon(watch_marker)
        # The capability must be in the first `initialize` reply: the agent keeps that one.
        options = server.create_initialization_options(NotificationOptions(tools_changed=True))
        await server.run(tap.server_read, tap.server_write, options)
        await tap.written.wait()  # Server.run closes its write stream; the writer drains it
        if tap.stopped.is_set():
            await done.wait()  # only wait_for_update stops the Tap
        group.cancel_scope.cancel()
    return tap, found[0] if tap.stopped.is_set() and not tap.ended else None


def _claim(fd: int, diversion: int) -> int:
    """Serve the wire from a private copy of `fd` that children do not get; point `fd` at
    `diversion`."""
    private = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 3)
    os.dup2(diversion, fd)
    os.close(diversion)
    return private


def _give_back(wire_in: int, wire_out: int) -> None:
    """Put the wire back on fd 0 and 1, where the next image looks for it."""
    sys.stdout.flush()  # text printed while fd 1 pointed at stderr must not reach the wire
    sys.stderr.flush()
    os.dup2(wire_in, 0)
    os.dup2(wire_out, 1)
    os.close(wire_in)
    os.close(wire_out)
