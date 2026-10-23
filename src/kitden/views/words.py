"""The words the pages say, in one place. `STATE_WORDS` is the twin of parts.js STATE_WORDS."""

# A cell's state, as the Library, Details and the After chips say it.
STATE_WORDS: dict[str, str] = {
    "on": "Available",
    "off": "Off",
    "unk": "Unknown",
    "gw": "Via gateway",
    "via": "Via Claude Code",
    "done": "Has its skills",
    "unread": "Could not read",
}

# What Kitden could not read: a whole client, or one file on its first read. An add or a change
# into such a file is refused, in words that follow the action.
CLIENT_UNREAD = "Could not read {}."
NOT_SHOWN = "Could not read {}; its items are not shown."
NO_ADD_UNREAD = "Can't add while {} can't be read."
CHANGE_UNREAD = "Can't change this while {} can't be read."

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

# Where a cell's items apply, said in a project view: a project item that wins over an
# all-projects one is a "project override". With All projects picked a cell says none.
ORIGIN_WORDS: dict[str | None, str] = {
    None: "all projects",
    "project": "this project",
    "override": "project override",
}

# How a client gets an item: the hover text and Details say it, never the cell's word slot.
ROUTE_WORDS: dict[str, str] = {
    "desktop": "from the Desktop app",
    "kitden": "through the Kitden gateway",
    "plugin": "from a plugin",
    "folder": "through {}'s folder",
}
