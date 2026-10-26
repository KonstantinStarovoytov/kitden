"""The preview tray as one change (mockup Phase 3): many requests, one step list, all-or-nothing.

Each tray row is one request the page would preview on its own. Their steps are joined in tray
order into one change, so Apply all and Undo all go through the engine once. A write that two
rows make the same way (the `kitden` entry two moves both add) is kept once and listed in both.
"""

import os
from dataclasses import dataclass

from kitden.changes.json_splice import ABSENT
from kitden.local_gateway.settings import CLIENT as KITDEN
from kitden.model import Change, Scope, Step
from kitden.views.words import NO_SKILL_MERGE

BATCH = "batch"  # the action of a change made of two or more tray rows
NEEDS = "Each change needs an id, a kind and a title."
SAME_ID = "Two changes in the preview have the same id."
# Why a change cannot join the tray. `other` is the title of the one already there.
AFTER = "Apply the preview first, or take that one out."
SAME = "“{other}” in the preview changes the same {what}. " + AFTER
LEAVES = "“{other}” in the preview removes {server} from the gateway. " + AFTER
REMOVES = (
    "This removes {server} from the gateway, but “{other}” in the preview changes it. " + AFTER
)
TWO_GATEWAYS = "“{other}” in the preview moves servers into another gateway. " + AFTER


@dataclass
class Part:
    """One tray row's steps, as its own builder made them."""

    id: str
    title: str
    steps: list[Step]
    # Kitden gateway servers the row needs held, besides the ones its steps write: a move into
    # the gateway of a server it holds already writes no server step.
    needs: frozenset[str] = frozenset()


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def requests_in(body: dict) -> list[dict]:
    """The tray's requests from a page body: each {id, kind, title, detail, targets, params,
    picked}. `picked` is the project the row was asked in, or None."""
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
        picked = request.get("picked")
        requests.append(
            {
                "id": request["id"],
                "kind": request["kind"],
                "title": request["title"],
                "detail": detail if isinstance(detail, str) else "",
                "targets": targets if isinstance(targets, list) else [],
                "params": params if isinstance(params, dict) else {},
                "picked": picked if _text(picked) else None,
            }
        )
    if len({r["id"] for r in requests}) != len(requests):
        raise ValueError(SAME_ID)
    return requests


def _real(path: str) -> str:
    return os.path.realpath(path)


def same_write(a: Step, b: Step) -> bool:
    """Both steps write the same value into the same entry the same way. A step with a Keychain
    item is never the same: its value goes to the Keychain."""
    if a.edit is None or b.edit is None or a.keychain or b.keychain:
        return False
    return (
        _real(a.edit.path) == _real(b.edit.path)
        and (a.edit.fmt, tuple(a.edit.key), a.edit.after)
        == (b.edit.fmt, tuple(b.edit.key), b.edit.after)
        and (a.mechanism, a.command) == (b.mechanism, b.command)
    )


def _server(step: Step) -> str | None:
    """The Kitden gateway server a settings step is about: its entry, its rules or its mode."""
    key = tuple(step.edit.key) if step.client == KITDEN and step.edit is not None else ()
    if len(key) > 1 and key[0] == "servers":
        return key[1]
    if len(key) > 2 and key[:2] == ("rules", "global"):
        return key[2]
    if len(key) > 3 and key[:2] == ("rules", "projects"):
        return key[3]
    return None


def _removed(step: Step) -> str | None:
    """The Kitden gateway server whose entry the step removes."""
    key = tuple(step.edit.key) if step.edit is not None else ()
    if len(key) == 2 and key[0] == "servers" and step.edit.after is ABSENT:
        return _server(step)
    return None


def _skill_rules(step: Step) -> str | None:
    """Which Claude Code settings file a step gives `skillOverrides`: "user", "project" (a
    project's local file) or None."""
    edit = step.edit
    adds = edit is not None and edit.key[:1] == ("skillOverrides",) and edit.after is not ABSENT
    if step.client != "claude_code" or not adds:
        return None
    return "user" if step.scope is Scope.USER else "project" if step.scope is Scope.LOCAL else None


def _folder(step: Step) -> str | None:
    """The folder a step copies into or removes."""
    place = step.copy.target if step.copy else step.removal.path if step.removal else None
    return _real(place) if place else None


def _between(old: Part, new: Part) -> str | None:
    """Why `new` cannot join a change that has `old`, or None."""
    other = old.title
    pairs = [(a, b) for a in old.steps for b in new.steps if not same_write(a, b)]
    # The engine moves servers into one registered gateway per change, each name once.
    for a, b in pairs:
        if a.gateway is not None and b.gateway is not None:
            if a.gateway.gateway_id != b.gateway.gateway_id:
                return TWO_GATEWAYS.format(other=other)
            if a.gateway.name == b.gateway.name:
                return SAME.format(other=other, what="server")
    # A server that leaves the Kitden gateway takes its rules with it, also ones not set yet.
    for a, b in pairs:
        if (server := _removed(b)) and _server(a) == server:
            return REMOVES.format(other=other, server=server)
        if (server := _removed(a)) and _server(b) == server:
            return LEAVES.format(other=other, server=server)
    if leaving := sorted(new.needs & {_removed(a) for a in old.steps}):
        return LEAVES.format(other=other, server=leaving[0])
    if leaving := sorted(old.needs & {_removed(b) for b in new.steps}):
        return REMOVES.format(other=other, server=leaving[0])
    for a, b in pairs:
        if a.edit is None or b.edit is None or _real(a.edit.path) != _real(b.edit.path):
            continue
        key, own = tuple(a.edit.key), tuple(b.edit.key)
        if key[: len(own)] == own or own[: len(key)] == key:
            return SAME.format(other=other, what="setting")
    for a, b in pairs:
        if _folder(a) and _folder(a) == _folder(b):
            return SAME.format(other=other, what="folder")
    # A one-project skill rule waits while the user file has `skillOverrides` (actions.py); a
    # tray that would write both is refused too, as the docs do not say how they merge.
    had, adds = {_skill_rules(a) for a in old.steps}, {_skill_rules(b) for b in new.steps}
    if ("user" in had and "project" in adds) or ("project" in had and "user" in adds):
        return NO_SKILL_MERGE
    return None


def clash(earlier: list[Part], new: Part) -> str | None:
    """Why `new` cannot join the parts already in the tray, in plain words; None when it can.
    One change cannot write the same entry twice, an entry inside another, or into two
    registered gateways, and a server it removes from the Kitden gateway gets no other change."""
    return next((reason for old in earlier if (reason := _between(old, new))), None)


def first_clash(parts: list[Part]) -> tuple[str, str] | None:
    """The first part that cannot join the ones before it: (why, its id); None when all can."""
    for i, part in enumerate(parts):
        if reason := clash(parts[:i], part):
            return reason, part.id
    return None


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


def step_rows(rows: list[dict]) -> dict[int, str]:
    """Each step's row by index: the first row in tray order that lists it."""
    found: dict[int, str] = {}
    for row in rows:
        for index in row["steps"]:
            found.setdefault(index, row["id"])
    return found


def part_of(change: Change, row: dict) -> Change:
    """One row of a combined change as a change of the row's kind, sharing the steps: the
    review's words for that row read it."""
    return Change(action=row["kind"], steps=[change.steps[i] for i in row["steps"]])
