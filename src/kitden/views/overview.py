"""Overview model: what needs attention first, in plain words, and a small map of the setup.

Every card has a name, one line that says why it matters, the clients it is about and one action:
a change for the tray (`body`) or a page to open (`go`). Cards never show file paths: those live
in the side panel.
"""

from pathlib import Path

from kitden.changes.actions import (
    GATEWAY_MOVE,
    KITDEN_GATEWAY,
    SETUP_SERVER_ENABLE,
    SETUP_SERVER_UPDATE,
)
from kitden.clients.base import SETUP_SERVER
from kitden.clients.versions import MINIMUM_VERSIONS
from kitden.local_gateway.settings import SETTINGS_FILE
from kitden.model import Finding, FindingType, Gateway, ItemKind, Severity, UnknownReason, _hash
from kitden.views.findings import base_name, find_bypasses, find_findings
from kitden.views.gateway_view import gateway_view
from kitden.views.library_map import library_map
from kitden.views.load_map import COLUMNS, NAMES
from kitden.views.setup_server import ENABLE_KEYS, kitden_on, setup_server_state

READ_PROBLEMS = {
    UnknownReason.UNRECOGNIZED_FORMAT: "The file format is not recognized",
    UnknownReason.PARSE_ERROR: "The file has a syntax error",
    UnknownReason.NO_ACCESS: "There is no permission to read it",
}
KIND_WORDS = {"mcp_server": "MCP server", "plugin": "plugin", "skill": "skill"}
# A card's icon: lucide names the page has (icons.js), or a client's mark.
KIND_ICONS = {"mcp_server": "server", "plugin": "puzzle", "skill": "sparkles"}
GROUP_ICONS = {"move": "globe", "local": "hard-drive"}
# The group's word, as the Gateway says it, before the line of two cards with one name.
GROUP_WORDS = {"move": "Remote", "local": "Local"}
# Server cards before one card says how many more there are.
SERVER_CARDS = 3
SKIPS = "Skips the gateway, so Kitden's rules don't reach it."
NOT_CONNECTED = "Not connected to the gateway yet."


def _join(words: list[str]) -> str:
    return " and ".join([", ".join(words[:-1]), words[-1]] if len(words) > 1 else words)


def _client_order(client: str) -> int:
    return COLUMNS.index(client) if client in COLUMNS else len(COLUMNS)


def _card(id, group, icon, name, line, clients, action, block) -> dict:
    """One card: its group ("attention" or "improve"), icon, name, one line, the clients it is
    about, its one action (or None) and what the "Your setup" map focuses for it."""
    return {
        "id": id,
        "group": group,
        "icon": icon,
        "name": name,
        "line": line,
        "clients": clients,
        "action": action,
        "focus": {"clients": clients, "block": block},
    }


def _unreadable(inventory) -> list[dict]:
    cards = []
    for problem in inventory.problems:
        where = problem.path or NAMES.get(problem.owner_client, problem.owner_client)
        why = READ_PROBLEMS.get(problem.unknown_reason, "It could not be read")
        client = NAMES.get(problem.owner_client, problem.owner_client)
        title = f"Could not read {Path(where).name}"
        text = f"{why}, so items from {client} may be missing or wrong."
        clients = [problem.owner_client] if problem.owner_client in COLUMNS else []
        card_id = _hash("unreadable", where)
        cards.append(_card(card_id, "attention", "file-text", title, text, clients, None, None))
    return cards


def _gateway_unreadable() -> dict:
    """Kitden cannot read its own gateway settings: they read as empty, so the page says so
    instead of showing an empty gateway (local_gateway/settings.py `load_settings`)."""
    line = f"Kitden can't read {SETTINGS_FILE}, so the gateway's servers and rules are not known."
    name = "Could not read the Kitden gateway settings"
    card_id = _hash("unreadable", SETTINGS_FILE)
    return _card(card_id, "attention", "file-text", name, line, [], None, "gateway")


def _untested(inventory) -> list[dict]:
    cards = []
    for client in inventory.clients:
        if client.version and not client.version_supported:
            tested = MINIMUM_VERSIONS.get(client.id, "a newer version")
            title = f"{client.display_name} {client.version} is not tested"
            text = f"Tested from {tested}, so some items may be missing or wrong."
            icon = {"client": client.id}
            card_id = _hash("version", client.id)
            card = _card(card_id, "attention", icon, title, text, [client.id], None, None)
            cards.append(card)
    return cards


def _duplicates(inventory, findings) -> list[dict]:
    """One card per item that loads twice, naming every client where it does. "Keep one…" opens
    the first copy, by kind and full name, as the page's address does (`sel`): a choice is
    needed, so it adds no change itself. An MCP server opens on the Gateway, the rest in the
    Library."""
    by_id = {i.id: i for i in inventory.items}
    groups: dict[tuple, dict] = {}
    for finding in findings:
        if finding.type is not FindingType.DUPLICATE_IN_CLIENT:
            continue
        items = [by_id[i] for i in finding.items if i in by_id]
        if not items:
            continue
        key = (str(items[0].kind), base_name(items[0]))
        group = groups.setdefault(key, {"clients": set(), "copies": 0, "name": items[0].name})
        group["clients"].add(finding.client)
        group["copies"] = max(group["copies"], len(items))
    cards = []
    for (kind, name), group in groups.items():
        clients = sorted(group["clients"], key=_client_order)
        copies = group["copies"]
        text = (
            f"{'Two' if copies == 2 else copies} copies of one "
            f"{KIND_WORDS.get(kind, kind)} load; keep one."
        )
        server = kind == str(ItemKind.MCP_SERVER)
        go = {"view": "gateway" if server else "library", "sel": f"{kind}:{group['name']}"}
        action = {"label": "Keep one…", "go": go}
        block = "gateway" if server else "library"
        icon = KIND_ICONS.get(kind, "puzzle")
        card_id = _hash("duplicate", kind, name)
        cards.append(_card(card_id, "attention", icon, name, text, clients, action, block))
    return sorted(cards, key=lambda c: (c["name"], [_client_order(x) for x in c["clients"]]))


def _old_entries(inventory) -> list[dict]:
    """One card for entries the working version (agentsetup) added (feature 002). "Update…"
    adds the Agents page's update of all of them (agents.js `update`) to the tray."""
    old = [s for s in setup_server_state(inventory) if s["item"]]
    if not old:
        return []
    ids = [s["client"] for s in old]
    where = _join([NAMES[c] for c in ids])
    one = len(ids) == 1
    it = "it" if one else "them"
    title = f"Old Kitden {'entry' if one else 'entries'} in {where}"
    text = (
        f"The working version, agentsetup, made {it}; update {it} so {where} "
        f"{'starts' if one else 'start'} kitden."
    )
    targets = [{"item": s["item"]} for s in old]
    body = {"action": SETUP_SERVER_UPDATE, "targets": targets, "params": {}}
    action = {"label": "Update…", "body": body}
    card_id = _hash("old-entries", where)
    return [_card(card_id, "attention", "house", title, text, ids, action, "gateway")]


def _move_ins(groups: dict) -> list[dict]:
    """A card per server outside the Kitden gateway that a move can take, as the Gateway's
    "Move into the gateway…" offers it (gateway-details.js `movesTo`): its row has entries
    Kitden can remove and nothing that makes the move refuse it. "Move in…" adds the same
    change (details.js `moveBody`). Two cards with one name (a remote and a local server) start
    their line with the group's word. Past SERVER_CARDS, one card says how many more and opens
    the Gateway's List at the outside group."""
    rows = [
        (group, row)
        for group in ("move", "local")
        for row in groups[group]
        if row["items"] and not row["stays"]
    ]
    rows.sort(key=lambda pair: pair[1]["name"].lower())
    names = [row["name"] for _, row in rows[:SERVER_CARDS]]
    cards = []
    for group, row in rows[:SERVER_CARDS]:
        targets = [{"item": i} for i in row["items"]]
        params = {"gateway": KITDEN_GATEWAY}
        action = {
            "label": "Move in…",
            "body": {"action": GATEWAY_MOVE, "targets": targets, "params": params},
        }
        icon = GROUP_ICONS[group]
        card_id = _hash("move-in", group, row["name"])
        line = f"{GROUP_WORDS[group]} · {SKIPS}" if names.count(row["name"]) > 1 else SKIPS
        cards.append(
            _card(card_id, "improve", icon, row["name"], line, row["columns"], action, "gateway")
        )
    rest = rows[SERVER_CARDS:]
    if rest:
        clients = sorted({c for _, row in rest for c in row["columns"]}, key=_client_order)
        n = len(rest)
        name = f"{n} more {'server skips' if n == 1 else 'servers skip'} the gateway"
        line = f"Kitden's rules don't reach {'it' if n == 1 else 'them'}."
        go = {"view": "gateway", "sel": "group:outside", "mode": "list"}
        action = {"label": "Show…", "go": go}
        card_id = _hash("move-in", "more")
        cards.append(_card(card_id, "improve", "server", name, line, clients, action, "gateway"))
    return cards


def _connects(inventory) -> list[dict]:
    """A card per client the Kitden gateway does not reach yet, with the Gateway's own change
    that connects it (gateway-details.js `connectBody`): its `kitden` entry is added, or turned
    back on where its docs name the switch. A client with an old entry gets the update instead
    (`_old_entries`); one whose entry a plugin gives, or that is not on this Mac, gets none."""
    cards = []
    for entry in setup_server_state(inventory):
        client = entry["client"]
        if entry["state"] == "missing":
            body = {"action": SETUP_SERVER, "targets": [{"client": client}], "params": {}}
        elif entry["state"] == "added" and entry["enabled"] is False and client in ENABLE_KEYS:
            body = {"action": SETUP_SERVER_ENABLE, "targets": [{"client": client}], "params": {}}
        else:
            continue
        action = {"label": "Connect…", "body": body}
        name, icon, card_id = NAMES[client], {"client": client}, _hash("connect", client)
        card = _card(card_id, "improve", icon, name, NOT_CONNECTED, [client], action, "gateway")
        cards.append(card)
    return cards


def _library_rules(answer: dict) -> bool:
    """The picked project's own settings decide a plugin or skill there (the Library's `here`)."""
    return any(
        any(item["here"].values())
        for group in answer["groups"]
        for item in group["items"]
        if item["kind"] in ("plugin", "skill")
    )


def _ruled_projects(inventory, adapters) -> set[str]:
    """The known projects whose own settings decide a plugin or skill. Only a project that has
    an item of its own, or a rule for a user skill, can: the Library map is read for those."""
    kinds = (ItemKind.PLUGIN, ItemKind.SKILL)
    maybe = {i.project for i in inventory.items if i.kind in kinds and i.project}
    maybe |= {p for i in inventory.items if i.kind in kinds for p, _, _ in i.project_rules}
    known = [p.path for p in inventory.projects if p.path in maybe]
    return {p for p in known if _library_rules(library_map(inventory, adapters, p))}


def _setup_map(inventory, adapters, project, held, gateway_rules, unread=False) -> dict:
    """The small "Your setup" map: the clients (`on`: found on this Mac), the Kitden gateway's
    servers and tools, the Library's plugins and skills, which client reaches which, and how
    many projects have rules of their own (for the gateway, or for a plugin or skill). While
    the gateway settings cannot be read (`unread`) its counts are not known (None)."""
    clients = [c for c in inventory.clients if c.id in COLUMNS]
    found = [c for c in clients if str(c.status) == "found"]
    shown = library_map(inventory, adapters, project)
    items = [i for g in shown["groups"] for i in g["items"]]
    states = {s["client"]: s for s in setup_server_state(inventory)}
    links = []
    for client in found:
        if kitden_on(states[client.id]):
            links.append({"client": client.id, "to": "gateway"})
        if any(i["by"].get(client.id) == "on" for i in items):
            links.append({"client": client.id, "to": "library"})
    ruled = _ruled_projects(inventory, adapters) | {
        p.path for p in inventory.projects if p.path in gateway_rules
    }
    return {
        "clients": [
            {
                "id": c.id,
                "name": c.display_name,
                "version": c.version,
                "tested": c.version_supported,
                "on": str(c.status) == "found",
            }
            for c in clients
        ],
        "gateway": {
            "servers": None if unread else len(held or []),
            "tools": None if unread else sum(s.get("tools") or 0 for s in held or []),
            "unread": unread,
        },
        "library": {
            "plugins": sum(i["kind"] == "plugin" for i in items),
            "skills": sum(i["kind"] == "skill" for i in items),
        },
        "links": links,
        "projects": len(inventory.projects),
        "own_rules": len(ruled),
    }


def note_count(findings: list[Finding]) -> int:
    """The notes the page shows: one row per name, however many notes it has."""
    return len({name for f in findings for name in f.names})


def overview(
    inventory,
    gateways: list[Gateway],
    project: str | None,
    held: list[dict] | None = None,
    adapters: dict | None = None,
    gateway_rules: set[str] | frozenset[str] = frozenset(),
    problem: str | None = None,
) -> dict:
    """The Overview page's `cards`, `notes` (how many rows the folded notes draw), `map` (the
    "Your setup" map) and `counts` (for the lede). `held` are the servers the Kitden gateway
    holds (None: no Kitden gateway here), `adapters` the clients' adapters, for the Library's
    counts, `gateway_rules` the known projects with gateway rules of their own, and `problem`
    why the Kitden gateway settings could not be read (None: they could)."""
    findings = find_findings(inventory, project)
    cards = (
        _unreadable(inventory)
        + ([_gateway_unreadable()] if problem else [])
        + _untested(inventory)
        + _old_entries(inventory)
        + _duplicates(inventory, findings)
    )
    # Servers outside the gateway and clients not connected are options, not problems. The rows
    # are the Gateway page's, so a server in two clients is one card. Nothing moves into a gateway
    # whose settings Kitden cannot read.
    if held is not None and not problem:
        groups = gateway_view(inventory, gateways, project, kitden=held)["groups"]
        cards += _move_ins(groups)
    if held and not problem:
        cards += _connects(inventory)

    # The notes the page lists: the info findings of /api/findings, gateway bypasses too.
    info = [f for f in findings + find_bypasses(inventory, project) if f.severity is Severity.INFO]
    setup = _setup_map(inventory, adapters or {}, project, held, gateway_rules, bool(problem))
    return {
        "cards": cards,
        "notes": note_count(info),
        "map": setup,
        "counts": {
            "attention": sum(c["group"] == "attention" for c in cards),
            # The map's clients: the Desktop Code tab counts as Claude Code.
            "clients": sum(c["on"] for c in setup["clients"]),
            "projects": len(inventory.projects),
        },
    }
