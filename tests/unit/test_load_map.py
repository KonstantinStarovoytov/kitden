"""Load map: items in rows, the three clients in columns (redesign plan, Task 1)."""

import pytest

import kitden.clients.base as base
from kitden.model import (
    Client,
    ClientStatus,
    Gateway,
    Item,
    ItemKind,
    Scope,
    Source,
    SourceKind,
)
from kitden.views.findings import mark_gateways
from kitden.views.inventory import Inventory, build_inventory
from kitden.views.load_map import COLUMNS, load_map, map_dict
from tests.conftest import make_home, write_cursor_fixture_state

EVIL = '<img src=x onerror="alert(1)">'


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


@pytest.fixture
def home(tmp_path):
    # Cursor first: its fixture also has .claude files, and the Claude Code ones must win.
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return home


def rows_by(rows, kind, name):
    return next(r for r in rows if (str(r.kind), r.name) == (kind, name))


def test_rows_group_by_kind_and_base_name(home):
    rows = load_map(build_inventory(home), None)
    superpowers = [r for r in rows if str(r.kind) == "plugin" and r.name == "superpowers"]
    assert len(superpowers) == 1
    assert superpowers[0].cells["codex"].state == "none"
    assert superpowers[0].cells["claude_code"].state == "on"
    assert set(superpowers[0].cells) == set(COLUMNS)


def test_cell_states_for_the_website_project(home):
    rows = load_map(build_inventory(home), str(home / "work/website"))
    cell = rows_by(rows, "plugin", "superpowers").cells["claude_code"]
    assert (cell.state, cell.where) == ("off", "this project")


def test_cursor_loading_a_plugin_twice_is_one_cell_with_count_2(home):
    row = rows_by(load_map(build_inventory(home), None), "plugin", "superpowers")
    assert row.cells["cursor"].count == 2
    assert row.cells["cursor"].where == "everywhere"  # Cursor's own copy comes first
    assert {
        "text": "Cursor loads it twice",
        "level": "warning",
        "client": "cursor",
        "fix": "Turn one copy off to keep the other.",
        "fix_action": "plugin.disable",
    } in row.flags


def test_a_duplicate_skill_names_the_fix_without_an_action(home):
    row = rows_by(load_map(build_inventory(home), None), "skill", "docker-expert")
    flag = next(f for f in row.flags if f["client"] == "codex")
    assert flag["text"] == "Codex loads it twice"
    assert flag["fix"] == "Remove one copy to keep the other."
    assert flag["fix_action"] is None


def test_cross_loaded_cells_say_via_which_client(home):
    row = rows_by(load_map(build_inventory(home), None), "skill", "brandkit")
    assert (row.cells["cursor"].state, row.cells["cursor"].where) == ("on", "via Claude Code")
    assert row.cells["claude_code"].where == "everywhere"


def test_gateway_entries_are_state_gw(home):
    inventory = build_inventory(home)
    mark_gateways(inventory, [Gateway(url="https://mcp.neon.tech/mcp")])
    rows = load_map(inventory, None, gateway_registered=True)
    assert rows_by(rows, "mcp_server", "Neon").cells["cursor"].state == "gw"
    assert {
        "text": "Around gateway",
        "level": "warning",
        "client": "codex",
        "fix": "Add it in the gateway, then remove this direct entry.",
        "fix_action": "mcp.remove_direct",
    } in rows_by(rows, "mcp_server", "langfuse-data").flags


def test_direct_entries_are_only_info_without_a_gateway(home):
    rows = load_map(build_inventory(home), None)
    assert {"text": "Direct", "level": "info"} in rows_by(rows, "mcp_server", "Neon").flags
    assert {"text": "Local server", "level": "info"} in rows_by(rows, "mcp_server", "n8n-mcp").flags


def test_desktop_items_show_in_the_claude_code_column(home):
    row = rows_by(load_map(build_inventory(home), None), "mcp_server", "metamcp-local")
    assert (row.cells["claude_code"].state, row.cells["claude_code"].where) == ("on", "Desktop app")


def test_not_installed_client_column_says_missing(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    rows = load_map(build_inventory(home), None)
    assert {r.cells["codex"].state for r in rows} == {"missing"}
    assert {r.cells["cursor"].state for r in rows} == {"missing"}
    data = map_dict(build_inventory(home), rows)
    assert [(c["id"], c["status"]) for c in data["columns"]] == [
        ("claude_code", "found"),
        ("codex", "not_found"),
        ("cursor", "not_found"),
    ]


def test_mcp_and_plugin_with_the_same_name_stay_separate():
    def item(client, kind, name):
        source = Source(kind=SourceKind.FILE, path=f"/h/{client}", owner_client=client)
        return Item(client=client, kind=kind, name=name, source=source, scope=Scope.USER)

    clients = [Client(id=c, display_name=c, status=ClientStatus.FOUND) for c in COLUMNS]
    inventory = Inventory(
        clients=clients,
        items=[
            item("claude_code", ItemKind.MCP_SERVER, "github"),
            item("codex", ItemKind.PLUGIN, "github@openai-curated-remote"),
        ],
    )
    keys = {(str(r.kind), r.name) for r in load_map(inventory, None)}
    assert keys == {("mcp_server", "github"), ("plugin", "github")}


def test_raw_names_are_returned_unchanged(home):
    skill = home / ".claude/skills/evil/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(f"---\nname: {EVIL}\ndescription: test\n---\n")
    data = map_dict(build_inventory(home), load_map(build_inventory(home), None))
    names = {r["name"] for r in data["rows"]}
    assert EVIL in names
    row = next(r for r in data["rows"] if r["name"] == EVIL)
    assert set(row["cells"]["claude_code"]) == {"state", "where", "items", "count"}


def test_project_only_items_are_not_rows_everywhere(home):
    everywhere = {r.name for r in load_map(build_inventory(home), None)}
    assert "site-db" not in everywhere
    site = {r.name for r in load_map(build_inventory(home), str(home / "work/site"))}
    assert "site-db" in site
