"""Example tests for JSON and TOML edits: missing parents, empty objects, comments, bad files."""

import pytest

from kitden.changes import json_splice, toml_edit
from kitden.changes.json_splice import ABSENT, UnrecognizedFormatError

GATEWAY = {"type": "http", "url": "http://127.0.0.1:12008/mcp"}


def test_json_adds_missing_parent_objects():
    text = '{\n  "theme": "dark"\n}\n'
    edited = json_splice.set_value(text, ("mcpServers", "gateway"), GATEWAY)
    assert edited == (
        '{\n  "theme": "dark",\n  "mcpServers": {\n    "gateway": {\n'
        '      "type": "http",\n      "url": "http://127.0.0.1:12008/mcp"\n    }\n  }\n}\n'
    )


def test_json_adds_to_an_empty_object():
    edited = json_splice.set_value('{"mcpServers": {}}', ("mcpServers", "gateway"), {"url": "u"})
    assert json_splice.get_value(edited, ("mcpServers", "gateway")) == {"url": "u"}


def test_json_creates_a_missing_file_body():
    edited = json_splice.set_value("", ("mcpServers", "gateway"), {"url": "u"})
    assert json_splice.get_value(edited, ("mcpServers", "gateway")) == {"url": "u"}


def test_json_keeps_keys_with_dots_and_slashes():
    text = '{"projects": {"/Users/a/my.app": {"mcpServers": {"db": {"command": "x"}}}}}'
    path = ("projects", "/Users/a/my.app", "mcpServers", "db")
    edited = json_splice.delete_value(text, path)
    assert edited == '{"projects": {"/Users/a/my.app": {"mcpServers": {}}}}'


def test_json_with_comments_is_refused():
    with pytest.raises(UnrecognizedFormatError):
        json_splice.get_value('{\n  // note\n  "a": 1\n}', ("a",))


def test_json_top_level_must_be_an_object():
    with pytest.raises(UnrecognizedFormatError):
        json_splice.set_value("[1, 2]", ("a",), 1)


def test_toml_keeps_comments_and_adds_a_table():
    text = '# top\nmodel = "x"  # keep\n\n[mcp_servers.neon]\nurl = "https://neon"  # neon\n'
    edited = toml_edit.set_value(
        text, ("mcp_servers", "gateway"), {"url": "u", "bearer_token_env_var": "GW_KEY"}
    )
    assert edited.startswith(text)
    assert toml_edit.get_value(edited, ("mcp_servers", "gateway")) == {
        "url": "u",
        "bearer_token_env_var": "GW_KEY",
    }


def test_toml_adds_a_table_to_a_file_without_mcp_servers():
    text = 'model = "x"\n'
    edited = toml_edit.set_value(text, ("mcp_servers", "gateway"), {"url": "u"})
    assert edited == 'model = "x"\n\n[mcp_servers.gateway]\nurl = "u"\n'
    assert toml_edit.delete_value(edited, ("mcp_servers", "gateway")) == text


def test_toml_missing_value_is_absent():
    assert toml_edit.get_value('model = "x"\n', ("mcp_servers", "x")) is ABSENT


def test_bad_toml_is_refused():
    with pytest.raises(UnrecognizedFormatError):
        toml_edit.get_value("model = = 1", ("model",))


SKILLS = (
    '# mine\n\n[[skills.config]]\npath = "/a/SKILL.md"  # first\nenabled = true  # on\n\n'
    '[mcp_servers.docs]\ncommand = "docs"\n'
)


def test_toml_changes_a_picked_table_in_place():
    key = ("skills", "config", toml_edit.pick("/a/SKILL.md"))
    assert toml_edit.get_value(SKILLS, key) == {"path": "/a/SKILL.md", "enabled": True}
    edited = toml_edit.set_value(SKILLS, key, {"path": "/a/SKILL.md", "enabled": False})
    assert edited == SKILLS.replace("enabled = true", "enabled = false")


def test_toml_adds_a_picked_table_after_the_others_and_takes_it_out():
    key = ("skills", "config", toml_edit.pick("/b/SKILL.md"))
    assert toml_edit.get_value(SKILLS, key) is ABSENT
    edited = toml_edit.set_value(SKILLS, key, {"path": "/b/SKILL.md", "enabled": False})
    assert edited == SKILLS.replace(
        "# on\n\n", '# on\n\n[[skills.config]]\npath = "/b/SKILL.md"\nenabled = false\n\n'
    )
    assert toml_edit.delete_value(edited, key) == SKILLS
    # A file with no skill tables gets its first one; taking it out gives the file back.
    alone = toml_edit.set_value("x = 1\n", key, {"path": "/b/SKILL.md", "enabled": False})
    assert alone == 'x = 1\n\n[[skills.config]]\npath = "/b/SKILL.md"\nenabled = false\n'
    assert toml_edit.delete_value(alone, key) == "x = 1\n"
