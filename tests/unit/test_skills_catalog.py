"""The skills catalog: skills in plugins on disk and in the clients' own folders (phase 2)."""

import json
import os
import sqlite3
from pathlib import Path

import pytest

import kitden.clients.base as base
from kitden.views.catalog import search
from kitden.views.inventory import build_inventory, default_adapters
from kitden.views.skills import front_matter, read_skill, skill_catalog
from tests.conftest import CURSOR_DB, make_home, write_cursor_fixture_state

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


def test_a_plugin_that_is_off_does_not_count_as_having_its_skills(home):
    # Claude Code has superpowers turned off: the same skill name from another plugin can go
    # to Claude Code again.
    settings = home / ".claude/settings.json"
    settings.write_text(
        settings.read_text().replace(
            '"superpowers@claude-plugins-official": true',
            '"superpowers@claude-plugins-official": false',
        )
    )
    other = _rows(home)[f"brainstorming@{PLUGIN}"]
    assert "claude_code" not in other["installed"]
    assert other["routes"].get("claude_code") == "ready"


def test_installed_copies_say_how_each_client_loads_them(home):
    rows = _rows(home)
    # Claude Code has the superpowers plugin; Cursor imports Claude Code plugins.
    via_plugin = rows["brainstorming@superpowers@claude-plugins-official"]
    assert via_plugin["installed"] == {"claude_code": "Via plugin", "cursor": "Via plugin"}
    assert via_plugin["routes"] == {"codex": "ready"}
    # The same skill name from another plugin: those clients have it already, so they take
    # no copy.
    other = rows[f"brainstorming@{PLUGIN}"]
    assert other["installed"] == {"claude_code": "Via plugin", "cursor": "Via plugin"}
    assert other["routes"] == {"codex": "ready"}
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


GLEAN = "glean@cursor-public"


def _skill(folder: Path, name: str) -> None:
    _write(folder / name / "SKILL.md", f"---\nname: {name}\ndescription: The {name} skill.\n---\n")


def add_cursor_plugin(home: Path) -> Path:
    """A Cursor plugin with two downloaded versions: the old one has skill a only, the new one
    has a and b. A hidden folder is never a version, even when it is the newest."""
    plugin = home / ".cursor/plugins/cache/cursor-public/glean"
    _skill(plugin / "old/skills", "a")
    _skill(plugin / "new/skills", "a")
    _skill(plugin / "new/skills", "b")
    _skill(plugin / ".partial/skills", "c")
    os.utime(plugin / "old", (1, 1))
    os.utime(plugin / "new", (2, 2))
    os.utime(plugin / ".partial", (3, 3))
    return plugin


def install_in_cursor(home: Path, plugin_id: str) -> None:
    """Add a user plugin to Cursor's install records."""
    key = "cursor.plugins.installedIds.123|no-workspace"
    with sqlite3.connect(home / CURSOR_DB) as con:
        (value,) = con.execute("SELECT value FROM ItemTable WHERE key = ?", (key,)).fetchone()
        records = [*json.loads(value), {"id": plugin_id, "sources": ["user"]}]
        con.execute("INSERT INTO ItemTable VALUES (?, ?)", (key, json.dumps(records)))


def test_skills_inside_cursor_plugins_are_listed_from_the_newest_version(home):
    plugin = add_cursor_plugin(home)
    rows = {r["id"]: r for r in _rows(home).values() if r["plugin"] == GLEAN}
    assert set(rows) == {f"a@{GLEAN}", f"b@{GLEAN}"}
    a = rows[f"a@{GLEAN}"]
    assert a["path"] == str(plugin / "new/skills/a")
    assert a["from"] == GLEAN and a["marketplace"] == "cursor-public"
    assert a["description"] == "The a skill." and a["category"] is None
    # Not installed in Cursor here, so every client found can take a copy.
    assert a["installed"] == {}
    assert a["routes"] == {"claude_code": "ready", "codex": "ready", "cursor": "ready"}


def test_a_cursor_plugin_skill_can_go_to_claude_code_and_codex(home):
    add_cursor_plugin(home)
    install_in_cursor(home, GLEAN)
    a = _rows(home)[f"a@{GLEAN}"]
    assert a["installed"] == {"cursor": "Via plugin"}
    assert a["routes"] == {"claude_code": "ready", "codex": "ready"}


def test_a_skill_cursor_loads_from_its_plugin_counts_in_other_plugins_too(home):
    # The scan has no items for the skills inside Cursor's plugins; the plugin folder says.
    add_cursor_plugin(home)
    install_in_cursor(home, GLEAN)
    toolbox = home / ".claude/plugins/marketplaces/claude-plugins-official/plugins/toolbox"
    _skill(toolbox / "skills", "a")
    a = _rows(home)[f"a@{PLUGIN}"]
    assert a["installed"] == {"cursor": "Via plugin"}
    assert a["routes"] == {"claude_code": "ready", "codex": "ready"}


def test_a_cursor_plugin_skill_is_not_listed_again_as_your_own(home):
    add_cursor_plugin(home)
    _skill(home / ".claude/skills", "a")
    rows = [r for r in _rows(home).values() if r["name"] == "a"]
    assert [r["id"] for r in rows] == [f"a@{GLEAN}"]


def test_a_plugin_skill_has_its_plugin_category(home):
    path = home / ".claude/plugins/marketplaces/claude-plugins-official/.claude-plugin"
    listed = json.loads((path / "marketplace.json").read_text())
    listed["plugins"][0]["category"] = "Developer Tools"
    (path / "marketplace.json").write_text(json.dumps(listed))
    rows = _rows(home)
    toolbox = [r for r in rows.values() if r["plugin"] == PLUGIN]
    assert len(toolbox) == 4 and {r["category"] for r in toolbox} == {"Development"}
    assert rows["brainstorming@superpowers@claude-plugins-official"]["category"] is None
    assert rows["brandkit@skills"]["category"] is None


def test_a_long_line_does_not_slow_the_skill_list(tmp_path):
    # A minified script made reading ~500 skills take 9 s (2026-10-20): the "../" search was
    # quadratic on long runs of path characters. It must stay linear.
    import time

    skill = tmp_path / "packed"
    _write(skill / "SKILL.md", "---\nname: packed\ndescription: Packed.\n---\nRead ../notes.md\n")
    _write(skill / "dist/app.js", "a/b." * 20000 + "\n")
    started = time.monotonic()
    info = read_skill(skill)
    assert time.monotonic() - started < 0.5
    assert info["needs"] == ["points outside its folder: ../notes.md"]
