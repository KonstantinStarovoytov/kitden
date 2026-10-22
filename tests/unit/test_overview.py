"""Overview: what needs attention, in plain words (redesign plan, Task 3)."""

import json
from dataclasses import replace

import pytest

from kitden.clients import version_cache
from kitden.model import FindingType, Gateway
from kitden.views.findings import find_findings, mark_gateways
from kitden.views.gateway_view import gateway_view
from kitden.views.inventory import build_inventory
from kitden.views.load_map import load_map, row_key
from kitden.views.overview import overview
from tests.conftest import CURSOR_DB, make_home, write_cursor_fixture_state


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
    assert (card["target"]["view"], card["target"]["kind"]) == ("map", "plugin")
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
        version_cache, "cached_version", lambda home, c: "2.0.0" if c == "claude_code" else None
    )
    first = overview(build_inventory(home), [], None)["attention"][0]
    assert first["title"] == "Claude Code 2.0.0 is not tested"
    assert first["text"] == "Tested from 2.1.283, so some items may be missing or wrong."


def test_all_clear_headline(tmp_path):
    empty = tmp_path / "empty-home"
    empty.mkdir()
    assert overview(build_inventory(empty), [], None)["headline"] == "All clear"


def _add_kitden_entry(home, relative):
    path = home / relative
    data = json.loads(path.read_text())
    data.setdefault("mcpServers", {})["kitden"] = {"command": "kitden", "args": ["mcp"]}
    path.write_text(json.dumps(data))


@pytest.fixture
def connected(home):
    """Claude Code and Cursor have the kitden entry; Codex does not."""
    _add_kitden_entry(home, ".claude.json")
    _add_kitden_entry(home, ".cursor/mcp.json")
    return home


def test_the_kitden_gateway_card_names_servers_and_clients(connected):
    held = [{"name": "github", "kind": "local", "state": "on", "differs": False}]
    data = overview(build_inventory(connected), [], None, held=held)
    assert data["gateway"] == {
        "kind": "kitden",
        "name": "Kitden gateway",
        "servers": 1,
        "clients": ["claude_code", "cursor"],
        "lacking": ["codex"],
        "problem": None,
    }
    assert data["suggestions"][0]["title"].endswith("can move into the Kitden gateway")


def test_a_turned_off_kitden_entry_is_not_connected_and_not_offered(connected):
    codex = connected / ".codex/config.toml"
    off = '\n[mcp_servers.kitden]\ncommand = "kitden"\nargs = ["mcp"]\nenabled = false\n'
    codex.write_text(codex.read_text() + off)
    held = [{"name": "github", "kind": "local", "state": "on", "differs": False}]
    data = overview(build_inventory(connected), [], None, held=held)
    assert data["gateway"]["clients"] == ["claude_code", "cursor"]


def test_without_held_servers_or_connected_clients_there_is_no_gateway(home):
    data = overview(build_inventory(home), [], None, held=[])
    assert data["gateway"] is None  # no client has the entry in the plain fixture
    assert data["suggestions"] == []


def test_overview_says_when_the_gateway_settings_are_unreadable(home):
    problem = "Kitden could not read the gateway settings."
    data = overview(build_inventory(home), [], None, held=[], problem=problem)
    assert data["gateway"]["problem"] == problem


def test_an_old_entry_is_not_connected_and_gets_no_set_up_button(connected):
    from kitden.changes import toml_edit

    config = connected / ".codex/config.toml"
    old = {"command": "/Users/me/.local/bin/agentsetup", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), old))
    data = overview(build_inventory(connected), [], None, held=[])
    assert "codex" not in data["gateway"]["clients"]
    assert "codex" not in data["gateway"]["lacking"]


def test_a_registered_gateway_still_gets_its_card_without_the_kitden_one(home):
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp")
    mark_gateways(inventory, [gateway])
    data = overview(inventory, [gateway], None, held=[])
    assert data["gateway"] == {"name": "mcp.neon.tech"}
    assert [s["title"] for s in data["suggestions"]] == ["2 MCP servers can move into the gateway"]


def test_direct_servers_are_a_suggestion_not_attention(home):
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp")
    mark_gateways(inventory, [gateway])
    data = overview(inventory, [gateway], None)
    moves = len(gateway_view(inventory, [gateway], None)["groups"]["move"])
    assert all("gateway" not in a["title"] for a in data["attention"])
    assert data["suggestions"] == [
        {
            "title": f"{moves} MCP servers can move into the gateway",
            "text": "They connect to each client directly now.",
            "action": "Review",
            "target": {"view": "gateway"},
        }
    ]
    assert data["headline"] == "2 things need attention"  # the two duplicates only


def test_a_server_in_two_clients_is_one_suggestion_row(home):
    from kitden.changes import toml_edit

    # github is already a direct entry in Claude Code; Codex gets one too.
    config = home / ".codex/config.toml"
    github = {"url": "https://api.githubcopilot.com/mcp/"}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "github"), github))
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp")
    mark_gateways(inventory, [gateway])
    # langfuse-data goes through the gateway, so only github is left to move.
    for index, item in enumerate(inventory.items):
        if item.name == "langfuse-data":
            inventory.items[index] = replace(item, via_gateway=gateway.id)
    [card] = overview(inventory, [gateway], None)["suggestions"]
    assert card["title"] == "1 MCP server can move into the gateway"
    assert card["text"] == "It connects to each client directly now."


def test_servers_that_cannot_move_are_not_a_suggestion(home):
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp")
    mark_gateways(inventory, [gateway])
    # Mark every remote entry as served by the gateway: only local and plugin servers remain.
    for index, item in enumerate(inventory.items):
        if str(item.kind) == "mcp_server" and "command" not in dict(item.summary):
            inventory.items[index] = replace(item, via_gateway=gateway.id)
    data = overview(inventory, [gateway], None)
    assert not any("gateway" in a["title"] for a in data["attention"])
    assert data["suggestions"] == []


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


def test_overview_duplicate_points_at_a_row_the_map_has(home):
    inventory = build_inventory(home)
    by_id = {i.id: i for i in inventory.items}
    twice = next(
        f
        for f in find_findings(inventory, None)
        if f.type is FindingType.DUPLICATE_IN_CLIENT and by_id[f.items[0]].name.startswith("superp")
    )
    card = next(
        a for a in overview(inventory, [], None)["attention"] if a["title"].startswith("superp")
    )
    assert card["target"]["row"] == row_key(by_id[twice.items[0]])
    assert card["target"]["row"] in {r.key for r in load_map(inventory, None)}
