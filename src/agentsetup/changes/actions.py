"""Turn a requested action into steps for the change engine (write-matrix.md)."""

import re

from agentsetup.clients.base import PLUGIN_DISABLE, PLUGIN_ENABLE, REMOVE_DIRECT, ClientAdapter
from agentsetup.model import Gateway, Item, Step

GATEWAY_CONNECT = "gateway.connect"
ENTRY_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def connect_steps(
    adapters: dict[str, ClientAdapter], clients: list[str], gateway: Gateway, name: str
) -> list[Step]:
    """One gateway entry per chosen client, in the user scope (FR-024, FR-033)."""
    if not ENTRY_NAME.fullmatch(name):
        raise ValueError("The entry name may use letters, digits, '-' and '_' only")
    if not clients:
        raise ValueError("Choose at least one client")
    steps = []
    for client in dict.fromkeys(clients):
        adapter = adapters.get(client)
        if adapter is None:
            raise ValueError(f"{client} cannot be connected to a gateway")
        steps.append(adapter.gateway_step(gateway, name))
    return steps


def remove_steps(adapters: dict[str, ClientAdapter], item: Item) -> list[Step]:
    """Remove one direct MCP entry (FR-026)."""
    adapter = adapters.get(item.client)
    if adapter is None or REMOVE_DIRECT not in item.actions:
        raise ValueError(f"{item.name} cannot be removed here")
    return [adapter.remove_step(item)]


def plugin_steps(adapters: dict[str, ClientAdapter], item: Item, enable: bool) -> list[Step]:
    """Turn one plugin on or off (FR-027). Cursor and account plugins have no control."""
    action = PLUGIN_ENABLE if enable else PLUGIN_DISABLE
    adapter = adapters.get(item.client)
    if adapter is None or action not in item.actions:
        raise ValueError(f"{item.name} cannot be turned {'on' if enable else 'off'} here")
    return [adapter.plugin_step(item, enable)]
