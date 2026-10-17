import re
import socket

import agentsetup.cli as cli
from agentsetup.cli import main, pick_port


def test_version_prints_name_and_version_and_exits_zero(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "agentsetup 0.1.0"


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


def test_start_serves_on_loopback_and_prints_a_token_link(monkeypatch, capsys):
    calls = {}
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: 47811)
    monkeypatch.setattr(
        cli, "run_server", lambda app, host, port: calls.update(host=host, port=port)
    )
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: calls.update(opened=url))
    monkeypatch.setattr(cli, "build_inventory", lambda home=None: cli.Inventory())

    assert main(["--no-browser"]) == 0

    assert calls == {"host": "127.0.0.1", "port": 47811}
    out = capsys.readouterr().out
    assert re.search(r"http://127\.0\.0\.1:47811/\?token=[A-Za-z0-9_-]{40,}", out)


def test_start_opens_the_browser_by_default(monkeypatch):
    opened = []
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: 47812)
    monkeypatch.setattr(cli, "run_server", lambda app, host, port: None)
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    monkeypatch.setattr(cli, "build_inventory", lambda home=None: cli.Inventory())
    main([])
    assert len(opened) == 1 and opened[0].startswith("http://127.0.0.1:47812/?token=")


def test_start_exits_2_without_a_free_port(monkeypatch):
    monkeypatch.setattr(cli, "pick_port", lambda start, tries=20: None)
    assert main(["--no-browser"]) == 2


def test_start_link_is_visible_to_a_program_reading_the_output(tmp_path):
    """The link must be flushed even when stdout is a pipe, not a terminal."""
    import subprocess
    import sys

    process = subprocess.Popen(
        [sys.executable, "-m", "agentsetup.cli", "--no-browser", "--home", str(tmp_path)],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        first_line = process.stdout.readline()
    finally:
        process.terminate()
        process.wait(timeout=10)
    assert "http://127.0.0.1:" in first_line and "token=" in first_line
