"""Gateway page model: which clients reach the gateway, and what still goes around it."""

from kitden.clients.base import REMOVE_DIRECT
from kitden.model import Gateway, Item, ItemKind
from kitden.views.effective import DESKTOP, effective_view
from kitden.views.explain import summary_line
from kitden.views.findings import bypass_kind
from kitden.views.load_map import COLUMNS
from kitden.views.setup_server import is_own_entry


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


def gateway_view(inventory, gateways: list[Gateway], project: str | None) -> dict:
    # Per gateway and client: the servers that load in this scope and go through that gateway.
    connections: dict[str, dict[str, list[str]]] = {
        g.id: {c: [] for c in COLUMNS} for g in gateways
    }
    # One row per server name, with the clients that have it and the entries that can go.
    groups: dict[str, dict[str, dict]] = {"move": {}, "local": {}, "plugin": {}}
    for item in loaded_mcp(inventory, project):
        if item.via_gateway:
            column = "claude_code" if item.client == DESKTOP else item.client
            names = connections.get(item.via_gateway, {}).get(column)
            if names is not None and item.name not in names:
                names.append(item.name)
            continue
        rows = groups[group_of(item)]
        row = rows.setdefault(
            item.name,
            {"name": item.name, "summary": summary_line(item), "clients": [], "items": []},
        )
        if item.client not in row["clients"]:
            row["clients"].append(item.client)
        if REMOVE_DIRECT in item.actions:
            row["items"].append(item.id)
    return {
        "gateways": [gateway_dict(g) for g in gateways],
        "connections": {
            g: {c: sorted(names) for c, names in columns.items()}
            for g, columns in connections.items()
        },
        "used": sorted(g for g, columns in connections.items() if any(columns.values())),
        "groups": {
            g: sorted(rows.values(), key=lambda r: r["name"].lower()) for g, rows in groups.items()
        },
    }
