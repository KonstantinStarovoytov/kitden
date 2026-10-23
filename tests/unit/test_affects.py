"""Which clients a change to one definition reaches, and where (Details, before any action)."""

from types import SimpleNamespace

import pytest

from kitden.clients.cursor import REACTIVE_KEY
from kitden.model import Client, ClientStatus, Item, ItemKind, Scope, Source, SourceKind
from kitden.views.affects import affects
from kitden.views.inventory import Inventory, build_inventory
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
    item = _item(inventory, "codex", "pixel-art", Scope.USER, "/.agents/skills/")
    assert affects(inventory, item) == {
        "clients": ["codex", "cursor"],
        "scope": "all",
        "note": "Cursor reads Codex's folder",
    }
    # Cursor also loads docker-expert from ~/.codex/skills, so this copy's removal leaves it.
    item = _item(inventory, "codex", "docker-expert", Scope.USER, "/.agents/skills/")
    assert affects(inventory, item) == {"clients": ["codex"], "scope": "all", "note": None}


def test_a_claude_code_user_plugin_reaches_cursor_which_loads_its_plugins(inventory):
    item = _item(
        inventory, "claude_code", "claude-md-management@claude-plugins-official", Scope.USER
    )
    assert affects(inventory, item) == {
        "clients": ["claude_code", "cursor"],
        "scope": "all",
        "note": "Cursor loads Claude Code's plugins",
    }
    # Cursor has superpowers from its own marketplace too, so it keeps that one.
    item = _item(inventory, "claude_code", "superpowers@claude-plugins-official", Scope.USER)
    assert affects(inventory, item) == {"clients": ["claude_code"], "scope": "all", "note": None}


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


def test_a_reader_that_keeps_its_own_copy_is_not_named(tmp_path):
    # Cursor reads Codex's folder, but it loads its own tidy too: removing Codex's leaves it.
    shared = tmp_path / ".agents/skills/tidy/SKILL.md"
    own = tmp_path / ".cursor/skills/tidy/SKILL.md"
    items = [_skill(shared, "codex", "codex"), _skill(shared, "cursor", "codex")]
    items.append(_skill(own, "cursor", "cursor"))
    assert affects(SimpleNamespace(items=items), items[0]) == {
        "clients": ["codex"],
        "scope": "all",
        "note": None,
    }


def _plugin(client, name, owner, kind=SourceKind.FILE):
    source = Source(kind=kind, path=f"/h/{client}/{name}.json", owner_client=owner)
    return Item(client=client, kind=ItemKind.PLUGIN, name=name, source=source, scope=Scope.USER)


def test_cursor_is_not_named_for_a_plugin_it_also_has_on_its_own():
    clients = [Client(id="claude_code", display_name="Claude Code", status=ClientStatus.FOUND)]
    claude = _plugin("claude_code", "x@a", "claude_code")
    imported = _plugin("cursor", "x@a", "claude_code", SourceKind.OTHER_CLIENT_FOLDER)
    mine = _plugin("cursor", "x@cursor-public", "cursor")
    alone = Inventory(clients=clients, items=[claude, imported])
    assert affects(alone, claude)["clients"] == ["claude_code", "cursor"]
    both = Inventory(clients=clients, items=[claude, imported, mine])
    assert affects(both, claude) == {"clients": ["claude_code"], "scope": "all", "note": None}
