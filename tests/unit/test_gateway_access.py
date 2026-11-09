"""What the Gateway page gets about each server and tool: where a state comes from, the server's
switch on its tools, the counts, and why an outside row stays direct (spec Part 4, 4.2)."""

import json
from pathlib import Path

from kitden.clients.entries import app_of
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


def test_only_this_project_needs_no_other_project_that_turns_the_server_on():
    atlas, website = "/w/atlas", "/w/website"
    both = settings_with(
        {"echo": {"server": "off"}},
        {atlas: {"echo": {"server": "on"}}, website: {"echo": {"server": "on"}}},
    )
    chains = {atlas: [atlas], website: [website]}
    for project in (atlas, website):
        row = held_servers(both, [project], ECHO_TOOLS, chains)[0]
        assert (row["state"], row["differs"], row["on_elsewhere"]) == ("on", True, 1)
    # Atlas alone turns it on; a folder under it follows its rule, so that one counts too.
    alone = settings_with({"echo": {"server": "off"}}, {atlas: {"echo": {"server": "on"}}})
    assert held_servers(alone, [atlas], ECHO_TOOLS, chains)[0]["on_elsewhere"] == 0
    web = {**chains, f"{atlas}/web": [f"{atlas}/web", atlas]}
    assert held_servers(alone, [atlas], ECHO_TOOLS, web)[0]["on_elsewhere"] == 1


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


# The pen.dev app writes `pencil` into each client when it starts, with its own --agent value
# for each (seen on a Mac, 2026-11-08).
PEN = "/Applications/Pen.app/Contents/Resources/app.asar.unpacked/out/mcp-server-darwin-arm64"
PEN_SET_UP = "pencil is set up differently for each client by the Pen app; change it in Pen."
PEN_NOTE = (
    "pencil runs from the Pen app, which may write it back. If it comes back, change it in Pen."
)


def test_app_of_names_the_mac_app_a_command_runs_from():
    assert app_of({"command": PEN}) == "Pen"
    assert app_of({"command": "/Users/me/Applications/My Tool.app/Contents/MacOS/mcp"}) == "My Tool"
    # Only a command inside an app bundle counts.
    assert app_of({"command": "npx", "args": [PEN]}) is None
    assert app_of({"command": "/opt/Pen.app/mcp"}) is None
    assert app_of({"url": "https://pen.example.test/mcp"}) is None
    assert app_of({"command": ["not", "text"]}) is None


def add_pencil(home, *clients):
    """Pen's entry in Claude Code and Codex, as Pen writes it."""
    if "claude_code" in clients:
        claude = home / ".claude.json"
        data = json.loads(claude.read_text())
        data["mcpServers"]["pencil"] = {"command": PEN, "args": ["--agent", "claudeCodeCLI"]}
        claude.write_text(json.dumps(data))
    if "codex" in clients:
        config = home / ".codex/config.toml"
        pencil = f'\n[mcp_servers.pencil]\ncommand = "{PEN}"\nargs = ["--agent", "codexCLI"]\n'
        config.write_text(config.read_text() + pencil)


def _pencil(page, client):
    query = {"client": client, "kind": "mcp_server", "scope": "user"}
    return next(i for i in page.get("/api/items", params=query).json() if i["name"] == "pencil")


def test_entries_an_app_sets_up_differently_name_the_app(tmp_path):
    with demo_page(tmp_path) as page:
        add_pencil(page.home, "claude_code", "codex")
        page.post("/api/rescan", headers=POST)
        local = page.get("/api/gateway-view").json()["groups"]["local"]
        row = next(r for r in local if r["name"] == "pencil")
        targets = [{"item": item} for item in row["items"]]
        body = {"action": "gateway.move", "targets": targets, "params": {"gateway": "kitden"}}
        refused = page.post("/api/changes/preview", json=body, headers=POST)
        assert _pencil(page, "codex")["app"] == "Pen"
    assert row["stays"] == PEN_SET_UP
    assert (refused.status_code, refused.json()["detail"]) == (422, PEN_SET_UP)


def test_a_review_says_an_app_may_write_its_server_back(tmp_path):
    with demo_page(tmp_path) as page:
        add_pencil(page.home, "codex")
        page.post("/api/rescan", headers=POST)
        pencil = {"item": _pencil(page, "codex")["id"]}
        reviews = {}
        for action, params in (("mcp.remove_direct", {}), ("gateway.move", {"gateway": "kitden"})):
            body = {"action": action, "targets": [pencil], "params": params}
            answer = page.post("/api/changes/preview", json=body, headers=POST)
            assert answer.status_code == 200, answer.text
            reviews[action] = answer.json()
            page.post(f"/api/changes/{answer.json()['id']}/cancel", headers=POST)
        # A server that runs from no app gets no such note.
        n8n = page.get("/api/items", params={"client": "cursor", "kind": "mcp_server"}).json()
        target = next(i["id"] for i in n8n if i["name"] == "n8n")
        body = {"action": "mcp.remove_direct", "targets": [{"item": target}], "params": {}}
        plain = page.post("/api/changes/preview", json=body, headers=POST).json()
    # One plain note in the review; the change can still be applied.
    for review in reviews.values():
        assert [e["note"] for e in review["after"] if PEN_NOTE in e.get("note", "")] == [PEN_NOTE]
    assert not any("app" in (e.get("note") or "") for e in plain["after"])
