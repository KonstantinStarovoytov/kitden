"""Adding the read-only setup server to clients (T060, FR-032)."""

import json
import shutil
from pathlib import Path

import pytest

from kitden.changes.actions import setup_server_steps
from kitden.model import Client, ClientStatus, Enabled, Item, ItemKind, Scope, Source, SourceKind
from kitden.views.inventory import Inventory, build_inventory, default_adapters
from kitden.views.setup_server import enable_steps, is_own_entry, setup_server_state
from tests.conftest import make_home

COMMAND = "/Users/me/.local/bin/kitden"


def test_each_client_gets_a_stdio_entry_with_the_absolute_path(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2")
    adapters = {a.id: a for a in default_adapters(home)}
    steps = {
        s.client: s
        for s in setup_server_steps(adapters, ["claude_code", "codex", "cursor"], COMMAND)
    }

    claude = steps["claude_code"]
    value = {"type": "stdio", "command": COMMAND, "args": ["mcp"]}
    assert claude.command == [
        "claude",
        "mcp",
        "add-json",
        "-s",
        "user",
        "kitden",
        json.dumps(value),
    ]
    assert claude.edit.after == value
    assert steps["codex"].edit.after == {"command": COMMAND, "args": ["mcp"]}
    assert steps["codex"].edit.key == ("mcp_servers", "kitden")
    assert steps["cursor"].edit.after == {"command": COMMAND, "args": ["mcp"]}
    assert all(s.restart_note for s in steps.values())


def test_a_relative_command_is_refused(tmp_path):
    home = make_home(tmp_path, "codex/0.159.2")
    adapters = {a.id: a for a in default_adapters(home)}
    with pytest.raises(ValueError, match="absolute"):
        setup_server_steps(adapters, ["codex"], "kitden")


# Feature 003, FR-014: a server a plugin provides.
PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins/kitden"


def _found(client: str) -> Client:
    return Client(id=client, display_name=client, status=ClientStatus.FOUND)


def _server(client: str, scope: Scope, name: str = "kitden") -> Item:
    kind = SourceKind.PLUGIN if scope is Scope.PLUGIN else SourceKind.FILE
    return Item(
        client=client,
        kind=ItemKind.MCP_SERVER,
        name=name,
        source=Source(kind=kind, path=f"/h/{scope}/.mcp.json", owner_client=client),
        scope=scope,
        enabled=Enabled.ON,
        summary=(("command", "kitden"), ("args", '["mcp"]')),
    )


def _state(inventory, client: str) -> dict:
    return next(s for s in setup_server_state(inventory) if s["client"] == client)


def test_a_server_from_a_plugin_gives_the_plugin_state():
    items = [_server("claude_code", Scope.PLUGIN)]
    inventory = Inventory(clients=[_found("claude_code")], items=items)
    state = _state(inventory, "claude_code")
    assert state["state"] == "plugin"
    assert state["enabled"] is True
    assert state["item"] is None


def test_a_user_entry_wins_over_a_plugin_server():
    items = [_server("claude_code", Scope.PLUGIN), _server("claude_code", Scope.USER)]
    inventory = Inventory(clients=[_found("claude_code")], items=items)
    assert _state(inventory, "claude_code")["state"] == "added"


def test_a_plugin_server_with_another_name_is_not_kitden():
    items = [_server("codex", Scope.PLUGIN, "other")]
    inventory = Inventory(clients=[_found("codex")], items=items)
    assert _state(inventory, "codex")["state"] == "missing"


def test_own_entry_includes_the_plugin_provided_server():
    assert is_own_entry(_server("claude_code", Scope.PLUGIN))
    assert is_own_entry(_server("codex", Scope.USER))
    assert not is_own_entry(_server("claude_code", Scope.PLUGIN, "other"))


def test_the_installed_plugin_is_read_from_claude_code_files(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    cache = home / ".claude/plugins/cache/kitden/kitden/0.1.0"
    shutil.copytree(PLUGIN_DIR, cache)
    (home / ".claude/plugins/installed_plugins.json").write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "kitden@kitden": [
                        {"scope": "user", "installPath": str(cache), "version": "0.1.0"}
                    ]
                },
            }
        )
    )
    assert _state(build_inventory(home), "claude_code")["state"] == "plugin"


def test_an_old_entry_beside_the_plugin_server_keeps_the_plugin_state(tmp_path):
    """Review 2026-10-18: the plugin provides the server, so the old entry is only removed."""
    home = make_home(tmp_path, "claude_code/2.1.283")
    old_command = home / ".local/bin/agentsetup"
    old_command.parent.mkdir(parents=True)
    old_command.write_text("#!/bin/sh\n")
    settings = home / ".claude.json"
    data = json.loads(settings.read_text())
    old = {"type": "stdio", "command": str(old_command), "args": ["mcp"]}
    data["mcpServers"]["agentsetup"] = old
    settings.write_text(json.dumps(data))
    cache = home / ".claude/plugins/cache/kitden/kitden/0.1.0"
    shutil.copytree(PLUGIN_DIR, cache)
    installs = {"kitden@kitden": [{"scope": "user", "installPath": str(cache)}]}
    (home / ".claude/plugins/installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": installs})
    )
    state = _state(build_inventory(home), "claude_code")
    assert state["state"] == "plugin"
    assert state["item"] is not None and state["command_exists"] is True


# Turning the kitden entry back on (spec Part 4, 4.4). Codex's docs name the key (checked
# 2026-10-24): `enabled = false` in the entry's own table turns it off.
KITDEN_OFF = (
    '\n[mcp_servers.kitden]\ncommand = "/opt/kitden/bin/kitden"\nargs = ["mcp"]\nenabled = false\n'
)


def test_only_codex_has_a_step_that_turns_the_entry_on(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    adapters = {a.id: a for a in default_adapters(home)}
    [step] = enable_steps(adapters, "codex")
    assert (step.client, step.name, step.edit.fmt) == ("codex", "kitden", "toml")
    assert (step.edit.key, step.edit.after) == (("mcp_servers", "kitden", "enabled"), True)
    assert step.edit.path == str(home / ".codex/config.toml") and step.restart_note
    for client, name in (("claude_code", "Claude Code"), ("cursor", "Cursor")):
        with pytest.raises(ValueError, match=f"Turn it on in {name}'s own MCP settings."):
            enable_steps(adapters, client)


def test_a_codex_kitden_entry_turned_off_can_be_turned_on_and_undone(tmp_path, monkeypatch):
    from tests.unit.test_api_changes import POST, _app_client, _files, _home

    home = _home(tmp_path, monkeypatch)
    config = home / ".codex/config.toml"
    config.write_text(config.read_text() + KITDEN_OFF)
    original = _files(home)
    with _app_client(home) as client:
        client.get("/?token=tok")
        entry = next(e for e in client.get("/api/setup-server").json() if e["client"] == "codex")
        assert (entry["state"], entry["enabled"]) == ("added", False)
        body = {"action": "setup_server.enable", "targets": [{"client": "codex"}], "params": {}}
        change = client.post("/api/changes/preview", json=body, headers=POST).json()
        assert _files(home) == original
        assert "-enabled = false" in change["steps"][0]["diff"]
        assert "+enabled = true" in change["steps"][0]["diff"]
        assert change["after"] == [{"client": "codex", "state": "on", "word": "On"}]
        applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        entry = next(e for e in client.get("/api/setup-server").json() if e["client"] == "codex")
        assert entry["enabled"] is True
        # Only the kitden entry's switch changed: the owner's comment and aseprite's stay.
        on = KITDEN_OFF.replace("enabled = false", "enabled = true")
        assert config.read_text() == original[".codex/config.toml"].decode().replace(KITDEN_OFF, on)
        client.post(f"/api/changes/{change['id']}/undo", headers=POST)
        assert _files(home) == original


def test_turning_on_an_entry_that_is_not_off_is_refused(tmp_path, monkeypatch):
    from tests.unit.test_api_changes import POST, _app_client, _files, _home

    home = _home(tmp_path, monkeypatch)
    original = _files(home)
    with _app_client(home) as client:
        client.get("/?token=tok")
        for target in ({"client": "codex"}, {"client": "cursor"}):
            body = {"action": "setup_server.enable", "targets": [target], "params": {}}
            answer = client.post("/api/changes/preview", json=body, headers=POST)
            assert answer.status_code == 422
    assert _files(home) == original
