"""The Context screen: for each client, what its last chat sent and whether the skill list fit,
with every sentence written (spec 2026-11-09 "Do your skills fit?").

A number is either read from the last chat log (the fact), or an estimate. Estimates show only
while the client's rule, run on the last chat's skills and window, rebuilds that list exactly
(`checked`, spec "The check that guards every estimate").
"""

import glob
import os
import re
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import TypeGuard

from kitden.clients.base import Reader, found_columns, from_plugin
from kitden.clients.claude_code import local_files
from kitden.clients.versions import highest_version
from kitden.context.claude_log import Unreadable, last_claude_list
from kitden.context.codex_log import codex_window, codex_windows, last_codex_list
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
)
from kitden.context.tables import (
    CLAUDE_ALWAYS_FULL,
    CLAUDE_CANDIDATES,
    CLAUDE_DESCRIPTION_CAP,
    CLAUDE_OTHER_WINDOW,
    CLAUDE_WINDOWS,
    CODEX_DESCRIPTION_CAP,
)
from kitden.local_gateway.settings import as_dict
from kitden.model import CLIENT_WORDS, Item, ItemKind, Project, Scope
from kitden.system import claude_desktop_dir
from kitden.views import words
from kitden.views.effective import effective_view
from kitden.views.match import plugin_of
from kitden.views.skills import read_skill

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
# The states `skill.rule` writes, per client (spec "Switches per client").
SWITCHES = {"claude_code": ["on", "name-only", "off"], "codex": ["on", "off"]}
ASKED = ("user-invocable-only", "only-asked")
# checked 2026-11-07 (Claude Code 2.1.311, two test chats at 8,000 and 12,000): this `env` value
# in Claude Code's settings sets the list's limit in characters. Like other settings, the most
# specific file wins: local, then project, then user (checked 2026-10-26, /en/settings).
BUDGET_KEY = "SLASH_COMMAND_TOOL_CHAR_BUDGET"
WHOLE = re.compile(r"[0-9]+")


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
    added: bool = False  # Claude Code: added during the chat, sent whole outside the limit
    built_in: bool = False  # Claude Code: built in, keeps its description whatever the limit
    moved: bool = False  # Codex: read from its plugin's newer version, the chat's one is gone


def context_view(
    inventory, home: Path, codex_home: Path, folder: str | None, draft: dict[str, dict[str, str]]
) -> dict:
    """One card per found client. `folder` is the picked project (None: all projects); `draft`
    maps client -> skill name -> state, the tray's changes not applied yet."""
    clients = []
    for client in found_columns(inventory):
        changes = as_dict(draft.get(client))
        if client == "claude_code":
            clients.append(_claude(inventory, home, folder, changes))
        elif client == "codex":
            clients.append(_codex(inventory, codex_home, folder, changes))
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
        "how": [],
    }
    return card | parts


def _skills(inventory, client: str, folder: str | None) -> list[Item]:
    """The skills the client loads there, one per name."""
    found: dict[str, Item] = {}
    for item in effective_view(inventory, client, folder).items:
        if item.kind is ItemKind.SKILL:
            found.setdefault(_name(client, item), item)
    return list(found.values())


def _name(client: str, item: Item) -> str:
    """The skill's name as Claude Code's list writes it: a plugin's skill has its prefix."""
    plugin = plugin_of(item) if client == "claude_code" else None
    return f"{plugin.split('@')[0]}:{item.name}" if plugin else item.name


def _state(item: Item | None) -> str:
    return (item.skill_state if item else None) or "on"


def _description(path: str | None) -> str | None:
    """The description in a SKILL.md, or None when there is no such file."""
    if not path or not Path(path).is_file():
        return None
    return read_skill(Path(path).parent)["description"]


def _app_description(home: Path, name: str) -> str | None:
    """The description of a skill the Claude app gives Claude Code (`anthropic-skills:docx`), from
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
        *(home / ".claude/skills/synced").glob(f"*/{skill}/SKILL.md"),
    ):
        try:
            found.append((path.stat().st_mtime, path))
        except OSError:  # gone since the folder was listed
            continue
    return _description(str(max(found)[1])) if found else None


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
) -> dict:
    # Claude Code's skillOverrides does not touch a plugin's skills (spec "Switches per client").
    plugin = client == "claude_code" and item is not None and from_plugin(item)
    switch = [] if item is None or plugin else SWITCHES.get(client, [])
    # Claude Code takes a rule for a project's own skill only in that project (changes/actions.py).
    project = item.project if client == "claude_code" and item and not plugin else None
    return {
        "name": name,
        "shown": name.split(":")[-1],
        "item": item.id if item else None,
        "project": Project(project, True).id if project else None,
        "source": _source(item, built_in),
        "size": size,
        "side": side,
        "state": _state(item),
        "switch": list(switch),
        "note": note,
    }


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
        size = len(_description(item.source.path) or "")
        skills.append(
            _skill(client, _name(client, item), item, size, int(state == "name-only"), note)
        )
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


def _claude_files(home: Path, folder: str | None) -> list[Path]:
    """Claude Code's settings files for a chat in `folder`, the winning one last."""
    files = [home / ".claude/settings.json"]
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


def _claude_weights(home: Path, at_ms: int) -> dict[str, float]:
    """Each skill's use, aged from the chat's time.

    # checked 2026-11-09 (real ~/.claude.json): skillUsage maps a skill's name, as the log
    # writes it (plugin prefix too), to {usageCount, lastUsedAt (ms)}.
    """
    state = as_dict(Reader("claude_code").json(home / ".claude.json"))
    weights = {}
    for name, entry in as_dict(state.get("skillUsage")).items():
        count, last = as_dict(entry).get("usageCount"), as_dict(entry).get("lastUsedAt")
        if _whole(count) and _whole(last):
            weights[name] = claude_weight(count, last, at_ms)
    return weights


def _claude_run(
    rows, states, weights, budget, unknown: str | None = None, *, as_sent: bool = False
) -> tuple[list[ClaudeSkill], ClaudeFit] | None:
    """The rule on the list's skills in these states; None when a size is not known.
    `unknown` stands in for a description Kitden cannot find. `as_sent`: as in the chat itself,
    where the skills added during it were sent whole, outside the limit."""
    skills = [
        ClaudeSkill(
            r.name,
            r.sent if r.sent is not None else r.full if r.full is not None else unknown,
            r.built_in,
            states[r.name] == "name-only",
            weights.get(r.name, 0.0),
        )
        for r in rows
        if states[r.name] != "off" and not (as_sent and r.added)
    ]
    try:
        fit = claude_rule(skills, budget)
    except ValueError:
        return None
    if as_sent:
        late = {r.name for r in rows if r.added and states[r.name] != "off"}
        fit = replace(fit, full=fit.full | late)
    return skills, fit


def _claude_gives(rows, states, weights, budget, sent_full: frozenset[str]) -> bool:
    """This limit rebuilds the sent list, whatever the size of a description Kitden cannot find.

    The rule gives the same list with every such description empty and with every one at the
    cap, so it gives it for any size between: a skill that fits at the cap fits when smaller,
    and one that does not fit when all are empty never fits."""
    for unknown in ("", "x" * CLAUDE_DESCRIPTION_CAP):
        run = _claude_run(rows, states, weights, budget, unknown, as_sent=True)
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


def _chosen(rows, states, weights, budget, checked: bool, settled: bool) -> tuple[set[str], bool]:
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
        run = _claude_run(rows, states | {name: "on"}, weights, budget, as_sent=True)
        if run is not None and run[1].full != sent_full:
            needed.add(name)
    return needed, False


def _claude_fact(rows: list[_Row], when: str, chosen: set[str], now: bool) -> dict:
    """What the last chat sent: characters per skill sent, and those of descriptions not sent.
    Only the log counts. `chosen` showed only a name by their setting (see `_chosen`): they are
    told apart and are no misfit."""
    sent: dict[str, int] = {}
    over: dict[str, int] = {}
    names = 0
    for r in rows:
        if r.sent is not None:
            sent[r.name] = len(r.name) + 4 + min(len(r.sent), CLAUDE_DESCRIPTION_CAP)
            continue
        names += len(r.name) + 2
        if r.full is not None and r.name not in chosen:
            over[r.name] = min(len(r.full), CLAUDE_DESCRIPTION_CAP) + 2
    used = sum(sent.values()) + names + max(0, len(rows) - 1)
    n, picked = len(rows), len(chosen)
    bad = n - len(sent) - picked
    misfit = None
    if bad:
        short = words.CLAUDE_SHORT_NAMES.format(bad=bad, n=n)
        skills, them = _many(n, "skill", "skills"), _many(bad, "it", "them")
        say = words.CLAUDE_NAMES_ONLY.format(when=when, bad=bad, n=n, skills=skills, them=them)
        misfit = {"kind": "name", "n": bad}
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


def _claude_estimate(skills: list[ClaudeSkill], fit: ClaudeFit, on: str, frame: str) -> dict:
    sent = {}
    over = {}
    for s in skills:
        if s.name in fit.full:
            sent[s.name] = len(s.name) + 4 + min(len(s.description or ""), CLAUDE_DESCRIPTION_CAP)
        elif not s.name_only:
            over[s.name] = min(len(s.description or ""), CLAUDE_DESCRIPTION_CAP) + 2
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
) -> str | None:
    """`explained`: the limit rebuilds the list, so it is why a description is missing.
    `can_free`: some skill with a description has a switch."""
    if row.item is None:
        return words.NOTE_BUILT_IN if row.built_in else None
    if state in ASKED:
        return words.NOTE_ONLY_ASKED
    if side is None:
        return words.NOTE_NOT_LISTED
    if from_plugin(row.item):
        return words.NOTE_PLUGIN
    if state == "name-only":
        return words.NOTE_NAME_ONLY
    if side == 0:
        return words.NOTE_FREES.format(n=f"{min(size, CLAUDE_DESCRIPTION_CAP) + 2:,}")
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


def _claude(inventory, home: Path, folder: str | None, draft: dict) -> dict:
    client = "claude_code"
    found = last_claude_list(home, folder)
    if found is None or isinstance(found, Unreadable):
        return _no_list(client, _skills(inventory, client, folder), found)
    if not found.skills:
        return _disk_card(client, [], words.NOTHING_TO_FIT, [])
    date, at_ms = _when(found.at)
    # The chat's own folder: its project's skills were in its list.
    items = _skills(inventory, client, found.folder)
    by_name = {_name(client, i): i for i in items}
    rows = []
    for name, text in found.skills:
        item = by_name.get(name)
        full = _description(item.source.path) if item else _app_description(home, name)
        rows.append(_Row(name, text, item, full, added=name in found.added))
    states = {r.name: _state(r.item) for r in rows}
    # Checked against each chat: a wrong name here and the rule no longer rebuilds the list.
    rows = [replace(r, built_in=r.item is None and r.name in CLAUDE_ALWAYS_FULL) for r in rows]
    weights = _claude_weights(home, at_ms)

    files = _claude_files(home, found.folder)
    setting = _claude_setting(files)
    model = CLAUDE_WINDOWS.get(found.model or "")
    window = model[0] if model else None
    budget = setting if setting is not None else (claude_budget(*model) if model else None)
    base = _claude_run(rows, states, weights, budget) if budget else None
    sent_full = frozenset(r.name for r in rows if r.sent is not None)
    as_sent = _claude_run(rows, states, weights, budget, as_sent=True) if budget else None
    checked = as_sent is not None and as_sent[1].full == sent_full
    # The log does not say the window: take the only one whose limit rebuilds the list.
    worked_out = two_limits = False
    rate = 0
    if setting is None and not checked:
        fits = [
            candidate
            for candidate in CLAUDE_CANDIDATES
            if _claude_gives(rows, states, weights, claude_budget(*candidate), sent_full)
        ]
        if len({size for size, _ in fits}) == 1:
            worked_out = True
            window, rate = fits[0]
            two_limits = len(fits) > 1
            budget = None if two_limits else claude_budget(*fits[0])
            # None when a size is not known: the window is sure, an estimate is not.
            base = _claude_run(rows, states, weights, budget) if budget else None
            checked = base is not None

    when = _on_date(date)
    settled = bool(date) and _unchanged(files, at_ms)
    chosen, now = _chosen(rows, states, weights, budget, checked, settled)
    fact = _claude_fact(rows, when, chosen, now)
    misfit = fact["misfit"] is not None
    if checked and not misfit:
        left = f"{budget - fact['used']:,}"
        fact["room"] = words.ROOM_LEFT.format(left=left, unit="characters")
    if setting is not None:
        title = words.LIMIT_TITLE.format(n=f"{setting:,}", unit="characters")
        models = words.CLAUDE_SETTING
    else:
        title = words.WINDOW_TITLE.format(size=_size(window)) if window else words.UNKNOWN_WINDOW
        source = words.WORKED_OUT if worked_out else None
        models = " · ".join(p for p in (_model_name(found.model), found.surface, source) if p)
    windows = [_window_card(title, models, _tag(date), budget, fact)]
    if base is not None and checked and setting is None and window in CLAUDE_OTHER_WINDOW:
        other, per_token = CLAUDE_OTHER_WINDOW[window]
        shown = ""  # which models have that window is not in any file Kitden can read
        if worked_out:
            per_token = rate  # the rate this chat's own list gives
        limit = claude_budget(other, per_token)
        skills = base[0]
        result = _claude_estimate(skills, claude_rule(skills, limit), _on(other), words.ESTIMATE)
        title = words.WINDOW_TITLE.format(size=_size(other))
        windows.append(_window_card(title, shown, words.ESTIMATE_TAG, limit, result))

    after = None
    changes = _changes(draft, states, SWITCHES[client])
    if checked and changes:
        run = _claude_run(rows, states | changes, weights, budget)
        if run is not None and base is not None:
            skills, fit = run
            full = base[1].full
            gets = [r.name for r in rows if r.name not in changes and r.name in fit.full - full]
            loses = [r.name for r in rows if r.name not in changes and r.name in full - fit.full]
            on = words.WITH_LIMIT if setting is not None else _on(window)
            result = _claude_estimate(skills, fit, on, words.AFTER_APPLY)
            say = f"{result['say']} {_swap(client, gets, loses)}".strip()
            after = {"say": say, "gets": gets, "loses": loses, "result": result}

    explained = checked or two_limits
    can_free = any(
        r.item is not None
        and r.sent is not None
        and states[r.name] == "on"
        and not from_plugin(r.item)
        for r in rows
    )
    skills = []
    for r in rows:
        side = 0 if r.sent is not None else 1
        size = len(r.full) if r.full is not None else len(r.sent or "")
        note = _claude_note(r, states[r.name], side, size, explained, can_free)
        skills.append(_skill(client, r.name, r.item, size, side, note, r.built_in))
    listed = {r.name for r in rows}
    for item in items:
        if _name(client, item) not in listed:
            extra = _Row(_name(client, item), None, item, _description(item.source.path))
            note = _claude_note(extra, _state(item), None, 0)
            skills.append(_skill(client, extra.name, item, len(extra.full or ""), None, note))

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
        words.HOW_CLAUDE_SETTING if setting is not None else words.HOW_CLAUDE_SHELL,
        words.HOW_CLAUDE_SURFACE,
        words.HOW_CLAUDE_REST,
    ]
    parts = {}
    if setting is not None:
        limit_set = words.CONTEXT_LIMIT_SET[client].format(n=f"{setting:,}")
        parts["lede"] = words.CONTEXT_LEDE + limit_set
    return _card(
        client,
        **parts,
        # Grey: Kitden cannot judge that chat (the limit may have dropped a skill set now).
        lamp="warn" if misfit else "none" if now else "ok",
        message=None if checked else words.TWO_LIMITS if two_limits else words.NO_CHECK,
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
    )


# Codex


def _codex_limit(codex_home: Path) -> int | None:
    """`[skills] max_context_tokens` in config.toml, when it is a whole number.

    # checked 2026-11-06 (Codex docs, skills.max_context_tokens): when set, it is the limit.
    """
    config = as_dict(Reader("codex").toml(codex_home / "config.toml"))
    value = as_dict(config.get("skills")).get("max_context_tokens")
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _codex_kind(sent: int | None, full: int) -> str:
    """Codex sends at most the first 1,024 characters of a description: that much is full."""
    if sent is None:
        return "out"
    return "full" if sent >= min(full, CODEX_DESCRIPTION_CAP) else "cut"


def _codex_cuts(rows: list[_Row]) -> list[int]:
    """The lengths sent of the descriptions that were cut, among those whose full text is
    known."""
    sent = [(len(r.sent), len(r.full)) for r in rows if r.sent is not None and r.full is not None]
    return [kept for kept, full in sent if _codex_kind(kept, full) == "cut"]


def _codex_same(rows: list[_Row], fit: CodexFit, names_only: bool) -> bool:
    """The rule leaves out, cuts and keeps the same skills as the log, at the same length: the
    log's cuts may differ by a few characters (366-370 on 2026-10-30), so the rule's length
    must fall among them."""
    for r in rows:
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
    each skill's path as the list shows it; `table`: tokens of the list's roots table."""
    sent: dict[str, int] = {}
    over: dict[str, int] = {}
    for r in rows:
        skill = CodexSkill(r.name, r.full or "", shown.get(r.name, r.path))
        if r.sent is not None:
            sent[r.name] = codex_tokens(codex_line(skill, r.sent))
        if r.full is not None:
            whole = codex_tokens(codex_line(skill, codex_catalog(r.full)))
            if whole > sent.get(r.name, 0):
                over[r.name] = whole - sent.get(r.name, 0)
    used = table + sum(sent.values())
    n = len(rows)
    out = sum(r.sent is None for r in rows)
    cuts = _codex_cuts(rows)
    # Full or cut only for skills whose full size is known; else only what the log shows.
    unknown = sum(r.sent is not None and r.full is None for r in rows)
    misfit = {"kind": "out", "n": out} if out else {"kind": "cut", "n": len(cuts)} if cuts else None
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
        and r.full is not None
        and _codex_kind(len(r.sent), len(r.full)) == "cut"
    }
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


def _codex(inventory, codex_home: Path, folder: str | None, draft: dict) -> dict:
    client = "codex"
    found = last_codex_list(codex_home, folder)
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
        rows.append(_Row(name, text, item, whole, path, moved=newer is not None))
    matched = {r.item.id for r in rows if r.item}
    extras = [i for i in items if i.id not in matched]
    # Codex leaves skills out only once it has removed every description: then the user's
    # skills on disk that are missing from the list were left out. Otherwise they were not there.
    # A file written after the chat says nothing about that chat.
    names_only = all(r.sent == "" for r in rows)
    if names_only:
        for item in [i for i in extras if i.scope is Scope.USER]:
            if not _unchanged([Path(item.source.path or "")], at_ms):
                continue
            text = _description(item.source.path)
            rows.append(_Row(item.name, None, item, text, item.source.path or ""))
            extras.remove(item)
    states = {r.name: _state(r.item) for r in rows}

    limit = _codex_limit(codex_home)
    window = codex_window(codex_home, sent_list.model)
    budget = codex_budget(window or 0, limit) if window or limit else None
    known = all(r.full is not None for r in rows)

    def run(states: dict[str, str], budget: int) -> tuple[list[CodexSkill], CodexFit]:
        skills = [
            CodexSkill(r.name, r.full or "", as_shown.get(r.name) or r.path)
            for r in rows
            if states[r.name] != "off"
        ]
        return skills, codex_rule(skills, budget, roots)

    base = run(states, budget) if budget and known else None
    checked = base is not None and _codex_same(rows, base[1], names_only)

    fact = _codex_fact(rows, names_only, when, as_shown, codex_table(roots))
    bad = fact.pop("bad")
    unknown = fact.pop("unknown")
    if checked and not bad:
        fact["room"] = words.ROOM_LEFT.format(left=f"{budget - fact['used']:,}", unit="tokens")
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
    windows = [_window_card(title, models, _tag(date), budget, fact)]
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
    changes = _changes(draft, states, SWITCHES[client])
    if base is not None and budget and checked and changes:
        skills, fit = run(states | changes, budget)
        lengths = {r.name: len(r.full or "") for r in rows}

        def full(fit: CodexFit) -> set[str]:
            return {n for n, kept in fit.sent.items() if _codex_kind(kept, lengths[n]) == "full"}

        was, now = full(base[1]), full(fit)
        gets = [r.name for r in rows if r.name not in changes and r.name in now - was]
        loses = [r.name for r in rows if r.name not in changes and r.name in was - now]
        on = words.WITH_LIMIT if limit is not None else _on(window)
        result = _codex_estimate(skills, fit, on, words.AFTER_APPLY)
        say = f"{result['say']} {_swap(client, gets, loses)}".strip()
        after = {"say": say, "gets": gets, "loses": loses, "result": result}

    skills = []
    for r in rows:
        logged = None if r.sent is None else len(r.sent)
        side = None if r.full is None else int(_codex_kind(logged, len(r.full)) != "full")
        note = words.NOTE_NO_FILE if r.full is None else None
        if r.item is not None and r.full is not None:
            note = words.NOTE_CODEX_OFF
            if len(r.full) > CODEX_DESCRIPTION_CAP:
                note = f"{words.NOTE_CODEX_LONG} {note}"
        if r.item is not None and from_plugin(r.item):
            note = words.NOTE_PLUGIN
        if r.moved:  # first, whatever the other note: the size read may not be the chat's
            note = f"{words.NOTE_NEWER} {note}" if note else words.NOTE_NEWER
        size = len(r.full) if r.full is not None else len(r.sent or "")
        skills.append(_skill(client, r.name, r.item, size, side, note))
    for item in extras:
        size = len(_description(item.source.path) or "")
        skills.append(_skill(client, item.name, item, size, None, words.NOTE_NOT_LISTED))

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
    ]
    return _card(
        client,
        lede=words.CONTEXT_LEDE + lede,
        lamp="warn" if bad else "none" if unknown else "ok",
        message=None if checked else words.NO_CHECK,
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
    )


# Cursor


def _cursor(inventory, folder: str | None) -> dict:
    """No limit and no log to read (checked 2026-11-06): the skills, split by Only when asked."""
    client = "cursor"
    items = _skills(inventory, client, folder)
    skills = []
    for item in items:
        asked = item.skill_state == "only-asked"
        size = len(_description(item.source.path) or "")
        note = words.NOTE_ONLY_ASKED if asked else None
        skills.append(_skill(client, item.name, item, size, int(asked), note))
    message = words.CURSOR_CANNOT_SEE if items else words.NOTHING_TO_FIT
    return _card(client, message=message, skills=skills, how=list(words.HOW_CURSOR))
