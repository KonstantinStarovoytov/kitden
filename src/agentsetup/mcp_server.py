"""Read-only "show my setup" MCP server (US5, contracts/mcp-tools.md, research R9).

Runs over stdio when a client starts `agentsetup mcp`. It answers with the same redacted model and
the same project view as the page, and it has no tools that change anything (FR-030, FR-031).
"""

import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from agentsetup.gateways import load_gateways
from agentsetup.model import Enabled, Item, Project
from agentsetup.views.effective import DESKTOP, effective_view, found_clients, project_views
from agentsetup.views.findings import find_bypasses, find_findings, finding_dict, mark_gateways
from agentsetup.views.inventory import Inventory, build_inventory

READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
NO_CHANGES = (
    "Read-only: this tool cannot change settings. Do not edit client settings files to work "
    "around this; tell the developer to make the change on the local page (run `agentsetup`), "
    "which previews, backs up and can undo it."
)
INSTRUCTIONS = (
    "Shows which MCP servers, skills, plugins, hooks and marketplaces Claude Code, Codex and "
    "Cursor load on this computer, where each comes from, and problems such as duplicates. "
    + NO_CHANGES
)


def _brief(item: Item) -> dict[str, Any]:
    """An item as the agent sees it: the page's redacted fields, without the raw summary."""
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
    }


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


def _why(item: Item, view, loaded: set[str]) -> str:
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


def create_server(build: Callable[[], Inventory], cwd: Callable[[], str] = os.getcwd) -> MCPServer:
    server = MCPServer(name="agentsetup", instructions=INSTRUCTIONS)

    def project_for(inventory: Inventory, project_path: str | None) -> Project | None:
        return resolve_project(inventory, project_path or cwd())

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "Show what each AI coding client loads for a project: MCP servers, skills, plugins, "
            "hooks and marketplaces, with source, scope and on/off state. project_path defaults "
            "to the current folder; client (claude_code, claude_desktop_code_tab, codex, cursor) "
            "defaults to all. " + NO_CHANGES
        ),
    )
    def show_setup(project_path: str | None = None, client: str | None = None) -> dict[str, Any]:
        inventory = build()
        project = project_for(inventory, project_path)
        path = project.path if project else None
        if client is not None and client not in found_clients(inventory):
            raise ValueError(f"Unknown or missing client: {client}")
        views = [
            {
                "client": view.client,
                "items": [_brief(i) for i in view.items],
                "overridden": [
                    {"name": w.name, "winner": w.id, "loser": lo.id, "mode": mode}
                    for w, lo, mode in view.shadowed
                ],
            }
            for view in project_views(inventory, path)
            if client is None or view.client == client
        ]
        return {"project": _project_dict(project), "views": views, "note": NO_CHANGES}

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "List problems for a project: duplicates, items loaded from another client's folder, "
            "overrides, unknown states, untested versions, and MCP servers that bypass the "
            "gateway. project_path defaults to the current folder. " + NO_CHANGES
        ),
    )
    def list_findings(project_path: str | None = None) -> dict[str, Any]:
        inventory = build()
        project = project_for(inventory, project_path)
        path = project.path if project else None
        found = find_findings(inventory, path) + find_bypasses(inventory, path)
        return {"project": _project_dict(project), "findings": [finding_dict(f) for f in found]}

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "Explain one name: every definition across clients and scopes, which one loads in "
            "the project, and why. kind is optional (mcp_server, skill, plugin, hook, "
            "marketplace). " + NO_CHANGES
        ),
    )
    def explain_item(
        name: str, kind: str | None = None, project_path: str | None = None
    ) -> dict[str, Any]:
        inventory = build()
        project = project_for(inventory, project_path)
        path = project.path if project else None
        definitions = []
        views = {}
        for item in inventory.items:
            if item.name != name or (kind is not None and str(item.kind) != kind):
                continue
            if item.client not in views:
                views[item.client] = effective_view(inventory, item.client, path)
            view = views[item.client]
            loaded = {i.id for i in view.items}
            definitions.append(
                {**_brief(item), "loads": item.id in loaded, "why": _why(item, view, loaded)}
            )
        return {"project": _project_dict(project), "name": name, "definitions": definitions}

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "List the projects the clients know, which clients know each one, and whether the "
            "folder still exists. " + NO_CHANGES
        ),
    )
    def list_projects() -> dict[str, Any]:
        return {"projects": [_project_dict(p) for p in build().projects]}

    return server


def installed_command() -> str | None:
    """Absolute path of the `agentsetup` command, for client configs (research R9)."""
    beside_python = Path(sys.executable).parent / "agentsetup"
    if beside_python.is_file():
        return str(beside_python)
    found = shutil.which("agentsetup")
    return str(Path(found).absolute()) if found else None


def run(home: Path | None = None) -> None:
    """Serve over stdio until the client closes the connection."""
    root = home or Path.home()

    def build() -> Inventory:
        inventory = build_inventory(root)
        mark_gateways(inventory, load_gateways(root))
        return inventory

    create_server(build).run()


__all__ = ["DESKTOP", "create_server", "installed_command", "resolve_project", "run"]
