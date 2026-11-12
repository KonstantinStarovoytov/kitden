"""The read-only "show my setup" server in each client (feature 002, FR-005 to FR-007;
feature 003, FR-014).

An old entry is one the working version (named `agentsetup`) added: a user-level MCP entry named
`agentsetup` that runs the old command with the `mcp` argument. Entries with that name that run
another program are someone else's and are left alone. The kitden plugin starts its own server
with `--read-only`, which offers no moved server: it is not the client's link to the gateway, so
it does not count here.
"""

import json
from pathlib import Path

from kitden.clients.base import SETUP_NAME, ClientAdapter, found_clients
from kitden.model import CLIENT_WORDS, CLIENTS, Enabled, Item, ItemKind, Scope, Step

OLD_NAME = "agentsetup"


def _user_entry(item: Item, client: str, name: str) -> bool:
    return (
        item.client == client
        and item.kind is ItemKind.MCP_SERVER
        and item.scope is Scope.USER
        and item.name == name
    )


def _plugin_entry(item: Item, client: str) -> bool:
    return (
        item.client == client
        and item.kind is ItemKind.MCP_SERVER
        and item.scope is Scope.PLUGIN
        and item.name == SETUP_NAME
    )


def is_own_entry(item: Item) -> bool:
    """Kitden's own read-only server, added by the page or provided by the kitden plugin: not a
    tool server, so not one to route or count."""
    return _user_entry(item, item.client, SETUP_NAME) or _plugin_entry(item, item.client)


def is_old_entry(item: Item) -> bool:
    if item.client not in CLIENTS or not _user_entry(item, item.client, OLD_NAME):
        return False
    summary = dict(item.summary)
    try:
        args = json.loads(summary.get("args", "null"))
    except ValueError:
        return False
    return summary.get("command", "").endswith(f"/{OLD_NAME}") and args == ["mcp"]


def gone(command: str) -> bool:
    """An absolute program path that is no longer there."""
    path = Path(command)
    return path.is_absolute() and not path.exists()


_gone = gone  # tests make their made-up paths count as present


def is_moved_entry(item: Item) -> bool:
    """The client's own `kitden` entry runs a program that is gone: Kitden moved (uv to
    Homebrew, or back) or was removed. Or it runs one versioned Homebrew folder
    (`Cellar/kitden/<version>`), which an upgrade can keep: the stable launcher is the opt
    link. Update points it at the Kitden that runs now."""
    command = dict(item.summary).get("command", "")
    return _user_entry(item, item.client, SETUP_NAME) and (
        _gone(command) or "/Cellar/kitden/" in command
    )


# The clients whose docs name the key that turns a user entry off, as Kitden reads it, and the
# key. Checked 2026-10-24:
# - Codex: `enabled = false` in the entry's `[mcp_servers.<name>]` table turns it off without
#   removing it (learn.chatgpt.com/docs/extend/mcp, /docs/config-file/config-reference);
#   codex.py reads it.
# - Claude Code: the /mcp panel keeps its choice per project in `disabledMcpServers` of
#   ~/.claude.json; the docs show no format to write by hand (code.claude.com/docs/en/mcp).
# - Cursor: only a toggle in Customize; mcp.json has no such key (cursor.com/docs/context/mcp).
ENABLE_KEYS = {"codex": "enabled"}


def enable_steps(adapters: dict[str, ClientAdapter], client: str) -> list[Step]:
    """Turn the client's `kitden` user entry back on, only where its docs name the key (see
    ENABLE_KEYS). The caller checks that the entry is there and off. Every other client turns
    it on in its own settings."""
    adapter = adapters.get(client)
    if client not in ENABLE_KEYS or adapter is None:
        name = CLIENT_WORDS.get(client, client)
        raise ValueError(f"Turn it on in {name}'s own MCP settings.")
    return [adapter.setup_entry_step(ENABLE_KEYS[client], True)]


def kitden_on(entry: dict) -> bool:
    """The client has its own `kitden` entry and it is not turned off."""
    return entry["state"] == "added" and entry["enabled"] is not False


def with_entry(inventory) -> set[str]:
    """The clients with their own `kitden` entry: added, or moved (Update fixes its path). A
    change that adds the entry leaves these alone."""
    return {
        s["client"] for s in setup_server_state(inventory) if s["state"] == "added" or s["moved"]
    }


def setup_server_state(inventory) -> list[dict]:
    """Per client: `added`, `old`, `missing` or `not_installed`, and the old entry to update.
    `moved`: the old entry is the client's own `kitden` entry, whose program is gone."""
    found = found_clients(inventory)
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
                    "moved": False,
                }
            )
            continue
        mine = next((i for i in inventory.items if _user_entry(i, client, SETUP_NAME)), None)
        old = next((i for i in inventory.items if i.client == client and is_old_entry(i)), None)
        moved = mine is not None and is_moved_entry(mine)
        if moved:
            old = mine
        state = "old" if moved else "added" if mine else "old" if old else "missing"
        exists = False if moved else Path(dict(old.summary)["command"]).exists() if old else None
        states.append(
            {
                "client": client,
                "state": state,
                "item": old.id if old else None,
                "command_exists": exists,
                "enabled": None if mine is None else mine.enabled is not Enabled.OFF,
                "moved": moved,
            }
        )
    return states
