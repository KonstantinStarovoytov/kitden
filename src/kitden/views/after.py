"""What each client shows after a change: the first line of the review (feature 004)."""

import os
from pathlib import Path

from kitden.changes.actions import claude_allows_kitden
from kitden.changes.json_splice import ABSENT
from kitden.clients.base import SETUP_NAME
from kitden.local_gateway.project import project_chain
from kitden.local_gateway.settings import CLIENT as KITDEN
from kitden.local_gateway.settings import (
    deciding_project,
    load_settings,
    moved_in,
    own_state,
    rule_parts,
    state_in,
)
from kitden.model import GATEWAY_CLIENT, Change, ItemKind, Scope
from kitden.views.effective import effective_view
from kitden.views.setup_server import CLIENTS, kitden_on, setup_server_state

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


def _is(words: list[str]) -> str:
    return "is" if len(words) == 1 else "are"


def _kitden_rules(change: Change) -> dict[str, dict]:
    """The gateway rules a move writes: server -> (project, tool) -> (state, the clients it
    comes from). None stands for all projects or for the whole server."""
    rules: dict[str, dict] = {}
    for step in change.steps:
        key = step.edit.key if step.client == KITDEN and step.edit is not None else ()
        if key[:1] != ("rules",):
            continue
        project, server, tool = rule_parts(key)
        rules.setdefault(server, {})[(project, tool)] = (step.edit.after, step.carried_from)
    return rules


def _had_on(change: Change, name: str, project: str | None) -> set[str]:
    """The clients whose moved entry had the server on there: a user entry that was on (Codex
    can turn one off), or a local-scope entry of that project."""
    clients = set()
    for step in change.steps:
        edit = step.edit
        removes = edit is not None and edit.after is ABSENT
        if step.client not in CLIENTS or step.name != name or not removes:
            continue
        on = not (isinstance(edit.before, dict) and edit.before.get("enabled") is False)
        where = step.cwd if step.scope is Scope.LOCAL else None
        if on and where in (None, project):
            clients.add(step.client)
    return clients


def _server_words(change: Change, name: str, rules: dict) -> tuple[list[str], bool]:
    """What the carried rules do to one moved server, and whether it ends up off everywhere.

    A rule has no per-client form, so an off a client had reaches every client; the words say
    so when it turns off what another client had on."""

    def who(clients: tuple[str, ...]) -> str:
        return _join([CLIENT_WORDS[c] for c in CLIENTS if c in clients])

    def place(project: str | None) -> str:
        return "in every client" if project is None else f"in {Path(project).name} for every client"

    words = []
    state, source = rules.get((None, None), ("on", ()))
    ons = [p for (p, tool), (s, _) in rules.items() if p and tool is None and s == "on"]
    if state == "off":
        if _had_on(change, name, None) - set(source):
            where = " outside its project" if ons else ""
            words.append(f"{name} will be off in every client{where}, as {who(source)} had it.")
        elif ons:
            words.append(f"{name} is on only in its project{'s' if len(ons) > 1 else ''}.")
        else:
            words.append(f"{name} stays off, as it was.")
        if not ons:
            return words, True
    tools: dict[tuple, list[str]] = {}
    for (project, tool), (s, source) in rules.items():
        if s != "off" or (project, tool) == (None, None):
            continue
        changed = bool(_had_on(change, name, project) - set(source))
        if tool is None and project is not None and state != "off":
            folder = Path(project).name
            words.append(
                f"{name} will be off {place(project)}, as {who(source)} had it."
                if changed
                else f"{name} stays off in {folder}, as it was."
            )
        elif tool is not None and changed:
            tools.setdefault((project, source), []).append(tool)
    for (project, source), names in tools.items():
        off = f"{_join(names)} of {name} will be off {place(project)}"
        words.append(f"{off}, as {who(source)} had it.")
    return words, False


def _offering(inventory) -> set[str]:
    """The clients whose `kitden` entry is on: they offer the Kitden gateway's tools."""
    return {s["client"] for s in setup_server_state(inventory) if kitden_on(s)}


def _kitden_move_words(change: Change, inventory, home: Path | None) -> list[dict]:
    """A move into the Kitden gateway: every client with the `kitden` entry offers the moved
    tools, also one that did not have the server. One line says which, what the rules carried
    over from the clients do, and which servers the gateway had already."""
    offering = _offering(inventory)
    offering |= {s.client for s in change.steps if s.client in CLIENTS and s.name == SETUP_NAME}
    leaving = [s for s in change.steps if s.client in CLIENTS and s.name != SETUP_NAME]
    removed = {s.client for s in leaving}
    written = moved_in(change)
    servers = list(dict.fromkeys([*written, *(s.name for s in leaving)]))
    # A held server is updated when its entry was there before, and kept when it is the same.
    updated = [
        s.edit.key[1]
        for s in change.steps
        if s.client == KITDEN
        and s.edit is not None
        and s.edit.key[0] == "servers"
        and s.edit.before not in (ABSENT, None)
    ]
    kept = [name for name in servers if name not in written]
    known = [p.path for p in inventory.projects]
    settings = load_settings(home) if home is not None else None
    rules = _kitden_rules(change)
    said, offered = [], []
    held = {*updated, *kept}
    for name in servers:
        if settings is not None and name in held:
            words, off = _held_words(name, settings, known)
        else:
            words, off = _server_words(change, name, rules.get(name, {}))
        said += words
        if not off:
            offered.append(name)
    out = []
    for client in CLIENTS:
        if client in offering:
            word = "Via Kitden gateway" if offered else "Off"
            out.append({"client": client, "state": "gw" if offered else "off", "word": word})
        elif client in removed:
            out.append({"client": client, "state": "off", "word": "Removed"})
    if not out:
        return out
    line = []
    if offering and offered:
        who = _join([CLIENT_WORDS[c] for c in CLIENTS if c in offering])
        whose = "its" if len(servers) == 1 else "their"
        what = f"{whose} tools" if offered == servers else f"the tools of {_join(offered)}"
        line.append(f"{who} will offer {what} through Kitden.")
    if updated:
        line.append(f"{_join(updated)} in the Kitden gateway {_is(updated)} updated.")
    if kept:
        line.append(f"{_join(kept)} {_is(kept)} in the Kitden gateway already.")
    line += said
    new = [name for name in offered if name not in kept]
    if new and "claude_code" in offering and home and claude_allows_kitden(home, known):
        line.append(
            "Claude Code allows every Kitden tool without asking; after the move that includes "
            f"the tools of {_join(new)}."
        )
    for step in change.steps:
        edit = step.edit
        if (
            step.client == KITDEN
            and edit is not None
            and edit.key[0] == "servers"
            and isinstance(edit.after, dict)
            and edit.after.get("url")
        ):
            line.append(f"Kitden asked {edit.key[1]} once whether it needs a sign-in.")
    line.append("Applies to new sessions.")
    out[0]["note"] = " ".join(line)
    # Each client whose own switches for the servers do not carry over says so.
    for entry in out:
        client = entry["client"]
        left = list(
            dict.fromkeys(s.name for s in leaving if s.client == client and s.switches_left)
        )
        notes = [entry.get("note")]
        if client == "cursor" and client in removed:
            notes.append(CURSOR_SWITCHES)
        if left:
            notes.append(
                f"{CLIENT_WORDS[client]}'s own switches for {_join(left)} do not carry over; "
                "the gateway keeps its rules."
            )
        if any(notes):
            entry["note"] = " ".join(n for n in notes if n)
    return out


def _held_words(name: str, settings: dict, known: list[str]) -> tuple[list[str], bool]:
    """What the gateway's own rules, which stay, do to a server it holds already, and whether
    it is off everywhere."""
    rules = settings["rules"]
    everywhere = own_state(rules["global"], name, None) or "on"
    other = [
        Path(p).name
        for p in known
        if own_state(rules["projects"].get(p), name, None) not in (None, everywhere)
    ]
    if everywhere == "on":
        return ([f"{name} stays off in {_join(other)}."] if other else []), False
    if other:
        return [f"{name} is on only in {_join(other)}."], False
    return [f"{name} stays off in every client."], True


RULE_WORDS = {"on": "On", "off": "Off"}


def _rule_words(change: Change, inventory, home: Path) -> list[dict]:
    """One switch of the Kitden gateway: what the server or tool will be in each client that
    offers the gateway's tools, and one line that says it with the project. Rules are read along
    the project's chain, as the gateway reads them (see `project_chain`): following all
    projects, it is what the projects around it or all projects have."""
    edit = change.steps[0].edit
    assert edit is not None
    project, server, tool = rule_parts(edit.key)
    settings = load_settings(home)
    projects = settings["rules"]["projects"]
    known = [p.path for p in inventory.projects]
    chain = project_chain(project, home, known) if project else []
    what = server if tool is None else f"{tool} of {server}"
    where = "all projects" if project is None else Path(project).name
    if edit.after is ABSENT:  # only a project follows all projects
        rest = [p for p in chain if p != project]
        state = state_in(settings, rest, server, tool)
        by = deciding_project(settings, rest, server, tool)
        source = "all projects" if by is None else Path(by).name
        word = f"Follows {source}"
        line = f"{what} will be {state} in {where}, as in {source}"
    else:
        state, word = edit.after, RULE_WORDS[edit.after]
        line = f"{what} will be {state} in {where}"
    if tool is not None and state == "on" and state_in(settings, chain, server, None) == "off":
        line += f", but {server} is off there"
    line += "."
    if project is None:
        # A project's own rule keeps its state; the words name each one that differs.
        kept = [p for p in known if own_state(projects.get(p), server, tool) not in (None, state)]
        if kept:
            other = "off" if state == "on" else "on"
            which = "which has its own rule" if len(kept) == 1 else "which have their own rules"
            line += f" It stays {other} in {_join([Path(p).name for p in kept])}, {which}."
    clients = [c for c in CLIENTS if c in _offering(inventory)]
    if not clients:
        return [{"note": f"{line} No client uses the Kitden gateway yet."}]
    out = [{"client": c, "state": state, "word": word} for c in clients]
    out[0]["note"] = f"{line} Applies to new sessions."
    return out


def after_words(
    change: Change,
    inventory,
    cursor_imports: bool = False,
    skills: list[dict] | None = None,
    home: Path | None = None,
) -> list[dict]:
    """One entry per client: {"client", "state", "word"}, in step order.

    With `cursor_imports` (Cursor loads Claude Code's plugins), a plugin added to Claude Code
    names Cursor last, with a note. `skills` are the skill list's rows a skill copy takes.
    `home` is the folder whose Kitden gateway and Claude Code settings a change to the Kitden
    gateway reads.
    """
    if change.action in ("skill.install", "plugin.skills") and change.steps:
        return _skill_words(change, inventory, skills or [])
    if change.action == "gateway.rule" and home is not None:
        return _rule_words(change, inventory, home)
    # A move into a registered gateway has that gateway's own step; one into the Kitden
    # gateway has none, also when the gateway holds the server already.
    if change.action == "gateway.move" and not any(
        s.client == GATEWAY_CLIENT for s in change.steps
    ):
        return _kitden_move_words(change, inventory, home)
    out: list[dict] = []
    # The gateway a server moves into; a client reaches the server only through an entry for it.
    target = next((s.gateway.gateway_id for s in change.steps if s.gateway is not None), None)
    for step in change.steps:
        if step.client == GATEWAY_CLIENT or any(e["client"] == step.client for e in out):
            continue
        state, word = WORDS.get(change.action, ("on", "Changed"))
        if change.action == "gateway.move" and not any(
            i.client == step.client and i.via_gateway == target for i in inventory.items
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
