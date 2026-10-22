"""Add what a project is missing: one review for every client (spec 3.5)."""

import json
import tomllib

import pytest

import kitden.clients.base as base
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_api_changes import FakeClaude
from tests.unit.test_api_plugin_install import FakeCli
from tests.unit.test_catalog import add_marketplaces
from tests.unit.test_local_gateway_move import add_claude, add_codex
from tests.unit.test_local_gateway_views import POST, page_for, project_id
from tests.unit.test_skills_catalog import add_skills_marketplace

MARKETPLACE = ".claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    add_skills_marketplace(home)
    skills = json.loads((home / MARKETPLACE).read_text())["plugins"]
    add_marketplaces(home)
    # Both helpers write the same marketplace file: list the plugins of both.
    listed = json.loads((home / MARKETPLACE).read_text())
    listed["plugins"] += skills
    (home / MARKETPLACE).write_text(json.dumps(listed))
    config = home / ".codex/config.toml"
    config.write_text(config.read_text() + '\n[plugins."superpowers@team-mkt"]\nenabled = true\n')
    add_claude(home, "neon", {"type": "http", "url": "https://other.invalid/mcp"})
    add_claude(home, "shelled", {"type": "stdio", "command": "npx", "args": ["x", "${TOKEN}"]})
    return home


def runner(home):
    def run(command, cwd):
        return (FakeClaude(home) if command[1] == "mcp" else FakeCli(home))(command, cwd)

    return run


def _align(page, project, chosen=None):
    body = {
        "action": "project.align",
        "targets": [],
        "params": {"project": project, "chosen": chosen},
    }
    return page.post("/api/changes/preview", json=body, headers=POST)


def test_add_missing_lists_what_each_client_lacks(home):
    api = str(home / "work/api")  # Codex trusts it
    with page_for(home, run=runner(home)) as page:
        listing = _align(page, project_id(page, api)).json()["align"]
    keys = {c["key"]: c for c in listing["candidates"]}
    assert all(c["chosen"] for c in listing["candidates"])
    assert keys["mcp_server:github:codex"]["from"] == "claude_code"
    assert keys["mcp_server:github:cursor"]["from"] == "claude_code"
    assert keys["mcp_server:langfuse-data:claude_code"]["from"] == "codex"
    assert keys["skill:brandkit:codex"]["from"] == "claude_code"
    assert keys["skill:docker-expert:claude_code"]["from"] == "codex"
    # A shared folder is Cursor's own: what it alone loads there is offered too.
    assert keys["skill:pixel-art:claude_code"]["from"] == "cursor"
    # Each says where it goes: an MCP entry is for all projects, a skill copy goes into api.
    assert keys["mcp_server:github:codex"]["place"] == "all"
    assert keys["skill:brandkit:codex"]["place"] == "project"
    # Names match exactly, as the Library rows do: Codex has neon, Cursor has Neon.
    assert "mcp_server:neon:codex" not in keys
    assert keys["mcp_server:neon:cursor"]["from"] == "claude_code"
    assert keys["mcp_server:Neon:codex"]["from"] == "cursor"
    # A name in another case is said on the item.
    beside = "already has {}; this adds {} beside it."
    assert keys["mcp_server:Neon:codex"]["note"] == "Codex " + beside.format("neon", "Neon")
    assert keys["mcp_server:neon:cursor"]["note"] == "Cursor " + beside.format("Neon", "neon")
    assert keys["mcp_server:github:codex"]["note"] is None
    # Cursor loads brandkit from Claude Code's folder, and Codex has pixel-art turned off.
    assert "skill:brandkit:cursor" not in keys
    assert "skill:pixel-art:codex" not in keys
    assert {"kind": "mcp_server", "name": "neon", "clients": ["claude_code", "codex"]} in listing[
        "not_same"
    ]
    assert {
        "kind": "plugin",
        "name": "superpowers",
        "clients": ["claude_code", "codex", "cursor"],
    } in listing["not_same"]
    # The same folder read by two clients is the same skill.
    assert "docker-expert" not in {n["name"] for n in listing["not_same"]}
    assert {
        "name": "shelled",
        "why": "Codex cannot read `${TOKEN}` from your shell; put the value in.",
    } in listing["left_out"]
    # Its marketplace folder is not in the fixture; said once, not once per client.
    browser = [e for e in listing["left_out"] if e["name"] == "browser@openai-bundled"]
    assert browser == [
        {"name": "browser@openai-bundled", "why": "not in a marketplace on this computer"}
    ]


def test_add_missing_is_one_change_and_undo_takes_it_all_back(home):
    api = str(home / "work/api")
    files = [home / ".codex/config.toml", home / ".claude.json"]
    before = {p: p.read_bytes() for p in files}
    with page_for(home, run=runner(home)) as page:
        chosen = [
            "mcp_server:github:codex",
            "skill:brandkit:codex",
            "mcp_server:langfuse-data:claude_code",
        ]
        change = _align(page, project_id(page, api), chosen).json()
        assert [(s["client"], s["name"]) for s in change["steps"]] == [
            ("codex", "github"),
            ("codex", "brandkit"),
            ("claude_code", "langfuse-data"),
        ]
        assert change["steps"][1]["path"] == f"{api}/.agents/skills/brandkit"
        assert change["steps"][1]["reaches"] == ["codex", "cursor"]
        assert [c["key"] for c in change["align"]["candidates"] if c["chosen"]] == chosen
        after = change["after"]
        assert [(a["client"], a["word"]) for a in after] == [
            ("claude_code", "Loads"),
            ("codex", "Loads"),
            ("cursor", "Loads twice"),  # it reads brandkit in Claude Code's folder already
        ]
        # langfuse-data's header holds a secret: the copy says so, as a single add does.
        assert after[0]["note"] == "This makes a second copy of a secret in ~/.claude.json."
        assert "SENTINEL" not in json.dumps(change)
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        assert (home / "work/api/.agents/skills/brandkit/SKILL.md").is_file()
        assert "github" in tomllib.loads((home / ".codex/config.toml").read_text())["mcp_servers"]
        assert "langfuse-data" in json.loads((home / ".claude.json").read_text())["mcpServers"]
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
    assert {p: p.read_bytes() for p in files} == before
    assert not (home / "work/api/.agents/skills/brandkit").exists()


def test_unchecked_items_are_left_out_of_the_change(home):
    api = str(home / "work/api")
    with page_for(home, run=runner(home)) as page:
        none = _align(page, project_id(page, api), [])
        assert (none.status_code, none.json()["detail"]) == (422, "Choose at least one item.")
        one = _align(page, project_id(page, api), ["skill:brandkit:codex"]).json()
        assert [s["name"] for s in one["steps"]] == ["brandkit"]
        unknown = _align(page, "nope")
        assert (unknown.status_code, unknown.json()["detail"]) == (422, "Unknown project.")


def test_a_copy_another_client_reads_is_not_made_twice_and_nothing_is_overwritten(home):
    # Claude Code's site-style lives in work/website. Codex does not trust website, so its copy
    # goes to all projects, in the folder Cursor reads too: Cursor gets no copy of its own.
    website = str(home / "work/website")
    (home / "work/website/.claude/skills/langfuse").mkdir(parents=True)  # a folder in the way
    with page_for(home, run=runner(home)) as page:
        change = _align(page, project_id(page, website)).json()
        listing = change["align"]
        keys = {c["key"]: c for c in listing["candidates"]}
        assert keys["skill:site-style:codex"]["place"] == "all"
        # Cursor's item stays checked and says where its copy is.
        cursor = keys["skill:site-style:cursor"]
        assert (cursor["chosen"], cursor["place"]) == (True, "all")
        copies = [s for s in change["steps"] if s["name"] == "site-style"]
        assert [(s["client"], s["path"], s["reaches"]) for s in copies] == [
            ("codex", f"{home}/.agents/skills/site-style", ["codex", "cursor"])
        ]
        assert {
            "name": "langfuse",
            "why": "Claude Code already has a skill named langfuse",
        } in listing["left_out"]
        # Without the Codex copy, Cursor gets one in the project.
        alone = _align(page, project_id(page, website), ["skill:site-style:cursor"]).json()
        assert [(s["client"], s["path"]) for s in alone["steps"]] == [
            ("cursor", f"{website}/.cursor/skills/site-style")
        ]


def test_plugins_go_where_each_client_can_take_them(home):
    # Two Claude Code plugins in website: Codex adds their marketplace once, for all projects.
    website = home / "work/website"
    settings = website / ".claude/settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    plugins = {"linter@claude-plugins-official": True, "toolbox@claude-plugins-official": True}
    settings.write_text(json.dumps({"enabledPlugins": plugins}))
    with page_for(home, run=runner(home)) as page:
        wanted = [
            "plugin:linter@claude-plugins-official:codex",
            "plugin:toolbox@claude-plugins-official:codex",
        ]
        change = _align(page, project_id(page, str(website)), wanted).json()
        assert [(s["client"], s["name"], s["scope"]) for s in change["steps"]] == [
            ("codex", "claude-plugins-official", "user"),
            ("codex", "linter@claude-plugins-official", "user"),
            ("codex", "toolbox@claude-plugins-official", "user"),
        ]
        keys = {c["key"]: c for c in change["align"]["candidates"]}
        assert keys["plugin:linter@claude-plugins-official:codex"]["place"] == "all"
        assert {
            "name": "linter@claude-plugins-official",
            "why": "Cursor loads Claude Code's plugins only when they are for all projects",
        } in change["align"]["left_out"]


def test_a_skill_copy_does_not_hide_a_server_of_the_same_name(home):
    # Claude Code has a skill named notion; Codex has an MCP server named notion. The skill's copy
    # for Codex reaches Cursor, but Cursor still gets the server.
    skill = home / ".claude/skills/notion/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: notion\ndescription: Notes.\n---\n# Notion\n")
    add_codex(home, "notion", 'url = "https://notion.invalid/mcp"')
    api = str(home / "work/api")
    with page_for(home, run=runner(home)) as page:
        chosen = ["skill:notion:codex", "mcp_server:notion:cursor"]
        change = _align(page, project_id(page, api), chosen).json()
        assert [(s["client"], s["name"]) for s in change["steps"]] == [
            ("codex", "notion"),
            ("cursor", "notion"),
        ]
