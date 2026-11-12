"""Old "show my setup" entries and the update to Kitden (feature 002, FR-005 to FR-007)."""

import json

import pytest

from kitden.changes import json_splice, toml_edit
from kitden.views.inventory import build_inventory
from kitden.views.setup_server import setup_server_state
from tests.conftest import make_home, write_cursor_fixture_state


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
        "enabled": None,
        "moved": False,
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


# The update action (T007) ------------------------------------------------------------------

KITDEN_COMMAND = "/opt/kitden/bin/kitden"


def _old_items(home):
    from kitden.views.setup_server import is_old_entry

    inventory = build_inventory(home)
    return inventory, {i.client: i for i in inventory.items if is_old_entry(i)}


def test_update_removes_the_old_entry_then_adds_kitden(home):
    from kitden.changes.actions import update_steps
    from kitden.changes.json_splice import ABSENT
    from kitden.views.inventory import default_adapters

    _, old = _old_items(home)
    adapters = {a.id: a for a in default_adapters(home)}
    steps = update_steps(adapters, [old["claude_code"], old["codex"]], set(), KITDEN_COMMAND)
    assert [(s.client, s.name) for s in steps] == [
        ("claude_code", "agentsetup"),
        ("claude_code", "kitden"),
        ("codex", "agentsetup"),
        ("codex", "kitden"),
    ]
    assert steps[0].command == ["claude", "mcp", "remove", "-s", "user", "agentsetup"]
    assert steps[2].edit.after is ABSENT
    assert steps[3].edit.after == {"command": KITDEN_COMMAND, "args": ["mcp"]}
    assert steps[1].edit.path == steps[0].edit.path


def test_update_only_removes_when_kitden_is_already_there(home):
    from kitden.changes.actions import update_steps
    from kitden.views.inventory import default_adapters

    _, old = _old_items(home)
    adapters = {a.id: a for a in default_adapters(home)}
    steps = update_steps(adapters, [old["codex"]], {"codex"}, KITDEN_COMMAND)
    assert [(s.client, s.name) for s in steps] == [("codex", "agentsetup")]


def _client(home, setup_command=lambda: KITDEN_COMMAND):
    from starlette.testclient import TestClient

    from kitden.web.app import create_app

    app = create_app(
        lambda: build_inventory(home),
        token="tok",
        port=47800,
        home=home,
        setup_command=setup_command,
    )
    return TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False)


POST = {"X-Tool-Request": "1", "Origin": "http://127.0.0.1:47800"}


def test_update_from_the_page_applies_and_undoes_exactly(home):
    config = home / ".codex/config.toml"
    original = config.read_bytes()
    with _client(home) as client:
        client.get("/?token=tok")
        states = {s["client"]: s for s in client.get("/api/setup-server").json()}
        body = {"action": "setup_server.update", "targets": [{"item": states["codex"]["item"]}]}
        change = client.post("/api/changes/preview", json=body, headers=POST).json()
        assert len(change["steps"]) == 2
        done = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert done["state"] == "verified"
        text = config.read_text()
        assert toml_edit.get_value(text, ("mcp_servers", "kitden"))["command"] == KITDEN_COMMAND
        assert "agentsetup" not in text
        client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert config.read_bytes() == original


def test_update_refuses_an_entry_that_is_not_ours(home):
    inventory = build_inventory(home)
    stranger = next(i for i in inventory.items if i.client == "cursor" and i.name == "agentsetup")
    body = {"action": "setup_server.update", "targets": [{"item": stranger.id}]}
    with _client(home) as client:
        client.get("/?token=tok")
        response = client.post("/api/changes/preview", json=body, headers=POST)
    assert response.status_code == 422
    assert response.json()["detail"] == "Choose an old Kitden entry."


def test_update_needs_the_kitden_command_installed(home):
    with _client(home, setup_command=lambda: None) as client:
        client.get("/?token=tok")
        states = {s["client"]: s for s in client.get("/api/setup-server").json()}
        body = {"action": "setup_server.update", "targets": [{"item": states["codex"]["item"]}]}
        response = client.post("/api/changes/preview", json=body, headers=POST)
    assert response.status_code == 422
    assert "Install the tool first" in response.json()["detail"]


# A kitden entry whose program is gone (Kitden moved from uv to Homebrew, or was removed) ------


def _kitden_entry(home, command):
    config = home / ".codex/config.toml"
    entry = {"command": command, "args": ["mcp"], "enabled": False}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "kitden"), entry))


def test_a_kitden_entry_whose_program_is_gone_is_old(home, real_programs):
    _kitden_entry(home, str(home / "gone/bin/kitden"))
    state = _states(home)["codex"]
    assert state["state"] == "old" and state["moved"] is True
    assert state["command_exists"] is False
    inventory = build_inventory(home)
    mine = next(i for i in inventory.items if i.client == "codex" and i.name == "kitden")
    assert state["item"] == mine.id


def test_a_kitden_entry_whose_program_is_there_is_added(home, real_programs):
    present = home / "here/bin/kitden"
    present.parent.mkdir(parents=True)
    present.write_text("")
    _kitden_entry(home, str(present))
    state = _states(home)["codex"]
    assert state["state"] == "added" and state["moved"] is False


def test_update_points_a_moved_kitden_entry_at_this_kitden_and_keeps_the_rest(home, real_programs):
    _kitden_entry(home, str(home / "gone/bin/kitden"))
    config = home / ".codex/config.toml"
    present = home / "opt/kitden/bin/kitden"
    present.parent.mkdir(parents=True)
    present.write_text("")
    original = config.read_bytes()
    with _client(home, setup_command=lambda: str(present)) as client:
        client.get("/?token=tok")
        states = {s["client"]: s for s in client.get("/api/setup-server").json()}
        body = {"action": "setup_server.update", "targets": [{"item": states["codex"]["item"]}]}
        change = client.post("/api/changes/preview", json=body, headers=POST).json()
        assert [s["name"] for s in change["steps"]] == ["kitden"]
        done = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert done["state"] == "verified"
        entry = toml_edit.get_value(config.read_text(), ("mcp_servers", "kitden"))
        assert entry == {"command": str(present), "args": ["mcp"], "enabled": False}
        after = {s["client"]: s for s in client.get("/api/setup-server").json()}
        assert after["codex"]["state"] == "added"
        client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert config.read_bytes() == original


def test_update_of_a_moved_claude_code_entry_applies_and_undoes_while_claude_writes(
    home, real_programs
):
    """Claude Code rewrites ~/.claude.json all the time: only the entry is checked."""
    path = home / ".claude.json"
    gone = {"type": "stdio", "command": str(home / "gone/bin/kitden"), "args": ["mcp"]}
    _add_json(path, ("mcpServers", "kitden"), gone)
    present = home / "opt/kitden/bin/kitden"
    present.parent.mkdir(parents=True)
    present.write_text("")
    with _client(home, setup_command=lambda: str(present)) as client:
        client.get("/?token=tok")
        states = {s["client"]: s for s in client.get("/api/setup-server").json()}
        assert states["claude_code"]["moved"] is True
        target = [{"item": states["claude_code"]["item"]}]
        body = {"action": "setup_server.update", "targets": target}
        change = client.post("/api/changes/preview", json=body, headers=POST).json()
        assert [s["name"] for s in change["steps"]] == ["kitden"]
        _add_json(path, ("numStartups",), 4)  # Claude Code writes while the review is open
        done = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert done["state"] == "verified", done
        data = json.loads(path.read_text())
        assert data["mcpServers"]["kitden"] == {**gone, "command": str(present)}
        assert data["numStartups"] == 4
        _add_json(path, ("numStartups",), 5)
        undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone", undone
    data = json.loads(path.read_text())
    assert data["mcpServers"]["kitden"] == gone
    assert data["numStartups"] == 5


# An entry on a versioned Homebrew path: the old keg can stay after an upgrade, so the program
# is still there, yet restarted agents would keep starting the old version.


@pytest.mark.parametrize("inside", ["libexec/bin/kitden", "bin/kitden"])
def test_a_kitden_entry_on_a_versioned_homebrew_path_is_moved(home, real_programs, inside):
    kept = home / "homebrew/Cellar/kitden/0.7.1" / inside
    kept.parent.mkdir(parents=True)
    kept.write_text("")
    _kitden_entry(home, str(kept))
    state = _states(home)["codex"]
    assert state["state"] == "old" and state["moved"] is True


def test_a_kitden_entry_on_the_homebrew_opt_link_is_added(home, real_programs):
    link = home / "homebrew/opt/kitden/bin/kitden"
    link.parent.mkdir(parents=True)
    link.write_text("")
    _kitden_entry(home, str(link))
    state = _states(home)["codex"]
    assert state["state"] == "added" and state["moved"] is False


def test_a_turned_off_kitden_entry_is_added_but_off(home):
    config = home / ".codex/config.toml"
    kitden = {"command": "/Users/me/.local/bin/kitden", "args": ["mcp"], "enabled": False}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "kitden"), kitden))
    state = _states(home)["codex"]
    assert (state["state"], state["enabled"]) == ("added", False)
    assert _states(home)["claude_code"]["enabled"] is None  # not added: nothing to be off
