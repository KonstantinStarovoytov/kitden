"""Overview: what needs attention, in plain words (redesign plan, Task 3)."""

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
    assert data["headline"] == "3 things need attention"
    assert [a["title"] for a in data["attention"]] == [
        "Codex loads docker-expert twice",
        "Cursor loads docker-expert twice",
        "Cursor loads superpowers twice",
    ]
    assert data["notes"] == 14  # 8 info findings + 6 direct MCP servers (no gateway yet)


def test_duplicate_card_says_where_from(home):
    data = overview(build_inventory(home), [], None)
    card = next(a for a in data["attention"] if a["title"] == "Cursor loads superpowers twice")
    assert card["action"] == "Show"
    assert card["target"] == {
        "view": "map",
        "kind": "plugin",
        "row": _hash("plugin", "superpowers"),
    }
    assert card["text"].startswith("From ") and "installed_plugins.json" in card["text"]


def test_unreadable_file_becomes_an_attention_card(tmp_path):
    home = make_home(tmp_path, "cursor/3.21.16")
    db = home / CURSOR_DB
    db.parent.mkdir(parents=True)
    db.write_bytes(b"this is not a database")
    first = overview(build_inventory(home), [], None)["attention"][0]
    assert first["title"] == "Could not read state.vscdb"
    assert "format is not recognized" in first["text"]


def test_untested_version_is_an_attention_card(home, monkeypatch):
    monkeypatch.setattr(
        base, "read_command_version", lambda client: "2.0.0" if client == "claude_code" else None
    )
    titles = [a["title"] for a in overview(build_inventory(home), [], None)["attention"]]
    assert titles[0] == "Claude Code 2.0.0 is not tested"


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
    assert card["title"].endswith("MCP servers go around your gateway")
    assert card["target"] == {"view": "gateway"}
    assert data["gateway"]["through"] == 2
    assert data["gateway"]["name"] == "mcp.neon.tech"


def test_old_kitden_entries_get_one_card_that_opens_agents(home):
    from kitden.changes import toml_edit

    config = home / ".codex/config.toml"
    old = {"command": "/Users/me/.local/bin/agentsetup", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), old))
    data = overview(build_inventory(home), [], None)
    card = next(a for a in data["attention"] if a["title"].startswith("Old Kitden"))
    assert card["title"] == "Old Kitden entry in Codex"
    assert card["action"] == "Update"
    assert card["target"] == {"view": "agents"}
    assert data["headline"] == "4 things need attention"
