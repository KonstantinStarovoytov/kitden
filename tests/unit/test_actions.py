"""Which items offer which actions (FR-025, FR-026) and the steps each client uses (T045)."""

import json

import pytest

import kitden.clients.base as base
from kitden.changes.actions import connect_steps, remove_steps
from kitden.changes.json_splice import ABSENT
from kitden.model import Gateway, GatewayAuth
from kitden.views.inventory import build_inventory, default_adapters
from tests.conftest import make_home, write_cursor_fixture_state

URL = "http://127.0.0.1:12008/metamcp/dev/mcp"
KEYED = Gateway(url=URL, auth=GatewayAuth.ENV_KEY, key_env_var="GW_KEY")


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


@pytest.fixture
def adapters(home):
    return {a.id: a for a in default_adapters(home)}


def _item(inventory, client, name, scope):
    return next(
        i
        for i in inventory.items
        if (i.client, i.name, str(i.scope)) == (client, name, scope) and str(i.kind) == "mcp_server"
    )


def test_only_direct_entries_in_files_can_be_removed_and_nothing_adds_or_toggles_mcp(home):
    inventory = build_inventory(home)
    assert {a for i in inventory.items for a in i.actions} == {
        "mcp.remove_direct",
        "plugin.enable",
        "plugin.disable",
    }
    mcp_actions = {a for i in inventory.items if str(i.kind) == "mcp_server" for a in i.actions}
    assert mcp_actions == {"mcp.remove_direct"}
    removable = {
        (i.client, i.name, str(i.scope))
        for i in inventory.items
        if "mcp.remove_direct" in i.actions
    }
    assert removable == {
        ("claude_code", "github", "user"),
        ("claude_code", "local-db", "local"),
        ("claude_code", "docs", "project"),
        ("claude_code", "old-search", "project"),
        ("codex", "neon", "user"),
        ("codex", "langfuse-data", "user"),
        ("codex", "aseprite", "user"),
        ("codex", "api-docs", "project"),
        ("codex", "neon", "project"),
        ("codex", "evil", "project"),
        ("cursor", "Neon", "user"),
        ("cursor", "n8n-mcp", "user"),
        ("cursor", "site-db", "project"),
    }


def test_gateway_entries_use_key_references_in_each_client(home, adapters):
    steps = {
        s.client: s
        for s in connect_steps(adapters, ["claude_code", "codex", "cursor"], KEYED, "gateway")
    }

    claude = steps["claude_code"]
    assert claude.mechanism == "client_cli"
    assert claude.command[:6] == ["claude", "mcp", "add-json", "-s", "user", "gateway"]
    value = {"type": "http", "url": URL, "headers": {"Authorization": "Bearer ${GW_KEY}"}}
    assert json.loads(claude.command[6]) == value == claude.edit.after
    assert (claude.edit.path, claude.edit.key, claude.edit.check) == (
        str(home / ".claude.json"),
        ("mcpServers", "gateway"),
        "entry",
    )

    codex = steps["codex"]
    assert (codex.mechanism, codex.edit.fmt, codex.edit.path) == (
        "format_preserving_edit",
        "toml",
        str(home / ".codex/config.toml"),
    )
    assert codex.edit.after == {"url": URL, "bearer_token_env_var": "GW_KEY"}

    cursor = steps["cursor"]
    assert cursor.edit.path == str(home / ".cursor/mcp.json")
    assert cursor.edit.after == {"url": URL, "headers": {"Authorization": "Bearer ${env:GW_KEY}"}}

    assert all(s.restart_note for s in steps.values())
    assert not any(s.shared_file or s.login_note for s in steps.values())


def test_oauth_gateway_shows_each_clients_login_step(adapters):
    oauth = Gateway(url=URL, auth=GatewayAuth.OAUTH)
    notes = {
        s.client: s.login_note
        for s in connect_steps(adapters, ["claude_code", "codex", "cursor"], oauth, "gw")
    }
    assert "/mcp" in notes["claude_code"]
    assert "codex mcp login gw" in notes["codex"]
    assert "Cursor" in notes["cursor"]


def test_unknown_client_is_refused(adapters):
    with pytest.raises(ValueError, match="claude_desktop_code_tab"):
        connect_steps(adapters, ["claude_desktop_code_tab"], KEYED, "gateway")


def test_remove_steps_for_each_client_and_scope(home, adapters):
    inventory = build_inventory(home)
    website = str(home / "work/website")

    local = remove_steps(adapters, _item(inventory, "claude_code", "local-db", "local"))[0]
    assert local.command == ["claude", "mcp", "remove", "-s", "local", "local-db"]
    assert local.cwd == website
    assert local.edit.key == ("projects", website, "mcpServers", "local-db")
    assert (local.edit.after, local.edit.check, local.shared_file) == (ABSENT, "entry", False)

    project = remove_steps(adapters, _item(inventory, "claude_code", "docs", "project"))[0]
    assert project.command == ["claude", "mcp", "remove", "-s", "project", "docs"]
    assert project.edit.path == str(home / "work/website/.mcp.json")
    assert (project.edit.check, project.shared_file) == ("file", True)

    codex = remove_steps(adapters, _item(inventory, "codex", "api-docs", "project"))[0]
    assert (codex.edit.fmt, codex.edit.key, codex.shared_file) == (
        "toml",
        ("mcp_servers", "api-docs"),
        True,
    )

    cursor = remove_steps(adapters, _item(inventory, "cursor", "Neon", "user"))[0]
    assert (cursor.edit.path, cursor.edit.key, cursor.shared_file) == (
        str(home / ".cursor/mcp.json"),
        ("mcpServers", "Neon"),
        False,
    )


def test_removal_is_refused_for_items_without_the_action(home, adapters):
    inventory = build_inventory(home)
    desktop = _item(inventory, "claude_desktop_code_tab", "metamcp-local", "user")
    with pytest.raises(ValueError, match="cannot be removed"):
        remove_steps(adapters, desktop)
