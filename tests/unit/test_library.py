"""The Library: what each client has on this computer and what it can add, in one list."""

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import kitden.clients.base as base
from kitden.clients.cursor import REACTIVE_KEY
from kitden.views.inventory import build_inventory, default_adapters
from kitden.views.library import library
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state
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


@pytest.fixture(autouse=True)
def _no_client_commands(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


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
    return {"state": state, "where": None, "items": [], "word": word, "add": add, "reason": reason}


def _add(action, label, plugin=None, skill=None, marketplace=None, warn=None) -> dict:
    return {
        "action": action,
        "label": label,
        "plugin": plugin,
        "skill": skill,
        "marketplace": marketplace,
        "warn": warn,
    }


def test_only_found_clients_are_columns(tmp_path):
    two = make_home(tmp_path / "two", "claude_code/2.1.283", "codex/0.159.2")
    answer = _library(two)
    assert answer["columns"] == [
        {"id": "claude_code", "name": "Claude Code", "mark": "CC", "hidden": False},
        {"id": "codex", "name": "Codex", "mark": "CX", "hidden": False},
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
    assert row["cells"]["claude_code"] == _cell(add=_add("plugin.skills", "Add skills", DOCUMENTS))
    # Cursor can't install it either, and Claude Code has no way to it: Cursor gets the skills.
    assert row["cells"]["cursor"]["add"]["label"] == "Add skills"


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
        assert glean["cells"][client] == _cell(add=_add("plugin.skills", "Add skills", GLEAN))

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
    assert toolbox["cells"]["claude_code"] == _cell(add=_add("plugin.install", "+ Add", PLUGIN))
    # Cursor does not import the plugins of Claude's account.
    account = _row(_library(home), "Claude account plugins and connectors")
    assert account["cells"]["claude_code"]["state"] == "unk"
    assert account["cells"]["cursor"] == _cell(
        reason="Cursor can't install this plugin, and it has no skills to copy."
    )

    # With Include Third-Party Plugins off, Cursor takes the skills that work alone instead.
    strict = _home(tmp_path / "strict", {REACTIVE_KEY: {"thirdPartyExtensibilityEnabled": False}})
    toolbox = _row(_library(strict, show="new"), "toolbox")
    assert toolbox["cells"]["cursor"] == _cell(add=_add("plugin.skills", "Add skills", PLUGIN))


def test_add_skills_turns_into_skills_added_when_all_are_there(home):
    for name in ("docx", "pptx"):
        _skill(home / ".claude/skills", name)
    row = _row(_library(home), "documents")
    assert row["cells"]["claude_code"]["add"]["label"] == "Add skills"  # xlsx is still missing

    _skill(home / ".claude/skills", "xlsx")
    row = _row(_library(home), "documents")
    assert row["cells"]["claude_code"] == _cell("done", word="Skills added")
    # Cursor reads Claude Code's skills folder, so it has them all as well.
    assert row["cells"]["cursor"] == _cell("done", word="Skills added")


def test_skill_that_needs_its_plugin_offers_add_the_plugin(home):
    answer = _library(home, "skill", show="new")
    rooted = _row(answer, "rooted")
    assert rooted["offer"] == f"rooted@{PLUGIN}" and rooted["source"] == PLUGIN
    assert rooted["cells"]["claude_code"] == _cell(
        add=_add("plugin.install", "Add the plugin", PLUGIN)
    )
    # Codex first adds the marketplace the plugin comes from.
    assert rooted["cells"]["codex"]["add"] == _add(
        "plugin.install", "Add the plugin", PLUGIN, marketplace=OFFICIAL
    )
    assert rooted["cells"]["cursor"] == _cell(
        reason="This skill needs its plugin, and Cursor can't install that plugin."
    )
    tidy = _row(answer, "tidy")
    assert tidy["cells"]["codex"] == _cell(
        add=_add("skill.install", "+ Add", skill=f"tidy@{PLUGIN}")
    )


def test_skill_cells_keep_the_state_the_scan_found(home):
    answer = _library(home, "skill", show="all")
    # Codex has pixel-art turned off in config.toml.
    codex = _row(answer, "pixel-art")["cells"]["codex"]
    assert (codex["state"], codex["where"]) == ("off", "global settings") and codex["items"]
    # Details can find a skill's definitions by name.
    brandkit = _row(answer, "brandkit")
    assert (brandkit["mine"], brandkit["lookup"]) == (True, "brandkit")
    assert brandkit["cells"]["claude_code"]["where"] == "global settings"
    assert brandkit["cells"]["cursor"]["where"] == "via Claude Code"
    assert brandkit["cells"]["codex"]["add"]["action"] == "skill.install"
    # Where the scan shows nothing, the skill list says how the client gets it.
    superpowers = _row(answer, "brainstorming", f"superpowers@{OFFICIAL}")
    assert superpowers["cells"]["cursor"] == {**_cell("on"), "where": "via plugin"}


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
    assert set(mine["counts"]) == {"mcp_server", "plugin", "skill", "hook", "marketplace"}
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


def test_hidden_column_drops_rows_only_it_has(home):
    glean = ("glean", "cursor-public")
    shown = _library(home)
    assert glean in _names(shown)
    for client in ("claude_code", "codex"):
        assert _row(shown, "glean")["cells"][client]["add"]["label"] == "Add skills"

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


def test_one_marketplace_note_per_client_and_marketplace(home):
    every = _library(home, show="all")
    # toolbox and superpowers both come from a marketplace Codex does not have yet.
    for name in ("toolbox", "superpowers"):
        add = _row(every, name, OFFICIAL)["cells"]["codex"]["add"]
        assert add == _add("plugin.install", "+ Add", f"{name}@{OFFICIAL}", marketplace=OFFICIAL)
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
        skill = client.get(f"/api/offer?kind=skill&id=tidy@{PLUGIN}")
        assert skill.status_code == 200 and skill.json()["name"] == "tidy"
        missing = client.get("/api/offer?kind=plugin&id=nope@nowhere")
        assert (missing.status_code, missing.json()) == (404, {"detail": "Not on this computer."})
