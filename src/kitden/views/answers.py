"""The read-only answers about a setup: the MCP server's tools and `kitden show` both give them.

Each answer is the same redacted model and the same project view as the page (FR-030, FR-031).
"""

import os
from pathlib import Path
from typing import Any

from kitden.gateways import load_gateways
from kitden.local_gateway.settings import load_settings
from kitden.local_gateway.views import gateway_items
from kitden.model import Project
from kitden.views.context_view import context_view
from kitden.views.effective import found_clients, project_views
from kitden.views.explain import brief, explain
from kitden.views.findings import find_bypasses, find_findings, finding_dict, mark_gateways
from kitden.views.inventory import Inventory, build_inventory

NO_EDITS = (
    "Do not edit client settings files to work around this; tell the developer to make the "
    "change on the local page (run `kitden open`), which previews, backs up and can undo it."
)
NO_CHANGES = "Read-only: this tool cannot change settings. " + NO_EDITS


def read_setup(home: Path) -> Inventory:
    """A fresh read, built as the page builds it, so the answers agree with the page."""
    inventory = build_inventory(home)
    mark_gateways(inventory, load_gateways(home))
    inventory.items += gateway_items(inventory, load_settings(home), home)
    return inventory


def _project_dict(project: Project | None) -> dict[str, Any] | None:
    if project is None:
        return None
    return {"path": project.path, "exists": project.exists, "known_by": list(project.known_by)}


def resolve_project(inventory: Inventory, path: str) -> Project | None:
    """The known project that is `path` or contains it; the deepest one wins."""
    real = os.path.realpath(path)
    found = [
        p
        for p in inventory.projects
        if real == os.path.realpath(p.path)
        or real.startswith(os.path.realpath(p.path).rstrip("/") + "/")
    ]
    return max(found, key=lambda p: len(p.path)) if found else None


def _where(inventory: Inventory, folder: str) -> tuple[Project | None, str | None]:
    project = resolve_project(inventory, folder)
    return project, project.path if project else None


def setup_answer(inventory: Inventory, folder: str, client: str | None = None) -> dict[str, Any]:
    """What each client loads for the project around `folder`; one client when asked."""
    project, path = _where(inventory, folder)
    if client is not None and client not in found_clients(inventory):
        raise ValueError(f"Unknown or missing client: {client}")
    views = [
        {
            "client": view.client,
            "items": [brief(i) for i in view.items],
            "overridden": [
                {"name": w.name, "winner": w.id, "loser": lo.id, "mode": mode}
                for w, lo, mode in view.shadowed
            ],
        }
        for view in project_views(inventory, path)
        if client is None or view.client == client
    ]
    return {"project": _project_dict(project), "views": views, "note": NO_CHANGES}


def findings_answer(inventory: Inventory, folder: str) -> dict[str, Any]:
    project, path = _where(inventory, folder)
    found = find_findings(inventory, path) + find_bypasses(inventory, path)
    return {"project": _project_dict(project), "findings": [finding_dict(f) for f in found]}


def item_answer(
    inventory: Inventory, folder: str, name: str, kind: str | None = None
) -> dict[str, Any]:
    project, path = _where(inventory, folder)
    # An agent's answer leaves this computer: a file's first lines stay on the local page.
    definitions = [{**d, "preview": None} for d in explain(inventory, name, kind, path)]
    return {"project": _project_dict(project), "name": name, "definitions": definitions}


def projects_answer(inventory: Inventory) -> dict[str, Any]:
    return {"projects": [_project_dict(p) for p in inventory.projects]}


def context_answer(inventory: Inventory, home: Path, folder: str) -> dict[str, Any]:
    """The Context page's cards: whether each client's skill list fit, in written sentences."""
    project, path = _where(inventory, folder)
    codex_home = Path(os.environ.get("CODEX_HOME") or home / ".codex")
    clients = context_view(inventory, home, codex_home, path, {})["clients"]
    return {"project": _project_dict(project), "clients": clients}
