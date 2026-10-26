"""The Instructions map's data: clients, the instruction files they read, and what those files
import (spec Part 6.1)."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kitden.views.instructions_map import instructions_map
from kitden.views.inventory import build_inventory, default_adapters
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

ORIGIN = "http://127.0.0.1:47800"


@pytest.fixture
def home(tmp_path):
    # Cursor first: its fixture also has .claude files, and the Claude Code ones must win.
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return home


def _map(home: Path, project: str | None = None, inventory=None) -> dict:
    adapters = {a.id: a for a in default_adapters(home, quick=True)}
    inventory = inventory or build_inventory(home, list(adapters.values()), [])
    return instructions_map(inventory, adapters, project)


def _files(answer: dict) -> dict[tuple[str, str], dict]:
    """Every file block by (group key, name)."""
    return {(g["key"], f["name"]): f for g in answer["groups"] for f in g["files"]}


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_files_are_grouped_for_all_projects_and_this_project(home):
    answer = _map(home)
    assert [c["id"] for c in answer["clients"]] == ["claude_code", "codex", "cursor"]
    assert [(g["key"], g["name"]) for g in answer["groups"]] == [("all", "All projects")]
    files = _files(answer)
    assert files["all", "CLAUDE.md"]["by"] == {"claude_code": True}
    assert files["all", "AGENTS.md"]["by"] == {"codex": True}
    # Commands and agents are not instruction files for this map.
    assert not any(name in ("review.md", "reviewer.md") for _, name in files)
    claude = files["all", "CLAUDE.md"]
    assert claude["technical"]["path"] == str(home / ".claude/CLAUDE.md")
    assert claude["technical"]["lines"][0] == "# My rules"
    assert claude["size"] == 4
    assert claude["imports"] == []

    website = _map(home, str(home / "work/website"))
    assert [(g["key"], g["name"]) for g in website["groups"]] == [
        ("all", "All projects"),
        ("project", "Only this project · website"),
    ]
    assert _files(website)["project", "CLAUDE.md"]["by"] == {"claude_code": True}
    # Another project's files are not shown.
    assert not any(name == ".cursorrules" for _, name in _files(website))


def test_a_file_two_clients_read_is_one_block(home):
    files = _files(_map(home, str(home / "work/site")))
    # Cursor reads the root AGENTS.md; with no CLAUDE.md here, Claude Code reads it too
    # (v2.1.277 and later), not through an import.
    agents = files["project", "AGENTS.md"]
    assert agents["by"] == {"claude_code": True, "cursor": True}
    assert agents["through"] == "CLAUDE.md for Claude Code"
    assert agents["imports"] == []
    assert "through" not in files["project", ".cursorrules"]


def test_claude_code_reads_agents_md_only_without_a_claude_md(home):
    api = home / "work/api"
    assert _files(_map(home, str(api)))["project", "AGENTS.md"]["by"] == {
        "claude_code": True,
        "codex": True,
    }
    # A CLAUDE.local.md in the folder, or a CLAUDE.md in a folder above it, counts.
    for found in (api / "CLAUDE.local.md", home / "work/CLAUDE.md"):
        _write(found, "# Mine\n")
        agents = _files(_map(home, str(api)))["project", "AGENTS.md"]
        assert agents["by"] == {"codex": True}
        assert "through" not in agents
        found.unlink()
    # The user's own ~/.claude/CLAUDE.md does not count: it is there in the fixture.
    assert (home / ".claude/CLAUDE.md").is_file()
    # Before v2.1.277 Claude Code does not read AGENTS.md.
    adapters = {a.id: a for a in default_adapters(home, quick=True)}
    inventory = build_inventory(home, list(adapters.values()), [])
    old = [replace(c, version="2.1.276") if c.id == "claude_code" else c for c in inventory.clients]
    inventory = replace(inventory, clients=old)
    agents = _files(_map(home, str(api), inventory))["project", "AGENTS.md"]
    assert agents["by"] == {"codex": True}


def test_claude_code_files_list_their_imports(home):
    website = home / "work/website"
    _write(website / "CLAUDE.md", "# Website\n\nSee @docs/design.md and @~/notes.md\n")
    _write(website / "docs/design.md", "@development.md\n")
    _write(website / "docs/development.md", "# Dev\n")
    _write(website / ".claude/CLAUDE.md", "@../docs/development.md\n")
    _write(home / "notes.md", "# Notes\n")
    answer = _map(home, str(website))
    files = _files(answer)
    root, inner = files["project", "CLAUDE.md"], files["project", ".claude/CLAUDE.md"]
    imports = {i["id"]: i for i in answer["imports"]}
    assert [imports[i]["name"] for i in root["imports"]] == [
        "docs/design.md",
        "~/notes.md",
        "docs/development.md",
    ]
    assert [imports[i]["name"] for i in inner["imports"]] == ["docs/development.md"]
    development = imports[inner["imports"][0]]
    # One block per imported file, with the files that bring it in.
    assert sorted(development["by_files"]) == sorted([root["id"], inner["id"]])
    assert development["technical"]["path"] == str((website / "docs/development.md").resolve())
    assert development["outside"] is False
    assert imports[root["imports"][1]]["outside"] is True
    assert development["missing"] is False


def test_codex_and_cursor_files_have_no_imports(home):
    site = home / "work/site"
    _write(site / "AGENTS.md", "@docs/a.md\n")
    _write(site / ".cursorrules", "@docs/a.md\n")
    _write(site / ".cursor/rules/style.mdc", "@docs/a.md\n")
    _write(site / "docs/a.md", "# A\n")
    _write(home / ".codex/AGENTS.md", "@notes.md\n")
    _write(home / ".codex/notes.md", "# Notes\n")
    answer = _map(home, str(site))
    assert answer["imports"] == []
    assert all(f["imports"] == [] for g in answer["groups"] for f in g["files"])


def test_cursor_rules_fold_by_folder(home):
    site = home / "work/site"
    _write(site / ".cursor/rules/backend/api.mdc", "# API\n")
    _write(home / ".cursor/rules/mine.mdc", "# Mine\n")
    files = _files(_map(home, str(site)))
    rules = files["project", ".cursor/rules"]
    assert rules["by"] == {"cursor": True}
    assert rules["count"] == 2
    assert rules["technical"]["lines"] == ["backend:api", "style"]
    assert rules["technical"]["path"] == str(site / ".cursor/rules")
    assert "size" not in rules
    assert files["all", ".cursor/rules"]["count"] == 1
    assert not any(name.endswith(".mdc") for _, name in files)


def test_the_answer_has_no_paths_outside_technical(home):
    website = home / "work/website"
    _write(website / "CLAUDE.md", f"@docs/a.md @~/notes.md @{home.parent}/away.md\n")
    _write(website / "docs/a.md", "# A\n")
    _write(home / "notes.md", "# Notes\n")
    _write(home.parent / "away.md", "# Away\n")
    answer = _map(home, str(website))
    assert answer["imports"]

    def strip(value):
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k != "technical"}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    text = json.dumps(strip(answer))
    assert str(home.parent) not in text
    assert str(home.parent.resolve()) not in text


def test_the_page_reads_the_map_behind_the_page_cookie(home):
    adapters = {a.id: a for a in default_adapters(home, quick=True)}
    build = lambda: build_inventory(home, list(adapters.values()), [])  # noqa: E731
    app = create_app(build, token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN) as page:
        assert page.get("/api/instructions-map").status_code == 401
        page.get("/?token=tok")
        answer = page.get("/api/instructions-map").json()
        assert [g["key"] for g in answer["groups"]] == ["all"]
        project = next(p for p in page.get("/api/projects").json() if p["path"].endswith("site"))
        picked = page.get(f"/api/instructions-map?project={project['id']}").json()
        assert picked["project"]["id"] == project["id"]
        assert [g["key"] for g in picked["groups"]] == ["all", "project"]
        assert page.get("/api/instructions-map?project=nope").status_code == 404
