"""The short project list: one row per real project, for the answers that list projects.

Clients record every folder they were opened in: links to one folder, git worktrees, folders that
are gone. Here two spellings of one folder are one row, a worktree folds into its main checkout,
and a gone folder is no row. An entry that holds a setting under its own path stays a row, so the
setting can still be reached. The inventory keeps every entry; this only shapes the list.
"""

import os
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

from kitden.changes.actions import KITDEN_GATEWAY
from kitden.local_gateway.project import main_checkout
from kitden.model import Item, ItemKind, Project, Scope
from kitden.views.inventory import Inventory

# What a project can have of its own. Instruction files do not count.
OWN_KINDS = {ItemKind.MCP_SERVER, ItemKind.SKILL, ItemKind.PLUGIN, ItemKind.HOOK}


@dataclass(frozen=True)
class ProjectRow:
    project: Project
    folded: tuple[str, ...]  # the ids of the entries that fold into this row
    own: bool  # it has a server, skill, plugin, hook or gateway rule of its own
    parent: str | None  # parent folder words when another row has the same folder name


def _real(path: str) -> str:
    try:
        return os.path.realpath(path)
    except (OSError, ValueError):
        return path


def _setting_paths(items: list[Item], ruled: Collection[str]) -> set[str]:
    """The entry paths that hold a setting stored under their own path."""
    paths = set(ruled)
    for item in items:
        if item.project and item.scope is Scope.LOCAL and item.via_gateway != KITDEN_GATEWAY:
            paths.add(item.project)
        paths.update(path for path, _, scope, _ in item.project_rules if scope is Scope.LOCAL)
    return paths


def _own_reals(items: list[Item], ruled: Collection[str]) -> set[str]:
    """The real paths of the projects that have something of their own."""
    paths = set(ruled)
    for item in items:
        if item.project and item.kind in OWN_KINDS and item.via_gateway != KITDEN_GATEWAY:
            paths.add(item.project)
        paths.update(path for path, _, _, _ in item.project_rules)
    return {_real(path) for path in paths}


def project_rows(inventory: Inventory, ruled: Collection[str] = ()) -> list[ProjectRow]:
    """One row per real project, sorted by path. `ruled`: the project paths with a gateway rule
    of their own. Reads only links and `.git` files; writes nothing."""
    holders = _setting_paths(inventory.items, ruled)
    # 1. Group the entries by real path; the row is the real spelling, else the first by path.
    groups: dict[str, list[Project]] = {}
    for entry in sorted(inventory.projects, key=lambda p: p.path):
        groups.setdefault(_real(entry.path), []).append(entry)
    heads = {
        real: next((p for p in group if p.path == real), group[0]) for real, group in groups.items()
    }
    # 2. A worktree group folds into its main checkout's group, when that one's row exists.
    into = {}
    for real, head in heads.items():
        # main_checkout never raises: an unreadable `.git` gives the folder itself.
        main = _real(str(main_checkout(Path(real)))) if head.exists else real
        if main != real and main in heads and heads[main].exists:
            into[real] = main
    # A hand-made `.git` can chain worktrees; fold only into a group that does not fold itself.
    into = {real: main for real, main in into.items() if main not in into}
    # 3. A group whose row does not exist is no row. 4. A holder is always a row of its own.
    folded: dict[str, list[str]] = {}
    own_rows: list[Project] = []
    for real, group in groups.items():
        target = into.get(real, real)
        for entry in group:
            if entry is heads[real] and target == real and entry.exists:
                folded.setdefault(real, [])  # the group's row
            elif entry.path in holders:
                own_rows.append(entry)
            elif heads[target].exists:
                folded.setdefault(target, []).append(entry.id)
    owned = _own_reals(inventory.items, ruled)
    rows = [(heads[real], tuple(ids)) for real, ids in folded.items()]
    rows += [(entry, ()) for entry in own_rows]
    rows.sort(key=lambda pair: pair[0].path)
    parents = _parents([entry.path for entry, _ in rows])
    return [
        ProjectRow(entry, ids, _real(entry.path) in owned, parents.get(entry.path))
        for entry, ids in rows
    ]


def _parents(paths: list[str]) -> dict[str, str]:
    """5. For paths with the same folder name: the shortest tail of each one's parent folder
    that no other path with that name has ("a", "c/work")."""
    by_name: dict[str, list[str]] = {}
    for path in paths:
        by_name.setdefault(Path(path).name.casefold(), []).append(path)
    found = {}
    for same in by_name.values():
        if len(same) < 2:
            continue
        for path in same:
            parts = Path(path).parent.parts
            others = [Path(p).parent.parts for p in same if p != path]
            tail = next(
                (
                    parts[-n:]
                    for n in range(1, len(parts) + 1)
                    if all(o[-n:] != parts[-n:] for o in others)
                ),
                parts,
            )
            found[path] = PurePath(*tail).as_posix()
    return found


def row_dict(row: ProjectRow) -> dict[str, Any]:
    return {
        "id": row.project.id,
        "path": row.project.path,
        "exists": row.project.exists,
        "known_by": list(row.project.known_by),
        "folded": list(row.folded),
        "own": row.own,
        "parent": row.parent,
    }


def own_rule_paths(settings: dict) -> frozenset[str]:
    """The projects with a gateway rule of their own, from the gateway's settings."""
    return frozenset(path for path, rules in settings["rules"]["projects"].items() if rules)


def listed_items(inventory: Inventory, rows: list[ProjectRow]) -> list[Item]:
    """The items of the user and of the rows; a folded or gone entry's items stay out."""
    paths = {row.project.path for row in rows}
    return [item for item in inventory.items if item.project is None or item.project in paths]
