"""Where an item comes from and why it loads or not (redesign plan, Task 2)."""

import pytest

from kitden.views.explain import explain
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
