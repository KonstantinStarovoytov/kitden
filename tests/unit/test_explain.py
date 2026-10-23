"""Where an item comes from and why it loads or not (redesign plan, Task 2)."""

from dataclasses import replace
from pathlib import Path

import pytest

from kitden.clients.base import file_source
from kitden.model import Item, ItemKind, Scope
from kitden.views.explain import explain, reads
from kitden.views.inventory import build_inventory
from tests.conftest import make_home, write_cursor_fixture_state


@pytest.fixture
def home(tmp_path):
    # Cursor first: its fixture also has .claude files, and the Claude Code ones must win.
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return home


def test_plugin_base_name_finds_all_marketplace_copies(home):
    found = explain(build_inventory(home), "superpowers", "plugin", str(home / "work/website"))
    assert sorted((d["client"], d["scope"]) for d in found) == [
        ("claude_code", "project"),
        ("claude_code", "user"),
        ("cursor", "user"),
        ("cursor", "user"),
    ]


def test_why_says_which_definition_wins(home):
    found = explain(build_inventory(home), "superpowers", "plugin", str(home / "work/website"))
    user = next(d for d in found if (d["client"], d["scope"]) == ("claude_code", "user"))
    assert user["loads"] is False
    assert "the project definition overrides it" in user["why"]


def test_actions_and_hints_are_included(home):
    found = explain(build_inventory(home), "superpowers", "plugin", None)
    user = next(d for d in found if (d["client"], d["scope"]) == ("claude_code", "user"))
    assert user["actions"] == ["plugin.disable", "plugin.remove"]
    cursor_own = next(d for d in found if d["name"] == "superpowers@cursor-public")
    assert "Customize" in cursor_own["change_hint"]
    assert cursor_own["actions"] == []


def test_mcp_definitions_carry_a_short_summary_line(home):
    neon = explain(build_inventory(home), "Neon", "mcp_server", None)
    assert neon[0]["summary"] == "https://mcp.neon.tech/mcp"
    n8n = explain(build_inventory(home), "n8n-mcp", "mcp_server", None)
    assert n8n[0]["summary"].startswith("npx n8n-mcp -e ")
    assert "SENTINEL" not in n8n[0]["summary"]
    plugin = explain(build_inventory(home), "superpowers", "plugin", None)
    assert plugin[0]["summary"] is None


def test_exact_names_still_match_for_other_kinds(home):
    found = explain(build_inventory(home), "neon", "mcp_server", str(home / "work/api"))
    assert {(d["client"], d["scope"]) for d in found} == {("codex", "user"), ("codex", "project")}


def test_overridden_definitions_are_marked(home):
    found = explain(build_inventory(home), "superpowers", "plugin", str(home / "work/website"))
    marks = {
        (d["client"], d["scope"]): d["overridden"] for d in found if d["client"] == "claude_code"
    }
    assert marks == {("claude_code", "user"): True, ("claude_code", "project"): False}


def test_merged_definitions_are_not_marked_overridden(home):
    found = explain(build_inventory(home), "neon", "mcp_server", str(home / "work/api"))
    user = next(d for d in found if d["scope"] == "user")
    assert (user["merged"], user["overridden"]) == (True, False)


def test_one_row_with_two_claude_md_files_lists_both_paths(home):
    website = home / "work/website"
    (website / ".claude/CLAUDE.md").write_text("# More rules\n")
    found = explain(build_inventory(home), "CLAUDE.md", "instructions", str(website))
    sources = {d["source"] for d in found if d["scope"] == "project"}
    assert sources == {str(website / "CLAUDE.md"), str(website / ".claude/CLAUDE.md")}
    assert {d["category"] for d in found} == {"instructions"}
    assert all("Loads" not in d["why"] for d in found)
    assert "session starts" in found[0]["why"]


def test_explain_can_pick_one_category(home):
    (home / ".claude/agents/review.md").write_text("Review code.\n")
    both = explain(build_inventory(home), "review", "instructions", None)
    agents = explain(build_inventory(home), "review", "instructions", None, category="agent")
    assert sorted(d["category"] for d in both) == ["agent", "command"]
    assert [d["category"] for d in agents] == ["agent"]


def _user_file(definitions: list[dict], home) -> dict:
    return next(d for d in definitions if d["source"] == str(home / ".claude/CLAUDE.md"))


def test_the_preview_is_short_and_survives_bytes(home):
    path = home / ".claude/CLAUDE.md"
    path.write_bytes(b"# rules\n" + b"x" * 500 + b"\n" + b"\xff\xfe\n" + b"line\n" * 20)
    definitions = explain(build_inventory(home), "CLAUDE.md", "instructions", None)
    preview = _user_file(definitions, home)["preview"]
    assert len(preview) == 12 and len(preview[1]) == 200 and "\ufffd" in preview[2]


def test_the_preview_hides_a_secret_line(home):
    definitions = explain(build_inventory(home), "CLAUDE.md", "instructions", None)
    preview = _user_file(definitions, home)["preview"]
    assert any("[secret]" in line for line in preview)
    assert not any("SENTINEL_SECRET" in line for d in definitions for line in d["preview"] or [])


def test_project_files_show_a_preview_only_in_their_project(home):
    website = str(home / "work/website")
    everywhere = explain(build_inventory(home), "CLAUDE.md", "instructions", None)
    project = next(d for d in everywhere if d["project"] == website)
    assert project["preview"] is None and project["source"].endswith("website/CLAUDE.md")
    inside = explain(build_inventory(home), "CLAUDE.md", "instructions", website)
    assert next(d for d in inside if d["project"] == website)["preview"]


def test_other_kinds_have_no_preview(home):
    assert explain(build_inventory(home), "Neon", "mcp_server", None)[0]["preview"] is None


def test_the_preview_drops_a_bom_and_a_line_cut_by_the_read_limit(home):
    path = home / ".claude/CLAUDE.md"
    path.write_text("\ufeff# rules\n" + "y" * 70_000 + "\n")
    preview = _user_file(explain(build_inventory(home), "CLAUDE.md", "instructions", None), home)
    assert preview["preview"] == ["# rules"]


def test_rules_words_only_for_the_rules_folder(home):
    rules = home / ".claude/rules"
    rules.mkdir()
    (rules / "style.md").write_text("Short lines.\n")
    found = explain(build_inventory(home), "style", "instructions", None)
    assert "paths" in found[0]["why"]
    # A project folder named rules holds a plain CLAUDE.md, not a rule.
    plain = Item(
        client="claude_code",
        kind=ItemKind.INSTRUCTIONS,
        name="CLAUDE.md",
        source=file_source(Path("/h/work/rules/CLAUDE.md"), "claude_code"),
        scope=Scope.PROJECT,
        summary=(("category", "instructions"),),
    )
    assert "paths" not in reads(plain, [plain])


def test_a_definition_kept_from_the_last_good_read_says_when(home):
    inventory = build_inventory(home)
    at = "2026-10-22T14:02:00+00:00"
    inventory.items = [
        replace(i, stale_at=at) if i.name == "github" else i for i in inventory.items
    ]
    found = explain(inventory, "github", "mcp_server", None)
    assert found and {d["stale_at"] for d in found} == {at}
    assert {d["stale_at"] for d in explain(inventory, "Neon", "mcp_server", None)} == {None}
