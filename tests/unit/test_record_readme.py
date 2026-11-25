"""The README recorder's page (scripts/record_readme.py): it goes online for nothing, and what
runs on this computer does not change it. How it films is in tests/browser/test_recorder.py."""

import contextlib
import http.cookiejar
import importlib.util
import json
import os
import socket
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

import tests.conftest
import tests.offline
from kitden import __version__
from kitden.changes.backup import ChangeStore
from kitden.gateways import data_dir

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def recorder(tmp_path, monkeypatch, fake_keychain):
    """The script as a module, with its stand-ins on until the test ends."""
    monkeypatch.setattr(sys, "path", sys.path[:])  # the script adds its folders
    monkeypatch.setitem(sys.modules, "conftest", tests.conftest)
    monkeypatch.setitem(sys.modules, "offline", tests.offline)
    spec = importlib.util.spec_from_file_location(
        "record_readme", ROOT / "scripts/record_readme.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for owner, name, value in tests.offline.STAND_INS:
        monkeypatch.setattr(owner, name, value)
    return module


@contextlib.contextmanager
def reading(recorder, home):
    """The recorder's page on `home`: a function that reads one of its addresses as JSON."""
    with socket.create_server(("127.0.0.1", 0)) as free:
        port = free.getsockname()[1]
    link, server = recorder.start_page(home, port)
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def read(path):
        with opener.open(link.split("?")[0] + path) as answer:
            return json.load(answer)

    try:
        opener.open(link).close()  # takes the page's cookie
        yield read
    finally:
        server.should_exit = True


def test_the_update_check_asks_nobody(recorder, tmp_path):
    """The network guard (tests/conftest.py) also fails this test when the page connects out."""
    with reading(recorder, recorder.sample(tmp_path)) as read:
        latest, end = None, time.monotonic() + 10
        while latest is None and time.monotonic() < end:
            update = read("api/update")
            latest = update["latest"]
            time.sleep(0.05)
    assert latest == __version__
    assert update["notes_url"] is None  # the page offers no update


def test_running_clients_bring_no_restart_strip(recorder, tmp_path, monkeypatch):
    """An Apply asks for restarts, and `ps` says both clients run from before it. A strip would
    move the map down in the pictures."""
    ps = tmp_path / "bin/ps"
    ps.parent.mkdir()
    ps.write_text(
        "#!/bin/sh\n"
        "echo 'Tue Nov  3 09:15:02 2026 /opt/homebrew/bin/claude'\n"
        "echo 'Tue Nov  3 09:15:02 2026 /opt/homebrew/bin/codex'\n"
    )
    ps.chmod(0o755)
    monkeypatch.setenv("PATH", str(ps.parent), prepend=os.pathsep)
    home = recorder.sample(tmp_path)
    steps = [
        {"client": "claude_code", "restart_note": "Restart Claude Code."},
        {"client": "codex", "restart_note": "Restart Codex."},
    ]
    applied = datetime.now(UTC).isoformat(timespec="seconds")
    ChangeStore(data_dir(home)).log(
        {"id": "c1", "time": applied, "state": "verified", "steps": steps}
    )
    with reading(recorder, home) as read:
        assert read("api/restarts") == []
