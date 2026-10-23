"""Adding a skill or a plugin into one project: the project place, verify, Undo."""

import json

import pytest
from starlette.testclient import TestClient

from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_api_plugin_install import LINTER, FakeCli
from tests.unit.test_catalog import add_marketplaces
from tests.unit.test_demo_mode import demo_page, scan_done, until
from tests.unit.test_skills_catalog import PLUGIN, add_skills_marketplace

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
TIDY = f"tidy@{PLUGIN}"
MARKETPLACE = ".claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json"
HOUSE = "---\nname: house-style\ndescription: Our style.\n---\nKeep it plain.\n"


@pytest.fixture
def client(tmp_path, monkeypatch):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home, {})
    add_marketplaces(home)
    linter = json.loads((home / MARKETPLACE).read_text())["plugins"]
    add_skills_marketplace(home)
    # Both helpers write the same marketplace file: list the plugins of both.
    listed = json.loads((home / MARKETPLACE).read_text())
    listed["plugins"] += linter
    (home / MARKETPLACE).write_text(json.dumps(listed))
    run = FakeCli(home)
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home, run=run)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        c.home, c.run = home, run
        yield c


def pid(client, folder):
    return next(p["id"] for p in client.get("/api/projects").json() if p["path"] == folder)


def _preview(client, action, chosen, params):
    body = {"action": action, "targets": [{"client": c} for c in chosen], "params": params}
    return client.post("/api/changes/preview", json=body, headers=POST)


def test_a_skill_goes_into_the_project_folder(client):
    home, website = client.home, str(client.home / "work/website")
    params = {"skill": TIDY, "project": pid(client, website)}
    change = _preview(client, "skill.install", ["claude_code"], params).json()
    step = change["steps"][0]
    assert (step["scope"], step["path"], step["reaches"]) == (
        "project",
        f"{website}/.claude/skills/tidy",
        ["claude_code", "cursor"],
    )
    assert change["shared_file_warning"] is True
    apply = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert apply["state"] == "verified"
    rows = client.get(f"/api/library?kind=skill&project={pid(client, website)}").json()["rows"]
    tidy = next(r for r in rows if r["name"] == "tidy")
    cell = tidy["cells"]["claude_code"]
    assert (cell["state"], cell["where"]) == ("on", "this project")
    everywhere = client.get("/api/library?kind=skill&show=all").json()["rows"]
    assert (
        next(r for r in everywhere if r["name"] == "tidy")["cells"]["claude_code"]["state"]
        == "none"
    )
    undo = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undo["state"] == "undone"
    assert not (home / "work/website/.claude/skills/tidy").exists()


def test_codex_and_cursor_project_folders(client):
    api = str(client.home / "work/api")  # Codex trusts it
    params = {"skill": TIDY, "project": pid(client, api)}
    codex = _preview(client, "skill.install", ["codex"], params).json()
    assert (codex["steps"][0]["path"], codex["steps"][0]["reaches"]) == (
        f"{api}/.agents/skills/tidy",
        ["codex", "cursor"],
    )
    cursor = _preview(client, "skill.install", ["cursor"], params).json()
    assert (cursor["steps"][0]["path"], cursor["steps"][0]["reaches"]) == (
        f"{api}/.cursor/skills/tidy",
        ["cursor"],
    )


def test_a_codex_project_copy_needs_trust(client):
    website = str(client.home / "work/website")
    params = {"skill": TIDY, "project": pid(client, website)}
    answer = _preview(client, "skill.install", ["codex"], params)
    assert (answer.status_code, answer.json()["detail"]) == (
        422,
        "Codex does not trust website yet, so it would not load the skill there.",
    )


def test_a_claude_code_plugin_goes_into_the_project(client):
    website = str(client.home / "work/website")
    settings = client.home / "work/website/.claude/settings.json"
    params = {"plugin": LINTER, "project": pid(client, website)}
    change = _preview(client, "plugin.install", ["claude_code"], params).json()
    step = change["steps"][0]
    assert step["command"] == f"claude plugin install {LINTER} -s project --json"
    assert (step["scope"], step["path"]) == ("project", f"{website}/.claude/settings.json")
    assert change["shared_file_warning"] is True
    # Cursor imports only Claude Code's user plugins, so the review does not promise it.
    assert [a["client"] for a in change["after"]] == ["claude_code"]
    apply = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert apply["state"] == "verified"
    assert json.loads(settings.read_text())["enabledPlugins"][LINTER] is True
    assert client.run.calls[-1][-4:] == [LINTER, "-s", "project", "--json"]
    undo = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undo["state"] == "undone"
    assert client.run.calls[-1][1:3] == ["plugin", "uninstall"]
    assert LINTER not in json.loads(settings.read_text())["enabledPlugins"]


def test_codex_has_no_project_place_for_a_plugin(client):
    website = str(client.home / "work/website")
    params = {"plugin": LINTER, "project": pid(client, website)}
    answer = _preview(client, "plugin.install", ["codex"], params)
    assert (answer.status_code, answer.json()["detail"]) == (
        422,
        "Codex has no project place for a plugin here; add it for all projects.",
    )
    unknown = _preview(client, "plugin.install", ["codex"], {"plugin": LINTER, "project": "nope"})
    assert (unknown.status_code, unknown.json()["detail"]) == (422, "Unknown project.")


def test_the_cells_say_which_adds_have_a_project_place(client):
    website = pid(client, str(client.home / "work/website"))
    skills = client.get(f"/api/library?kind=skill&show=new&project={website}").json()["rows"]
    tidy = next(r for r in skills if r["name"] == "tidy")
    # Codex does not trust website (see the test below); the others can add into it.
    assert all(tidy["cells"][c]["add"]["project_place"] is True for c in ("claude_code", "cursor"))
    plugins = client.get(f"/api/library?kind=plugin&show=new&project={website}").json()["rows"]
    linter = next(r for r in plugins if r["name"] == "linter")
    claude, codex = linter["cells"]["claude_code"]["add"], linter["cells"]["codex"]["add"]
    assert (claude["project_place"], claude["project_hint"]) == (True, None)
    assert (codex["project_place"], codex["project_hint"]) == (
        False,
        "Codex plugins are for all projects.",
    )


def test_cursor_plugin_cells_say_where_to_add_per_project(client):
    """Cursor keeps its plugins in its own database: in a project view its cell says where."""
    website = pid(client, str(client.home / "work/website"))
    plugins = client.get(f"/api/library?kind=plugin&show=all&project={website}").json()["rows"]
    cursor = [
        r["cells"]["cursor"]
        for r in plugins
        if r["cells"]["cursor"]["state"] in ("none", "via", "done")
    ]
    assert cursor
    for cell in cursor:
        said = (cell["add"] or {}).get("project_hint") or cell["reason"] or ""
        assert "Customize → Plugins, Install, then choose the project scope." in said, cell
    everywhere = client.get("/api/library?kind=plugin&show=all").json()["rows"]
    for row in everywhere:
        cell = row["cells"]["cursor"]
        assert "Customize" not in ((cell["add"] or {}).get("project_hint") or cell["reason"] or "")


def test_an_add_without_a_project_stays_for_all_projects(client):
    change = _preview(client, "skill.install", ["claude_code"], {"skill": TIDY}).json()
    assert change["steps"][0]["path"] == f"{client.home}/.claude/skills/tidy"
    assert change["steps"][0]["scope"] == "user"


def test_codex_offers_no_project_place_in_a_project_it_does_not_trust(client):
    """website is not trusted by Codex: its skill add goes to all projects and says why."""
    website = pid(client, str(client.home / "work/website"))
    rows = client.get(f"/api/library?kind=skill&show=new&project={website}").json()["rows"]
    add = next(r for r in rows if r["name"] == "tidy")["cells"]["codex"]["add"]
    assert (add["project_place"], add["project_hint"]) == (
        False,
        "Adds for all projects. To add it to website only, trust website in Codex first.",
    )
    api = pid(client, str(client.home / "work/api"))
    rows = client.get(f"/api/library?kind=skill&show=new&project={api}").json()["rows"]
    add = next(r for r in rows if r["name"] == "tidy")["cells"]["codex"]["add"]
    assert (add["project_place"], add["project_hint"]) == (True, None)


def test_a_skill_add_into_a_known_project_on_another_disk_previews(client, tmp_path):
    site = tmp_path / "other-disk/site"  # outside the home folder
    site.mkdir(parents=True)
    settings_path = client.home / ".claude.json"
    settings = json.loads(settings_path.read_text())
    settings.setdefault("projects", {})[str(site)] = {"hasTrustDialogAccepted": True}
    settings_path.write_text(json.dumps(settings))
    client.post("/api/rescan", headers=POST)  # a fixture home: no held servers to ask
    params = {"skill": TIDY, "project": pid(client, str(site))}
    change = _preview(client, "skill.install", ["claude_code"], params)
    assert change.status_code == 200
    assert all(step["path"].startswith(str(site)) for step in change.json()["steps"])


def _project_skill(client, project):
    """A skill in the project's own Claude Code folder; Claude Code knows the project."""
    folder = client.home / f"work/{project}/.claude/skills/house-style"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(HOUSE)
    settings_path = client.home / ".claude.json"
    settings = json.loads(settings_path.read_text())
    known = {"hasTrustDialogAccepted": True}
    settings.setdefault("projects", {})[str(client.home / f"work/{project}")] = known
    settings_path.write_text(json.dumps(settings))
    client.post("/api/rescan", headers=POST)  # a fixture home: no held servers to ask


def test_a_project_skill_copies_into_the_same_project(client):
    _project_skill(client, "api")  # Codex trusts api
    api = str(client.home / "work/api")
    params = {"skill": "project/house-style", "project": pid(client, api)}
    change = _preview(client, "skill.install", ["codex"], params)
    assert change.json()["steps"][0]["path"] == f"{api}/.agents/skills/house-style"
    refused = _preview(client, "skill.install", ["codex"], {"skill": "project/house-style"})
    assert (refused.status_code, refused.json()["detail"]) == (
        422,
        "This skill is in one project only. Pick that project to add it.",
    )
    website = pid(client, str(client.home / "work/website"))
    elsewhere = {"skill": "project/house-style", "project": website}
    missing = _preview(client, "skill.install", ["codex"], elsewhere)
    assert (missing.status_code, missing.json()["detail"]) == (
        422,
        "This skill is not on this computer.",
    )


def test_a_project_skill_for_codex_in_an_untrusted_project_says_trust_first(client):
    _project_skill(client, "untrusted")
    untrusted = pid(client, str(client.home / "work/untrusted"))
    rows = client.get(f"/api/library?kind=skill&project={untrusted}").json()["rows"]
    codex = next(r for r in rows if r["name"] == "house-style")["cells"]["codex"]
    assert (codex["add"], codex["reason"]) == (
        None,
        "To add it to untrusted, trust untrusted in Codex first.",
    )


def test_a_project_skill_copy_says_when_cursor_would_load_it_twice(tmp_path):
    # The medium sample: Codex and Cursor load atlas/.agents/skills/api-style, and Cursor reads
    # Claude Code's project folder too, so a copy for Claude Code reaches Cursor a second time.
    with demo_page(tmp_path) as page:
        until(lambda: scan_done(page), 20)
        atlas = pid(page, str(page.home / "work/atlas"))
        params = {"skill": "project/api-style", "project": atlas}
        change = _preview(page, "skill.install", ["claude_code"], params).json()
        assert change["steps"][0]["reaches"] == ["claude_code", "cursor"]
        cursor = next(e for e in change["after"] if e["client"] == "cursor")
        assert (cursor["word"], cursor["note"]) == (
            "Loads twice",
            "Cursor reads two folders that hold this skill, so it loads the skill twice.",
        )
        page.post(f"/api/changes/{change['id']}/cancel", headers=POST)
