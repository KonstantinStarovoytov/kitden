"""The Kitden gateway in Kitden's views: its servers in each client, their tools and rules.

The MCP SDK loads only when a server is asked for its tools: the page must start without it.
"""

from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from kitden.changes.actions import KITDEN_GATEWAY
from kitden.clients.base import mcp_item
from kitden.gateways import data_dir
from kitden.local_gateway.settings import (
    CLIENT,
    SETTINGS_FILE,
    load_settings,
    load_tools,
    own_state,
    rule_step,
    save_tools,
)
from kitden.model import Change, Enabled, Item, Scope, Source, SourceKind, Step
from kitden.views.setup_server import setup_server_state


def gateway_items(inventory, settings: dict, home: Path) -> list[Item]:
    """One MCP server item per held server in each client with the `kitden` entry, so the
    Library and the Overview count them. It is off where that entry is off."""
    path = str(data_dir(home) / SETTINGS_FILE)
    items = []
    for entry in setup_server_state(inventory):
        if entry["state"] not in ("added", "plugin"):
            continue
        enabled = Enabled.OFF if entry["enabled"] is False else Enabled.ON
        for name, server in settings["servers"].items():
            source = Source(
                kind=SourceKind.FILE, path=path, owner_client=CLIENT, key_path=f"servers.{name}"
            )
            item = mcp_item(entry["client"], name, server, source, Scope.USER, enabled=enabled)
            items.append(replace(item, via_gateway=KITDEN_GATEWAY))
    return items


def _states(settings: dict, server: str, tool: str | None, project: str | None) -> dict:
    """A server's or a tool's state in the project, and whether the project's own rule makes
    it differ from all projects."""
    rules = settings["rules"]
    everywhere = own_state(rules["global"], server, tool) or "on"
    own = own_state(rules["projects"].get(project), server, tool) if project else None
    return {"state": own or everywhere, "differs": own is not None and own != everywhere}


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
    if tool is not None and tool not in known:
        raise ValueError("Choose a tool of this server.")
    if project is not None and (not isinstance(project, str) or project not in projects):
        raise ValueError("Unknown project.")
    if project is None and state is None:
        raise ValueError("Choose on or off.")
    return [rule_step(home, projects.get(project), server, tool, state)]


def moved_in(change: Change) -> list[str]:
    """The servers a move put into the Kitden gateway."""
    return [
        step.edit.key[1]
        for step in change.steps
        if step.client == CLIENT and step.edit is not None and step.edit.key[0] == "servers"
    ]


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
    # The MCP SDK loads only here: the page must start without it.
    from kitden.local_gateway.proxy import UpstreamError, Upstreams

    found: dict[str, str | None] = {}
    for name in held:
        # One block per server, so each one stops before the next starts.
        async with Upstreams(home, settings) as upstreams:
            try:
                tools = await upstreams.list_tools(name)
            except UpstreamError as problem:
                found[name] = str(problem)
                continue
        save_tools(home, name, tools)
        found[name] = None
    return found
