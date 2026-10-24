"""The preview tray's endpoints on the demo home: one change from many requests (Phase 3)."""

import json
from contextlib import contextmanager
from pathlib import Path

from starlette.testclient import TestClient

from kitden.changes.batch import NEEDS, SAME_ID
from kitden.changes.client_cli import CommandResult
from kitden.demo import DemoRunner, build_demo_home, demo_build
from kitden.gateways import data_dir
from kitden.local_gateway.settings import SETTINGS_FILE
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
