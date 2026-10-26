"""Where a change goes and what its Undo cannot bring back: the review's first sentence and its
lede (spec 3.3).

"Other projects are unchanged." is said only when the steps guarantee it: every step is in one
known project's files, or is a Kitden gateway rule for that project, no other known project
lies inside that folder or around it, and no step runs a client's plugin command. A gateway
rule passes down to a child project, and a client working in a parent folder may read a
child's files too. A plugin command (`claude plugin install`, `codex plugin remove`) also works
on the client's plugin cache, which every project shares, while Kitden checks only the settings
file; an MCP command (`claude mcp remove -s local`) is judged by the file it edits. For the same
reason a plugin command is never for "all projects but the picked one".
"""

import os
from pathlib import Path

from kitden.changes.actions import PLUGIN_INSTALL
from kitden.changes.engine import step_readers
from kitden.clients.base import PLUGIN_DISABLE, PLUGIN_ENABLE, PLUGIN_REMOVE
from kitden.model import Change, Item, Scope, Step
from kitden.views.affects import affects
from kitden.views.effective import effective_view
from kitden.views.words import KEYCHAIN_UNDO, KEYCHAIN_UNDO_MANY, REMOVE_NOTE


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
    # A project's own file, also its local settings (`.claude/settings.local.json`).
    if step.scope in (Scope.PROJECT, Scope.LOCAL):
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


def _touched(step: Step) -> list[str]:
    """The clients a step changes: the readers of a copied or removed folder, every client a
    plugin step reaches, else (also with no reader listed) its own client."""
    return step_readers(step) or [step.client]


def _plugin_command(step: Step) -> bool:
    """`claude plugin …` or `codex plugin …`: it works on the plugin cache too."""
    return bool(step.command) and len(step.command) > 1 and step.command[1] == "plugin"


def _wins_in(change: Change, inventory, picked: str, items: list[Item] | None) -> bool:
    """For every client the steps change, the picked project's own definition overrides one of
    `items`, the definitions the change changes, by that step's name (a merge does not count:
    Codex merges a project's fields over the user entry, so the change still reaches the merge
    there). Another kind with the same name is another definition."""
    ids = {item.id for item in items or []}
    views: dict = {}
    for step in change.steps:
        for client in _touched(step):
            if client not in views:
                views[client] = effective_view(inventory, client, picked)
            beaten = any(
                loser.id in ids
                and loser.name == step.name
                and winner.project == picked
                and mode == "override"
                for winner, loser, mode in views[client].shadowed
            )
            if not beaten:
                return False
    return bool(change.steps)


def change_target(
    change: Change,
    projects: list[str],
    inventory=None,
    picked: str | None = None,
    items: list[Item] | None = None,
) -> dict:
    """Where the steps go: "project" (one known project, `project`), "all" (no step is in a
    project), "others" (all projects but the picked one, `project`, whose own definition wins
    over `items`, the definitions the change changes, for every client the steps change; never
    for a plugin command), or "mixed". `others_unchanged`: the review may say "Other projects
    are unchanged.\""""
    places = {step_project(s, projects) for s in change.steps}
    plugin = any(_plugin_command(s) for s in change.steps)
    if len(places) == 1 and None not in places:
        [project] = places
        alone = _alone(project, projects) and not plugin
        return {"scope": "project", "project": project, "others_unchanged": alone}
    scoped = any(
        s.scope in (Scope.PROJECT, Scope.LOCAL) or _rule_project(s) is not None
        for s in change.steps
    )
    if scoped:
        return {"scope": "mixed", "project": None, "others_unchanged": False}
    beaten = picked and inventory is not None and _wins_in(change, inventory, picked, items)
    if beaten and not plugin:
        return {"scope": "others", "project": picked, "others_unchanged": False}
    return {"scope": "all", "project": None, "others_unchanged": False}


def _join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


def undo_note(change: Change) -> str | None:
    """What Undo cannot bring back, when Kitden knows: a removed Claude Code plugin's saved
    options, and the old value of a Keychain item the change replaced. None when nothing."""
    notes = []
    if change.action == PLUGIN_REMOVE and any(s.client == "claude_code" for s in change.steps):
        notes.append(REMOVE_NOTE)
    kept = [f"{i.server}/{i.key}" for s in change.steps for i in s.keychain if i.existed]
    if kept:
        notes.append((KEYCHAIN_UNDO if len(kept) == 1 else KEYCHAIN_UNDO_MANY).format(_join(kept)))
    return " ".join(notes) or None


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
