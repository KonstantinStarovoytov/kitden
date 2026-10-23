"""Findings: duplicates, cross-loading, overrides, unknown state, unsupported versions, and MCP
servers that bypass the gateway.

FR-011 to FR-014, FR-034, FR-039. Built on the per-project effective views, so "loads twice"
means it really loads twice in that client and project. A name set up in two clients is one item
set up twice only when it comes from the same source (match.py); else it is the same name from
another source. Every finding names the clients it is about.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace

from kitden.changes.actions import KITDEN_GATEWAY
from kitden.model import (
    ClientStatus,
    Enabled,
    Finding,
    FindingType,
    Gateway,
    Item,
    ItemKind,
    Scope,
    Severity,
    SourceKind,
    normalize_url,
)
from kitden.views.effective import DESKTOP, effective_view
from kitden.views.match import odd_ones, source_keys
from kitden.views.setup_server import is_own_entry

# Kinds where two copies are a problem. Hooks all run by design; marketplaces are just sources.
DUPLICATE_KINDS = {ItemKind.MCP_SERVER, ItemKind.SKILL, ItemKind.PLUGIN}


def _where(item: Item) -> str:
    return item.source.path or f"{item.source.owner_client} account"


def _finding(
    kind: FindingType,
    severity: Severity,
    items: Iterable[Item],
    text: str,
    client: str | None = None,
    clients: tuple[str, ...] = (),
) -> Finding:
    items = list(items)
    return Finding(
        type=kind,
        severity=severity,
        items=tuple(i.id for i in items),
        names=tuple(i.name for i in items),
        explanation=text,
        client=client,
        clients=clients or ((client,) if client else ()),
    )


def base_name(item: Item) -> str:
    # The same plugin can come from different marketplaces: "x@a" and "x@b" are both "x".
    return item.name.split("@", 1)[0] if item.kind is ItemKind.PLUGIN else item.name


def find_findings(inventory, project: str | None = None) -> list[Finding]:
    findings: list[Finding] = []
    clients = sorted({i.client for i in inventory.items} - {DESKTOP})
    own: dict[tuple[ItemKind, str], dict[str, Item]] = defaultdict(dict)

    for client in clients:
        view = effective_view(inventory, client, project)

        groups: dict[tuple[ItemKind, str], list[Item]] = defaultdict(list)
        for item in view.items:
            if item.kind in DUPLICATE_KINDS:
                groups[(item.kind, base_name(item))].append(item)
        for (kind, name), same in groups.items():
            if len(same) > 1:
                places = "; ".join(_where(i) for i in same)
                findings.append(
                    _finding(
                        FindingType.DUPLICATE_IN_CLIENT,
                        Severity.WARNING,
                        same,
                        f"{client} loads {kind.replace('_', ' ')} '{name}' {len(same)} times: "
                        f"{places}",
                        client,
                    )
                )

        for winner, loser, mode in view.shadowed:
            # A Kitden gateway server's project item replaces its global one by design.
            if KITDEN_GATEWAY in (winner.via_gateway, loser.via_gateway):
                continue
            findings.append(
                _finding(
                    FindingType.SCOPE_OVERRIDE,
                    Severity.INFO,
                    [winner, loser],
                    f"In {client}, '{winner.name}' from {winner.scope} ({_where(winner)}) "
                    f"{'is merged over' if mode == 'merged' else 'replaces'} the {loser.scope} "
                    f"definition ({_where(loser)})",
                    client,
                )
            )

        for item in view.items:
            if item.source.kind is SourceKind.OTHER_CLIENT_FOLDER:
                findings.append(
                    _finding(
                        FindingType.CROSS_LOADED,
                        Severity.INFO,
                        [item],
                        f"{client} loads '{item.name}' from {item.source.owner_client}: "
                        f"{_where(item)}",
                        client,
                    )
                )
            elif item.source.owner_client == client:
                # Kitden's own entry and servers it holds are meant to be in every client, and
                # one AGENTS.md read by two clients is expected.
                if (
                    is_own_entry(item)
                    or item.via_gateway == KITDEN_GATEWAY
                    or item.kind is ItemKind.INSTRUCTIONS
                ):
                    continue
                own[(item.kind, item.name)][client] = item

        unknown = [i for i in view.items if i.enabled is Enabled.UNKNOWN]
        if unknown:
            findings.append(
                _finding(
                    FindingType.UNKNOWN_STATE,
                    Severity.INFO,
                    unknown,
                    f"{client}: on/off state of {len(unknown)} items "
                    "cannot be read from local files",
                    client,
                )
            )

    if any(i.client == DESKTOP for i in inventory.items):
        for winner, loser, _mode in effective_view(inventory, DESKTOP, project).shadowed:
            if winner.client == DESKTOP:
                findings.append(
                    _finding(
                        FindingType.SCOPE_OVERRIDE,
                        Severity.INFO,
                        [winner, loser],
                        f"In the Claude Desktop Code tab, '{winner.name}' from {_where(winner)} "
                        f"replaces the Claude Code definition ({_where(loser)})",
                        DESKTOP,
                    )
                )

    for (kind, name), by_client in own.items():
        if len(by_client) < 2:
            continue
        where = ", ".join(sorted(by_client))
        if not odd_ones({c: source_keys(i) for c, i in by_client.items()}):
            found, text = (
                FindingType.SAME_IN_OTHER_CLIENTS,
                f"{kind.replace('_', ' ')} '{name}' is set up separately in {where}",
            )
        else:
            found, text = (
                FindingType.SAME_NAME_OTHER_SOURCE,
                f"{kind.replace('_', ' ')} '{name}' has the same name in {where} but comes from "
                "another source",
            )
        findings.append(
            _finding(
                found, Severity.INFO, by_client.values(), text, clients=tuple(sorted(by_client))
            )
        )

    for client in inventory.clients:
        if client.status is ClientStatus.FOUND and client.version and not client.version_supported:
            items = [i for i in inventory.items if i.client == client.id]
            if items:
                findings.append(
                    _finding(
                        FindingType.VERSION_UNSUPPORTED,
                        Severity.WARNING,
                        items,
                        f"{client.display_name} {client.version} is older than the tested "
                        "versions; results may be incomplete",
                        client.id,
                    )
                )
    return findings


def finding_dict(f: Finding) -> dict:
    return {
        "id": f.id,
        "type": str(f.type),
        "severity": str(f.severity),
        "items": list(f.items),
        "names": list(f.names),
        "client": f.client,
        "clients": list(f.clients),
        "explanation": f.explanation,
    }


def mark_gateways(inventory, gateways: list[Gateway]) -> None:
    """Mark MCP entries that point to a registered gateway (FR-034). They are not direct."""
    by_url = {g.url: g for g in gateways}
    for index, item in enumerate(inventory.items):
        url = dict(item.summary).get("url")
        gateway = (
            by_url.get(normalize_url(url)) if item.kind is ItemKind.MCP_SERVER and url else None
        )
        if gateway:
            actions = tuple(a for a in item.actions if a != "mcp.remove_direct")
            inventory.items[index] = replace(item, via_gateway=gateway.id, actions=actions)


def bypass_kind(item: Item) -> str:
    if item.scope is Scope.PLUGIN or item.source.kind is SourceKind.PLUGIN:
        return "comes from a plugin"
    if "command" in dict(item.summary):
        return "is a local server (runs on this computer)"
    return "is a direct entry"


def find_bypasses(inventory, project: str | None = None) -> list[Finding]:
    """Every MCP server that loads without going through a registered gateway (FR-039), except
    Kitden's own entry."""
    findings = []
    for client in sorted({i.client for i in inventory.items}):
        for item in effective_view(inventory, client, project).items:
            if item.kind is not ItemKind.MCP_SERVER or item.via_gateway or item.client != client:
                continue
            if is_own_entry(item):  # Kitden's own read-only server, not a tool server
                continue
            text = (
                f"{client}: {item.name} {bypass_kind(item)} and does not go through the "
                f"gateway. Source: {_where(item)}."
            )
            findings.append(
                _finding(FindingType.BYPASSES_GATEWAY, Severity.INFO, [item], text, client)
            )
    return findings
