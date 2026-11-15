"""The shapes of the files the clients write: keys and value types, never values."""

import json
import tomllib

from tests.contract.written import WATCHED, newest_fixture, parts, save, shape, unknown


def test_shape_keeps_keys_and_types_and_drops_values():
    entry = {"command": "npx", "args": ["-y", "x"], "env": {"A": "1", "B": "2"}, "on": True}
    assert shape(entry) == {"args": ["str"], "command": "str", "env": {"*": ["str"]}, "on": "bool"}


def test_a_new_key_a_missing_key_and_a_changed_type_are_each_named():
    stored = {"p": [{"command": "str", "args": ["str"]}]}
    assert unknown(stored, stored) == []
    (line,) = unknown({"p": [{"command": "str", "args": ["str"], "trust": "bool"}]}, stored)
    assert "p" in line and "new key" in line and "trust" in line
    (line,) = unknown({"p": [{"command": "str"}]}, stored)
    assert "missing key" in line and "args" in line
    (line,) = unknown({"p": [{"command": "str", "args": "str"}]}, stored)
    assert "type" in line and "args" in line


def test_a_part_no_fixture_has_is_named():
    (line,) = unknown({"q": [{"a": "str"}]}, {})
    assert "q" in line and "no fixture has this part" in line


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
        assert len(stored) == len(WATCHED[client]), (client, sorted(stored))


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
