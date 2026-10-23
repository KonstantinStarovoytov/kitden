"""Removing a plugin from the Library: the client's own command, verify, Undo (spec 3.1)."""

import json
import tomllib

import pytest
from starlette.testclient import TestClient

from kitden.clients.cursor import CURSOR_HINT
from kitden.views.inventory import build_inventory
from kitden.views.words import REMOVE_NOTE
from kitden.web.app import create_app
from tests.unit.test_api_plugin_install import LINTER, ORIGIN, POST, _client, _preview

SUPERPOWERS = "superpowers@claude-plugins-official"
OFF = "claude-md-management@claude-plugins-official"
BROWSER = "browser@openai-bundled"
PDF = "pdf@openai-primary-runtime"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Claude Code, Codex and Cursor, with Cursor loading Claude Code's plugins."""
    yield from _client(tmp_path, monkeypatch, cursor_flags={})


@pytest.fixture
def plain(tmp_path, monkeypatch):
    """Claude Code and Codex only; Claude Code's settings keep a plugin that is off."""
    yield from _client(tmp_path, monkeypatch)


def _item(client, name, who="claude_code", scope="user"):
    items = client.get(f"/api/items?client={who}&kind=plugin").json()
    return next(i for i in items if i["name"] == name and i["scope"] == scope)


def _remove(client, item_id):
    body = {"action": "plugin.remove", "targets": [{"item": item_id}], "params": {}}
    return client.post("/api/changes/preview", json=body, headers=POST)


def _settings(client):
    return json.loads((client.home / ".claude/settings.json").read_text())


def test_removing_a_claude_code_plugin_runs_uninstall_and_undo_installs_it_again(client):
    change = _remove(client, _item(client, SUPERPOWERS)["id"]).json()
    assert [(s["client"], s["name"]) for s in change["steps"]] == [("claude_code", SUPERPOWERS)]
    assert (
        change["steps"][0]["command"]
        == f"claude plugin uninstall {SUPERPOWERS} -s user --keep-data --json"
    )
    # Cursor loads this copy from Claude Code and has one of its own, which stays.
    assert change["after"] == [
        {"client": "claude_code", "state": "off", "word": "Removed"},
        {
            "client": "cursor",
            "state": "on",
            "word": "Loads once",
            "note": "Cursor loads Claude Code's plugins, so it loses this copy and keeps its own.",
        },
    ]
    # The Undo limit is said once, in the review's lede; Cursor keeps a copy, so the title
    # names Claude Code only, as Details' Affects does.
    assert change["undo_note"] == REMOVE_NOTE
    assert change["steps"][0]["reaches"] == ["claude_code"]
    assert client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == (
        "verified"
    )
    assert SUPERPOWERS not in _settings(client)["enabledPlugins"]
    assert client.run.calls[-1][:3] == ["claude", "plugin", "uninstall"]
    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")
    assert client.run.calls[-1][:3] == ["claude", "plugin", "install"]
    assert _settings(client)["enabledPlugins"][SUPERPOWERS] is True


def test_cursor_loses_a_claude_code_plugin_it_only_imports(client):
    added = _preview(client, LINTER, ["claude_code"]).json()
    assert client.post(f"/api/changes/{added['id']}/apply", headers=POST).json()["state"] == (
        "verified"
    )
    change = _remove(client, _item(client, LINTER)["id"]).json()
    assert change["after"] == [
        {"client": "claude_code", "state": "off", "word": "Removed"},
        {
            "client": "cursor",
            "state": "off",
            "word": "Removed",
            "note": "Cursor loads Claude Code's plugins, so it loses this one too.",
        },
    ]
    assert change["undo_note"] == REMOVE_NOTE
    # The review's title names Cursor too, as Details' Affects and Remove button do; so does
    # the line after Apply.
    assert change["steps"][0]["reaches"] == ["claude_code", "cursor"]
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["steps"][0]["reaches"] == ["claude_code", "cursor"]


def test_a_plugin_command_is_for_all_projects_even_where_the_project_has_its_own(client):
    website = next(
        p for p in client.get("/api/projects").json() if p["path"].endswith("/work/website")
    )
    item_id = _item(client, SUPERPOWERS)["id"]
    everywhere = {"scope": "all", "project": None, "others_unchanged": False}
    for action in ("plugin.disable", "plugin.remove"):
        body = {"action": action, "targets": [{"item": item_id}], "params": {}}
        # website has its own superpowers, which wins there; but `claude plugin …` also works
        # on the plugin cache every project shares, so website is not left out.
        picked = client.post(
            "/api/changes/preview", json={**body, "picked": website["id"]}, headers=POST
        ).json()
        assert picked["target"] == everywhere
        client.post(f"/api/changes/{picked['id']}/cancel", headers=POST)


def test_the_changes_page_keeps_the_clients_and_the_place_after_a_restart(client):
    added = _preview(client, LINTER, ["claude_code"]).json()
    client.post(f"/api/changes/{added['id']}/apply", headers=POST)
    change = _remove(client, _item(client, LINTER)["id"]).json()
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    everywhere = {"scope": "all", "project": None, "others_unchanged": False}
    entry = client.get("/api/changes").json()[0]
    assert (entry["id"], entry["steps"][0]["reaches"]) == (change["id"], ["claude_code", "cursor"])
    assert entry["target"] == everywhere
    home = client.home
    app = create_app(
        lambda: build_inventory(home), token="tok", port=47800, home=home, run=client.run
    )
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as again:
        again.get("/?token=tok")
        read = again.get(f"/api/changes/{change['id']}").json()
    assert read["steps"][0]["reaches"] == ["claude_code", "cursor"]
    assert read["target"] == everywhere


def test_undo_of_removing_an_off_plugin_leaves_it_off(plain):
    before = (plain.home / ".claude/settings.json").read_text()
    change = _remove(plain, _item(plain, OFF)["id"]).json()
    assert change["after"] == [{"client": "claude_code", "state": "off", "word": "Removed"}]
    assert change["undo_note"] == REMOVE_NOTE
    assert plain.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == (
        "verified"
    )
    assert OFF not in _settings(plain)["enabledPlugins"]
    undone = plain.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")
    assert plain.run.calls[-1][:3] == ["claude", "plugin", "install"]
    # The install turns it on; Undo then puts the entry back as it was: off.
    assert _settings(plain)["enabledPlugins"][OFF] is False
    assert json.loads((plain.home / ".claude/settings.json").read_text()) == json.loads(before)


def test_removing_a_codex_plugin_keeps_the_rest_of_the_file(plain):
    change = _remove(plain, _item(plain, BROWSER, "codex")["id"]).json()
    assert change["steps"][0]["command"] == f"codex plugin remove {BROWSER}"
    assert change["after"] == [{"client": "codex", "state": "off", "word": "Removed"}]
    # Codex's own Undo has no such limit to name.
    assert change["undo_note"] is None
    plain.post(f"/api/changes/{change['id']}/apply", headers=POST)
    text = (plain.home / ".codex/config.toml").read_text()
    assert BROWSER not in tomllib.loads(text).get("plugins", {})
    assert "# Owner comment: keep me" in text
    undone = plain.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")
    plugins = tomllib.loads((plain.home / ".codex/config.toml").read_text())["plugins"]
    assert plugins[BROWSER] == {"enabled": True}


def test_undo_of_removing_an_off_codex_plugin_leaves_it_off(plain):
    change = _remove(plain, _item(plain, PDF, "codex")["id"]).json()
    plain.post(f"/api/changes/{change['id']}/apply", headers=POST)
    assert PDF not in tomllib.loads((plain.home / ".codex/config.toml").read_text())["plugins"]
    undone = plain.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")
    text = (plain.home / ".codex/config.toml").read_text()
    assert tomllib.loads(text)["plugins"][PDF] == {"enabled": False}
    assert "# Owner comment: keep me" in text


def test_a_project_plugin_is_removed_from_its_project(client):
    item = _item(client, SUPERPOWERS, scope="project")
    change = _remove(client, item["id"]).json()
    step = change["steps"][0]
    assert step["command"] == f"claude plugin uninstall {SUPERPOWERS} -s project --keep-data --json"
    # A project's file is shared, and Cursor imports only user plugins.
    assert change["shared_file_warning"] is True
    assert [e["client"] for e in change["after"]] == ["claude_code"]
    assert step["reaches"] == ["claude_code"]
    assert change["target"]["project"] == item["project"]


def test_plugins_without_a_file_entry_cannot_be_removed(client):
    gmail = _item(client, "gmail@openai-curated-remote", "codex")  # state in the account
    assert _remove(client, gmail["id"]).status_code == 422
    cursor = _item(client, SUPERPOWERS, "cursor")  # imported from Claude Code
    assert _remove(client, cursor["id"]).status_code == 422
    assert "Remove it in Cursor: Customize → Plugins." in CURSOR_HINT
    assert "Add for Myself" in CURSOR_HINT


def test_details_offer_remove_for_each_definition_that_has_a_file(client):
    answer = client.get(f"/api/explain?name={SUPERPOWERS}&kind=plugin").json()["definitions"]
    by_client = {(d["client"], d["scope"], d["name"]): d["actions"] for d in answer}
    assert "plugin.remove" in by_client[("claude_code", "user", SUPERPOWERS)]
    assert "plugin.remove" in by_client[("claude_code", "project", SUPERPOWERS)]
    assert by_client[("cursor", "user", SUPERPOWERS)] == []


def test_a_plugin_with_no_install_is_not_offered_for_removal(plain):
    # A project can switch off a plugin synced from claude.ai; there is no install to remove.
    path = plain.home / "work/website/.claude/settings.json"
    data = json.loads(path.read_text())
    data["enabledPlugins"]["notes@synced"] = False
    path.write_text(json.dumps(data))
    plain.post("/api/rescan", headers=POST)
    synced = _item(plain, "notes@synced", scope="project")
    assert synced["actions"] == ["plugin.enable"]
