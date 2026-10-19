"""Turn a requested action into steps for the change engine (write-matrix.md)."""

import ipaddress
import re
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from kitden.changes import json_splice, toml_edit
from kitden.clients.base import PLUGIN_DISABLE, PLUGIN_ENABLE, REMOVE_DIRECT, ClientAdapter
from kitden.gateway_api import gateway_name
from kitden.model import GATEWAY_CLIENT, Gateway, GatewayEdit, Item, Scope, Step

GATEWAY_CONNECT = "gateway.connect"
GATEWAY_MOVE = "gateway.move"
GATEWAY_SWITCH = "gateway.switch"
PLUGIN_INSTALL = "plugin.install"
MARKETPLACE_ADD = "marketplace.add"
SKILL_INSTALL = "skill.install"
CLIENT_WORDS = {"claude_code": "Claude Code", "codex": "Codex", "cursor": "Cursor"}
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


def switch_steps(
    adapters: dict[str, ClientAdapter], items: list[Item], gateway: Gateway, name: str
) -> list[Step]:
    """Move clients from their gateway to another: per client, remove each entry that points to
    another gateway, then add one entry for this one. Both edit one file, in order."""
    if not ENTRY_NAME.fullmatch(name):
        raise ValueError("The entry name may use letters, digits, '-' and '_' only")
    old = [i for i in items if i.via_gateway and i.via_gateway != gateway.id]
    if not old:
        raise ValueError("No client uses another gateway")
    steps = []
    for client in dict.fromkeys(i.client for i in old):
        adapter = adapters.get(client)
        if adapter is None:
            raise ValueError(f"{client} cannot be connected to a gateway")
        mine = [i for i in old if i.client == client]
        if any(i.name == name for i in mine):
            raise ValueError(f"{client} already has an entry named {name}; choose another name")
        # The entry points to a gateway, so it is not "direct"; it is still an entry we may edit.
        steps += [adapter.remove_step(replace(i, via_gateway=None)) for i in mine]
        if not any(i.client == client and i.via_gateway == gateway.id for i in items):
            steps.append(adapter.gateway_step(gateway, name))
    return steps


def install_steps(
    adapters: dict[str, ClientAdapter], offer: dict, clients: list[str]
) -> list[Step]:
    """Install one catalog plugin in the chosen clients (Discover). A client that does not know
    the plugin's marketplace first adds it, from the source another client uses."""
    if not clients:
        raise ValueError("Choose at least one client")
    steps = []
    for client in dict.fromkeys(clients):
        route = offer["routes"].get(client)
        if route is None or client not in adapters:
            raise ValueError(f"{CLIENT_WORDS.get(client, client)} cannot get {offer['name']}")
        if client in offer["installed"]:
            raise ValueError(f"{CLIENT_WORDS.get(client, client)} already has {offer['name']}")
        adapter = adapters[client]
        if route == "add_marketplace":
            source = next(
                (
                    s
                    for other, a in adapters.items()
                    if other != client
                    and isinstance(s := a.marketplace_sources().get(offer["marketplace"]), str)
                ),
                None,
            )
            if source is None:
                raise ValueError(f"The source of {offer['marketplace']} is not known")
            steps.append(adapter.marketplace_add_step(offer["marketplace"], source))
        steps.append(adapter.plugin_install_step(offer["id"]))
    return steps


def skill_steps(
    adapters: dict[str, ClientAdapter], skill: dict, clients: list[str], found: set[str]
) -> list[Step]:
    """Copy one catalog skill so each chosen client loads it once (Discover, phase 2).

    Claude Code reads ~/.claude/skills; Codex and Cursor both read ~/.agents/skills, so one
    copy there serves both; Cursor alone gets ~/.cursor/skills. With Include Third-Party
    Plugins on, Cursor also reads ~/.claude/skills, so a copy for Claude Code reaches it too.
    """
    if not clients:
        raise ValueError("Choose at least one client")
    if not skill["self_contained"]:
        raise ValueError("This skill needs the rest of its plugin. Add the plugin instead.")
    chosen = list(dict.fromkeys(clients))
    for client in chosen:
        words = CLIENT_WORDS.get(client, client)
        if client in skill["installed"]:
            raise ValueError(f"{words} already has {skill['name']}")
        if skill["routes"].get(client) is None or client not in adapters:
            raise ValueError(f"{words} cannot get {skill['name']}")
    cursor = adapters.get("cursor") if "cursor" in found else None
    via_claude = bool(cursor and cursor.reads_other_clients())
    folder = Path(skill["path"])
    steps = []
    if "claude_code" in chosen:
        readers = ["claude_code"] + (["cursor"] if via_claude else [])
        steps.append(adapters["claude_code"].skill_copy_step(folder, readers))
    if "codex" in chosen:
        readers = ["codex"] + (["cursor"] if cursor else [])
        steps.append(adapters["codex"].skill_copy_step(folder, readers))
    elif "cursor" in chosen and not ("claude_code" in chosen and via_claude):
        steps.append(adapters["cursor"].skill_copy_step(folder, ["cursor"]))
    return steps


def marketplace_steps(
    adapters: dict[str, ClientAdapter], found: dict, clients: list[str]
) -> list[Step]:
    """Add one marketplace, read from its link, to the chosen clients (Discover)."""
    if not clients:
        raise ValueError("Choose at least one client")
    steps = []
    for client in dict.fromkeys(clients):
        adapter = adapters.get(client)
        words = CLIENT_WORDS.get(client, client)
        if adapter is None or client == "cursor":
            raise ValueError(f"{words} keeps its marketplaces in the Cursor account; add it there")
        if client == "claude_code" and "claude" not in found["formats"]:
            raise ValueError("Claude Code reads only .claude-plugin/marketplace.json")
        if found["name"] in adapter.marketplace_sources():
            raise ValueError(f"{words} already has a marketplace named {found['name']}")
        steps.append(adapter.marketplace_add_step(found["name"], found["source"]))
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


def _raw_entry(step: Step) -> Any:
    """The entry as written in the client file, secrets included. Never shown."""
    edit = step.edit
    assert edit is not None
    editor = {"json": json_splice, "toml": toml_edit}[edit.fmt]
    try:
        text = Path(edit.path).read_text()
    except OSError:
        return None
    try:
        value = editor.get_value(text, edit.key)
    except json_splice.UnrecognizedFormatError:
        return None
    return value if isinstance(value, dict) else None


def _gateway_server(name: str, entry: dict) -> dict:
    """What MetaMCP needs for one remote server, from a client's entry (research table)."""
    url = entry.get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError(f"{name} is not a remote server; a gateway cannot run it")
    if entry.get("env_http_headers") or entry.get("bearer_token_env_var"):
        raise ValueError(f"{name} uses a variable the gateway cannot read")
    headers = entry.get("headers") or entry.get("http_headers") or {}
    if not isinstance(headers, dict) or any(
        not isinstance(v, str) or "${" in v for v in headers.values()
    ):
        raise ValueError(f"{name} uses a variable the gateway cannot read")
    kind = (
        "SSE"
        if str(entry.get("type", "")).lower() == "sse" or url.endswith("/sse")
        else ("STREAMABLE_HTTP")
    )
    server: dict = {"type": kind, "url": url}
    if headers:
        server["headers"] = headers
    return server


LOCAL_HOSTS = {"localhost", "host.docker.internal"}


def is_local_address(url: str) -> bool:
    """True for an address on this computer or a private network: localhost, 127/8, ::1,
    RFC 1918, link-local and unique-local ranges, and Docker's name for the host."""
    host = (urlsplit(url).hostname or "").lower()
    if host in LOCAL_HOSTS or host.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


def move_steps(
    adapters: dict[str, ClientAdapter], items: list[Item], gateway: Gateway
) -> list[Step]:
    """Move direct entries into the gateway: one gateway step per server name, then the
    remove step of every client entry. The gateway steps come first.

    MetaMCP (feature 006) cleans the name to what it accepts. Obot (checked 2026-10-19,
    v0.26.3) keeps the name, needs an administrator's key, and refuses servers on this
    computer or a private network; Kitden refuses those before the review."""
    if not items:
        raise ValueError("Choose a server to move")
    if not gateway.movable:
        if gateway.kind == "metamcp":
            raise ValueError("Add the sign-in email and password variable to the gateway first")
        if gateway.kind == "obot":
            raise ValueError("Add the name of the Obot key variable to the gateway first")
        raise ValueError("Kitden cannot move servers into this gateway")
    gateway_steps: dict[str, Step] = {}
    file_steps: list[Step] = []
    for item in items:
        remove = remove_steps(adapters, item)[0]
        file_steps.append(remove)
        name = item.name if gateway.kind == "obot" else gateway_name(item.name)
        if name in gateway_steps:
            continue
        entry = _raw_entry(remove)
        if entry is None:
            raise ValueError(f"{item.name} could not be read from its file")
        if gateway.kind == "obot" and is_local_address(str(entry.get("url", ""))):
            raise ValueError(
                f"Obot cannot reach {item.name}: it runs on this computer or a private "
                "network. Keep the direct entry, or set up an Obot tunnel."
            )
        edit = GatewayEdit(
            gateway_id=gateway.id,
            url=gateway.url,
            name=name,
            server=_gateway_server(item.name, entry),
        )
        gateway_steps[name] = Step(
            client=GATEWAY_CLIENT,
            scope=Scope.USER,
            name=name,
            gateway=edit,
            mechanism="gateway_api",
        )
    return [*gateway_steps.values(), *file_steps]
