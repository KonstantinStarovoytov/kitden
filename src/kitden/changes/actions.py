"""Turn a requested action into steps for the change engine (write-matrix.md)."""

import re
from pathlib import Path

from kitden.clients.base import PLUGIN_DISABLE, PLUGIN_ENABLE, REMOVE_DIRECT, ClientAdapter
from kitden.model import Gateway, Item, Step

GATEWAY_CONNECT = "gateway.connect"
SETUP_SERVER_UPDATE = "setup_server.update"
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


def setup_server_steps(
    adapters: dict[str, ClientAdapter], clients: list[str], command: str
) -> list[Step]:
    """Add the read-only setup server to the chosen clients (FR-032).

    GUI clients may not see the shell PATH, so the entry uses an absolute path (research R9).
    """
    if not Path(command).is_absolute():
        raise ValueError("The setup server needs the absolute path of the kitden command")
    if not clients:
        raise ValueError("Choose at least one client")
    steps = []
    for client in dict.fromkeys(clients):
        adapter = adapters.get(client)
        if adapter is None:
            raise ValueError(f"The setup server cannot be added to {client}")
        steps.append(adapter.setup_server_step(command, ["mcp"]))
    return steps


def update_steps(
    adapters: dict[str, ClientAdapter],
    items: list[Item],
    added_clients: set[str],
    command: str | None,
) -> list[Step]:
    """Replace old `agentsetup` entries with `kitden` (feature 002, FR-006).

    Per client: remove the old entry, then add `kitden` unless that client already has it. Both
    steps edit one settings file; the engine applies them in order.
    """
    if not items:
        raise ValueError("Choose an old Kitden entry.")
    steps = []
    for item in items:
        adapter = adapters.get(item.client)
        if adapter is None:
            raise ValueError("Choose an old Kitden entry.")
        steps.append(adapter.remove_step(item))
        if item.client not in added_clients:
            if command is None or not Path(command).is_absolute():
                raise ValueError("The setup server needs the absolute path of the kitden command")
            steps.append(adapter.setup_server_step(command, ["mcp"]))
    return steps
