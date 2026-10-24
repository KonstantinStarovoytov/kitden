"""The preview tray as one change (mockup Phase 3): many requests, one step list, all-or-nothing.

Each tray row is one request the page would preview on its own. Their steps are joined in tray
order into one change, so Apply all and Undo all go through the engine once. A write that two
rows make the same way (the `kitden` entry two moves both add) is kept once and listed in both.
"""

import os
from dataclasses import dataclass

from kitden.model import Change, Step

BATCH = "batch"  # the action of a change made of two or more tray rows
NEEDS = "Each change needs an id, a kind and a title."
SAME_ID = "Two changes in the preview have the same id."


@dataclass
class Part:
    """One tray row's steps, as its own builder made them."""

    id: str
    title: str
    steps: list[Step]


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def requests_in(body: dict) -> list[dict]:
    """The tray's requests from a page body: each {id, kind, title, detail, targets, params}."""
    raw = body.get("requests")
    if not isinstance(raw, list) or not raw:
        raise ValueError(NEEDS)
    requests = []
    for request in raw:
        if not isinstance(request, dict):
            raise ValueError(NEEDS)
        if not all(_text(request.get(k)) for k in ("id", "kind", "title")):
            raise ValueError(NEEDS)
        detail, targets, params = (request.get(k) for k in ("detail", "targets", "params"))
        requests.append(
            {
                "id": request["id"],
                "kind": request["kind"],
                "title": request["title"],
                "detail": detail if isinstance(detail, str) else "",
                "targets": targets if isinstance(targets, list) else [],
                "params": params if isinstance(params, dict) else {},
            }
        )
    if len({r["id"] for r in requests}) != len(requests):
        raise ValueError(SAME_ID)
    return requests


def same_write(a: Step, b: Step) -> bool:
    """Both steps write the same value into the same entry the same way. A step with a Keychain
    item is never the same: its value goes to the Keychain."""
    if a.edit is None or b.edit is None or a.keychain or b.keychain:
        return False
    return (
        os.path.realpath(a.edit.path) == os.path.realpath(b.edit.path)
        and (a.edit.fmt, tuple(a.edit.key), a.edit.after)
        == (b.edit.fmt, tuple(b.edit.key), b.edit.after)
        and (a.mechanism, a.command) == (b.mechanism, b.command)
    )


def combine(parts: list[Part]) -> tuple[list[Step], list[list[int]]]:
    """One step list in tray order, with a write already there kept once, and each part's
    indices into it."""
    steps: list[Step] = []
    maps = []
    for part in parts:
        indices = []
        for step in part.steps:
            same = next((i for i, s in enumerate(steps) if same_write(s, step)), None)
            if same is None:
                steps.append(step)
                same = len(steps) - 1
            indices.append(same)
        maps.append(indices)
    return steps, maps


def part_of(change: Change, row: dict) -> Change:
    """One row of a combined change as a change of the row's kind, sharing the steps: the
    review's words for that row read it."""
    return Change(action=row["kind"], steps=[change.steps[i] for i in row["steps"]])
