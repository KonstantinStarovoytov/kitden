"""What each client shows after a change: the first line of the review (feature 004)."""

from kitden.model import GATEWAY_CLIENT, Change, ItemKind
from kitden.views.effective import effective_view

# Socket state and word per action, as on the Load map.
WORDS = {
    "plugin.enable": ("on", "Loads"),
    "plugin.disable": ("off", "Off"),
    "mcp.remove_direct": ("off", "Removed"),
    "gateway.connect": ("gw", "Via gateway"),
    "gateway.move": ("gw", "Via gateway"),
    "gateway.switch": ("gw", "Via the new gateway"),
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
    return out
