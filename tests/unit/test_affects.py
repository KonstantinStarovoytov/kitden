"""Which clients a change to one definition reaches, and where (Details, before any action)."""

from types import SimpleNamespace

import pytest

from kitden.clients.cursor import REACTIVE_KEY
from kitden.model import Item, ItemKind, Scope, Source, SourceKind
from kitden.views.affects import affects
from kitden.views.inventory import build_inventory
from tests.conftest import make_home, write_cursor_fixture_state


@pytest.fixture
def inventory(tmp_path):
    # Cursor first: its fixture also has .claude files, and the Claude Code ones must win.
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return build_inventory(home)


def _item(inventory, client, name, scope, folder=""):
    return next(
        i
        for i in inventory.items
        if (i.client, i.name, i.scope) == (client, name, scope) and folder in str(i.source.path)
    )


def test_a_skill_in_a_shared_folder_reaches_every_reader(inventory):
    item = _item(inventory, "codex", "docker-expert", Scope.USER, "/.agents/skills/")
    assert affects(inventory, item) == {
        "clients": ["codex", "cursor"],
        "scope": "all",
        "note": "Cursor reads Codex's folder",
    }


def test_a_claude_code_user_plugin_reaches_cursor_which_loads_its_plugins(inventory):
    item = _item(inventory, "claude_code", "superpowers@claude-plugins-official", Scope.USER)
    assert affects(inventory, item) == {
        "clients": ["claude_code", "cursor"],
        "scope": "all",
        "note": "Cursor loads Claude Code's plugins",
    }


def test_a_project_plugin_does_not_reach_cursor(inventory):
    item = _item(inventory, "claude_code", "superpowers@claude-plugins-official", Scope.PROJECT)
    one = {"clients": ["claude_code"], "scope": "project", "note": None}
    assert affects(inventory, item) == one


def test_a_local_entry_reaches_one_project(inventory):
    item = _item(inventory, "claude_code", "local-db", Scope.LOCAL)
    one = {"clients": ["claude_code"], "scope": "project", "note": None}
    assert affects(inventory, item) == one


def test_with_cursor_import_off_a_claude_code_plugin_reaches_only_claude_code(tmp_path):
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home, {REACTIVE_KEY: {"importPluginsFromClaudeOnBoot": False}})
    inventory = build_inventory(home)
    item = _item(inventory, "claude_code", "superpowers@claude-plugins-official", Scope.USER)
    assert affects(inventory, item) == {"clients": ["claude_code"], "scope": "all", "note": None}


def _skill(path, client, owner):
    source = Source(kind=SourceKind.FOLDER, path=str(path), owner_client=owner)
    return Item(client=client, kind=ItemKind.SKILL, name="tidy", source=source, scope=Scope.USER)


def test_each_other_reader_is_named_in_the_note(tmp_path):
    # Made up: no real folder has three readers today, but each one still gets its words.
    path = tmp_path / "skills/tidy/SKILL.md"
    items = [_skill(path, c, "claude_code") for c in ("cursor", "codex", "claude_code")]
    assert affects(SimpleNamespace(items=items), items[2]) == {
        "clients": ["claude_code", "codex", "cursor"],
        "scope": "all",
        "note": "Codex reads Claude Code's folder; Cursor reads Claude Code's folder",
    }


def test_a_folder_no_client_owns_reaches_its_readers_without_a_note(tmp_path):
    path = tmp_path / ".agents/skills/tidy/SKILL.md"
    items = [_skill(path, "codex", "shared"), _skill(path, "cursor", "shared")]
    assert affects(SimpleNamespace(items=items), items[0]) == {
        "clients": ["codex", "cursor"],
        "scope": "all",
        "note": None,
    }
