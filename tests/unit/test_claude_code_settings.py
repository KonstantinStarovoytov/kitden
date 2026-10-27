"""Claude Code's local settings and `skillOverrides` (checked 2026-10-26, see claude_code.py)."""

import json

import kitden.clients.claude_code as claude_code
from kitden.clients.claude_code import ClaudeCodeAdapter, git_root
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


def _state_in(home, project, name, scope=Scope.USER):
    view = effective_view(build_inventory(home), "claude_code", project)
    found = [i for i in view.items if i.kind is ItemKind.SKILL and i.name == name]
    # An Off skill is not in the loaded list: look it up in the inventory instead.
    if not found:
        inventory = build_inventory(home)
        (item,) = [
            i
            for i in inventory.items
            if i.kind is ItemKind.SKILL and i.name == name and i.scope is scope
        ]
        return Enabled.OFF, item
    return Enabled.ON, found[0]


def test_a_local_rule_turns_a_user_skill_on_in_that_project_only(tmp_path, no_version):
    home, root = _home(
        tmp_path,
        user={"skillOverrides": {"deploy": "off"}},
        local={"skillOverrides": {"deploy": "on"}},
    )
    state, item = _state_in(home, str(root), "deploy")
    assert (state, item.state_scope) == (Enabled.ON, Scope.LOCAL)
    state, item = _state_in(home, None, "deploy")
    assert (state, item.state_scope) == (Enabled.OFF, Scope.USER)
    # There is still one deploy item: nothing is duplicated in the inventory.
    names = [i.name for i in build_inventory(home).items if i.kind is ItemKind.SKILL]
    assert names.count("deploy") == 1


def test_a_local_rule_turns_a_user_skill_off_in_that_project_only(tmp_path, no_version):
    home, root = _home(tmp_path, local={"skillOverrides": {"deploy": "off"}})
    inventory = build_inventory(home)
    (user_skill,) = [i for i in inventory.items if i.name == "deploy"]
    assert (user_skill.enabled, user_skill.state_scope) == (Enabled.ON, None)
    inside = effective_view(inventory, "claude_code", str(root))
    assert "deploy" not in {i.name for i in inside.items}
    state, _ = _state_in(home, str(root), "deploy")
    assert state is Enabled.OFF
    outside = effective_view(inventory, "claude_code", None)
    assert "deploy" in {i.name for i in outside.items}
    # The rule source in that project is the local file.
    assert user_skill.project_rules == ((str(root), Enabled.OFF, Scope.LOCAL),)


def test_a_project_off_plugin_with_a_local_off_shows_on_under_all_projects(tmp_path, no_version):
    home, root = _home(
        tmp_path,
        user={"enabledPlugins": {PLUGIN: True}},
        local={"enabledPlugins": {PLUGIN: False}},
    )
    inventory = build_inventory(home)
    local = [i for i in inventory.items if i.name == PLUGIN and i.scope is Scope.LOCAL]
    assert [(i.enabled, i.state_scope) for i in local] == [(Enabled.OFF, Scope.LOCAL)]
    everywhere = effective_view(inventory, "claude_code", None)
    (plugin,) = [i for i in everywhere.items if i.name == PLUGIN]
    assert (plugin.scope, plugin.enabled) == (Scope.USER, Enabled.ON)
    assert not [
        i for i in effective_view(inventory, "claude_code", str(root)).items if i.name == PLUGIN
    ]


def test_skill_overrides_merge_across_files_for_one_project_skill(tmp_path, no_version):
    home, _ = _home(
        tmp_path,
        user={"skillOverrides": {"review": "off"}},
        local={"skillOverrides": {"other": "on"}},
    )
    items = _scan(home, no_version)
    assert _skill_state(items, "review", Scope.PROJECT) == (Enabled.OFF, Scope.USER)


def test_unreadable_settings_leave_skill_states_unknown(tmp_path, no_version):
    home, root = _home(tmp_path)
    (home / ".claude/settings.json").write_text("{ not json")
    items = _scan(home, no_version)
    assert _skill_state(items, "deploy", Scope.USER) == (Enabled.UNKNOWN, None)
    assert _skill_state(items, "review", Scope.PROJECT) == (Enabled.UNKNOWN, None)

    home, root = _home(tmp_path / "two", project={})
    (root / ".claude/settings.local.json").write_text("{ not json")
    items = _scan(home, no_version)
    assert _skill_state(items, "review", Scope.PROJECT) == (Enabled.UNKNOWN, None)
    assert _skill_state(items, "deploy", Scope.USER) == (Enabled.ON, None)


def _repository(tmp_path, root_local=None, own_local=None):
    """A sandbox home with a repository `repo` (its `.git` folder) and a known project in its
    subfolder `repo/web`, which has its own skill `review`."""
    home = tmp_path / "home"
    repo, web = home / "work/repo", home / "work/repo/web"
    _write(home / ".claude.json", {"projects": {str(web): {}}})
    _write(home / ".claude/settings.json", {})
    _write(
        home / ".claude/plugins/installed_plugins.json",
        {"plugins": {PLUGIN: [{"installPath": str(home / "nowhere")}]}},
    )
    (repo / ".git").mkdir(parents=True)
    (repo / ".claude").mkdir()
    (web / ".claude").mkdir(parents=True)
    if root_local is not None:
        _write(repo / ".claude/settings.local.json", root_local)
    if own_local is not None:
        _write(web / ".claude/settings.local.json", own_local)
    _skill(home / ".claude/skills", "deploy")
    _skill(web / ".claude/skills", "review")
    return home, repo, web


def test_a_project_in_a_subfolder_of_a_repository_reads_the_roots_local_file(tmp_path, no_version):
    # checked 2026-10-27 (code.claude.com/docs/en/settings): started in a subfolder of a git
    # repository, Claude Code reads .claude/settings.local.json at the repository root; a file an
    # earlier version left in the starting folder is still read, and the root's value wins.
    home, repo, web = _repository(
        tmp_path,
        root_local={"skillOverrides": {"deploy": "off"}, "enabledPlugins": {PLUGIN: False}},
        own_local={
            "skillOverrides": {"deploy": "on", "review": "off"},
            "enabledPlugins": {PLUGIN: True},
        },
    )
    inventory = build_inventory(home)
    state, item = _state_in(home, str(web), "deploy")
    assert (state, item.project_rules) == (Enabled.OFF, ((str(web), Enabled.OFF, Scope.LOCAL),))
    # The key only the starting folder's file has still counts.
    assert _skill_state(inventory.items, "review", Scope.PROJECT) == (Enabled.OFF, Scope.LOCAL)
    # The plugin: one local entry, the root's, off.
    local = [i for i in inventory.items if i.name == PLUGIN and i.scope is Scope.LOCAL]
    assert [(i.enabled, i.source.path) for i in local] == [
        (Enabled.OFF, str(repo / ".claude/settings.local.json"))
    ]
    assert not [
        i for i in effective_view(inventory, "claude_code", str(web)).items if i.name == PLUGIN
    ]


def test_the_roots_local_file_counts_only_for_a_repository_inside_home(tmp_path, no_version):
    # The repository root is the home folder: the file stays with the project (docs, same day).
    home, repo, web = _repository(tmp_path, root_local={"skillOverrides": {"deploy": "off"}})
    (repo / ".git").rmdir()
    (home / ".git").mkdir()
    state, _ = _state_in(home, str(web), "deploy")
    assert state is Enabled.ON
    # No repository at all: only the project's own file.
    (home / ".git").rmdir()
    assert _state_in(home, str(web), "deploy")[0] is Enabled.ON


def test_git_root_follows_only_a_repository_folder_the_user_owns(tmp_path, monkeypatch):
    home = tmp_path / "home"
    repo, web = home / "work/repo", home / "work/repo/web"
    web.mkdir(parents=True)
    (repo / ".git").mkdir()
    assert git_root(web, home) == repo
    # The project is the root itself: its own file is the root's.
    assert git_root(repo, home) is None
    # A `.git` file (a worktree or a submodule): Kitden does not follow it.
    (repo / ".git").rmdir()
    (repo / ".git").write_text("gitdir: /elsewhere/.git/worktrees/repo\n")
    assert git_root(web, home) is None
    (repo / ".git").unlink()
    (repo / ".git").mkdir()
    # Not the user's own: the file stays with the project (docs checked 2026-10-27).
    monkeypatch.setattr(claude_code.os, "getuid", lambda: -1)
    assert git_root(web, home) is None
    monkeypatch.undo()
    # Outside home, the walk goes up to the repository; it never passes the home folder.
    outside = tmp_path / "srv/repo"
    (outside / ".git").mkdir(parents=True)
    (outside / "api").mkdir()
    assert git_root(outside / "api", home) == outside
    (tmp_path / ".git").mkdir()
    (repo / ".git").rmdir()
    assert git_root(web, home) is None
