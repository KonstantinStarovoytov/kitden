from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.model import ClientStatus, Enabled, UnknownReason
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
    ("claude_desktop_code_tab", "mcp_server", "metamcp-local", "user", "on", None),
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
    bundled = home / "Library/Application Support/Claude/claude-code"
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
    (home / "Library/Application Support/Claude/claude_desktop_config.json").unlink()
    assert ClaudeCodeAdapter(home, read_version=no_version).extra_clients() == []


def test_detect_without_files_or_command_is_not_found(tmp_path, no_version):
    client = ClaudeCodeAdapter(tmp_path / "empty", read_version=no_version).detect()
    assert client.status is ClientStatus.NOT_FOUND


def test_the_desktop_tab_keeps_its_folder_version_in_a_scan(tmp_path):
    home = make_home(tmp_path, FIXTURE)
    (home / "Library/Application Support/Claude/claude-code/2.1.299").mkdir(parents=True)
    clients = {c.id: c for c in build_inventory(home).clients}
    assert clients["claude_desktop_code_tab"].version == "2.1.299"
    assert clients["claude_code"].version is None
