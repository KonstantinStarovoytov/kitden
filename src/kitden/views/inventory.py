"""One inventory from all client adapters (FR-001 to FR-005)."""

import contextlib
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from kitden.apps import app_roots, app_url
from kitden.clients.base import ClientAdapter, Scan
from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.clients.codex import CodexAdapter
from kitden.clients.cursor import CursorAdapter
from kitden.model import (
    Client,
    ClientStatus,
    Item,
    Project,
    ReadStatus,
    Source,
    SourceKind,
    UnknownReason,
)
from kitden.views.skills import plugin_skill_folders


@dataclass
class Inventory:
    clients: list[Client] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    problems: list[Source] = field(default_factory=list)
    partial: bool = False  # a quick scan left out a slow answer; a new scan follows when it is in
    # (plugin id, skill folder) of each skill in a marketplace's plugins or in Cursor's plugin
    # folders: a skill copied from one is still that plugin's (match.py).
    plugin_skills: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class LastGood:
    """The last good read of each source, in memory while the page runs. `sources`: source key
    (a file's path, or `client:<id>` for a whole client) -> (time read, items). `projects`: the
    project list of the last read that kept nothing."""

    sources: dict[str, tuple[str, list[Item]]] = field(default_factory=dict)
    projects: list[Project] = field(default_factory=list)


def keep_last_good(inventory: Inventory, last: LastGood, now: str) -> Inventory:
    """Add the last good items of each source that failed now, marked with when they were read
    and with no action (a Remove would be refused), and remember this read's good sources.

    A whole client that failed keeps its items like a file does. While a source is kept, the
    projects of the last good read stay too, so a broken ~/.claude.json does not drop them. A
    first read that fails keeps nothing; a file emptied on purpose keeps nothing either.
    """
    failed = {p.path or f"client:{p.owner_client}" for p in inventory.problems}
    gone = {k.removeprefix("client:") for k in failed if k.startswith("client:")}
    have = {i.id for i in inventory.items}
    kept: dict[str, Item] = {}  # by id: a file a failed client also read gives each item once
    for key in sorted(failed & last.sources.keys()):
        at, items = last.sources[key]
        for i in items:
            if i.id not in have:
                kept.setdefault(i.id, replace(i, stale_at=at, actions=()))
    fresh: dict[str, list[Item]] = {}
    for item in inventory.items:
        fresh.setdefault(item.source.path or "", []).append(item)
        fresh.setdefault(f"client:{item.client}", []).append(item)
    new = {k: (now, v) for k, v in fresh.items() if k and k not in failed}
    for key, (at, items) in last.sources.items():  # a failed source, or a file of a failed client
        if key in failed or (items and items[0].client in gone):
            new.setdefault(key, (at, items))
    last.sources = new
    inventory.items += kept.values()
    if kept:
        known = {p.path for p in inventory.projects}
        inventory.projects = sorted(
            [*inventory.projects, *(p for p in last.projects if p.path not in known)],
            key=lambda p: p.path,
        )
    else:  # nothing kept: this read's projects are the best known, even with a file broken
        last.projects = list(inventory.projects)
    return inventory


def default_adapters(
    home: Path, quick: bool = False, on_slow_answer: Callable[[], None] | None = None
) -> list[ClientAdapter]:
    """The three clients; `quick` does not wait for slow answers (see CodexAdapter)."""
    codex = CodexAdapter(home, quick=quick, on_slow_answer=on_slow_answer)
    return [ClaudeCodeAdapter(home), codex, CursorAdapter(home)]


def _read(adapter: ClientAdapter, apps: list[Path]) -> tuple[Client, Scan | None]:
    """One client's detection and scan; no scan when it is not found or could not be read."""
    client = replace(adapter.detect(), app_url=app_url(adapter.id, apps))
    if client.status is ClientStatus.NOT_FOUND:
        return client, None
    try:
        return client, adapter.scan()
    except Exception:  # a changed file format must not hide the other clients
        return replace(client, status=ClientStatus.UNREADABLE), None


def build_inventory(
    home: Path | None = None,
    adapters: Iterable[ClientAdapter] | None = None,
    apps: list[Path] | None = None,
    *,
    quick: bool = False,
    on_step: Callable[[str], None] | None = None,
    on_slow_answer: Callable[[], None] | None = None,
) -> Inventory:
    """Read every client, side by side; `on_step(client_id)` runs as each one is done. `apps`
    is where to look for the clients' Mac apps; by default the usual folders of `home`'s owner,
    and nowhere when the test passes its own adapters. `quick` does not wait for slow answers:
    they come in the background, and `on_slow_answer` runs when one is in."""
    if adapters is None:
        adapters = default_adapters(home or Path.home(), quick, on_slow_answer)
    adapters = list(adapters)
    if apps is None:
        apps = app_roots(home) if home is not None else []

    def read(adapter: ClientAdapter) -> tuple[Client, Scan | None]:
        found = _read(adapter, apps)
        if on_step:
            with contextlib.suppress(Exception):  # only a progress note; never lose the scan
                on_step(adapter.id)
        return found

    with ThreadPoolExecutor(max_workers=max(len(adapters), 1)) as pool:
        results = list(pool.map(read, adapters))
    inventory = Inventory()
    projects: dict[str, Project] = {}
    for adapter, (client, scan) in zip(adapters, results, strict=True):
        if scan is None:
            inventory.clients.append(client)
            if client.status is not ClientStatus.UNREADABLE:
                continue
            inventory.problems.append(
                Source(
                    kind=SourceKind.MANAGED,
                    path=None,
                    owner_client=adapter.id,
                    read_status=ReadStatus.UNKNOWN,
                    unknown_reason=UnknownReason.UNRECOGNIZED_FORMAT,
                )
            )
            continue
        inventory.clients.append(client)
        inventory.clients += adapter.extra_clients()
        inventory.items += [replace(i, actions=adapter.item_actions(i)) for i in scan.items]
        inventory.problems += scan.problems
        for found in scan.projects:
            known = projects.get(found.path)
            projects[found.path] = (
                found
                if known is None
                else replace(known, known_by=tuple(dict.fromkeys(known.known_by + found.known_by)))
            )
    inventory.projects = sorted(projects.values(), key=lambda p: p.path)
    inventory.partial = any(adapter.skipped for adapter in adapters)
    with contextlib.suppress(Exception):  # only to match copies; never lose the scan
        folders = plugin_skill_folders({a.id: a for a in adapters})
        inventory.plugin_skills = [(plugin, str(folder)) for plugin, _, folder, _ in folders]
    return inventory


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return str(value) if hasattr(value, "value") else value


def item_dict(item: Item) -> dict:
    data = _plain(asdict(item))
    data["id"] = item.id
    data["summary"] = dict(item.summary)
    data["source"]["id"] = item.source.id
    return data


def inventory_dict(inventory: Inventory) -> dict:
    """The redacted, JSON-ready shape shared by `scan --json`, the page and the MCP server."""
    return {
        "clients": [_plain(asdict(c)) for c in inventory.clients],
        "items": [item_dict(i) for i in inventory.items],
        "projects": [{**_plain(asdict(p)), "id": p.id} for p in inventory.projects],
        "problems": [_plain(asdict(p)) for p in inventory.problems],
    }
