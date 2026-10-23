"""When two items with one name are the same item: an MCP server by its command, arguments and
address; a skill by its files, or by its plugin; a marketplace by where it comes from; anything
else by its full name.

The Library's "Needs review", Add missing's "Not the same" and the Overview notes use these.
"""

import os
from collections import Counter
from pathlib import Path, PurePath

from kitden.clients.base import SETUP_NAME
from kitden.clients.claude_code import DESKTOP
from kitden.model import Item, ItemKind, Scope, normalize_url
from kitden.views.skills import skill_digest

# What makes two MCP entries one server; "type" is only how each client spells it.
SERVER_FIELDS = ("command", "args", "url")
# Plugin copies of skills: skill folder name -> (plugin id, folder) of each copy.
Copies = dict[str, list[tuple[str, str]]]


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


def is_compared(item: Item) -> bool:
    """An entry of the client's own: a server the gateway holds, Kitden's own entry, an account
    item and the Desktop app's are not compared."""
    return (
        item.via_gateway is None
        and item.name != SETUP_NAME
        and item.scope is not Scope.ACCOUNT
        and item.client != DESKTOP
    )


def plugin_copies(inventory) -> Copies:
    """Every plugin's copy of a skill on this computer: in a marketplace or Cursor's plugin
    folders (Inventory.plugin_skills), and installed (a plugin's skill item)."""
    copies: Copies = {}
    found = [(p, f) for p, f in inventory.plugin_skills]
    for item in inventory.items:
        plugin = plugin_of(item) if item.kind is ItemKind.SKILL else None
        if plugin and item.source.path:
            found.append((plugin, str(Path(item.source.path).parent)))
    for plugin, folder in found:
        copies.setdefault(Path(folder).name, []).append((plugin, folder))
    return copies


def folder_key(folder: Path) -> str:
    """A skill folder by its files, so a copy is the same skill; by its real path when Kitden
    cannot read its files."""
    return skill_digest(folder) or os.path.realpath(folder)


def plugin_keys(item: Item) -> frozenset:
    """The keys known without reading a file: a plugin's skill by its plugin."""
    plugin = plugin_of(item) if item.kind is ItemKind.SKILL else None
    return frozenset({f"plugin:{plugin}"}) if plugin else frozenset()


def _server(value: str, key: str) -> str:
    """A server field as Kitden copies it: Cursor's `${env:X}` is `${X}` (server_entry.py)."""
    value = value.replace("${env:", "${")
    return normalize_url(value) if key == "url" else value


def source_keys(item: Item, copies: Copies | None = None) -> frozenset:
    """Where an item comes from. Two items with the same name are the same when their keys
    meet. A server is keyed as Kitden's copy writes it (an empty value left out), so a copy is
    the same server. A skill matches by its files or by its plugin, so a newer copy of a
    plugin's skill is still that plugin's, and so is a folder with the files of a plugin's copy
    (`copies`). A marketplace that does not say where it comes from has no keys."""
    if item.kind is ItemKind.MCP_SERVER:
        pairs = tuple(
            (key, _server(value, key))
            for key, value in item.summary
            if key in SERVER_FIELDS and value not in ("", "[]")
        )
        return frozenset({pairs})
    if item.kind is ItemKind.SKILL and item.source.path:
        folder = Path(item.source.path).parent
        own = folder_key(folder)
        keys = {own} | plugin_keys(item)
        for plugin, place in (copies or {}).get(folder.name, []):
            if f"plugin:{plugin}" not in keys and folder_key(Path(place)) == own:
                keys.add(f"plugin:{plugin}")
        return frozenset(keys)
    if item.kind is ItemKind.MARKETPLACE:
        source = dict(item.summary).get("source")
        return frozenset({("source", source)}) if source else frozenset()
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


def odd_sources(items: dict[str, list[Item]], copies: Copies | None = None) -> set[str]:
    """odd_ones of each client's items. Parts of one plugin are the same without reading
    their files; a client whose items have no keys is not compared."""
    quick = [frozenset().union(*(plugin_keys(i) for i in group)) for group in items.values()]
    if len(items) < 2 or (all(quick) and frozenset.intersection(*quick)):
        return set()
    keys = {
        client: frozenset().union(*(source_keys(i, copies) for i in group))
        for client, group in items.items()
    }
    return odd_ones({client: k for client, k in keys.items() if k})
