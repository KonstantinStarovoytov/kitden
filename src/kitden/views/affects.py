"""Which clients a change to one definition reaches, and where, for Details before any action.

The same readers the review's steps name: the clients that read a skill's folder
(`skill_readers`, sent as a removal step's `reaches`), and Cursor's import of Claude Code's user
plugins (the After chips' Cursor line). A reader that keeps another copy of its own is left out,
as the review leaves it out (`skill_keepers`, `cursor_keeps`).
"""

from kitden.model import Item, ItemKind, Scope
from kitden.views.after import cursor_keeps
from kitden.views.skills import CLIENT_WORDS, CLIENTS, skill_keepers, skill_readers
from kitden.views.words import LOADS_PLUGINS, READS_FOLDER


def affects(inventory, item: Item) -> dict:
    """`clients`: the clients the change reaches, in CLIENTS order. `scope`: "project" when it
    changes one project's files (the page says "In this project."; whether other projects stay
    as they are is the review's to say), else "all". `note`: why other clients are reached."""
    reached = {item.client}
    notes: list[str] = []
    if item.kind is ItemKind.SKILL and item.source.path:
        # The folder's owner; ~/.agents/skills ("shared") is no client's, so it gets no note.
        owner = CLIENT_WORDS.get(item.source.owner_client)
        readers = skill_readers(inventory, item)
        keepers = skill_keepers(inventory, item, readers)
        for reader in readers:
            if reader != item.client and reader not in keepers:
                reached.add(reader)
                if owner:
                    notes.append(READS_FOLDER.format(reader=CLIENT_WORDS[reader], owner=owner))
    elif item.kind is ItemKind.PLUGIN and item.scope is Scope.USER:
        # Only Cursor lists another client's plugin as its own item: its import of Claude Code's
        # user plugins. (It reads Claude Code's hooks too, but Kitden changes no hook.)
        importers = {
            i.client
            for i in inventory.items
            if i.client != item.client
            and i.kind is ItemKind.PLUGIN
            and i.name == item.name
            and i.source.owner_client == item.client
        }
        if importers and not cursor_keeps(inventory, item.name):
            reached |= importers
            notes.append(LOADS_PLUGINS)
    in_project = item.project and item.scope in (Scope.PROJECT, Scope.LOCAL)
    order = {c: i for i, c in enumerate(CLIENTS)}
    return {
        "clients": sorted(reached, key=lambda c: order.get(c, len(CLIENTS))),
        "scope": "project" if in_project else "all",
        "note": "; ".join(notes) or None,
    }
