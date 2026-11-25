"""The Context screen: for each client, what its last chat sent and whether the skill list fit,
with every sentence written (spec 2026-11-09 "Do your skills fit?").

A number is either read from the last chat log (the fact), or an estimate. Estimates show only
while the client's rule, run on the last chat's skills and window, rebuilds that list exactly
(`checked`, spec "The check that guards every estimate"). One holds without it: whether every
description fits a limit, for Claude Code's skill list limit (`_claude_count`).
"""

import glob
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import TypeGuard

from kitden.clients.base import (
    PLUGIN_DISABLE,
    PLUGIN_ENABLE,
    Reader,
    found_columns,
    from_plugin,
)
from kitden.clients.claude_code import LIMIT_KEY, SKILL_STATES, ClaudeCodeAdapter, local_files
from kitden.clients.claude_folder import ClaudeFolder, claude_folder
from kitden.clients.codex import skills_off
from kitden.clients.versions import highest_version
from kitden.context.claude_log import Unreadable, earlier_descriptions, last_claude_list
from kitden.context.codex_log import CodexSent, codex_window, codex_windows, last_codex_list
from kitden.context.rules import (
    ClaudeFit,
    ClaudeSkill,
    CodexFit,
    CodexSkill,
    claude_budget,
    claude_rule,
    claude_weight,
    codex_budget,
    codex_catalog,
    codex_line,
    codex_rule,
    codex_table,
    codex_tokens,
    same_share,
    shares_above,
    shares_below,
)
from kitden.context.tables import (
    CLAUDE_ALWAYS_FULL,
    CLAUDE_BUILT_IN,
    CLAUDE_CANDIDATES,
    CLAUDE_DESCRIPTION_CAP,
    CLAUDE_OTHER_WINDOW,
    CLAUDE_RULED,
    CLAUDE_SHARE,
    CLAUDE_SHARES,
    CLAUDE_WINDOWS,
    CODEX_DESCRIPTION_CAP,
    CODEX_LIMIT_STEP,
    CODEX_MAX_LIMIT,
)
from kitden.local_gateway.settings import as_dict
from kitden.model import CLIENT_WORDS, Enabled, Item, ItemKind, Project, Scope
from kitden.system import claude_desktop_dir
from kitden.views import words
from kitden.views.after import home_path
from kitden.views.catalog import installed_inside
from kitden.views.effective import effective_view, in_project
from kitden.views.match import plugin_at, plugin_of
from kitden.views.skills import list_text, read_skill

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
# The states `skill.rule` writes, per client (spec "Switches per client").
SWITCHES = {"claude_code": ["on", "name-only", "off"], "codex": ["on", "off"]}
ASKED = ("user-invocable-only", "only-asked")
# checked 2026-11-07 (Claude Code 2.1.311, two test chats at 8,000 and 12,000): this `env` value
# in Claude Code's settings sets the list's limit in characters. Like other settings, the most
# specific file wins: local, then project, then user (checked 2026-10-26, /en/settings).
BUDGET_KEY = "SLASH_COMMAND_TOOL_CHAR_BUDGET"
# checked 2026-11-23 (/en/settings-reference): top-level keys of any settings file; the share of
# the window the list may use (default 0.01) and the cap on one description (default 1536).
FRACTION_KEY = LIMIT_KEY
CAP_KEY = "skillListingMaxDescChars"
WHOLE = re.compile(r"[0-9]+")
# In a Codex skill's `agents/openai.yaml`, under `policy`.
ONLY_ASKED = re.compile(r"^[ \t]+allow_implicit_invocation[ \t]*:[ \t]*false\b", re.M | re.I)


@dataclass
class _Row:
    """One skill of the last list. `sent`: Claude Code's sent text (None = name only); Codex's
    sent description ("" = name only, None = left out). `full`: the description on disk, None
    when Kitden cannot find it."""

    name: str
    sent: str | None
    item: Item | None
    full: str | None
    path: str = ""  # Codex: the `file:` path of its line
    shown: str = ""  # Claude Code: the name as the list shows it, where that is more than the name
    added: bool = False  # Claude Code: added during the chat, sent whole outside the limit
    built_in: bool = False  # Claude Code: built in, so no file
    always_full: bool = False  # Claude Code: built in, keeps its description whatever the limit
    newer: str = ""  # Codex: its file in its plugin's newer version, when the chat's one is gone
    # Codex: the newer version's description is another text than the chat sent, so the size it
    # had in the chat is not known.
    changed: bool = False
    # Claude Code: the description an earlier chat's list sent, for a built-in skill (no file).
    # Only the count uses it: `full` is what is on disk.
    earlier: str | None = None
    # Claude Code: the description alone, what the page shows; `full` also holds when_to_use.
    plain: str | None = None

    @property
    def moved(self) -> bool:
        return bool(self.newer)

    @property
    def file(self) -> str:
        """Codex: the skill's file as it is now."""
        return self.newer or self.path

    @property
    def page_text(self) -> str | None:
        """The description the page shows for the skill."""
        return self.full if self.plain is None else self.plain

    @property
    def then(self) -> str | None:
        """The description as it was in the chat: `full`, or None when that is not known."""
        return None if self.changed else self.full


def context_view(
    inventory,
    home: Path,
    codex_home: Path,
    folder: str | None,
    draft: dict,
    anywhere: bool = False,
    claude: ClaudeFolder | None = None,
) -> dict:
    """One card per found client. `folder` is the picked project (None: all projects); `draft`
    maps client -> skill name -> state, the tray's changes not applied yet, and `limits` to
    client -> the skill list's share of the window in the tray ("default": the key taken out).
    With `anywhere`, a client with no chat in `folder` shows its last chat in any folder; the
    card's fact names it. `claude` is where Claude Code keeps the user's files; by default the one
    the environment says."""
    claude = claude or claude_folder(home)
    clients = []
    limits = as_dict(draft.get("limits"))
    for client in found_columns(inventory):
        changes = as_dict(draft.get(client))
        if client == "claude_code":
            asked = limits.get(client)
            clients.append(_claude(inventory, home, claude, folder, changes, anywhere, asked))
        elif client == "codex":
            asked = limits.get(client)
            clients.append(_codex(inventory, codex_home, folder, changes, anywhere, asked))
        else:
            clients.append(_cursor(inventory, folder))
    return {"clients": clients}


# Shared parts


def _card(client: str, **parts) -> dict:
    card = {
        "client": client,
        "lamp": "none",
        "lede": words.CONTEXT_LEDE + words.CONTEXT_LIMITS[client],
        "message": None,
        "unit": "tokens" if client == "codex" else "characters",
        "fact": None,
        "checked": False,
        "windows": [],
        "sides": list(words.CONTEXT_SIDES[client]),
        "skills": [],
        "after": None,
        # The estimate for the setup as it is now, when the last chat was sent under another one.
        "now": None,
        "how": [],
        "limit": None,
        "changed": [],
    }
    return card | parts


def _skills(inventory, client: str, folder: str | None) -> list[Item]:
    """The skills the client loads there, one per name."""
    found: dict[str, Item] = {}
    for item in effective_view(inventory, client, folder).items:
        if item.kind is ItemKind.SKILL:
            found.setdefault(_name(client, item), item)
    return list(found.values())


def _not_loaded(inventory, client: str, folder: str | None, loaded: dict[str, Item]) -> set[str]:
    """The skills Kitden knows of there that the client does not load now: turned off, or a part
    of a plugin that is off."""
    return {
        name
        for item in inventory.items
        if item.client == client
        and item.kind is ItemKind.SKILL
        and item.project in (None, folder)
        and (name := _name(client, item)) not in loaded
    }


def _name(client: str, item: Item) -> str:
    """The skill's name as Claude Code's list writes it: a plugin's skill has its prefix."""
    plugin = plugin_of(item) if client == "claude_code" else None
    return f"{plugin.split('@')[0]}:{item.name}" if plugin else item.name


def _state(item: Item | None) -> str:
    # A plugin that is off takes its skills with it.
    if item is not None and from_plugin(item) and item.enabled is Enabled.OFF:
        return "off"
    return (item.skill_state if item else None) or "on"


def _off_skills(inventory, client: str, folder: str | None) -> dict[str, Item]:
    """The skills that are off there, by name: the effective view leaves them out."""
    found: dict[str, Item] = {}
    for item in inventory.items:
        here = item.client == client and item.project in (None, folder)
        if here and item.kind is ItemKind.SKILL:
            item = in_project(item, folder)
            if item.enabled is Enabled.OFF:
                found.setdefault(_name(client, item), item)
    return found


def _texts(path: str | None) -> tuple[str | None, str | None]:
    """A SKILL.md's description, and the text Claude Code's list holds, which adds the skill's
    when_to_use (`list_text`); (None, None) when there is no such file."""
    if not path or not Path(path).is_file():
        return None, None
    info = read_skill(Path(path).parent)
    return info["description"], list_text(info)


def _description(path: str | None) -> str | None:
    """The description in a SKILL.md, or None when there is no such file."""
    return _texts(path)[0]


def _claude_row(name: str, sent: str | None, item: Item | None, path: str | None, **kw) -> _Row:
    """A Claude Code row: `full` is the text its list holds, `plain` the description the page
    shows."""
    plain, full = _texts(path)
    return _Row(name, sent, item, full, plain=plain, **kw)


def _app_path(home: Path, claude: ClaudeFolder, name: str) -> str | None:
    """The SKILL.md of a skill the Claude app gives Claude Code (`anthropic-skills:docx`), from
    the newest copy of its SKILL.md; None when there is none.

    # checked 2026-11-12 (real files, Claude app with Claude Code 2.1.309): the app keeps them in
    # local-agent-mode-sessions/skills-plugin/<org>/<id>/skills/<skill>/SKILL.md, one folder per
    # account, and Claude Code keeps a copy of some in ~/.claude/skills/synced/<org>_<id>/<skill>.
    """
    skill = glob.escape(name.rpartition(":")[2])
    app = claude_desktop_dir(home) / "local-agent-mode-sessions/skills-plugin"
    found = []
    for path in (
        *app.glob(f"*/*/skills/{skill}/SKILL.md"),
        *(claude.config / "skills/synced").glob(f"*/{skill}/SKILL.md"),
    ):
        try:
            found.append((path.stat().st_mtime, path))
        except OSError:  # gone since the folder was listed
            continue
    return str(max(found)[1]) if found else None


def _newer_copy(path: str) -> str | None:
    """The same file in the newest version folder beside the one `path` names, when that one is
    gone; None when there is no such file.

    # checked 2026-11-13 (real files, Codex 0.167.0): plugins are kept at
    # ~/.codex/plugins/cache/<market>/<plugin>/<version>/, and an update removes the old version.
    """
    parts = Path(path).parts
    for i in range(len(parts) - 1, 0, -1):
        if highest_version([parts[i]]) is None:  # not a version folder
            continue
        try:
            names = [p.name for p in Path(*parts[:i]).iterdir() if p.is_dir()]
        except OSError:
            return None
        newest = highest_version(names)
        found = Path(*parts[:i], newest, *parts[i + 1 :]) if newest else None
        return str(found) if found and found.is_file() else None
    return None


def _skill(
    client: str,
    name: str,
    item: Item | None,
    size: int,
    side: int | None,
    note: str | None,
    built_in: bool = False,
    description: str | None = None,
    seen: int | None = None,
    state: str | None = None,
    plugin_switch: dict | None = None,
    source: str | None = None,
    held: bool = False,
) -> dict:
    """`state` and `source`: of a skill with no item to say them. `held`: a project's own settings
    set it, so the user's file cannot change it there."""
    # Claude Code's skillOverrides does not touch a plugin's skills (spec "Switches per client").
    plugin = client == "claude_code" and item is not None and from_plugin(item)
    ruled = item is not None or (built_in and name in CLAUDE_RULED)
    switch = SWITCHES.get(client, []) if ruled and not plugin and not held else []
    # Claude Code takes a rule for a project's own skill only in that project (changes/actions.py).
    project = item.project if client == "claude_code" and item and not plugin else None
    return {
        "name": name,
        "shown": name.split(":")[-1],
        # The plugin part of "venture:review" (None for a skill with no plugin), as the client and
        # `kitden scan` write it.
        "plugin": name.rpartition(":")[0] or None,
        "item": item.id if item else None,
        "project": Project(project, True).id if project else None,
        "source": source or _source(item, built_in),
        # Not a file on this computer: no Library item.
        "built_in": built_in,
        "size": size,
        "side": side,
        "state": state or _state(item),
        "switch": list(switch),
        # Claude Code: the plugin's own switch, for a skill that follows its plugin.
        "plugin_switch": plugin_switch,
        "note": note,
        "description": description,
        "seen": seen,
    }


def _seen(full: str | None, sent: str | None, side: int | None, cap: int | None) -> int | None:
    """How many characters of the description the agent got: at most `cap`, the most the
    client keeps of one (None: no cap, as for a skill Claude Code added during the chat). A
    skill not sent whole (side 1) got the sent text's length: 0 for a name only or a skill left
    out. The length, not a match with the file: quotes may be written apart. None when it got
    all of it or Kitden has no file."""
    if full is None:
        return None
    got = len(sent or "") if side == 1 else len(full)
    got = got if cap is None else min(got, cap)
    return None if got >= len(full) else got


def _cap_then(cap: int, sent: str | None) -> int:
    """The cap for what the last chat sent: today's setting, or more when the log holds a longer
    description. The setting may have been lowered since, and the log is what the agent got."""
    return max(cap, len(sent or ""))


def _source(item: Item | None, built_in: bool) -> str | None:
    if item is None:
        return words.SOURCE_BUILT_IN if built_in else None
    if from_plugin(item):
        plugin = plugin_of(item)
        return words.SOURCE_PLUGIN.format(plugin.split("@")[0]) if plugin else None
    if item.project:
        return words.SOURCE_PROJECT.format(Path(item.project).name)
    return words.SOURCE_OWN


def _disk_card(client: str, items: list[Item], message: str, how: list[str]) -> dict:
    """No list to read: the skills on disk, no verdict."""
    skills = []
    for item in items:
        state = _state(item)
        note = words.NOTE_ONLY_ASKED if state in ASKED else None
        if from_plugin(item):
            note = words.NOTE_PLUGIN
        text, listed = _texts(item.source.path)
        size = len((listed if client == "claude_code" else text) or "")
        side = int(state == "name-only")
        skills.append(_skill(client, _name(client, item), item, size, side, note, description=text))
    sides = [words.SKILLS_FOUND, words.CONTEXT_SIDES[client][1]]
    return _card(client, message=message, sides=sides, skills=skills, how=how)


def _no_list(client: str, items: list[Item], found: Unreadable | None) -> dict:
    """The card when there is no list to read: a log Kitden cannot read, or no chat yet."""
    name = CLIENT_WORDS[client]
    if isinstance(found, Unreadable):
        which = words.THIS_VERSION.format(client=name)
        if found.version:
            which = f"{name} {found.version}"
        message = words.CANNOT_READ_LOG.format(client=which)
        return _disk_card(client, items, message, [words.HOW_UNREADABLE])
    if items:
        return _disk_card(client, items, words.NO_CHAT.format(client=name), [words.HOW_NO_CHAT])
    return _disk_card(
        client, items, words.NOTHING_TO_FIT, [words.HOW_NO_SKILLS.format(client=name)]
    )


def _when(at: str) -> tuple[str, int]:
    """ "Nov 6" on this computer's clock, and the time in ms; ("", now) when it does not parse."""
    try:
        moment = datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return "", int(datetime.now().timestamp() * 1000)
    return f"{MONTHS[moment.month - 1]} {moment.day}", int(moment.timestamp() * 1000)


def _on_date(date: str) -> str:
    """ " on Nov 6", or "" when the log's time did not parse."""
    return words.ON_DATE.format(date=date) if date else ""


def _tag(date: str) -> str:
    return words.LAST_CHAT_TAG.format(date=date) if date else words.LAST_CHAT


def _many(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _size(window: int) -> str:
    """1M, 200K, 272K."""
    if window >= 1_000_000:
        return f"{window / 1_000_000:g}M"
    return f"{round(window / 1000)}K"


def _on(window: int | None) -> str:
    return words.ON_WINDOW.format(size=_size(window)) if window else words.WITH_LIMIT


def _names(names: list[str]) -> str:
    shown = [n.split(":")[-1] for n in names]
    return words.join_words(shown) if len(shown) < 3 else f"{len(shown)} skills"


def _swap(client: str, gets: list[str], loses: list[str]) -> str:
    """ "xlsx gets a description. skill-creator loses its description." """
    said = []
    for names, (one, many) in ((gets, words.GAINS[client]), (loses, words.LOSES[client])):
        if names:
            said.append((one if len(names) == 1 else many).format(_names(names)))
    return " ".join(said)


def _whole(value) -> TypeGuard[float]:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _changes(draft: dict, states: dict[str, str], allowed: list[str]) -> dict[str, str]:
    """The draft's states that differ from today's, for skills of the last list."""
    return {
        name: state
        for name, state in draft.items()
        if name in states and state in allowed and state != states[name]
    }


def _window_card(title: str, models: str, tag: str, budget: int | None, result: dict) -> dict:
    return {"title": title, "models": models, "tag": tag, "budget": budget, "result": result}


# Claude Code


def _claude_files(home: Path, claude: ClaudeFolder, folder: str | None) -> list[Path]:
    """Claude Code's settings files for a chat in `folder`, the winning one last."""
    files = [claude.settings]
    if folder:
        project = Path(folder)
        files += [project / ".claude/settings.json", *local_files(project, home)]
    return files


def _claude_setting(files: list[Path]) -> int | None:
    """The limit set in Claude Code's settings files, when it is a whole number."""
    read = Reader("claude_code")
    for path in reversed(files):
        env = as_dict(as_dict(read.json(path)).get("env"))
        if BUDGET_KEY not in env:
            continue
        value = env[BUDGET_KEY]
        if isinstance(value, str) and WHOLE.fullmatch(value.strip()):
            value = int(value)
        return (
            value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None
        )
    return None


def _built_in_rules(files: list[Path]) -> dict[str, tuple[str, bool]]:
    """The `skillOverrides` state of each built-in skill it is known to reach, key by key, the
    winning file last, and whether a project's file sets it (checked 2026-11-24, Claude Code
    2.1.330: the files merge key by key)."""
    read = Reader("claude_code")
    rules: dict[str, tuple[str, bool]] = {}
    for i, path in enumerate(files):
        found = as_dict(as_dict(read.json(path)).get("skillOverrides"))
        rules |= {
            n: (s, i > 0) for n, s in found.items() if n in CLAUDE_RULED and s in SKILL_STATES
        }
    return rules


def _tagged(row: _Row) -> _Row:
    """Whether the row is a skill built into Claude Code, by its name: such a skill has no file."""
    own = row.item is None
    full = own and row.name in CLAUDE_ALWAYS_FULL
    return replace(row, built_in=own and row.name in CLAUDE_BUILT_IN, always_full=full)


def _ruled(row: _Row) -> bool:
    """A built-in skill that a skill rule is known to reach."""
    return row.built_in and row.name in CLAUDE_RULED


@dataclass
class _Plugins:
    """Claude Code's plugins, and what each one holds."""

    items: list[Item]
    inside: dict[str, dict]

    def named(self, name: str) -> list[Item]:
        return [p for p in self.items if p.name.split("@")[0] == name]

    def of(self, row: _Row) -> Item | None:
        """The plugin a row follows, for all projects; None when it has none, Kitden cannot tell
        which, or a project has an entry of its own for it."""
        prefix = row.name.rpartition(":")[0]
        found = self.named(prefix) if prefix else []
        if row.item is not None:
            found = [p for p in found if p.name == plugin_of(row.item)]
        return found[0] if len(found) == 1 and found[0].scope is Scope.USER else None

    def switch(self, row: _Row, rows: list[_Row]) -> dict | None:
        """The plugin's own switch: the change it adds to the tray, what it says, and, to turn it
        off, what goes with it and about how much shorter the last list would be."""
        item = self.of(row)
        action = next(
            (a for a in (PLUGIN_DISABLE, PLUGIN_ENABLE) if item and a in item.actions), None
        )
        if item is None or action is None:
            return None
        name = item.name.split("@")[0]
        offer = {"item": item.id, "action": action}
        if action == PLUGIN_ENABLE:
            return offer | {"label": words.PLUGIN_TURN_ON.format(name), "say": None}
        held = self.inside.get(item.name, {})
        parts = [
            f"{len(held[key])} {_many(len(held[key]), one, many)}"
            for key, one, many in words.PLUGIN_PARTS
            if held.get(key)
        ]
        say = []
        if parts:
            say.append(words.PLUGIN_GOES.format(plugin=name, parts=words.join_words(parts)))
        # Each line of the list, with the break after it.
        lines = [r for r in rows if self.of(r) is item]
        size = sum(
            len(r.shown or r.name) + (2 if r.sent is None else 4 + len(r.sent)) + 1 for r in lines
        )
        if size:
            say.append(words.PLUGIN_FREES.format(n=f"{size:,}"))
        label = words.PLUGIN_TURN_OFF.format(name)
        return offer | {"label": label, "say": " ".join(say) or None}


def _row_state(row: _Row, rules: dict[str, tuple[str, bool]], plugins: _Plugins) -> str:
    if _ruled(row):
        return rules.get(row.name, ("on", False))[0]
    plugin = plugins.of(row) if row.item is None else None
    if plugin is not None and plugin.enabled is Enabled.OFF:
        return "off"  # a plugin's command goes with it
    return _state(row.item)


def _held(row: _Row, rules: dict[str, tuple[str, bool]]) -> bool:
    """A project's own settings set this skill, over the user's file."""
    if _ruled(row):
        return rules.get(row.name, ("on", False))[1]
    item = row.item
    return (
        item is not None
        and item.project is None
        and item.state_scope in (Scope.PROJECT, Scope.LOCAL)
    )


def _claude_plugins(inventory, home: Path, claude: ClaudeFolder, folder: str | None) -> _Plugins:
    """Those Claude Code installed, for all projects or in `folder`; not an account's."""
    items = [
        i
        for i in inventory.items
        if i.client == "claude_code"
        and i.kind is ItemKind.PLUGIN
        and i.scope is not Scope.ACCOUNT
        and i.project in (None, folder)
    ]
    return _Plugins(
        items, installed_inside({"claude_code": ClaudeCodeAdapter(home, folder=claude)})
    )


def _plugin_note(note: str | None, offer: dict | None) -> str | None:
    return words.NOTE_PLUGIN_SWITCH if offer and note == words.NOTE_PLUGIN else note


def _outside(row: _Row, plugins: _Plugins) -> tuple[str | None, str | None]:
    """The source and the note of a listed skill with a prefix and no item: a part of a plugin
    Kitden knows, a skill of the Claude app, or of a plugin Kitden does not know."""
    prefix = row.name.rpartition(":")[0]
    if row.item is not None or not prefix:
        return None, None
    if plugins.named(prefix):
        return words.SOURCE_PLUGIN.format(prefix), words.NOTE_PLUGIN
    # checked 2026-11-24 (code.claude.com/docs/en/skills): the name is reserved for skills synced
    # from claude.ai, which the Claude app may give to Claude Code as a plugin.
    if prefix == "anthropic-skills":
        return words.SOURCE_APP, words.NOTE_APP
    return prefix, words.NOTE_OTHER_PLUGIN.format(prefix)


def _claude_key(files: list[Path], key: str):
    """The value of a top-level key in the winning settings file that has it."""
    read = Reader("claude_code")
    for path in reversed(files):
        settings = as_dict(read.json(path))
        if key in settings:
            return settings[key]
    return None


def _claude_fraction(files: list[Path]) -> float | None:
    """skillListingBudgetFraction: a number above 0 and at most 1; anything else is not set."""
    value = _claude_key(files, FRACTION_KEY)
    return value if _whole(value) and 0 < value <= 1 else None


def _claude_cap(files: list[Path]) -> int:
    """skillListingMaxDescChars: a positive whole number; anything else is the default."""
    value = _claude_key(files, CAP_KEY)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return CLAUDE_DESCRIPTION_CAP


def _percent(fraction: float | None) -> str:
    """0.02 as "2%", 0.015 as "1.5%"."""
    return words.percent(fraction or CLAUDE_SHARE)


def _limit_file(files: list[Path]) -> Path | None:
    """The winning settings file that has skillListingBudgetFraction, whatever its value."""
    read = Reader("claude_code")
    return next((p for p in reversed(files) if FRACTION_KEY in as_dict(read.json(p))), None)


def _about(n: float) -> str:
    """A count to two figures: 14,237 as "14,000", 4,745 as "4,700"; at least 1."""
    whole = max(1, round(n))
    return f"{round(whole, 2 - len(str(whole))):,}" if whole >= 100 else str(whole)


def _asked_share(value) -> float | None:
    """The share a tray row asks for: a number above 0 and at most 1, or the default."""
    if value == "default":
        return CLAUDE_SHARE
    return value if _whole(value) and 0 < value <= 1 else None


def _limit_steps(
    points: list[tuple],
    now_used: int | None,
    n: int,
    unit: str,
    short_words: str,
    unknown_words: str | None = None,
) -> list[dict]:
    """Where the limit line can be dragged to and what each place gives, in words the page shows
    as they are (spec limit-line-control). `points`: (value, limit, short, used, head, now) per
    place, `value` as a tray row sends it, `limit` in the card's unit, `short` how many skills the
    limit would still cut and `used` what the list would send (both None with no estimate), and
    `head` the share or the limit in words. `n`: the skills on the list. `unknown_words`:
    what a place says whose `short` is not known."""
    out = []
    for value, limit, short, used, head, now in points:
        parts = [head]
        if short is not None:
            fit = words.LIMIT_STEP_ALL.format(n=n)
            parts.append(fit if short == 0 else short_words.format(short=short, n=n))
        elif unknown_words is not None:
            parts.append(unknown_words)
        if used is not None and now_used is not None and used != now_used:
            extra = used - now_used
            more = words.LIMIT_STEP_MORE if extra > 0 else words.LIMIT_STEP_LESS
            parts.append(more.format(n=_about(abs(extra)), unit=unit))
        step = {"value": value, "limit": limit, "short": short, "say": " · ".join(parts)}
        out.append(step | {"now": True} if now else step)
    return out


@dataclass(frozen=True)
class _Fits:
    """What a limit gives the next chats: by the rule, when it rebuilds the last chat's list, else
    by a count of what all descriptions need (`counted`)."""

    skills: list[ClaudeSkill]
    used: int  # characters the list uses at the limit now
    # The fit at a limit of this many characters. A count gives one only where everything fits:
    # it cannot say which descriptions a lower limit keeps.
    at: Callable[[int], ClaudeFit | None]
    not_needed: str  # why there is nothing to raise when everything fits already
    lines: list[str]  # Details' quiet lines on what was counted
    counted: bool  # by a count, not by the rule
    # By a count, when the chat was sent under today's limit and the next chat adds no skill: how
    # many of its skills showed only a name, and are not Name only or Off now. The place of today
    # says it where the count cannot.
    short_now: int | None = None


def _claude_steps(
    pair: tuple[int, int],
    share: float,
    fits: _Fits,
    back: bool,
    ups: list[tuple[float, ClaudeFit | None]],
) -> list[dict]:
    """The limit line's places for Claude Code: 1% when Back is offered and the shares on the list
    between it and the share now, the share now, and the shares above it Kitden offers (`ups`, as
    the suggestion ran them)."""
    wanted = {s.name for s in fits.skills if not s.name_only}

    def point(value, at: float, fit: ClaudeFit | None, head: str, here: bool = False) -> tuple:
        short = len(wanted - fit.full) if fit is not None else None
        if here and fit is None:
            short = fits.short_now
        used = fit.used if fit is not None else None
        return (value, claude_budget(*pair, at), short, used, head, here)

    points = []
    if back:
        fit = fits.at(claude_budget(*pair, CLAUDE_SHARE))
        head = words.LIMIT_STEP_DEFAULT.format(share=_percent(None))
        points.append(point("default", CLAUDE_SHARE, fit, head))
        for at in shares_below(share):
            points.append(point(at, at, fits.at(claude_budget(*pair, at)), words.percent(at)))
    now = fits.at(claude_budget(*pair, share))
    head = words.LIMIT_STEP_NOW.format(share=_percent(share))
    points.append(point(share, share, now, head, True))
    points += [point(at, at, fit, words.percent(at)) for at, fit in ups]
    short, unknown = words.LIMIT_STEP_SHORT, words.LIMIT_STEP_NOT_ALL
    # The place of today costs nothing more, also where the count of it is not what the chat used.
    used = now.used if now is not None else fits.used
    # Of all the skills the next chats list, as the verdict and the window cards count.
    return _limit_steps(points, used, len(fits.skills), "characters", short, unknown)


def _claude_limit(
    home: Path,
    files: list[Path],
    setting: int | None,
    fraction: float | None,
    share: float,
    pair: tuple[int, int] | None,
    fits: _Fits | None,
    keep: bool = False,
) -> dict:
    """Details' "Skill list limit" (spec skill-list-limit): the limit now, the first share on
    Kitden's list (`CLAUDE_SHARES`) above it at which every description the limit cut fits, by
    the same rule as the verdict or else by a count (see `_Fits`), and what that costs; Back to
    the default when the user file has a higher share. `why`: why there is no suggestion. Skills
    set to Name only or Off stay as they are. `keep`: the line keeps its places with nothing to
    suggest (changes wait in the preview, so it must not go while the person works with it)."""
    holder = _limit_file(files)
    user = files[0]
    above = fraction is not None and fraction > CLAUDE_SHARE
    back = None
    if setting is None and holder == user and above:
        back = {"fraction": "default", "label": words.LIMIT_BACK.format(share=_percent(None))}
    limit = {"now": None, "offer": None, "back": back, "note": None, "why": None}
    limit |= {"param": "fraction", "steps": []}
    if setting is not None:
        return limit | {"back": None, "why": words.LIMIT_NOT_FIXED}
    if holder is not None and holder != user:
        place = home_path(str(holder), home)
        return limit | {"back": None, "why": words.LIMIT_NOT_PROJECT.format(file=place)}
    if pair is None or fits is None:
        return limit | {"why": words.LIMIT_NOT_ESTIMATED}
    budget = claude_budget(*pair, share)
    limit["now"] = words.LIMIT_NOW.format(share=_percent(share), n=f"{budget:,}")
    if fits.lines:
        limit["counted"] = fits.lines
    skills, now = fits.skills, fits.at(budget)
    wanted = {s.name for s in skills if not s.name_only}
    shows = back is not None or keep
    if now is not None and wanted <= now.full:
        all_fit: list[tuple[float, ClaudeFit | None]] = []
        if keep:
            all_fit = [(at, now) for at in shares_above(share)]
        steps = _claude_steps(pair, share, fits, back is not None, all_fit) if shows else []
        return limit | {"why": fits.not_needed, "steps": steps}
    # Every share on the list above today's, as the line can be dragged there. Once all fit, a
    # higher share sends the same list: the rule runs no more. Today's share may be off the list.
    ups: list[tuple[float, ClaudeFit | None]] = []
    found = None
    for at in shares_above(share):
        fit = found[1] if found else fits.at(claude_budget(*pair, at))
        ups.append((at, fit))
        if found is None and fit is not None and wanted <= fit.full:
            found = (at, fit)
    if found is None:
        # Nothing on the list fits: the ceiling, or today's share when that is higher still.
        most = words.percent(max(CLAUDE_SHARES[-1], share))
        more = ups if keep else []
        steps = _claude_steps(pair, share, fits, back is not None, more) if shows else []
        return limit | {"why": words.LIMIT_NOT_ENOUGH.format(share=most), "steps": steps}
    offered, fit = found
    limit["steps"] = _claude_steps(pair, share, fits, back is not None, ups)
    shown = words.percent(offered)
    n = len(fit.full)
    say = (words.LIMIT_FITS_ALL if n > 1 else words.LIMIT_FITS_ONE).format(share=shown, n=n)
    extra = fit.used - fits.used
    cost = words.LIMIT_COST.format(chars=_about(extra), tokens=_about(extra / pair[1]))
    note = words.LIMIT_NOTE
    if any(s.name_only for s in skills):
        note = f"{words.LIMIT_KEEPS_CHOSEN} {note}"
    offer = {"fraction": offered, "label": words.LIMIT_SET.format(share=shown), "say": say}
    return limit | {"offer": offer | {"cost": cost}, "note": note}


def _share_then(
    rows, states, weights, model: tuple[int, int], share: float, sent_full: frozenset[str], cap: int
) -> float | None:
    """The share the chat was sent under, when today's does not give its list: the default, or
    a share Kitden offers, whose limit rebuilds what the chat sent. None when none does."""
    for then in CLAUDE_SHARES:
        if same_share(then, share):
            continue
        if _claude_gives(rows, states, weights, claude_budget(*model, then), sent_full, cap):
            return then
    return None


def _list_ends_at(rows, states, budget: int, cap: int) -> bool:
    """The chat's list stops at this limit, whatever the order descriptions are dropped in: the
    room left is less than every description that was not sent. False when it dropped none whose
    size is known: then the list says nothing of the limit. A description's size is its file's;
    with no file, that of the text an earlier chat sent (`earlier`, a built-in skill).

    # checked 2026-11-24 (real log, Claude Code 2.1.330): the client let a list of 30,009
    # characters through 30,000. So up to 0.2% over is still at the limit.
    """
    listed = [r for r in rows if not r.added]
    used = sum(len(r.shown or r.name) + (2 if r.sent is None else 4 + len(r.sent)) for r in listed)
    used += max(0, len(listed) - 1)
    # An empty description has nothing to drop. One longer than the default cap (the cap is a
    # setting) counts at that: a huge one would have no room at several limits.
    dropped = [
        min(len(text), cap, CLAUDE_DESCRIPTION_CAP)
        for r in listed
        if r.sent is None
        and states[r.name] != "name-only"
        and (text := r.full if r.full is not None else r.earlier)
    ]
    return bool(dropped) and -(budget // 500) <= budget - used < min(dropped) + 2


def _share_counted(rows, states, model: tuple[int, int], share: float, cap: int) -> float | None:
    """As `_share_then`, for a chat no limit rebuilds: the share at whose limit its list ends."""
    for then in CLAUDE_SHARES:
        if same_share(then, share):
            continue
        if _list_ends_at(rows, states, claude_budget(*model, then), cap):
            return then
    return None


def _longer_now(row: _Row, cap: int) -> bool:
    """The skill's file has a longer description than the chat sent (changed since, or the cap
    was raised)."""
    return bool(row.full and row.sent is not None and min(len(row.full), cap) > len(row.sent))


def _claude_count(
    rows, states, budget: int, cap: int
) -> tuple[list[ClaudeSkill], ClaudeFit | None]:
    """The list's skills in these states, and the fit when every description fits in the limit.

    Whether everything fits does not depend on the order descriptions are dropped in, so this
    holds also when the rule does not rebuild the chat. The count and the comparison are the
    rule's own (`size <= budget` in claude_rule), with no margin: the client let 30,009 through
    30,000 (see `_list_ends_at`), but Kitden claims no fit its own count is over.
    A description counts as the chat sent it, or as its file is now when that is longer. A
    built-in skill's that the chat did not send counts as an earlier chat sent it (`earlier`).
    One that Kitden cannot find counts at the cap, the worst case; it stops just past the limit,
    as in `_claude_gives`."""
    skills, fit = _claude_count_run(rows, states, budget, cap)
    return skills, fit if fit.size <= budget else None


def _as_counted(row: _Row, cap: int) -> _Row:
    """The row with the description the count takes for it (see `_claude_count`)."""
    if _longer_now(row, cap):
        return replace(row, sent=row.full)
    if row.sent is None and row.full is None and row.earlier is not None:
        return replace(row, sent=row.earlier)
    return row


def _claude_count_run(rows, states, budget: int, cap: int) -> tuple[list[ClaudeSkill], ClaudeFit]:
    """The rule's run that `_claude_count` judges, also where not everything fits."""
    rows = [_as_counted(r, cap) for r in rows]
    run = _claude_run(rows, states, {}, budget, "x" * min(cap, budget + 1), cap=cap)
    assert run is not None  # every size is given
    return run


def _claude_counted(
    rows,
    extras,
    states,
    budget: int,
    used: int,
    sent: frozenset[str],
    changed: bool,
    cap: int,
    same_limit: bool,
    replayed: bool,
) -> _Fits:
    """`_Fits` by count, at today's limit `budget`. `used`: what the chat's list used. `sent`: the
    skills it sent inside its limit, when no setting changed since: it shows that they fit.
    `extras`: the skills that were not in its list. `changed`: the limit was changed after it.
    `same_limit`: the chat was sent under today's limit, and no change in the preview waits.
    `replayed`: the rule rebuilds the chat; only a size it needs for the next ones is missing."""
    # A skill the chat sent, off or Name only now, leaves room: the chat's numbers say less then.
    same_limit = same_limit and not any(
        r.sent is not None and states[r.name] in ("off", "name-only") for r in rows
    )
    listed = {r.name for r in rows}
    chat = rows
    rows = [*rows, *extras]
    skills, run = _claude_count_run(rows, states, budget, cap)
    wanted = frozenset(s.name for s in skills if not s.name_only)
    # What the list uses at today's limit: the chat's own number when it was sent under it (the
    # limit does not count the skills added during the chat, so the list may have used more).
    # Else the count's estimate: which descriptions the limit keeps is not known, but what the
    # list uses is within one description of the limit.
    now_used = min(used, budget) if same_limit else run.used

    def at(limit: int) -> ClaudeFit | None:
        fit = _claude_count(rows, states, limit, cap)[1]
        if fit is None and wanted <= sent and limit >= budget:
            return ClaudeFit(wanted, frozenset(s.name for s in skills) - wanted, used, used)
        return fit

    bare = [
        r
        for r in rows
        if r.sent is None and r.full is None and states[r.name] not in ("off", "name-only")
    ]
    unknown = sum(r.earlier is None for r in bare)
    earlier = len(bare) - unknown
    lines = [] if replayed else [words.LIMIT_COUNTED]
    if unknown:
        line = _many(unknown, words.LIMIT_COUNTED_ONE, words.LIMIT_COUNTED_MANY)
        lines.append(line.format(n=unknown, cap=f"{cap:,}"))
    if earlier:
        line = _many(earlier, words.LIMIT_EARLIER_ONE, words.LIMIT_EARLIER_MANY)
        lines.append(line.format(n=earlier))
    lines += _added_lines(extras, states)
    all_sent = wanted & listed <= {r.name for r in rows if r.sent is not None}
    why = words.LIMIT_NOT_NEEDED if changed or all_sent else words.LIMIT_NOT_WHY
    # The chat's own list says how many show only a name at today's limit, while no skill joins.
    short_now = None
    if same_limit and not any(states[r.name] != "off" for r in extras):
        names = sum(r.sent is None and states[r.name] not in ("off", "name-only") for r in chat)
        short_now = names or None
    return _Fits(skills, now_used, at, why, lines, True, short_now)


def _added_lines(extras, states) -> list[str]:
    """Details' line on the skills the next chat lists and the last chat did not."""
    n = sum(states[r.name] != "off" for r in extras)
    return [_many(n, words.LIMIT_ADDED_ONE, words.LIMIT_ADDED_MANY).format(n=n)] if n else []


def _claude_weights(claude: ClaudeFolder, at_ms: int) -> dict[str, float]:
    """Each skill's use, aged from the chat's time.

    # checked 2026-11-09 (real ~/.claude.json): skillUsage maps a skill's name, as the log
    # writes it (plugin prefix too), to {usageCount, lastUsedAt (ms)}.
    """
    state = as_dict(Reader("claude_code").json(claude.state))
    weights = {}
    for name, entry in as_dict(state.get("skillUsage")).items():
        count, last = as_dict(entry).get("usageCount"), as_dict(entry).get("lastUsedAt")
        if _whole(count) and _whole(last):
            weights[name] = claude_weight(count, last, at_ms)
    return weights


def _claude_run(
    rows,
    states,
    weights,
    budget,
    unknown: str | None = None,
    *,
    as_sent: bool = False,
    cap: int = CLAUDE_DESCRIPTION_CAP,
) -> tuple[list[ClaudeSkill], ClaudeFit] | None:
    """The rule on the list's skills in these states; None when a size is not known.
    `unknown` stands in for a description Kitden cannot find. `as_sent`: as in the chat itself,
    where the skills added during it were sent whole, outside the limit."""
    skills = [
        ClaudeSkill(
            r.name,
            r.sent if r.sent is not None else r.full if r.full is not None else unknown,
            r.always_full,
            states[r.name] == "name-only",
            weights.get(r.name, 0.0),
            r.shown,
        )
        for r in rows
        if states[r.name] != "off" and not (as_sent and r.added)
    ]
    try:
        fit = claude_rule(skills, budget, cap)
    except ValueError:
        return None
    if as_sent:
        late = {r.name for r in rows if r.added and states[r.name] != "off"}
        fit = replace(fit, full=fit.full | late)
    return skills, fit


def _claude_gives(rows, states, weights, budget, sent_full: frozenset[str], cap: int) -> bool:
    """This limit rebuilds the sent list, whatever the size of a description Kitden cannot find.

    The rule gives the same list with every such description empty and with every one at the
    cap, so it gives it for any size between: a skill that fits at the cap fits when smaller,
    and one that does not fit when all are empty never fits. A description longer than the whole
    limit cannot fit either way, so the longer one stops just past the limit: the cap is a
    setting, and a huge number in it must not make a huge text."""
    for unknown in ("", "x" * min(cap, budget + 1)):
        run = _claude_run(rows, states, weights, budget, unknown, as_sent=True, cap=cap)
        if run is None or run[1].full != sent_full:
            return False
    return True


def _unchanged(files: list[Path], at_ms: int) -> bool:
    """No settings file changed after the chat, so the skills' states today were its states.
    A file removed since is not seen."""
    for path in files:
        try:
            if path.stat().st_mtime * 1000 > at_ms:
                return False
        except OSError:  # no such file
            continue
    return True


def _chosen(
    rows, states, weights, budget, checked: bool, settled: bool, cap: int
) -> tuple[set[str], bool]:
    """The skills that showed only a name because they were set to Name only, not because of
    the limit; and True when Kitden can tell only that they are set so now.

    Kitden cannot see past settings. It knows a skill was Name only at the chat when no settings
    file changed since (`settled`), or when the rule, with that skill on, would not rebuild the
    list: only its setting explains it. When the limit alone explains it, it stays a misfit.
    Without a check Kitden says only that it is set to Name only now."""
    named = {r.name for r in rows if r.sent is None and states[r.name] == "name-only"}
    if not named or settled:
        return named, False
    if not checked:
        return named, True
    sent_full = frozenset(r.name for r in rows if r.sent is not None)
    needed = set()
    for name in named:
        run = _claude_run(rows, states | {name: "on"}, weights, budget, as_sent=True, cap=cap)
        if run is not None and run[1].full != sent_full:
            needed.add(name)
    return needed, False


def _claude_fact(rows: list[_Row], when: str, chosen: set[str], now: bool, cap: int) -> dict:
    """What the last chat sent: characters per skill sent, and those of descriptions not sent.
    Only the log counts. `chosen` showed only a name by their setting (see `_chosen`): they are
    told apart and are no misfit. The misfit names the other skills that showed only a name."""
    sent: dict[str, int] = {}
    over: dict[str, int] = {}
    names = 0
    for r in rows:
        if r.sent is not None:
            # The log's own length: the cap may have been another one when the chat was sent.
            sent[r.name] = len(r.shown or r.name) + 4 + len(r.sent)
            continue
        names += len(r.shown or r.name) + 2
        if r.full is not None and r.name not in chosen:
            over[r.name] = min(len(r.full), cap) + 2
    used = sum(sent.values()) + names + max(0, len(rows) - 1)
    n, picked = len(rows), len(chosen)
    bad = n - len(sent) - picked
    misfit = None
    if bad:
        short = words.CLAUDE_SHORT_NAMES.format(bad=bad, n=n)
        skills, them = _many(n, "skill", "skills"), _many(bad, "it", "them")
        say = words.CLAUDE_NAMES_ONLY.format(when=when, bad=bad, n=n, skills=skills, them=them)
        missed = [r.name for r in rows if r.sent is None and r.name not in chosen]
        misfit = {"kind": "name", "n": bad, "names": missed}
    else:
        short = words.CLAUDE_SHORT_ALL.format(n=n)
        say = _many(n, words.CLAUDE_ONE_SENT, words.CLAUDE_ALL_SENT).format(when=when, n=n)
    if picked:
        count = words.CLAUDE_MORE.format(n=picked) if bad else str(picked)
        rest = (words.CLAUDE_SET_NOW if now else words.CLAUDE_CHOSEN).format(
            chosen=count, are=_many(picked, "is", "are")
        )
        if bad:
            say = f"{say} {rest}"
        else:
            but = _many(n, words.CLAUDE_ONE_SENT_BUT, words.CLAUDE_ALL_SENT_BUT)
            say = but.format(when=when, n=n, rest=rest)
    result = {"short": short, "say": say, "sent": sent, "over": over, "used": used}
    return result | {"size": used + sum(over.values()), "room": None, "misfit": misfit}


def _claude_estimate(
    skills: list[ClaudeSkill], fit: ClaudeFit, on: str, frame: str, cap: int
) -> dict:
    sent = {}
    over = {}
    for s in skills:
        if s.name in fit.full:
            sent[s.name] = len(s.label) + 4 + min(len(s.description or ""), cap)
        elif not s.name_only:
            over[s.name] = min(len(s.description or ""), cap) + 2
    n = len(skills)
    chosen = sum(s.name_only for s in skills)
    bad = n - len(fit.full) - chosen
    if bad:
        skills_word, them = _many(n, "skill", "skills"), _many(bad, "it", "them")
        body = words.CLAUDE_WOULD_DROP.format(on=on, bad=bad, n=n, skills=skills_word, them=them)
    elif chosen:
        them = "1 skill shows" if chosen == 1 else f"{chosen} skills show"
        body = words.CLAUDE_WOULD_KEEP_CHOSEN.format(on=on, chosen=them)
    else:
        body = words.CLAUDE_WOULD_KEEP.format(on=on)
    short = words.CLAUDE_WOULD_SHORT.format(bad=bad, n=n) if bad else words.WOULD_FIT.format(n=n)
    result = {"short": short, "say": frame.format(body), "sent": sent, "over": over}
    misfit = {"kind": "name", "n": bad} if bad else None
    return result | {"used": fit.used, "size": fit.size, "room": None, "misfit": misfit}


def _claude_note(
    row: _Row,
    state: str,
    side: int | None,
    size: int,
    explained: bool = True,
    can_free: bool = True,
    cap: int = CLAUDE_DESCRIPTION_CAP,
) -> str | None:
    """`explained`: the limit rebuilds the list, so it is why a description is missing.
    `can_free`: some skill with a description has a switch."""
    if state == "off":
        return words.NOTE_OFF
    if row.item is None and not _ruled(row):
        return words.NOTE_BUILT_IN if row.built_in else words.NOTE_NO_ITEM
    if state in ASKED:
        return words.NOTE_ONLY_ASKED
    if side is None:
        return words.NOTE_NOT_LISTED
    if row.item is not None and from_plugin(row.item):
        return words.NOTE_PLUGIN
    if state == "name-only":
        return words.NOTE_NAME_ONLY
    if side == 0:
        return words.NOTE_FREES.format(n=f"{min(size, cap) + 2:,}")
    if not explained:
        return words.NOTE_NOT_SENT
    return f"{words.NOTE_NO_ROOM} {words.NOTE_FREE_ROOM}" if can_free else words.NOTE_NO_ROOM


def _model_name(model: str | None) -> str | None:
    """ "Opus 5.5" for claude-opus-5-5; any other id as it is."""
    parts = (model or "").split("-")
    if len(parts) >= 3 and parts[0] == "claude":
        numbers = [p for p in parts[2:] if p.isdigit() and len(p) <= 2]
        return f"{parts[1].capitalize()} {'.'.join(numbers)}".strip()
    return model


def _claude(
    inventory,
    home: Path,
    claude: ClaudeFolder,
    folder: str | None,
    draft: dict,
    anywhere: bool,
    asked=None,
) -> dict:
    """`asked`: the skill list's share a tray row asks for (a number or "default")."""
    client = "claude_code"
    found = last_claude_list(claude.config, folder)
    if found is None and anywhere and folder is not None:
        found = last_claude_list(claude.config, None)
    if found is None or isinstance(found, Unreadable):
        return _no_list(client, _skills(inventory, client, folder), found)
    if not found.skills:
        return _disk_card(client, [], words.NOTHING_TO_FIT, [])
    date, at_ms = _when(found.at)
    # The chat's own folder: its project's skills were in its list.
    items = _skills(inventory, client, found.folder)
    loaded = {_name(client, i): i for i in items}
    turned_off = _off_skills(inventory, client, found.folder)
    by_name = turned_off | loaded
    plugins = _claude_plugins(inventory, home, claude, found.folder)
    rows = []
    for name, text in found.skills:
        item = by_name.get(name)
        path = item.source.path if item else _app_path(home, claude, name)
        rows.append(
            _claude_row(
                name, text, item, path, shown=found.shown.get(name, ""), added=name in found.added
            )
        )
    # The skills there that the last chat's list does not hold: the next chat lists them, unless
    # they are off or only asked for.
    listed = {r.name for r in rows}
    extras = [
        _claude_row(name, None, item, item.source.path)
        for name, item in loaded.items()
        if name not in listed
    ]
    files = _claude_files(home, claude, found.folder)
    rules = _built_in_rules(files)
    # `always_full` is checked against each chat: a wrong name here and the rule no longer
    # rebuilds the list.
    rows = [_tagged(r) for r in rows]
    # Off before the chat, so in no list: they wait on the page, and count once the tray turns one
    # on. Your own skills, and the built-in ones a setting keeps out; a plugin's come back with it.
    waiting = [
        _claude_row(name, None, item, item.source.path)
        for name, item in turned_off.items()
        if name not in listed and name not in loaded and not from_plugin(item)
    ]
    waiting += [
        _tagged(_Row(name, None, None, None))
        for name, (state, _) in rules.items()
        if state in ("off", *ASKED) and name not in listed and name not in by_name
    ]
    rows_now = [*rows, *extras, *waiting]
    # Today's states; and those of the chat as far as its list tells: what it lists was not off,
    # and what it sent with a description was not Name only.
    states = {r.name: _row_state(r, rules, plugins) for r in rows_now}
    then = states | {
        r.name: "on"
        for r in rows
        if states[r.name] == "off" or (states[r.name] == "name-only" and r.sent is not None)
    }
    off = _not_loaded(inventory, client, found.folder, loaded)
    off |= {name for name, state in states.items() if state in ASKED}
    # What the next chats list: today's skills, in today's states (`rows_now`); and what they list
    # once the preview's changes are applied.
    states_now = states | {name: "off" for name in states if name in off}
    changes = _changes(draft, states, SWITCHES[client])
    states_next = states_now | changes
    weights = _claude_weights(claude, at_ms)

    setting = _claude_setting(files)
    fraction = _claude_fraction(files)
    # checked 2026-11-24 (Claude Code 2.1.311): with both set, the fixed budget is the limit; the
    # list was the same with and without the share.
    by_fraction = setting is None and fraction is not None
    share = fraction if by_fraction and fraction is not None else CLAUDE_SHARE
    cap = _claude_cap(files)
    model = CLAUDE_WINDOWS.get(found.model or "")
    window = model[0] if model else None
    budget = setting if setting is not None else (claude_budget(*model, share) if model else None)
    base = _claude_run(rows_now, states_now, weights, budget, cap=cap) if budget else None
    sent_full = frozenset(r.name for r in rows if r.sent is not None)
    as_sent = _claude_run(rows, then, weights, budget, as_sent=True, cap=cap) if budget else None
    checked = as_sent is not None and as_sent[1].full == sent_full
    # Settings changed after the chat: the share may differ from the one the chat was sent
    # under. When another share rebuilds the chat's list, the chat's card shows that limit, and
    # the estimates use today's (`changed`).
    moved = not _unchanged(files, at_ms)
    then_share = None
    if setting is None and model and not checked and moved:
        then_share = _share_then(rows, then, weights, model, share, sent_full, cap)
        checked = then_share is not None and base is not None
    # The log does not say the window: take the only one whose limit rebuilds the list.
    worked_out = two_limits = False
    rate = 0
    # The window and characters per token the limit is worked out from; None with a fixed limit.
    pair = model if setting is None else None
    if setting is None and not checked:
        fits = [
            candidate
            for candidate in CLAUDE_CANDIDATES
            if _claude_gives(rows, then, weights, claude_budget(*candidate, share), sent_full, cap)
        ]
        if len({size for size, _ in fits}) == 1:
            worked_out = True
            window, rate = fits[0]
            two_limits = len(fits) > 1
            budget = None if two_limits else claude_budget(*fits[0], share)
            pair = None if two_limits else fits[0]
            # None when a size is not known: the window is sure, an estimate is not.
            base = _claude_run(rows_now, states_now, weights, budget, cap=cap) if budget else None
            checked = base is not None

    # A built-in skill has no file: when the rule cannot rebuild the chat, the place its list
    # stops at and the count take its description from an earlier chat's list. Not in `full`,
    # which is what is on disk: the rule stays exact and never reads it.
    # A change in the preview may turn on a skill whose size is not known: then the next chats are
    # counted too.
    ruled = base
    if changes and budget:
        ruled = _claude_run(rows_now, states_next, weights, budget, cap=cap)
    if setting is None and not (checked and base is not None and ruled is not None):
        bare = [r for r in (*rows, *waiting) if r.built_in and r.full is None and r.sent is None]
        found_earlier = earlier_descriptions(claude.config, {r.name for r in bare})
        for r in bare:
            r.earlier = found_earlier.get(r.name)

    # The limit the chat was sent under: today's, the share found above, or not known when the
    # settings changed since and nothing rebuilds the chat's list (then no limit line is drawn).
    then_budget = budget
    unsure = moved and not checked and then_share is None and pair is not None
    if unsure and budget is not None and not _list_ends_at(rows, then, budget, cap):
        # The rule cannot say; the place where the chat's list stops can (`_list_ends_at`). When
        # the settings have a share it does not stop at, and it stops at another share's limit,
        # that share was set since. (A window worked out from the list gives it at today's.)
        then_budget = None
        if by_fraction and not worked_out and model:
            then_share = _share_counted(rows, then, model, share, cap)
    if then_share is not None and model:
        then_budget = claude_budget(*model, then_share)
    when = _on_date(date)
    settled = bool(date) and not moved
    chosen, now = _chosen(rows, then, weights, then_budget, checked, settled, cap)
    fact = _claude_fact(rows, when, chosen, now, cap)
    misfit = fact["misfit"] is not None
    if checked and not misfit and then_budget is not None:
        left = f"{then_budget - fact['used']:,}"
        fact["room"] = words.ROOM_LEFT.format(left=left, unit="characters")
    if setting is not None:
        title = words.LIMIT_TITLE.format(n=f"{setting:,}", unit="characters")
        models = words.CLAUDE_SETTING
    else:
        title = words.WINDOW_TITLE.format(size=_size(window)) if window else words.UNKNOWN_WINDOW
        source = words.WORKED_OUT if worked_out else None
        models = " · ".join(p for p in (_model_name(found.model), found.surface, source) if p)
    windows = [_window_card(title, models, _tag(date), then_budget, fact)]

    # What the next chats get at each limit, in these states: by the rule, or by a count when the
    # rule does not rebuild the chat (or cannot run) but its limit is known.
    def fits_in(states: dict[str, str], run: tuple | None, waits: bool) -> _Fits | None:
        if pair is None or budget is None:
            return None
        new = [*extras, *waiting]
        if checked and run is not None:
            return _Fits(
                run[0],
                run[1].used,
                lambda limit: claude_rule(run[0], limit, cap),
                words.LIMIT_NOT_NEEDED,
                _added_lines(new, states),
                False,
            )
        # What the chat sent inside its limit, when no setting changed since.
        late = {r.name for r in rows if r.added or _longer_now(r, cap)}
        known = frozenset() if moved else sent_full - late
        is_new = then_share is not None
        same = then_budget == budget and not waits
        return _claude_counted(
            rows, new, states, budget, fact["used"], known, is_new, cap, same, checked
        )

    fits_now = fits_in(states_now, base, False)
    fits_next = fits_in(states_next, ruled, True) if changes else fits_now
    counted = fits_now is not None and fits_now.counted
    # A count holds for the next chats unless the chat itself goes against it: the list it sent has
    # room for everything by the count and was not sent whole, or the other way round.
    holds = then_budget is None
    if counted and then_budget is not None:
        first = [r for r in rows if not r.added]
        whole = all(r.sent is not None or then[r.name] == "name-only" for r in first)
        holds = whole == (_claude_count(first, then, then_budget, cap)[1] is not None)
    with_limit = words.WITH_LIMIT if setting is not None else _on(window)

    def count_says(states: dict[str, str], limit: int, frame: str) -> dict:
        """The estimate for a limit by a count: `result` is None where not everything fits."""
        skills, fit = _claude_count(rows_now, states, limit, cap)
        if fit is None:
            say = frame.format(words.CLAUDE_WOULD_NOT_FIT.format(on=_on(window)))
            return {"say": say, "result": None, "full": frozenset()}
        result = _claude_estimate(skills, fit, _on(window), frame, cap)
        return {"say": result["say"], "result": result, "full": fit.full}

    # The next chats list other skills than this list, or in other states: some came or went, or
    # were added during the chat (sent whole, outside the limit).
    listed_then = {r.name: then[r.name] == "name-only" for r in rows}
    listed_now = {name: s == "name-only" for name, s in states_now.items() if s != "off"}
    other_skills = listed_now != listed_then or any(r.added and r.name in listed_now for r in rows)
    # A skill the fact counts as cut by the limit is Name only now. Whether it was so in the chat
    # Kitden cannot tell (`_chosen`): it gives the estimate and does not say that a skill changed.
    cut_now_named = any(
        r.sent is None and listed_now.get(r.name) and r.name not in chosen for r in rows
    )
    # What Kitden expects from the setup as it is now, said under the chat's verdict; the picture
    # follows it.
    changed, expected = [], None
    say = None
    if budget is not None and (then_share is not None or other_skills or cut_now_named):
        if checked and base is not None:
            expected = _claude_estimate(base[0], base[1], with_limit, words.ESTIMATE, cap)
            if expected["misfit"] is None:
                left = f"{budget - base[1].used:,}"
                expected["room"] = words.ROOM_LEFT.format(left=left, unit="characters")
            say = expected["say"]
        elif counted and (then_share is not None or holds):
            count = count_says(states_now, budget, words.ESTIMATE)
            expected, say = count["result"], count["say"]
    if say is not None:
        shown = _percent(share)
        if then_share is not None and other_skills:
            changed = [words.LIMIT_AND_SKILLS_CHANGED.format(share=shown), say]
        elif then_share is not None:
            changed = [words.LIMIT_CHANGED.format(share=shown), say]
        else:
            changed = [words.SKILLS_CHANGED, say] if other_skills else [say]
    if base is not None and checked and setting is None and window in CLAUDE_OTHER_WINDOW:
        other, per_token = CLAUDE_OTHER_WINDOW[window]
        shown = ""  # which models have that window is not in any file Kitden can read
        if worked_out:
            per_token = rate  # the rate this chat's own list gives
        limit = claude_budget(other, per_token, share)
        skills = base[0]
        fit = claude_rule(skills, limit, cap)
        result = _claude_estimate(skills, fit, _on(other), words.ESTIMATE, cap)
        title = words.WINDOW_TITLE.format(size=_size(other))
        windows.append(_window_card(title, shown, words.ESTIMATE_TAG, limit, result))

    # The limit line counts what the preview's changes leave. While they wait it keeps the places
    # above today's share that the setup without them has, or that a new limit in the tray is on.
    keep = (_asked_share(asked) or 0) > share
    if changes and not keep:
        today = _claude_limit(home, files, setting, fraction, share, pair, fits_now)
        keep = today["offer"] is not None
    limit_card = _claude_limit(home, files, setting, fraction, share, pair, fits_next, keep)
    # A share in the tray counts only where Kitden would write it: the user file decides.
    new_share = _asked_share(asked) if limit_card["now"] is not None else None
    if new_share is not None and abs(new_share - share) < 1e-9:
        new_share = None
    after = None
    budget_after = budget
    if new_share is not None and pair is not None:
        budget_after = claude_budget(*pair, new_share)
    if (changes or new_share is not None) and budget_after is not None:
        run = _claude_run(rows_now, states_next, weights, budget_after, cap=cap)
        if checked and run is not None and base is not None:
            skills, fit = run
            full = base[1].full
            gets = [r.name for r in rows_now if r.name not in changes and r.name in fit.full - full]
            loses = [
                r.name for r in rows_now if r.name not in changes and r.name in full - fit.full
            ]
            result = _claude_estimate(skills, fit, with_limit, words.AFTER_APPLY, cap)
            say = f"{result['say']} {_swap(client, gets, loses)}".strip()
            after = {"say": say, "gets": gets, "loses": loses, "result": result}
            after["budget"] = budget_after
        elif not checked and fits_next is not None and (new_share is not None or holds):
            # A count says what a limit gives; with a switch alone it has to hold for the chat.
            expect = count_says(states_next, budget_after, words.AFTER_APPLY)
            full = expect["full"]
            gets = [
                r.name for r in rows if r.name not in changes and r.sent is None and r.name in full
            ]
            say = f"{expect['say']} {_swap(client, gets, [])}".strip()
            after = {"say": say, "gets": gets, "loses": [], "result": expect["result"]}
            after["budget"] = budget_after

    explained = checked or two_limits
    # A skill's note goes by the side it has now: the estimate's, or else the chat's.
    sent_now = sent_full if expected is None else frozenset(expected["sent"])
    can_free = any(
        r.name in sent_now
        and states[r.name] == "on"
        and not _held(r, rules)
        and (_ruled(r) or (r.item is not None and not from_plugin(r.item)))
        for r in rows
    )
    project_rule = words.NOTE_PROJECT_RULE.format(Path(found.folder or "").name)
    skills = []
    for r in rows:
        side = 0 if r.sent is not None else 1
        size = len(r.full) if r.full is not None else len(r.sent or "")
        side_now = 0 if r.name in sent_now else 1
        note = _claude_note(r, states[r.name], side_now, size, explained, can_free, cap)
        text, seen = (
            r.page_text if r.full is not None else r.sent,
            _seen(r.full, r.sent, side, None if r.added else _cap_then(cap, r.sent)),
        )
        if seen is not None and r.plain is not None:
            seen = min(seen, len(r.plain))  # the page shows the description, not when_to_use
        source, outside = _outside(r, plugins)
        held = _held(r, rules)
        if held:
            note = project_rule
        elif states[r.name] == "off":
            outside = None  # off says more than where it comes from
        offer = plugins.switch(r, rows)
        skills.append(
            _skill(
                client,
                r.name,
                r.item,
                size,
                side,
                _plugin_note(outside or note, offer),
                r.built_in,
                text,
                seen,
                states[r.name],
                offer,
                source,
                held,
            )
        )
    for r in [*extras, *waiting]:
        note = _claude_note(r, states[r.name], None, 0)
        offer = plugins.switch(r, rows)
        held = _held(r, rules)
        skills.append(
            _skill(
                client,
                r.name,
                r.item,
                len(r.full or ""),
                None,
                project_rule if held else _plugin_note(note, offer),
                r.built_in,
                description=r.page_text,
                state=states[r.name],
                plugin_switch=offer,
                held=held,
            )
        )

    version = f" {found.version}" if found.version else ""
    surface = f" {found.surface}" if found.surface else ""
    if checked:
        check = words.HOW_CLAUDE_CHECKED
    elif two_limits:
        check = words.HOW_TWO_LIMITS
    else:
        check = words.HOW_NOT_MATCHED if base is not None else words.HOW_NOT_RUN
    how = [
        words.HOW_CLAUDE_LIST.format(version=version, when=when, surface=surface),
        *([words.HOW_CLAUDE_WINDOW.format(size=_size(window))] if worked_out and window else []),
        words.HOW_CLAUDE_RULE,
        f"{words.HOW_CLAUDE_CHECK} {check}",
        *limit_card.get("counted", []),
        *([words.HOW_CLAUDE_FRACTION.format(share=_percent(fraction))] if by_fraction else []),
        words.HOW_CLAUDE_SETTING if setting is not None else words.HOW_CLAUDE_SHELL,
        *([words.HOW_CLAUDE_CAP.format(n=f"{cap:,}")] if cap != CLAUDE_DESCRIPTION_CAP else []),
        words.HOW_CLAUDE_SURFACE,
        words.HOW_CLAUDE_REST,
        *([limit_card["why"]] if limit_card["why"] else []),
    ]
    parts = {}
    if setting is not None:
        limit_set = words.CONTEXT_LIMIT_SET[client].format(n=f"{setting:,}")
        parts["lede"] = words.CONTEXT_LEDE + limit_set
    elif by_fraction:
        parts["lede"] = words.CONTEXT_LEDE + words.CLAUDE_SHARE_SET.format(share=_percent(share))
    return _card(
        client,
        **parts,
        # Grey: Kitden cannot judge that chat (the limit may have dropped a skill set now).
        lamp="warn" if misfit else "none" if now else "ok",
        # An estimate that cannot be checked is explained under "How this is counted".
        message=words.TWO_LIMITS if two_limits and not checked else None,
        fact={
            "date": date,
            "surface": found.surface,
            "folder": found.folder,
            "version": found.version,
        },
        checked=checked,
        windows=windows,
        skills=skills,
        after=after,
        how=how,
        limit=limit_card,
        changed=changed,
        now=expected | {"budget": budget} if expected else None,
    )


# Codex


def _codex_limit(codex_home: Path) -> int | None:
    """`[skills] max_context_tokens` in config.toml, when it is a whole number.

    # checked 2026-11-06 (Codex docs, skills.max_context_tokens): when set, it is the limit.
    """
    config = as_dict(Reader("codex").toml(codex_home / "config.toml"))
    value = as_dict(config.get("skills")).get("max_context_tokens")
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _codex_cap(full: str | None) -> int | None:
    """The most of a description Codex sends: all of one up to 1,024 characters, else the first
    1,021 and `...` (rules.codex_catalog)."""
    if full is None or len(full) <= CODEX_DESCRIPTION_CAP:
        return None
    return CODEX_DESCRIPTION_CAP - 3


def _codex_kind(sent: int | None, full: int) -> str:
    """Codex sends at most the first 1,024 characters of a description: that much is full."""
    if sent is None:
        return "out"
    return "full" if sent >= min(full, CODEX_DESCRIPTION_CAP) else "cut"


def _codex_cuts(rows: list[_Row]) -> list[int]:
    """The lengths sent of the descriptions that were cut, among those whose full text is
    known."""
    sent = [(len(r.sent), len(r.then)) for r in rows if r.sent is not None and r.then is not None]
    return [kept for kept, full in sent if _codex_kind(kept, full) == "cut"]


def _codex_added(rows: list[_Row]) -> list[_Row]:
    """Mark the skills read from a newer version whose shorter text in the chat may be the
    whole old description, with the rest added by the update. Codex cuts every long description
    at about one length (334-338 on 2026-11-22), so it is a cut only at a length that a skill
    read from the chat's own file was cut at."""
    cuts = _codex_cuts([r for r in rows if not r.moved])
    out = []
    for r in rows:
        kept = len(r.sent or "")
        shorter = r.moved and kept and r.then is not None
        shorter = shorter and _codex_kind(kept, len(r.then or "")) == "cut"
        if shorter and not (cuts and min(cuts) <= kept <= max(cuts)):
            r = replace(r, changed=True)
        out.append(r)
    return out


def _codex_off(inventory, codex_home: Path, folder: str | None) -> Callable[[str], bool]:
    """Whether the skill at a path is off there now, by itself or with its plugin. By the path in
    config.toml, not by Kitden's item: an off skill, and one inside another's folder, has none."""
    off = skills_off(as_dict(Reader("codex").toml(codex_home / "config.toml")))
    loaded = effective_view(inventory, "codex", folder).items
    plugins_off = {
        i.name
        for i in inventory.items
        if i.client == "codex" and i.kind is ItemKind.PLUGIN and i.project in (None, folder)
    } - {i.name for i in loaded if i.kind is ItemKind.PLUGIN}

    def is_off(path: str) -> bool:
        return os.path.realpath(path) in off or plugin_at(path) in plugins_off

    return is_off


def _codex_policy(path: str) -> Path:
    return Path(path).parent / "agents/openai.yaml"


def _codex_as_then(path: str, at_ms: int) -> bool:
    """Nothing that puts the skill on Codex's list or keeps it off was written after the chat."""
    return _unchanged([Path(path), _codex_policy(path)], at_ms)


def _codex_hidden(path: str) -> bool:
    """Codex does not list this skill: its `agents/openai.yaml` keeps it for when it is asked for.

    # checked 2026-11-25 (learn.chatgpt.com/docs/build-skills: `allow_implicit_invocation`; that
    # the skill is then not on the list: codex-rs/ext/skills/src/provider/host.rs)
    """
    try:
        text = _codex_policy(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return ONLY_ASKED.search(text) is not None


def _codex_new(
    extras: list[Item], found: CodexSent, names_only: bool, at_ms: int
) -> tuple[list[_Row], dict[str, str], list[str]]:
    """The skills there that the last chat's list does not hold and the next one will: their rows,
    the path each has on the list, and the names of those whose line Kitden cannot tell (a skill
    that is a link, or under a root that the list does not have). Codex skips a SKILL.md with no
    description. When the list had names only, skills may have been left out of it: then only one
    whose file, or policy file, was written after the chat counts."""
    rows, shown, unknown = [], {}, []
    for item in extras:
        path = item.source.path or ""
        text = _description(path)
        if not text or _codex_hidden(path):
            continue
        if names_only and _codex_as_then(path, at_ms):
            continue
        line = None if item.source.link_path else found.path_of(path)
        if line is None:
            unknown.append(item.name)
        else:
            rows.append(_Row(item.name, None, item, text, path))
            shown[item.name] = line
    return rows, shown, unknown


def _codex_order(rows: list[_Row], new: list[_Row]) -> list[_Row]:
    """`new` among the list's rows, in Codex's order: its own skills, then the project's, then the
    user's, each by name. At the end when the list itself is in another order.

    # checked 2026-11-25 (codex-rs/ext/skills/src/render.rs order_entries, and real lists)
    """

    def place(r: _Row) -> tuple[int, str]:
        if "/.system/" in r.path:
            return 0, r.name
        return 1 if r.item is not None and r.item.project else 2, r.name

    in_order = all(place(a) <= place(b) for a, b in pairwise(rows))
    return sorted([*rows, *new], key=place) if in_order else [*rows, *new]


def _codex_same(rows: list[_Row], fit: CodexFit, names_only: bool) -> bool:
    """The rule leaves out, cuts and keeps the same skills as the log, at the same length: the
    log's cuts may differ by a few characters (366-370 on 2026-10-30), so the rule's length
    must fall among them."""
    for r in rows:
        if r.changed:  # the rule ran on the new text: nothing of the chat's to match
            continue
        logged = None if r.sent is None else len(r.sent)
        full = len(r.full or "")
        if _codex_kind(logged, full) != _codex_kind(fit.sent.get(r.name), full):
            return False
    if names_only:
        return True
    cuts = _codex_cuts(rows)
    return not cuts or (fit.cap is not None and min(cuts) <= fit.cap <= max(cuts))


def _codex_fact(
    rows: list[_Row], names_only: bool, when: str, shown: dict[str, str], table: int
) -> dict:
    """What the last chat sent: tokens per line sent, and those of the parts not sent. `shown`:
    each skill's path as the list shows it; `table`: tokens of the list's roots table. The
    misfit names the skills left out, or else those whose description was cut."""
    sent: dict[str, int] = {}
    over: dict[str, int] = {}
    for r in rows:
        skill = CodexSkill(r.name, r.full or "", shown.get(r.name, r.path))
        if r.sent is not None:
            sent[r.name] = codex_tokens(codex_line(skill, r.sent))
        if r.then is not None:
            whole = codex_tokens(codex_line(skill, codex_catalog(r.then)))
            if whole > sent.get(r.name, 0):
                over[r.name] = whole - sent.get(r.name, 0)
    used = table + sum(sent.values())
    n = len(rows)
    out = sum(r.sent is None for r in rows)
    cuts = _codex_cuts(rows)
    # Full or cut only for skills whose full size is known; else only what the log shows.
    unknown = sum(r.sent is not None and r.then is None for r in rows)
    skills = _many(n, "skill", "skills")
    if out:
        short = words.CODEX_SHORT_OUT.format(out=out)
        them = _many(out, "it", "them")
        say = words.CODEX_LEFT_OUT.format(when=when, out=out, n=n, skills=skills, them=them)
    elif cuts and names_only:
        short = words.CODEX_SHORT_CUT.format(bad=len(cuts), n=n)
        say = words.CODEX_NAMES.format(when=when)
    elif cuts:
        low, high = min(cuts), max(cuts)
        cut = f"{low:,}" if low == high else f"{low:,}–{high:,}"
        bad = len(cuts)
        short = words.CODEX_SHORT_CUT.format(bad=bad, n=n)
        say = words.CODEX_CUT.format(
            when=when,
            bad=bad,
            n=n,
            cut=cut,
            descriptions=_many(n, "description", "descriptions"),
            were=_many(bad, "was", "were"),
            their=_many(bad, "its", "their"),
        )
        if unknown:
            more = _many(unknown, words.CODEX_ONE_UNKNOWN, words.CODEX_MORE_UNKNOWN)
            say = f"{say} {more.format(n=unknown)}"
    elif unknown:
        short = words.CODEX_SHORT_SENT.format(n=n)
        their = _many(n, "its", "their")
        say = words.CODEX_SENT_UNKNOWN.format(when=when, n=n, skills=skills, their=their)
    else:
        short = words.CODEX_SHORT_ALL.format(n=n)
        say = _many(n, words.CODEX_ONE_SENT, words.CODEX_ALL_SENT).format(when=when, n=n)
    kept = {
        r.name: len(r.sent)
        for r in rows
        if r.sent is not None
        and r.then is not None
        and _codex_kind(len(r.sent), len(r.then)) == "cut"
    }
    misfit = None
    if out:
        misfit = {"kind": "out", "n": out, "names": [r.name for r in rows if r.sent is None]}
    elif cuts:
        misfit = {"kind": "cut", "n": len(cuts), "names": list(kept)}
    result = {"short": short, "say": say, "sent": sent, "over": over, "used": used, "kept": kept}
    return result | {
        "size": used + sum(over.values()),
        "room": None,
        "misfit": misfit,
        "bad": out + len(cuts),
        "unknown": bool(unknown),
    }


def _codex_estimate(skills: list[CodexSkill], fit: CodexFit, on: str, frame: str) -> dict:
    sent = {}
    over = {}
    for s in skills:
        kept = fit.sent.get(s.name)
        if kept is not None:
            sent[s.name] = codex_tokens(codex_line(s, codex_catalog(s.description)[:kept]))
        whole = codex_tokens(codex_line(s, codex_catalog(s.description)))
        if whole > sent.get(s.name, 0):
            over[s.name] = whole - sent.get(s.name, 0)
    n = len(skills)
    out = sum(fit.sent.get(s.name) is None for s in skills)
    bad = sum(_codex_kind(fit.sent.get(s.name), len(s.description)) != "full" for s in skills)
    # The rule removes every description only when the names alone do not fit, so then at least
    # one skill is left out: `fit.cap` is a number in the branches below.
    cap = fit.cap or 0
    if out:
        body = words.CODEX_WOULD_LEAVE_OUT.format(
            on=on, out=out, n=n, skills=_many(n, "skill", "skills")
        )
    elif bad and cap == 0:
        body = words.CODEX_WOULD_NAMES.format(on=on)
    elif bad:
        # A cap of a few characters would round to 0.
        cap = cap if cap < 10 else round(cap / 10) * 10
        body = words.CODEX_WOULD_CUT.format(
            on=on,
            bad=bad,
            n=n,
            descriptions=_many(n, "description", "descriptions"),
            cap=f"{cap:,}",
            characters=_many(cap, "character", "characters"),
        )
    else:
        body = words.CODEX_WOULD_KEEP.format(on=on)
    short = words.CODEX_WOULD_SHORT.format(bad=bad, n=n) if bad else words.WOULD_FIT.format(n=n)
    kept = {
        s.name: n
        for s in skills
        if (n := fit.sent.get(s.name)) is not None and _codex_kind(n, len(s.description)) == "cut"
    }
    result = {"short": short, "say": frame.format(body), "sent": sent, "over": over, "kept": kept}
    misfit = {"kind": "out", "n": out} if out else {"kind": "cut", "n": bad} if bad else None
    return result | {"used": fit.used, "size": fit.size, "room": None, "misfit": misfit}


def _codex_full(fit: CodexFit, lengths: dict[str, int]) -> set[str]:
    """The skills a fit sends whole (up to Codex's cap on one description)."""
    return {n for n, kept in fit.sent.items() if _codex_kind(kept, lengths[n]) == "full"}


def _codex_limit_card(
    window: int | None,
    limit: int | None,
    budget: int | None,
    base: tuple[list[CodexSkill], CodexFit] | None,
    checked: bool,
    lengths: dict[str, int],
    rerun,
    keep: bool = False,
) -> dict:
    """Details' "Skill list limit" for Codex (spec limit-line-control, stage 2): the limit now in
    tokens, the smallest limit in steps of 500 above it up to 10,000 at which no description is
    cut and no skill is left out, by the rule that gives the verdict, its cost, and Back to the
    default when config.toml sets the key. `base` and `rerun(budget)` run the rule on today's
    skills, with the preview's changes. The places the limit line can be dragged to are in `steps`,
    as for Claude Code, and so is `keep`."""
    back = {"tokens": "default", "label": words.CODEX_LIMIT_BACK} if limit is not None else None
    card = {"now": None, "offer": None, "back": back, "note": None, "why": None}
    card |= {"param": "tokens", "steps": []}
    default = codex_budget(window, None) if window else None
    skills, now = base if base is not None else ([], None)
    names = {s.name for s in skills}

    def point(value, at: int, fit: CodexFit | None, head: str, here: bool = False) -> tuple:
        short = len(names - _codex_full(fit, lengths)) if fit is not None else None
        return (value, at, short, fit.used if fit is not None else None, head, here)

    def steps(ups: list[tuple[int, CodexFit]]) -> list[dict]:
        if budget is None:
            return []
        points = []
        if back and default is not None:
            fit = rerun(default) if now is not None else None
            head = words.LIMIT_STEP_DEFAULT.format(share=words.TOKENS.format(n=f"{default:,}"))
            points.append(point("default", default, fit, head))
            # The steps of 500 between the default and today's limit; none when config.toml
            # sets less than the default.
            first = (default // CODEX_LIMIT_STEP + 1) * CODEX_LIMIT_STEP
            for n in range(first, budget, CODEX_LIMIT_STEP):
                fit = rerun(n) if now is not None else None
                points.append(point(n, n, fit, words.TOKENS.format(n=f"{n:,}")))
        head = words.LIMIT_STEP_NOW.format(share=words.TOKENS.format(n=f"{budget:,}"))
        points.append(point(limit if limit is not None else budget, budget, now, head, True))
        points += [point(n, n, fit, words.TOKENS.format(n=f"{n:,}")) for n, fit in ups]
        # Left to right, smallest first: config.toml may set less than the default.
        points.sort(key=lambda p: p[1])
        used = now.used if now is not None else None
        return _limit_steps(points, used, len(names), "tokens", words.CODEX_LIMIT_STEP_SHORT)

    if base is None or not checked or budget is None:
        return card | {"why": words.LIMIT_NOT_ESTIMATED, "steps": steps([]) if back else []}
    shown = words.TOKENS.format(n=f"{budget:,}")
    said = words.CODEX_LIMIT_NOW_SET if limit is not None else words.CODEX_LIMIT_NOW_DEFAULT
    card["now"] = said.format(n=f"{budget:,}")
    assert now is not None
    above = range(
        (budget // CODEX_LIMIT_STEP + 1) * CODEX_LIMIT_STEP, CODEX_MAX_LIMIT + 1, CODEX_LIMIT_STEP
    )
    shows = back is not None or keep
    if names <= _codex_full(now, lengths):
        same = [(n, now) for n in above] if keep else []
        return card | {"why": words.LIMIT_NOT_NEEDED, "steps": steps(same) if shows else []}
    ups: list[tuple[int, CodexFit]] = []
    found = None
    for n in above:
        fit = found[1] if found else rerun(n)
        ups.append((n, fit))
        if found is None and names <= _codex_full(fit, lengths):
            found = (n, fit)
    if found is None:
        why = words.CODEX_LIMIT_NOT_ENOUGH.format(n=f"{CODEX_MAX_LIMIT:,}")
        return card | {"why": why, "steps": steps(ups if keep else []) if shows else []}
    offered, fit = found
    shown = words.TOKENS.format(n=f"{offered:,}")
    offer = {"tokens": offered, "label": words.LIMIT_SET.format(share=shown)}
    offer["say"] = words.CODEX_LIMIT_FITS.format(limit=shown)
    offer["cost"] = words.CODEX_LIMIT_COST.format(tokens=_about(fit.used - now.used))
    return card | {"offer": offer, "note": words.CODEX_LIMIT_NOTE, "steps": steps(ups)}


def _asked_tokens(value, window: int | None) -> int | None:
    """The Codex limit a tray row asks for, as the budget it gives: "default" (2% of the window)
    or a whole number of tokens (capped as Codex caps it)."""
    if value == "default":
        return codex_budget(window, None) if window else None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return codex_budget(window or 0, value)
    return None


def _codex(
    inventory, codex_home: Path, folder: str | None, draft: dict, anywhere: bool, asked=None
) -> dict:
    """`asked`: the skill list's limit a tray row asks for (tokens, or "default")."""
    client = "codex"
    found = last_codex_list(codex_home, folder)
    if found is None and anywhere and folder is not None:
        found = last_codex_list(codex_home, None)
    if found is None or isinstance(found, Unreadable):
        return _no_list(client, _skills(inventory, client, folder), found)
    sent_list = found.list
    as_shown, roots = found.shown, found.roots
    if not sent_list.skills:
        return _disk_card(client, [], words.NOTHING_TO_FIT, [])
    date, at_ms = _when(sent_list.at)
    when = _on_date(date)
    items = _skills(inventory, client, sent_list.folder)
    by_path = {os.path.realpath(i.source.path): i for i in items if i.source.path}
    by_name = {i.name: i for i in items}
    rows = []
    for name, text in sent_list.skills:
        path = found.paths.get(name, "")
        item = (by_path.get(os.path.realpath(path)) if path else None) or by_name.get(name)
        whole, newer = _description(path), None
        if whole is None and path and (newer := _newer_copy(path)):
            whole = _description(newer)
        # checked 2026-11-22 (real log, Codex 0.169.0): an update can change a description. The
        # chat's text is then not the start of the new one, and the new size says nothing of it.
        changed = bool(
            newer
            and whole is not None
            and text is not None
            and not codex_catalog(whole).startswith(text)
        )
        rows.append(_Row(name, text, item, whole, path, newer=newer or "", changed=changed))
    rows = _codex_added(rows)
    matched = {r.item.id for r in rows if r.item}
    extras = [i for i in items if i.id not in matched]
    # Codex leaves skills out only once it has removed every description: then the user's
    # skills on disk that are missing from the list were left out. Otherwise they were not there.
    # A file written after the chat says nothing about that chat.
    names_only = all(r.sent == "" for r in rows)
    if names_only:
        for item in [i for i in extras if i.scope is Scope.USER]:
            path = item.source.path or ""
            if not _codex_as_then(path, at_ms) or _codex_hidden(path):
                continue
            rows.append(_Row(item.name, None, item, _description(path), path))
            extras.remove(item)
    # What the next chats list: the chat's skills in today's states, and those new since.
    new, new_shown, not_counted = _codex_new(extras, found, names_only, at_ms)
    as_shown = as_shown | new_shown
    rows_now = _codex_order(rows, new)
    is_off = _codex_off(inventory, codex_home, sent_list.folder)
    states = {r.name: "off" if is_off(r.file) else _state(r.item) for r in rows_now}
    # A skill kept for when it is asked for is on, and not on the list.
    asked_for = {r.name for r in rows if _codex_hidden(r.file)}
    states_now = states | dict.fromkeys(asked_for, "off")
    then = {r.name: "on" for r in rows}  # the chat listed them

    limit = _codex_limit(codex_home)
    window = codex_window(codex_home, sent_list.model)
    budget = codex_budget(window or 0, limit) if window or limit else None
    known = all(r.full is not None for r in rows)

    def run(
        states: dict[str, str], budget: int, listed: list[_Row] = rows_now
    ) -> tuple[list[CodexSkill], CodexFit]:
        skills = [
            CodexSkill(r.name, r.full or "", as_shown.get(r.name) or r.path)
            for r in listed
            if states[r.name] != "off"
        ]
        return skills, codex_rule(skills, budget, roots)

    def rebuilds(budget: int) -> bool:
        return _codex_same(rows, run(then, budget, rows)[1], names_only)

    base = run(states_now, budget) if budget and known else None
    checked = base is not None and budget is not None and rebuilds(budget)
    # config.toml changed after the chat: the limit may differ from the one the chat was sent
    # under. When the default or a limit Kitden offers rebuilds the chat's list, the chat's card
    # shows that limit and the estimates use today's (as for Claude Code).
    moved = not _unchanged([codex_home / "config.toml"], at_ms)
    then_budget = budget
    then_found = False
    if not checked and known and window and moved:
        offers = range(CODEX_LIMIT_STEP, CODEX_MAX_LIMIT + 1, CODEX_LIMIT_STEP)
        for other in dict.fromkeys([codex_budget(window, None), *offers]):
            if other != budget and rebuilds(other):
                then_budget, then_found = other, True
                break
        checked = then_found and base is not None
    if moved and not checked:
        then_budget = None

    fact = _codex_fact(rows, names_only, when, as_shown, codex_table(roots))
    bad = fact.pop("bad")
    unknown = fact.pop("unknown")
    if checked and not bad and then_budget is not None:
        left = f"{then_budget - fact['used']:,}"
        fact["room"] = words.ROOM_LEFT.format(left=left, unit="tokens")
    lede = words.CONTEXT_LIMITS[client]
    if limit is not None and budget is not None:
        title, models = (
            words.LIMIT_TITLE.format(n=f"{budget:,}", unit="tokens"),
            words.CODEX_SETTING,
        )
        lede = words.CONTEXT_LIMIT_SET[client].format(n=f"{budget:,}")
        if limit > budget:
            models = words.CODEX_ABOVE_MOST.format(said=f"{limit:,}", most=f"{budget:,}")
            lede = words.CODEX_MOST.format(n=f"{budget:,}")
    else:
        title = words.WINDOW_TITLE.format(size=_size(window)) if window else words.UNKNOWN_WINDOW
        models = sent_list.model or ""
    if then_found:  # the chat was sent under another limit than today's
        title = words.WINDOW_TITLE.format(size=_size(window or 0))
        models = sent_list.model or ""
    windows = [_window_card(title, models, _tag(date), then_budget, fact)]
    lengths = {r.name: len(r.full or "") for r in rows_now}
    # The limit line counts what the preview's changes leave (as for Claude Code).
    changes = _changes(draft, states, SWITCHES[client])

    def limit_with(states: dict[str, str], keep: bool) -> dict:
        ran = run(states, budget) if budget and known else None
        return _codex_limit_card(
            window, limit, budget, ran, checked, lengths, lambda b: run(states, b)[1], keep
        )

    keep = (_asked_tokens(asked, window) or 0) > (budget or 0)
    if changes and not keep:
        keep = limit_with(states_now, False)["offer"] is not None
    limit_card = limit_with(states_now | changes, keep)
    # What Kitden expects from the setup as it is now, as for Claude Code.
    changed, expect = [], None
    other_skills = bool(new) or any(states_now[r.name] == "off" for r in rows)
    if checked and base is not None and budget and (then_found or other_skills):
        on = words.WITH_LIMIT if limit is not None and not then_found else _on(window)
        expect = _codex_estimate(base[0], base[1], on, words.ESTIMATE)
        if expect["misfit"] is None:
            left = f"{budget - base[1].used:,}"
            expect["room"] = words.ROOM_LEFT.format(left=left, unit="tokens")
    if checked and (expect or not_counted):
        shown = words.TOKENS.format(n=f"{budget:,}")
        if not then_found:
            changed = [words.SKILLS_CHANGED]
        elif other_skills or not_counted:
            changed = [words.LIMIT_AND_SKILLS_CHANGED.format(share=shown)]
        else:
            changed = [words.LIMIT_CHANGED.format(share=shown)]
        changed += [expect["say"]] if expect else []
    uncounted = []
    if checked and not_counted:
        line = _many(len(not_counted), words.CODEX_NOT_COUNTED_ONE, words.CODEX_NOT_COUNTED_MANY)
        uncounted = [line.format(names=_names(not_counted))]
        changed += uncounted
    if base is not None and checked:
        other = None
        if limit is not None and window:
            other = (window, words.DEFAULT_LIMIT)
        elif limit is None:
            other = next(
                ((w, ", ".join(n)) for w, n in codex_windows(codex_home) if w != window), None
            )
        if other:
            size, shown = other
            limit_there = codex_budget(size, None)
            skills = base[0]
            fit = codex_rule(skills, limit_there, roots)
            result = _codex_estimate(skills, fit, _on(size), words.ESTIMATE)
            title = words.WINDOW_TITLE.format(size=_size(size))
            windows.append(_window_card(title, shown, words.ESTIMATE_TAG, limit_there, result))

    after = None
    # A limit in the tray counts only where Kitden could estimate today's.
    new_budget = _asked_tokens(asked, window) if limit_card["now"] is not None else None
    if new_budget == budget:
        new_budget = None
    if base is not None and budget and checked and (changes or new_budget is not None):
        budget_after = new_budget if new_budget is not None else budget
        skills, fit = run(states_now | changes, budget_after)
        was, now = _codex_full(base[1], lengths), _codex_full(fit, lengths)
        gets = [r.name for r in rows_now if r.name not in changes and r.name in now - was]
        loses = [r.name for r in rows_now if r.name not in changes and r.name in was - now]
        on = words.WITH_LIMIT if limit is not None or new_budget is not None else _on(window)
        result = _codex_estimate(skills, fit, on, words.AFTER_APPLY)
        say = f"{result['say']} {_swap(client, gets, loses)}".strip()
        after = {"say": say, "gets": gets, "loses": loses, "result": result}
        after["budget"] = budget_after

    skills = []
    for r in rows:
        logged = None if r.sent is None else len(r.sent)
        side = None if r.then is None else int(_codex_kind(logged, len(r.then)) != "full")
        note = words.NOTE_NO_FILE if r.full is None else None
        if r.item is not None and r.full is not None:
            note = words.NOTE_CODEX_OFF
            if len(r.full) > CODEX_DESCRIPTION_CAP:
                note = f"{words.NOTE_CODEX_LONG} {note}"
        if r.item is not None and from_plugin(r.item):
            note = words.NOTE_PLUGIN
        if r.changed:
            note = words.NOTE_CHANGED
        elif r.moved:  # first, whatever the other note: the size read may not be the chat's
            note = f"{words.NOTE_NEWER} {note}" if note else words.NOTE_NEWER
        if states[r.name] == "off":
            note = words.NOTE_OFF
        elif r.name in asked_for:
            note = words.NOTE_ONLY_ASKED
        size = len(r.full) if r.full is not None else len(r.sent or "")
        text, seen = (
            r.full if r.full is not None else r.sent,
            _seen(r.full, r.sent, side, _codex_cap(r.full)),
        )
        skills.append(
            _skill(
                client,
                r.name,
                r.item,
                size,
                side,
                note,
                description=text,
                seen=seen,
                state=states[r.name],
            )
        )
    for item in extras:
        text = _description(item.source.path)
        note = words.NOTE_NOT_LISTED
        skills.append(
            _skill(client, item.name, item, len(text or ""), None, note, description=text)
        )

    version = f" {sent_list.version}" if sent_list.version else ""
    if checked:
        check = words.HOW_CODEX_SAME.format(n=bad) if bad else words.HOW_CODEX_DOES
    else:
        check = words.HOW_NOT_MATCHED if base is not None else words.HOW_NOT_RUN
    how = [
        words.HOW_CODEX_LIST.format(version=version, when=when),
        words.HOW_CODEX_RULE,
        f"{words.HOW_CODEX_CHECK} {check}",
        *([words.HOW_CODEX_SETTING] if limit is not None else []),
        words.HOW_CODEX_SIZES.format(when=when),
        words.HOW_CODEX_TOKENS,
        *uncounted,
        *([limit_card["why"]] if limit_card["why"] else []),
    ]
    return _card(
        client,
        lede=words.CONTEXT_LEDE + lede,
        lamp="warn" if bad else "none" if unknown else "ok",
        message=None,
        fact={
            "date": date,
            "surface": None,
            "folder": sent_list.folder,
            "version": sent_list.version,
        },
        checked=checked,
        windows=windows,
        skills=skills,
        after=after,
        how=how,
        limit=limit_card,
        changed=changed,
        now=expect | {"budget": budget} if expect else None,
    )


# Cursor


def _cursor(inventory, folder: str | None) -> dict:
    """No limit and no log to read (checked 2026-11-06): the skills, split by Only when asked."""
    client = "cursor"
    items = _skills(inventory, client, folder)
    skills = []
    for item in items:
        asked = item.skill_state == "only-asked"
        text = _description(item.source.path)
        note = words.NOTE_ONLY_ASKED if asked else None
        skills.append(
            _skill(client, item.name, item, len(text or ""), int(asked), note, description=text)
        )
    message = words.CURSOR_CANNOT_SEE if items else words.NOTHING_TO_FIT
    return _card(client, message=message, skills=skills, how=list(words.HOW_CURSOR))
