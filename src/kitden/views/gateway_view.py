"""Gateway page model: which clients reach the gateway, and what still goes around it."""

from pathlib import Path

from kitden.changes.actions import KITDEN_GATEWAY
from kitden.clients.base import REMOVE_DIRECT
from kitden.clients.entries import IN_PROJECT_FILES
from kitden.model import Gateway, Item, ItemKind, Scope
from kitden.views.effective import DESKTOP, effective_view
from kitden.views.explain import summary_line
from kitden.views.findings import bypass_kind
from kitden.views.load_map import COLUMNS
from kitden.views.setup_server import is_own_entry
from kitden.views.words import KEPT_UNREAD

# The gateway inside `kitden mcp`. It runs on this Mac, so it also takes local servers.
KITDEN = {
    "id": KITDEN_GATEWAY,
    "kind": "kitden",
    "name": "Kitden gateway",
    "where": "On this Mac",
    "movable": True,
}


def gateway_dict(gateway: Gateway) -> dict:
    return {
        "id": gateway.id,
        "url": gateway.url,
        "ui_url": gateway.ui_url,
        "auth": str(gateway.auth),
        "key_env_var": gateway.key_env_var,
        "login_email": gateway.login_email,
        "login_password_env_var": gateway.login_password_env_var,
        "kind": gateway.kind,
        "managed": gateway.managed,
        "movable": gateway.movable,
    }


def loaded_mcp(inventory, project: str | None) -> tuple[list[Item], set[str]]:
    """MCP servers that load in the project, across the three clients and the Desktop Code tab,
    and the ids of those that are the project's own definition and replace an all-projects one.

    Kitden's own read-only server is left out: it is not a tool server to route anywhere.
    """
    found = {c.id for c in inventory.clients if str(c.status) == "found"}
    items: list[Item] = []
    overrides: set[str] = set()
    for client in [*COLUMNS, DESKTOP]:
        if client in found:
            view = effective_view(inventory, client, project)
            items += [
                i
                for i in view.items
                if i.client == client and i.kind is ItemKind.MCP_SERVER and not is_own_entry(i)
            ]
            overrides |= {
                w.id for w, lo, _ in view.shadowed if w.project is not None and lo.project is None
            }
    return items, overrides


def group_of(item: Item) -> str:
    kind = bypass_kind(item)
    if "plugin" in kind:
        return "plugin"
    if "local server" in kind:
        return "local"
    return "move"


def stays(item: Item, group: str) -> str | None:
    """Why a move into a gateway would refuse this entry, as far as Kitden knows without the
    network; None when it would not."""
    if group == "plugin":
        return f"{item.name} comes with a plugin; it stays with the plugin."
    if item.scope is Scope.PROJECT:
        return IN_PROJECT_FILES.format(item.name)
    if item.stays_direct:
        return item.stays_direct
    if item.stale_at:
        return KEPT_UNREAD.format(Path(item.source.path or "").name)
    return None


def gateway_view(
    inventory,
    gateways: list[Gateway],
    project: str | None,
    kitden: list[dict] | None = None,
    problem: str | None = None,
) -> dict:
    """With `kitden` (the servers it holds; see `held_servers`), the Kitden gateway comes first
    and local servers can move too. `problem` says why its settings could not be read.

    Each outside row has the client columns that load it (the Desktop Code tab counts as
    Claude Code), whether one of its entries is the project's own and replaces an all-projects
    one (`override`), and the first reason a move would refuse it (`stays`), or None."""
    ids = ([KITDEN_GATEWAY] if kitden is not None else []) + [g.id for g in gateways]
    # Per gateway and client: the servers that load in this scope and go through that gateway.
    connections: dict[str, dict[str, list[str]]] = {g: {c: [] for c in COLUMNS} for g in ids}
    # One row per server name, with the clients that have it and the entries that can go.
    groups: dict[str, dict[str, dict]] = {"move": {}, "local": {}, "plugin": {}}
    movable = {
        "move": kitden is not None or any(g.movable for g in gateways),
        "local": kitden is not None,
        "plugin": False,
    }
    loaded, overrides = loaded_mcp(inventory, project)
    for item in loaded:
        if item.via_gateway:
            column = "claude_code" if item.client == DESKTOP else item.client
            names = connections.get(item.via_gateway, {}).get(column)
            if names is not None and item.name not in names:
                names.append(item.name)
            continue
        group = group_of(item)
        row = groups[group].setdefault(
            item.name,
            {
                "name": item.name,
                "summary": summary_line(item),
                "clients": [],
                "items": [],
                "movable": movable[group],
                "override": False,
                "stays": None,
            },
        )
        if item.client not in row["clients"]:
            row["clients"].append(item.client)
        if REMOVE_DIRECT in item.actions:
            row["items"].append(item.id)
        row["override"] = row["override"] or item.id in overrides
        row["stays"] = row["stays"] or stays(item, group)
    for rows in groups.values():
        for row in rows.values():
            loads = {"claude_code" if c == DESKTOP else c for c in row["clients"]}
            row["columns"] = [c for c in COLUMNS if c in loads]
    return {
        "gateways": (
            [{**KITDEN, "servers": kitden, **({"problem": problem} if problem else {})}]
            if kitden is not None
            else []
        )
        + [gateway_dict(g) for g in gateways],
        "connections": {
            g: {c: sorted(names) for c, names in columns.items()}
            for g, columns in connections.items()
        },
        "used": sorted(g for g, columns in connections.items() if any(columns.values())),
        "groups": {
            g: sorted(rows.values(), key=lambda r: r["name"].lower()) for g, rows in groups.items()
        },
    }
