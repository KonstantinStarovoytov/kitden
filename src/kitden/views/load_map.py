"""The load map: one row per item, one column per client (portal redesign).

Rows group items by kind and base name, so the same plugin from two marketplaces is one row.
Each cell says what that client does with the item in the chosen project: loads it, has it but
does not load it, routes it through the gateway, or does not know. The Claude Desktop Code tab
has no column of its own: its extra items show in the Claude Code column as "Desktop app".
"""

from dataclasses import dataclass, field

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

COLUMNS = ("claude_code", "codex", "cursor")
MARKS = {"claude_code": "CC", "codex": "CX", "cursor": "CU"}
NAMES = {"claude_code": "Claude Code", "codex": "Codex", "cursor": "Cursor"}
SCOPE_WORDS = {
    Scope.USER: "everywhere",
    Scope.PROJECT: "this project",
    Scope.LOCAL: "this Mac",
    Scope.PLUGIN: "plugin",
    Scope.ACCOUNT: "account",
    Scope.MANAGED: "managed",
}


@dataclass
class Cell:
    state: str  # "on", "off", "gw", "unk", "none" or "missing" (client not installed)
    where: str | None = None
    items: list[str] = field(default_factory=list)
    count: int = 0


@dataclass
class Row:
    key: str
    kind: ItemKind
    name: str
    cells: dict[str, Cell] = field(default_factory=dict)
    flags: list[dict] = field(default_factory=list)


def _where(item: Item, column: str) -> str:
    if item.client == DESKTOP:
        return "Desktop app"
    owner = item.source.owner_client
    if owner in NAMES and owner != column:
        return f"via {NAMES[owner]}"
    return SCOPE_WORDS.get(item.scope, str(item.scope))


def _own_first(item: Item, column: str) -> tuple[bool, str]:
    return (item.source.owner_client in NAMES and item.source.owner_client != column, item.name)


def _cell(column: str, loaded: list[Item], present: list[Item], winners: set[str]) -> Cell:
    if loaded:
        loaded = sorted(loaded, key=lambda i: _own_first(i, column))
        if any(i.via_gateway for i in loaded):
            state = "gw"
        elif any(i.enabled is Enabled.UNKNOWN for i in loaded):
            state = "unk"
        else:
            state = "on"
        return Cell(state, _where(loaded[0], column), [i.id for i in loaded], len(loaded))
    if present:
        # The definition that decides (for example a project's "off") names the place.
        present = sorted(present, key=lambda i: (i.id not in winners, i.project is None))
        return Cell("off", _where(present[0], column), [i.id for i in present], 0)
    return Cell("none")


# What fixes a duplicate, and the action that does it where the page has one.
DUPLICATE_FIXES = {
    ItemKind.PLUGIN: ("Turn one copy off to keep the other.", "plugin.disable"),
    ItemKind.MCP_SERVER: ("Remove one entry to keep the other.", "mcp.remove_direct"),
}
GATEWAY_FIX = "Add it in the gateway, then remove this direct entry."


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
        if gateway_registered:
            return _warning("Not via gateway", item.client, GATEWAY_FIX, "mcp.remove_direct")
        return {"text": "Direct", "level": "info"}
    return None


def load_map(inventory, project: str | None, gateway_registered: bool = False) -> list[Row]:
    status = {c.id: c.status for c in inventory.clients}
    views = {c: effective_view(inventory, c, project) for c in COLUMNS}
    desktop = effective_view(inventory, DESKTOP, project) if status.get(DESKTOP) else None
    loaded: dict[str, list[Item]] = {c: list(v.items) for c, v in views.items()}
    if desktop:
        loaded["claude_code"] += [i for i in desktop.items if i.client == DESKTOP]
    winners = {w.id for v in views.values() for w, _, _ in v.shadowed}

    rows: dict[str, Row] = {}

    def row_for(item: Item) -> Row:
        key = _hash(item.kind, base_name(item))
        if key not in rows:
            rows[key] = Row(key=key, kind=item.kind, name=base_name(item))
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

    for row in rows.values():
        for column in COLUMNS:
            if status.get(column) is not ClientStatus.FOUND:
                row.cells[column] = Cell("missing")
                continue
            row.cells[column] = _cell(
                column,
                by_row_loaded.get((row.key, column), []),
                by_row_present.get((row.key, column), []),
                winners,
            )

    item_rows = {
        item_id: row for row in rows.values() for c in row.cells.values() for item_id in c.items
    }
    items_by_id = {i.id: i for i in inventory.items}
    for finding in find_findings(inventory, project) + find_bypasses(inventory, project):
        for item_id in finding.items:
            row, item = item_rows.get(item_id), items_by_id.get(item_id)
            copies = [items_by_id[i] for i in finding.items if i in items_by_id]
            flag = _flag(finding, item, gateway_registered, copies) if row and item else None
            if flag and flag not in row.flags:
                row.flags.append(flag)
    order = {ItemKind.MCP_SERVER: 0, ItemKind.PLUGIN: 1, ItemKind.SKILL: 2, ItemKind.HOOK: 3}
    return sorted(rows.values(), key=lambda r: (order.get(r.kind, 4), r.name.lower()))


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
                "cells": {
                    c: {
                        "state": cell.state,
                        "where": cell.where,
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
