"""What the Gateway page gets about each server and tool: where a state comes from, the server's
switch on its tools, the counts, and why an outside row stays direct (spec Part 4, 4.2)."""

import json
from pathlib import Path

from kitden.demo import build_demo_home
from kitden.local_gateway.settings import load_settings, load_tools
from kitden.local_gateway.views import held_servers, own_rules, tools_view
from tests.unit.test_demo_mode import POST, demo_page
from tests.unit.test_local_gateway_views import tool

SITE, WEB = "/w/site", "/w/site/web"
ECHO_TOOLS = {"echo": [tool(n) for n in ("echo", "slow", "clash", "where")]}


def settings_with(global_rules, projects):
    return {
        "servers": {"echo": {"command": "echo"}},
        "rules": {"global": global_rules, "projects": projects},
    }


def test_each_tool_says_where_its_state_comes_from():
    settings = settings_with(
        {"echo": {"tools": {"slow": "off"}}},
        {SITE: {"echo": {"tools": {"clash": "off"}}}, WEB: {"echo": {"tools": {"where": "on"}}}},
    )
    web = tools_view(settings, ECHO_TOOLS, "echo", [WEB, SITE])
    assert [(t["origin"], t["origin_from"]) for t in web["tools"]] == [
        ("default", None),
        ("global", None),
        ("parent", "site"),
        ("project", None),
    ]


def test_a_tool_of_a_server_that_is_off_is_off():
    settings = settings_with({}, {SITE: {"echo": {"server": "off"}}})
    row = held_servers(settings, [WEB, SITE], ECHO_TOOLS)[0]
    assert (row["state"], row["origin"], row["origin_from"], row["on_count"]) == (
        "off",
        "parent",
        "site",
        0,
    )
    assert {(t["effective"], t.get("why")) for t in row["tool_list"]} == {("off", "server_off")}
    # Their own rules are untouched.
    assert [t["state"] for t in row["tool_list"]] == ["on", "on", "on", "on"]
    view = tools_view(settings, ECHO_TOOLS, "echo", [WEB, SITE])
    assert {(t["state"], t["effective"], t["why"]) for t in view["tools"]} == {
        ("on", "off", "server_off")
    }


def test_all_projects_counts_the_projects_that_turn_a_server_on():
    settings = settings_with({"echo": {"server": "off"}}, {SITE: {"echo": {"server": "on"}}})
    chains = {SITE: [SITE], WEB: [WEB, SITE], "/w/other": []}
    row = held_servers(settings, [], ECHO_TOOLS, chains)[0]
    assert (row["state"], row["on_in"], row["projects"]) == ("off", 2, 1)


def test_the_medium_sample_counts_tools_and_own_rules(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    settings, tools = load_settings(home), load_tools(home)
    files = next(r for r in held_servers(settings, [], tools) if r["name"] == "files")
    assert files["on_count"] == len(files["tool_list"]) - 1  # delete_file is off for all projects
    tracker = next(r for r in held_servers(settings, [], tools) if r["name"] == "tracker")
    report = next(t for t in tracker["tool_list"] if t["name"] == "export_report")
    assert report["origin"] == "strict"
    atlas, web = str(home / "work/atlas"), str(home / "work/atlas/web")
    website = str(home / "work/website")
    counts = (own_rules(settings, [atlas]), own_rules(settings, [web, atlas]))
    assert (*counts, own_rules(settings, [website])) == (1, 1, 0)


def test_a_rule_equal_to_the_shared_one_is_not_counted():
    settings = settings_with(
        {"echo": {"tools": {"slow": "off"}}}, {WEB: {"echo": {"tools": {"slow": "off"}}}}
    )
    assert own_rules(settings, [WEB]) == 0
    assert tools_view(settings, ECHO_TOOLS, "echo", [WEB])["tools"][1]["origin"] == "project"


def test_outside_rows_name_their_columns_and_why_they_stay(tmp_path):
    with demo_page(tmp_path) as page:  # medium
        groups = page.get("/api/gateway-view").json()["groups"]
        assert {r["name"]: r["columns"] for r in groups["local"]}["docs"] == ["codex"]
        assert all(r["stays"] is None for r in groups["move"] + groups["local"])
        # An entry that reads a header from the shell stays.
        claude = page.home / ".claude.json"
        data = json.loads(claude.read_text())
        data["mcpServers"]["github"]["headers"] = {"Authorization": "Bearer ${TOKEN}"}
        claude.write_text(json.dumps(data))
        page.post("/api/rescan", headers=POST)
        moves = page.get("/api/gateway-view").json()["groups"]["move"]
    row = next(r for r in moves if r["name"] == "github")
    assert row["stays"] == "github reads values from your shell; it stays direct for now."


def test_a_name_set_up_differently_in_one_group_stays_with_the_moves_own_words(tmp_path):
    with demo_page(tmp_path) as page:
        # Codex gets files too, with one more argument than Cursor's.
        config = page.home / ".codex/config.toml"
        files = '\n[mcp_servers.files]\ncommand = "npx"\nargs = ["files-mcp", "--fast"]\n'
        config.write_text(config.read_text() + files)
        page.post("/api/rescan", headers=POST)
        local = page.get("/api/gateway-view").json()["groups"]["local"]
        row = next(r for r in local if r["name"] == "files")
        targets = [{"item": item} for item in row["items"]]
        body = {"action": "gateway.move", "targets": targets, "params": {"gateway": "kitden"}}
        refused = page.post("/api/changes/preview", json=body, headers=POST)
    assert row["columns"] == ["codex", "cursor"]
    assert row["stays"] == "files is set up differently in Codex and Cursor; keep one first."
    assert (refused.status_code, refused.json()["detail"]) == (422, row["stays"])


def test_a_project_server_claude_code_has_not_approved_is_not_known(tmp_path):
    with demo_page(tmp_path) as page:
        # Atlas approves docs only: Claude Code still asks about notes.
        mcp = page.home / "work/atlas/.mcp.json"
        data = json.loads(mcp.read_text())
        data["mcpServers"]["notes"] = {"command": "npx", "args": ["notes-mcp"]}
        mcp.write_text(json.dumps(data))
        page.post("/api/rescan", headers=POST)
        projects = page.get("/api/projects").json()
        atlas = next(p["id"] for p in projects if p["path"].endswith("/work/atlas"))
        groups = page.get(f"/api/gateway-view?project={atlas}").json()["groups"]
    notes = next(r for r in groups["local"] if r["name"] == "notes")
    docs = next(r for r in groups["move"] if r["name"] == "docs")
    assert (notes["unknown"], docs["unknown"]) == (True, False)


def test_a_row_kept_from_the_last_good_read_stays(tmp_path):
    with demo_page(tmp_path) as page:
        (page.home / ".cursor/mcp.json").write_text("{ broken")
        page.post("/api/rescan", headers=POST)
        local = page.get("/api/gateway-view").json()["groups"]["local"]
    row = next(r for r in local if r["name"] == "files")
    assert row["stays"] == "Kitden can't change this until it reads mcp.json again."


def test_the_page_gets_own_rules_per_project_and_the_mcp_server_does_not(tmp_path):
    with demo_page(tmp_path) as page:
        projects = {Path(p["path"]).name: p for p in page.get("/api/projects").json()}
        atlas = page.get(f"/api/gateway-view?project={projects['atlas']['id']}").json()
        everywhere = page.get("/api/gateway-view").json()
    owned = {name: p["own_rules"] for name, p in projects.items()}
    assert (owned["atlas"], owned["web"], owned["website"]) == (1, 1, 0)
    # The scope bar counts the picked project's own rules; All projects has none.
    assert (atlas["own_rules"], everywhere["own_rules"]) == (1, 0)
    # The read-only MCP server's projects answer has no `own_rules`: see test_mcp_server.py.


def test_a_project_definition_that_replaces_a_shared_one_is_an_override(tmp_path):
    with demo_page(tmp_path) as page:
        projects = page.get("/api/projects").json()
        atlas = next(p["id"] for p in projects if p["path"].endswith("/work/atlas"))
        groups = page.get(f"/api/gateway-view?project={atlas}").json()["groups"]
        everywhere = page.get("/api/gateway-view").json()["groups"]
    docs = next(r for r in groups["move"] if r["name"] == "docs")
    assert docs["override"] is True
    assert docs["stays"] == "docs is in the project's own files; it stays there."
    assert not any(r["override"] for g in everywhere.values() for r in g)
