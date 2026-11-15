"""Gateway page model: connections and what goes around it (redesign plan, Task 3)."""

from dataclasses import replace

import pytest

from kitden.model import Client, ClientStatus, Item, ItemKind, Scope, Source, SourceKind
from kitden.views.effective import DESKTOP
from kitden.views.gateway_view import gateway_view
from kitden.views.inventory import Inventory, build_inventory
from tests.conftest import make_home, write_cursor_fixture_state


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return home


def row(groups, group, name):
    return next((r for r in groups[group] if r["name"] == name), None)


def test_gateway_groups_have_one_row_per_server(home):
    groups = gateway_view(build_inventory(home), None)["groups"]
    neon = row(groups, "move", "Neon")
    assert neon["clients"] == ["cursor"]
    assert len(neon["items"]) == 1  # the one direct entry that can be removed
    assert row(groups, "local", "n8n-mcp")["clients"] == ["cursor"]
    assert all(r["name"] != "aseprite" for g in groups.values() for r in g)  # turned off
    # A dimmed second line says what the server is: its address or its command.
    assert neon["summary"] == "https://mcp.neon.tech/mcp"
    assert row(groups, "local", "n8n-mcp")["summary"].startswith("npx n8n-mcp")


def test_kitdens_own_server_is_not_listed(home):
    from kitden.changes import toml_edit

    config = home / ".codex/config.toml"
    mine = {"command": "/opt/kitden/bin/kitden", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "kitden"), mine))
    groups = gateway_view(build_inventory(home), None)["groups"]
    assert all(r["name"] != "kitden" for g in groups.values() for r in g)


def direct(client):
    source = Source(kind=SourceKind.FILE, path=f"/h/{client}.json", owner_client=client)
    return Item(
        client=client,
        kind=ItemKind.MCP_SERVER,
        name="github",
        source=source,
        scope=Scope.USER,
        summary=(("url", "https://api.githubcopilot.com/mcp/"),),
        actions=("mcp.remove_direct",),
    )


def found(*clients):
    return [Client(id=c, display_name=c, status=ClientStatus.FOUND) for c in clients]


def test_a_server_in_two_clients_is_one_row_with_both_marks():
    inventory = Inventory(
        clients=found("claude_code", "codex"), items=[direct("claude_code"), direct("codex")]
    )
    groups = gateway_view(inventory, None)["groups"]
    assert len(groups["move"]) == 1
    github = groups["move"][0]
    assert github["clients"] == ["claude_code", "codex"]
    assert len(github["items"]) == 2
    assert (github["columns"], github["override"], github["stays"]) == (
        ["claude_code", "codex"],
        False,
        None,
    )


def test_columns_follow_the_page_and_count_the_desktop_code_tab_as_claude_code():
    inventory = Inventory(
        clients=found("cursor", DESKTOP), items=[direct("cursor"), direct(DESKTOP)]
    )
    github = gateway_view(inventory, None)["groups"]["move"][0]
    assert github["clients"] == ["cursor", DESKTOP]
    assert github["columns"] == ["claude_code", "cursor"]


def test_each_column_names_the_entries_its_line_takes_out():
    # A bypass line's × removes that client's own entries; the Desktop Code tab's count as Claude
    # Code's, as its line does. An entry that cannot be removed is in none.
    stuck = replace(direct("codex"), actions=())
    inventory = Inventory(
        clients=found("claude_code", "cursor", "codex", DESKTOP),
        items=[direct("claude_code"), direct("cursor"), direct(DESKTOP), stuck],
    )
    github = gateway_view(inventory, None)["groups"]["move"][0]
    ids = {i.client: i.id for i in inventory.items}
    assert github["client_items"] == {
        "claude_code": [ids["claude_code"], ids[DESKTOP]],
        "cursor": [ids["cursor"]],
    }


def test_a_plugins_server_stays_with_the_plugin():
    item = replace(direct("codex"), scope=Scope.PLUGIN)
    inventory = Inventory(clients=found("codex"), items=[item])
    row = gateway_view(inventory, None)["groups"]["plugin"][0]
    assert row["stays"] == "github comes with a plugin; it stays with the plugin."
