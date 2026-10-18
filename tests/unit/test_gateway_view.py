"""Gateway page model: connections and what goes around it (redesign plan, Task 3)."""

import pytest

import kitden.clients.base as base
from kitden.model import Client, ClientStatus, Gateway, Item, ItemKind, Scope, Source, SourceKind
from kitden.views.findings import mark_gateways
from kitden.views.gateway_view import gateway_view
from kitden.views.inventory import Inventory, build_inventory
from tests.conftest import make_home, write_cursor_fixture_state


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return home


def row(groups, group, name):
    return next((r for r in groups[group] if r["name"] == name), None)


def test_gateway_groups_have_one_row_per_server(home):
    groups = gateway_view(build_inventory(home), [], None)["groups"]
    neon = row(groups, "move", "Neon")
    assert neon["clients"] == ["cursor"]
    assert len(neon["items"]) == 1  # the one direct entry that can be removed
    assert row(groups, "local", "n8n-mcp")["clients"] == ["cursor"]
    assert all(r["name"] != "aseprite" for g in groups.values() for r in g)  # turned off


def test_kitdens_own_server_is_not_listed(home):
    from kitden.changes import toml_edit

    config = home / ".codex/config.toml"
    mine = {"command": "/opt/kitden/bin/kitden", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "kitden"), mine))
    groups = gateway_view(build_inventory(home), [], None)["groups"]
    assert all(r["name"] != "kitden" for g in groups.values() for r in g)


def test_a_server_in_two_clients_is_one_row_with_both_marks():
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

    clients = [
        Client(id=c, display_name=c, status=ClientStatus.FOUND) for c in ("claude_code", "codex")
    ]
    inventory = Inventory(clients=clients, items=[direct("claude_code"), direct("codex")])
    groups = gateway_view(inventory, [], None)["groups"]
    assert len(groups["move"]) == 1
    github = groups["move"][0]
    assert github["clients"] == ["claude_code", "codex"]
    assert len(github["items"]) == 2


def test_connections_list_gateway_entries_per_client(home):
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp", ui_url="https://console.neon.tech")
    mark_gateways(inventory, [gateway])
    data = gateway_view(inventory, [gateway], None)
    assert data["connections"] == {"claude_code": [], "codex": ["neon"], "cursor": ["Neon"]}
    assert data["gateways"][0]["ui_url"] == "https://console.neon.tech"
    assert data["used"] == [gateway.id]
    assert row(data["groups"], "move", "Neon") is None
