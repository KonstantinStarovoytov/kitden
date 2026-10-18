"""The read-only "show my setup" server in each client (feature 002, FR-005 to FR-007).

An old entry is one the working version (named `agentsetup`) added: a user-level MCP entry named
`agentsetup` that runs the old command with the `mcp` argument. Entries with that name that run
another program are someone else's and are left alone.
"""

import json
from pathlib import Path

from kitden.clients.base import SETUP_NAME
from kitden.model import Enabled, Item, ItemKind, Scope

CLIENTS = ("claude_code", "codex", "cursor")
OLD_NAME = "agentsetup"


def _user_entry(item: Item, client: str, name: str) -> bool:
    return (
        item.client == client
        and item.kind is ItemKind.MCP_SERVER
        and item.scope is Scope.USER
        and item.name == name
    )


def is_own_entry(item: Item) -> bool:
    """Kitden's own read-only server: not a tool server, so not one to route or count."""
    return _user_entry(item, item.client, SETUP_NAME)


def is_old_entry(item: Item) -> bool:
    if item.client not in CLIENTS or not _user_entry(item, item.client, OLD_NAME):
        return False
    summary = dict(item.summary)
    try:
        args = json.loads(summary.get("args", "null"))
    except ValueError:
        return False
    return summary.get("command", "").endswith(f"/{OLD_NAME}") and args == ["mcp"]


def setup_server_state(inventory) -> list[dict]:
    """Per client: `added`, `old`, `missing` or `not_installed`, and the old entry to update."""
    found = {c.id for c in inventory.clients if str(c.status) == "found"}
    states = []
    for client in CLIENTS:
        if client not in found:
            states.append(
                {
                    "client": client,
                    "state": "not_installed",
                    "item": None,
                    "command_exists": None,
                    "enabled": None,
                }
            )
            continue
        mine = next((i for i in inventory.items if _user_entry(i, client, SETUP_NAME)), None)
        added = mine is not None
        old = next((i for i in inventory.items if i.client == client and is_old_entry(i)), None)
        state = "added" if added else "old" if old else "missing"
        exists = Path(dict(old.summary)["command"]).exists() if old else None
        states.append(
            {
                "client": client,
                "state": state,
                "item": old.id if old else None,
                "command_exists": exists,
                "enabled": None if mine is None else mine.enabled is not Enabled.OFF,
            }
        )
    return states
