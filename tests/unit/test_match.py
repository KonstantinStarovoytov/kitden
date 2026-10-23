"""When two items with one name are the same: a server by its command and address, a skill by
its files or its plugin."""

import shutil
from dataclasses import replace

from kitden.model import Item, ItemKind, Scope, Source, SourceKind
from kitden.views.match import odd_ones, plugin_of, source_keys


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
