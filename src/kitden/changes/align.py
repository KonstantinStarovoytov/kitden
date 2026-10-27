"""Add what one client loads in a project and another client lacks, in one review (spec 3.5).
Under All projects: the plugins and skills one client has for all projects and another lacks.

Each add is built by the same step builders as a single add from the Library.
"""

from pathlib import Path

from kitden.changes.actions import (
    CLIENT_WORDS,
    add_server_steps,
    folder_readers,
    install_steps,
)
from kitden.clients.base import SETUP_NAME, ClientAdapter, is_direct_entry
from kitden.model import Item, ItemKind, Scope, Step
from kitden.views.catalog import catalog
from kitden.views.effective import effective_view
from kitden.views.findings import base_name
from kitden.views.match import Copies, is_compared, odd_sources, plugin_copies
from kitden.views.skills import read_skill, skill_catalog

CLIENTS = ("claude_code", "codex", "cursor")
KINDS = (ItemKind.MCP_SERVER, ItemKind.PLUGIN, ItemKind.SKILL)
# Under All projects MCP servers are left to the Gateway.
ALL_KINDS = (ItemKind.PLUGIN, ItemKind.SKILL)
NO_OFFER = "not in a marketplace on this computer"
# Cursor loads Claude Code's user plugins (Include Third-Party Plugins and the import on), so it
# has no plugin of its own to get; Add missing puts a Claude Code plugin into the project.
CURSOR_VIA = "Cursor loads Claude Code's plugins only when they are for all projects"


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


def _skipped(kind: ItemKind, client: str, project: str | None) -> bool:
    """Under All projects Cursor neither gives nor gets a plugin: it adds plugins only in its own
    window (D26)."""
    return project is None and kind is ItemKind.PLUGIN and client == "cursor"


def _place(item: Item, client: str, adapters: dict[str, ClientAdapter], project: str | None) -> str:
    """Where the add goes: "project" when the client can load it from the project, else "all".
    An MCP entry and a Codex plugin are for all projects; Codex reads a project's skills only
    when it trusts the project. Under All projects (`project` None) every add is for all."""
    if project is None or item.kind is ItemKind.MCP_SERVER:
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
    project: str | None,
    imports: bool,
) -> list[Step]:
    """The steps of one add, as the single add makes them. Raises ValueError with the reason
    when the client cannot get it. `imports`: Cursor loads Claude Code's plugins."""
    into = project if place == "project" else None
    if item.kind is ItemKind.MCP_SERVER:
        return add_server_steps(adapters, item, [client])
    if item.kind is ItemKind.PLUGIN:
        offer = offers.get(item.name)
        if offer is None:
            raise ValueError(NO_OFFER)
        if client == "cursor" and imports:
            raise ValueError(CURSOR_VIA)
        if client not in offer["routes"]:
            raise ValueError(f"{CLIENT_WORDS[client]} cannot get it")
        return install_steps(adapters, offer, [client], into)
    folder = Path(item.source.path or "").parent
    if not read_skill(folder)["self_contained"]:
        raise ValueError("needs the rest of its plugin")
    readers = folder_readers(client, adapters, found)
    return [adapters[client].skill_copy_step(folder, readers, into)]


def _words(clients: list[str]) -> str:
    names = [CLIENT_WORDS[c] for c in clients]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _not_same(views: dict[str, list[Item]], copies: Copies) -> list[dict]:
    """Names a client loads from another source than the others (match.py): a plugin from
    another marketplace, a skill with other files, an MCP server with another command or
    address. A copy with the same files is the same skill."""
    sources: dict[tuple, dict[str, list[Item]]] = {}
    for client, items in views.items():
        for item in items:
            if is_compared(item):
                key = (item.kind, base_name(item))
                sources.setdefault(key, {}).setdefault(client, []).append(item)
    out = []
    for (kind, name), by_client in sources.items():
        if odd_sources(by_client, copies):
            clients = [c for c in CLIENTS if c in by_client]
            out.append({"kind": kind.value, "name": name, "clients": clients})
    return sorted(out, key=lambda n: (KINDS.index(ItemKind(n["kind"])), n["name"]))


def align_steps(
    inventory,
    adapters: dict[str, ClientAdapter],
    project: str | None,
    found: set[str],
    chosen: list[str] | None,
) -> tuple[list[Step], dict]:
    """Every plugin, skill and MCP server one found client loads in `project` and another
    lacks, as candidates; the steps add the chosen ones. With `project` None (All projects):
    the plugins and skills one client has for all projects and another lacks, each added for
    all projects. Names match exactly. A client that has an item turned off keeps it off: it is
    not offered. With `chosen` None, an add that makes a duplicate (a name in another case,
    here or earlier in the list, or a skill a reader already has) is unchecked."""
    kinds = KINDS if project else ALL_KINDS
    clients = [c for c in CLIENTS if c in found and c in adapters]
    views = {
        c: [i for i in effective_view(inventory, c, project).items if i.kind in kinds]
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
    cursor = adapters.get("cursor")
    imports = "cursor" in clients and cursor is not None and cursor.imports_claude_plugins()

    candidates: list[dict] = []
    built: list[list[Step]] = []
    left_out: list[dict] = []
    seen: set[tuple] = set()
    firsts: dict[tuple, str] = {}  # (kind, client, name in lower case) -> the first name added
    for source in clients:
        for kind in kinds:
            if _skipped(kind, source, project):
                continue
            items = sorted(
                (i for i in views[source] if i.kind is kind and _is_source(i, source)),
                key=lambda i: i.name,
            )
            for item in items:
                for client in clients:
                    key = (kind, base_name(item), client)
                    if client == source or key in seen or key[:2] in has[client]:
                        continue
                    if _skipped(kind, client, project):  # Cursor gets no plugin here
                        continue
                    seen.add(key)
                    place = _place(item, client, adapters, project)
                    try:
                        steps = _build(
                            item, client, place, adapters, offers, found, project, imports
                        )
                    except ValueError as error:
                        why = {"name": item.name, "why": str(error)}
                        if why not in left_out:
                            left_out.append(why)
                        continue
                    name = f"{kind.value}:{item.name}:{client}"
                    # Names match exactly; one that differs only in case is said, not merged.
                    alike = sorted(
                        n
                        for k, n in has[client]
                        if k is kind and n != key[1] and n.lower() == key[1].lower()
                    )
                    # A skill copy reaches every client that reads its folder (folder_readers);
                    # one that already has the skill would load it twice.
                    readers = [r for s in steps if s.copy is not None for r in s.copy.readers]
                    twice = [r for r in readers if r != client and key[:2] in has[r]]
                    notes = []
                    if alike:
                        who = CLIENT_WORDS[client]
                        notes.append(f"{who} already has {alike[0]}; this adds {key[1]} beside it.")
                    # Two adds for one client whose names differ only in case: the first stays.
                    first = firsts.setdefault((kind, client, key[1].lower()), key[1])
                    if first != key[1] and not alike:
                        notes.append(f"This list also adds {first}; this adds {key[1]} beside it.")
                    if twice:
                        notes.append(f"{_words(twice)} would load it twice.")
                    # Such an add makes a duplicate: it starts unchecked.
                    default = not notes
                    candidates.append(
                        {
                            "key": name,
                            "kind": kind.value,
                            "name": item.name,
                            "from": source,
                            "to": client,
                            "place": place,
                            "note": " ".join(notes) or None,
                            "chosen": default if chosen is None else name in chosen,
                        }
                    )
                    built.append(steps)

    steps: list[Step] = []
    marketplaces: set[tuple] = set()
    # A skill -> the clients a copy made here reaches, and that copy's place.
    reached: dict[str, tuple[list[str], str]] = {}
    for candidate, add in zip(candidates, built, strict=True):
        if not candidate["chosen"]:
            continue
        readers, place = reached.get(candidate["name"], ([], ""))
        if candidate["kind"] == "skill" and candidate["to"] in readers:
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
    not_same = _not_same(views, plugin_copies(inventory))
    listing = {"candidates": candidates, "not_same": not_same, "left_out": left_out}
    if not candidates:
        where = f" in {Path(project).name}" if project else ""
        raise ValueError(f"Nothing is missing{where}.")
    # The first review may check nothing (every add makes a duplicate); it still lists them.
    if not steps and chosen is not None:
        raise ValueError("Choose at least one item.")
    return steps, listing
