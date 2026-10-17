"""Gateway page model: which clients reach the gateway, and what still goes around it."""

from agentsetup.model import Gateway, Item, ItemKind
from agentsetup.views.effective import DESKTOP, effective_view
from agentsetup.views.findings import bypass_kind
from agentsetup.views.load_map import COLUMNS


def gateway_dict(gateway: Gateway) -> dict:
    return {
        "id": gateway.id,
        "url": gateway.url,
        "ui_url": gateway.ui_url,
        "auth": str(gateway.auth),
        "key_env_var": gateway.key_env_var,
    }


def loaded_mcp(inventory, project: str | None) -> list[Item]:
    """MCP servers that load in the project, across the three clients and the Desktop Code tab."""
    found = {c.id for c in inventory.clients if str(c.status) == "found"}
    items: list[Item] = []
    for client in [*COLUMNS, DESKTOP]:
        if client in found:
            view = effective_view(inventory, client, project)
            items += [i for i in view.items if i.client == client and i.kind is ItemKind.MCP_SERVER]
    return items


def group_of(item: Item) -> str:
    kind = bypass_kind(item)
    if "plugin" in kind:
        return "plugin"
    if "local server" in kind:
        return "local"
    return "move"


def gateway_view(inventory, gateways: list[Gateway], project: str | None) -> dict:
    connections: dict[str, list[str]] = {c: [] for c in COLUMNS}
    for item in inventory.items:
        column = "claude_code" if item.client == DESKTOP else item.client
        if item.via_gateway and column in connections and item.name not in connections[column]:
            connections[column].append(item.name)
    groups: dict[str, list[dict]] = {"move": [], "local": [], "plugin": []}
    for item in loaded_mcp(inventory, project):
        if item.via_gateway:
            continue
        groups[group_of(item)].append(
            {
                "item": item.id,
                "client": item.client,
                "name": item.name,
                "path": item.source.path,
                "actions": list(item.actions),
            }
        )
    return {
        "gateways": [gateway_dict(g) for g in gateways],
        "connections": {c: sorted(names) for c, names in connections.items()},
        "groups": groups,
    }
