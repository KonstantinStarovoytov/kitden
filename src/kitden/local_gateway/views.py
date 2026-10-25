"""The Kitden gateway in Kitden's views: its servers in each client, their tools and rules.

The MCP SDK loads only when a server is asked for its tools: the page must start without it.
"""

import asyncio
import importlib
import re
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

from kitden.changes.actions import GATEWAY_RULE, KITDEN_GATEWAY, secrets_out
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
    what the project would get without that rule; the folder name of the project it would
    then follow (None: all projects); and where the state comes from (`origin`): the picked
    project, a parent project (`origin_from` names its folder), all projects, a new tool of a
    strict server, or the default."""
    own = own_state(settings["rules"]["projects"].get(chain[0]), server, tool) if chain else None
    without = state_in(settings, chain[1:], server, tool)
    by = deciding_project(settings, chain[1:], server, tool)
    if own is not None:
        origin = "project"
    elif by:
        origin = "parent"
    elif own_state(settings["rules"]["global"], server, tool) is not None:
        origin = "global"
    elif tool is not None and strict_mode(settings, server):
        origin = "strict"
    else:
        origin = "default"
    return {
        "state": own or without,
        "differs": own is not None and own != without,
        "follows": Path(by).name if by else None,
        "origin": origin,
        "origin_from": Path(by).name if origin == "parent" else None,
    }


def _effective(state: str, server_on: bool) -> dict:
    """A tool's state with its server's switch: a tool of a server that is off is off."""
    return {"effective": state} if server_on else {"effective": "off", "why": "server_off"}


def _ruled(rules: Any, server: str) -> list[str | None]:
    """What one scope of rules sets a state for: the server (None) and each of its tools."""
    entry = rules.get(server) if isinstance(rules, dict) else None
    tools = entry.get("tools") if isinstance(entry, dict) else None
    names = [None, *(tools if isinstance(tools, dict) else {})]
    return [name for name in names if own_state(rules, server, name) is not None]


def own_rules(settings: dict, chain: list[str]) -> int:
    """How many states the picked project (`chain[0]`) sets that differ from what it would
    get without them: its server switches and tool states, over all held servers. 0 for all
    projects."""
    if not chain:
        return 0
    rules = settings["rules"]["projects"].get(chain[0])
    return sum(
        _states(settings, server, name, chain)["differs"]
        for server in settings["servers"]
        for name in _ruled(rules, server)
    )


def tool_count(tools: dict | None, server: str) -> int | None:
    """How many tools the cache knows for a held server; None when it knows none."""
    return len((tools or {}).get(server) or []) or None


def held_servers(
    settings: dict,
    chain: list[str],
    tools: dict | None = None,
    chains: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Every server in the Kitden gateway, for its card: name, local or remote, and its state
    along the picked project's chain (empty: all projects) and where it comes from, whether
    its entry still holds a plain secret the Keychain could keep, and how many tools `tools`
    (the cache) knows for it. Commands, addresses and env stay out.

    Also its known tools with their states (`tool_list`, each with how many known projects
    have a rule of their own for it, `own_in`) and how many are on (`on_count`); with all
    projects and the server off, how many known projects turn it on (`on_in`); with a picked
    project, how many other known projects have it on (`on_elsewhere`, a folder under it by its
    rule too); and how many known projects have rules of their own for it (`projects`).
    `chains` maps every known project to its chain."""
    rules = settings["rules"]["projects"]
    known = chains or {}
    cards = []
    for name, server in sorted(settings["servers"].items(), key=lambda pair: pair[0].lower()):
        states = _states(settings, name, None, chain)
        held = isinstance(server, dict)
        server_on = states["state"] == "on"
        listed = []
        for tool in (tools or {}).get(name) or []:
            found = _states(settings, name, tool["name"], chain)
            listed.append(
                {
                    "name": tool["name"],
                    "title": tool.get("title"),
                    "state": found["state"],
                    **_effective(found["state"], server_on),
                    "hint": tool_hint(tool)[0],
                    "origin": found["origin"],
                    "origin_from": found["origin_from"],
                    "own_in": sum(
                        own_state(rules.get(p), name, tool["name"]) is not None for p in known
                    ),
                }
            )
        on_in = on_elsewhere = 0
        if not chain and not server_on:
            on_in = sum(state_in(settings, c, name, None) == "on" for c in known.values())
        if chain:
            others = [c for p, c in known.items() if p != chain[0]]
            on_elsewhere = sum(state_in(settings, c, name, None) == "on" for c in others)
        cards.append(
            {
                "name": name,
                "kind": "remote" if held and "url" in server else "local",
                "state": states["state"],
                "differs": states["differs"],
                "origin": states["origin"],
                "origin_from": states["origin_from"],
                "plain_secrets": held and bool(secrets_out(name, server)[1]),
                "tools": tool_count(tools, name),
                "tool_list": listed,
                "on_count": sum(t["effective"] == "on" for t in listed),
                "on_in": on_in,
                "on_elsewhere": on_elsewhere,
                "projects": sum(bool(_ruled(rules.get(p), name)) for p in known),
            }
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
    "edit",
    "add",
    "insert",
    "drop",
    "merge",
    "push",
    "commit",
    "apply",
    "replace",
    "archive",
    "publish",
    "approve",
    "assign",
    "invite",
    "fork",
    "close",
    "kill",
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
    # In MCP, readOnlyHint defaults to false, and the other two hints only apply to tools that
    # are not read-only: a tool that holds one of them writes.
    if any(k in hints for k in ("readOnlyHint", "destructiveHint", "idempotentHint")):
        return "writes", "server"
    # Other annotations, such as a title, say nothing about writing: the name may.
    if any(w.lower() in WRITE_VERBS for w in _WORD.findall(tool["name"])):
        return "may write", "name"
    return "unknown", None


def tools_view(
    settings: dict,
    tools: dict,
    server: str,
    chain: list[str],
    calls: dict | None = None,
    chains: dict[str, list[str]] | None = None,
) -> dict:
    """A held server's state and its known tools, each with its state, along the picked
    project's chain (empty: all projects), and where each comes from. A tool's `state` is its
    own rule's; `effective` also applies the server's switch, as in `held_servers`. A tool is
    new when the server is strict and no rule of the chain or for all projects has a state for
    it: it waits, off, until someone decides. `calls` is what `load_calls` gives; each tool
    carries its count and last time, or None. `shared` is the state all projects get, which
    "for all projects" turns the other way. `chains` maps each known project's id to its chain;
    `projects` then says the server's and each tool's state in every one of them, as the gateway
    decides it there (the rule state, without the server's switch on its tools), so "in some
    projects" offers only projects it would change, which tools have a rule of the project's own
    there (`own`, as `own_in` counts them) and whether the server has one (`own_server`)."""
    strict = strict_mode(settings, server)
    scopes = _scopes(settings, chain)
    counted = (calls or {}).get(server, {})
    states = _states(settings, server, None, chain)
    server_on = states["state"] == "on"
    listed = []
    for tool in tools.get(server, []):
        found = _states(settings, server, tool["name"], chain)
        listed.append(
            {
                "name": tool["name"],
                "title": tool.get("title"),
                **dict(zip(("hint", "hint_from"), tool_hint(tool), strict=True)),
                "description": tool.get("description") or "",
                "calls": counted.get(tool["name"]),
                "new": strict and all(own_state(r, server, tool["name"]) is None for r in scopes),
                **found,
                **_effective(found["state"], server_on),
                "shared": state_in(settings, [], server, tool["name"]),
            }
        )
    shared = state_in(settings, [], server, None)
    rules = settings["rules"]["projects"]
    projects = [
        {
            "id": project,
            "server": state_in(settings, each, server, None),
            "tools": {t["name"]: state_in(settings, each, server, t["name"]) for t in listed},
            # The project's own rules are kept by its folder, the first of its chain.
            "own": [
                t["name"]
                for t in listed
                if each and own_state(rules.get(each[0]), server, t["name"]) is not None
            ],
            "own_server": bool(each) and own_state(rules.get(each[0]), server, None) is not None,
        }
        for project, each in (chains or {}).items()
    ]
    return {
        "server": server,
        **states,
        "shared": shared,
        "strict": strict,
        "tools": listed,
        "projects": projects,
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
