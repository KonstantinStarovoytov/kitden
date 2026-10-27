"""The Library map's data: clients, then plugins and skills by source, then what a plugin holds."""

import json
from dataclasses import replace
from pathlib import Path

from starlette.testclient import TestClient

from kitden.changes.engine import writable, writable_roots
from kitden.demo import build_demo_home, demo_adapters, demo_build
from kitden.model import Scope
from kitden.views.inventory import build_inventory
from kitden.views.library_map import library_map
from kitden.web.app import create_app

MARKET = "demo-market"
ORIGIN = "http://127.0.0.1:47800"


def _read(home: Path, broken: str | None = None):
    adapters = {a.id: a for a in demo_adapters(home)}
    if broken:

        def fail():
            raise ValueError("a file format Kitden does not know")

        adapters[broken].scan = fail
    return build_inventory(home, list(adapters.values()), []), adapters


def _map(home: Path, project: str | None = None, broken: str | None = None) -> dict:
    inventory, adapters = _read(home, broken)
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
    assert not any(any(i["here"].values()) for i in shared.values())

    here = _items(_map(home, str(atlas)))
    assert here["superpowers"]["by"]["claude_code"] == "off"
    # Per client: Cursor gets superpowers through Claude Code; only Claude Code is decided here.
    assert here["superpowers"]["here"] == {"claude_code": True, "cursor": False}
    assert here["brandkit"]["by"]["claude_code"] == "off"
    assert here["brandkit"]["here"] == {"claude_code": True, "cursor": False}
    # What follows the shared setup carries no tag.
    assert not any(here["release-notes"]["here"].values())
    assert not any(here["pr-review"]["here"].values())
    # The project's own items have their group, not the tag.
    assert not any(here["api-style"]["here"].values())
    # Local settings decide: "Use the shared rule…" can take the key out there.
    assert here["superpowers"]["can"]["local"] == ["claude_code"]
    assert here["brandkit"]["can"]["local"] == ["claude_code"]
    assert here["superpowers"]["can"]["shared"] == []

    # A project's shared settings decide too: website turns superpowers off.
    website = _items(_map(home, str(home / "work/website")))
    assert website["superpowers"]["by"]["claude_code"] == "off"
    assert website["superpowers"]["here"]["claude_code"] is True
    assert website["superpowers"]["can"]["shared"] == ["claude_code"]
    assert website["superpowers"]["can"]["local"] == []


def test_another_clients_project_copy_does_not_mark_claude_code(tmp_path):
    # atlas has its own Codex copy of brandkit; Claude Code still loads the user's copy there.
    home = build_demo_home(tmp_path, "medium")
    atlas = home / "work/atlas"
    copy = atlas / ".agents/skills/brandkit/SKILL.md"
    copy.parent.mkdir(parents=True)
    copy.write_text("---\nname: brandkit\ndescription: Brand kit.\n---\nUse it.\n")
    brandkit = _items(_map(home, str(atlas)))["brandkit"]
    assert brandkit["here"]["codex"] is True
    assert brandkit["here"]["claude_code"] is False
    assert brandkit["can"]["local"] == []


def test_a_skill_says_which_projects_turn_it_off_already(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inventory, _ = _read(home)
    ids = {Path(p.path).name: p.id for p in inventory.projects}
    _write(home / "work/atlas/.claude/settings.local.json", {"skillOverrides": {"brandkit": "off"}})
    _write(home / "work/website/.claude/settings.json", {"skillOverrides": {"brandkit": "on"}})
    items = _items(_map(home))
    assert items["brandkit"]["off_in"] == [ids["atlas"]]
    assert items["release-notes"]["off_in"] == []


def test_a_codex_skill_in_one_project_can_turn_off_that_copy(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    items = _items(_map(home, str(home / "work/atlas")))
    assert items["api-style"]["can"]["copy"] == ["codex"]
    # A skill of all projects has no such copy.
    assert items["code-review"]["can"]["copy"] == []


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


def test_each_item_names_the_inventory_items_of_each_client(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    atlas = home / "work/atlas"
    _write(
        atlas / ".claude/settings.local.json", {"enabledPlugins": {f"superpowers@{MARKET}": False}}
    )
    inventory, adapters = _read(home)
    by_id = {i.id: i for i in inventory.items}
    items = _items(library_map(inventory, adapters, str(atlas)))
    superpowers = items["superpowers"]["items"]
    assert set(superpowers) == {"claude_code", "cursor"}
    # The deciding one first: the project's local rule, then the user's install.
    assert [by_id[i].scope for i in superpowers["claude_code"]] == [Scope.LOCAL, Scope.USER]
    assert by_id[superpowers["cursor"][0]].client == "cursor"
    # Every client with a state has its ids; "via" has none.
    for item in items.values():
        assert set(item["items"]) == {c for c, s in item["by"].items() if s != "via"}
        assert all(item["items"].values())


def test_a_plugin_whose_state_kitden_does_not_know_stays_on_the_map(tmp_path):
    # Only Codex's plugin list knows whether calendar is on, and it gave no answer.
    items = _items(_map(build_demo_home(tmp_path, "large")))
    calendar = items["calendar"]
    assert calendar["group"] == "marketplace:openai-curated-remote"
    assert calendar["by"] == {"codex": "unknown"}
    assert calendar["items"]["codex"]


def test_a_plugin_with_no_marketplace_is_under_other_plugins(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inventory, adapters = _read(home)
    cursor = next(i for i in inventory.items if i.name == "ui-kit@cursor-public")
    inventory.items[inventory.items.index(cursor)] = replace(cursor, name="plugin 501")
    answer = library_map(inventory, adapters, None)
    other = next(g for g in answer["groups"] if g["key"] == "other")
    assert (other["name"], other["icon"], other["kind"]) == ("Other plugins", "puzzle", "other")
    assert [i["name"] for i in other["items"]] == ["plugin 501"]
    keys = [g["key"] for g in answer["groups"]]
    assert keys.index("other") == keys.index("skills") - 1  # after the marketplaces


def test_a_client_kitden_could_not_read_draws_no_link(tmp_path):
    answer = _map(build_demo_home(tmp_path, "medium"), broken="cursor")
    clients = {c["id"]: (c["state"], c["words"]) for c in answer["clients"]}
    assert clients["cursor"] == ("unreadable", "Could not read")
    items = _items(answer)
    assert not any("cursor" in i["by"] for i in items.values())
    # What another client has stays; what only Cursor had is not on the map.
    assert items["superpowers"]["by"] == {"claude_code": "on"}
    assert "ui-kit" not in items and "ui-polish" not in items


def test_the_route_answers_for_a_project_that_is_gone(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        gone = next(p for p in page.get("/api/projects").json() if p["path"].endswith("old-app"))
        assert not gone["exists"]
        for path in ["/api/library-map", "/api/gateway-view"]:
            response = page.get(f"{path}?project={gone['id']}")
            assert response.status_code == 200, path
        answer = page.get(f"/api/library-map?project={gone['id']}").json()
        assert answer["project"]["id"] == gone["id"]
        assert "superpowers" in _items(answer)
        assert page.get("/api/library-map?project=nope").status_code == 404


def test_each_item_says_what_details_can_offer(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    items = _items(_map(home))
    # superpowers: Codex can still add it; Claude Code can turn it off. Cursor is never offered:
    # it gets plugins through Claude Code, and has no switch of its own.
    assert items["superpowers"]["can"] == {
        "add": ["codex"],
        "off": ["claude_code"],
        "on": [],
        "remove": ["claude_code"],
        "project": [],
        "local": [],
        "shared": [],
    }
    # Off already: Claude Code can turn it on again, or remove it. A bundled plugin no marketplace
    # offers: nothing to add, only Codex's switch.
    assert items["pr-review"]["can"] == {
        "add": ["codex"],
        "off": [],
        "on": ["claude_code"],
        "remove": ["claude_code"],
        "project": [],
        "local": [],
        "shared": [],
    }
    assert items["browser"]["can"] == {
        "add": [],
        "off": ["codex"],
        "on": [],
        "remove": ["codex"],
        "project": [],
        "local": [],
        "shared": [],
    }
    assert items["ui-kit"]["can"] == {
        "add": [],
        "off": [],
        "on": [],
        "remove": [],
        "project": [],
        "local": [],
        "shared": [],
    }
    # A skill: each client that loads its own copy has a rule; Cursor has none.
    assert items["brandkit"]["can"] == {
        "add": ["codex"],
        "off": ["claude_code"],
        "remove": ["claude_code"],
        "project": [],
        "local": [],
        "shared": [],
        "copy": [],
    }
    assert items["code-review"]["can"] == {
        "add": ["claude_code"],
        "off": ["codex"],
        "remove": ["codex"],
        "project": [],
        "local": [],
        "shared": [],
        "copy": [],
    }
    assert items["ui-polish"]["can"] == {
        "add": ["claude_code", "codex"],
        "off": [],
        "remove": ["cursor"],
        "project": [],
        "local": [],
        "shared": [],
        "copy": [],
    }
    # A hook has no switch.
    assert items["PreToolUse: Bash"]["can"] == {}


def test_each_item_says_which_clients_can_remove_their_own_entry(tmp_path):
    # A link's x removes or turns off. A plugin's file entry and a skill's own folder can be
    # removed; Cursor's plugin (it gets it through Claude Code) and a skill read through another
    # client's folder cannot.
    home = build_demo_home(tmp_path, "medium")
    items = _items(_map(home))
    assert items["superpowers"]["can"]["remove"] == ["claude_code"]
    assert items["browser"]["can"]["remove"] == ["codex"]
    assert items["ui-kit"]["can"]["remove"] == []
    assert items["pr-review"]["can"]["remove"] == ["claude_code"]  # off, but its own entry
    assert items["ui-polish"]["can"]["remove"] == ["cursor"]
    assert items["shared-style"]["can"]["remove"] == []
    assert "remove" not in items["PreToolUse: Bash"]["can"]


def test_a_skill_says_which_clients_can_take_a_copy_cursor_too(tmp_path):
    # A drag onto a client adds the skill there: the skill catalog's id and its routes. Cursor
    # can take one when the catalog gives it a route; here it reads Claude Code's folder.
    home = build_demo_home(tmp_path, "medium")
    items = _items(_map(home))
    assert items["brandkit"]["skill"] == "brandkit@skills"
    assert items["brandkit"]["can"] == {
        "add": ["codex"],
        "off": ["claude_code"],
        "remove": ["claude_code"],
        "project": [],
        "local": [],
        "shared": [],
        "copy": [],
    }
    assert items["ui-polish"]["can"] == {
        "add": ["claude_code", "codex"],
        "off": [],
        "remove": ["cursor"],
        "project": [],
        "local": [],
        "shared": [],
        "copy": [],
    }
    # A plugin's can stays as it was: never Cursor.
    assert items["superpowers"]["can"]["add"] == ["codex"]
    inventory, adapters = _read(home)
    inventory.items[:] = [
        i for i in inventory.items if not (i.client == "cursor" and i.name == "brandkit")
    ]
    brandkit = _items(library_map(inventory, adapters, None))["brandkit"]
    assert "cursor" not in brandkit["by"]
    assert brandkit["can"]["add"] == ["codex", "cursor"]


def test_skill_rules_say_where_one_project_can_turn_a_skill_off(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inventory, adapters = _read(home)
    ids = {Path(p.path).name: p.id for p in inventory.projects}
    rules = library_map(inventory, adapters, None)["skill_rules"]
    assert rules["some"] is True
    # Only projects whose folder is there; one with no Claude Code settings yet cannot take a rule.
    assert rules["projects"][ids["website"]] == "ok"
    assert rules["projects"][ids["atlas"]] == "new"
    assert ids["old-app"] not in rules["projects"]
    # A project whose shared settings hold skillOverrides keeps its own rules.
    _write(home / "work/website/.claude/settings.json", {"skillOverrides": {"x": "off"}})
    rules = _map(home)["skill_rules"]
    assert rules["projects"][ids["website"]] == "own"
    # The user settings with skillOverrides: no one-project rule anywhere (it may not merge).
    settings = home / ".claude/settings.json"
    _write(settings, {**json.loads(settings.read_text()), "skillOverrides": {"y": "off"}})
    assert _map(home)["skill_rules"]["some"] is False


def test_details_of_a_skill_turned_off_in_one_project_say_so(tmp_path):
    # Claude Code's /skills menu writes skillOverrides in the project's settings.local.json.
    home = build_demo_home(tmp_path, "medium")
    atlas = home / "work/atlas"
    _write(atlas / ".claude/settings.local.json", {"skillOverrides": {"brandkit": "off"}})
    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        project = next(p for p in page.get("/api/projects").json() if p["path"] == str(atlas))
        url = f"/api/explain?kind=skill&name=brandkit&project={project['id']}"
        found = page.get(url).json()["definitions"]
        claude = next(d for d in found if d["client"] == "claude_code")
        assert claude["enabled"] == "off"
        assert claude["loads"] is False
        assert claude["why"] == "Does not load: it is turned off."
        # With no project picked, the shared setup still loads it.
        shared = page.get("/api/explain?kind=skill&name=brandkit").json()["definitions"]
        assert next(d for d in shared if d["client"] == "claude_code")["enabled"] == "on"


def test_turn_off_for_all_projects_acts_only_on_the_users_own_entry(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    atlas = home / "work/atlas"
    # The project's shared settings turn two plugins on: one the user has off, one on.
    plugins = {f"pr-review@{MARKET}": True, f"superpowers@{MARKET}": True}
    _write(atlas / ".claude/settings.json", {"enabledPlugins": plugins})
    here = _items(_map(home, str(atlas)))
    # The project's entry decides: only "Turn off in this project…", never its shared file.
    assert here["pr-review"]["can"]["off"] == []
    assert here["superpowers"]["can"]["off"] == []
    # With no project picked, the user's own entry decides.
    assert _items(_map(home))["superpowers"]["can"]["off"] == ["claude_code"]
    # A user skill a project's rule decides: no rule for all projects from there either.
    _write(atlas / ".claude/settings.local.json", {"skillOverrides": {"brandkit": "on"}})
    assert _items(_map(home, str(atlas)))["brandkit"]["can"]["off"] == []


def test_a_project_only_skill_gets_no_rule_for_all_projects(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    website = home / "work/website"
    skill = website / ".claude/skills/site-notes/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: site-notes\ndescription: Notes for the site.\n---\nWrite notes.\n")
    items = _items(_map(home, str(website)))
    assert items["site-notes"]["group"] == "project"
    assert items["site-notes"]["by"]["claude_code"] == "on"
    # Not the user's settings file: Details offers a rule in this project instead.
    assert items["site-notes"]["can"]["off"] == []


def test_turn_on_and_remove_never_act_on_a_projects_own_entry(tmp_path):
    # website's shared settings turn superpowers off. Turn on and Remove would write that
    # committed file (and Remove would bring it back on there), so Claude Code is left out; Details
    # say where its setting comes from instead.
    home = build_demo_home(tmp_path, "medium")
    website = str(home / "work/website")
    off = _items(_map(home, website))["superpowers"]
    assert off["by"]["claude_code"] == "off"
    assert (off["can"]["on"], off["can"]["remove"], off["can"]["off"]) == ([], [], [])
    assert off["can"]["project"] == ["claude_code"]
    # A project that turns on a plugin that is off for all projects: no Turn off, no Remove, no
    # x for that client either (they would act on the project's entry).
    atlas = home / "work/atlas"
    _write(atlas / ".claude/settings.json", {"enabledPlugins": {"pr-review@demo-market": True}})
    on = _items(_map(home, str(atlas)))["pr-review"]
    assert on["by"]["claude_code"] == "on"
    assert (on["can"]["on"], on["can"]["remove"], on["can"]["off"]) == ([], [], [])
    assert on["can"]["project"] == ["claude_code"]
    # For all projects the same plugin keeps its own Turn on and Remove.
    everywhere = _items(_map(home))["pr-review"]
    assert everywhere["can"]["on"] == ["claude_code"] and everywhere["can"]["project"] == []


def test_skill_rules_for_a_project_in_a_repository_subfolder(tmp_path):
    # atlas is a git repository; atlas/web is a known project in it.
    home = build_demo_home(tmp_path, "medium")
    inventory, adapters = _read(home)
    web = next(p.id for p in inventory.projects if p.path.endswith("atlas/web"))
    atlas = home / "work/atlas"
    (atlas / ".git").mkdir()
    (atlas / "web/.claude").mkdir()
    # The root has no .claude folder: the rule goes in web's own file, so web is not "new".
    assert _map(home)["skill_rules"]["projects"][web] == "ok"
    # The rule would go in the root's file while web's own local file holds skillOverrides.
    (atlas / ".claude").mkdir()
    _write(atlas / "web/.claude/settings.local.json", {"skillOverrides": {"x": "off"}})
    assert _map(home)["skill_rules"]["projects"][web] == "own"


def test_a_project_whose_rule_file_kitden_does_not_write_is_outside(tmp_path):
    # api is a known project outside home in the repository /srv/repo, which is not a project:
    # Claude Code keeps api's local settings at that root, where the engine does not write.
    home = build_demo_home(tmp_path, "medium")
    repo = tmp_path / "srv/repo"
    api = repo / "api"
    (repo / ".git").mkdir(parents=True)
    (repo / ".claude").mkdir()
    _write(api / ".claude/settings.local.json", {"skillOverrides": {"brandkit": "off"}})
    state = home / ".claude.json"
    data = json.loads(state.read_text())
    data["projects"][str(api)] = {}
    state.write_text(json.dumps(data))
    inventory, adapters = _read(home)
    ids = {p.path: p.id for p in inventory.projects}
    rules = library_map(inventory, adapters, None)["skill_rules"]
    assert rules["projects"][ids[str(api)]] == "outside"
    assert rules["outside"] == {ids[str(api)]: "repo"}
    # api's local file decides brandkit, but nothing offers to take its key out.
    brandkit = _items(library_map(inventory, adapters, str(api)))["brandkit"]
    assert brandkit["can"]["project"] == ["claude_code"]
    assert brandkit["can"]["local"] == []
    # The page asks the engine's own test.
    roots = writable_roots(home, inventory)
    assert not writable(repo / ".claude/settings.local.json", home, roots)
    assert writable(api / ".claude/settings.local.json", home, roots)
    # The root as a known project too: Kitden writes there.
    data["projects"][str(repo)] = {}
    state.write_text(json.dumps(data))
    inventory, adapters = _read(home)
    rules = library_map(inventory, adapters, None)["skill_rules"]
    assert rules["projects"][ids[str(api)]] == "own"  # api's own local file holds skillOverrides
    assert rules["outside"] == {}
