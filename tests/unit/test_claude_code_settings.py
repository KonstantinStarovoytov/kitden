"""Claude Code's local settings and `skillOverrides` (checked 2026-10-26, see claude_code.py)."""

import json

from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.model import Enabled, ItemKind, Scope
from kitden.views.effective import effective_view
from kitden.views.inventory import build_inventory

PLUGIN = "lint@tools"


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _skill(folder, name):
    (folder / name).mkdir(parents=True)
    (folder / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {name}\n---\n")


def _home(tmp_path, user=None, project=None, local=None):
    """A sandbox home with one known project and a user skill and a project skill, both `deploy`."""
    home = tmp_path / "home"
    root = home / "work/app"
    _write(home / ".claude.json", {"projects": {str(root): {}}})
    _write(home / ".claude/settings.json", user or {})
    _write(
        home / ".claude/plugins/installed_plugins.json",
        {"plugins": {PLUGIN: [{"installPath": str(home / "nowhere")}]}},
    )
    if project is not None:
        _write(root / ".claude/settings.json", project)
    if local is not None:
        _write(root / ".claude/settings.local.json", local)
    _skill(home / ".claude/skills", "deploy")
    _skill(root / ".claude/skills", "review")
    return home, root


def _scan(home, no_version):
    return ClaudeCodeAdapter(home, read_version=no_version).scan().items


def _plugin_rows(items):
    return {
        (str(i.scope), str(i.enabled), str(i.state_scope))
        for i in items
        if i.kind is ItemKind.PLUGIN and i.name == PLUGIN
    }


def _skill_state(items, name, scope):
    (item,) = [i for i in items if i.kind is ItemKind.SKILL and i.name == name and i.scope is scope]
    return item.enabled, item.state_scope


def test_local_enabled_plugins_win_over_project_and_user(tmp_path, no_version):
    home, root = _home(
        tmp_path,
        user={"enabledPlugins": {PLUGIN: False}},
        project={"enabledPlugins": {PLUGIN: False}},
        local={"enabledPlugins": {PLUGIN: True}},
    )
    items = _scan(home, no_version)
    assert _plugin_rows(items) == {
        ("user", "off", "user"),
        ("project", "off", "project"),
        ("local", "on", "local"),
    }
    view = effective_view(build_inventory(home), "claude_code", str(root))
    (loaded,) = [i for i in view.items if i.kind is ItemKind.PLUGIN and i.name == PLUGIN]
    assert loaded.scope is Scope.LOCAL
    assert loaded.state_scope is Scope.LOCAL
    # With no project, only the user file counts.
    outside = effective_view(build_inventory(home), "claude_code", None)
    assert not [i for i in outside.items if i.kind is ItemKind.PLUGIN and i.name == PLUGIN]


def test_a_project_off_plugin_shows_on_under_all_projects(tmp_path, no_version):
    home, root = _home(
        tmp_path,
        user={"enabledPlugins": {PLUGIN: True}},
        project={"enabledPlugins": {PLUGIN: False}},
    )
    inventory = build_inventory(home)
    everywhere = effective_view(inventory, "claude_code", None)
    (user_plugin,) = [i for i in everywhere.items if i.name == PLUGIN]
    assert (user_plugin.scope, user_plugin.enabled) == (Scope.USER, Enabled.ON)
    inside = effective_view(inventory, "claude_code", str(root))
    assert not [i for i in inside.items if i.name == PLUGIN]


def test_skill_overrides_off_in_user_settings_turns_the_skill_off(tmp_path, no_version):
    home, _ = _home(tmp_path, user={"skillOverrides": {"deploy": "off"}})
    items = _scan(home, no_version)
    assert _skill_state(items, "deploy", Scope.USER) == (Enabled.OFF, Scope.USER)
    # A skill with no rule has no rule source.
    assert _skill_state(items, "review", Scope.PROJECT) == (Enabled.ON, None)


def test_skill_overrides_most_specific_file_wins_key_by_key(tmp_path, no_version):
    home, _ = _home(
        tmp_path,
        user={"skillOverrides": {"review": "off", "other": "off"}},
        project={"skillOverrides": {"review": "on"}},
        local={"skillOverrides": {"review": "off", "extra": "name-only"}},
    )
    items = _scan(home, no_version)
    # local beats project and user for `review`.
    assert _skill_state(items, "review", Scope.PROJECT) == (Enabled.OFF, Scope.LOCAL)

    home, _ = _home(
        tmp_path / "two",
        user={"skillOverrides": {"review": "off", "deploy": "off"}},
        project={"skillOverrides": {"review": "on"}},
    )
    items = _scan(home, no_version)
    # project turns `review` back on; the user rule for `deploy` is still read key by key.
    assert _skill_state(items, "review", Scope.PROJECT) == (Enabled.ON, Scope.PROJECT)
    assert _skill_state(items, "deploy", Scope.USER) == (Enabled.OFF, Scope.USER)


def test_unknown_skill_override_values_are_ignored(tmp_path, no_version):
    home, _ = _home(
        tmp_path,
        user={"skillOverrides": {"deploy": "off"}},
        project={"skillOverrides": {"review": "maybe"}},
        local={"skillOverrides": {"deploy": 3, "review": False}},
    )
    items = _scan(home, no_version)
    assert _skill_state(items, "review", Scope.PROJECT) == (Enabled.ON, None)
    # The bad local value does not hide the valid user rule.
    assert _skill_state(items, "deploy", Scope.USER) == (Enabled.OFF, Scope.USER)
