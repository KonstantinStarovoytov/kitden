"""The words the pages say, in one place. `STATE_WORDS` is the twin of parts.js STATE_WORDS."""

# A cell's state, as the Library, Details and the After chips say it.
STATE_WORDS: dict[str, str] = {
    "on": "On",
    "off": "Off",
    "unk": "Unknown",
    "review": "Needs review",
    "gw": "Via gateway",
    "via": "Via Claude Code",
    "done": "Has its skills",
    "unread": "Could not read",
    "missing": "Not installed",
}

# What Kitden could not read: a whole client, or one file on its first read. An add or a change
# into such a file is refused, in words that follow the action.
CLIENT_UNREAD = "Could not read {}."
NOT_SHOWN = "Could not read {}; its items are not shown."
NO_ADD_UNREAD = "Can't add while {} can't be read."
CHANGE_UNREAD = "Can't change this while {} can't be read."
# A cell whose items were kept from the last good read of a file that now fails; the time is
# this Mac's clock, "14:02".
STALE = "From the last good read at {}"
# A change to a definition kept from the last good read: its file must read well first.
KEPT_UNREAD = "Kitden can't change this until it reads {} again."
# A client whose item has the name of another client's but another command, address or skill
# files. No add in such a row: it would copy one side without asking.
NOT_SAME = "Same name, another source."
NO_ADD_REVIEW = "Same name, another source: decide first."

# What only one project has. Its skill adds into that project; its MCP server has no add (a
# project MCP write needs each client's project file, checked with a date: Later).
NO_PROJECT_SERVER = "Kitden adds MCP servers for all projects only."
ONLY_IN_PROJECT = "This skill is in one project only. Pick that project to add it."
PROJECT_TRUST = "To add it to {name}, trust {name} in Codex first."

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
    "setup_server.enable": ("on", STATE_WORDS["on"]),
    "client.disconnect": ("off", "Removed"),
    "gateway.add": ("gw", STATE_WORDS["gw"]),
}

# A change to the Kitden gateway when no client has its `kitden` entry on.
NO_GATEWAY_CLIENT = "No client uses the Kitden gateway yet."

# The tag a cell carries in a project view: "This project" when the project's own settings
# decide it (a project item that wins over a shared one), "Only this project" for an item only
# that project has. A cell that follows the shared setup carries none, and so does every cell
# with All projects picked. The twin of parts.js ORIGIN_WORDS.
ORIGIN_WORDS: dict[str, str] = {
    "override": "This project",
    "project": "Only this project",
}

# Why a change to one client's definition reaches another client too: Details says it before
# any action, and the After chips say the plugin one.
READS_FOLDER = "{reader} reads {owner}'s folder"
LOADS_PLUGINS = "Cursor loads Claude Code's plugins"

# What Undo of a removed Claude Code plugin cannot bring back: uninstall keeps the data folder
# (--keep-data) but not the plugin's saved options. The review's lede says it once.
REMOVE_NOTE = "Undo installs it again; its saved options are not brought back."
# The review's lede, when every step is in one project and no other known project lies inside
# or around it (views/review.py `others_unchanged`). The twin of review.js UNCHANGED.
UNCHANGED = "Other projects are unchanged."
# What Undo of a change that replaced a Keychain item's value cannot bring back: the old value is
# recorded nowhere (engine.py undo). "{}" names the item, "github/TOKEN", or the items.
KEYCHAIN_UNDO = "After Undo, {} in your Keychain keeps its new value."
KEYCHAIN_UNDO_MANY = "After Undo, {} in your Keychain keep their new values."

# How a client gets an item: the hover text and Details say it, never the cell's word slot.
ROUTE_WORDS: dict[str, str] = {
    "desktop": "from the Desktop app",
    "kitden": "through the Kitden gateway",
    "plugin": "from a plugin",
    "folder": "through {}'s folder",
}
