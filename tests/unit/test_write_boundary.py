"""Kitden writes only in the home folder, its data folder, found clients' folders and known
projects (spec 1.3)."""

import os
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import kitden.web.app as page_app
from kitden.changes.backup import ChangeStore
from kitden.changes.engine import CLIENT_CLI, OUTSIDE, ChangeRefusedError, Engine, writable_roots
from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.clients.codex import CodexAdapter
from kitden.gateways import data_dir
from kitden.model import (
    ChangeState,
    Client,
    ClientStatus,
    FileEdit,
    Project,
    Scope,
    Step,
)
from kitden.views.inventory import Inventory, build_inventory
from tests.conftest import make_home

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}


def real(path):
    return Path(os.path.realpath(path))


def no_run(command, cwd):
    raise AssertionError("no command in this test")


def test_writable_roots_are_home_data_projects_and_found_client_folders(tmp_path):
    home, other = tmp_path / "home", tmp_path / "disk2/atlas"
    home.mkdir()
    found = Client("codex", "Codex", ClientStatus.FOUND, config_roots=(str(tmp_path / "codex"),))
    gone = Client("cursor", "Cursor", ClientStatus.NOT_FOUND, config_roots=(str(tmp_path / "x"),))
    inventory = Inventory(clients=[found, gone], projects=[Project(path=str(other), exists=False)])
    assert writable_roots(home, inventory) == [
        real(home),
        real(data_dir(home)),
        real(other),
        real(tmp_path / "codex"),
    ]


def test_a_path_outside_every_root_is_refused_before_it_is_read(tmp_path):
    home, outside = tmp_path / "home", tmp_path / "elsewhere/settings.json"
    home.mkdir()
    outside.parent.mkdir()
    outside.write_text("not json")  # a read would fail differently
    engine = Engine(ChangeStore(tmp_path / "store"), no_run, roots=lambda: [real(home)])
    edit = FileEdit(path=str(outside), fmt="json", key=("mcpServers", "x"), after={"url": "u"})
    with pytest.raises(ChangeRefusedError) as refused:
        engine.preview("mcp.add", [Step(client="cursor", scope=Scope.USER, name="x", edit=edit)])
    assert str(refused.value) == OUTSIDE


def test_a_known_project_outside_home_stays_writable(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    project = tmp_path / "disk2/atlas"
    project.mkdir(parents=True)
    inventory = Inventory(projects=[Project(path=str(project), exists=True)])
    engine = Engine(
        ChangeStore(data_dir(home)), no_run, roots=lambda: writable_roots(home, inventory)
    )
    step = ClaudeCodeAdapter(home).skill_copy_step(
        home / ".claude/skills/brandkit", ["claude_code"], str(project)
    )
    change = engine.preview("skill.install", [step])
    assert engine.apply(change.id).state is ChangeState.VERIFIED
    assert (project / ".claude/skills/brandkit/SKILL.md").is_file()


def test_a_link_out_of_home_is_refused_and_one_inside_is_not(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    settings = home / ".claude/settings.json"
    kept = home / "dotfiles/claude-settings.json"
    kept.parent.mkdir()
    kept.write_text(settings.read_text())
    settings.unlink()
    settings.symlink_to(kept)
    engine = Engine(
        ChangeStore(data_dir(home)), no_run, roots=lambda: writable_roots(home, Inventory())
    )

    def turn_off():
        key = ("enabledPlugins", "superpowers@claude-plugins-official")
        edit = FileEdit(path=str(settings), fmt="json", key=key, after=False)
        return [Step(client="claude_code", scope=Scope.USER, name=key[1], edit=edit)]

    engine.preview("plugin.disable", turn_off())  # the file itself is in the home folder
    away = tmp_path / "elsewhere/claude-settings.json"
    away.parent.mkdir()
    away.write_text(kept.read_text())
    settings.unlink()
    settings.symlink_to(away)
    with pytest.raises(ChangeRefusedError) as refused:
        engine.preview("plugin.disable", turn_off())
    assert str(refused.value) == OUTSIDE


def test_a_codex_home_outside_home_stays_writable(tmp_path):
    home, moved = tmp_path / "home", tmp_path / "codex-home"
    home.mkdir()
    moved.mkdir()
    client = CodexAdapter(home, read_version=lambda: "0.159.2", codex_home=moved).detect()
    assert client.config_roots == (str(moved),)
    assert real(moved) in writable_roots(home, Inventory(clients=[client]))


def test_a_project_at_the_top_or_above_home_counts_only_for_itself(tmp_path):
    # Claude Code records a project for any folder it started in, `/` and `/Users` too.
    home, outside = tmp_path / "home", tmp_path / "elsewhere/settings.json"
    home.mkdir()
    outside.parent.mkdir()
    outside.write_text("{}")
    known = [Project(path="/", exists=True), Project(path=str(tmp_path), exists=True)]
    roots = writable_roots(home, Inventory(projects=known))
    engine = Engine(ChangeStore(tmp_path / "store"), no_run, roots=lambda: roots)
    edit = FileEdit(path=str(outside), fmt="json", key=("mcpServers", "x"), after={"url": "u"})
    with pytest.raises(ChangeRefusedError) as refused:
        engine.preview("mcp.add", [Step(client="cursor", scope=Scope.USER, name="x", edit=edit)])
    assert str(refused.value) == OUTSIDE

    def command_in(folder):
        command = ["claude", "mcp", "list"]  # never run: preview runs no command
        return Step(
            "claude_code",
            Scope.PROJECT,
            "x",
            mechanism=CLIENT_CLI,
            command=command,
            cwd=str(folder),
        )

    engine.preview("mcp.add", [command_in(tmp_path)])  # the folder itself still counts
    with pytest.raises(ChangeRefusedError):
        engine.preview("mcp.add", [command_in(outside.parent)])


def test_the_page_refuses_a_change_outside_with_the_sentence(tmp_path, monkeypatch):
    home = make_home(tmp_path, "claude_code/2.1.283")
    data_dir(home).mkdir(parents=True, exist_ok=True)
    (data_dir(home) / "gateway.json").write_text('{"servers": {"files": {"command": "npx"}}}')
    monkeypatch.setattr(page_app, "writable_roots", lambda home, inventory: [tmp_path / "nowhere"])
    app = page_app.create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        body = {"action": "gateway.rule", "params": {"server": "files", "state": "off"}}
        answer = page.post("/api/changes/preview", json=body, headers=POST)
    assert answer.status_code == 422 and answer.json() == {"detail": OUTSIDE}
