"""The Instructions map: clients, the instruction files they read, and the files those import
(spec Part 6.1).

Files are grouped "All projects" and, with a project picked, "Only this project · <folder>": one
block per file, with the clients that read it. A Cursor rules folder is one block. Only Claude
Code's CLAUDE.md files have imports. Commands and agents (Claude Code's, the user's and the picked
project's) are a third group, "Commands and agents", one block each. Kitden only reads these
files; paths are only under `technical`, and imports reach the page only, never the MCP server.
"""

import os
from pathlib import Path

from kitden.clients.base import found_columns
from kitden.clients.claude_code import user_folder
from kitden.clients.claude_folder import ClaudeFolder
from kitden.model import CLIENT_WORDS, CLIENTS, ClientStatus, ItemKind, _hash
from kitden.redact import redact_line
from kitden.views.effective import client_order
from kitden.views.explain import PREVIEW_READ, head
from kitden.views.imports import imports, read_text
from kitden.views.library_map import map_clients
from kitden.views.load_map import category
from kitden.views.words import NO_FILE_ALL, NO_FILE_HERE, PICK_PROJECT, join_words

ALL = {"key": "all", "name": "All projects"}
PROJECT = "Only this project · {}"
COMMANDS = {"key": "commands", "name": "Commands and agents"}
# A client block whose only files on the map are commands or agents.
ONLY_COMMANDS = "Commands and agents only"
# The categories of instruction items this map shows: files, and commands and agents (their kind).
KINDS = {"command": "command", "agent": "agent"}
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


def _reads_agents(inventory, project: str, own: ClaudeFolder) -> bool:
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
        if not own.is_own(folder):  # the user's own CLAUDE.md does not count
            names.append(".claude/CLAUDE.md")
        if any((folder / name).is_file() for name in names):
            return False
    return True


def _blocks(inventory, project: str | None) -> dict[str, dict]:
    """The file blocks by path, from the instruction files each client lists."""
    blocks: dict[str, dict] = {}
    for item in inventory.items:
        if item.client not in CLIENTS or item.kind is not ItemKind.INSTRUCTIONS:
            continue
        kind = KINDS.get(category(item) or "")
        if (category(item) != "instructions" and not kind) or not item.source.path:
            continue
        if item.project is not None and item.project != project:
            continue
        path = Path(item.source.path)
        folder = _rules_folder(path) if item.client == "cursor" and path.suffix == ".mdc" else None
        key = str(folder or path)
        group = COMMANDS["key"] if kind else ALL["key"] if item.project is None else "project"
        name = CURSOR_RULES if folder else _name(path, item.project is not None)
        block = blocks.setdefault(
            key,
            {
                "group": group,
                "name": item.name if kind else name,
                "kind": kind,
                "by": {},
                "rules": [] if folder else None,
                "claude_md": False,
                "names": [],
            },
        )
        block["by"][item.client] = True
        if item.name not in block["names"]:
            block["names"].append(item.name)
        if folder:
            block["rules"].append(item.name)
        elif item.client == "claude_code" and item.name in CLAUDE_FILES:
            block["claude_md"] = True  # its imports are read
    return blocks


def instructions_map(inventory, adapters, project: str | None) -> dict:
    """The clients, the file groups and the imported files of the Instructions map. A file is
    `{id, name, kind?, names, by, through?, count?, size?, imports, technical: {path, lines,
    cut?}}`: `kind` is "command" or "agent" in "Commands and agents", `names` the names of the
    items it stands for (what an Overview link selects), `through` says Claude Code reads an
    AGENTS.md as its CLAUDE.md, `count` is a Cursor rules folder's number of rules (its `lines`
    are their names), `size` a file's number of lines (None, with `cut`, when the file is longer
    than Kitden reads), `lines` its first lines with secrets hidden, and `imports` the ids of
    every file it brings in, nested ones too. An imported file is
    `{id, name, by_files, outside, missing, technical: {path?}}`; a missing one has no path."""
    home = next((a.home for a in adapters.values()), None)
    blocks = _blocks(inventory, project)
    through: set[str] = set()
    own = user_folder(adapters, home) if home is not None else None
    if project is not None and own is not None and _reads_agents(inventory, project, own):
        agents = Path(project) / "AGENTS.md"
        if agents.is_file():
            block = blocks.setdefault(
                str(agents),
                {
                    "group": "project",
                    "name": agents.name,
                    "by": {},
                    "kind": None,
                    "rules": None,
                    "claude_md": False,
                    "names": [agents.name],
                },
            )
            block["by"]["claude_code"] = True
            through.add(str(agents))

    imported: dict[str, dict] = {}
    groups = {ALL["key"]: [], "project": [], COMMANDS["key"]: []}
    for path, block in blocks.items():
        file_id = _hash("instruction-file", path)
        entry = {
            "id": file_id,
            "name": block["name"],
            "by": {c: True for c in CLIENTS if c in block["by"]},
            "names": block["names"],
            "imports": [],
            "technical": {"path": path},
        }
        if block["kind"]:
            entry["kind"] = block["kind"]
        if path in through:
            entry["through"] = THROUGH_AGENTS
        text = ""
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

    def key(entry: dict) -> tuple:
        first = min(client_order(c) for c in entry["by"])
        return (first, entry["name"].lower(), entry["technical"]["path"])

    out = [{**ALL, "files": sorted(groups[ALL["key"]], key=key)}]
    if project is not None and groups["project"]:
        name = PROJECT.format(os.path.basename(project.rstrip("/")))
        out.append({"key": "project", "name": name, "files": sorted(groups["project"], key=key)})
    if groups[COMMANDS["key"]]:
        out.append({**COMMANDS, "files": sorted(groups[COMMANDS["key"]], key=key)})
    files = [f for g in out if g["key"] != COMMANDS["key"] for f in g["files"]]
    extras = groups[COMMANDS["key"]]
    loads = {
        client: _file_words(
            sum(client in f["by"] for f in files), any(client in f["by"] for f in extras)
        )
        for client in CLIENTS
    }
    return {
        # Cursor taking Claude Code's plugins says nothing about instruction files.
        "clients": map_clients(inventory, False, loads),
        "groups": out,
        "imports": list(imported.values()),
        "note": _no_file_note(found_columns(inventory), files, project),
    }


def _file_words(count: int, extras: bool) -> str | None:
    """What a client reads on this map: its instruction files ("3 files"), as the note under the
    map counts them; with none of those but a command or an agent, "Commands and agents only";
    None for nothing."""
    if count:
        return f"{count} file" if count == 1 else f"{count} files"
    return ONLY_COMMANDS if extras else None


def _no_file_note(found: list[str], files: list[dict], project: str | None) -> str | None:
    """One quiet sentence when a found client reads no instruction file in the scope shown: with
    All projects, only the files every project loads are shown; with a project picked, its own
    too. Commands and agents are not instruction files. None when every found client has one."""
    reading = {c for f in files for c in f["by"]}
    none = [CLIENT_WORDS[c] for c in found if c not in reading]
    if not none:
        return None
    sentence = NO_FILE_ALL if project is None else NO_FILE_HERE
    note = sentence.format(names=join_words(none), loads="loads" if len(none) == 1 else "load")
    return f"{note} {PICK_PROJECT}" if project is None else note
