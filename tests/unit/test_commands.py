"""Show-only commands (T054, FR-029): the tool shows them and never runs them."""

import pytest

import agentsetup.clients.base as base
from agentsetup.views.commands import commands_for
from agentsetup.views.inventory import build_inventory, default_adapters
from tests.conftest import make_home, write_cursor_fixture_state


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


@pytest.fixture
def setup(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return build_inventory(home), {a.id: a for a in default_adapters(home)}


def find(inventory, client, kind, name, scope="user"):
    return next(
        i
        for i in inventory.items
        if (i.client, str(i.kind), i.name, str(i.scope)) == (client, kind, name, scope)
    )


def _by_label(commands):
    return {c.label: c for c in commands}


def test_claude_plugin_commands_include_moving_it_to_codex_and_cursor(setup):
    inventory, adapters = setup
    item = find(inventory, "claude_code", "plugin", "superpowers@claude-plugins-official")
    commands = _by_label(commands_for(item, adapters))
    assert commands["Update in Claude Code"].command == (
        "claude plugin update superpowers@claude-plugins-official"
    )
    assert commands["Uninstall from Claude Code"].command == (
        "claude plugin uninstall superpowers@claude-plugins-official -s user"
    )
    assert commands["Install in Codex"].command == (
        "codex plugin marketplace add anthropics/claude-plugins-official\n"
        "codex plugin add superpowers@claude-plugins-official"
    )
    assert "Include Third-Party Plugins" in commands["Use in Cursor"].note


def test_codex_built_in_plugin_cannot_be_moved(setup):
    inventory, adapters = setup
    item = find(inventory, "codex", "plugin", "browser@openai-bundled")
    commands = _by_label(commands_for(item, adapters))
    assert commands["Uninstall from Codex"].command == "codex plugin remove browser@openai-bundled"
    assert commands["Install in Claude Code"].command is None
    assert "comes with Codex" in commands["Install in Claude Code"].note


def test_marketplace_commands_add_it_to_the_other_clients(setup):
    inventory, adapters = setup
    item = find(inventory, "claude_code", "marketplace", "claude-plugins-official")
    commands = _by_label(commands_for(item, adapters))
    assert commands["Add to Codex"].command == (
        "codex plugin marketplace add anthropics/claude-plugins-official"
    )


def test_cursor_plugins_point_to_the_cursor_interface(setup):
    inventory, adapters = setup
    item = find(inventory, "cursor", "plugin", "superpowers@cursor-public")
    commands = commands_for(item, adapters)
    assert all(c.command is None for c in commands)
    assert any("Customize" in (c.note or "") for c in commands)


def test_items_that_are_not_plugins_or_marketplaces_have_no_commands(setup):
    inventory, adapters = setup
    item = find(inventory, "codex", "mcp_server", "neon")
    assert commands_for(item, adapters) == []


def test_git_sources_with_credentials_are_hidden(setup, tmp_path):
    from agentsetup.views.commands import marketplace_add

    command = marketplace_add(
        "codex", "https://user:ghp_a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6@github.com/a/b.git"
    )
    assert "ghp_" not in command and "user:" not in command
