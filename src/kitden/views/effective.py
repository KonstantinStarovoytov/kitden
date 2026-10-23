"""What each client actually loads in one project (FR-010, FR-014). Research R3.

For every client and kind, a rank table says which scope wins when the same name is defined
more than once. The winner is kept; the others are recorded as shadowed. Items that are off do
not load, and parts of a Claude Code plugin load only when that plugin loads.
"""

from dataclasses import dataclass, field

from kitden.model import Enabled, Item, ItemKind, Scope
from kitden.views.match import plugin_of

DESKTOP = "claude_desktop_code_tab"
DESKTOP_RANK = 99  # claude_desktop_config.json wins on a name clash

# Higher number wins. Kinds without a table never shadow each other (for example hooks, which
# all run, and Codex or Cursor skills, which all load).
RANKS: dict[str, dict[ItemKind, dict[Scope, int]]] = {
    "claude_code": {
        ItemKind.MCP_SERVER: {
            Scope.ACCOUNT: 0,
            Scope.PLUGIN: 1,
            Scope.USER: 2,
            Scope.PROJECT: 3,
            Scope.LOCAL: 4,
            Scope.MANAGED: 5,
        },
        ItemKind.PLUGIN: {
            Scope.ACCOUNT: 0,
            Scope.USER: 1,
            Scope.PROJECT: 2,
            Scope.LOCAL: 3,
            Scope.MANAGED: 4,
        },
        ItemKind.SKILL: {Scope.PROJECT: 1, Scope.USER: 2, Scope.MANAGED: 3},
    },
    "codex": {ItemKind.MCP_SERVER: {Scope.USER: 1, Scope.PROJECT: 2}},
    "cursor": {
        ItemKind.MCP_SERVER: {Scope.USER: 1, Scope.PROJECT: 2},
        ItemKind.PLUGIN: {Scope.USER: 1, Scope.PROJECT: 2},
    },
}
# Codex merges MCP fields across layers instead of replacing the whole entry.
MERGED = {("codex", ItemKind.MCP_SERVER)}


@dataclass
class EffectiveView:
    client: str
    project: str | None
    items: list[Item] = field(default_factory=list)
    shadowed: list[tuple[Item, Item, str]] = field(default_factory=list)


def _ranked(item: Item, base: str) -> int | None:
    if item.client == DESKTOP:
        return DESKTOP_RANK
    if item.kind is ItemKind.SKILL and item.scope is Scope.PLUGIN:
        return None  # plugin skills are namespaced by their plugin
    return RANKS.get(base, {}).get(item.kind, {}).get(item.scope)


def effective_view(inventory, client: str, project: str | None) -> EffectiveView:
    base = "claude_code" if client == DESKTOP else client
    clients = {base, DESKTOP} if client == DESKTOP else {base}
    candidates = [
        i
        for i in inventory.items
        if i.client in clients and (i.project is None or i.project == project)
    ]

    view = EffectiveView(client=client, project=project)
    winners: dict[tuple[ItemKind, str], Item] = {}
    for item in candidates:
        rank = _ranked(item, base)
        if rank is None:
            continue
        key = (item.kind, item.name)
        current = winners.get(key)
        if current is None or rank > _ranked(current, base):
            winners[key] = item
    for item in candidates:
        winner = winners.get((item.kind, item.name))
        if winner is not None and winner is not item and _ranked(item, base) is not None:
            mode = "merged" if (base, item.kind) in MERGED else "override"
            view.shadowed.append((winner, item, mode))

    kept = [
        i
        for i in candidates
        if (_ranked(i, base) is None or winners[(i.kind, i.name)] is i)
        and i.enabled is not Enabled.OFF
    ]
    loaded_plugins = {i.name for i in kept if i.kind is ItemKind.PLUGIN}
    view.items = [
        i
        for i in kept
        if not (
            base == "claude_code"
            and i.scope is Scope.PLUGIN
            and i.kind is not ItemKind.PLUGIN
            and plugin_of(i) not in loaded_plugins
        )
    ]
    return view


def found_clients(inventory) -> list[str]:
    return [c.id for c in inventory.clients if str(c.status) == "found"]


def project_views(inventory, project: str | None) -> list[EffectiveView]:
    """What each found client loads in one project. The page and the MCP server both use this."""
    return [effective_view(inventory, client, project) for client in found_clients(inventory)]
