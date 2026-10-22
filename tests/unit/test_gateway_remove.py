"""Remove a server from the Kitden gateway, or put it back in a client (spec 3.3)."""

import json
import tomllib

import pytest

from kitden.gateways import data_dir
from kitden.local_gateway.settings import SETTINGS_FILE, load_settings, load_tools, save_tools
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_api_changes import FakeClaude
from tests.unit.test_local_gateway_views import (
    FILES,
    POST,
    add_entry,
    add_kitden,
    hold,
    page_for,
    tool,
)

NOTE = "files is then in no client. Undo brings it back."


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def _remove(page, server):
    body = {"action": "gateway.remove", "targets": [], "params": {"server": server}}
    return page.post("/api/changes/preview", json=body, headers=POST)


def test_removing_a_held_server_takes_its_rules_and_undo_restores(home):
    website = str(home / "work/website")
    rules = {
        "global": {
            "files": {"server": "off", "mode": "strict", "tools": {"search": "off", "read": "on"}},
            "other": {"server": "on"},
        },
        "projects": {website: {"files": {"server": "on"}}},
    }
    hold(home, {"files": FILES, "other": {"command": "x"}}, rules)
    save_tools(home, "files", [tool("search")])
    add_kitden(home, "claude_code", "cursor")
    path = data_dir(home) / SETTINGS_FILE
    before = path.read_bytes()
    with page_for(home) as page:
        answer = _remove(page, "files")
        assert answer.status_code == 200, answer.json()
        change = answer.json()
        assert [(s["client"], s["name"]) for s in change["steps"]] == [("kitden", "files")] * 3
        assert [s["diff"].splitlines()[0] for s in change["steps"]] == [
            "servers > files",
            "rules > global > files",
            f"rules > projects > {website} > files",
        ]
        assert "SENTINEL" not in answer.text
        assert change["after"] == [
            {
                "client": "claude_code",
                "state": "off",
                "word": "Removed",
                "note": "files is then in no client. Open sessions refuse its tools at once. "
                "Undo brings it back.",
            },
            {"client": "cursor", "state": "off", "word": "Removed"},
        ]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        saved = load_settings(home)
        assert saved["servers"] == {"other": {"command": "x"}}
        assert saved["rules"] == {"global": {"other": {"server": "on"}}, "projects": {website: {}}}
        assert "files" in load_tools(home)  # found data stays
        rows = page.get("/api/library?kind=mcp_server").json()["rows"]
        assert not any(r["name"] == "files" for r in rows)
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
    assert path.read_bytes() == before


def test_removing_without_a_connected_client_only_has_the_note(home):
    hold(home, {"files": FILES})
    with page_for(home) as page:
        change = _remove(page, "files").json()
    assert change["after"] == [{"note": NOTE}]


def test_removing_says_which_clients_still_load_it_directly(home):
    hold(home, {"files": FILES})
    add_entry(home, "cursor", "files", {"command": "npx", "args": ["files-mcp"]})
    with page_for(home) as page:
        change = _remove(page, "files").json()
    note = "Cursor still has its own entry for files. Undo brings it back."
    assert change["after"] == [{"note": note}]


def test_removing_an_unknown_server_is_refused(home):
    with page_for(home) as page:
        answer = _remove(page, "nope")
    assert (answer.status_code, answer.json()["detail"]) == (
        422,
        "Choose a server in the Kitden gateway.",
    )


def _put_back(page, server, *clients):
    body = {
        "action": "gateway.put_back",
        "targets": [{"client": c} for c in clients],
        "params": {"server": server},
    }
    return page.post("/api/changes/preview", json=body, headers=POST)


def test_putting_a_server_back_writes_the_clients_entry_and_says_about_the_secret(home):
    hold(home, {"files": {**FILES, "startup_timeout_sec": 45}})
    add_kitden(home, "claude_code")
    original = (home / ".claude.json").read_bytes()
    with page_for(home, run=FakeClaude(home)) as page:
        change = _put_back(page, "files", "claude_code").json()
        assert [(s["client"], s["name"]) for s in change["steps"]] == [("claude_code", "files")]
        assert change["steps"][0]["command"].startswith("claude mcp add-json -s user files ")
        assert "[secret]" in change["steps"][0]["command"]
        assert "[secret]" in change["steps"][0]["diff"]
        assert "SENTINEL" not in json.dumps(change)
        assert change["after"] == [
            {
                "client": "claude_code",
                "state": "on",
                "word": "Loads",
                "note": "This writes a secret into ~/.claude.json. Claude Code then loads files "
                "twice: directly and through the Kitden gateway. Remove it from the gateway to "
                "keep one.",
            }
        ]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        assert "SENTINEL" not in json.dumps(applied)
        written = json.loads((home / ".claude.json").read_text())["mcpServers"]["files"]
        assert written == {"type": "stdio", **FILES}
        assert load_settings(home)["servers"]["files"] == {**FILES, "startup_timeout_sec": 45}
        assert "SENTINEL" not in page.get("/api/changes").text
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
    assert (home / ".claude.json").read_bytes() == original
    # The change record next to the backup keeps only the masked command.
    records = list((data_dir(home) / "changes").glob("*/change.json"))
    assert records and all("SENTINEL" not in json.dumps(
        [s["command"] for s in json.loads(r.read_text())["steps"]]
    ) for r in records)


def test_put_back_in_codex_and_cursor_keeps_each_clients_shape(home):
    remote = {"url": "https://api.invalid/mcp", "headers": {"X": "1"}}
    hold(home, {"files": {**FILES, "startup_timeout_sec": 45}, "api": remote})
    with page_for(home) as page:
        codex = _put_back(page, "files", "codex").json()
        assert "http_headers" not in codex["steps"][0]["diff"]  # a local entry
        applied = page.post(f"/api/changes/{codex['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        config = tomllib.loads((home / ".codex/config.toml").read_text())
        assert config["mcp_servers"]["files"] == {**FILES, "startup_timeout_sec": 45}
        assert "http_headers" in _put_back(page, "api", "codex").json()["steps"][0]["diff"]
        cursor = _put_back(page, "api", "cursor").json()
        # Every header value counts as a secret; no kitden entry in Cursor, so no "twice".
        assert cursor["after"] == [
            {
                "client": "cursor",
                "state": "on",
                "word": "Loads",
                "note": "This writes a secret into ~/.cursor/mcp.json.",
            }
        ]
        applied = page.post(f"/api/changes/{cursor['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        written = json.loads((home / ".cursor/mcp.json").read_text())["mcpServers"]["api"]
        assert written == remote


def test_put_back_is_refused_when_the_client_has_the_name(home):
    hold(home, {"github": {"url": "https://api.githubcopilot.com/mcp/"}})
    before = (home / ".claude.json").read_bytes()
    with page_for(home) as page:
        answer = _put_back(page, "github", "claude_code")
    assert (answer.status_code, answer.json()["detail"]) == (422, "Claude Code already has github.")
    assert (home / ".claude.json").read_bytes() == before


def test_put_back_needs_a_client_and_a_held_server(home):
    hold(home, {"files": FILES})
    with page_for(home) as page:
        none = _put_back(page, "files")
        unknown = _put_back(page, "nope", "cursor")
        codex = _put_back(page, "files", "claude_desktop_code_tab")
    assert none.json()["detail"] == "Choose at least one client"
    assert unknown.json()["detail"] == "Choose a server in the Kitden gateway."
    assert codex.json()["detail"] == "claude_desktop_code_tab cannot take an MCP entry"


def test_put_back_refuses_a_project_folder_codex_or_cursor_cannot_fill(home):
    hold(home, {"p": {"command": "npx", "args": ["p-mcp", "${workspaceFolder}"]}})
    with page_for(home) as page:
        codex = _put_back(page, "p", "codex")
        cursor = _put_back(page, "p", "cursor")
    assert (codex.status_code, codex.json()["detail"]) == (
        422,
        "Codex cannot fill in the project folder this server needs.",
    )
    assert (cursor.status_code, cursor.json()["detail"]) == (
        422,
        "Cursor cannot fill in the project folder this server needs.",
    )


# Secrets in the Keychain (spec 5.1) -------------------------------------------------------

HELD = {**FILES, "env": {"FILES_TOKEN": {"keychain": "files/FILES_TOKEN"}}}


def test_put_back_writes_the_value_from_the_keychain(home, fake_keychain):
    fake_keychain.write_text(json.dumps({"kitden files/FILES_TOKEN": "SENTINEL_SECRET_FILES"}))
    hold(home, {"files": HELD})
    with page_for(home, run=FakeClaude(home)) as page:
        change = _put_back(page, "files", "claude_code").json()
        assert "SENTINEL" not in json.dumps(change)
        assert "[secret]" in change["steps"][0]["command"]
        assert change["after"][0]["note"].startswith("This writes a secret into ~/.claude.json.")
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
    written = json.loads((home / ".claude.json").read_text())["mcpServers"]["files"]
    assert written == {"type": "stdio", **FILES}
    assert load_settings(home)["servers"]["files"] == HELD


def test_put_back_without_the_keychain_item_is_refused(home, fake_keychain):
    hold(home, {"files": HELD})
    before = (home / ".claude.json").read_bytes()
    with page_for(home) as page:
        answer = _put_back(page, "files", "claude_code")
    assert (answer.status_code, answer.json()["detail"]) == (
        422,
        "Kitden could not read a secret of files from the Keychain.",
    )
    assert (home / ".claude.json").read_bytes() == before


def test_removing_a_held_server_leaves_its_keychain_items(home, fake_keychain):
    items = json.dumps({"kitden files/FILES_TOKEN": "SENTINEL_SECRET_FILES"})
    fake_keychain.write_text(items)
    hold(home, {"files": HELD})
    with page_for(home) as page:
        change = _remove(page, "files").json()
        assert change["after"] == [
            {
                "note": "files is then in no client. Its secrets stay in your Keychain under "
                "kitden. Undo brings it back."
            }
        ]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
    assert fake_keychain.read_text() == items


def _to_keychain(page, server):
    body = {"action": "gateway.keychain", "targets": [], "params": {"server": server}}
    return page.post("/api/changes/preview", json=body, headers=POST)


MOVE_NOTE = "The secrets of files go to your Keychain; the settings file keeps references."


def test_a_held_server_with_plain_secrets_says_so_and_can_move_them(home, fake_keychain):
    docs = {"url": "https://docs.example.com/mcp"}
    hold(home, {"files": FILES, "docs": docs, "kept": {**HELD}})
    path = data_dir(home) / SETTINGS_FILE
    before = path.read_bytes()

    def plain(page):
        servers = page.get("/api/gateway-view").json()["gateways"][0]["servers"]
        return {s["name"]: s["plain_secrets"] for s in servers}

    with page_for(home) as page:
        assert plain(page) == {"docs": False, "files": True, "kept": False}
        change = _to_keychain(page, "files").json()
        assert [(s["client"], s["name"]) for s in change["steps"]] == [("kitden", "files")]
        assert "SENTINEL" not in json.dumps(change)
        assert change["after"] == [{"note": MOVE_NOTE}]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        ref = {"keychain": "files/FILES_TOKEN"}
        assert load_settings(home)["servers"]["files"] == {**FILES, "env": {"FILES_TOKEN": ref}}
        stored = {"kitden files/FILES_TOKEN": "SENTINEL_SECRET_FILES"}
        assert json.loads(fake_keychain.read_text()) == stored
        assert plain(page)["files"] is False
        assert "SENTINEL" not in page.get("/api/changes").text
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
    assert path.read_bytes() == before
    assert json.loads(fake_keychain.read_text()) == {}
    assert "SENTINEL" not in (data_dir(home) / "changes.log").read_text()


def test_moving_secrets_warns_of_an_item_already_in_the_keychain(home, fake_keychain):
    fake_keychain.write_text(json.dumps({"kitden files/FILES_TOKEN": "old"}))
    hold(home, {"files": FILES})
    with page_for(home) as page:
        change = _to_keychain(page, "files").json()
    replaced = "files/FILES_TOKEN is already in your Keychain; its value will be replaced."
    assert change["after"] == [{"note": f"{replaced} {MOVE_NOTE}"}]


def test_moving_secrets_needs_a_held_server_with_a_plain_secret(home, fake_keychain):
    hold(home, {"kept": HELD})
    with page_for(home) as page:
        none = _to_keychain(page, "kept")
        unknown = _to_keychain(page, "nope")
    assert (none.status_code, none.json()["detail"]) == (
        422,
        "kept keeps no secret in the settings file.",
    )
    assert (unknown.status_code, unknown.json()["detail"]) == (
        422,
        "Choose a server in the Kitden gateway.",
    )
