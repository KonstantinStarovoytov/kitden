"""The Kitden gateway in Kitden's views: its servers in each client, their tools and rules.

The MCP SDK loads only when a server is asked for its tools: the page must start without it.
"""

import asyncio
import importlib
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from kitden.changes.actions import GATEWAY_RULE, KITDEN_GATEWAY
from kitden.clients.base import mcp_item
from kitden.gateways import data_dir
from kitden.local_gateway.settings import (
    CLIENT,
    SETTINGS_FILE,
    load_settings,
    load_tools,
    own_state,
    rule_parts,
    rule_step,
    save_tools,
)
from kitden.model import Change, Enabled, Item, Scope, Source, SourceKind, Step
from kitden.views.setup_server import setup_server_state


def gateway_items(inventory, settings: dict, home: Path) -> list[Item]:
    """The held servers in each client with the `kitden` entry, so the Library and the
    Overview count them and follow the server rules.

    Per client and server: one user-level item, off when the server is off for all projects,
    and one project item for each project with its own state for the server. All are off where
    the `kitden` entry is off.
    """
    path = str(data_dir(home) / SETTINGS_FILE)
    rules = settings["rules"]
    items = []
    for entry in setup_server_state(inventory):
        if entry["state"] not in ("added", "plugin"):
            continue
        for name, server in settings["servers"].items():
            places = [(None, own_state(rules["global"], name, None), f"servers.{name}")]
            for project, own in rules["projects"].items():
                state = own_state(own, name, None)
                if state is not None:
                    places.append((project, state, f"rules.projects.{project}.{name}"))
            for project, state, key in places:
                source = Source(kind=SourceKind.FILE, path=path, owner_client=CLIENT, key_path=key)
                on = entry["enabled"] is not False and state != "off"
                item = mcp_item(
                    entry["client"],
                    name,
                    server,
                    source,
                    Scope.USER if project is None else Scope.PROJECT,
                    project=project,
                    enabled=Enabled.ON if on else Enabled.OFF,
                )
                items.append(replace(item, via_gateway=KITDEN_GATEWAY))
    return items


def _states(settings: dict, server: str, tool: str | None, project: str | None) -> dict:
    """A server's or a tool's state in the project, and whether the project's own rule makes
    it differ from all projects."""
    rules = settings["rules"]
    everywhere = own_state(rules["global"], server, tool) or "on"
    own = own_state(rules["projects"].get(project), server, tool) if project else None
    return {"state": own or everywhere, "differs": own is not None and own != everywhere}


def held_servers(settings: dict, project: str | None) -> list[dict]:
    """Every server in the Kitden gateway, for its card: name, local or remote, and its state in
    the project (None: all projects). Commands, addresses and env stay out."""
    return [
        {
            "name": name,
            "kind": "remote" if isinstance(server, dict) and "url" in server else "local",
            **_states(settings, name, None, project),
        }
        for name, server in sorted(settings["servers"].items(), key=lambda pair: pair[0].lower())
    ]


def tools_view(settings: dict, tools: dict, server: str, project: str | None) -> dict:
    """A held server's state and its known tools, each with its state, for the project (None:
    all projects)."""
    return {
        "server": server,
        **_states(settings, server, None, project),
        "tools": [
            {
                "name": tool["name"],
                "description": tool.get("description") or "",
                **_states(settings, server, tool["name"], project),
            }
            for tool in tools.get(server, [])
        ],
    }


def rule_steps(home: Path, params: dict, projects: dict[str, str]) -> list[Step]:
    """The change one switch makes: `params` has server, tool (None: the whole server), state
    ("on", "off", or None to follow all projects) and project (an id; None: all projects).
    `projects` maps project ids to their folders."""
    server, tool = params.get("server"), params.get("tool")
    project, state = params.get("project"), params.get("state")
    if not isinstance(server, str) or server not in load_settings(home)["servers"]:
        raise ValueError("Choose a server in the Kitden gateway.")
    known = [t["name"] for t in load_tools(home).get(server, [])]
    # A tool the server no longer lists may still have a rule: it can follow all projects.
    if tool is not None and (not isinstance(tool, str) or (tool not in known and state)):
        raise ValueError("Choose a tool of this server.")
    if project is not None and (not isinstance(project, str) or project not in projects):
        raise ValueError("Unknown project.")
    if project is None and state is None:
        raise ValueError("Choose on or off.")
    return [rule_step(home, projects.get(project), server, tool, state)]


def rule_of(change: Change | None) -> dict | None:
    """A tool rule change's parts for the Changes page: the project's folder (None: all
    projects), the server, the tool (None: the whole server) and the new state (None: follows
    all projects). None when the change is not a rule or its record cannot be read as one."""
    if change is None or change.action != GATEWAY_RULE or not change.steps:
        return None
    edit = change.steps[0].edit
    if edit is None or edit.key[:1] != ("rules",):
        return None
    try:
        project, server, tool = rule_parts(edit.key)
    except IndexError:  # a key too short to be a rule
        return None
    state = edit.after if edit.after in ("on", "off") else None
    folder = Path(project).name if project else None
    return {"project": folder, "server": server, "tool": tool, "state": state}


async def load_proxy():
    """The gateway's proxy module. It loads the MCP SDK, which takes about half a second, so
    it is imported in a thread: the page goes on meanwhile."""
    return await asyncio.to_thread(importlib.import_module, "kitden.local_gateway.proxy")


async def refresh_tools(home: Path, names: Iterable[str] | None = None) -> dict[str, str | None]:
    """Ask held servers for their tools, one at a time, and keep each list in the cache.

    `names` None asks every held server. The answer maps each server asked to None, or to one
    plain sentence when it did not start or answer in time; its old list then stays.
    """
    settings = load_settings(home)
    servers = settings["servers"]
    held = [name for name in (servers if names is None else names) if name in servers]
    if not held:
        return {}
    proxy = await load_proxy()
    found: dict[str, str | None] = {}
    for name in held:
        # One block per server, so each one stops before the next starts.
        try:
            async with proxy.Upstreams(home, settings) as upstreams:
                try:
                    tools = await upstreams.list_tools(name)
                except proxy.UpstreamError as problem:
                    found[name] = str(problem)
                    continue
        except Exception:  # noqa: BLE001 - the server did not stop cleanly; the others go on
            found.setdefault(name, f"{name} did not list its tools.")
            continue
        save_tools(home, name, tools)
        found[name] = None
    return found
