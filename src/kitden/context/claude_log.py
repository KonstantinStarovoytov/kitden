"""Claude Code's last skill list, read from the newest chat log."""

import json
from dataclasses import dataclass, replace
from pathlib import Path

CLIENT = "claude_code"

# checked 2026-11-09 (real logs): `claude-desktop`. `cli` is not confirmed yet; one terminal chat
# will confirm it. An entrypoint not here is still read, without a surface.
INTERACTIVE = {"claude-desktop": "in the Claude app", "cli": "in the terminal"}

# checked 2026-11-09 (real logs, Claude Code 2.1.311): the newest version whose list entry shape
# is known.
KNOWN_VERSIONS = "2.1.311"


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


def _version(text: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in text.split("."))
    except ValueError:
        return None


def _newer_than_known(version: object) -> bool:
    parsed = _version(version) if isinstance(version, str) else None
    return parsed is None or parsed > _version(KNOWN_VERSIONS)


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


def _full(attachment: dict) -> bool:
    names = attachment.get("names")
    return (
        attachment.get("isInitial") is True
        and isinstance(names, list)
        and isinstance(attachment.get("content"), str)
        and attachment.get("skillCount") == len(names)
    )


def _read_chat(path: Path, folder: str | None) -> SentList | Unreadable | None:
    """The last list this chat sent, or None. Only lines with a list or a model are parsed.

    # checked 2026-11-09 (real logs, Claude Code 2.1.309): entry fields timestamp, version,
    # entrypoint, cwd, isSidechain; attachment fields type, isInitial, skillCount, names, content;
    # model is message.model of an assistant entry.
    """
    result: SentList | Unreadable | None = None
    model = None
    with path.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            is_list = '"skill_listing"' in line
            if not is_list and '"model"' not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:  # a line still being written
                continue
            if not isinstance(entry, dict):
                continue
            if not is_list:
                message = entry.get("message")
                name = message.get("model") if isinstance(message, dict) else None
                if (
                    entry.get("type") == "assistant"
                    and isinstance(name, str)
                    and not name.startswith("<")
                ):
                    model = name
                continue
            attachment = entry.get("attachment")
            if not isinstance(attachment, dict) or attachment.get("type") != "skill_listing":
                continue
            entrypoint = entry.get("entrypoint")
            if (
                entry.get("isSidechain")
                or not isinstance(entrypoint, str)
                or entrypoint.startswith("sdk")
            ):
                return None
            if folder is not None and entry.get("cwd") != folder:
                return None
            version = entry.get("version")
            if _full(attachment):
                result = SentList(
                    CLIENT,
                    str(entry.get("timestamp", "")),
                    str(version),
                    INTERACTIVE.get(entrypoint),
                    None,
                    entry.get("cwd"),
                    _split(attachment["names"], attachment["content"]),
                )
            elif _newer_than_known(version):
                result = Unreadable(CLIENT, str(version))
    if isinstance(result, SentList):
        result = replace(result, model=model)
    return result


def last_claude_list(home: Path, folder: str | None) -> SentList | Unreadable | None:
    """The list from the newest chat that has one. With a folder, only that folder's chats."""
    files = sorted(
        (home / ".claude/projects").glob("*/*.jsonl"),  # not */*/subagents/*
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in files:
        found = _read_chat(path, folder)
        if found is not None:
            return found
    return None
