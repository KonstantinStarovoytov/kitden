"""Which clients still need a restart after an Apply.

The change log says what each applied change asked for (a step's `restart_note`). A client still
needs it while a process of that client, started before the Apply, runs. If none runs, there is
nothing to restart. The page shows one strip for each client.
"""

import os
from datetime import datetime

# What a client's process is called. A name with a "/" is looked for in the whole command line.
CLIENT_PROCESSES = {
    "claude_code": ("claude", "Claude", "@anthropic-ai/claude-code"),
    "codex": ("codex", "Codex"),
    "cursor": ("Cursor", "cursor"),
}
# A change that is in effect. An undone one no longer asks for anything.
IN_EFFECT = ("verified", "undo_blocked")


def _time(text: object) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(text))
    except ValueError:
        return None
    return when if when.tzinfo else None


def _belongs(client: str, args: str) -> bool:
    names = CLIENT_PROCESSES[client]
    first = [os.path.basename(word) for word in args.split(None, 2)[:2]]
    return any(name in first or ("/" in name and name in args) for name in names)


def _changes(log: list[dict]) -> list[dict]:
    """One record for each change, newest first. Its state is the latest line's; its time and
    steps are the first line's (the Apply)."""
    lines: dict[str, list[dict]] = {}
    for entry in log:
        if entry.get("id"):
            lines.setdefault(entry["id"], []).append(entry)
    return [
        {
            "id": change,
            "state": own[0].get("state"),
            "time": _time(own[-1].get("time")),
            "steps": own[-1].get("steps") or [],
        }
        for change, own in lines.items()
    ]


def pending_restarts(log: list[dict], starts: list[tuple[datetime, str]]) -> list[dict]:
    """One strip for each client that needs one: the note of its newest change in effect, while
    a process of the client that started before that change still runs. The newest decides:
    a process older than an earlier change is older than the newest one too.
    `log` is the change log, newest line first; `starts` is `system.process_starts()`."""
    changes = [c for c in _changes(log) if c["state"] in IN_EFFECT]
    found = []
    for client in CLIENT_PROCESSES:
        running = [started for started, args in starts if _belongs(client, args)]
        for change in changes:
            note = next(
                (
                    s["restart_note"]
                    for s in change["steps"]
                    if s.get("client") == client and s.get("restart_note")
                ),
                None,
            )
            if not note:
                continue
            if change["time"] and any(started < change["time"] for started in running):
                found.append({"client": client, "note": note, "change": change["id"]})
            break
    return found
