"""Claude Code's folder moved by CLAUDE_CONFIG_DIR and CLAUDE_CODE_PLUGIN_CACHE_DIR: Kitden reads
and writes only there. Every home is a sandbox, and the old `~/.claude` holds a decoy."""

import json
import os
import re
from pathlib import Path

import pytest

from kitden import cli, page
from kitden.changes.actions import (
    _claude_denies,
    _claude_project_offs,
    claude_allows_kitden,
    folder_readers,
)
from kitden.changes.json_splice import ABSENT
from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.clients.claude_folder import claude_folder
from kitden.clients.cursor import CursorAdapter
from kitden.context.claude_log import last_claude_list
from kitden.demo import demo_adapters
from kitden.model import Change, FileEdit, ItemKind, Scope, Step
from kitden.system import watched
from kitden.views.after import after_words
from kitden.views.answers import context_answer
from kitden.views.explain import reads
from kitden.views.inventory import build_inventory
from kitden.views.library_map import cursor_imports
from tests.conftest import make_home, rows
from tests.unit.test_context_claude_log import assistant, list_entry, write_chat
from tests.unit.test_context_view import LONG, claude_chat, skill, usage, view, write_json
from tests.unit.test_demo_mode import demo_page
from tests.unit.test_demo_mode import preview as demo_preview
from tests.unit.test_skill_rule import _item, _page, _round_trip, _rule

FIXTURE = "claude_code/2.1.283"
DECOY = {
    "enabledPlugins": {"decoy@old": True},
    "permissions": {"allow": ["mcp__kitden"], "deny": ["mcp__decoy"]},
    "skillListingBudgetFraction": 0.04,
}


def _move(home: Path, to: Path, monkeypatch) -> Path:
    """Move the home's Claude Code files to `to`, as the variable does, and leave a decoy."""
    old = str(home / ".claude")
    (home / ".claude").rename(to)
    if (home / ".claude.json").exists():
        (home / ".claude.json").rename(to / ".claude.json")
    for path in to.rglob("*.json"):
        path.write_text(path.read_text().replace(old + "/", f"{to}/"))
    write_json(home / ".claude/settings.json", DECOY)
    write_json(home / ".claude.json", {"mcpServers": {"decoy": {"command": "decoy"}}})
    skill(home / ".claude/skills", "decoy", "Decoy.")
    (home / ".claude/CLAUDE.md").write_text("Decoy.")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(to))
    return to


def _old_files(home: Path) -> dict[str, bytes]:
    paths = [home / ".claude.json", *(p for p in (home / ".claude").rglob("*") if p.is_file())]
    return {str(p): p.read_bytes() for p in paths}


@pytest.fixture
def home(tmp_path):
    return make_home(tmp_path, FIXTURE)


@pytest.fixture
def moved(home, tmp_path, monkeypatch):
    return _move(home, tmp_path / "claude-work", monkeypatch)


def _adapter(home: Path, **more) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(home, read_version=lambda: None, **more)


# The folder


def test_with_no_variable_the_folder_is_in_the_home_folder(tmp_path):
    folder = claude_folder(tmp_path)
    assert folder.config == tmp_path / ".claude"
    assert folder.state == tmp_path / ".claude.json"
    assert folder.plugins == tmp_path / ".claude/plugins"


@pytest.mark.parametrize("name", ["CLAUDE_CONFIG_DIR", "CLAUDE_CODE_PLUGIN_CACHE_DIR"])
def test_an_empty_variable_is_no_variable(tmp_path, monkeypatch, name):
    plain = claude_folder(tmp_path)
    monkeypatch.setenv(name, "")
    assert claude_folder(tmp_path) == plain


def test_the_variable_set_to_the_default_folder_still_moves_the_state_file(tmp_path):
    # Seen 2026-11-25, Claude Code 2.1.311: `.claude.json` is then inside the folder.
    folder = claude_folder(tmp_path, {"CLAUDE_CONFIG_DIR": str(tmp_path / ".claude")})
    assert folder.state == tmp_path / ".claude/.claude.json"


def test_the_plugin_folder_moves_alone_or_out_of_a_moved_folder(tmp_path):
    plugins = {"CLAUDE_CODE_PLUGIN_CACHE_DIR": "/p"}
    alone = claude_folder(tmp_path, plugins)
    assert (alone.config, alone.plugins) == (tmp_path / ".claude", Path("/p"))
    both = claude_folder(tmp_path, {**plugins, "CLAUDE_CONFIG_DIR": "/c"})
    assert (both.config, both.state) == (Path("/c"), Path("/c/.claude.json"))
    assert both.plugins == Path("/p")
    assert claude_folder(tmp_path, {"CLAUDE_CONFIG_DIR": "/c"}).plugins == Path("/c/plugins")


def test_a_tilde_is_the_home_folder_only_for_the_plugin_folder(tmp_path):
    # Seen 2026-11-25, Claude Code 2.1.311: CLAUDE_CONFIG_DIR keeps `~` as typed.
    env = {"CLAUDE_CODE_PLUGIN_CACHE_DIR": "~/plug", "CLAUDE_CONFIG_DIR": "~/conf"}
    folder = claude_folder(tmp_path, env)
    assert folder.plugins == tmp_path / "plug"
    assert folder.config == Path("~/conf")


# Reading


def test_a_moved_folder_reads_the_same_setup_and_nothing_of_the_old_one(home, monkeypatch):
    before = rows(_adapter(home).scan().items, home)
    _move(home, home / "claude-work", monkeypatch)  # beside .claude: a skill there is a link
    scan = _adapter(home).scan()
    assert rows(scan.items, home) == before
    assert scan.problems == []
    old = str(home / ".claude")
    assert not [i.source.path for i in scan.items if (i.source.path or "").startswith(old)]


def test_a_moved_plugin_folder_is_read(home, tmp_path, monkeypatch):
    before = rows(_adapter(home).scan().items, home)
    plugins = tmp_path / "plug"
    (home / ".claude/plugins").rename(plugins)
    for path in plugins.rglob("*.json"):
        path.write_text(path.read_text().replace(f"{home}/.claude/plugins", str(plugins)))
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(plugins))
    adapter = _adapter(home)
    assert rows(adapter.scan().items, home) == before
    assert adapter.plugin_folders() and adapter.marketplace_sources()
    assert all(p.is_relative_to(plugins) for p in adapter.plugin_folders().values())


def test_the_client_is_found_in_its_moved_folder(home, moved):
    client = _adapter(home).detect()
    assert client.config_roots == (str(moved),)
    assert str(client.status) == "found"


def test_a_moved_folder_that_is_not_there_is_not_found(home, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "gone"))
    assert str(_adapter(home).detect().status) == "not_found"


def _home_project(state_file: Path, project: Path) -> None:
    state = json.loads(state_file.read_text())
    state["projects"] = {str(project): {}}
    state_file.write_text(json.dumps(state))


def test_the_home_folder_is_an_ordinary_project_when_the_folder_moved(home, moved):
    # Seen 2026-11-25: `plugin install -s project` there writes ~/.claude/settings.json.
    _home_project(moved / ".claude.json", home)
    found = [i for i in _adapter(home).scan().items if i.project == str(home)]
    assert {"decoy@old", "decoy", "CLAUDE.md"} <= {i.name for i in found}
    assert {str(i.scope) for i in found} == {"project"}


def test_a_folder_whose_claude_folder_is_the_moved_one_is_not_read_twice(
    home, tmp_path, monkeypatch
):
    base = tmp_path / "base"
    base.mkdir()
    to = _move(home, base / ".claude", monkeypatch)
    _home_project(to / ".claude.json", base)
    write_json(base / ".mcp.json", {"mcpServers": {"own": {"command": "x"}}})
    write_json(to / "settings.local.json", {"enabledMcpjsonServers": ["own"]})
    here = [i for i in _adapter(home).scan().items if i.project == str(base)]
    assert [(i.name, str(i.enabled)) for i in here] == [("own", "on")]  # no trust needed there


# Writing


def test_every_user_step_writes_in_the_moved_folder(home, moved):
    adapter = _adapter(home)
    scan = adapter.scan()
    plugin = next(
        i
        for i in scan.items
        if i.kind is ItemKind.PLUGIN and i.scope is Scope.USER and i.source.path
    )
    server = next(
        i
        for i in scan.items
        if i.kind is ItemKind.MCP_SERVER and i.scope is Scope.USER and i.client == "claude_code"
    )
    own = next(i for i in scan.items if i.kind is ItemKind.SKILL and i.scope is Scope.USER)
    steps = [
        *adapter.skill_rule_steps("brandkit", None, "off"),
        adapter.skill_limit_step(0.02),
        adapter.marketplace_add_step("m", "owner/repo"),
        adapter.plugin_install_step("a@m"),
        adapter.plugin_remove_step(plugin),
        adapter.plugin_step(plugin, enable=False)
        if str(plugin.enabled) == "on"
        else adapter.plugin_step(plugin, enable=True),
        adapter.setup_server_step("/opt/kitden", ["mcp"]),
        adapter.add_server_step("s", {"type": "http", "url": "https://x.test"}),
        adapter.remove_step(server),
    ]
    for step in steps:
        assert step.edit is not None
        assert Path(step.edit.path).is_relative_to(moved), step.name
    source = skill(home / "copy", "fresh", "Fresh.").parent
    copy = adapter.skill_copy_step(source, ["claude_code"]).copy
    assert copy is not None and Path(copy.target) == moved / "skills/fresh"
    assert own.source.path and Path(own.source.path).is_relative_to(moved)


def test_a_project_s_own_steps_stay_in_the_project(home, moved):
    adapter = _adapter(home)
    website = home / "work/website"
    path = adapter.plugin_install_step("a@m", str(website)).edit.path
    assert Path(path) == website / ".claude/settings.json"
    source = skill(home / "copy", "fresh", "Fresh.").parent
    copy = adapter.skill_copy_step(source, ["claude_code"], str(website)).copy
    assert Path(copy.target) == website / ".claude/skills/fresh"
    rule = adapter.skill_rule_steps("brandkit", str(website), "off")[0].edit.path
    assert Path(rule) == website / ".claude/settings.local.json"


def test_a_change_and_its_undo_touch_only_the_moved_folder(home, moved):
    before, old = (moved / "settings.json").read_bytes(), _old_files(home)
    with _page(home) as open_page:
        rule = _rule("claude_code", _item(open_page, "claude_code", "brandkit"))
        _, _, undo = _round_trip(open_page, rule)
        written = json.loads((moved / "settings.json").read_text())
        assert written["skillOverrides"] == {"brandkit": "off"}
        assert _old_files(home) == old
        undo()
    assert (moved / "settings.json").read_bytes() == before
    assert _old_files(home) == old


def test_a_skill_can_be_turned_on_again_from_the_moved_settings(home, moved):
    settings = json.loads((moved / "settings.json").read_text())
    write_json(moved / "settings.json", {**settings, "skillOverrides": {"brandkit": "off"}})
    with _page(home) as open_page:
        rule = _rule("claude_code", _item(open_page, "claude_code", "brandkit"))
        rule["params"] = {"scope": "all", "state": "on"}
        _round_trip(open_page, rule)
    assert "brandkit" not in json.loads((moved / "settings.json").read_text()).get(
        "skillOverrides", {}
    )


# What the page reads beside the scan


def test_chats_come_from_the_moved_folder(home, tmp_path, monkeypatch):
    write_chat(home, "p", "chat", [list_entry(["a"], "- a: Mine."), assistant()], 100)
    to = _move(home, tmp_path / "claude-work", monkeypatch)
    write_chat(home, "p", "chat", [list_entry(["d"], "- d: Decoy."), assistant()], 200)
    assert last_claude_list(to, None).skills == (("a", "Mine."),)


def test_the_context_page_reads_the_moved_folder(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    for name in "ab":
        skill(home / ".claude/skills", name, LONG[:500])
    usage(home, {"a": 1, "b": 2})
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.02})
    claude_chat(home, dict.fromkeys("ab", LONG[:500]), model="claude-sonnet-4-6")
    plain = view(home)["claude_code"]
    to = _move(home, tmp_path / "claude-work", monkeypatch)
    claude_chat(home, {"decoy": "Decoy."})
    card = view(home)["claude_code"]

    def said(card: dict) -> str:  # without item ids, which come from the path
        return re.sub(r'"item": "\w+"', "", json.dumps(card))

    assert said(card) == said(plain).replace(f"{home}/.claude", str(to))
    answer = context_answer(build_inventory(home), home, str(home))
    claude = next(c for c in answer["clients"] if c["client"] == "claude_code")
    assert claude["lamp"] == plain["lamp"]


def test_a_move_into_the_gateway_reads_the_moved_rules(home, moved):
    folder = claude_folder(home)
    website = str(home / "work/website")
    settings = json.loads((moved / "settings.json").read_text())
    write_json(moved / "settings.json", {**settings, "permissions": {"deny": ["mcp__mine"]}})
    state = json.loads((moved / ".claude.json").read_text())
    state.setdefault("projects", {})[website] = {"disabledMcpServers": ["off-one"]}
    write_json(moved / ".claude.json", state)
    assert _claude_denies(folder, [])[None] == ["mcp__mine"]
    assert _claude_denies(folder, [str(home)])[str(home)] == ["mcp__decoy"]  # a project's file now
    assert _claude_project_offs(folder) == {website: ["off-one"]}
    assert not claude_allows_kitden(folder, [])  # the decoy allows it
    assert claude_allows_kitden(folder, [str(home)])


def test_a_rule_taken_out_follows_the_moved_shared_settings(home, moved):
    website = home / "work/website"
    write_json(moved / "settings.json", {"skillOverrides": {"brandkit": "off"}})
    edit = FileEdit(
        path=str(website / ".claude/settings.local.json"),
        fmt="json",
        key=("skillOverrides", "brandkit"),
        after=ABSENT,
    )
    step = Step(
        client="claude_code", scope=Scope.LOCAL, name="brandkit", edit=edit, cwd=str(website)
    )
    change = Change(action="skill.rule", steps=[step])
    said = after_words(change, build_inventory(home), home=home)
    assert said[0]["state"] == "off"


def test_a_rule_in_the_moved_folder_is_told_as_a_rule(home, moved):
    (moved / "rules").mkdir()
    (moved / "rules/style.md").write_text("Style.")
    items = _adapter(home).scan().items
    said = {i.name: reads(i, items) for i in items if i.kind is ItemKind.INSTRUCTIONS}
    assert "A rule that names paths" in said["style"]
    assert said["CLAUDE.md"] == "Read when a session starts."


def test_the_page_watches_the_moved_folders(home, moved, tmp_path, monkeypatch):
    assert moved in watched(home) and home / ".claude" not in watched(home)
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "plug"))
    assert {moved, tmp_path / "plug"} <= set(watched(home))


# Cursor reads ~/.claude


def test_a_skill_in_the_moved_folder_does_not_reach_cursor(home, moved):
    adapters = {"claude_code": _adapter(home), "cursor": CursorAdapter(home, lambda: "3.21")}
    found = {"claude_code", "cursor"}
    assert folder_readers("claude_code", adapters, found) == ["claude_code"]
    # A project's own .claude/skills does not move.
    project = str(home / "work/website")
    assert folder_readers("claude_code", adapters, found, project) == ["claude_code", "cursor"]
    assert not cursor_imports(adapters, list(found))


def test_with_no_variable_a_skill_reaches_cursor(home):
    adapters = {"claude_code": _adapter(home), "cursor": CursorAdapter(home, lambda: "3.21")}
    found = {"claude_code", "cursor"}
    assert folder_readers("claude_code", adapters, found) == ["claude_code", "cursor"]
    assert cursor_imports(adapters, list(found))


def test_a_moved_plugin_folder_takes_only_plugins_from_cursor(home, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "plug"))
    adapters = {"claude_code": _adapter(home), "cursor": CursorAdapter(home, lambda: "3.21")}
    found = {"claude_code", "cursor"}
    assert folder_readers("claude_code", adapters, found) == ["claude_code", "cursor"]
    assert not cursor_imports(adapters, list(found))


# The demo


@pytest.fixture
def real(tmp_path, monkeypatch):
    real = tmp_path / "real-claude"
    write_json(real / "settings.json", {"enabledPlugins": {"from-real@x": True}})
    write_json(real / ".claude.json", {"mcpServers": {"from-real": {"command": "x"}}})
    skill(real / "skills", "from-real", "Real.")
    entries = [list_entry(["from-real"], "- from-real: Real."), assistant()]
    chat = real / "projects/p/chat.jsonl"
    chat.parent.mkdir(parents=True)
    chat.write_text("".join(json.dumps(e) + "\n" for e in entries))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(real))
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(real / "plugins"))
    return real


def test_the_demo_ignores_both_variables(tmp_path, real):
    before = {p: p.read_bytes() for p in real.rglob("*") if p.is_file()}
    with demo_page(tmp_path / "demo") as open_page:
        for path in ("/api/items", "/api/context", "/api/library-map"):
            answer = open_page.get(path)
            assert answer.status_code == 200, path
            assert "from-real" not in answer.text, path
        skills = open_page.get("/api/items?kind=skill&client=claude_code").json()
        target = next(i for i in skills if i["scope"] == "user")
        params = {"scope": "all", "state": "off"}
        targets = [{"client": "claude_code", "item": target["id"]}]
        change = demo_preview(open_page, "skill.rule", targets, params)
        assert Path(change["steps"][0]["path"]).is_relative_to(open_page.home)
    assert {p: p.read_bytes() for p in real.rglob("*") if p.is_file()} == before


def test_the_demo_watches_only_the_sample(tmp_path, real):
    home = tmp_path / "demo-home"
    folders = [a.folder for a in demo_adapters(home) if isinstance(a, ClaudeCodeAdapter)]
    assert [f.config for f in folders] == [home / ".claude"]
    assert real not in watched(home, {})


# One page per home folder


def test_open_restarts_a_page_that_reads_another_folder(tmp_path, monkeypatch):
    lock = page.PageLock(tmp_path)
    assert lock.acquire()
    page.write_record(tmp_path, port=47899, token="old", background=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-work"))
    stopped, opened = [], []

    def stop(home, record):
        stopped.append(record["token"])
        lock.release()
        return True

    def start(home, home_arg):
        assert lock.acquire()
        page.write_record(home, port=47901, token="new", background=True)

    monkeypatch.setattr(page, "stop_page", stop)
    monkeypatch.setattr(page, "start_background", start)
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    try:
        for _ in range(2):  # the new page reads this folder, so it stays
            assert cli.main(["open", "--home", str(tmp_path)]) == 0
    finally:
        lock.release()
    assert stopped == ["old"]
    assert opened == ["http://127.0.0.1:47901/?token=new"] * 2


def test_the_command_line_gives_the_client_the_same_folder(home, moved, monkeypatch):
    # A client command inherits the variable, so it writes where Kitden reads.
    from kitden.changes import client_cli

    script = home / "bin/claude"
    script.parent.mkdir()
    script.write_text('#!/bin/sh\necho "$CLAUDE_CONFIG_DIR"\n')
    script.chmod(0o755)
    monkeypatch.setattr(client_cli, "find_command", lambda name, where: str(script))
    done = client_cli.CommandRunner(home)(["claude"], None)
    assert done.output == str(moved) == os.environ["CLAUDE_CONFIG_DIR"]


def test_a_relative_folder_is_the_one_under_the_start_folder(tmp_path, monkeypatch):
    # The page and client commands run in other folders, so the program makes it absolute first.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "claude-work")
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", "plug")
    seen = {}
    monkeypatch.setattr(cli, "_open", lambda args: seen.update(os.environ) or 0)
    assert cli.main(["open", "--home", str(tmp_path / "home")]) == 0
    assert seen["CLAUDE_CONFIG_DIR"] == str(tmp_path / "claude-work")
    assert seen["CLAUDE_CODE_PLUGIN_CACHE_DIR"] == str(tmp_path / "plug")


@pytest.mark.parametrize("value", ["", "~/plug", "/plug"])
def test_a_plugin_folder_that_is_not_relative_stays_as_typed(tmp_path, monkeypatch, value):
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", value)
    monkeypatch.setattr(cli, "_open", lambda args: 0)
    assert cli.main(["open", "--home", str(tmp_path)]) == 0
    assert os.environ["CLAUDE_CODE_PLUGIN_CACHE_DIR"] == value
    assert "CLAUDE_CONFIG_DIR" not in os.environ
