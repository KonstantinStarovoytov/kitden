"""Where a change goes and what its Undo cannot bring back: the review's first sentence and its
lede (spec 3.3).

"Other projects are unchanged." is said only when the steps guarantee it: every step is in one
known project's files, or is a Kitden gateway rule for that project, and no other known project
lies inside that folder or around it. A gateway rule passes down to a child project, and a
client working in a parent folder may read a child's files too.
"""

import os
from pathlib import Path

from kitden.changes.actions import PLUGIN_INSTALL
from kitden.clients.base import PLUGIN_DISABLE, PLUGIN_ENABLE, PLUGIN_REMOVE
from kitden.model import Change, Item, Scope, Step
from kitden.views.affects import affects
from kitden.views.words import REMOVE_NOTE


def _real(path: str) -> Path:
    return Path(os.path.realpath(path))


def _known(path: str, projects: list[str]) -> str | None:
    """The known project that is `path`, as the list spells it."""
    real = _real(path)
    return next((p for p in projects if _real(p) == real), None)


def _holder(path: str, projects: list[str]) -> str | None:
    """The deepest known project folder that holds `path`."""
    real = _real(path)
    inside = [p for p in projects if real.is_relative_to(_real(p))]
    return max(inside, key=lambda p: len(_real(p).parts)) if inside else None


def _rule_project(step: Step) -> str | None:
    """The project of a Kitden gateway rule for one project, as rule_step makes its key."""
    key = step.edit.key if step.edit else ()
    return key[2] if len(key) > 2 and key[:2] == ("rules", "projects") else None


def step_project(step: Step, projects: list[str]) -> str | None:
    """The known project a step changes only, or None. Folders are compared by their real path;
    the answer is the project's path as `projects` spells it."""
    rule = _rule_project(step)
    if rule is not None:
        return _known(rule, projects)
    key = step.edit.key if step.edit else ()
    if step.scope is Scope.LOCAL and len(key) > 1 and key[0] == "projects":
        # Claude Code's entry for one project, in ~/.claude.json.
        return _known(key[1], projects)
    if step.scope is Scope.PROJECT:
        place = (
            (step.edit and step.edit.path)
            or (step.copy and step.copy.target)
            or (step.removal and step.removal.path)
        )
        return _holder(place, projects) if place else None
    return None


def _alone(project: str, projects: list[str]) -> bool:
    """No other known project lies inside the folder or around it."""
    here = _real(project)
    others = [_real(p) for p in projects if _real(p) != here]
    return not any(o.is_relative_to(here) or here.is_relative_to(o) for o in others)


def change_target(change: Change, projects: list[str]) -> dict:
    """Where the steps go: "project" (one known project, `project`), "all" (no step is in a
    project), or "mixed". `others_unchanged`: the review may say "Other projects are
    unchanged.\""""
    places = {step_project(s, projects) for s in change.steps}
    if len(places) == 1 and None not in places:
        [project] = places
        alone = _alone(project, projects)
        return {"scope": "project", "project": project, "others_unchanged": alone}
    scoped = any(
        s.scope in (Scope.PROJECT, Scope.LOCAL) or _rule_project(s) is not None
        for s in change.steps
    )
    return {"scope": "mixed" if scoped else "all", "project": None, "others_unchanged": False}


def undo_note(change: Change) -> str | None:
    """What Undo cannot bring back, when Kitden knows: a removed Claude Code plugin's saved
    options. None for every other change."""
    if change.action == PLUGIN_REMOVE and any(s.client == "claude_code" for s in change.steps):
        return REMOVE_NOTE
    return None


def mark_reach(change: Change, inventory, item: Item | None, cursor_imports: bool) -> None:
    """Mark each plugin step with every client it changes, so the review's title names the
    clients Details' Affects names (views/affects.py): a Claude Code user plugin reaches Cursor
    too while Cursor loads Claude Code's plugins. `item` is the plugin a switch or a removal
    changes; an install into Claude Code for all projects reaches Cursor when it imports."""
    if change.action in (PLUGIN_REMOVE, PLUGIN_ENABLE, PLUGIN_DISABLE) and item is not None:
        clients = affects(inventory, item)["clients"]
        for step in change.steps:
            step.reaches = clients
    elif change.action == PLUGIN_INSTALL and cursor_imports:
        for step in change.steps:
            plugin = step.edit is not None and step.edit.key[:1] == ("enabledPlugins",)
            if plugin and step.client == "claude_code" and step.scope is Scope.USER:
                step.reaches = ["claude_code", "cursor"]
