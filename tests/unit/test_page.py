"""One page per home folder: the lock and the page record (feature 002, FR-009, FR-010)."""

import stat
import subprocess
import sys
import time

from kitden import page
from kitden.gateways import data_dir


def test_only_one_page_holds_the_lock(tmp_path):
    first, second = page.PageLock(tmp_path), page.PageLock(tmp_path)
    assert first.acquire()
    try:
        assert not second.acquire()
        assert page.page_running(tmp_path)
    finally:
        first.release()
    assert not page.page_running(tmp_path)


def test_the_lock_is_released_when_the_page_process_dies(tmp_path):
    code = (
        "import sys, time; sys.path.insert(0, 'src'); from kitden import page; "
        f"assert page.PageLock({str(tmp_path)!r}).acquire(); print('locked', flush=True); "
        "time.sleep(60)"
    )
    process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)  # noqa: S603
    try:
        assert process.stdout.readline().strip() == "locked"
        assert page.page_running(tmp_path)
    finally:
        process.kill()
        process.wait(timeout=10)
    assert not page.page_running(tmp_path)


def test_the_record_is_private_and_removed_on_stop(tmp_path):
    page.write_record(tmp_path, port=47811, token="tok", background=True)
    path = data_dir(tmp_path) / "page.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    record = page.read_record(tmp_path)
    assert (record["port"], record["token"], record["background"]) == (47811, "tok", True)
    assert page.start_link(record) == "http://127.0.0.1:47811/?token=tok"
    page.remove_record(tmp_path)
    assert page.read_record(tmp_path) is None


def test_a_record_without_a_running_page_is_stale(tmp_path):
    page.write_record(tmp_path, port=47811, token="tok", background=False)
    assert page.running_page(tmp_path) is None
    assert page.read_record(tmp_path) is None


def test_the_running_page_is_found_through_the_lock(tmp_path):
    lock = page.PageLock(tmp_path)
    assert lock.acquire()
    try:
        page.write_record(tmp_path, port=47811, token="tok", background=False)
        assert page.running_page(tmp_path)["port"] == 47811
    finally:
        lock.release()


def test_waiting_for_a_record_gives_up(tmp_path):
    started = time.monotonic()
    assert page.wait_for_record(tmp_path, seconds=0.3) is None
    assert time.monotonic() - started < 2


# Stop when no tab is open (feature 002, FR-012, research R6) --------------------------------


def test_no_tab_for_the_whole_wait_means_stop():
    clock = page.IdleClock(wait=600, now=0)
    assert not clock.tick(tabs=0, busy=False, now=599)
    assert clock.tick(tabs=0, busy=False, now=600)


def test_a_tab_within_the_wait_keeps_the_page():
    clock = page.IdleClock(wait=600, now=0)
    assert not clock.tick(tabs=1, busy=False, now=500)
    assert not clock.tick(tabs=0, busy=False, now=1000)
    assert clock.tick(tabs=0, busy=False, now=1100)


def test_a_running_change_delays_the_stop():
    clock = page.IdleClock(wait=600, now=0)
    assert not clock.tick(tabs=0, busy=True, now=700)
    assert not clock.tick(tabs=0, busy=False, now=1200)
    assert clock.tick(tabs=0, busy=False, now=1300)


def test_the_page_counts_open_tabs_and_running_changes():
    # An endless event stream cannot be closed by the test client, so count streams directly.
    from kitden.views.inventory import Inventory
    from kitden.web.app import Broadcaster, create_app

    events = Broadcaster()
    queue = events.subscribe()
    assert events.count == 1
    events.unsubscribe(queue)
    assert events.count == 0
    activity = create_app(lambda: Inventory(), token="tok", port=47800).state.activity
    assert (activity.tabs(), activity.busy()) == (0, False)


def test_the_server_stops_when_asked(tmp_path):
    import time

    from kitden.cli import pick_port, run_server

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            while (await receive())["type"] != "lifespan.shutdown":
                await send({"type": "lifespan.startup.complete"})
            await send({"type": "lifespan.shutdown.complete"})

    started = time.monotonic()
    run_server(app, "127.0.0.1", pick_port(47900), stop_when=lambda: True)
    assert time.monotonic() - started < 5


def test_the_background_start_does_not_run_from_the_callers_folder(tmp_path, monkeypatch):
    # `python -m` would put the caller's folder first on the import path (final review).
    import os
    import subprocess

    seen = {}
    monkeypatch.setattr(
        subprocess, "Popen", lambda command, **kw: seen.update(command=command, cwd=kw.get("cwd"))
    )
    monkeypatch.chdir(tmp_path)
    page.start_background(tmp_path / "home", "home")
    command = seen["command"]
    assert command[1:4] == ["-P", "-m", "kitden"]
    assert seen["cwd"] == str(data_dir(tmp_path / "home"))
    assert command[command.index("--home") + 1] == str(tmp_path / "home")
    assert os.path.isabs(command[command.index("--home") + 1])


def test_the_event_route_counts_a_tab_until_it_disconnects():
    import asyncio

    from starlette.testclient import TestClient

    from kitden.views.inventory import Inventory
    from kitden.web.app import create_app

    app = create_app(lambda: Inventory(), token="tok", port=47800)
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        cookie = "; ".join(f"{k}={v}" for k, v in client.cookies.items())
    activity = app.state.activity

    async def probe():
        gone = asyncio.Event()
        sent = asyncio.Event()

        async def receive():
            if not hasattr(receive, "started"):
                receive.started = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await gone.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.body":
                sent.set()

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/events",
            "raw_path": b"/api/events",
            "query_string": b"",
            "headers": [(b"host", b"127.0.0.1:47800"), (b"cookie", cookie.encode())],
            "scheme": "http",
            "server": ("127.0.0.1", 47800),
            "client": ("127.0.0.1", 50000),
            "http_version": "1.1",
            "root_path": "",
        }
        call = asyncio.create_task(app(scope, receive, send))
        await asyncio.wait_for(sent.wait(), 5)
        open_tabs = activity.tabs()
        gone.set()
        await asyncio.wait_for(call, 5)
        return open_tabs, activity.tabs()

    assert asyncio.run(probe()) == (1, 0)


# The page listens before its first scan (owner check: the first open took 10+ s) -----------


def _slow_build(seconds, calls):
    from kitden.views.inventory import Inventory

    def build():
        calls.append(1)
        time.sleep(seconds)
        return Inventory()

    return build


def test_a_page_can_listen_before_its_first_scan():
    from starlette.testclient import TestClient

    from kitden.web.app import create_app

    calls = []
    started = time.monotonic()
    app = create_app(_slow_build(0.5, calls), token="tok", port=47800, first_scan_later=True)
    assert time.monotonic() - started < 0.3 and calls == []
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        assert client.get("/api/clients").status_code == 200  # waits for the first scan
    assert calls == [1]


def test_a_failing_first_scan_still_lets_the_page_answer():
    from starlette.testclient import TestClient

    from kitden.web.app import create_app

    def broken():
        raise RuntimeError("cannot read")

    app = create_app(broken, token="tok", port=47800, first_scan_later=True)
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        assert client.get("/api/clients").json() == []


def test_the_page_does_not_load_the_mcp_sdk():
    # The MCP SDK takes about half a second to import; only `kitden mcp` needs it.
    import subprocess
    import sys

    code = "import sys, kitden.web.app, kitden.cli; print('mcp' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)  # noqa: S603
    assert out.stdout.strip() == "False"
