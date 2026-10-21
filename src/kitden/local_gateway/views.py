"""The Kitden gateway in Kitden's views: its servers in each client, their tools and rules.

The MCP SDK loads only when a server is asked for its tools: the page must start without it.
"""

import asyncio
import importlib
import re
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from kitden.changes.actions import GATEWAY_RULE, KITDEN_GATEWAY
from kitden.clients.base import mcp_item
from kitden.gateways import data_dir
from kitden.local_gateway.project import project_chain
from kitden.local_gateway.settings import (
    CLIENT,
    SETTINGS_FILE,
    _scopes,
    deciding_project,
    load_settings,
    load_tools,
    own_state,
    rule_parts,
    rule_step,
    save_tools,
    state_in,
    strict_mode,
    strict_step,
)
from kitden.model import Change, Enabled, Item, Scope, Source, SourceKind, Step
from kitden.views.setup_server import setup_server_state


def gateway_items(inventory, settings: dict, home: Path) -> list[Item]:
    """The held servers in each client with the `kitden` entry, so the Library and the
    Overview count them and follow the server rules.

    Per client and server: one user-level item, off when the server is off for all projects,
    and one project item for each known project whose chain (see `project_chain`) has a
    project with its own state for the server. All are off where the `kitden` entry is off.
    """
    path = str(data_dir(home) / SETTINGS_FILE)
    rules = settings["rules"]
    known = [p.path for p in inventory.projects]
    items = []
    for entry in setup_server_state(inventory):
        if entry["state"] not in ("added", "plugin"):
            continue
        for name, server in settings["servers"].items():
            places = [(None, own_state(rules["global"], name, None), f"servers.{name}")]
            # Only projects with a rule of their own for the server can change it.
            ruled = [k for k in known if own_state(rules["projects"].get(k), name, None)]
            for project in known:
                chain = project_chain(project, home, ruled) if ruled else []
                if chain:
                    state = state_in(settings, chain, name, None)
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


def _states(settings: dict, server: str, tool: str | None, chain: list[str]) -> dict:
    """A server's or a tool's state along the picked project's chain (the picked project
    first; empty for all projects); whether the picked project's own rule makes it differ from
    what the project would get without that rule; and the folder name of the project it would
    then follow (None: all projects)."""
    own = own_state(settings["rules"]["projects"].get(chain[0]), server, tool) if chain else None
    without = state_in(settings, chain[1:], server, tool)
    by = deciding_project(settings, chain[1:], server, tool)
    return {
        "state": own or without,
        "differs": own is not None and own != without,
        "follows": Path(by).name if by else None,
    }


def held_servers(settings: dict, chain: list[str]) -> list[dict]:
    """Every server in the Kitden gateway, for its card: name, local or remote, and its state
    along the picked project's chain (empty: all projects). Commands, addresses and env stay
    out."""
    cards = []
    for name, server in sorted(settings["servers"].items(), key=lambda pair: pair[0].lower()):
        states = _states(settings, name, None, chain)
        kind = "remote" if isinstance(server, dict) and "url" in server else "local"
        cards.append(
            {"name": name, "kind": kind, "state": states["state"], "differs": states["differs"]}
        )
    return cards


# Words in a tool's name that suggest it changes something. A guess: the page says so.
WRITE_VERBS = (
    "write",
    "create",
    "delete",
    "remove",
    "update",
    "set",
    "send",
    "post",
    "put",
    "patch",
    "move",
    "rename",
    "upload",
    "execute",
    "run",
)
# Whole words of a name: runs of capitals before a capitalised word ("HTTPPost"), a word with
# its first capital ("uploadFile"), or other runs of letters and digits; `_`, `-` and `.` split.
_WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def tool_hint(tool: dict) -> tuple[str, str | None]:
    """Whether a tool reads or writes, and where that comes from: the server's hints
    ("server"), or a verb among the whole words of its name ("name"). ("unknown", None) when
    neither says."""
    hints = tool.get("annotations") or {}
    if hints.get("readOnlyHint") is True:
        return "reads", "server"
    if hints.get("readOnlyHint") is False or hints.get("destructiveHint") is True:
        return "writes", "server"
    # Other annotations, such as a title, say nothing about writing: the name may.
    said = "readOnlyHint" in hints or "destructiveHint" in hints
    if not said and any(w.lower() in WRITE_VERBS for w in _WORD.findall(tool["name"])):
        return "may write", "name"
    return "unknown", None


def tools_view(
    settings: dict, tools: dict, server: str, chain: list[str], calls: dict | None = None
) -> dict:
    """A held server's state and its known tools, each with its state, along the picked
    project's chain (empty: all projects). A tool is new when the server is strict and no rule
    of the chain or for all projects has a state for it: it waits, off, until someone decides.
    `calls` is what `load_calls` gives; each tool carries its count and last time, or None."""
    strict = strict_mode(settings, server)
    scopes = _scopes(settings, chain)
    counted = (calls or {}).get(server, {})
    return {
        "server": server,
        **_states(settings, server, None, chain),
        "strict": strict,
        "tools": [
            {
                "name": tool["name"],
                **dict(zip(("hint", "hint_from"), tool_hint(tool), strict=True)),
                "description": tool.get("description") or "",
                "calls": counted.get(tool["name"]),
                "new": strict and all(own_state(r, server, tool["name"]) is None for r in scopes),
                **_states(settings, server, tool["name"], chain),
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


def rules_steps(home: Path, params: dict, projects: dict[str, str]) -> list[Step]:
    """The change one batch switch makes: `params` has server, tools (a list of names), state
    ("on" or "off") and project (an id; None: all projects). One rule step per tool, checked
    as `rule_steps` checks one switch."""
    tools, state = params.get("tools"), params.get("state")
    if not isinstance(tools, list) or not tools or not all(isinstance(t, str) for t in tools):
        raise ValueError("Choose at least one tool.")
    if state not in ("on", "off"):
        raise ValueError("Choose on or off.")
    names = dict.fromkeys(tools)  # each tool once, in order
    return [s for tool in names for s in rule_steps(home, {**params, "tool": tool}, projects)]


def strict_steps(home: Path, params: dict, tools: dict[str, list[dict]]) -> list[Step]:
    """The change the strict switch makes: `params` has server and state ("on" or "off").

    On writes the mode and a global on for every known tool without a global rule of its own,
    whatever the server's state, so no project goes dark; a new tool then waits. A global off
    stays, and project rules still come first. Off removes the mode only."""
    server, state = params.get("server"), params.get("state")
    settings = load_settings(home)
    if not isinstance(server, str) or server not in settings["servers"]:
        raise ValueError("Choose a server in the Kitden gateway.")
    if state not in ("on", "off"):
        raise ValueError("Choose on or off.")
    if state == "off":
        return [strict_step(home, server, False)]
    return [
        strict_step(home, server, True),
        *(
            rule_step(home, None, server, t["name"], "on")
            for t in tools.get(server, [])
            if own_state(settings["rules"]["global"], server, t["name"]) is None
        ),
    ]


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
    except (IndexError, ValueError):  # a key too short to be a rule, or not a rule
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
