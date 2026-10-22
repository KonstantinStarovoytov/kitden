import os
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import kitden
import kitden.cli as cli
import kitden.demo
from kitden import page
from kitden.cli import main, pick_port
from kitden.demo import VERSIONS


def test_version_prints_name_and_version_and_exits_zero(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"kitden {kitden.__version__}"


def _busy(port):
    sock = socket.socket()
    sock.bind(("127.0.0.1", port))
    sock.listen()
    return sock


def test_pick_port_skips_a_busy_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        start = probe.getsockname()[1]
    busy = _busy(start)
    try:
        assert pick_port(start, tries=5) not in (None, start)
        assert pick_port(start, tries=1) is None
    finally:
        busy.close()


def test_serve_runs_on_loopback_and_prints_a_token_link(monkeypatch, capsys):
    calls = {}
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: 47811)
    monkeypatch.setattr(
        cli, "run_server", lambda app, host, port, **kw: calls.update(host=host, port=port)
    )
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: calls.update(opened=url))
    monkeypatch.setattr(cli, "build_inventory", lambda home=None: cli.Inventory())

    assert main(["serve", "--no-browser"]) == 0

    assert calls == {"host": "127.0.0.1", "port": 47811}
    out = capsys.readouterr().out
    assert re.search(r"http://127\.0\.0\.1:47811/\?token=[A-Za-z0-9_-]{40,}", out)


def test_serve_opens_the_browser_once_started(monkeypatch):
    opened = []
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: 47812)
    monkeypatch.setattr(cli, "run_server", lambda app, host, port, on_started, **kw: on_started())
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    monkeypatch.setattr(cli, "build_inventory", lambda home=None: cli.Inventory())
    main(["serve"])
    assert len(opened) == 1 and opened[0].startswith("http://127.0.0.1:47812/?token=")


def test_serve_exits_2_without_a_free_port(monkeypatch):
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: None)
    assert main(["serve", "--no-browser"]) == 2


def test_start_link_is_visible_to_a_program_reading_the_output(tmp_path):
    """The link must be flushed even when stdout is a pipe, not a terminal."""
    process = subprocess.Popen(
        [sys.executable, "-m", "kitden", "serve", "--no-browser", "--home", str(tmp_path)],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        first_line = process.stdout.readline()
    finally:
        process.terminate()
        process.wait(timeout=10)
    assert "http://127.0.0.1:" in first_line and "token=" in first_line


def test_mcp_command_serves_the_read_only_server(monkeypatch, tmp_path):
    import kitden.mcp_server as mcp_server

    started = []
    monkeypatch.setattr(mcp_server, "run", lambda home=None: started.append(home))
    assert cli.main(["mcp", "--home", str(tmp_path)]) == 0
    assert started == [tmp_path]


def test_installed_command_is_an_absolute_path():
    from kitden.mcp_server import installed_command

    command = installed_command()
    assert command is not None and command.startswith("/")
    assert command.endswith("/kitden")


def test_server_stops_quickly_even_with_an_open_page(monkeypatch):
    # An open page keeps an event stream; Ctrl+C must not wait for it forever.
    import uvicorn

    calls = []
    monkeypatch.setattr(uvicorn.Server, "run", lambda self: calls.append(self.config))
    cli.run_server(object(), "127.0.0.1", 47800)
    assert calls[0].timeout_graceful_shutdown <= 3


def test_every_command_copies_the_old_data_folder_once(tmp_path, capsys):
    from kitden.gateways import OLD_DATA_DIR, data_dir

    (tmp_path / OLD_DATA_DIR).mkdir(parents=True)
    (tmp_path / OLD_DATA_DIR / "settings.json").write_text('{"gateways": []}')
    cli.main(["scan", "--home", str(tmp_path)])
    assert (data_dir(tmp_path) / "settings.json").is_file()
    assert "Copied" in capsys.readouterr().err


def test_tests_never_see_the_real_home():
    assert "real-home" in str(Path.home())


# kitden open and one page per home folder (feature 002, T011) --------------------------------


def _hold_page(home, port=47899, token="tok"):
    lock = page.PageLock(home)
    assert lock.acquire()
    page.write_record(home, port=port, token=token, background=True)
    return lock


def test_open_with_a_running_page_opens_it_and_starts_nothing(tmp_path, monkeypatch, capsys):
    lock = _hold_page(tmp_path)
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    monkeypatch.setattr(page, "start_background", lambda *a: pytest.fail("started a second page"))
    try:
        assert main(["open", "--home", str(tmp_path)]) == 0
    finally:
        lock.release()
    assert opened == ["http://127.0.0.1:47899/?token=tok"]
    assert "http://127.0.0.1:47899/?token=tok" in capsys.readouterr().out


def test_open_starts_a_background_page_when_none_runs(tmp_path, monkeypatch):
    locks = []

    def fake_start(home, home_arg):
        locks.append(_hold_page(home, port=47898, token="new"))

    monkeypatch.setattr(page, "start_background", fake_start)
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    try:
        assert main(["open", "--home", str(tmp_path)]) == 0
    finally:
        for lock in locks:
            lock.release()
    assert opened == ["http://127.0.0.1:47898/?token=new"]


def test_open_gives_up_when_the_page_does_not_start(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(page, "start_background", lambda home, home_arg: None)
    monkeypatch.setattr(page, "WAIT_SECONDS", 0.3)
    assert main(["open", "--home", str(tmp_path)]) == 4
    assert "page.log" in capsys.readouterr().err


def test_open_without_a_browser_only_prints_the_link(tmp_path, monkeypatch, capsys):
    lock = _hold_page(tmp_path)
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: pytest.fail("opened a browser"))
    try:
        assert main(["open", "--no-browser", "--home", str(tmp_path)]) == 0
    finally:
        lock.release()
    assert "token=tok" in capsys.readouterr().out


def test_no_command_means_open(tmp_path, monkeypatch):
    lock = _hold_page(tmp_path)
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    try:
        assert main(["--home", str(tmp_path)]) == 0
    finally:
        lock.release()
    assert opened == ["http://127.0.0.1:47899/?token=tok"]


def test_serve_opens_the_running_page_instead_of_a_second_one(tmp_path, monkeypatch):
    lock = _hold_page(tmp_path)
    monkeypatch.setattr(cli, "run_server", lambda *a, **kw: pytest.fail("started a second page"))
    try:
        assert main(["serve", "--no-browser", "--home", str(tmp_path)]) == 0
    finally:
        lock.release()


def test_serve_writes_the_record_once_started_and_removes_it(tmp_path, monkeypatch):
    seen = {}

    def fake_run(app, host, port, on_started, **kw):
        on_started()
        seen.update(record=page.read_record(tmp_path), running=page.page_running(tmp_path))

    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: 47811)
    monkeypatch.setattr(cli, "run_server", fake_run)
    assert main(["serve", "--no-browser", "--home", str(tmp_path)]) == 0
    assert seen["record"]["port"] == 47811 and seen["running"]
    assert page.read_record(tmp_path) is None
    assert not page.page_running(tmp_path)


@pytest.mark.parametrize(("extra", "stops"), [([], False), (["--background"], True)])
def test_only_a_background_page_stops_by_itself(tmp_path, monkeypatch, extra, stops):
    seen = {}
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: 47813)
    monkeypatch.setattr(
        cli, "run_server", lambda app, host, port, stop_when=None, **kw: seen.update(s=stop_when)
    )
    main(["serve", "--no-browser", "--home", str(tmp_path), *extra])
    assert (seen["s"] is not None) == stops
    if stops:
        assert seen["s"]() is False  # just started: no reason to stop yet


# Final review fixes (feature 002) ----------------------------------------------------------


def test_open_ignores_a_record_left_by_a_page_that_ended(tmp_path, monkeypatch, capsys):
    import threading

    page.write_record(tmp_path, port=47999, token="STALE", background=True)  # no page holds it
    locks = []

    def slow_start(home, home_arg):
        lock = page.PageLock(home)
        assert lock.acquire()
        locks.append(lock)
        threading.Timer(0.3, page.write_record, (home, 47802, "NEW", True)).start()

    monkeypatch.setattr(page, "start_background", slow_start)
    try:
        assert main(["open", "--no-browser", "--home", str(tmp_path)]) == 0
    finally:
        for lock in locks:
            lock.release()
    out = capsys.readouterr().out
    assert "token=NEW" in out and "STALE" not in out


def test_serve_removes_a_record_left_by_a_page_that_ended(tmp_path, monkeypatch):
    page.write_record(tmp_path, port=47999, token="STALE", background=False)
    seen = {}

    def fake_run(app, host, port, on_started, **kw):
        seen["before"] = page.read_record(tmp_path)

    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: 47811)
    monkeypatch.setattr(cli, "run_server", fake_run)
    main(["serve", "--no-browser", "--home", str(tmp_path)])
    assert seen["before"] is None


@pytest.mark.parametrize("signal_name", ["SIGTERM", "SIGINT"])
def test_a_stopped_page_exits_cleanly_and_removes_its_record(tmp_path, signal_name):
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "kitden", "serve", "--no-browser", "--home", str(tmp_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while page.read_record(tmp_path) is None and time.monotonic() < deadline:
            time.sleep(0.1)
        assert page.read_record(tmp_path) is not None
        process.send_signal(getattr(signal, signal_name))
        _, err = process.communicate(timeout=15)
    finally:
        process.kill()
    assert process.returncode == 0, err
    assert "Traceback" not in err
    assert page.read_record(tmp_path) is None


def test_a_background_page_never_writes_its_link(tmp_path, monkeypatch, capsys):
    # A background page's output goes to page.log; the start link holds the session token.
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: 47814)
    monkeypatch.setattr(cli, "run_server", lambda app, host, port, on_started, **kw: on_started())
    main(["serve", "--background", "--no-browser", "--home", str(tmp_path)])
    lock = _hold_page(tmp_path)
    try:
        main(["serve", "--background", "--no-browser", "--home", str(tmp_path)])
    finally:
        lock.release()
    assert "token=" not in capsys.readouterr().out


def test_open_waits_long_enough_for_a_slow_first_scan():
    # A large home took 4.2 s to scan (feature 001 validation): 5 s is a goal, not a limit.
    assert page.WAIT_SECONDS >= 15


def test_serve_lets_the_page_listen_before_the_first_scan(tmp_path, monkeypatch):
    import kitden.web.app as web

    seen = {}
    real = web.create_app
    monkeypatch.setattr(web, "create_app", lambda *a, **kw: seen.update(kw) or real(*a, **kw))
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: 47815)
    monkeypatch.setattr(cli, "run_server", lambda *a, **kw: None)
    main(["serve", "--no-browser", "--home", str(tmp_path)])
    assert seen["first_scan_later"] is True


# kitden demo (visual management, Part 1) ---------------------------------------------------


def _demo_run(monkeypatch, seen, server=None):
    real = kitden.demo.build_demo_home
    monkeypatch.setattr(
        kitden.demo,
        "build_demo_home",
        lambda root, size: seen.setdefault("home", real(root, size)),
    )
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: start)
    monkeypatch.setattr(cli, "run_server", server or (lambda app, host, port, **kw: None))


def test_demo_serves_the_sample_and_deletes_it_on_exit(monkeypatch, capsys):
    seen = {}

    def server(app, host, port, **kw):
        home = seen["home"]
        assert home.is_dir() and port == cli.DEMO_PORT
        assert home == home.resolve()  # macOS: /var is a link to /private/var
        link = re.search(r"http://127\.0\.0\.1:\d+/\?token=\S+", capsys.readouterr().out)
        with TestClient(app, base_url=f"http://127.0.0.1:{port}") as tab:
            tab.get(link.group(0))
            assert tab.get("/api/about").json()["demo"] is True
            assert {c["id"]: c["version"] for c in tab.get("/api/clients").json()} == VERSIONS

    _demo_run(monkeypatch, seen, server)
    assert main(["demo", "--no-browser"]) == 0
    assert not seen["home"].parent.exists()


def test_demo_says_it_runs_a_sample_and_how_to_stop(monkeypatch, capsys):
    _demo_run(monkeypatch, {})
    main(["demo", "--no-browser", "--size", "small"])
    lines = capsys.readouterr().out.splitlines()
    assert re.fullmatch(
        r"Kitden demo is running on a sample setup\. Open: "
        r"http://127\.0\.0\.1:47900/\?token=[A-Za-z0-9_-]{40,}",
        lines[0],
    )
    assert lines[1] == "Press Ctrl+C to stop. The sample folder is deleted then."


def test_demo_deletes_its_folder_when_the_server_fails(monkeypatch):
    seen = {}

    def server(app, host, port, **kw):
        raise RuntimeError("the server broke")

    _demo_run(monkeypatch, seen, server)
    with pytest.raises(RuntimeError):
        main(["demo", "--no-browser", "--size", "small"])
    assert not seen["home"].parent.exists()


def test_demo_exits_2_without_a_free_port(monkeypatch, capsys):
    seen = {}
    _demo_run(monkeypatch, seen, lambda *a, **kw: pytest.fail("served without a port"))
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: None)
    assert main(["demo", "--no-browser", "--size", "small"]) == 2
    assert "No free port from 47900." in capsys.readouterr().err
    assert not seen["home"].parent.exists()


def test_demo_never_touches_the_real_home(monkeypatch):
    real = Path.home()  # the fake home conftest gives every test
    old = real / "Library/Application Support/agentsetup/settings.json"
    old.parent.mkdir(parents=True)
    old.write_text("{}")
    before = sorted(p.relative_to(real) for p in real.rglob("*"))
    _demo_run(monkeypatch, {})
    assert main(["demo", "--no-browser", "--size", "small"]) == 0
    assert sorted(p.relative_to(real) for p in real.rglob("*")) == before


def test_demo_opens_the_browser_once_started(monkeypatch):
    opened = []
    _demo_run(monkeypatch, {}, lambda app, host, port, on_started, **kw: on_started())
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    main(["demo", "--size", "small"])
    assert len(opened) == 1 and opened[0].startswith("http://127.0.0.1:47900/?token=")


def test_demo_takes_only_the_three_sizes():
    with pytest.raises(SystemExit) as stopped:
        main(["demo", "--size", "huge"])
    assert stopped.value.code == 2


def test_a_second_stop_does_not_stop_the_delete(monkeypatch):
    # `uv run` and `uvx` pass the program a second Ctrl+C about 200 ms after the terminal's
    # (uv 0.10.10, checked 2026-10-22).
    seen, stopped = {}, []
    real = shutil.rmtree

    def rmtree(path, *args, **options):
        seen["sigterm"] = signal.getsignal(signal.SIGTERM)
        try:
            signal.raise_signal(signal.SIGINT)
        except KeyboardInterrupt:
            stopped.append(path)
            return  # a real delete stops here
        real(path, *args, **options)

    monkeypatch.setattr(shutil, "rmtree", rmtree)
    _demo_run(monkeypatch, seen)
    handlers = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
    assert main(["demo", "--no-browser", "--size", "small"]) == 0
    assert stopped == [] and seen["sigterm"] is signal.SIG_IGN
    assert not seen["home"].parent.exists()
    assert (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)) == handlers


def test_a_stop_while_the_sample_is_built_still_deletes_it(monkeypatch):
    seen = {}
    real = kitden.demo.build_demo_home

    def build(root, size):
        seen["home"] = real(root, size)
        stop = signal.getsignal(signal.SIGTERM)
        stop(signal.SIGTERM, None)  # what a SIGTERM does now
        return seen["home"]

    _demo_run(monkeypatch, seen, lambda *a, **kw: pytest.fail("served after a stop"))
    monkeypatch.setattr(kitden.demo, "build_demo_home", build)
    before = signal.getsignal(signal.SIGTERM)
    with pytest.raises(SystemExit) as stopped:
        main(["demo", "--no-browser", "--size", "small"])
    assert stopped.value.code == 0
    assert not seen["home"].parent.exists()
    assert signal.getsignal(signal.SIGTERM) is before


def test_a_folder_that_cannot_be_deleted_is_named(monkeypatch, capsys):
    seen = {}
    real = shutil.rmtree
    monkeypatch.setattr(shutil, "rmtree", lambda path, **options: None)
    _demo_run(monkeypatch, seen)
    try:
        assert main(["demo", "--no-browser", "--size", "small"]) == 0
        folder = seen["home"].parent
        assert capsys.readouterr().err == f"The sample folder was not deleted: {folder}\n"
    finally:
        real(seen["home"].parent)


def _first_line(process, seconds=20):
    """The program's first line, or a failure after `seconds`, not a hang."""
    ready, _, _ = select.select([process.stdout], [], [], seconds)
    assert ready, "the program printed nothing"
    return process.stdout.readline()


def _listening(port, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return True
        except OSError:
            time.sleep(0.1)
    return False


@pytest.mark.parametrize("signal_name", ["SIGTERM", "SIGINT"])
def test_a_stopped_demo_exits_cleanly_and_deletes_its_folder(tmp_path, signal_name):
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "kitden", "demo", "--no-browser", "--size", "small"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "TMPDIR": str(tmp_path)},  # the sample is made here
    )
    try:
        port = int(re.search(r"127\.0\.0\.1:(\d+)/", _first_line(process)).group(1))
        assert [p.name[:12] for p in tmp_path.iterdir()] == ["kitden-demo-"]
        assert _listening(port)
        process.send_signal(getattr(signal, signal_name))
        _, err = process.communicate(timeout=15)
    finally:
        process.kill()
    assert process.returncode == 0, err
    assert "Traceback" not in err
    assert list(tmp_path.iterdir()) == []
