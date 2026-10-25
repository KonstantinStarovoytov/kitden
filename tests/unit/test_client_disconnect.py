"""Disconnect a client from Kitden: remove its `kitden` entry, and Undo puts it back."""

import json
import shutil
from pathlib import Path

import pytest

from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_api_changes import FakeClaude, _files
from tests.unit.test_local_gateway_views import POST, add_kitden, page_for

CLIENTS = ["claude_code", "codex", "cursor"]
FILE = {"claude_code": ".claude.json", "codex": ".codex/config.toml", "cursor": ".cursor/mcp.json"}
CODEX_ENTRY = '\n[mcp_servers.kitden]\ncommand = "/opt/kitden/bin/kitden"\nargs = ["mcp"]\n'
PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins/kitden"
PLUGIN_WORDS = (
    "Claude Code gets Kitden from the Claude Code plugin. Turn the plugin off to disconnect it."
)


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def connect(home, client, extra=""):
    """The client has the user `kitden` entry that Connect writes."""
    if client == "codex":
        config = home / FILE[client]
        config.write_text(config.read_text() + CODEX_ENTRY + extra)
    else:
        add_kitden(home, client)


def disconnect(page, *clients):
    body = {
        "action": "client.disconnect",
        "targets": [{"client": c} for c in clients],
        "params": {},
    }
    return page.post("/api/changes/preview", json=body, headers=POST)


def setup_state(page, client):
    states = page.get("/api/setup-server").json()
    return next(s["state"] for s in states if s["client"] == client)


@pytest.mark.parametrize("client", CLIENTS)
def test_disconnect_removes_the_entry_and_undo_puts_it_back(home, client):
    connect(home, client)
    before = _files(home)
    with page_for(home, run=FakeClaude(home)) as page:
        assert setup_state(page, client) == "added"
        answer = disconnect(page, client)
        assert answer.status_code == 200, answer.text
        change = answer.json()
        assert _files(home) == before
        assert [(s["client"], s["name"]) for s in change["steps"]] == [(client, "kitden")]
        assert change["after"] == [{"client": client, "state": "off", "word": "Removed"}]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        assert setup_state(page, client) == "missing"
        # Only this client's file changed.
        now = _files(home)
        assert {name for name in now if now[name] != before[name]} == {FILE[client]}
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
        assert _files(home) == before
        assert setup_state(page, client) == "added"


def test_a_client_is_disconnected_without_touching_the_others(home):
    for client in CLIENTS:
        connect(home, client)
    with page_for(home, run=FakeClaude(home)) as page:
        change = disconnect(page, "codex", "cursor").json()
        assert [s["client"] for s in change["steps"]] == ["codex", "cursor"]
        page.post(f"/api/changes/{change['id']}/apply", headers=POST)
        assert [setup_state(page, c) for c in CLIENTS] == ["added", "missing", "missing"]


def test_disconnect_refuses_a_client_without_the_entry(home):
    connect(home, "cursor")
    before = _files(home)
    with page_for(home, run=FakeClaude(home)) as page:
        answer = disconnect(page, "codex")
        assert answer.status_code == 422
        assert answer.json()["detail"] == "Codex is not connected to Kitden."
        # A client that has the entry does not make up for one that does not.
        assert disconnect(page, "cursor", "codex").status_code == 422
    assert _files(home) == before


def test_disconnect_refuses_the_plugin_entry(home):
    cache = home / ".claude/plugins/cache/kitden/kitden/0.1.0"
    shutil.copytree(PLUGIN_DIR, cache)
    (home / ".claude/plugins/installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {"kitden@kitden": [{"installPath": str(cache)}]}})
    )
    before = _files(home)
    with page_for(home, run=FakeClaude(home)) as page:
        assert setup_state(page, "claude_code") == "plugin"
        answer = disconnect(page, "claude_code")
        assert answer.status_code == 422
        assert answer.json()["detail"] == PLUGIN_WORDS
    assert _files(home) == before


def test_a_codex_entry_turned_off_can_be_disconnected(home):
    connect(home, "codex", extra="enabled = false\n")
    before = _files(home)
    with page_for(home, run=FakeClaude(home)) as page:
        states = page.get("/api/setup-server").json()
        codex = next(s for s in states if s["client"] == "codex")
        assert (codex["state"], codex["enabled"]) == ("added", False)
        change = disconnect(page, "codex").json()
        assert "kitden" in change["steps"][0]["diff"]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        assert setup_state(page, "codex") == "missing"
        page.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert _files(home) == before


def test_disconnect_and_connect_of_one_client_clash_in_the_tray(home):
    connect(home, "claude_code")
    connect_row = {
        "id": "a",
        "kind": "setup_server.register",
        "title": "Connect Claude Code to Kitden",
        "targets": [{"client": "claude_code"}],
        "params": {},
    }
    disconnect_row = {
        "id": "b",
        "kind": "client.disconnect",
        "title": "Disconnect Claude Code from Kitden",
        "targets": [{"client": "claude_code"}],
        "params": {},
    }
    with page_for(home, run=FakeClaude(home)) as page:
        answer = page.post(
            "/api/batch/check", json={"requests": [connect_row, disconnect_row]}, headers=POST
        )
        assert answer.status_code == 200
        found = answer.json()
        assert found["ok"] is False and found["row"] == "b"
        assert "Connect Claude Code to Kitden" in found["reason"]
        alone = page.post("/api/batch/check", json={"requests": [disconnect_row]}, headers=POST)
        assert alone.json() == {"ok": True}
