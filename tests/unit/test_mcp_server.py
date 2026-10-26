"""Read-only "show my setup" MCP server (T057, contracts/mcp-tools.md)."""

import hashlib
import json

import pytest
from mcp import Client
from starlette.testclient import TestClient

from kitden import mcp_server
from kitden.clients import version_cache
from kitden.demo import build_demo_home, demo_build
from kitden.mcp_server import create_server
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import all_text, fake_client_command, make_home, write_cursor_fixture_state

TOOLS = {"show_setup", "list_findings", "explain_item", "list_projects"}
pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


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
    assert all(f["clients"] for f in data["findings"])


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


async def test_explain_item_leaves_out_file_lines(home):
    # An agent's answer leaves this computer: a file's first lines stay on the local page.
    data = await call(server_for(home), "explain_item", name="CLAUDE.md")
    assert data["definitions"]
    assert all(d.get("preview") is None for d in data["definitions"])
    assert "Answer in short sentences." in (home / ".claude/CLAUDE.md").read_text()
    assert "Answer in short sentences." not in json.dumps(data)


async def test_explain_item_has_no_page_fields(home):
    # What a change reaches and the file key are for the local page; an agent's answer stays.
    data = await call(server_for(home), "explain_item", name="docker-expert")
    assert data["definitions"]
    assert all("affects" not in d and "key" not in d for d in data["definitions"])


async def test_list_projects(home):
    data = await call(server_for(home), "list_projects")
    paths = {p["path"] for p in data["projects"]}
    assert str(home / "work/website") in paths
    # The page's count of each project's own rules is for the project menu only.
    assert all("own_rules" not in p for p in data["projects"])


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


def test_server_is_named_kitden_and_points_to_kitden_open(home):
    server = server_for(home)
    assert server.name == "kitden"
    assert "kitden open" in server.instructions


def test_kitden_mcp_reads_versions_from_the_cache_and_runs_no_command(home, tmp_path, monkeypatch):
    ran = tmp_path / "ran"
    client = fake_client_command(tmp_path, "client", f"echo ran >> '{ran}'; echo 9.9.9")
    monkeypatch.setattr(version_cache, "version_command", lambda c: [str(client), "--version"])
    built = {}

    class Server:
        def run(self):
            built["inventory"] = built["build"]()

    def create(build, **options):
        built["build"] = build
        return Server()

    monkeypatch.setattr(mcp_server, "create_server", create)
    mcp_server.run(home)
    assert not ran.exists()
    assert {c.version for c in built["inventory"].clients if c.id != "claude_desktop_code_tab"} == {
        None
    }


def test_the_server_names_instruction_files():
    from kitden.views.inventory import Inventory

    server = create_server(lambda: Inventory())
    assert "instruction files" in server.instructions


async def test_a_same_name_note_names_the_client_with_another_source(home):
    from tests.unit.test_local_gateway_move import add_claude

    add_claude(home, "neon", {"type": "http", "url": "https://other.invalid/mcp"})
    data = await call(server_for(home), "list_findings")
    (note,) = [f for f in data["findings"] if f["type"] == "same_name_other_source"]
    assert note["clients"] == ["claude_code", "codex"]
    assert note["explanation"].endswith("but codex's neon comes from another source")


async def test_explain_item_sees_a_skill_turned_off_in_one_project(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    atlas = home / "work/atlas"
    local = atlas / ".claude/settings.local.json"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(json.dumps({"skillOverrides": {"brandkit": "off"}}))
    server = create_server(demo_build(home), cwd=lambda: str(atlas))
    data = await call(server, "explain_item", name="brandkit", kind="skill")
    claude = next(d for d in data["definitions"] if d["client"] == "claude_code")
    assert claude["enabled"] == "off"
    assert claude["why"] == "Does not load: it is turned off."
