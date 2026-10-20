"""Adding a skill from Discover: the fewest copies, one review, verify, Undo (phase 2)."""

import pytest
from starlette.testclient import TestClient

import kitden.clients.base as base
from kitden.changes.client_cli import CommandResult
from kitden.changes.copy_folder import digest
from kitden.clients.cursor import REACTIVE_KEY
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_skills_catalog import (
    GLEAN,
    PLUGIN,
    add_cursor_plugin,
    add_skills_marketplace,
    install_in_cursor,
)

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
TIDY = f"tidy@{PLUGIN}"


def _no_run(command, cwd):
    return CommandResult(1, "a skill copy runs no command")


def _client(tmp_path, monkeypatch, third_party=True):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    flags = {} if third_party else {REACTIVE_KEY: {"thirdPartyExtensibilityEnabled": False}}
    write_cursor_fixture_state(home, flags)
    add_skills_marketplace(home)
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home, run=_no_run)
    c = TestClient(app, base_url=ORIGIN, follow_redirects=False)
    c.__enter__()
    c.get("/?token=tok")
    c.home = home
    return c


@pytest.fixture
def client(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    yield c
    c.__exit__(None, None, None)


@pytest.fixture
def strict_cursor(tmp_path, monkeypatch):
    """Cursor with Include Third-Party Plugins off: it reads only its own folders."""
    c = _client(tmp_path, monkeypatch, third_party=False)
    yield c
    c.__exit__(None, None, None)


def _preview(client, skill, clients):
    body = {
        "action": "skill.install",
        "targets": [{"client": c} for c in clients],
        "params": {"skill": skill},
    }
    return client.post("/api/changes/preview", json=body, headers=POST)


def _targets(change):
    return [(s["client"], s["path"].split("/home/")[1], s["reaches"]) for s in change["steps"]]


def test_the_catalog_serves_skills_with_their_own_counts(client):
    answer = client.get("/api/catalog?kind=skill").json()
    names = {o["name"] for o in answer["offers"]}
    assert {"tidy", "rooted", "reaching", "brandkit", "docker-expert"} <= names
    assert answer["all"] == answer["total"] == len(answer["offers"])
    # Marketplaces count the plugin skills only; a client's own skills have none.
    assert answer["marketplaces"] == [{"name": "claude-plugins-official", "count": 5}]
    assert answer["facets"]["categories"] == []
    found = client.get("/api/catalog?kind=skill&q=tidy").json()["offers"]
    assert [o["id"] for o in found] == [TIDY]
    added = client.get("/api/catalog?kind=skill&only=added").json()["offers"]
    assert all(o["installed"] for o in added) and any(o["name"] == "brandkit" for o in added)


def test_one_client_gets_one_copy_in_its_own_folder(client):
    for chosen, where, reaches in (
        (["claude_code"], ".claude/skills/tidy", ["claude_code", "cursor"]),
        (["codex"], ".agents/skills/tidy", ["codex", "cursor"]),
        (["cursor"], ".cursor/skills/tidy", ["cursor"]),
    ):
        change = _preview(client, TIDY, chosen).json()
        assert _targets(change) == [(chosen[0], where, reaches)], chosen
        assert change["steps"][0]["diff"].splitlines() == [
            "+SKILL.md",
            "+references/rules.md",
            "+scripts/check",
            "+scripts/run.sh",
        ]
        assert change["steps"][0]["command"] is None
        client.post(f"/api/changes/{change['id']}/cancel", headers=POST)


def test_codex_and_cursor_share_one_copy(client):
    change = _preview(client, TIDY, ["codex", "cursor"]).json()
    assert _targets(change) == [("codex", ".agents/skills/tidy", ["codex", "cursor"])]
    assert change["after"] == [
        {"client": "codex", "state": "on", "word": "Loads"},
        {"client": "cursor", "state": "on", "word": "Loads"},
    ]


def test_cursor_reads_claude_codes_folder_so_two_copies_make_it_load_twice(client):
    one = _preview(client, TIDY, ["claude_code", "cursor"]).json()
    assert _targets(one) == [("claude_code", ".claude/skills/tidy", ["claude_code", "cursor"])]
    assert [e["word"] for e in one["after"]] == ["Loads", "Loads"]
    client.post(f"/api/changes/{one['id']}/cancel", headers=POST)

    both = _preview(client, TIDY, ["claude_code", "codex"]).json()
    assert [t[1] for t in _targets(both)] == [".claude/skills/tidy", ".agents/skills/tidy"]
    cursor = next(e for e in both["after"] if e["client"] == "cursor")
    assert cursor["word"] == "Loads twice"
    assert cursor["note"] == (
        "Cursor reads two folders that hold this skill, so it loads the skill twice."
    )
    assert "note" not in next(e for e in both["after"] if e["client"] == "codex")


def test_with_third_party_off_cursor_gets_its_own_copy(strict_cursor):
    change = _preview(strict_cursor, TIDY, ["claude_code", "cursor"]).json()
    assert _targets(change) == [
        ("claude_code", ".claude/skills/tidy", ["claude_code"]),
        ("cursor", ".cursor/skills/tidy", ["cursor"]),
    ]
    assert [e["word"] for e in change["after"]] == ["Loads", "Loads"]


def test_a_skill_that_needs_its_plugin_is_refused(client):
    answer = _preview(client, f"rooted@{PLUGIN}", ["claude_code"])
    assert answer.status_code == 422
    assert answer.json()["detail"] == (
        "This skill needs the rest of its plugin. Add the plugin instead."
    )


def test_a_client_that_has_the_skill_is_refused(client):
    answer = _preview(client, "brandkit@skills", ["claude_code"])
    assert answer.status_code == 422
    assert "Claude Code already has brandkit" in answer.json()["detail"]
    # Cursor loads it from Claude Code's folder already.
    answer = _preview(client, "brandkit@skills", ["cursor"])
    assert answer.status_code == 422
    assert "Cursor already has brandkit" in answer.json()["detail"]
    assert _preview(client, "nothing@nowhere", ["codex"]).status_code == 422


def test_apply_copies_then_undo_removes_and_a_changed_copy_stays(client):
    home = client.home
    source = (
        home / ".claude/plugins/marketplaces/claude-plugins-official/plugins/toolbox/skills/tidy"
    )
    change = _preview(client, TIDY, ["claude_code", "codex"]).json()
    assert not (home / ".claude/skills/tidy").exists()

    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified", applied.get("error")
    for folder in (home / ".claude/skills/tidy", home / ".agents/skills/tidy"):
        assert digest(folder) == digest(source)
    tidy = next(o for o in client.get("/api/catalog?kind=skill&q=tidy").json()["offers"])
    assert tidy["installed"] == {
        "claude_code": "Installed",
        "codex": "Installed",
        "cursor": "Installed",
    }
    assert tidy["routes"] == {}

    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")
    assert not (home / ".claude/skills/tidy").exists()
    assert not (home / ".agents/skills/tidy").exists()
    assert source.is_dir()

    change = _preview(client, TIDY, ["codex"]).json()
    assert (
        client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"]
        == "verified"
    )
    (home / ".agents/skills/tidy/SKILL.md").write_text("my notes\n")
    blocked = client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert blocked.status_code == 409
    assert blocked.json()["state"] == "undo_blocked"
    assert "changed after the change was applied" in blocked.json()["error"]
    assert (home / ".agents/skills/tidy/SKILL.md").read_text() == "my notes\n"


def test_a_copied_skill_is_a_change_on_the_changes_page(client):
    change = _preview(client, TIDY, ["cursor"]).json()
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    entry = client.get("/api/changes").json()[0]
    assert (entry["action"], entry["state"]) == ("skill.install", "verified")
    assert entry["steps"][0]["reaches"] == ["cursor"]
    assert entry["steps"][0]["path"].endswith(".cursor/skills/tidy")


# Add skills: a plugin's self-contained skills, copied into one client in one change -------

BRAINSTORMING = f"brainstorming@{PLUGIN}"
LEFT_OUT = [
    {"name": "reaching", "why": "needs the rest of the plugin"},
    {"name": "rooted", "why": "needs the rest of the plugin"},
]


def _add_skills(client, clients, plugin=PLUGIN):
    body = {
        "action": "plugin.skills",
        "targets": [{"client": c} for c in clients],
        "params": {"plugin": plugin},
    }
    return client.post("/api/changes/preview", json=body, headers=POST)


def _apply(client, change):
    return client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()


def test_add_skills_is_one_change_that_undo_removes_whole(client):
    home = client.home
    change = _add_skills(client, ["codex"]).json()
    assert [(s["client"], s["name"]) for s in change["steps"]] == [
        ("codex", "brainstorming"),
        ("codex", "tidy"),
    ]
    assert change["left_out"] == LEFT_OUT
    # Claude Code loads a skill named brainstorming from the superpowers plugin already. Cursor
    # loads it from there too, and reads the shared folder the copies go to.
    assert change["after"] == [
        {"client": "claude_code", "state": "on", "word": "Loads"},
        {"client": "codex", "state": "on", "word": "Loads"},
        {
            "client": "cursor",
            "state": "on",
            "word": "Loads twice",
            "note": "Cursor would load brainstorming twice, from two folders.",
        },
    ]
    assert not (home / ".agents/skills/tidy").exists()

    assert _apply(client, change)["state"] == "verified"
    for name in ("brainstorming", "tidy"):
        assert (home / ".agents/skills" / name / "SKILL.md").is_file()
    # The same plugin has nothing left to add there.
    again = _add_skills(client, ["codex"])
    assert again.status_code == 422
    assert again.json()["detail"] == "Codex has every skill in toolbox it can use"

    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")
    assert not (home / ".agents/skills/tidy").exists()
    assert not (home / ".agents/skills/brainstorming").exists()
    entry = client.get("/api/changes").json()[0]
    assert (entry["action"], entry["state"]) == ("plugin.skills", "undone")


def test_add_skills_skips_what_the_client_has_and_undo_leaves_that_alone(client):
    home = client.home
    earlier = _preview(client, BRAINSTORMING, ["codex"]).json()
    assert _apply(client, earlier)["state"] == "verified"
    kept = digest(home / ".agents/skills/brainstorming")

    change = _add_skills(client, ["codex"]).json()
    assert [s["name"] for s in change["steps"]] == ["tidy"]
    assert change["steps"][0]["reaches"] == ["codex", "cursor"]
    assert change["left_out"] == [
        {"name": "brainstorming", "why": "Codex already has it"},
        *LEFT_OUT,
    ]
    assert change["after"] == [
        {"client": "codex", "state": "on", "word": "Loads"},
        {"client": "cursor", "state": "on", "word": "Loads"},
    ]
    assert _apply(client, change)["state"] == "verified"
    assert (home / ".agents/skills/tidy/SKILL.md").is_file()

    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")
    assert not (home / ".agents/skills/tidy").exists()
    assert digest(home / ".agents/skills/brainstorming") == kept


def test_add_skills_says_when_a_client_would_load_a_skill_twice(client):
    # Cursor already reads Codex's copy of tidy; Claude Code's folder would be a second one.
    assert _apply(client, _preview(client, TIDY, ["codex"]).json())["state"] == "verified"
    change = _add_skills(client, ["claude_code"]).json()
    assert [s["name"] for s in change["steps"]] == ["tidy"]
    cursor = next(e for e in change["after"] if e["client"] == "cursor")
    assert cursor["word"] == "Loads twice"
    assert cursor["note"] == (
        "Cursor reads two folders that hold this skill, so it loads the skill twice."
    )


def test_add_skills_leaves_out_a_skill_the_client_loads_from_another_plugin(client):
    # Claude Code loads brainstorming from the superpowers plugin, so it takes no copy of it.
    change = _add_skills(client, ["claude_code"]).json()
    assert [s["name"] for s in change["steps"]] == ["tidy"]
    assert change["left_out"] == [
        {"name": "brainstorming", "why": "Claude Code already has it"},
        *LEFT_OUT,
    ]
    assert change["after"] == [
        {"client": "claude_code", "state": "on", "word": "Loads"},
        {"client": "cursor", "state": "on", "word": "Loads"},
    ]


def test_add_skills_from_a_cursor_plugin_says_cursor_loads_them_twice(client):
    # Cursor has glean (skills a and b) and reads Claude Code's folder too.
    add_cursor_plugin(client.home)
    install_in_cursor(client.home, GLEAN)
    client.post("/api/rescan", headers=POST)
    change = _add_skills(client, ["claude_code"], GLEAN).json()
    assert [(s["name"], s["reaches"]) for s in change["steps"]] == [
        ("a", ["claude_code", "cursor"]),
        ("b", ["claude_code", "cursor"]),
    ]
    assert change["after"] == [
        {"client": "claude_code", "state": "on", "word": "Loads"},
        {
            "client": "cursor",
            "state": "on",
            "word": "Loads twice",
            "note": "Cursor would load a, b twice, from two folders.",
        },
    ]
    # One skill copied on its own: the same.
    one = _preview(client, f"a@{GLEAN}", ["claude_code"]).json()
    assert one["after"][1]["word"] == "Loads twice"


def test_add_skills_leaves_nothing_out_when_every_skill_is_copied(client):
    change = _add_skills(client, ["codex"], "superpowers@claude-plugins-official").json()
    assert [s["name"] for s in change["steps"]] == ["brainstorming"]
    assert change["left_out"] == []
    # Only this action says what it leaves out.
    assert "left_out" not in _preview(client, TIDY, ["codex"]).json()


def test_add_skills_needs_one_client_and_a_plugin_with_skills(client):
    both = _add_skills(client, ["codex", "cursor"])
    assert (both.status_code, both.json()["detail"]) == (422, "Choose one client.")
    none = _add_skills(client, [])
    assert (none.status_code, none.json()["detail"]) == (422, "Choose one client.")
    unknown = _add_skills(client, ["codex"], "nothing@nowhere")
    assert unknown.status_code == 422
    assert unknown.json()["detail"] == "This plugin has no skills on this computer."
