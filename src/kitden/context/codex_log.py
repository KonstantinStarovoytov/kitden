"""Codex's last skill list, read from the newest chat log, and its window from the model cache."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from kitden.context.claude_log import SentList, Unreadable

CLIENT = "codex"

# `- name: description (file: path)`; a name-only line is `- name: (file: path)`. The name is
# everything up to the first ": " (it may contain spaces), so a plugin skill keeps its prefix
# (`plugin:skill`). The roots lines of the same block (`- `alias` = `/path``) have no `(file:`.
# checked 2026-11-09 (real Codex list, cli 0.163.0-alpha.11)
ENTRY = re.compile(r"^- (?P<name>.+?): (?P<desc>.*?) ?\(file: (?P<path>[^)]*)\)$")
# A roots line names the folder an alias stands for; a skill's `file:` path may start with that
# alias (`r2/<skill>/SKILL.md`). checked 2026-11-09 (real Codex list, cli 0.163.0-alpha.11)
ROOT = re.compile(r"^- `(?P<alias>[^`]+)` = `(?P<folder>[^`]+)`$")


@dataclass(frozen=True)
class CodexSent:
    list: SentList
    paths: dict[str, str]  # name -> the `file:` path of its line, its root alias resolved


def _entries(entry: dict) -> list[tuple[str, str, str]] | None:
    """(name, sent text, path) for each line of the list in a developer message; [] if it has
    no list. None when the list has `- ` lines and Kitden knows none of them: a new shape."""
    payload = entry.get("payload")
    if not isinstance(payload, dict) or payload.get("role") != "developer":
        return []
    content = payload.get("content")
    for part in content if isinstance(content, list) else []:
        text = part.get("text") if isinstance(part, dict) else None
        if isinstance(text, str) and "<skills_instructions>" in text:
            lines = text.splitlines()
            roots = {m["alias"]: m["folder"] for m in map(ROOT.match, lines) if m}
            matches = [m for m in map(ENTRY.match, lines) if m]
            if not matches and any(ln.startswith("- ") and not ROOT.match(ln) for ln in lines):
                return None
            return [(m["name"], m["desc"], _resolve(m["path"], roots)) for m in matches]
    return []


def _resolve(path: str, roots: dict[str, str]) -> str:
    """An absolute path for `alias/rest` when the alias is a root; any other path as it is."""
    alias, slash, rest = path.partition("/")
    if path.startswith("/") or not slash or alias not in roots:
        return path
    return f"{roots[alias].rstrip('/')}/{rest}"


def _read_log(path: Path, folder: str | None) -> CodexSent | Unreadable | None:
    """The last list this log sent, or None when it sent none. A log whose list has a shape
    Kitden does not know is Unreadable, on any version of the client. Only the first
    `session_meta`, `turn_context` lines and lines with a list are parsed.

    # checked 2026-11-09 (real logs, Codex app, cli 0.163.0-alpha.11): session_meta payload
    # fields timestamp, cwd, thread_source (`user` for a person's chat), cli_version;
    # turn_context payload field model; the list is the `<skills_instructions>` text in a
    # response_item message with role `developer`; a line has a top-level timestamp.
    """
    meta: dict | None = None
    model = None
    found: tuple[str, list[tuple[str, str, str]]] | None = None  # list entry's date, its lines
    odd = False  # the last list had a shape Kitden does not know
    with path.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            if meta is None:
                if '"session_meta"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                payload = entry.get("payload") if isinstance(entry, dict) else None
                if not isinstance(payload, dict) or entry.get("type") != "session_meta":
                    continue
                if payload.get("thread_source") != "user":
                    return None
                if folder is not None and payload.get("cwd") != folder:
                    return None
                meta = payload
            elif "<skills_instructions>" in line or '"turn_context"' in line:
                try:
                    entry = json.loads(line)
                except ValueError:  # a line still being written
                    continue
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") == "turn_context":
                    payload = entry.get("payload")
                    value = payload.get("model") if isinstance(payload, dict) else None
                    model = value if isinstance(value, str) else model
                elif entry.get("type") == "response_item":
                    listed = _entries(entry)
                    if listed is None:
                        found, odd = None, True
                    elif listed:
                        found, odd = (str(entry.get("timestamp", "")), listed), False
    if meta is None:
        return None
    version = meta.get("cli_version")
    version = version if isinstance(version, str) else ""
    if found is None:
        return Unreadable(CLIENT, version) if odd else None
    at, listed = found
    sent = SentList(
        CLIENT,
        at,
        version,
        None,
        model,
        meta.get("cwd"),
        tuple((name, desc) for name, desc, _ in listed),
    )
    return CodexSent(sent, {name: file for name, _, file in listed})


def last_codex_list(codex_home: Path, folder: str | None) -> CodexSent | Unreadable | None:
    """The list from the newest log that has one. With a folder, only that folder's logs.
    Compressed `.zst` logs are not opened.

    # checked 2026-11-09 (real Codex list, cli 0.163.0-alpha.11): logs are at
    # sessions/<year>/<month>/<day>/rollout-*.jsonl under the codex home.
    """
    files = []
    for path in (codex_home / "sessions").rglob("rollout-*.jsonl"):
        try:
            files.append((path.stat().st_mtime, path))
        except OSError:  # gone since the folder was listed
            continue
    for _, path in sorted(files, reverse=True):
        try:
            found = _read_log(path, folder)
        except OSError:  # removed or unreadable: this log only
            continue
        if found is not None:
            return found
    return None


def _models(codex_home: Path) -> list[dict]:
    """The model cache's entries that have a whole-number window.

    # checked 2026-11-09 (real file): models_cache.json holds models[] with slug, display_name,
    # context_window. session_meta.context_window holds only an id.
    """
    try:
        data = json.loads((codex_home / "models_cache.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        return []
    return [
        m
        for m in models
        if isinstance(m, dict)
        and isinstance(m.get("context_window"), int)
        and not isinstance(m["context_window"], bool)
    ]


def codex_window(codex_home: Path, model: str | None) -> int | None:
    """The model's window from Codex's model cache."""
    for m in _models(codex_home):
        if model is not None and m.get("slug") == model:
            return m["context_window"]
    return None


def codex_windows(codex_home: Path) -> list[tuple[int, list[str]]]:
    """Each distinct window in the cache, smallest first, with the display names that use it."""
    names: dict[int, list[str]] = {}
    for m in _models(codex_home):
        shown = names.setdefault(m["context_window"], [])
        name = m.get("display_name")
        if isinstance(name, str) and name not in shown:
            shown.append(name)
    return sorted(names.items())
