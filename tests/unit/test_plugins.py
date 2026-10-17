"""Plugin on/off (T050): which plugins offer it, the steps, and round trips with undo."""

import json
from pathlib import Path

import pytest

import agentsetup.clients.base as base
from agentsetup.changes import json_splice, toml_edit
from agentsetup.changes.actions import plugin_steps
from agentsetup.changes.backup import ChangeStore
from agentsetup.changes.client_cli import CommandResult
from agentsetup.changes.engine import Engine
from agentsetup.clients.codex import CodexAdapter
from agentsetup.model import ChangeState
from agentsetup.views.inventory import build_inventory, default_adapters
from tests.conftest import make_home, write_cursor_fixture_state


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


@pytest.fixture
def home(tmp_path):
    # Cursor first: its fixture also has .claude files, and the Claude Code ones must win.
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return home


@pytest.fixture
def adapters(home):
    return {a.id: a for a in default_adapters(home)}


def plugin(inventory, client, name, scope="user"):
    return next(
        i
        for i in inventory.items
        if (i.client, i.name, str(i.scope)) == (client, name, scope) and str(i.kind) == "plugin"
    )


class FakeClaudePlugins:
    """Acts like `claude plugin enable|disable <id> -s <scope> --json`: rewrites settings."""

    def __init__(self, home):
        self.home = home

    def __call__(self, command, cwd):
        verb, plugin_id, scope = command[2], command[3], command[5]
        root = self.home if scope == "user" else Path(cwd)
        path = root / ".claude/settings.json"
        data = json.loads(path.read_text()) if path.exists() else {}
        data.setdefault("enabledPlugins", {})[plugin_id] = verb == "enable"
        enabled = data.pop("enabledPlugins")
        data["enabledPlugins"] = enabled  # the real CLI moves the key to the end
        path.write_text(json.dumps(data, indent=2))
        return CommandResult(0, '{"outcome":"ok"}')


def test_plugins_offer_the_opposite_of_their_state_where_the_state_is_in_a_file(home):
    inventory = build_inventory(home)
    actions = {
        (i.client, i.name, str(i.scope)): i.actions
        for i in inventory.items
        if str(i.kind) == "plugin"
    }
    assert actions[("claude_code", "superpowers@claude-plugins-official", "user")] == (
        "plugin.disable",
    )
    assert actions[("claude_code", "claude-md-management@claude-plugins-official", "user")] == (
        "plugin.enable",
    )
    assert actions[("claude_code", "superpowers@claude-plugins-official", "project")] == (
        "plugin.enable",
    )
    assert actions[("codex", "browser@openai-bundled", "user")] == ("plugin.disable",)
    assert actions[("codex", "pdf@openai-primary-runtime", "user")] == ("plugin.enable",)
    for key in [
        ("claude_code", "notes@synced", "account"),
        ("claude_code", "Claude account plugins and connectors", "account"),
        ("codex", "gmail@openai-curated-remote", "user"),
        ("cursor", "superpowers@cursor-public", "user"),
        ("cursor", "langfuse@cursor-public", "project"),
    ]:
        assert actions[key] == (), key


def test_plugins_without_a_control_say_where_to_change_them(home):
    inventory = build_inventory(home)
    assert "Customize" in plugin(inventory, "cursor", "superpowers@cursor-public").change_hint
    assert "account" in plugin(inventory, "codex", "gmail@openai-curated-remote").change_hint
    assert "Claude" in plugin(inventory, "claude_code", "notes@synced", "account").change_hint
    imported = plugin(inventory, "cursor", "superpowers@claude-plugins-official")
    assert "Claude Code" in imported.change_hint
    assert plugin(inventory, "codex", "browser@openai-bundled").change_hint is None


def test_claude_plugin_step_uses_the_cli_for_the_items_scope(home, adapters):
    inventory = build_inventory(home)
    user = plugin_steps(
        adapters, plugin(inventory, "claude_code", "superpowers@claude-plugins-official"), False
    )[0]
    assert user.mechanism == "client_cli"
    assert user.command == [
        "claude",
        "plugin",
        "disable",
        "superpowers@claude-plugins-official",
        "-s",
        "user",
        "--json",
    ]
    assert (user.edit.path, user.edit.key, user.edit.after) == (
        str(home / ".claude/settings.json"),
        ("enabledPlugins", "superpowers@claude-plugins-official"),
        False,
    )
    assert "/reload-plugins" in user.restart_note

    project = plugin_steps(
        adapters,
        plugin(inventory, "claude_code", "superpowers@claude-plugins-official", "project"),
        True,
    )[0]
    assert project.command[2:6] == [
        "enable",
        "superpowers@claude-plugins-official",
        "-s",
        "project",
    ]
    assert project.cwd == str(home / "work/website")
    assert project.shared_file is True


def test_an_action_the_item_does_not_offer_is_refused(home, adapters):
    inventory = build_inventory(home)
    with pytest.raises(ValueError, match="cannot be turned on"):
        plugin_steps(
            adapters, plugin(inventory, "claude_code", "superpowers@claude-plugins-official"), True
        )
    with pytest.raises(ValueError):
        plugin_steps(adapters, plugin(inventory, "cursor", "superpowers@cursor-public"), False)


def test_claude_plugin_off_then_undo_restores_the_exact_bytes(home, adapters, tmp_path):
    settings = home / ".claude/settings.json"
    original = settings.read_bytes()
    inventory = build_inventory(home)
    engine = Engine(ChangeStore(tmp_path / "data"), FakeClaudePlugins(home))
    steps = plugin_steps(
        adapters, plugin(inventory, "claude_code", "superpowers@claude-plugins-official"), False
    )
    change = engine.preview("plugin.disable", steps)
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED
    value = json_splice.get_value(
        settings.read_text(), ("enabledPlugins", "superpowers@claude-plugins-official")
    )
    assert value is False
    engine.undo(change.id)
    assert settings.read_bytes() == original


def test_codex_plugin_off_keeps_comments_and_undo_restores_bytes(home, adapters, tmp_path):
    config = home / ".codex/config.toml"
    original = config.read_bytes()
    inventory = build_inventory(home)
    engine = Engine(ChangeStore(tmp_path / "data"), run=None)
    step = plugin_steps(adapters, plugin(inventory, "codex", "browser@openai-bundled"), False)[0]
    assert (step.edit.fmt, step.edit.key, step.mechanism) == (
        "toml",
        ("plugins", "browser@openai-bundled", "enabled"),
        "format_preserving_edit",
    )
    change = engine.preview("plugin.disable", [step])
    engine.apply(change.id)
    text = config.read_text()
    assert toml_edit.get_value(text, ("plugins", "browser@openai-bundled", "enabled")) is False
    assert "# Owner comment: keep me" in text
    engine.undo(change.id)
    assert config.read_bytes() == original


def test_codex_remote_plugin_state_comes_from_the_codex_plugin_list(home):
    listing = {"installed": [{"pluginId": "gmail@openai-curated-remote", "enabled": False}]}
    adapter = CodexAdapter(home, read_version=lambda: "0.159.2", list_plugins=lambda: listing)
    gmail = next(i for i in adapter.scan().items if i.name == "gmail@openai-curated-remote")
    assert str(gmail.enabled) == "off"
    assert gmail.actions == ()
    assert "account" in gmail.change_hint


def test_codex_plugin_list_is_not_used_when_codex_is_missing(home):
    def boom():
        raise AssertionError("must not run")

    adapter = CodexAdapter(home, read_version=lambda: None, list_plugins=boom)
    gmail = next(i for i in adapter.scan().items if i.name == "gmail@openai-curated-remote")
    assert str(gmail.enabled) == "unknown"
