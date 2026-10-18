import asyncio
import time

from starlette.testclient import TestClient

from kitden.views.inventory import Inventory
from kitden.web.app import Broadcaster, State, create_app, event_lines

ORIGIN = "http://127.0.0.1:47800"


def test_rescan_announces_start_and_finish():
    async def scenario():
        events = Broadcaster()
        state = State(lambda: Inventory(), events)
        queue = events.subscribe()
        await state.rescan()
        return [queue.get_nowait(), queue.get_nowait()]

    assert asyncio.run(scenario()) == ["rescan_started", "rescan_finished"]


def _collect(queue, checks, heartbeat=15.0):
    answers = iter(checks)

    async def is_disconnected():
        return next(answers)

    async def run():
        return [line async for line in event_lines(queue, is_disconnected, heartbeat)]

    return asyncio.run(run())


def test_event_stream_sends_events_until_the_browser_leaves():
    queue = asyncio.Queue()
    queue.put_nowait("rescan_finished")
    lines = _collect(queue, [False, True])
    assert lines == [": connected\n\n", "event: rescan_finished\ndata: {}\n\n"]


def test_event_stream_sends_heartbeats_when_idle():
    lines = _collect(asyncio.Queue(), [False, True], heartbeat=0.01)
    assert lines == [": connected\n\n", ": heartbeat\n\n"]


def test_a_changed_file_triggers_a_rescan(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("a = 1\n")
    time.sleep(1)
    builds = []

    def build():
        builds.append(1)
        return Inventory()

    app = create_app(build, token="tok", port=47800, watch_folders=[tmp_path], debounce_ms=100)
    with TestClient(app, base_url=ORIGIN):
        time.sleep(0.5)
        config.write_text("a = 2\n")
        deadline = time.monotonic() + 8
        while len(builds) < 2 and time.monotonic() < deadline:
            time.sleep(0.1)
    assert len(builds) >= 2  # the first build at start, then one after the change
