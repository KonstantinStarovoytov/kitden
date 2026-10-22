import json

from kitden.gateways import data_dir
from kitden.local_gateway.settings import SETTINGS_FILE, load_settings
from kitden.local_gateway.views import gateway_items
from kitden.model import (
    Client,
    ClientStatus,
    Enabled,
    FindingType,
    Gateway,
    Item,
    ItemKind,
    Scope,
    Source,
    SourceKind,
)
from kitden.views.findings import find_bypasses, find_findings, mark_gateways
from kitden.views.inventory import Inventory, build_inventory
from tests.conftest import make_home, write_cursor_fixture_state


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


def mcp(client, name, url=None, command=None, scope=Scope.USER, source_kind=SourceKind.FILE):
    source = Source(kind=source_kind, path=f"/h/{client}.json", owner_client=client)
    return Item(
        client=client,
        kind=ItemKind.MCP_SERVER,
        name=name,
        source=source,
        scope=scope,
        summary=(("url", url),) if url else (("command", command),),
        actions=("mcp.remove_direct",) if source_kind is SourceKind.FILE else (),
    )


GATEWAY_URL = "http://127.0.0.1:12008/metamcp/dev/mcp"


def test_every_mcp_server_outside_the_gateway_is_flagged_with_its_kind():
    items = [
        mcp("codex", "neon", url="https://mcp.neon.tech/mcp"),
        mcp("cursor", "n8n", command="npx"),
        mcp("codex", "pw", command="npx", scope=Scope.PLUGIN, source_kind=SourceKind.PLUGIN),
    ]
    findings = {f.names[0]: f for f in find_bypasses(Inventory(items=items))}
    assert {str(f.type) for f in findings.values()} == {"bypasses_gateway"}
    assert "direct entry" in findings["neon"].explanation
    assert "local server" in findings["n8n"].explanation
    assert "plugin" in findings["pw"].explanation
    assert "/h/codex.json" in findings["neon"].explanation


def test_entries_that_point_to_a_registered_gateway_are_marked_and_not_flagged():
    gateway = Gateway(url=GATEWAY_URL)
    inventory = Inventory(
        items=[
            mcp("codex", "gateway", url=GATEWAY_URL + "/"),
            mcp("codex", "neon", url="https://mcp.neon.tech/mcp"),
        ]
    )
    mark_gateways(inventory, [gateway])
    marked = inventory.items[0]
    assert marked.via_gateway == gateway.id
    assert "mcp.remove_direct" not in marked.actions
    assert [f.names for f in find_bypasses(inventory)] == [("neon",)]


def test_a_user_entry_beside_the_plugin_server_is_reported():
    """Feature 003, FR-014: Kitden's own server twice in one client. The effective view ranks
    the user entry over the plugin one, so the pair shows as an override that names both."""
    user = item("claude_code", ItemKind.MCP_SERVER, "kitden", "/h/.claude.json")
    plugin = item(
        "claude_code",
        ItemKind.MCP_SERVER,
        "kitden",
        "/h/.claude/plugins/cache/kitden/kitden/0.1.0/.mcp.json",
        scope=Scope.PLUGIN,
        source_kind=SourceKind.PLUGIN,
    )
    found = summary(find_findings(Inventory(items=[user, plugin])))
    assert ("scope_override", "info", ("kitden", "kitden")) in found


KITDEN = {"command": "kitden", "args": ["mcp"]}


def real_home(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def add_entry(home, client, name, entry):
    path = home / (".claude.json" if client == "claude_code" else ".cursor/mcp.json")
    data = json.loads(path.read_text())
    data.setdefault("mcpServers", {})[name] = entry
    path.write_text(json.dumps(data, indent=2))


def hold_github(home):
    path = data_dir(home) / SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    settings = {"servers": {"github": {"command": "npx"}}, "rules": {"global": {}, "projects": {}}}
    path.write_text(json.dumps(settings))


def cross_client_names(home, with_held=False):
    inventory = build_inventory(home)
    if with_held:
        inventory.items.extend(gateway_items(inventory, load_settings(home), home))
    found = find_findings(inventory)
    return [f.names for f in found if f.type is FindingType.SAME_IN_OTHER_CLIENTS]


def test_kitden_entries_make_no_cross_client_note(tmp_path):
    home = real_home(tmp_path)
    for client in ("claude_code", "cursor"):
        add_entry(home, client, "kitden", KITDEN)
    names = cross_client_names(home)
    assert all("kitden" not in n for n in names)


def test_held_servers_make_no_cross_client_note(tmp_path):
    home = real_home(tmp_path)
    for client in ("claude_code", "cursor"):
        add_entry(home, client, "kitden", KITDEN)
    hold_github(home)
    names = cross_client_names(home, with_held=True)
    assert all("github" not in n for n in names)


def test_direct_entries_beside_a_held_server_keep_their_note(tmp_path):
    home = real_home(tmp_path)
    for client in ("claude_code", "cursor"):
        add_entry(home, client, "kitden", KITDEN)
    hold_github(home)
    add_entry(home, "claude_code", "github", {"command": "npx"})
    add_entry(home, "cursor", "github", {"command": "npx"})
    names = cross_client_names(home, with_held=True)
    assert any(n == ("github", "github") for n in names)


def test_instruction_files_in_two_clients_are_not_a_finding():
    codex = item("codex", ItemKind.INSTRUCTIONS, "AGENTS.md", "/h/.codex/AGENTS.md")
    cursor = item("cursor", ItemKind.INSTRUCTIONS, "AGENTS.md", "/h/p/AGENTS.md")
    rules = item("cursor", ItemKind.INSTRUCTIONS, "AGENTS.md", "/h/q/AGENTS.md")
    assert find_findings(Inventory(items=[codex, cursor, rules])) == []
