"""The gateway inside `kitden mcp`: the tools of the servers moved into it, per project.

A client starts `kitden mcp` once per session. When the gateway settings hold servers, it offers
Kitden's own read-only tools and the tools turned on for the session's project, under names that
are unique and short enough for every client. It finds the project and the tool list at the
first `tools/list` and keeps them for the session. A server starts when one of its tools is first
called, or at that first `tools/list` when its tool list is not known yet.

MCP SDK facts this relies on (mcp 2.3.0, checked 2026-10-21):
- `MCPServer` keeps its low-level server in a private attribute. So the gateway is its own
  low-level `Server` with `on_list_tools` and `on_call_tool`, and it reaches Kitden's own tools
  through the public `MCPServer.list_tools()` and `MCPServer.call_tool()`.
- The server handles each request in its own task, so a slow call does not hold up the others.
- `ServerSession.list_roots()` warns on every call that roots are deprecated (protocol
  2026-07-28); the gateway sends the same `roots/list` request with `send_request`.
- `Client` with `StdioServerParameters` puts the given env over HOME, LOGNAME, PATH, SHELL, TERM
  and USER of this process.
"""

import hashlib
import logging
import os
import sys
from collections.abc import Callable, Iterable
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Any

import anyio
import anyio.to_thread
import httpx2
from anyio.abc import TaskGroup, TaskStatus
from mcp import Client, MCPError, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.server import Server
from mcp.server.context import ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.server.stdio import stdio_server
from mcp_types import (
    CallToolRequestParams,
    CallToolResult,
    InputRequiredResult,
    ListRootsRequest,
    ListRootsResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from kitden.local_gateway.project import find_project
from kitden.local_gateway.settings import (
    allowed_tools,
    load_settings,
    load_tools,
    save_tools,
    servers_on,
)

START_TIMEOUT = 20  # seconds for a server to start and list its tools; Claude Code waits 30
CALL_TIMEOUT = 300  # seconds for one tool call
ROOTS_TIMEOUT = 5  # seconds for the client to name its roots
NAME_LIMIT = 54  # Cursor allows 60 characters for server and tool; the entry is named "kitden"
PLACEHOLDERS = ("${workspaceFolder}", "${CLAUDE_PROJECT_DIR}", "${CLAUDE_PROJECT_DIR:-.}")

# The HTTP library logs each request with its full address, and the MCP client logs some failures
# with addresses too; an address may hold a token. The gateway prints its own plain line instead.
for _logger in ("httpx2", "mcp.client"):
    logging.getLogger(_logger).setLevel(logging.CRITICAL)


def exposed_names(
    allowed: dict[str, list[dict]], taken: Iterable[str] = ()
) -> dict[str, tuple[str, str]]:
    """The name each allowed tool is offered under → (server, tool).

    Servers go in name order. A tool keeps its name unless an earlier server has it or the name is
    `taken` (Kitden's own tools); then it gets `<server>_` in front. A name over 54 characters
    becomes its first 45 characters, "_" and the first 8 hex characters of its SHA-1.
    """
    names: dict[str, tuple[str, str]] = {}
    used = set(taken)
    for server in sorted(allowed):
        for tool in allowed[server]:
            name = tool["name"]
            if name in used:
                name = f"{server}_{name}"
            if len(name) > NAME_LIMIT:
                digest = hashlib.sha1(name.encode(), usedforsecurity=False).hexdigest()
                name = f"{name[:45]}_{digest[:8]}"
            names[name] = (server, tool["name"])
            used.update((tool["name"], name))
    return names


class UpstreamError(Exception):
    """A server could not start or answer. The message is one plain sentence with no secrets."""


def _say(text: str) -> None:
    """One plain line on stderr, which the client keeps in its log."""
    print(text, file=sys.stderr, flush=True)


def _error(text: str) -> CallToolResult:
    _say(text)
    return CallToolResult(content=[TextContent(type="text", text=text)], is_error=True)


def _fill(arg: str, folder: str) -> str:
    for placeholder in PLACEHOLDERS:
        arg = arg.replace(placeholder, folder)
    return arg


class Upstreams:
    """The servers in the gateway, for one gateway process or one listing on the page.

    Use it as `async with Upstreams(home, settings) as upstreams:`. A server starts on its first
    use and runs until the block ends. Set `project` before the first use: a local server runs in
    that folder (or the home folder), and it fills the project placeholders in the arguments.
    """

    def __init__(self, home: Path, settings: dict, project: str | None = None) -> None:
        self.home = home
        self.settings = settings
        self.project = project
        self._clients: dict[str, Client] = {}
        self._locks: dict[str, anyio.Lock] = {}
        self._group: TaskGroup | None = None

    async def __aenter__(self) -> "Upstreams":
        self._group = anyio.create_task_group()
        await self._group.__aenter__()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self._group.cancel_scope.cancel()
        await self._group.__aexit__(None, None, None)

    async def list_tools(self, server: str) -> list[dict]:
        """The server's tools as it lists them, within START_TIMEOUT seconds.

        Raises UpstreamError when the server does not start or answer.
        """
        try:
            with anyio.fail_after(START_TIMEOUT):
                client = await self._client(server)
                tools: list[dict] = []
                cursor = None
                while True:
                    page = await client.list_tools(cursor=cursor)
                    tools += [
                        t.model_dump(by_alias=True, mode="json", exclude_none=True)
                        for t in page.tools
                    ]
                    cursor = page.next_cursor
                    if not cursor:
                        return tools
        except UpstreamError as problem:
            sentence = str(problem)
        except TimeoutError:
            state = "answer" if server in self._clients else "start"
            sentence = f"{server} did not {state} in {START_TIMEOUT} seconds."
        except Exception:
            sentence = f"{server} did not list its tools."
        _say(sentence)
        raise UpstreamError(sentence)

    async def call(self, server: str, tool: str, arguments: dict[str, Any]) -> CallToolResult:
        """Call one tool. When that fails, the result is an error with one plain sentence."""
        try:
            with anyio.fail_after(START_TIMEOUT):
                client = await self._client(server)
        except UpstreamError as problem:
            return _error(str(problem))
        except TimeoutError:
            return _error(f"{server} did not start in {START_TIMEOUT} seconds.")
        try:
            with anyio.fail_after(CALL_TIMEOUT):
                return await client.call_tool(tool, arguments)
        except TimeoutError:
            return _error(f"{server} did not answer in {CALL_TIMEOUT} seconds.")
        except Exception:
            # The text of an error may hold the server's address; say it plainly instead.
            return _error(f"The call to {server} failed.")

    async def _client(self, server: str) -> Client:
        """The server's connection; the first use opens it. Only one opens at a time."""
        async with self._locks.setdefault(server, anyio.Lock()):
            client = self._clients.get(server)
            if client is None:
                try:
                    client = await self._group.start(self._serve, server)
                except Exception:
                    entry = self.settings["servers"].get(server)
                    verb = "reach" if isinstance(entry, dict) and entry.get("url") else "start"
                    raise UpstreamError(f"Kitden could not {verb} {server}.") from None
            return client

    async def _serve(self, server: str, *, task_status: TaskStatus[Client]) -> None:
        """Open the server's connection and hold it until the `async with` block ends.

        It runs in the group's own task: a connection must close in the task that opened it.
        """
        entry = self.settings["servers"][server]
        ready = False
        try:
            async with AsyncExitStack() as stack:
                target = await self._target(entry, stack)
                # The initialize handshake, which every server answers. Mode "auto" first asks
                # `server/discover`; a server that leaves it unanswered costs 10 s.
                client = await stack.enter_async_context(Client(target, mode="legacy"))
                self._clients[server] = client
                task_status.started(client)
                ready = True
                await anyio.sleep_forever()
        except Exception:
            if not ready:
                raise
            _say(f"{server} stopped.")
        finally:
            self._clients.pop(server, None)

    async def _target(self, entry: dict, stack: AsyncExitStack) -> Any:
        """How to reach a server: streamable HTTP for a `url`, else its command over stdio."""
        if entry.get("url"):
            headers = {str(k): str(v) for k, v in (entry.get("headers") or {}).items()}
            timeout = httpx2.Timeout(START_TIMEOUT, read=CALL_TIMEOUT)
            http = await stack.enter_async_context(
                httpx2.AsyncClient(headers=headers, timeout=timeout)
            )
            return streamable_http_client(str(entry["url"]), http_client=http)
        folder = self.project or str(self.home)
        return StdioServerParameters(
            command=entry["command"],
            args=[_fill(str(arg), folder) for arg in entry.get("args") or []],
            env=self._env(entry),
            cwd=folder,
        )

    def _env(self, entry: dict) -> dict[str, str]:
        """HOME, USER, LANG, the PATH saved when the server moved, and the server's own env."""
        env = {"HOME": str(self.home)}
        env.update({key: os.environ[key] for key in ("USER", "LANG") if key in os.environ})
        path = self.settings.get("path") or os.environ.get("PATH")
        if path:
            env["PATH"] = str(path)
        env.update({str(k): str(v) for k, v in (entry.get("env") or {}).items()})
        return env


def _tool(name: str, tool: dict) -> Tool:
    """An offered tool: the server's description and input schema under the offered name."""
    schema = tool.get("inputSchema")
    return Tool(
        name=name,
        description=tool.get("description") or None,
        input_schema=schema if isinstance(schema, dict) else {"type": "object"},
    )


async def _roots(ctx: ServerRequestContext) -> list[str]:
    """The client's roots as URIs. Roots are only a hint: no answer means none."""
    capabilities = ctx.session.client_capabilities
    if capabilities is None or capabilities.roots is None:
        return []
    try:
        answer = await ctx.session.send_request(
            ListRootsRequest(), ListRootsResult, request_read_timeout_seconds=ROOTS_TIMEOUT
        )
    except Exception:
        return []
    return [str(root.uri) for root in answer.roots]


def _project(roots: list[str], known: list[str], home: Path) -> str | None:
    try:
        return find_project(os.environ, roots, Path.cwd(), home, known)
    except (OSError, ValueError):  # an unreadable folder or a malformed root: no project
        return None


class _Gateway:
    """One session of `kitden mcp` with servers in the gateway."""

    def __init__(self, home: Path, own: MCPServer, known: Callable[[], list[str]]) -> None:
        self.home = home
        self.own = own
        self.known = known
        self.settings = load_settings(home)
        self.upstreams = Upstreams(home, self.settings)
        self.names: dict[str, tuple[str, str]] = {}
        self.tools: list[Tool] | None = None
        self._lock = anyio.Lock()

    async def list_tools(
        self, ctx: ServerRequestContext, params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        return ListToolsResult(tools=[*await self.own.list_tools(), *await self._offered(ctx)])

    async def call_tool(
        self, ctx: ServerRequestContext, params: CallToolRequestParams
    ) -> CallToolResult | InputRequiredResult:
        arguments = params.arguments or {}
        if params.name not in {t.name for t in await self.own.list_tools()}:
            await self._offered(ctx)
            target = self.names.get(params.name)
            if target is not None:
                return await self.upstreams.call(*target, arguments)
        try:
            return await self.own.call_tool(params.name, arguments)
        except MCPError:
            raise
        except Exception as exc:  # as MCPServer answers for its own tools
            return CallToolResult(content=[TextContent(type="text", text=str(exc))], is_error=True)

    async def _offered(self, ctx: ServerRequestContext) -> list[Tool]:
        """The upstream tools of this session, found once."""
        async with self._lock:
            if self.tools is None:
                self.tools = await self._find(ctx)
        return self.tools

    async def _find(self, ctx: ServerRequestContext) -> list[Tool]:
        roots = await _roots(ctx)
        known = await anyio.to_thread.run_sync(self._known)
        project = _project(roots, known, self.home)
        self.upstreams.project = project
        tools = load_tools(self.home)
        # A server whose list is not known yet is asked now, all of them at once.
        async with anyio.create_task_group() as group:
            for server in servers_on(self.settings, project):
                if server not in tools:
                    group.start_soon(self._learn, server, tools)
        allowed = allowed_tools(self.settings, tools, project)
        self.names = exposed_names(allowed, taken=[t.name for t in await self.own.list_tools()])
        found = {(server, t["name"]): t for server, listed in allowed.items() for t in listed}
        return [_tool(name, found[key]) for name, key in self.names.items()]

    def _known(self) -> list[str]:
        try:
            return self.known()
        except Exception:
            _say("Kitden could not read the projects; it offers the tools of all projects.")
            return []

    async def _learn(self, server: str, tools: dict[str, list[dict]]) -> None:
        try:
            listed = await self.upstreams.list_tools(server)
        except UpstreamError:
            return  # already on stderr; its tools are missing in this session
        tools[server] = listed
        try:
            save_tools(self.home, server, listed)
        except OSError:
            _say(f"Kitden could not keep the tool list of {server}.")


def gateway_server(home: Path, own: MCPServer, known: Callable[[], list[str]]) -> Server:
    """A low-level MCP server with Kitden's own tools and the tools of the moved servers.

    `known` returns Kitden's known project folders; it is called once, at the first list.
    """
    gateway = _Gateway(home, own, known)

    @asynccontextmanager
    async def lifespan(server: Server):
        async with gateway.upstreams:
            yield {}

    return Server(
        own.name,
        version=own.version,
        instructions=own.instructions,
        lifespan=lifespan,
        on_list_tools=gateway.list_tools,
        on_call_tool=gateway.call_tool,
    )


def run(home: Path, own: MCPServer, known: Callable[[], list[str]]) -> None:
    """Serve over stdio until the client closes the connection."""
    server = gateway_server(home, own, known)

    async def serve() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(serve)
