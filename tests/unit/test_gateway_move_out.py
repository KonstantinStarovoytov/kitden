"""Move a server out of the Kitden gateway into one client: put it back there, then remove it
from the gateway, as one change."""

import json
import tomllib

import pytest

from kitden.changes.batch import LEAVES, REMOVES
from kitden.gateways import data_dir
from kitden.local_gateway.settings import SETTINGS_FILE, load_settings, load_tools, save_tools
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_api_changes import FakeClaude, _files
from tests.unit.test_gateway_remove import HELD
from tests.unit.test_local_gateway_views import (
    FILES,
    POST,
    add_entry,
    add_kitden,
    hold,
    page_for,
    tool,
)

TITLE = "Move files out of the gateway into Codex"


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def move_out(page, server, *clients):
    body = {
        "action": "gateway.move_out",
        "targets": [{"client": c} for c in clients],
        "params": {"server": server},
    }
    return page.post("/api/changes/preview", json=body, headers=POST)


def test_move_out_puts_the_entry_in_the_client_and_takes_it_out_of_the_gateway(home):
    website = str(home / "work/website")
    rules = {
        "global": {
            "files": {"server": "off", "mode": "strict", "tools": {"search": "off"}},
            "other": {"server": "on"},
        },
        "projects": {website: {"files": {"server": "on"}}},
    }
    hold(home, {"files": FILES, "other": {"command": "x"}}, rules)
    save_tools(home, "files", [tool("search")])
    add_kitden(home, "claude_code", "cursor")
    path = data_dir(home) / SETTINGS_FILE
    before = (_files(home), path.read_bytes())
    with page_for(home, run=FakeClaude(home)) as page:
        answer = move_out(page, "files", "codex")
        assert answer.status_code == 200, answer.text
        change = answer.json()
        # The client's entry first, then the gateway's entry and its rules.
        assert [(s["client"], s["name"]) for s in change["steps"]] == [
            ("codex", "files"),
            ("kitden", "files"),
            ("kitden", "files"),
            ("kitden", "files"),
        ]
        assert [s["diff"].splitlines()[0] for s in change["steps"][1:]] == [
            "servers > files",
            "rules > global > files",
            f"rules > projects > {website} > files",
        ]
        assert "SENTINEL" not in answer.text
        # Codex loads it from its own file. The clients that used the gateway lose it.
        assert change["after"] == [
            {
                "client": "codex",
                "state": "on",
                "word": "On",
                "note": "This writes a secret into ~/.codex/config.toml.",
            },
            {
                "client": "claude_code",
                "state": "off",
                "word": "Removed",
                "note": "Only Codex then loads files. Open sessions refuse its tools at once. "
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
        config = tomllib.loads((home / ".codex/config.toml").read_text())
        assert config["mcp_servers"]["files"] == FILES
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
    assert (_files(home), path.read_bytes()) == before


def test_move_out_into_a_client_that_uses_the_gateway_does_not_say_twice(home):
    hold(home, {"files": {"command": "npx", "args": ["files-mcp"]}})
    add_kitden(home, "claude_code", "cursor")
    before = (_files(home), (data_dir(home) / SETTINGS_FILE).read_bytes())
    with page_for(home, run=FakeClaude(home)) as page:
        change = move_out(page, "files", "claude_code").json()
        # No secret in the entry, so Claude Code adds it with its own command.
        assert change["steps"][0]["command"] is not None
        assert change["after"] == [
            {"client": "claude_code", "state": "on", "word": "On"},
            {
                "client": "cursor",
                "state": "off",
                "word": "Removed",
                "note": "Only Claude Code then loads files. Open sessions refuse its tools at "
                "once. Undo brings it back.",
            },
        ]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        written = json.loads((home / ".claude.json").read_text())["mcpServers"]["files"]
        assert written["command"] == "npx"
        assert load_settings(home)["servers"] == {}
        page.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert (_files(home), (data_dir(home) / SETTINGS_FILE).read_bytes()) == before


def test_move_out_says_which_other_clients_keep_their_own_entry(home):
    hold(home, {"files": FILES})
    add_kitden(home, "cursor")
    add_entry(home, "cursor", "files", {"command": "npx", "args": ["files-mcp"]})
    with page_for(home, run=FakeClaude(home)) as page:
        change = move_out(page, "files", "codex").json()
    note = "Cursor still has its own entry for files. Open sessions refuse its tools at once."
    assert change["after"][1] == {
        "client": "cursor",
        "state": "off",
        "word": "Removed",
        "note": f"{note} Undo brings it back.",
    }


def test_move_out_with_no_gateway_client_has_only_the_note(home):
    hold(home, {"files": {"command": "npx"}})
    with page_for(home) as page:
        change = move_out(page, "files", "cursor").json()
    assert change["after"] == [
        {"client": "cursor", "state": "on", "word": "On"},
        {"note": "Only Cursor then loads files. Undo brings it back."},
    ]


def test_move_out_says_a_keychain_secret_becomes_plain(home, fake_keychain):
    items = json.dumps({"kitden files/FILES_TOKEN": "SENTINEL_SECRET_FILES"})
    fake_keychain.write_text(items)
    hold(home, {"files": HELD})
    add_kitden(home, "cursor")
    with page_for(home, run=FakeClaude(home)) as page:
        change = move_out(page, "files", "claude_code").json()
        assert "SENTINEL" not in json.dumps(change)
        assert change["steps"][0]["command"] is None  # the value is written directly
        assert "[secret]" in change["steps"][0]["diff"]
        assert change["after"][0]["note"] == "This writes a secret into ~/.claude.json."
        assert "Its secrets stay in your Keychain under kitden." in change["after"][1]["note"]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        assert "SENTINEL" not in page.get("/api/changes").text
    # The client file holds the Keychain's value; the item stays where it was.
    written = json.loads((home / ".claude.json").read_text())["mcpServers"]["files"]
    assert written == {"type": "stdio", **FILES}
    assert load_settings(home)["servers"] == {}
    assert fake_keychain.read_text() == items


def test_move_out_without_the_keychain_item_changes_nothing(home, fake_keychain):
    hold(home, {"files": HELD})
    before = (_files(home), (data_dir(home) / SETTINGS_FILE).read_bytes())
    with page_for(home) as page:
        answer = move_out(page, "files", "claude_code")
    assert (answer.status_code, answer.json()["detail"]) == (
        422,
        "Kitden could not read a secret of files from the Keychain.",
    )
    assert (_files(home), (data_dir(home) / SETTINGS_FILE).read_bytes()) == before


def test_move_out_refuses_a_client_that_has_the_name(home):
    hold(home, {"github": {"url": "https://api.githubcopilot.com/mcp/"}})
    before = (_files(home), (data_dir(home) / SETTINGS_FILE).read_bytes())
    with page_for(home) as page:
        answer = move_out(page, "github", "claude_code")
    assert (answer.status_code, answer.json()["detail"]) == (422, "Claude Code already has github.")
    assert (_files(home), (data_dir(home) / SETTINGS_FILE).read_bytes()) == before


def test_move_out_refuses_an_unknown_server(home):
    with page_for(home) as page:
        answer = move_out(page, "nope", "codex")
    assert (answer.status_code, answer.json()["detail"]) == (
        422,
        "Choose a server in the Kitden gateway.",
    )


def test_move_out_needs_one_client(home):
    hold(home, {"files": FILES})
    with page_for(home) as page:
        none = move_out(page, "files")
        two = move_out(page, "files", "codex", "cursor")
    for answer in (none, two):
        assert (answer.status_code, answer.json()["detail"]) == (
            422,
            "Pick one client to move it into.",
        )


def test_move_out_clashes_with_a_rule_row_of_the_same_server(home):
    hold(home, {"files": FILES})
    save_tools(home, "files", [tool("search")])
    out = {
        "id": "a",
        "kind": "gateway.move_out",
        "title": TITLE,
        "targets": [{"client": "codex"}],
        "params": {"server": "files"},
    }
    rule = {
        "id": "b",
        "kind": "gateway.rule",
        "title": "Turn off search",
        "params": {"server": "files", "tool": "search", "state": "off", "project": None},
    }

    def check(*rows):
        return page.post("/api/batch/check", json={"requests": list(rows)}, headers=POST).json()

    with page_for(home) as page:
        leaves = LEAVES.format(other=TITLE, server="files")
        assert check(out, rule) == {"ok": False, "reason": leaves, "row": "b"}
        removes = REMOVES.format(other="Turn off search", server="files")
        assert check(rule, out) == {"ok": False, "reason": removes, "row": "a"}
        assert check(out) == {"ok": True}


def test_move_out_joins_a_tray_with_a_rule_of_another_server(home):
    hold(home, {"files": FILES, "docs": {"url": "https://docs.example.com/mcp"}})
    save_tools(home, "docs", [tool("read")])
    add_kitden(home, "cursor")
    path = data_dir(home) / SETTINGS_FILE
    before = (_files(home), path.read_bytes())
    out = {
        "id": "a",
        "kind": "gateway.move_out",
        "title": TITLE,
        "targets": [{"client": "codex"}],
        "params": {"server": "files"},
    }
    rule = {
        "id": "b",
        "kind": "gateway.rule",
        "title": "Turn off read",
        "params": {"server": "docs", "tool": "read", "state": "off", "project": None},
    }
    with page_for(home) as page:
        answer = page.post("/api/batch/preview", json={"requests": [out, rule]}, headers=POST)
        assert answer.status_code == 200, answer.text
        change = answer.json()
        first = change["rows"][0]
        assert (first["kind"], first["after"][0]["client"]) == ("gateway.move_out", "codex")
        assert first["after"][1]["client"] == "cursor"
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        assert list(load_settings(home)["servers"]) == ["docs"]
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
    assert (_files(home), path.read_bytes()) == before
