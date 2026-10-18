"""What each client shows after a change: the first line of the review (feature 004)."""

from kitden.model import Change, ItemKind
from kitden.views.effective import effective_view

# Socket state and word per action, as on the Load map.
WORDS = {
    "plugin.enable": ("on", "Loads"),
    "plugin.disable": ("off", "Off"),
    "mcp.remove_direct": ("off", "Removed"),
    "gateway.connect": ("gw", "Via gateway"),
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


def after_words(change: Change, inventory) -> list[dict]:
    """One entry per client: {"client", "state", "word"}, in step order."""
    out: list[dict] = []
    for step in change.steps:
        if any(entry["client"] == step.client for entry in out):
            continue
        state, word = WORDS.get(change.action, ("on", "Changed"))
        if change.action == "plugin.disable" and _other_copy_loads(
            inventory, step.client, step.name
        ):
            state, word = "on", "Loads once"
        out.append({"client": step.client, "state": state, "word": word})
    return out
