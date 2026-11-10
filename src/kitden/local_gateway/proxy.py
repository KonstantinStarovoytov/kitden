"""The gateway inside `kitden mcp`: the tools of the servers moved into it, per project.

A client starts `kitden mcp` once per session. When the gateway settings hold servers, it offers
Kitden's own read-only tools and the tools turned on for the session's project, under names that
are unique, the same in every project, and short enough for every client. It finds the session's
folder, its projects and the tool list at the first `tools/list` and keeps them for the session.
On each call of an upstream tool it reads the rules again and refuses a tool that is off now.
A local server starts in that folder (or in its own start folder, `cwd`) when one of its tools
is first called, or at that first `tools/list` when its tool list is not known yet.

MCP SDK facts this relies on (mcp 2.3.0, checked 2026-10-21):
- `MCPServer` keeps its low-level server in a private attribute. So the gateway is its own
  low-level `Server` with `on_list_tools` and `on_call_tool`, and it reaches Kitden's own tools
  through the public `MCPServer.list_tools()` and `MCPServer.call_tool()`.
- The server handles each request in its own task, so a slow call does not hold up the others.
- `ServerSession.list_roots()` warns on every call that roots are deprecated (protocol
  2026-07-28); the gateway sends the same `roots/list` request with `send_request`.
- `ServerSession.send_tool_list_changed()` sends `notifications/tools/list_changed`.
- `Client` with `StdioServerParameters` puts the given env over HOME, LOGNAME, PATH, SHELL, TERM
  and USER of this process.
"""

import hashlib
import os
import re
import sys
from collections.abc import Callable, Iterable
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial
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
    CONNECTION_CLOSED,
    INTERNAL_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    REQUEST_TIMEOUT,
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

from kitden import sign_in
from kitden.changes.atomic import RefusedWriteError
from kitden.gateways import data_dir
from kitden.local_gateway import oauth
from kitden.local_gateway.keychain import KeychainError, is_reference, resolve_entry
from kitden.local_gateway.project import project_chain, session_folder
from kitden.local_gateway.settings import (
    SETTINGS_FILE,
    START_TIME,
    allowed_tools,
    count_call,
    fill_placeholders,
    is_allowed,
    load_names,
    load_settings,
    load_tools,
    mark_refused,
    save_names,
    save_tools,
    servers_on,
)

# Seconds for a server to start and list its tools; Claude Code waits 30 (checked 2026-10-21).
START_TIMEOUT = 20
CALL_TIMEOUT = 300  # seconds for one tool call
ROOTS_TIMEOUT = 5  # seconds for the client to name its roots
# Cursor allows 60 characters for server and tool (checked 2026-10-21); the entry is "kitden".
NAME_LIMIT = 54
# The Claude API takes tool names of letters, digits, "_" and "-" only (checked 2026-10-21,
# platform.claude.com tool use docs), so a server's name in front of a tool keeps only those.
NOT_IN_NAMES = re.compile(r"[^A-Za-z0-9_-]")
# Error codes the SDK makes itself (mcp 2.3.0, checked 2026-10-21): a closed connection or a
# timeout on any transport; and over HTTP the transport turns HTTP failures into JSON-RPC errors
# too, and the one for a refused redirect names the other address. A server's own error with any
# other code is its answer, and it goes to the model as it is.
SDK_CODES = {CONNECTION_CLOSED, REQUEST_TIMEOUT}
HTTP_CODES = SDK_CODES | {PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INTERNAL_ERROR}

# The HTTP library's and the MCP client's own logs are silenced by `oauth` (imported above): an
# address or an error they log may hold a token. The gateway prints its own plain line instead.


def exposed_names(
    tools: dict[str, list[dict]], taken: Iterable[str] = (), kept: dict[str, str] | None = None
) -> dict[str, tuple[str, str]]:
    """The name each tool is offered under → (server, tool).

    `tools` are every held server's known tools, on or off, so a name always means the same tool
    in every project. `kept` are the bare names given before → their server: such a name stays
    with its server, so a server added later cannot take it (a client rule that allows
    `mcp__kitden__search` must keep meaning the same tool). A kept name of a server whose tools
    are not known now is left free. The other tools go by server, in name order. A tool keeps
    its name unless it is in use or `taken` (Kitden's own tools); then it gets `<server>_` in
    front. A name over 54 characters, or a `<server>_<tool>` that is in use too, becomes its
    first 45 characters, "_" and the first 8 hex characters of its SHA-1; when that is in use
    too, of the name with "#2", "#3" and so on. So no name is given twice and no tool is left
    out. In the prefix, each character a tool name may not have becomes "_".
    """
    names: dict[str, tuple[str, str]] = {}
    used = set(taken)
    for name, server in (kept or {}).items():
        if name in used:
            continue
        if server not in tools or any(t["name"] == name for t in tools[server]):
            used.add(name)
            if server in tools:
                names[name] = (server, name)
    for server in sorted(tools):
        for tool in tools[server]:
            name = tool["name"]
            if names.get(name) == (server, name):
                continue
            if name in used:
                name = f"{NOT_IN_NAMES.sub('_', server)}_{name}"
            seed, tries = name, 0
            while len(name) > NAME_LIMIT or name in used:
                tries += 1
                key = seed if tries == 1 else f"{seed}#{tries}"
                digest = hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()
                name = f"{seed[:45]}_{digest[:8]}"
            names[name] = (server, tool["name"])
            used.update((tool["name"], name))
    return names


def bare_names(
    names: dict[str, tuple[str, str]], kept: dict[str, str], held: Iterable[str]
) -> dict[str, str]:
    """The bare names to keep: those given now, and the kept ones of servers whose tools are not
    known now (`held` are the servers whose tools are)."""
    held = set(held)
    still = {name: server for name, server in kept.items() if server not in held}
    return still | {name: server for name, (server, tool) in names.items() if name == tool}


class UpstreamError(Exception):
    """A server could not start or answer. The message is one plain sentence with no secrets."""


# A remote server that answered 401 or 403: the library reports only the server's own words.
REFUSED = "{server} turned down its access: its token is wrong or has ended."
# A remote server that started but answered a call with 401 or 403.
ASK_FOR_ACCESS = (
    "{server} needs a token, or its token is wrong. Add it in Kitden: Gateway, {server}, "
    "Add access."
)


def _turned_down(entry: dict) -> bool:
    """Whether a remote server that would not start answers 401 or 403 (needs_sign_in)."""
    from kitden.changes.actions import needs_sign_in

    try:
        return needs_sign_in(str(entry["url"]), entry.get("headers") or {})
    except OSError:
        return False


def _say(text: str) -> None:
    """One plain line on stderr, which the client keeps in its log."""
    print(text, file=sys.stderr, flush=True)


def _answer(text: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=text)], is_error=True)


def _error(text: str) -> CallToolResult:
    _say(text)
    return _answer(text)


class Upstreams:
    """The servers in the gateway, for one gateway process or one listing on the page.

    Use it as `async with Upstreams(home, settings) as upstreams:`. A server starts on its first
    use and runs until the block ends. Set `folder` (the session's folder) before the first use:
    a local server runs in that folder, or the home folder without one, and it fills the project
    placeholders in the arguments.
    The block is a task group: an error raised in it comes out in an ExceptionGroup, so catch
    UpstreamError inside the block.
    """

    def __init__(self, home: Path, settings: dict) -> None:
        self.home = home
        self.settings = settings
        self.folder: str | None = None
        self._clients: dict[str, Client] = {}
        self._auths: dict[str, oauth.StoredSignIn] = {}  # the stored sign-in of each running one
        # How many 401 or 403 answers each remote server gave: the MCP library reports such an
        # answer to a call only as an internal error, so the HTTP client counts them, and a call
        # compares the count before and after (calls to one server may run at once).
        self._turned: dict[str, int] = {}
        self._locks: dict[str, anyio.Lock] = {}
        self._group: TaskGroup | None = None

    async def __aenter__(self) -> "Upstreams":
        self._group = anyio.create_task_group()
        await self._group.__aenter__()
        return self

    async def __aexit__(self, *exc_info: Any) -> bool | None:
        group, self._group = self._open(), None
        group.cancel_scope.cancel()
        return await group.__aexit__(*exc_info)

    def _open(self) -> TaskGroup:
        if self._group is None:
            raise RuntimeError("Use Upstreams in an `async with` block.")
        return self._group

    async def list_tools(self, server: str) -> list[dict]:
        """The server's tools as it lists them, within its start time (see `_start_time`).

        Raises UpstreamError when the server does not start or answer.
        """
        self._open()
        wait = self._start_time(server)
        try:
            with anyio.fail_after(wait):
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
            sentence = f"{server} did not {state} in {wait:g} seconds."
        except Exception:  # noqa: BLE001 - whatever went wrong, the client gets one plain sentence
            sentence = f"{server} did not list its tools."
        _say(sentence)
        raise UpstreamError(sentence)

    async def call(self, server: str, tool: str, arguments: dict[str, Any]) -> CallToolResult:
        """Call one tool. The server's own error answer comes back as it is; when the call
        fails in any other way, the result is an error with one plain sentence."""
        self._open()
        wait = self._start_time(server)
        try:
            with anyio.fail_after(wait):
                client = await self._client(server)
        except UpstreamError as problem:
            return _error(str(problem))
        except TimeoutError:
            return _error(f"{server} did not start in {wait:g} seconds.")
        turned = self._turned.get(server, 0)
        try:
            with anyio.fail_after(CALL_TIMEOUT):
                answer = await client.call_tool(tool, arguments)
        except TimeoutError:
            return _error(f"{server} did not answer in {CALL_TIMEOUT} seconds.")
        except MCPError as refused:
            if refused.code not in (HTTP_CODES if self._remote(server) else SDK_CODES):
                await self._note_refused(server, False)
                return _answer(refused.message)  # the server's own answer
            return _error(await self._failed(server, turned))
        except Exception:  # noqa: BLE001
            # The text of an error may hold the server's address; say it plainly instead.
            return _error(await self._failed(server, turned))
        await self._note_refused(server, False)
        return answer

    async def _failed(self, server: str, turned: int = 0) -> str:
        """Why a call failed: a sign-in that ended while the server ran, a token the server
        wants (noted for the page), or plainly."""
        auth = self._auths.get(server)
        if auth is not None and auth.signed_out:
            return sign_in.SIGNED_OUT.format(server=server)
        if self._turned.get(server, 0) > turned:
            await self._note_refused(server, True)
            return ASK_FOR_ACCESS.format(server=server)
        return f"The call to {server} failed."

    async def _note_refused(self, server: str, refused: bool) -> None:
        """Keep for the page whether a remote server turned down its last call. A note that
        cannot be written is only said."""
        if not self._remote(server):
            return
        try:
            await anyio.to_thread.run_sync(mark_refused, self.home, server, refused)
        except OSError:
            _say(f"Kitden could not note the answer of {server}.")

    def _start_time(self, server: str) -> float:
        """Seconds for the server to start and list its tools: the gateway's own, or the longer
        time its Codex entry gave it (`startup_timeout_sec`, carried by the move)."""
        entry = self.settings["servers"].get(server)
        wait = entry.get(START_TIME) if isinstance(entry, dict) else None
        if isinstance(wait, int | float) and not isinstance(wait, bool):
            return max(START_TIMEOUT, wait)
        return START_TIMEOUT

    def _remote(self, server: str) -> bool:
        entry = self.settings["servers"].get(server)
        return isinstance(entry, dict) and bool(entry.get("url"))

    async def _client(self, server: str) -> Client:
        """The server's connection; the first use opens it. Only one opens at a time."""
        async with self._locks.setdefault(server, anyio.Lock()):
            client = self._clients.get(server)
            if client is None:
                try:
                    client = await self._open().start(self._serve, server)
                except UpstreamError:
                    raise
                except Exception:  # noqa: BLE001 - the error's text may hold the server's address
                    verb = "reach" if self._remote(server) else "start"
                    raise UpstreamError(f"Kitden could not {verb} {server}.") from None
            return client

    async def _serve(self, server: str, *, task_status: TaskStatus[Client]) -> None:
        """Open the server's connection and hold it until the `async with` block ends.

        It runs in the group's own task: a connection must close in the task that opened it.
        A server whose browser sign-in ended says so; when another gateway process refreshed
        it meanwhile (the item changed), it starts once more with the new tokens.
        """
        try:
            # Secrets in env and headers are Keychain references until the server starts.
            entry = await anyio.to_thread.run_sync(resolve_entry, self.settings["servers"][server])
        except KeychainError as problem:
            raise UpstreamError(str(problem)) from None
        for attempt in (1, 2):
            auth = None
            if entry.get("url") and is_reference(entry.get("sign_in")):
                auth = oauth.StoredSignIn(server, str(entry["url"]), entry["sign_in"])
            ready = False
            try:
                async with AsyncExitStack() as stack:
                    target = await self._target(entry, stack, auth, server)
                    # The initialize handshake, which every server answers. Mode "auto" first
                    # asks `server/discover`; a server that leaves it unanswered costs 10 s.
                    client = await stack.enter_async_context(Client(target, mode="legacy"))
                    self._clients[server] = client
                    if auth is not None:
                        self._auths[server] = auth
                    task_status.started(client)
                    ready = True
                    await anyio.sleep_forever()
            except Exception:
                if not ready:
                    if auth is not None and auth.signed_out:
                        if attempt == 1 and await self._refreshed_elsewhere(auth):
                            continue
                        raise UpstreamError(sign_in.SIGNED_OUT.format(server=server)) from None
                    if entry.get("url") and await anyio.to_thread.run_sync(_turned_down, entry):
                        raise UpstreamError(REFUSED.format(server=server)) from None
                    raise
                _say(f"{server} stopped.")
            finally:
                self._clients.pop(server, None)
                self._auths.pop(server, None)
            return

    @staticmethod
    async def _refreshed_elsewhere(auth: oauth.StoredSignIn) -> bool:
        """Whether the sign-in's Keychain item changed since this process read it."""
        try:
            now = await auth.storage.read()
        except KeychainError:
            return False
        return now is not None and now != auth.storage.raw

    async def _target(
        self, entry: dict, stack: AsyncExitStack, auth: Any = None, server: str = ""
    ) -> Any:
        """How to reach a server: streamable HTTP for a `url` (with `auth`, its stored
        sign-in), else its command over stdio. A 401 or 403 answer is counted (`_turned`)."""
        if entry.get("url"):
            # It names itself: Cloudflare turns down Python's default agent (seen 2026-10-31).
            headers = {"User-Agent": "kitden"}
            headers.update({str(k): str(v) for k, v in (entry.get("headers") or {}).items()})
            timeout = httpx2.Timeout(START_TIMEOUT, read=CALL_TIMEOUT)

            async def note(answer: httpx2.Response) -> None:
                if answer.status_code in (401, 403):
                    self._turned[server] = self._turned.get(server, 0) + 1

            hooks = {"response": [note]}
            http = await stack.enter_async_context(
                httpx2.AsyncClient(headers=headers, timeout=timeout, auth=auth, event_hooks=hooks)
            )
            return streamable_http_client(str(entry["url"]), http_client=http)
        folder = self.folder or str(self.home)
        return StdioServerParameters(
            command=entry["command"],
            args=[fill_placeholders(str(arg), folder) for arg in entry.get("args") or []],
            env=self._env(entry),
            # A server with a start folder of its own starts there; a project folder in its
            # arguments is still the session's.
            cwd=entry.get("cwd") or folder,
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
    """An offered tool under the offered name: the server's description, input schema, title
    and annotations, so a client keeps its read-only and destructive hints."""
    schema = tool.get("inputSchema")
    plain = {
        "name": name,
        "description": tool.get("description") or None,
        "input_schema": schema if isinstance(schema, dict) else {"type": "object"},
    }
    try:
        return Tool(**plain, title=tool.get("title"), annotations=tool.get("annotations"))
    except ValueError:  # a title or hints Kitden did not write: the tool goes without them
        return Tool(**plain)


async def _roots(ctx: ServerRequestContext) -> list[str]:
    """The client's roots as URIs. Roots are only a hint: no answer means none."""
    capabilities = ctx.session.client_capabilities
    if capabilities is None or capabilities.roots is None:
        return []
    try:
        answer = await ctx.session.send_request(
            ListRootsRequest(), ListRootsResult, request_read_timeout_seconds=ROOTS_TIMEOUT
        )
    except Exception:  # noqa: BLE001 - a client that cannot say its roots has none
        return []
    return [str(root.uri) for root in answer.roots]


def _session(roots: list[str], known: list[str], home: Path) -> tuple[str | None, list[str]]:
    """The session's folder and the chain of known projects whose rules apply there."""
    try:
        folder = session_folder(os.environ, roots, Path.cwd(), home)
        return folder, project_chain(folder, home, known)
    except (OSError, ValueError):  # an unreadable folder or a malformed root: no project
        return None, []


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
        self.chain: list[str] = []
        self.rules_time: int | None = None  # when the rules file last changed, as last seen
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
                await self._tell_new_list(ctx)
                # The rules are read again on each call: a tool turned off is refused at once.
                # When the file cannot be read, the rules the session started with decide.
                allowed = partial(
                    is_allowed, self.home, self.chain, *target, fallback=self.settings
                )
                if not await anyio.to_thread.run_sync(allowed):
                    return _answer(f"{params.name} is turned off in Kitden.")
                answer = await self.upstreams.call(*target, arguments)
                await self._count(*target)
                return answer
        try:
            return await self.own.call_tool(params.name, arguments)
        except MCPError:
            raise
        except Exception as exc:  # noqa: BLE001 - as MCPServer answers for its own tools
            return _answer(str(exc))

    async def _count(self, server: str, tool: str) -> None:
        """Count a call that went to the server. A count that cannot be written is only said."""
        try:
            await anyio.to_thread.run_sync(count_call, self.home, server, tool)
        except OSError:
            _say(f"Kitden could not count the call to {server}.")

    async def _offered(self, ctx: ServerRequestContext) -> list[Tool]:
        """The upstream tools of this session, found once."""
        async with self._lock:
            if self.tools is None:
                self.tools = await self._find(ctx)
        return self.tools

    async def _find(self, ctx: ServerRequestContext) -> list[Tool]:
        roots = await _roots(ctx)
        known = await anyio.to_thread.run_sync(self._known)
        folder, chain = _session(roots, known, self.home)
        self.chain = chain
        self.rules_time = await anyio.to_thread.run_sync(self._rules_time)
        # Local servers start in the session's folder; the rules follow its chain.
        self.upstreams.folder = folder
        tools = load_tools(self.home)
        # A server whose list is not known yet is asked now, all of them at once.
        async with anyio.create_task_group() as group:
            for server in servers_on(self.settings, chain):
                if server not in tools:
                    group.start_soon(self._learn, server, tools)
        allowed = allowed_tools(self.settings, tools, chain)
        found = {(server, t["name"]): t for server, listed in allowed.items() for t in listed}
        # Names come from every held server's tools, so they do not change with the project.
        held = {server: tools[server] for server in self.settings["servers"] if server in tools}
        # A bare name stays with the server that had it, while that server is held.
        saved = load_names(self.home)
        kept = {n: s for n, s in saved.items() if s in self.settings["servers"]}
        own = [t.name for t in await self.own.list_tools()]
        names = exposed_names(held, taken=own, kept=kept)
        if (bare := bare_names(names, kept, held)) != saved:
            try:
                await anyio.to_thread.run_sync(save_names, self.home, bare)
            except (OSError, RefusedWriteError):
                _say("Kitden could not keep the tool names; they may change when servers change.")
        self.names = {name: key for name, key in names.items() if key in found}
        return [_tool(name, found[key]) for name, key in self.names.items()]

    async def _tell_new_list(self, ctx: ServerRequestContext) -> None:
        """Best effort: when the rules file changed and the tools it allows now differ from the
        offered ones, tell the client once that the tool list changed. The offered list stays as
        the session found it. This never fails a call."""
        try:
            changed = await anyio.to_thread.run_sync(self._rules_time)
            if changed == self.rules_time:
                return
            self.rules_time = changed
            if await anyio.to_thread.run_sync(self._allowed_now) != set(self.names.values()):
                # mcp 2.3.0 ServerSession.send_tool_list_changed sends
                # notifications/tools/list_changed (checked 2026-10-21).
                await ctx.session.send_tool_list_changed()
        except Exception:  # noqa: BLE001
            return  # the client keeps its list until a new session

    def _rules_time(self) -> int | None:
        try:
            return (data_dir(self.home) / SETTINGS_FILE).stat().st_mtime_ns
        except OSError:
            return None

    def _allowed_now(self) -> set[tuple[str, str]]:
        """The tools the rules allow now, from the known tool lists; no server is asked."""
        allowed = allowed_tools(load_settings(self.home), load_tools(self.home), self.chain)
        return {(server, t["name"]) for server, listed in allowed.items() for t in listed}

    def _known(self) -> list[str]:
        try:
            return self.known()
        except Exception:  # noqa: BLE001 - the session still starts, with the global tools
            _say(
                "Kitden could not read the known projects; "
                "this session gets the global set of tools."
            )
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
