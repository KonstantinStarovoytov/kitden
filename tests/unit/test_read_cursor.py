from kitden.clients.cursor import INSTALLED_PREFIX, REACTIVE_KEY, CursorAdapter
from kitden.model import ItemKind, Scope, SourceKind, UnknownReason
from tests.conftest import (
    CURSOR_DB,
    all_text,
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
    (home / CURSOR_DB).unlink()
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
    home, scan = _scan(tmp_path, no_version)
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
    db = home / CURSOR_DB
    db.parent.mkdir(parents=True)
    db.write_bytes(b"this is not a database")
    scan = CursorAdapter(home, read_version=no_version).scan()
    assert [(p.path, p.unknown_reason) for p in scan.problems] == [
        (str(db), UnknownReason.UNRECOGNIZED_FORMAT)
    ]
    assert ("cursor", "plugin", "langfuse@cursor-public", "user", "unknown", None) in rows(
        scan.items, home
    )


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
