"""The preview tray's endpoints on the demo home: one change from many requests (Phase 3)."""

import json
import time
from contextlib import contextmanager
from pathlib import Path

from starlette.testclient import TestClient

from kitden.changes.batch import LEAVES, NEEDS, REMOVES, SAME_ID
from kitden.changes.client_cli import CommandResult
from kitden.demo import DemoRunner, build_demo_home, demo_build
from kitden.gateways import data_dir
from kitden.local_gateway.settings import SETTINGS_FILE, TOOLS_FILE
from kitden.web.app import create_app

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
RESTORED = "The original settings were restored."


@contextmanager
def _page(tmp_path, fail=None):
    """The page on the medium demo home. A client command that starts with `fail` fails."""
    home = build_demo_home(tmp_path / "demo", "medium")
    demo = DemoRunner(home)

    def run(command, cwd):
        if fail and command[: len(fail)] == fail:
            return CommandResult(1, "failed")
        return demo(command, cwd)

    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True, run=run)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        page.home = home
        yield page


def _ids(page, client):
    """The user-scope MCP entries of one client, id by name."""
    query = {"client": client, "kind": "mcp_server", "scope": "user"}
    return {i["name"]: i["id"] for i in page.get("/api/items", params=query).json()}


def _projects(page):
    """Project ids by folder, relative to the home."""
    paths = {Path(p["path"]): p["id"] for p in page.get("/api/projects").json()}
    return {str(path.relative_to(page.home)): pid for path, pid in paths.items()}


def _files(home):
    names = [".claude.json", ".codex/config.toml", ".cursor/mcp.json"]
    found = {n: (home / n).read_bytes() for n in names}
    found["settings"] = (data_dir(home) / SETTINGS_FILE).read_bytes()
    return found


def _remove(row_id, item_id, title="Remove it"):
    return {
        "id": row_id,
        "kind": "mcp.remove_direct",
        "title": title,
        "targets": [{"item": item_id}],
    }


def _rule(row_id, tool, state="off", project=None, server="files"):
    params = {"server": server, "tool": tool, "state": state, "project": project}
    return {"id": row_id, "kind": "gateway.rule", "title": f"Turn {state} {tool}", "params": params}


def _hold(home, server, tools):
    """The demo's Kitden gateway holds one more server, with no rules, and knows its tools."""
    for name, value in ((SETTINGS_FILE, None), (TOOLS_FILE, [{"name": t} for t in tools])):
        path = data_dir(home) / name
        data = json.loads(path.read_text())
        if value is None:
            data["servers"][server] = {"url": f"https://{server}.example.test/mcp"}
        else:
            data[server] = value
        path.write_text(json.dumps(data, indent=2))


def _move(row_id, item_id, title="Move it into the gateway"):
    return {
        "id": row_id,
        "kind": "gateway.move",
        "title": title,
        "targets": [{"item": item_id}],
        "params": {"gateway": "kitden"},
    }


def _check(page, *requests):
    answer = page.post("/api/batch/check", json={"requests": list(requests)}, headers=POST)
    assert answer.status_code == 200, answer.text
    return answer.json()


def _events(page):
    """The events published so far to a queue made by `page.app.state.events.subscribe()`."""
    queue = page.queue
    found = []
    while not queue.empty():
        event = queue.get_nowait()
        found.append(event if isinstance(event, tuple) else (event, None))
    return found


def _preview(page, *requests):
    return page.post("/api/batch/preview", json={"requests": list(requests)}, headers=POST)


def _apply(page, change_id, verb="apply"):
    return page.post(f"/api/changes/{change_id}/{verb}", headers=POST)


def test_two_requests_on_cursors_file_apply_as_one_change(tmp_path):
    with _page(tmp_path) as page:
        cursor = _ids(page, "cursor")
        answer = _preview(
            page,
            _remove("a", cursor["n8n"], "Remove n8n from Cursor"),
            _remove("b", cursor["browser-tools"], "Remove browser-tools from Cursor"),
        )
        assert answer.status_code == 200, answer.text
        change = answer.json()
        assert change["action"] == "batch" and change["state"] == "previewed"
        rows = change["rows"]
        assert [(r["id"], r["title"], r["steps"]) for r in rows] == [
            ("a", "Remove n8n from Cursor", [0]),
            ("b", "Remove browser-tools from Cursor", [1]),
        ]
        applied = _apply(page, change["id"])
        assert applied.status_code == 200, applied.text
        assert applied.json()["state"] == "verified"
        servers = json.loads((page.home / ".cursor/mcp.json").read_text())["mcpServers"]
        assert list(servers) == ["files"]


def test_a_failing_last_step_puts_every_file_back(tmp_path):
    with _page(tmp_path, fail=["claude", "mcp", "remove"]) as page:
        before = _files(page.home)
        answer = _preview(
            page,
            _remove("a", _ids(page, "cursor")["n8n"]),
            _remove("b", _ids(page, "codex")["docs"]),
            _remove("c", _ids(page, "claude_code")["docs"]),
        )
        assert answer.status_code == 200, answer.text
        applied = _apply(page, answer.json()["id"])
        assert applied.status_code == 500
        assert applied.json()["state"] == "restored"
        assert applied.json()["error"].endswith(RESTORED)
        assert _files(page.home) == before


def test_one_project_per_request_for_one_tool(tmp_path):
    with _page(tmp_path) as page:
        projects = _projects(page)
        folders = ["work/atlas", "work/atlas/web", "work/website"]
        requests = [_rule(f"p{n}", "read_file", project=projects[f]) for n, f in enumerate(folders)]
        answer = _preview(page, *requests)
        assert answer.status_code == 200, answer.text
        change = answer.json()
        assert [r["project"] for r in change["rows"]] == [str(page.home / f) for f in folders]
        assert _apply(page, change["id"]).json()["state"] == "verified"
        settings = json.loads((data_dir(page.home) / SETTINGS_FILE).read_text())
        for folder in folders:
            own = settings["rules"]["projects"][str(page.home / folder)]
            assert own["files"]["tools"]["read_file"] == "off"


def test_one_request_keeps_its_own_kind(tmp_path):
    with _page(tmp_path) as page:
        alone = _rule("a", "read_file")
        answer = _preview(page, alone)
        assert answer.status_code == 200, answer.text
        change = answer.json()
        assert change["action"] == "gateway.rule" and len(change["rows"]) == 1
        body = {"action": "gateway.rule", "targets": [], "params": alone["params"]}
        single = page.post("/api/changes/preview", json=body, headers=POST).json()
        assert change["rows"][0]["after"] == single["after"]
        assert change["rows"][0]["target"] == single["target"]


def test_a_refused_request_names_its_row(tmp_path):
    with _page(tmp_path) as page:
        log = page.get("/api/changes").json()
        answer = _preview(page, _rule("a", "read_file"), _rule("b", "x", server="nope"))
        assert answer.status_code == 422
        assert answer.json() == {"detail": "Choose a server in the Kitden gateway.", "row": "b"}
        assert page.get("/api/changes").json() == log


def test_a_bad_body_is_refused_in_plain_words(tmp_path):
    with _page(tmp_path) as page:
        untitled = {**_rule("a", "read_file"), "title": ""}
        assert _preview(page, untitled).json() == {"detail": NEEDS}
        twice = _preview(page, _rule("a", "read_file"), _rule("a", "write_file"))
        assert twice.status_code == 422 and twice.json() == {"detail": SAME_ID}


def test_remove_github_and_a_github_tool_are_refused_at_check(tmp_path):
    with _page(tmp_path) as page:
        _hold(page.home, "github", ["create_issue", "list_issues"])
        remove = {
            "id": "a",
            "kind": "gateway.remove",
            "title": "Remove github from the gateway",
            "params": {"server": "github"},
        }
        tool = {**_rule("b", "create_issue", server="github"), "title": "Turn off create_issue"}
        leaves = LEAVES.format(other="Remove github from the gateway", server="github")
        assert _check(page, remove, tool) == {"ok": False, "reason": leaves, "row": "b"}
        removes = REMOVES.format(other="Turn off create_issue", server="github")
        assert _check(page, tool, remove) == {"ok": False, "reason": removes, "row": "a"}
        answer = _preview(page, remove, tool)
        assert answer.status_code == 422
        assert answer.json() == {"detail": leaves, "row": "b"}


def test_check_says_ok_for_two_rules(tmp_path):
    with _page(tmp_path) as page:
        log = page.get("/api/changes").json()
        page.queue = page.app.state.events.subscribe()
        assert _check(page, _rule("a", "read_file"), _rule("b", "search_files")) == {"ok": True}
        assert [name for name, _ in _events(page)] == []
        assert page.get("/api/changes").json() == log


def test_check_names_the_new_row_when_nothing_would_change(tmp_path):
    with _page(tmp_path) as page:
        # The demo's gateway has delete_file of files off for all projects already.
        answer = _check(page, _rule("a", "read_file"), _rule("b", "delete_file"))
        nothing = "The Kitden gateway has this already. Nothing to change."
        assert answer == {"ok": False, "reason": nothing, "row": "b"}


def test_two_moves_from_cursor_join(tmp_path):
    with _page(tmp_path) as page:
        cursor = _ids(page, "cursor")
        a, b = _move("a", cursor["n8n"]), _move("b", cursor["browser-tools"])
        assert _check(page, a, b) == {"ok": True}
        answer = _preview(page, a, b)
        assert answer.status_code == 200, answer.text
        change = answer.json()
        entry = [
            i
            for i, s in enumerate(change["steps"])
            if (s["client"], s["name"]) == ("cursor", "kitden")
        ]
        assert len(entry) == 1
        assert all(entry[0] in row["steps"] for row in change["rows"])
        applied = _apply(page, change["id"])
        assert applied.status_code == 200, applied.text
        assert applied.json()["state"] == "verified"
        servers = json.loads((page.home / ".cursor/mcp.json").read_text())["mcpServers"]
        assert list(servers) == ["files", "kitden"]


def _progress(page):
    return [data for name, data in _events(page) if name == "change_progress"]


def test_progress_names_each_row(tmp_path):
    with _page(tmp_path) as page:
        answer = _preview(
            page,
            _remove("a", _ids(page, "cursor")["n8n"]),
            _remove("b", _ids(page, "codex")["docs"]),
            _rule("c", "read_file"),
        )
        change = answer.json()
        page.queue = page.app.state.events.subscribe()
        assert _apply(page, change["id"]).json()["state"] == "verified"
        seen = _progress(page)
        assert {p["row"] for p in seen} == {"a", "b", "c"}
        assert all(p["id"] == change["id"] for p in seen)
        assert seen[-1]["done"] == seen[-1]["total"] == 3


def test_undo_all_restores_every_file(tmp_path):
    with _page(tmp_path) as page:
        before = _files(page.home)
        cursor = _ids(page, "cursor")
        answer = _preview(
            page,
            _remove("a", cursor["n8n"]),
            _remove("b", cursor["browser-tools"]),
            _remove("c", _ids(page, "codex")["docs"]),
            _rule("d", "read_file"),
        )
        change = answer.json()
        assert _apply(page, change["id"]).json()["state"] == "verified"
        assert _files(page.home) != before
        page.queue = page.app.state.events.subscribe()
        undone = _apply(page, change["id"], "undo")
        assert undone.status_code == 200 and undone.json()["state"] == "undone"
        assert _files(page.home) == before
        # File entries come back together at the end: the last count names no row.
        last = _progress(page)[-1]
        assert last["done"] == last["total"] == 4 and last["row"] is None


def test_a_file_changed_before_apply_all_stops_all(tmp_path):
    with _page(tmp_path) as page:
        answer = _preview(
            page,
            _remove("a", _ids(page, "cursor")["n8n"]),
            _remove("b", _ids(page, "codex")["docs"]),
        )
        codex = (page.home / ".codex/config.toml").read_bytes()
        mcp = page.home / ".cursor/mcp.json"
        mcp.write_text(mcp.read_text().replace('"files"', '"my-files"'))
        edited = mcp.read_bytes()
        applied = _apply(page, answer.json()["id"])
        assert applied.status_code == 409 and applied.json()["state"] == "stale"
        assert (page.home / ".codex/config.toml").read_bytes() == codex
        assert mcp.read_bytes() == edited


def test_a_file_changed_before_undo_all_blocks_all(tmp_path):
    with _page(tmp_path) as page:
        answer = _preview(
            page,
            _remove("a", _ids(page, "cursor")["n8n"]),
            _remove("b", _ids(page, "codex")["docs"]),
        )
        change_id = answer.json()["id"]
        assert _apply(page, change_id).json()["state"] == "verified"
        codex = (page.home / ".codex/config.toml").read_bytes()
        mcp = page.home / ".cursor/mcp.json"
        mcp.write_text(mcp.read_text().replace('"files"', '"my-files"'))
        undone = _apply(page, change_id, "undo")
        assert undone.status_code == 409 and undone.json()["state"] == "undo_blocked"
        assert (page.home / ".codex/config.toml").read_bytes() == codex


def test_moves_in_a_batch_get_their_tools_read(tmp_path):
    with _page(tmp_path) as page:
        cursor = _ids(page, "cursor")
        change = _preview(
            page,
            _move("a", cursor["n8n"]),
            _move("b", cursor["browser-tools"]),
            _rule("c", "read_file"),
        ).json()
        page.queue = page.app.state.events.subscribe()
        assert _apply(page, change["id"]).json()["state"] == "verified"
        tools = data_dir(page.home) / TOOLS_FILE
        end = time.monotonic() + 5
        while not {"n8n", "browser-tools"} <= set(json.loads(tools.read_text())):
            assert time.monotonic() < end, "the moved servers' tools were not read"
            time.sleep(0.05)


def test_a_move_of_a_held_server_and_its_removal_are_refused(tmp_path):
    with _page(tmp_path) as page:
        # Cursor's files entry is now the one the gateway holds, so the move writes no server.
        path = page.home / ".cursor/mcp.json"
        data = json.loads(path.read_text())
        data["mcpServers"]["files"]["env"] = {"FILES_TOKEN": "DEMO_SECRET_FILES"}
        path.write_text(json.dumps(data, indent=2))
        page.post("/api/rescan", headers=POST)
        remove = {
            "id": "a",
            "kind": "gateway.remove",
            "title": "Remove files from the gateway",
            "params": {"server": "files"},
        }
        move = _move("b", _ids(page, "cursor")["files"])
        leaves = LEAVES.format(other="Remove files from the gateway", server="files")
        assert _check(page, remove, move) == {"ok": False, "reason": leaves, "row": "b"}
        assert _preview(page, remove, move).status_code == 422
