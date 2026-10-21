"""Gateway page model: which clients reach the gateway, and what still goes around it."""

from kitden.changes.actions import KITDEN_GATEWAY
from kitden.clients.base import REMOVE_DIRECT
from kitden.model import Gateway, Item, ItemKind
from kitden.views.effective import DESKTOP, effective_view
from kitden.views.explain import summary_line
from kitden.views.findings import bypass_kind
from kitden.views.load_map import COLUMNS
from kitden.views.setup_server import is_own_entry

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


def loaded_mcp(inventory, project: str | None) -> list[Item]:
    """MCP servers that load in the project, across the three clients and the Desktop Code tab.

    Kitden's own read-only server is left out: it is not a tool server to route anywhere.
    """
    found = {c.id for c in inventory.clients if str(c.status) == "found"}
    items: list[Item] = []
    for client in [*COLUMNS, DESKTOP]:
        if client in found:
            view = effective_view(inventory, client, project)
            items += [
                i
                for i in view.items
                if i.client == client and i.kind is ItemKind.MCP_SERVER and not is_own_entry(i)
            ]
    return items


def group_of(item: Item) -> str:
    kind = bypass_kind(item)
    if "plugin" in kind:
        return "plugin"
    if "local server" in kind:
        return "local"
    return "move"


def gateway_view(
    inventory, gateways: list[Gateway], project: str | None, kitden: bool = False
) -> dict:
    """With `kitden`, the Kitden gateway comes first and local servers can move too."""
    ids = ([KITDEN_GATEWAY] if kitden else []) + [g.id for g in gateways]
    # Per gateway and client: the servers that load in this scope and go through that gateway.
    connections: dict[str, dict[str, list[str]]] = {g: {c: [] for c in COLUMNS} for g in ids}
    # One row per server name, with the clients that have it and the entries that can go.
    groups: dict[str, dict[str, dict]] = {"move": {}, "local": {}, "plugin": {}}
    movable = {
        "move": kitden or any(g.movable for g in gateways),
        "local": kitden,
        "plugin": False,
    }
    for item in loaded_mcp(inventory, project):
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
            },
        )
        if item.client not in row["clients"]:
            row["clients"].append(item.client)
        if REMOVE_DIRECT in item.actions:
            row["items"].append(item.id)
    return {
        "gateways": ([dict(KITDEN)] if kitden else []) + [gateway_dict(g) for g in gateways],
        "connections": {
            g: {c: sorted(names) for c, names in columns.items()}
            for g, columns in connections.items()
        },
        "used": sorted(g for g, columns in connections.items() if any(columns.values())),
        "groups": {
            g: sorted(rows.values(), key=lambda r: r["name"].lower()) for g, rows in groups.items()
        },
    }
