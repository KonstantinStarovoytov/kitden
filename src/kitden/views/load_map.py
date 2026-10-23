"""The load map: one row per item, one column per client (portal redesign).

Rows group items by kind and name. A plugin is one row per marketplace ("figma@a" and
"figma@b" are two rows named "figma"); an instruction file per category (a command and an agent
named "review" are two rows); other kinds group by name.
Each cell says what that client does with the item in the chosen project: has it available,
has it but off, routes it through the gateway, or does not know (a client Kitden could not read
says why). A client whose item has the name of another client's but another source needs review
(match.py). A cell kept from the last good read says when it was read. In a project a cell also
says where it applies, and every cell keeps how the client gets the item (its route) for the
hover text. The Claude Desktop Code tab has no column of its own: its extra items show in the
Claude Code column, with the route "from the Desktop app".
"""

from dataclasses import dataclass, field
from datetime import datetime

from kitden.changes.actions import KITDEN_GATEWAY
from kitden.model import (
    ClientStatus,
    Enabled,
    FindingType,
    Item,
    ItemKind,
    Scope,
    _hash,
)
from kitden.views.effective import DESKTOP, effective_view
from kitden.views.findings import base_name, bypass_kind, find_bypasses, find_findings
from kitden.views.match import Copies, is_compared, odd_sources, plugin_copies, plugin_of
from kitden.views.words import CLIENT_UNREAD, NOT_SAME, ORIGIN_WORDS, ROUTE_WORDS, STALE

COLUMNS = ("claude_code", "codex", "cursor")
MARKS = {"claude_code": "CC", "codex": "CX", "cursor": "CU"}
NAMES = {"claude_code": "Claude Code", "codex": "Codex", "cursor": "Cursor"}


@dataclass
class Cell:
    # "on", "off", "gw", "unk", "review" (same name, another source), "none" or "missing"
    # (client not installed)
    state: str
    where: str | None = None  # in a project, ORIGIN_WORDS[origin]; with All projects, None
    origin: str | None = None  # None (all projects), "project" or "override"
    route: str | None = None  # how the client gets it, from ROUTE_WORDS; None when plain
    reason: str | None = None  # why the state, when the page should say it (a client not read)
    stale_at: str | None = None  # the earliest last good read its items were kept from
    items: list[str] = field(default_factory=list)
    count: int = 0


@dataclass
class Row:
    key: str
    kind: ItemKind
    name: str
    source: str | None  # the marketplace of a plugin id, else None
    lookup: str  # the full item name that /api/explain takes
    category: str | None = None  # an instruction file's: "instructions", "command" or "agent"
    cells: dict[str, Cell] = field(default_factory=dict)
    flags: list[dict] = field(default_factory=list)


def category(item: Item) -> str | None:
    """An instruction file's category; None for other kinds."""
    return dict(item.summary).get("category") if item.kind is ItemKind.INSTRUCTIONS else None


def row_key(item: Item) -> str:
    """The row an item belongs to: a plugin per full id, an instruction file per category and
    name, anything else per name."""
    if item.kind is ItemKind.INSTRUCTIONS:
        return _hash(item.kind, category(item) or "", item.name)
    return _hash(item.kind, item.name if item.kind is ItemKind.PLUGIN else base_name(item))


def _route(item: Item, column: str) -> str | None:
    """How the client gets the item, or None when it is the client's own plain entry. An
    account, managed or local entry and a registered gateway get none: the state or Details
    says it."""
    if item.client == DESKTOP:
        return ROUTE_WORDS["desktop"]
    if item.via_gateway == KITDEN_GATEWAY:
        return ROUTE_WORDS["kitden"]
    owner = item.source.owner_client
    if owner in NAMES and owner != column:
        return ROUTE_WORDS["folder"].format(NAMES[owner])
    if item.scope is Scope.PLUGIN:
        return ROUTE_WORDS["plugin"]
    return None


def _deciding(items: list[Item], plugins: dict[str, Item]) -> list[Item]:
    """The items that decide where these apply. A plugin's part (a skill, server or hook in it)
    follows its plugin: `plugins` holds the plugin item that decides in this column, by id."""
    return [plugins.get(plugin_of(i) or "", i) if i.scope is Scope.PLUGIN else i for i in items]


def _origin(deciding: list[Item], overrides: set[str]) -> str | None:
    """Where the items apply: "override" when a project item wins over an all-projects one,
    "project" when one is a project's own, else None (all projects)."""
    if any(i.id in overrides for i in deciding):
        return "override"
    if any(i.project is not None for i in deciding):
        return "project"
    return None


def _deciding_first(item: Item, winners: set[str]) -> tuple[bool, bool]:
    """The definition that decides first (for example a project's "off"), then project items."""
    return (item.id not in winners, item.project is None)


def _own_first(item: Item, column: str) -> tuple[bool, str]:
    return (item.source.owner_client in NAMES and item.source.owner_client != column, item.name)


def _clock(at: str) -> str:
    """The time of a last good read on this Mac's clock: "14:02"."""
    return datetime.fromisoformat(at).astimezone().strftime("%H:%M")


def _cell(
    column: str,
    loaded: list[Item],
    present: list[Item],
    winners: set[str],
    overrides: set[str],
    plugins: dict[str, Item],
    in_project: bool,
) -> Cell:
    """The cell from the items the client loads, or else those it has. In a project it says
    where they apply; the first item gives the route. Items kept from the last good read say
    when, and so do the parts of a plugin whose deciding item was kept."""
    if loaded:
        items = sorted(loaded, key=lambda i: _own_first(i, column))
        if any(i.via_gateway for i in items):
            state = "gw"
        elif any(i.enabled is Enabled.UNKNOWN for i in items):
            state = "unk"
        else:
            state = "on"
    elif present:
        # The definition that decides gives the route.
        items = sorted(present, key=lambda i: _deciding_first(i, winners))
        state = "off"
    else:
        return Cell("none")
    deciding = _deciding(items, plugins)
    origin = _origin(deciding, overrides)
    stale = min((i.stale_at for i in items + deciding if i.stale_at), default=None)
    return Cell(
        state,
        where=ORIGIN_WORDS[origin] if in_project else None,
        origin=origin,
        route=_route(items[0], column),
        reason=STALE.format(_clock(stale)) if stale else None,
        stale_at=stale,
        items=[i.id for i in items],
        count=len(loaded),
    )


def _review(row: Row, items: dict[str, Item], copies: Copies) -> None:
    """Same name, another source: of two or more Available cells, those whose items share no
    command, address, skill files or plugin with the most common ones need review. Only the
    state and the reason change."""
    if row.kind not in (ItemKind.MCP_SERVER, ItemKind.SKILL):
        return
    compared = {
        c: [items[i] for i in row.cells[c].items if i in items and is_compared(items[i])]
        for c in COLUMNS
        if row.cells[c].state == "on"
    }
    for column in odd_sources({c: group for c, group in compared.items() if group}, copies):
        row.cells[column].state = "review"
        row.cells[column].reason = NOT_SAME


# What fixes a duplicate, and the action that does it where the page has one.
DUPLICATE_FIXES = {
    ItemKind.PLUGIN: ("Remove one copy to keep the other.", "plugin.remove"),
    ItemKind.MCP_SERVER: ("Remove one entry to keep the other.", "mcp.remove_direct"),
    ItemKind.SKILL: ("Remove one copy to keep the other.", "skill.remove"),
}


def _warning(text: str, client: str, fix: str, fix_action: str | None) -> dict:
    return {
        "text": text,
        "level": "warning",
        "client": client,
        "fix": fix,
        "fix_action": fix_action,
    }


def _cross_client_fix(client: str, via: str, kind: ItemKind) -> str:
    """One copy is the client's own, the other is loaded from another client's folder."""
    own, other = NAMES.get(client, client), NAMES.get(via, via)
    if client == "cursor" and kind is ItemKind.PLUGIN:
        return (
            f"Two copies load in {own}: its own and {other}'s. To keep one: remove it in Cursor "
            "(Customize → Plugins), or turn off Include Third-Party Plugins in Cursor Settings. "
            f"Turning it off in {other} also turns it off for {other}."
        )
    return (
        f"Two copies load in {own}: its own and {other}'s. Keep one; removing {other}'s copy "
        f"also removes it for {other}."
    )


def _flag(finding, item: Item, gateway_registered: bool, copies: list[Item]) -> dict | None:
    """A short flag for the row; warnings also carry the fix in words and the action."""
    if finding.type is FindingType.DUPLICATE_IN_CLIENT:
        text = f"{NAMES.get(finding.client, finding.client)} loads it twice"
        others = sorted(
            {c.source.owner_client for c in copies if c.source.owner_client != finding.client}
        )
        if others:
            flag = _warning(
                text, finding.client, _cross_client_fix(finding.client, others[0], item.kind), None
            )
            return {**flag, "via": others[0]}
        fix, action = DUPLICATE_FIXES.get(item.kind, ("Remove one copy to keep the other.", None))
        return _warning(text, finding.client, fix, action)
    if finding.type is FindingType.BYPASSES_GATEWAY:
        kind = bypass_kind(item)
        if "plugin" in kind:
            return {"text": "From plugin", "level": "info"}
        if "local server" in kind:
            return {"text": "Local server", "level": "info"}
        # With a gateway, a direct server is an option to move, not a problem.
        return {"text": "Direct connection" if gateway_registered else "Direct", "level": "info"}
    return None


def load_map(inventory, project: str | None, gateway_registered: bool = False) -> list[Row]:
    status = {c.id: c.status for c in inventory.clients}
    views = {c: effective_view(inventory, c, project) for c in COLUMNS}
    desktop = effective_view(inventory, DESKTOP, project) if status.get(DESKTOP) else None
    loaded: dict[str, list[Item]] = {c: list(v.items) for c, v in views.items()}
    if desktop:
        loaded["claude_code"] += [i for i in desktop.items if i.client == DESKTOP]
    winners = {w.id for v in views.values() for w, _, _ in v.shadowed}
    # Project items that win over an all-projects definition of the same name.
    overrides = {
        w.id
        for v in views.values()
        for w, loser, _ in v.shadowed
        if w.project is not None and loser.project is None
    }

    rows: dict[str, Row] = {}

    def row_for(item: Item) -> Row:
        key = row_key(item)
        if key not in rows:
            marketplace = item.name.partition("@")[2] if item.kind is ItemKind.PLUGIN else ""
            rows[key] = Row(
                key=key,
                kind=item.kind,
                name=base_name(item),
                source=marketplace or None,
                lookup=item.name,
                category=category(item),
            )
        return rows[key]

    # Everywhere means user-level items only; a project adds its own items.
    applies = [i for i in inventory.items if i.project is None or i.project == project]
    for item in applies:
        if item.client in COLUMNS or item.client == DESKTOP:
            row_for(item)

    by_row_loaded: dict[tuple[str, str], list[Item]] = {}
    for column, items in loaded.items():
        for item in items:
            by_row_loaded.setdefault((row_for(item).key, column), []).append(item)
    by_row_present: dict[tuple[str, str], list[Item]] = {}
    for item in applies:
        column = "claude_code" if item.client == DESKTOP else item.client
        if column in COLUMNS and (item.project is None or item.project == project):
            by_row_present.setdefault((row_for(item).key, column), []).append(item)

    # The plugin item that decides in each column, by plugin id: its parts follow it.
    plugins: dict[str, dict[str, Item]] = {}
    for (_, column), items in by_row_present.items():
        first = min(items, key=lambda i: _deciding_first(i, winners))
        if first.kind is ItemKind.PLUGIN:
            plugins.setdefault(column, {})[first.name] = first

    items_by_id = {i.id: i for i in inventory.items}
    copies = plugin_copies(inventory)
    for row in rows.values():
        for column in COLUMNS:
            read = status.get(column)
            if read not in (ClientStatus.FOUND, ClientStatus.UNREADABLE):
                row.cells[column] = Cell("missing")
                continue
            cell = _cell(
                column,
                by_row_loaded.get((row.key, column), []),
                by_row_present.get((row.key, column), []),
                winners,
                overrides,
                plugins.get(column, {}),
                project is not None,
            )
            # A client Kitden could not read may have it: Unknown, never "—".
            if read is ClientStatus.UNREADABLE and cell.state == "none":
                cell = Cell("unk", reason=CLIENT_UNREAD.format(NAMES[column]))
            row.cells[column] = cell
        _review(row, items_by_id, copies)
        # Kept from the last good read: the row's first flag says when.
        stale = min((c.stale_at for c in row.cells.values() if c.stale_at), default=None)
        if stale:
            row.flags.append({"text": STALE.format(_clock(stale)), "level": "info"})

    item_rows = {
        item_id: row for row in rows.values() for c in row.cells.values() for item_id in c.items
    }
    for finding in find_findings(inventory, project) + find_bypasses(inventory, project):
        for item_id in finding.items:
            row, item = item_rows.get(item_id), items_by_id.get(item_id)
            copies = [items_by_id[i] for i in finding.items if i in items_by_id]
            flag = _flag(finding, item, gateway_registered, copies) if row and item else None
            if flag and flag not in row.flags:
                row.flags.append(flag)
    order = {ItemKind.MCP_SERVER: 0, ItemKind.PLUGIN: 1, ItemKind.SKILL: 2, ItemKind.HOOK: 3}
    return sorted(
        rows.values(), key=lambda r: (order.get(r.kind, 4), r.name.lower(), r.source or "")
    )


def map_dict(inventory, rows: list[Row]) -> dict:
    status = {c.id: str(c.status) for c in inventory.clients}
    return {
        "columns": [
            {"id": c, "name": NAMES[c], "mark": MARKS[c], "status": status.get(c, "not_found")}
            for c in COLUMNS
        ],
        "rows": [
            {
                "key": r.key,
                "kind": str(r.kind),
                "name": r.name,
                "source": r.source,
                "lookup": r.lookup,
                "category": r.category,
                "cells": {
                    c: {
                        "state": cell.state,
                        "where": cell.where,
                        "origin": cell.origin,
                        "route": cell.route,
                        "reason": cell.reason,
                        "stale_at": cell.stale_at,
                        "items": cell.items,
                        "count": cell.count,
                    }
                    for c, cell in r.cells.items()
                },
                "flags": r.flags,
            }
            for r in rows
        ],
    }
