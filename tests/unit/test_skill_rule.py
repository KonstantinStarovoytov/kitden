"""The `skill.rule` change: a skill, or a plugin in one project, turned off with Undo (spec 5.5).

Every test runs on a sandbox home in tmp_path, through the preview tray's endpoint, Apply and
Undo, as the page does.
"""

import json
import os
import tomllib
from contextlib import contextmanager

from starlette.testclient import TestClient

from kitden.views.inventory import build_inventory
from kitden.views.words import (
    CHANGE_UNREAD,
    CODEX_NO_PROJECT,
    CURSOR_NO_SKILL_SWITCH,
    NEW_LOCAL_FILE,
    NO_CLAUDE_FOLDER,
    NO_SKILL_MERGE,
    PROJECT_SKILL_ALL,
    REPO_RULE,
)
from kitden.web.app import create_app

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
PLUGIN = "lint@tools"
# The user's file, as a person wrote it: four spaces, a key Kitden does not touch.
USER = '{\n    "theme": "dark",\n    "enabledPlugins": {\n        "lint@tools": true\n    }\n}\n'
CODEX = '# my Codex setup\nmodel = "gpt-5"\n\n[mcp_servers.docs]\ncommand = "docs"  # keep\n'


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if isinstance(text, str) else json.dumps(text, indent=2))


def _skill(folder, name):
    _write(folder / name / "SKILL.md", f"---\nname: {name}\ndescription: {name}\n---\n")


def _home(tmp_path, user=USER, local=None, site=None):
    """A sandbox home: two known projects (app, site), a Claude Code user skill `deploy` and a
    plugin, a Codex skill `lint-fix` and a Cursor skill `polish`."""
    home = tmp_path / "home"
    app, other = home / "work/app", home / "work/site"
    _write(home / ".claude.json", {"projects": {str(app): {}, str(other): {}}})
    _write(home / ".claude/settings.json", user)
    _write(
        home / ".claude/plugins/installed_plugins.json",
        {"plugins": {PLUGIN: [{"installPath": str(home / "nowhere")}]}},
    )
    _skill(home / ".claude/skills", "deploy")
    (app / ".claude").mkdir(parents=True)
    (other / ".claude").mkdir(parents=True)
    if local is not None:
        _write(app / ".claude/settings.local.json", local)
    if site is not None:
        _write(other / ".claude/settings.json", site)
    _write(home / ".codex/config.toml", CODEX)
    _skill(home / ".agents/skills", "lint-fix")
    _skill(home / ".cursor/skills", "polish")
    return home, app, other


@contextmanager
def _page(home):
    def run(command, cwd):
        raise AssertionError(f"no client command runs here: {command}")

    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home, run=run)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        yield page


def _item(page, client, name, kind="skill"):
    query = {"client": client, "kind": kind}
    found = [i for i in page.get("/api/items", params=query).json() if i["name"] == name]
    assert found, (client, name)
    return found[0]["id"]


def _skills(home, client):
    return [i for i in build_inventory(home).items if i.client == client and i.kind == "skill"]


def _project(page, folder):
    return next(p["id"] for p in page.get("/api/projects").json() if p["path"] == str(folder))


def _rule(client, item, scope="all", project=None, off=True):
    params = {"scope": scope, "off": off, **({"project": project} if project else {})}
    targets = [{"client": client, "item": item}]
    return {
        "id": "r1",
        "kind": "skill.rule",
        "title": "Turn it off",
        "targets": targets,
        "params": params,
    }


def _preview(page, *requests):
    return page.post("/api/batch/preview", json={"requests": list(requests)}, headers=POST)


def _verb(page, change_id, verb):
    answer = page.post(f"/api/changes/{change_id}/{verb}", headers=POST)
    assert answer.status_code == 200, answer.text
    return answer.json()


def _round_trip(page, *requests):
    """Preview, Apply and check the state; returns (the preview's answer, apply, undo)."""
    answer = _preview(page, *requests)
    assert answer.status_code == 200, answer.text
    change = answer.json()
    applied = _verb(page, change["id"], "apply")
    assert applied["state"] == "verified", applied
    return change, applied, lambda: _verb(page, change["id"], "undo")


def test_turn_off_a_claude_code_skill_for_all_projects_and_undo(tmp_path):
    home, _, _ = _home(tmp_path)
    settings = home / ".claude/settings.json"
    with _page(home) as page:
        rule = _rule("claude_code", _item(page, "claude_code", "deploy"))
        change, _, undo = _round_trip(page, rule)
        assert change["target"]["scope"] == "all"
        (row,) = change["rows"]
        assert row["after"] == [{"client": "claude_code", "state": "off", "word": "Off"}]
        data = json.loads(settings.read_text())
        assert data["skillOverrides"] == {"deploy": "off"}
        assert data["theme"] == "dark"
        # The scan reads it back as off.
        (skill,) = [i for i in _skills(home, "claude_code") if i.name == "deploy"]
        assert str(skill.enabled) == "off"
        assert undo()["state"] == "undone"
    assert settings.read_text() == USER


def test_turn_off_in_one_project_writes_the_local_settings_and_undo(tmp_path):
    local = '{\n  "permissions": {\n    "allow": ["Bash(ls)"]\n  }\n}\n'
    home, app, _ = _home(tmp_path, local=local)
    path = app / ".claude/settings.local.json"
    with _page(home) as page:
        rule = _rule(
            "claude_code", _item(page, "claude_code", "deploy"), "project", _project(page, app)
        )
        change, _, undo = _round_trip(page, rule)
        assert change["target"] == {
            "scope": "project",
            "project": str(app),
            "others_unchanged": True,
        }
        assert json.loads(path.read_text())["skillOverrides"] == {"deploy": "off"}
        assert (home / ".claude/settings.json").read_text() == USER
        assert undo()["state"] == "undone"
    assert path.read_text() == local


def test_one_project_waits_while_the_user_settings_have_skill_overrides(tmp_path):
    user = {"skillOverrides": {"other": "off"}}
    home, app, _ = _home(tmp_path, user=user)
    with _page(home) as page:
        rule = _rule(
            "claude_code", _item(page, "claude_code", "deploy"), "project", _project(page, app)
        )
        answer = _preview(page, rule)
    assert answer.status_code == 422
    assert answer.json() == {"detail": NO_SKILL_MERGE, "row": "r1"}
    assert NO_SKILL_MERGE == (
        "Claude Code may not merge skill settings across files; turn it off for all projects "
        "instead."
    )


def test_one_project_waits_while_its_shared_file_has_skill_overrides(tmp_path):
    home, _, other = _home(tmp_path, user={}, site={"skillOverrides": {"tidy": "off"}})
    with _page(home) as page:
        item = _item(page, "claude_code", "deploy")
        answer = _preview(page, _rule("claude_code", item, "project", _project(page, other)))
        assert answer.json() == {"detail": NO_SKILL_MERGE, "row": "r1"}
        # A project with no .claude folder gets no new folder: Kitden writes one file only.
        (other / ".claude/settings.json").unlink()
        (other / ".claude").rmdir()
        answer = _preview(page, _rule("claude_code", item, "project", _project(page, other)))
    assert answer.json() == {"detail": NO_CLAUDE_FOLDER.format(folder="site"), "row": "r1"}


def test_use_the_shared_rule_removes_the_project_key(tmp_path):
    local = '{\n  "skillOverrides": {\n    "deploy": "off",\n    "other": "on"\n  }\n}\n'
    home, app, _ = _home(tmp_path, local=local)
    path = app / ".claude/settings.local.json"
    with _page(home) as page:
        item = _item(page, "claude_code", "deploy")
        rule = _rule("claude_code", item, "project", _project(page, app), off=False)
        change, _, undo = _round_trip(page, rule)
        (row,) = change["rows"]
        assert row["after"] == [
            {"client": "claude_code", "state": "on", "word": "Follows all projects"}
        ]
        assert json.loads(path.read_text())["skillOverrides"] == {"other": "on"}
        assert undo()["state"] == "undone"
    assert path.read_text() == local


def test_turn_off_a_plugin_in_one_project(tmp_path):
    home, app, _ = _home(tmp_path)
    path = app / ".claude/settings.local.json"
    with _page(home) as page:
        plugin = _item(page, "claude_code", PLUGIN, kind="plugin")
        change, _, undo = _round_trip(
            page, _rule("claude_code", plugin, "project", _project(page, app))
        )
        assert change["target"]["scope"] == "project"
        assert json.loads(path.read_text()) == {"enabledPlugins": {PLUGIN: False}}
        # Only this project: the user file still turns it on.
        assert (home / ".claude/settings.json").read_text() == USER
        assert undo()["state"] == "undone"
    assert not path.exists()


def test_turn_off_a_codex_skill_adds_skills_config_and_undo(tmp_path):
    home, app, _ = _home(tmp_path)
    config = home / ".codex/config.toml"
    with _page(home) as page:
        item = _item(page, "codex", "lint-fix")
        refused = _preview(page, _rule("codex", item, "project", _project(page, app)))
        assert refused.json() == {"detail": CODEX_NO_PROJECT, "row": "r1"}
        change, _, undo = _round_trip(page, _rule("codex", item))
        assert change["rows"][0]["after"] == [{"client": "codex", "state": "off", "word": "Off"}]
        text = config.read_text()
        assert text.startswith(CODEX)  # comments and order stay
        skill = os.path.realpath(home / ".agents/skills/lint-fix/SKILL.md")
        assert tomllib.loads(text)["skills"]["config"] == [{"path": skill, "enabled": False}]
        (read,) = [i for i in _skills(home, "codex") if i.name == "lint-fix"]
        assert str(read.enabled) == "off"
        assert undo()["state"] == "undone"
    assert config.read_text() == CODEX


def test_cursor_is_refused_with_its_reason(tmp_path):
    home, _, _ = _home(tmp_path)
    with _page(home) as page:
        answer = _preview(page, _rule("cursor", _item(page, "cursor", "polish")))
    assert answer.status_code == 422
    assert answer.json() == {"detail": CURSOR_NO_SKILL_SWITCH, "row": "r1"}
    assert CURSOR_NO_SKILL_SWITCH == "Cursor has no switch to turn off one skill."


def test_an_all_projects_change_names_a_project_that_keeps_its_own_rule(tmp_path):
    # app's local file keeps deploy on; site's shared file has rules for other skills only.
    local = {"skillOverrides": {"deploy": "on"}}
    home, _, _ = _home(tmp_path, local=local, site={"skillOverrides": {"tidy": "off"}})
    with _page(home) as page:
        answer = _preview(page, _rule("claude_code", _item(page, "claude_code", "deploy")))
    assert answer.status_code == 200, answer.text
    (after,) = answer.json()["rows"][0]["after"]
    assert after["word"] == "Off"
    assert after["note"] == (
        "It stays on in app, which has its own rule. "
        "site has its own skill settings; it may keep this skill on."
    )


def _row(row_id, rule):
    return {**rule, "id": row_id}


def test_two_codex_skills_turn_off_in_one_tray_and_undo(tmp_path):
    home, _, _ = _home(tmp_path)
    _skill(home / ".agents/skills", "tidy")
    # A table Codex has already, with comments of its own: it stays as it is.
    config = home / ".codex/config.toml"
    before = CODEX + '\n[[skills.config]]\npath = "/elsewhere/SKILL.md"  # mine\nenabled = false\n'
    config.write_text(before)
    with _page(home) as page:
        rows = [
            _row("a", _rule("codex", _item(page, "codex", "lint-fix"))),
            _row("b", _rule("codex", _item(page, "codex", "tidy"))),
        ]
        change, _, undo = _round_trip(page, *rows)
        assert len(change["steps"]) == 2
        text = config.read_text()
        assert text.startswith(before)
        paths = [r["path"] for r in tomllib.loads(text)["skills"]["config"]]
        assert paths[0] == "/elsewhere/SKILL.md" and len(paths) == 3
        off = {i.name for i in _skills(home, "codex") if str(i.enabled) == "off"}
        assert off == {"lint-fix", "tidy"}
        assert undo()["state"] == "undone"
    assert config.read_text() == before


def test_an_existing_codex_entry_is_turned_off_where_it_is(tmp_path):
    home, _, _ = _home(tmp_path)
    skill = os.path.realpath(home / ".agents/skills/lint-fix/SKILL.md")
    config = home / ".codex/config.toml"
    before = f'{CODEX}\n[[skills.config]]\npath = "{skill}"  # mine\nenabled = true  # on for now\n'
    config.write_text(before)
    with _page(home) as page:
        _, _, undo = _round_trip(page, _rule("codex", _item(page, "codex", "lint-fix")))
        assert config.read_text() == before.replace("enabled = true", "enabled = false")
        assert undo()["state"] == "undone"
    assert config.read_text() == before


def test_a_codex_file_kitden_cannot_read_is_named(tmp_path):
    home, _, _ = _home(tmp_path)
    with _page(home) as page:
        item = _item(page, "codex", "lint-fix")
        (home / ".codex/config.toml").write_bytes(b"\xff\xfe not text")
        answer = _preview(page, _rule("codex", item))
    assert answer.status_code == 422
    assert answer.json() == {"detail": CHANGE_UNREAD.format("config.toml"), "row": "r1"}


def test_a_tray_never_writes_skill_rules_in_the_user_and_a_project_file(tmp_path):
    home, app, _ = _home(tmp_path)
    with _page(home) as page:
        item = _item(page, "claude_code", "deploy")
        everywhere = _row("a", _rule("claude_code", item))
        here = _row("b", _rule("claude_code", item, "project", _project(page, app)))
        for first, then in ((everywhere, here), (here, everywhere)):
            answer = page.post("/api/batch/check", json={"requests": [first, then]}, headers=POST)
            assert answer.json() == {"ok": False, "reason": NO_SKILL_MERGE, "row": then["id"]}


def test_a_project_only_skill_is_never_turned_off_in_the_users_file(tmp_path):
    home, app, _ = _home(tmp_path)
    _skill(app / ".claude/skills", "app-notes")
    with _page(home) as page:
        item = _item(page, "claude_code", "app-notes")
        answer = _preview(page, _rule("claude_code", item))
        assert answer.json() == {"detail": PROJECT_SKILL_ALL, "row": "r1"}
        assert (
            PROJECT_SKILL_ALL == "This skill is only in one project; turn it off in that project."
        )
        # In its project, the rule goes to the project's local settings.
        _round_trip(page, _rule("claude_code", item, "project", _project(page, app)))
    assert json.loads((app / ".claude/settings.local.json").read_text()) == {
        "skillOverrides": {"app-notes": "off"}
    }
    assert (home / ".claude/settings.json").read_text() == USER


def test_codex_skills_written_as_an_inline_list_are_refused_when_the_row_is_added(tmp_path):
    home, _, _ = _home(tmp_path)
    config = home / ".codex/config.toml"
    skill = os.path.realpath(home / ".agents/skills/other/SKILL.md")
    inline = [
        f'skills = {{ config = [ {{ path = "{skill}", enabled = true }} ] }}\n',
        f'[skills]\nconfig = [ {{ path = "{skill}", enabled = true }} ]\n',
    ]
    for text in inline:
        config.write_text(CODEX.split("[mcp_servers")[0] + text)
        before = config.read_text()
        with _page(home) as page:
            answer = _preview(page, _rule("codex", _item(page, "codex", "lint-fix")))
        assert answer.status_code == 422, text
        assert answer.json() == {
            "detail": "Codex's skills settings are not a list of tables; Kitden leaves them.",
            "row": "r1",
        }
        assert config.read_text() == before


def test_a_rule_that_makes_the_local_settings_file_says_so_once(tmp_path):
    home, app, _ = _home(tmp_path)
    with _page(home) as page:
        project = _project(page, app)
        skill = _rule("claude_code", _item(page, "claude_code", "deploy"), "project", project)
        answer = _preview(page, skill)
        (after,) = answer.json()["rows"][0]["after"]
        assert after["note"] == NEW_LOCAL_FILE.format(folder="app")
        assert NEW_LOCAL_FILE == (
            "Kitden creates .claude/settings.local.json in {folder}. If git lists it, add it to "
            ".gitignore."
        )
        # The file is there already: nothing to say.
        _write(app / ".claude/settings.local.json", {})
        (after,) = _preview(page, skill).json()["rows"][0]["after"]
        assert "note" not in after


def test_use_the_shared_rule_removes_a_plugins_project_key_and_undo_puts_it_back(tmp_path):
    local = '{\n  "enabledPlugins": {\n    "lint@tools": false\n  },\n  "theme": "light"\n}\n'
    home, app, _ = _home(tmp_path, local=local)
    path = app / ".claude/settings.local.json"
    with _page(home) as page:
        plugin = _item(page, "claude_code", PLUGIN, kind="plugin")
        rule = _rule("claude_code", plugin, "project", _project(page, app), off=False)
        change, _, undo = _round_trip(page, rule)
        (row,) = change["rows"]
        assert row["after"] == [
            {"client": "claude_code", "state": "on", "word": "Follows all projects"}
        ]
        assert json.loads(path.read_text()) == {"enabledPlugins": {}, "theme": "light"}
        assert undo()["state"] == "undone"
    assert path.read_text() == local


def _in_repository(home):
    """`work/repo` is a git repository, and the known project `site` moves into it as `web`."""
    repo, web = home / "work/repo", home / "work/repo/web"
    (repo / ".git").mkdir(parents=True)
    (repo / ".claude").mkdir()
    (web / ".claude").mkdir(parents=True)
    _write(home / ".claude.json", {"projects": {str(web): {}}})
    return repo, web


def test_a_rule_for_a_project_in_a_repository_subfolder_goes_to_the_roots_local_file(tmp_path):
    # checked 2026-10-27 (code.claude.com/docs/en/settings): Claude Code reads the root's
    # .claude/settings.local.json first when started in a subfolder of a git repository.
    home, _, _ = _home(tmp_path)
    repo, web = _in_repository(home)
    root = repo / ".claude/settings.local.json"
    with _page(home) as page:
        item = _item(page, "claude_code", "deploy")
        rule = _rule("claude_code", item, "project", _project(page, web))
        change, _, undo = _round_trip(page, rule)
        (after,) = change["rows"][0]["after"]
        assert after["note"] == (
            f"{NEW_LOCAL_FILE.format(folder='repo')} {REPO_RULE.format(folder='repo')}"
        )
        assert REPO_RULE == (
            "Claude Code keeps this rule in {folder}'s local settings, so it holds in all of "
            "{folder}."
        )
        assert json.loads(root.read_text()) == {"skillOverrides": {"deploy": "off"}}
        assert not (web / ".claude/settings.local.json").exists()
        assert undo()["state"] == "undone"
    assert not root.exists()


def test_use_the_shared_rule_takes_the_key_from_both_local_files_and_undo_puts_them_back(
    tmp_path,
):
    # A file an earlier Claude Code left in the starting folder is still read (docs, same day).
    home, _, _ = _home(tmp_path)
    repo, web = _in_repository(home)
    root, own = repo / ".claude/settings.local.json", web / ".claude/settings.local.json"
    root_text = '{\n    "skillOverrides": {\n        "deploy": "off"\n    }\n}\n'
    own_text = '{"skillOverrides": {"deploy": "on", "tidy": "off"}}\n'
    root.write_text(root_text)
    own.write_text(own_text)
    with _page(home) as page:
        item = _item(page, "claude_code", "deploy")
        rule = _rule("claude_code", item, "project", _project(page, web), off=False)
        change, _, undo = _round_trip(page, rule)
        assert [s["path"] for s in change["steps"]] == [str(own), str(root)]
        # One client, one word.
        assert change["rows"][0]["after"] == [
            {
                "client": "claude_code",
                "state": "on",
                "word": "Follows all projects",
                "note": REPO_RULE.format(folder="repo"),
            }
        ]
        assert json.loads(root.read_text())["skillOverrides"] == {}
        assert json.loads(own.read_text())["skillOverrides"] == {"tidy": "off"}
        assert undo()["state"] == "undone"
    assert (root.read_text(), own.read_text()) == (root_text, own_text)


def test_turn_off_this_copy_in_codex_for_a_skill_in_one_project(tmp_path):
    home, app, _ = _home(tmp_path)
    config = home / ".codex/config.toml"
    config.write_text(f'{CODEX}\n[projects."{app}"]\ntrust_level = "trusted"\n')
    before = config.read_text()
    _skill(app / ".agents/skills", "app-style")
    with _page(home) as page:
        item = _item(page, "codex", "app-style")
        change, _, undo = _round_trip(page, _rule("codex", item))
        skill = os.path.realpath(app / ".agents/skills/app-style/SKILL.md")
        assert tomllib.loads(config.read_text())["skills"]["config"] == [
            {"path": skill, "enabled": False}
        ]
        # The scan reads that copy back as off.
        (read,) = [i for i in _skills(home, "codex") if i.name == "app-style"]
        assert str(read.enabled) == "off"
        assert undo()["state"] == "undone"
    assert config.read_text() == before
