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

from agentsetup.views.inventory import Inventory, inventory_dict
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


class State:
    """The current inventory, rebuilt on demand."""

    def __init__(self, build: Callable[[], Inventory], events: Broadcaster) -> None:
        self.build = build
        self.events = events
        self.data = inventory_dict(build())
        self.lock = asyncio.Lock()

    async def rescan(self) -> dict:
        async with self.lock:
            self.events.publish("rescan_started")
            self.data = inventory_dict(await asyncio.to_thread(self.build))
            self.events.publish("rescan_finished")
        return self.data


def create_app(
    build: Callable[[], Inventory],
    token: str,
    port: int,
    watch_folders: Iterable[Path] = (),
    flat_folders: Iterable[Path] = (),
    debounce_ms: int = 800,
) -> Starlette:
    events = Broadcaster()
    state = State(build, events)

    async def on_files_changed() -> None:
        events.publish("files_changed")
        await state.rescan()

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        watcher = Watcher(watch_folders, on_files_changed, debounce_ms, flat_folders)
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
            Route("/api/rescan", rescan, methods=["POST"]),
            Route("/api/events", stream),
            Mount("/static", StaticFiles(directory=STATIC), name="static"),
        ],
        middleware=[Middleware(SecurityMiddleware, token=token, port=port)],
        lifespan=lifespan,
    )
    app.state.inventory = state
    return app
