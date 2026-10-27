"""The Changes page's entries: one per change, from the log lines and the records (Phase 7)."""

import json
from datetime import datetime
from types import SimpleNamespace

from kitden.gateways import data_dir
from kitden.views.changes_view import change_entries
from tests.unit.test_api_batch import (
    POST,
    _apply,
    _hold,
    _ids,
    _page,
    _preview,
    _projects,
    _remove,
    _rule,
)

RESTORED = "The original settings were restored."
NO_ENGINE = SimpleNamespace(changes={})
NO_ITEMS = SimpleNamespace(items=[])


def _line(change_id, time, state, **fields):
    return {
        "id": change_id,
        "time": time,
        "action": "mcp.remove_direct",
        "state": state,
        "error": None,
        "target": None,
        "rows": None,
        "steps": [{"client": "codex", "name": "neon", "scope": "user", "path": "/h/.codex/c"}],
        **fields,
    }


def _entries(*lines):
    """Entries from log lines given oldest first; the log reads newest first."""
    return change_entries(list(reversed(lines)), NO_ENGINE, NO_ITEMS)


def _day(time):
    return datetime.fromisoformat(time).astimezone().date().isoformat()


def test_one_entry_per_change_with_its_history_in_order():
    a, b = "20261026T091500Z-aaaaaa", "20261027T140200Z-bbbbbb"
    entries = _entries(
        _line(a, "2026-10-26T09:15:30+00:00", "verified"),
        _line(b, "2026-10-27T14:02:10+00:00", "verified"),
        _line(a, "2026-10-27T15:00:00+00:00", "undone"),
    )
    # Newest first by when each change was made; the later Undo does not move it.
    assert [e["id"] for e in entries] == [b, a]
    old = entries[1]
    assert (old["time"], old["state"]) == ("2026-10-26T09:15:30+00:00", "undone")
    assert old["day"] == _day("2026-10-26T09:15:30+00:00")
    # The preview time is the change's id; then each logged state in order.
    assert old["history"] == [
        {"time": "2026-10-26T09:15:00+00:00", "state": "previewed"},
        {"time": "2026-10-26T09:15:30+00:00", "state": "verified"},
        {"time": "2026-10-27T15:00:00+00:00", "state": "undone"},
    ]
    assert old["title_parts"]["action"] == "mcp.remove_direct"
    assert old["title_parts"]["steps"] == [
        {"client": "codex", "name": "neon", "scope": "user", "reaches": None, "keeps": None}
    ]
    assert old["clients"] == ["codex"] and old["project"] is None


def test_a_several_row_change_is_titled_by_its_rows():
    rule = {"kind": "gateway.rule", "detail": ""}
    rows = [
        {**rule, "id": "r1", "title": "Turn off slow", "project": "/h/w", "steps": [0]},
        {**rule, "id": "r2", "title": "Turn off fast", "project": None, "steps": [1]},
    ]
    [entry] = _entries(
        _line(
            "20261027T140200Z-cccccc",
            "2026-10-27T14:02:10+00:00",
            "verified",
            action="batch",
            rows=rows,
        )
    )
    # The page titles it "Turn off slow and 1 more" (parts.js changeTitle); Details list each.
    assert entry["rows"] == [{"title": "Turn off slow"}, {"title": "Turn off fast"}]
    assert entry["title_parts"]["action"] == "batch"
    assert entry["title_parts"]["rows"] == entry["rows"]


def test_backup_words_follow_the_state():
    cases = [
        ("verified", None, "kept"),
        ("undo_blocked", "/h/x changed after the change was applied", "kept"),
        ("undone", None, "back"),
        ("restored", f"it failed. {RESTORED}", "back"),
        ("restored", "it failed. `claude mcp add` failed; neon was not put back.", "kept"),
        ("stale", "/h/x changed since preview", "none"),
        ("cancelled", None, "none"),
    ]
    for n, (state, error, words) in enumerate(cases):
        made = f"20261027T1402{n:02}Z-dddddd"
        line = _line(made, "2026-10-27T14:03:00+00:00", state, error=error)
        assert _entries(line)[0]["backup"] == words, state


def test_takes_effect_is_per_client_from_restart_notes():
    steps = [
        {"client": "codex", "name": "a", "scope": "user", "restart_note": "Restart Codex."},
        {"client": "codex", "name": "b", "scope": "user", "restart_note": "Restart Codex."},
        {"client": "kitden", "name": "a", "scope": "user", "restart_note": None},
        {"client": "claude_code", "name": "a", "scope": "user", "restart_note": "New session."},
    ]
    line = _line("20261027T140200Z-eeeeee", "2026-10-27T14:02:10+00:00", "verified", steps=steps)
    [entry] = _entries(line)
    assert entry["takes_effect"] == [
        {"client": "claude_code", "note": "New session.", "login": None},
        {"client": "codex", "note": "Restart Codex.", "login": None},
    ]
    assert entry["clients"] == ["claude_code", "codex"]
    # A log-in note goes with its client, beside the restart note.
    login = {"client": "cursor", "name": "gw", "scope": "user", "restart_note": "Restart Cursor."}
    login["login_note"] = "Open the gateway and sign in."
    line = _line("20261027T140230Z-efefef", "2026-10-27T14:02:40+00:00", "verified", steps=[login])
    assert _entries(line)[0]["takes_effect"] == [
        {"client": "cursor", "note": "Restart Cursor.", "login": "Open the gateway and sign in."}
    ]
    # A change that wrote nothing needs nothing done.
    stale = _line("20261027T140300Z-ffffff", "2026-10-27T14:03:10+00:00", "stale", steps=steps)
    assert _entries(stale)[0]["takes_effect"] == []


def _log(home):
    path = data_dir(home) / "changes.log"
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_a_new_change_keeps_its_request_and_an_old_one_has_no_redo(tmp_path):
    with _page(tmp_path) as page:
        projects = _projects(page)
        rows = [_rule("a", "read_file"), _rule("b", "write_file", project=projects["work/website"])]
        rows[1]["picked"] = projects["work/website"]
        change = _preview(page, *rows).json()
        assert _apply(page, change["id"]).json()["state"] == "verified"
        # The tray rows' bodies, as the tray sends them again: Redo… adds them back.
        request = [
            {"action": "gateway.rule", "targets": [], "params": rows[0]["params"], "picked": None},
            {
                "action": "gateway.rule",
                "targets": [],
                "params": rows[1]["params"],
                "picked": projects["work/website"],
            },
        ]
        record = data_dir(page.home) / "changes" / change["id"] / "change.json"
        assert json.loads(record.read_text())["request"] == request
        assert _log(page.home)[-1]["request"] == request
        entry = page.get("/api/changes").json()[0]
        assert (entry["id"], entry["redo"]) == (change["id"], request)
        # After Undo, the tray takes the bodies back as they are.
        assert _apply(page, change["id"], "undo").json()["state"] == "undone"
        again = _preview(
            page,
            *[
                {
                    "id": f"r{n}",
                    "kind": b["action"],
                    "title": "Again",
                    "targets": b["targets"],
                    "params": b["params"],
                    "picked": b["picked"],
                }
                for n, b in enumerate(entry["redo"])
            ],
        )
        assert again.status_code == 200, again.text
        page.post(f"/api/changes/{again.json()['id']}/cancel", headers=POST)
        # A line from before Kitden kept requests reads as before, with no Redo….
        old = {k: v for k, v in _log(page.home)[-2].items() if k != "request"}
        old["id"] = "20261001T090000Z-0a0a0a"
        with (data_dir(page.home) / "changes.log").open("a") as log:
            log.write(json.dumps(old) + "\n")
        entries = page.get("/api/changes").json()
        gone = next(e for e in entries if e["id"] == old["id"])
        assert gone["redo"] is None and gone["state"] == "verified"
        assert gone["title_parts"]["action"] == "batch"


def test_map_target_and_gone_for_a_removed_item(tmp_path):
    with _page(tmp_path) as page:
        rule = _preview(page, _rule("a", "read_file")).json()
        _apply(page, rule["id"])
        n8n = _ids(page, "cursor")["n8n"]
        removal = _preview(page, _remove("b", n8n)).json()
        _apply(page, removal["id"])

        def map_of(change_id):
            return next(e for e in page.get("/api/changes").json() if e["id"] == change_id)["map"]

        tool = {"view": "gateway", "sel": "tool:files/read_file", "gone": False}
        assert map_of(rule["id"]) == tool
        assert map_of(removal["id"]) == {"view": "gateway", "sel": None, "gone": True}
        _apply(page, removal["id"], "undo")
        assert map_of(removal["id"]) == {"view": "gateway", "sel": "mcp_server:n8n", "gone": False}


def test_map_target_of_several_rows(tmp_path):
    with _page(tmp_path) as page:
        two = _preview(page, _rule("a", "read_file"), _rule("b", "write_file")).json()
        _apply(page, two["id"])
        n8n = _ids(page, "cursor")["n8n"]
        mixed = _preview(page, _rule("c", "search_files"), _remove("d", n8n)).json()
        _apply(page, mixed["id"])
        maps = {e["id"]: e["map"] for e in page.get("/api/changes").json()}
    # Every row is about files: the server. A rule and a removal touch two things: none.
    assert maps[two["id"]] == {"view": "gateway", "sel": "mcp_server:files", "gone": False}
    assert maps[mixed["id"]] is None


def test_a_kitden_gateway_server_that_left_is_gone(tmp_path):
    with _page(tmp_path) as page:
        _hold(page.home, "extra", ["ping"])
        row = {"id": "a", "kind": "gateway.remove", "title": "Remove extra"}
        removal = _preview(page, {**row, "params": {"server": "extra"}})
        assert removal.status_code == 200, removal.text
        assert _apply(page, removal.json()["id"]).json()["state"] == "verified"
        entry = page.get("/api/changes").json()[0]
    assert entry["map"] == {"view": "gateway", "sel": "mcp_server:extra", "gone": True}


def test_a_tray_change_keeps_the_titles_shown_at_apply(tmp_path):
    with _page(tmp_path) as page:
        n8n = _ids(page, "cursor")["n8n"]
        rows = [_rule("a", "read_file"), _remove("b", n8n, title="New change")]
        change = _preview(page, *rows).json()
        titles = ["Turn off read_file of files", "Remove n8n from Cursor ghp_SENTINEL_SECRET_ROW1"]
        applied = page.post(
            f"/api/changes/{change['id']}/apply", json={"titles": titles}, headers=POST
        )
        assert applied.json()["state"] == "verified"
        record = data_dir(page.home) / "changes" / change["id"] / "change.json"
        kept = [r["title"] for r in json.loads(record.read_text())["rows"]]
        assert kept == ["Turn off read_file of files", "Remove n8n from Cursor [secret]"]
        assert [r["title"] for r in _log(page.home)[-1]["rows"]] == kept
        assert page.get("/api/changes").json()[0]["rows"] == [{"title": t} for t in kept]
        # A list that does not fit the rows changes nothing.
        other = _preview(page, _rule("c", "write_file"), _rule("d", "search_files")).json()
        page.post(f"/api/changes/{other['id']}/apply", json={"titles": ["One"]}, headers=POST)
        record = data_dir(page.home) / "changes" / other["id"] / "change.json"
        kept = [r["title"] for r in json.loads(record.read_text())["rows"]]
        assert kept == ["Turn off write_file", "Turn off search_files"]


def _without(entry, key):
    return {k: v for k, v in entry.items() if k != key}


def test_entries_hold_no_paths_outside_technical(tmp_path):
    with _page(tmp_path) as page:
        projects = _projects(page)
        rule = _rule("a", "read_file", project=projects["work/website"])
        rows = [rule, _remove("b", _ids(page, "cursor")["n8n"])]
        change = _preview(page, *rows).json()
        assert _apply(page, change["id"]).json()["state"] == "verified"
        single = _preview(page, _rule("c", "write_file", project=projects["work/website"])).json()
        assert _apply(page, single["id"]).json()["state"] == "verified"
        entries = page.get("/api/changes").json()
    home = str(page.home)
    assert len(entries) == 2
    for entry in entries:
        assert home not in json.dumps(_without(entry, "technical")), entry["id"]
    by_id = {e["id"]: e for e in entries}
    tray, alone = by_id[change["id"]], by_id[single["id"]]
    assert all(p.startswith(home) for p in tray["technical"]["paths"])
    assert {p.rsplit("/", 1)[-1] for p in tray["technical"]["paths"]} >= {"mcp.json"}
    backups = tray["technical"]["backups"]
    assert backups and all(b.startswith(home) for b in backups)
    assert alone["project"] == "website"
    assert alone["title_parts"]["target"]["project"] == "website"
    assert alone["title_parts"]["rule"]["project"] == "website"
