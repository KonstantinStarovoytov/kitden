"""Every definition of one name, which one loads, and why (page side panel and MCP server)."""

from typing import Any

from agentsetup.model import Enabled, Item, ItemKind
from agentsetup.views.effective import effective_view
from agentsetup.views.findings import base_name


def brief(item: Item) -> dict[str, Any]:
    """An item as shown outside the inventory: redacted fields, without the raw summary."""
    return {
        "id": item.id,
        "client": item.client,
        "kind": str(item.kind),
        "name": item.name,
        "scope": str(item.scope),
        "project": item.project,
        "enabled": str(item.enabled),
        "source": item.source.path or str(item.source.kind),
        "owner_client": item.source.owner_client,
        "unknown_reason": str(item.source.unknown_reason) if item.source.unknown_reason else None,
        "via_gateway": item.via_gateway,
        "change_hint": item.change_hint,
        "secret_present": item.secret_present,
        "actions": list(item.actions),
    }


def why(item: Item, view, loaded: set[str]) -> str:
    beaten = {lo.id: (w, mode) for w, lo, mode in view.shadowed}
    beats = [lo for w, lo, _ in view.shadowed if w.id == item.id]
    if item.id in loaded:
        if beats:
            scopes = ", ".join(sorted({str(lo.scope) for lo in beats}))
            return f"Loads. It overrides the {scopes} definition."
        return "Loads."
    if item.id in beaten:
        winner, mode = beaten[item.id]
        if mode == "merged":
            return f"Merged with the {winner.scope} definition; its fields win."
        return f"Does not load: the {winner.scope} definition overrides it."
    if item.enabled is Enabled.OFF:
        return "Does not load: it is turned off."
    if item.project and item.project != view.project:
        return "Does not load here: it belongs to another project."
    return "Does not load here: its plugin is not loaded."


def _matches(item: Item, name: str) -> bool:
    return item.name == name or (item.kind is ItemKind.PLUGIN and base_name(item) == name)


def explain(inventory, name: str, kind: str | None, project: str | None) -> list[dict]:
    """All definitions of `name` (plugins also by base name) with `loads` and `why`."""
    definitions = []
    views: dict[str, Any] = {}
    for item in inventory.items:
        if not _matches(item, name) or (kind is not None and str(item.kind) != kind):
            continue
        if item.project is not None and project is not None and item.project != project:
            continue
        if item.client not in views:
            views[item.client] = effective_view(inventory, item.client, project)
        view = views[item.client]
        loaded = {i.id for i in view.items}
        definitions.append(
            {**brief(item), "loads": item.id in loaded, "why": why(item, view, loaded)}
        )
    return definitions
