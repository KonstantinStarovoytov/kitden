"""The servers that marketplace plugins bring, listed and checked without the network."""

import json

import pytest
from starlette.testclient import TestClient

from kitden.demo import build_demo_home, demo_adapters, demo_build
from kitden.demo.sample import MARKET
from kitden.gateways import data_dir
from kitden.views.catalog import market_entry, market_servers
from kitden.web.app import create_app

NO_SSE = "{} uses a connection the Kitden gateway does not support yet."
BUNDLE = "{} comes as a bundle; Kitden can't run it yet."
CANNOT_FILL = "{} reads values Kitden can't fill in."
IN_FOLDER = "{} runs a file inside its plugin folder; Kitden can't run it from the gateway."


@pytest.fixture
def home(tmp_path):
    return build_demo_home(tmp_path, "medium")


def _read(home, held=()):
    inventory = demo_build(home)()
    adapters = {a.id: a for a in demo_adapters(home)}
    return inventory, adapters, market_servers(inventory, adapters, set(held))


def _offer(home, name, entry):
    """Make the demo marketplace offer one more plugin with a single server, `name`."""
    root = home / ".claude/plugins/marketplaces" / MARKET
    listed = root / ".claude-plugin/marketplace.json"
    data = json.loads(listed.read_text())
    data["plugins"].append({"name": "extra", "source": "./plugins/extra"})
    listed.write_text(json.dumps(data))
    folder = root / "plugins/extra"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".mcp.json").write_text(json.dumps({"mcpServers": {name: entry}}))


def _row(rows, name):
    return next(r for r in rows if r["name"] == name)


def test_market_servers_say_why_before_any_preview(home):
    _, _, rows = _read(home)
    db = _row(rows, "db-query")
    assert (db["kind"], db["refusal"]) == ("local", None)
    assert db["id"] == "db-tools@demo-market/db-query"
    assert (db["plugin"], db["marketplace"], db["held"]) == ("db-tools", MARKET, False)
    assert (_row(rows, "test-status")["kind"], _row(rows, "test-status")["refusal"]) == (
        "remote",
        None,
    )
    assert _row(rows, "pr-index")["refusal"] == IN_FOLDER.format("pr-index")
    assert all("tools" not in r and "runs" not in r and "url" not in r for r in rows)


def test_servers_are_sorted_by_marketplace_then_name_ignoring_case(home):
    _, _, rows = _read(home)
    keys = [(r["marketplace"], r["name"].lower()) for r in rows]
    assert keys == sorted(keys)


@pytest.mark.parametrize(
    ("entry", "why"),
    [
        ({"type": "sse", "url": "https://x.example.test/stream"}, NO_SSE),
        ({"url": "https://x.example.test/sse"}, NO_SSE),
        ({"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/server.js"]}, CANNOT_FILL),
        (
            {
                "type": "http",
                "url": "https://x.example.test/mcp",
                "headers": {"Authorization": "Bearer ${TOKEN}"},
            },
            CANNOT_FILL,
        ),
        ({"command": "./bin/server"}, IN_FOLDER),
        ({"command": "npx", "args": ["x.mcpb"]}, BUNDLE),
    ],
)
def test_entries_the_gateway_cannot_run_are_refused(home, entry, why):
    _offer(home, "odd", entry)
    _, _, rows = _read(home)
    assert _row(rows, "odd")["refusal"] == why.format("odd")


def test_a_name_a_client_has_offers_move_instead(home):
    inventory, _, _ = _read(home)
    taken = next(
        i.name for i in inventory.items if i.kind.value == "mcp_server" and not i.via_gateway
    )
    _offer(home, taken, {"command": "uvx", "args": ["x"]})
    _, _, rows = _read(home)
    refusal = _row(rows, taken)["refusal"]
    assert refusal.endswith(f"has {taken} already. Move it into the gateway instead.")


def test_a_held_name_is_in_the_gateway_already(home):
    _, _, rows = _read(home, held={"db-query"})
    db = _row(rows, "db-query")
    assert db["held"] is True
    assert db["refusal"] == "db-query is in the gateway already."


def test_market_entry_reads_the_raw_entry_and_refuses_a_gone_one(home):
    _, adapters, _ = _read(home)
    plugin, entry = market_entry(adapters, "db-tools@demo-market/db-query")
    assert plugin == "db-tools@demo-market"
    assert entry == {"command": "uvx", "args": ["mcp-db-query"]}
    with pytest.raises(ValueError, match="This server is no longer offered."):
        market_entry(adapters, "db-tools@demo-market/gone")


def test_the_route_lists_the_servers_and_marks_a_held_one(home):
    settings = data_dir(home) / "gateway.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"servers": {"db-query": {"command": "uvx"}}}))
    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True)
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as page:
        assert page.get("/api/market-servers").status_code == 401
        page.get("/?token=tok")
        rows = page.get("/api/market-servers").json()["servers"]
    assert _row(rows, "db-query")["held"] is True
    assert _row(rows, "test-status")["refusal"] is None
