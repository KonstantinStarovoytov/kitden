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
    REMOVE_FOLDER,
    ChangeState,
    Client,
    ClientStatus,
    FileEdit,
    FolderRemoval,
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


def edit_at(path):
    edit = FileEdit(path=str(path), fmt="json", key=("mcpServers", "x"), after={"url": "u"})
    return Step(client="cursor", scope=Scope.USER, name="x", edit=edit)


def command_in(folder):
    command = ["claude", "mcp", "list"]  # never run: preview runs no command
    return Step(
        "claude_code", Scope.PROJECT, "x", mechanism=CLIENT_CLI, command=command, cwd=str(folder)
    )


def removal_of(folder):
    removal = FolderRemoval(path=str(folder))
    return Step("claude_code", Scope.PROJECT, "x", mechanism=REMOVE_FOLDER, removal=removal)


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


def test_an_empty_or_relative_path_is_no_root(tmp_path):
    # realpath("") is the folder Kitden runs in.
    home = tmp_path / "home"
    home.mkdir()
    odd = Client("codex", "Codex", ClientStatus.FOUND, config_roots=("", ".codex"))
    projects = [Project(path="", exists=False), Project(path="atlas", exists=False)]
    inventory = Inventory(clients=[odd], projects=projects)
    assert writable_roots(home, inventory) == [real(home), real(data_dir(home))]


def test_a_path_outside_every_root_is_refused_before_it_is_read(tmp_path):
    home, outside = tmp_path / "home", tmp_path / "elsewhere/settings.json"
    home.mkdir()
    outside.parent.mkdir()
    outside.write_text("not json")  # a read would fail differently
    engine = Engine(ChangeStore(tmp_path / "store"), no_run, roots=lambda: (home, [real(home)]))
    with pytest.raises(ChangeRefusedError) as refused:
        engine.preview("mcp.add", [edit_at(outside)])
    assert str(refused.value) == OUTSIDE


def test_each_kind_of_place_outside_is_refused(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    project, sibling = tmp_path / "atlas", tmp_path / "atlas2"
    project.mkdir()
    (sibling / "skill").mkdir(parents=True)
    (sibling / "skill/SKILL.md").write_text("# Skill\n")
    inventory = Inventory(projects=[Project(path=str(project), exists=True)])
    engine = Engine(
        ChangeStore(data_dir(home)), no_run, roots=lambda: (home, writable_roots(home, inventory))
    )
    brandkit = home / ".claude/skills/brandkit"
    outside = [
        ClaudeCodeAdapter(home).skill_copy_step(brandkit, ["claude_code"], str(sibling)),
        removal_of(sibling / "skill"),
        edit_at(sibling / ".mcp.json"),  # a known project's name is no prefix
        edit_at(f"{project}/../atlas2/.mcp.json"),  # `..` leaves the project
        command_in(sibling),
    ]
    for step in outside:
        with pytest.raises(ChangeRefusedError) as refused:
            engine.preview("x", [step])
        assert str(refused.value) == OUTSIDE


def test_a_known_project_outside_home_stays_writable(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    project = tmp_path / "disk2/atlas"
    project.mkdir(parents=True)
    inventory = Inventory(projects=[Project(path=str(project), exists=True)])
    engine = Engine(
        ChangeStore(data_dir(home)), no_run, roots=lambda: (home, writable_roots(home, inventory))
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
        ChangeStore(data_dir(home)), no_run, roots=lambda: (home, writable_roots(home, Inventory()))
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


def test_preview_pins_the_real_copy_target_and_command_folder(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    project, elsewhere = home / "work/atlas", tmp_path / "elsewhere"
    project.mkdir(parents=True)
    elsewhere.mkdir()
    link = home / "atlas-link"
    link.symlink_to(project)
    engine = Engine(
        ChangeStore(data_dir(home)), no_run, roots=lambda: (home, writable_roots(home, Inventory()))
    )
    step = ClaudeCodeAdapter(home).skill_copy_step(
        home / ".claude/skills/brandkit", ["claude_code"], str(link)
    )
    change = engine.preview("skill.install", [step])
    assert engine.preview("mcp.add", [command_in(link)]).steps[0].cwd == str(real(project))
    link.unlink()
    link.symlink_to(elsewhere)  # changed after the review
    assert engine.apply(change.id).state is ChangeState.VERIFIED
    assert (project / ".claude/skills/brandkit/SKILL.md").is_file()
    assert not (elsewhere / ".claude").exists()


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
    engine = Engine(ChangeStore(tmp_path / "store"), no_run, roots=lambda: (home, roots))
    with pytest.raises(ChangeRefusedError) as refused:
        engine.preview("mcp.add", [edit_at(outside)])
    assert str(refused.value) == OUTSIDE
    engine.preview("mcp.add", [command_in(tmp_path)])  # a command may run in the folder itself
    for step in (command_in(outside.parent), removal_of(tmp_path)):
        with pytest.raises(ChangeRefusedError) as refused:
            engine.preview("mcp.add", [step])
        assert str(refused.value) == OUTSIDE


def test_a_folder_above_home_spelled_in_other_letters_counts_only_for_itself(tmp_path):
    home, alias = tmp_path / "Box/home", tmp_path / "box"
    home.mkdir(parents=True)
    if not alias.exists():
        pytest.skip("this disk tells upper and lower case apart")
    assert real(alias) != real(tmp_path / "Box")  # another text for the same folder
    (alias / "elsewhere").mkdir()
    (alias / "elsewhere/settings.json").write_text("{}")
    roots = writable_roots(home, Inventory(projects=[Project(path=str(alias), exists=True)]))
    engine = Engine(ChangeStore(tmp_path / "store"), no_run, roots=lambda: (home, roots))
    with pytest.raises(ChangeRefusedError) as refused:
        engine.preview("mcp.add", [edit_at(alias / "elsewhere/settings.json")])
    assert str(refused.value) == OUTSIDE


def test_a_folder_that_holds_home_by_another_path_counts_only_for_itself(tmp_path):
    # `/System/Volumes/Data` is not `/`, yet `/System/Volumes/Data/Users` is `/Users`. Here a
    # link inside `data` stands in for that: data/<home's whole path> is the home folder.
    home, data = real(tmp_path) / "home", real(tmp_path) / "data"
    home.mkdir()
    inner = data / home.relative_to("/")
    inner.parent.mkdir(parents=True)
    inner.symlink_to(home)
    (data / "elsewhere").mkdir()
    (data / "elsewhere/settings.json").write_text("{}")
    roots = writable_roots(home, Inventory(projects=[Project(path=str(data), exists=True)]))
    engine = Engine(ChangeStore(tmp_path / "store"), no_run, roots=lambda: (home, roots))
    with pytest.raises(ChangeRefusedError) as refused:
        engine.preview("mcp.add", [edit_at(data / "elsewhere/settings.json")])
    assert str(refused.value) == OUTSIDE
    engine.preview("mcp.add", [command_in(data)])  # a command may run in the folder itself


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
