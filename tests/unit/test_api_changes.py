"""Change and gateway endpoints (T047, contracts/local-api.md)."""

import json
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import kitden.clients.base as base
from kitden.changes import json_splice
from kitden.changes.client_cli import CommandResult
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.fake_metamcp import FakeMetaMcp

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
URL = "http://127.0.0.1:12008/metamcp/dev/mcp"


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
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
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


def _register(client, **extra):
    body = {"url": URL, "auth": "env_key", "key_env_var": "GW_KEY", **extra}
    return client.post("/api/gateways", json=body, headers=POST)


def _connect(client, gateway_id, clients=("claude_code", "codex", "cursor")):
    body = {
        "action": "gateway.connect",
        "targets": [{"client": c} for c in clients],
        "params": {"gateway": gateway_id, "name": "gateway"},
    }
    return client.post("/api/changes/preview", json=body, headers=POST)


def test_registering_a_gateway_refuses_secrets(client):
    assert _register(client, url=URL + "?token=abc12345").status_code == 422
    assert _register(client, auth="env_key", key_env_var="sk-not-a-name").status_code == 422
    response = _register(client, ui_url="http://127.0.0.1:12008")
    assert response.status_code == 200
    assert client.get("/api/gateways").json() == [response.json()]


def test_registering_sign_in_details_keeps_no_password(client):
    half = _register(client, login_email="me@example.com")
    assert half.status_code == 422
    secret = _register(client, login_email="me@example.com", login_password_env_var="hunter2pw")
    assert secret.status_code == 422
    ok = _register(client, login_email=" me@example.com ", login_password_env_var="METAMCP_PW")
    assert ok.status_code == 200
    saved = ok.json()
    assert (saved["login_email"], saved["login_password_env_var"]) == (
        "me@example.com",
        "METAMCP_PW",
    )
    assert saved["managed"] is True
    assert client.get("/api/gateway-view").json()["gateways"][0]["managed"] is True


def test_connect_previews_then_applies_then_undoes_exactly(client):
    original = _files(client.home)
    gateway = _register(client).json()

    preview = _connect(client, gateway["id"])
    assert preview.status_code == 200
    change = preview.json()
    assert change["state"] == "previewed"
    assert _files(client.home) == original
    assert {s["client"] for s in change["steps"]} == {"claude_code", "codex", "cursor"}
    assert all(s["restart_note"] for s in change["steps"])
    assert "${env:GW_KEY}" in next(s["diff"] for s in change["steps"] if s["client"] == "cursor")

    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    assert applied.status_code == 200
    assert applied.json()["state"] == "verified"
    items = client.get("/api/items?kind=mcp_server").json()
    marked = {i["client"] for i in items if i["name"] == "gateway" and i["via_gateway"]}
    assert marked == {"claude_code", "codex", "cursor"}
    bypassing = {
        tuple(f["names"])
        for f in client.get("/api/findings").json()
        if f["type"] == "bypasses_gateway"
    }
    assert ("gateway",) not in bypassing and ("github",) in bypassing
    assert client.get("/api/changes").json()[0]["state"] == "verified"

    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert undone.json()["state"] == "undone"
    assert _files(client.home) == original


def test_preview_says_what_each_client_shows_after(client):
    gateway = _register(client).json()
    change = _connect(client, gateway["id"], clients=["codex", "cursor"]).json()
    assert change["after"] == [
        {"client": "codex", "state": "gw", "word": "Via gateway"},
        {"client": "cursor", "state": "gw", "word": "Via gateway"},
    ]
    neon = next(
        i
        for i in client.get("/api/items?client=cursor&kind=mcp_server").json()
        if i["name"] == "Neon"
    )
    body = {"action": "mcp.remove_direct", "targets": [{"item": neon["id"]}], "params": {}}
    change = client.post("/api/changes/preview", json=body, headers=POST).json()
    assert change["after"] == [{"client": "cursor", "state": "off", "word": "Removed"}]


def test_a_hand_edit_between_preview_and_apply_stops_the_change(client):
    gateway = _register(client).json()
    change = _connect(client, gateway["id"], clients=["codex"]).json()
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


def _apply_remove_direct(client):
    """Preview and apply removing Codex's user-level `neon` entry. Returns the change id."""
    neon = next(
        i
        for i in client.get("/api/items?client=codex&kind=mcp_server").json()
        if i["name"] == "neon" and i["scope"] == "user"
    )
    body = {"action": "mcp.remove_direct", "targets": [{"item": neon["id"]}], "params": {}}
    change = client.post("/api/changes/preview", json=body, headers=POST).json()
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    return change["id"]


def test_a_change_can_be_read_back_by_id(client):
    change_id = _apply_remove_direct(client)
    answer = client.get(f"/api/changes/{change_id}")
    assert answer.status_code == 200
    assert answer.json()["id"] == change_id and answer.json()["state"] == "verified"


def test_the_changes_log_keeps_each_steps_restart_note(client):
    from kitden.clients.codex import RESTART

    _apply_remove_direct(client)
    step = client.get("/api/changes").json()[0]["steps"][0]
    assert step["restart_note"] == RESTART
    assert step["login_note"] is None


def test_reading_an_unknown_change_is_404(client):
    answer = client.get("/api/changes/nope")
    assert answer.status_code == 404 and answer.json()["detail"] == "Unknown change."


def test_a_change_only_in_the_log_can_be_read_back(client):
    gateway = _register(client).json()
    change = _connect(client, gateway["id"], clients=["codex"]).json()
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
    gateway = _register(client).json()
    change = _connect(client, gateway["id"], clients=["cursor"]).json()
    assert (
        client.post(f"/api/changes/{change['id']}/cancel", headers=POST).json()["state"]
        == "cancelled"
    )
    assert client.post(f"/api/changes/{change['id']}/apply", headers=POST).status_code == 409
    assert client.post("/api/changes/nope/apply", headers=POST).status_code == 404


def test_change_requests_need_the_tool_header(client):
    gateway = _register(client).json()
    body = {
        "action": "gateway.connect",
        "targets": [{"client": "cursor"}],
        "params": {"gateway": gateway["id"], "name": "gw"},
    }
    assert (
        client.post("/api/changes/preview", json=body, headers={"Origin": ORIGIN}).status_code
        == 403
    )


def test_login_command_for_an_oauth_gateway_entry(client):
    gateway = _register(client, auth="oauth", key_env_var=None).json()
    change = _connect(client, gateway["id"], clients=["codex"]).json()
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    entry = next(
        i
        for i in client.get("/api/items?client=codex&kind=mcp_server").json()
        if i["name"] == "gateway"
    )
    response = client.get(f"/api/commands?item={entry['id']}&action=gateway.login")
    assert response.json()["command"] == "Run: codex mcp login gateway"


def test_turning_a_plugin_off_and_undo(client):
    settings = client.home / ".claude/settings.json"
    original = settings.read_bytes()
    plugin = next(
        i
        for i in client.get("/api/items?client=claude_code&kind=plugin&scope=user").json()
        if i["actions"] == ["plugin.disable"]
    )
    body = {"action": "plugin.disable", "targets": [{"item": plugin["id"]}], "params": {}}
    change = client.post("/api/changes/preview", json=body, headers=POST).json()
    assert "/reload-plugins" in change["steps"][0]["restart_note"]
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified"
    after = next(i for i in client.get("/api/items").json() if i["id"] == plugin["id"])
    assert after["enabled"] == "off" and after["actions"] == ["plugin.enable"]
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


def test_registering_is_refused_where_the_plugin_provides_the_server(plugin_client):
    body = {"action": "setup_server.register", "targets": [{"client": "claude_code"}], "params": {}}
    assert plugin_client.post("/api/changes/preview", json=body, headers=POST).status_code == 422


def test_updating_an_old_entry_beside_the_plugin_only_removes_it(plugin_client):
    states = {s["client"]: s for s in plugin_client.get("/api/setup-server").json()}
    assert states["claude_code"]["state"] == "plugin"
    body = {"action": "setup_server.update", "targets": [{"item": states["claude_code"]["item"]}]}
    change = plugin_client.post("/api/changes/preview", json={**body, "params": {}}, headers=POST)
    assert change.status_code == 200, change.text
    steps = change.json()["steps"]
    assert len(steps) == 1 and "agentsetup" in steps[0]["diff"]


# Moving servers into the gateway (feature 006) ---------------------------------------------


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("METAMCP_PW", "right-password")
    fake = FakeMetaMcp().start()
    yield fake
    fake.stop()


def _managed(client, fake):
    body = {
        "url": fake.mcp_url,
        "login_email": "me@example.com",
        "login_password_env_var": "METAMCP_PW",
    }
    return client.post("/api/gateways", json=body, headers=POST).json()


def _move_rows(client):
    return client.get("/api/gateway-view").json()["groups"]["move"]


def _move(client, gateway_id, items):
    body = {
        "action": "gateway.move",
        "targets": [{"item": i} for i in items],
        "params": {"gateway": gateway_id},
    }
    return client.post("/api/changes/preview", json=body, headers=POST)


def test_the_page_reads_what_the_gateway_holds(client, fake):
    gateway = _managed(client, fake)
    fake.hold("docs", "http://127.0.0.1:8765/mcp")
    answer = client.get(f"/api/gateways/{gateway['id']}/servers").json()
    assert answer == {
        "servers": [
            {"name": "docs", "type": "STREAMABLE_HTTP", "url": "http://127.0.0.1:8765/mcp"}
        ],
        "error": None,
    }
    assert client.get("/api/gateways/nope/servers").status_code == 404
    fake.stop()
    answer = client.get(f"/api/gateways/{gateway['id']}/servers").json()
    assert answer["servers"] is None and "Could not reach" in answer["error"]


def test_move_one_server_then_undo(client, fake):
    original = _files(client.home)
    gateway = _managed(client, fake)
    # The fixture has "neon" in Codex and "Neon" in Cursor: two rows, moved as one change.
    rows = [r for r in _move_rows(client) if r["name"].lower() == "neon"]
    assert [r["clients"] for r in rows] == [["codex"], ["cursor"]]
    items = [i for r in rows for i in r["items"]]

    preview = _move(client, gateway["id"], items)
    assert preview.status_code == 200, preview.json()
    change = preview.json()
    assert [s["client"] for s in change["steps"]] == ["gateway", "gateway", "codex", "cursor"]
    assert change["steps"][0]["path"] == gateway["url"]
    assert "+" in change["steps"][0]["diff"] and "neon" in change["steps"][0]["diff"]
    # Neither client has a gateway entry yet, so the entry is simply gone for them.
    assert [(a["client"], a["word"]) for a in change["after"]] == [
        ("codex", "Removed"),
        ("cursor", "Removed"),
    ]
    assert _files(client.home) == original and fake.held_names() == []

    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    assert applied.status_code == 200 and applied.json()["state"] == "verified"
    assert fake.held_names() == ["neon", "Neon"]
    assert all(r["name"].lower() != "neon" for r in _move_rows(client))
    entry = client.get("/api/changes").json()[0]
    assert entry["action"] == "gateway.move" and entry["steps"][0]["client"] == "gateway"

    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert undone.status_code == 200 and undone.json()["state"] == "undone"
    assert _files(client.home) == original and fake.held_names() == []


def test_move_all_keeps_secrets_out_of_sight(client, fake):
    original = _files(client.home)
    gateway = _managed(client, fake)
    items = [i for row in _move_rows(client) for i in row["items"]]
    names = sorted(r["name"] for r in _move_rows(client))
    change = _move(client, gateway["id"], items).json()
    assert "SENTINEL" not in json.dumps(change)
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified"
    assert sorted(fake.held_names()) == [n.replace(".", "-") for n in names]
    github = next(s for s in fake.servers.values() if s["name"] == "github")
    assert github["headers"]["Authorization"] == "Bearer SENTINEL_SECRET_GITHUB"
    assert _move_rows(client) == []
    assert "SENTINEL" not in json.dumps(client.get("/api/changes").json())
    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone"
    assert _files(client.home) == original and fake.servers == {}


def test_a_name_the_gateway_holds_or_a_variable_is_refused(client, fake):
    gateway = _managed(client, fake)
    fake.hold("neon", "https://mcp.neon.tech/mcp")
    neon = next(r for r in _move_rows(client) if r["name"] == "neon")
    refused = _move(client, gateway["id"], neon["items"])
    assert refused.status_code == 422 and "already has neon" in refused.json()["detail"]

    mcp = client.home / ".cursor/mcp.json"
    data = json.loads(mcp.read_text())
    data["mcpServers"]["linear"] = {
        "url": "https://mcp.linear.app/mcp",
        "headers": {"Authorization": "Bearer ${env:LINEAR}"},
    }
    mcp.write_text(json.dumps(data, indent=2))
    client.post("/api/rescan", headers=POST)
    linear = next(r for r in _move_rows(client) if r["name"] == "linear")
    refused = _move(client, gateway["id"], linear["items"])
    assert refused.status_code == 422 and "variable" in refused.json()["detail"]


def test_an_unmanaged_gateway_cannot_take_servers(client, fake):
    gateway = _register(client, url=fake.mcp_url).json()
    neon = next(r for r in _move_rows(client) if r["name"] == "neon")
    refused = _move(client, gateway["id"], neon["items"])
    assert refused.status_code == 422 and "sign-in" in refused.json()["detail"]
    answer = client.get(f"/api/gateways/{gateway['id']}/servers").json()
    assert answer["servers"] is None and "sign-in" in answer["error"]


# Feature 007: an Obot gateway beside MetaMCP ---------------------------------------------


@pytest.fixture
def obot(monkeypatch):
    from tests.unit.fake_obot import FakeObot

    fake = FakeObot().start()
    monkeypatch.setenv("OBOT_KEY", fake.key)
    yield fake
    fake.stop()


def _register_obot(client, fake, **extra):
    body = {"url": fake.mcp_url, "auth": "oauth", "key_env_var": "OBOT_KEY", **extra}
    return client.post("/api/gateways", json=body, headers=POST)


def test_the_page_reads_what_an_obot_gateway_holds(client, obot):
    obot.hold("docs", "https://docs.example.com/mcp")
    saved = _register_obot(client, obot, ui_url=obot.url).json()
    assert (saved["kind"], saved["managed"], saved["movable"]) == ("obot", True, True)
    answer = client.get(f"/api/gateways/{saved['id']}/servers").json()
    assert answer == {
        "servers": [{"name": "docs", "type": "remote", "url": "https://docs.example.com/mcp"}],
        "error": None,
    }  # the entry id stays inside Kitden
    obot.stop()
    answer = client.get(f"/api/gateways/{saved['id']}/servers").json()
    assert answer["servers"] is None and "Could not reach" in answer["error"]
    assert obot.key not in answer["error"]


def test_an_obot_gateway_without_a_key_variable_says_so(client, obot):
    saved = _register_obot(client, obot, key_env_var=None).json()
    assert saved["managed"] is False
    answer = client.get(f"/api/gateways/{saved['id']}/servers").json()
    assert answer["servers"] is None and "key variable" in answer["error"]
    neon = next(r for r in _move_rows(client) if r["name"] == "neon")
    refused = _move(client, saved["id"], neon["items"])
    assert refused.status_code == 422 and "key variable" in refused.json()["detail"]


def test_an_obot_key_never_reaches_a_client_file_or_a_response(client, obot):
    saved = _register_obot(client, obot).json()
    assert obot.key not in client.get("/api/gateways").text
    change = _connect(client, saved["id"]).json()
    assert change["state"] == "previewed"
    assert obot.key not in json.dumps(change)
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified"
    for name, raw in _files(client.home).items():
        assert raw is not None and obot.key.encode() not in raw, name
        assert b"mcp-connect" in raw, name
    marked = {
        i["client"]
        for i in client.get("/api/items?kind=mcp_server").json()
        if i["name"] == "gateway" and i["via_gateway"]
    }
    assert marked == {"claude_code", "codex", "cursor"}
    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone"


def test_clients_connect_to_obot_with_a_key_reference_or_an_oauth_login(client, obot):
    by_key = _register_obot(client, obot, auth="env_key").json()
    change = _connect(client, by_key["id"]).json()
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    files = _files(client.home)
    assert b'bearer_token_env_var = "OBOT_KEY"' in files[".codex/config.toml"]
    assert b"${OBOT_KEY}" in files[".claude.json"]
    assert b"${env:OBOT_KEY}" in files[".cursor/mcp.json"]
    assert all(obot.key.encode() not in raw for raw in files.values())
    client.post(f"/api/changes/{change['id']}/undo", headers=POST)

    by_login = _register_obot(client, obot, url=obot.mcp_url + "2").json()
    change = _connect(client, by_login["id"], clients=["codex", "claude_code"]).json()
    notes = {s["client"]: s.get("login_note") for s in change["steps"]}
    assert notes["codex"] == "Run: codex mcp login gateway"
    assert notes["claude_code"]
    assert obot.key not in json.dumps(change)


def test_clients_switch_from_one_gateway_to_another_and_undo_puts_them_back(client):
    old = _register(client).json()
    connected = _connect(client, old["id"]).json()
    client.post(f"/api/changes/{connected['id']}/apply", headers=POST)
    before = _files(client.home)
    new = client.post(
        "/api/gateways",
        json={"url": "http://localhost:8080/mcp-connect/vmcp1", "auth": "oauth"},
        headers=POST,
    ).json()

    body = {
        "action": "gateway.switch",
        "targets": [],
        "params": {"gateway": new["id"], "name": "obot"},
    }
    preview = client.post("/api/changes/preview", json=body, headers=POST)
    assert preview.status_code == 200
    change = preview.json()
    assert [(s["client"], s["name"]) for s in change["steps"]] == [
        ("claude_code", "gateway"),
        ("claude_code", "obot"),
        ("codex", "gateway"),
        ("codex", "obot"),
        ("cursor", "gateway"),
        ("cursor", "obot"),
    ]
    assert _files(client.home) == before

    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified"
    items = client.get("/api/items?kind=mcp_server").json()
    via = {(i["client"], i["name"]): i["via_gateway"] for i in items if i["via_gateway"]}
    assert via == {(c, "obot"): new["id"] for c in ("claude_code", "codex", "cursor")}

    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone"
    assert _files(client.home) == before


def test_switching_to_the_gateway_already_in_use_is_refused(client):
    gateway = _register(client).json()
    connected = _connect(client, gateway["id"]).json()
    client.post(f"/api/changes/{connected['id']}/apply", headers=POST)
    body = {
        "action": "gateway.switch",
        "targets": [],
        "params": {"gateway": gateway["id"], "name": "gateway"},
    }
    answer = client.post("/api/changes/preview", json=body, headers=POST)
    assert answer.status_code == 422
    assert "No client uses another gateway" in answer.json()["detail"]


def test_move_one_server_into_obot_then_undo(client, obot):
    original = _files(client.home)
    gateway = _register_obot(client, obot).json()
    assert gateway["movable"] is True
    obot.hold("docs", "https://docs.example.com/mcp")
    rows = [r for r in _move_rows(client) if r["name"].lower() == "neon"]
    items = [i for r in rows for i in r["items"]]

    preview = _move(client, gateway["id"], items)
    assert preview.status_code == 200, preview.json()
    change = preview.json()
    assert [s["client"] for s in change["steps"]] == ["gateway", "gateway", "codex", "cursor"]
    assert "mcp.neon.tech" in change["steps"][0]["diff"]
    assert _files(client.home) == original and obot.held_names() == ["docs"]

    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    assert applied.status_code == 200 and applied.json()["state"] == "verified"
    assert obot.held_names() == ["docs", "neon", "Neon"]  # Obot keeps the names as they are
    assert len(obot.entries) == 3 and obot.profiles_kept
    assert all(r["name"].lower() != "neon" for r in _move_rows(client))
    held = client.get(f"/api/gateways/{gateway['id']}/servers").json()["servers"]
    assert [s["name"] for s in held] == ["docs", "neon", "Neon"]

    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert undone.status_code == 200 and undone.json()["state"] == "undone"
    assert _files(client.home) == original
    assert obot.held_names() == ["docs"] and list(obot.entries) == ["e1"]


def test_moving_several_servers_into_a_busy_obot_still_works(client, obot):
    # The real Obot answers 409 to a quick second write while its controller catches up.
    original = _files(client.home)
    gateway = _register_obot(client, obot).json()
    rows = [r for r in _move_rows(client) if r["name"].lower() == "neon"]
    obot.conflicts = {2}
    change = _move(client, gateway["id"], [i for r in rows for i in r["items"]]).json()
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    assert applied.json()["state"] == "verified", applied.json().get("error")
    assert obot.held_names() == ["neon", "Neon"]
    obot.conflicts = {obot.vmcp_puts + 1}
    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert undone.json()["state"] == "undone", undone.json().get("error")
    assert _files(client.home) == original and obot.held_names() == []


def test_apply_tells_the_open_page_how_many_steps_are_done(client, obot):
    gateway = _register_obot(client, obot).json()
    rows = [r for r in _move_rows(client) if r["name"].lower() == "neon"]
    change = _move(client, gateway["id"], [i for r in rows for i in r["items"]]).json()
    queue = client.app.state.events.subscribe()
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    seen = []
    while not queue.empty():
        event = queue.get_nowait()
        if isinstance(event, tuple) and event[0] == "change_progress":
            seen.append((event[1]["done"], event[1]["total"]))
    assert seen == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_move_into_obot_needs_an_administrator(client, obot):
    original = _files(client.home)
    gateway = _register_obot(client, obot).json()
    obot.forbid_writes = True
    neon = next(r for r in _move_rows(client) if r["name"] == "neon")
    change = _move(client, gateway["id"], neon["items"]).json()
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "restored" and "administrator" in applied["error"]
    assert obot.key not in applied["error"]
    assert _files(client.home) == original and obot.entries == {}


def test_move_into_obot_refuses_a_server_on_this_computer(tmp_path, monkeypatch, obot):
    home = _home(tmp_path, monkeypatch)
    mcp = home / ".cursor/mcp.json"
    data = json.loads(mcp.read_text())
    data["mcpServers"]["bridge"] = {"url": "http://127.0.0.1:8765/mcp"}
    mcp.write_text(json.dumps(data, indent=2))
    with _app_client(home) as c:
        c.get("/?token=tok")
        gateway = _register_obot(c, obot).json()
        bridge = next(r for r in _move_rows(c) if r["name"] == "bridge")
        refused = _move(c, gateway["id"], bridge["items"])
        assert refused.status_code == 422
        assert "runs on this computer" in refused.json()["detail"]
        assert "tunnel" in refused.json()["detail"]
    assert obot.entries == {}
