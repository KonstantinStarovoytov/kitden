import pytest
from starlette.testclient import TestClient

import agentsetup.clients.base as base
from agentsetup.views.inventory import build_inventory
from agentsetup.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

ORIGIN = "http://127.0.0.1:47800"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    app = create_app(lambda: build_inventory(home), token="tok", port=47800)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        c.home = home
        yield c


def test_items_can_be_filtered_by_client_and_kind(client):
    names = {i["name"] for i in client.get("/api/items?client=codex&kind=mcp_server").json()}
    assert names == {"neon", "langfuse-data", "aseprite", "api-docs", "evil"}


def test_items_can_be_filtered_by_project(client):
    site = str(client.home / "work/site")
    found = {(i["client"], i["name"]) for i in client.get(f"/api/items?project={site}").json()}
    assert found == {
        ("cursor", "site-db"),
        ("cursor", "langfuse@cursor-public"),
    }


def test_clients_and_projects_are_listed(client):
    ids = {c["id"] for c in client.get("/api/clients").json()}
    assert ids == {"claude_code", "claude_desktop_code_tab", "codex", "cursor"}
    paths = {
        p["path"].removeprefix(str(client.home) + "/") for p in client.get("/api/projects").json()
    }
    assert paths == {
        "work/website",
        "work/deleted-project",
        "work/api",
        "work/untrusted",
        "work/site",
    }


def test_api_responses_never_contain_secrets(client):
    for url in ("/api/clients", "/api/items", "/api/projects", "/api/problems"):
        assert "SENTINEL_SECRET" not in client.get(url).text
