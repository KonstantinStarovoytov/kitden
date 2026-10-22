"""The page server in demo mode: the sample's home, stand-ins for everything that would leave it,
and `/api/about`."""

import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import kitden
from kitden.changes.actions import KITDEN_GATEWAY
from kitden.clients import version_cache
from kitden.demo import (
    CANNED_TOOLS,
    NOT_IN_DEMO,
    VERSIONS,
    build_demo_home,
    demo_build,
    keychain_file,
)
from kitden.gateways import add_gateway, data_dir
from kitden.local_gateway.settings import load_settings
from kitden.model import Gateway
from kitden.views import inventory as inventory_module
from kitden.views.inventory import Inventory, build_inventory
from kitden.web import app as page_app
from kitden.web.app import create_app
from tests.conftest import make_home

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}


@contextmanager
def demo_page(root, size="medium", **options):
    home = build_demo_home(root, size)
    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True, **options)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        page.home = home
        yield page


def until(ready, seconds=5.0):
    end = time.monotonic() + seconds
    while not ready():
        assert time.monotonic() < end, "gave up waiting"
        time.sleep(0.05)


def scan_done(page):
    """The first scan and everything after it (versions, marketplaces) are done."""
    view = page.get("/api/progress").json()
    return view["ready"] and all(step["done"] for step in view["steps"])


def preview(page, action, targets, params):
    body = {"action": action, "targets": targets, "params": params}
    answer = page.post("/api/changes/preview", json=body, headers=POST)
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_about_says_the_version_and_whether_it_is_a_demo(tmp_path):
    with demo_page(tmp_path / "demo") as page:
        assert page.get("/api/about").json() == {"version": kitden.__version__, "demo": True}
    home = make_home(tmp_path, "claude_code/2.1.283")
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN) as page:
        page.get("/?token=tok")
        assert page.get("/api/about").json() == {"version": kitden.__version__, "demo": False}


def test_about_answers_before_the_first_scan(tmp_path):
    gate = threading.Event()

    def slow(**options):
        gate.wait(10)
        return Inventory()

    app = create_app(slow, token="tok", port=47800, first_scan_later=True)
    with TestClient(app, base_url=ORIGIN) as page:
        page.get("/?token=tok")
        try:
            assert page.get("/api/about").json()["demo"] is False
            # The scan is still waiting: had /api/about waited for it, it would be done now.
            assert page.get("/api/progress").json()["ready"] is False
        finally:
            gate.set()


def test_a_demo_needs_the_sample_home():
    with pytest.raises(ValueError, match="Demo mode needs the sample's home folder."):
        create_app(lambda: Inventory(), token="tok", port=47800, demo=True)


def test_the_demo_shows_the_sample_versions_and_reads_none(tmp_path, monkeypatch):
    # Recorded, not raised: the page swallows an error of the version read.
    calls = []

    def recorder(name):
        def called(*args, **kwargs):
            calls.append(name)
            return {}

        return called

    for name in ("stale_clients", "refresh_versions", "cached_version"):
        monkeypatch.setattr(version_cache, name, recorder(name))
    # As `kitden serve` starts the page: the scan, then the versions, in the background.
    with demo_page(tmp_path, first_scan_later=True, quick_first=True) as page:
        until(lambda: scan_done(page))
        assert {c["id"]: c["version"] for c in page.get("/api/clients").json()} == VERSIONS
    assert calls == []


def test_the_demo_ignores_codex_home(tmp_path, monkeypatch):
    real = tmp_path / "real-codex"
    real.mkdir()
    (real / "config.toml").write_text('[mcp_servers.from-real-codex]\nurl = "https://r.test/mcp"\n')
    monkeypatch.setenv("CODEX_HOME", str(real))
    with demo_page(tmp_path / "demo") as page:
        assert "from-real-codex" not in page.get("/api/items").text
        # A change goes into the sample's Codex file too, not into CODEX_HOME.
        tools = next(
            i
            for i in page.get("/api/items?kind=mcp_server").json()
            if (i["client"], i["name"]) == ("cursor", "browser-tools")
        )
        change = preview(page, "mcp.add", [{"client": "codex"}], {"item": tools["id"]})
        assert [s["client"] for s in change["steps"]] == ["codex"]
        assert Path(change["steps"][0]["path"]).is_relative_to(page.home)


def test_the_demo_reads_no_app_folder(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(inventory_module, "app_url", lambda client, roots: seen.append(roots))
    with demo_page(tmp_path) as page:
        page.get("/api/clients")
    assert seen and all(list(roots) == [] for roots in seen)


def test_a_marketplace_and_a_registered_gateway_are_not_part_of_the_demo(tmp_path):
    with demo_page(tmp_path) as page:
        body = {
            "action": "marketplace.add",
            "targets": [{"client": "claude_code"}],
            "params": {"source": "team/market"},
        }
        market = page.post("/api/changes/preview", json=body, headers=POST)
        gateway = page.post(
            "/api/gateways",
            json={"url": "http://127.0.0.1:12008/mcp", "auth": "none"},
            headers=POST,
        )
    for answer in (market, gateway):
        assert (answer.status_code, answer.json()) == (422, {"detail": NOT_IN_DEMO})


def test_the_demo_shows_no_registered_gateway(tmp_path, monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("the demo reached a gateway")

    monkeypatch.setattr(page_app, "MetaMcpClient", never)
    monkeypatch.setattr(page_app, "ObotClient", never)
    with demo_page(tmp_path) as page:
        gateway = add_gateway(page.home, Gateway(url="http://127.0.0.1:12008/metamcp/team/mcp"))
        assert page.get("/api/gateways").json() == []
        assert page.get(f"/api/gateways/{gateway.id}/servers").status_code == 404
        body = {
            "action": "gateway.connect",
            "targets": [{"client": "cursor"}],
            "params": {"gateway": gateway.id, "name": "team"},
        }
        answer = page.post("/api/changes/preview", json=body, headers=POST)
    assert (answer.status_code, answer.json()) == (422, {"detail": "Register the gateway first."})


def test_moving_a_remote_server_in_uses_the_stand_ins(tmp_path):
    with demo_page(tmp_path) as page:
        home = page.home
        files = [home / ".claude.json", data_dir(home) / "gateway.json"]
        before = {p: p.read_bytes() for p in files}
        github = next(
            i
            for i in page.get("/api/items?kind=mcp_server").json()
            if (i["client"], i["name"]) == ("claude_code", "github")
        )
        change = preview(
            page, "gateway.move", [{"item": github["id"]}], {"gateway": KITDEN_GATEWAY}
        )
        done = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert done["state"] == "verified"
        stored = json.loads(keychain_file(home).read_text())
        assert stored["kitden github/Authorization"].startswith("Bearer DEMO_SECRET_")
        held = load_settings(home)["servers"]["github"]
        assert held["headers"]["Authorization"] == {"keychain": "github/Authorization"}
        names = [t["name"] for t in CANNED_TOOLS]
        until(
            lambda: (
                [t["name"] for t in page.get("/api/gateway/tools?server=github").json()["tools"]]
                == names
            )
        )
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
        assert "kitden github/Authorization" not in json.loads(keychain_file(home).read_text())
        assert {p: p.read_bytes() for p in files} == before


def test_put_back_reads_the_stand_in_keychain(tmp_path):
    with demo_page(tmp_path) as page:
        change = preview(page, "gateway.put_back", [{"client": "cursor"}], {"server": "tracker"})
    assert [s["client"] for s in change["steps"]] == ["cursor"]
    assert "DEMO_SECRET_" not in json.dumps(change)
