"""The shapes of the files the clients write: keys and value types, never values."""

import json

from tests.contract.written import WATCHED, newest_fixture, parts, shape, unknown


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
