"""Every definition of one name, which one loads, and why (page side panel and MCP server)."""

import json
from pathlib import Path
from typing import Any

from kitden.changes.actions import KITDEN_GATEWAY
from kitden.local_gateway.views import tool_count
from kitden.model import Enabled, Item, ItemKind
from kitden.redact import redact_lines
from kitden.views.affects import affects
from kitden.views.effective import effective_view, in_project
from kitden.views.findings import base_name
from kitden.views.load_map import category as category_of


def summary_line(item: Item) -> str:
    """What an MCP server is, in one line: its address, or its command with the arguments.

    The summary is already redacted (FR-006), so secrets never reach this line.
    """
    summary = dict(item.summary)
    if summary.get("url"):
        return summary["url"]
    try:
        args = json.loads(summary.get("args", "[]"))
    except ValueError:
        args = [summary.get("args", "")]
    parts = [summary.get("command", ""), *(args if isinstance(args, list) else [str(args)])]
    return " ".join(str(p) for p in parts if p)


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
        "summary": summary_line(item) or None,
        "category": category_of(item),
    }


# Details shows this many first lines of an instruction file, each cut at this many characters.
PREVIEW_LINES = 12
PREVIEW_WIDTH = 200
PREVIEW_READ = 64_000


def preview(item: Item) -> list[str] | None:
    """The first lines of an instruction file, secrets hidden; None when it cannot be read."""
    if item.kind is not ItemKind.INSTRUCTIONS or not item.source.path:
        return None
    try:
        with Path(item.source.path).open(encoding="utf-8-sig", errors="replace") as file:
            text = file.read(PREVIEW_READ)  # a file with no line breaks is not read whole
    except OSError:
        return None
    return head(text, cut=len(text) == PREVIEW_READ)


def head(text: str, cut: bool = False) -> list[str]:
    """The first lines of a file's text, secrets hidden. With `cut` the read stopped inside the
    text, so a last line without its end is left out."""
    lines = text.splitlines()
    if cut and not text.endswith(("\n", "\r")):
        lines = lines[:-1]  # the read stopped inside this line
    # Hide secrets before cutting, so a cut never leaves part of a secret behind.
    return [line[:PREVIEW_WIDTH] for line in redact_lines(lines[:PREVIEW_LINES])]


def reads(item: Item, items: list[Item]) -> str:
    """When the client reads an instruction file, where its docs say so; else what it is.

    checked 2026-10-22 (code.claude.com/docs/en/memory): CLAUDE.md files and rules without
    `paths` load at launch; a rule with `paths` loads when Claude works with matching files.
    checked 2026-10-22 (learn.chatgpt.com/docs/agent-configuration/agents-md): Codex reads
    AGENTS.override.md instead of AGENTS.md in the same folder.
    checked 2026-10-22 (cursor.com/docs/context/rules): a rule applies always, by its
    description, for matching files, or when you @-mention it; AGENTS.md in the project root.
    checked 2026-10-22 (cursor.com/help/customization/rules): `.cursorrules` is legacy.
    """
    kind = category_of(item)
    path = item.source.path or ""
    if kind == "command":
        return f"A command: it runs when you type /{item.name}."
    if kind == "agent":
        return "An agent: it runs when a task calls for it or you ask for it."
    if item.client == "codex":
        override = any(
            i.client == "codex"
            and i.name == "AGENTS.override.md"
            and i.source.path == path.replace("AGENTS.md", "AGENTS.override.md")
            for i in items
        )
        if item.name == "AGENTS.md" and override:
            return "Codex reads AGENTS.override.md in this folder instead."
        return "Codex reads it when a session starts."
    if item.client == "cursor":
        if path.endswith(".mdc"):
            return (
                "Cursor uses it by its rule type: always, when it fits, for some files, "
                "or when you mention it."
            )
        if item.name == ".cursorrules":
            return "An older rules file. Cursor plans to stop reading it."
        return "Cursor reads it in each chat in this project."
    if "/.claude/rules/" in path:
        return "Read when a session starts. A rule that names paths is read only for those files."
    return "Read when a session starts."


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


def explain(
    inventory,
    name: str,
    kind: str | None,
    project: str | None,
    category: str | None = None,
    tools: dict | None = None,
) -> list[dict]:
    """Every definition of `name` (plugins also by base name), with how it loads and why.
    `category` narrows instruction files to one (a command and an agent may share a name).
    `tools` is the Kitden gateway's tool cache: a server in that gateway says how many tools
    it knows. A direct server gets no count, since another server may have the same name."""
    definitions = []
    views: dict[str, Any] = {}
    for item in inventory.items:
        if not _matches(item, name) or (kind is not None and str(item.kind) != kind):
            continue
        if category is not None and category_of(item) != category:
            continue
        if item.project is not None and project is not None and item.project != project:
            continue
        item = in_project(item, project)  # a user skill as this project's settings leave it
        if item.client not in views:
            views[item.client] = effective_view(inventory, item.client, project)
        view = views[item.client]
        loaded = {i.id for i in view.items}
        beaten = {lo.id: mode for _, lo, mode in view.shadowed}
        definitions.append(
            {
                **brief(item),
                "loads": item.id in loaded,
                "overridden": beaten.get(item.id) == "override",
                "merged": beaten.get(item.id) == "merged",
                # Kept from the last good read of a file that now fails: Details says when.
                "stale_at": item.stale_at,
                # With no project picked, only global files show their first lines; a project's
                # files show theirs when that project is picked.
                "preview": preview(item) if item.project is None or project else None,
                "tools": (
                    tool_count(tools, item.name) if item.via_gateway == KITDEN_GATEWAY else None
                ),
                "why": (
                    reads(item, inventory.items)
                    if item.kind is ItemKind.INSTRUCTIONS
                    else why(item, view, loaded)
                ),
            }
        )
    return definitions


def with_page_fields(definitions: list[dict], inventory) -> list[dict]:
    """explain()'s definitions with what only the local page shows: each one's file key, and for
    one Kitden can change, which clients and projects that change reaches (`affects`). The MCP
    server sends explain() as it is."""
    items = {i.id: i for i in inventory.items}
    out = []
    for definition in definitions:
        item = items.get(definition["id"])
        extra: dict[str, Any] = {"key": item.source.key_path if item else None}
        if item and definition["actions"]:
            extra["affects"] = affects(inventory, item)
        out.append({**definition, **extra})
    return out
