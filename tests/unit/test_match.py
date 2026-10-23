"""When two items with one name are the same: a server by its command and address, a skill by
its files or its plugin."""

import shutil
from dataclasses import replace
from pathlib import Path

from kitden.changes.server_entry import translate_entry
from kitden.clients.base import file_source, marketplace_source, mcp_item
from kitden.model import Client, ClientStatus, Item, ItemKind, Scope, Source, SourceKind
from kitden.views import match
from kitden.views.findings import find_findings
from kitden.views.inventory import Inventory
from kitden.views.load_map import load_map
from kitden.views.match import odd_ones, plugin_of, source_keys

CLIENTS = ("claude_code", "codex", "cursor")


def _item(kind, name, path, summary=(), scope=Scope.USER):
    source = Source(kind=SourceKind.FILE, path=str(path), owner_client="claude_code")
    return Item(
        client="claude_code", kind=kind, name=name, scope=scope, source=source, summary=summary
    )


def test_the_odd_one_needs_review_and_a_tie_keeps_the_first():
    a, b = frozenset({"a"}), frozenset({"b"})
    assert odd_ones({"claude_code": a, "codex": b, "cursor": b}) == {"claude_code"}
    assert odd_ones({"claude_code": a, "codex": b}) == {"codex"}
    assert odd_ones({"claude_code": frozenset({"a", "b"}), "codex": b}) == set()
    assert odd_ones({"claude_code": a, "codex": a}) == set()


def test_a_plugin_skill_is_known_by_its_plugin():
    path = "/h/.claude/plugins/cache/claude-plugins-official/superpowers/7.0.0/skills/x/SKILL.md"
    skill = Item(
        client="claude_code",
        kind=ItemKind.SKILL,
        name="x",
        scope=Scope.PLUGIN,
        source=Source(kind=SourceKind.PLUGIN, path=path, owner_client="claude_code"),
    )
    assert plugin_of(skill) == "superpowers@claude-plugins-official"
    assert plugin_of(replace(skill, scope=Scope.USER)) is None


def test_a_server_is_known_by_its_address_however_it_is_spelled():
    one = _item(
        ItemKind.MCP_SERVER, "docs", "/h/a", (("type", "http"), ("url", "https://D.test/mcp/"))
    )
    two = _item(ItemKind.MCP_SERVER, "docs", "/h/b", (("url", "https://d.test/mcp"),))
    other = _item(ItemKind.MCP_SERVER, "docs", "/h/c", (("command", "npx"), ("args", '["docs"]')))
    assert source_keys(one) == source_keys(two)
    assert source_keys(one).isdisjoint(source_keys(other))


def test_a_skill_is_known_by_its_files(tmp_path):
    first = tmp_path / "a/brandkit"
    first.mkdir(parents=True)
    (first / "SKILL.md").write_text("---\nname: brandkit\n---\nBrand.\n")
    shutil.copytree(first, tmp_path / "b/brandkit")
    (tmp_path / "c/brandkit").mkdir(parents=True)
    (tmp_path / "c/brandkit/SKILL.md").write_text("---\nname: brandkit\n---\nOther.\n")
    keys = [
        source_keys(_item(ItemKind.SKILL, "brandkit", tmp_path / f"{x}/brandkit/SKILL.md"))
        for x in "abc"
    ]
    assert keys[0] == keys[1]
    assert keys[0].isdisjoint(keys[2])


# Each entry as its client writes it.
ENTRIES = [
    ("claude_code", {"type": "stdio", "command": "zed-mcp", "args": [], "env": {}}),
    ("codex", {"command": "zed-mcp", "args": []}),
    ("cursor", {"command": "zed-mcp", "args": [], "env": {}}),
    ("cursor", {"command": "npx", "args": ["--dir", "${env:HOME}/data"]}),
    ("claude_code", {"type": "stdio", "command": "npx", "args": ["--dir", "${HOME}/data"]}),
    ("claude_code", {"type": "http", "url": "https://docs.example.test/mcp/"}),
]


def test_a_server_kitden_copied_is_the_same_server():
    copied = 0
    for source, entry in ENTRIES:
        for target in CLIENTS:
            if target == source:
                continue
            try:
                copy = translate_entry(entry, target, source=source)
            except ValueError:  # Codex cannot read a reference in an argument
                continue
            one = mcp_item(source, "x", entry, file_source(Path("/h/a"), source), Scope.USER)
            two = mcp_item(target, "x", copy, file_source(Path("/h/b"), target), Scope.USER)
            assert not source_keys(one).isdisjoint(source_keys(two)), (source, target, entry)
            copied += 1
    assert copied == 10


def test_a_marketplace_is_known_by_its_source():
    github = marketplace_source({"source": "github", "repo": "anthropics/claude-plugins-official"})
    clone = marketplace_source(
        {
            "source_type": "git",
            "source": "https://github.com/anthropics/claude-plugins-official.git",
        }
    )
    other = marketplace_source({"source_type": "git", "source": "https://github.com/me/fork.git"})
    assert github == clone == "github.com/anthropics/claude-plugins-official"
    assert other != github
    folder = marketplace_source({"source": "directory", "path": "/m/demo/"})
    assert folder == marketplace_source({"source_type": "local", "source": "/m/demo"})
    assert marketplace_source({}) is None


def _plugin_skill(client, version):
    path = f"/h/.{client}/plugins/cache/m/p/{version}/skills/x/SKILL.md"
    source = Source(kind=SourceKind.PLUGIN, path=path, owner_client=client)
    return Item(client=client, kind=ItemKind.SKILL, name="x", scope=Scope.PLUGIN, source=source)


def test_parts_of_one_plugin_are_the_same_without_reading_their_files(monkeypatch):
    def no_read(folder):
        raise AssertionError(f"read {folder}")

    monkeypatch.setattr(match, "skill_digest", no_read)
    clients = [Client(id=c, display_name=c, status=ClientStatus.FOUND) for c in CLIENTS]
    items = [_plugin_skill("codex", "1.0.0"), _plugin_skill("cursor", "2.0.0")]
    inventory = Inventory(clients=clients, items=items)
    (row,) = load_map(inventory, None)
    assert (row.cells["codex"].state, row.cells["cursor"].state) == ("on", "on")
    assert [str(f.type) for f in find_findings(inventory)] == ["same_in_other_clients"]
