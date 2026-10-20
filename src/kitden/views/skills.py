"""The skills catalog: skills inside the plugins on this computer, and the ones already in a
client's skills folder, so they can be copied to another client (Discover, phase 2). Read only.

Where each client reads the user's skills (checked 2026-10-19: Claude Code 2.1.283, Codex CLI
0.163, Cursor 3.21): Claude Code ~/.claude/skills; Codex ~/.agents/skills and ~/.codex/skills;
Cursor ~/.cursor/skills and ~/.agents/skills, plus ~/.claude/skills and ~/.codex/skills when
Include Third-Party Plugins is on.
"""

import os
import re
from pathlib import Path

from kitden.changes.copy_folder import CopyRefusedError, list_files
from kitden.clients.base import ClientAdapter
from kitden.model import ClientStatus, Enabled, ItemKind, Scope
from kitden.views.catalog import (
    INSTALLERS,
    MARKETPLACE_FILES,
    _category_name,
    _first,
    _plugin_dir,
)

CLIENTS = ("claude_code", "codex", "cursor")
CLIENT_WORDS = {"claude_code": "Claude Code", "codex": "Codex", "cursor": "Cursor"}
NEEDS_PLUGIN = "This skill needs the rest of its plugin. Add the plugin instead."
# Files the agent may run. Everything else is read as text or data.
SCRIPT_SUFFIXES = {
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".rb",
    ".pl",
    ".ps1",
    ".command",
}
TEXT_LIMIT = 512 * 1024
# A path-like word that climbs out of its folder, such as ../../assets/logo.svg.
# A path that goes up a folder. It starts only where a path starts, so a long run of path
# characters is read once, not once per character (that took 8 s on a real Mac, 2026-10-20).
PATH_UP = re.compile(r"(?<![\w.${}~/-])[\w.${}~/-]*?\.\./[\w.${}~/-]*")
KEY_LINE = re.compile(r"^([A-Za-z][\w-]*):\s*(.*)$")
BLOCK_MARKS = {"|", ">", "|-", ">-", "|+", ">+"}


def front_matter(skill_md: Path) -> dict[str, str]:
    """The `key: value` lines between the `---` fences of SKILL.md, as plain text.

    A block value (`description: >` followed by indented lines) is joined into one line.
    Lists and nested keys are skipped; only flat text is needed here.
    """
    try:
        text = skill_md.read_text()
    except (OSError, UnicodeDecodeError):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        return {}
    out: dict[str, str] = {}
    key = None
    block: list[str] | None = None
    for line in parts[1].splitlines():
        match = KEY_LINE.match(line)
        if match:
            if key and block is not None:
                out[key] = " ".join(x for x in block if x)
            key, value = match.group(1), match.group(2).strip()
            block = [] if value in BLOCK_MARKS else None
            if block is None:
                out[key] = value.strip("'\"")
        elif key and block is not None:
            block.append(line.strip())
    if key and block is not None:
        out[key] = " ".join(x for x in block if x)
    return out


def _text(path: Path) -> str | None:
    try:
        if path.stat().st_size > TEXT_LIMIT:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:1024]:
        return None
    return data.decode("utf-8", "ignore")


def _is_script(path: Path) -> bool:
    if path.suffix.lower() in SCRIPT_SUFFIXES:
        return True
    if path.suffix or not os.access(path, os.X_OK):
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(2) == b"#!"
    except OSError:
        return False


def _signature(folder: Path) -> tuple:
    out = []
    for path in sorted(folder.rglob("*")):
        try:
            st = path.lstat()
        except OSError:
            continue
        rel = path.relative_to(folder).as_posix()
        out.append((rel, st.st_mode, st.st_size, st.st_mtime_ns))
    return tuple(out)


def _read_skill(folder: Path) -> dict:
    meta = front_matter(folder / "SKILL.md")
    needs: list[str] = []
    try:
        names = list_files(folder)
    except (CopyRefusedError, OSError) as error:
        names = sorted(
            p.relative_to(folder).as_posix() for p in folder.rglob("*") if not p.is_dir()
        )
        needs.append(str(error))
    files = []
    outside: set[str] = set()
    plugin_root = False
    for rel in names:
        path = folder / rel
        files.append({"path": rel, "script": _is_script(path)})
        text = _text(path)
        if text is None:
            continue
        if "PLUGIN_ROOT" in text:
            plugin_root = True
        for token in PATH_UP.findall(text) if "../" in text else ():
            resolved = os.path.normpath(os.path.join(path.parent, token))
            if resolved != str(folder) and not resolved.startswith(str(folder) + os.sep):
                outside.add(token)
    if plugin_root:
        needs.append("mentions the plugin root")
    if outside:
        needs.append("points outside its folder: " + ", ".join(sorted(outside)[:3]))
    return {
        "name": meta.get("name") or folder.name,
        "description": meta.get("description", ""),
        "files": files,
        "self_contained": not needs,
        "needs": needs,
    }


# Reading every file of hundreds of skills takes a moment; a folder is read again only when a
# file in it changed.
_CACHE: dict[str, tuple[tuple, dict]] = {}


def read_skill(folder: Path) -> dict:
    """Name, description, files (scripts marked) and whether the skill stands on its own."""
    folder = Path(os.path.realpath(folder))
    signature = _signature(folder)
    cached = _CACHE.get(str(folder))
    if cached and cached[0] == signature:
        return cached[1]
    info = _read_skill(folder)
    _CACHE[str(folder)] = (signature, info)
    return info


def _row(
    row_id: str,
    info: dict,
    folder: Path,
    source: str,
    plugin_id: str | None,
    marketplace: str | None,
    category: str | None,
    installed: dict[str, str],
    found: set[str],
) -> dict:
    can = info["self_contained"]
    return {
        "id": row_id,
        "kind": "skill",
        "name": info["name"],
        "description": info["description"],
        "from": source,
        "plugin": plugin_id,
        "marketplace": marketplace,
        "category": category,
        "path": str(folder),
        "files": info["files"],
        "self_contained": can,
        "needs": info["needs"],
        "installed": installed,
        "routes": {c: "ready" for c in CLIENTS if c in found and c not in installed and can},
    }


def skill_catalog(inventory, adapters: dict[str, ClientAdapter]) -> list[dict]:
    """Every skill on this computer, once, with what each client does with it.

    `installed[client]` says how the client already loads a skill of that name ("Installed" in
    its own folder, "Via Claude Code" from another client's folder, "Via plugin" from any of its
    plugins); `routes[client]` is "ready" when the client can take a copy. A skill that is not
    self-contained has no routes.
    """
    found = {c.id for c in inventory.clients if c.status is ClientStatus.FOUND and c.id in CLIENTS}
    loads: dict[str, dict[str, str]] = {}
    plugins: dict[str, set[str]] = {}
    plugins_on: dict[str, set[str]] = {}  # the same, only where the plugin is not turned off
    # Skill name -> the clients that load it from a plugin. The scan has these for Claude Code;
    # for Codex and Cursor the plugin folders read below say.
    from_plugins: dict[str, set[str]] = {}
    for item in inventory.items:
        if item.client not in CLIENTS:
            continue
        if item.kind is ItemKind.SKILL and item.scope is Scope.USER:
            owner = item.source.owner_client
            own = owner in (item.client, "shared")
            word = "Installed" if own else f"Via {CLIENT_WORDS.get(owner, owner)}"
            words = loads.setdefault(item.name, {})
            if own or item.client not in words:
                words[item.client] = word
        elif item.kind is ItemKind.SKILL and item.scope is Scope.PLUGIN:
            if item.enabled is not Enabled.OFF:
                from_plugins.setdefault(item.name, set()).add(item.client)
        elif item.kind is ItemKind.PLUGIN and "@" in item.name:
            plugins.setdefault(item.name, set()).add(item.client)
            if item.enabled is not Enabled.OFF:
                plugins_on.setdefault(item.name, set()).add(item.client)

    rows: dict[str, dict] = {}

    def add_plugin_skills(plugin_id: str, marketplace: str, folder: Path, category: str | None):
        for skill_dir in sorted(p.parent for p in folder.glob("skills/*/SKILL.md")):
            row_id = f"{skill_dir.name}@{plugin_id}"
            if row_id in rows:
                continue
            info = read_skill(skill_dir)
            installed = dict(loads.get(info["name"], {}))
            rows[row_id] = _row(
                row_id,
                info,
                skill_dir,
                plugin_id,
                plugin_id,
                marketplace,
                category,
                installed,
                found,
            )

    for client in INSTALLERS:
        if client not in adapters:
            continue
        for marketplace, root in adapters[client].marketplace_roots().items():
            listed = _first(root, MARKETPLACE_FILES) or {}
            for entry in listed.get("plugins") or []:
                if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                    continue
                folder = _plugin_dir(root, entry.get("source"))
                if folder is None:
                    continue
                category = _category_name(entry.get("category"))
                add_plugin_skills(f"{entry['name']}@{marketplace}", marketplace, folder, category)

    # Cursor keeps the plugins it installs in its own cache, with no marketplace file to read.
    cursor = adapters.get("cursor")
    for plugin_id, folder in (cursor.plugin_folders() if cursor else {}).items():
        add_plugin_skills(plugin_id, plugin_id.split("@", 1)[1], folder, None)

    # A skill in a client's own folder that no plugin here holds: it can go to another client.
    plugin_names = {r["name"] for r in rows.values()}
    own: dict[str, Path] = {}
    for item in inventory.items:
        standalone = (
            item.kind is ItemKind.SKILL
            and item.scope is Scope.USER
            and item.client in CLIENTS
            and item.name not in plugin_names
            and item.source.path is not None
        )
        if standalone:
            own.setdefault(item.name, Path(item.source.path).parent)
    for name, skill_dir in own.items():
        info = read_skill(skill_dir)
        installed = dict(loads.get(name, {}))
        owners = [CLIENT_WORDS[c] for c in CLIENTS if installed.get(c) == "Installed"]
        source = " and ".join(owners) if owners else "Your skills"
        row_id = f"{name}@skills"
        rows[row_id] = _row(row_id, info, skill_dir, source, None, None, None, installed, found)

    # A client that loads a skill from one plugin has it: a copy from another place would be a
    # second one, so it takes none. Its own folders still name the way it loads it.
    for row in rows.values():
        for client in plugins_on.get(row["plugin"], ()):
            from_plugins.setdefault(row["name"], set()).add(client)
    for row in rows.values():
        for client in from_plugins.get(row["name"], ()):
            row["installed"].setdefault(client, "Via plugin")
        row["routes"] = {c: r for c, r in row["routes"].items() if c not in row["installed"]}
    return sorted(rows.values(), key=lambda r: (r["name"].lower(), r["from"].lower()))
