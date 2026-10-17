from agentsetup.model import (
    Client,
    ClientStatus,
    Enabled,
    Item,
    ItemKind,
    Scope,
    Source,
    SourceKind,
)
from agentsetup.views.findings import find_findings
from agentsetup.views.inventory import Inventory


def item(
    client,
    kind,
    name,
    path,
    owner=None,
    scope=Scope.USER,
    project=None,
    enabled=Enabled.ON,
    source_kind=SourceKind.FILE,
):
    source = Source(kind=source_kind, path=path, owner_client=owner or client)
    return Item(
        client=client,
        kind=kind,
        name=name,
        source=source,
        scope=scope,
        project=project,
        enabled=enabled,
    )


def summary(findings):
    return {(str(f.type), str(f.severity), tuple(sorted(f.names))) for f in findings}


def test_same_skill_loaded_twice_in_one_client_is_a_warning():
    a = item("codex", ItemKind.SKILL, "docker-expert", "/h/.agents/skills/docker-expert/SKILL.md")
    b = item("codex", ItemKind.SKILL, "docker-expert", "/h/.codex/skills/docker-expert/SKILL.md")
    (finding,) = find_findings(Inventory(items=[a, b]))
    assert summary([finding]) == {
        ("duplicate_in_client", "warning", ("docker-expert", "docker-expert"))
    }
    assert "/h/.agents/skills/docker-expert/SKILL.md" in finding.explanation
    assert "/h/.codex/skills/docker-expert/SKILL.md" in finding.explanation


def test_same_plugin_from_two_sources_loads_twice():
    own = item("cursor", ItemKind.PLUGIN, "superpowers@cursor-public", "/db")
    imported = item(
        "cursor",
        ItemKind.PLUGIN,
        "superpowers@claude-plugins-official",
        "/h/.claude/plugins/installed_plugins.json",
        owner="claude_code",
        source_kind=SourceKind.OTHER_CLIENT_FOLDER,
    )
    found = summary(find_findings(Inventory(items=[own, imported])))
    assert (
        "duplicate_in_client",
        "warning",
        ("superpowers@claude-plugins-official", "superpowers@cursor-public"),
    ) in found


def test_item_read_from_another_clients_folder_is_cross_loaded():
    skill = item(
        "cursor",
        ItemKind.SKILL,
        "brandkit",
        "/h/.claude/skills/brandkit/SKILL.md",
        owner="claude_code",
        source_kind=SourceKind.OTHER_CLIENT_FOLDER,
    )
    (finding,) = find_findings(Inventory(items=[skill]))
    assert summary([finding]) == {("cross_loaded", "info", ("brandkit",))}
    assert "/h/.claude/skills/brandkit/SKILL.md" in finding.explanation
    assert "claude_code" in finding.explanation


def test_shared_agents_folder_is_not_cross_loading():
    skill = item(
        "cursor",
        ItemKind.SKILL,
        "docker-expert",
        "/h/.agents/skills/x/SKILL.md",
        owner="shared",
        source_kind=SourceKind.FOLDER,
    )
    assert find_findings(Inventory(items=[skill])) == []


def test_same_server_set_up_in_two_clients_is_information():
    a = item("codex", ItemKind.MCP_SERVER, "Neon", "/h/.codex/config.toml")
    b = item("cursor", ItemKind.MCP_SERVER, "Neon", "/h/.cursor/mcp.json")
    assert summary(find_findings(Inventory(items=[a, b]))) == {
        ("same_in_other_clients", "info", ("Neon", "Neon"))
    }


def test_project_definition_overriding_user_definition_is_reported():
    user = item("claude_code", ItemKind.MCP_SERVER, "docs", "/h/.claude.json")
    project = item(
        "claude_code",
        ItemKind.MCP_SERVER,
        "docs",
        "/p/.mcp.json",
        scope=Scope.PROJECT,
        project="/p",
    )
    found = summary(find_findings(Inventory(items=[user, project]), project="/p"))
    assert found == {("scope_override", "info", ("docs", "docs"))}


def test_unknown_states_are_grouped_per_client():
    a = item("cursor", ItemKind.PLUGIN, "a@m", "/db", enabled=Enabled.UNKNOWN)
    b = item("cursor", ItemKind.PLUGIN, "b@m", "/db", enabled=Enabled.UNKNOWN)
    assert summary(find_findings(Inventory(items=[a, b]))) == {
        ("unknown_state", "info", ("a@m", "b@m"))
    }


def test_unsupported_client_version_is_a_warning():
    old = Client(
        id="codex",
        display_name="Codex",
        status=ClientStatus.FOUND,
        version="0.100.0",
        version_supported=False,
    )
    skill = item("codex", ItemKind.SKILL, "x", "/h/.agents/skills/x/SKILL.md")
    found = summary(find_findings(Inventory(clients=[old], items=[skill])))
    assert found == {("version_unsupported", "warning", ("x",))}


def test_nothing_to_report_gives_no_findings():
    skill = item("codex", ItemKind.SKILL, "x", "/h/.agents/skills/x/SKILL.md")
    assert find_findings(Inventory(items=[skill])) == []


def test_desktop_config_overriding_claude_code_is_reported_once():
    code = item("claude_code", ItemKind.MCP_SERVER, "github", "/h/.claude.json")
    desktop = item(
        "claude_desktop_code_tab", ItemKind.MCP_SERVER, "github", "/h/claude_desktop_config.json"
    )
    found = summary(find_findings(Inventory(items=[code, desktop])))
    assert found == {("scope_override", "info", ("github", "github"))}
