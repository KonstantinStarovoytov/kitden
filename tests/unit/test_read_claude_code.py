import json
from dataclasses import replace

from kitden.clients.base import PLUGIN_DISABLE, PLUGIN_REMOVE
from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.model import ClientStatus, Enabled, ItemKind, Scope, UnknownReason
from kitden.system import claude_desktop_dir
from kitden.views.inventory import build_inventory
from tests.conftest import all_text, make_home, rows

FIXTURE = "claude_code/2.1.283"

EXPECTED = {
    ("claude_code", "mcp_server", "github", "user", "on", None),
    ("claude_code", "mcp_server", "local-db", "local", "on", "work/website"),
    ("claude_code", "mcp_server", "docs", "project", "on", "work/website"),
    ("claude_code", "mcp_server", "old-search", "project", "off", "work/website"),
    ("claude_code", "mcp_server", "md-index", "plugin", "off", None),
    ("claude_code", "plugin", "superpowers@claude-plugins-official", "user", "on", None),
    (
        "claude_code",
        "plugin",
        "superpowers@claude-plugins-official",
        "project",
        "off",
        "work/website",
    ),
    ("claude_code", "plugin", "claude-md-management@claude-plugins-official", "user", "off", None),
    ("claude_code", "plugin", "notes@synced", "account", "on", None),
    ("claude_code", "plugin", "Claude account plugins and connectors", "account", "unknown", None),
    ("claude_code", "skill", "brandkit", "user", "on", None),
    ("claude_code", "skill", "shared-style", "user", "on", None),
    ("claude_code", "skill", "site-style", "project", "on", "work/website"),
    ("claude_code", "skill", "brainstorming", "plugin", "on", None),
    ("claude_code", "hook", "PreToolUse: Bash", "user", "on", None),
    ("claude_code", "marketplace", "claude-plugins-official", "user", "on", None),
    ("claude_desktop_code_tab", "mcp_server", "team-proxy", "user", "on", None),
    ("claude_code", "instructions", "CLAUDE.md", "user", "on", None),
    ("claude_code", "instructions", "review", "user", "on", None),
    ("claude_code", "instructions", "reviewer", "user", "on", None),
    ("claude_code", "instructions", "CLAUDE.md", "project", "on", "work/website"),
    ("claude_code", "instructions", "deploy", "project", "on", "work/website"),
}


def test_scan_lists_every_item_with_scope_and_state(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    assert rows(scan.items, home) == EXPECTED
    assert scan.problems == []


def test_scan_never_shows_secret_values(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    assert "SENTINEL_SECRET" not in all_text(scan)
    flagged = {i.name for i in scan.items if i.secret_present}
    assert flagged == {"github", "local-db"}


def test_symlinked_skill_shows_its_real_location(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    (skill,) = [i for i in scan.items if i.name == "shared-style"]
    assert skill.source.path == str(home / "shared/style/SKILL.md")
    assert skill.source.link_path == str(home / ".claude/skills/shared-style")


def test_projects_report_missing_folders(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    exists = {p.path.removeprefix(str(home) + "/"): p.exists for p in scan.projects}
    assert exists == {"work/website": True, "work/deleted-project": False}


def test_unreadable_settings_become_unknown_not_a_crash(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    settings = home / ".claude/settings.json"
    settings.chmod(0)
    try:
        scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    finally:
        settings.chmod(0o644)
    assert [(p.path, p.unknown_reason) for p in scan.problems] == [
        (str(settings), UnknownReason.NO_ACCESS)
    ]
    (plugin,) = [
        i
        for i in scan.items
        if i.name == "superpowers@claude-plugins-official" and str(i.scope) == "user"
    ]
    assert plugin.enabled is Enabled.UNKNOWN


def test_broken_json_is_reported_and_other_files_still_read(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    (home / ".claude.json").write_text("{ not json")
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    assert [(p.path, p.unknown_reason) for p in scan.problems] == [
        (str(home / ".claude.json"), UnknownReason.PARSE_ERROR)
    ]
    assert ("claude_code", "skill", "brandkit", "user", "on", None) in rows(scan.items, home)


def test_detect_reports_version_and_support(tmp_path):
    home = make_home(tmp_path, FIXTURE)
    client = ClaudeCodeAdapter(home, read_version=lambda: "2.1.283").detect()
    assert (client.status, client.version, client.version_supported) == (
        ClientStatus.FOUND,
        "2.1.283",
        True,
    )


def test_desktop_code_tab_is_its_own_client_with_its_bundled_version(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    bundled = claude_desktop_dir(home) / "claude-code"
    for version in ("2.1.295", "2.1.299", "latest"):
        (bundled / version).mkdir(parents=True)
    (desktop,) = ClaudeCodeAdapter(home, read_version=no_version).extra_clients()
    assert (desktop.id, desktop.status, desktop.version, desktop.version_supported) == (
        "claude_desktop_code_tab",
        ClientStatus.FOUND,
        "2.1.299",
        True,
    )


def test_no_desktop_client_without_claude_desktop(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    (claude_desktop_dir(home) / "claude_desktop_config.json").unlink()
    assert ClaudeCodeAdapter(home, read_version=no_version).extra_clients() == []


def test_detect_without_files_or_command_is_not_found(tmp_path, no_version):
    client = ClaudeCodeAdapter(tmp_path / "empty", read_version=no_version).detect()
    assert client.status is ClientStatus.NOT_FOUND


def test_the_desktop_tab_keeps_its_folder_version_in_a_scan(tmp_path):
    home = make_home(tmp_path, FIXTURE)
    (claude_desktop_dir(home) / "claude-code/2.1.299").mkdir(parents=True)
    clients = {c.id: c for c in build_inventory(home).clients}
    assert clients["claude_desktop_code_tab"].version == "2.1.299"
    assert clients["claude_code"].version is None


def _instructions(home, no_version):
    return {
        (i.scope, i.name, dict(i.summary)["category"], i.project)
        for i in ClaudeCodeAdapter(home, read_version=no_version).scan().items
        if i.kind is ItemKind.INSTRUCTIONS
    }


def test_scan_reads_instructions_commands_and_agents(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    site = str(home / "work/website")
    assert _instructions(home, no_version) == {
        (Scope.USER, "CLAUDE.md", "instructions", None),
        (Scope.USER, "review", "command", None),
        (Scope.USER, "reviewer", "agent", None),
        (Scope.PROJECT, "CLAUDE.md", "instructions", site),
        (Scope.PROJECT, "deploy", "command", site),
    }


def test_scan_reads_every_project_instruction_file_and_rules(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    site = home / "work/website"
    (site / ".claude/CLAUDE.md").write_text("x")
    (site / "CLAUDE.local.md").write_text("x")
    (site / ".claude/agents").mkdir()
    (site / ".claude/agents/tester.md").write_text("x")
    (site / ".claude/rules/frontend").mkdir(parents=True)
    (site / ".claude/rules/frontend/css.md").write_text("x")
    (home / ".claude/rules").mkdir()
    (home / ".claude/rules/style.md").write_text("x")
    found = {(i[0], i[1], i[2]) for i in _instructions(home, no_version)}
    assert {
        (Scope.PROJECT, "CLAUDE.md", "instructions"),
        (Scope.PROJECT, "CLAUDE.local.md", "instructions"),
        (Scope.PROJECT, "tester", "agent"),
        (Scope.PROJECT, "frontend:css", "instructions"),
        (Scope.USER, "style", "instructions"),
    } <= found
    paths = {
        i.source.path
        for i in ClaudeCodeAdapter(home, read_version=no_version).scan().items
        if i.kind is ItemKind.INSTRUCTIONS and i.name == "CLAUDE.md"
    }
    assert str(site / ".claude/CLAUDE.md") in paths and str(site / "CLAUDE.md") in paths


def test_a_missing_project_gives_no_instruction_rows(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    state = json.loads((home / ".claude.json").read_text())
    state["projects"][str(home / "work/gone")] = {}
    (home / ".claude.json").write_text(json.dumps(state))
    projects = {i[3] for i in _instructions(home, no_version)}
    assert projects == {None, str(home / "work/website")}


def test_commands_in_sub_folders_are_named_with_a_colon(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    commands = home / ".claude/commands"
    (commands / "notes.txt").write_text("x")
    (commands / "frontend").mkdir()
    (commands / "frontend/component.md").write_text("x")
    names = {i[1] for i in _instructions(home, no_version) if i[2] == "command"}
    assert names == {"review", "frontend:component", "deploy"}


def test_the_home_folder_as_a_project_keeps_only_its_root_files(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    (home / "CLAUDE.md").write_text("x")
    (home / "CLAUDE.local.md").write_text("x")
    state = json.loads((home / ".claude.json").read_text())
    state["projects"][str(home)] = {}
    (home / ".claude.json").write_text(json.dumps(state))
    in_home = {(i[1], i[2]) for i in _instructions(home, no_version) if i[3] == str(home)}
    assert in_home == {("CLAUDE.md", "instructions"), ("CLAUDE.local.md", "instructions")}


def test_claude_desktop_config_is_read_from_the_linux_config_folder(system, tmp_path, no_version):
    system("linux")
    home = make_home(tmp_path, FIXTURE)
    assert (home / ".config/Claude/claude_desktop_config.json").is_file()
    assert not (home / "Library").exists()
    (desktop,) = ClaudeCodeAdapter(home, read_version=no_version).extra_clients()
    assert desktop.id == "claude_desktop_code_tab"


def _scan_with_bad_project_file(tmp_path, no_version, make_bad, problem=True):
    """Scan with the project's .mcp.json made bad. The scan runs in a thread that must finish
    within 10 seconds. With `problem`, the bad file must be a problem of its own."""
    import os
    import threading

    home = make_home(tmp_path, FIXTURE)
    bad = home / "work/website/.mcp.json"
    bad.unlink()
    make_bad(bad)
    done = {}

    def scan():
        done["scan"] = ClaudeCodeAdapter(home, read_version=no_version).scan()

    worker = threading.Thread(target=scan, daemon=True)
    worker.start()
    worker.join(10)
    if worker.is_alive():  # let a stuck reader go before failing
        os.close(os.open(bad, os.O_WRONLY | os.O_NONBLOCK))
    assert "scan" in done, "the scan did not finish"
    problems = [(p.path, p.unknown_reason) for p in done["scan"].problems]
    if problem:
        assert (str(bad), UnknownReason.PARSE_ERROR) in problems
    found = rows(done["scan"].items, home)
    assert ("claude_code", "skill", "brandkit", "user", "on", None) in found
    assert ("claude_code", "mcp_server", "local-db", "local", "on", "work/website") in found


def test_a_project_file_that_is_not_utf8_is_a_problem_of_its_own(tmp_path, no_version):
    _scan_with_bad_project_file(tmp_path, no_version, lambda p: p.write_bytes(b'{"a": "\xff"}'))


def test_a_fifo_named_like_a_project_file_does_not_stop_the_scan(tmp_path, no_version):
    import os

    _scan_with_bad_project_file(tmp_path, no_version, os.mkfifo)


def test_a_deeply_nested_project_file_does_not_stop_the_scan(tmp_path, no_version):
    # Whether Python parses this depends on the stack it has, so only the scan is checked.
    deep = "[" * 100_000 + "]" * 100_000
    _scan_with_bad_project_file(tmp_path, no_version, lambda p: p.write_text(deep), False)


def test_a_file_too_deep_for_the_parser_is_a_problem_of_its_own(tmp_path, no_version, monkeypatch):
    import json

    real = json.loads

    def loads(text, *args, **kwargs):
        if text.startswith("[[["):
            raise RecursionError
        return real(text, *args, **kwargs)

    monkeypatch.setattr(json, "loads", loads)
    _scan_with_bad_project_file(tmp_path, no_version, lambda p: p.write_text("[[[]]]"))


# Project `.mcp.json` approvals. Claude Code 2.1.311, run in a sandbox home on 2026-11-15, moved
# `enabledMcpjsonServers` and `disabledMcpjsonServers` from `~/.claude.json` to the project's
# `.claude/settings.local.json` and left only `hasTrustDialogAccepted` in the project's entry.


def _approvals(tmp_path, no_version, trust: bool = True, local: dict | None = None):
    """A home whose website project keeps its approvals in its local file, as 2.1.311 left it."""
    home = make_home(tmp_path, FIXTURE)
    site = home / "work/website"
    state = json.loads((home / ".claude.json").read_text())
    state["projects"][str(site)] = {"hasTrustDialogAccepted": trust}
    (home / ".claude.json").write_text(json.dumps(state))
    if local is None:
        local = {"enabledMcpjsonServers": ["docs"], "disabledMcpjsonServers": ["old-search"]}
    (site / ".claude/settings.local.json").write_text(json.dumps(local))

    def states() -> dict[str, Enabled]:
        scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
        return {
            i.name: i.enabled
            for i in scan.items
            if i.kind is ItemKind.MCP_SERVER and i.scope is Scope.PROJECT
        }

    return home, site, states


def test_project_server_approvals_are_read_from_the_local_file(tmp_path, no_version):
    _, _, states = _approvals(tmp_path, no_version)
    assert states() == {"docs": Enabled.ON, "old-search": Enabled.OFF}


def test_the_project_settings_file_approves_too(tmp_path, no_version):
    _, site, states = _approvals(tmp_path, no_version, local={})
    (site / ".claude/settings.json").write_text(json.dumps({"enableAllProjectMcpServers": True}))
    assert states() == {"docs": Enabled.ON, "old-search": Enabled.ON}


def test_a_folder_not_trusted_takes_approval_only_from_user_settings(tmp_path, no_version):
    home, site, states = _approvals(tmp_path, no_version, trust=False)
    (site / ".claude/settings.json").write_text(json.dumps({"enableAllProjectMcpServers": True}))
    assert states() == {"docs": Enabled.UNKNOWN, "old-search": Enabled.OFF}
    user = json.loads((home / ".claude/settings.json").read_text())
    user["enabledMcpjsonServers"] = ["docs"]
    (home / ".claude/settings.json").write_text(json.dumps(user))
    assert states() == {"docs": Enabled.ON, "old-search": Enabled.OFF}


def test_a_rejection_in_any_file_wins(tmp_path, no_version):
    _, site, states = _approvals(tmp_path, no_version, trust=False, local={})
    (site / ".claude/settings.json").write_text(json.dumps({"disabledMcpjsonServers": ["docs"]}))
    assert states() == {"docs": Enabled.OFF, "old-search": Enabled.UNKNOWN}


def test_trust_from_a_folder_above_counts_only_in_a_git_repository(tmp_path, no_version):
    home, _, states = _approvals(tmp_path, no_version, trust=False)
    state = json.loads((home / ".claude.json").read_text())
    state["projects"][str(home / "work")] = {"hasTrustDialogAccepted": True}
    (home / ".claude.json").write_text(json.dumps(state))
    assert states()["docs"] is Enabled.UNKNOWN
    (home / "work/.git").mkdir()
    assert states()["docs"] is Enabled.ON


def test_an_unreadable_local_file_leaves_approval_unknown(tmp_path, no_version):
    _, site, states = _approvals(tmp_path, no_version, local={})
    (site / ".claude/settings.json").write_text(json.dumps({"disabledMcpjsonServers": ["docs"]}))
    local = site / ".claude/settings.local.json"
    local.write_text("{ not json")
    assert states() == {"docs": Enabled.OFF, "old-search": Enabled.UNKNOWN}


# Hooks with `if` on events that are not tool events never run.


def _hooks(tmp_path, no_version, user: dict, project: dict | None = None):
    home = make_home(tmp_path, FIXTURE)
    (home / ".claude/settings.json").write_text(json.dumps(user))
    if project is not None:
        (home / "work/website/.claude/settings.json").write_text(json.dumps(project))
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    return {i.name: i for i in scan.items if i.kind is ItemKind.HOOK}


def _group(*handlers: dict, matcher: str = "") -> list[dict]:
    return [{"matcher": matcher, "hooks": list(handlers)}]


def test_a_hook_with_if_on_a_non_tool_event_is_off(tmp_path, no_version):
    cmd = {"type": "command", "command": "x", "if": "Bash(git *)"}
    hooks = _hooks(
        tmp_path,
        no_version,
        {
            "hooks": {
                "Stop": _group(cmd, matcher="a"),
                "PreToolUse": _group(cmd, matcher="b"),
                "SessionStart": _group(cmd, {"type": "command", "command": "y"}, matcher="c"),
                "Notification": [{"matcher": "d"}],
            }
        },
    )
    assert hooks["Stop: a"].enabled is Enabled.OFF
    assert hooks["PreToolUse: b"].enabled is Enabled.ON
    assert hooks["SessionStart: c"].enabled is Enabled.ON  # one handler has no `if`
    assert hooks["Notification: d"].enabled is Enabled.ON  # no handlers


def test_a_dead_group_beside_a_live_one_of_the_same_matcher_is_not_off(tmp_path, no_version):
    # The two share one id, so they must agree: the hook does run.
    dead = {"type": "command", "command": "x", "if": "Bash(git *)"}
    groups = _group(dead) + _group({"type": "command", "command": "y"})
    home = make_home(tmp_path, FIXTURE)
    (home / ".claude/settings.json").write_text(json.dumps({"hooks": {"Stop": groups}}))
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    hooks = [i for i in scan.items if i.name == "Stop: *"]
    assert [i.enabled for i in hooks] == [Enabled.ON, Enabled.ON]


def test_disable_all_hooks_false_does_not_revive_a_dead_hook(tmp_path, no_version):
    cmd = {"type": "command", "command": "x", "if": "Bash(git *)"}
    user = {"hooks": {"Stop": _group(cmd, matcher="a"), "PreToolUse": _group(cmd, matcher="b")}}
    hooks = _hooks(tmp_path, no_version, {**user, "disableAllHooks": False})
    assert hooks["Stop: a"].enabled is Enabled.OFF
    assert hooks["PreToolUse: b"].enabled is Enabled.ON


def test_a_project_rule_does_not_say_a_dead_hook_is_on(tmp_path, no_version):
    cmd = {"type": "command", "command": "x", "if": "Bash(git *)"}
    user = {"disableAllHooks": True, "hooks": {"Stop": _group(cmd, matcher="a")}}
    user["hooks"]["PreToolUse"] = _group(cmd, matcher="b")
    home = make_home(tmp_path, FIXTURE)
    (home / ".claude/settings.json").write_text(json.dumps(user))
    (home / "work/website/.claude/settings.local.json").write_text(
        json.dumps({"disableAllHooks": False})
    )
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    hooks = {i.name: i for i in scan.items if i.kind is ItemKind.HOOK and i.project is None}
    assert hooks["Stop: a"].project_rules == ()
    assert len(hooks["PreToolUse: b"].project_rules) == 1


# A plugin enabled only in a project's shared settings waits for an install.


def _project_plugin(tmp_path, no_version, installs=None, user=None, local=None):
    home = make_home(tmp_path, FIXTURE)
    site = home / "work/website"
    (site / ".claude/settings.json").write_text(json.dumps({"enabledPlugins": {"ghost@m": True}}))
    if user is not None:
        (home / ".claude/settings.json").write_text(json.dumps({"enabledPlugins": user}))
    if local is not None:
        (site / ".claude/settings.local.json").write_text(json.dumps({"enabledPlugins": local}))
    if installs is not None:
        file = home / ".claude/plugins/installed_plugins.json"
        records = installs(site) if callable(installs) else installs
        file.write_text(json.dumps({"plugins": {"ghost@m": records}}))
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    found = [i for i in scan.items if i.name == "ghost@m" and i.scope is Scope.PROJECT]
    return home, site, found[0], ClaudeCodeAdapter(home, read_version=no_version)


def test_a_project_plugin_that_is_not_installed_is_unknown(tmp_path, no_version):
    _, _, item, adapter = _project_plugin(tmp_path, no_version)
    assert item.enabled is Enabled.UNKNOWN
    assert item.change_hint
    # The person can still turn it off and remove it.
    actions = adapter.item_actions(replace(item, actions=()))
    assert PLUGIN_DISABLE in actions and PLUGIN_REMOVE in actions


def test_a_user_install_counts_for_a_project_plugin(tmp_path, no_version):
    record = [{"scope": "user", "installPath": "/x"}]
    _, _, item, _ = _project_plugin(tmp_path, no_version, installs=record)
    assert item.enabled is Enabled.ON and item.change_hint is None


def test_an_install_for_another_project_does_not_count(tmp_path, no_version):
    record = [{"scope": "project", "projectPath": "/somewhere/else", "installPath": "/x"}]
    _, _, item, _ = _project_plugin(tmp_path, no_version, installs=record)
    assert item.enabled is Enabled.UNKNOWN


def test_an_install_for_this_project_counts(tmp_path, no_version):
    def record(site):
        return [{"scope": "project", "projectPath": str(site)}]

    _, _, item, _ = _project_plugin(tmp_path, no_version, installs=record)
    assert item.enabled is Enabled.ON


def test_user_or_local_settings_that_enable_it_make_it_on(tmp_path, no_version):
    _, _, item, _ = _project_plugin(tmp_path / "a", no_version, user={"ghost@m": True})
    assert item.enabled is Enabled.ON
    _, _, item, _ = _project_plugin(tmp_path / "b", no_version, local={"ghost@m": True})
    assert item.enabled is Enabled.ON
    _, _, item, _ = _project_plugin(tmp_path / "c", no_version, user={"ghost@m": False})
    assert item.enabled is Enabled.UNKNOWN


def test_a_plugin_with_no_install_of_its_own_is_not_called_not_installed(tmp_path, no_version):
    # A skills-folder plugin loads from the repository; it never has an install record.
    home = make_home(tmp_path, FIXTURE)
    settings = home / "work/website/.claude/settings.json"
    settings.write_text(json.dumps({"enabledPlugins": {"kit@skills-dir": True}}))
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    (item,) = [i for i in scan.items if i.name == "kit@skills-dir"]
    assert item.enabled is Enabled.ON and item.change_hint is None


def test_an_install_in_the_main_checkout_counts_in_a_worktree(tmp_path, no_version):
    main = tmp_path / "main"
    (main / ".git/worktrees/site").mkdir(parents=True)

    def record(site):
        (site / ".git").write_text(f"gitdir: {main}/.git/worktrees/site\n")
        return [{"scope": "project", "projectPath": str(main)}]

    _, _, item, _ = _project_plugin(tmp_path / "home-of-it", no_version, installs=record)
    assert item.enabled is Enabled.ON and item.change_hint is None


def test_an_unreadable_install_record_does_not_say_not_installed(tmp_path, no_version):
    home, _, _, adapter = _project_plugin(tmp_path, no_version)
    (home / ".claude/plugins/installed_plugins.json").write_text("{broken")
    items = [i for i in adapter.scan().items if i.name == "ghost@m"]
    assert [(i.enabled, i.change_hint) for i in items] == [(Enabled.UNKNOWN, None)]


def test_an_install_recorded_under_a_linked_project_path_counts(tmp_path, no_version):
    def record(site):
        link = tmp_path / "link"
        link.symlink_to(site)
        return [{"scope": "local", "projectPath": str(link)}]

    _, _, item, _ = _project_plugin(tmp_path / "home-of-it", no_version, installs=record)
    assert item.enabled is Enabled.ON


# A server the /mcp menu turned off in a project (`disabledMcpServers` in ~/.claude.json).


def _mcp_offs(tmp_path, no_version, names):
    home = make_home(tmp_path, FIXTURE)
    site = str(home / "work/website")
    state = json.loads((home / ".claude.json").read_text())
    state["projects"][site]["disabledMcpServers"] = names
    (home / ".claude.json").write_text(json.dumps(state))
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    return site, [i for i in scan.items if i.kind is ItemKind.MCP_SERVER]


def test_a_local_or_project_server_the_mcp_menu_turned_off_is_off(tmp_path, no_version):
    _, items = _mcp_offs(tmp_path, no_version, ["local-db", "docs"])
    state = {i.name: i.enabled for i in items if i.scope in (Scope.LOCAL, Scope.PROJECT)}
    assert state["local-db"] is Enabled.OFF
    assert state["docs"] is Enabled.OFF


def test_a_user_server_turned_off_in_a_project_has_a_rule_there(tmp_path, no_version):
    site, items = _mcp_offs(tmp_path, no_version, ["github"])
    user = next(i for i in items if i.name == "github" and i.scope is Scope.USER)
    assert user.enabled is Enabled.ON
    assert [(p, e) for p, e, *_ in user.project_rules] == [(site, Enabled.OFF)]


# The home folder is trusted for its own local file.


def test_the_home_folder_needs_no_trust_for_its_local_approvals(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    (home / ".mcp.json").write_text(json.dumps({"mcpServers": {"homesrv": {"command": "x"}}}))
    (home / ".claude/settings.local.json").write_text(
        json.dumps({"enabledMcpjsonServers": ["homesrv"]})
    )
    state = json.loads((home / ".claude.json").read_text())
    state["projects"][str(home)] = {"hasTrustDialogAccepted": False}
    (home / ".claude.json").write_text(json.dumps(state))
    scan = ClaudeCodeAdapter(home, read_version=no_version).scan()
    found = [i for i in scan.items if i.name == "homesrv"]
    assert [i.enabled for i in found] == [Enabled.ON]
