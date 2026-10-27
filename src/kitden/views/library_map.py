"""The Library map: clients, then plugins and skills by where they come from, then what a plugin
holds (spec Part 5.3).

Only what is on this computer and present in some client shows: a marketplace plugin no client
has is left out, and so are account plugins. A plugin's parts are read from its installed folder
and follow the plugin, so the map never says "N of M on". Paths are only under `technical`.
"""

from pathlib import Path

from kitden.changes.actions import CLIENT_WORDS, skill_rules_in
from kitden.changes.engine import writable, writable_roots
from kitden.clients.base import PLUGIN_DISABLE, PLUGIN_ENABLE, PLUGIN_REMOVE, SKILL_REMOVE
from kitden.clients.claude_code import _holds, local_files, rule_file
from kitden.model import ClientStatus, Enabled, Item, ItemKind, Scope
from kitden.views.catalog import catalog, installed_inside
from kitden.views.effective import in_project
from kitden.views.load_map import COLUMNS, Row, load_map, row_key
from kitden.views.setup_server import kitden_on, setup_server_state
from kitden.views.skills import skill_catalog
from kitden.views.words import ORIGIN_WORDS, STATE_WORDS

# A client's words, from its `kitden` entry, as on the Gateway.
CONNECTED = "Connected"
NOT_CONNECTED = "Not connected"
STORE = "store"
# Plugins whose id names no marketplace (a Cursor plugin whose name is not stored locally).
OTHER = {"key": "other", "name": "Other plugins", "icon": "puzzle", "kind": "other"}
SKILLS = {"key": "skills", "name": "Your skills", "icon": "user-round", "kind": "skills"}
SETTINGS = {"key": "settings", "name": "Your settings", "icon": "settings", "kind": "settings"}
PROJECT = {
    "key": "project",
    "name": ORIGIN_WORDS["project"],
    "icon": "folder",
    "kind": "project",
}
KINDS = {ItemKind.PLUGIN: "plugin", ItemKind.SKILL: "skill", ItemKind.HOOK: "hook"}


def _clients(inventory, cursor_imports: bool) -> list[dict]:
    """Each client and its state: not installed, not read, Cursor getting Claude Code's plugins,
    or whether its `kitden` entry is on."""
    status = {c.id: c.status for c in inventory.clients}
    setup = {e["client"]: e for e in setup_server_state(inventory)}
    out = []
    for client in COLUMNS:
        read, entry = status.get(client), setup[client]
        if read is ClientStatus.UNREADABLE:
            state, words = "unreadable", STATE_WORDS["unread"]
        elif read is not ClientStatus.FOUND:
            state, words = "missing", STATE_WORDS["missing"]
        elif client == "cursor" and cursor_imports:
            state, words = "via", STATE_WORDS["via"]
        elif kitden_on(entry):
            state, words = "on", CONNECTED
        else:
            state = "off"
            words = STATE_WORDS["off"] if entry["enabled"] is False else NOT_CONNECTED
        out.append({"id": client, "name": CLIENT_WORDS[client], "state": state, "words": words})
    return out


def _present(inventory, project: str | None) -> dict[str, list[Item]]:
    """The items on this computer that apply in this view, by load map row. Account plugins are
    kept in the account, not here."""
    out: dict[str, list[Item]] = {}
    for item in inventory.items:
        if item.client not in COLUMNS or item.kind not in KINDS or item.scope is Scope.ACCOUNT:
            continue
        if item.project is None or item.project == project:
            out.setdefault(row_key(item), []).append(item)
    return out


def _group(row: Row, own: list[Item], project: str | None) -> dict:
    if row.kind is ItemKind.PLUGIN and not row.source:
        return OTHER
    if row.kind is ItemKind.PLUGIN:
        key = f"marketplace:{row.source}"
        return {"key": key, "name": row.source, "icon": STORE, "kind": "marketplace"}
    if project is not None and all(i.project is not None for i in own):
        return PROJECT
    return SKILLS if row.kind is ItemKind.SKILL else SETTINGS


def _decides_here(item: Item, project: str) -> bool:
    """The project's own settings decide the item there: it is the project's own entry, or the
    project's rule sets a user skill (see `Item.project_rules`)."""
    return item.project is not None or _rule_file(item, project) is not None


def _rule_file(item: Item, project: str | None) -> Scope | None:
    """Which of the project's settings files sets the item there: LOCAL (its local settings),
    PROJECT (the shared, committed file) or None."""
    if project is None:
        return None
    scope = in_project(item, project).state_scope
    return scope if scope in (Scope.PROJECT, Scope.LOCAL) else None


def _links(row: Row, own: set[str], by_id: dict[str, Item], via: bool):
    """Per client: on, off, unknown (it has the item, but Kitden does not know its state) or via
    (not loaded yet; Cursor gets it once Claude Code has it); the client whose folder it loads
    from when that is another client (a faint link); the client's item ids, the deciding one
    first; and the items that decide, by client. A client without the item, or one Kitden could
    not read that has no item kept, has no entry."""
    by, through, ids, deciding = {}, {}, {}, {}
    for client in COLUMNS:
        cell = row.cells[client]
        items = [by_id[i] for i in cell.items if i in own]
        if cell.state == "none" and client == "cursor" and via:
            by[client] = "via"
        if not items or cell.state not in ("on", "review", "off", "unk"):
            continue
        by[client] = {"off": "off", "unk": "unknown"}.get(cell.state, "on")
        ids[client] = [i.id for i in items]
        owner = items[0].source.owner_client
        if by[client] == "on" and owner in COLUMNS and owner != client:
            through[client] = owner
        deciding[client] = items[:1] if cell.state == "off" else items
    return by, through, ids, deciding


def _via_claude_code(row: Row, offers: dict[str, dict], cursor_imports: bool, found) -> bool:
    """Cursor does not have this plugin yet and gets it once Claude Code adds it."""
    offer = offers.get(row.lookup)
    return bool(
        cursor_imports
        and row.kind is ItemKind.PLUGIN
        and offer
        and "claude_code" in found
        and "claude_code" in offer["routes"]
        and "cursor" not in offer["installed"]
    )


# The clients Details may offer: a plugin added to one of these, a skill rule in one of these.
ADDS = ("claude_code", "codex")
RULES = ("claude_code", "codex")


def _can(
    row: Row, by: dict, through: dict, ids: dict, by_id, offer, found, project, outside=False
) -> dict:
    """What Details and a drag may offer for an item, by client: `add`, the clients that can add
    the plugin and lack it (never Cursor: it gets plugins through Claude Code), or that can take a
    copy of the skill (Cursor too, when the skill catalog gives it a route), and `off`, the
    clients that load their own copy and can turn it off for all projects (a plugin's switch, or a
    skill rule), `on`, the clients that have the plugin off and can turn it on, `remove`, the
    clients whose own entry (on or off) Kitden can remove: a plugin's file entry, or a skill's own
    folder (Details' "Remove from …"; a link's × uses it only for a plugin and for Cursor's own
    skill: on a Claude Code or Codex skill the × turns the skill off with `off` instead), and
    `project`, the clients whose state in the picked project comes from the project's own entry or
    rule. A faint link has none.
    `off`, `on` and `remove` act on the user's own entry for all projects, the client's first
    item: a client in `project` is left out of all three (Details say where its setting comes
    from, and offer "Turn off in this project…" where they can). Of those, `local` are the
    clients whose deciding item comes from the project's local settings ("Use the shared rule…"
    takes that key out) and `shared` those set by its committed settings, which Kitden leaves.
    A skill's `copy`: Codex, when it loads a project's own copy (a rule for all projects turns
    off that copy only). A hook has no switch."""
    project_decides = [
        c
        for c, state in by.items()
        if state in ("on", "off", "unknown")
        and c in ids
        and any(project and _decides_here(by_id[i], project) for i in ids[c])
    ]
    files = {c: _rule_file(by_id[ids[c][0]], project) for c in project_decides}
    # Where Kitden does not write the project's rule file, nothing takes its key out either.
    local = [c for c in project_decides if files[c] is Scope.LOCAL and not outside]
    shared = [c for c in project_decides if files[c] is Scope.PROJECT]
    own = [c for c, state in by.items() if state == "on" and c not in through]
    own = [c for c in own if c not in project_decides]
    held = [
        c
        for c, state in by.items()
        if state in ("on", "off") and c not in through and c not in project_decides
    ]
    off = [c for c, state in by.items() if state == "off" and c not in project_decides]

    def removable(action: str) -> list[str]:
        return [c for c in held if action in by_id[ids[c][0]].actions]

    if row.kind is ItemKind.PLUGIN:
        routes, installed = (offer["routes"], offer["installed"]) if offer else ({}, ())
        add = [c for c in ADDS if c in found and c in routes and c not in installed]
        return {
            "add": add,
            "off": [c for c in own if PLUGIN_DISABLE in by_id[ids[c][0]].actions],
            "on": [c for c in off if PLUGIN_ENABLE in by_id[ids[c][0]].actions],
            "remove": removable(PLUGIN_REMOVE),
            "project": project_decides,
            "local": local,
            "shared": shared,
        }
    if row.kind is ItemKind.SKILL:
        routes = offer["routes"] if offer else {}
        add = [c for c in COLUMNS if c in found and c in routes]
        copy = [
            c
            for c in ("codex",)
            if by.get(c) == "on" and c not in through and by_id[ids[c][0]].project is not None
        ]
        return {
            "add": add,
            "off": [c for c in RULES if c in own],
            "remove": removable(SKILL_REMOVE),
            "project": project_decides,
            "local": local,
            "shared": shared,
            "copy": copy,
        }
    return {}


def _off_in(inventory, own: list[Item]) -> list[str]:
    """The projects (by id) whose own settings already turn Claude Code's user skill off."""
    paths = {
        path
        for item in own
        if item.client == "claude_code"
        for path, enabled, _ in item.project_rules
        if enabled is Enabled.OFF
    }
    return [p.id for p in inventory.projects if p.path in paths]


def _skill_offers(inventory, adapters) -> dict[str, dict]:
    """The skill catalog's row for each skill name, a client's own skill first: what a skill of
    "Your skills" is copied from (its id) and the clients that can take a copy (its routes)."""
    out: dict[str, dict] = {}
    for offer in skill_catalog(inventory, adapters):
        if offer["name"] not in out or offer["id"].endswith("@skills"):
            out[offer["name"]] = offer
    return out


def _skill_rules(inventory, adapters, found) -> dict:
    """Where a one-project skill rule can go (Claude Code only): `some` while the user settings
    hold no `skillOverrides` (Claude Code may not merge them across files), and per project whose
    folder is there "ok", "own" (its shared settings hold `skillOverrides`, or its own local file
    does while the rule would go in its repository root's), "new" (no `.claude` folder where its
    rule could go: Kitden makes no folder) or "outside" (its rule file is where Kitden does not
    write, the engine's own test; `outside` names that folder). The same rules as
    changes/actions.py."""
    if "claude_code" not in found or "claude_code" not in adapters:
        return {"some": False, "projects": {}, "outside": {}}

    def holds(path: Path) -> bool:
        try:
            return skill_rules_in(path)
        except ValueError:
            return True  # a file Kitden cannot read may hold them

    home = adapters["claude_code"].home
    projects: dict[str, str] = {}
    outside: dict[str, str] = {}
    for project in inventory.projects:
        folder = Path(project.path)
        if not folder.is_dir():
            continue
        target = rule_file(folder, home)
        own = folder / ".claude/settings.local.json"
        # A rule in the repository root's file is read beside the project's own local file.
        files = [folder / ".claude/settings.json", *([own] if target != own else [])]
        if target is None:
            projects[project.id] = "new"
        elif not _writable(target, home, inventory):
            projects[project.id] = "outside"
            outside[project.id] = target.parent.parent.name
        else:
            projects[project.id] = "own" if any(holds(f) for f in files) else "ok"
    some = not holds(home / ".claude/settings.json")
    return {"some": some, "projects": projects, "outside": outside}


def _writable(path: Path, home: Path, inventory) -> bool:
    return writable(path, home, writable_roots(home, inventory))


def _rule_outside(inventory, adapters, project: str | None) -> bool:
    """The picked project's rule file is where Kitden does not write (`_skill_rules`)."""
    adapter = adapters.get("claude_code")
    if project is None or adapter is None or not Path(project).is_dir():
        return False
    target = rule_file(Path(project), adapter.home)
    return target is not None and not _writable(target, adapter.home, inventory)


def _plugin_folders(adapters) -> dict[str, str]:
    """Plugin id -> its installed folder, the first client's that has it (as installed_inside)."""
    out: dict[str, str] = {}
    for client in COLUMNS:
        if client in adapters:
            for plugin_id, folder in adapters[client].plugin_folders().items():
                out.setdefault(plugin_id, str(folder))
    return out


def _marketplace_sources(inventory) -> dict[str, str]:
    """Marketplace name -> where it comes from, as its item says it (a folder, or host/path with
    no credentials)."""
    out: dict[str, str] = {}
    for client in COLUMNS:
        for item in inventory.items:
            if item.client == client and item.kind is ItemKind.MARKETPLACE:
                source = dict(item.summary).get("source")
                if source:
                    out.setdefault(item.name, source)
    return out


def _local_in(row: Row, project: str, home: Path) -> str | None:
    """The folder whose local settings decide Claude Code's entry in `project`, when it is not
    the project's own but its repository root's (claude_code.local_files: the winning file last),
    so Details name the folder that holds the file."""
    key = (
        ("enabledPlugins", row.lookup)
        if row.kind is ItemKind.PLUGIN
        else ("skillOverrides", row.name)
    )
    holding = [f for f in local_files(Path(project), home) if _holds(f, key)]
    folder = holding[-1].parent.parent if holding else None
    return folder.name if folder and folder != Path(project) else None


def _marketplace_entries(inventory) -> dict[str, dict[str, str]]:
    """Marketplace name -> each client's marketplace item id, for its "Commands…"."""
    out: dict[str, dict[str, str]] = {}
    for item in inventory.items:
        if item.client in COLUMNS and item.kind is ItemKind.MARKETPLACE:
            out.setdefault(item.name, {}).setdefault(item.client, item.id)
    return out


def library_map(inventory, adapters, project: str | None) -> dict:
    """The clients and the source groups of the Library map, in the order the map draws them:
    marketplaces by name, then "Other plugins", "Your skills", "Your settings" and, with a project
    picked, "Only this project". `here` says, per client, the picked project's own settings
    decide the item there; a skill's `off_in` the projects that turn it off already; `can` what
    Details and a drag may offer for it; `skill` the skill catalog's id a skill of "Your skills"
    is copied from; and `skill_rules` where a one-project skill rule can go. `can.local_in` names
    the folder whose local settings decide for Claude Code when it is the project's repository
    root, not the project itself. A marketplace group's
    `entries` are each client's marketplace item id, which `/api/commands` takes."""
    status = {c.id: c.status for c in inventory.clients}
    found = [c for c in COLUMNS if status.get(c) is ClientStatus.FOUND]
    cursor = adapters.get("cursor") if "cursor" in found else None
    cursor_imports = bool(cursor and cursor.imports_claude_plugins() and "claude_code" in found)
    by_id = {i.id: i for i in inventory.items}
    present = _present(inventory, project)
    offers = {o["id"]: o for o in catalog(inventory, adapters)}
    skill_offers = _skill_offers(inventory, adapters)
    held = installed_inside(adapters)
    folders = _plugin_folders(adapters)
    sources = _marketplace_sources(inventory)
    entries = _marketplace_entries(inventory)
    outside = _rule_outside(inventory, adapters, project)

    groups: dict[str, dict] = {}
    for row in load_map(inventory, project):
        items = present.get(row.key, [])
        # A plugin's own skills and hooks are in its Inside column.
        own = [i for i in items if row.kind is ItemKind.PLUGIN or i.scope is not Scope.PLUGIN]
        if not own:
            continue
        via = _via_claude_code(row, offers, cursor_imports, found)
        by, through, ids, deciding = _links(row, {i.id for i in own}, by_id, via)
        if not by:
            continue
        group = _group(row, own, project)
        # Per client, so another client's project copy does not mark Claude Code's.
        here = {
            c: project is not None
            and group["key"] != PROJECT["key"]
            and any(_decides_here(i, project) for i in deciding.get(c, []))
            for c in by
        }
        # Only a skill of "Your skills" adds from the skill catalog; a project's own one does not.
        skill = skill_offers.get(row.name) if group["key"] == SKILLS["key"] else None
        offer = skill if row.kind is ItemKind.SKILL else offers.get(row.lookup)
        entry = {
            "id": row.key,
            "name": row.name,
            "kind": KINDS[row.kind],
            "by": by,
            "through": through,
            "items": ids,
            "here": here,
            "source": group["name"],
            "can": _can(row, by, through, ids, by_id, offer, found, project, outside),
        }
        if project and "claude_code" in entry["can"].get("local", []) and "claude_code" in adapters:
            folder = _local_in(row, project, adapters["claude_code"].home)
            if folder:
                entry["can"]["local_in"] = {"claude_code": folder}
        if skill:
            entry["skill"] = skill["id"]
        if row.kind is ItemKind.SKILL:
            entry["off_in"] = _off_in(inventory, own)
        technical: dict[str, str] = {}
        if row.kind is ItemKind.PLUGIN:
            entry["plugin"] = row.lookup
            if row.lookup in held:
                entry["inside"] = held[row.lookup]
                entry["count"] = sum(len(names) for names in held[row.lookup].values())
            if row.lookup in folders:
                technical["path"] = folders[row.lookup]
            if row.source in sources:
                technical["marketplace"] = sources[row.source]
        elif own[0].source.path:
            technical["path"] = own[0].source.path
        entry["technical"] = technical
        if group["kind"] == "marketplace" and group["key"] not in groups:
            group = {**group, "entries": entries.get(row.source, {})}
        groups.setdefault(group["key"], {**group, "items": []})
        groups[group["key"]]["items"].append(entry)

    markets = sorted(
        (g for g in groups.values() if g["kind"] == "marketplace"),
        key=lambda g: g["name"].lower(),
    )
    rest = [groups[g["key"]] for g in (OTHER, SKILLS, SETTINGS, PROJECT) if g["key"] in groups]
    for group in [*markets, *rest]:
        group["items"].sort(key=lambda i: i["name"].lower())
    return {
        "clients": _clients(inventory, cursor_imports),
        "groups": [*markets, *rest],
        "skill_rules": _skill_rules(inventory, adapters, found),
    }
