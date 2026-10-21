"""The local gateway's settings, rules and tool cache.

The settings file holds the servers and the rules. It changes only through the change engine
(preview, Apply with a backup, verify, Undo). The tool cache holds what each server answered to
`tools/list`; it is found data, so Rescan and the gateway write it directly.

Rules: for each server "on" or "off", and a state for each tool. A project's rule wins over the
global rule; with no rule a server or a tool is on.
"""

import json
from pathlib import Path
from typing import Any

from kitden.changes.atomic import write_atomic
from kitden.changes.json_splice import ABSENT
from kitden.gateways import data_dir
from kitden.model import FileEdit, Scope, Step

SETTINGS_FILE = "gateway.json"
TOOLS_FILE = "gateway-tools.json"
CLIENT = "kitden"
STATES = ("on", "off")


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _read(path: Path) -> dict:
    try:
        return _dict(json.loads(path.read_text()))
    except (OSError, ValueError):
        return {}


def load_settings(home: Path) -> dict:
    """The gateway's servers and rules; a missing or unreadable file reads as empty."""
    data = _read(data_dir(home) / SETTINGS_FILE)
    rules = _dict(data.get("rules"))
    return {
        **data,
        "servers": _dict(data.get("servers")),
        "rules": {"global": _dict(rules.get("global")), "projects": _dict(rules.get("projects"))},
    }


def load_tools(home: Path) -> dict[str, list[dict]]:
    """Each server's known tools, by server name. Entries that are not tools are left out."""
    data = _read(data_dir(home) / TOOLS_FILE)
    return {
        server: [t for t in tools if isinstance(t, dict) and isinstance(t.get("name"), str)]
        for server, tools in data.items()
        if isinstance(tools, list)
    }


def save_tools(home: Path, server: str, tools: list[dict]) -> None:
    """Replace one server's known tools. Each is kept as name, description and inputSchema."""
    folder = data_dir(home)
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)
    cache = load_tools(home)
    cache[server] = [
        {
            "name": tool["name"],
            "description": tool.get("description") or "",
            "inputSchema": tool.get("inputSchema") or {"type": "object"},
        }
        for tool in tools
    ]
    write_atomic(folder / TOOLS_FILE, json.dumps(cache, indent=2).encode())


def _is_on(scopes: list[dict], server: str, tool: str | None) -> bool:
    """The first scope that has a state decides; with none, it is on."""
    for rules in scopes:
        entry = _dict(rules.get(server))
        state = entry.get("server") if tool is None else _dict(entry.get("tools")).get(tool)
        if state in STATES:
            return state == "on"
    return True


def allowed_tools(settings: dict, tools: dict, project: str | None) -> dict[str, list[dict]]:
    """For each gateway server that is on, its known tools that are on, for this project.

    A rule for a tool the server no longer has does nothing; a tool the server adds is on.
    """
    rules = _dict(settings.get("rules"))
    scopes = [_dict(rules.get("global"))]
    if project is not None:
        scopes.insert(0, _dict(_dict(rules.get("projects")).get(project)))
    offered = {}
    for server in _dict(settings.get("servers")):
        if server in tools and _is_on(scopes, server, None):
            offered[server] = [t for t in tools[server] if _is_on(scopes, server, t["name"])]
    return offered


def rule_step(
    home: Path, project: str | None, server: str, tool: str | None, state: str | None
) -> Step:
    """One rule as a change step. `project` None is the global rule, `tool` None the server's.

    `state` None removes the rule: a project then follows the global rule.
    """
    if state not in (*STATES, None):
        raise ValueError("A rule is on or off")
    where = ("global",) if project is None else ("projects", project)
    what = ("server",) if tool is None else ("tools", tool)
    edit = FileEdit(
        path=str(data_dir(home) / SETTINGS_FILE),
        fmt="json",
        key=("rules", *where, server, *what),
        after=ABSENT if state is None else state,
        check="entry",
    )
    return Step(client=CLIENT, scope=Scope.USER, name=tool or server, edit=edit)
