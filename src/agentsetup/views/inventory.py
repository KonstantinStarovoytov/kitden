"""One inventory from all client adapters (FR-001 to FR-005)."""

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from agentsetup.clients.base import ClientAdapter
from agentsetup.clients.claude_code import ClaudeCodeAdapter
from agentsetup.clients.codex import CodexAdapter
from agentsetup.clients.cursor import CursorAdapter
from agentsetup.model import (
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
    home: Path | None = None, adapters: Iterable[ClientAdapter] | None = None
) -> Inventory:
    adapters = list(adapters) if adapters is not None else default_adapters(home or Path.home())
    inventory = Inventory()
    projects: dict[str, Project] = {}
    for adapter in adapters:
        client = adapter.detect()
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
