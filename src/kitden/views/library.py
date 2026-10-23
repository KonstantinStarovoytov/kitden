"""The Library: one list per kind of what each client has and what it can add.

Rows join the load map (what is on this computer) with the plugin and skill catalogs (what the
marketplaces on this computer offer). Each cell already says the state, or the one action for
that client, or why there is none. Columns are the clients found on this computer, and those
Kitden could not read: their cells say Unknown and offer no add. A row where a client's item has
the name but another source says "Needs review" there and offers no add.
"""

from collections.abc import Callable
from pathlib import Path

from kitden.changes.actions import (
    CLIENT_WORDS,
    KITDEN_GATEWAY,
    MCP_ADD,
    PLUGIN_INSTALL,
    PLUGIN_SKILLS,
    SKILL_INSTALL,
)
from kitden.clients.base import REMOVE_DIRECT, SETUP_NAME, is_direct_entry, is_home
from kitden.model import ClientStatus, Item, ItemKind, Scope, _hash
from kitden.views.catalog import catalog, search
from kitden.views.gateway_view import group_of
from kitden.views.load_map import COLUMNS, MARKS, NAMES, Row, load_map
from kitden.views.match import Copies, catalog_keys, plugin_copies, plugin_keys, source_keys
from kitden.views.skills import skill_catalog
from kitden.views.words import (
    CLIENT_UNREAD,
    NO_ADD_REVIEW,
    NO_ADD_UNREAD,
    NOT_SAME,
    NOT_SHOWN,
    ORIGIN_WORDS,
    ROUTE_WORDS,
    STATE_WORDS,
)

KINDS = ("mcp_server", "plugin", "skill", "hook", "marketplace", "instructions")
# Tabs with something to add; the others show only what is on this computer.
CATALOG_KINDS = ("plugin", "skill")
SHOWS = ("mine", "new", "all")
VIA_CLAUDE_CODE = "Cursor loads Claude Code's plugins. Add it to Claude Code."
SKILL_VIA_CLAUDE_CODE = "Cursor loads Claude Code's plugins. Add the plugin to Claude Code."
OUTSIDE_FOLDER = "This skill uses files outside its folder, so it can't be copied."
SHARE_IN_GATEWAY = "Move it into the gateway to share it."
# Where a plugin goes into one project when Kitden cannot put it there.
# checked 2026-10-22 (learn.chatgpt.com/docs/plugins): Codex installs a plugin for its whole
# environment; the docs show no per-project install.
CODEX_PROJECT = "Codex plugins are for all projects."
# checked 2026-10-22 (cursor.com/docs/plugins): in Customize you select Install and choose a
# project or user scope. Cursor keeps it in its own database, so Kitden writes nothing.
CURSOR_PROJECT = (
    "To add a plugin to one project in Cursor: Customize → Plugins, Install, "
    "then choose the project scope."
)


def _cell(
    state: str = "none",
    where: str | None = None,
    items: list[str] | None = None,
    word: str | None = None,
    add: dict | None = None,
    reason: str | None = None,
    origin: str | None = None,
    route: str | None = None,
    stale_at: str | None = None,
) -> dict:
    return {
        "state": state,
        "where": where,
        "origin": origin,
        "route": route,
        "stale_at": stale_at,
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
    item: str | None = None,
    project_place: bool = False,
    project_hint: str | None = None,
) -> dict:
    """One add. `project_place`: with a project picked it can go into that project only.
    `project_hint`: where it goes instead, said in a project view."""
    return {
        "action": action,
        "label": label,
        "plugin": plugin,
        "skill": skill,
        "marketplace": marketplace,
        "item": item,
        "warn": warn,
        "project_place": project_place,
        "project_hint": project_hint,
    }


def _plugin_add(
    client: str, label: str, plugin_id: str, marketplace: str | None, warn: str | None = None
) -> dict:
    """A plugin install: Claude Code can put it into one project; Codex cannot."""
    return _add(
        PLUGIN_INSTALL,
        label,
        plugin_id,
        marketplace=marketplace,
        warn=warn,
        project_place=client == "claude_code",
        project_hint=CODEX_PROJECT if client == "codex" else None,
    )


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
    return _cell(
        cell.state,
        cell.where,
        cell.items,
        reason=cell.reason,
        origin=cell.origin,
        route=cell.route,
        stale_at=cell.stale_at,
    )


# Each builder gives (row, holders): holders are the found clients that have the item.
Built = list[tuple[dict, set[str]]]
# Why a client has a dash in a load map row, or None when no reason is true.
Why = Callable[[Row, str], str | None]
# The add a client with a dash in a load map row gets, or None.
Add = Callable[[Row, str], dict | None]


def _map_rows(
    map_rows: list[Row],
    kind: str,
    found: list[str],
    why: Why | None = None,
    add: Add | None = None,
) -> Built:
    """MCP servers, hooks and marketplaces: the load map rows as they are, an add on a dash
    where `add` has one, else a reason where `why` has one."""
    out = []
    for r in map_rows:
        if str(r.kind) != kind:
            continue
        holders = {c for c in found if _has(r, c)}
        cells = {c: _map_cell(r, c) for c in found}
        for client, cell in cells.items():
            if cell["state"] != "none":
                continue
            if add:
                cell["add"] = add(r, client)
            if why and not cell["add"]:
                cell["reason"] = why(r, client)
        row = _row(
            r.key,
            kind,
            r.name,
            r.source,
            cells,
            mine=bool(holders),
            lookup=r.lookup,
            flags=r.flags,
            category=r.category,
        )
        out.append((row, holders))
    return out


def _instruction_rows(map_rows: list[Row], found: list[str]) -> Built:
    """Instruction files, commands and agents: the load map rows, with the state words of every
    tab. Details says when each client reads a file. Kitden adds none, so a dash has no reason."""
    return _map_rows(map_rows, "instructions", found)


def _server_add(found: list[str], items: list[Item]) -> Add:
    """A direct user-scope server one client loads: the other clients Kitden writes can add
    it. The source is the first such entry in column order. A row a gateway serves has none."""
    by_id = {i.id: i for i in items}

    def source(row: Row) -> str | None:
        for client in found:
            if row.cells[client].state != "on":
                continue
            for i in row.cells[client].items:
                item = by_id.get(i)
                if (
                    item is not None
                    and is_direct_entry(item, item.client, {Scope.USER})
                    and item.name != SETUP_NAME
                    and REMOVE_DIRECT in item.actions
                ):
                    return item.id
        return None

    def add(row: Row, client: str) -> dict | None:
        if client not in CLIENT_WORDS or any(row.cells[c].state == "gw" for c in found):
            return None
        item = source(row)
        return _add(MCP_ADD, "+ Add", item=item) if item else None

    return add


def _server_why(map_rows: list[Row], found: list[str], items: list[Item]) -> Why:
    """A gateway entry: connect the client. A direct server another client loads: move it into
    the gateway this client reaches, when the client gets no add (_server_add). Other dashes
    have no reason."""
    by_id = {i.id: i for i in items}
    servers = [r for r in map_rows if r.kind is ItemKind.MCP_SERVER]
    on_gateway = {c for r in servers for c in found if r.cells[c].state == "gw"}

    def movable(row: Row) -> bool:
        # The same entries the Gateway page offers to move.
        loaded = [
            i
            for c in found
            if row.cells[c].state in ("on", "review", "unk")
            for i in row.cells[c].items
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
        return _cell(add=_plugin_add(client, "+ Add", plugin_id, marketplace, warn))
    # When Claude Code has the plugin, the load map already shows Cursor's copy; when it shows
    # none (an account plugin), Cursor does not import it.
    if client == "cursor" and cursor_imports and "claude_code" in routes:
        return _cell("via", word=STATE_WORDS["via"], reason=VIA_CLAUDE_CODE)
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
            word=STATE_WORDS["done"],
            reason=f"{who} already has every skill it can take from this plugin.",
        )
    why = "its skills need the rest of it" if skills else "it has no skills to copy"
    return _cell(reason=f"{who} can't install this plugin, and {why}.")


def _cursor_in_project(cell: dict) -> dict:
    """A Cursor plugin cell in a project view: say where a plugin goes into one project."""
    if cell["add"]:
        cell["add"]["project_hint"] = f"Adds its skills for all projects. {CURSOR_PROJECT}"
    else:
        cell["reason"] = " ".join(filter(None, [cell["reason"], CURSOR_PROJECT]))
    return cell


def _plugin_rows(
    map_rows: list[Row],
    offers: list[dict],
    skills: list[dict],
    found: list[str],
    cursor_imports: bool,
    in_project: bool = False,
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
            if client == "cursor" and in_project:
                _cursor_in_project(cells[client])
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


def _installed_route(word: str) -> str | None:
    """The route of the skill list's installed word: "Installed" has none, "Via plugin" is
    from a plugin, "Via Claude Code" through Claude Code's folder."""
    if word == "Via plugin":
        return ROUTE_WORDS["plugin"]
    if word.startswith("Via "):
        return ROUTE_WORDS["folder"].format(word.removeprefix("Via "))
    return None


def _skill_cell(
    client: str,
    skill: dict,
    row: Row | None,
    plugin_routes: dict[str, str],
    cursor_imports: bool,
    no_place: dict[str, str] | None = None,
    where: str | None = None,
) -> dict:
    """The scan's state when it has one; else how the skill list says the client gets it, or
    what the client can add. `no_place`: clients that cannot take a copy in the picked project,
    with what to say instead. `where`: the scope word of an installed one (its items apply in
    all projects), None with All projects picked."""
    if _has(row, client):
        return _map_cell(row, client)
    word = skill["installed"].get(client)
    if word:
        return _cell("on", where=where, route=_installed_route(word))
    if client in skill["routes"]:
        hint = (no_place or {}).get(client)
        add = _add(SKILL_INSTALL, "+ Add", skill=skill["id"], project_place=hint is None)
        return _cell(add={**add, "project_hint": hint})
    # A found client without the skill and without a route: it does not work alone.
    if skill["plugin"] is None:
        return _cell(reason=OUTSIDE_FOLDER)
    route = plugin_routes.get(client)
    if route:
        marketplace = skill["marketplace"] if route == "add_marketplace" else None
        return _cell(add=_plugin_add(client, "+ Add the plugin", skill["plugin"], marketplace))
    if client == "cursor" and cursor_imports and "claude_code" in plugin_routes:
        return _cell("via", word=STATE_WORDS["via"], reason=SKILL_VIA_CLAUDE_CODE)
    return _cell(reason=f"{NAMES[client]} can't install the plugin this skill needs.")


def _not_this_skill(
    cells: dict[str, dict], skill: dict, items: dict[str, Item], copies: Copies
) -> None:
    """A plugin's skill against the client's own of that name: when they share no files and no
    plugin, the client has another skill, so its cell needs review. A part of this plugin is
    this skill without reading its files."""
    on = [c for c, cell in cells.items() if cell["state"] == "on" and cell["items"]]
    if not on or skill["plugin"] is None:
        return
    keys = None
    for client in on:
        theirs = [items[i] for i in cells[client]["items"] if i in items]
        if f"plugin:{skill['plugin']}" in frozenset().union(*map(plugin_keys, theirs)):
            continue
        keys = keys or catalog_keys(skill)
        if keys.isdisjoint(frozenset().union(*(source_keys(i, copies) for i in theirs))):
            cells[client].update(state="review", reason=NOT_SAME)


def _no_skill_place(adapters, project: str | None) -> dict[str, str]:
    """Codex loads a project's skills only when it trusts the project (codex.py), so in an
    untrusted one its skill add goes to all projects and says why."""
    codex = adapters.get("codex")
    if project is None or codex is None or codex.trusts(project):
        return {}
    name = Path(project).name
    hint = f"Adds for all projects. To add it to {name} only, trust {name} in Codex first."
    return {"codex": hint}


def _skill_rows(
    map_rows: list[Row],
    offers: list[dict],
    skills: list[dict],
    found: list[str],
    cursor_imports: bool,
    items: dict[str, Item],
    copies: Copies,
    no_place: dict[str, str] | None = None,
    in_project: bool = False,
) -> Built:
    """Every skill in the skill catalog, plus skills the load map has that it does not.

    A catalog row takes the cells, flags and lookup of the load map row with its name, where
    that row has them; a plugin's skill that is not the one a client loads needs review there.
    The first one also takes its key, so links from the Overview still find it; keys stay unique.
    """
    mapped = {r.name: r for r in map_rows if r.kind is ItemKind.SKILL}
    routes = {o["id"]: o["routes"] for o in offers}
    # The skill list reads no project: its installed words come from user skills and from plugins
    # of any scope. In a project an installed cell says all projects.
    where = ORIGIN_WORDS[None] if in_project else None
    used: set[str] = set()
    out = []
    for skill in skills:
        row = mapped.get(skill["name"])
        key = row.key if row and row.key not in used else _hash(ItemKind.SKILL, skill["id"])
        used.add(key)
        plugin_routes = {c: r for c, r in routes.get(skill["plugin"], {}).items() if c in found}
        holders = {c for c in found if _has(row, c) or c in skill["installed"]}
        cells = {
            c: _skill_cell(c, skill, row, plugin_routes, cursor_imports, no_place, where)
            for c in found
        }
        _not_this_skill(cells, skill, items, copies)
        built = _row(
            key,
            "skill",
            skill["name"],
            skill["from"],
            cells,
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


# What Kitden could not read -----------------------------------------------------------------


def _unread_cells(rows: list[dict], by_key: dict[str, Row], columns: list[str], found: list[str]):
    """Give each row a cell per client Kitden could not read: the load map row's cell when the
    row has one (Unknown, or kept from the last good read), else Unknown. Never an add. Cells
    keep the column order."""
    unread = [c for c in columns if c not in found]
    for row in rows:
        known = by_key.get(row["key"])
        for client in unread:
            row["cells"][client] = (
                _map_cell(known, client)
                if known
                else _cell("unk", reason=CLIENT_UNREAD.format(NAMES[client]))
            )
        row["cells"] = {c: row["cells"][c] for c in columns}


def _read_notes(inventory, project: str | None, homes: list[Path]) -> list[str]:
    """One line per file Kitden could not read in this view. A file inside known projects
    belongs to the deepest one and shows only when it is picked; the home folder is not a
    project here, as its own files are the user's. A client not read at all has no line (its
    column says it), nor a file whose items are kept from the last good read (its cells say it).
    """
    folders = [
        (p.path, Path(p.path))
        for p in inventory.projects
        if not any(is_home(Path(p.path), h) for h in homes)
    ]
    kept = {i.source.path for i in inventory.items if i.stale_at}
    lines: list[str] = []
    for problem in inventory.problems:
        if not problem.path or problem.path in kept:
            continue
        path = Path(problem.path)
        inside = [(name, f) for name, f in folders if path.is_relative_to(f)]
        owner = max(inside, key=lambda pair: len(pair[1].parts))[0] if inside else None
        line = NOT_SHOWN.format(path.name)
        if owner in (None, project) and line not in lines:
            lines.append(line)
    return lines


def _add_file(adapters, client: str, add: dict, project: str | None) -> str | None:
    """The settings file an add's step edits, put in `project` (None: all projects). The client's
    own step maker builds the step, which never runs. None for a skill copy (it writes only
    folders), or when the client cannot make the step."""
    adapter = adapters.get(client)
    try:
        if adapter is None:
            return None
        if add["action"] == MCP_ADD:
            step = adapter.add_server_step("entry", {})  # the name does not change the file
        elif add["action"] == PLUGIN_INSTALL:
            step = adapter.plugin_install_step(add["plugin"], project)
        else:
            return None
    except ValueError:
        return None
    return step.edit.path if step.edit else None


def _no_add_in_review(rows: list[dict]) -> None:
    """In an MCP server or skill row with a Needs review cell no cell offers an add: it would
    copy one side without asking."""
    for row in rows:
        cells = row["cells"].values()
        if row["kind"] not in ("mcp_server", "skill") or all(c["state"] != "review" for c in cells):
            continue
        for cell in cells:
            if cell["add"]:
                cell["add"] = None
                cell["reason"] = NO_ADD_REVIEW


def _hold_adds(rows: list[dict], adapters, broken: set[str], project: str | None) -> None:
    """No add into a file Kitden could not read: the client may have the item there, so its
    cell is Unknown and says why. Adds into the client's other files stay. An add that can go
    into this project or all projects is held only when every place Kitden can add into is
    broken."""
    if not broken:
        return
    files: dict[tuple, str | None] = {}  # one step per client, action and place

    def file(client: str, add: dict, place: str | None) -> str | None:
        key = (client, add["action"], place)
        if key not in files:
            files[key] = _add_file(adapters, client, add, place)
        return files[key]

    for row in rows:
        for client, cell in row["cells"].items():
            add = cell["add"]
            if not add:
                continue
            places = [project, None] if project is not None and add["project_place"] else [None]
            usable = [f for f in (file(client, add, p) for p in places) if f]
            if usable and all(f in broken for f in usable):
                cell["state"] = "unk"
                cell["add"] = None
                cell["reason"] = NO_ADD_UNREAD.format(Path(usable[0]).name)


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
    columns = [c for c in COLUMNS if c in found or status.get(c) is ClientStatus.UNREADABLE]
    if hidden.issuperset(found):
        hidden = frozenset()
    visible = [c for c in found if c not in hidden]
    homes = list({a.home for a in adapters.values()})
    cursor = adapters.get("cursor") if "cursor" in found else None
    cursor_imports = bool(cursor and cursor.imports_claude_plugins())

    map_rows = load_map(inventory, project, gateway_registered=gateway_registered)
    offers = catalog(inventory, adapters)
    skills = skill_catalog(inventory, adapters)
    built = {
        "mcp_server": _map_rows(
            map_rows,
            "mcp_server",
            found,
            _server_why(map_rows, found, inventory.items),
            _server_add(found, inventory.items),
        ),
        "plugin": _plugin_rows(
            map_rows, offers, skills, found, cursor_imports, in_project=project is not None
        ),
        "skill": _skill_rows(
            map_rows,
            offers,
            skills,
            found,
            cursor_imports,
            {i.id: i for i in inventory.items},
            plugin_copies(inventory),
            _no_skill_place(adapters, project),
            in_project=project is not None,
        ),
        # Kitden adds no hooks, so a hook's dash has no reason.
        "hook": _map_rows(map_rows, "hook", found),
        "marketplace": _map_rows(map_rows, "marketplace", found, _marketplace_why(offers)),
        "instructions": _instruction_rows(map_rows, found),
    }
    by_key = {r.key: r for r in map_rows}
    # A shown client Kitden could not read makes a row visible only with items kept from its
    # last good read: they are on this computer.
    unread = [c for c in columns if c not in found and c not in hidden]
    rows = {}
    for k, pairs in built.items():
        _mark_same_names([r for r, _ in pairs])
        rows[k] = []
        for r, holders in pairs:
            known = by_key.get(r["key"])
            if known and any(known.cells[c].stale_at for c in unread):
                r["mine"] = True
            elif not _in_view(r, holders, visible):
                continue
            rows[k].append(r)
    # After the view, so a held add keeps its row where it was.
    _unread_cells(rows[kind], by_key, columns, found)
    broken = {p.path for p in inventory.problems if p.path}
    _hold_adds(rows[kind], adapters, broken, project)
    _no_add_in_review(rows[kind])

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
            {
                "id": c,
                "name": NAMES[c],
                "mark": MARKS[c],
                "hidden": c in hidden,
                "note": None if c in found else STATE_WORDS["unread"],
            }
            for c in columns
        ],
        "counts": {
            k: len(matched) if k == kind else len(_chosen(rows[k], k, show_for(k), q))
            for k in KINDS
        },
        "rows": _ordered(shown, ranked=bool(q.strip()) and has_catalog),
        "more": more,
        "attention": len(_narrowed(matched, category, True)),
        "categories": _categories(matched) if has_catalog else [],
        "notes": _read_notes(inventory, project, homes) + _notes(shown, visible),
    }
