"""Gateway page model: connections and what goes around it (redesign plan, Task 3)."""

import pytest

import agentsetup.clients.base as base
from agentsetup.model import Gateway
from agentsetup.views.findings import mark_gateways
from agentsetup.views.gateway_view import gateway_view
from agentsetup.views.inventory import build_inventory
from tests.conftest import make_home, write_cursor_fixture_state


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return home


def entry(groups, group, client, name):
    return next((e for e in groups[group] if (e["client"], e["name"]) == (client, name)), None)


def test_gateway_groups(home):
    groups = gateway_view(build_inventory(home), [], None)["groups"]
    neon = entry(groups, "move", "cursor", "Neon")
    assert neon["actions"] == ["mcp.remove_direct"]
    assert neon["path"].endswith(".cursor/mcp.json")
    assert entry(groups, "local", "cursor", "n8n-mcp") is not None
    assert all(e["name"] != "aseprite" for g in groups.values() for e in g)  # turned off


def test_connections_list_gateway_entries_per_client(home):
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp", ui_url="https://console.neon.tech")
    mark_gateways(inventory, [gateway])
    data = gateway_view(inventory, [gateway], None)
    assert data["connections"] == {"claude_code": [], "codex": ["neon"], "cursor": ["Neon"]}
    assert data["gateways"][0]["ui_url"] == "https://console.neon.tech"
    assert entry(data["groups"], "move", "cursor", "Neon") is None
