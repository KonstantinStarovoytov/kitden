"""The local page and its API. See contracts/local-api.md."""

import asyncio
import contextlib
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
    GATEWAY_CONNECT,
    SETUP_SERVER_UPDATE,
    connect_steps,
    plugin_steps,
    remove_steps,
    setup_server_steps,
    update_steps,
)
from kitden.changes.backup import ChangeStore
from kitden.changes.client_cli import CommandRunner
from kitden.changes.engine import ChangeRefusedError, Engine, Runner
from kitden.clients.base import PLUGIN_DISABLE, PLUGIN_ENABLE, REMOVE_DIRECT, SETUP_SERVER
from kitden.command import installed_command
from kitden.gateways import add_gateway, data_dir, load_gateways
from kitden.model import Change, ChangeState, Gateway, GatewayAuth
from kitden.redact import redact_text
from kitden.views.commands import commands_for
from kitden.views.effective import project_views
from kitden.views.explain import explain
from kitden.views.findings import find_bypasses, find_findings, finding_dict, mark_gateways
from kitden.views.gateway_view import gateway_dict, gateway_view
from kitden.views.inventory import Inventory, default_adapters, inventory_dict, item_dict
from kitden.views.load_map import load_map, map_dict
from kitden.views.overview import overview
from kitden.views.setup_server import is_old_entry, setup_server_state
from kitden.watch import Watcher
from kitden.web.security import SecurityMiddleware

STATIC = Path(__file__).parent / "static"
HEARTBEAT_SECONDS = 15


class Broadcaster:
    """Sends short event names (never item contents) to every open event stream."""

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[str]] = set()

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self._queues.discard(queue)

    @property
    def count(self) -> int:
        """Open event streams, one per open tab."""
        return len(self._queues)

    def publish(self, event: str) -> None:
        for queue in self._queues:
            queue.put_nowait(event)


async def event_lines(
    queue: asyncio.Queue[str],
    is_disconnected: Callable[[], Awaitable[bool]],
    heartbeat: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """Server-sent event lines until the browser goes away."""
    yield ": connected\n\n"
    while not await is_disconnected():
        try:
            event = await asyncio.wait_for(queue.get(), heartbeat)
            yield f"event: {event}\ndata: {{}}\n\n"
        except TimeoutError:
            yield ": heartbeat\n\n"


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
                "path": s.edit.path,
                "diff": s.edit.masked_diff,
                "command": redact_text(" ".join(s.command)) if s.command else None,
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


class State:
    """The current inventory, rebuilt on demand.

    With `scan_now=False` the page starts empty and the first scan runs once the server is up,
    so `kitden open` does not wait for it; API calls wait for `ready` instead.
    """

    def __init__(
        self, build: Callable[[], Inventory], events: Broadcaster, scan_now: bool = True
    ) -> None:
        self.build = build
        self.events = events
        self.ready = asyncio.Event()
        self.inventory = build() if scan_now else Inventory()
        self.data = inventory_dict(self.inventory)
        self.lock = asyncio.Lock()
        if scan_now:
            self.ready.set()

    async def first_scan(self) -> None:
        try:
            await self.rescan()
        except Exception as error:  # noqa: BLE001 - the page must answer even if the scan fails
            print(f"The first scan failed: {error}", file=sys.stderr, flush=True)
        finally:
            self.ready.set()

    async def rescan(self) -> dict:
        async with self.lock:
            self.events.publish("rescan_started")
            self.inventory = await asyncio.to_thread(self.build)
            self.data = inventory_dict(self.inventory)
            self.events.publish("rescan_finished")
        return self.data


class WaitForFirstScan:
    """API calls wait for the first scan; the page itself and its event stream do not."""

    def __init__(self, app: Callable, state: State) -> None:
        self.app = app
        self.state = state

    async def __call__(self, scope, receive, send) -> None:
        path = scope.get("path", "")
        if scope["type"] == "http" and path.startswith("/api/") and path != "/api/events":
            await self.state.ready.wait()
        await self.app(scope, receive, send)


def create_app(
    build: Callable[[], Inventory],
    token: str,
    port: int,
    watch_folders: Iterable[Path] = (),
    flat_folders: Iterable[Path] = (),
    debounce_ms: int = 800,
    home: Path | None = None,
    run: Runner | None = None,
    setup_command: Callable[[], str | None] | None = None,
    first_scan_later: bool = False,
) -> Starlette:
    """The page. Changes are available only when `home` is given (the folder being shown)."""
    events = Broadcaster()
    watcher_ref: list[Watcher] = []

    def build_marked() -> Inventory:
        inventory = build()
        if home is not None:
            mark_gateways(inventory, load_gateways(home))
        return inventory

    state = State(build_marked, events, scan_now=not first_scan_later)
    engine = None
    adapters = {}
    if home is not None:

        def on_write(path: str, sha: str | None) -> None:
            if sha and watcher_ref:
                watcher_ref[0].expect(Path(path), sha)

        engine = Engine(ChangeStore(data_dir(home)), run or CommandRunner(home), on_write)
        adapters = {a.id: a for a in default_adapters(home)}
    write_lock = asyncio.Lock()

    async def on_files_changed() -> None:
        events.publish("files_changed")
        await state.rescan()

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
            for running in (task, scan):
                if running is not None:
                    running.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await running

    async def index(request: Request) -> FileResponse:
        return FileResponse(STATIC / "index.html")

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

    def _read_model(make):
        async def endpoint(request: Request) -> JSONResponse:
            try:
                project = _project(request)
            except _UnknownProject:
                return _error("Unknown project.", 404)
            return make(request, project, project["path"] if project else None)

        return endpoint

    def _map(request, project, path):
        gateways = _registered()
        rows = load_map(state.inventory, path, gateway_registered=bool(gateways))
        return JSONResponse({"project": project, **map_dict(state.inventory, rows)})

    def _explain(request, project, path):
        name = request.query_params.get("name")
        if not name:
            return _error("Say which item to explain.", 422)
        kind = request.query_params.get("kind") or None
        return JSONResponse({"definitions": explain(state.inventory, name, kind, path)})

    def _overview(request, project, path):
        return JSONResponse(overview(state.inventory, _registered(), path))

    def _gateway_view(request, project, path):
        return JSONResponse(gateway_view(state.inventory, _registered(), path))

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
            )
            add_gateway(home, gateway)
        except ValueError as error:
            return _error(str(error), 422)
        await state.rescan()
        return JSONResponse(gateway_dict(gateway))

    def _item(item_id: str):
        return next((i for i in state.inventory.items if i.id == item_id), None)

    async def preview(request: Request) -> JSONResponse:
        if engine is None:
            return _error("Changes are not available.", 404)
        body = await _body(request)
        action = body.get("action")
        targets = body.get("targets") if isinstance(body.get("targets"), list) else []
        params = body.get("params") if isinstance(body.get("params"), dict) else {}
        try:
            if action == GATEWAY_CONNECT:
                gateway = next(
                    (g for g in load_gateways(home) if g.id == params.get("gateway")), None
                )
                if gateway is None:
                    return _error("Register the gateway first.", 422)
                clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
                steps = connect_steps(adapters, clients, gateway, str(params.get("name", "")))
            elif action == SETUP_SERVER:
                command = (setup_command or installed_command)()
                if command is None:
                    return _error("Install the tool first: uv tool install <this folder>", 422)
                clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
                steps = setup_server_steps(adapters, clients, command)
            elif action == SETUP_SERVER_UPDATE:
                ids = [str(t.get("item")) for t in targets if isinstance(t, dict)]
                items = [_item(i) for i in ids]
                if not items or any(i is None or not is_old_entry(i) for i in items):
                    return _error("Choose an old Kitden entry.", 422)
                added = {
                    s["client"]
                    for s in setup_server_state(state.inventory)
                    if s["state"] == "added"
                }
                command = None
                if any(i.client not in added for i in items):
                    command = (setup_command or installed_command)()
                    if command is None:
                        return _error("Install the tool first: uv tool install <this folder>", 422)
                steps = update_steps(adapters, items, added, command)
            elif action in (REMOVE_DIRECT, PLUGIN_ENABLE, PLUGIN_DISABLE):
                ids = [t.get("item") for t in targets if isinstance(t, dict)]
                item = _item(str(ids[0])) if len(ids) == 1 else None
                if item is None:
                    return _error("Choose one known item.", 422)
                if action == REMOVE_DIRECT:
                    steps = remove_steps(adapters, item)
                else:
                    steps = plugin_steps(adapters, item, action == PLUGIN_ENABLE)
            else:
                return _error("This action is not offered.", 422)
            change = await asyncio.to_thread(engine.preview, str(action), steps)
        except ValueError as error:  # includes ChangeRefusedError
            return _error(str(error), 422)
        events.publish("change_state")
        return JSONResponse(change_dict(change))

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
        async with write_lock:
            try:
                change = await asyncio.to_thread(method, change_id)
            except ChangeRefusedError as error:
                return _error(str(error), 422)
            except ValueError as error:
                return _error(str(error), 409)
            if verb != "cancel":
                await state.rescan()
        events.publish("change_state")
        return JSONResponse(change_dict(change), status_code=STATUS.get(change.state, 200))

    async def changes(request: Request) -> JSONResponse:
        return JSONResponse(engine.store.entries() if engine else [])

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
        data = await state.rescan()
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
            Route("/api/changes", changes),
            Route("/api/changes/preview", preview, methods=["POST"]),
            Route("/api/changes/{change_id}/{verb}", change_action, methods=["POST"]),
            Route("/api/commands", commands),
            Route("/api/map", _read_model(_map)),
            Route("/api/explain", _read_model(_explain)),
            Route("/api/overview", _read_model(_overview)),
            Route("/api/gateway-view", _read_model(_gateway_view)),
            Route("/api/events", stream),
            Mount("/static", StaticFiles(directory=STATIC), name="static"),
        ],
        middleware=[
            Middleware(SecurityMiddleware, token=token, port=port),
            Middleware(WaitForFirstScan, state=state),
        ],
        lifespan=lifespan,
    )
    app.state.inventory = state
    # What a background page checks before it stops by itself (feature 002, research R6).
    app.state.activity = SimpleNamespace(tabs=lambda: events.count, busy=write_lock.locked)
    return app
