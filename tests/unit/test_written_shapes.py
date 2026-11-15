"""The shapes of the files the clients write: keys and value types, never values."""

import json
import shutil
import tomllib
from pathlib import Path

import pytest

from kitden.views.inventory import build_inventory
from tests.conftest import make_home, rows
from tests.contract.written import WATCHED, newest_fixture, parts, save, shape, unknown

ROOT = Path(__file__).resolve().parents[2]


def test_shape_keeps_keys_and_types_and_drops_values():
    entry = {"command": "npx", "args": ["-y", "x"], "env": {"A": "1", "B": "2"}, "on": True}
    assert shape(entry) == {"args": ["str"], "command": "str", "env": {"*": ["str"]}, "on": "bool"}


def test_a_new_key_a_missing_key_and_a_changed_type_are_each_named():
    stored = {"p": [{"command": "str", "args": ["str"]}]}
    assert unknown(stored, stored) == []
    (line,) = unknown({"p": [{"command": "str", "args": ["str"], "trust": "bool"}]}, stored)
    assert "p" in line and "new key" in line and "trust" in line
    # The log is read first: it points at the steps, never only "add a folder".
    assert "tests/fixtures/README.md" in line and "folder" not in line
    (line,) = unknown({"p": [{"command": "str"}]}, stored)
    assert "missing key" in line and "args" in line
    (line,) = unknown({"p": [{"command": "str", "args": "str"}]}, stored)
    assert "type" in line and "args" in line


def test_a_part_no_fixture_has_is_named():
    (line,) = unknown({"q": [{"a": "str"}]}, {})
    assert "q" in line and "no fixture has this part" in line


def test_a_part_the_client_no_longer_writes_is_named():
    stored = {"p": [{"command": "str"}], "q": [{"a": "str"}]}
    (line,) = unknown({"p": [{"command": "str"}]}, stored)
    assert "q" in line and "no longer writes this part" in line
    assert "how Kitden reads this part" in line


@pytest.mark.parametrize(
    "change",
    [
        lambda doc: doc.update(mcp_servers=doc.pop("mcpServers")),  # the key was renamed
        lambda doc: doc.update(mcpServers=list(doc["mcpServers"].values())),  # a map became a list
    ],
)
def test_a_part_that_moved_or_changed_its_kind_is_seen(change, tmp_path):
    fixture = newest_fixture("claude_code") / "home"
    home = tmp_path / "home"
    shutil.copytree(fixture, home)
    doc = json.loads((home / ".claude.json").read_text())
    change(doc)
    (home / ".claude.json").write_text(json.dumps(doc))
    found = unknown(parts(home, "claude_code"), parts(fixture, "claude_code"))
    assert any(".claude.json: mcpServers" in line and "no longer writes" in line for line in found)


def test_a_watched_file_that_is_gone_is_seen(tmp_path):
    fixture = newest_fixture("claude_code") / "home"
    home = tmp_path / "home"
    shutil.copytree(fixture, home)
    (home / ".claude/plugins/installed_plugins.json").unlink()
    found = unknown(parts(home, "claude_code"), parts(fixture, "claude_code"))
    assert any("installed_plugins.json" in line and "no longer writes" in line for line in found)


def test_keys_outside_the_watched_parts_do_not_count(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    server = {"type": "stdio", "command": "x", "args": []}
    (home / ".claude.json").write_text(json.dumps({"numStartups": 3, "mcpServers": {"a": server}}))
    found = parts(home, "claude_code")
    assert list(found) == [".claude.json: mcpServers.*"] and "numStartups" not in str(found)


def test_every_watched_part_is_in_the_newest_fixture_of_its_client():
    for client in WATCHED:
        stored = parts(newest_fixture(client) / "home", client)
        assert len(stored) == len(WATCHED[client]), (
            f"The newest fixture folder of {client} must hold every watched file, because the "
            "shape test compares with it. Put a fixture for one test in an older version's "
            f"folder, or give it every watched file. Found: {sorted(stored)}"
        )


def test_save_keeps_only_the_parts_kitden_reads(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    server = {"type": "stdio", "command": str(home / "bin/x"), "args": []}
    account = {"emailAddress": "someone@example.com", "accountUuid": "0000"}
    (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": account, "userID": "abc123", "mcpServers": {"a": server}})
    )
    save(home, "claude_code", tmp_path / "out")
    saved = (tmp_path / "out/claude_code/.claude.json").read_text()
    assert json.loads(saved) == {
        "mcpServers": {"a": {"type": "stdio", "command": "{HOME}/bin/x", "args": []}}
    }
    for word in ("oauthAccount", "someone@example.com", "userID", "abc123", str(home)):
        assert word not in saved


def test_save_keeps_only_the_watched_tables_of_codex(tmp_path):
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    (home / ".codex/config.toml").write_text(
        'model = "gpt-6"\n\n[mcp_servers.a]\ncommand = "x"\n\n'
        f'[projects."{home}/work"]\ntrust_level = "trusted"\n'
    )
    save(home, "codex", tmp_path / "out")
    saved = (tmp_path / "out/codex/.codex/config.toml").read_text()
    assert tomllib.loads(saved) == {"mcp_servers": {"a": {"command": "x"}}}
    assert "projects" not in saved and "model" not in saved


def test_save_writes_the_checkout_as_a_folder_in_the_home(tmp_path):
    home = tmp_path / "home"
    (home / ".claude/plugins").mkdir(parents=True)
    entry = {"source": {"source": "directory", "path": str(ROOT)}, "installLocation": str(ROOT)}
    (home / ".claude/plugins/known_marketplaces.json").write_text(json.dumps({"kitden": entry}))
    save(home, "claude_code", tmp_path / "out")
    saved = (tmp_path / "out/claude_code/.claude/plugins/known_marketplaces.json").read_text()
    assert "{HOME}/work/kitden" in saved
    assert str(ROOT) not in saved and str(ROOT.resolve()) not in saved


def test_kitden_reads_the_newest_fixtures(tmp_path):
    # The shape test trusts these folders, so Kitden must read what they hold.
    home = make_home(tmp_path, "claude_code/2.1.325", "codex/0.169.0")
    items = build_inventory(home).items
    found = {(client, kind, name) for client, kind, name, *_ in rows(items, home)}
    for client in ("claude_code", "codex"):
        for server in ("notes", "remote"):
            assert (client, "mcp_server", server) in found, (client, server, sorted(found))
        assert (client, "plugin", "kitden@kitden") in found, (client, sorted(found))
    assert ("claude_code", "marketplace", "kitden") in found, sorted(found)
