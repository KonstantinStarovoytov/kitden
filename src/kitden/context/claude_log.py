"""Claude Code's last skill list: the newest one sent, from the chat logs."""

import json
import math
import mmap
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Protocol

CLIENT = "claude_code"

# checked 2026-11-09 (real logs): `claude-desktop`. `cli` is not confirmed yet; one terminal chat
# will confirm it. An entrypoint not here is still read, without a surface.
INTERACTIVE = {"claude-desktop": "in the Claude app", "cli": "in the terminal"}

LISTING = b'"skill_listing"'  # in the line of every list
STAMP = re.compile(rb'"timestamp"\s*:\s*"([^"]*)"')
ASSISTANT = re.compile(r'"type"\s*:\s*"assistant"')
MODEL = re.compile(r'"model"\s*:\s*"([^"]*)"')


@dataclass(frozen=True)
class SentList:
    client: str
    at: str
    version: str
    surface: str | None
    model: str | None
    folder: str | None
    skills: tuple[tuple[str, str | None], ...]  # name, sent text (None = name only)
    # name -> as the list shows it, where that is more than the name: `ship-local (ship)`
    shown: dict[str, str] = field(default_factory=dict)
    added: frozenset[str] = frozenset()  # added during the chat: sent whole, outside the limit
    # When the chat's last full list was sent. `at` moves on with every list of added skills,
    # and the app can add skills to a chat nobody is in; a full list comes when a chat starts
    # or is resumed, so it says which chat is the last one.
    full: str = field(default="", compare=False)


@dataclass(frozen=True)
class Unreadable:
    client: str
    version: str
    at: str = field(default="", compare=False)  # when the list Kitden could not read was sent


def _find_entry(content: str, name: str, at: int) -> re.Match[str] | None:
    """The `- <name>` that starts a line and ends it or has `:` after it, from `at`; with none,
    the one with a command in brackets after the name (the plain one goes first: a description
    can hold a line like the other). None if it is not there.

    # checked 2026-11-24 (Claude Code 2.1.330): a skill whose command is another word than its
    # name is shown as `name (command)`; 12 lists in real logs have one, with its description.
    # From the program file: it is shown so without a description too, the word has no spaces and
    # no brackets, and a skill set to Name only shows no command. `names` holds the name alone.
    """
    for command in ("", r" \([^\s()]+\)"):
        entry = rf"^- (?P<shown>{re.escape(name)}{command})(?=:|\n|\Z)"
        found = re.compile(entry, re.MULTILINE).search(content, at)
        if found is not None:
            return found
    return None


def _split(
    names: list[str], content: str
) -> tuple[tuple[tuple[str, str | None], ...], dict[str, str]]:
    """The skills, and the shown names that are more than the name. Entries start at `- <name>`
    for each name, in order; a `- ` line in a description stays."""
    found = []
    at = 0
    for name in names:
        entry = _find_entry(content, name, at)
        found.append(entry)
        if entry is not None:
            at = entry.end()
    skills = []
    shown = {}
    for i, name in enumerate(names):
        entry = found[i]
        if entry is None:
            skills.append((name, None))
            continue
        stop = next((e.start() for e in found[i + 1 :] if e is not None), len(content))
        rest = content[entry.end() : stop].removesuffix("\n")
        skills.append((name, rest[1:].removeprefix(" ") if rest.startswith(":") else None))
        if entry["shown"] != name:
            shown[name] = entry["shown"]
    return tuple(skills), shown


def _added(skills: tuple, added: tuple) -> tuple[tuple[str, str | None], ...]:
    """The list with the added skills: a skill already there takes its new text."""
    new = dict(added)
    kept = tuple((name, new.pop(name)) if name in new else (name, text) for name, text in skills)
    return kept + tuple(new.items())


def _known_shape(attachment: dict) -> bool:
    """The list has the fields Kitden reads, whatever the client's version."""
    names = attachment.get("names")
    return (
        isinstance(attachment.get("isInitial"), bool)
        and isinstance(names, list)
        and all(isinstance(name, str) for name in names)
        and isinstance(attachment.get("content"), str)
    )


def _not_a_person(entry: dict) -> bool:
    """A sidechain, claude -p or the Agent SDK: not a person's chat."""
    entrypoint = entry.get("entrypoint")
    return bool(entry.get("isSidechain")) or (
        isinstance(entrypoint, str) and entrypoint.startswith("sdk")
    )


def _read_chat(path: Path, folder: str | None) -> SentList | Unreadable | None:
    """The last list this chat sent, or None when it sent none. A chat whose list has a shape
    Kitden does not know is Unreadable, on any version of the client. Only lines with a list or a
    model are parsed.

    # checked 2026-11-09 (real logs, Claude Code 2.1.309): entry fields timestamp, version,
    # entrypoint, cwd, isSidechain; attachment fields type, isInitial, skillCount, names, content;
    # model is message.model of an assistant entry.
    # checked 2026-11-10 (real logs, Claude Code 2.1.271-2.1.309): a list with isInitial false
    # holds only the skills added since the last list, each with its description whatever the
    # limit. A chat sends its full list again when it is resumed, not when the model changes, so
    # the list's model is the first one to answer after it.
    """
    result: SentList | Unreadable | None = None
    model = None  # the last model so far
    answered = True  # a model has answered the last full list
    with path.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            if '"skill_listing"' in line:
                try:
                    entry = json.loads(line)
                except ValueError:  # a line still being written
                    continue
                attachment = entry.get("attachment") if isinstance(entry, dict) else None
                if not isinstance(attachment, dict) or attachment.get("type") != "skill_listing":
                    continue
                if _not_a_person(entry):
                    return None
                # checked 2026-11-22 (real logs, Claude app 2.1.325): one chat can send lists
                # from more than one folder when its folder changes. Keep the picked folder's.
                if folder is not None and entry.get("cwd") != folder:
                    continue
                entrypoint = entry.get("entrypoint")
                version = entry.get("version")
                version = version if isinstance(version, str) else ""
                at = str(entry.get("timestamp", ""))
                if not _known_shape(attachment):
                    result = Unreadable(CLIENT, version, at)
                    continue
                if attachment.get("skillCount") != len(attachment["names"]):  # cut short
                    continue
                skills, shown = _split(attachment["names"], attachment["content"])
                if attachment["isInitial"]:
                    result = SentList(
                        CLIENT,
                        at,
                        version,
                        INTERACTIVE.get(entrypoint) if isinstance(entrypoint, str) else None,
                        model,
                        entry.get("cwd"),
                        skills,
                        shown,
                        full=at,
                    )
                    answered = False
                elif isinstance(result, SentList):
                    new = {name for name, _ in skills}
                    kept = {name: text for name, text in result.shown.items() if name not in new}
                    result = replace(
                        result,
                        at=at,
                        skills=_added(result.skills, skills),
                        shown=kept | shown,
                        added=result.added | new,
                    )
            elif '"model"' in line and ASSISTANT.search(line):
                found = MODEL.search(line)  # a regex: no need to parse a large assistant line
                if found and not found[1].startswith("<"):
                    model = found[1]
                    if not answered and isinstance(result, SentList):
                        result = replace(result, model=model)
                        answered = True
    return result


def _time(at: str) -> float:
    """Seconds since 1970 for a log's time; 0 for a time Kitden cannot read."""
    try:
        return datetime.fromisoformat(at).timestamp()
    except ValueError:
        return 0.0


class _Dated(Protocol):
    @property
    def at(self) -> str: ...


def newest[T: _Dated](
    paths: Iterable[Path],
    read: Callable[[Path], T | None],
    latest: Callable[[Path], float | None] | None = None,
    when: Callable[[T], float] | None = None,
) -> T | None:
    """The list sent last among these logs, by the time in the log, not by when the file last
    changed: an app may rewrite an old chat's file with no new list. Files are read newest first;
    one that last changed before the best list so far cannot hold a newer one. `latest` is a
    quick look at a file: the latest time its list can have, or None when it holds no list. A
    file whose list cannot be newer than the best so far is not read. `when` gives the time a
    list is ranked by, when that is not its own time."""
    rank = when or (lambda found: _time(found.at))
    files = []
    for path in paths:
        try:
            files.append((path.stat().st_mtime, path))
        except OSError:  # gone since the folder was listed
            continue
    best: T | None = None
    for changed, path in sorted(files, reverse=True):
        if best is not None and changed < rank(best):
            break
        try:
            if latest is not None:
                top = latest(path)
                if top is None or (best is not None and top <= rank(best)):
                    continue
            found = read(path)
        except OSError:  # removed or unreadable: this log only
            continue
        if found is not None and (best is None or rank(found) > rank(best)):
            best = found
    return best


def _latest_list(path: Path, folder: str | None) -> float | None:
    """The latest time on a line of this log that may hold a list (one sent from the folder, when
    a folder is picked); None when no line may. It is found by a search of the raw file, far
    quicker than reading the log line by line, and it is never earlier than the time of the list
    a full read gives.

    # measured 2026-11-23 on a real home: 525 logs (1.9 GB) had changed after the newest list of
    # a picked project, 402 of them with an older list of that project, so the file's time ruled
    # none of them out and reading them took 4 s on every read of the page; this takes 0.4 s.
    """
    # The folder as a JSON string, with other letters as they are and as \u escapes.
    spellings = {json.dumps(folder, ensure_ascii=plain).encode() for plain in (True, False)}
    latest = None
    with path.open("rb") as file:
        try:
            data = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
        except ValueError:  # an empty file cannot be mapped
            return None
        with data:
            at = data.find(LISTING)
            while at != -1:
                start = data.rfind(b"\n", 0, at) + 1
                end = data.find(b"\n", at)
                end = len(data) if end == -1 else end
                at = data.find(LISTING, end)
                if folder is not None and all(data.find(s, start, end) == -1 for s in spellings):
                    continue
                times = [_time(t.decode(errors="replace")) for t in STAMP.findall(data, start, end)]
                # A line with no time Kitden can read rules nothing out.
                top = max(times) if times and all(times) else math.inf
                latest = top if latest is None else max(latest, top)
    return latest


EARLIER_LOGS = 40  # the newest logs `earlier_descriptions` reads, at most


def _listed(line: bytes) -> tuple[tuple[str, str | None], ...]:
    """The skills of one log line that holds a list, read as `_read_chat` reads them; none when
    the line is no list Kitden can read."""
    try:
        entry = json.loads(line)
    except ValueError:  # a line still being written, or not text
        return ()
    attachment = entry.get("attachment") if isinstance(entry, dict) else None
    if not isinstance(attachment, dict) or attachment.get("type") != "skill_listing":
        return ()
    if not _known_shape(attachment) or attachment.get("skillCount") != len(attachment["names"]):
        return ()
    return _split(attachment["names"], attachment["content"])[0]


def _earlier_in(path: Path, wanted: set[str], found: dict[str, str]) -> None:
    """Adds to `found` the descriptions of the `wanted` skills this log's lists sent, its last list
    first. Only the lines with a list are parsed, found by a search of the raw file."""
    with path.open("rb") as file:
        try:
            data = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
        except ValueError:  # an empty file cannot be mapped
            return
        with data:
            at = data.rfind(LISTING)
            while at != -1 and not found.keys() >= wanted:
                start = data.rfind(b"\n", 0, at) + 1
                end = data.find(b"\n", at)
                end = len(data) if end == -1 else end
                at = data.rfind(LISTING, 0, start)
                for name, text in _listed(data[start:end]):
                    if name in wanted and name not in found and text is not None:
                        found[name] = text


def earlier_descriptions(home: Path, names: Iterable[str]) -> dict[str, str]:
    """For each of these skills, the description the newest list in the chat logs sent with it;
    only the skills found. For a skill built into Claude Code, which has no file: a list that
    shows its name only says nothing of its size, and a built-in skill is the same in every
    folder, so the lists of every folder count. The newest logs are read first, at most
    `EARLIER_LOGS` of them, and reading stops once every skill is found.

    # checked 2026-11-24 (real logs, 549 lists): `init` came with a description of 59 characters
    # in 446 of them and `security-review` with 71 characters in 432; in a list sent at its limit
    # both came by name only.
    """
    wanted = set(names)
    found: dict[str, str] = {}
    if not wanted:
        return found
    files = []
    for path in (home / ".claude/projects").glob("*/*.jsonl"):  # not */*/subagents/*
        try:
            files.append((path.stat().st_mtime, path))
        except OSError:  # gone since the folder was listed
            continue
    for _, path in sorted(files, reverse=True)[:EARLIER_LOGS]:
        try:
            _earlier_in(path, wanted, found)
        except OSError:  # removed or unreadable: this log only
            continue
        if found.keys() >= wanted:
            break
    return found


def last_claude_list(home: Path, folder: str | None) -> SentList | Unreadable | None:
    """The newest list sent in a chat. With a folder, only that folder's chats."""
    chats = (home / ".claude/projects").glob("*/*.jsonl")  # not */*/subagents/*
    return newest(
        chats,
        lambda path: _read_chat(path, folder),
        lambda path: _latest_list(path, folder),
        _ranked,
    )


def _ranked(found: SentList | Unreadable) -> float:
    """The time a chat is ranked by: its last full list, not a later list of added skills.

    # checked 2026-11-23 (real logs, Claude app): the app added 21 new skills to two chats of
    # Nov 13 and 14 that nobody was in. Ranked by that list, they were "your last chat", with 3
    # skills by name only, while every chat started that week had 22.
    """
    return _time(found.full if isinstance(found, SentList) and found.full else found.at)
