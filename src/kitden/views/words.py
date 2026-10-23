"""The words the pages say, in one place. `STATE_WORDS` is the twin of parts.js STATE_WORDS."""

# A cell's state, as the Library, Details and the After chips say it.
STATE_WORDS: dict[str, str] = {
    "on": "Available",
    "off": "Off",
    "unk": "Unknown",
    "gw": "Via gateway",
    "via": "Via Claude Code",
    "done": "Has its skills",
}

# Socket state and word per action, as the Library shows them after the change. "Removed",
# "Added", "Updated" and "Via the new gateway" say what the change did, not a state.
AFTER_WORDS: dict[str, tuple[str, str]] = {
    "plugin.enable": ("on", STATE_WORDS["on"]),
    "plugin.disable": ("off", STATE_WORDS["off"]),
    "mcp.remove_direct": ("off", "Removed"),
    "plugin.remove": ("off", "Removed"),
    "skill.remove": ("off", "Removed"),
    "gateway.connect": ("gw", STATE_WORDS["gw"]),
    "gateway.move": ("gw", STATE_WORDS["gw"]),
    "gateway.switch": ("gw", "Via the new gateway"),
    "plugin.install": ("on", STATE_WORDS["on"]),
    "marketplace.add": ("on", "Added"),
    "setup_server.register": ("on", "Added"),
    "setup_server.update": ("on", "Updated"),
}
