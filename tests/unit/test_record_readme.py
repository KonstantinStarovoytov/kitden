"""The README recorder's page (scripts/record_readme.py): it goes online for nothing. How it
films is in tests/browser/test_recorder.py."""

import http.cookiejar
import importlib.util
import json
import socket
import sys
import time
import urllib.request
from pathlib import Path

import pytest

import tests.conftest
import tests.offline
from kitden import __version__

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


def test_the_update_check_asks_nobody(recorder, tmp_path):
    """The network guard (tests/conftest.py) also fails this test when the page connects out."""
    with socket.create_server(("127.0.0.1", 0)) as free:
        port = free.getsockname()[1]
    link, server = recorder.start_page(recorder.sample(tmp_path), port)
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    try:
        opener.open(link).close()  # takes the page's cookie
        latest, end = None, time.monotonic() + 10
        while latest is None and time.monotonic() < end:
            with opener.open(link.split("?")[0] + "api/update") as answer:
                update = json.load(answer)
            latest = update["latest"]
            time.sleep(0.05)
    finally:
        server.should_exit = True
    assert latest == __version__
    assert update["notes_url"] is None  # the page offers no update
