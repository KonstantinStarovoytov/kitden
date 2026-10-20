"""What each client shows after a change: the first line of the review (feature 004)."""

from kitden.model import GATEWAY_CLIENT, Change, ItemKind, Scope
from kitden.views.effective import effective_view

SKILL_CLIENTS = ("claude_code", "codex", "cursor")
CLIENT_WORDS = {"claude_code": "Claude Code", "codex": "Codex", "cursor": "Cursor"}
CURSOR_IMPORT = {
    "client": "cursor",
    "state": "on",
    "word": "Loads",
    "note": "Cursor loads Claude Code plugins, so it gets this one too.",
}

# Socket state and word per action, as on the Load map.
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


def _other_copy_loads(inventory, client: str, name: str) -> bool:
    """True when the client loads another copy of the plugin, so one copy keeps loading."""
    short = name.split("@", 1)[0]
    copies = [
        i
        for i in effective_view(inventory, client, None).items
        if i.kind is ItemKind.PLUGIN and i.name.split("@", 1)[0] == short
    ]
    return len(copies) > 1


def _skill_words(change: Change, inventory) -> list[dict]:
    """Every client that will load the skills, and twice when it reads two folders that hold
    one of them: a copy made here or one it already has."""
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


def after_words(change: Change, inventory, cursor_imports: bool = False) -> list[dict]:
    """One entry per client: {"client", "state", "word"}, in step order.

    With `cursor_imports` (Cursor loads Claude Code's plugins), a plugin added to Claude Code
    names Cursor last, with a note.
    """
    if change.action in ("skill.install", "plugin.skills") and change.steps:
        return _skill_words(change, inventory)
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
