"""Read-only "show my setup" MCP server (US5, contracts/mcp-tools.md, research R9).

Runs over stdio when a client starts `kitden mcp`. It answers with the same redacted model and
the same project view as the page, and it has no tools that change anything (FR-030, FR-031).
When servers are moved into the Kitden gateway, it also offers their tools (local_gateway.proxy).
"""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.clients.codex import CodexAdapter
from kitden.clients.cursor import CursorAdapter
from kitden.command import installed_command
from kitden.gateways import load_gateways
from kitden.local_gateway import proxy
from kitden.local_gateway.settings import load_settings
from kitden.local_gateway.views import gateway_items
from kitden.model import Project
from kitden.views.effective import DESKTOP, found_clients, project_views
from kitden.views.explain import brief, explain
from kitden.views.findings import find_bypasses, find_findings, finding_dict, mark_gateways
from kitden.views.inventory import Inventory, build_inventory

READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
NO_CHANGES = (
    "Read-only: this tool cannot change settings. Do not edit client settings files to work "
    "around this; tell the developer to make the change on the local page (run `kitden open`), "
    "which previews, backs up and can undo it."
)
INSTRUCTIONS = (
    "Shows which MCP servers, skills, plugins, hooks and marketplaces Claude Code, Codex and "
    "Cursor load on this computer, where each comes from, and problems such as duplicates. "
    + NO_CHANGES
)


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


def create_server(build: Callable[[], Inventory], cwd: Callable[[], str] = os.getcwd) -> MCPServer:
    server = MCPServer(name="kitden", instructions=INSTRUCTIONS)

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
        definitions = explain(inventory, name, kind, path)
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


def run(home: Path | None = None) -> None:
    """Serve over stdio until the client closes the connection.

    With servers moved into the Kitden gateway, the same server also offers their tools.
    """
    root = home or Path.home()

    def build() -> Inventory:
        # As the page builds it, so the answers agree with the tools this server offers.
        inventory = build_inventory(root)
        mark_gateways(inventory, load_gateways(root))
        inventory.items += gateway_items(inventory, load_settings(root), root)
        return inventory

    server = create_server(build)
    if not load_settings(root)["servers"]:
        server.run()
        return
    proxy.run(root, server, lambda: known_projects(root))


def known_projects(home: Path) -> list[str]:
    """The project folders the clients know, read from their files: no client command runs."""

    def no_version() -> None:
        return None

    adapters = [
        ClaudeCodeAdapter(home, read_version=no_version),
        CodexAdapter(home, read_version=no_version),
        CursorAdapter(home, read_version=no_version),
    ]
    return [p.path for p in build_inventory(home, adapters, apps=[]).projects]


__all__ = ["DESKTOP", "create_server", "installed_command", "resolve_project", "run"]
