"""The words the pages say, in one place. `STATE_WORDS` is the twin of parts.js STATE_WORDS."""


def join_words(words: list[str]) -> str:
    """ "a", "a and b", "a, b and c"; "" for none."""
    return " and ".join([", ".join(words[:-1]), words[-1]] if len(words) > 1 else words)


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

# A skill's own state besides On and Off (`Item.skill_state`), as Details says it.
SKILL_STATE_WORDS: dict[str, str] = {
    "name-only": "Name only",
    "user-invocable-only": "Only when you ask",
    "only-asked": "Only when you ask",
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
    "skill.rule": ("off", STATE_WORDS["off"]),
}

# A change to the Kitden gateway when no client has its `kitden` entry on.
NO_GATEWAY_CLIENT = "No client uses the Kitden gateway yet."

# A server that runs from a Mac app (clients/entries.py app_of): the app may write its entries
# again when it starts, so a change to them may not last. The Gateway says why a move refuses
# it, and the review says it before a removal or a move.
APP_SET_UP = "{name} is set up differently for each client by the {app} app; change it in {app}."
APP_WRITES_BACK = (
    "{name} runs from the {app} app, which may write it back. If it comes back, change it in {app}."
)
# A server a change took out of a client that is back there now: an Overview card's name and
# line. The twins of changes.js cameBackWords, which says them as two sentences.
BACK_IN = "{name} is back in {client}"
BACK_BY_APP = "The {app} app wrote it again; change it there."
BACK_BY_OTHER = "Something else on this computer wrote it again."

# The Overview card for a client whose last chat did not fit its skill list: its name and its
# line, by what happened ("name": descriptions showed only a name, "cut", "out": left out).
SKILL_LIST_IN = "Skill list in {client}"
CONTEXT_CARD_LINES = {
    "name": "{skills} showed only a name in your last {client} chat",
    "cut": "{skills} {were} cut short in your last {client} chat",
    "out": "{skills} {were} left out of your last {client} chat",
}

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
KEYCHAIN_UNDO = "After Undo, {} in your {store} keeps its new value."
KEYCHAIN_UNDO_MANY = "After Undo, {} in your {store} keep their new values."

# How a client gets an item: the hover text and Details say it, never the cell's word slot.
ROUTE_WORDS: dict[str, str] = {
    "desktop": "from the Desktop app",
    "kitden": "through the Kitden gateway",
    "plugin": "from a plugin",
    "folder": "through {}'s folder",
}

# A skill or a plugin turned off by a settings rule (`skill.rule`, spec 5.5). A refusal says why
# there is no switch; the review's note names a project whose own skill settings may win.
CURSOR_NO_SKILL_SWITCH = "Cursor has no switch to turn off one skill."
CODEX_NO_PROJECT = "Codex has no switch for one project; turn it off for all projects."
CODEX_NO_NAME_ONLY = "Codex has no Name only setting."
PLUGIN_NO_NAME_ONLY = "A plugin is On or Off; it has no Name only setting."
CODEX_SKILLS_NOT_TABLES = "Codex's skills settings are not a list of tables; Kitden leaves them."
NO_SKILL_MERGE = (
    "Claude Code may not merge skill settings across files; turn it off for all projects instead."
)
OWN_SKILL_SETTINGS = "{folder} has its own skill settings; it may keep this skill on."
# checked 2026-10-27 (code.claude.com/docs/en/settings): Claude Code adds
# `**/.claude/settings.local.json` to the global git excludes the first time it writes the file;
# a file made another way must be added to .gitignore by hand.
NEW_LOCAL_FILE = (
    "Kitden creates .claude/settings.local.json in {folder}. If git lists it, add it to .gitignore."
)
# A project in a subfolder of a repository: its rule goes in the root's local file, which Claude
# Code reads in every folder of that repository (checked 2026-10-27, same page).
REPO_RULE = (
    "Claude Code keeps this rule in {folder}'s local settings, so it holds in all of {folder}."
)
REPO_RULE_OUT = (
    "Claude Code takes this rule out of {folder}'s local settings, so it changes all of {folder}."
)
# A project whose own skill rule keeps the skill on, named by an all-projects change.
KEEPS_ITS_RULE = "It stays on in {folders}, which has its own rule."
KEEP_THEIR_RULES = "It stays on in {folders}, which have their own rules."
PLUGIN_SKILL = "A plugin's skill follows its plugin; turn the plugin off instead."
PLUGIN_ALL_PROJECTS = "Turn a plugin off for all projects with its own switch."
PROJECT_SKILL_ALL = "This skill is only in one project; turn it off in that project."
NO_CLAUDE_FOLDER = "{folder} has no Claude Code settings yet; start Claude Code there once first."
# A project's own rule removed: the skill or the plugin then follows the shared setup.
FOLLOWS_SHARED = "Follows all projects"

# The Context screen (spec 2026-11-09 "Do your skills fit?", "States"). Facts say "was";
# estimates say "would" and start with "Estimate:".
CONTEXT_LEDE = (
    "Every chat starts with a list of your skills. The agent reads it to choose the right skill. "
)
CONTEXT_LIMITS = {
    "claude_code": "Claude Code lets this list use 1% of the context window.",
    "codex": "Codex lets this list use 2% of the context window.",
    "cursor": "Cursor does not publish a limit for this list.",
}
# In place of CONTEXT_LIMITS when the user's own setting is the limit.
CONTEXT_LIMIT_SET = {
    "claude_code": "Your Claude Code settings limit this list to {n} characters.",
    "codex": "Your config.toml limits this list to {n} tokens.",
}
# A config.toml value above the most Codex allows.
CODEX_MOST = "Codex lets this list use {n} tokens at most."
NO_CHAT = "No {client} chat yet. Open one chat, and Kitden will show what {client} sent."
# "{client}" is "Claude Code 2.2.0", or "this version of Claude Code" when the log names none.
CANNOT_READ_LOG = (
    "Kitden cannot read chat logs of {client} yet, so it shows no result and no estimate."
)
THIS_VERSION = "this version of {client}"
NOTHING_TO_FIT = "There is nothing to fit."
CURSOR_CANNOT_SEE = "Kitden cannot see what Cursor sends, so it cannot tell if your skills fit."
NO_CHECK = "Kitden cannot check its estimate against your last chat, so it shows none."
TWO_LIMITS = "Two limits give the list of your last chat, so Kitden shows no estimate."
# After the model's name, when the window comes from the list and not from the model.
WORKED_OUT = "worked out from the list"
# The fact of the last chat, on its window card. "{when}" is " on Nov 6", or "" when the log's
# time does not parse; the words in () are the forms for one.
ON_DATE = " on {date}"
CLAUDE_ALL_SENT = "In your last chat{when}, all {n} skills were sent with their descriptions."
CLAUDE_ONE_SENT = "In your last chat{when}, your one skill was sent with its description."
CLAUDE_NAMES_ONLY = (
    "In your last chat{when}, {bad} of {n} {skills} showed only a name. "
    "The agent may not have used {them}."
)
# Skills that showed only a name because they were set to Name only: a choice, not a misfit.
# "{rest}" is CLAUDE_CHOSEN or CLAUDE_SET_NOW.
CLAUDE_ALL_SENT_BUT = "In your last chat{when}, all {n} skills were sent; {rest}"
CLAUDE_ONE_SENT_BUT = "In your last chat{when}, your one skill was sent; {rest}"
CLAUDE_MORE = "{n} more"
# Kitden can tell it was the setting at that chat (see context_view._chosen).
CLAUDE_CHOSEN = "{chosen} showed only a name, as you chose."
# Kitden cannot tell: it says only what the setting is today.
CLAUDE_SET_NOW = "{chosen} showed only a name and {are} set to Name only now."
CODEX_ALL_SENT = "In your last chat{when}, all {n} skills were sent with full descriptions."
CODEX_ONE_SENT = "In your last chat{when}, your one skill was sent with its full description."
CODEX_CUT = (
    "In your last chat{when}, {bad} of {n} {descriptions} {were} cut to {cut} characters. "
    "The agent saw only {their} start."
)
CODEX_LEFT_OUT = (
    "In your last chat{when}, Codex removed every description and left {out} of {n} {skills} "
    "out of the list. The agent did not see {them} at all."
)
CODEX_NAMES = (
    "In your last chat{when}, Codex removed every description. The agent saw only the names."
)
# A Codex list whose skill files Kitden cannot all find: no full or cut verdict.
CODEX_SENT_UNKNOWN = (
    "In your last chat{when}, Codex sent {n} {skills}. Kitden cannot find all {their} files, so "
    "it cannot tell if any were cut."
)
# After CODEX_CUT, when Kitden cannot find the files of some other skills in the list.
CODEX_ONE_UNKNOWN = "Kitden cannot find the file of 1 more, so it cannot tell if it was cut."
CODEX_MORE_UNKNOWN = "Kitden cannot find the files of {n} more, so it cannot tell if they were cut."
ROOM_LEFT = "Estimate: about {left} {unit} left before the limit."
# The short result on a card's face.
CLAUDE_SHORT_ALL = "All {n} sent"
CLAUDE_SHORT_NAMES = "{bad} of {n} showed only a name"
CODEX_SHORT_ALL = "All {n} sent in full"
CODEX_SHORT_CUT = "{bad} of {n} cut short"
CODEX_SHORT_OUT = "{out} left out, the rest name only"
CODEX_SHORT_SENT = "{n} sent"
WOULD_FIT = "All {n} would fit"
CLAUDE_WOULD_SHORT = "{bad} of {n} would show only a name"
CODEX_WOULD_SHORT = "{bad} of {n} would be cut short"
# An estimate's sentence. "{on}" is ON_WINDOW, or WITH_LIMIT when the window is not known.
ESTIMATE = "Estimate: {}"
AFTER_APPLY = "After Apply, estimate: {}"
ON_WINDOW = "On a {size} window"
WITH_LIMIT = "With this limit"
CLAUDE_WOULD_DROP = (
    "{on}, {bad} of {n} {skills} would show only a name. The agent may not use {them}."
)
CLAUDE_WOULD_KEEP = "{on}, every skill would keep its description."
CLAUDE_WOULD_KEEP_CHOSEN = "{on}, everything would fit. {chosen} only a name, as you chose."
CODEX_WOULD_LEAVE_OUT = "{on}, {out} of {n} {skills} would be left out and no description sent."
CODEX_WOULD_CUT = "{on}, {bad} of {n} {descriptions} would be cut to about {cap} {characters}."
CODEX_WOULD_NAMES = (
    "{on}, Codex would remove every description. The agent would see only the names."
)
CODEX_WOULD_KEEP = "{on}, every skill would keep its full description."
# Both sides of a swap after Apply: (one, many).
GAINS = {
    "claude_code": ("{} gets a description.", "{} get descriptions."),
    "codex": ("{} gets its full description.", "{} get their full descriptions."),
}
LOSES = {
    "claude_code": ("{} loses its description.", "{} lose their descriptions."),
    "codex": ("{} is cut short.", "{} are cut short."),
}
# Window cards.
LAST_CHAT_TAG = "Last chat · {date}"
LAST_CHAT = "Last chat"
ESTIMATE_TAG = "Estimate"
WINDOW_TITLE = "{size} window"
UNKNOWN_WINDOW = "Unknown window"
LIMIT_TITLE = "{n} {unit}"
CLAUDE_SETTING = "Set in Claude Code settings"
CODEX_SETTING = "Set in config.toml"
CODEX_ABOVE_MOST = "config.toml says {said}; Codex allows {most} at most"
DEFAULT_LIMIT = "Default limit"
# The two sides of the picture, and the first side's name when there is no list to read.
CONTEXT_SIDES = {
    "claude_code": ("Description sent", "Name only"),
    "codex": ("Full description", "Cut short"),
    "cursor": ("The agent can pick it", "Only when you ask"),
}
SKILLS_FOUND = "Skills found"
# Where a skill comes from, in its Details.
SOURCE_BUILT_IN = "Built into Claude Code"
SOURCE_PLUGIN = "Plugin {}"
SOURCE_PROJECT = "Project {}"
SOURCE_OWN = "Your skills"
# One skill's Details line.
NOTE_BUILT_IN = "Claude Code always sends built-in skills in full."
NOTE_PLUGIN = "A plugin's skill follows its plugin. Turn the plugin off in the Library."
NOTE_FREES = "Name only frees {n} characters. The agent no longer sees when to use it."
NOTE_NO_ROOM = "No room for its description."
# After NOTE_NO_ROOM, when a skill with a description has a switch.
NOTE_FREE_ROOM = "Set a skill with a description to Name only or Off to free room."
# The limit does not explain the list, so Kitden does not blame it.
NOTE_NOT_SENT = "Its description was not sent in your last chat. Kitden cannot tell why."
NOTE_NAME_ONLY = "The agent sees the name, not when to use it."
NOTE_ONLY_ASKED = "The agent uses it only when you type its name."
NOTE_CODEX_OFF = "Off frees room, so long descriptions get cut less."
NOTE_CODEX_LONG = "Codex sends only the first 1,024 characters of a description."
NOTE_NOT_LISTED = "It was not in the list of your last chat."
NOTE_NO_FILE = "Kitden cannot find its file, so it cannot tell if it was cut."
# "How this is counted".
# "{version}", "{when}" and "{surface}" each start with a space, or are "" when the log does not
# say.
HOW_CLAUDE_LIST = (
    "Last chat: the list Claude Code{version} sent{when}{surface}, read from its chat log."
)
HOW_CLAUDE_RULE = (
    "Estimates use the rule Kitden found in Claude Code 2.1.311: 1% of the window, at 3 "
    "characters per token for new models and 4 for older ones. Built-in skills always keep their "
    "description; of the rest, the most used in the last weeks go first. A newer Claude Code may "
    "count differently."
)
HOW_CLAUDE_CHECK = (
    "Before it shows an estimate, Kitden checks that the rule gives the same list as your last "
    "chat."
)
HOW_CLAUDE_CHECKED = "On Nov 7 the rule also matched two test chats with a smaller limit."
HOW_NOT_MATCHED = "This time it does not."
# The rule could not run: no limit known, or a size not known.
HOW_NOT_RUN = "This time Kitden could not run the check."
HOW_TWO_LIMITS = "This time two limits give it, so the check cannot pick one."
HOW_CLAUDE_WINDOW = (
    "The chat log does not say the window. Only a {size} window gives this list, so Kitden "
    "shows it."
)
HOW_CLAUDE_SETTING = (
    "The limit is SLASH_COMMAND_TOOL_CHAR_BUDGET from your Claude Code settings. "
    "A value set in the shell is out of Kitden's sight."
)
HOW_CLAUDE_SHELL = "A SLASH_COMMAND_TOOL_CHAR_BUDGET set in the shell is out of Kitden's sight."
HOW_CLAUDE_SURFACE = "The list in the terminal can differ from the Claude app."
HOW_CLAUDE_REST = "The rest of the window (system prompt, tools, MCP, the chat) is not measured."
HOW_CODEX_LIST = "Last chat: the list Codex{version} sent{when}, read from its chat log."
HOW_CODEX_RULE = (
    "Estimates start from Codex's source code: 2% of the window, at most 1,024 characters per "
    "description, about 4 bytes per token. Each entry also pays for its name and file path. How "
    "Codex cuts a list that does not fit is fitted to one real list, not read from the code."
)
HOW_CODEX_CHECK = (
    "Before it shows an estimate, Kitden checks that the rule cuts the same skills as your last "
    "chat."
)
HOW_CODEX_SAME = "It does: the same {n}."
HOW_CODEX_DOES = "It does."
HOW_CODEX_SETTING = "The limit is skills.max_context_tokens in Codex's config.toml."
HOW_CODEX_SIZES = (
    "Full sizes come from your skill files today. They may have changed since the chat{when}."
)
HOW_CODEX_TOKENS = "Tokens here are Codex's own count, not exact model tokens."
HOW_CURSOR = (
    "Cursor does not publish a limit for this list, and Kitden found no log that shows what it "
    "sends. Checked 2026-11-06.",
    "Sizes and the Only when asked setting come from your skill files.",
    "Cursor's own built-in skills and one plugin with no local name are not counted.",
)
HOW_NO_CHAT = (
    "Kitden shows a result only after it reads a real chat log. Before that it shows the skills it "
    "finds on disk."
)
HOW_UNREADABLE = (
    "When the log format changes, Kitden stops showing results until it is updated. It never "
    "shows an old result as new."
)
HOW_NO_SKILLS = "Kitden looks in the same folders and plugins as {client}."
