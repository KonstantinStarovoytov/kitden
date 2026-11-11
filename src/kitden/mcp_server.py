"""Read-only "show my setup" MCP server (US5, contracts/mcp-tools.md, research R9).

Runs over stdio when a client starts `kitden mcp`. It answers with the same redacted model and
the same project view as the page, and it has no tools that change anything (FR-030, FR-031).
When servers are moved into the Kitden gateway, it also offers their tools (local_gateway.proxy).
"""

import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from mcp.server import Server
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations
from pydantic import Field

from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.clients.codex import CodexAdapter
from kitden.clients.cursor import CursorAdapter
from kitden.local_gateway import proxy, resume
from kitden.local_gateway.settings import load_settings
from kitden.update import install
from kitden.views import answers
from kitden.views.answers import NO_CHANGES, NO_EDITS, read_setup, resolve_project
from kitden.views.inventory import Inventory, build_inventory

READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
# The same words for project_path on every tool that takes one (Glama's TDQS asked, 2026-11-09).
ProjectPath = Annotated[
    str | None,
    Field(
        description=(
            "A folder, absolute or relative to the current folder; the current folder by "
            "default. The project is the known project that is or contains the folder. Outside "
            "any known project the answer shows the user-level setup."
        )
    ),
]
ABOUT = (
    "Shows which MCP servers, skills, plugins, hooks, marketplaces and instruction files "
    "(CLAUDE.md, AGENTS.md, rules, commands, agents) Claude Code, Codex and Cursor have on this "
    "computer, where each comes from, and problems such as duplicates. "
)
INSTRUCTIONS = ABOUT + NO_CHANGES
# With servers in the Kitden gateway, the same server also offers their tools.
GATEWAY_INSTRUCTIONS = (
    ABOUT
    + "Kitden's own tools (show_setup, list_findings, explain_item, list_projects) only read: "
    "they cannot change settings. "
    + NO_EDITS
    + " The other tools come from MCP servers moved into the Kitden gateway and do what those "
    "servers do."
)


def create_server(
    build: Callable[[], Inventory],
    cwd: Callable[[], str] = os.getcwd,
    instructions: str = INSTRUCTIONS,
) -> MCPServer:
    server = MCPServer(name="kitden", instructions=instructions)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "Show what each AI coding client loads for a project: MCP servers, skills, plugins, "
            "hooks, marketplaces and instruction files, with source, scope and on/off state. "
            "Start here for the full picture; use list_findings for problems only and "
            "explain_item for one name. client (claude_code, claude_desktop_code_tab, codex, "
            "cursor) defaults to all. " + NO_CHANGES
        ),
    )
    def show_setup(project_path: ProjectPath = None, client: str | None = None) -> dict[str, Any]:
        return answers.setup_answer(build(), project_path or cwd(), client)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "List problems for a project: duplicates, items loaded from another client's folder, "
            "the same name from another source, overrides, unknown states, untested versions, "
            "and MCP servers that bypass the gateway. Each names its clients. Use it to check a "
            "setup for problems; show_setup lists everything that loads, and explain_item follows "
            "one name. " + NO_CHANGES
        ),
    )
    def list_findings(project_path: ProjectPath = None) -> dict[str, Any]:
        return answers.findings_answer(build(), project_path or cwd())

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "Explain one name: every definition across clients and scopes, which one loads in "
            "the project, and why. Use it after show_setup or list_findings names an item; "
            "show_setup lists everything. kind is optional (mcp_server, skill, plugin, hook, "
            "marketplace, instructions). " + NO_CHANGES
        ),
    )
    def explain_item(
        name: str, kind: str | None = None, project_path: ProjectPath = None
    ) -> dict[str, Any]:
        return answers.item_answer(build(), project_path or cwd(), name, kind)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "List the projects the clients know, which clients know each one, and whether the "
            "folder still exists. Use it to find a project_path for show_setup, list_findings "
            "and explain_item. " + NO_CHANGES
        ),
    )
    def list_projects() -> dict[str, Any]:
        return answers.projects_answer(build())

    return server


def run(home: Path | None = None, read_only: bool = False) -> None:
    """Serve over stdio until the client closes the connection.

    With servers moved into the Kitden gateway, the same server also offers their tools. With
    `read_only` it offers only its own tools: the kitden plugin starts it so. After an update
    from the page it moves to the new version in the same process (local_gateway.resume).
    """
    root = home or Path.home()
    held = {} if read_only else load_settings(root)["servers"]

    def make() -> MCPServer:
        return create_server(
            lambda: read_setup(root), instructions=GATEWAY_INSTRUCTIONS if held else INSTRUCTIONS
        )

    # Only a uv tool or Homebrew install is updated in place, so only such a gateway watches
    # for updates. One that an update started again goes on with the agent's session.
    watch = install.detect() is not None
    if watch or resume.RESUME in os.environ:

        def make_low_level() -> Server:
            if held:
                return proxy.gateway_server(root, make(), lambda: known_projects(root))
            # MCPServer.run() serves this low-level server (mcp 2.3.0, checked 2026-11-11).
            return make()._lowlevel_server

        resume.serve_stdio(make_low_level, root, sys.argv[1:], watch)
        return
    server = make()
    if not held:
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


__all__ = ["NO_CHANGES", "NO_EDITS", "create_server", "resolve_project", "run"]
