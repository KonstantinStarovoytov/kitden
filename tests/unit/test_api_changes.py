"""Change and gateway endpoints (T047, contracts/local-api.md)."""

import json

import pytest
from starlette.testclient import TestClient

import agentsetup.clients.base as base
from agentsetup.changes import json_splice
from agentsetup.changes.client_cli import CommandResult
from agentsetup.views.inventory import build_inventory
from agentsetup.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
URL = "http://127.0.0.1:12008/metamcp/dev/mcp"


class FakeClaude:
    """Acts like `claude mcp add-json` and `claude mcp remove` on the sandbox ~/.claude.json."""

    def __init__(self, home):
        self.path = home / ".claude.json"

    def __call__(self, command, cwd):
        text = self.path.read_text()
        if command[1:3] == ["mcp", "add-json"]:
            text = json_splice.set_value(text, ("mcpServers", command[-2]), json.loads(command[-1]))
        else:
            text = json_splice.delete_value(text, ("mcpServers", command[-1]))
        self.path.write_text(text)
        return CommandResult(0, "")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    app = create_app(
        lambda: build_inventory(home), token="tok", port=47800, home=home, run=FakeClaude(home)
    )
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
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
