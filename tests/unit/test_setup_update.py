"""Old "show my setup" entries and the update to Kitden (feature 002, FR-005 to FR-007)."""

import json

import pytest

import kitden.clients.base as base
from kitden.changes import json_splice, toml_edit
from kitden.views.inventory import build_inventory
from kitden.views.setup_server import setup_server_state
from tests.conftest import make_home, write_cursor_fixture_state


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


def _add_json(path, key, value):
    path.write_text(json_splice.set_value(path.read_text(), key, value))


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    present = home / ".local/bin/agentsetup"
    present.parent.mkdir(parents=True)
    present.write_text("#!/bin/sh\n")
    old = {"type": "stdio", "command": str(present), "args": ["mcp"]}
    _add_json(home / ".claude.json", ("mcpServers", "agentsetup"), old)
    config = home / ".codex/config.toml"
    gone = {"command": "/Users/me/old-venv/bin/agentsetup", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), gone))
    stranger = {"command": "/usr/local/bin/other-tool", "args": ["serve"]}
    _add_json(home / ".cursor/mcp.json", ("mcpServers", "agentsetup"), stranger)
    project = home / "work/website/.mcp.json"
    _add_json(project, ("mcpServers", "agentsetup"), old)
    return home


def _states(home):
    return {s["client"]: s for s in setup_server_state(build_inventory(home))}


def test_old_entries_are_found_per_client(home):
    states = _states(home)
    assert states["claude_code"]["state"] == "old"
    assert states["claude_code"]["command_exists"] is True
    assert states["codex"]["state"] == "old"
    assert states["codex"]["command_exists"] is False
    assert states["claude_code"]["item"] and states["codex"]["item"]


def test_an_agentsetup_entry_running_another_program_is_ignored(home):
    assert _states(home)["cursor"] == {
        "client": "cursor",
        "state": "missing",
        "item": None,
        "command_exists": None,
    }


def test_a_project_level_entry_is_not_an_old_entry(home):
    items = {s["item"] for s in _states(home).values()}
    inventory = build_inventory(home)
    project_ids = {i.id for i in inventory.items if i.name == "agentsetup" and i.project}
    assert project_ids and not project_ids & items


def test_a_kitden_entry_means_added_and_keeps_the_old_one_for_removal(home):
    kitden = {"type": "stdio", "command": "/Users/me/.local/bin/kitden", "args": ["mcp"]}
    _add_json(home / ".claude.json", ("mcpServers", "kitden"), kitden)
    state = _states(home)["claude_code"]
    assert state["state"] == "added" and state["item"]


def test_a_client_that_is_not_installed(tmp_path):
    home = make_home(tmp_path, "codex/0.159.2")
    states = _states(home)
    assert states["codex"]["state"] == "missing"
    assert states["cursor"]["state"] == "not_installed"


def test_the_page_api_returns_the_states(home):
    from starlette.testclient import TestClient

    from kitden.web.app import create_app

    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        data = client.get("/api/setup-server").json()
    assert {s["client"]: s["state"] for s in data} == {
        "claude_code": "old",
        "codex": "old",
        "cursor": "missing",
    }
    assert json.dumps(data)  # plain JSON, no secret values
