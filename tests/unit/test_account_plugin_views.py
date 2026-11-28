"""The plugins of the Claude account on the Library, in Context and in their commands."""

import json
import os
from pathlib import Path

import pytest

from kitden.changes.actions import plugin_steps, skill_rule_steps
from kitden.clients.claude_code import ACCOUNT_PLUGIN_HINT, ACCOUNT_REQUIRED_HINT
from kitden.model import Enabled, ItemKind, Scope
from kitden.system import claude_desktop_dir
from kitden.views import words
from kitden.views.commands import commands_for
from kitden.views.context_view import context_view
from kitden.views.inventory import build_inventory, default_adapters
from kitden.views.library import library_list
from kitden.views.library_map import library_map
from tests.conftest import make_home
from tests.unit.test_context_claude_log import assistant, list_entry, write_chat

GARDEN = "garden@inline"
MANIFESTS = "local-agent-mode-sessions/*/*/rpm/manifest.json"


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "claude_app/6.28899.6")
    for root in (".codex", ".cursor"):
        (home / root).mkdir()
    # The account with plugins is the one the app wrote last.
    for manifest in claude_desktop_dir(home).glob(MANIFESTS):
        at = 2_000_000_000 if json.loads(manifest.read_text())["plugins"] else 1_000_000_000
        os.utime(manifest, (at, at))
    return home


def read(home: Path):
    adapters = {a.id: a for a in default_adapters(home)}
    return build_inventory(home, list(adapters.values()), []), adapters


def item(inventory, name: str):
    (found,) = [
        i for i in inventory.items if i.name == name and i.kind is ItemKind.PLUGIN and not i.project
    ]
    return found


def chat(home: Path, skills: dict, entrypoint: str = "claude-desktop") -> None:
    content = "\n".join(f"- {n}: {t}" for n, t in skills.items())
    entry = list_entry(list(skills), content, folder=str(home), entrypoint=entrypoint)
    write_chat(home, "p", "chat", [entry, assistant("claude-opus-5-5")], 100)


def context_rows(home: Path) -> dict:
    inventory, _ = read(home)
    answer = context_view(inventory, home, home / ".codex", None, {})
    (claude,) = [c for c in answer["clients"] if c["client"] == "claude_code"]
    return {s["name"]: s for s in claude["skills"]}


def test_the_library_map_has_a_group_of_its_own_for_them(home):
    inventory, adapters = read(home)
    answer = library_map(inventory, adapters, None)
    groups = {g["key"]: g for g in answer["groups"]}
    account = groups["account"]
    assert (account["name"], account["icon"], account["kind"]) == (
        "From your Claude account",
        "cloud",
        "account",
    )
    entries = {i["name"]: i for i in account["items"]}
    assert set(entries) == {"garden", "nimbus", "tower"}
    garden = entries["garden"]
    assert garden["by"] == {"claude_code": "on"}
    assert garden["source"] == "From your Claude account"
    assert garden["note"] == ACCOUNT_PLUGIN_HINT
    assert garden["can"]["off"] == ["claude_code"]
    assert garden["can"]["remove"] == []  # no install to remove
    assert garden["inside"]["skills"] == ["planting", "rivals"]
    assert garden["inside"]["agents"] == ["scout"]
    assert garden["inside"]["mcp_servers"] == ["seed-catalog"]
    assert garden["technical"]["path"].endswith("rpm/plugin_01GARDEN0000000000000000")
    assert "marketplace" not in garden["technical"]
    # Required by the organization: no switch, and Details say why.
    tower = entries["tower"]
    assert (tower["by"], tower["can"]["on"], tower["note"]) == (
        {"claude_code": "off"},
        [],
        ACCOUNT_REQUIRED_HINT,
    )
    # The group comes after the marketplaces and before the others.
    keys = [g["key"] for g in answer["groups"]]
    assert keys.index("account") == len([g for g in answer["groups"] if g["kind"] == "marketplace"])


def test_its_parts_do_not_show_as_your_skills(home):
    inventory, adapters = read(home)
    answer = library_map(inventory, adapters, None)
    names = {i["name"] for g in answer["groups"] for i in g["items"]}
    assert not names & {"rivals", "planting", "forecast", "policy"}


def test_the_list_puts_the_accounts_rows_in_that_group(home):
    settings = {"enabledPlugins": {"old@synced": True}}
    (home / ".claude/settings.json").write_text(json.dumps(settings))
    inventory, adapters = read(home)
    answer = library_list(inventory, adapters, None)
    (group,) = [g for g in answer["groups"] if g["key"] == "account"]
    names = [i["name"] for i in group["items"]]
    assert names[:3] == ["garden", "nimbus", "tower"]
    # Kept in the account: the Unknown row and a `@synced` key, after the app's plugins.
    assert set(names[3:]) == {"old", "Claude account plugins and connectors"}
    assert not [g for g in answer["groups"] if g["key"] == "other"]
    garden = next(i for i in group["items"] if i["name"] == "garden")
    assert garden["cells"]["claude_code"]["state"] == "on"
    assert garden["cells"]["codex"]["reason"] == words.ACCOUNT_ONLY_CLAUDE
    assert garden["cells"]["cursor"]["reason"] == words.ACCOUNT_ONLY_CLAUDE
    assert {p["name"] for p in garden["parts"]} == {"planting", "rivals", "scout", "seed-catalog"}


def test_turning_it_off_for_all_projects_writes_its_key_in_the_users_settings(home):
    inventory, adapters = read(home)
    (step,) = plugin_steps(adapters, item(inventory, GARDEN), enable=False)
    assert (step.scope, step.edit.key, step.edit.after, step.command) == (
        Scope.USER,
        ("enabledPlugins", GARDEN),
        False,
        None,
    )


def test_a_project_can_turn_it_off_in_its_local_settings(home, tmp_path):
    project = home / "work/shop"
    (project / ".claude").mkdir(parents=True)
    (home / ".claude.json").write_text(json.dumps({"projects": {str(project): {}}}))
    inventory, adapters = read(home)
    target = {"client": "claude_code", "item": item(inventory, GARDEN).id}
    (picked,) = [p for p in inventory.projects if p.path == str(project)]
    params = {"scope": "project", "project": picked.id, "state": "off"}
    (step,) = skill_rule_steps(adapters, inventory, home, [target], params)
    assert step.edit.path == str(project / ".claude/settings.local.json")
    assert (step.edit.key, step.edit.after) == (("enabledPlugins", GARDEN), False)
    # One the organization requires has no switch there either.
    target = {"client": "claude_code", "item": item(inventory, "tower@inline").id}
    with pytest.raises(ValueError, match="organization requires"):
        skill_rule_steps(adapters, inventory, home, [target], params)


def test_a_project_that_turns_it_off_turns_its_skills_off_there(home):
    project = home / "work/shop"
    (project / ".claude").mkdir(parents=True)
    (project / ".claude/settings.local.json").write_text(
        json.dumps({"enabledPlugins": {GARDEN: False}})
    )
    (home / ".claude.json").write_text(json.dumps({"projects": {str(project): {}}}))
    inventory, adapters = read(home)
    answer = library_map(inventory, adapters, str(project))
    (garden,) = [i for g in answer["groups"] for i in g["items"] if i["name"] == "garden"]
    assert garden["by"] == {"claude_code": "off"}
    assert garden["here"] == {"claude_code": True}


def test_its_commands_say_where_to_change_it_and_run_nothing(home):
    inventory, adapters = read(home)
    (command,) = commands_for(item(inventory, GARDEN), adapters)
    assert (command.command, command.note) == (None, ACCOUNT_PLUGIN_HINT)


def test_context_names_the_plugin_and_offers_its_switch(home):
    chat(home, {"garden:rivals": "Lists the rivals of a garden shop.", "tower:policy": "Reads."})
    rows = context_rows(home)
    rivals = rows["garden:rivals"]
    assert rivals["source"] == "Plugin garden from your Claude account"
    assert rivals["note"] == words.NOTE_PLUGIN_SWITCH
    assert rivals["plugin_switch"]["label"] == "Turn off garden"
    assert rivals["plugin_switch"]["action"] == "plugin.disable"
    # A plugin the organization requires: no switch, and the note says why.
    policy = rows["tower:policy"]
    assert policy["plugin_switch"] is None
    assert policy["source"] == "Plugin tower from your Claude account"


def test_a_required_plugins_skill_says_why_it_has_no_switch(home):
    (home / ".claude/settings.json").write_text(
        json.dumps({"enabledPlugins": {"tower@inline": True}})
    )
    chat(home, {"tower:policy": "Reads the house rules."})
    policy = context_rows(home)["tower:policy"]
    assert (policy["plugin_switch"], policy["note"]) == (None, ACCOUNT_REQUIRED_HINT)


def test_after_a_terminal_chat_its_skills_are_not_the_next_chats(home):
    chat(home, {"alpha": "Does alpha."}, entrypoint="cli")
    assert "garden:rivals" not in context_rows(home)
    chat(home, {"alpha": "Does alpha."})
    assert context_rows(home)["garden:rivals"]["side"] is None  # the next app chat lists it


def test_a_plugin_turned_off_takes_its_skills_out_of_the_next_chat(home):
    (home / ".claude/settings.json").write_text(json.dumps({"enabledPlugins": {GARDEN: False}}))
    chat(home, {"garden:rivals": "Lists the rivals of a garden shop."})
    rivals = context_rows(home)["garden:rivals"]
    assert rivals["state"] == "off"
    assert rivals["plugin_switch"]["action"] == "plugin.enable"


def test_the_inventory_marks_the_state_and_the_switch(home):
    inventory, _ = read(home)
    garden = item(inventory, GARDEN)
    assert (garden.enabled, garden.actions) == (Enabled.ON, ("plugin.disable",))
    assert item(inventory, "tower@inline").actions == ()
    assert item(inventory, "nimbus@inline").actions == ()
