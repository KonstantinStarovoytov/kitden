"""The Instructions map: clients, the instruction files they read, and the files those import
(spec Part 6.1).

Files are grouped "All projects" and, with a project picked, "Only this project · <folder>": one
block per file, with the clients that read it. A Cursor rules folder is one block. Only Claude
Code's CLAUDE.md files have imports. Commands and agents are not instruction files here. Kitden
only reads these files; paths are only under `technical`, and imports reach the page only, never
the MCP server.
"""

import os
from pathlib import Path

from kitden.clients.base import is_home
from kitden.model import ClientStatus, ItemKind, _hash
from kitden.redact import redact_line
from kitden.views.explain import PREVIEW_READ, head
from kitden.views.imports import imports, read_text
from kitden.views.library_map import _clients
from kitden.views.load_map import COLUMNS, category

ALL = {"key": "all", "name": "All projects"}
PROJECT = "Only this project · {}"
CURSOR_RULES = ".cursor/rules"
# Claude Code's files whose imports are read: CLAUDE.md, CLAUDE.local.md and .claude/CLAUDE.md.
CLAUDE_FILES = ("CLAUDE.md", "CLAUDE.local.md")
# checked 2026-10-26 (code.claude.com/docs/en/memory, "AGENTS.md"): by default Claude Code
# v2.1.277 and later reads AGENTS.md in place of CLAUDE.md when there is no CLAUDE.md,
# .claude/CLAUDE.md or CLAUDE.local.md in the working folder or a folder above it;
# ~/.claude/CLAUDE.md does not count. It reads AGENTS.md itself, not through an import.
# Not read here: the "Project instructions" setting that can change this, `.claude/AGENTS.md`,
# AGENTS.md in folders above, and the imports inside an AGENTS.md: spec 6.1 reads imports from
# Claude Code's CLAUDE.md files only.
AGENTS_SINCE = (2, 1, 277)
THROUGH_AGENTS = "CLAUDE.md for Claude Code"


def _version(text: str | None) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in text.split(".")) if text else None
    except ValueError:
        return None


def _rules_folder(path: Path) -> Path | None:
    """The `.cursor/rules` folder a Cursor rule is in."""
    return next((p for p in path.parents if p.name == "rules" and p.parent.name == ".cursor"), None)


def _name(path: Path, in_project: bool) -> str:
    """The block's name: the file's name; a project's `.claude/CLAUDE.md` says its folder, so it
    is not taken for the CLAUDE.md beside it."""
    if in_project and path.name == "CLAUDE.md" and path.parent.name == ".claude":
        return ".claude/CLAUDE.md"
    return path.name


def _reads_agents(inventory, project: str, home: Path) -> bool:
    """Claude Code reads the project's AGENTS.md: it is found, not too old, and no CLAUDE.md
    file is in the project or a folder above it."""
    claude = next((c for c in inventory.clients if c.id == "claude_code"), None)
    if claude is None or claude.status is not ClientStatus.FOUND:
        return False
    version = _version(claude.version)
    if version is not None and version < AGENTS_SINCE:
        return False
    root = Path(project)
    for folder in (root, *root.parents):
        names = ["CLAUDE.md", "CLAUDE.local.md"]
        if not is_home(folder, home):  # ~/.claude/CLAUDE.md is the user's own
            names.append(".claude/CLAUDE.md")
        if any((folder / name).is_file() for name in names):
            return False
    return True


def _blocks(inventory, project: str | None) -> dict[str, dict]:
    """The file blocks by path, from the instruction files each client lists."""
    blocks: dict[str, dict] = {}
    for item in inventory.items:
        if item.client not in COLUMNS or item.kind is not ItemKind.INSTRUCTIONS:
            continue
        if category(item) != "instructions" or not item.source.path:
            continue
        if item.project is not None and item.project != project:
            continue
        path = Path(item.source.path)
        folder = _rules_folder(path) if item.client == "cursor" and path.suffix == ".mdc" else None
        key = str(folder or path)
        block = blocks.setdefault(
            key,
            {
                "group": ALL["key"] if item.project is None else "project",
                "name": CURSOR_RULES if folder else _name(path, item.project is not None),
                "by": {},
                "rules": [] if folder else None,
                "claude_md": False,
            },
        )
        block["by"][item.client] = True
        if folder:
            block["rules"].append(item.name)
        elif item.client == "claude_code" and item.name in CLAUDE_FILES:
            block["claude_md"] = True  # its imports are read
    return blocks


def instructions_map(inventory, adapters, project: str | None) -> dict:
    """The clients, the file groups and the imported files of the Instructions map. A file is
    `{id, name, by, through?, count?, size?, imports, technical: {path, lines, cut?}}`: `through`
    says Claude Code reads an AGENTS.md as its CLAUDE.md, `count` is a Cursor rules folder's
    number of rules (its `lines` are their names), `size` a file's number of lines (None, with
    `cut`, when the file is longer than Kitden reads), `lines` its first lines with secrets
    hidden, and `imports` the ids of every file it brings in, nested ones too. An imported file is
    `{id, name, by_files, outside, missing, technical: {path?}}`; a missing one has no path."""
    home = next((a.home for a in adapters.values()), None)
    status = {c.id: c.status for c in inventory.clients}
    cursor = adapters.get("cursor") if status.get("cursor") is ClientStatus.FOUND else None
    found_claude = status.get("claude_code") is ClientStatus.FOUND
    cursor_imports = bool(cursor and cursor.imports_claude_plugins() and found_claude)
    blocks = _blocks(inventory, project)
    through: set[str] = set()
    if project is not None and home is not None and _reads_agents(inventory, project, home):
        agents = Path(project) / "AGENTS.md"
        if agents.is_file():
            block = blocks.setdefault(
                str(agents),
                {
                    "group": "project",
                    "name": agents.name,
                    "by": {},
                    "rules": None,
                    "claude_md": False,
                },
            )
            block["by"]["claude_code"] = True
            through.add(str(agents))

    imported: dict[str, dict] = {}
    groups = {ALL["key"]: [], "project": []}
    for path, block in blocks.items():
        file_id = _hash("instruction-file", path)
        entry = {
            "id": file_id,
            "name": block["name"],
            "by": {c: True for c in COLUMNS if c in block["by"]},
            "imports": [],
            "technical": {"path": path},
        }
        if path in through:
            entry["through"] = THROUGH_AGENTS
        # The first lines are file text and may name paths: they stay under `technical`.
        if block["rules"] is not None:
            entry["count"] = len(block["rules"])
            entry["technical"]["lines"] = sorted(block["rules"])
        else:
            # One read gives the size, the first lines and the imports. A file longer than the
            # read has no size: `cut` says so.
            text, cut = read_text(Path(path))
            entry["size"] = None if cut else len(text.splitlines())
            if cut:
                entry["technical"]["cut"] = True
            entry["technical"]["lines"] = head(
                text[:PREVIEW_READ], cut=cut or len(text) > PREVIEW_READ
            )
        if home is not None and block["claude_md"]:
            root = Path(project) if block["group"] == "project" and project else None
            for found in imports(Path(path), root, home, text):
                import_id = _hash("imported-file", found["target"])
                one = imported.setdefault(
                    import_id,
                    {
                        "id": import_id,
                        "name": found["name"],
                        "by_files": [],
                        "outside": False,
                        "missing": found["missing"],
                        # A missing import's path is only what the file says: it is left out.
                        "technical": (
                            {} if found["missing"] else {"path": redact_line(found["target"])}
                        ),
                    },
                )
                one["outside"] = one["outside"] or found["outside"]
                if file_id not in one["by_files"]:
                    one["by_files"].append(file_id)
                entry["imports"].append(import_id)
        groups[block["group"]].append(entry)

    order = {c: i for i, c in enumerate(COLUMNS)}

    def key(entry: dict) -> tuple:
        first = min(order[c] for c in entry["by"])
        return (first, entry["name"].lower(), entry["technical"]["path"])

    out = [{**ALL, "files": sorted(groups[ALL["key"]], key=key)}]
    if project is not None and groups["project"]:
        name = PROJECT.format(os.path.basename(project.rstrip("/")))
        out.append({"key": "project", "name": name, "files": sorted(groups["project"], key=key)})
    return {
        "clients": _clients(inventory, cursor_imports),
        "groups": out,
        "imports": list(imported.values()),
    }
