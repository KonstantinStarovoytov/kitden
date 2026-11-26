"""The same actions wherever a thing is shown: the server's one answer for a skill's switch, a
Codex skill and server turned on again, off servers on the Gateway, and the reasons where a client
has no switch."""

import tomllib
from pathlib import Path

import pytest

from kitden.changes.actions import SKILL_SWITCHES
from kitden.clients.codex import CodexAdapter
from kitden.demo import build_demo_home, demo_adapters
from kitden.model import ItemKind
from kitden.views import words
from kitden.views.context_view import context_view
from kitden.views.gateway_view import gateway_view
from kitden.views.inventory import build_inventory
from kitden.views.library import _hook_why


def _read(home: Path):
    adapters = demo_adapters(home)
    return build_inventory(home, adapters, []), {a.id: a for a in adapters}


def _off_skill(home: Path) -> Path:
    skill = home / ".agents/skills/code-review/SKILL.md"
    config = home / ".codex/config.toml"
    config.write_text(
        f'{config.read_text()}\n[[skills.config]]\npath = "{skill}"\nenabled = false\n'
    )
    return skill


def test_a_skills_switch_takes_each_clients_states():
    assert SKILL_SWITCHES == {"claude_code": ("on", "name-only", "off"), "codex": ("on", "off")}


def test_a_codex_skill_turns_on_again_by_its_own_entry(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    _off_skill(home)
    inventory, adapters = _read(home)
    codex: CodexAdapter = adapters["codex"]
    item = next(i for i in inventory.items if i.client == "codex" and i.name == "code-review")
    step = codex.skill_rule_step(item, on=True)
    assert step.edit is not None and step.edit.after["enabled"] is True
    other = next(i for i in inventory.items if i.client == "codex" and i.name == "langfuse")
    with pytest.raises(ValueError, match=r"langfuse is on already\."):
        codex.skill_rule_step(other, on=True)


def test_context_gives_an_off_codex_skill_its_switch(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    _off_skill(home)
    inventory, _ = _read(home)
    answer = context_view(inventory, home, home / ".codex", None, {}, anywhere=True)
    codex = next(c for c in answer["clients"] if c["client"] == "codex")
    skill = next(s for s in codex["skills"] if s["name"] == "code-review")
    assert (skill["state"], skill["switch"]) == ("off", ["on", "off"])


def test_a_codex_server_that_is_off_is_on_the_gateway_with_its_switch(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inventory, adapters = _read(home)
    rows = {r["name"]: r for rows in gateway_view(inventory, None)["groups"].values() for r in rows}
    assert rows["sqlite"]["off"] == ["codex"]
    assert rows["sqlite"]["stays"] == words.OFF_STAYS.format("sqlite")
    item = next(
        i
        for i in inventory.items
        if i.client == "codex" and i.name == "sqlite" and i.kind is ItemKind.MCP_SERVER
    )
    assert "plugin.enable" in item.actions
    step = adapters["codex"].plugin_step(item, True)
    assert step.edit is not None and step.edit.key == ("mcp_servers", "sqlite", "enabled")
    # An untrusted project's server is off because Codex skips the file: no switch, a reason.
    scratch = next(i for i in inventory.items if i.client == "codex" and i.name == "scratch")
    assert not {"plugin.enable", "plugin.disable"} & set(scratch.actions)
    assert scratch.change_hint == words.UNTRUSTED.format("sandbox")
    on = tomllib.loads((home / ".codex/config.toml").read_text())["mcp_servers"]["docs"]
    assert "enabled" not in on


def test_cursor_skills_and_hooks_say_why_they_have_no_switch(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inventory, _ = _read(home)
    answer = context_view(inventory, home, home / ".codex", None, {}, anywhere=True)
    cursor = next(c for c in answer["clients"] if c["client"] == "cursor")
    notes = {s["note"] for s in cursor["skills"]}
    assert words.CURSOR_NO_SWITCH_NOTE in notes
    assert _hook_why(None, "codex") == words.HOOKS_NOT_READ  # pyright: ignore[reportArgumentType]
    assert _hook_why(None, "claude_code") == words.HOOKS_ONLY_SHOWN  # pyright: ignore[reportArgumentType]
