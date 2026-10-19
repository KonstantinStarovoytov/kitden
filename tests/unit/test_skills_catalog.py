"""The skills catalog: skills in plugins on disk and in the clients' own folders (phase 2)."""

import json
import os
from pathlib import Path

import pytest

import kitden.clients.base as base
from kitden.views.catalog import search
from kitden.views.inventory import build_inventory, default_adapters
from kitden.views.skills import front_matter, read_skill, skill_catalog
from tests.conftest import make_home, write_cursor_fixture_state

PLUGIN = "toolbox@claude-plugins-official"


def _write(path: Path, text: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if mode is not None:
        path.chmod(mode)


def add_skills_marketplace(home: Path) -> Path:
    """A marketplace clone with one plugin that holds four skills, and the superpowers plugin
    the fixture has installed in Claude Code."""
    root = home / ".claude/plugins/marketplaces/claude-plugins-official"
    _write(
        root / ".claude-plugin/marketplace.json",
        json.dumps(
            {
                "name": "claude-plugins-official",
                "plugins": [
                    {"name": "toolbox", "source": "./plugins/toolbox"},
                    {"name": "superpowers", "source": "./plugins/superpowers"},
                ],
            }
        ),
    )
    skills = root / "plugins/toolbox/skills"
    _write(
        skills / "tidy/SKILL.md",
        "---\nname: tidy\ndescription: >\n  Tidy up the code\n  you touch.\n---\n"
        "# Tidy\nSee [the rules](references/rules.md).\n",
    )
    _write(skills / "tidy/references/rules.md", "Back to [the skill](../SKILL.md).\n")
    _write(skills / "tidy/scripts/run.sh", "#!/bin/sh\necho tidy\n", 0o755)
    _write(skills / "tidy/scripts/check", "#!/usr/bin/env python3\nprint(1)\n", 0o755)
    _write(
        skills / "rooted/SKILL.md",
        "---\nname: rooted\ndescription: Needs its plugin.\n---\n"
        "Run ${CLAUDE_PLUGIN_ROOT}/scripts/go.sh\n",
    )
    _write(
        skills / "reaching/SKILL.md",
        "---\nname: reaching\ndescription: 'Reads a shared file.'\n---\n"
        "Read ../../assets/logo.svg and ../tidy/SKILL.md first.\n",
    )
    _write(
        skills / "brainstorming/SKILL.md",
        "---\nname: brainstorming\ndescription: Think first.\n---\n",
    )
    _write(
        root / "plugins/superpowers/skills/brainstorming/SKILL.md",
        "---\nname: brainstorming\ndescription: Think first.\n---\n",
    )
    return home


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return add_skills_marketplace(home)


def _rows(home):
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}
    return {r["id"]: r for r in skill_catalog(inventory, adapters)}


def test_front_matter_reads_plain_quoted_and_block_values(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text(
        "---\nname: demo\ndescription: >-\n  One line\n\n  and another.\n"
        "allowed-tools:\n  - Read\nuser-invocable: true\n---\n# Demo\n"
    )
    meta = front_matter(path)
    assert meta["name"] == "demo"
    assert meta["description"] == "One line and another."
    assert meta["user-invocable"] == "true"
    path.write_text("# No front matter\n")
    assert front_matter(path) == {}


def test_a_skill_in_a_plugin_lists_its_files_and_marks_scripts(home):
    tidy = _rows(home)[f"tidy@{PLUGIN}"]
    assert tidy["description"] == "Tidy up the code you touch."
    assert tidy["from"] == PLUGIN and tidy["marketplace"] == "claude-plugins-official"
    assert tidy["self_contained"] is True and tidy["needs"] == []
    assert tidy["files"] == [
        {"path": "SKILL.md", "script": False},
        {"path": "references/rules.md", "script": False},
        {"path": "scripts/check", "script": True},
        {"path": "scripts/run.sh", "script": True},
    ]
    # No client has it, so every client found here can take a copy.
    assert tidy["installed"] == {}
    assert tidy["routes"] == {"claude_code": "ready", "codex": "ready", "cursor": "ready"}


def test_a_skill_that_needs_its_plugin_has_no_route(home):
    rows = _rows(home)
    rooted = rows[f"rooted@{PLUGIN}"]
    assert rooted["self_contained"] is False and rooted["routes"] == {}
    assert rooted["needs"] == ["mentions the plugin root"]
    reaching = rows[f"reaching@{PLUGIN}"]
    assert reaching["description"] == "Reads a shared file."
    assert reaching["needs"] == [
        "points outside its folder: ../../assets/logo.svg, ../tidy/SKILL.md"
    ]


def test_installed_copies_say_how_each_client_loads_them(home):
    rows = _rows(home)
    # Claude Code has the superpowers plugin; Cursor imports Claude Code plugins.
    via_plugin = rows["brainstorming@superpowers@claude-plugins-official"]
    assert via_plugin["installed"] == {"claude_code": "Via plugin", "cursor": "Via plugin"}
    assert via_plugin["routes"] == {"codex": "ready"}
    # The same skill name from another plugin: nothing loads it yet from that plugin, but a
    # standalone copy of the name would still count.
    other = rows[f"brainstorming@{PLUGIN}"]
    assert other["installed"] == {}
    # Skills already in a client's own folder, with no plugin here: rows of their own.
    brandkit = rows["brandkit@skills"]
    assert brandkit["from"] == "Claude Code"
    assert brandkit["installed"] == {"claude_code": "Installed", "cursor": "Via Claude Code"}
    assert brandkit["routes"] == {"codex": "ready"}
    docker = rows["docker-expert@skills"]
    assert docker["from"] == "Codex and Cursor"  # ~/.agents/skills is read by both
    assert docker["installed"] == {"codex": "Installed", "cursor": "Installed"}
    langfuse = rows["langfuse@skills"]
    assert langfuse["installed"] == {"codex": "Installed", "cursor": "Via Codex"}
    assert langfuse["path"] == str(home / ".codex/skills/langfuse")


def test_search_finds_skills_by_name_and_by_their_plugin(home):
    rows = list(_rows(home).values())
    assert [r["name"] for r in search(rows, "tidy")] == ["tidy"]
    by_plugin = search(rows, "toolbox")
    assert {r["name"] for r in by_plugin} == {"brainstorming", "reaching", "rooted", "tidy"}
    assert all(r["match"] == "name" for r in by_plugin)
    # A word found only in the description is marked, so the page can group it apart.
    assert [(r["name"], r["match"]) for r in search(rows, "file")] == [("reaching", "text")]


def test_a_skill_folder_is_read_again_only_when_it_changes(tmp_path):
    folder = tmp_path / "demo"
    _write(folder / "SKILL.md", "---\nname: demo\ndescription: First.\n---\n")
    assert read_skill(folder)["description"] == "First."
    _write(folder / "SKILL.md", "---\nname: demo\ndescription: Second.\n---\n")
    os.utime(folder / "SKILL.md", ns=(1, 2_000_000_000_000_000_000))
    assert read_skill(folder)["description"] == "Second."
    os.symlink(tmp_path, folder / "out")
    info = read_skill(folder)
    assert info["self_contained"] is False and "link" in info["needs"][0]
