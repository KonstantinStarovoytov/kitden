"""Which clients a change to one definition reaches, and where (Details, before any action)."""

import pytest

from kitden.model import Scope
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
