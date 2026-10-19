"""One inventory from all client adapters (FR-001 to FR-005)."""

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from kitden.apps import app_roots, app_url
from kitden.clients.base import ClientAdapter
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


@dataclass
class Inventory:
    clients: list[Client] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    problems: list[Source] = field(default_factory=list)


def default_adapters(home: Path) -> list[ClientAdapter]:
    return [ClaudeCodeAdapter(home), CodexAdapter(home), CursorAdapter(home)]


def build_inventory(
    home: Path | None = None,
    adapters: Iterable[ClientAdapter] | None = None,
    apps: list[Path] | None = None,
) -> Inventory:
    """Read every client. `apps` is where to look for the clients' Mac apps; by default the
    usual folders of `home`'s owner, and nowhere when the test passes its own adapters."""
    adapters = list(adapters) if adapters is not None else default_adapters(home or Path.home())
    if apps is None:
        apps = app_roots(home) if home is not None else []
    inventory = Inventory()
    projects: dict[str, Project] = {}
    for adapter in adapters:
        client = replace(adapter.detect(), app_url=app_url(adapter.id, apps))
        if client.status is ClientStatus.NOT_FOUND:
            inventory.clients.append(client)
            continue
        try:
            scan = adapter.scan()
        except Exception:  # a changed file format must not hide the other clients
            inventory.clients.append(replace(client, status=ClientStatus.UNREADABLE))
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
