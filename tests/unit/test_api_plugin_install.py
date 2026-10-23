"""Adding a plugin from the Library: one review, the clients' own commands, verify, Undo."""

import json
import tomllib
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kitden.changes import json_splice, toml_edit
from kitden.changes.client_cli import CommandResult
from kitden.clients.cursor import REACTIVE_KEY
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_catalog import add_marketplaces

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
LINTER = "linter@claude-plugins-official"


def _marketplace_name(source):
    """The name a client would read from the marketplace file at a local source."""
    for name in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
        path = Path(source) / name
        if path.is_file():
            return json.loads(path.read_text())["name"]
    return "claude-plugins-official"


class FakeCli:
    """Acts like `claude plugin …` and `codex plugin …`: each writes its own record."""

    def __init__(self, home):
        self.home = home
        self.calls = []

    def __call__(self, command, cwd):
        self.calls.append(command)
        project = "-s" in command and command[command.index("-s") + 1] == "project"
        if command[0] == "claude" and project:
            # A project install switches the plugin on in <cwd>/.claude/settings.json.
            path = Path(cwd) / ".claude/settings.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            text = path.read_text() if path.exists() else "{}\n"
            if command[1:3] == ["plugin", "install"]:
                text = json_splice.set_value(text, ("enabledPlugins", command[3]), True)
            elif command[1:3] == ["plugin", "uninstall"]:
                text = json_splice.delete_value(text, ("enabledPlugins", command[3]))
            path.write_text(text)
            return CommandResult(0, "{}")
        if command[0] == "claude":
            path = self.home / ".claude/settings.json"
            text = path.read_text()
            record = self.home / ".claude/plugins/installed_plugins.json"
            installed = record.read_text()
            known_path = self.home / ".claude/plugins/known_marketplaces.json"
            known = known_path.read_text()
            if command[1:4] == ["plugin", "marketplace", "add"]:
                name = _marketplace_name(command[4])
                entry = {"source": {"source": "directory", "path": command[4]}}
                text = json_splice.set_value(text, ("extraKnownMarketplaces", name), entry)
                # Like the real CLI: a folder marketplace is read where it is.
                known = json_splice.set_value(
                    known, (name,), {**entry, "installLocation": command[4]}
                )
            elif command[1:4] == ["plugin", "marketplace", "remove"]:
                text = json_splice.delete_value(text, ("extraKnownMarketplaces", command[4]))
                known = json_splice.delete_value(known, (command[4],))
            elif command[1:3] == ["plugin", "install"]:
                text = json_splice.set_value(text, ("enabledPlugins", command[3]), True)
                cache = self.home / ".claude/plugins/cache" / command[3].replace("@", "/") / "1.0.0"
                cache.mkdir(parents=True, exist_ok=True)
                entry = [{"scope": "user", "installPath": str(cache), "version": "1.0.0"}]
                installed = json_splice.set_value(installed, ("plugins", command[3]), entry)
            elif command[1:3] == ["plugin", "uninstall"]:
                text = json_splice.delete_value(text, ("enabledPlugins", command[3]))
                installed = json_splice.delete_value(installed, ("plugins", command[3]))
            path.write_text(text)
            record.write_text(installed)
            known_path.write_text(known)
            return CommandResult(0, "{}")
        path = self.home / ".codex/config.toml"
        text = path.read_text()
        if command[1:4] == ["plugin", "marketplace", "add"]:
            local = Path(command[4]).is_absolute()
            entry = {"source_type": "local" if local else "git", "source": command[4]}
            text = toml_edit.set_value(text, ("marketplaces", _marketplace_name(command[4])), entry)
        elif command[1:4] == ["plugin", "marketplace", "remove"]:
            text = toml_edit.delete_value(text, ("marketplaces", command[4]))
        elif command[1:3] == ["plugin", "add"]:
            text = toml_edit.set_value(text, ("plugins", command[3]), {"enabled": True})
        elif command[1:3] == ["plugin", "remove"]:
            text = toml_edit.delete_value(text, ("plugins", command[3]))
        path.write_text(text)
        return CommandResult(0, "{}")


def _client(tmp_path, monkeypatch, cursor_flags=None):
    """Claude Code and Codex; with `cursor_flags`, also Cursor with those switches."""
    fixtures = ["claude_code/2.1.283", "codex/0.159.2"]
    if cursor_flags is not None:
        fixtures.append("cursor/3.21.16")
    home = add_marketplaces(make_home(tmp_path, *fixtures))
    if cursor_flags is not None:
        write_cursor_fixture_state(home, {REACTIVE_KEY: cursor_flags})
    run = FakeCli(home)
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home, run=run)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        c.home, c.run = home, run
        yield c


@pytest.fixture
def client(tmp_path, monkeypatch):
    yield from _client(tmp_path, monkeypatch)


@pytest.fixture
def cursor_client(tmp_path, monkeypatch):
    yield from _client(tmp_path, monkeypatch, cursor_flags={})


@pytest.fixture
def strict_cursor_client(tmp_path, monkeypatch):
    off = {"importPluginsFromClaudeOnBoot": False}
    yield from _client(tmp_path, monkeypatch, cursor_flags=off)


def _files(home):
    names = (
        ".claude/settings.json",
        ".codex/config.toml",
        ".claude/plugins/installed_plugins.json",
    )
    return {n: (home / n).read_bytes() for n in names}


def _preview(client, plugin, clients):
    body = {
        "action": "plugin.install",
        "targets": [{"client": c} for c in clients],
        "params": {"plugin": plugin},
    }
    return client.post("/api/changes/preview", json=body, headers=POST)


def _offer(client, plugin=LINTER):
    """The plugin as Details of a Library row reads it."""
    return client.get(f"/api/offer?kind=plugin&id={plugin}").json()


def test_a_plugin_goes_to_two_clients_in_one_review_and_undo_takes_it_back(client):
    before = _files(client.home)
    preview = _preview(client, LINTER, ["claude_code", "codex"])
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
    assert sorted(_offer(client)["installed"]) == ["claude_code", "codex"]
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


def test_adding_to_claude_code_says_cursor_loads_it_too(cursor_client):
    change = _preview(cursor_client, LINTER, ["claude_code"]).json()
    assert change["after"][-1] == {
        "client": "cursor",
        "state": "on",
        "word": "Available",
        "note": "Cursor loads Claude Code's plugins, so it gets this one too.",
    }
    # The title names Cursor too, as Details' Affects does before the click.
    assert [s["reaches"] for s in change["steps"]] == [["claude_code", "cursor"]]
    assert _offer(cursor_client)["inherits"] == {"plugin": True, "skill": True}


def test_with_cursor_import_off_the_review_does_not_name_cursor(strict_cursor_client):
    change = _preview(strict_cursor_client, LINTER, ["claude_code"])
    assert [e["client"] for e in change.json()["after"]] == ["claude_code"]
    assert [s["reaches"] for s in change.json()["steps"]] == [None]
    assert _offer(strict_cursor_client)["inherits"] == {"plugin": False, "skill": True}


def test_without_cursor_neither_kind_is_inherited(client):
    assert _offer(client)["inherits"] == {"plugin": False, "skill": False}


def _marketplace(client, source, clients):
    body = {
        "action": "marketplace.add",
        "targets": [{"client": c} for c in clients],
        "params": {"source": source},
    }
    return client.post("/api/changes/preview", json=body, headers=POST)


def test_a_marketplace_from_a_folder_goes_to_codex_and_undo_removes_it(client, tmp_path):
    folder = tmp_path / "team-mkt/.claude-plugin"
    folder.mkdir(parents=True)
    (folder / "marketplace.json").write_text('{"name": "team-tools", "plugins": [{"name": "a"}]}')
    before = _files(client.home)
    preview = _marketplace(client, str(tmp_path / "team-mkt"), ["codex"])
    assert preview.status_code == 200, preview.text
    change = preview.json()
    assert [(s["client"], s["name"]) for s in change["steps"]] == [("codex", "team-tools")]
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified", applied.get("error")
    # Its plugins show in the Library at once, ready to add to Codex.
    rows = client.get("/api/library?kind=plugin&show=new").json()["rows"]
    added = next(r for r in rows if r["offer"] == "a@team-tools")
    assert added["cells"]["codex"]["add"]["action"] == "plugin.install"
    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone"
    assert _files(client.home) == before


def test_a_marketplace_the_client_already_has_is_refused(client, tmp_path):
    folder = tmp_path / "again/.claude-plugin"
    folder.mkdir(parents=True)
    (folder / "marketplace.json").write_text('{"name": "claude-plugins-official", "plugins": []}')
    answer = _marketplace(client, str(tmp_path / "again"), ["claude_code"])
    assert answer.status_code == 422
    assert "already has" in answer.json()["detail"]


def test_a_codex_only_marketplace_is_refused_for_claude_code(client, tmp_path):
    folder = tmp_path / "codex-only/.agents/plugins"
    folder.mkdir(parents=True)
    (folder / "marketplace.json").write_text('{"name": "cx", "plugins": []}')
    answer = _marketplace(client, str(tmp_path / "codex-only"), ["claude_code"])
    assert answer.status_code == 422
    assert "Claude Code reads only" in answer.json()["detail"]
