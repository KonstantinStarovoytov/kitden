"""Load map: items in rows, the three clients in columns (redesign plan, Task 1)."""

import shutil
from dataclasses import replace

import pytest

from kitden.demo import build_demo_home
from kitden.model import (
    Client,
    ClientStatus,
    Gateway,
    Item,
    ItemKind,
    Scope,
    Source,
    SourceKind,
)
from kitden.views.explain import explain
from kitden.views.findings import mark_gateways
from kitden.views.inventory import Inventory, build_inventory
from kitden.views.load_map import COLUMNS, load_map, map_dict
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_local_gateway_move import add_claude, add_cursor

EVIL = '<img src=x onerror="alert(1)">'


@pytest.fixture
def home(tmp_path):
    # Cursor first: its fixture also has .claude files, and the Claude Code ones must win.
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return home


def rows_by(rows, kind, name):
    return next(r for r in rows if (str(r.kind), r.name) == (kind, name))


def plugin_row(rows, lookup):
    return next(r for r in rows if str(r.kind) == "plugin" and r.lookup == lookup)


def test_rows_group_by_kind_and_name_with_one_plugin_row_per_marketplace(home):
    rows = load_map(build_inventory(home), None)
    superpowers = [r for r in rows if str(r.kind) == "plugin" and r.name == "superpowers"]
    assert [(r.source, r.lookup) for r in superpowers] == [
        ("claude-plugins-official", "superpowers@claude-plugins-official"),
        ("cursor-public", "superpowers@cursor-public"),
    ]
    official = superpowers[0]
    assert official.cells["codex"].state == "none"
    assert official.cells["claude_code"].state == "on"
    assert set(official.cells) == set(COLUMNS)
    assert superpowers[1].cells["claude_code"].state == "none"


def test_cell_states_for_the_website_project(home):
    rows = load_map(build_inventory(home), str(home / "work/website"))
    cell = plugin_row(rows, "superpowers@claude-plugins-official").cells["claude_code"]
    assert (cell.state, cell.where) == ("off", "This project")


def test_cursor_loading_a_plugin_twice_flags_both_rows_and_each_row_has_one_cell(home):
    rows = load_map(build_inventory(home), None)
    own = plugin_row(rows, "superpowers@cursor-public")
    claudes = plugin_row(rows, "superpowers@claude-plugins-official")
    assert own.cells["cursor"].where is None
    assert (claudes.cells["cursor"].count, claudes.cells["cursor"].route) == (
        1,
        "through Claude Code's folder",
    )
    for row in (own, claudes):
        assert [f["text"] for f in row.flags] == ["Cursor loads it twice"]


def test_a_cursor_copy_of_a_claude_code_plugin_names_the_choice(home):
    row = plugin_row(load_map(build_inventory(home), None), "superpowers@claude-plugins-official")
    flag = next(f for f in row.flags if f["client"] == "cursor")
    assert flag["via"] == "claude_code"
    assert flag["fix_action"] is None
    assert flag["fix"] == (
        "Two copies load in Cursor: its own and Claude Code's. To keep one: remove it in Cursor "
        "(Customize → Plugins), or turn off Include Third-Party Plugins in Cursor Settings. "
        "Turning it off in Claude Code also turns it off for Claude Code."
    )


def test_two_copies_of_a_plugin_in_one_client_offer_to_turn_one_off():
    def plugin(name, path):
        source = Source(kind=SourceKind.FILE, path=path, owner_client="claude_code")
        return Item(
            client="claude_code",
            kind=ItemKind.PLUGIN,
            name=name,
            source=source,
            scope=Scope.USER,
            actions=("plugin.disable",),
        )

    clients = [Client(id="claude_code", display_name="Claude Code", status=ClientStatus.FOUND)]
    inventory = Inventory(
        clients=clients, items=[plugin("x@a", "/h/a.json"), plugin("x@b", "/h/b.json")]
    )
    row = rows_by(load_map(inventory, None), "plugin", "x")
    assert row.flags == [
        {
            "text": "Claude Code loads it twice",
            "level": "warning",
            "client": "claude_code",
            "fix": "Remove one copy to keep the other.",
            "fix_action": "plugin.remove",
        }
    ]


def test_a_duplicate_skill_names_the_fix_and_its_action(home):
    row = rows_by(load_map(build_inventory(home), None), "skill", "docker-expert")
    flag = next(f for f in row.flags if f["client"] == "codex")
    assert flag["text"] == "Codex loads it twice"
    assert flag["fix"] == "Remove one copy to keep the other."
    assert flag["fix_action"] == "skill.remove"


def test_cross_loaded_cells_say_via_which_client(home):
    row = rows_by(load_map(build_inventory(home), None), "skill", "brandkit")
    assert (row.cells["cursor"].state, row.cells["cursor"].route) == (
        "on",
        "through Claude Code's folder",
    )
    assert row.cells["claude_code"].where is None


def test_gateway_entries_are_state_gw(home):
    inventory = build_inventory(home)
    mark_gateways(inventory, [Gateway(url="https://mcp.neon.tech/mcp")])
    rows = load_map(inventory, None, gateway_registered=True)
    assert rows_by(rows, "mcp_server", "Neon").cells["cursor"].state == "gw"
    # A direct server is an option to move, not a problem.
    assert rows_by(rows, "mcp_server", "langfuse-data").flags == [
        {"text": "Direct connection", "level": "info"}
    ]


def test_unknown_state_is_said_by_the_cell_alone(home):
    rows = load_map(build_inventory(home), None)
    gmail = rows_by(rows, "plugin", "gmail")
    assert "unk" in {cell.state for cell in gmail.cells.values()}
    assert all(f["text"] != "State unknown" for r in rows for f in r.flags)


def test_direct_entries_are_only_info_without_a_gateway(home):
    rows = load_map(build_inventory(home), None)
    assert {"text": "Direct", "level": "info"} in rows_by(rows, "mcp_server", "Neon").flags
    assert {"text": "Local server", "level": "info"} in rows_by(rows, "mcp_server", "n8n-mcp").flags


def test_desktop_items_show_in_the_claude_code_column(home):
    row = rows_by(load_map(build_inventory(home), None), "mcp_server", "metamcp-local")
    cell = row.cells["claude_code"]
    assert (cell.state, cell.route) == ("on", "from the Desktop app")


def test_not_installed_client_column_says_missing(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    rows = load_map(build_inventory(home), None)
    assert {r.cells["codex"].state for r in rows} == {"missing"}
    assert {r.cells["cursor"].state for r in rows} == {"missing"}
    data = map_dict(build_inventory(home), rows)
    assert [(c["id"], c["status"]) for c in data["columns"]] == [
        ("claude_code", "found"),
        ("codex", "not_found"),
        ("cursor", "not_found"),
    ]


def test_mcp_and_plugin_with_the_same_name_stay_separate():
    def item(client, kind, name):
        source = Source(kind=SourceKind.FILE, path=f"/h/{client}", owner_client=client)
        return Item(client=client, kind=kind, name=name, source=source, scope=Scope.USER)

    clients = [Client(id=c, display_name=c, status=ClientStatus.FOUND) for c in COLUMNS]
    inventory = Inventory(
        clients=clients,
        items=[
            item("claude_code", ItemKind.MCP_SERVER, "github"),
            item("codex", ItemKind.PLUGIN, "github@openai-curated-remote"),
        ],
    )
    keys = {(str(r.kind), r.name) for r in load_map(inventory, None)}
    assert keys == {("mcp_server", "github"), ("plugin", "github")}


def test_raw_names_are_returned_unchanged(home):
    skill = home / ".claude/skills/evil/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(f"---\nname: {EVIL}\ndescription: test\n---\n")
    data = map_dict(build_inventory(home), load_map(build_inventory(home), None))
    names = {r["name"] for r in data["rows"]}
    assert EVIL in names
    row = next(r for r in data["rows"] if r["name"] == EVIL)
    assert set(row["cells"]["claude_code"]) == {
        "state",
        "where",
        "origin",
        "route",
        "reason",
        "stale_at",
        "items",
        "count",
    }


def test_project_only_items_are_not_rows_everywhere(home):
    everywhere = {r.name for r in load_map(build_inventory(home), None)}
    assert "site-db" not in everywhere
    site = {r.name for r in load_map(build_inventory(home), str(home / "work/site"))}
    assert "site-db" in site


def test_a_plugin_from_two_marketplaces_makes_two_rows(home):
    config = home / ".codex/config.toml"
    config.write_text(
        config.read_text() + '\n[plugins."figma@a"]\nenabled = true\n'
        '\n[plugins."figma@b"]\nenabled = true\n'
    )
    inventory = build_inventory(home)
    rows = [r for r in load_map(inventory, None) if str(r.kind) == "plugin" and r.name == "figma"]
    assert sorted((r.source, r.lookup) for r in rows) == [("a", "figma@a"), ("b", "figma@b")]
    assert len({r.key for r in rows}) == 2
    for row in rows:
        assert row.cells["codex"].count == 1
        assert [f["text"] for f in row.flags] == ["Codex loads it twice"]
    only_a = explain(inventory, "figma@a", "plugin", None)
    assert [d["name"] for d in only_a] == ["figma@a"]
    data = map_dict(inventory, rows)
    assert {(r["source"], r["lookup"]) for r in data["rows"]} == {
        ("a", "figma@a"),
        ("b", "figma@b"),
    }


def test_a_name_without_a_marketplace_has_no_source(home):
    rows = load_map(build_inventory(home), None)
    stored = rows_by(rows, "plugin", "plugin 4800 (name not stored locally)")
    assert (stored.source, stored.lookup) == (None, "plugin 4800 (name not stored locally)")
    skill = rows_by(rows, "skill", "docker-expert")
    assert (skill.source, skill.lookup) == (None, "docker-expert")


def test_an_item_only_the_project_has_says_only_this_project_and_a_project_win_says_this_project(
    home,
):
    rows = load_map(build_inventory(home), str(home / "work/website"))
    docs = rows_by(rows, "mcp_server", "docs").cells["claude_code"]
    assert (docs.where, docs.origin) == ("Only this project", "project")
    plugin = plugin_row(rows, "superpowers@claude-plugins-official").cells["claude_code"]
    assert (plugin.state, plugin.where, plugin.origin) == ("off", "This project", "override")
    github = rows_by(rows, "mcp_server", "github").cells["claude_code"]
    assert (github.where, github.origin) == (None, None)


def test_a_plugin_part_applies_where_its_plugin_does(home):
    rows = load_map(build_inventory(home), str(home / "work/website"))
    # The website turns superpowers off over the all-projects install; its skill follows it.
    skill = rows_by(rows, "skill", "brainstorming").cells["claude_code"]
    assert (skill.state, skill.where, skill.origin) == ("off", "This project", "override")
    assert skill.route == "from a plugin"
    # claude-md-management is off for all projects, so its server is too.
    server = rows_by(rows, "mcp_server", "md-index").cells["claude_code"]
    assert (server.state, server.where, server.origin) == ("off", None, None)


def test_a_cell_in_a_project_carries_a_tag_or_nothing(home):
    rows = load_map(build_inventory(home), str(home / "work/website"))
    cells = [c for r in rows for c in r.cells.values() if c.items]
    assert {c.where for c in cells} == {None, "This project", "Only this project"}


def test_all_projects_cells_carry_no_tag(home):
    rows = load_map(build_inventory(home), None)
    assert all(c.origin is None and c.where is None for r in rows for c in r.cells.values())


def test_the_route_leaves_the_word_slot(home):
    rows = load_map(build_inventory(home), None)
    brandkit = rows_by(rows, "skill", "brandkit").cells
    assert (brandkit["cursor"].where, brandkit["cursor"].route) == (
        None,
        "through Claude Code's folder",
    )
    assert brandkit["claude_code"].route is None
    metamcp = rows_by(rows, "mcp_server", "metamcp-local").cells["claude_code"]
    assert metamcp.route == "from the Desktop app"
    assert rows_by(rows, "mcp_server", "md-index").cells["claude_code"].route == "from a plugin"


def test_a_cell_says_this_project_only_where_the_project_decides(tmp_path):
    home = build_demo_home(tmp_path, "medium")  # Part 1: atlas/.mcp.json overrides the user docs
    rows = load_map(build_inventory(home), str(home / "work/atlas"))
    docs = rows_by(rows, "mcp_server", "docs").cells
    assert (docs["claude_code"].origin, docs["claude_code"].where) == ("override", "This project")
    assert (docs["codex"].origin, docs["codex"].where) == (None, None)
    shared = rows_by(rows, "mcp_server", "github").cells["claude_code"]
    assert (shared.origin, shared.where) == (None, None)
    only = rows_by(rows, "skill", "api-style").cells["codex"]
    assert (only.origin, only.where) == ("project", "Only this project")


def test_a_kept_cell_keeps_its_route(home):
    inventory = build_inventory(home)
    settings = str(home / ".claude/settings.json")
    inventory.items = [
        replace(i, stale_at="2026-10-22T14:02:00+00:00") if i.source.path == settings else i
        for i in inventory.items
    ]
    rows = load_map(inventory, str(home / "work/website"))
    row = rows_by(rows, "hook", "PreToolUse: Bash")
    cell = row.cells["cursor"]
    assert (cell.state, cell.where, cell.route) == (
        "on",
        None,
        "through Claude Code's folder",
    )
    assert cell.stale_at == "2026-10-22T14:02:00+00:00"
    assert cell.reason.startswith("From the last good read at ")
    assert row.flags[0] == {"text": cell.reason, "level": "info"}


def test_a_same_name_server_from_another_source_needs_review(home):
    add_claude(home, "neon", {"type": "http", "url": "https://other.invalid/mcp"})
    neon = rows_by(load_map(build_inventory(home), None), "mcp_server", "neon")
    assert (neon.cells["claude_code"].state, neon.cells["codex"].state) == ("on", "review")
    assert neon.cells["codex"].reason == "Same name, another source."


def test_the_two_that_agree_stay_and_the_odd_one_needs_review(home):
    add_claude(home, "neon", {"type": "http", "url": "https://other.invalid/mcp"})
    add_cursor(
        home, "neon", {"url": "https://mcp.neon.tech/mcp"}
    )  # loads: not turned off in Cursor
    neon = rows_by(load_map(build_inventory(home), None), "mcp_server", "neon")
    assert {c: neon.cells[c].state for c in COLUMNS} == {
        "claude_code": "review",
        "codex": "on",
        "cursor": "on",
    }


def test_a_copied_skill_is_the_same_skill(home):
    shutil.copytree(home / ".claude/skills/brandkit", home / ".codex/skills/brandkit")
    row = rows_by(load_map(build_inventory(home), None), "skill", "brandkit")
    assert "review" not in {c.state for c in row.cells.values()}


def test_a_same_name_skill_with_other_files_needs_review(home):
    folder = home / ".codex/skills/brandkit"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("---\nname: brandkit\n---\nSomething else.\n")
    row = rows_by(load_map(build_inventory(home), None), "skill", "brandkit")
    assert row.cells["codex"].state == "review"


def test_a_duplicate_in_one_client_is_not_review(home):
    row = rows_by(load_map(build_inventory(home), None), "skill", "docker-expert")
    assert "review" not in {c.state for c in row.cells.values()}


def test_a_review_cell_that_follows_the_shared_setup_carries_no_tag(tmp_path):
    home = build_demo_home(tmp_path, "medium")  # Part 1: Claude Code's docs is an address
    rows = load_map(build_inventory(home), str(home / "work/atlas"))
    codex = rows_by(rows, "mcp_server", "docs").cells["codex"]
    assert (codex.state, codex.where, codex.reason) == (
        "review",
        None,
        "Same name, another source.",
    )
