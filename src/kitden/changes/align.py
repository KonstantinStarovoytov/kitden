"""Add what one client loads in a project and another client lacks, in one review (spec 3.5).

Each add is built by the same step builders as a single add from the Library.
"""

import os
from pathlib import Path

from kitden.changes.actions import (
    CLIENT_WORDS,
    _skill_readers,
    add_server_steps,
    install_steps,
)
from kitden.clients.base import SETUP_NAME, ClientAdapter, is_direct_entry
from kitden.model import Item, ItemKind, Scope, Step
from kitden.views.catalog import catalog
from kitden.views.effective import effective_view
from kitden.views.findings import base_name
from kitden.views.skills import read_skill, skill_catalog

CLIENTS = ("claude_code", "codex", "cursor")
KINDS = (ItemKind.MCP_SERVER, ItemKind.PLUGIN, ItemKind.SKILL)
# What makes two MCP entries one server; "type" is only how each client spells it.
SERVER_FIELDS = ("command", "args", "url")
NO_OFFER = "not in a marketplace on this computer"


def _is_source(item: Item, client: str) -> bool:
    """An item `client` loads that another client can get a copy of."""
    if item.kind is ItemKind.MCP_SERVER:
        return is_direct_entry(item, client, {Scope.USER}) and item.name != SETUP_NAME
    if item.scope not in (Scope.USER, Scope.PROJECT):
        return False
    if item.kind is ItemKind.PLUGIN:
        return "@" in item.name
    # A skill in the client's own folder; ~/.agents/skills is Cursor's own folder too.
    own = item.source.owner_client in (client, "shared")
    return own and item.source.link_path is None and item.source.path is not None


def _source(item: Item) -> object:
    """Where an item comes from: two items with the same name and source are the same."""
    if item.kind is ItemKind.MCP_SERVER:
        return tuple(pair for pair in item.summary if pair[0] in SERVER_FIELDS)
    if item.kind is ItemKind.SKILL:
        return os.path.realpath(item.source.path or "")
    return item.name


def _place(item: Item, client: str, adapters: dict[str, ClientAdapter], project: str) -> str:
    """Where the add goes: "project" when the client can load it from the project, else "all".
    An MCP entry and a Codex plugin are for all projects; Codex reads a project's skills only
    when it trusts the project."""
    if item.kind is ItemKind.MCP_SERVER:
        return "all"
    if item.kind is ItemKind.PLUGIN:
        return "project" if client == "claude_code" else "all"
    codex = adapters.get("codex")
    if client == "codex" and codex is not None and not codex.trusts(project):
        return "all"
    return "project"


def _build(
    item: Item,
    client: str,
    place: str,
    adapters: dict[str, ClientAdapter],
    offers: dict[str, dict],
    found: set[str],
    project: str,
) -> list[Step]:
    """The steps of one add, as the single add makes them. Raises ValueError with the reason
    when the client cannot get it."""
    into = project if place == "project" else None
    if item.kind is ItemKind.MCP_SERVER:
        return add_server_steps(adapters, item, [client])
    if item.kind is ItemKind.PLUGIN:
        offer = offers.get(item.name)
        if offer is None:
            raise ValueError(NO_OFFER)
        if client not in offer["routes"]:
            raise ValueError(f"{CLIENT_WORDS[client]} cannot get it")
        return install_steps(adapters, offer, [client], into)
    folder = Path(item.source.path or "").parent
    if not read_skill(folder)["self_contained"]:
        raise ValueError("needs the rest of its plugin")
    readers = _skill_readers(client, adapters, found)
    return [adapters[client].skill_copy_step(folder, readers, into)]


def _not_same(views: dict[str, list[Item]]) -> list[dict]:
    """Names two clients load from different sources: a plugin from another marketplace, a
    skill from another folder, an MCP server with another command or address."""
    sources: dict[tuple, dict[str, set]] = {}
    for client, items in views.items():
        for item in items:
            own = item.via_gateway is None and item.name != SETUP_NAME
            if own and item.scope is not Scope.ACCOUNT:
                key = (item.kind, base_name(item))
                sources.setdefault(key, {}).setdefault(client, set()).add(_source(item))
    out = []
    for (kind, name), by_client in sources.items():
        if len(by_client) > 1 and len({frozenset(s) for s in by_client.values()}) > 1:
            clients = [c for c in CLIENTS if c in by_client]
            out.append({"kind": kind.value, "name": name, "clients": clients})
    return sorted(out, key=lambda n: (KINDS.index(ItemKind(n["kind"])), n["name"]))


def align_steps(
    inventory,
    adapters: dict[str, ClientAdapter],
    project: str,
    found: set[str],
    chosen: list[str] | None,
) -> tuple[list[Step], dict]:
    """Every plugin, skill and MCP server one found client loads in `project` and another
    lacks, as candidates; the steps add the chosen ones. Names match exactly. A client that
    has an item turned off keeps it off: it is not offered."""
    clients = [c for c in CLIENTS if c in found and c in adapters]
    views = {
        c: [i for i in effective_view(inventory, c, project).items if i.kind in KINDS]
        for c in clients
    }
    has: dict[str, set] = {
        c: {
            (i.kind, base_name(i))
            for i in inventory.items
            if i.client == c and i.project in (None, project)
        }
        for c in clients
    }
    # Skills a client loads from a plugin the scan does not list (Codex and Cursor plugins).
    for skill in skill_catalog(inventory, adapters):
        for client in skill["installed"]:
            if client in has:
                has[client].add((ItemKind.SKILL, skill["name"]))
    offers = {o["id"]: o for o in catalog(inventory, adapters)}

    candidates: list[dict] = []
    built: list[list[Step]] = []
    left_out: list[dict] = []
    seen: set[tuple] = set()
    for source in clients:
        for kind in KINDS:
            items = sorted(
                (i for i in views[source] if i.kind is kind and _is_source(i, source)),
                key=lambda i: i.name,
            )
            for item in items:
                for client in clients:
                    key = (kind, base_name(item), client)
                    if client == source or key in seen or key[:2] in has[client]:
                        continue
                    seen.add(key)
                    place = _place(item, client, adapters, project)
                    try:
                        steps = _build(item, client, place, adapters, offers, found, project)
                    except ValueError as error:
                        why = {"name": item.name, "why": str(error)}
                        if why not in left_out:
                            left_out.append(why)
                        continue
                    name = f"{kind.value}:{item.name}:{client}"
                    candidates.append(
                        {
                            "key": name,
                            "kind": kind.value,
                            "name": item.name,
                            "from": source,
                            "to": client,
                            "place": place,
                            "chosen": chosen is None or name in chosen,
                        }
                    )
                    built.append(steps)

    steps: list[Step] = []
    marketplaces: set[tuple] = set()
    # Skill name -> the clients a copy made here reaches, and that copy's place.
    reached: dict[str, tuple[list[str], str]] = {}
    for candidate, add in zip(candidates, built, strict=True):
        if not candidate["chosen"]:
            continue
        readers, place = reached.get(candidate["name"], ([], ""))
        if candidate["to"] in readers:
            candidate["place"] = place  # it loads the copy made for another client
            continue
        for step in add:
            if step.copy is not None:
                reached[candidate["name"]] = (step.copy.readers, candidate["place"])
            # A plugin's marketplace is added once per client; its own step has no "@".
            if candidate["kind"] == "plugin" and "@" not in step.name:
                if (step.client, step.name) in marketplaces:
                    continue
                marketplaces.add((step.client, step.name))
            steps.append(step)
    listing = {"candidates": candidates, "not_same": _not_same(views), "left_out": left_out}
    if not steps:
        if not candidates:
            raise ValueError(f"Nothing is missing in {Path(project).name}.")
        raise ValueError("Choose at least one item.")
    return steps, listing
