"""What each client shows after a change: the first line of the review (feature 004)."""

import os

from kitden.clients.base import SETUP_NAME
from kitden.local_gateway.settings import CLIENT as KITDEN
from kitden.model import GATEWAY_CLIENT, Change, ItemKind, Scope
from kitden.views.effective import effective_view
from kitden.views.setup_server import CLIENTS, setup_server_state

SKILL_CLIENTS = ("claude_code", "codex", "cursor")
CLIENT_WORDS = {"claude_code": "Claude Code", "codex": "Codex", "cursor": "Cursor"}
CURSOR_IMPORT = {
    "client": "cursor",
    "state": "on",
    "word": "Loads",
    "note": "Cursor loads Claude Code plugins, so it gets this one too.",
}

# Socket state and word per action, as the Library shows them.
WORDS = {
    "plugin.enable": ("on", "Loads"),
    "plugin.disable": ("off", "Off"),
    "mcp.remove_direct": ("off", "Removed"),
    "gateway.connect": ("gw", "Via gateway"),
    "gateway.move": ("gw", "Via gateway"),
    "gateway.switch": ("gw", "Via the new gateway"),
    "plugin.install": ("on", "Loads"),
    "marketplace.add": ("on", "Added"),
    "setup_server.register": ("on", "Added"),
    "setup_server.update": ("on", "Updated"),
}
CURSOR_SWITCHES = "Cursor's own switches for these tools do not carry over."


def _other_copy_loads(inventory, client: str, name: str) -> bool:
    """True when the client loads another copy of the plugin, so one copy keeps loading."""
    short = name.split("@", 1)[0]
    copies = [
        i
        for i in effective_view(inventory, client, None).items
        if i.kind is ItemKind.PLUGIN and i.name.split("@", 1)[0] == short
    ]
    return len(copies) > 1


def _skill_words(change: Change, inventory, skills: list[dict]) -> list[dict]:
    """Every client that will load the skills, and twice when it reads two folders that hold
    one of them: a copy made here or one it already has.

    `skills` are the skill list's rows of the copied skills. A client they say loads one from a
    plugin has one copy already: the scan has no items for the skills inside Cursor's plugins.
    """
    names = list(dict.fromkeys(step.name for step in change.steps))
    loads: dict[str, dict[str, int]] = {}  # client -> skill -> how many copies it loads
    for item in inventory.items:
        loads_now = (
            item.kind is ItemKind.SKILL
            and item.scope in (Scope.USER, Scope.PLUGIN)
            and item.name in names
        )
        if loads_now:
            loads.setdefault(item.client, {})[item.name] = 1
    # The review keeps each source by its real path.
    by_path = {os.path.realpath(skill["path"]): skill for skill in skills}
    for step in change.steps:
        skill = by_path.get(os.path.realpath(step.copy.source)) if step.copy else None
        for client, word in (skill["installed"] if skill else {}).items():
            if word == "Via plugin":
                loads.setdefault(client, {})[step.name] = 1
    for step in change.steps:
        for client in step.copy.readers if step.copy else []:
            copies = loads.setdefault(client, {})
            copies[step.name] = copies.get(step.name, 0) + 1
    out = []
    for client in SKILL_CLIENTS:
        if not loads.get(client):
            continue
        entry = {"client": client, "state": "on", "word": "Loads"}
        twice = [name for name in names if loads[client].get(name, 0) > 1]
        if twice:
            entry["word"] = "Loads twice"
            who = CLIENT_WORDS[client]
            if len(names) == 1:
                entry["note"] = (
                    f"{who} reads two folders that hold this skill, so it loads the skill twice."
                )
            else:
                entry["note"] = f"{who} would load {', '.join(twice)} twice, from two folders."
        out.append(entry)
    return out


def _join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


def _kitden_move_words(change: Change, inventory) -> list[dict]:
    """A move into the Kitden gateway: every client with the `kitden` entry offers the moved
    tools, also one that did not have the server. One line says which, and where a moved
    server is on only in its project or stays off."""
    offering = {
        s["client"]
        for s in setup_server_state(inventory)
        if s["state"] in ("added", "plugin") and s["enabled"] is not False
    }
    offering |= {s.client for s in change.steps if s.client in CLIENTS and s.name == SETUP_NAME}
    removed = {s.client for s in change.steps if s.client in CLIENTS and s.name != SETUP_NAME}
    out = []
    for client in CLIENTS:
        if client in offering:
            out.append({"client": client, "state": "gw", "word": "Via Kitden gateway"})
        elif client in removed:
            out.append({"client": client, "state": "off", "word": "Removed"})
    if not out:
        return out
    mine = [s.edit for s in change.steps if s.client == KITDEN and s.edit is not None]
    servers = [e.key[1] for e in mine if e.key[0] == "servers"]
    rules = {e.key: e.after for e in mine if e.key[0] == "rules"}
    line = []
    if offering:
        who = _join([CLIENT_WORDS[c] for c in CLIENTS if c in offering])
        whose = "its" if len(servers) == 1 else "their"
        line.append(f"{who} will offer {whose} tools through Kitden.")
    for name in servers:
        if rules.get(("rules", "global", name, "server")) != "off":
            continue
        projects = [
            key
            for key, state in rules.items()
            if key[1:2] == ("projects",) and key[3:] == (name, "server") and state == "on"
        ]
        if projects:
            line.append(f"{name} is on only in its project{'s' if len(projects) > 1 else ''}.")
        else:
            line.append(f"{name} stays off, as it was.")
    line.append("Applies to new sessions.")
    out[0]["note"] = " ".join(line)
    if "cursor" in removed:
        entry = next(e for e in out if e["client"] == "cursor")
        entry["note"] = " ".join(n for n in (entry.get("note"), CURSOR_SWITCHES) if n)
    return out


def after_words(
    change: Change, inventory, cursor_imports: bool = False, skills: list[dict] | None = None
) -> list[dict]:
    """One entry per client: {"client", "state", "word"}, in step order.

    With `cursor_imports` (Cursor loads Claude Code's plugins), a plugin added to Claude Code
    names Cursor last, with a note. `skills` are the skill list's rows a skill copy takes.
    """
    if change.action in ("skill.install", "plugin.skills") and change.steps:
        return _skill_words(change, inventory, skills or [])
    if change.action == "gateway.move" and any(s.client == KITDEN for s in change.steps):
        return _kitden_move_words(change, inventory)
    out: list[dict] = []
    for step in change.steps:
        if step.client == GATEWAY_CLIENT or any(e["client"] == step.client for e in out):
            continue
        state, word = WORDS.get(change.action, ("on", "Changed"))
        # A moved server reaches the client only if the client has a gateway entry.
        if change.action == "gateway.move" and not any(
            i.client == step.client and i.via_gateway for i in inventory.items
        ):
            state, word = "off", "Removed"
        if change.action == "plugin.disable" and _other_copy_loads(
            inventory, step.client, step.name
        ):
            state, word = "on", "Loads once"
        out.append({"client": step.client, "state": state, "word": word})
    to_claude = any(s.client == "claude_code" for s in change.steps)
    if change.action == "plugin.install" and to_claude and cursor_imports:
        out.append(dict(CURSOR_IMPORT))
    return out
