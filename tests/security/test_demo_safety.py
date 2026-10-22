"""The demo starts nothing and goes nowhere (spec Part 1, Done): changes run with every program
start and every connection refused, `localhost` included."""

import json
import re
import socket
import subprocess

import pytest
from starlette.testclient import TestClient

from kitden.changes.actions import KITDEN_GATEWAY
from kitden.cli import main
from kitden.gateways import data_dir
from kitden.views.library import KINDS
from tests.unit.test_cli import _demo_run
from tests.unit.test_demo_mode import POST, demo_page, preview, scan_done, until


@pytest.fixture
def no_programs(monkeypatch):
    started = []

    class Refused(subprocess.Popen):
        def __init__(self, args, *rest, **options):
            started.append(args)
            raise AssertionError(f"the demo started a program: {args}")

    monkeypatch.setattr(subprocess, "Popen", Refused)
    return started


@pytest.fixture
def no_connections(monkeypatch):
    tried = []

    def refuse(*args, **kwargs):
        tried.append(args)
        raise OSError("the demo stays offline")

    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    return tried


def _item(page, client, name):
    items = page.get("/api/items?kind=mcp_server").json()
    return next(i for i in items if (i["client"], i["name"]) == (client, name))


def _heard(queue, event):
    """Whether the page sent `event` since `queue` subscribed; reads what came so far."""
    while not queue.empty():
        if queue.get_nowait() == event:
            return True
    return False


def test_an_add_a_tool_switch_and_undo_run_no_program_and_go_nowhere(
    tmp_path, no_programs, no_connections
):
    with demo_page(tmp_path) as page:
        home = page.home
        files = [home / ".claude.json", data_dir(home) / "gateway.json"]
        before = {p: p.read_bytes() for p in files}
        tools = _item(page, "cursor", "browser-tools")
        add = preview(page, "mcp.add", [{"client": "claude_code"}], {"item": tools["id"]})
        applied = page.post(f"/api/changes/{add['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        assert "browser-tools" in json.loads((home / ".claude.json").read_text())["mcpServers"]
        atlas = next(
            p["id"]
            for p in page.get("/api/projects").json()
            if p["path"] == str(home / "work/atlas")
        )
        rule = preview(
            page,
            "gateway.rule",
            [],
            {"server": "files", "tool": "read_file", "state": "off", "project": atlas},
        )
        applied = page.post(f"/api/changes/{rule['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        # Rescan and the refresh button each ask the held servers once; wait for each pass.
        events = page.app.state.events.subscribe()
        assert page.post("/api/rescan", headers=POST).status_code == 200
        until(lambda: _heard(events, "gateway_tools"))
        assert page.post("/api/gateway/tools/refresh", headers=POST).status_code == 202
        until(lambda: _heard(events, "gateway_tools"))
        for change in (rule, add):
            undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
            assert undone["state"] == "undone"
        assert {p: p.read_bytes() for p in files} == before
    assert no_programs == [] and no_connections == []


def test_moving_servers_in_and_strict_mode_start_nothing(tmp_path, no_programs, no_connections):
    with demo_page(tmp_path) as page:
        analytics = _item(page, "codex", "analytics")
        move = preview(
            page, "gateway.move", [{"item": analytics["id"]}], {"gateway": KITDEN_GATEWAY}
        )
        strict = preview(page, "gateway.strict", [], {"server": "files", "state": "on"})
        for change in (move, strict):
            done = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
            assert done["state"] == "verified"
        until(lambda: page.get("/api/gateway/tools?server=analytics").json()["tools"])
        for change in (strict, move):
            undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
            assert undone["state"] == "undone"
    assert no_programs == [] and no_connections == []


def test_kitden_demo_as_it_starts_runs_no_program_and_goes_nowhere(
    monkeypatch, capsys, no_programs, no_connections
):
    """The app as `kitden demo` wires it: watched folders, a first scan after listening."""
    seen = {}

    def server(app, host, port, **options):
        home = seen["home"]
        post = {"Origin": f"http://{host}:{port}", "X-Tool-Request": "1"}
        link = re.search(r"http://127\.0\.0\.1:\d+/\?token=\S+", capsys.readouterr().out)
        with TestClient(app, base_url=f"http://{host}:{port}") as page:
            page.get(link.group(0))
            until(lambda: scan_done(page), seconds=20)
            tools = _item(page, "cursor", "browser-tools")
            body = {"action": "mcp.add", "targets": [{"client": "claude_code"}]}
            add = page.post(
                "/api/changes/preview", json={**body, "params": {"item": tools["id"]}}, headers=post
            ).json()
            applied = page.post(f"/api/changes/{add['id']}/apply", headers=post).json()
            assert applied["state"] == "verified"
            # A skill added outside Kitden: the watcher sees it and the page reads again.
            skill = home / ".claude/skills/note-taker/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: note-taker\ndescription: Takes notes.\n---\n")
            until(
                lambda: "note-taker" in [i["name"] for i in page.get("/api/items").json()],
                seconds=20,
            )
            for kind in KINDS:
                assert page.get(f"/api/library?kind={kind}").status_code == 200
            undone = page.post(f"/api/changes/{add['id']}/undo", headers=post).json()
            assert undone["state"] == "undone"

    _demo_run(monkeypatch, seen, server)
    assert main(["demo", "--no-browser"]) == 0
    assert not seen["home"].parent.exists()
    assert no_programs == [] and no_connections == []
