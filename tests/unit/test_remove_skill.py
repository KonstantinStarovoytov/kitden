"""Removing a skill from the Library: back the folder up, remove it, Undo copies it back
(spec 3.2)."""

import pytest

from kitden.changes.copy_folder import digest
from kitden.gateways import data_dir
from tests.unit.test_api_skill_install import POST, _client


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Claude Code, Codex and Cursor; Cursor reads the other clients' skill folders."""
    c = _client(tmp_path, monkeypatch)
    yield c
    c.__exit__(None, None, None)


def _skill_item(client, who, name, where=None):
    items = client.get(f"/api/items?client={who}&kind=skill").json()
    return next(
        i
        for i in items
        if i["name"] == name and (where is None or i["source"]["path"] == f"{where}/SKILL.md")
    )


def _remove(client, item_id):
    body = {"action": "skill.remove", "targets": [{"item": item_id}], "params": {}}
    return client.post("/api/changes/preview", json=body, headers=POST)


def _row(client, name):
    rows = client.get("/api/library?kind=skill").json()["rows"]
    return next(r for r in rows if r["name"] == name)


def test_removing_a_skill_backs_it_up_and_undo_copies_it_back(client):
    home = client.home
    folder = home / ".claude/skills/brandkit"
    before = digest(folder)
    brandkit = _skill_item(client, "claude_code", "brandkit")
    assert "skill.remove" in brandkit["actions"]
    change = _remove(client, brandkit["id"]).json()
    step = change["steps"][0]
    assert (step["client"], step["name"], step["reaches"], step["command"]) == (
        "claude_code",
        "brandkit",
        ["claude_code", "cursor"],
        None,
    )
    assert step["path"] == str(folder) and step["diff"] == "-SKILL.md" and step["keeps"] == []
    assert change["after"] == [
        {"client": "claude_code", "state": "off", "word": "Removed"},
        {"client": "cursor", "state": "off", "word": "Removed"},
    ]
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified", applied.get("error")
    assert not folder.exists()
    copies = list((data_dir(home) / "changes" / change["id"]).glob("folder-brandkit"))
    assert len(copies) == 1 and digest(copies[0]) == before
    rows = client.get("/api/library?kind=skill").json()["rows"]
    assert all(
        r["name"] != "brandkit" or r["cells"]["claude_code"]["state"] == "none" for r in rows
    )
    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")
    assert digest(folder) == before
    parts = client.get("/api/changes").json()[0]["title_parts"]
    assert (parts["action"], parts["steps"][0]["reaches"]) == (
        "skill.remove",
        ["claude_code", "cursor"],
    )


def test_a_plugin_skill_and_a_cross_loaded_skill_cannot_be_removed(client):
    assert (
        _remove(client, _skill_item(client, "claude_code", "brainstorming")["id"]).status_code
        == 422
    )
    assert _remove(client, _skill_item(client, "cursor", "brandkit")["id"]).status_code == 422
    # The shared folder is Codex's to remove.
    shared = _skill_item(
        client, "cursor", "docker-expert", where=str(client.home / ".agents/skills/docker-expert")
    )
    assert "skill.remove" not in shared["actions"]
    assert _remove(client, shared["id"]).status_code == 422


def test_a_linked_skill_folder_is_refused(client, tmp_path):
    real = tmp_path / "elsewhere/linked"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("---\nname: linked\n---\n")
    (client.home / ".claude/skills/linked").symlink_to(real)
    client.post("/api/rescan", headers=POST)
    linked = _skill_item(client, "claude_code", "linked")
    assert "skill.remove" not in linked["actions"]
    assert _remove(client, linked["id"]).status_code == 422
    assert (client.home / ".claude/skills/linked").is_symlink() and (real / "SKILL.md").exists()


def test_a_skill_whose_skill_md_is_a_link_is_not_offered(client, tmp_path):
    # Its real SKILL.md sits elsewhere; removing that folder would remove the wrong one.
    real = tmp_path / "elsewhere/inner"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("---\nname: inner\n---\n")
    folder = client.home / ".claude/skills/inner"
    folder.mkdir()
    (folder / "SKILL.md").symlink_to(real / "SKILL.md")
    client.post("/api/rescan", headers=POST)
    assert "skill.remove" not in _skill_item(client, "claude_code", "inner")["actions"]


def test_undo_leaves_a_folder_that_came_back(client):
    folder = client.home / ".agents/skills/docker-expert"
    change = _remove(
        client, _skill_item(client, "codex", "docker-expert", where=str(folder))["id"]
    ).json()
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    folder.mkdir(parents=True)
    (folder / "notes.md").write_text("mine\n")
    blocked = client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert blocked.status_code == 409 and blocked.json()["state"] == "undo_blocked"
    assert "is back" in blocked.json()["error"] and (folder / "notes.md").read_text() == "mine\n"


def test_a_duplicate_skill_keeps_one(client):
    # Codex loads docker-expert from ~/.agents/skills and ~/.codex/skills.
    flag = next(f for f in _row(client, "docker-expert")["flags"] if f["level"] == "warning")
    assert (flag["fix"], flag["fix_action"]) == (
        "Remove one copy to keep the other.",
        "skill.remove",
    )
    definitions = client.get("/api/explain?name=docker-expert&kind=skill").json()["definitions"]
    assert [d["source"] for d in definitions if "skill.remove" in d["actions"]] == [
        str(client.home / ".agents/skills/docker-expert/SKILL.md"),
        str(client.home / ".codex/skills/docker-expert/SKILL.md"),
    ]
    own = _skill_item(
        client, "codex", "docker-expert", where=str(client.home / ".codex/skills/docker-expert")
    )
    change = _remove(client, own["id"]).json()
    assert change["steps"][0]["keeps"] == ["codex", "cursor"]
    # Cursor reads ~/.codex/skills too (Include Third-Party Plugins is on in the fixture). Both
    # still load the copy in ~/.agents/skills, so neither loses the skill.
    assert change["after"] == [
        {
            "client": "codex",
            "state": "on",
            "word": "Loads once",
            "note": "Codex still loads another copy of docker-expert.",
        },
        {
            "client": "cursor",
            "state": "on",
            "word": "Loads once",
            "note": "Cursor still loads another copy of docker-expert.",
        },
    ]
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    parts = client.get("/api/changes").json()[0]["title_parts"]
    assert parts["steps"][0]["keeps"] == ["codex", "cursor"]
    assert not [f for f in _row(client, "docker-expert")["flags"] if f["level"] == "warning"]


def test_a_project_skill_removal_names_the_project(client):
    site = _skill_item(client, "claude_code", "site-style")
    change = _remove(client, site["id"]).json()
    assert (change["steps"][0]["scope"], change["shared_file_warning"]) == ("project", True)
    assert (
        client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"]
        == "verified"
    )
    assert (
        client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
    )
