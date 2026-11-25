import os
from pathlib import Path

from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.clients.cursor import INSTALLED_PREFIX, MAX_SKILL_DEPTH, REACTIVE_KEY, CursorAdapter
from kitden.model import ItemKind, Scope, SourceKind, UnknownReason
from tests.conftest import (
    all_text,
    cursor_db,
    cursor_state_rows,
    make_home,
    rows,
    write_cursor_fixture_state,
    write_cursor_state,
)

FIXTURE = "cursor/3.21.16"

# Spike S1: Cursor has no plugin on/off switch, so an installed plugin is on.
OWN = {
    ("cursor", "mcp_server", "Neon", "user", "on", None),
    ("cursor", "mcp_server", "n8n-mcp", "user", "on", None),
    ("cursor", "mcp_server", "site-db", "project", "on", "work/site"),
    ("cursor", "skill", "docker-expert", "user", "on", None),
    ("cursor", "plugin", "superpowers@cursor-public", "user", "on", None),
    ("cursor", "plugin", "plugin 4800 (name not stored locally)", "user", "on", None),
    ("cursor", "plugin", "langfuse@cursor-public", "project", "on", "work/site"),
    ("cursor", "marketplace", "team-mkt", "user", "on", None),
    ("cursor", "hook", "afterFileEdit", "user", "on", None),
    ("cursor", "instructions", "style", "project", "on", "work/site"),
    ("cursor", "instructions", ".cursorrules", "project", "on", "work/site"),
    ("cursor", "instructions", "AGENTS.md", "project", "on", "work/site"),
}
CROSS_LOADED = {
    ("cursor", "skill", "brandkit", "user", "on", None),
    ("cursor", "skill", "langfuse", "user", "on", None),
    ("cursor", "plugin", "superpowers@claude-plugins-official", "user", "on", None),
    ("cursor", "hook", "PreToolUse: Bash", "user", "on", None),
}


def _scan(tmp_path, no_version, extra_rows=None):
    home = make_home(tmp_path, FIXTURE)
    write_cursor_fixture_state(home, extra_rows)
    return home, CursorAdapter(home, read_version=no_version).scan()


def _plugins(scan, home):
    return {r[2:] for r in rows(scan.items, home) if r[1] == "plugin" and "@claude" not in r[2]}


def test_user_installs_come_from_the_no_workspace_row_not_stale_project_copies(
    tmp_path, no_version
):
    # Project rows repeat the user's plugins as they were when Cursor last opened the
    # project. Plugin 648 was removed for the user since then, so it must not show.
    home, scan = _scan(tmp_path, no_version)
    assert not any("648" in r[0] for r in _plugins(scan, home))
    user_source = next(i.source for i in scan.items if i.name == "superpowers@cursor-public")
    assert user_source.key_path == INSTALLED_PREFIX + "123|no-workspace"
    assert user_source.unknown_reason is UnknownReason.NOT_DOCUMENTED


def test_project_installs_may_be_stale(tmp_path, no_version):
    _, scan = _scan(tmp_path, no_version)
    source = next(i.source for i in scan.items if i.name == "langfuse@cursor-public")
    assert source.unknown_reason is UnknownReason.MAY_BE_STALE


def test_user_installs_fall_back_to_project_rows_without_a_no_workspace_row(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    write_cursor_fixture_state(home)
    (cursor_db(home)).unlink()
    state = cursor_state_rows(home)
    write_cursor_state(home, {k: v for k, v in state.items() if "no-workspace" not in k})
    scan = CursorAdapter(home, read_version=no_version).scan()
    assert {r for r in _plugins(scan, home) if r[1] == "user"} == {
        ("plugin 648 (name not stored locally)", "user", "on", None),
        ("superpowers@cursor-public", "user", "on", None),
        ("plugin 4800 (name not stored locally)", "user", "on", None),
    }


def test_project_installs_in_a_multi_folder_window_go_to_folders_without_their_own_row(
    tmp_path, no_version
):
    site = f"file://{tmp_path}/home/work/site"
    other = f"file://{tmp_path}/home/work/other"
    home, scan = _scan(
        tmp_path,
        no_version,
        {INSTALLED_PREFIX + f"123|{site},{other}": [{"id": "739", "sources": ["project"]}]},
    )
    assert {r for r in _plugins(scan, home) if "739" in r[0]} == {
        ("plugin 739 (name not stored locally)", "project", "on", "work/other")
    }


def test_multi_folder_window_does_not_spread_a_plugin_installed_in_one_of_its_folders(
    tmp_path, no_version
):
    # langfuse (738) is installed in work/site; a window with work/site and work/other shows it.
    site = f"file://{tmp_path}/home/work/site"
    other = f"file://{tmp_path}/home/work/other"
    home, scan = _scan(
        tmp_path,
        no_version,
        {INSTALLED_PREFIX + f"123|{site},{other}": [{"id": "738", "sources": ["project"]}]},
    )
    assert {r for r in _plugins(scan, home) if r[0] == "langfuse@cursor-public"} == {
        ("langfuse@cursor-public", "project", "on", "work/site")
    }


def test_scan_includes_items_cursor_reads_from_other_clients(tmp_path, no_version):
    home, scan = _scan(tmp_path, no_version)
    assert rows(scan.items, home) == OWN | CROSS_LOADED
    assert scan.problems == []


def test_cross_loaded_items_name_the_client_that_owns_them(tmp_path, no_version):
    _home, scan = _scan(tmp_path, no_version)
    owners = {
        i.name: (i.source.kind, i.source.owner_client)
        for i in scan.items
        if i.name in {"brandkit", "langfuse", "docker-expert"}
    }
    assert owners == {
        "brandkit": (SourceKind.OTHER_CLIENT_FOLDER, "claude_code"),
        "langfuse": (SourceKind.OTHER_CLIENT_FOLDER, "codex"),
        "docker-expert": (SourceKind.FOLDER, "shared"),
    }


def test_turning_off_third_party_imports_removes_cross_loaded_items(tmp_path, no_version):
    home, scan = _scan(
        tmp_path, no_version, {REACTIVE_KEY: {"thirdPartyExtensibilityEnabled": False}}
    )
    assert rows(scan.items, home) == OWN


def cursor_adapter(path, flags, no_version):
    home = make_home(path, FIXTURE)
    write_cursor_fixture_state(home, {REACTIVE_KEY: flags})
    return CursorAdapter(home, read_version=no_version)


def test_cursor_imports_claude_plugins_only_with_both_switches_on(tmp_path, no_version):
    assert cursor_adapter(tmp_path / "a", {}, no_version).imports_claude_plugins() is True
    off = {"importPluginsFromClaudeOnBoot": False}
    assert cursor_adapter(tmp_path / "b", off, no_version).imports_claude_plugins() is False
    no_third = {"thirdPartyExtensibilityEnabled": False}
    assert cursor_adapter(tmp_path / "c", no_third, no_version).imports_claude_plugins() is False


def test_secret_rows_and_values_never_appear(tmp_path, no_version):
    _, scan = _scan(tmp_path, no_version)
    assert "SENTINEL_SECRET" not in all_text(scan)
    assert {i.name for i in scan.items if i.secret_present} == {"n8n-mcp"}


def test_broken_state_database_is_reported_and_cache_still_read(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    db = cursor_db(home)
    db.parent.mkdir(parents=True)
    db.write_bytes(b"this is not a database")
    scan = CursorAdapter(home, read_version=no_version).scan()
    assert [(p.path, p.unknown_reason) for p in scan.problems] == [
        (str(db), UnknownReason.UNRECOGNIZED_FORMAT)
    ]
    assert ("cursor", "plugin", "langfuse@cursor-public", "user", "unknown", None) in rows(
        scan.items, home
    )


def _state_problems(scan, home):
    return [(p.path, p.unknown_reason) for p in scan.problems if p.path == str(cursor_db(home))]


def test_switches_in_an_unknown_shape_are_reported_and_items_still_read(tmp_path, no_version):
    for odd in (
        ["thirdPartyExtensibilityEnabled"],
        "not json",
        {"importPluginsFromClaudeOnBoot": 0},
    ):
        home, scan = _scan(tmp_path / str(type(odd).__name__), no_version, {REACTIVE_KEY: odd})
        assert _state_problems(scan, home) == [
            (str(cursor_db(home)), UnknownReason.UNRECOGNIZED_FORMAT)
        ]
        assert rows(scan.items, home) >= OWN


def test_a_state_database_without_the_switches_is_read_with_the_defaults(tmp_path, no_version):
    home, scan = _scan(tmp_path, no_version)
    assert REACTIVE_KEY not in cursor_state_rows(home)
    assert _state_problems(scan, home) == []
    assert rows(scan.items, home) >= OWN | CROSS_LOADED


def _instructions(scan):
    return {
        (i.scope, i.name, dict(i.summary)["category"], i.project, i.source.path)
        for i in scan.items
        if i.kind is ItemKind.INSTRUCTIONS
    }


def test_scan_reads_rules_cursorrules_and_agents_md(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    site = home / "work/site"
    rules = site / ".cursor/rules"
    (rules / "frontend").mkdir()
    (rules / "frontend/components.mdc").write_text("x")
    (rules / "notes.md").write_text("x")  # a plain .md in the rules folder is not a rule
    (site / "AGENTS.md").write_text("x")
    (home / ".cursor/rules").mkdir()
    (home / ".cursor/rules/mine.mdc").write_text("x")
    write_cursor_fixture_state(home)
    scan = CursorAdapter(home, read_version=no_version).scan()
    p = str(site)
    assert _instructions(scan) == {
        (Scope.USER, "mine", "instructions", None, str(home / ".cursor/rules/mine.mdc")),
        (Scope.PROJECT, "style", "instructions", p, str(rules / "style.mdc")),
        (
            Scope.PROJECT,
            "frontend:components",
            "instructions",
            p,
            str(rules / "frontend/components.mdc"),
        ),
        (Scope.PROJECT, ".cursorrules", "instructions", p, str(site / ".cursorrules")),
        (Scope.PROJECT, "AGENTS.md", "instructions", p, str(site / "AGENTS.md")),
    }


def test_the_home_folder_as_a_cursor_project_skips_only_the_user_rules(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    (home / "AGENTS.md").write_text("x")
    (home / ".cursorrules").write_text("x")
    (home / ".cursor/rules").mkdir()
    (home / ".cursor/rules/mine.mdc").write_text("x")
    write_cursor_fixture_state(home, {INSTALLED_PREFIX + f"123|file://{home}": []})
    scan = CursorAdapter(home, read_version=no_version).scan()
    in_home = {i[1] for i in _instructions(scan) if i[3] == str(home)}
    assert in_home == {"AGENTS.md", ".cursorrules"}
    assert (Scope.USER, "mine") in {(i[0], i[1]) for i in _instructions(scan)}


def test_cursor_reads_only_the_project_root_claude_md(tmp_path, no_version):
    # checked 2026-11-25 (cursor.com/help/customization/rules): the root CLAUDE.md is read
    # like AGENTS.md; CLAUDE.local.md, .claude/CLAUDE.md and nested ones are not added.
    for third_party in (True, False):
        home = make_home(tmp_path / str(third_party), FIXTURE)
        site = home / "work/site"
        for name in ("CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md", "docs/CLAUDE.md"):
            (site / name).parent.mkdir(parents=True, exist_ok=True)
            (site / name).write_text("x")
        (home / ".claude").mkdir(exist_ok=True)
        (home / ".claude/CLAUDE.md").write_text("x")  # the user's own file: home-folder project
        write_cursor_fixture_state(
            home,
            {
                REACTIVE_KEY: {"thirdPartyExtensibilityEnabled": third_party},
                INSTALLED_PREFIX + f"123|file://{home}": [],
            },
        )
        scan = CursorAdapter(home, read_version=no_version).scan()
        claude = {i[4] for i in _instructions(scan) if "CLAUDE" in str(i[4])}
        assert claude == {str(site / "CLAUDE.md")}, third_party


def test_cursor_state_is_read_from_the_linux_config_folder(system, tmp_path, no_version):
    system("linux")
    home, scan = _scan(tmp_path, no_version)
    assert cursor_db(home) == home / ".config/Cursor/User/globalStorage/state.vscdb"
    assert cursor_db(home).exists()
    assert not (home / "Library").exists()
    assert rows(scan.items, home) >= OWN


def _write_skill(folder: Path, body: str = "# Skill\n") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    skill_md = folder / "SKILL.md"
    skill_md.write_text(body)
    return skill_md


def _skill_names(scan) -> set[str]:
    return {i.name for i in scan.items if i.kind is ItemKind.SKILL}


def test_skills_in_category_subfolders_are_listed_with_their_own_names(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    _write_skill(home / ".cursor/skills/shipping/land-it")
    _write_skill(home / ".cursor/skills/tdd")
    _write_skill(
        home / ".cursor/skills/release/cut-tag",
        "---\nname: release-tag\ndisable-model-invocation: true\n---\n",
    )
    _write_skill(home / ".agents/skills/ops/deploy")
    _write_skill(home / ".claude/skills/team/review")
    _write_skill(home / ".codex/skills/team/triage")
    _write_skill(home / "work/site/.cursor/skills/frontend/polish")
    write_cursor_fixture_state(home)

    adapter = CursorAdapter(home, read_version=no_version)
    scan = adapter.scan()
    names = _skill_names(scan)
    assert {"land-it", "tdd", "release-tag", "deploy", "review", "triage", "polish"} <= names
    assert not ({"shipping", "release", "ops", "team", "frontend"} & names)

    by_name = {i.name: i for i in scan.items if i.kind is ItemKind.SKILL}
    assert by_name["release-tag"].skill_state == "only-asked"
    assert (by_name["land-it"].source.owner_client, by_name["land-it"].source.kind) == (
        "cursor",
        SourceKind.FOLDER,
    )
    assert adapter.item_actions(by_name["land-it"]) == ("skill.remove",)
    assert (by_name["deploy"].source.owner_client, by_name["deploy"].source.kind) == (
        "shared",
        SourceKind.FOLDER,
    )
    assert (by_name["review"].source.owner_client, by_name["review"].source.kind) == (
        "claude_code",
        SourceKind.OTHER_CLIENT_FOLDER,
    )
    assert (by_name["triage"].source.owner_client, by_name["triage"].source.kind) == (
        "codex",
        SourceKind.OTHER_CLIENT_FOLDER,
    )
    assert (by_name["polish"].scope, by_name["polish"].project) == (
        Scope.PROJECT,
        str(home / "work/site"),
    )

    cursor_db(home).unlink()
    write_cursor_state(
        home, {**cursor_state_rows(home), REACTIVE_KEY: {"thirdPartyExtensibilityEnabled": False}}
    )
    without_third = _skill_names(CursorAdapter(home, read_version=no_version).scan())
    assert {"land-it", "tdd", "release-tag", "deploy", "polish"} <= without_third
    assert not ({"review", "triage"} & without_third)


def test_a_skill_folder_is_not_searched_for_more_skills_inside_it(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    _write_skill(home / ".cursor/skills/a")
    _write_skill(home / ".cursor/skills/a/b")
    write_cursor_fixture_state(home)

    names = _skill_names(CursorAdapter(home, read_version=no_version).scan())
    assert "a" in names and "b" not in names


def test_hidden_folders_and_skills_past_four_levels_are_skipped(tmp_path, no_version):
    assert MAX_SKILL_DEPTH == 4
    home = make_home(tmp_path, FIXTURE)
    _write_skill(home / ".cursor/skills/.trash/old")
    _write_skill(home / ".cursor/skills/shipping/.hidden/old-two")
    _write_skill(home / ".cursor/skills/l1/l2/l3/four-deep")
    _write_skill(home / ".cursor/skills/d1/d2/d3/d4/five-deep")
    write_cursor_fixture_state(home)

    names = _skill_names(CursorAdapter(home, read_version=no_version).scan())
    assert "four-deep" in names
    assert not ({"old", "old-two", "five-deep", "l1", "d1"} & names)


def test_symlinked_category_is_not_entered_and_symlinked_skill_keeps_its_link(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    elsewhere = tmp_path / "elsewhere"
    _write_skill(elsewhere / "cat/inside")
    top_md = _write_skill(elsewhere / "top-skill")
    real_md = _write_skill(elsewhere / "direct-skill")
    (home / ".cursor/skills").mkdir(parents=True, exist_ok=True)
    (home / ".cursor/skills/linked-cat").symlink_to(elsewhere / "cat")
    (home / ".cursor/skills/top-linked").symlink_to(elsewhere / "top-skill")
    (home / ".cursor/skills/shipping").mkdir()
    (home / ".cursor/skills/shipping/linked-skill").symlink_to(elsewhere / "direct-skill")
    (home / ".cursor/skills/shipping/loop").symlink_to(home / ".cursor/skills")
    write_cursor_fixture_state(home)

    adapter = CursorAdapter(home, read_version=no_version)
    scan = adapter.scan()
    names = _skill_names(scan)
    assert "inside" not in names
    top = next(i for i in scan.items if i.kind is ItemKind.SKILL and i.name == "top-linked")
    assert top.source.path == os.path.realpath(top_md)
    assert top.source.link_path == str(home / ".cursor/skills/top-linked")
    assert adapter.item_actions(top) == ()
    linked = next(i for i in scan.items if i.kind is ItemKind.SKILL and i.name == "linked-skill")
    assert linked.source.path == os.path.realpath(real_md)
    assert linked.source.link_path == str(home / ".cursor/skills/shipping/linked-skill")
    assert adapter.item_actions(linked) == ()


def test_nested_skill_folders_do_not_change_claude_code_skill_lists(tmp_path, no_version):
    home = make_home(tmp_path, "claude_code/2.1.283")
    before = _skill_names(ClaudeCodeAdapter(home, read_version=no_version).scan())

    _write_skill(home / ".claude/skills/shipping/land-it")
    _write_skill(home / "work/website/.claude/skills/shipping/web-land")

    assert _skill_names(ClaudeCodeAdapter(home, read_version=no_version).scan()) == before
