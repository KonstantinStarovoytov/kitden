"""The demo starts nothing and goes nowhere (spec Part 1, Done): changes run with every program
start and every connection refused, `localhost` included."""

import json
import socket
import subprocess

import pytest

from kitden.changes.actions import KITDEN_GATEWAY
from kitden.gateways import data_dir
from tests.unit.test_demo_mode import POST, demo_page, preview, until


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
        assert page.post("/api/rescan", headers=POST).status_code == 200
        assert page.post("/api/gateway/tools/refresh", headers=POST).status_code == 202
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
