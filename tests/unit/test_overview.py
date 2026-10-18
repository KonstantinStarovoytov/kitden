"""Overview: what needs attention, in plain words (redesign plan, Task 3)."""

from dataclasses import replace

import pytest

import kitden.clients.base as base
from kitden.model import Gateway, _hash
from kitden.views.findings import mark_gateways
from kitden.views.inventory import build_inventory
from kitden.views.overview import overview
from tests.conftest import CURSOR_DB, make_home, write_cursor_fixture_state


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


@pytest.fixture
def home(tmp_path):
    # Cursor first: its fixture also has .claude files, and the Claude Code ones must win.
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return home


def test_headline_counts_attention(home):
    data = overview(build_inventory(home), [], None)
    assert data["headline"] == "2 things need attention"
    assert [a["title"] for a in data["attention"]] == [
        "docker-expert loads twice in Codex and Cursor",
        "superpowers loads twice in Cursor",
    ]
    assert data["notes"] == 14  # 8 info findings + 6 direct MCP servers (no gateway yet)


def test_duplicate_card_is_one_sentence_and_opens_the_item(home):
    data = overview(build_inventory(home), [], None)
    card = next(a for a in data["attention"] if a["title"].startswith("superpowers"))
    assert card["text"] == "Two copies of one plugin load; keep one."
    assert card["action"] == "Keep one…"
    assert card["target"] == {
        "view": "map",
        "kind": "plugin",
        "row": _hash("plugin", "superpowers"),
    }
    skill = next(a for a in data["attention"] if a["title"].startswith("docker-expert"))
    assert skill["text"] == "Two copies of one skill load; keep one."


def test_no_card_shows_a_file_path(home, tmp_path):
    db = home / CURSOR_DB
    db.write_bytes(b"this is not a database")
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp")
    mark_gateways(inventory, [gateway])
    for card in overview(inventory, [gateway], None)["attention"]:
        assert "/" not in card["title"] + card["text"], card


def test_unreadable_file_becomes_an_attention_card(tmp_path):
    home = make_home(tmp_path, "cursor/3.21.16")
    db = home / CURSOR_DB
    db.parent.mkdir(parents=True)
    db.write_bytes(b"this is not a database")
    first = overview(build_inventory(home), [], None)["attention"][0]
    assert first["title"] == "Could not read state.vscdb"
    assert first["text"] == (
        "The file format is not recognized, so items from Cursor may be missing or wrong."
    )


def test_untested_version_is_an_attention_card(home, monkeypatch):
    monkeypatch.setattr(
        base, "read_command_version", lambda client: "2.0.0" if client == "claude_code" else None
    )
    first = overview(build_inventory(home), [], None)["attention"][0]
    assert first["title"] == "Claude Code 2.0.0 is not tested"
    assert first["text"] == "Tested from 2.1.283, so some items may be missing or wrong."


def test_all_clear_headline(tmp_path):
    empty = tmp_path / "empty-home"
    empty.mkdir()
    assert overview(build_inventory(empty), [], None)["headline"] == "All clear"


def test_gateway_card_only_with_a_registered_gateway(home):
    inventory = build_inventory(home)
    data = overview(inventory, [], None)
    assert data["gateway"] is None
    assert not any("gateway" in a["title"] for a in data["attention"])

    gateway = Gateway(url="https://mcp.neon.tech/mcp")
    mark_gateways(inventory, [gateway])
    data = overview(inventory, [gateway], None)
    card = data["attention"][-1]
    assert card["title"] == "4 MCP servers are not connected to the gateway"
    assert card["text"] == "2 can move into the gateway, 2 must stay on this Mac."
    assert card["action"] == "Review"
    assert card["target"] == {"view": "gateway"}
    assert data["gateway"] == {"name": "mcp.neon.tech"}


def test_kitdens_own_server_is_not_counted_as_not_connected(home):
    from kitden.changes import toml_edit

    config = home / ".codex/config.toml"
    mine = {"command": "/opt/kitden/bin/kitden", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "kitden"), mine))
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp")
    mark_gateways(inventory, [gateway])
    card = overview(inventory, [gateway], None)["attention"][-1]
    assert card["title"] == "4 MCP servers are not connected to the gateway"
    assert card["text"] == "2 can move into the gateway, 2 must stay on this Mac."


def test_servers_that_cannot_move_are_not_an_attention_card(home):
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp")
    mark_gateways(inventory, [gateway])
    # Mark every remote entry as served by the gateway: only local and plugin servers remain.
    for index, item in enumerate(inventory.items):
        if str(item.kind) == "mcp_server" and "command" not in dict(item.summary):
            inventory.items[index] = replace(item, via_gateway=gateway.id)
    data = overview(inventory, [gateway], None)
    assert not any("gateway" in a["title"] for a in data["attention"])


def test_old_kitden_entries_get_one_card_that_opens_agents(home):
    from kitden.changes import toml_edit

    config = home / ".codex/config.toml"
    old = {"command": "/Users/me/.local/bin/agentsetup", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), old))
    data = overview(build_inventory(home), [], None)
    card = next(a for a in data["attention"] if a["title"].startswith("Old Kitden"))
    assert card["title"] == "Old Kitden entry in Codex"
    assert card["text"] == (
        "The working version, agentsetup, made it; update it so Codex starts kitden."
    )
    assert card["action"] == "Update"
    assert card["target"] == {"view": "agents"}
    assert data["headline"] == "3 things need attention"
