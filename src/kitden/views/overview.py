"""Overview model: what needs attention first, in plain words (portal redesign)."""

from pathlib import Path
from urllib.parse import urlsplit

from kitden.clients.versions import MINIMUM_VERSIONS
from kitden.model import FindingType, Gateway, Severity, UnknownReason, _hash
from kitden.views.findings import base_name, find_bypasses, find_findings
from kitden.views.gateway_view import group_of, loaded_mcp
from kitden.views.load_map import NAMES
from kitden.views.setup_server import setup_server_state

READ_PROBLEMS = {
    UnknownReason.UNRECOGNIZED_FORMAT: "The file format is not recognized.",
    UnknownReason.PARSE_ERROR: "The file has a syntax error.",
    UnknownReason.NO_ACCESS: "There is no permission to read it.",
}


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _unreadable(inventory) -> list[dict]:
    cards = []
    for problem in inventory.problems:
        where = problem.path or NAMES.get(problem.owner_client, problem.owner_client)
        cards.append(
            {
                "id": _hash("unreadable", where),
                "title": f"Could not read {Path(where).name}",
                "text": f"{READ_PROBLEMS.get(problem.unknown_reason, 'It could not be read.')} "
                f"{where}",
                "action": None,
                "target": None,
            }
        )
    return cards


def _untested(inventory) -> list[dict]:
    cards = []
    for client in inventory.clients:
        if client.version and not client.version_supported:
            cards.append(
                {
                    "id": _hash("version", client.id),
                    "title": f"{client.display_name} {client.version} is not tested",
                    "text": f"Tested from {MINIMUM_VERSIONS.get(client.id, 'a newer version')}. "
                    "Some items may be missing or wrong.",
                    "action": None,
                    "target": None,
                }
            )
    return cards


def _duplicates(inventory, findings) -> list[dict]:
    by_id = {i.id: i for i in inventory.items}
    cards = []
    for finding in findings:
        if finding.type is not FindingType.DUPLICATE_IN_CLIENT:
            continue
        items = [by_id[i] for i in finding.items if i in by_id]
        if not items:
            continue
        name = base_name(items[0])
        places = " and ".join(i.source.path or str(i.source.kind) for i in items)
        cards.append(
            {
                "id": finding.id,
                "title": f"{NAMES.get(finding.client, finding.client)} loads {name} twice",
                "text": f"From {places}.",
                "action": "Show",
                "target": {
                    "view": "map",
                    "kind": str(items[0].kind),
                    "row": _hash(items[0].kind, name),
                },
            }
        )
    return sorted(cards, key=lambda c: c["title"])


def _old_entries(inventory) -> list[dict]:
    """One card for entries the working version (agentsetup) added (feature 002)."""
    clients = [NAMES[s["client"]] for s in setup_server_state(inventory) if s["item"]]
    if not clients:
        return []
    where = " and ".join([", ".join(clients[:-1]), clients[-1]] if len(clients) > 1 else clients)
    return [
        {
            "id": _hash("old-entries", where),
            "title": f"Old Kitden {'entry' if len(clients) == 1 else 'entries'} in {where}",
            "text": "Made by the working version, agentsetup. Update so the client starts kitden.",
            "action": "Update",
            "target": {"view": "agents"},
        }
    ]


def overview(inventory, gateways: list[Gateway], project: str | None) -> dict:
    findings = find_findings(inventory, project)
    attention = (
        _unreadable(inventory)
        + _untested(inventory)
        + _old_entries(inventory)
        + _duplicates(inventory, findings)
    )

    mcp = loaded_mcp(inventory, project)
    around = [i for i in mcp if not i.via_gateway]
    groups = {g: sum(1 for i in around if group_of(i) == g) for g in ("move", "local", "plugin")}
    gateway = None
    if gateways:
        gateway = {
            "name": urlsplit(gateways[0].url).netloc or "Gateway",
            "through": len(mcp) - len(around),
            "total": len(mcp),
            "can_move": groups["move"],
            "stay_local": groups["local"],
            "from_plugins": groups["plugin"],
        }
        if around:
            parts = [
                f"{groups['move']} can move in." if groups["move"] else "",
                f"{groups['local']} must run on this Mac." if groups["local"] else "",
                _count(groups["plugin"], "comes from a plugin.", "come from plugins.")
                if groups["plugin"]
                else "",
            ]
            attention.append(
                {
                    "id": _hash("gateway", project),
                    "title": f"{_count(len(around), 'MCP server goes', 'MCP servers go')} "
                    "around your gateway",
                    "text": " ".join(p for p in parts if p),
                    "action": "Review",
                    "target": {"view": "gateway"},
                }
            )

    info = [f for f in findings if f.severity is Severity.INFO]
    if not gateways:
        info += find_bypasses(inventory, project)
    n = len(attention)
    headline = "All clear" if not n else f"{_count(n, 'thing needs', 'things need')} attention"
    return {
        "headline": headline,
        "attention": attention,
        "notes": len(info),
        "clients": [
            {
                "id": c.id,
                "name": c.display_name,
                "version": c.version,
                "tested": c.version_supported,
                "status": str(c.status),
            }
            for c in inventory.clients
        ],
        "gateway": gateway,
    }
