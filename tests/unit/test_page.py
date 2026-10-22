"""One page per home folder: the lock and the page record (feature 002, FR-009, FR-010)."""

import re
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


def _progress_done(client, tries=60):
    for _ in range(tries):
        view = client.get("/api/progress").json()
        if view["ready"] and all(s["done"] for s in view["steps"]):
            return view
        time.sleep(0.05)
    raise AssertionError(f"the progress never ended: {view}")


def test_scans_are_quick_and_a_slow_answer_brings_one_more(tmp_path):
    import threading

    from starlette.testclient import TestClient

    from kitden.views.inventory import Inventory
    from kitden.web.app import create_app

    calls = []

    def build(quick=False, on_step=None, on_slow_answer=None):
        calls.append(quick)
        time.sleep(0.3)
        if on_step:
            on_step("codex")
        inventory = Inventory()
        if len(calls) == 1:  # Codex's list is on its way; it answers a moment later
            inventory.partial = True
            threading.Timer(0.2, on_slow_answer).start()
        return inventory

    app = create_app(build, token="tok", port=47800, first_scan_later=True, quick_first=True)
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        early = client.get("/api/progress").json()  # answers before the first scan is done
        assert early["ready"] is False
        assert [s["name"] for s in early["steps"]] == [
            "Claude Code",
            "Codex",
            "Cursor",
            "Codex plugins",
        ]
        assert client.get("/api/clients").status_code == 200
        _progress_done(client)
    assert calls == [True, True]  # the second scan is quick too: the answer is cached by then


def test_a_failing_quick_scan_still_ends_its_progress():
    from starlette.testclient import TestClient

    from kitden.web.app import create_app

    def broken(quick=False, on_step=None, on_slow_answer=None):
        raise RuntimeError("cannot read")

    app = create_app(broken, token="tok", port=47800, first_scan_later=True, quick_first=True)
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        assert client.get("/api/clients").json() == []
        _progress_done(client)


def test_progress_tells_the_open_pages_each_step():
    from kitden.web.app import Broadcaster, Progress

    events = Broadcaster()
    queue = events.subscribe()
    progress = Progress(events)
    progress.start(["Codex"], ["marketplaces"])
    progress.done("Codex")
    progress.finish()
    sent = [queue.get_nowait() for _ in range(3)]
    assert [name for name, _ in sent] == ["scan_progress"] * 3
    assert sent[1][1]["steps"][0] == {"name": "Codex", "done": True, "later": False}
    assert sent[2][1] == {
        "ready": True,
        "steps": [
            {"name": "Codex", "done": True, "later": False},
            {"name": "marketplaces", "done": True, "later": True},
        ],
    }


def test_the_marketplaces_are_read_once_the_page_has_its_data(tmp_path):
    from starlette.testclient import TestClient

    from kitden.views.inventory import Inventory
    from kitden.web.app import create_app

    app = create_app(
        lambda quick=False, on_step=None, on_slow_answer=None: Inventory(),
        token="tok",
        port=47800,
        home=tmp_path,
        first_scan_later=True,
        quick_first=True,
    )
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        names = [s["name"] for s in client.get("/api/progress").json()["steps"]]
        assert names[-1] == "marketplaces"


def test_the_page_does_not_load_the_mcp_sdk():
    # The MCP SDK takes about half a second to import; only `kitden mcp` needs it.
    import subprocess
    import sys

    code = "import sys, kitden.web.app, kitden.cli; print('mcp' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)  # noqa: S603
    assert out.stdout.strip() == "False"


# Versions arrive in the background, after the first scan (spec 4.1) -------------------------


def _client(client_id, version, found=True):
    from kitden.model import Client, ClientStatus

    status = ClientStatus.FOUND if found else ClientStatus.NOT_FOUND
    return Client(id=client_id, display_name=client_id, status=status, version=version)


def _sent(queue):
    out = []
    while not queue.empty():
        event = queue.get_nowait()
        out.append(event if isinstance(event, tuple) else (event, None))
    return out


def test_versions_come_after_the_first_scan_and_the_page_is_told():
    from starlette.testclient import TestClient

    from kitden.views.inventory import Inventory
    from kitden.web.app import create_app

    known: dict[str, str] = {}
    calls = []

    def build(quick=False, on_step=None, on_slow_answer=None):
        calls.append(dict(known))
        return Inventory(clients=[_client("claude_code", known.get("claude_code"))])

    def refresh():
        known["claude_code"] = "2.1.300"
        return dict(known)

    app = create_app(
        build,
        token="tok",
        port=47800,
        first_scan_later=True,
        quick_first=True,
        version_refresh=refresh,
    )
    queue = app.state.events.subscribe()
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        early = client.get("/api/progress").json()
        names = [s["name"] for s in early["steps"]]
        assert names[-2:] == ["Codex plugins", "client versions"]
        _progress_done(client)
        assert client.get("/api/clients").json()[0]["version"] == "2.1.300"
    assert calls == [{}, {"claude_code": "2.1.300"}]  # one more scan, with the new version
    events = [name for name, _ in _sent(queue)]
    assert events.count("versions") == 1
    assert events.index("versions") > events.index("rescan_finished")


def test_the_same_versions_bring_no_more_scans():
    from starlette.testclient import TestClient

    from kitden.views.inventory import Inventory
    from kitden.web.app import create_app

    calls = []

    def build(quick=False, on_step=None, on_slow_answer=None):
        calls.append(1)
        return Inventory(clients=[_client("codex", "0.159.2")])

    app = create_app(
        build,
        token="tok",
        port=47800,
        first_scan_later=True,
        quick_first=True,
        version_refresh=lambda: {"codex": "0.159.2", "cursor": None},
    )
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        _progress_done(client)
    assert calls == [1]


def test_a_failed_refresh_keeps_unknown_and_says_so_once(capsys):
    from starlette.testclient import TestClient

    from kitden.views.inventory import Inventory
    from kitden.web.app import create_app

    def refresh():
        raise OSError("no such file")

    app = create_app(
        lambda quick=False, on_step=None, on_slow_answer=None: Inventory(
            clients=[_client("claude_code", None)]
        ),
        token="tok",
        port=47800,
        first_scan_later=True,
        quick_first=True,
        version_refresh=refresh,
    )
    queue = app.state.events.subscribe()
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        _progress_done(client)
        assert client.get("/api/clients").json()[0]["version"] is None
    err = capsys.readouterr().err
    assert err.count("Reading the client versions failed (OSError).") == 1
    assert "no such file" not in err
    assert [name for name, _ in _sent(queue)].count("versions") == 1


def test_a_plain_first_scan_also_reads_the_versions():
    from starlette.testclient import TestClient

    from kitden.views.inventory import Inventory
    from kitden.web.app import create_app

    asked = []

    def refresh():
        asked.append(1)
        return {}

    app = create_app(
        lambda: Inventory(), token="tok", port=47800, first_scan_later=True, version_refresh=refresh
    )
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        client.get("/api/clients")
        for _ in range(60):
            if asked:
                break
            time.sleep(0.05)
    assert asked == [1]


def test_codex_plugins_are_checked_again_once_its_version_is_known():
    import threading

    from starlette.testclient import TestClient

    from kitden.views.inventory import Inventory
    from kitden.web.app import create_app

    known: dict[str, str] = {}

    def build(quick=False, on_step=None, on_slow_answer=None):
        inventory = Inventory(clients=[_client("codex", known.get("codex"))])
        if known and not hasattr(build, "asked"):  # the version is known: the list is asked
            build.asked = True
            inventory.partial = True
            threading.Timer(0.2, on_slow_answer).start()
        return inventory

    def refresh():
        known["codex"] = "0.159.2"
        return dict(known)

    app = create_app(
        build,
        token="tok",
        port=47800,
        first_scan_later=True,
        quick_first=True,
        version_refresh=refresh,
    )
    queue = app.state.events.subscribe()
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        _progress_done(client)
    plugins = [
        next(s["done"] for s in data["steps"] if s["name"] == "Codex plugins")
        for name, data in _sent(queue)
        if name == "scan_progress"
    ]
    # Done after the first scan, open again while Codex answers, done at the end.
    assert re.search(r"1+0+1+$", "".join("1" if done else "0" for done in plugins))


def test_a_client_found_only_by_its_command_is_found_once_the_versions_are_read(
    tmp_path, monkeypatch
):
    from starlette.testclient import TestClient

    from kitden.clients import version_cache
    from kitden.views.inventory import build_inventory
    from kitden.web.app import create_app
    from tests.conftest import fake_client_command

    home = tmp_path / "home"
    home.mkdir()
    claude = fake_client_command(tmp_path, "claude", "echo '2.1.300 (Claude Code)'")
    monkeypatch.setattr(
        version_cache,
        "version_command",
        lambda client: [str(claude), "--version"] if client == "claude_code" else None,
    )

    def status():
        found = client.get("/api/clients").json()
        return next((c["status"], c["version"]) for c in found if c["id"] == "claude_code")

    app = create_app(
        lambda **options: build_inventory(home, **options),
        token="tok",
        port=47800,
        home=home,
        first_scan_later=True,
        quick_first=True,
    )
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        client.get("/api/clients")
        _progress_done(client)
        assert status() == ("found", "2.1.300")
    assert version_cache.cached_version(home, "claude_code") == "2.1.300"
