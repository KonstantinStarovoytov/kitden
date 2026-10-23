"""The Library: what each client has on this computer and what it can add, in one list."""

import json
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.clients.codex import CodexAdapter
from kitden.clients.cursor import REACTIVE_KEY, CursorAdapter
from kitden.demo import build_demo_home
from kitden.model import FindingType, Gateway
from kitden.views.findings import find_findings, mark_gateways
from kitden.views.inventory import LastGood, build_inventory, default_adapters, keep_last_good
from kitden.views.library import library
from kitden.views.load_map import load_map
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_local_gateway_views import POST, page_for
from tests.unit.test_skills_catalog import (
    PLUGIN,
    add_cursor_plugin,
    add_skills_marketplace,
    install_in_cursor,
)

ORIGIN = "http://127.0.0.1:47800"
DOCUMENTS = "documents@openai-curated"
GLEAN = "glean@cursor-public"
OFFICIAL = "claude-plugins-official"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _skill(folder: Path, name: str, body: str = "") -> None:
    _write(
        folder / name / "SKILL.md",
        f"---\nname: {name}\ndescription: The {name} skill.\n---\n{body}",
    )


def add_documents(home: Path) -> Path:
    """Codex's curated marketplace with one plugin, documents, holding three skills that work
    alone. Codex has it installed; Claude Code and Cursor cannot install it."""
    curated = home / ".codex/.tmp/plugins"
    entry = {
        "name": "documents",
        "description": "Read and write office files",
        "category": "Productivity",
        "source": {"source": "local", "path": "./plugins/documents"},
    }
    listed = {"name": "openai-curated", "plugins": [entry]}
    _write(curated / ".agents/plugins/marketplace.json", json.dumps(listed))
    for name in ("docx", "pptx", "xlsx"):
        _skill(curated / "plugins/documents/skills", name)
    config = home / ".codex/config.toml"
    config.write_text(config.read_text() + f'\n[plugins."{DOCUMENTS}"]\nenabled = true\n')
    return home


def _home(base_dir: Path, cursor_flags: dict | None = None) -> Path:
    """All three clients, Claude Code's marketplace with toolbox, Codex's with documents, and
    Cursor's glean plugin (installed in Cursor, two skills that work alone)."""
    home = make_home(base_dir, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home, cursor_flags)
    add_skills_marketplace(home)
    add_documents(home)
    add_cursor_plugin(home)
    install_in_cursor(home, GLEAN)
    return home


@pytest.fixture
def home(tmp_path):
    return _home(tmp_path)


def _library(home: Path, kind: str = "plugin", **options) -> dict:
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}
    return library(inventory, adapters, None, gateway_registered=False, kind=kind, **options)


def _row(answer: dict, name: str, source: str | None = None) -> dict:
    return next(r for r in answer["rows"] if r["name"] == name and source in (None, r["source"]))


def _names(answer: dict) -> list[tuple]:
    return [(r["name"], r["source"]) for r in answer["rows"]]


def _cell(state="none", word=None, add=None, reason=None) -> dict:
    return {
        "state": state,
        "where": None,
        "origin": None,
        "route": None,
        "stale_at": None,
        "items": [],
        "word": word,
        "add": add,
        "reason": reason,
    }


CODEX_HINT = "Codex plugins are for all projects."


def _add(
    action,
    label,
    plugin=None,
    skill=None,
    marketplace=None,
    warn=None,
    project_place=False,
    project_hint=None,
    project_only=False,
) -> dict:
    return {
        "action": action,
        "label": label,
        "plugin": plugin,
        "skill": skill,
        "marketplace": marketplace,
        "item": None,
        "warn": warn,
        "project_place": project_place,
        "project_hint": project_hint,
        "project_only": project_only,
    }


def test_only_found_clients_are_columns(tmp_path):
    two = make_home(tmp_path / "two", "claude_code/2.1.283", "codex/0.159.2")
    answer = _library(two)
    assert answer["columns"] == [
        {"id": "claude_code", "name": "Claude Code", "mark": "CC", "hidden": False, "note": None},
        {"id": "codex", "name": "Codex", "mark": "CX", "hidden": False, "note": None},
    ]
    assert answer["rows"]
    assert all(list(r["cells"]) == ["claude_code", "codex"] for r in answer["rows"])

    one = make_home(tmp_path / "one", "codex/0.159.2")
    answer = _library(one, "mcp_server")
    assert [c["id"] for c in answer["columns"]] == ["codex"]
    assert answer["rows"]
    assert all(list(r["cells"]) == ["codex"] for r in answer["rows"])

    nothing = tmp_path / "none/home"
    nothing.mkdir(parents=True)
    answer = _library(nothing, show="all")
    assert (answer["columns"], answer["rows"], answer["counts"]["plugin"]) == ([], [], 0)


def test_codex_plugin_offers_add_skills_to_claude_code(home):
    row = _row(_library(home), "documents")
    assert (row["mine"], row["offer"], row["lookup"]) == (True, DOCUMENTS, DOCUMENTS)
    assert (row["category"], row["description"]) == ("Productivity", "Read and write office files")
    assert row["cells"]["codex"]["state"] == "on"
    assert row["cells"]["claude_code"] == _cell(
        add=_add("plugin.skills", "+ Add skills", DOCUMENTS)
    )
    # Cursor can't install it either, and Claude Code has no way to it: Cursor gets the skills.
    assert row["cells"]["cursor"]["add"]["label"] == "+ Add skills"


def test_cursor_add_skills_in_a_project_says_it_is_for_all_projects(home):
    inventory, adapters = build_inventory(home), {a.id: a for a in default_adapters(home)}
    website = str(home / "work/website")
    answer = library(inventory, adapters, website, gateway_registered=False, kind="plugin")
    hint = _row(answer, "documents")["cells"]["cursor"]["add"]["project_hint"]
    assert hint.startswith("Adds its skills for all projects. To add a plugin to one project")


def test_cursor_plugin_offers_add_skills_to_claude_code_and_codex(home):
    # A second Cursor plugin with no skills, and a third whose only skill needs the plugin.
    cache = home / ".cursor/plugins/cache/cursor-public"
    _write(cache / "empty/v1/.cursor-plugin/plugin.json", "{}")
    _skill(cache / "rooted/v1/skills", "deploy", "Run ${CURSOR_PLUGIN_ROOT}/go.sh\n")
    for plugin_id in ("empty@cursor-public", "rooted@cursor-public"):
        install_in_cursor(home, plugin_id)
    answer = _library(home)

    glean = _row(answer, "glean")
    assert (glean["source"], glean["lookup"], glean["offer"]) == ("cursor-public", GLEAN, None)
    assert (glean["description"], glean["category"]) == ("", None)
    assert glean["cells"]["cursor"]["state"] == "on"
    for client in ("claude_code", "codex"):
        assert glean["cells"][client] == _cell(add=_add("plugin.skills", "+ Add skills", GLEAN))

    empty = _row(answer, "empty")["cells"]["codex"]
    assert empty == _cell(reason="Codex can't install this plugin, and it has no skills to copy.")
    rooted = _row(answer, "rooted", "cursor-public")["cells"]["claude_code"]
    assert rooted == _cell(
        reason="Claude Code can't install this plugin, and its skills need the rest of it."
    )


def test_cursor_gets_via_claude_code_for_a_claude_plugin(home, tmp_path):
    toolbox = _row(_library(home, show="new"), "toolbox")
    assert toolbox["cells"]["cursor"] == _cell(
        "via",
        word="Via Claude Code",
        reason="Cursor loads Claude Code's plugins. Add it to Claude Code.",
    )
    assert toolbox["cells"]["claude_code"] == _cell(
        add=_add("plugin.install", "+ Add", PLUGIN, project_place=True)
    )
    # Cursor does not import the plugins of Claude's account.
    account = _row(_library(home), "Claude account plugins and connectors")
    assert account["cells"]["claude_code"]["state"] == "unk"
    assert account["cells"]["cursor"] == _cell(
        reason="Cursor can't install this plugin, and it has no skills to copy."
    )

    # With Include Third-Party Plugins off, Cursor takes the skills that work alone instead.
    strict = _home(tmp_path / "strict", {REACTIVE_KEY: {"thirdPartyExtensibilityEnabled": False}})
    toolbox = _row(_library(strict, show="new"), "toolbox")
    assert toolbox["cells"]["cursor"] == _cell(add=_add("plugin.skills", "+ Add skills", PLUGIN))
    # And a skill that needs the plugin has no way into Cursor.
    rooted = _row(_library(strict, "skill", show="new"), "rooted")
    assert rooted["cells"]["cursor"] == _cell(
        reason="Cursor can't install the plugin this skill needs."
    )


def test_add_skills_turns_into_has_its_skills_when_all_are_there(home):
    for name in ("docx", "pptx"):
        _skill(home / ".claude/skills", name)
    row = _row(_library(home), "documents")
    assert row["cells"]["claude_code"]["add"]["label"] == "+ Add skills"  # xlsx is still missing

    _skill(home / ".claude/skills", "xlsx")
    row = _row(_library(home), "documents")
    assert row["cells"]["claude_code"] == _cell(
        "done",
        word="Has its skills",
        reason="Claude Code already has every skill it can take from this plugin.",
    )
    # Cursor reads Claude Code's skills folder, so it has them all as well.
    assert row["cells"]["cursor"] == _cell(
        "done",
        word="Has its skills",
        reason="Cursor already has every skill it can take from this plugin.",
    )


def test_skills_a_client_loads_from_another_plugin_count_as_had(home):
    # Cursor's superpowers holds brainstorming, which Claude Code loads from its own superpowers.
    cursor_copy = home / ".cursor/plugins/cache/cursor-public/superpowers/1a2b3c4/skills"
    _skill(cursor_copy, "brainstorming")
    row = _row(_library(home), "superpowers", "cursor-public")
    assert row["cells"]["claude_code"] == _cell(
        "done",
        word="Has its skills",
        reason="Claude Code already has every skill it can take from this plugin.",
    )
    assert row["cells"]["codex"] == _cell(
        add=_add("plugin.skills", "+ Add skills", "superpowers@cursor-public")
    )

    # One more skill: Claude Code can take that one, and the review says it has a twin.
    _skill(cursor_copy, "planning")
    row = _row(_library(home), "superpowers", "cursor-public")
    warn = (
        "Claude Code already has superpowers from claude-plugins-official. "
        "It will load skills from both."
    )
    assert row["cells"]["claude_code"] == _cell(
        add=_add("plugin.skills", "+ Add skills", "superpowers@cursor-public", warn=warn)
    )
    assert row["cells"]["codex"]["add"]["warn"] is None


def test_a_plugin_in_another_project_is_not_offered_again(home):
    settings = home / "work/website/.claude/settings.json"
    data = json.loads(settings.read_text())
    data["enabledPlugins"][PLUGIN] = True
    settings.write_text(json.dumps(data))
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}

    def toolbox(project):
        answer = library(
            inventory, adapters, project, gateway_registered=False, kind="plugin", show="all"
        )
        return _row(answer, "toolbox")["cells"]["claude_code"]

    assert toolbox(str(home / "work/website"))["state"] == "on"
    elsewhere = _cell(reason="Claude Code has it in another project.")
    assert toolbox(None) == elsewhere
    assert toolbox(str(home / "work/api")) == elsewhere


def test_skill_that_needs_its_plugin_offers_add_the_plugin(home):
    answer = _library(home, "skill", show="new")
    rooted = _row(answer, "rooted")
    assert rooted["offer"] == f"rooted@{PLUGIN}" and rooted["source"] == PLUGIN
    assert rooted["cells"]["claude_code"] == _cell(
        add=_add("plugin.install", "+ Add the plugin", PLUGIN, project_place=True)
    )
    # Codex first adds the marketplace the plugin comes from.
    assert rooted["cells"]["codex"]["add"] == _add(
        "plugin.install", "+ Add the plugin", PLUGIN, marketplace=OFFICIAL, project_hint=CODEX_HINT
    )
    # Cursor loads the plugin once Claude Code has it.
    assert rooted["cells"]["cursor"] == _cell(
        "via",
        word="Via Claude Code",
        reason="Cursor loads Claude Code's plugins. Add the plugin to Claude Code.",
    )
    tidy = _row(answer, "tidy")
    assert tidy["cells"]["codex"] == _cell(
        add=_add("skill.install", "+ Add", skill=f"tidy@{PLUGIN}", project_place=True)
    )


def test_own_skill_that_reaches_outside_its_folder_says_why(home):
    _skill(home / ".claude/skills", "notes", "Read ../shared/notes.md\n")
    notes = _row(_library(home, "skill"), "notes")
    assert notes["source"] == "Claude Code" and notes["cells"]["claude_code"]["state"] == "on"
    assert notes["cells"]["codex"] == _cell(
        reason="This skill uses files outside its folder, so it can't be copied."
    )


def test_skill_cells_keep_the_state_the_scan_found(home):
    answer = _library(home, "skill", show="all")
    # Codex has pixel-art turned off in config.toml.
    codex = _row(answer, "pixel-art")["cells"]["codex"]
    assert (codex["state"], codex["where"]) == ("off", None) and codex["items"]
    # Details can find a skill's definitions by name.
    brandkit = _row(answer, "brandkit")
    assert (brandkit["mine"], brandkit["lookup"]) == (True, "brandkit")
    assert brandkit["cells"]["claude_code"]["where"] is None
    assert brandkit["cells"]["cursor"]["route"] == "through Claude Code's folder"
    assert brandkit["cells"]["codex"]["add"]["action"] == "skill.install"
    # Where the scan shows nothing, the skill list says how the client gets it.
    superpowers = _row(answer, "brainstorming", f"superpowers@{OFFICIAL}")
    assert superpowers["cells"]["cursor"] == {**_cell("on"), "route": "from a plugin"}


def test_show_mine_new_and_all(home):
    mine = _library(home)
    new = _library(home, show="new")
    every = _library(home, show="all")
    assert _names(mine) == [
        ("browser", "openai-bundled"),
        ("Claude account plugins and connectors", None),
        ("documents", "openai-curated"),
        ("glean", "cursor-public"),
        ("gmail", "openai-curated-remote"),
        ("pdf", "openai-primary-runtime"),
        ("plugin 4800 (name not stored locally)", None),
        ("superpowers", OFFICIAL),
        ("superpowers", "cursor-public"),
    ]
    assert all(r["mine"] for r in mine["rows"])
    assert _names(new) == [("toolbox", OFFICIAL)]
    assert not new["rows"][0]["mine"] and new["rows"][0]["lookup"] is None
    # All: what is on this computer first, then what can be added.
    assert _names(every) == _names(mine) + _names(new)
    assert (mine["counts"]["plugin"], new["counts"]["plugin"], every["counts"]["plugin"]) == (
        9,
        1,
        10,
    )
    assert set(mine["counts"]) == {
        "mcp_server",
        "plugin",
        "skill",
        "hook",
        "marketplace",
        "instructions",
    }
    # Tabs without a catalog always show what is on this computer.
    assert _library(home, "hook", show="new")["rows"] == _library(home, "hook")["rows"]
    assert _library(home, "hook")["categories"] == []


def test_categories_filter_rows_but_not_counts(home):
    every = _library(home, show="all")
    assert every["categories"] == [{"name": "Productivity", "count": 1}]
    productive = _library(home, show="all", category="Productivity")
    assert _names(productive) == [("documents", "openai-curated")]
    assert productive["counts"] == every["counts"]
    assert productive["categories"] == every["categories"]


def test_search_reports_matches_the_show_choice_hides(home):
    hidden_by_choice = _library(home, q="toolbox")
    assert (hidden_by_choice["rows"], hidden_by_choice["more"]) == ([], 1)
    assert hidden_by_choice["counts"]["plugin"] == 0
    found = _library(home, show="new", q="toolbox")
    assert (_names(found), found["more"]) == ([("toolbox", OFFICIAL)], 0)
    assert _library(home, show="all", q="toolbox")["more"] == 0
    assert _library(home)["more"] == 0
    # The plugin's name finds its skills too. Claude Code has a skill named brainstorming (from
    # superpowers), so that one counts as on this computer.
    skills = _library(home, "skill", q="toolbox")
    assert (_names(skills), skills["more"]) == ([("brainstorming", PLUGIN)], 3)
    # On tabs without a catalog the search looks at names, and nothing is hidden by a choice.
    servers = _library(home, "mcp_server", q="neon")
    assert {r["name"] for r in servers["rows"]} == {"neon", "Neon"} and servers["more"] == 0


def test_tabs_without_a_catalog_find_any_part_of_a_name(home):
    # "hub" finds github. Plugins and skills rank by catalog.search.
    servers = _library(home, "mcp_server", q="hub")
    assert _names(servers) == [("github", None)]
    assert servers["counts"]["mcp_server"] == 1
    assert _names(_library(home, "mcp_server", q="FUSE")) == [("langfuse-data", None)]
    assert _names(_library(home, "hook", q="bash")) == [("PreToolUse: Bash", None)]
    assert _names(_library(home, "marketplace", q="-mkt")) == [("team-mkt", None)]
    assert _library(home, "plugin", q="hub")["counts"]["mcp_server"] == 1
    assert _library(home, "plugin", show="all", q="ools")["rows"] == []


def _list_plugins(marketplace_json: Path, *entries: dict) -> None:
    listed = json.loads(marketplace_json.read_text())
    listed["plugins"] += entries
    marketplace_json.write_text(json.dumps(listed))


def test_search_ranks_inside_each_group(home):
    # On this computer: office-kit (Codex has it, "office" in the name) and documents ("office"
    # in the description). Not yet: office (the whole name) and alpha (the description).
    _list_plugins(
        home / ".codex/.tmp/plugins/.agents/plugins/marketplace.json",
        {"name": "office-kit", "source": {"source": "local", "path": "./plugins/office-kit"}},
    )
    config = home / ".codex/config.toml"
    config.write_text(
        config.read_text() + '\n[plugins."office-kit@openai-curated"]\nenabled = true\n'
    )
    _list_plugins(
        home
        / ".claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json",
        {"name": "alpha", "description": "Edit office files", "source": "./plugins/alpha"},
        {"name": "office", "description": "Work with files", "source": "./plugins/office"},
    )
    answer = _library(home, show="all", q="office")
    # Name before description inside each group, though the names sort the other way.
    assert _names(answer) == [
        ("office-kit", "openai-curated"),
        ("documents", "openai-curated"),
        ("office", OFFICIAL),
        ("alpha", OFFICIAL),
    ]
    assert answer["counts"]["plugin"] == 4


def test_hidden_column_drops_rows_only_it_has(home):
    glean = ("glean", "cursor-public")
    shown = _library(home)
    assert glean in _names(shown)
    for client in ("claude_code", "codex"):
        assert _row(shown, "glean")["cells"][client]["add"]["label"] == "+ Add skills"

    cursor = frozenset({"cursor"})
    hidden = _library(home, hidden=cursor)
    assert [c["hidden"] for c in hidden["columns"]] == [False, False, True]
    # Only Cursor has these three, so they leave every choice and the counts, even though
    # glean's skills could still go to the clients shown.
    only_cursor = {glean, ("plugin 4800 (name not stored locally)", None)}
    only_cursor.add(("superpowers", "cursor-public"))
    assert set(_names(shown)) - set(_names(hidden)) == only_cursor
    assert hidden["counts"]["plugin"] == shown["counts"]["plugin"] - len(only_cursor)
    for show in ("mine", "new", "all"):
        answer = _library(home, show=show, hidden=cursor)
        assert not only_cursor & set(_names(answer)), show
    every = _library(home, show="all")
    assert _library(home, show="all", hidden=cursor)["counts"]["plugin"] == (
        every["counts"]["plugin"] - len(only_cursor)
    )
    assert _library(home, show="new", hidden=cursor)["counts"]["plugin"] == 1


def test_hiding_every_found_client_hides_none(home, tmp_path):
    shown = _library(home, show="all")
    everyone = _library(home, show="all", hidden=frozenset({"claude_code", "codex", "cursor"}))
    assert [c["hidden"] for c in everyone["columns"]] == [False, False, False]
    assert (everyone["rows"], everyone["counts"]) == (shown["rows"], shown["counts"])
    # A client that is gone from this computer was hidden with the rest: the same.
    two = make_home(tmp_path / "two", "claude_code/2.1.283", "codex/0.159.2")
    left = _library(two, hidden=frozenset({"claude_code", "codex", "cursor"}))
    assert [c["hidden"] for c in left["columns"]] == [False, False]
    assert left["rows"] == _library(two)["rows"]


def test_one_marketplace_note_per_client_and_marketplace(home):
    every = _library(home, show="all")
    # toolbox and superpowers both come from a marketplace Codex does not have yet.
    for name in ("toolbox", "superpowers"):
        add = _row(every, name, OFFICIAL)["cells"]["codex"]["add"]
        assert add == _add(
            "plugin.install",
            "+ Add",
            f"{name}@{OFFICIAL}",
            marketplace=OFFICIAL,
            project_hint=CODEX_HINT,
        )
    assert every["notes"] == [
        "Codex gets the claude-plugins-official marketplace the first time you add one of its "
        "plugins."
    ]
    assert _library(home, show="all", hidden=frozenset({"codex"}))["notes"] == []
    assert _library(home, show="all", q="documents")["notes"] == []


def test_same_name_from_two_marketplaces_is_marked(home):
    answer = _library(home, show="all")
    marked = {(r["name"], r["source"]) for r in answer["rows"] if r["same_name"]}
    assert marked == {("superpowers", OFFICIAL), ("superpowers", "cursor-public")}
    skills = _library(home, "skill", show="all")
    assert [r["source"] for r in skills["rows"] if r["name"] == "brainstorming"] == [
        f"superpowers@{OFFICIAL}",
        PLUGIN,
    ]
    assert all(r["same_name"] for r in skills["rows"] if r["name"] == "brainstorming")
    assert len({r["key"] for r in skills["rows"]}) == len(skills["rows"])

    # Codex has documents from openai-curated; adding the one from Claude Code's marketplace
    # stays possible, with a warning.
    path = home / ".claude/plugins/marketplaces/claude-plugins-official/.claude-plugin"
    listed = json.loads((path / "marketplace.json").read_text())
    listed["plugins"].append({"name": "documents", "source": "./plugins/documents"})
    (path / "marketplace.json").write_text(json.dumps(listed))
    other = _row(_library(home, show="all"), "documents", OFFICIAL)
    assert other["same_name"] is True
    assert other["cells"]["codex"]["add"]["warn"] == (
        "Codex already has documents from openai-curated. It will load both."
    )
    assert other["cells"]["claude_code"]["add"]["warn"] is None


def _server_reasons(home: Path, gateway: bool, project: str | None = None) -> dict:
    """Per MCP server row, the reason of each dash."""
    inventory = build_inventory(home)
    if gateway:
        mark_gateways(inventory, [Gateway(url="https://mcp.neon.tech/mcp")])
    adapters = {a.id: a for a in default_adapters(home)}
    answer = library(inventory, adapters, project, gateway_registered=gateway, kind="mcp_server")
    return {
        r["name"]: {c: cell["reason"] for c, cell in r["cells"].items() if cell["state"] == "none"}
        for r in answer["rows"]
    }


def _server_adds(home: Path, gateway: bool) -> dict:
    """Per MCP server row, the action of each dash's add, or None."""
    inventory = build_inventory(home)
    if gateway:
        mark_gateways(inventory, [Gateway(url="https://mcp.neon.tech/mcp")])
    adapters = {a.id: a for a in default_adapters(home)}
    answer = library(inventory, adapters, None, gateway_registered=gateway, kind="mcp_server")
    return {
        r["name"]: {
            c: (cell["add"] or {}).get("action")
            for c, cell in r["cells"].items()
            if cell["state"] == "none"
        }
        for r in answer["rows"]
    }


def test_a_server_dash_says_how_the_gateway_would_share_it(home):
    # Codex and Cursor reach the gateway through their neon entries; Claude Code does not.
    reasons = _server_reasons(home, gateway=True)
    connect = "Connect Claude Code to the gateway on the Gateway page."
    share = "Move it into the gateway to share it."
    assert reasons["neon"] == {"claude_code": connect, "cursor": None}
    # A direct server another client lacks is copied there; the add replaces the share reason.
    assert reasons["github"] == {"codex": None, "cursor": None}
    assert reasons["langfuse-data"] == {"claude_code": None, "cursor": None}
    adds = _server_adds(home, gateway=True)
    assert adds["github"] == {"codex": "mcp.add", "cursor": "mcp.add"}
    # A row a gateway serves: Claude Code is told to connect, not offered a copy.
    assert adds["neon"]["claude_code"] is None
    assert share not in {r for row in reasons.values() for r in row.values()}
    # A server that runs on this computer does not move.
    assert reasons["n8n-mcp"] == {"claude_code": None, "codex": None}
    without = _server_reasons(home, gateway=False)
    assert all(r is None for row in without.values() for r in row.values())


def test_a_project_only_server_a_gateway_client_cannot_move_says_why(home):
    # Codex and Cursor use the gateway; website's old-search runs on this computer, so it
    # does not move, and only website has it.
    reasons = _server_reasons(home, gateway=True, project=str(home / "work/website"))
    only = "Kitden adds MCP servers for all projects only."
    assert reasons["old-search"] == {"codex": only, "cursor": only}


def test_a_marketplace_dash_says_when_an_add_brings_it(home):
    answer = _library(home, "marketplace")
    official = _row(answer, OFFICIAL)["cells"]
    assert official["codex"]["reason"] == "Codex gets it the first time you add one of its plugins."
    assert official["cursor"]["reason"] is None
    assert _row(answer, "openai-bundled")["cells"]["claude_code"]["reason"] is None


def test_api_library_and_offer(home):
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        client.get("/?token=tok")
        answer = client.get("/api/library?kind=plugin&show=all&hidden=cursor,codex").json()
        assert set(answer) == {
            "project",
            "columns",
            "counts",
            "rows",
            "more",
            "attention",
            "categories",
            "notes",
        }
        assert answer["project"] is None
        assert [c["id"] for c in answer["columns"] if c["hidden"]] == ["codex", "cursor"]
        # Only Claude Code is shown: rows it has, or can add to it.
        assert {r["name"] for r in answer["rows"]} == {
            "Claude account plugins and connectors",
            "superpowers",
            "toolbox",
        }

        fallback = client.get("/api/library?kind=nope&show=nope").json()
        assert fallback == client.get("/api/library?kind=mcp_server&show=mine").json()
        assert fallback["rows"] and all(r["kind"] == "mcp_server" for r in fallback["rows"])

        # Cursor loads superpowers twice: both rows need attention.
        flagged = client.get("/api/library?kind=plugin&attention=1").json()
        assert _names(flagged) == [("superpowers", OFFICIAL), ("superpowers", "cursor-public")]
        assert flagged["attention"] == client.get("/api/library?kind=plugin").json()["attention"]
        assert flagged["attention"] == 2

        plugin = client.get(f"/api/offer?kind=plugin&id={PLUGIN}")
        assert plugin.status_code == 200 and plugin.json()["id"] == PLUGIN
        # Details and the Add form say what Cursor loads as well; the server reads its switches.
        assert plugin.json()["inherits"] == {"plugin": True, "skill": True}
        skill = client.get(f"/api/offer?kind=skill&id=tidy@{PLUGIN}")
        assert skill.status_code == 200 and skill.json()["name"] == "tidy"
        assert skill.json()["inherits"] == {"plugin": True, "skill": True}
        missing = client.get("/api/offer?kind=plugin&id=nope@nowhere")
        assert (missing.status_code, missing.json()) == (404, {"detail": "Not on this computer."})


def test_library_and_offer_let_other_requests_run_meanwhile(home, monkeypatch):
    # The first read of every skill takes seconds; other requests must not wait for it.
    import kitden.web.app as page

    started, release = threading.Event(), threading.Event()

    def slow(real):
        def wait(*args, **kwargs):
            started.set()
            assert release.wait(5), "no other request could run meanwhile"
            return real(*args, **kwargs)

        return wait

    monkeypatch.setattr(page, "library", slow(page.library))
    monkeypatch.setattr(page, "skill_catalog", slow(page.skill_catalog))
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        client.get("/?token=tok")
        for path in ("/api/library?kind=plugin", f"/api/offer?kind=skill&id=tidy@{PLUGIN}"):
            started.clear()
            release.clear()
            with ThreadPoolExecutor(1) as pool:
                slow_read = pool.submit(client.get, path)
                assert started.wait(5)
                assert client.get("/api/clients").status_code == 200
                release.set()
                assert slow_read.result().status_code == 200, path


# Instructions ---------------------------------------------------------------------------------


def test_the_instructions_tab_lists_files_per_client(home):
    answer = _library(home, "instructions")
    names = {(r["name"], r["category"]) for r in answer["rows"]}
    assert {
        ("CLAUDE.md", "instructions"),
        ("AGENTS.md", "instructions"),
        ("review", "command"),
        ("reviewer", "agent"),
    } <= names
    cells = [c for r in answer["rows"] for c in r["cells"].values()]
    assert all(c["add"] is None for c in cells)
    # No word of its own: the page says the state word, as on every tab.
    assert {c["word"] for c in cells if c["state"] != "none"} == {None}
    assert answer["categories"] == []


def test_agents_md_is_one_row_for_codex_and_cursor_without_a_flag(home):
    site = str(home / "work/site")
    inventory = build_inventory(home)
    assert not [f for f in find_findings(inventory, site) if "AGENTS.md" in f.names]
    answer = library(
        inventory,
        {a.id: a for a in default_adapters(home)},
        site,
        gateway_registered=False,
        kind="instructions",
    )
    (row,) = [r for r in answer["rows"] if r["name"] == "AGENTS.md"]
    assert (row["cells"]["codex"]["word"], row["cells"]["cursor"]["word"]) == (None, None)
    assert row["flags"] == []


def test_a_command_and_an_agent_with_one_name_are_two_rows(home):
    _write(home / ".claude/agents/review.md", "---\nname: review\n---\nReview code.\n")
    rows = [r for r in _library(home, "instructions")["rows"] if r["name"] == "review"]
    assert sorted(r["category"] for r in rows) == ["agent", "command"]
    assert len({r["key"] for r in rows}) == 2


# Unknown: what Kitden could not read ----------------------------------------------------------


class _BrokenCodex(CodexAdapter):
    def scan(self):
        raise ValueError("a format Kitden does not know")


def test_a_client_that_could_not_be_read_keeps_its_column_as_unknown(home):
    inventory = build_inventory(
        home, adapters=[ClaudeCodeAdapter(home), _BrokenCodex(home), CursorAdapter(home)]
    )
    rows = load_map(inventory, None)
    assert {r.cells["codex"].state for r in rows} == {"unk"}
    assert {r.cells["codex"].reason for r in rows} == {"Could not read Codex."}
    adapters = {a.id: a for a in default_adapters(home)}
    answer = library(inventory, adapters, None, gateway_registered=False, kind="mcp_server")
    assert [(c["id"], c["note"]) for c in answer["columns"]] == [
        ("claude_code", None),
        ("codex", "Could not read"),
        ("cursor", None),
    ]
    cells = [r["cells"]["codex"] for r in answer["rows"]]
    assert cells and all(c["state"] == "unk" and c["add"] is None for c in cells)


def test_no_add_goes_into_a_settings_file_that_could_not_be_read(home):
    (home / ".cursor/mcp.json").write_text("{ not json")
    answer = _library(home, "mcp_server")
    github = _row(answer, "github")["cells"]
    assert github["cursor"]["add"] is None  # its add writes into the broken file
    assert github["cursor"]["state"] == "unk"  # Cursor may have it in that file: never "—"
    assert github["cursor"]["reason"] == "Can't add while mcp.json can't be read."
    assert github["codex"]["add"]["action"] == "mcp.add"  # Codex's own file reads well
    assert "Could not read mcp.json; its items are not shown." in answer["notes"]


def _preview_github_into(home, client):
    with page_for(home) as page:
        github = next(
            i
            for i in page.get("/api/items?kind=mcp_server").json()
            if (i["client"], i["name"]) == ("claude_code", "github")
        )
        body = {
            "action": "mcp.add",
            "targets": [{"client": client}],
            "params": {"item": github["id"]},
        }
        return page.post("/api/changes/preview", json=body, headers=POST)


def test_a_preview_into_a_file_that_could_not_be_read_says_why(home):
    (home / ".cursor/mcp.json").write_text("{ not json")
    answer = _preview_github_into(home, "cursor")
    assert (answer.status_code, answer.json()) == (
        422,
        {"detail": "Can't add while mcp.json can't be read."},
    )


def test_a_preview_into_a_broken_codex_config_is_refused_not_a_crash(home):
    # Codex stays found; the file is a problem.
    (home / ".codex/config.toml").write_text("not = [toml\n")
    answer = _preview_github_into(home, "codex")
    assert (answer.status_code, answer.json()) == (
        422,
        {"detail": "Can't add while config.toml can't be read."},
    )


def test_the_medium_sample_names_its_unreadable_file_above_the_table(tmp_path):
    home = build_demo_home(tmp_path, "medium")  # Part 1: work/website/.cursor/mcp.json is cut short
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}

    def answer(project):
        return library(inventory, adapters, project, gateway_registered=False, kind="mcp_server")

    website = answer(str(home / "work/website"))
    assert "Could not read mcp.json; its items are not shown." in website["notes"]
    # Cursor's add of github writes into ~/.cursor/mcp.json, which reads well: it stays offered.
    assert _row(website, "github")["cells"]["cursor"]["add"]["action"] == "mcp.add"
    # The file belongs to website, so All projects and the other projects do not name it.
    assert not any(n.startswith("Could not read mcp.json") for n in answer(None)["notes"])


# The last good read, kept while the page runs ------------------------------------------------


def test_a_file_that_breaks_keeps_its_items_from_the_last_good_read(home):
    # This home holds no gateway servers, so the rescan starts none.
    with page_for(home) as page:
        before = page.get("/api/library?kind=mcp_server").json()
        assert _row(before, "github")["cells"]["claude_code"]["state"] == "on"
        (home / ".claude.json").write_text("{ broken")
        page.post("/api/rescan", headers=POST)
        answer = page.get("/api/library?kind=mcp_server").json()
    row = _row(answer, "github")
    assert row["cells"]["claude_code"]["state"] == "on" and row["cells"]["claude_code"]["stale_at"]
    assert row["flags"][0]["text"].startswith("From the last good read at ")
    # Claude Code lacks neon; its add writes .claude.json.
    neon = _row(answer, "neon")["cells"]["claude_code"]
    assert neon["add"] is None and neon["reason"] == "Can't add while .claude.json can't be read."
    assert not any(n.startswith("Could not read .claude.json") for n in answer["notes"])


def _known_projects(home: Path, *folders: Path) -> None:
    """Claude Code lists these folders as projects too."""
    path = home / ".claude.json"
    state = json.loads(path.read_text())
    state["projects"].update({str(f): {} for f in folders})
    path.write_text(json.dumps(state))


def _notes(home: Path, project: Path | None) -> list[str]:
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}
    where = str(project) if project else None
    answer = library(inventory, adapters, where, gateway_registered=False, kind="mcp_server")
    return answer["notes"]


def test_a_broken_user_file_is_named_when_the_home_folder_is_a_known_project(home):
    # Anyone who ran claude in ~ has it in the project list; ~/.cursor/mcp.json is still the user's.
    _known_projects(home, home)
    (home / ".cursor/mcp.json").write_text("{ not json")
    line = "Could not read mcp.json; its items are not shown."
    assert line in _notes(home, None)
    assert line in _notes(home, home / "work/website")


def test_a_broken_project_file_belongs_to_the_deepest_project(home):
    work, website = home / "work", home / "work/website"
    _known_projects(home, work)
    (website / ".claude/settings.json").write_text("{ not json")
    line = "Could not read settings.json; its items are not shown."
    assert line in _notes(home, website)
    assert line not in _notes(home, work)
    assert line not in _notes(home, None)


def test_a_failed_client_keeps_its_rows_from_the_last_good_read(home):
    last = LastGood()
    keep_last_good(build_inventory(home), last, "2026-10-22T14:02:00+00:00")
    broken = [ClaudeCodeAdapter(home), _BrokenCodex(home), CursorAdapter(home)]
    inventory = keep_last_good(
        build_inventory(home, adapters=broken), last, "2026-10-22T14:05:00+00:00"
    )
    adapters = {a.id: a for a in default_adapters(home)}
    answer = library(inventory, adapters, None, gateway_registered=False, kind="mcp_server")
    # Only Codex had langfuse-data: its row stays, as Codex had it at the last good read.
    row = _row(answer, "langfuse-data")
    assert row["mine"] is True
    codex = row["cells"]["codex"]
    assert (codex["state"], codex["stale_at"], codex["add"]) == (
        "on",
        "2026-10-22T14:02:00+00:00",
        None,
    )
    assert codex["reason"].startswith("From the last good read at ")
    # A row Codex did not have stays Unknown in its column.
    assert _row(answer, "github")["cells"]["codex"]["state"] == "unk"
    # The column says it; a whole client gives no line above the table.
    assert not any(n.startswith("Could not read") for n in answer["notes"])


def _toolbox_cell(home: Path, project: Path) -> dict:
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}
    answer = library(
        inventory, adapters, str(project), gateway_registered=False, kind="plugin", show="all"
    )
    return _row(answer, "toolbox")["cells"]["claude_code"]


def test_an_add_with_a_project_place_is_held_only_when_both_places_are_broken(home):
    website = home / "work/website"
    assert _toolbox_cell(home, website)["add"]["project_place"] is True
    (home / ".claude/settings.json").write_text("{ not json")
    assert _toolbox_cell(home, website)["add"]["action"] == "plugin.install"  # the project's reads
    (website / ".claude/settings.json").write_text("{ not json")
    held = _toolbox_cell(home, website)
    assert (held["state"], held["add"], held["reason"]) == (
        "unk",
        None,
        "Can't add while settings.json can't be read.",
    )


def test_a_place_kitden_cannot_add_into_does_not_keep_an_add_offered(home):
    # The project folder is gone, so the add can go to all projects only; that file is broken.
    (home / ".claude/settings.json").write_text("{ not json")
    cell = _toolbox_cell(home, home / "work/deleted-project")
    assert (cell["add"], cell["reason"]) == (None, "Can't add while settings.json can't be read.")


def test_a_definition_kept_from_the_last_good_read_cannot_be_changed(home):
    with page_for(home) as page:
        (home / ".claude.json").write_text("{ broken")
        page.post("/api/rescan", headers=POST)
        github = next(
            i
            for i in page.get("/api/items?kind=mcp_server").json()
            if (i["client"], i["name"]) == ("claude_code", "github")
        )
        assert github["stale_at"]
        body = {"action": "mcp.remove_direct", "targets": [{"item": github["id"]}]}
        answer = page.post("/api/changes/preview", json=body, headers=POST)
    assert (answer.status_code, answer.json()) == (
        422,
        {"detail": "Kitden can't change this until it reads .claude.json again."},
    )


def test_a_marketplace_skill_named_like_a_clients_own_is_not_shown_as_loaded(home):
    add_skills_marketplace(home)
    _skill(home / ".codex/skills", "tidy", "Not the toolbox one.")
    tidy = _row(_library(home, "skill", show="all"), "tidy")
    assert tidy["cells"]["codex"]["state"] == "review" and tidy["cells"]["codex"]["add"] is None
    assert tidy["cells"]["codex"]["reason"] == "Same name, another source."


def test_a_plugin_skill_is_not_review_after_the_marketplace_moves_on(home):
    # The marketplace copy says "Think first."; Claude Code's cache copy is another version.
    row = _row(_library(home, "skill", show="all"), "brainstorming", f"superpowers@{OFFICIAL}")
    assert (row["cells"]["claude_code"]["state"], row["cells"]["claude_code"]["route"]) == (
        "on",
        "from a plugin",
    )


def test_review_rows_on_the_medium_sample_offer_no_add(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    answer = library(
        build_inventory(home),
        {a.id: a for a in default_adapters(home)},
        None,
        gateway_registered=False,
        kind="mcp_server",
    )
    docs = _row(answer, "docs")["cells"]  # Part 1: same name, two sources; a tie keeps Claude Code
    assert (docs["claude_code"]["state"], docs["codex"]["state"]) == ("on", "review")
    assert (docs["cursor"]["add"], docs["cursor"]["reason"]) == (
        None,
        "Same name, another source: decide first.",
    )
    review = [c for r in answer["rows"] for c in r["cells"].values() if c["state"] == "review"]
    assert all(c["add"] is None for c in review)


@pytest.mark.parametrize("folder", [".agents/skills", ".codex/skills"])
def test_a_plugin_skill_kitden_copied_is_still_that_plugins_skill(home, folder):
    # Kitden's "+ Add" copies the marketplace's folder; Claude Code loads its own cache copy.
    market = home / ".claude/plugins/marketplaces/claude-plugins-official/plugins/superpowers"
    shutil.copytree(market / "skills/brainstorming", home / folder / "brainstorming")
    inventory = build_inventory(home)
    row = next(r for r in load_map(inventory, None) if r.name == "brainstorming")
    assert "review" not in {c.state for c in row.cells.values()}
    shown = _row(_library(home, "skill", show="all"), "brainstorming", f"superpowers@{OFFICIAL}")
    assert "review" not in {c["state"] for c in shown["cells"].values()}
    notes = {f.type for f in find_findings(inventory) if "brainstorming" in f.names}
    assert FindingType.SAME_NAME_OTHER_SOURCE not in notes


def test_a_review_skill_row_offers_no_add_in_its_other_cells(home):
    # Claude Code loads superpowers' brainstorming, not the toolbox one.
    row = _row(_library(home, "skill", show="all"), "brainstorming", f"toolbox@{OFFICIAL}")
    assert row["cells"]["claude_code"]["state"] == "review"
    assert (row["cells"]["codex"]["add"], row["cells"]["codex"]["reason"]) == (
        None,
        "Same name, another source: decide first.",
    )


def test_a_copy_made_before_a_plugin_update_does_not_flag_the_plugins_skill(home):
    # Codex has a copy of Claude Code's plugin skill (Cursor reads it too); then the plugin's
    # files change. The plugin is the source; the old copy drifted.
    cache = home / ".claude/plugins/cache/claude-plugins-official/superpowers/7.0.0/skills"
    shutil.copytree(cache / "brainstorming", home / ".codex/skills/brainstorming")
    skill_md = cache / "brainstorming/SKILL.md"
    skill_md.write_text(skill_md.read_text() + "\nA newer version.\n")
    inventory = build_inventory(home)
    row = next(r for r in load_map(inventory, None) if r.name == "brainstorming")
    assert {c: row.cells[c].state for c in ("claude_code", "codex", "cursor")} == {
        "claude_code": "on",
        "codex": "on",
        "cursor": "on",
    }
    shown = _row(_library(home, "skill", show="all"), "brainstorming", f"superpowers@{OFFICIAL}")
    assert shown["cells"]["claude_code"]["state"] == "on"
    notes = {f.type for f in find_findings(inventory) if "brainstorming" in f.names}
    assert FindingType.SAME_NAME_OTHER_SOURCE not in notes


def test_a_project_only_skill_adds_into_the_project(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inventory, adapters = build_inventory(home), {a.id: a for a in default_adapters(home)}
    atlas_path = str(home / "work/atlas")
    atlas = library(inventory, adapters, atlas_path, gateway_registered=False, kind="skill")
    style = _row(atlas, "api-style")
    add = style["cells"]["claude_code"]["add"]
    assert (add["action"], add["skill"], add["project_only"]) == (
        "skill.install",
        "project/api-style",
        True,
    )
    assert (add["project_place"], add["project_hint"]) == (False, None)
    assert style["cells"]["codex"]["where"] == "this project"
    assert (style["source"], style["offer"]) == ("atlas", None)
    everywhere = library(
        inventory, adapters, None, gateway_registered=False, kind="skill", show="all"
    )
    assert not any(r["name"] == "api-style" for r in everywhere["rows"])


def test_a_project_only_server_says_why_it_has_no_add(home):
    answer = library(
        build_inventory(home),
        {a.id: a for a in default_adapters(home)},
        str(home / "work/website"),
        gateway_registered=False,
        kind="mcp_server",
    )
    docs = _row(answer, "docs")["cells"]  # only website's own .mcp.json has docs
    assert (docs["codex"]["add"], docs["codex"]["reason"]) == (
        None,
        "Kitden adds MCP servers for all projects only.",
    )
