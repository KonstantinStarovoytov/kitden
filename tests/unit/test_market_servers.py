"""The servers that marketplace plugins bring, listed and checked without the network."""

import json
import time
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

import kitden.demo
from kitden.changes.actions import gateway_add_steps
from kitden.demo import build_demo_home, demo_adapters, demo_build
from kitden.demo.sample import MARKET
from kitden.gateways import data_dir
from kitden.local_gateway.settings import SETTINGS_FILE, TOOLS_FILE
from kitden.model import Change
from kitden.views.after import after_words
from kitden.views.catalog import market_entry, market_servers
from kitden.web.app import create_app

NO_SSE = "{} uses a connection the Kitden gateway does not support yet."
BUNDLE = "{} comes as a bundle; Kitden can't run it yet."
CANNOT_FILL = "{} reads values Kitden can't fill in."
IN_FOLDER = "{} runs a file inside its plugin folder; Kitden can't run it from the gateway."
ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
TEST_STATUS = "test-helper@demo-market/test-status"
DB_QUERY = "db-tools@demo-market/db-query"


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
        i.name
        for i in inventory.items
        if i.kind.value == "mcp_server" and not i.via_gateway and i.scope.value != "plugin"
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


def test_a_server_a_client_loads_from_a_plugin_is_refused_last(home):
    # Claude Code has pr-index from the pr-review plugin; another plugin offers one it could run.
    _offer(home, "pr-index", {"command": "uvx", "args": ["mcp-pr-index"]})
    _, _, rows = _read(home)
    extra = next(r for r in rows if r["id"] == f"extra@{MARKET}/pr-index")
    assert extra["refusal"] == "Claude Code loads pr-index from a plugin already."
    # The plugin's own entry still says why first: it runs a file in its folder.
    own = next(r for r in rows if r["id"] == f"pr-review@{MARKET}/pr-index")
    assert own["refusal"] == IN_FOLDER.format("pr-index")


# The gateway.add change -----------------------------------------------------------------


def _steps(home, server_id, sign_in=None):
    inventory, adapters, _ = _read(home)
    return gateway_add_steps(adapters, inventory, home, server_id, sign_in=sign_in)


def _never(url, headers):
    raise AssertionError("no sign-in check was expected")


def test_add_steps_write_only_the_gateway_settings(home):
    asked = []
    steps = _steps(home, TEST_STATUS, lambda url, headers: asked.append((url, headers)) or False)
    # One sign-in check, without headers: the entry has none.
    assert asked == [("https://status.example.test/mcp", {})]
    # The demo's settings have a PATH and Codex's kitden entry has its timeouts.
    assert [(s.client, s.name) for s in steps] == [("kitden", "test-status")]
    assert steps[0].edit.key == ("servers", "test-status")
    assert steps[0].edit.after == {"url": "https://status.example.test/mcp"}
    local = _steps(home, DB_QUERY, _never)
    assert local[0].edit.after == {"command": "uvx", "args": ["mcp-db-query"]}


def test_add_steps_put_secrets_in_the_keychain_and_map_streamable_http(home):
    entry = {
        "type": "streamable-http",
        "url": "https://x.example.test/mcp",
        "headers": {"Authorization": "Bearer DEMO_SECRET_X"},
    }
    _offer(home, "odd", entry)
    # A remote server with headers of its own gets no sign-in check.
    [step] = _steps(home, f"extra@{MARKET}/odd", _never)
    reference = {"keychain": "odd/Authorization"}
    assert step.edit.after == {
        "url": "https://x.example.test/mcp",
        "headers": {"Authorization": reference},
    }
    assert [(i.key, i.value) for i in step.keychain] == [("Authorization", "Bearer DEMO_SECRET_X")]


def test_add_steps_give_a_path_and_codex_timeouts_only_when_missing(home, monkeypatch):
    path = data_dir(home) / SETTINGS_FILE
    settings = json.loads(path.read_text())
    del settings["path"]
    path.write_text(json.dumps(settings))
    config = home / ".codex/config.toml"
    config.write_text(config.read_text().replace("tool_timeout_sec = 300\n", ""))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    steps = _steps(home, DB_QUERY)
    assert [(s.client, s.name) for s in steps] == [
        ("kitden", "db-query"),
        ("kitden", "PATH"),
        ("codex", "kitden"),
    ]
    assert steps[1].edit.after == "/usr/bin:/bin"
    assert steps[2].edit.key[-1] == "tool_timeout_sec"


def test_add_steps_refuse_what_the_list_refuses(home):
    with pytest.raises(ValueError, match=IN_FOLDER.format("pr-index")):
        _steps(home, f"pr-review@{MARKET}/pr-index", _never)
    with pytest.raises(ValueError, match="This server is no longer offered."):
        _steps(home, f"db-tools@{MARKET}/gone", _never)


@contextmanager
def _page(home):
    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        yield page


def _preview(page, server_id):
    body = {"action": "gateway.add", "targets": [], "params": {"server": server_id}}
    return page.post("/api/changes/preview", json=body, headers=POST)


def _verb(page, change_id, verb):
    return page.post(f"/api/changes/{change_id}/{verb}", headers=POST)


def _client_files(home):
    """Every file in the home but Kitden's own folder, by path."""
    own = data_dir(home)
    return {
        p: p.read_bytes()
        for p in sorted(home.rglob("*"))
        if p.is_file() and not p.is_relative_to(own)
    }


def test_adding_a_marketplace_server_to_the_gateway_and_undo(home):
    settings = data_dir(home) / SETTINGS_FILE
    before = settings.read_bytes()
    with _page(home) as page:
        answer = _preview(page, TEST_STATUS)
        assert answer.status_code == 200, answer.text
        change = answer.json()
        assert [(s["client"], s["name"]) for s in change["steps"]] == [("kitden", "test-status")]
        gw = {"state": "gw", "word": "Via gateway"}
        assert change["after"] == [{"client": c, **gw} for c in ("claude_code", "codex")]
        applied = _verb(page, change["id"], "apply")
        assert applied.status_code == 200, applied.text
        assert applied.json()["state"] == "verified"
        held = json.loads(settings.read_text())["servers"]["test-status"]
        assert held == {"url": "https://status.example.test/mcp"}
        rows = page.get("/api/market-servers").json()["servers"]
        assert _row(rows, "test-status")["held"] is True
        # Its tools are read after Apply, as after a move.
        tools = data_dir(home) / TOOLS_FILE
        end = time.monotonic() + 5
        while "test-status" not in json.loads(tools.read_text()):
            assert time.monotonic() < end, "the added server's tools were not read"
            time.sleep(0.05)
        undone = _verb(page, change["id"], "undo")
        assert undone.status_code == 200 and undone.json()["state"] == "undone"
    assert settings.read_bytes() == before


def test_add_changes_no_client_file(home):
    before = _client_files(home)
    with _page(home) as page:
        change = _preview(page, DB_QUERY).json()
        assert _verb(page, change["id"], "apply").json()["state"] == "verified"
    assert _client_files(home) == before


def test_codex_gets_only_the_timeouts_its_kitden_entry_lacks(home):
    config = home / ".codex/config.toml"
    config.write_text(config.read_text().replace("tool_timeout_sec = 300\n", ""))
    before = _client_files(home)
    with _page(home) as page:
        change = _preview(page, DB_QUERY).json()
        assert _verb(page, change["id"], "apply").json()["state"] == "verified"
    after = _client_files(home)
    assert "tool_timeout_sec = 300" in config.read_text()
    assert {p for p in after if after[p] != before.get(p)} == {config}


def _refused(home, server_id, words):
    settings = data_dir(home) / SETTINGS_FILE
    before = settings.read_bytes()
    with _page(home) as page:
        log = page.get("/api/changes").json()
        answer = _preview(page, server_id)
        assert answer.status_code == 422
        assert answer.json() == {"detail": words}
        assert page.get("/api/changes").json() == log
    assert settings.read_bytes() == before


def test_an_oauth_server_is_refused_at_preview_and_nothing_is_written(home, monkeypatch):
    monkeypatch.setattr(kitden.demo, "no_sign_in", lambda url, headers: True)
    _refused(home, TEST_STATUS, "test-status signs in with OAuth; Kitden can't add it yet.")


def test_an_unreachable_server_is_refused(home, monkeypatch):
    def no_answer(url, headers):
        raise OSError("no answer")

    monkeypatch.setattr(kitden.demo, "no_sign_in", no_answer)
    _refused(home, TEST_STATUS, "Kitden could not reach test-status.")


def test_an_add_with_no_client_on_the_gateway_says_so(home):
    [step] = _steps(home, TEST_STATUS, lambda url, headers: False)
    nobody = SimpleNamespace(clients=[], items=[])
    words = after_words(Change(action="gateway.add", steps=[step]), nobody, home=home)
    assert words == [{"note": "No client uses the Kitden gateway yet."}]
