"""Change endpoints (T047, contracts/local-api.md)."""

import json
import os
import re
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kitden.changes import json_splice
from kitden.changes.client_cli import CommandResult
from kitden.gateways import data_dir
from kitden.local_gateway.settings import SETTINGS_FILE
from kitden.views.inventory import build_inventory
from kitden.web.app import ADD_ACTIONS, create_app, unread_refusal
from tests.conftest import make_home, write_cursor_fixture_state

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}


class FakeClaude:
    """Acts like `claude mcp add-json` and `claude mcp remove` on the sandbox ~/.claude.json."""

    def __init__(self, home):
        self.path = home / ".claude.json"

    def __call__(self, command, cwd):
        if command[1] == "plugin":  # claude plugin enable|disable <id> -s user --json
            settings = self.path.parent / ".claude/settings.json"
            key = ("enabledPlugins", command[3])
            settings.write_text(
                json_splice.set_value(settings.read_text(), key, command[2] == "enable")
            )
            return CommandResult(0, "")
        text = self.path.read_text()
        if command[1:3] == ["mcp", "add-json"]:
            text = json_splice.set_value(text, ("mcpServers", command[-2]), json.loads(command[-1]))
        else:
            text = json_splice.delete_value(text, ("mcpServers", command[-1]))
        self.path.write_text(text)
        return CommandResult(0, "")


def _app_client(home):
    app = create_app(
        lambda: build_inventory(home),
        token="tok",
        port=47800,
        home=home,
        run=FakeClaude(home),
        setup_command=lambda: "/opt/kitden/bin/kitden",
    )
    return TestClient(app, base_url=ORIGIN, follow_redirects=False)


def _home(tmp_path, monkeypatch):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


@pytest.fixture
def client(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    with _app_client(home) as c:
        c.get("/?token=tok")
        c.home = home
        yield c


@pytest.fixture
def plugin_client(tmp_path, monkeypatch):
    """Claude Code has the kitden plugin installed and an old agentsetup entry (feature 003)."""
    home = _home(tmp_path, monkeypatch)
    cache = home / ".claude/plugins/cache/kitden/kitden/0.1.0"
    shutil.copytree(Path(__file__).resolve().parents[2] / "plugins/kitden", cache)
    (home / ".claude/plugins/installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {"kitden@kitden": [{"installPath": str(cache)}]}})
    )
    old_command = home / ".local/bin/agentsetup"
    old_command.parent.mkdir(parents=True)
    old_command.write_text("#!/bin/sh\n")
    settings = home / ".claude.json"
    data = json.loads(settings.read_text())
    old = {"type": "stdio", "command": str(old_command), "args": ["mcp"]}
    data["mcpServers"]["agentsetup"] = old
    settings.write_text(json.dumps(data))
    with _app_client(home) as c:
        c.get("/?token=tok")
        c.home = home
        yield c


def _files(home):
    names = [".claude.json", ".codex/config.toml", ".cursor/mcp.json"]
    return {n: (home / n).read_bytes() if (home / n).exists() else None for n in names}


def test_a_removal_preview_says_what_the_client_shows_after(client):
    neon = next(
        i
        for i in client.get("/api/items?client=cursor&kind=mcp_server").json()
        if i["name"] == "Neon"
    )
    body = {"action": "mcp.remove_direct", "targets": [{"item": neon["id"]}], "params": {}}
    change = client.post("/api/changes/preview", json=body, headers=POST).json()
    assert change["after"] == [{"client": "cursor", "state": "off", "word": "Removed"}]


def test_a_preview_names_its_target(client):
    servers = client.get("/api/items?client=codex&kind=mcp_server").json()
    docs = next(i for i in servers if i["name"] == "api-docs")
    body = {"action": "mcp.remove_direct", "targets": [{"item": docs["id"]}], "params": {}}
    answer = client.post("/api/changes/preview", json=body, headers=POST).json()
    # No other known project lies inside work/api, or around it, in the base fixture, and the
    # step edits the file itself.
    assert answer["target"] == {
        "scope": "project",
        "project": str(client.home / "work/api"),
        "others_unchanged": True,
    }
    assert answer["undo_note"] is None
    client.post(f"/api/changes/{answer['id']}/cancel", headers=POST)
    # Claude Code's `mcp remove -s local` edits website's entry in ~/.claude.json, and only it:
    # an MCP command is judged by the file it edits.
    servers = client.get("/api/items?client=claude_code&kind=mcp_server").json()
    local = next(i for i in servers if i["name"] == "local-db")
    body = {"action": "mcp.remove_direct", "targets": [{"item": local["id"]}], "params": {}}
    answer = client.post("/api/changes/preview", json=body, headers=POST).json()
    assert answer["target"] == {
        "scope": "project",
        "project": str(client.home / "work/website"),
        "others_unchanged": True,
    }
    client.post(f"/api/changes/{answer['id']}/cancel", headers=POST)
    # A user entry goes for all projects.
    neon = next(
        i
        for i in client.get("/api/items?client=codex&kind=mcp_server").json()
        if i["name"] == "neon" and i["scope"] == "user"
    )
    body = {"action": "mcp.remove_direct", "targets": [{"item": neon["id"]}], "params": {}}
    answer = client.post("/api/changes/preview", json=body, headers=POST).json()
    assert answer["target"] == {"scope": "all", "project": None, "others_unchanged": False}


def test_a_server_the_picked_project_defines_itself_goes_to_every_other_project(
    tmp_path, monkeypatch
):
    home = _home(tmp_path, monkeypatch)
    # website gets its own github in Claude Code, which wins there over the user one.
    config = home / ".claude.json"
    data = json.loads(config.read_text())
    data["projects"][str(home / "work/website")]["mcpServers"]["github"] = {"command": "gh-mcp"}
    config.write_text(json.dumps(data))
    with _app_client(home) as client:
        client.get("/?token=tok")
        website = next(
            p for p in client.get("/api/projects").json() if p["path"].endswith("/work/website")
        )
        github = next(
            i
            for i in client.get("/api/items?client=claude_code&kind=mcp_server").json()
            if i["name"] == "github" and i["scope"] == "user"
        )
        body = {"action": "mcp.remove_direct", "targets": [{"item": github["id"]}], "params": {}}
        picked = {**body, "picked": website["id"]}
        answer = client.post("/api/changes/preview", json=picked, headers=POST).json()
    assert answer["target"] == {
        "scope": "others",
        "project": website["path"],
        "others_unchanged": False,
    }


def test_the_page_and_the_log_say_the_same_clients_and_places():
    from kitden.changes import engine
    from kitden.web import app

    # One function each, so a preview, an answer and the Changes page cannot drift apart.
    assert (app.step_readers, app.step_path) == (engine.step_readers, engine.step_path)


def test_a_hand_edit_between_preview_and_apply_stops_the_change(client):
    change = _preview_remove_direct(client)
    config = client.home / ".codex/config.toml"
    config.write_text(config.read_text() + "# by hand\n")
    response = client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    assert response.status_code == 409
    assert "changed since preview" in response.json()["error"]


def test_removing_a_direct_entry_and_undo(client):
    original = _files(client.home)
    neon = next(
        i
        for i in client.get("/api/items?client=cursor&kind=mcp_server").json()
        if i["name"] == "Neon"
    )
    body = {"action": "mcp.remove_direct", "targets": [{"item": neon["id"]}], "params": {}}
    change = client.post("/api/changes/preview", json=body, headers=POST).json()
    assert (
        client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"]
        == "verified"
    )
    names = {i["name"] for i in client.get("/api/items?client=cursor&kind=mcp_server").json()}
    assert "Neon" not in names
    client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert _files(client.home) == original


def _preview_remove_direct(client):
    """Preview removing Codex's user-level `neon` entry. Returns the change."""
    neon = next(
        i
        for i in client.get("/api/items?client=codex&kind=mcp_server").json()
        if i["name"] == "neon" and i["scope"] == "user"
    )
    body = {"action": "mcp.remove_direct", "targets": [{"item": neon["id"]}], "params": {}}
    return client.post("/api/changes/preview", json=body, headers=POST).json()


def _apply_remove_direct(client):
    """Preview and apply removing Codex's user-level `neon` entry. Returns the change id."""
    change = _preview_remove_direct(client)
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    return change["id"]


def test_a_change_can_be_read_back_by_id(client):
    change_id = _apply_remove_direct(client)
    answer = client.get(f"/api/changes/{change_id}")
    assert answer.status_code == 200
    assert answer.json()["id"] == change_id and answer.json()["state"] == "verified"
    assert answer.json()["stale"] is False  # only a previewed change is checked


def test_a_change_says_it_is_stale_once_its_file_changes(client):
    change = _preview_remove_direct(client)
    assert client.get(f"/api/changes/{change['id']}").json()["stale"] is False
    config = client.home / ".codex/config.toml"
    before = config.read_text()
    config.write_text(before + "\n# edited by hand\n")
    answer = client.get(f"/api/changes/{change['id']}").json()
    assert answer["stale"] is True and answer["state"] == "previewed"  # only looked
    assert config.read_text() == before + "\n# edited by hand\n"
    # A file Kitden can no longer read is not the one the preview read either (root reads it
    # anyway, so this part needs another user).
    config.write_text(before)
    assert client.get(f"/api/changes/{change['id']}").json()["stale"] is False
    if os.geteuid() == 0:
        return
    config.chmod(0)
    try:
        assert client.get(f"/api/changes/{change['id']}").json()["stale"] is True
    finally:
        config.chmod(0o600)


def test_the_changes_log_keeps_each_steps_restart_note(client):
    from kitden.clients.codex import RESTART

    _apply_remove_direct(client)
    log = (data_dir(client.home) / "changes.log").read_text().splitlines()
    step = json.loads(log[-1])["steps"][0]
    assert step["restart_note"] == RESTART
    # The Changes page says it per client.
    entry = client.get("/api/changes").json()[0]
    assert entry["takes_effect"] == [{"client": "codex", "note": RESTART}]


def test_reading_an_unknown_change_is_404(client):
    answer = client.get("/api/changes/nope")
    assert answer.status_code == 404 and answer.json()["detail"] == "Unknown change."


def test_a_change_only_in_the_log_can_be_read_back(client):
    change = _preview_remove_direct(client)
    config = client.home / ".codex/config.toml"
    config.write_text(config.read_text() + "# by hand\n")
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    with _app_client(client.home) as again:  # a restarted page keeps only the log of it
        again.get("/?token=tok")
        answer = again.get(f"/api/changes/{change['id']}")
    assert answer.status_code == 200 and answer.json()["state"] == "stale"


def test_removing_a_server_from_two_clients_is_one_change(client):
    items = client.get("/api/items?kind=mcp_server").json()
    github = next(i for i in items if i["name"] == "github" and i["client"] == "claude_code")
    langfuse = next(i for i in items if i["name"] == "langfuse-data")
    body = {
        "action": "mcp.remove_direct",
        "targets": [{"item": github["id"]}, {"item": langfuse["id"]}],
        "params": {},
    }
    change = client.post("/api/changes/preview", json=body, headers=POST).json()
    assert [s["client"] for s in change["steps"]] == ["claude_code", "codex"]
    assert [a["client"] for a in change["after"]] == ["claude_code", "codex"]
    client.post(f"/api/changes/{change['id']}/cancel", headers=POST)


def test_actions_an_item_does_not_offer_are_refused(client):
    desktop = next(
        i
        for i in client.get("/api/items?kind=mcp_server").json()
        if i["client"] == "claude_desktop_code_tab"
    )
    body = {"action": "mcp.remove_direct", "targets": [{"item": desktop["id"]}], "params": {}}
    assert client.post("/api/changes/preview", json=body, headers=POST).status_code == 422
    body = {"action": "mcp.enable", "targets": [], "params": {}}
    assert client.post("/api/changes/preview", json=body, headers=POST).status_code == 422


def test_cancel_and_unknown_change(client):
    change = _preview_remove_direct(client)
    assert (
        client.post(f"/api/changes/{change['id']}/cancel", headers=POST).json()["state"]
        == "cancelled"
    )
    assert client.post(f"/api/changes/{change['id']}/apply", headers=POST).status_code == 409
    assert client.post("/api/changes/nope/apply", headers=POST).status_code == 404


def test_change_requests_need_the_tool_header(client):
    neon = next(i for i in client.get("/api/items?client=codex&kind=mcp_server").json())
    body = {"action": "mcp.remove_direct", "targets": [{"item": neon["id"]}], "params": {}}
    assert (
        client.post("/api/changes/preview", json=body, headers={"Origin": ORIGIN}).status_code
        == 403
    )


def test_turning_a_plugin_off_and_undo(client):
    settings = client.home / ".claude/settings.json"
    original = settings.read_bytes()
    plugin = next(
        i
        for i in client.get("/api/items?client=claude_code&kind=plugin&scope=user").json()
        if i["actions"] == ["plugin.disable", "plugin.remove"]
    )
    body = {"action": "plugin.disable", "targets": [{"item": plugin["id"]}], "params": {}}
    change = client.post("/api/changes/preview", json=body, headers=POST).json()
    assert "/reload-plugins" in change["steps"][0]["restart_note"]
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified"
    after = next(i for i in client.get("/api/items").json() if i["id"] == plugin["id"])
    assert after["enabled"] == "off" and after["actions"] == ["plugin.enable", "plugin.remove"]
    client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert settings.read_bytes() == original


def test_cursor_plugins_cannot_be_turned_off(client):
    cursor = next(i for i in client.get("/api/items?client=cursor&kind=plugin").json())
    body = {"action": "plugin.disable", "targets": [{"item": cursor["id"]}], "params": {}}
    assert client.post("/api/changes/preview", json=body, headers=POST).status_code == 422
    assert "Customize" in cursor["change_hint"]


def test_show_only_commands_for_a_plugin(client):
    plugin = next(
        i
        for i in client.get("/api/items?client=claude_code&kind=plugin&scope=user").json()
        if i["name"] == "superpowers@claude-plugins-official"
    )
    commands = client.get(f"/api/commands?item={plugin['id']}").json()["commands"]
    labels = {c["label"]: c for c in commands}
    assert labels["Install in Codex"]["command"].endswith(
        "codex plugin add superpowers@claude-plugins-official"
    )


def test_adding_the_setup_server_and_undo(client):
    original = _files(client.home)
    body = {
        "action": "setup_server.register",
        "targets": [{"client": "codex"}, {"client": "cursor"}],
        "params": {},
    }
    change = client.post("/api/changes/preview", json=body, headers=POST).json()
    assert _files(client.home) == original
    assert all("/opt/kitden/bin/kitden" in s["diff"] for s in change["steps"])
    assert (
        client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"]
        == "verified"
    )
    names = {(i["client"], i["name"]) for i in client.get("/api/items?kind=mcp_server").json()}
    assert {("codex", "kitden"), ("cursor", "kitden")} <= names
    client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert _files(client.home) == original


def test_registering_adds_the_entry_beside_the_plugins_server(plugin_client):
    """The plugin's server only reads; the client's own entry is its link to the gateway."""
    body = {"action": "setup_server.register", "targets": [{"client": "claude_code"}], "params": {}}
    change = plugin_client.post("/api/changes/preview", json=body, headers=POST)
    assert change.status_code == 200, change.text
    steps = change.json()["steps"]
    assert [(s["client"], s["name"]) for s in steps] == [("claude_code", "kitden")]


def test_updating_an_old_entry_beside_the_plugin_adds_the_new_one(plugin_client):
    states = {s["client"]: s for s in plugin_client.get("/api/setup-server").json()}
    assert states["claude_code"]["state"] == "old"
    body = {"action": "setup_server.update", "targets": [{"item": states["claude_code"]["item"]}]}
    change = plugin_client.post("/api/changes/preview", json={**body, "params": {}}, headers=POST)
    assert change.status_code == 200, change.text
    steps = change.json()["steps"]
    assert [s["name"] for s in steps] == ["agentsetup", "kitden"]


# Moving servers into the gateway (feature 006) ---------------------------------------------


def _hold_in_kitden(home):
    """A server held in the Kitden gateway, reached through Cursor's `kitden` entry."""
    settings = data_dir(home) / SETTINGS_FILE
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"servers": {"files": {"command": "npx"}}}))
    cursor = home / ".cursor/mcp.json"
    data = json.loads(cursor.read_text())
    data["mcpServers"]["kitden"] = {"command": "/opt/kitden/bin/kitden", "args": ["mcp"]}
    cursor.write_text(json.dumps(data))
    return settings


def test_gateway_strict_previews_applies_and_undoes(client):
    home = client.home
    path = _hold_in_kitden(home)
    path.write_text(json.dumps({"servers": {"github": {"command": "npx"}}}))
    before = path.read_bytes()
    params = {"server": "github", "state": "on"}
    body = {"action": "gateway.strict", "targets": [], "params": params}
    answer = client.post("/api/changes/preview", json=body, headers=POST)
    assert answer.status_code == 200, answer.json()
    change = answer.json()
    assert "Strict mode on for github" in change["after"][0]["note"]
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified", applied
    assert json.loads(path.read_text())["rules"]["global"]["github"] == {"mode": "strict"}
    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone
    assert path.read_bytes() == before


def test_gateway_rules_previews_one_change_with_several_steps(client):
    from kitden.local_gateway.settings import save_tools

    home = client.home
    path = _hold_in_kitden(home)
    tools = [{"name": n, "description": "", "inputSchema": {}} for n in ("create", "delete")]
    save_tools(home, "files", tools)
    before = path.read_bytes()
    params = {"server": "files", "tools": ["create", "delete"], "state": "off", "project": None}
    body = {"action": "gateway.rules", "targets": [], "params": params}
    answer = client.post("/api/changes/preview", json=body, headers=POST)
    assert answer.status_code == 200, answer.json()
    change = answer.json()
    assert len(change["steps"]) == 2
    note = change["after"][0]["note"]
    assert note.startswith("2 tools of files will be off in all projects: create, delete. ")
    assert "Hints come from the server and names are a guess; check the list." in note
    assert "For a real guarantee, give files a token that can only read." in note
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified", applied
    rules = json.loads(path.read_text())["rules"]["global"]["files"]
    assert rules == {"tools": {"create": "off", "delete": "off"}}
    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone
    assert path.read_bytes() == before


def test_a_refusal_into_an_unreadable_file_follows_the_action():
    assert unread_refusal("mcp.add", "/h/.cursor/mcp.json") == (
        "Can't add while mcp.json can't be read."
    )
    assert unread_refusal("plugin.disable", "/h/.claude/settings.json") == (
        "Can't change this while settings.json can't be read."
    )


def test_the_page_and_the_server_agree_on_what_an_add_is():
    review = (Path(__file__).parents[2] / "src/kitden/web/static/js/review.js").read_text()
    adds = set(re.findall(r'"([a-z_.]+)"', review.split("export const ADDS = [")[1].split("]")[0]))
    # Add missing names its project in its title; an update changes an entry where it is;
    # connecting a client says "to Kitden"; moving a server out says the client it goes into.
    # None names a scope in the review. All four still refuse a broken file as adds.
    assert ADD_ACTIONS - adds == {
        "project.align",
        "setup_server.update",
        "setup_server.register",
        "gateway.move_out",
    }
    assert adds <= ADD_ACTIONS
    assert unread_refusal("marketplace.add", "/h/.claude/settings.json") == (
        "Can't add while settings.json can't be read."
    )
