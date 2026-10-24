"""The read-only "show my setup" server in each client (feature 002, FR-005 to FR-007;
feature 003, FR-014).

An old entry is one the working version (named `agentsetup`) added: a user-level MCP entry named
`agentsetup` that runs the old command with the `mcp` argument. Entries with that name that run
another program are someone else's and are left alone. A plugin entry is the same server as
provided by the kitden plugin (feature 003): the page shows it and never adds a second one.
"""

import json
from pathlib import Path

from kitden.clients.base import SETUP_NAME, ClientAdapter
from kitden.model import Enabled, Item, ItemKind, Scope, Step

CLIENTS = ("claude_code", "codex", "cursor")
CLIENT_WORDS = {"claude_code": "Claude Code", "codex": "Codex", "cursor": "Cursor"}
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
    """The client has a `kitden` entry (its own or a plugin's) and it is not turned off."""
    return entry["state"] in ("added", "plugin") and entry["enabled"] is not False


def setup_server_state(inventory) -> list[dict]:
    """Per client: `added`, `old`, `plugin`, `missing` or `not_installed`, and the old entry to
    update. A user-level entry wins over a plugin one, and a plugin one over an old entry, which is
    then only removed (the plugin already provides the server)."""
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
        plugin = next((i for i in inventory.items if _plugin_entry(i, client)), None)
        old = next((i for i in inventory.items if i.client == client and is_old_entry(i)), None)
        state = "added" if mine else "plugin" if plugin else "old" if old else "missing"
        exists = Path(dict(old.summary)["command"]).exists() if old else None
        present = mine or plugin
        states.append(
            {
                "client": client,
                "state": state,
                "item": old.id if old else None,
                "command_exists": exists,
                "enabled": None if present is None else present.enabled is not Enabled.OFF,
            }
        )
    return states
