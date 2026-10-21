"""The local gateway's settings, rules and tool cache.

The settings file holds the servers and the rules. It changes only through the change engine
(preview, Apply with a backup, verify, Undo). The tool cache holds what each server answered to
`tools/list`; it is found data, so Rescan and the gateway write it directly.

Rules: for each server "on" or "off", and a state for each tool. Rules are read along a chain
of known projects (see project.project_chain): the deepest project with its own state wins, then
the next, then the global rule; with no rule a server or a tool is on.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from kitden.changes.atomic import write_atomic
from kitden.changes.json_splice import ABSENT
from kitden.gateways import data_dir
from kitden.model import Change, FileEdit, Scope, Step

SETTINGS_FILE = "gateway.json"
TOOLS_FILE = "gateway-tools.json"
CLIENT = "kitden"
STATES = ("on", "off")
# A Codex entry's own start time; the move carries it and the gateway waits that long.
START_TIME = "startup_timeout_sec"
# Project folders in a local server's arguments; the gateway fills in the project it found.
PLACEHOLDERS = ("${workspaceFolder}", "${CLAUDE_PROJECT_DIR}", "${CLAUDE_PROJECT_DIR:-.}")


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


def settings_unreadable(home: Path) -> bool:
    """True when the settings file is there but is not a JSON object. It then reads as empty,
    and the page says so."""
    try:
        return not isinstance(json.loads((data_dir(home) / SETTINGS_FILE).read_text()), dict)
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        return True


def load_tools(home: Path) -> dict[str, list[dict]]:
    """Each server's known tools, by server name. Entries that are not tools are left out."""
    data = _read(data_dir(home) / TOOLS_FILE)
    return {
        server: [t for t in tools if isinstance(t, dict) and isinstance(t.get("name"), str)]
        for server, tools in data.items()
        if isinstance(tools, list)
    }


def save_tools(home: Path, server: str, tools: list[dict]) -> None:
    """Replace one server's known tools. Each is kept as name, description and inputSchema,
    and its title and annotations (the read-only and destructive hints) when it has them."""
    # No lock on purpose: the write is atomic, and a list lost in a race is written again on the
    # next start or Rescan.
    folder = data_dir(home)
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)
    cache = load_tools(home)
    cache[server] = [
        {
            "name": tool["name"],
            "description": tool.get("description") or "",
            "inputSchema": tool.get("inputSchema") or {"type": "object"},
            **{key: tool[key] for key in ("title", "annotations") if tool.get(key)},
        }
        for tool in tools
    ]
    write_atomic(folder / TOOLS_FILE, json.dumps(cache, indent=2).encode())


def own_state(rules: Any, server: str, tool: str | None) -> str | None:
    """The state one scope of rules sets for a server (`tool` None) or one of its tools, or
    None when it sets none. An empty object left by a removed rule sets none."""
    entry = _dict(_dict(rules).get(server))
    state = entry.get("server") if tool is None else _dict(entry.get("tools")).get(tool)
    return state if state in STATES else None


def strict_mode(settings: dict, server: str) -> bool:
    """Whether a server is in strict mode: a tool without a rule is off."""
    rules = _dict(_dict(settings.get("rules")).get("global"))
    return _dict(rules.get(server)).get("mode") == "strict"


def _is_on(scopes: list[dict], server: str, tool: str | None, strict: bool = False) -> bool:
    """The first scope that has a state decides. With none, it is on, except a tool of a
    strict server."""
    for rules in scopes:
        state = own_state(rules, server, tool)
        if state is not None:
            return state == "on"
    return tool is None or not strict


def _scopes(settings: dict, chain: Sequence[str]) -> list[dict]:
    """The rules to read: each project's of the chain, deepest first, then the global ones."""
    rules = _dict(settings.get("rules"))
    projects = _dict(rules.get("projects"))
    return [*(_dict(projects.get(project)) for project in chain), _dict(rules.get("global"))]


def state_in(settings: dict, chain: Sequence[str], server: str, tool: str | None) -> str:
    """The state of a server (`tool` None) or one of its tools along the chain: on or off."""
    strict = strict_mode(settings, server)
    return "on" if _is_on(_scopes(settings, chain), server, tool, strict) else "off"


def is_allowed(home: Path, chain: Sequence[str], server: str, tool: str) -> bool:
    """Whether a tool can be called now: the settings file is read again, and the server and
    the tool must both be on along the chain."""
    settings = load_settings(home)
    return state_in(settings, chain, server, None) == "on" and (
        state_in(settings, chain, server, tool) == "on"
    )


def deciding_project(
    settings: dict, chain: Sequence[str], server: str, tool: str | None
) -> str | None:
    """The first project of the chain with its own state for a server or tool; None when the
    global rule decides."""
    projects = _dict(_dict(settings.get("rules")).get("projects"))
    return next((p for p in chain if own_state(projects.get(p), server, tool)), None)


def servers_on(settings: dict, chain: Sequence[str]) -> list[str]:
    """Every gateway server that is on along the chain, whether or not its tools are known."""
    scopes = _scopes(settings, chain)
    return [server for server in _dict(settings.get("servers")) if _is_on(scopes, server, None)]


def allowed_tools(settings: dict, tools: dict, chain: Sequence[str]) -> dict[str, list[dict]]:
    """For each gateway server that is on, its known tools that are on, along the chain.

    A server whose tools are not known yet is left out (see `servers_on`). A rule for a tool the
    server no longer has does nothing; a tool the server adds is on.
    """
    scopes = _scopes(settings, chain)
    return {
        server: [
            t
            for t in tools[server]
            if _is_on(scopes, server, t["name"], strict_mode(settings, server))
        ]
        for server in servers_on(settings, chain)
        if server in tools
    }


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
    value = ABSENT if state is None else state
    return settings_step(home, ("rules", *where, server, *what), value, tool or server)


def strict_step(home: Path, server: str, on: bool) -> Step:
    """A server's strict mode as a change step; off removes the mode."""
    return settings_step(
        home, ("rules", "global", server, "mode"), "strict" if on else ABSENT, server
    )


def is_mode_key(key: tuple[str, ...]) -> bool:
    """True for the key of a server's strict mode, as strict_step makes it."""
    return len(key) == 4 and key[:2] == ("rules", "global") and key[3] == "mode"


def rule_parts(key: tuple[str, ...]) -> tuple[str | None, str, str | None]:
    """The project, server and tool of a rule's key, as rule_step makes it. None stands for
    all projects or for the whole server. Raises ValueError for a key that is not a rule, such
    as a server's strict mode, and IndexError for one too short."""
    project, rest = (None, key[2:]) if key[1] == "global" else (key[2], key[3:])
    if rest[1] not in ("server", "tools"):
        raise ValueError("Not a rule")
    return project, rest[0], (rest[2] if rest[1] == "tools" else None)


def moved_in(change: Change) -> list[str]:
    """The servers a change adds to the gateway's settings."""
    return [
        step.edit.key[1]
        for step in change.steps
        if step.client == CLIENT and step.edit is not None and step.edit.key[0] == "servers"
    ]


def settings_step(home: Path, key: tuple[str, ...], value: Any, name: str) -> Step:
    """One entry of the settings file as a change step; ABSENT removes it."""
    edit = FileEdit(
        path=str(data_dir(home) / SETTINGS_FILE), fmt="json", key=key, after=value, check="entry"
    )
    return Step(client=CLIENT, scope=Scope.USER, name=name, edit=edit)
