"""When two items with one name are the same item: an MCP server by its command, arguments and
address; a skill by its files, or by its plugin; anything else by its full name.

The Library's "Needs review", Add missing's "Not the same" and the Overview notes use these.
"""

import os
from collections import Counter
from pathlib import Path, PurePath

from kitden.model import Item, ItemKind, Scope, normalize_url
from kitden.views.skills import skill_digest

# What makes two MCP entries one server; "type" is only how each client spells it.
SERVER_FIELDS = ("command", "args", "url")


def plugin_of(item: Item) -> str | None:
    """'superpowers@claude-plugins-official' for a part of that plugin, else None. All three
    clients keep a plugin's files in plugins/cache/<marketplace>/<plugin>/<version>/ (checked
    2026-10-20: Claude Code's installPath in 2.1.283, Codex, Cursor's plugin folders)."""
    if item.scope is not Scope.PLUGIN:
        return None
    parts = PurePath(item.source.path or "").parts
    for i in range(len(parts) - 4, -1, -1):
        if parts[i] == "plugins" and parts[i + 1] == "cache":
            return f"{parts[i + 3]}@{parts[i + 2]}"
    return None


def folder_key(folder: Path) -> str:
    """A skill folder by its files, so a copy is the same skill; by its real path when Kitden
    cannot read its files."""
    return skill_digest(folder) or os.path.realpath(folder)


def source_keys(item: Item) -> frozenset:
    """Where an item comes from. Two items with the same name are the same when their keys
    meet: a skill matches by its files or by its plugin, so a newer copy of a plugin's skill is
    still that plugin's."""
    if item.kind is ItemKind.MCP_SERVER:
        pairs = tuple(
            (key, normalize_url(value) if key == "url" else value)
            for key, value in item.summary
            if key in SERVER_FIELDS
        )
        return frozenset({pairs})
    if item.kind is ItemKind.SKILL and item.source.path:
        keys = {folder_key(Path(item.source.path).parent)}
        plugin = plugin_of(item)
        if plugin:
            keys.add(f"plugin:{plugin}")
        return frozenset(keys)
    return frozenset({item.name})


def catalog_keys(skill: dict) -> frozenset:
    """A skill list row's keys, the same way as source_keys."""
    keys = {folder_key(Path(skill["path"]))}
    if skill["plugin"]:
        keys.add(f"plugin:{skill['plugin']}")
    return frozenset(keys)


def odd_ones(keys: dict[str, frozenset]) -> set[str]:
    """The clients whose keys share nothing with the keys most clients have (on a tie, the
    first client's). Empty when every client has the same keys."""
    values = list(keys.values())
    if len(set(values)) < 2:
        return set()
    counts = Counter(values)
    reference = max(values, key=lambda k: (counts[k], -values.index(k)))
    return {client for client, k in keys.items() if k.isdisjoint(reference)}
