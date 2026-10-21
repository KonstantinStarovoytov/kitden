"""Overview model: what needs attention first, in plain words (portal redesign).

Every card is a short title, one sentence that says why it matters and what to do, and one
action. Cards never show file paths: those live in the side panel.
"""

from pathlib import Path
from urllib.parse import urlsplit

from kitden.clients.versions import MINIMUM_VERSIONS
from kitden.model import FindingType, Gateway, Severity, UnknownReason, _hash
from kitden.views.findings import base_name, find_bypasses, find_findings
from kitden.views.gateway_view import gateway_view
from kitden.views.load_map import COLUMNS, NAMES, row_key
from kitden.views.setup_server import setup_server_state

READ_PROBLEMS = {
    UnknownReason.UNRECOGNIZED_FORMAT: "The file format is not recognized",
    UnknownReason.PARSE_ERROR: "The file has a syntax error",
    UnknownReason.NO_ACCESS: "There is no permission to read it",
}
KIND_WORDS = {"mcp_server": "MCP server", "plugin": "plugin", "skill": "skill"}


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _join(words: list[str]) -> str:
    return " and ".join([", ".join(words[:-1]), words[-1]] if len(words) > 1 else words)


def _client_order(client: str) -> int:
    return COLUMNS.index(client) if client in COLUMNS else len(COLUMNS)


def _unreadable(inventory) -> list[dict]:
    cards = []
    for problem in inventory.problems:
        where = problem.path or NAMES.get(problem.owner_client, problem.owner_client)
        why = READ_PROBLEMS.get(problem.unknown_reason, "It could not be read")
        client = NAMES.get(problem.owner_client, problem.owner_client)
        cards.append(
            {
                "id": _hash("unreadable", where),
                "title": f"Could not read {Path(where).name}",
                "text": f"{why}, so items from {client} may be missing or wrong.",
                "action": None,
                "target": None,
            }
        )
    return cards


def _untested(inventory) -> list[dict]:
    cards = []
    for client in inventory.clients:
        if client.version and not client.version_supported:
            tested = MINIMUM_VERSIONS.get(client.id, "a newer version")
            cards.append(
                {
                    "id": _hash("version", client.id),
                    "title": f"{client.display_name} {client.version} is not tested",
                    "text": f"Tested from {tested}, so some items may be missing or wrong.",
                    "action": None,
                    "target": None,
                }
            )
    return cards


def _duplicates(inventory, findings) -> list[dict]:
    """One card per item that loads twice, naming every client where it does."""
    by_id = {i.id: i for i in inventory.items}
    groups: dict[tuple, dict] = {}
    for finding in findings:
        if finding.type is not FindingType.DUPLICATE_IN_CLIENT:
            continue
        items = [by_id[i] for i in finding.items if i in by_id]
        if not items:
            continue
        key = (str(items[0].kind), base_name(items[0]))
        group = groups.setdefault(key, {"clients": set(), "copies": 0, "row": row_key(items[0])})
        group["clients"].add(finding.client)
        group["copies"] = max(group["copies"], len(items))
    cards = []
    for (kind, name), group in groups.items():
        clients = sorted(group["clients"], key=_client_order)
        copies = group["copies"]
        times = "twice" if copies == 2 else f"{copies} times"
        cards.append(
            {
                "id": _hash("duplicate", kind, name),
                "title": f"{name} loads {times} in {_join([NAMES.get(c, c) for c in clients])}",
                "text": f"{'Two' if copies == 2 else copies} copies of one "
                f"{KIND_WORDS.get(kind, kind)} load; keep one.",
                "action": "Keep one…",
                "target": {"view": "map", "kind": kind, "row": group["row"]},
            }
        )
    return sorted(cards, key=lambda c: c["title"])


def _old_entries(inventory) -> list[dict]:
    """One card for entries the working version (agentsetup) added (feature 002)."""
    clients = [NAMES[s["client"]] for s in setup_server_state(inventory) if s["item"]]
    if not clients:
        return []
    where = _join(clients)
    one = len(clients) == 1
    it = "it" if one else "them"
    return [
        {
            "id": _hash("old-entries", where),
            "title": f"Old Kitden {'entry' if one else 'entries'} in {where}",
            "text": f"The working version, agentsetup, made {it}; update {it} so {where} "
            f"{'starts' if one else 'start'} kitden.",
            "action": "Update",
            "target": {"view": "agents"},
        }
    ]


def _kitden_card(inventory, held: list[dict], problem: str | None) -> dict | None:
    """The Kitden gateway: how many servers it holds and which clients reach it. A client with
    an old entry is neither connected nor offered a new one: the old entry is updated instead."""
    states = setup_server_state(inventory)
    clients = [s["client"] for s in states if s["state"] in ("added", "plugin")]
    if not (held or clients or problem):
        return None
    return {
        "kind": "kitden",
        "name": "Kitden gateway",
        "servers": len(held),
        "clients": clients,
        "lacking": [s["client"] for s in states if s["state"] == "missing"],
        "problem": problem,
    }


def overview(
    inventory,
    gateways: list[Gateway],
    project: str | None,
    held: list[dict] | None = None,
    problem: str | None = None,
) -> dict:
    findings = find_findings(inventory, project)
    attention = (
        _unreadable(inventory)
        + _untested(inventory)
        + _old_entries(inventory)
        + _duplicates(inventory, findings)
    )

    # Direct servers are an option, not a problem. The count is the Gateway page's rows, so a
    # server in two clients counts once; with the Kitden gateway, local servers can move too.
    gateway = None
    suggestions = []
    kitden = None if held is None else _kitden_card(inventory, held, problem)
    if kitden or gateways:
        view = gateway_view(inventory, gateways, project, kitden=held if kitden else None)
        groups = view["groups"]
        rows = groups["move"] + (groups["local"] if kitden else [])
        moves = len({row["name"] for row in rows})
        gateway = kitden or {"name": urlsplit(gateways[0].url).netloc or "Gateway"}
        if moves:
            into = "the Kitden gateway" if kitden else "the gateway"
            suggestions.append(
                {
                    "title": f"{_count(moves, 'MCP server', 'MCP servers')} can move into {into}",
                    "text": f"{'It connects' if moves == 1 else 'They connect'} to each client "
                    "directly now.",
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
        "suggestions": suggestions,
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
