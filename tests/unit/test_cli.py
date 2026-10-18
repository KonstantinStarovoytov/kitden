import re
import socket

import kitden.cli as cli
from kitden.cli import main, pick_port


def test_version_prints_name_and_version_and_exits_zero(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "kitden 0.2.0"


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
        [sys.executable, "-m", "kitden.cli", "--no-browser", "--home", str(tmp_path)],
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
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.append(kwargs))
    cli.run_server(object(), "127.0.0.1", 47800)
    assert calls[0]["timeout_graceful_shutdown"] <= 3


def test_every_command_copies_the_old_data_folder_once(tmp_path, capsys):
    from kitden.gateways import OLD_DATA_DIR, data_dir

    (tmp_path / OLD_DATA_DIR).mkdir(parents=True)
    (tmp_path / OLD_DATA_DIR / "settings.json").write_text('{"gateways": []}')
    cli.main(["scan", "--home", str(tmp_path)])
    assert (data_dir(tmp_path) / "settings.json").is_file()
    assert "Copied" in capsys.readouterr().err


def test_tests_never_see_the_real_home():
    from pathlib import Path

    assert "real-home" in str(Path.home())
