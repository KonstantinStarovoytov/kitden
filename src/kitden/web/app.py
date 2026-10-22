"""The local page and its API. See contracts/local-api.md."""

import asyncio
import contextlib
import json
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from pathlib import Path
from types import SimpleNamespace

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from kitden.changes.actions import (
    CLIENT_WORDS,
    GATEWAY_CONNECT,
    GATEWAY_KEYCHAIN,
    GATEWAY_MOVE,
    GATEWAY_PUT_BACK,
    GATEWAY_REMOVE,
    GATEWAY_RULE,
    GATEWAY_RULES,
    GATEWAY_STRICT,
    GATEWAY_SWITCH,
    KITDEN_GATEWAY,
    MARKETPLACE_ADD,
    MCP_ADD,
    PLUGIN_INSTALL,
    PLUGIN_SKILLS,
    PROJECT_ALIGN,
    SETUP_SERVER_UPDATE,
    SKILL_INSTALL,
    add_server_steps,
    connect_steps,
    install_steps,
    keychain_steps,
    local_move_steps,
    marketplace_steps,
    move_steps,
    plugin_skill_steps,
    plugin_skills_left_out,
    plugin_steps,
    put_back_steps,
    remove_plugin_steps,
    remove_steps,
    setup_server_steps,
    skill_remove_steps,
    skill_steps,
    switch_steps,
    tools_to_read,
    update_steps,
)
from kitden.changes.align import align_steps
from kitden.changes.backup import ChangeStore
from kitden.changes.client_cli import CommandRunner
from kitden.changes.engine import ChangeRefusedError, Engine, NothingToChangeError, Runner
from kitden.clients import version_cache
from kitden.clients.base import (
    PLUGIN_DISABLE,
    PLUGIN_ENABLE,
    PLUGIN_REMOVE,
    REMOVE_DIRECT,
    SETUP_SERVER,
    SKILL_REMOVE,
)
from kitden.command import installed_command
from kitden.gateway_api import GatewayError, MetaMcpClient, ObotClient
from kitden.gateways import add_gateway, data_dir, load_gateways
from kitden.local_gateway.project import project_chain
from kitden.local_gateway.settings import CLIENT as KITDEN
from kitden.local_gateway.settings import (
    load_calls,
    load_settings,
    load_tools,
    moved_in,
    remove_server_steps,
    save_tools,
    settings_unreadable,
)
from kitden.local_gateway.views import (
    gateway_items,
    held_servers,
    load_proxy,
    refresh_tools,
    rule_of,
    rule_steps,
    rules_steps,
    strict_steps,
    tools_view,
)
from kitden.marketplace_link import LinkError, read_marketplace
from kitden.model import Change, ChangeState, Gateway, GatewayAuth, GatewayEdit, ItemKind
from kitden.redact import masked_command, redact_text
from kitden.views.after import after_words
from kitden.views.catalog import catalog
from kitden.views.commands import commands_for
from kitden.views.effective import project_views
from kitden.views.explain import explain
from kitden.views.findings import find_bypasses, find_findings, finding_dict, mark_gateways
from kitden.views.gateway_view import gateway_dict, gateway_view
from kitden.views.inventory import Inventory, default_adapters, inventory_dict, item_dict
from kitden.views.library import KINDS, SHOWS, library
from kitden.views.load_map import load_map, map_dict
from kitden.views.overview import overview
from kitden.views.setup_server import is_old_entry, setup_server_state
from kitden.views.skills import skill_catalog, skill_keepers, skill_readers
from kitden.watch import Watcher
from kitden.web.security import SecurityMiddleware

STATIC = Path(__file__).parent / "static"
HEARTBEAT_SECONDS = 15
UNREADABLE = "Kitden could not read the gateway settings."


Event = str | tuple[str, dict]


class Broadcaster:
    """Sends short event names (never item contents) to every open event stream. An event may
    carry a little data, such as how many steps of a change are done."""

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[Event]] = set()

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        self._queues.discard(queue)

    @property
    def count(self) -> int:
        """Open event streams, one per open tab."""
        return len(self._queues)

    def publish(self, event: str, data: dict | None = None) -> None:
        for queue in self._queues:
            queue.put_nowait((event, data) if data is not None else event)


async def event_lines(
    queue: asyncio.Queue[Event],
    is_disconnected: Callable[[], Awaitable[bool]],
    heartbeat: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """Server-sent event lines until the browser goes away."""
    yield ": connected\n\n"
    while not await is_disconnected():
        try:
            event = await asyncio.wait_for(queue.get(), heartbeat)
            name, data = event if isinstance(event, tuple) else (event, {})
            yield f"event: {name}\ndata: {json.dumps(data)}\n\n"
        except TimeoutError:
            yield ": heartbeat\n\n"


def _step_path(step) -> str | None:
    if step.edit:
        return step.edit.path
    if step.gateway:
        return step.gateway.url
    if step.removal:
        return step.removal.path
    return step.copy.target if step.copy else None


def _readers(step) -> list[str] | None:
    """The clients that read a copied or removed skill folder."""
    if step.copy:
        return step.copy.readers
    return step.removal.readers if step.removal else None


def _step_diff(step) -> str:
    part = step.edit or step.gateway or step.copy or step.removal
    return part.masked_diff if part else ""


def change_dict(change: Change) -> dict:
    """What the page may see of a change: masked diffs and notes, never the values."""
    return {
        "id": change.id,
        "action": change.action,
        "state": str(change.state),
        "error": change.error,
        "restart_needed": change.restart_needed,
        "shared_file_warning": change.shared_file_warning,
        "steps": [
            {
                "client": s.client,
                "scope": str(s.scope),
                "name": s.name,
                "mechanism": s.mechanism,
                "path": _step_path(s),
                "diff": _step_diff(s),
                "reaches": _readers(s),
                "keeps": s.removal.keeps if s.removal else None,
                "command": redact_text(" ".join(masked_command(s.command))) if s.command else None,
                "restart_note": s.restart_note,
                "login_note": s.login_note,
                "shared_file": s.shared_file,
            }
            for s in change.steps
        ],
    }


# HTTP status for each state a change can end in after apply or undo.
STATUS = {
    ChangeState.VERIFIED: 200,
    ChangeState.UNDONE: 200,
    ChangeState.CANCELLED: 200,
    ChangeState.STALE: 409,
    ChangeState.UNDO_BLOCKED: 409,
    ChangeState.RESTORED: 500,
}


def _error(text: str, status: int) -> JSONResponse:
    return JSONResponse({"detail": text}, status_code=status)


# What the first scan reads, step by step, so the page can say what it still waits for.
CLIENT_STEPS = {"claude_code": "Claude Code", "codex": "Codex", "cursor": "Cursor"}
SLOW_STEP = "Codex plugins"
VERSION_STEP = "client versions"
WARM_STEP = "marketplaces"


class Progress:
    """The first scan's steps and which are done; each change goes to the open pages."""

    def __init__(self, events: Broadcaster) -> None:
        self.events = events
        self.steps: list[dict] = []
        self.ready = False

    def start(self, first: list[str], later: list[str]) -> None:
        """`first` end when the page has its data; `later` run after it, in the background."""
        self.steps = [{"name": n, "done": False, "later": False} for n in first]
        self.steps += [{"name": n, "done": False, "later": True} for n in later]
        self._publish()

    def done(self, *names: str) -> None:
        if not any(s["name"] in names and not s["done"] for s in self.steps):
            return
        for step in self.steps:
            if step["name"] in names:
                step["done"] = True
        self._publish()

    def reopen(self, *names: str) -> None:
        """Steps that wait again, such as Codex plugins once Codex's version is known."""
        if not any(s["name"] in names and s["done"] for s in self.steps):
            return
        for step in self.steps:
            if step["name"] in names:
                step["done"] = False
        self._publish()

    def mark_ready(self, *names: str) -> None:
        """The page has its data; `names` are steps that ended with it."""
        self.ready = True
        for step in self.steps:
            if step["name"] in names:
                step["done"] = True
        self._publish()

    def finish(self) -> None:
        """Nothing is left to wait for, also after a failure."""
        self.mark_ready(*(step["name"] for step in self.steps))

    def view(self) -> dict:
        return {"ready": self.ready, "steps": [dict(step) for step in self.steps]}

    def _publish(self) -> None:
        self.events.publish("scan_progress", self.view())


class State:
    """The current inventory, rebuilt on demand.

    With `scan_now=False` the page starts empty and the first scan runs once the server is up,
    so `kitden open` does not wait for it; API calls wait for `ready` instead. With
    `quick_first` every scan is quick: a slow answer (Codex's plugin list) comes in the
    background and brings one more scan. After the first scan, `warm` reads the marketplaces,
    so the Library opens at once, and `versions` reads the clients' versions that are not known
    yet; a new version brings one more scan. Each later Rescan reads them again in the background.
    """

    def __init__(
        self,
        build: Callable[..., Inventory],
        events: Broadcaster,
        scan_now: bool = True,
        quick_first: bool = False,
        warm: Callable[[Inventory], None] | None = None,
        versions: Callable[[], dict[str, str | None]] | None = None,
    ) -> None:
        self.build = build
        self.events = events
        self.quick_first = quick_first
        self.warm = warm
        self.versions = versions
        self.progress = Progress(events)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.follow_ups: set[asyncio.Task] = set()
        self.reading_versions = False
        self.ready = asyncio.Event()
        self.inventory = build() if scan_now else Inventory()
        self.data = inventory_dict(self.inventory)
        self.lock = asyncio.Lock()
        if scan_now:
            self.ready.set()
            self.progress.ready = True

    def _options(self, **more) -> dict:
        if not self.quick_first:
            return {}
        return {"quick": True, "on_slow_answer": self._slow_answer_in, **more}

    def _slow_answer_in(self) -> None:
        """Called from the thread that asked; scans again on the page's own loop."""
        if self.loop is None:
            return
        with contextlib.suppress(RuntimeError):  # the page has stopped
            self.loop.call_soon_threadsafe(self._scan_again)

    def _scan_again(self) -> None:
        task = asyncio.ensure_future(self.rescan())
        self.follow_ups.add(task)
        task.add_done_callback(self.follow_ups.discard)

    async def first_scan(self) -> None:
        self.loop = asyncio.get_running_loop()
        try:
            if self.quick_first:
                await self._quick_first_scan()
            else:
                await self.rescan()
                self.ready.set()
                await self._read_versions()
        except Exception as error:  # noqa: BLE001 - the page must answer even if the scan fails
            print(f"The first scan failed: {error}", file=sys.stderr, flush=True)
            self.progress.finish()
        finally:
            self.ready.set()
            if not self.progress.ready:
                self.progress.finish()

    async def _quick_first_scan(self) -> None:
        later = [SLOW_STEP]
        later += ([VERSION_STEP] if self.versions else []) + ([WARM_STEP] if self.warm else [])
        self.progress.start(list(CLIENT_STEPS.values()), later)
        loop = asyncio.get_running_loop()

        def step(client: str) -> None:
            if client in CLIENT_STEPS:
                loop.call_soon_threadsafe(self.progress.done, CLIENT_STEPS[client])

        async with self.lock:
            options = self._options(on_step=step)
            self.inventory = await asyncio.to_thread(self.build, **options)
            self.data = inventory_dict(self.inventory)
        self.ready.set()
        # Every client step ends here, also for a client the build did not report.
        done = list(CLIENT_STEPS.values()) + ([] if self.inventory.partial else [SLOW_STEP])
        self.progress.mark_ready(*done)
        await asyncio.gather(self._read_versions(), self._warm())

    def read_versions_later(self) -> asyncio.Task | None:
        """Read the versions again in the background, so an updated client gets its new one.
        Cheap when no binary changed; None while a read is running."""
        if self.versions is None or self.reading_versions:
            return None
        return asyncio.ensure_future(self._read_versions())

    async def _read_versions(self) -> None:
        """Read the versions not known yet; scan again when one is new. One read at a time."""
        if self.versions is None or self.reading_versions:
            return
        self.reading_versions = True
        try:
            found = await asyncio.to_thread(self.versions)
            held = {client.id: client.version for client in self.inventory.clients}
            if any(version and version != held.get(client) for client, version in found.items()):
                await self.rescan()
                # Codex asks for its plugin list only once its version is known.
                if self.inventory.partial:
                    self.progress.reopen(SLOW_STEP)
        except Exception as error:  # noqa: BLE001 - the page keeps working without versions
            kind = type(error).__name__
            print(f"Reading the client versions failed ({kind}).", file=sys.stderr, flush=True)
        finally:
            self.reading_versions = False
            self.progress.done(VERSION_STEP)
            self.events.publish("versions")

    async def _warm(self) -> None:
        if self.warm is None:
            return
        try:
            await asyncio.to_thread(self.warm, self.inventory)
        except Exception as error:  # noqa: BLE001 - only a head start; the Library reads again
            print(f"Reading the marketplaces failed: {error}", file=sys.stderr, flush=True)
        finally:
            self.progress.done(WARM_STEP)

    async def rescan(self) -> dict:
        async with self.lock:
            self.events.publish("rescan_started")
            self.inventory = await asyncio.to_thread(self.build, **self._options())
            self.data = inventory_dict(self.inventory)
            self.events.publish("rescan_finished")
        if not self.inventory.partial:
            self.progress.done(SLOW_STEP)
        return self.data


def refusal_words(error: ValueError) -> str:
    """What the review says when a change cannot be prepared, in the owner's words."""
    if isinstance(error, NothingToChangeError):
        if error.client == KITDEN:
            return "The Kitden gateway has this already. Nothing to change."
        client = CLIENT_WORDS.get(error.client, error.client)
        return f"{client} has this already. Nothing to change."
    return str(error)


class WaitForFirstScan:
    """API calls wait for the first scan; the page itself and its event stream do not."""

    def __init__(self, app: Callable, state: State) -> None:
        self.app = app
        self.state = state

    async def __call__(self, scope, receive, send) -> None:
        path = scope.get("path", "")
        waits = path.startswith("/api/") and path not in ("/api/events", "/api/progress")
        if scope["type"] == "http" and waits:
            await self.state.ready.wait()
        await self.app(scope, receive, send)


def _states_in(inventory, *states: str) -> set[str]:
    """Clients whose "show my setup" server is in one of the given states."""
    return {s["client"] for s in setup_server_state(inventory) if s["state"] in states}


def create_app(
    build: Callable[..., Inventory],
    token: str,
    port: int,
    watch_folders: Iterable[Path] = (),
    flat_folders: Iterable[Path] = (),
    debounce_ms: int = 800,
    home: Path | None = None,
    run: Runner | None = None,
    setup_command: Callable[[], str | None] | None = None,
    first_scan_later: bool = False,
    quick_first: bool = False,
    version_refresh: Callable[[], dict[str, str | None]] | None = None,
) -> Starlette:
    """The page. Changes are available only when `home` is given (the folder being shown).
    `version_refresh` reads the clients' versions after the first scan; by default the ones
    the disk cache does not know yet (tests pass a fake, so no client command runs)."""
    events = Broadcaster()
    watcher_ref: list[Watcher] = []

    def build_marked(**options) -> Inventory:
        inventory = build(**options)
        if home is not None:
            mark_gateways(inventory, load_gateways(home))
            inventory.items += gateway_items(inventory, load_settings(home), home)
        return inventory

    adapters = {a.id: a for a in default_adapters(home)} if home is not None else {}

    def warm(inventory: Inventory) -> None:
        """Read the marketplaces' plugins and skills once, so the first Library read is quick."""
        catalog(inventory, adapters)
        skill_catalog(inventory, adapters)

    def read_versions() -> dict[str, str | None]:
        stale = version_cache.stale_clients(home, version_cache.CLIENTS)
        return version_cache.refresh_versions(home, stale) if stale else {}

    if version_refresh is None and home is not None:
        version_refresh = read_versions
    state = State(
        build_marked,
        events,
        scan_now=not first_scan_later,
        quick_first=quick_first,
        warm=warm if home is not None else None,
        versions=version_refresh,
    )
    engine = None
    if home is not None:

        def on_write(path: str, sha: str | None) -> None:
            if sha and watcher_ref:
                watcher_ref[0].expect(Path(path), sha)

        def gateway_client(edit: GatewayEdit) -> MetaMcpClient | ObotClient:
            found = next((g for g in load_gateways(home) if g.id == edit.gateway_id), None)
            if found is None:
                raise GatewayError("This gateway is no longer registered")
            return ObotClient(found) if found.kind == "obot" else MetaMcpClient(found)

        engine = Engine(
            ChangeStore(data_dir(home)), run or CommandRunner(home), on_write, gateway_client
        )
    write_lock = asyncio.Lock()
    # The Kitden gateway's tool lists: a refresh runs in the background, one at a time. A server
    # that did not answer keeps its old list; the sentence that says why waits for Details.
    tool_problems: dict[str, str] = {}
    refresh_lock = asyncio.Lock()
    refreshing: set[asyncio.Task] = set()
    # The pass that waits for the running one: {"names": the servers it asks, or None for all}.
    waiting: dict[str, list[str] | None] = {}

    async def _refresh() -> None:
        try:
            async with refresh_lock:
                found = await refresh_tools(home, waiting.pop("names"))
            for name, problem in found.items():
                if problem:
                    tool_problems[name] = problem
                else:
                    tool_problems.pop(name, None)
        except Exception as error:  # noqa: BLE001 - a background refresh must not stop the page
            kind = type(error).__name__
            print(f"Refreshing the gateway tools failed ({kind}).", file=sys.stderr, flush=True)
        finally:
            events.publish("gateway_tools")

    def refresh_later(names: list[str] | None = None) -> None:
        """Ask the held servers (or only `names`) for their tools, in the background. A pass
        that already waits takes these servers too, so none queues twice."""
        if home is None:
            return
        if "names" in waiting:
            wanted = waiting["names"]
            if wanted is None or names is None:
                waiting["names"] = None
            else:
                waiting["names"] = list(dict.fromkeys([*wanted, *names]))
            return
        waiting["names"] = names
        task = asyncio.ensure_future(_refresh())
        refreshing.add(task)
        task.add_done_callback(refreshing.discard)

    def read_versions_later() -> None:
        """After a rescan: a client updated while the page runs gets its new version."""
        task = state.read_versions_later()
        if task is not None:
            refreshing.add(task)
            task.add_done_callback(refreshing.discard)

    async def on_files_changed() -> None:
        # Never starts a server: only the Rescan button refreshes the tool lists.
        events.publish("files_changed")
        await state.rescan()
        read_versions_later()

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        watcher = Watcher(watch_folders, on_files_changed, debounce_ms, flat_folders)
        watcher_ref.append(watcher)
        task = asyncio.create_task(watcher.run())
        scan = None if state.ready.is_set() else asyncio.create_task(state.first_scan())
        try:
            yield
        finally:
            watcher.stop()
            for running in (task, scan, *refreshing):
                if running is not None:
                    running.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await running

    async def index(request: Request) -> FileResponse:
        return FileResponse(STATIC / "index.html")

    async def progress(request: Request) -> JSONResponse:
        """What the first scan still reads; answers before that scan is done."""
        return JSONResponse(state.progress.view())

    async def clients(request: Request) -> JSONResponse:
        return JSONResponse(state.data["clients"])

    async def setup_server(request: Request) -> JSONResponse:
        return JSONResponse(setup_server_state(state.inventory))

    async def items(request: Request) -> JSONResponse:
        filters = {
            k: v
            for k, v in request.query_params.items()
            if k in {"client", "kind", "scope", "project"}
        }
        found = [
            i for i in state.data["items"] if all(str(i.get(k)) == v for k, v in filters.items())
        ]
        return JSONResponse(found)

    async def projects(request: Request) -> JSONResponse:
        return JSONResponse(state.data["projects"])

    async def problems(request: Request) -> JSONResponse:
        return JSONResponse(state.data["problems"])

    async def project_view(request: Request) -> JSONResponse:
        wanted = request.path_params["project_id"]
        found = next((p for p in state.data["projects"] if p["id"] == wanted), None)
        if found is None:
            return JSONResponse({"detail": "Unknown project."}, status_code=404)
        views = [
            {
                "client": view.client,
                "items": [item_dict(i) for i in view.items],
                "shadowed": [
                    {"winner": w.id, "loser": lo.id, "mode": m, "name": w.name}
                    for w, lo, m in view.shadowed
                ],
            }
            for view in project_views(state.inventory, found["path"])
        ]
        return JSONResponse({"project": found, "views": views})

    async def findings(request: Request) -> JSONResponse:
        project = request.query_params.get("project") or None
        found = find_findings(state.inventory, project) + find_bypasses(state.inventory, project)
        return JSONResponse([finding_dict(f) for f in found])

    # Read models for the redesigned page ------------------------------------------------

    class _UnknownProject(Exception):
        pass

    def _project(request: Request) -> dict | None:
        """The project chosen with ?project=<id>; None means everywhere."""
        wanted = request.query_params.get("project") or ""
        if not wanted:
            return None
        found = next((p for p in state.data["projects"] if p["id"] == wanted), None)
        if found is None:
            raise _UnknownProject
        return found

    def _registered() -> list:
        return load_gateways(home) if home is not None else []

    def _chain(path: str | None) -> list[str]:
        """The known projects whose gateway rules apply in the picked project, as the gateway
        finds them for a session there (see `project_chain`); empty for all projects."""
        if path is None or home is None:
            return []
        return project_chain(path, home, [p.path for p in state.inventory.projects])

    def _read_model(make):
        async def endpoint(request: Request) -> JSONResponse:
            try:
                project = _project(request)
            except _UnknownProject:
                return _error("Unknown project.", 404)
            # The first Library read takes seconds (it reads every skill); in a thread, other
            # requests and the event stream go on meanwhile.
            path = project["path"] if project else None
            return await asyncio.to_thread(make, request, project, path)

        return endpoint

    def _map(request, project, path):
        gateways = _registered()
        rows = load_map(state.inventory, path, gateway_registered=bool(gateways))
        return JSONResponse({"project": project, **map_dict(state.inventory, rows)})

    def _library(request, project, path):
        """One kind tab of the Library: rows, columns, counts and the lines above the table."""
        params = request.query_params
        kind = params.get("kind")
        show = params.get("show")
        hidden = frozenset(c for c in params.get("hidden", "").split(",") if c)
        answer = library(
            state.inventory,
            adapters,
            path,
            gateway_registered=bool(_registered()),
            kind=kind if kind in KINDS else "mcp_server",
            show=show if show in SHOWS else "mine",
            q=params.get("q", ""),
            category=params.get("category", ""),
            hidden=hidden,
            attention=params.get("attention") == "1",
        )
        return JSONResponse({"project": project, **answer})

    def _explain(request, project, path):
        name = request.query_params.get("name")
        if not name:
            return _error("Say which item to explain.", 422)
        kind = request.query_params.get("kind") or None
        category = request.query_params.get("category") or None
        tools = load_tools(home) if home is not None else None
        definitions = explain(state.inventory, name, kind, path, category, tools)
        return JSONResponse({"definitions": definitions})

    def _overview(request, project, path):
        held, problem = _kitden(path)
        return JSONResponse(overview(state.inventory, _registered(), path, held, problem))

    def _kitden(path):
        """The servers the Kitden gateway holds, and why its settings could not be read."""
        if home is None:
            return None, None
        held = held_servers(load_settings(home), _chain(path), load_tools(home))
        problem = UNREADABLE if settings_unreadable(home) else None
        return held, problem

    def _gateway_view(request, project, path):
        held, problem = _kitden(path)
        view = gateway_view(state.inventory, _registered(), path, kitden=held, problem=problem)
        return JSONResponse(view)

    async def gateway_tools(request: Request) -> JSONResponse:
        """A held server's tools with their states for the project, from the cache and rules."""
        if home is None:
            return _error("Changes are not available.", 404)
        try:
            project = _project(request)
        except _UnknownProject:
            return _error("Unknown project.", 404)
        server = request.query_params.get("server", "")
        settings = load_settings(home)
        if server not in settings["servers"]:
            return _error("Unknown server.", 404)
        path = project["path"] if project else None
        answer = tools_view(settings, load_tools(home), server, _chain(path), load_calls(home))
        return JSONResponse({**answer, "problem": tool_problems.get(server)})

    async def gateway_tools_refresh(request: Request) -> JSONResponse:
        """Starts asking each held server for its tools; `gateway_tools` says when it is done."""
        if home is None:
            return _error("Changes are not available.", 404)
        refresh_later()
        return JSONResponse({"refreshing": True}, status_code=202)

    # Gateways and changes (US3) ---------------------------------------------------------

    async def _body(request: Request) -> dict:
        try:
            body = await request.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

    async def gateways(request: Request) -> JSONResponse:
        if home is None:
            return JSONResponse([])
        if request.method == "GET":
            return JSONResponse([gateway_dict(g) for g in load_gateways(home)])
        body = await _body(request)
        try:
            gateway = Gateway(
                url=str(body.get("url", "")),
                ui_url=body.get("ui_url") or None,
                auth=GatewayAuth(body.get("auth", "none")),
                key_env_var=body.get("key_env_var") or None,
                login_email=str(body.get("login_email") or "").strip() or None,
                login_password_env_var=body.get("login_password_env_var") or None,
            )
            add_gateway(home, gateway)
        except ValueError as error:
            return _error(str(error), 422)
        await state.rescan()
        return JSONResponse(gateway_dict(gateway))

    async def gateway_servers(request: Request) -> JSONResponse:
        """What the gateway holds, read live; an error never blocks the page (FR-008)."""
        gateway = next(
            (g for g in _registered() if g.id == request.path_params["gateway_id"]), None
        )
        if gateway is None:
            return _error("Unknown gateway.", 404)

        def read() -> list[dict]:
            if gateway.kind == "obot":
                held = ObotClient(gateway).held()
            else:
                with MetaMcpClient(gateway) as client:
                    held = client.held()
            return [{"name": s["name"], "type": s["type"], "url": s["url"]} for s in held]

        try:
            servers = await asyncio.to_thread(read)
        except GatewayError as error:
            return JSONResponse({"servers": None, "error": redact_text(str(error))})
        return JSONResponse({"servers": servers, "error": None})

    def _item(item_id: str):
        return next((i for i in state.inventory.items if i.id == item_id), None)

    def _found_cursor():
        """The Cursor adapter when Cursor is on this computer, else None."""
        clients = state.data["clients"]
        found = any(c["id"] == "cursor" and c["status"] == "found" for c in clients)
        return adapters.get("cursor") if found else None

    async def _read_tools(name: str, server: dict) -> list[dict] | None:
        """The server's tools, asked as the gateway asks; None when it does not answer."""
        proxy = await load_proxy()  # the MCP SDK loads only here: the page starts without it
        async with proxy.Upstreams(home, {"servers": {name: server}}) as upstreams:
            try:
                return await upstreams.list_tools(name)
            except proxy.UpstreamError:
                return None

    def _project_param(params: dict) -> str | None:
        """The folder of the project an add goes into; None for all projects."""
        wanted = params.get("project")
        if not wanted:
            return None
        paths = {p["id"]: p["path"] for p in state.data["projects"]}
        if str(wanted) not in paths:
            raise ValueError("Unknown project.")
        return paths[str(wanted)]

    async def preview(request: Request) -> JSONResponse:
        if engine is None:
            return _error("Changes are not available.", 404)
        body = await _body(request)
        action = body.get("action")
        targets = body.get("targets") if isinstance(body.get("targets"), list) else []
        params = body.get("params") if isinstance(body.get("params"), dict) else {}
        left_out = None
        copied = None  # the skill list's rows a skill copy takes, for the review's first line
        align = None  # Add missing: what each client lacks, for the review's checkboxes
        try:
            if action == GATEWAY_CONNECT:
                gateway = next(
                    (g for g in load_gateways(home) if g.id == params.get("gateway")), None
                )
                if gateway is None:
                    return _error("Register the gateway first.", 422)
                clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
                steps = connect_steps(adapters, clients, gateway, str(params.get("name", "")))
            elif action == PLUGIN_INSTALL:
                offer = next(
                    (
                        o
                        for o in catalog(state.inventory, adapters)
                        if o["id"] == params.get("plugin")
                    ),
                    None,
                )
                if offer is None:
                    return _error("This plugin is not in a marketplace on this computer.", 422)
                clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
                steps = install_steps(adapters, offer, clients, _project_param(params))
            elif action == SKILL_INSTALL:
                skill = next(
                    (
                        s
                        for s in skill_catalog(state.inventory, adapters)
                        if s["id"] == params.get("skill")
                    ),
                    None,
                )
                if skill is None:
                    return _error("This skill is not on this computer.", 422)
                clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
                found = {c["id"] for c in state.data["clients"] if c["status"] == "found"}
                steps = skill_steps(adapters, skill, clients, found, _project_param(params))
                copied = [skill]
            elif action == PLUGIN_SKILLS:
                if len(targets) != 1 or not isinstance(targets[0], dict):
                    return _error("Choose one client.", 422)
                client = str(targets[0].get("client"))
                plugin_id = str(params.get("plugin"))
                skills = skill_catalog(state.inventory, adapters)
                if not any(s["plugin"] == plugin_id for s in skills):
                    return _error("This plugin has no skills on this computer.", 422)
                found = {c["id"] for c in state.data["clients"] if c["status"] == "found"}
                steps = plugin_skill_steps(adapters, plugin_id, skills, client, found)
                left_out = plugin_skills_left_out(plugin_id, skills, client)
                copied = [s for s in skills if s["plugin"] == plugin_id]
            elif action == MARKETPLACE_ADD:
                try:
                    found = await asyncio.to_thread(read_marketplace, str(params.get("source", "")))
                except LinkError as error:
                    return _error(str(error), 422)
                clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
                steps = marketplace_steps(adapters, found, clients)
            elif action == GATEWAY_SWITCH:
                gateway = next(
                    (g for g in load_gateways(home) if g.id == params.get("gateway")), None
                )
                if gateway is None:
                    return _error("Register the gateway first.", 422)
                mcp = [i for i in state.inventory.items if i.kind is ItemKind.MCP_SERVER]
                steps = switch_steps(adapters, mcp, gateway, str(params.get("name", "")))
            elif action == SETUP_SERVER:
                command = (setup_command or installed_command)()
                if command is None:
                    return _error("Install the tool first: uv tool install <this folder>", 422)
                clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
                provided = _states_in(state.inventory, "plugin")
                if any(c in provided for c in clients):
                    return _error("The kitden plugin already provides this server there.", 422)
                steps = setup_server_steps(adapters, clients, command)
            elif action == SETUP_SERVER_UPDATE:
                ids = [str(t.get("item")) for t in targets if isinstance(t, dict)]
                items = [_item(i) for i in ids]
                if not items or any(i is None or not is_old_entry(i) for i in items):
                    return _error("Choose an old Kitden entry.", 422)
                added = _states_in(state.inventory, "added", "plugin")
                command = None
                if any(i.client not in added for i in items):
                    command = (setup_command or installed_command)()
                    if command is None:
                        return _error("Install the tool first: uv tool install <this folder>", 422)
                steps = update_steps(adapters, items, added, command)
            elif action == GATEWAY_MOVE and params.get("gateway") == KITDEN_GATEWAY:
                ids = [str(t.get("item")) for t in targets if isinstance(t, dict)]
                items = [_item(i) for i in ids]
                if not items or any(i is None for i in items):
                    return _error("Choose a known server.", 422)
                known = [p.path for p in state.inventory.projects]
                added = _states_in(state.inventory, "added", "plugin")
                command = (setup_command or installed_command)()
                if command is None and {i.client for i in items} - added:
                    return _error("Install the tool first: uv tool install <this folder>", 422)
                # A Codex entry that keeps only some tools on: Kitden needs the whole list.
                wanted = await asyncio.to_thread(tools_to_read, adapters, items, home, known)
                for name, server in wanted.items():
                    tools = await _read_tools(name, server)
                    if tools is None:
                        return _error(
                            f"Kitden could not read the tools of {name}; it stays direct for now.",
                            422,
                        )
                    save_tools(home, name, tools)
                # It may ask a remote server whether it signs in, so not on the event loop.
                steps = await asyncio.to_thread(
                    local_move_steps, adapters, items, home, known, command, added_clients=added
                )
            elif action == GATEWAY_RULE:
                projects = {p["id"]: p["path"] for p in state.data["projects"]}
                steps = rule_steps(home, params, projects)
            elif action == GATEWAY_RULES:
                projects = {p["id"]: p["path"] for p in state.data["projects"]}
                steps = rules_steps(home, params, projects)
            elif action == GATEWAY_STRICT:
                steps = strict_steps(home, params, load_tools(home))
            elif action == GATEWAY_REMOVE:
                steps = remove_server_steps(home, str(params.get("server", "")))
            elif action == GATEWAY_PUT_BACK:
                clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
                server = str(params.get("server", ""))
                steps = put_back_steps(adapters, home, server, clients)
            elif action == GATEWAY_KEYCHAIN:
                steps = keychain_steps(home, str(params.get("server", "")))
            elif action == MCP_ADD:
                item = _item(str(params.get("item", "")))
                if item is None:
                    return _error("Choose a known server.", 422)
                clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
                steps = add_server_steps(adapters, item, clients)
            elif action == PROJECT_ALIGN:
                folder = _project_param(params)
                if folder is None:
                    return _error("Unknown project.", 422)
                found = {c["id"] for c in state.data["clients"] if c["status"] == "found"}
                wanted = params.get("chosen")
                chosen = [str(k) for k in wanted] if isinstance(wanted, list) else None
                steps, align = await asyncio.to_thread(
                    align_steps, state.inventory, adapters, folder, found, chosen
                )
                if not steps:
                    # Every add would make a duplicate, so none is chosen: the list only, with
                    # no change to apply.
                    listing = {"action": action, "steps": [], "after": [], "align": align}
                    return JSONResponse(listing)
                copied = skill_catalog(state.inventory, adapters)
            elif action == GATEWAY_MOVE:
                gateway = next(
                    (g for g in load_gateways(home) if g.id == params.get("gateway")), None
                )
                if gateway is None:
                    return _error("Register the gateway first.", 422)
                ids = [str(t.get("item")) for t in targets if isinstance(t, dict)]
                items = [_item(i) for i in ids]
                if not items or any(i is None for i in items):
                    return _error("Choose a known server.", 422)
                steps = move_steps(adapters, items, gateway)
            elif action == SKILL_REMOVE:
                ids = [t.get("item") for t in targets if isinstance(t, dict)]
                items = [_item(str(i)) for i in ids]
                if len(items) != 1 or items[0] is None:
                    return _error("Choose one known item.", 422)
                readers = skill_readers(state.inventory, items[0])
                keeps = skill_keepers(state.inventory, items[0], readers)
                steps = skill_remove_steps(adapters, items[0], readers, keeps)
            elif action in (REMOVE_DIRECT, PLUGIN_ENABLE, PLUGIN_DISABLE, PLUGIN_REMOVE):
                ids = [t.get("item") for t in targets if isinstance(t, dict)]
                items = [_item(str(i)) for i in ids]
                # A direct entry may go from several clients at once; a plugin is one item.
                one = len(items) == 1 or action == REMOVE_DIRECT
                if not items or any(i is None for i in items) or not one:
                    return _error("Choose one known item.", 422)
                if action == REMOVE_DIRECT:
                    steps = [s for item in items for s in remove_steps(adapters, item)]
                elif action == PLUGIN_REMOVE:
                    steps = remove_plugin_steps(adapters, items[0])
                else:
                    steps = plugin_steps(adapters, items[0], action == PLUGIN_ENABLE)
            else:
                return _error("This action is not offered.", 422)
            change = await asyncio.to_thread(engine.preview, str(action), steps)
        except ValueError as error:  # includes ChangeRefusedError
            return _error(refusal_words(error), 422)
        events.publish("change_state")
        # Only an added or removed plugin reaches Cursor through Claude Code.
        plugins = (PLUGIN_INSTALL, PLUGIN_REMOVE, PROJECT_ALIGN)
        cursor = _found_cursor() if action in plugins else None
        imports = bool(cursor and cursor.imports_claude_plugins())
        after = after_words(
            change, state.inventory, cursor_imports=imports, skills=copied, home=home
        )
        answer = {**change_dict(change), "after": after}
        if left_out is not None:
            answer["left_out"] = left_out
        if align is not None:
            answer["align"] = align
        return JSONResponse(answer)

    async def change_action(request: Request) -> JSONResponse:
        if engine is None:
            return _error("Changes are not available.", 404)
        change_id = request.path_params["change_id"]
        verb = request.path_params["verb"]
        if change_id not in engine.changes:
            return _error("Unknown change.", 404)
        method = {"apply": engine.apply, "cancel": engine.cancel, "undo": engine.undo}.get(verb)
        if method is None:
            return _error("Unknown action.", 404)
        loop = asyncio.get_running_loop()

        def progress(change_id: str, done: int, total: int) -> None:
            # The engine works in a thread; the open pages hear it on the event loop.
            data = {"id": change_id, "done": done, "total": total}
            loop.call_soon_threadsafe(events.publish, "change_progress", data)

        async with write_lock:
            engine.on_progress = progress
            try:
                change = await asyncio.to_thread(method, change_id)
            except ChangeRefusedError as error:
                return _error(str(error), 422)
            except ValueError as error:
                return _error(str(error), 409)
            finally:
                engine.on_progress = lambda change_id, done, total: None
            if verb != "cancel":
                await state.rescan()
        if verb == "apply" and change.state is ChangeState.VERIFIED:
            # Servers just moved into the Kitden gateway: Details shows their tools soon.
            moved = moved_in(change) if change.action == GATEWAY_MOVE else []
            if moved:
                refresh_later(moved)
        events.publish("change_state")
        return JSONResponse(change_dict(change), status_code=STATUS.get(change.state, 200))

    async def change_view(request: Request) -> JSONResponse:
        """One change as it stands now, so the page can check an Apply whose answer was lost."""
        if engine is None:
            return _error("Changes are not available.", 404)
        change_id = request.path_params["change_id"]
        if change_id in engine.changes:
            return JSONResponse(change_dict(engine.changes[change_id]))
        logged = next((e for e in engine.store.entries() if e.get("id") == change_id), None)
        if logged is None:
            return _error("Unknown change.", 404)
        return JSONResponse(logged)

    def _with_rule(entry: dict) -> dict:
        """A tool rule's log line, with the parts the Changes page names (see `rule_of`), read
        from the change Kitden keeps for Undo. A line without them stays as it is."""
        assert engine is not None
        if entry.get("action") != GATEWAY_RULE:
            return entry
        rule = rule_of(engine.changes.get(entry.get("id", "")))
        return {**entry, "rule": rule} if rule else entry

    async def changes(request: Request) -> JSONResponse:
        return JSONResponse([_with_rule(e) for e in engine.store.entries()] if engine else [])

    def _inherits() -> dict:
        """Whether Cursor loads Claude Code's plugins and the skills in its folder."""
        cursor = _found_cursor()
        return {
            "plugin": bool(cursor and cursor.imports_claude_plugins()),
            "skill": bool(cursor and cursor.reads_other_clients()),
        }

    async def offer_view(request: Request) -> JSONResponse:
        """One plugin or skill from the catalogs, for Details of a row not on this computer, with
        `inherits`, so Details and the Add form can name Cursor."""
        params = request.query_params
        read = skill_catalog if params.get("kind") == "skill" else catalog
        offers = await asyncio.to_thread(read, state.inventory, adapters)
        found = next((o for o in offers if o["id"] == params.get("id")), None)
        if found is None:
            return _error("Not on this computer.", 404)
        return JSONResponse({**found, "inherits": _inherits()})

    async def commands(request: Request) -> JSONResponse:
        """Steps the developer runs themselves (FR-029, FR-035). Never run by the tool."""
        item = _item(request.query_params.get("item", ""))
        action = request.query_params.get("action")
        if item is None:
            return _error("Unknown item.", 404)
        if not action:
            listed = commands_for(item, adapters)
            return JSONResponse({"commands": [c.__dict__ for c in listed]})
        if home is None or action != "gateway.login" or not item.via_gateway:
            return _error("No command for this item and action.", 404)
        gateway = next((g for g in load_gateways(home) if g.id == item.via_gateway), None)
        adapter = adapters.get(item.client)
        if gateway is None or adapter is None or gateway.auth is not GatewayAuth.OAUTH:
            return _error("No login is needed.", 404)
        return JSONResponse({"command": adapter.gateway_step(gateway, item.name).login_note})

    async def rescan(request: Request) -> JSONResponse:
        """The Rescan button: read every client again, then its version and the gateway's tools."""
        data = await state.rescan()
        refresh_later()
        read_versions_later()
        return JSONResponse({"items": len(data["items"]), "problems": len(data["problems"])})

    async def stream(request: Request) -> StreamingResponse:
        queue = events.subscribe()

        async def lines() -> AsyncIterator[str]:
            try:
                async for line in event_lines(queue, request.is_disconnected):
                    yield line
            finally:
                events.unsubscribe(queue)

        return StreamingResponse(lines(), media_type="text/event-stream")

    app = Starlette(
        routes=[
            Route("/", index),
            Route("/api/clients", clients),
            Route("/api/setup-server", setup_server),
            Route("/api/items", items),
            Route("/api/projects", projects),
            Route("/api/problems", problems),
            Route("/api/projects/{project_id}/effective", project_view),
            Route("/api/findings", findings),
            Route("/api/rescan", rescan, methods=["POST"]),
            Route("/api/gateways", gateways, methods=["GET", "POST"]),
            Route("/api/gateways/{gateway_id}/servers", gateway_servers),
            Route("/api/gateway/tools", gateway_tools),
            Route("/api/gateway/tools/refresh", gateway_tools_refresh, methods=["POST"]),
            Route("/api/changes", changes),
            Route("/api/changes/preview", preview, methods=["POST"]),
            Route("/api/changes/{change_id}", change_view),
            Route("/api/changes/{change_id}/{verb}", change_action, methods=["POST"]),
            Route("/api/commands", commands),
            Route("/api/map", _read_model(_map)),
            Route("/api/library", _read_model(_library)),
            Route("/api/offer", offer_view),
            Route("/api/explain", _read_model(_explain)),
            Route("/api/overview", _read_model(_overview)),
            Route("/api/gateway-view", _read_model(_gateway_view)),
            Route("/api/events", stream),
            Route("/api/progress", progress),
            Mount("/static", StaticFiles(directory=STATIC), name="static"),
        ],
        middleware=[
            Middleware(SecurityMiddleware, token=token, port=port),
            Middleware(WaitForFirstScan, state=state),
        ],
        lifespan=lifespan,
    )
    app.state.inventory = state
    app.state.events = events
    # What a background page checks before it stops by itself (feature 002, research R6).
    app.state.activity = SimpleNamespace(tabs=lambda: events.count, busy=write_lock.locked)
    return app
