"""`kitden show`: the MCP server's answers on the command line, for the plugin's skills."""

import json

import pytest
from mcp import Client

from kitden.cli import main
from kitden.mcp_server import create_server
from kitden.views.answers import read_setup
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_project_rows import worktree

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def show(capsys, home, *args):
    code = main(["show", *args, "--home", str(home)])
    out = capsys.readouterr()
    return code, out


async def tool(home, tool_name, arguments):
    server = create_server(lambda: read_setup(home), cwd=lambda: str(home))
    async with Client(server) as client:
        result = await client.call_tool(tool_name, arguments)
    return result.structured_content


async def test_show_prints_what_the_server_tools_answer(home, capsys):
    project = str(home / "work/website")
    asked = [
        (["setup", "--project", project], "show_setup", {"project_path": project}),
        (
            ["setup", "--project", project, "--client", "codex"],
            "show_setup",
            {"project_path": project, "client": "codex"},
        ),
        (["findings", "--project", project], "list_findings", {"project_path": project}),
        (
            ["item", "github", "--kind", "mcp_server", "--project", project],
            "explain_item",
            {"name": "github", "kind": "mcp_server", "project_path": project},
        ),
        (["projects"], "list_projects", {}),
    ]
    for args, name, arguments in asked:
        code, out = show(capsys, home, *args)
        assert code == 0, out.err
        assert json.loads(out.out) == await tool(home, name, arguments), args


def test_show_setup_names_the_project_and_forbids_edits(home, capsys):
    code, out = show(capsys, home, "setup", "--project", str(home / "work/website"))
    answer = json.loads(out.out)
    assert code == 0
    assert answer["project"]["path"] == str(home / "work/website")
    assert {v["client"] for v in answer["views"]} >= {"claude_code", "codex"}
    assert "Do not edit client settings files" in answer["note"]


def test_show_context_prints_a_card_per_client(home, capsys):
    code, out = show(capsys, home, "context")
    answer = json.loads(out.out)
    assert code == 0
    assert answer["project"] is None
    assert [c["client"] for c in answer["clients"]] == ["claude_code", "codex", "cursor"]
    for card in answer["clients"]:
        assert card["lede"] and isinstance(card["skills"], list)


def test_show_item_needs_a_name(home, capsys):
    code, out = show(capsys, home, "item")
    assert code == 2
    assert out.out == ""
    assert "kitden show item NAME" in out.err


def test_show_says_when_the_client_is_unknown(home, capsys):
    code, out = show(capsys, home, "setup", "--client", "nope")
    assert code == 2
    assert out.out == ""
    assert "Unknown or missing client: nope" in out.err


def test_show_says_it_asks_codex_and_a_second_run_does_not(home, capsys, monkeypatch):
    import subprocess

    import kitden.clients.codex as codex

    runs = []

    def codex_list(command, **kwargs):
        runs.append(command)
        return subprocess.CompletedProcess(command, 0, '{"installed": []}', "")

    monkeypatch.setattr(codex, "version_command", lambda client: ["codex", "--version"])
    monkeypatch.setattr(codex.subprocess, "run", codex_list)
    monkeypatch.setattr("kitden.clients.version_cache.cached_version", lambda h, c: "0.163.0")
    notes = []
    for _ in range(2):
        monkeypatch.setattr(codex, "_LIST_CACHE", {})  # a new process each time
        code, out = show(capsys, home, "projects")
        assert code == 0
        json.loads(out.out)  # stdout stays valid JSON
        notes.append(out.err)
    assert len(runs) == 1
    assert notes == ["Asking Codex which plugins are on (up to 15 s)…\n", ""]


def test_show_projects_lists_the_short_list(home, capsys):
    website = home / "work/website"
    wt = worktree(website, website / ".claude/worktrees/wt", "wt")
    config = json.loads((home / ".claude.json").read_text())
    config["projects"][str(wt)] = {}
    (home / ".claude.json").write_text(json.dumps(config))
    code, out = show(capsys, home, "projects")
    assert code == 0
    paths = [p["path"] for p in json.loads(out.out)["projects"]]
    assert str(website) in paths
    assert str(wt) not in paths
