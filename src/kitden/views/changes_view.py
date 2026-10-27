"""The Changes page: one entry per change, from its log lines and the record Kitden keeps.

An entry says what the page shows: when, the title's parts, the state, the clients, the project,
the backup, what to do for it to take effect, the history, the tray rows, the request Redo…
previews again, and where "See it on the map" goes. Paths, backups and commands are only under
`technical`, for Technical details.
"""

from datetime import UTC, datetime
from pathlib import Path

from kitden.changes.batch import kitden_server
from kitden.changes.engine import PUT_BACK
from kitden.local_gateway.settings import CLIENT as KITDEN
from kitden.local_gateway.views import rule_of
from kitden.model import Change, ItemKind
from kitden.redact import masked_command, redact_text
from kitden.views.load_map import COLUMNS

# Steps whose client is not one the person uses: a registered gateway and Kitden's own settings.
NOT_CLIENTS = {"gateway", KITDEN}
# The states of a change that wrote something and still has it, or had it put back.
HAPPENED = {"verified", "undone", "undo_blocked"}
# A Library action; any other item opens on the Gateway.
LIBRARY_ACTIONS = ("plugin.", "skill.", "marketplace.")
TITLE_STEP = ("client", "name", "scope", "reaches", "keeps")


def _order(client: str) -> int:
    return COLUMNS.index(client) if client in COLUMNS else len(COLUMNS)


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
    return sorted((c for c in found if c and c not in NOT_CLIENTS), key=_order)


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
    found = sorted(notes, key=lambda found: _order(found[0]))
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
    several tray rows, a server counts only when every row is a gateway row about it."""
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
    ids = set().union(*(_item_ids(body) for body in request))
    if not ids:
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
    }


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
    return sorted(reversed(entries), key=lambda e: e["time"] or "", reverse=True)
