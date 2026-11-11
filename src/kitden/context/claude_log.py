"""Claude Code's last skill list, read from the newest chat log."""

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

CLIENT = "claude_code"

# checked 2026-11-09 (real logs): `claude-desktop`. `cli` is not confirmed yet; one terminal chat
# will confirm it. An entrypoint not here is still read, without a surface.
INTERACTIVE = {"claude-desktop": "in the Claude app", "cli": "in the terminal"}

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


@dataclass(frozen=True)
class Unreadable:
    client: str
    version: str


def _find_entry(content: str, name: str, at: int) -> int:
    """Where `- <name>` starts on its own line, from `at`; -1 if it is not there."""
    marker = f"- {name}"
    pos = content.find(marker, at)
    while pos != -1:
        starts_line = pos == 0 or content[pos - 1] == "\n"
        if starts_line and content[pos + len(marker) : pos + len(marker) + 1] in ("", ":", "\n"):
            return pos
        pos = content.find(marker, pos + 1)
    return -1


def _split(names: list[str], content: str) -> tuple[tuple[str, str | None], ...]:
    """Entries start at `- <name>` for each name, in order; a `- ` line in a description stays."""
    starts = []
    at = 0
    for name in names:
        start = _find_entry(content, name, at)
        starts.append(start)
        if start != -1:
            at = start + len(name) + 2
    skills = []
    for i, name in enumerate(names):
        if starts[i] == -1:
            skills.append((name, None))
            continue
        stop = next((s for s in starts[i + 1 :] if s != -1), len(content))
        rest = content[starts[i] + len(name) + 2 : stop].removesuffix("\n")
        skills.append((name, rest[1:].removeprefix(" ") if rest.startswith(":") else None))
    return tuple(skills)


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


def _skipped(entry: dict, folder: str | None) -> bool:
    """Not a person's chat (a sidechain, claude -p, the Agent SDK), or not the picked folder."""
    entrypoint = entry.get("entrypoint")
    if entry.get("isSidechain") or (isinstance(entrypoint, str) and entrypoint.startswith("sdk")):
        return True
    return folder is not None and entry.get("cwd") != folder


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
                if _skipped(entry, folder):
                    return None
                entrypoint = entry.get("entrypoint")
                version = entry.get("version")
                version = version if isinstance(version, str) else ""
                at = str(entry.get("timestamp", ""))
                if not _known_shape(attachment):
                    result = Unreadable(CLIENT, version)
                    continue
                if attachment.get("skillCount") != len(attachment["names"]):  # cut short
                    continue
                skills = _split(attachment["names"], attachment["content"])
                if attachment["isInitial"]:
                    result = SentList(
                        CLIENT,
                        at,
                        version,
                        INTERACTIVE.get(entrypoint) if isinstance(entrypoint, str) else None,
                        model,
                        entry.get("cwd"),
                        skills,
                    )
                    answered = False
                elif isinstance(result, SentList):
                    result = replace(result, at=at, skills=_added(result.skills, skills))
            elif '"model"' in line and ASSISTANT.search(line):
                found = MODEL.search(line)  # a regex: no need to parse a large assistant line
                if found and not found[1].startswith("<"):
                    model = found[1]
                    if not answered and isinstance(result, SentList):
                        result = replace(result, model=model)
                        answered = True
    return result


def last_claude_list(home: Path, folder: str | None) -> SentList | Unreadable | None:
    """The list from the newest chat that has one. With a folder, only that folder's chats."""
    files = []
    for path in (home / ".claude/projects").glob("*/*.jsonl"):  # not */*/subagents/*
        try:
            files.append((path.stat().st_mtime, path))
        except OSError:  # gone since the folder was listed
            continue
    for _, path in sorted(files, reverse=True):
        try:
            found = _read_chat(path, folder)
        except OSError:  # removed or unreadable: this chat only
            continue
        if found is not None:
            return found
    return None
