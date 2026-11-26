"""Which items offer which actions (FR-025, FR-026) and the steps each client uses (T045)."""

import pytest

from kitden.changes.actions import (
    folder_readers,
    plugin_skill_steps,
    plugin_skills_left_out,
    remove_steps,
)
from kitden.changes.json_splice import ABSENT
from kitden.views.inventory import build_inventory, default_adapters
from kitden.views.skills import skill_catalog
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_skills_catalog import PLUGIN, add_skills_marketplace


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


@pytest.fixture
def adapters(home):
    return {a.id: a for a in default_adapters(home)}


def _item(inventory, client, name, scope):
    return next(
        i
        for i in inventory.items
        if (i.client, i.name, str(i.scope)) == (client, name, scope) and str(i.kind) == "mcp_server"
    )


def test_only_direct_entries_in_files_can_be_removed_and_only_codex_toggles_mcp(home):
    inventory = build_inventory(home)
    assert {a for i in inventory.items for a in i.actions} == {
        "mcp.remove_direct",
        "plugin.enable",
        "plugin.disable",
        "plugin.remove",
        "skill.remove",
    }
    mcp_actions = {a for i in inventory.items if str(i.kind) == "mcp_server" for a in i.actions}
    assert mcp_actions <= {"mcp.remove_direct", "plugin.enable", "plugin.disable"}
    # Only a Codex entry has its own `enabled` switch.
    switched = {
        i.client
        for i in inventory.items
        if str(i.kind) == "mcp_server" and {"plugin.enable", "plugin.disable"} & set(i.actions)
    }
    assert switched <= {"codex"}
    removable = {
        (i.client, i.name, str(i.scope))
        for i in inventory.items
        if "mcp.remove_direct" in i.actions
    }
    assert removable == {
        ("claude_code", "github", "user"),
        ("claude_code", "local-db", "local"),
        ("claude_code", "docs", "project"),
        ("claude_code", "old-search", "project"),
        ("codex", "neon", "user"),
        ("codex", "langfuse-data", "user"),
        ("codex", "aseprite", "user"),
        ("codex", "api-docs", "project"),
        ("codex", "neon", "project"),
        ("codex", "evil", "project"),
        ("cursor", "Neon", "user"),
        ("cursor", "n8n-mcp", "user"),
        ("cursor", "site-db", "project"),
    }


def test_remove_steps_for_each_client_and_scope(home, adapters):
    inventory = build_inventory(home)
    website = str(home / "work/website")

    local = remove_steps(adapters, _item(inventory, "claude_code", "local-db", "local"))[0]
    assert local.command == ["claude", "mcp", "remove", "-s", "local", "local-db"]
    assert local.cwd == website
    assert local.edit.key == ("projects", website, "mcpServers", "local-db")
    assert (local.edit.after, local.edit.check, local.shared_file) == (ABSENT, "entry", False)

    project = remove_steps(adapters, _item(inventory, "claude_code", "docs", "project"))[0]
    assert project.command == ["claude", "mcp", "remove", "-s", "project", "docs"]
    assert project.edit.path == str(home / "work/website/.mcp.json")
    assert (project.edit.check, project.shared_file) == ("file", True)

    codex = remove_steps(adapters, _item(inventory, "codex", "api-docs", "project"))[0]
    assert (codex.edit.fmt, codex.edit.key, codex.shared_file) == (
        "toml",
        ("mcp_servers", "api-docs"),
        True,
    )

    cursor = remove_steps(adapters, _item(inventory, "cursor", "Neon", "user"))[0]
    assert (cursor.edit.path, cursor.edit.key, cursor.shared_file) == (
        str(home / ".cursor/mcp.json"),
        ("mcpServers", "Neon"),
        False,
    )


def test_removal_is_refused_for_items_without_the_action(home, adapters):
    inventory = build_inventory(home)
    desktop = _item(inventory, "claude_desktop_code_tab", "team-proxy", "user")
    with pytest.raises(ValueError, match="cannot be removed"):
        remove_steps(adapters, desktop)


# Add skills: copy a plugin's self-contained skills into one client --------------------------

ALL_FOUND = {"claude_code", "codex", "cursor"}


def _skill_rows(home):
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}
    return adapters, skill_catalog(inventory, adapters)


def _claude_has(home, name):
    folder = home / ".claude/skills" / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Mine.\n---\n")


def test_add_skills_copies_each_self_contained_skill_once(home):
    # toolbox holds tidy and brainstorming (both work alone), rooted and reaching (they do not).
    add_skills_marketplace(home)
    _claude_has(home, "brainstorming")
    adapters, rows = _skill_rows(home)

    steps = plugin_skill_steps(adapters, PLUGIN, rows, "claude_code", ALL_FOUND)
    assert [(s.client, s.name) for s in steps] == [("claude_code", "tidy")]
    assert steps[0].copy.target == str(home / ".claude/skills/tidy")
    # Cursor reads Claude Code's folder, so it reads this copy too.
    assert steps[0].copy.readers == ["claude_code", "cursor"]

    # Codex has neither, so it gets both, in the shared folder Cursor reads as well.
    steps = plugin_skill_steps(adapters, PLUGIN, rows, "codex", ALL_FOUND)
    assert [s.name for s in steps] == ["brainstorming", "tidy"]
    assert {s.copy.target for s in steps} == {
        str(home / ".agents/skills/brainstorming"),
        str(home / ".agents/skills/tidy"),
    }
    assert all(s.copy.readers == ["codex", "cursor"] for s in steps)


def test_add_skills_names_what_it_leaves_out_and_why(home):
    add_skills_marketplace(home)
    _claude_has(home, "brainstorming")
    _, rows = _skill_rows(home)
    assert plugin_skills_left_out(PLUGIN, rows, "claude_code") == [
        {"name": "brainstorming", "why": "Claude Code already has it"},
        {"name": "reaching", "why": "needs the rest of the plugin"},
        {"name": "rooted", "why": "needs the rest of the plugin"},
    ]
    assert plugin_skills_left_out(PLUGIN, rows, "codex") == [
        {"name": "reaching", "why": "needs the rest of the plugin"},
        {"name": "rooted", "why": "needs the rest of the plugin"},
    ]


def test_add_skills_refuses_when_nothing_is_left(home):
    add_skills_marketplace(home)
    _claude_has(home, "brainstorming")
    _claude_has(home, "tidy")
    adapters, rows = _skill_rows(home)
    with pytest.raises(ValueError, match=r"^Claude Code has every skill in toolbox it can use$"):
        plugin_skill_steps(adapters, PLUGIN, rows, "claude_code", ALL_FOUND)


def test_folder_readers_is_shared_with_the_views():
    # The Library and Add missing ask the same question; Cursor reads Codex's .agents/skills.
    assert folder_readers("codex", {"cursor": object()}, {"codex", "cursor"}) == ["codex", "cursor"]
    assert folder_readers("cursor", {}, {"cursor"}) == ["cursor"]


# Sign-in checks never reach inside (review 2026-11-03) ---------------------------------------


@pytest.fixture
def lookups(name_lookups):
    """A public name, a private one and one that does not resolve; numbers and localhost
    resolve as usual (`name_lookups` in tests/conftest.py)."""
    name_lookups["public.example"] = "93.184.216.34"
    name_lookups["inside.example"] = "10.0.0.5"
    name_lookups["inside-v6.example"] = "fd00::5"
    name_lookups["unknown.example"] = None


def test_local_addresses_are_found_in_every_spelling(lookups):
    from kitden.changes.actions import is_local_address

    for url in (
        "http://127.1/mcp",
        "http://2130706433/mcp",
        "http://0x7f.0.0.1/mcp",
        "http://localhost./mcp",
        "http://169.254.169.254/latest",
        "http://10.1.2.3/",
        "http://192.168.0.1/",
        "http://100.64.0.1/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://0.0.0.0/",
        "https://inside.example/mcp",
        "https://inside-v6.example/mcp",
        "https://unknown.example/mcp",  # does not resolve
    ):
        assert is_local_address(url), url
    assert not is_local_address("https://public.example/mcp")
    # A name that does not resolve is what the caller says it is.
    assert not is_local_address("https://unknown.example/mcp", unknown=False)
    assert not is_local_address("https://public.example/mcp", unknown=False)


def test_a_public_server_cannot_send_the_check_to_a_local_address(lookups, monkeypatch):
    from kitden.changes import actions

    asked = []

    class Opener:
        def open(self, request, timeout):
            asked.append(request.full_url)
            raise OSError("no network in tests")

    monkeypatch.setattr(actions, "direct_opener", Opener)
    challenge = 'Bearer resource_metadata="http://127.0.0.1:9/.well-known/oauth-protected-resource"'
    assert actions._can_register("https://public.example/mcp", challenge) is None
    assert asked and not any("127.0.0.1" in url for url in asked)


def test_a_server_added_at_a_local_address_is_still_checked_there():
    from kitden.changes.actions import _reaches_inside

    assert not _reaches_inside("http://127.0.0.1:9/meta", "http://localhost:8080/mcp")
