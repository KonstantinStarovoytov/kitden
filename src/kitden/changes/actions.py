"""Turn a requested action into steps for the change engine (write-matrix.md)."""

import http.client
import ipaddress
import json
import os
import re
import socket
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from kitden.changes import json_splice
from kitden.changes.engine import EDITORS
from kitden.changes.server_entry import is_number, translate_entry
from kitden.clients.base import (
    PLUGIN_DISABLE,
    PLUGIN_ENABLE,
    PLUGIN_REMOVE,
    REMOVE_DIRECT,
    SETUP_NAME,
    SKILL_REMOVE,
    ClientAdapter,
)
from kitden.clients.claude_code import rule_file
from kitden.clients.entries import IN_PROJECT_FILES, entry_refusal, gateway_entry
from kitden.gateway_api import gateway_name
from kitden.local_gateway.keychain import (
    SECRET_FIELDS,
    KeychainError,
    Runner,
    resolve_entry,
    run_security,
)
from kitden.local_gateway.settings import (
    START_TIME,
    load_settings,
    load_tools,
    rule_step,
    settings_step,
    strict_step,
)
from kitden.model import (
    CLIENT_WORDS,
    GATEWAY_CLIENT,
    Gateway,
    GatewayEdit,
    Item,
    ItemKind,
    KeychainItem,
    Scope,
    Step,
)
from kitden.redact import redact
from kitden.sign_in import GONE, SignIn
from kitden.sign_in import KEY as SIGN_IN_KEY
from kitden.views.catalog import known_refusal, market_entry
from kitden.views.setup_server import is_own_entry
from kitden.views.words import (
    CHANGE_UNREAD,
    CODEX_NO_PROJECT,
    CURSOR_NO_SKILL_SWITCH,
    NO_SKILL_MERGE,
    PLUGIN_ALL_PROJECTS,
    PLUGIN_SKILL,
    PROJECT_SKILL_ALL,
)

if TYPE_CHECKING:
    from kitden.views.inventory import Inventory

GATEWAY_CONNECT = "gateway.connect"
GATEWAY_MOVE = "gateway.move"
GATEWAY_SWITCH = "gateway.switch"
PLUGIN_INSTALL = "plugin.install"
MARKETPLACE_ADD = "marketplace.add"
SKILL_INSTALL = "skill.install"
PLUGIN_SKILLS = "plugin.skills"
SETUP_SERVER_UPDATE = "setup_server.update"
# Turns a client's `kitden` entry back on, where its docs name the switch (views/setup_server.py).
SETUP_SERVER_ENABLE = "setup_server.enable"
# Takes the `kitden` entry out of a client: the client is then not connected to Kitden.
CLIENT_DISCONNECT = "client.disconnect"
KITDEN_GATEWAY = "kitden"  # the gateway inside `kitden mcp`, on this Mac
GATEWAY_RULE = "gateway.rule"  # one switch of the Kitden gateway: a server or a tool on or off
GATEWAY_STRICT = "gateway.strict"  # a held server's strict mode on or off: new tools wait
GATEWAY_RULES = "gateway.rules"  # several tools of one server on or off in one review
GATEWAY_REMOVE = "gateway.remove"  # a held server and its rules leave the Kitden gateway
GATEWAY_PUT_BACK = "gateway.put_back"  # a held server's entry written into a client
GATEWAY_MOVE_OUT = "gateway.move_out"  # a held server put back in one client and removed
GATEWAY_KEYCHAIN = "gateway.keychain"  # a held server's plain secrets moved to the Keychain
GATEWAY_ADD = "gateway.add"  # a server a marketplace plugin offers, added to the Kitden gateway
GATEWAY_SIGN_IN = "gateway.sign_in"  # a held server signed in again: only its Keychain item
GATEWAY_ACCESS = "gateway.access"  # one secret of a held server replaced or removed, or sign out
MCP_ADD = "mcp.add"  # a direct server one client has, added to other clients
PROJECT_ALIGN = "project.align"  # what one client loads in a project, added to the others
SKILL_RULE = "skill.rule"  # a skill, or a plugin in one project, turned off by a settings rule

NEEDS_COMMAND = "The setup server needs the absolute path of the kitden command"
ENTRY_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
LOCAL_HOSTS = {"localhost", "host.docker.internal"}
# Shared address space (RFC 6598): carrier NAT and Tailscale; Python does not call it private.
SHARED_RANGE = ipaddress.ip_network("100.64.0.0/10")
# Codex waits 10 s for a server to start and 60 s for a tool call (checked 2026-10-21). The
# Kitden gateway may take up to 20 s to list a server and 300 s for one call.
CODEX_TIMEOUTS = {"startup_timeout_sec": 30, "tool_timeout_sec": 300}
SIGN_IN_SECONDS = 5
MCP_VERSION = "2025-06-18"  # a protocol version every MCP server knows (checked 2026-10-21)
# Where a server that signs in through the browser keeps its sign-in metadata (RFC 9728).
SIGN_IN_METADATA = "/.well-known/oauth-protected-resource"
# The one field a remote server that needs a plain token gets: the token alone, sent as
# `Authorization: Bearer`.
TOKEN_FIELD = {
    "field": "headers",
    "name": "Authorization",
    "label": "Access token",
    "prefix": "Bearer ",
}
SIGN_IN_LATER = "{name} does not let Kitden sign in yet. It may take an API key; see its docs."


def _check_entry_name(name: str) -> None:
    if not ENTRY_NAME.fullmatch(name):
        raise ValueError("The entry name may use letters, digits, '-' and '_' only")


def connect_steps(
    adapters: dict[str, ClientAdapter], clients: list[str], gateway: Gateway, name: str
) -> list[Step]:
    """One gateway entry per chosen client, in the user scope (FR-024, FR-033)."""
    _check_entry_name(name)
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
    _check_entry_name(name)
    # The Kitden gateway's servers live in its own settings, not in a client entry; they stay.
    old = [i for i in items if i.via_gateway not in (None, gateway.id, KITDEN_GATEWAY)]
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
    adapters: dict[str, ClientAdapter],
    offer: dict,
    clients: list[str],
    project: str | None = None,
) -> list[Step]:
    """Install one catalog plugin in the chosen clients, for the user or into `project`. A
    client that does not know the plugin's marketplace first adds it (for the user), from the
    source another client uses."""
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
        steps.append(adapter.plugin_install_step(offer["id"], project))
    return steps


def folder_readers(client: str, adapters: dict[str, ClientAdapter], found: set[str]) -> list[str]:
    """The clients that read the skills folder of `client`, in the user's home or a project.

    Claude Code reads .claude/skills; Codex and Cursor both read .agents/skills; Cursor alone
    reads .cursor/skills. With Include Third-Party Plugins on, Cursor also reads .claude/skills.
    """
    cursor = adapters.get("cursor") if "cursor" in found else None
    if client == "claude_code":
        return ["claude_code"] + (["cursor"] if cursor and cursor.reads_other_clients() else [])
    if client == "codex":
        return ["codex"] + (["cursor"] if cursor else [])
    return [client]


def skill_steps(
    adapters: dict[str, ClientAdapter],
    skill: dict,
    clients: list[str],
    found: set[str],
    project: str | None = None,
) -> list[Step]:
    """Copy one catalog skill so each chosen client loads it once, for the user or into the
    same folders inside `project`.

    One copy in .agents/skills serves Codex and Cursor; a copy for Claude Code reaches Cursor
    too when Cursor reads Claude Code's folder (folder_readers).
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
    folder = Path(skill["path"])
    steps = []
    for client in ("claude_code", "codex"):
        if client in chosen:
            readers = folder_readers(client, adapters, found)
            steps.append(adapters[client].skill_copy_step(folder, readers, project))
    if "cursor" in chosen and not any("cursor" in s.copy.readers for s in steps if s.copy):
        steps.append(adapters["cursor"].skill_copy_step(folder, ["cursor"], project))
    return steps


def _left_out_why(skill: dict, client: str) -> str | None:
    """Why an "Add skills" copy skips this skill for the client; None when it is copied."""
    if client in skill["installed"]:
        return f"{CLIENT_WORDS.get(client, client)} already has it"
    if not skill["self_contained"]:
        return "needs the rest of the plugin"
    return None


def plugin_skill_steps(
    adapters: dict[str, ClientAdapter],
    plugin_id: str,
    skills: list[dict],
    client: str,
    found: set[str],
) -> list[Step]:
    """Copy the skills of one plugin that work alone into one client that cannot install the
    plugin. A skill the client already has is skipped. Each copy is the one skill_steps makes
    for a single skill, so the folder choice is the same."""
    steps = []
    for skill in skills:
        copied = (
            skill["plugin"] == plugin_id
            and client in skill["routes"]
            and _left_out_why(skill, client) is None
        )
        if copied:
            steps += skill_steps(adapters, skill, [client], found)
    if not steps:
        words = CLIENT_WORDS.get(client, client)
        raise ValueError(f"{words} has every skill in {plugin_id.split('@')[0]} it can use")
    return steps


def plugin_skills_left_out(plugin_id: str, skills: list[dict], client: str) -> list[dict]:
    """The skills of the plugin that "Add skills" does not copy, each with the reason."""
    out = []
    for skill in skills:
        why = _left_out_why(skill, client) if skill["plugin"] == plugin_id else None
        if why:
            out.append({"name": skill["name"], "why": why})
    return out


def marketplace_steps(
    adapters: dict[str, ClientAdapter], found: dict, clients: list[str]
) -> list[Step]:
    """Add one marketplace, read from its link, to the chosen clients."""
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


def _adapter_for(
    adapters: dict[str, ClientAdapter], item: Item, action: str, why: str = "removed"
) -> ClientAdapter:
    """The item's client, when the item offers `action`; else the words that it cannot be."""
    adapter = adapters.get(item.client)
    if adapter is None or action not in item.actions:
        raise ValueError(f"{item.name} cannot be {why} here")
    return adapter


def remove_steps(adapters: dict[str, ClientAdapter], item: Item) -> list[Step]:
    """Remove one direct MCP entry (FR-026)."""
    return [_adapter_for(adapters, item, REMOVE_DIRECT).remove_step(item)]


def remove_plugin_steps(adapters: dict[str, ClientAdapter], item: Item) -> list[Step]:
    """Remove one installed plugin with its client's own command (spec 3.1)."""
    return [_adapter_for(adapters, item, PLUGIN_REMOVE).plugin_remove_step(item)]


def skill_remove_steps(
    adapters: dict[str, ClientAdapter], item: Item, readers: list[str], keeps: list[str]
) -> list[Step]:
    """Remove one skill folder from its client; Undo copies it back (spec 3.2)."""
    adapter = _adapter_for(adapters, item, SKILL_REMOVE)
    return [adapter.skill_remove_step(item, readers, keeps)]


def plugin_steps(adapters: dict[str, ClientAdapter], item: Item, enable: bool) -> list[Step]:
    """Turn one plugin on or off (FR-027). Cursor and account plugins have no control."""
    action, why = (PLUGIN_ENABLE, "turned on") if enable else (PLUGIN_DISABLE, "turned off")
    return [_adapter_for(adapters, item, action, why).plugin_step(item, enable)]


def setup_server_steps(
    adapters: dict[str, ClientAdapter], clients: list[str], command: str
) -> list[Step]:
    """Add the read-only setup server to the chosen clients (FR-032).

    GUI clients may not see the shell PATH, so the entry uses an absolute path (research R9).
    """
    if not Path(command).is_absolute():
        raise ValueError(NEEDS_COMMAND)
    if not clients:
        raise ValueError("Choose at least one client")
    steps = []
    for client in dict.fromkeys(clients):
        adapter = adapters.get(client)
        if adapter is None:
            raise ValueError(f"The setup server cannot be added to {client}")
        steps.append(adapter.setup_server_step(command, ["mcp"]))
    return steps


def disconnect_steps(
    adapters: dict[str, ClientAdapter], inventory: "Inventory", clients: list[str]
) -> list[Step]:
    """Remove the user-scope `kitden` entry from each chosen client, with that client's own
    remove step. An entry a plugin provides stays: the plugin is how to turn it off."""
    if not clients:
        raise ValueError("Choose at least one client")
    steps = []
    for client in dict.fromkeys(clients):
        words = CLIENT_WORDS.get(client, client)
        entries = [i for i in inventory.items if i.client == client and is_own_entry(i)]
        mine = next((i for i in entries if i.scope is Scope.USER), None)
        adapter = adapters.get(client)
        if mine is None or adapter is None:
            if entries:
                raise ValueError(
                    f"{words} gets Kitden from a plugin. Turn the plugin off to disconnect it."
                )
            raise ValueError(f"{words} is not connected to Kitden.")
        steps.append(adapter.remove_step(mine))
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
                raise ValueError(NEEDS_COMMAND)
            steps.append(adapter.setup_server_step(command, ["mcp"]))
    return steps


def _raw_entry(step: Step) -> Any:
    """The entry as written in the client file, secrets included. Never shown."""
    edit = step.edit
    assert edit is not None
    try:
        text = Path(edit.path).read_text()
    except OSError:
        return None
    try:
        value = EDITORS[edit.fmt].get_value(text, edit.key)
    except json_splice.UnrecognizedFormatError:
        return None
    return value if isinstance(value, dict) else None


def _gateway_server(name: str, entry: dict) -> dict:
    """What a gateway needs for one remote server, from a client's entry (research table)."""
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
        else "STREAMABLE_HTTP"
    )
    server: dict = {"type": kind, "url": url}
    if headers:
        server["headers"] = headers
    return server


def is_local_address(url: str) -> bool:
    """True for an address on this computer or a private network: localhost, loopback,
    private, link-local, unspecified and shared (100.64/10) ranges, and Docker's name for the
    host. The name is looked up, so `127.1`, `2130706433`, `0x7f.0.0.1`, `localhost.` and a
    name that points at a private address count too; a name that does not resolve counts as
    local, as it cannot be checked."""
    try:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return True
    if not host or host in LOCAL_HOSTS or host.endswith(".localhost"):
        return True
    try:
        found = socket.getaddrinfo(host, None)
        addresses = [ipaddress.ip_address(info[4][0].partition("%")[0]) for info in found]
    except (OSError, UnicodeError, ValueError):
        return True
    return not addresses or any(_local_ip(address) for address in addresses)


def _local_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_unspecified
        or address in SHARED_RANGE
    )


def _reaches_inside(url: str, server: str) -> bool:
    """`url`, named in an answer of the server at `server`, points at this computer or a
    private network while the server itself is not there. Kitden never fetches such an address:
    a server must not make it read what only this computer can reach. A server the user added
    at a local address may still be checked there."""
    return is_local_address(url) and not is_local_address(server)


def move_steps(
    adapters: dict[str, ClientAdapter], items: list[Item], gateway: Gateway
) -> list[Step]:
    """Move direct entries into the gateway: one gateway step per server name, then the
    remove step of every client entry. The gateway steps come first.

    MetaMCP (feature 006) cleans the name to what it accepts. Obot (checked 2026-10-19,
    v0.26.3) keeps the name, needs an administrator's key, and refuses servers on this
    computer or a private network; Kitden refuses those before the review."""
    if not items:
        raise ValueError("Choose a server to move.")
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
            raise ValueError(f"{item.name} could not be read from its file.")
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect, so the headers reach the server's own address only."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class NeedsAccess(ValueError):
    """A server that needs access before it can join the preview: the kind ("token" or
    "sign-in"), the fields to ask for, and whether a value given was refused. Its words are
    the reason the page shows; no value given is ever in them. `url` is the server's address,
    which the page never gets: it hands out a sign-in id for it instead."""

    def __init__(
        self,
        server: str,
        kind: str,
        fields: list[dict],
        refused: bool = False,
        url: str | None = None,
        reason: str | None = None,
    ):
        self.server, self.kind, self.fields, self.refused = server, kind, fields, refused
        self.url = url
        if reason is not None:
            words = reason
        elif refused:
            words = f"{server} did not accept this token."
        elif kind == "sign-in":
            words = f"{server} needs sign-in."
        else:
            words = f"{server} needs a token."
        super().__init__(words)

    def answer(self) -> dict:
        return {
            "server": self.server,
            "kind": self.kind,
            "fields": self.fields,
            "reason": str(self),
            "refused": self.refused,
        }


def _opener() -> urllib.request.OpenerDirector:
    """No redirect followed and no proxy used, so a request goes to the server's own address."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


def initialize_body() -> dict:
    """One MCP `initialize` request, as the access check and the sign-in send it."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": MCP_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "kitden", "version": "1"},
        },
    }


def _initialize(url: str, headers: dict) -> tuple[int, str]:
    """The status of one MCP `initialize` POST to `url`, and its WWW-Authenticate header.
    Raises OSError when there is no answer, or only a redirect, which the gateway would not
    follow.

    One POST to the server's own address, within 5 seconds. No redirect is followed and no
    proxy is used, so the headers go nowhere else; an error never holds them. It names itself:
    Cloudflare answers Python's default user agent with 403 (error 1010, seen 2026-10-31).
    """
    if urlsplit(url).scheme not in ("http", "https"):
        raise OSError("not a web address")
    request = urllib.request.Request(  # noqa: S310 - the scheme is http or https
        url,
        data=json.dumps(initialize_body()).encode(),
        method="POST",
        headers={
            "User-Agent": "kitden",
            **{str(k): str(v) for k, v in headers.items()},
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    try:
        with _opener().open(request, timeout=SIGN_IN_SECONDS) as answer:
            return answer.status, ""
    except urllib.error.HTTPError as answer:
        challenge = answer.headers.get("WWW-Authenticate", "") if answer.headers else ""
        answer.close()
        if 300 <= answer.code < 400:
            raise OSError("moved") from None
        return answer.code, challenge
    except (OSError, ValueError, http.client.HTTPException):
        raise OSError("no answer") from None


def needs_sign_in(url: str, headers: dict) -> bool:
    """True when the server answers an MCP `initialize` with 401 or 403, as a server that
    needs access does (Claude Code reads both that way, checked 2026-10-21). Raises OSError
    as `_initialize` does."""
    return _initialize(url, headers)[0] in (401, 403)


def _has_sign_in_metadata(url: str) -> bool:
    """Whether the server's origin serves sign-in metadata: one GET with no header of the
    entry, within 5 seconds, that answers a JSON document naming its authorization servers
    (RFC 9728), so a web page every address answers does not count."""
    parts = urlsplit(url)
    found = _get_json(f"{parts.scheme}://{parts.netloc}{SIGN_IN_METADATA}", url)
    return bool(found) and isinstance(found.get("authorization_servers"), list)


def check_access(
    name: str,
    server: dict,
    sign_in: Callable[[str, dict], str] | None,
    fields: list[dict],
    refused: bool,
    signed_in: SignIn | None = None,
) -> None:
    """Ask a remote server once what access it needs, with its headers: NeedsAccess unless it
    answers as open (`refused`: the headers hold a value typed for it), and the words that it
    could not be reached when it does not answer. With `signed_in`, the server is asked with
    that sign-in's token: it must be a finished sign-in for this address."""
    headers = server.get("headers") or {}
    if signed_in is not None:
        if signed_in.state != "done" or signed_in.url != server["url"]:
            raise NeedsAccess(name, "sign-in", fields, url=server["url"], reason=GONE)
        headers = {**headers, "Authorization": f"Bearer {signed_in.access_token}"}
    try:
        kind = (sign_in or access_needed)(server["url"], headers)
    except OSError:
        raise ValueError(f"Kitden could not reach {name}.") from None
    if kind == "sign-in-later":
        # Sign-in Kitden cannot do: a token, said so up front (no Sign in to press first).
        later = None if refused else SIGN_IN_LATER.format(name=name)
        raise NeedsAccess(name, "token", fields, refused=refused, url=server["url"], reason=later)
    if kind != "open":
        reason = f"{name} did not accept this sign-in." if signed_in is not None else None
        raise NeedsAccess(
            name, kind, fields, refused=refused or bool(reason), url=server["url"], reason=reason
        )


def signed_in_server(
    home: Path, name: str, server: dict, old: Any, signed_in: SignIn, run: Runner | None
) -> Step:
    """The gateway settings step for a server that signed in: its entry names the Keychain item
    `<name>/sign-in`, and the step carries the sign-in's JSON for Apply to store."""
    item = KeychainItem(name, SIGN_IN_KEY, signed_in.secret or "")
    entry = {**server, "sign_in": item.ref}
    step = _server_step(home, name, entry, old, run)
    if step is None:  # the same entry: only the Keychain item changes; the entry stays as held
        step = _entry_step(home, name, {**old, "sign_in": item.ref})
    step.keychain = [*step.keychain, item]
    return step


def _held_step(
    home: Path, name: str, server: dict, old: Any, signed_in: SignIn | None, run: Runner | None
) -> Step | None:
    """The gateway settings step for a server, with its sign-in when it signed in; None when the
    gateway holds the same entry already."""
    if signed_in is not None:
        return signed_in_server(home, name, server, old, signed_in, run)
    return _server_step(home, name, server, old, run)


def _with_access(
    server: dict, headers: dict | None, signed_in: SignIn | None, alone: bool = True
) -> dict:
    """The server with the token typed for it in its headers. A token (only `Authorization`)
    and a sign-in go with one remote server; `alone` is False when the change has more."""
    remote = alone and "url" in server
    if headers:
        if set(headers) != {"Authorization"}:
            raise ValueError("Only the server's declared access fields can be set.")
        if not remote:
            raise ValueError("A token goes with one remote server.")
        server = {**server, "headers": {**(server.get("headers") or {}), **headers}}
    if signed_in is not None and not remote:
        raise ValueError("A sign-in goes with one remote server.")
    return server


def _path_steps(home: Path, settings: dict) -> list[Step]:
    """The PATH the gateway's local servers use, when the settings have none."""
    path = os.environ.get("PATH")
    if path and not settings.get("path"):
        return [settings_step(home, ("path",), path, "PATH")]
    return []


def access_needed(url: str, headers: dict) -> str:
    """What a remote server needs: "open" (nothing), "token", "sign-in", or "sign-in-later"
    (it offers sign-in, but Kitden cannot register as its client, so it takes a token). A 401
    or 403 means it needs access; sign-in is possible when the 401 names its metadata in
    WWW-Authenticate (`resource_metadata`: MCP authorization spec 2025-06-18, checked
    2026-11-01) or its origin serves that metadata. Raises OSError as `_initialize` does."""
    status, challenge = _initialize(url, headers)
    if status not in (401, 403):
        return "open"
    if "resource_metadata" in challenge or _has_sign_in_metadata(url):
        return "sign-in-later" if _can_register(url, challenge) is False else "sign-in"
    return "token"


def _get_json(url: str, server: str) -> dict | None:
    """One GET of a JSON document, with no header of the entry, within 5 seconds; None when
    there is no such document, or when `url` points inside while `server`, the address the
    user gave, does not (see `_reaches_inside`)."""
    if urlsplit(url).scheme not in ("http", "https") or _reaches_inside(url, server):
        return None
    request = urllib.request.Request(url, headers={"User-Agent": "kitden"})  # noqa: S310
    try:
        with _opener().open(request, timeout=SIGN_IN_SECONDS) as answer:
            data = json.loads(answer.read(1_000_000))
    except (OSError, ValueError, http.client.HTTPException):
        return None
    return data if isinstance(data, dict) else None


def _can_register(url: str, challenge: str) -> bool | None:
    """Whether Kitden can register as the client of a server that offers sign-in: its
    authorization server lists a `registration_endpoint` (dynamic registration, the one way
    Kitden can: it has no public address for a client metadata document). None when Kitden
    could not read the metadata; the sign-in then tries.

    The metadata comes from the server's protected resource metadata (named by the 401, else
    at its well-known path) and its first authorization server's metadata (RFC 8414, else
    OpenID Connect discovery), as the MCP authorization spec says (2026-07-28, checked
    2026-11-02). Zoom, for one, lists none: it takes only apps registered with it."""
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    named = re.search(r'resource_metadata="([^"]+)"', challenge)
    places = [named.group(1)] if named else []
    path = parts.path.rstrip("/")
    places += [f"{origin}{SIGN_IN_METADATA}{path}", f"{origin}{SIGN_IN_METADATA}"]
    resource = next((m for p in dict.fromkeys(places) if (m := _get_json(p, url))), None)
    servers = resource.get("authorization_servers") if resource else None
    if not isinstance(servers, list) or not servers or not isinstance(servers[0], str):
        return None
    issuer = urlsplit(servers[0])
    root, tail = f"{issuer.scheme}://{issuer.netloc}", issuer.path.rstrip("/")
    for place in (
        f"{root}/.well-known/oauth-authorization-server{tail}",
        f"{root}/.well-known/openid-configuration{tail}",
        f"{root}{tail}/.well-known/openid-configuration",
    ):
        metadata = _get_json(place, url)
        if metadata:
            return bool(metadata.get("registration_endpoint"))
    return None


def _codex_layers(name: str, known_projects: list[str], user_file: str) -> bool:
    """A known project's `.codex/config.toml` has its own `[mcp_servers.<name>]` table, which
    changes Codex's user entry there."""
    for project in known_projects:
        path = Path(project) / ".codex/config.toml"
        if path.resolve() == Path(user_file).resolve():
            continue  # the home folder: that file is the user's own
        try:
            servers = tomllib.loads(path.read_text()).get("mcp_servers")
        except (OSError, ValueError):
            continue
        if isinstance(servers, dict) and name in servers:
            return True
    return False


def _movable(
    adapters: dict[str, ClientAdapter], item: Item, known_projects: list[str]
) -> tuple[Step, dict, dict]:
    """The item's remove step, its entry and what the gateway will run. Refuses, with the
    reason, an entry that stays direct."""
    name = item.name
    if item.scope is Scope.PROJECT:
        raise ValueError(IN_PROJECT_FILES.format(name))
    if name == SETUP_NAME:
        raise ValueError("Kitden's own entry stays in each client.")
    remove = remove_steps(adapters, item)[0]
    assert remove.edit is not None
    if item.client == "codex" and _codex_layers(name, known_projects, remove.edit.path):
        raise ValueError(IN_PROJECT_FILES.format(name))
    entry = _raw_entry(remove)
    if entry is None:
        raise ValueError(f"{name} could not be read from its file.")
    refusal = entry_refusal(name, entry)
    if refusal is not None:
        raise ValueError(refusal)
    return remove, entry, gateway_entry(entry)


def _permission_rules(path: Path, kind: str = "deny") -> list[str]:
    """Claude Code's `permissions.deny` (or `allow`) rules in one settings file; none if it
    cannot be read."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    permissions = data.get("permissions") if isinstance(data, dict) else None
    rules = permissions.get(kind) if isinstance(permissions, dict) else None
    return [rule for rule in rules if isinstance(rule, str)] if isinstance(rules, list) else []


def claude_allows_kitden(home: Path, known_projects: list[str]) -> bool:
    """True when Claude Code's user settings or a known project's settings allow every tool of
    the `kitden` entry without asking (`mcp__kitden` or `mcp__kitden__*`, or the same for the
    kitden plugin's server). Tools moved into the Kitden gateway are then allowed too."""
    files = [home / ".claude/settings.json"]
    for project in known_projects:
        folder = Path(project) / ".claude"
        files += [folder / "settings.json", folder / "settings.local.json"]
    # A plugin's server tools are mcp__plugin_<plugin>_<server>__<tool> (checked 2026-10-21,
    # code.claude.com MCP docs); the kitden plugin and its server are both "kitden".
    servers = (f"mcp__{SETUP_NAME}", f"mcp__plugin_{SETUP_NAME}_{SETUP_NAME}")
    whole = {rule for server in servers for rule in (server, f"{server}__*")}
    return any(rule in whole for path in files for rule in _permission_rules(path, "allow"))


def _claude_denies(home: Path, known_projects: list[str]) -> dict[str | None, list[str]]:
    """Claude Code's deny rules: the user's (None) and each known project's."""
    denies: dict[str | None, list[str]] = {None: _permission_rules(home / ".claude/settings.json")}
    for project in known_projects:
        folder = Path(project) / ".claude"
        if folder.resolve() == (home / ".claude").resolve():
            continue  # the home folder: its settings are the user's
        denies[project] = _permission_rules(folder / "settings.json")
        denies[project] += _permission_rules(folder / "settings.local.json")
    return denies


def _claude_project_offs(home: Path) -> dict[str, list[str]]:
    """The servers Claude Code's /mcp turned off in each project: `disabledMcpServers` in
    ~/.claude.json (Task 4 ruling, 2026-10-21)."""
    try:
        state = json.loads((home / ".claude.json").read_text())
    except (OSError, ValueError):
        return {}
    projects = state.get("projects") if isinstance(state, dict) else None
    offs = {}
    for project, data in projects.items() if isinstance(projects, dict) else []:
        names = data.get("disabledMcpServers") if isinstance(data, dict) else None
        if isinstance(names, list):
            offs[project] = [n for n in names if isinstance(n, str)]
    return offs


Rules = dict[tuple[str | None, str | None], tuple[str, set[str]]]


def _carried_rules(
    name: str,
    found: list[tuple[Item, dict]],
    home: Path,
    denies: dict[str | None, list[str]],
    project_offs: dict[str, list[str]],
) -> tuple[Rules, bool]:
    """The server's rules from what the clients had: (project or None, tool or None) ->
    (state, the clients it comes from); and whether a Codex `enabled_tools` list was carried,
    which turns strict mode on.

    Codex `enabled`, `enabled_tools` and `disabled_tools`, Claude Code deny rules and servers
    Claude Code turned off in a project turn things off; a Claude Code local-scope entry turns
    the server on in its project only. The tools an `enabled_tools` list keeps are on, so they
    stay on in strict mode. A rule has no per-client form, so off wins.
    """
    rules: Rules = {}

    def rule(project: str | None, tool: str | None, state: str, client: str) -> None:
        now, clients = rules.get((project, tool), (state, set()))
        if now == state:
            rules[(project, tool)] = (state, clients | {client})
        elif state == "off":
            rules[(project, tool)] = (state, {client})

    known = [t["name"] for t in load_tools(home).get(name, [])]
    codex_off = strict = False
    for item, entry in found:
        if item.client != "codex":
            continue
        if entry.get("enabled") is False:
            codex_off = True
            rule(None, None, "off", "codex")
        kept = entry.get("enabled_tools")
        strict = strict or isinstance(kept, list)
        for tool in known if isinstance(kept, list) else []:
            rule(None, tool, "on" if tool in kept else "off", "codex")
        off = entry.get("disabled_tools")
        for tool in off if isinstance(off, list) else []:
            if isinstance(tool, str):
                rule(None, tool, "off", "codex")
    prefix = f"mcp__{name}__"
    for project, deny in denies.items():
        for text in deny:
            if text in (f"mcp__{name}", f"{prefix}*"):
                rule(project, None, "off", "claude_code")
            elif text.startswith(prefix) and text != prefix:
                rule(project, text.removeprefix(prefix), "off", "claude_code")
    for project, names in project_offs.items():
        if name in names:
            rule(project, None, "off", "claude_code")
    local = [item.project for item, _ in found if item.scope is Scope.LOCAL]
    if local and (codex_off or len(local) == len(found)):
        rule(None, None, "off", "claude_code")
        for project in local:
            rule(project, None, "on", "claude_code")
    return rules, strict


def _codex_timeout_steps(adapters: dict[str, ClientAdapter]) -> list[Step]:
    """The timeouts an existing Codex `kitden` entry lacks."""
    adapter = adapters.get("codex")
    if adapter is None:
        return []
    # The entry as written now, where the step that would add it puts it.
    entry = _raw_entry(adapter.setup_server_step("", []))
    if entry is None:
        return []
    return [
        adapter.setup_entry_step(key, value)
        for key, value in CODEX_TIMEOUTS.items()
        if key not in entry
    ]


def tools_to_read(
    adapters: dict[str, ClientAdapter], items: list[Item], home: Path, known_projects: list[str]
) -> dict[str, dict]:
    """The servers a move must ask for their tools first, by name, with what the gateway runs:
    a Codex entry that keeps only some tools on (`enabled_tools`), when Kitden does not know
    its tools yet and the gateway does not hold it already (its rules stay). Refuses an entry
    that stays direct, as local_move_steps does."""
    cached = load_tools(home)
    held = load_settings(home)["servers"]
    wanted = {}
    for item in items:
        _, entry, server = _movable(adapters, item, known_projects)
        some = item.client == "codex" and isinstance(entry.get("enabled_tools"), list)
        if some and item.name not in cached and item.name not in held:
            wanted[item.name] = server
    return wanted


def set_up_differently(name: str, first: str, other: str) -> str:
    """Why a move refuses a name whose entries differ: the gateway runs one entry per name.
    `first` and `other` are the clients of the first entry and of the one that differs."""
    a, b = CLIENT_WORDS[first], CLIENT_WORDS[other]
    where = f"two places in {a}" if a == b else f"{a} and {b}"
    return f"{name} is set up differently in {where}; keep one first."


def local_move_steps(
    adapters: dict[str, ClientAdapter],
    items: list[Item],
    home: Path,
    known_projects: list[str],
    command: str | None,
    *,
    added_clients: set[str],
    sign_in: Callable[[str, dict], str] | None = None,
    keychain_run: Runner | None = None,
    headers: dict | None = None,
    signed_in: SignIn | None = None,
) -> list[Step]:
    """Move direct entries into the Kitden gateway, in one change.

    The steps: each server in the gateway settings (plus the PATH its local servers use, when
    the settings have none), the rules the clients had for it, the removal of each client
    entry, and the `kitden` entry for each of those clients that lacks it (`added_clients` have
    it, also from the kitden plugin). An existing Codex `kitden` entry gets the timeouts it
    lacks. An entry that must stay direct is refused, with the reason, before any step.

    A server the gateway holds already keeps its rules: a different entry replaces the held one
    (a new token, say), and the same entry only leaves the clients. A client's removal step is
    marked (`switches_left`) when that client had tools or the server off, which do not carry.

    `sign_in` asks a remote server what access it needs, and `keychain_run` reads the
    Keychain; None is `access_needed` and the real Keychain (the demo passes its stand-ins).
    A remote server that needs access raises NeedsAccess. `headers` is the token typed for
    it (only `Authorization`, for a single remote server), checked before any step; `signed_in`
    is a browser sign-in for a single remote server, checked the same way.
    """
    if not items:
        raise ValueError("Choose a server to move.")
    items = list({item.id: item for item in items}.values())
    servers: dict[str, dict] = {}
    found: dict[str, list[tuple[Item, dict]]] = {}
    removes = []
    for item in items:
        remove, entry, server = _movable(adapters, item, known_projects)
        first = servers.setdefault(item.name, server)
        if server != first:
            before = found[item.name][0][0].client
            raise ValueError(set_up_differently(item.name, before, item.client))
        found.setdefault(item.name, []).append((item, entry))
        removes.append(remove)
    settings = load_settings(home)
    held = settings["servers"]
    # A Codex entry may give its server more time to start; the gateway keeps the longest, also
    # the one an entry it holds already has.
    for name, server in servers.items():
        waits = [e.get(START_TIME) for i, e in found[name] if i.client == "codex"]
        if isinstance(held.get(name), dict):
            waits.append(held[name].get(START_TIME))
        waits = [w for w in waits if is_number(w)]
        if waits:
            servers[name] = {**server, START_TIME: max(waits)}
    lacking = [c for c in dict.fromkeys(i.client for i in items) if c not in added_clients]
    if lacking and (command is None or not Path(command).is_absolute()):
        raise ValueError(NEEDS_COMMAND)
    name = next(iter(servers))
    servers[name] = _with_access(servers[name], headers, signed_in, alone=len(servers) == 1)
    for name, server in servers.items():
        if "url" in server:
            check_access(name, server, sign_in, [TOKEN_FIELD], bool(headers), signed_in)
    written = (
        _held_step(home, n, s, held.get(n), signed_in, keychain_run) for n, s in servers.items()
    )
    steps = [step for step in written if step is not None]
    if steps:  # with a server entry written
        steps += _path_steps(home, settings)
    denies = _claude_denies(home, known_projects)
    project_offs = _claude_project_offs(home)
    for name in servers:
        rules, strict = _carried_rules(name, found[name], home, denies, project_offs)
        if name in held:
            # The gateway's own rules for it stay; the review names the clients whose own
            # switches for it do not carry over.
            had = {client for _, clients in rules.values() for client in clients}
            for remove in removes:
                remove.switches_left |= remove.name == name and remove.client in had
            continue
        for (project, tool), (state, clients) in rules.items():
            step = rule_step(home, project, name, tool, state)
            step.carried_from = tuple(sorted(clients))
            steps.append(step)
        if strict:
            step = strict_step(home, name, True)
            step.carried_from = ("codex",)
            steps.append(step)
    steps += removes
    if lacking:
        assert command is not None  # checked above
        for step in setup_server_steps(adapters, lacking, command):
            if step.client == "codex":
                assert step.edit is not None
                step.edit.after = {**step.edit.after, **CODEX_TIMEOUTS}
            steps.append(step)
    return steps + _codex_timeout_steps(adapters)


def secrets_out(name: str, server: dict) -> tuple[dict, list[KeychainItem]]:
    """The entry with each env or header value that `redact` hides replaced by a Keychain
    reference, and those values as Keychain items. An empty value is no secret: it stays."""
    entry = dict(server)
    items = []
    for field in SECRET_FIELDS:
        values = server.get(field)
        if not isinstance(values, dict):
            continue
        entry[field] = {}
        for key, value in values.items():
            if isinstance(value, str) and value and redact({field: {key: value}})[1]:
                item = KeychainItem(name, key, value)
                items.append(item)
                value = item.ref
            entry[field][key] = value
    return entry, items


def _server_step(
    home: Path, name: str, server: dict, old: Any, keychain_run: Runner | None = None
) -> Step | None:
    """The gateway settings step for a moved server, with its secrets as Keychain items.

    A server the gateway holds already is compared with its references read from the
    Keychain: the same values need no step, and a secret whose item holds the same value
    needs no write.
    """
    entry, items = secrets_out(name, server)
    if isinstance(old, dict):
        if not all(isinstance(old.get(f) or {}, dict) for f in SECRET_FIELDS):
            raise ValueError(f"{name} in the gateway settings could not be read.")
        try:
            values = resolve_entry(old, run=keychain_run or run_security)
        except KeychainError:
            values = None  # an item is missing: write them all again
        if values == server:
            return None
        if values is not None:
            items = [
                i
                for i in items
                if not any(
                    (old.get(f) or {}).get(i.key) == i.ref
                    and (values.get(f) or {}).get(i.key) == i.value
                    for f in SECRET_FIELDS
                )
            ]
    return _entry_step(home, name, entry, items)


def _entry_step(home: Path, name: str, entry: dict, items: Sequence[KeychainItem] = ()) -> Step:
    """The gateway settings step that writes one server's entry, with its Keychain items."""
    step = settings_step(home, ("servers", name), entry, name)
    step.keychain = list(items)
    return step


def _held(home: Path, server: str, remote: bool = False) -> dict:
    """The entry the Kitden gateway holds for `server`; with `remote`, only one with an address."""
    held = load_settings(home)["servers"].get(server)
    if not isinstance(held, dict) or (remote and "url" not in held):
        raise ValueError("Choose a server in the Kitden gateway.")
    return held


def _resolved(held: dict, run: Runner | None) -> dict:
    """The held entry with its values read from the Keychain in place of the references."""
    try:
        return resolve_entry(held, run=run or run_security)
    except KeychainError as problem:
        raise ValueError(str(problem)) from None


def sign_in_steps(
    home: Path,
    server: str,
    signed_in: SignIn | None,
    *,
    sign_in: Callable[[str, dict], str] | None = None,
    keychain_run: Runner | None = None,
) -> list[Step]:
    """Sign a held server in again: one step with the same entry that carries the new
    sign-in for Apply to store in its Keychain item. The new token is checked first."""
    held = _held(home, server, remote=True)
    if signed_in is None:
        raise ValueError(f"Sign in to {server} first.")
    values = _resolved(held, keychain_run)
    values.pop("sign_in", None)
    check_access(server, values, sign_in, [TOKEN_FIELD], False, signed_in)
    return [signed_in_server(home, server, values, held, signed_in, keychain_run)]


def access_steps(
    home: Path,
    server: str,
    field: str,
    name: str,
    value: str | None,
    *,
    sign_in: Callable[[str, dict], str] | None = None,
    keychain_run: Runner | None = None,
) -> list[Step]:
    """Replace one secret of a held server (`value`), or remove it (None): an env or header
    value, or its sign-in (sign out; a sign-in is changed by signing in again). A new value
    goes to the Keychain on Apply; a remote server is asked with it first, a local one checks
    it when it starts. A removed value's Keychain item stays, so Undo brings the server back."""
    held = _held(home, server)
    if field == "sign_in":
        if value is not None:
            raise ValueError("Sign in again to change a sign-in.")
        if "sign_in" not in held:
            raise ValueError(f"{server} is not signed in.")
        entry = {k: v for k, v in held.items() if k != "sign_in"}
        return [_entry_step(home, server, entry)]
    if field not in SECRET_FIELDS:
        raise ValueError("Choose a value to change.")
    values = dict(held.get(field) or {}) if isinstance(held.get(field), dict) else {}
    if value is None:
        if name not in values:
            raise ValueError(f"{server} has no {name}.")
        values.pop(name)
        entry = {k: v for k, v in held.items() if k != field}
        if values:
            entry[field] = values
        return [_entry_step(home, server, entry)]
    value = value.strip()
    if not value or "\n" in value or "\r" in value:
        raise ValueError("Enter a valid access value again.")
    if field == "headers" and "url" in held:
        resolved = _resolved(held, keychain_run)
        resolved.pop("sign_in", None)
        given = {**resolved, "headers": {**(resolved.get("headers") or {}), name: value}}
        check_access(server, given, sign_in, [TOKEN_FIELD], True)
    item = KeychainItem(server, name, value)
    return [_entry_step(home, server, {**held, field: {**values, name: item.ref}}, [item])]


def keychain_steps(home: Path, server: str) -> list[Step]:
    """Move the plain env and header values of a held server to the Keychain: one step that
    writes the entry with references, carrying the values for Apply to store."""
    entry, items = secrets_out(server, _held(home, server))
    if not items:
        raise ValueError(f"{server} keeps no secret in the settings file.")
    return [_entry_step(home, server, entry, items)]


def gateway_add_steps(
    adapters: dict[str, ClientAdapter],
    inventory: "Inventory",
    home: Path,
    server_id: str,
    *,
    discovered: tuple[str, dict] | None = None,
    sign_in: Callable[[str, dict], str] | None = None,
    keychain_run: Runner | None = None,
    fields: list[dict] | None = None,
    headers: dict | None = None,
    signed_in: SignIn | None = None,
) -> list[Step]:
    """Add one server a marketplace plugin offers (`server_id`, its row in market_servers) to
    the Kitden gateway, in one change: its entry in the gateway settings, with its secrets as
    Keychain items, the PATH when the settings have none, and the timeouts an existing Codex
    `kitden` entry lacks. No client gets a `kitden` entry or any other change.

    A server the gateway cannot take is refused first, with the list's reason. A remote one is
    asked once what access it needs, as a move asks; `fields` are the access values its
    catalog row declares (else the one token field). `headers` is a token typed for a
    marketplace server (only `Authorization`), as local_move_steps takes it, and so is
    `signed_in`. `sign_in` and `keychain_run` are as in local_move_steps.
    """
    name = server_id.partition("/")[2]
    if discovered is None:
        _, entry = market_entry(adapters, server_id)
    else:
        name, entry = discovered
    settings = load_settings(home)
    refusal = known_refusal(name, entry, inventory, set(settings["servers"]))
    if refusal is not None:
        raise ValueError(refusal)
    server = _with_access(gateway_entry(entry), headers, signed_in)
    if "url" in server:
        # A value typed for it was refused: for a marketplace server only a token typed here
        # (its entry may send a header of its own); a catalog row's headers are all typed.
        given = bool(headers) if discovered is None else bool(server.get("headers"))
        check_access(name, server, sign_in, fields or [TOKEN_FIELD], given, signed_in)
    step = _held_step(home, name, server, None, signed_in, keychain_run)
    assert step is not None  # a new server always has its step
    return [step, *_path_steps(home, settings), *_codex_timeout_steps(adapters)]


def _refuse_if_present(step: Step, client: str, name: str) -> None:
    """A client that has an entry of that name already keeps it: nothing is replaced."""
    if _raw_entry(step) is not None:
        raise ValueError(f"{CLIENT_WORDS[client]} already has {name}.")


def put_back_steps(
    adapters: dict[str, ClientAdapter],
    home: Path,
    server: str,
    clients: list[str],
    keychain_run: Runner | None = None,
) -> list[Step]:
    """Write a held server's entry into each chosen client, as a user-scope MCP entry, in that
    client's format. The gateway keeps the server; the review says it then loads twice.
    `keychain_run` reads the Keychain; None is the real one."""
    if not clients:
        raise ValueError("Choose at least one client")
    entry = _resolved(_held(home, server), keychain_run)  # the values, not the references
    steps = []
    for client in dict.fromkeys(clients):
        value = translate_entry(entry, client)
        adapter = adapters.get(client)
        if adapter is None:
            raise ValueError(f"{client} cannot take an MCP entry")
        step = adapter.add_server_step(server, value)
        _refuse_if_present(step, client, server)
        steps.append(step)
    return steps


def add_server_steps(
    adapters: dict[str, ClientAdapter], item: Item, clients: list[str]
) -> list[Step]:
    """Write a direct server one client has into each chosen client, as a user-scope MCP
    entry in that client's format. The first client keeps its own entry."""
    if item.scope in (Scope.PROJECT, Scope.LOCAL):
        raise ValueError("It is already per project; copy the file into the project instead.")
    if item.name == SETUP_NAME:
        raise ValueError("Kitden's own entry stays in each client.")
    if item.via_gateway or REMOVE_DIRECT not in item.actions:
        raise ValueError(f"{item.name} is not a direct entry.")
    entry = _raw_entry(remove_steps(adapters, item)[0])
    if entry is None:
        raise ValueError(f"{item.name} could not be read from its file.")
    if not clients:
        raise ValueError("Choose at least one client")
    steps = []
    for client in dict.fromkeys(clients):
        adapter = adapters.get(client)
        if adapter is None:
            raise ValueError(f"{client} cannot take an MCP entry")
        value = translate_entry(entry, client, source=item.client)
        step = adapter.add_server_step(item.name, value)
        _refuse_if_present(step, client, item.name)
        steps.append(step)
    return steps


def skill_rules_in(path: Path) -> bool:
    """The Claude Code settings file has `skillOverrides` with at least one key."""
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        raise ValueError(CHANGE_UNREAD.format(path.name)) from None
    rules = data.get("skillOverrides") if isinstance(data, dict) else None
    return bool(rules)


def _claude_rule_steps(
    adapter: ClientAdapter, home: Path, item: Item, project: str | None, off: bool
) -> list[Step]:
    """Claude Code: a skill's `skillOverrides` key, or a plugin's key in one project (taken out
    of each local file that holds it)."""
    if item.kind is ItemKind.PLUGIN:
        if item.scope is Scope.ACCOUNT:
            raise ValueError(item.change_hint or f"{item.name} has no switch here.")
        if project is None:
            raise ValueError(PLUGIN_ALL_PROJECTS)
        return adapter.plugin_rule_steps(item.name, project, off)
    if item.kind is not ItemKind.SKILL:
        raise ValueError("Choose a skill or a plugin.")
    if item.scope is Scope.PLUGIN:
        raise ValueError(PLUGIN_SKILL)
    if project is None and item.project is not None:
        raise ValueError(PROJECT_SKILL_ALL)  # a rule in the user's file would hide every copy
    real = os.path.realpath
    if item.scope is Scope.PROJECT and project and real(str(item.project)) != real(project):
        raise ValueError("This skill is in another project.")
    if project is not None and off:
        # The docs do not confirm that `skillOverrides` merges key by key (claude_code.py). If a
        # higher file replaces the whole object, a new key in the local file would drop the
        # rules of the user's file, and of the project's shared file, in that project.
        folder = Path(project) / ".claude"
        files = [home / ".claude/settings.json", folder / "settings.json"]
        # A rule in the repository root's local file: the starting folder's own local file (an
        # earlier Claude Code wrote there) is read beside it (clients/claude_code.py git_root).
        if rule_file(Path(project), home) != folder / "settings.local.json":
            files.append(folder / "settings.local.json")
        if any(skill_rules_in(f) for f in files):
            raise ValueError(NO_SKILL_MERGE)
    return adapter.skill_rule_steps(item.name, project, off)


def skill_rule_steps(
    adapters: dict[str, ClientAdapter],
    inventory: "Inventory",
    home: Path,
    targets: list,
    params: dict,
) -> list[Step]:
    """Turn skills off for all projects or in one project, one step per target {client, item}
    (spec 5.5). `params`: scope "all" or "project", `project` (its id), and `off`. `off` False
    takes a project's own rule out, so the shared rule applies there again.

    Claude Code writes `skillOverrides` (a plugin: `enabledPlugins` in one project's local
    settings), Codex a `[[skills.config]]` entry, for all projects only. Cursor has no switch.
    """
    scope, off = params.get("scope"), params.get("off", True) is not False
    project = None
    if scope == "project":
        paths = {p.id: p.path for p in inventory.projects}
        project = paths.get(str(params.get("project") or ""))
        if project is None:
            raise ValueError("Unknown project.")
    elif scope != "all":
        raise ValueError("Choose all projects or one project.")
    elif not off:
        raise ValueError("Pick a project to use the shared rule there.")
    by_id = {i.id: i for i in inventory.items}
    steps = []
    for target in targets:
        item = by_id.get(str(target.get("item"))) if isinstance(target, dict) else None
        if item is None or target.get("client") != item.client:
            raise ValueError("Choose a known skill.")
        adapter = adapters.get(item.client)
        if item.client == "cursor":
            raise ValueError(CURSOR_NO_SKILL_SWITCH)
        if adapter is None or item.client not in ("claude_code", "codex"):
            raise ValueError(f"{item.name} has no switch here.")
        if item.client == "claude_code":
            steps += _claude_rule_steps(adapter, home, item, project, off)
            continue
        if item.kind is not ItemKind.SKILL or item.scope is Scope.PLUGIN:
            raise ValueError(f"{item.name} has no switch here.")
        if project is not None:
            raise ValueError(CODEX_NO_PROJECT)
        steps.append(adapter.skill_rule_step(item))
    if not steps:
        raise ValueError("Choose a skill.")
    return steps
