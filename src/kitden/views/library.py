"""The Library: one list per kind of what each client has and what it can add.

Rows join the load map (what is on this computer) with the plugin and skill catalogs (what the
marketplaces on this computer offer). Each cell already says the state, or the one action for
that client, or why there is none. Columns are the clients found on this computer.
"""

from collections.abc import Callable

from kitden.changes.actions import KITDEN_GATEWAY, PLUGIN_INSTALL, PLUGIN_SKILLS, SKILL_INSTALL
from kitden.clients.base import REMOVE_DIRECT
from kitden.model import ClientStatus, Item, ItemKind, _hash
from kitden.views.catalog import catalog, search
from kitden.views.gateway_view import group_of
from kitden.views.load_map import COLUMNS, MARKS, NAMES, Row, load_map
from kitden.views.skills import skill_catalog

KINDS = ("mcp_server", "plugin", "skill", "hook", "marketplace")
# Tabs with something to add; the others show only what is on this computer.
CATALOG_KINDS = ("plugin", "skill")
SHOWS = ("mine", "new", "all")
VIA_CLAUDE_CODE = "Cursor loads Claude Code's plugins. Add it to Claude Code."
SKILL_VIA_CLAUDE_CODE = "Cursor loads Claude Code's plugins. Add the plugin to Claude Code."
OUTSIDE_FOLDER = "This skill uses files outside its folder, so it can't be copied."
SHARE_IN_GATEWAY = "Move it into the gateway to share it."


def _cell(
    state: str = "none",
    where: str | None = None,
    items: list[str] | None = None,
    word: str | None = None,
    add: dict | None = None,
    reason: str | None = None,
) -> dict:
    return {
        "state": state,
        "where": where,
        "items": items or [],
        "word": word,
        "add": add,
        "reason": reason,
    }


def _add(
    action: str,
    label: str,
    plugin: str | None = None,
    skill: str | None = None,
    marketplace: str | None = None,
    warn: str | None = None,
) -> dict:
    return {
        "action": action,
        "label": label,
        "plugin": plugin,
        "skill": skill,
        "marketplace": marketplace,
        "warn": warn,
    }


def _row(
    key: str,
    kind: str,
    name: str,
    source: str | None,
    cells: dict[str, dict],
    *,
    mine: bool,
    lookup: str | None,
    offer: str | None = None,
    flags: list[dict] | None = None,
    category: str | None = None,
    description: str = "",
) -> dict:
    return {
        "key": key,
        "kind": kind,
        "name": name,
        "source": source,
        "same_name": False,
        "category": category,
        "description": description,
        "mine": mine,
        "lookup": lookup,
        "offer": offer,
        "flags": flags or [],
        "cells": cells,
    }


def _has(row: Row | None, client: str) -> bool:
    """The load map says the client has the item (loads it, has it off, or may load it)."""
    return row is not None and row.cells[client].state not in ("none", "missing")


def _map_cell(row: Row, client: str) -> dict:
    cell = row.cells[client]
    return _cell(cell.state, cell.where, cell.items)


# Each builder gives (row, holders): holders are the found clients that have the item.
Built = list[tuple[dict, set[str]]]
# Why a client has a dash in a load map row, or None when no reason is true.
Why = Callable[[Row, str], str | None]


def _map_rows(map_rows: list[Row], kind: str, found: list[str], why: Why | None = None) -> Built:
    """MCP servers, hooks and marketplaces: the load map rows as they are, and a reason on a
    dash where `why` has one."""
    out = []
    for r in map_rows:
        if str(r.kind) != kind:
            continue
        holders = {c for c in found if _has(r, c)}
        cells = {c: _map_cell(r, c) for c in found}
        for client, cell in cells.items():
            if why and cell["state"] == "none":
                cell["reason"] = why(r, client)
        row = _row(
            r.key, kind, r.name, r.source, cells, mine=bool(holders), lookup=r.lookup, flags=r.flags
        )
        out.append((row, holders))
    return out


def _server_why(map_rows: list[Row], found: list[str], items: list[Item]) -> Why:
    """A gateway entry: connect the client. A direct server another client loads: move it into
    the gateway this client reaches. Kitden copies no server entry from one client to another,
    so other dashes have no reason."""
    by_id = {i.id: i for i in items}
    servers = [r for r in map_rows if r.kind is ItemKind.MCP_SERVER]
    on_gateway = {c for r in servers for c in found if r.cells[c].state == "gw"}

    def movable(row: Row) -> bool:
        # The same entries the Gateway page offers to move.
        loaded = [
            i for c in found if row.cells[c].state in ("on", "unk") for i in row.cells[c].items
        ]
        return any(
            group_of(by_id[i]) == "move" and REMOVE_DIRECT in by_id[i].actions
            for i in loaded
            if i in by_id
        )

    def held(row: Row) -> bool:
        """The Kitden gateway holds it: a client reaches it through its `kitden` entry."""
        return any(
            by_id[i].via_gateway == KITDEN_GATEWAY
            for c in found
            for i in row.cells[c].items
            if i in by_id
        )

    def why(row: Row, client: str) -> str | None:
        if client in on_gateway:
            return SHARE_IN_GATEWAY if movable(row) else None
        if any(row.cells[c].state == "gw" for c in found):
            if held(row):
                return f"Set up the Kitden gateway in {NAMES[client]} on the Gateway page."
            return f"Connect {NAMES[client]} to the gateway on the Gateway page."
        return None

    return why


def _marketplace_why(offers: list[dict]) -> Why:
    """A client gets a marketplace with the first plugin it adds from it. Cursor keeps its
    plugins in the account, so Kitden adds none there and its dash has no reason."""
    brings = {
        (c, o["marketplace"])
        for o in offers
        for c, r in o["routes"].items()
        if r == "add_marketplace"
    }

    def why(row: Row, client: str) -> str | None:
        if (client, row.name) in brings:
            return f"{NAMES[client]} gets it the first time you add one of its plugins."
        return None

    return why


# Plugins -------------------------------------------------------------------------------------


def _plugin_cell(
    client: str,
    plugin_id: str,
    name: str,
    offer: dict | None,
    routes: dict[str, str],
    skills: list[dict],
    cursor_imports: bool,
    twin: str | None,
) -> dict:
    """What a client without the plugin here can do: add it, get it through Claude Code, or
    take the skills that work alone. Otherwise, why not. A route comes only with an offer.
    `twin` is the other marketplace the client has a plugin of this name from."""
    who = NAMES[client]
    # The client has it in a project this view does not show; adding it again would fail.
    if offer and client in offer["installed"]:
        return _cell(reason=f"{who} has it in another project.")
    route = routes.get(client)
    if offer and route:
        marketplace = offer["marketplace"] if route == "add_marketplace" else None
        warn = f"{who} already has {name} from {twin}. It will load both." if twin else None
        return _cell(
            add=_add(PLUGIN_INSTALL, "+ Add", plugin_id, marketplace=marketplace, warn=warn)
        )
    # When Claude Code has the plugin, the load map already shows Cursor's copy; when it shows
    # none (an account plugin), Cursor does not import it.
    if client == "cursor" and cursor_imports and "claude_code" in routes:
        return _cell("via", word="Via Claude Code", reason=VIA_CLAUDE_CODE)
    alone = [s for s in skills if s["self_contained"]]
    if any(client in s["routes"] for s in alone):
        warn = (
            f"{who} already has {name} from {twin}. It will load skills from both."
            if twin
            else None
        )
        return _cell(add=_add(PLUGIN_SKILLS, "+ Add skills", plugin_id, warn=warn))
    # Copied here, or brought by another plugin: either way the client has them.
    if alone and all(client in s["installed"] for s in alone):
        return _cell(
            "done",
            word="Has its skills",
            reason=f"{who} already has every skill it can take from this plugin.",
        )
    why = "its skills need the rest of it" if skills else "it has no skills to copy"
    return _cell(reason=f"{who} can't install this plugin, and {why}.")


def _plugin_rows(
    map_rows: list[Row],
    offers: list[dict],
    skills: list[dict],
    found: list[str],
    cursor_imports: bool,
) -> Built:
    """Plugins on this computer and plugins in its marketplaces, one row per
    name@marketplace: a load map row and an offer with the same id are one row."""
    rows = {r.key: r for r in map_rows if r.kind is ItemKind.PLUGIN}
    offered = {_hash(ItemKind.PLUGIN, o["id"]): o for o in offers}
    by_plugin: dict[str, list[dict]] = {}
    for skill in skills:
        if skill["plugin"]:
            by_plugin.setdefault(skill["plugin"], []).append(skill)
    # Which marketplaces each client already has a plugin of this name from.
    has_name: dict[tuple[str, str], list[str]] = {}
    for row in rows.values():
        for client in found:
            if row.source and _has(row, client):
                has_name.setdefault((row.name, client), []).append(row.source)

    out = []
    for key in [*rows, *(k for k in offered if k not in rows)]:
        row, offer = rows.get(key), offered.get(key)
        plugin_id = offer["id"] if offer else row.lookup
        name = row.name if row else offer["name"]
        source = row.source if row else offer["marketplace"]
        routes = {c: r for c, r in (offer["routes"] if offer else {}).items() if c in found}
        plugin_skills = by_plugin.get(plugin_id, [])
        cells = {}
        for client in found:
            if _has(row, client):
                cells[client] = _map_cell(row, client)
                continue
            others = [m for m in has_name.get((name, client), []) if m != source]
            cells[client] = _plugin_cell(
                client,
                plugin_id,
                name,
                offer,
                routes,
                plugin_skills,
                cursor_imports,
                others[0] if others else None,
            )
        installed = offer["installed"] if offer else []
        holders = {c for c in found if _has(row, c) or c in installed}
        built = _row(
            key,
            "plugin",
            name,
            source,
            cells,
            mine=bool(holders),
            lookup=row.lookup if row else None,
            offer=offer["id"] if offer else None,
            flags=row.flags if row else [],
            category=offer["category"] if offer else None,
            description=offer["description"] if offer else "",
        )
        out.append((built, holders))
    return out


# Skills --------------------------------------------------------------------------------------


def _skill_cell(
    client: str,
    skill: dict,
    row: Row | None,
    plugin_routes: dict[str, str],
    cursor_imports: bool,
) -> dict:
    """The scan's state when it has one; else how the skill list says the client gets it, or
    what the client can add."""
    if _has(row, client):
        return _map_cell(row, client)
    word = skill["installed"].get(client)
    if word:
        # "Via Claude Code" -> "via Claude Code", as the load map says it.
        return _cell("on", where=word[:1].lower() + word[1:])
    if client in skill["routes"]:
        return _cell(add=_add(SKILL_INSTALL, "+ Add", skill=skill["id"]))
    # A found client without the skill and without a route: it does not work alone.
    if skill["plugin"] is None:
        return _cell(reason=OUTSIDE_FOLDER)
    route = plugin_routes.get(client)
    if route:
        marketplace = skill["marketplace"] if route == "add_marketplace" else None
        return _cell(
            add=_add(PLUGIN_INSTALL, "+ Add the plugin", skill["plugin"], marketplace=marketplace)
        )
    if client == "cursor" and cursor_imports and "claude_code" in plugin_routes:
        return _cell("via", word="Via Claude Code", reason=SKILL_VIA_CLAUDE_CODE)
    return _cell(reason=f"{NAMES[client]} can't install the plugin this skill needs.")


def _skill_rows(
    map_rows: list[Row],
    offers: list[dict],
    skills: list[dict],
    found: list[str],
    cursor_imports: bool,
) -> Built:
    """Every skill in the skill catalog, plus skills the load map has that it does not.

    A catalog row takes the cells, flags and lookup of the load map row with its name, where
    that row has them. The first one also takes its key, so links from the Overview still find
    it; keys stay unique.
    """
    mapped = {r.name: r for r in map_rows if r.kind is ItemKind.SKILL}
    routes = {o["id"]: o["routes"] for o in offers}
    used: set[str] = set()
    out = []
    for skill in skills:
        row = mapped.get(skill["name"])
        key = row.key if row and row.key not in used else _hash(ItemKind.SKILL, skill["id"])
        used.add(key)
        plugin_routes = {c: r for c, r in routes.get(skill["plugin"], {}).items() if c in found}
        holders = {c for c in found if _has(row, c) or c in skill["installed"]}
        built = _row(
            key,
            "skill",
            skill["name"],
            skill["from"],
            {c: _skill_cell(c, skill, row, plugin_routes, cursor_imports) for c in found},
            mine=bool(holders),
            lookup=row.lookup if row else None,
            offer=skill["id"],
            flags=row.flags if row else [],
            category=skill["category"],
            description=skill["description"],
        )
        out.append((built, holders))
    named = {s["name"] for s in skills}
    extra = [r for r in map_rows if r.kind is ItemKind.SKILL and r.name not in named]
    return out + _map_rows(extra, "skill", found)


# Filters -------------------------------------------------------------------------------------


def _mark_same_names(rows: list[dict]) -> None:
    seen: dict[str, int] = {}
    for row in rows:
        seen[row["name"]] = seen.get(row["name"], 0) + 1
    for row in rows:
        row["same_name"] = seen[row["name"]] > 1


def _in_view(row: dict, holders: set[str], visible: list[str]) -> bool:
    """Not a row only hidden clients have, and a shown client has it or can do something."""
    if holders and not holders.intersection(visible):
        return False
    return any(row["cells"][c]["state"] != "none" or row["cells"][c]["add"] for c in visible)


def _matching(rows: list[dict], q: str, kind: str) -> list[dict]:
    """Rows that match the search: on plugins and skills best first (catalog.search), on the
    other tabs any part of the name ("hub" finds github)."""
    if not q.strip():
        return rows
    if kind not in CATALOG_KINDS:
        part = q.strip().lower()
        return [r for r in rows if part in r["name"].lower()]
    terms = [
        {
            "name": r["name"],
            "description": r["description"],
            "category": r["category"],
            "from": r["source"] if r["kind"] == "skill" else None,
            "marketplace": r["source"] if r["kind"] == "plugin" else None,
            "at": i,
        }
        for i, r in enumerate(rows)
    ]
    return [rows[t["at"]] for t in search(terms, q)]


def _chosen(rows: list[dict], kind: str, show: str, q: str) -> list[dict]:
    """Rows the show choice keeps, matching the search."""
    kept = [r for r in rows if show == "all" or r["mine"] == (show == "mine")]
    return _matching(kept, q, kind)


def _needs_attention(row: dict) -> bool:
    return any(f.get("level") == "warning" for f in row["flags"])


def _narrowed(rows: list[dict], category: str, attention: bool) -> list[dict]:
    return [
        r
        for r in rows
        if (not category or r["category"] == category) and (not attention or _needs_attention(r))
    ]


def _categories(rows: list[dict]) -> list[dict]:
    seen: dict[str, int] = {}
    for row in rows:
        if row["category"]:
            seen[row["category"]] = seen.get(row["category"], 0) + 1
    return [{"name": n, "count": c} for n, c in sorted(seen.items(), key=lambda p: (-p[1], p[0]))]


def _ordered(rows: list[dict], ranked: bool) -> list[dict]:
    """What is on this computer first; inside each group the search rank, or else by name."""
    if ranked:
        return sorted(rows, key=lambda r: not r["mine"])  # stable: keeps the search rank
    return sorted(rows, key=lambda r: (not r["mine"], r["name"].lower(), r["source"] or ""))


def _notes(rows: list[dict], visible: list[str]) -> list[str]:
    """One line per client and marketplace an add brings in first."""
    pairs = {
        (c, r["cells"][c]["add"]["marketplace"])
        for r in rows
        for c in visible
        if r["cells"][c]["add"] and r["cells"][c]["add"]["marketplace"]
    }
    return [
        f"{NAMES[c]} gets the {m} marketplace the first time you add one of its plugins."
        for c, m in sorted(pairs, key=lambda p: (COLUMNS.index(p[0]), p[1]))
    ]


def library(
    inventory,
    adapters,
    project: str | None,
    *,
    gateway_registered: bool,
    kind: str,
    show: str = "mine",
    q: str = "",
    category: str = "",
    hidden: frozenset[str] = frozenset(),
    attention: bool = False,
) -> dict:
    """The rows of one kind tab, with the columns, the tab counts and the lines above the table.

    `show` is "mine" (Installed), "new" (New: not on this computer yet) or "all"; the tabs
    without a catalog always show what is on this computer. `hidden` columns stay in
    `columns`, marked, and a row that only they have is left out; hiding every found client
    hides none. Counts follow show, search and hidden, not the category.
    """
    status = {c.id: c.status for c in inventory.clients}
    found = [c for c in COLUMNS if status.get(c) is ClientStatus.FOUND]
    if hidden.issuperset(found):
        hidden = frozenset()
    visible = [c for c in found if c not in hidden]
    cursor = adapters.get("cursor") if "cursor" in found else None
    cursor_imports = bool(cursor and cursor.imports_claude_plugins())

    map_rows = load_map(inventory, project, gateway_registered=gateway_registered)
    offers = catalog(inventory, adapters)
    skills = skill_catalog(inventory, adapters)
    built = {
        "mcp_server": _map_rows(
            map_rows, "mcp_server", found, _server_why(map_rows, found, inventory.items)
        ),
        "plugin": _plugin_rows(map_rows, offers, skills, found, cursor_imports),
        "skill": _skill_rows(map_rows, offers, skills, found, cursor_imports),
        # Kitden adds no hooks, so a hook's dash has no reason.
        "hook": _map_rows(map_rows, "hook", found),
        "marketplace": _map_rows(map_rows, "marketplace", found, _marketplace_why(offers)),
    }
    rows = {}
    for k, pairs in built.items():
        _mark_same_names([r for r, _ in pairs])
        rows[k] = [r for r, holders in pairs if _in_view(r, holders, visible)]

    def show_for(k: str) -> str:
        return show if k in CATALOG_KINDS else "mine"

    has_catalog = kind in CATALOG_KINDS
    category = category if has_catalog else ""
    matched = _chosen(rows[kind], kind, show_for(kind), q)
    shown = _narrowed(matched, category, attention)
    more = 0
    if q.strip() and has_catalog and show != "all":
        everything = _narrowed(_chosen(rows[kind], kind, "all", q), category, attention)
        more = len(everything) - len(shown)
    return {
        "columns": [
            {"id": c, "name": NAMES[c], "mark": MARKS[c], "hidden": c in hidden} for c in found
        ],
        "counts": {
            k: len(matched) if k == kind else len(_chosen(rows[k], k, show_for(k), q))
            for k in KINDS
        },
        "rows": _ordered(shown, ranked=bool(q.strip()) and has_catalog),
        "more": more,
        "attention": len(_narrowed(matched, category, True)),
        "categories": _categories(matched) if has_catalog else [],
        "notes": _notes(shown, visible),
    }
