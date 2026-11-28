import json

import pytest
from starlette.testclient import TestClient

from kitden.model import Project
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_project_rows import worktree

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}


@pytest.fixture
def client(tmp_path, monkeypatch):
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
        ("cursor", "style"),
        ("cursor", ".cursorrules"),
        ("cursor", "AGENTS.md"),
    }


def test_clients_and_projects_are_listed(client):
    ids = {c["id"] for c in client.get("/api/clients").json()}
    assert ids == {"claude_code", "claude_desktop_code_tab", "codex", "cursor"}
    paths = {
        p["path"].removeprefix(str(client.home) + "/") for p in client.get("/api/projects").json()
    }
    # A gone folder with nothing of its own is no row.
    assert paths == {"work/website", "work/api", "work/untrusted", "work/site"}


def _fold_a_worktree_and_a_link(home):
    """A worktree of work/website and a link to it, both recorded by Claude Code."""
    website = home / "work/website"
    feature = worktree(website, website / ".claude/worktrees/feature", "feature")
    link = home / "work/web-link"
    link.symlink_to(website)
    config = json.loads((home / ".claude.json").read_text())
    config["projects"].update({str(feature): {}, str(link): {}})
    (home / ".claude.json").write_text(json.dumps(config))
    return feature, link


def test_api_projects_fold_a_worktree_and_a_link(client):
    feature, link = _fold_a_worktree_and_a_link(client.home)
    client.post("/api/rescan", headers=POST)
    rows = client.get("/api/projects").json()
    paths = {r["path"].removeprefix(str(client.home) + "/") for r in rows}
    assert paths == {"work/website", "work/api", "work/untrusted", "work/site"}
    website = next(r for r in rows if r["path"].endswith("work/website"))
    assert set(website["folded"]) == {Project(str(feature), True).id, Project(str(link), True).id}
    assert website["own"] is True  # its local-db server
    assert all({"folded", "own", "parent", "own_rules"} <= r.keys() for r in rows)


def test_a_folded_id_still_reads(client):
    feature, _ = _fold_a_worktree_and_a_link(client.home)
    client.post("/api/rescan", headers=POST)
    folded = Project(str(feature), True).id
    assert client.get(f"/api/overview?project={folded}").status_code == 200


def test_api_responses_never_contain_secrets(client):
    for url in ("/api/clients", "/api/items", "/api/projects", "/api/problems"):
        assert "SENTINEL_SECRET" not in client.get(url).text
