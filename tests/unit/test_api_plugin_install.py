"""Adding a plugin from Discover: one review, the clients' own commands, verify, Undo (phase 1)."""

import tomllib

import pytest
from starlette.testclient import TestClient

import kitden.clients.base as base
from kitden.changes import json_splice, toml_edit
from kitden.changes.client_cli import CommandResult
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home
from tests.unit.test_catalog import add_marketplaces

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}


class FakeCli:
    """Acts like `claude plugin …` and `codex plugin …`: each writes its own record."""

    def __init__(self, home):
        self.home = home
        self.calls = []

    def __call__(self, command, cwd):
        self.calls.append(command)
        if command[0] == "claude":
            path = self.home / ".claude/settings.json"
            text = path.read_text()
            if command[1:3] == ["plugin", "install"]:
                text = json_splice.set_value(text, ("enabledPlugins", command[3]), True)
            elif command[1:3] == ["plugin", "uninstall"]:
                text = json_splice.delete_value(text, ("enabledPlugins", command[3]))
            path.write_text(text)
            return CommandResult(0, "{}")
        path = self.home / ".codex/config.toml"
        text = path.read_text()
        if command[1:4] == ["plugin", "marketplace", "add"]:
            entry = {"source_type": "git", "source": command[4]}
            text = toml_edit.set_value(text, ("marketplaces", "claude-plugins-official"), entry)
        elif command[1:4] == ["plugin", "marketplace", "remove"]:
            text = toml_edit.delete_value(text, ("marketplaces", command[4]))
        elif command[1:3] == ["plugin", "add"]:
            text = toml_edit.set_value(text, ("plugins", command[3]), {"enabled": True})
        elif command[1:3] == ["plugin", "remove"]:
            text = toml_edit.delete_value(text, ("plugins", command[3]))
        path.write_text(text)
        return CommandResult(0, "{}")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    home = add_marketplaces(make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2"))
    run = FakeCli(home)
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home, run=run)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        c.home, c.run = home, run
        yield c


def _files(home):
    return {n: (home / n).read_bytes() for n in (".claude/settings.json", ".codex/config.toml")}


def _preview(client, plugin, clients):
    body = {
        "action": "plugin.install",
        "targets": [{"client": c} for c in clients],
        "params": {"plugin": plugin},
    }
    return client.post("/api/changes/preview", json=body, headers=POST)


def test_the_catalog_lists_plugins_with_how_each_client_gets_them(client):
    answer = client.get("/api/catalog?q=lint").json()
    assert [o["id"] for o in answer["offers"]][:2] == [
        "linter@claude-plugins-official",
        "deploy-helper@claude-plugins-official",
    ]
    assert answer["offers"][0]["routes"] == {"claude_code": "ready", "codex": "add_marketplace"}


def test_a_plugin_goes_to_two_clients_in_one_review_and_undo_takes_it_back(client):
    before = _files(client.home)
    preview = _preview(client, "linter@claude-plugins-official", ["claude_code", "codex"])
    assert preview.status_code == 200, preview.text
    change = preview.json()
    # Codex first adds the marketplace from Claude Code's source, then the plugin.
    assert [(s["client"], s["name"]) for s in change["steps"]] == [
        ("claude_code", "linter@claude-plugins-official"),
        ("codex", "claude-plugins-official"),
        ("codex", "linter@claude-plugins-official"),
    ]
    assert _files(client.home) == before

    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified", applied.get("error")
    commands = [c[:4] for c in client.run.calls]
    assert ["claude", "plugin", "install", "linter@claude-plugins-official"] in commands
    assert ["codex", "plugin", "marketplace", "add"] in commands
    assert all("-y" not in c and "--yes" not in c for c in client.run.calls)
    config = tomllib.loads((client.home / ".codex/config.toml").read_text())
    assert config["plugins"]["linter@claude-plugins-official"] == {"enabled": True}
    assert (
        config["marketplaces"]["claude-plugins-official"]["source"]
        == "anthropics/claude-plugins-official"
    )

    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")
    assert [c[1:3] for c in client.run.calls[-3:]] == [
        ["plugin", "remove"],
        ["plugin", "marketplace"],
        ["plugin", "uninstall"],
    ]
    assert _files(client.home) == before


def test_a_client_without_a_route_is_refused(client):
    answer = _preview(client, "tracker@openai-curated", ["claude_code"])
    assert answer.status_code == 422
    assert "Claude Code cannot get tracker" in answer.json()["detail"]


def test_an_unknown_plugin_is_refused(client):
    answer = _preview(client, "nothing@nowhere", ["codex"])
    assert answer.status_code == 422
