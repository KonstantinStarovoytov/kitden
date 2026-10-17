"""The local page and its API. See contracts/local-api.md."""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from agentsetup.changes.actions import GATEWAY_CONNECT, connect_steps, remove_steps
from agentsetup.changes.backup import ChangeStore
from agentsetup.changes.client_cli import CommandRunner
from agentsetup.changes.engine import ChangeRefusedError, Engine, Runner
from agentsetup.clients.base import REMOVE_DIRECT
from agentsetup.gateways import add_gateway, data_dir, load_gateways
from agentsetup.model import Change, ChangeState, Gateway, GatewayAuth
from agentsetup.redact import redact_text
from agentsetup.views.effective import effective_view
from agentsetup.views.findings import find_bypasses, find_findings, mark_gateways
from agentsetup.views.inventory import Inventory, default_adapters, inventory_dict, item_dict
from agentsetup.watch import Watcher
from agentsetup.web.security import SecurityMiddleware

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


def gateway_dict(gateway: Gateway) -> dict:
    return {
        "id": gateway.id,
        "url": gateway.url,
        "ui_url": gateway.ui_url,
        "auth": str(gateway.auth),
        "key_env_var": gateway.key_env_var,
    }


def _finding_dict(f) -> dict:
    return {
        "id": f.id,
        "type": str(f.type),
        "severity": str(f.severity),
        "items": list(f.items),
        "names": list(f.names),
        "client": f.client,
        "explanation": f.explanation,
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
    """The current inventory, rebuilt on demand."""

    def __init__(self, build: Callable[[], Inventory], events: Broadcaster) -> None:
        self.build = build
        self.events = events
        self.inventory = build()
        self.data = inventory_dict(self.inventory)
        self.lock = asyncio.Lock()

    async def rescan(self) -> dict:
        async with self.lock:
            self.events.publish("rescan_started")
            self.inventory = await asyncio.to_thread(self.build)
            self.data = inventory_dict(self.inventory)
            self.events.publish("rescan_finished")
        return self.data


def create_app(
    build: Callable[[], Inventory],
    token: str,
    port: int,
    watch_folders: Iterable[Path] = (),
    flat_folders: Iterable[Path] = (),
    debounce_ms: int = 800,
    home: Path | None = None,
    run: Runner | None = None,
) -> Starlette:
    """The page. Changes are available only when `home` is given (the folder being shown)."""
    events = Broadcaster()
    watcher_ref: list[Watcher] = []

    def build_marked() -> Inventory:
        inventory = build()
        if home is not None:
            mark_gateways(inventory, load_gateways(home))
        return inventory

    state = State(build_marked, events)
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
        try:
            yield
        finally:
            watcher.stop()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def index(request: Request) -> FileResponse:
        return FileResponse(STATIC / "index.html")

    async def clients(request: Request) -> JSONResponse:
        return JSONResponse(state.data["clients"])

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
        clients = [c["id"] for c in state.data["clients"] if c["status"] == "found"]
        views = []
        for client in clients:
            view = effective_view(state.inventory, client, found["path"])
            views.append(
                {
                    "client": client,
                    "items": [item_dict(i) for i in view.items],
                    "shadowed": [
                        {"winner": w.id, "loser": lo.id, "mode": m, "name": w.name}
                        for w, lo, m in view.shadowed
                    ],
                }
            )
        return JSONResponse({"project": found, "views": views})

    async def findings(request: Request) -> JSONResponse:
        project = request.query_params.get("project") or None
        found = find_findings(state.inventory, project) + find_bypasses(state.inventory, project)
        return JSONResponse([_finding_dict(f) for f in found])

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
            elif action == REMOVE_DIRECT:
                ids = [t.get("item") for t in targets if isinstance(t, dict)]
                item = _item(str(ids[0])) if len(ids) == 1 else None
                if item is None:
                    return _error("Choose one known item.", 422)
                steps = remove_steps(adapters, item)
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
        """Steps the developer runs themselves (FR-029, FR-035). US3: gateway login."""
        item = _item(request.query_params.get("item", ""))
        action = request.query_params.get("action")
        if home is None or item is None or action != "gateway.login" or not item.via_gateway:
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
            Route("/api/events", stream),
            Mount("/static", StaticFiles(directory=STATIC), name="static"),
        ],
        middleware=[Middleware(SecurityMiddleware, token=token, port=port)],
        lifespan=lifespan,
    )
    app.state.inventory = state
    return app
