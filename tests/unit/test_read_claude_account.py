"""The plugins of the Claude account, read from the Claude app's folder (claude_account.py)."""

import json
import os
from pathlib import Path

import pytest

from kitden.clients.base import PLUGIN_DISABLE, Reader
from kitden.clients.claude_account import account_plugins, is_account_plugin
from kitden.clients.claude_code import (
    ACCOUNT_OFF_HINT,
    ACCOUNT_PLUGIN_HINT,
    ACCOUNT_REQUIRED_HINT,
    ClaudeCodeAdapter,
)
from kitden.model import Enabled, ItemKind, Scope, SourceKind
from kitden.system import claude_desktop_dir
from kitden.views.match import plugin_of
from tests.conftest import make_home

FIXTURE = "claude_app/6.28899.6"
GARDEN = "garden@inline"
MANIFESTS = "local-agent-mode-sessions/*/*/rpm/manifest.json"


@pytest.fixture
def home(tmp_path):
    return make_home(tmp_path, FIXTURE)


def rpm(home: Path) -> Path:
    (manifest,) = [
        p for p in claude_desktop_dir(home).glob(MANIFESTS) if json.loads(p.read_text())["plugins"]
    ]
    return manifest.parent


def newest_first(home: Path) -> None:
    """The account with plugins is the one the app wrote last."""
    for manifest in claude_desktop_dir(home).glob(MANIFESTS):
        at = 2_000_000_000 if json.loads(manifest.read_text())["plugins"] else 1_000_000_000
        os.utime(manifest, (at, at))


def scan(home: Path):
    return ClaudeCodeAdapter(home, read_version=lambda: None).scan()


def plugins(home: Path) -> dict:
    items = scan(home).items
    return {i.name: i for i in items if i.kind is ItemKind.PLUGIN and i.scope is Scope.USER}


def settings(home: Path, enabled: dict) -> None:
    (home / ".claude/settings.json").write_text(json.dumps({"enabledPlugins": enabled}))


def test_the_plugins_are_read_from_the_account_the_app_wrote_last(home):
    newest_first(home)
    read = Reader("claude_code")
    found = {p.id: p for p in account_plugins(claude_desktop_dir(home), read)}
    # A row whose folder leads out of `rpm`, or whose folder is gone, has nothing to load.
    assert set(found) == {GARDEN, "nimbus@inline", "tower@inline"}
    assert found[GARDEN].folder == rpm(home) / "plugin_01GARDEN0000000000000000"
    assert (found[GARDEN].required, found[GARDEN].off_in_account) == (False, False)
    assert found["nimbus@inline"].off_in_account is True
    assert found["tower@inline"].required is True
    assert found["tower@inline"].on_by_default is False
    assert read.problems == []


def test_an_older_account_folder_is_not_read(home):
    for manifest in claude_desktop_dir(home).glob(MANIFESTS):
        at = 1_000_000_000 if json.loads(manifest.read_text())["plugins"] else 2_000_000_000
        os.utime(manifest, (at, at))
    assert account_plugins(claude_desktop_dir(home), Reader("claude_code")) == []


def test_no_app_folder_means_no_account_plugins(tmp_path):
    assert account_plugins(tmp_path / "no-app", Reader("claude_code")) == []


def test_a_broken_manifest_is_a_problem_of_its_own(home):
    newest_first(home)
    manifest = rpm(home) / "manifest.json"
    manifest.write_text("{not json")
    read = Reader("claude_code")
    assert account_plugins(claude_desktop_dir(home), read) == []
    assert [p.path for p in read.problems] == [str(manifest)]


def test_each_plugin_is_a_claude_code_plugin_with_its_own_state_and_hint(home):
    newest_first(home)
    found = plugins(home)
    garden, nimbus, tower = found[GARDEN], found["nimbus@inline"], found["tower@inline"]
    assert all(is_account_plugin(p) for p in (garden, nimbus, tower))
    assert (garden.enabled, garden.change_hint) == (Enabled.ON, ACCOUNT_PLUGIN_HINT)
    assert garden.source.kind is SourceKind.FILE
    assert garden.source.path == str(home / ".claude/settings.json")
    assert garden.source.key_path == "enabledPlugins.garden@inline"
    # Off in the account: the app does not give it, and the switch is the account's.
    assert (nimbus.enabled, nimbus.change_hint) == (Enabled.OFF, ACCOUNT_OFF_HINT)
    assert nimbus.source.kind is SourceKind.ACCOUNT
    # Required, and off until a settings file says true (`defaultEnabled: false`).
    assert (tower.enabled, tower.change_hint) == (Enabled.OFF, ACCOUNT_REQUIRED_HINT)
    assert tower.source.kind is SourceKind.ACCOUNT


def test_the_switch_is_offered_only_where_claude_code_decides(home):
    newest_first(home)
    adapter = ClaudeCodeAdapter(home, read_version=lambda: None)
    found = plugins(home)
    assert adapter.item_actions(found[GARDEN]) == (PLUGIN_DISABLE,)
    assert adapter.item_actions(found["nimbus@inline"]) == ()
    assert adapter.item_actions(found["tower@inline"]) == ()


def test_the_users_settings_turn_it_off_and_on(home):
    newest_first(home)
    settings(home, {GARDEN: False, "tower@inline": True})
    found = plugins(home)
    assert (found[GARDEN].enabled, found[GARDEN].state_scope) == (Enabled.OFF, Scope.USER)
    assert found["tower@inline"].enabled is Enabled.ON
    settings(home, {GARDEN: "yes"})  # only false turns it off
    assert plugins(home)[GARDEN].enabled is Enabled.ON


def test_a_synced_key_does_not_decide_the_apps_copy(home):
    newest_first(home)
    settings(home, {"garden@synced": False})
    found = plugins(home)
    assert found[GARDEN].enabled is Enabled.ON
    # The key itself is still the account's row, as before.
    synced = [i for i in scan(home).items if i.name == "garden@synced"]
    assert [i.scope for i in synced] == [Scope.ACCOUNT]


def test_unreadable_settings_leave_the_state_unknown(home):
    newest_first(home)
    (home / ".claude/settings.json").write_text("{broken")
    assert plugins(home)[GARDEN].enabled is Enabled.UNKNOWN


def test_its_skills_and_servers_follow_it_and_name_it(home):
    newest_first(home)
    settings(home, {GARDEN: False})
    parts = [i for i in scan(home).items if i.scope is Scope.PLUGIN and plugin_of(i) == GARDEN]
    assert {(str(i.kind), i.name) for i in parts} == {
        ("skill", "rivals"),
        ("skill", "planting"),
        ("mcp_server", "seed-catalog"),
    }
    assert {i.enabled for i in parts} == {Enabled.OFF}


def test_the_plugin_folder_is_known_for_what_it_holds(home):
    newest_first(home)
    folders = ClaudeCodeAdapter(home, read_version=lambda: None).plugin_folders()
    assert folders[GARDEN] == rpm(home) / "plugin_01GARDEN0000000000000000"


def test_a_plugin_without_a_name_is_left_out(home):
    newest_first(home)
    (rpm(home) / "plugin_01GARDEN0000000000000000/.claude-plugin/plugin.json").write_text("{}")
    assert GARDEN not in plugins(home)


def test_the_switch_writes_one_key_with_no_command(home):
    newest_first(home)
    adapter = ClaudeCodeAdapter(home, read_version=lambda: None)
    step = adapter.plugin_step(plugins(home)[GARDEN], enable=False)
    assert (step.mechanism, step.command) == ("format_preserving_edit", None)
    assert (step.edit.path, step.edit.key, step.edit.after) == (
        str(home / ".claude/settings.json"),
        ("enabledPlugins", GARDEN),
        False,
    )
    settings(home, {GARDEN: False})
    step = adapter.plugin_step(plugins(home)[GARDEN], enable=True)
    assert step.edit.after is True


def test_no_switch_for_a_plugin_the_organization_requires(home):
    newest_first(home)
    adapter = ClaudeCodeAdapter(home, read_version=lambda: None)
    with pytest.raises(ValueError, match="cannot be turned on"):
        adapter.plugin_step(plugins(home)["tower@inline"], enable=True)
