"""The local page and its API. See contracts/local-api.md."""

import asyncio
import contextlib
import json
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from kitden import __version__
from kitden.changes.actions import (
    CLIENT_DISCONNECT,
    CLIENT_WORDS,
    GATEWAY_ADD,
    GATEWAY_CONNECT,
    GATEWAY_KEYCHAIN,
    GATEWAY_MOVE,
    GATEWAY_MOVE_OUT,
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
    SETUP_SERVER_ENABLE,
    SETUP_SERVER_UPDATE,
    SKILL_INSTALL,
    SKILL_RULE,
    add_server_steps,
    connect_steps,
    disconnect_steps,
    gateway_add_steps,
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
    skill_rule_steps,
    skill_steps,
    switch_steps,
    tools_to_read,
    update_steps,
)
from kitden.changes.align import align_steps
from kitden.changes.backup import ChangeStore
from kitden.changes.batch import (
    BATCH,
    Part,
    combine,
    first_clash,
    part_of,
    requests_in,
    step_rows,
)
from kitden.changes.client_cli import CommandRunner
from kitden.changes.engine import (
    ChangeRefusedError,
    Engine,
    NothingToChangeError,
    Runner,
    step_path,
    step_readers,
    writable_roots,
)
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
from kitden.local_gateway.project import project_chain, project_chains
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
    own_rules,
    refresh_tools,
    rule_of,
    rule_steps,
    rules_steps,
    strict_steps,
    tools_view,
)
from kitden.marketplace_link import LinkError, read_marketplace
from kitden.model import Change, ChangeState, Gateway, GatewayAuth, GatewayEdit, ItemKind, Step
from kitden.redact import masked_command, redact_text
from kitden.views.after import after_words
from kitden.views.catalog import catalog, market_servers
from kitden.views.commands import commands_for
from kitden.views.effective import project_views
from kitden.views.explain import explain, with_page_fields
from kitden.views.findings import find_bypasses, find_findings, finding_dict, mark_gateways
from kitden.views.gateway_view import gateway_dict, gateway_view
from kitden.views.instructions_map import instructions_map
from kitden.views.inventory import (
    Inventory,
    LastGood,
    default_adapters,
    inventory_dict,
    item_dict,
    keep_last_good,
)
from kitden.views.library import KINDS, LIST_SHOWS, LIST_TABS, SHOWS, library, library_list
from kitden.views.library_map import library_map
from kitden.views.load_map import load_map, map_dict
from kitden.views.overview import overview
from kitden.views.review import change_target, mark_reach, undo_note
from kitden.views.setup_server import enable_steps, is_old_entry, setup_server_state
from kitden.views.skills import (
    library_offers,
    project_skills,
    skill_catalog,
    skill_keepers,
    skill_readers,
)
from kitden.views.words import CHANGE_UNREAD, KEPT_UNREAD, NO_ADD_UNREAD, ONLY_IN_PROJECT
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
        "target": change.target,
        "rows": change.rows,
        "steps": [
            {
                "client": s.client,
                "scope": str(s.scope),
                "name": s.name,
                "mechanism": s.mechanism,
                "path": step_path(s),
                "diff": _step_diff(s),
                "reaches": step_readers(s),
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


@dataclass
class Built:
    """What one request's builder made: the steps, and what the review's words read besides."""

    steps: list[Step]
    items: list = field(default_factory=list)  # the definitions the change changes
    left_out: list | None = None
    copied: list | None = None
    align: Any = None


class _RowRefused(Exception):
    """A tray request cannot join the change: the words, and the row they come from (None when
    the engine refuses the whole change)."""

    def __init__(self, reason: str, row: str | None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.row = row


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


# The actions that add something: a refusal into a file Kitden could not read says "add". The
# page's ADDS (review.js) names their scope in the review; it leaves out PROJECT_ALIGN,
# SETUP_SERVER, SETUP_SERVER_UPDATE and GATEWAY_MOVE_OUT, which say their place another way.
ADD_ACTIONS = frozenset(
    {
        MCP_ADD,
        SKILL_INSTALL,
        PLUGIN_INSTALL,
        PLUGIN_SKILLS,
        MARKETPLACE_ADD,
        PROJECT_ALIGN,
        GATEWAY_CONNECT,
        SETUP_SERVER,
        SETUP_SERVER_UPDATE,
        GATEWAY_PUT_BACK,
        GATEWAY_MOVE_OUT,
        GATEWAY_ADD,
    }
)


def unread_refusal(action: str, path: str) -> str:
    """Why a change into a settings file Kitden could not read is refused, in words that follow
    the action."""
    words = NO_ADD_UNREAD if action in ADD_ACTIONS else CHANGE_UNREAD
    return words.format(Path(path).name)


def kept_refusal(item) -> str:
    """Why a definition kept from the last good read cannot be changed: Kitden must read its
    file again first."""
    path = item.source.path
    where = Path(path).name if path else CLIENT_WORDS.get(item.client, "its settings")
    return KEPT_UNREAD.format(where)


def refusal_words(error: ValueError) -> str:
    """What the review says when a change cannot be prepared, in the owner's words."""
    if isinstance(error, NothingToChangeError):
        if error.client == KITDEN:
            return "The Kitden gateway has this already. Nothing to change."
        client = CLIENT_WORDS.get(error.client, error.client)
        return f"{client} has this already. Nothing to change."
    return str(error)


# The API calls that answer before the first scan is done.
NO_WAIT = ("/api/events", "/api/progress", "/api/about")


class WaitForFirstScan:
    """API calls wait for the first scan; the page itself and its event stream do not."""

    def __init__(self, app: Callable, state: State) -> None:
        self.app = app
        self.state = state

    async def __call__(self, scope, receive, send) -> None:
        path = scope.get("path", "")
        waits = path.startswith("/api/") and path not in NO_WAIT
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
    demo: bool = False,
) -> Starlette:
    """The page. Changes are available only when `home` is given (the folder being shown).
    `version_refresh` reads the clients' versions after the first scan; by default the ones
    the disk cache does not know yet (tests pass a fake, so no client command runs).

    With `demo`, `home` is the sample's, and stand-ins keep everything inside it: no client
    command, Keychain, MCP server, version read or network. What would go online is refused.
    """
    events = Broadcaster()
    watcher_ref: list[Watcher] = []
    make_adapters = default_adapters
    stand_ins = keychain_run = sign_in = None
    if demo:
        if home is None:
            raise ValueError("Demo mode needs the sample's home folder.")
        from kitden import demo as stand_ins  # loaded only for a demo

        make_adapters = stand_ins.demo_adapters
        run = run or stand_ins.DemoRunner(home)
        setup_command = setup_command or (lambda: stand_ins.demo_command(home))
        keychain_run = stand_ins.DemoKeychain(stand_ins.keychain_file(home))
        sign_in = stand_ins.no_sign_in

    def _registered() -> list[Gateway]:
        """The registered gateways; none in the demo, which never goes online."""
        return load_gateways(home) if home is not None and not demo else []

    def build_marked(**options) -> Inventory:
        inventory = build(**options)
        # A source that fails keeps its last good items while the page runs.
        now = datetime.now(UTC).isoformat(timespec="seconds")
        keep_last_good(inventory, last_good, now)
        if home is not None:
            mark_gateways(inventory, _registered())
            inventory.items += gateway_items(inventory, load_settings(home), home)
        return inventory

    adapters = {a.id: a for a in make_adapters(home)} if home is not None else {}

    def warm(inventory: Inventory) -> None:
        """Read the marketplaces' plugins and skills once, so the first Library read is quick."""
        catalog(inventory, adapters)
        skill_catalog(inventory, adapters)

    def read_versions() -> dict[str, str | None]:
        stale = version_cache.stale_clients(home, version_cache.CLIENTS)
        return version_cache.refresh_versions(home, stale) if stale else {}

    if version_refresh is None and home is not None and not demo:
        version_refresh = read_versions
    last_good = LastGood()  # State builds at once, so it is made first
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
            found = next((g for g in _registered() if g.id == edit.gateway_id), None)
            if found is None:
                raise GatewayError("This gateway is no longer registered")
            return ObotClient(found) if found.kind == "obot" else MetaMcpClient(found)

        engine = Engine(
            ChangeStore(data_dir(home)),
            run or CommandRunner(home),
            on_write,
            None if demo else gateway_client,
            roots=lambda: (home, writable_roots(home, state.inventory)),
            keychain_run=keychain_run,
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
            # Picked as the pass runs, so tests can patch refresh_tools.
            ask = stand_ins.canned_refresh if stand_ins else refresh_tools
            async with refresh_lock:
                found = await ask(home, waiting.pop("names"))
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

    async def about(request: Request) -> JSONResponse:
        """Kitden's version, and whether this is the demo; answers before the first scan."""
        return JSONResponse({"version": __version__, "demo": demo})

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
        """The known projects, each with how many gateway rules of its own differ from the
        shared setup, for the project menu."""
        settings = load_settings(home) if home is not None else {}
        chains = _chains()  # with no home, none: every count is 0
        return JSONResponse(
            [
                {**p, "own_rules": own_rules(settings, chains.get(p["path"], []))}
                for p in state.data["projects"]
            ]
        )

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

    def _chain(path: str | None) -> list[str]:
        """The known projects whose gateway rules apply in the picked project, as the gateway
        finds them for a session there (see `project_chain`); empty for all projects."""
        if path is None or home is None:
            return []
        return project_chain(path, home, [p.path for p in state.inventory.projects])

    def _chains() -> dict[str, list[str]]:
        """Each known project's `_chain`, found in one pass."""
        if home is None:
            return {}
        return project_chains(home, [p.path for p in state.inventory.projects])

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

    def _library_list(request, project, path):
        """One tab of the Library's List: its groups, columns and the lines above them."""
        params = request.query_params
        tab = params.get("kind")
        show = params.get("show")
        answer = library_list(
            state.inventory,
            adapters,
            path,
            gateway_registered=bool(_registered()),
            tab=tab if tab in LIST_TABS else "plugin",
            show=show if show in LIST_SHOWS else "mine",
            q=params.get("q", ""),
            hidden=frozenset(c for c in params.get("hidden", "").split(",") if c),
            attention=params.get("attention") == "1",
        )
        return JSONResponse({"project": project, **answer})

    def _library_map(request, project, path):
        """The Library map: clients, plugins and skills by source, and what each plugin holds."""
        answer = library_map(state.inventory, adapters, path)
        return JSONResponse({"project": project, **answer})

    def _instructions_map(request, project, path):
        """The Instructions map: clients, the instruction files they read, and their imports."""
        answer = instructions_map(state.inventory, adapters, path)
        return JSONResponse({"project": project, **answer})

    def _explain(request, project, path):
        name = request.query_params.get("name")
        if not name:
            return _error("Say which item to explain.", 422)
        kind = request.query_params.get("kind") or None
        category = request.query_params.get("category") or None
        tools = load_tools(home) if home is not None else None
        definitions = explain(state.inventory, name, kind, path, category, tools)
        # What each change reaches, and whether Cursor loads Claude Code's plugins and folder.
        return JSONResponse(
            {
                "definitions": with_page_fields(definitions, state.inventory),
                "inherits": _inherits(),
            }
        )

    def _overview(request, project, path):
        held, problem = _kitden(path)
        return JSONResponse(overview(state.inventory, _registered(), path, held, problem))

    def _kitden(path):
        """The servers the Kitden gateway holds, and why its settings could not be read."""
        if home is None:
            return None, None
        held = held_servers(load_settings(home), _chain(path), load_tools(home), _chains())
        problem = UNREADABLE if settings_unreadable(home) else None
        return held, problem

    def _gateway_view(request, project, path):
        held, problem = _kitden(path)
        view = gateway_view(state.inventory, _registered(), path, kitden=held, problem=problem)
        # The picked project's own rules, for the scope bar; 0 for all projects, and None when
        # the gateway settings could not be read.
        rules = own_rules(load_settings(home), _chain(path)) if home is not None else 0
        if problem:
            rules = None
        return JSONResponse({**view, "own_rules": rules})

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
        # Every known project's chain, by its id: what "in some projects" would change there.
        ids = {p["path"]: p["id"] for p in state.data["projects"]}
        chains = {ids[k]: chain for k, chain in _chains().items() if k in ids}
        calls = load_calls(home)
        answer = tools_view(settings, load_tools(home), server, _chain(path), calls, chains)
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
            return JSONResponse([gateway_dict(g) for g in _registered()])
        if stand_ins:
            return _error(stand_ins.NOT_IN_DEMO, 422)
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
        if stand_ins:
            return list(stand_ins.CANNED_TOOLS)
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

    async def _steps_for(action: str, targets: list, params: dict) -> Built:
        """The steps one request makes, from that action's own builder. Raises ValueError with
        the review's words when the builder refuses. Writes nothing."""
        steps: list = []
        left_out = None
        copied = None  # the skill list's rows a skill copy takes, for the review's first line
        align = None  # Add missing: what each client lacks, for the review's checkboxes
        items: list = []  # the definitions a removal, switch, move or update changes
        # A definition kept from the last good read stays as it was until its file reads well.
        named = [t.get("item") for t in targets if isinstance(t, dict)] + [params.get("item")]
        found = [_item(str(i)) for i in named if i]
        kept = next((i for i in found if i is not None and i.stale_at), None)
        if kept is not None:
            raise ValueError(kept_refusal(kept))
        if action == GATEWAY_CONNECT:
            gateway = next((g for g in _registered() if g.id == params.get("gateway")), None)
            if gateway is None:
                raise ValueError("Register the gateway first.")
            clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
            steps = connect_steps(adapters, clients, gateway, str(params.get("name", "")))
        elif action == PLUGIN_INSTALL:
            offer = next(
                (o for o in catalog(state.inventory, adapters) if o["id"] == params.get("plugin")),
                None,
            )
            if offer is None:
                raise ValueError("This plugin is not in a marketplace on this computer.")
            clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
            steps = install_steps(adapters, offer, clients, _project_param(params))
        elif action == SKILL_INSTALL:
            # A project's own skill ("project/<name>") is read from that project only.
            wanted = str(params.get("skill", ""))
            project = _project_param(params)
            if wanted.startswith("project/") and project is None:
                raise ValueError(ONLY_IN_PROJECT)
            listed = (
                project_skills(state.inventory, adapters, project)
                if wanted.startswith("project/")
                else skill_catalog(state.inventory, adapters)
            )
            skill = next((s for s in listed if s["id"] == wanted), None)
            if skill is None:
                raise ValueError("This skill is not on this computer.")
            clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
            found = {c["id"] for c in state.data["clients"] if c["status"] == "found"}
            steps = skill_steps(adapters, skill, clients, found, project)
            copied = [skill]
        elif action == PLUGIN_SKILLS:
            if len(targets) != 1 or not isinstance(targets[0], dict):
                raise ValueError("Choose one client.")
            client = str(targets[0].get("client"))
            plugin_id = str(params.get("plugin"))
            skills = skill_catalog(state.inventory, adapters)
            if not any(s["plugin"] == plugin_id for s in skills):
                raise ValueError("This plugin has no skills on this computer.")
            found = {c["id"] for c in state.data["clients"] if c["status"] == "found"}
            steps = plugin_skill_steps(adapters, plugin_id, skills, client, found)
            left_out = plugin_skills_left_out(plugin_id, skills, client)
            copied = [s for s in skills if s["plugin"] == plugin_id]
        elif action == MARKETPLACE_ADD:
            if stand_ins:
                raise ValueError(stand_ins.NOT_IN_DEMO)
            try:
                found = await asyncio.to_thread(read_marketplace, str(params.get("source", "")))
            except LinkError as error:
                raise ValueError(str(error)) from None
            clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
            steps = marketplace_steps(adapters, found, clients)
        elif action == GATEWAY_SWITCH:
            gateway = next((g for g in _registered() if g.id == params.get("gateway")), None)
            if gateway is None:
                raise ValueError("Register the gateway first.")
            mcp = [i for i in state.inventory.items if i.kind is ItemKind.MCP_SERVER]
            steps = switch_steps(adapters, mcp, gateway, str(params.get("name", "")))
        elif action == SETUP_SERVER:
            command = (setup_command or installed_command)()
            if command is None:
                raise ValueError("Install the tool first: uv tool install <this folder>")
            clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
            provided = _states_in(state.inventory, "plugin")
            if any(c in provided for c in clients):
                raise ValueError("The kitden plugin already provides this server there.")
            steps = setup_server_steps(adapters, clients, command)
        elif action == SETUP_SERVER_UPDATE:
            ids = [str(t.get("item")) for t in targets if isinstance(t, dict)]
            items = [_item(i) for i in ids]
            if not items or any(i is None or not is_old_entry(i) for i in items):
                raise ValueError("Choose an old Kitden entry.")
            added = _states_in(state.inventory, "added", "plugin")
            command = None
            if any(i.client not in added for i in items):
                command = (setup_command or installed_command)()
                if command is None:
                    raise ValueError("Install the tool first: uv tool install <this folder>")
            steps = update_steps(adapters, items, added, command)
        elif action == SETUP_SERVER_ENABLE:
            clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
            entries = setup_server_state(state.inventory)
            entry = next((e for e in entries if [e["client"]] == clients), None)
            # Only the client's own entry, turned off: a plugin's is the plugin's switch.
            if entry is None or entry["state"] != "added" or entry["enabled"] is not False:
                raise ValueError("The kitden entry there is not turned off.")
            steps = enable_steps(adapters, clients[0])
        elif action == CLIENT_DISCONNECT:
            clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
            steps = disconnect_steps(adapters, state.inventory, clients)
        elif action == GATEWAY_MOVE and params.get("gateway") == KITDEN_GATEWAY:
            ids = [str(t.get("item")) for t in targets if isinstance(t, dict)]
            items = [_item(i) for i in ids]
            if not items or any(i is None for i in items):
                raise ValueError("Choose a known server.")
            known = [p.path for p in state.inventory.projects]
            added = _states_in(state.inventory, "added", "plugin")
            command = (setup_command or installed_command)()
            if command is None and {i.client for i in items} - added:
                raise ValueError("Install the tool first: uv tool install <this folder>")
            # A Codex entry that keeps only some tools on: Kitden needs the whole list.
            wanted = await asyncio.to_thread(tools_to_read, adapters, items, home, known)
            for name, server in wanted.items():
                tools = await _read_tools(name, server)
                if tools is None:
                    raise ValueError(
                        f"Kitden could not read the tools of {name}; it stays direct for now."
                    )
                save_tools(home, name, tools)
            # It may ask a remote server whether it signs in, so not on the event loop.
            steps = await asyncio.to_thread(
                local_move_steps,
                adapters,
                items,
                home,
                known,
                command,
                added_clients=added,
                sign_in=sign_in,
                keychain_run=keychain_run,
            )
        elif action == GATEWAY_ADD:
            # It may ask a remote server whether it signs in, so not on the event loop.
            steps = await asyncio.to_thread(
                gateway_add_steps,
                adapters,
                state.inventory,
                home,
                str(params.get("server", "")),
                sign_in=sign_in,
                keychain_run=keychain_run,
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
            steps = put_back_steps(adapters, home, server, clients, keychain_run)
        elif action == GATEWAY_MOVE_OUT:
            clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
            if len(clients) != 1:
                raise ValueError("Pick one client to move it into.")
            server = str(params.get("server", ""))
            # The client's entry first: when its file is wrong, no other step is built.
            steps = [
                *put_back_steps(adapters, home, server, clients, keychain_run),
                *remove_server_steps(home, server),
            ]
        elif action == GATEWAY_KEYCHAIN:
            steps = keychain_steps(home, str(params.get("server", "")))
        elif action == SKILL_RULE:
            steps = skill_rule_steps(adapters, state.inventory, home, targets, params)
        elif action == MCP_ADD:
            item = _item(str(params.get("item", "")))
            if item is None:
                raise ValueError("Choose a known server.")
            clients = [str(t.get("client")) for t in targets if isinstance(t, dict)]
            steps = add_server_steps(adapters, item, clients)
        elif action == PROJECT_ALIGN:
            folder = _project_param(params)
            if folder is None:
                raise ValueError("Unknown project.")
            found = {c["id"] for c in state.data["clients"] if c["status"] == "found"}
            wanted = params.get("chosen")
            chosen = [str(k) for k in wanted] if isinstance(wanted, list) else None
            steps, align = await asyncio.to_thread(
                align_steps, state.inventory, adapters, folder, found, chosen
            )
            if not steps:
                return Built(steps=[], align=align)
            copied = skill_catalog(state.inventory, adapters)
        elif action == GATEWAY_MOVE:
            gateway = next((g for g in _registered() if g.id == params.get("gateway")), None)
            if gateway is None:
                raise ValueError("Register the gateway first.")
            ids = [str(t.get("item")) for t in targets if isinstance(t, dict)]
            items = [_item(i) for i in ids]
            if not items or any(i is None for i in items):
                raise ValueError("Choose a known server.")
            steps = move_steps(adapters, items, gateway)
        elif action == SKILL_REMOVE:
            ids = [t.get("item") for t in targets if isinstance(t, dict)]
            items = [_item(str(i)) for i in ids]
            if len(items) != 1 or items[0] is None:
                raise ValueError("Choose one known item.")
            readers = skill_readers(state.inventory, items[0])
            keeps = skill_keepers(state.inventory, items[0], readers)
            steps = skill_remove_steps(adapters, items[0], readers, keeps)
        elif action in (REMOVE_DIRECT, PLUGIN_ENABLE, PLUGIN_DISABLE, PLUGIN_REMOVE):
            ids = [t.get("item") for t in targets if isinstance(t, dict)]
            items = [_item(str(i)) for i in ids]
            # A direct entry may go from several clients at once; a plugin is one item.
            one = len(items) == 1 or action == REMOVE_DIRECT
            if not items or any(i is None for i in items) or not one:
                raise ValueError("Choose one known item.")
            if action == REMOVE_DIRECT:
                steps = [s for item in items for s in remove_steps(adapters, item)]
            elif action == PLUGIN_REMOVE:
                steps = remove_plugin_steps(adapters, items[0])
            else:
                steps = plugin_steps(adapters, items[0], action == PLUGIN_ENABLE)
        else:
            raise ValueError("This action is not offered.")
        # No step into a file Kitden could not read, also for a place chosen after the add opened.
        broken = {p.path for p in state.inventory.problems if p.path}
        stuck = next((s.edit.path for s in steps if s.edit and s.edit.path in broken), None)
        if stuck:
            raise ValueError(unread_refusal(str(action), stuck))
        return Built(steps, items, left_out, copied, align)

    def _picked(body: dict) -> str | None:
        """The folder of the project picked at the top of the page, if any."""
        paths = {p["id"]: p["path"] for p in state.data["projects"]}
        return paths.get(str(body.get("picked") or ""))

    def _review(change: Change, built: Built, picked: str | None) -> dict:
        """The review's words for a previewed change: what each client shows after it and what
        Undo cannot bring back. Also marks the clients a plugin step reaches and sets where the
        steps go (`change.target`)."""
        # Only an added or removed plugin reaches Cursor through Claude Code.
        plugins = (PLUGIN_INSTALL, PLUGIN_REMOVE, PROJECT_ALIGN)
        cursor = _found_cursor() if change.action in plugins else None
        imports = bool(cursor and cursor.imports_claude_plugins())
        switches = (PLUGIN_REMOVE, PLUGIN_ENABLE, PLUGIN_DISABLE)
        switched = built.items[0] if change.action in switches else None
        mark_reach(change, state.inventory, switched, imports)
        after = after_words(
            change, state.inventory, cursor_imports=imports, skills=built.copied, home=home
        )
        # The review's first sentence: where the steps go (also for the project picked at the
        # top, which may have its own definition of what changes), and what Undo cannot bring
        # back.
        known = [p.path for p in state.inventory.projects]
        change.target = change_target(change, known, state.inventory, picked, built.items)
        words = {"after": after, "undo_note": undo_note(change)}
        if built.left_out is not None:
            words["left_out"] = built.left_out
        if built.align is not None:
            words["align"] = built.align
        return words

    async def preview(request: Request) -> JSONResponse:
        if engine is None:
            return _error("Changes are not available.", 404)
        body = await _body(request)
        action = body.get("action")
        targets = body.get("targets") if isinstance(body.get("targets"), list) else []
        params = body.get("params") if isinstance(body.get("params"), dict) else {}
        try:
            built = await _steps_for(action, targets, params)
            if action == PROJECT_ALIGN and not built.steps:
                # Every add would make a duplicate, so none is chosen: the list only, with no
                # change to apply.
                listing = {"action": action, "steps": [], "after": [], "align": built.align}
                return JSONResponse(listing)
            change = await asyncio.to_thread(engine.preview, str(action), built.steps)
        except ValueError as error:  # includes ChangeRefusedError
            return _error(refusal_words(error), 422)
        events.publish("change_state")
        words = _review(change, built, _picked(body))
        return JSONResponse({**change_dict(change), **words})

    def _needs(request: dict, made: Built) -> frozenset[str]:
        """The Kitden gateway servers a tray row needs held after Apply: the ones a move into
        it takes in (one it holds already gets no server step of its own)."""
        if request["kind"] != GATEWAY_MOVE or request["params"].get("gateway") != KITDEN_GATEWAY:
            return frozenset()
        return frozenset(item.name for item in made.items)

    async def _batch(
        requests: list[dict], keep: bool = True
    ) -> tuple[Change | None, list[Built], list[list[int]]]:
        """Build each request, refuse a clash, join the steps in tray order and preview them as
        one change; without `keep` the engine only checks them, and there is no change. Raises
        _RowRefused with the words and the row they come from."""
        assert engine is not None
        built = []
        added: set[str] = set()  # the server names the add rows before this one bring
        for request in requests:
            if request["kind"] == GATEWAY_ADD:
                # Two plugins may offer one name; the gateway holds one server per name.
                name = str(request["params"].get("server", "")).partition("/")[2]
                if name in added:
                    raise _RowRefused(f"{name} waits in preview already.", request["id"])
                added.add(name)
            try:
                made = await _steps_for(request["kind"], request["targets"], request["params"])
            except ValueError as error:
                raise _RowRefused(refusal_words(error), request["id"]) from None
            if not made.steps:
                raise _RowRefused("Nothing to change.", request["id"])
            built.append(made)
        parts = [
            Part(r["id"], r["title"], m.steps, _needs(r, m))
            for r, m in zip(requests, built, strict=True)
        ]
        clash = first_clash(parts)
        if clash is not None:
            raise _RowRefused(*clash)
        steps, maps = combine(parts)
        action = requests[0]["kind"] if len(requests) == 1 else BATCH
        try:
            if not keep:
                await asyncio.to_thread(engine.check, steps)
                return None, built, maps
            change = await asyncio.to_thread(engine.preview, action, steps)
        except ValueError as error:  # includes ChangeRefusedError
            raise _RowRefused(refusal_words(error), None) from None
        return change, built, maps

    async def batch_check(request: Request) -> JSONResponse:
        """Whether the last request can join the ones before it in the preview tray: the same
        checks as `batch_preview`, with nothing kept. A refusal is an answer, not an error:
        {"ok": False, "reason", "row"}, `row` being the request that cannot join."""
        if engine is None:
            return _error("Changes are not available.", 404)
        try:
            requests = requests_in(await _body(request))
            await _batch(requests, keep=False)
        except ValueError as error:
            return _error(str(error), 422)
        except _RowRefused as refused:
            row = refused.row or requests[-1]["id"]
            return JSONResponse({"ok": False, "reason": refused.reason, "row": row})
        return JSONResponse({"ok": True})

    async def batch_preview(request: Request) -> JSONResponse:
        """The preview tray as one change (changes/batch.py): each request's own builder, the
        steps joined in tray order. Apply, Undo and Cancel are the change's own verbs. A
        refusal names the row it comes from (`row`), or none when the engine refuses."""
        if engine is None:
            return _error("Changes are not available.", 404)
        body = await _body(request)
        try:
            requests = requests_in(body)
        except ValueError as error:
            return _error(str(error), 422)
        try:
            change, built, maps = await _batch(requests)
        except _RowRefused as refused:
            return JSONResponse({"detail": refused.reason, "row": refused.row}, status_code=422)
        assert change is not None
        picked = _picked(body)
        rows, answers = [], []
        for request, made, row_steps in zip(requests, built, maps, strict=True):
            row = {k: request[k] for k in ("id", "kind", "title", "detail")}
            row.update(project=None, steps=row_steps)
            part = part_of(change, row)
            # A row keeps the project it was asked in; the body's is for rows with none.
            words = _review(part, made, _picked(request) if request["picked"] else picked)
            if part.target["scope"] == "project":
                row["project"] = part.target["project"]
            rows.append(row)
            answers.append({**row, "target": part.target, **words})
        change.rows = rows
        known = [p.path for p in state.inventory.projects]
        items = [i for made in built for i in made.items]
        change.target = change_target(change, known, state.inventory, picked, items)
        events.publish("change_state")
        notes = list(dict.fromkeys(a["undo_note"] for a in answers if a["undo_note"]))
        answer = {**change_dict(change), "rows": answers, "undo_note": " ".join(notes) or None}
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
        # A tray change names the row of each step (`row`); a row is done only once the whole
        # change is verified.
        rows = step_rows(engine.changes[change_id].rows or [])

        def progress(change_id: str, done: int, total: int, step: int | None) -> None:
            # The engine works in a thread; the open pages hear it on the event loop.
            data = {"id": change_id, "done": done, "total": total, "row": rows.get(step)}
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
                engine.on_progress = lambda change_id, done, total, step: None
            if verb != "cancel":
                await state.rescan()
        if verb == "apply" and change.state is ChangeState.VERIFIED:
            # Servers just moved or added into the Kitden gateway: Details shows their tools
            # soon. In a tray change, only its move and add rows brought servers in.
            brings = (GATEWAY_MOVE, GATEWAY_ADD)
            if change.rows:
                moves = [part_of(change, r) for r in change.rows if r["kind"] in brings]
            else:
                moves = [change] if change.action in brings else []
            moved = [name for move in moves for name in moved_in(move)]
            if moved:
                refresh_later(moved)
        events.publish("change_state")
        return JSONResponse(change_dict(change), status_code=STATUS.get(change.state, 200))

    async def change_view(request: Request) -> JSONResponse:
        """One change as it stands now, so the page can check an Apply whose answer was lost.
        `stale`: a previewed change whose files changed since, which Apply would stop; an open
        review asks after each rescan. A file Kitden cannot read now counts as changed."""
        if engine is None:
            return _error("Changes are not available.", 404)
        change_id = request.path_params["change_id"]
        if change_id in engine.changes:
            try:
                stale = await asyncio.to_thread(engine.stale_reason, change_id) is not None
            except OSError:
                stale = True
            return JSONResponse({**change_dict(engine.changes[change_id]), "stale": stale})
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

    async def market_server_list(request: Request) -> JSONResponse:
        """The MCP servers that marketplace plugins on this computer bring, for the Add panel,
        each with why the gateway cannot take it (if so). No address and no command."""
        held = set(load_settings(home)["servers"]) if home is not None else set()
        rows = await asyncio.to_thread(market_servers, state.inventory, adapters, held)
        return JSONResponse({"servers": rows})

    async def library_offer_list(request: Request) -> JSONResponse:
        """The plugins and skills the marketplaces on this computer offer, for the Library's add
        panel, each with the clients that can add it. No paths."""
        rows = await asyncio.to_thread(library_offers, state.inventory, adapters)
        return JSONResponse({"offers": rows})

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
        gateway = next((g for g in _registered() if g.id == item.via_gateway), None)
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
            Route("/api/batch/preview", batch_preview, methods=["POST"]),
            Route("/api/batch/check", batch_check, methods=["POST"]),
            Route("/api/changes/{change_id}", change_view),
            Route("/api/changes/{change_id}/{verb}", change_action, methods=["POST"]),
            Route("/api/commands", commands),
            Route("/api/map", _read_model(_map)),
            Route("/api/library", _read_model(_library)),
            Route("/api/library-list", _read_model(_library_list)),
            Route("/api/library-map", _read_model(_library_map)),
            Route("/api/instructions-map", _read_model(_instructions_map)),
            Route("/api/offer", offer_view),
            Route("/api/market-servers", market_server_list),
            Route("/api/library-offers", library_offer_list),
            Route("/api/explain", _read_model(_explain)),
            Route("/api/overview", _read_model(_overview)),
            Route("/api/gateway-view", _read_model(_gateway_view)),
            Route("/api/events", stream),
            Route("/api/progress", progress),
            Route("/api/about", about),
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
