"""Read models for the redesigned page (redesign plan, Task 4)."""

import pytest
from starlette.testclient import TestClient

from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

ORIGIN = "http://127.0.0.1:47800"
ENDPOINTS = [
    "/api/map",
    "/api/library",
    "/api/library-list",
    "/api/overview",
    "/api/gateway-view",
    "/api/library-map",
    "/api/explain?name=x",
]


def _app(home):
    return create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)


@pytest.fixture
def home(tmp_path, monkeypatch):
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


def test_library_everywhere_and_for_a_project(client):
    everywhere = client.get("/api/library?kind=mcp_server").json()
    assert everywhere["project"] is None
    assert [c["id"] for c in everywhere["columns"]] == ["claude_code", "codex", "cursor"]
    assert "site-db" not in {r["name"] for r in everywhere["rows"]}

    site = client.get(f"/api/library?kind=mcp_server&project={_project_id(client, 'work/site')}")
    assert site.json()["project"]["path"] == str(client.home / "work/site")
    assert "site-db" in {r["name"] for r in site.json()["rows"]}


def test_overview_and_gateway_view(client):
    assert client.get("/api/overview").json()["counts"]["attention"] == 2
    view = client.get("/api/gateway-view").json()
    assert any(e["name"] == "Neon" for e in view["groups"]["move"])
    assert view["own_rules"] == 0  # All projects
    assert {p["own_rules"] for p in client.get("/api/projects").json()} == {0}


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


def test_explain_says_what_a_change_reaches(client):
    # Cursor reads pixel-art from Codex's folder only (docker-expert it also has elsewhere).
    answer = client.get("/api/explain?kind=skill&name=pixel-art").json()
    codex = next(d for d in answer["definitions"] if d["client"] == "codex")
    assert codex["affects"]["clients"] == ["codex", "cursor"]
    assert all("key" in d for d in answer["definitions"])
    assert all("affects" not in d for d in answer["definitions"] if not d["actions"])
    assert set(answer["inherits"]) == {"plugin", "skill"}
    # The file key goes with each definition, for Details' technical part.
    entry = client.get("/api/explain?kind=mcp_server&name=Neon").json()["definitions"]
    assert {d["client"]: d["key"] for d in entry}["cursor"] == "mcpServers.Neon"


@pytest.mark.parametrize("path", [*ENDPOINTS, "/api/library-offers", "/api/market-servers"])
def test_new_endpoints_need_the_session_cookie(home, path):
    with TestClient(_app(home), base_url=ORIGIN, follow_redirects=False) as anonymous:
        assert anonymous.get(path).status_code == 401
