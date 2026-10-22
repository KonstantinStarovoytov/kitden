"""The demo's stand-ins: client commands, the Keychain and tool lists, all inside the sample."""

import asyncio
import json
import stat
import tomllib

import pytest

from kitden.changes.client_cli import CommandResult
from kitden.demo import (
    CANNED_TOOLS,
    NOT_IN_DEMO,
    DemoKeychain,
    DemoRunner,
    build_demo_home,
    canned_refresh,
    keychain_file,
)
from kitden.gateways import data_dir
from kitden.local_gateway import keychain
from kitden.local_gateway.keychain import REACH, KeychainError
from kitden.local_gateway.settings import load_tools


def _files(folder):
    """Every file under a folder with its bytes, to show nothing was written."""
    return {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def test_the_runner_adds_and_removes_a_claude_code_server(tmp_path):
    home = build_demo_home(tmp_path, "small")
    before = (home / ".claude.json").read_bytes()
    run = DemoRunner(home)
    entry = {"type": "http", "url": "https://notes.example.test/mcp"}
    add = ["claude", "mcp", "add-json", "-s", "user", "notes", json.dumps(entry)]
    assert run(add, None) == CommandResult(0, "")
    assert json.loads((home / ".claude.json").read_text())["mcpServers"]["notes"] == entry
    assert run(["claude", "mcp", "remove", "-s", "user", "notes"], None).returncode == 0
    assert (home / ".claude.json").read_bytes() == before


def test_the_runner_removes_a_local_and_a_project_server(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    website, atlas = str(home / "work/website"), str(home / "work/atlas")
    run = DemoRunner(home)
    assert run(["claude", "mcp", "remove", "-s", "local", "local-db"], website).returncode == 0
    state = json.loads((home / ".claude.json").read_text())
    assert "local-db" not in state["projects"][website]["mcpServers"]
    assert run(["claude", "mcp", "remove", "-s", "project", "docs"], atlas).returncode == 0
    assert "docs" not in json.loads((home / "work/atlas/.mcp.json").read_text())["mcpServers"]


def test_the_runner_sets_plugins_in_the_scope_it_is_given(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    atlas, run = str(home / "work/atlas"), DemoRunner(home)
    plugin = "test-helper@demo-market"
    run(["claude", "plugin", "install", plugin, "-s", "project", "--json"], atlas)
    project = json.loads((home / "work/atlas/.claude/settings.json").read_text())
    assert project["enabledPlugins"][plugin] is True
    run(["claude", "plugin", "uninstall", plugin, "-s", "project", "--json"], atlas)
    project = json.loads((home / "work/atlas/.claude/settings.json").read_text())
    assert plugin not in project.get("enabledPlugins", {})
    run(["claude", "plugin", "disable", "superpowers@demo-market", "-s", "user", "--json"], None)
    user = json.loads((home / ".claude/settings.json").read_text())
    assert user["enabledPlugins"]["superpowers@demo-market"] is False
    run(["codex", "plugin", "add", "db-tools@demo-market", "--json"], None)
    config = tomllib.loads((home / ".codex/config.toml").read_text())
    assert config["plugins"]["db-tools@demo-market"]["enabled"] is True
    run(["codex", "plugin", "remove", "db-tools@demo-market"], None)
    config = tomllib.loads((home / ".codex/config.toml").read_text())
    assert "db-tools@demo-market" not in config["plugins"]


@pytest.mark.parametrize(
    "command",
    [
        ["claude", "plugin", "marketplace", "add", "team/market"],
        ["codex", "plugin", "marketplace", "add", "team/market", "--json"],
        ["cursor", "--version"],
        ["security", "find-generic-password"],
    ],
)
def test_the_runner_refuses_everything_else(tmp_path, command):
    home = build_demo_home(tmp_path, "small")
    before = _files(tmp_path)
    assert DemoRunner(home)(command, None) == CommandResult(1, NOT_IN_DEMO)
    assert _files(tmp_path) == before


def test_the_runner_refuses_a_folder_outside_the_sample(tmp_path):
    home = build_demo_home(tmp_path, "small")
    before = _files(tmp_path)
    command = ["claude", "plugin", "install", "x@y", "-s", "project", "--json"]
    assert DemoRunner(home)(command, str(tmp_path)) == CommandResult(1, NOT_IN_DEMO)
    assert _files(tmp_path) == before


def test_the_runner_answers_a_failure_it_cannot_write(tmp_path):
    home = build_demo_home(tmp_path, "small")
    run = DemoRunner(home)
    before = _files(tmp_path)
    not_json = ["claude", "mcp", "add-json", "-s", "user", "notes", "{not json"]
    assert run(not_json, None).returncode == 1
    assert _files(tmp_path) == before
    (home / ".claude.json").write_text("{cut short")
    entry = json.dumps({"type": "http", "url": "https://notes.example.test/mcp"})
    assert run(["claude", "mcp", "add-json", "-s", "user", "notes", entry], None).returncode == 1
    assert (home / ".claude.json").read_text() == "{cut short"


def test_the_stand_in_keychain_keeps_values_in_its_file(tmp_path):
    path = tmp_path / "keychain.json"
    run = DemoKeychain(path)
    ref = keychain.store("files", "FILES_TOKEN", "DEMO_SECRET_X", run=run)
    assert ref == {"keychain": "files/FILES_TOKEN"}
    assert keychain.read(ref, run=run) == "DEMO_SECRET_X"
    assert json.loads(path.read_text()) == {"kitden files/FILES_TOKEN": "DEMO_SECRET_X"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    keychain.delete(ref, run=run)
    assert keychain.read(ref, run=run) is None


@pytest.mark.parametrize("broken", ["{not json", "[]", "a folder"])
def test_a_broken_stand_in_file_reads_as_a_keychain_kitden_cannot_reach(tmp_path, broken):
    path = tmp_path / "keychain.json"
    if broken == "a folder":
        path.mkdir()
    else:
        path.write_text(broken)
    before = _files(tmp_path)
    run = DemoKeychain(path)
    ref = {"keychain": "files/FILES_TOKEN"}
    for call in (
        lambda: keychain.read(ref, run=run),
        lambda: keychain.store("files", "FILES_TOKEN", "DEMO_SECRET_X", run=run),
        lambda: keychain.delete(ref, run=run),
    ):
        with pytest.raises(KeychainError, match=REACH):
            call()
    assert _files(tmp_path) == before


def test_the_stand_in_keychain_answers_no_arguments(tmp_path):
    assert DemoKeychain(tmp_path / "keychain.json")([]) == (1, "")


def test_the_stand_in_reads_the_sample_reference(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    ref = {"keychain": "tracker/Authorization"}
    assert keychain.read(ref, run=DemoKeychain(keychain_file(home))) == "Bearer DEMO_SECRET_TRACKER"


def test_a_canned_refresh_fills_only_servers_without_tools(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    path = data_dir(home) / "gateway.json"
    settings = json.loads(path.read_text())
    settings["servers"]["notes"] = {"command": "npx", "args": ["notes-mcp"]}
    path.write_text(json.dumps(settings))
    before = load_tools(home)
    assert asyncio.run(canned_refresh(home)) == {"files": None, "tracker": None, "notes": None}
    tools = load_tools(home)
    assert [t["name"] for t in tools["notes"]] == [t["name"] for t in CANNED_TOOLS]
    assert tools["files"] == before["files"]
    assert asyncio.run(canned_refresh(home, ["not-held"])) == {}
