"""The demo's sample homes, and the cases later parts name in them."""

import json
from pathlib import Path

import pytest

from kitden.demo import (
    DEMO_SECRET,
    VERSIONS,
    build_demo_home,
    demo_adapters,
    demo_build,
    keychain_file,
)
from kitden.local_gateway.project import project_chain
from kitden.local_gateway.settings import deciding_project, load_calls, load_settings, load_tools
from kitden.local_gateway.views import held_servers, tools_view
from kitden.model import ClientStatus, Enabled, ItemKind, Scope
from kitden.views.effective import effective_view
from kitden.views.inventory import build_inventory
from kitden.views.setup_server import setup_server_state


def _found(inventory):
    return {c.id for c in inventory.clients if c.status is ClientStatus.FOUND}


def _rel(home, path):
    return Path(path).relative_to(home).as_posix()


def test_the_small_sample_is_claude_code_and_one_project(tmp_path):
    home = build_demo_home(tmp_path, "small")
    inventory = demo_build(home)()
    assert home == tmp_path / "home"
    assert _found(inventory) == {"claude_code"}
    assert [_rel(home, p.path) for p in inventory.projects] == ["work/atlas"]
    kinds = [i.kind for i in inventory.items]
    assert kinds.count(ItemKind.MCP_SERVER) >= 2 and kinds.count(ItemKind.SKILL) >= 2
    assert ItemKind.PLUGIN in kinds


def test_the_medium_sample_has_three_clients_five_projects_and_about_60_items(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inventory = demo_build(home)()
    assert {c.id: c.version for c in inventory.clients} == VERSIONS
    assert 50 <= len(inventory.items) <= 75
    assert {_rel(home, p.path): p.exists for p in inventory.projects} == {
        "work/atlas": True,
        "work/atlas/web": True,
        "work/website": True,
        "work/sandbox": True,
        "work/old-app": False,
    }
    codex = next(a for a in demo_adapters(home) if a.id == "codex")
    assert codex.trusts(str(home / "work/atlas"))
    assert not codex.trusts(str(home / "work/sandbox"))


def test_the_medium_sample_contract(tmp_path):
    """The cases later parts name; read as any test reads a home, under the conftest guards."""
    home = build_demo_home(tmp_path, "medium")
    inventory = build_inventory(home)
    items = inventory.items
    assert _found(inventory) == {"claude_code", "codex", "cursor"}
    for name, clients in (
        ("code-review", {"codex", "cursor"}),
        ("brandkit", {"claude_code", "cursor"}),
    ):
        shared = [i for i in items if i.kind is ItemKind.SKILL and i.name == name]
        assert {i.client for i in shared} == clients
        assert len({i.source.path for i in shared}) == 1  # one folder, read by two clients
    docs = [
        i
        for i in items
        if i.kind is ItemKind.MCP_SERVER and i.name == "docs" and i.scope is Scope.USER
    ]
    assert sorted(i.client for i in docs) == ["claude_code", "codex"]
    fields = {tuple(p for p in i.summary if p[0] in ("command", "args", "url")) for i in docs}
    assert len(fields) == 2  # same name, two sources
    for client in ("claude_code", "codex"):  # and it loads in both, for all projects
        assert "docs" in {i.name for i in effective_view(inventory, client, None).items}
    view = effective_view(inventory, "claude_code", str(home / "work/atlas"))
    assert [(w.scope, lo.scope, m) for w, lo, m in view.shadowed if w.name == "docs"] == [
        (Scope.PROJECT, Scope.USER, "override")
    ]
    website = str(home / "work/website")
    plugin = [i for i in items if i.name == "superpowers@demo-market" and i.project == website]
    assert [(i.scope, i.enabled) for i in plugin] == [(Scope.PROJECT, Enabled.OFF)]
    settings, tools = load_settings(home), load_tools(home)
    search = next(
        t for t in tools_view(settings, tools, "files", [])["tools"] if t["name"] == "search_files"
    )
    assert (search["hint"], search["state"]) == ("unknown", "on")
    assert [(_rel(home, p.path), str(p.unknown_reason)) for p in inventory.problems] == [
        ("work/website/.cursor/mcp.json", "parse_error")
    ]
    names = {i.name for i in items if i.kind is ItemKind.INSTRUCTIONS}
    assert {"CLAUDE.md", "AGENTS.md", "review", "reviewer"} <= names
    agent = (home / ".claude/agents/reviewer.md").read_text()
    assert "name: reviewer" in agent and "description:" in agent
    states = {s["client"]: s["state"] for s in setup_server_state(inventory)}
    assert states == {"claude_code": "added", "codex": "added", "cursor": "missing"}
    assert any(i.client == "cursor" and i.name == "files" and i.via_gateway is None for i in items)


def test_the_medium_sample_has_a_kitden_gateway_with_rules_and_tools(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    inventory = demo_build(home)()
    settings, tools = load_settings(home), load_tools(home)
    held = {s["name"]: (s["kind"], s["plain_secrets"]) for s in held_servers(settings, [], tools)}
    assert held == {"files": ("local", True), "tracker": ("remote", False)}
    hints = {t["name"]: t["hint"] for t in tools_view(settings, tools, "files", [])["tools"]}
    assert hints == {
        "read_file": "reads",
        "write_file": "writes",
        "delete_file": "may write",
        "search_files": "unknown",
    }
    new = {t["name"]: t["new"] for t in tools_view(settings, tools, "tracker", [])["tools"]}
    assert new == {"list_issues": False, "create_issue": False, "export_report": True}
    web, atlas = str(home / "work/atlas/web"), str(home / "work/atlas")
    chain = project_chain(web, home, [p.path for p in inventory.projects])
    assert chain == [web, atlas]
    assert deciding_project(settings, chain, "files", "write_file") == atlas  # parent's rule
    assert deciding_project(settings, chain, "files", "search_files") == web  # its own rule
    assert settings.get("path")
    assert load_calls(home)["files"]["read_file"]["count"] == 12
    assert json.loads(keychain_file(home).read_text()) == {
        "kitden tracker/Authorization": "Bearer DEMO_SECRET_TRACKER"
    }


def test_the_small_sample_keeps_its_own_path_and_an_empty_keychain(tmp_path):
    home = build_demo_home(tmp_path, "small")
    assert load_settings(home) == {
        "path": "/usr/local/bin:/usr/bin:/bin",
        "servers": {},
        "rules": {"global": {}, "projects": {}},
    }
    assert json.loads(keychain_file(home).read_text()) == {}


@pytest.mark.parametrize("size", ["small", "medium"])
def test_a_sample_holds_demo_secrets_and_no_sentinel(tmp_path, size):
    build_demo_home(tmp_path, size)
    files = [p for p in tmp_path.rglob("*") if p.is_file() and not p.is_symlink()]
    text = "".join(p.read_text(errors="ignore") for p in files)
    assert text.count(DEMO_SECRET) >= (2 if size == "small" else 6)
    assert "SENTINEL" not in text


def test_the_same_size_writes_the_same_files(tmp_path):
    def files(home):
        return {
            p.relative_to(home.parent).as_posix(): p.read_text().replace(str(home), "~")
            for p in sorted(home.parent.rglob("*"))
            if p.is_file() and not p.is_symlink() and p.suffix != ".vscdb"
        }

    assert files(build_demo_home(tmp_path / "a", "medium")) == files(
        build_demo_home(tmp_path / "b", "medium")
    )


def test_an_unknown_size_is_refused(tmp_path):
    with pytest.raises(ValueError, match="Choose small, medium or large."):
        build_demo_home(tmp_path, "huge")


def test_a_home_that_exists_is_not_written_over(tmp_path):
    (tmp_path / "home").mkdir()
    with pytest.raises(FileExistsError):
        build_demo_home(tmp_path, "small")
