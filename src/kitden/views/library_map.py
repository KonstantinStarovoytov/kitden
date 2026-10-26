"""The Library map: clients, then plugins and skills by where they come from, then what a plugin
holds (spec Part 5.3).

Only what is on this computer and present in some client shows: a marketplace plugin no client
has is left out, and so are account plugins. A plugin's parts are read from its installed folder
and follow the plugin, so the map never says "N of M on". Paths are only under `technical`.
"""

from kitden.changes.actions import CLIENT_WORDS
from kitden.model import ClientStatus, Item, ItemKind, Scope
from kitden.views.catalog import catalog, installed_inside
from kitden.views.effective import in_project
from kitden.views.load_map import COLUMNS, Row, load_map, row_key
from kitden.views.setup_server import kitden_on, setup_server_state
from kitden.views.words import ORIGIN_WORDS, STATE_WORDS

# A client's words, from its `kitden` entry, as on the Gateway.
CONNECTED = "Connected"
NOT_CONNECTED = "Not connected"
STORE = "store"
# Plugins whose id names no marketplace (a Cursor plugin whose name is not stored locally).
OTHER = {"key": "other", "name": "Other plugins", "icon": "puzzle", "kind": "other"}
SKILLS = {"key": "skills", "name": "Your skills", "icon": "user-round", "kind": "skills"}
SETTINGS = {"key": "settings", "name": "Your settings", "icon": "settings", "kind": "settings"}
PROJECT = {
    "key": "project",
    "name": ORIGIN_WORDS["project"],
    "icon": "folder",
    "kind": "project",
}
KINDS = {ItemKind.PLUGIN: "plugin", ItemKind.SKILL: "skill", ItemKind.HOOK: "hook"}


def _clients(inventory, cursor_imports: bool) -> list[dict]:
    """Each client and its state: not installed, not read, Cursor getting Claude Code's plugins,
    or whether its `kitden` entry is on."""
    status = {c.id: c.status for c in inventory.clients}
    setup = {e["client"]: e for e in setup_server_state(inventory)}
    out = []
    for client in COLUMNS:
        read, entry = status.get(client), setup[client]
        if read is ClientStatus.UNREADABLE:
            state, words = "unreadable", STATE_WORDS["unread"]
        elif read is not ClientStatus.FOUND:
            state, words = "missing", STATE_WORDS["missing"]
        elif client == "cursor" and cursor_imports:
            state, words = "via", STATE_WORDS["via"]
        elif kitden_on(entry):
            state, words = "on", CONNECTED
        else:
            state = "off"
            words = STATE_WORDS["off"] if entry["enabled"] is False else NOT_CONNECTED
        out.append({"id": client, "name": CLIENT_WORDS[client], "state": state, "words": words})
    return out


def _present(inventory, project: str | None) -> dict[str, list[Item]]:
    """The items on this computer that apply in this view, by load map row. Account plugins are
    kept in the account, not here."""
    out: dict[str, list[Item]] = {}
    for item in inventory.items:
        if item.client not in COLUMNS or item.kind not in KINDS or item.scope is Scope.ACCOUNT:
            continue
        if item.project is None or item.project == project:
            out.setdefault(row_key(item), []).append(item)
    return out


def _group(row: Row, own: list[Item], project: str | None) -> dict:
    if row.kind is ItemKind.PLUGIN and not row.source:
        return OTHER
    if row.kind is ItemKind.PLUGIN:
        key = f"marketplace:{row.source}"
        return {"key": key, "name": row.source, "icon": STORE, "kind": "marketplace"}
    if project is not None and all(i.project is not None for i in own):
        return PROJECT
    return SKILLS if row.kind is ItemKind.SKILL else SETTINGS


def _decides_here(item: Item, project: str) -> bool:
    """The project's own settings decide the item there: it is the project's own entry, or the
    project's rule sets a user skill (see `Item.project_rules`)."""
    return item.project is not None or in_project(item, project).state_scope in (
        Scope.PROJECT,
        Scope.LOCAL,
    )


def _links(row: Row, own: set[str], by_id: dict[str, Item], via: bool):
    """Per client: on, off, unknown (it has the item, but Kitden does not know its state) or via
    (not loaded yet; Cursor gets it once Claude Code has it); the client whose folder it loads
    from when that is another client (a faint link); the client's item ids, the deciding one
    first; and the items that decide. A client without the item, or one Kitden could not read
    that has no item kept, has no entry."""
    by, through, ids, deciding = {}, {}, {}, []
    for client in COLUMNS:
        cell = row.cells[client]
        items = [by_id[i] for i in cell.items if i in own]
        if cell.state == "none" and client == "cursor" and via:
            by[client] = "via"
        if not items or cell.state not in ("on", "review", "off", "unk"):
            continue
        by[client] = {"off": "off", "unk": "unknown"}.get(cell.state, "on")
        ids[client] = [i.id for i in items]
        owner = items[0].source.owner_client
        if by[client] == "on" and owner in COLUMNS and owner != client:
            through[client] = owner
        deciding += items[:1] if cell.state == "off" else items
    return by, through, ids, deciding


def _via_claude_code(row: Row, offers: dict[str, dict], cursor_imports: bool, found) -> bool:
    """Cursor does not have this plugin yet and gets it once Claude Code adds it."""
    offer = offers.get(row.lookup)
    return bool(
        cursor_imports
        and row.kind is ItemKind.PLUGIN
        and offer
        and "claude_code" in found
        and "claude_code" in offer["routes"]
        and "cursor" not in offer["installed"]
    )


def _plugin_folders(adapters) -> dict[str, str]:
    """Plugin id -> its installed folder, the first client's that has it (as installed_inside)."""
    out: dict[str, str] = {}
    for client in COLUMNS:
        if client in adapters:
            for plugin_id, folder in adapters[client].plugin_folders().items():
                out.setdefault(plugin_id, str(folder))
    return out


def _marketplace_sources(inventory) -> dict[str, str]:
    """Marketplace name -> where it comes from, as its item says it (a folder, or host/path with
    no credentials)."""
    out: dict[str, str] = {}
    for client in COLUMNS:
        for item in inventory.items:
            if item.client == client and item.kind is ItemKind.MARKETPLACE:
                source = dict(item.summary).get("source")
                if source:
                    out.setdefault(item.name, source)
    return out


def library_map(inventory, adapters, project: str | None) -> dict:
    """The clients and the source groups of the Library map, in the order the map draws them:
    marketplaces by name, then "Other plugins", "Your skills", "Your settings" and, with a project
    picked, "Only this project". `here` says the picked project's own settings decide the item
    there."""
    status = {c.id: c.status for c in inventory.clients}
    found = [c for c in COLUMNS if status.get(c) is ClientStatus.FOUND]
    cursor = adapters.get("cursor") if "cursor" in found else None
    cursor_imports = bool(cursor and cursor.imports_claude_plugins() and "claude_code" in found)
    by_id = {i.id: i for i in inventory.items}
    present = _present(inventory, project)
    offers = {o["id"]: o for o in catalog(inventory, adapters)}
    held = installed_inside(adapters)
    folders = _plugin_folders(adapters)
    sources = _marketplace_sources(inventory)

    groups: dict[str, dict] = {}
    for row in load_map(inventory, project):
        items = present.get(row.key, [])
        # A plugin's own skills and hooks are in its Inside column.
        own = [i for i in items if row.kind is ItemKind.PLUGIN or i.scope is not Scope.PLUGIN]
        if not own:
            continue
        via = _via_claude_code(row, offers, cursor_imports, found)
        by, through, ids, deciding = _links(row, {i.id for i in own}, by_id, via)
        if not by:
            continue
        group = _group(row, own, project)
        here = (
            project is not None
            and group["key"] != PROJECT["key"]
            and any(_decides_here(i, project) for i in deciding)
        )
        entry = {
            "id": row.key,
            "name": row.name,
            "kind": KINDS[row.kind],
            "by": by,
            "through": through,
            "items": ids,
            "here": here,
            "source": group["name"],
        }
        technical: dict[str, str] = {}
        if row.kind is ItemKind.PLUGIN:
            entry["plugin"] = row.lookup
            if row.lookup in held:
                entry["inside"] = held[row.lookup]
                entry["count"] = sum(len(names) for names in held[row.lookup].values())
            if row.lookup in folders:
                technical["path"] = folders[row.lookup]
            if row.source in sources:
                technical["marketplace"] = sources[row.source]
        elif own[0].source.path:
            technical["path"] = own[0].source.path
        entry["technical"] = technical
        groups.setdefault(group["key"], {**group, "items": []})
        groups[group["key"]]["items"].append(entry)

    markets = sorted(
        (g for g in groups.values() if g["kind"] == "marketplace"),
        key=lambda g: g["name"].lower(),
    )
    rest = [groups[g["key"]] for g in (OTHER, SKILLS, SETTINGS, PROJECT) if g["key"] in groups]
    for group in [*markets, *rest]:
        group["items"].sort(key=lambda i: i["name"].lower())
    return {"clients": _clients(inventory, cursor_imports), "groups": [*markets, *rest]}
