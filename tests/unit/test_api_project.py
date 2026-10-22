import pytest
from starlette.testclient import TestClient

from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

ORIGIN = "http://127.0.0.1:47800"


@pytest.fixture
def client(tmp_path, monkeypatch):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    app = create_app(lambda: build_inventory(home), token="tok", port=47800)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        c.home = home
        yield c


def _project_id(client, relative):
    path = str(client.home / relative)
    return next(p["id"] for p in client.get("/api/projects").json() if p["path"] == path)


def test_project_view_shows_what_each_client_loads_there(client):
    data = client.get(f"/api/projects/{_project_id(client, 'work/website')}/effective").json()
    views = {v["client"]: v for v in data["views"]}
    claude = {i["name"] for i in views["claude_code"]["items"]}
    assert {"docs", "local-db", "site-style"} <= claude
    assert "brainstorming" not in claude  # its plugin is off in this project
    assert [(s["mode"]) for s in views["claude_code"]["shadowed"]] == ["override"]
    assert data["project"]["path"] == str(client.home / "work/website")


def test_unknown_project_is_404(client):
    assert client.get("/api/projects/nope/effective").status_code == 404


def test_findings_for_a_project_and_without_one(client):
    website = str(client.home / "work/website")
    in_project = {f["type"] for f in client.get(f"/api/findings?project={website}").json()}
    assert {"scope_override", "cross_loaded", "unknown_state"} <= in_project
    everywhere = client.get("/api/findings").json()
    duplicates = [f for f in everywhere if f["type"] == "duplicate_in_client"]
    assert {(f["client"], f["names"][0]) for f in duplicates} >= {("codex", "docker-expert")}


def test_project_responses_never_contain_secrets(client):
    pid = _project_id(client, "work/website")
    for url in (f"/api/projects/{pid}/effective", "/api/findings"):
        assert "SENTINEL_SECRET" not in client.get(url).text
