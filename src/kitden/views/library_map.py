"""The Library map: clients, then plugins and skills by where they come from, then what a plugin
holds (spec Part 5.3).

Only what is on this computer and present in some client shows: a marketplace plugin no client
has is left out, and so are account plugins. A plugin's parts are read from its installed folder
and follow the plugin, so the map never says "N of M on". Paths are only under `technical`.
"""

from pathlib import Path

from kitden.changes.actions import SKILL_SWITCHES
from kitden.changes.engine import writable, writable_roots
from kitden.clients.base import (
    PLUGIN_DISABLE,
    PLUGIN_ENABLE,
    PLUGIN_REMOVE,
    SKILL_REMOVE,
    found_columns,
    from_plugin,
    listed_columns,
)
from kitden.clients.claude_account import is_account_plugin
from kitden.clients.claude_code import holds, local_files, rule_file
from kitden.model import CLIENT_WORDS, CLIENTS, ClientStatus, Enabled, Item, ItemKind, Scope
from kitden.views.after import home_path
from kitden.views.catalog import catalog, installed_inside, plugin_folders
from kitden.views.effective import effective_view, in_project
from kitden.views.findings import duplicate_copies
from kitden.views.load_map import Row, load_map, row_key
from kitden.views.skills import skill_catalog
from kitden.views.words import (
    GROUP_WORDS,
    OFF_IN_PROJECT,
    ORIGIN_WORDS,
    STATE_WORDS,
    times,
    why_project,
)

# A found client that loads nothing in the view shown.
NOTHING_LOADED = "Nothing loaded"
STORE = "store"
# Plugins whose id names no marketplace (a Cursor plugin whose name is not stored locally).
OTHER = {"key": "other", "name": GROUP_WORDS["other"], "icon": "puzzle", "kind": "other"}
# The plugins the Claude app gives Claude Code from the user's Claude account.
ACCOUNT = {"key": "account", "name": GROUP_WORDS["account"], "icon": "cloud", "kind": "account"}
SKILLS = {"key": "skills", "name": GROUP_WORDS["own"], "icon": "user-round", "kind": "skills"}
SETTINGS = {"key": "settings", "name": "Your settings", "icon": "settings", "kind": "settings"}
PROJECT = {
    "key": "project",
    "name": ORIGIN_WORDS["project"],
    "icon": "folder",
    "kind": "project",
}
KINDS = {ItemKind.PLUGIN: "plugin", ItemKind.SKILL: "skill", ItemKind.HOOK: "hook"}


def cursor_imports(adapters, found: list[str]) -> bool:
    """Cursor and Claude Code are both found, and Cursor loads Claude Code's plugins."""
    cursor = adapters.get("cursor") if "cursor" in found else None
    claude = adapters.get("claude_code") if "claude_code" in found else None
    return bool(
        cursor
        and claude
        and claude.reaches_cursor(ItemKind.PLUGIN)
        and cursor.imports_claude_plugins()
    )


def map_clients(inventory, cursor_imports: bool, loads: dict[str, str | None]) -> list[dict]:
    """Each client and its state on a Library map: not installed, not read, or what it loads there.
    `loads` has, per client, the words for what it loads in the view shown ("5 plugins · 62
    skills", "2 files") and None when it loads nothing there. A found client that loads
    something is `on`; one that loads nothing is `off`, except Cursor when it takes Claude Code's
    plugins: it says "Via Claude Code". The word "Connected" is the Gateway's and means the
    Kitden gateway entry is on; no Library map uses it."""
    status = {c.id: c.status for c in inventory.clients}
    out = []
    for client in listed_columns(inventory):
        read, mine = status.get(client), loads.get(client)
        if read is ClientStatus.UNREADABLE:
            state, words = "unreadable", STATE_WORDS["unread"]
        elif read is not ClientStatus.FOUND:
            state, words = "missing", STATE_WORDS["missing"]
        elif mine:
            state, words = "on", mine
        elif client == "cursor" and cursor_imports:
            state, words = "via", STATE_WORDS["via"]
        else:
            state, words = "off", NOTHING_LOADED
        out.append({"id": client, "name": CLIENT_WORDS[client], "state": state, "words": words})
    return out


def plugin_skill_words(groups: list[dict]) -> dict[str, str | None]:
    """Per client, what it loads of the items in `groups`: its plugins and skills ("5 plugins ·
    62 skills"); with none of those, its hooks ("1 hook"), so a client whose only item is a hook
    never says it loads nothing; None where it loads none. An item another client's folder brings
    in counts, since the client loads it."""
    kinds = ("plugin", "skill", "hook")
    found: dict[str, dict[str, int]] = {c: dict.fromkeys(kinds, 0) for c in CLIENTS}
    for group in groups:
        for item in group["items"]:
            if item["kind"] not in kinds:
                continue
            for client, state in item["by"].items():
                if state == "on":
                    found[client][item["kind"]] += 1

    def words(n: dict[str, int], shown: tuple[str, ...]) -> str:
        return " · ".join(f"{n[k]} {k}{'' if n[k] == 1 else 's'}" for k in shown if n[k])

    return {
        client: words(n, ("plugin", "skill")) or words(n, ("hook",)) or None
        for client, n in found.items()
    }


def _present(inventory, project: str | None) -> dict[str, list[Item]]:
    """The items on this computer that apply in this view, by load map row. Account plugins are
    kept in the account, not here."""
    out: dict[str, list[Item]] = {}
    for item in inventory.items:
        if item.client not in CLIENTS or item.kind not in KINDS or item.scope is Scope.ACCOUNT:
            continue
        if item.project is None or item.project == project:
            out.setdefault(row_key(item), []).append(item)
    return out


def _group(row: Row, own: list[Item], project: str | None) -> dict:
    if row.kind is ItemKind.PLUGIN and any(is_account_plugin(i) for i in own):
        return ACCOUNT
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
    for client in CLIENTS:
        cell = row.cells[client]
        items = [by_id[i] for i in cell.items if i in own]
        if cell.state == "none" and client == "cursor" and via:
            by[client] = "via"
        if not items or cell.state not in ("on", "review", "off", "unk"):
            continue
        by[client] = {"off": "off", "unk": "unknown"}.get(cell.state, "on")
        ids[client] = [i.id for i in items]
        owner = items[0].source.owner_client
        if by[client] == "on" and owner in CLIENTS and owner != client:
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
            # Codex's own table in the picked project, which Kitden turns on or off there.
            "project_switch": [
                c
                for c in project_decides
                if c == "codex"
                and (item := by_id[ids[c][0]]).project == project
                and {PLUGIN_ENABLE, PLUGIN_DISABLE} & set(item.actions)
            ],
        }
    if row.kind is ItemKind.SKILL:
        routes = offer["routes"] if offer else {}
        add = [c for c in CLIENTS if c in found and c in routes]
        copy = [
            c
            for c in ("codex",)
            if by.get(c) == "on" and c not in through and by_id[ids[c][0]].project is not None
        ]
        rule = [c for c in RULES if c in held and _ruled(by_id[ids[c][0]])]
        # A project's own skill folder can go too, from that project's view.
        own_folder = [
            c
            for c in project_decides
            if c not in through
            and by_id[ids[c][0]].project == project
            and SKILL_REMOVE in by_id[ids[c][0]].actions
        ]
        return {
            "add": add,
            "off": [c for c in RULES if c in own],
            "on": [c for c in rule if by[c] == "off"],
            # The skill's own switch for all projects, per client: the states it takes (the same
            # answer as Context's), shown as On, Name only and Off.
            "rule": {c: list(SKILL_SWITCHES[c]) for c in rule},
            "remove": [*removable(SKILL_REMOVE), *own_folder],
            "project": project_decides,
            "local": local,
            "shared": shared,
            "copy": copy,
        }
    return {}


def _copies(inventory, copies: dict[str, list[Item]], ids: dict, home: Path | None) -> dict:
    """Per client that loads the item more than once, `say` ("Cursor loads it 3 times:") and in
    `list` each copy it loads: `where` (a skill's
    folder, a plugin's marketplace), `owner` (the client whose folder or entry it is: "shared" for
    ~/.agents/skills), `remove` (the item whose removal takes this copy away, or None) and `also`
    (the other clients that lose it with it). The copies are the duplicate finding's items, the
    same the Overview and the terminal count."""
    out = {}
    for client, held in ids.items():
        same = next((copies[i] for i in held if i in copies), None)
        if same:
            say = f"{CLIENT_WORDS[client]} loads it {times(len(same))}:"
            out[client] = {"say": say, "list": [_copy(inventory, i, client, home) for i in same]}
    return out


def _copy(inventory, item: Item, client: str, home: Path | None) -> dict:
    action = PLUGIN_REMOVE if item.kind is ItemKind.PLUGIN else SKILL_REMOVE
    path = item.source.path
    holders = [
        i
        for i in inventory.items
        if i.kind is item.kind and (i.id == item.id or (path and i.source.path == path))
    ]
    remove = next((i for i in holders if action in i.actions), None)
    if item.kind is ItemKind.PLUGIN:
        where = item.name.partition("@")[2] or item.name
    else:
        folder = str(Path(path).parent.parent) if path else ""
        where = home_path(folder, home) if home and folder else folder
    return {
        "where": where,
        "owner": item.source.owner_client,
        "remove": remove.id if remove else None,
        "also": sorted({i.client for i in holders if i.client != client and i.client in CLIENTS}),
    }


def _ruled(item: Item) -> bool:
    """A skill rule reaches it: a client's own skill, not one of a plugin's."""
    return item.kind is ItemKind.SKILL and not from_plugin(item)


def _off_in(inventory, own: list[Item]) -> list[str]:
    """The projects (by id) whose own settings already turn Claude Code's user skill off."""
    paths = {
        path
        for item in own
        if item.client == "claude_code"
        for path, enabled, *_ in item.project_rules
        if enabled is Enabled.OFF
    }
    return [p.id for p in inventory.projects if p.path in paths]


def _plugin_off_in(inventory, row: Row) -> list[str]:
    """What the Library says of a plugin with All projects: each project whose own settings turn
    it off (Codex's project config.toml, Claude Code's project settings)."""
    folders = dict.fromkeys(
        i.project
        for i in inventory.items
        if i.kind is ItemKind.PLUGIN
        and i.name == row.lookup
        and i.project is not None
        and i.enabled is Enabled.OFF
    )
    return [OFF_IN_PROJECT.format(project=Path(f).name) for f in folders if f]


def _no_switch(row: Row, can: dict, deciding: dict[str, list[Item]], project: str | None):
    """Why a plugin has no switch in the picked project: Codex's project settings set it there,
    and Kitden does not write them. The same words as Context's group."""
    if row.kind is not ItemKind.PLUGIN or not project or "codex" not in can.get("project", []):
        return None
    if "codex" in can.get("project_switch", []):
        return None
    if not any(i.project == project for i in deciding.get("codex", [])):
        return None
    return why_project(project)


def _skill_offers(inventory, adapters) -> dict[str, dict]:
    """The skill catalog's row for each skill name, a client's own skill first: what a skill of
    "Your skills" is copied from (its id) and the clients that can take a copy (its routes)."""
    out: dict[str, dict] = {}
    for offer in skill_catalog(inventory, adapters):
        if offer["name"] not in out or offer["id"].endswith("@skills"):
            out[offer["name"]] = offer
    return out


def _skill_rules(inventory, adapters, found) -> dict:
    """Where a one-project skill rule can go (Claude Code only), per project whose folder is
    there: "ok", "new" (no `.claude` folder where its rule could go: Kitden makes no folder) or
    "outside" (its rule file is where Kitden does not write, the engine's own test; `outside`
    names that folder). The same rules as changes/actions.py."""
    if "claude_code" not in found or "claude_code" not in adapters:
        return {"projects": {}, "outside": {}}
    home = adapters["claude_code"].home
    projects: dict[str, str] = {}
    outside: dict[str, str] = {}
    for project in inventory.projects:
        folder = Path(project.path)
        if not folder.is_dir():
            continue
        target = rule_file(folder, home)
        if target is None:
            projects[project.id] = "new"
        elif not _writable(target, home, inventory):
            projects[project.id] = "outside"
            outside[project.id] = target.parent.parent.name
        else:
            projects[project.id] = "ok"
    return {"projects": projects, "outside": outside}


def _writable(path: Path, home: Path, inventory) -> bool:
    return writable(path, home, writable_roots(home, inventory))


def _rule_outside(inventory, adapters, project: str | None) -> bool:
    """The picked project's rule file is where Kitden does not write (`_skill_rules`)."""
    adapter = adapters.get("claude_code")
    if project is None or adapter is None or not Path(project).is_dir():
        return False
    target = rule_file(Path(project), adapter.home)
    return target is not None and not _writable(target, adapter.home, inventory)


def has_own_rules(inventory, project: str) -> bool:
    """The project's own settings decide a plugin or skill there: what `here` says in
    `library_map`, without the catalogs and folders that map reads for Details. The Overview asks
    this for every known project, so it must stay cheap."""
    by_id = {i.id: i for i in inventory.items}
    present = _present(inventory, project)
    for row in load_map(inventory, project):
        if row.kind not in (ItemKind.PLUGIN, ItemKind.SKILL):
            continue
        items = present.get(row.key, [])
        own = [i for i in items if row.kind is ItemKind.PLUGIN or i.scope is not Scope.PLUGIN]
        if not own or _group(row, own, project)["key"] == PROJECT["key"]:
            continue
        deciding = _links(row, {i.id for i in own}, by_id, False)[3]
        if any(_decides_here(i, project) for held in deciding.values() for i in held):
            return True
    return False


def _marketplace_sources(inventory) -> dict[str, str]:
    """Marketplace name -> where it comes from, as its item says it (a folder, or host/path with
    no credentials)."""
    out: dict[str, str] = {}
    for client in CLIENTS:
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
    holding = [f for f in local_files(Path(project), home) if holds(f, key)]
    folder = holding[-1].parent.parent if holding else None
    return folder.name if folder and folder != Path(project) else None


def _marketplace_entries(inventory) -> dict[str, dict[str, str]]:
    """Marketplace name -> each client's marketplace item id, for its "Commands…"."""
    out: dict[str, dict[str, str]] = {}
    for item in inventory.items:
        if item.client in CLIENTS and item.kind is ItemKind.MARKETPLACE:
            out.setdefault(item.name, {}).setdefault(item.client, item.id)
    return out


def library_map(inventory, adapters, project: str | None) -> dict:
    """The clients and the source groups of the Library map, in the order the map draws them:
    marketplaces by name, then "From your Claude account", "Other plugins", "Your skills", "Your
    settings" and, with a project picked, "Only this project". A plugin of the Claude account
    has `note`: where it comes from and where its switch is. `here` says, per client, the picked
    project's own settings decide the item there; a skill's `off_in` the projects that turn it
    off already; `can` what Details and a drag may offer for it; `skill` the skill catalog's id
    a skill of "Your skills" is copied from; and `skill_rules` where a one-project skill rule
    can go. `can.local_in` names the folder whose local settings decide for Claude Code when it
    is the project's repository root, not the project itself. A marketplace group's `entries`
    are each client's marketplace item id, which `/api/commands` takes."""
    found = found_columns(inventory)
    imports = cursor_imports(adapters, found)
    by_id = {i.id: i for i in inventory.items}
    present = _present(inventory, project)
    offers = {o["id"]: o for o in catalog(inventory, adapters)}
    skill_offers = _skill_offers(inventory, adapters)
    held = installed_inside(adapters)
    folders = plugin_folders(adapters)
    sources = _marketplace_sources(inventory)
    entries = _marketplace_entries(inventory)
    outside = _rule_outside(inventory, adapters, project)
    copies = duplicate_copies(inventory, project)
    home = next((a.home.resolve() for a in adapters.values()), None)

    # A skill's own state (Name only) as the client reads it there, a project's local file too.
    states = {
        i.id: i.skill_state
        for client in found
        for i in effective_view(inventory, client, project).items
        if i.kind is ItemKind.SKILL
    }
    groups: dict[str, dict] = {}
    for row in load_map(inventory, project):
        items = present.get(row.key, [])
        # A plugin's own skills and hooks are in its Inside column.
        own = [i for i in items if row.kind is ItemKind.PLUGIN or i.scope is not Scope.PLUGIN]
        if not own:
            continue
        via = _via_claude_code(row, offers, imports, found)
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
        if loads_twice := _copies(inventory, copies, ids, home):
            entry["copies"] = loads_twice
        if row.kind is ItemKind.SKILL:
            entry["off_in"] = _off_in(inventory, own)
            said = [states.get(i.id, i.skill_state) for i in own]
            said = [state for state in said if state and state != "off"]
            if said:
                entry["skill_state"] = said[0]
            # Where its switch is, the state it shows now, per client.
            entry["can"]["now"] = {
                c: "off" if by[c] == "off" else states.get(ids[c][0]) or "on"
                for c in entry["can"]["rule"]
            }
        account = next((i for i in own if is_account_plugin(i)), None)
        if account is not None and account.change_hint:
            entry["note"] = account.change_hint
        technical: dict[str, str] = {}
        if row.kind is ItemKind.PLUGIN:
            entry["plugin"] = row.lookup
            if project is None and (off_in := _plugin_off_in(inventory, row)):
                entry["off_where"] = off_in
            if why := _no_switch(row, entry["can"], deciding, project):
                entry["no_switch"] = why
            if row.lookup in held:
                entry["inside"] = held[row.lookup]
                entry["count"] = sum(len(names) for names in held[row.lookup].values())
            if row.lookup in folders:
                technical["path"] = str(folders[row.lookup])
            if row.source in sources:
                technical["marketplace"] = sources[row.source]
        elif own[0].source.path:
            technical["path"] = own[0].source.path
        entry["technical"] = technical
        if group["kind"] == "marketplace" and group["key"] not in groups:
            group = {**group, "entries": entries.get(row.source, {}) if row.source else {}}
        groups.setdefault(group["key"], {**group, "items": []})
        groups[group["key"]]["items"].append(entry)

    markets = sorted(
        (g for g in groups.values() if g["kind"] == "marketplace"),
        key=lambda g: g["name"].lower(),
    )
    order = (ACCOUNT, OTHER, SKILLS, SETTINGS, PROJECT)
    rest = [groups[g["key"]] for g in order if g["key"] in groups]
    for group in [*markets, *rest]:
        group["items"].sort(key=lambda i: i["name"].lower())
    shown = [*markets, *rest]
    return {
        "clients": map_clients(inventory, imports, plugin_skill_words(shown)),
        "groups": shown,
        "skill_rules": _skill_rules(inventory, adapters, found),
    }
