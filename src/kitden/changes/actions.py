"""Turn a requested action into steps for the change engine (write-matrix.md)."""

import http.client
import ipaddress
import json
import os
import re
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from kitden.changes import json_splice, toml_edit
from kitden.clients.base import (
    PLUGIN_DISABLE,
    PLUGIN_ENABLE,
    PLUGIN_REMOVE,
    REMOVE_DIRECT,
    SETUP_NAME,
    SKILL_REMOVE,
    ClientAdapter,
)
from kitden.clients.entries import IN_PROJECT_FILES, entry_refusal, gateway_entry
from kitden.gateway_api import gateway_name
from kitden.local_gateway.keychain import KeychainError, Runner, resolve_entry, run_security
from kitden.local_gateway.settings import (
    START_TIME,
    load_settings,
    load_tools,
    rule_step,
    settings_step,
    strict_step,
)
from kitden.model import (
    GATEWAY_CLIENT,
    Gateway,
    GatewayEdit,
    Item,
    KeychainItem,
    Scope,
    Step,
)
from kitden.redact import redact

GATEWAY_CONNECT = "gateway.connect"
GATEWAY_MOVE = "gateway.move"
GATEWAY_SWITCH = "gateway.switch"
PLUGIN_INSTALL = "plugin.install"
MARKETPLACE_ADD = "marketplace.add"
SKILL_INSTALL = "skill.install"
PLUGIN_SKILLS = "plugin.skills"
CLIENT_WORDS = {"claude_code": "Claude Code", "codex": "Codex", "cursor": "Cursor"}
SETUP_SERVER_UPDATE = "setup_server.update"
# Turns a client's `kitden` entry back on, where its docs name the switch (views/setup_server.py).
SETUP_SERVER_ENABLE = "setup_server.enable"
NEEDS_COMMAND = "The setup server needs the absolute path of the kitden command"
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


def remove_steps(adapters: dict[str, ClientAdapter], item: Item) -> list[Step]:
    """Remove one direct MCP entry (FR-026)."""
    adapter = adapters.get(item.client)
    if adapter is None or REMOVE_DIRECT not in item.actions:
        raise ValueError(f"{item.name} cannot be removed here")
    return [adapter.remove_step(item)]


def remove_plugin_steps(adapters: dict[str, ClientAdapter], item: Item) -> list[Step]:
    """Remove one installed plugin with its client's own command (spec 3.1)."""
    adapter = adapters.get(item.client)
    if adapter is None or PLUGIN_REMOVE not in item.actions:
        raise ValueError(f"{item.name} cannot be removed here")
    return [adapter.plugin_remove_step(item)]


def skill_remove_steps(
    adapters: dict[str, ClientAdapter], item: Item, readers: list[str], keeps: list[str]
) -> list[Step]:
    """Remove one skill folder from its client; Undo copies it back (spec 3.2)."""
    adapter = adapters.get(item.client)
    if adapter is None or SKILL_REMOVE not in item.actions:
        raise ValueError(f"{item.name} cannot be removed here")
    return [adapter.skill_remove_step(item, readers, keeps)]


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


KITDEN_GATEWAY = "kitden"  # the gateway inside `kitden mcp`, on this Mac
GATEWAY_RULE = "gateway.rule"  # one switch of the Kitden gateway: a server or a tool on or off
GATEWAY_STRICT = "gateway.strict"  # a held server's strict mode on or off: new tools wait
GATEWAY_RULES = "gateway.rules"  # several tools of one server on or off in one review
GATEWAY_REMOVE = "gateway.remove"  # a held server and its rules leave the Kitden gateway
GATEWAY_PUT_BACK = "gateway.put_back"  # a held server's entry written into a client
GATEWAY_KEYCHAIN = "gateway.keychain"  # a held server's plain secrets moved to the Keychain
# Codex waits 10 s for a server to start and 60 s for a tool call (checked 2026-10-21). The
# Kitden gateway may take up to 20 s to list a server and 300 s for one call.
CODEX_TIMEOUTS = {"startup_timeout_sec": 30, "tool_timeout_sec": 300}
SIGN_IN_SECONDS = 5
MCP_VERSION = "2025-06-18"  # a protocol version every MCP server knows (checked 2026-10-21)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect, so the headers reach the server's own address only."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def needs_sign_in(url: str, headers: dict) -> bool:
    """True when the server answers an MCP `initialize` with 401 or 403, as a server that
    signs in with OAuth does (Claude Code reads both that way, checked 2026-10-21). Raises
    OSError when there is no answer, or only a redirect, which the gateway would not follow.

    One POST to the server's own address, within 5 seconds. No redirect is followed and no
    proxy is used, so the headers go nowhere else; an error never holds them.
    """
    if urlsplit(url).scheme not in ("http", "https"):
        raise OSError("not a web address")
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": MCP_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "kitden", "version": "1"},
        },
    }
    request = urllib.request.Request(  # noqa: S310 - the scheme is http or https
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            **{str(k): str(v) for k, v in headers.items()},
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)
    try:
        with opener.open(request, timeout=SIGN_IN_SECONDS):
            return False
    except urllib.error.HTTPError as answer:
        answer.close()
        if 300 <= answer.code < 400:
            raise OSError("moved") from None
        return answer.code in (401, 403)
    except (OSError, ValueError, http.client.HTTPException):
        raise OSError("no answer") from None


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
    sign_in: Callable[[str, dict], bool] | None = None,
    keychain_run: Runner | None = None,
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

    `sign_in` asks a remote server whether it signs in, and `keychain_run` reads the Keychain;
    None is `needs_sign_in` and the real Keychain (the demo passes its stand-ins).
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
        waits = [w for w in waits if isinstance(w, int | float) and not isinstance(w, bool)]
        if waits:
            servers[name] = {**server, START_TIME: max(waits)}
    lacking = [c for c in dict.fromkeys(i.client for i in items) if c not in added_clients]
    if lacking and (command is None or not Path(command).is_absolute()):
        raise ValueError(NEEDS_COMMAND)
    for name, server in servers.items():
        if "url" not in server:
            continue
        try:
            oauth = (sign_in or needs_sign_in)(server["url"], server.get("headers") or {})
        except OSError:
            raise ValueError(f"Kitden could not reach {name}.") from None
        if oauth:
            raise ValueError(f"{name} signs in with OAuth; it stays direct for now.")

    steps = [
        step
        for n, s in servers.items()
        if (step := _server_step(home, n, s, held.get(n), keychain_run)) is not None
    ]
    path = os.environ.get("PATH")
    if steps and path and not settings.get("path"):  # with a server entry written
        steps.append(settings_step(home, ("path",), path, "PATH"))
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


SECRET_FIELDS = ("env", "headers")  # the gateway entry's maps whose values may be secrets


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
    step = settings_step(home, ("servers", name), entry, name)
    step.keychain = items
    return step


def keychain_steps(home: Path, server: str) -> list[Step]:
    """Move the plain env and header values of a held server to the Keychain: one step that
    writes the entry with references, carrying the values for Apply to store."""
    held = load_settings(home)["servers"].get(server)
    if not isinstance(held, dict):
        raise ValueError("Choose a server in the Kitden gateway.")
    entry, items = secrets_out(server, held)
    if not items:
        raise ValueError(f"{server} keeps no secret in the settings file.")
    step = settings_step(home, ("servers", server), entry, server)
    step.keychain = items
    return [step]


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
    from kitden.changes.server_entry import translate_entry  # it reads helpers of this module

    if not clients:
        raise ValueError("Choose at least one client")
    held = load_settings(home)["servers"].get(server)
    if held is None:
        raise ValueError("Choose a server in the Kitden gateway.")
    try:
        # The client gets the values, not the references.
        entry = resolve_entry(held, run=keychain_run or run_security)
    except KeychainError as error:
        raise ValueError(str(error)) from None
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


MCP_ADD = "mcp.add"  # a direct server one client has, added to other clients
PROJECT_ALIGN = "project.align"  # what one client loads in a project, added to the others


def add_server_steps(
    adapters: dict[str, ClientAdapter], item: Item, clients: list[str]
) -> list[Step]:
    """Write a direct server one client has into each chosen client, as a user-scope MCP
    entry in that client's format. The first client keeps its own entry."""
    from kitden.changes.server_entry import translate_entry  # it reads helpers of this module

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
        if adapter is None or client not in CLIENT_WORDS:
            raise ValueError(f"{client} cannot take an MCP entry")
        value = translate_entry(entry, client, source=item.client)
        step = adapter.add_server_step(item.name, value)
        _refuse_if_present(step, client, item.name)
        steps.append(step)
    return steps
