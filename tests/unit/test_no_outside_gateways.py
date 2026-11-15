"""Kitden no longer works with outside gateways; only its own gateway stays. Their saved list
is deleted when Kitden starts, an entry that pointed at one is an ordinary server, and an old
change that wrote into one leaves the history."""

import json

from starlette.testclient import TestClient

from kitden import cli
from kitden.changes.backup import ChangeStore
from kitden.changes.engine import Engine
from kitden.gateways import data_dir
from kitden.views.changes_view import change_entries
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
SAVED = {"gateways": [{"url": "https://gw.example.com/mcp-connect/team", "auth": "oauth"}]}


def test_every_command_deletes_the_saved_gateways(tmp_path):
    folder = data_dir(tmp_path)
    folder.mkdir(parents=True)
    (folder / "settings.json").write_text(json.dumps(SAVED))
    cli.main(["scan", "--home", str(tmp_path)])
    assert not (folder / "settings.json").exists()


def test_no_saved_gateways_is_fine(tmp_path):
    cli.main(["scan", "--home", str(tmp_path)])
    assert not (data_dir(tmp_path) / "settings.json").exists()


def _old_gateway_change(home):
    """A change from an older Kitden that added a server to an outside gateway: its record and
    its log line, as that version wrote them."""
    store = ChangeStore(data_dir(home))
    change_id = "20261001T000000Z-outside"
    step = {
        "client": "gateway",
        "scope": "user",
        "name": "neon",
        "mechanism": "gateway_api",
        "command": None,
        "undo_command": None,
        "cwd": None,
        "restart_note": None,
        "login_note": None,
        "shared_file": False,
        "edit": None,
        "gateway": {
            "gateway_id": "abc",
            "url": "https://gw.example.com/mcp-connect/team",
            "name": "neon",
            "server": {},
            "server_uuid": "u1",
            "masked_diff": "",
        },
        "copy": None,
        "removal": None,
        "keychain": [],
        "reaches": [],
    }
    store.save(
        change_id,
        {
            "id": change_id,
            "action": "gateway.move",
            "state": "verified",
            "error": None,
            "refused_by": None,
            "holds_secret": False,
            "target": None,
            "rows": None,
            "request": None,
            "steps": [step],
        },
    )
    store.log(
        {
            "id": change_id,
            "time": "2026-10-01T00:00:00+00:00",
            "action": "gateway.move",
            "state": "verified",
            "steps": [{"client": "gateway", "name": "neon", "mechanism": "gateway_api"}],
        }
    )
    return store, change_id


def test_an_old_change_into_an_outside_gateway_leaves_the_history(tmp_path):
    store, change_id = _old_gateway_change(tmp_path)
    engine = Engine(store, run=None)
    assert change_id not in engine.changes
    assert store.entries() == []
    assert change_entries(store.entries(), engine, None) == []


def _page(home):
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    client = TestClient(app, base_url=ORIGIN, follow_redirects=False)
    client.get("/?token=tok")
    return client


def test_an_entry_that_pointed_at_a_saved_gateway_is_an_ordinary_server(tmp_path):
    home = make_home(tmp_path, "codex/0.159.2")
    folder = data_dir(home)
    folder.mkdir(parents=True, exist_ok=True)
    saved = {"gateways": [{"url": "https://mcp.neon.tech/mcp", "auth": "none"}]}
    (folder / "settings.json").write_text(json.dumps(saved))
    view = _page(home).get("/api/gateway-view").json()
    assert [g["kind"] for g in view["gateways"]] == ["kitden"]
    assert "neon" in [r["name"] for r in view["groups"]["move"]]


def test_the_page_has_no_outside_gateway_api(tmp_path):
    client = _page(make_home(tmp_path, "codex/0.159.2"))
    assert client.get("/api/gateways").status_code == 404
    answer = client.post("/api/gateways", headers=POST, json={"url": "https://gw.example.com/mcp"})
    assert answer.status_code in (404, 405)
