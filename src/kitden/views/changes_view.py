"""The Changes page: one entry per change, from its log lines and the record Kitden keeps.

An entry says what the page shows: when, the title's parts, the state, the clients, the project,
the backup, what to do for it to take effect, the history, the tray rows, the request Redo…
previews again, where "See it on the map" goes and the servers it took out of a client that are
back there now. Paths, backups and commands are only under `technical`, for Technical details.
"""

import os
from datetime import UTC, datetime
from pathlib import Path

from kitden.changes.actions import GATEWAY_MOVE
from kitden.changes.batch import kitden_server
from kitden.changes.engine import PUT_BACK
from kitden.changes.json_splice import ABSENT
from kitden.clients.base import REMOVE_DIRECT
from kitden.local_gateway.settings import CLIENT as KITDEN
from kitden.local_gateway.views import rule_of
from kitden.model import CLIENTS, Change, Item, ItemKind, Scope, Step
from kitden.redact import masked_command, redact_text
from kitden.views.effective import client_order

# Steps whose client is not one the person uses: a registered gateway and Kitden's own settings.
NOT_CLIENTS = {"gateway", KITDEN}
# The states of a change that wrote something and still has it, or had it put back.
HAPPENED = {"verified", "undone", "undo_blocked"}
# A Library action; any other item opens on the Gateway.
LIBRARY_ACTIONS = ("plugin.", "skill.", "marketplace.")
TITLE_STEP = ("client", "name", "scope", "reaches", "keeps")
# The changes that take a direct MCP entry out of a client: a removal, and a move.
TAKES_OUT = (REMOVE_DIRECT, GATEWAY_MOVE)
# The tables of MCP entries in the clients' files.
SERVER_TABLES = ("mcpServers", "mcp_servers")


def _made(change_id: str) -> str | None:
    """When the change was previewed: its id starts with that time (model._new_change_id)."""
    try:
        made = datetime.strptime(change_id[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None
    return made.isoformat()


def _day(time: str) -> str | None:
    """The local calendar day of a log time, such as "2026-10-27"; the page says it in words."""
    try:
        return datetime.fromisoformat(time).astimezone().date().isoformat()
    except (TypeError, ValueError):
        return None


def _folder(path: str | None) -> str | None:
    return Path(path).name if path else None


def _target(target: dict | None) -> dict | None:
    """Where the steps go, with the project's folder name in place of its path."""
    if not target:
        return None
    return {**target, "project": _folder(target.get("project"))}


def _clients(steps: list[dict]) -> list[str]:
    found = {c for s in steps for c in (s.get("reaches") or [s.get("client")])}
    return sorted((c for c in found if c and c not in NOT_CLIENTS), key=client_order)


def _backup(state: str, error: str | None) -> str:
    """ "kept" while the backup holds what was there before, "back" once it is back in place,
    "none" when nothing was written."""
    if state in ("verified", "undo_blocked"):
        return "kept"
    if state == "undone" or (state == "restored" and (error or "").endswith(PUT_BACK)):
        return "back"
    return "kept" if state == "restored" else "none"


def _takes_effect(state: str, steps: list[dict]) -> list[dict]:
    """Each client's restart note and log-in note (None when it has none), once; nothing for a
    change that wrote nothing."""
    if state not in HAPPENED:
        return []
    notes = {
        (s["client"], s.get("restart_note"), s.get("login_note")): None
        for s in steps
        if s.get("restart_note") or s.get("login_note")
    }
    found = sorted(notes, key=lambda found: client_order(found[0]))
    return [{"client": client, "note": note, "login": login} for client, note, login in found]


def _history(change_id: str, lines: list[dict]) -> list[dict]:
    made = _made(change_id)
    first = [{"time": made, "state": "previewed"}] if made else []
    return first + [{"time": line.get("time"), "state": line.get("state")} for line in lines]


def _item_ids(body: dict) -> set[str]:
    targets = body.get("targets") or []
    ids = [t.get("item") for t in targets if isinstance(t, dict)]
    ids.append((body.get("params") or {}).get("item"))
    return {i for i in ids if isinstance(i, str) and i}


def _about(body: dict) -> str | None:
    """The Kitden gateway server a gateway row names (`params.server`); an add names it as
    "<plugin>/<name>"."""
    server = (body.get("params") or {}).get("server")
    if not str(body.get("action", "")).startswith("gateway.") or not isinstance(server, str):
        return None
    return server.partition("/")[2] if body["action"] == "gateway.add" else server


def _map(change: Change | None, request: list[dict] | None, rows: int, inventory) -> dict | None:
    """Where "See it on the map" goes, when the change touched one Kitden gateway server or one
    item: {view, sel, gone}. `sel` is as the page's address writes it ("tool:files/read_file").
    `gone`: the item is no longer there; `sel` is then None when only its id was known. Of
    several tray rows, a server counts only when every row is a gateway row about it, and an
    item only when every row names one."""
    servers = {name for s in change.steps if (name := kitden_server(s))} if change else set()
    several = rows > 1 and (not request or any(_about(body) not in servers for body in request))
    if len(servers) == 1 and several:
        return None
    if len(servers) == 1:
        [server] = servers
        rule = rule_of(change)
        tool = rule["tool"] if rule else None
        sel = f"tool:{server}/{tool}" if tool else f"mcp_server:{server}"
        mcp = ItemKind.MCP_SERVER
        gone = not any(i.kind is mcp and i.name == server for i in inventory.items)
        return {"view": "gateway", "sel": sel, "gone": gone}
    if servers or not request:
        return None
    named = [_item_ids(body) for body in request]
    ids = set().union(*named)
    if not ids or (len(request) > 1 and not all(named)):
        return None
    by_id = {i.id: i for i in inventory.items}
    found = {(str(by_id[i].kind), by_id[i].name) for i in ids if i in by_id}
    # Several rows name one item only when every id is still there and is that item.
    if len(found) > 1 or (len(request) > 1 and (ids - by_id.keys() or not found)):
        return None
    if found:
        [(kind, name)] = found
        view = "gateway" if kind == str(ItemKind.MCP_SERVER) else "library"
        return {"view": view, "sel": f"{kind}:{name}", "gone": False}
    library = str(request[0].get("action", "")).startswith(LIBRARY_ACTIONS)
    return {"view": "library" if library else "gateway", "sel": None, "gone": True}


def _technical(steps: list[dict], change: Change | None, error: str | None) -> dict:
    """The paths and addresses the steps wrote, the backup files, the commands (masked) and the
    engine's error, which names files."""
    paths = list(dict.fromkeys(s["path"] for s in steps if s.get("path")))
    backups, commands = [], []
    for step in change.steps if change else []:
        for part in (step.edit, step.removal):
            if part is not None and part.backup_path:
                backups.append(part.backup_path)
        if step.command:
            commands.append(redact_text(" ".join(masked_command(step.command))))
    backups = list(dict.fromkeys(backups))
    return {"paths": paths, "backups": backups, "commands": commands, "error": error}


def _entry(change_id: str, lines: list[dict], change: Change | None, inventory) -> dict:
    """One change from its log lines, oldest first, and its record (None when Kitden has none)."""
    first, last = lines[0], lines[-1]
    steps = last.get("steps") or []
    state = str(last.get("state"))
    rows = [{"title": row.get("title", "")} for row in last.get("rows") or []]
    target = _target(last.get("target"))
    request = last.get("request")
    return {
        "id": change_id,
        "time": first.get("time"),
        "day": _day(first.get("time")),
        "title_parts": {
            "action": last.get("action"),
            "steps": [{k: s.get(k) for k in TITLE_STEP} for s in steps],
            "target": target,
            "rule": rule_of(change),
            "rows": rows,
        },
        "state": state,
        "clients": _clients(steps),
        "project": target["project"] if target and target.get("scope") == "project" else None,
        "backup": _backup(state, last.get("error")),
        # The backup or the record keeps a secret: the page says so (parts.js backupNote).
        "holds_secret": bool(last.get("holds_secret")),
        "takes_effect": _takes_effect(state, steps),
        "history": _history(change_id, lines),
        "rows": rows,
        # Never drawn on the page: Redo… only puts these bodies back into the tray, so a typed
        # source here may name a folder.
        "redo": request or None,
        "map": _map(change, request, len(rows), inventory),
        "technical": _technical(steps, change, last.get("error")),
        "came_back": [],  # filled in by change_entries
    }


def _taken_out(change: Change) -> list[Step]:
    """The steps of a removal or a move (also as tray rows) that take a direct MCP entry out
    of a client's file."""
    kinds = {i: row["kind"] for row in change.rows or [] for i in row.get("steps", [])}
    return [
        step
        for i, step in enumerate(change.steps)
        if kinds.get(i, change.action) in TAKES_OUT
        and step.client in CLIENTS
        and step.edit is not None
        and step.edit.after is ABSENT
        and step.edit.key[-2:] in [(table, step.name) for table in SERVER_TABLES]
    ]


def _back_in(step: Step, inventory) -> Item | None:
    """The direct entry in the same file and scope that a step took out, when it is there
    again. A Claude Code local entry is also in the same project."""
    assert step.edit is not None
    edit = step.edit
    for item in inventory.items:
        same = (
            item.kind is ItemKind.MCP_SERVER
            and (item.client, item.name, item.scope) == (step.client, step.name, step.scope)
            and item.via_gateway is None
            and item.source.path is not None
            and os.path.realpath(item.source.path) == os.path.realpath(edit.path)
        )
        if same and (step.scope is not Scope.LOCAL or item.project == edit.key[1]):
            return item
    return None


def _came_back(entries: list[dict], records: dict, inventory) -> None:
    """Fill in each entry's `came_back`: the servers a verified change took out of a client that
    are there again, so something other than Kitden wrote them, {name, client, app}. `entries`
    are newest first: only the latest change still in place about a client's server counts, so
    one that added it again later means it did not come back."""
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        if entry["state"] not in ("verified", "undo_blocked"):
            continue  # nothing of it is in place
        change = records.get(entry["id"])
        taken = _taken_out(change) if change and entry["state"] == "verified" else []
        for step in taken:
            item = None if (step.client, step.name) in seen else _back_in(step, inventory)
            back = item and {"name": step.name, "client": step.client, "app": item.app}
            if back and back not in entry["came_back"]:
                entry["came_back"].append(back)
        seen |= {(s["client"], s["name"]) for s in entry["title_parts"]["steps"]}


def change_entries(log: list[dict], engine, inventory) -> list[dict]:
    """One entry per change id, newest first by the time of its first log line (when it was
    applied, or stopped). `log` is the change log, newest line first; `engine` holds the
    records (`engine.changes`)."""
    lines: dict[str, list[dict]] = {}
    for line in reversed(log):
        if line.get("id"):
            lines.setdefault(line["id"], []).append(line)
    entries = [
        _entry(change_id, own, engine.changes.get(change_id), inventory)
        for change_id, own in lines.items()
    ]
    # Made in the same second: the one logged later comes first.
    entries = sorted(reversed(entries), key=lambda e: e["time"] or "", reverse=True)
    _came_back(entries, engine.changes, inventory)
    return entries


def came_back(log: list[dict], engine, inventory) -> list[dict]:
    """Every server a change took out of a client that is back there now, newest change
    first, as the Changes page has them (`came_back`)."""
    return [back for entry in change_entries(log, engine, inventory) for back in entry["came_back"]]
