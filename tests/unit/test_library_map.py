"""The Library map's data: clients, then plugins and skills by source, then what a plugin holds."""

import json
from pathlib import Path

from kitden.demo import build_demo_home, demo_adapters
from kitden.views.inventory import build_inventory
from kitden.views.library_map import library_map

MARKET = "demo-market"


def _read(home: Path):
    adapters = {a.id: a for a in demo_adapters(home)}
    return build_inventory(home, list(adapters.values()), []), adapters


def _map(home: Path, project: str | None = None) -> dict:
    inventory, adapters = _read(home)
    return library_map(inventory, adapters, project)


def _items(answer: dict) -> dict[str, dict]:
    """Every item on the map by name, with its group's key."""
    return {i["name"]: {**i, "group": g["key"]} for g in answer["groups"] for i in g["items"]}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_library_map_groups_by_source_in_order(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    answer = _map(home)
    groups = [(g["key"], g["name"], g["icon"], g["kind"]) for g in answer["groups"]]
    assert groups == [
        ("marketplace:cursor-public", "cursor-public", "store", "marketplace"),
        (f"marketplace:{MARKET}", MARKET, "store", "marketplace"),
        ("marketplace:openai-bundled", "openai-bundled", "store", "marketplace"),
        ("skills", "Your skills", "user-round", "skills"),
        ("settings", "Your settings", "settings", "settings"),
    ]
    items = _items(answer)
    assert items["superpowers"]["group"] == f"marketplace:{MARKET}"
    assert items["superpowers"]["source"] == MARKET
    assert items["brandkit"]["group"] == "skills"
    assert items["brandkit"]["source"] == "Your skills"
    # A plugin's own skills sit inside it, not under Your skills.
    assert "brainstorming" not in items
    # Inside a group, by name.
    names = [i["name"] for i in answer["groups"][3]["items"]]
    assert names == sorted(names, key=str.lower)

    # With a project picked, its own items come last, under Only this project.
    atlas = str(home / "work/atlas")
    picked = _map(home, atlas)
    assert [g["key"] for g in picked["groups"]][-1] == "project"
    project = picked["groups"][-1]
    assert (project["name"], project["icon"], project["kind"]) == (
        "Only this project",
        "folder",
        "project",
    )
    assert [i["name"] for i in project["items"]] == ["api-style"]
    assert _items(picked)["api-style"]["source"] == "Only this project"
    assert "api-style" not in _items(answer)


def test_library_map_clients_say_kitdens_own_facts(tmp_path):
    answer = _map(build_demo_home(tmp_path, "medium"))
    clients = {c["id"]: (c["name"], c["state"], c["words"]) for c in answer["clients"]}
    assert clients == {
        "claude_code": ("Claude Code", "on", "Connected"),
        "codex": ("Codex", "on", "Connected"),
        "cursor": ("Cursor", "via", "Via Claude Code"),
    }
    small = _map(build_demo_home(tmp_path / "small", "small"))
    assert {c["id"]: c["state"] for c in small["clients"]} == {
        "claude_code": "off",
        "codex": "missing",
        "cursor": "missing",
    }
    assert {c["id"]: c["words"] for c in small["clients"]}["codex"] == "Not installed"
    assert small["clients"][0]["words"] == "Not connected"


def test_a_plugin_counts_what_it_holds_and_never_says_n_of_m(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    items = _items(_map(home))
    superpowers = items["superpowers"]
    assert superpowers["kind"] == "plugin"
    assert superpowers["plugin"] == f"superpowers@{MARKET}"
    assert superpowers["inside"] == {
        "skills": ["brainstorming", "planning"],
        "commands": [],
        "agents": [],
        "hooks": [],
        "mcp_servers": [],
    }
    assert superpowers["count"] == 2
    assert items["pr-review"]["count"] == 1  # its pr-index server
    assert items["pr-review"]["by"]["claude_code"] == "off"
    # A part follows its plugin: no state per part, and no "N of M" anywhere.
    assert all(isinstance(name, str) for part in superpowers["inside"].values() for name in part)
    assert " of " not in json.dumps(items)
    # A skill or a hook holds nothing.
    assert "inside" not in items["brandkit"] and "count" not in items["brandkit"]

    # The large sample has a marketplace with thirty plugins and a plugin with twenty skills.
    large = _map(build_demo_home(tmp_path / "large", "large"))
    bench = next(g for g in large["groups"] if g["key"] == "marketplace:bench-market")
    assert len(bench["items"]) == 30
    assert max(i["count"] for i in bench["items"]) == 20


def test_cursor_via_claude_code_has_no_link_until_loaded(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    # Codex has test-helper; Claude Code does not have it yet, but can add it.
    folder = home / f".codex/plugins/cache/{MARKET}/test-helper/1.2.0"
    _write(folder / ".codex-plugin/plugin.json", {"name": "test-helper", "version": "1.2.0"})
    with (home / ".codex/config.toml").open("a") as config:
        config.write(f'\n[plugins."test-helper@{MARKET}"]\nenabled = true\n')
    items = _items(_map(home))

    # Not loaded yet: "via" and no link.
    helper = items["test-helper"]
    assert helper["by"] == {"codex": "on", "cursor": "via"}
    assert helper["through"] == {}
    # Loaded through Claude Code: On, and the link is the faint one.
    superpowers = items["superpowers"]
    assert superpowers["by"] == {"claude_code": "on", "cursor": "on"}
    assert superpowers["through"] == {"cursor": "claude_code"}
    # Off in Claude Code, so off in Cursor too.
    assert items["pr-review"]["by"] == {"claude_code": "off", "cursor": "off"}
    # Cursor's own plugin is a plain link.
    assert items["ui-kit"]["by"] == {"cursor": "on"} and items["ui-kit"]["through"] == {}
    # A skill Cursor reads from Claude Code's folder.
    assert items["brandkit"]["through"] == {"cursor": "claude_code"}


def test_a_project_rule_marks_here(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    atlas = home / "work/atlas"
    _write(
        atlas / ".claude/settings.local.json",
        {
            "enabledPlugins": {f"superpowers@{MARKET}": False},
            "skillOverrides": {"brandkit": "off"},
        },
    )
    shared = _items(_map(home))
    assert shared["superpowers"]["by"]["claude_code"] == "on"
    assert shared["brandkit"]["by"]["claude_code"] == "on"
    assert not any(i["here"] for i in shared.values())

    here = _items(_map(home, str(atlas)))
    assert here["superpowers"]["by"]["claude_code"] == "off"
    assert here["superpowers"]["here"] is True
    assert here["brandkit"]["by"]["claude_code"] == "off"
    assert here["brandkit"]["here"] is True
    # What follows the shared setup carries no tag.
    assert here["release-notes"]["here"] is False
    assert here["pr-review"]["here"] is False
    # The project's own items have their group, not the tag.
    assert here["api-style"]["here"] is False

    # A project's shared settings decide too: website turns superpowers off.
    website = _items(_map(home, str(home / "work/website")))
    assert website["superpowers"]["by"]["claude_code"] == "off"
    assert website["superpowers"]["here"] is True


def test_hooks_sit_under_your_settings(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    answer = _map(home)
    settings = next(g for g in answer["groups"] if g["key"] == "settings")
    hooks = {i["name"]: i for i in settings["items"]}
    assert set(hooks) == {"PreToolUse: Bash", "afterFileEdit"}
    assert all(h["kind"] == "hook" and h["source"] == "Your settings" for h in hooks.values())
    assert hooks["PreToolUse: Bash"]["by"] == {"claude_code": "on", "cursor": "on"}
    assert hooks["PreToolUse: Bash"]["through"] == {"cursor": "claude_code"}
    assert hooks["afterFileEdit"]["by"] == {"cursor": "on"}
    # Hooks are nowhere else.
    others = [i for g in answer["groups"] if g["key"] != "settings" for i in g["items"]]
    assert all(i["kind"] != "hook" for i in others)


def test_a_marketplace_plugin_no_client_has_is_not_on_the_map(tmp_path):
    items = _items(_map(build_demo_home(tmp_path, "medium")))
    # demo-market offers test-helper and db-tools, and no client has them.
    assert "test-helper" not in items and "db-tools" not in items
    # Account plugins are not on this computer.
    assert not any("account" in name.lower() for name in items)
    assert all(i["by"] for i in items.values())


def test_library_map_answer_has_no_paths_outside_technical(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    answer = _map(home, str(home / "work/atlas"))
    outside: list[str] = []

    def walk(value, key=None):
        if key == "technical":
            return
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, k)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, str):
            outside.append(value)

    walk(answer)
    assert outside
    assert not [s for s in outside if "/" in s or s.startswith("~") or str(home) in s]
    text = json.dumps(answer)
    for command in ("echo check", "server.js", "node"):
        assert command not in text
    # The paths are there, under Technical details.
    items = _items(answer)
    superpowers = items["superpowers"]["technical"]
    assert superpowers["path"].startswith(str(home / ".claude/plugins/cache"))
    assert superpowers["marketplace"] == str(home / ".claude/plugins/marketplaces" / MARKET)
    assert items["brandkit"]["technical"]["path"].startswith(str(home / ".claude/skills"))
    assert items["PreToolUse: Bash"]["technical"]["path"] == str(home / ".claude/settings.json")
