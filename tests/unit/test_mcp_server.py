"""Read-only "show my setup" MCP server (T057, contracts/mcp-tools.md)."""

import hashlib
import json

import pytest
from mcp import Client
from starlette.testclient import TestClient

import agentsetup.clients.base as base
from agentsetup.mcp_server import create_server
from agentsetup.views.inventory import build_inventory
from agentsetup.web.app import create_app
from tests.conftest import all_text, make_home, write_cursor_fixture_state

TOOLS = {"show_setup", "list_findings", "explain_item", "list_projects"}
pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def server_for(home, cwd=None):
    return create_server(lambda: build_inventory(home), cwd=lambda: str(cwd or home))


async def call(server, tool, **arguments):
    async with Client(server) as client:
        result = await client.call_tool(tool, arguments)
    assert not result.is_error, result.content
    return result.structured_content


def _hashes(home):
    return {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in home.rglob("*")
        if p.is_file() and not p.is_symlink()
    }


async def test_only_read_only_tools_are_offered(home):
    async with Client(server_for(home)) as client:
        tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for tool in tools:
        hints = tool.annotations
        assert (hints.read_only_hint, hints.destructive_hint, hints.open_world_hint) == (
            True,
            False,
            False,
        )
        assert "cannot change" in tool.description
        # Agents with file access must not work around the read-only tool (found in validation).
        assert "Do not edit client settings files" in tool.description


async def test_show_setup_matches_the_page_project_view(home):
    website = str(home / "work/website")
    data = await call(server_for(home), "show_setup", project_path=website)
    from_mcp = {v["client"]: {i["id"] for i in v["items"]} for v in data["views"]}

    app = create_app(lambda: build_inventory(home), token="tok", port=47800)
    with TestClient(app, base_url="http://127.0.0.1:47800") as page:
        page.get("/?token=tok")
        project = next(p for p in page.get("/api/projects").json() if p["path"] == website)
        views = page.get(f"/api/projects/{project['id']}/effective").json()["views"]
    from_page = {v["client"]: {i["id"] for i in v["items"]} for v in views}
    assert from_mcp == from_page
    assert data["project"]["path"] == website


async def test_default_project_is_the_known_project_around_the_current_folder(home):
    inside = home / "work/website/src"
    inside.mkdir(parents=True)
    data = await call(server_for(home, cwd=inside), "show_setup", client="claude_code")
    assert data["project"]["path"] == str(home / "work/website")
    assert [v["client"] for v in data["views"]] == ["claude_code"]


async def test_outside_any_project_shows_user_level_setup(home):
    data = await call(server_for(home, cwd=home / "work"), "show_setup", client="codex")
    assert data["project"] is None
    names = {i["name"] for i in data["views"][0]["items"]}
    assert "neon" in names and "api-docs" not in names


async def test_findings_include_gateway_bypasses(home):
    data = await call(server_for(home), "list_findings", project_path=str(home / "work/website"))
    types = {f["type"] for f in data["findings"]}
    assert {"bypasses_gateway", "scope_override"} <= types


async def test_explain_item_lists_every_definition_and_the_winner(home):
    data = await call(
        server_for(home),
        "explain_item",
        name="superpowers@claude-plugins-official",
        project_path=str(home / "work/website"),
    )
    claude = [d for d in data["definitions"] if d["client"] == "claude_code"]
    assert {(d["scope"], d["loads"]) for d in claude} == {("user", False), ("project", False)}
    assert any("overrides" in d["why"] for d in claude)


async def test_list_projects(home):
    data = await call(server_for(home), "list_projects")
    paths = {p["path"] for p in data["projects"]}
    assert str(home / "work/website") in paths


async def test_no_secret_values_in_any_answer_and_no_file_changes(home):
    before = _hashes(home)
    server = server_for(home)
    answers = [
        await call(server, "show_setup", project_path=str(home / "work/website")),
        await call(server, "show_setup"),
        await call(server, "list_findings"),
        await call(server, "explain_item", name="langfuse-data"),
        await call(server, "list_projects"),
    ]
    assert "SENTINEL" not in json.dumps(answers) + all_text(answers)
    assert _hashes(home) == before


async def test_unknown_client_is_an_error(home):
    async with Client(server_for(home)) as client:
        result = await client.call_tool("show_setup", {"client": "vim"})
    assert result.is_error
