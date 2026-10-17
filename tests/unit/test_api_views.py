"""Read models for the redesigned page (redesign plan, Task 4)."""

import pytest
from starlette.testclient import TestClient

import agentsetup.clients.base as base
from agentsetup.views.inventory import build_inventory
from agentsetup.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

ORIGIN = "http://127.0.0.1:47800"
ENDPOINTS = ["/api/map", "/api/overview", "/api/gateway-view", "/api/explain?name=x"]


def _app(home):
    return create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return home


@pytest.fixture
def client(home):
    with TestClient(_app(home), base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        c.home = home
        yield c


def _project_id(client, relative):
    path = str(client.home / relative)
    return next(p["id"] for p in client.get("/api/projects").json() if p["path"] == path)


def test_map_everywhere_and_for_a_project(client):
    everywhere = client.get("/api/map").json()
    assert everywhere["project"] is None
    assert [c["id"] for c in everywhere["columns"]] == ["claude_code", "codex", "cursor"]
    names = {r["name"] for r in everywhere["rows"]}
    assert "site-db" not in names

    site = client.get(f"/api/map?project={_project_id(client, 'work/site')}").json()
    assert site["project"]["path"] == str(client.home / "work/site")
    assert "site-db" in {r["name"] for r in site["rows"]}


def test_overview_and_gateway_view(client):
    assert client.get("/api/overview").json()["headline"] == "3 things need attention"
    groups = client.get("/api/gateway-view").json()["groups"]
    assert any(e["name"] == "Neon" for e in groups["move"])


def test_explain_for_a_project(client):
    website = _project_id(client, "work/website")
    found = client.get(f"/api/explain?kind=plugin&name=superpowers&project={website}").json()
    assert len(found["definitions"]) == 4


@pytest.mark.parametrize("path", ENDPOINTS)
def test_unknown_project_is_404(client, path):
    sep = "&" if "?" in path else "?"
    response = client.get(f"{path}{sep}project=nope")
    assert (response.status_code, response.json()) == (404, {"detail": "Unknown project."})


def test_explain_needs_a_name(client):
    assert client.get("/api/explain?kind=plugin").status_code == 422


@pytest.mark.parametrize("path", ENDPOINTS)
def test_new_endpoints_need_the_session_cookie(home, path):
    with TestClient(_app(home), base_url=ORIGIN, follow_redirects=False) as anonymous:
        assert anonymous.get(path).status_code == 401
