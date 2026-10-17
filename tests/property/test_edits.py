"""Property tests for file edits (T037, research R7).

- A no-op edit keeps the bytes.
- Adding an entry and then deleting it gives back the original bytes.
- Only the target entry changes: every other entry reads back the same.
"""

import json

import pytest
import tomlkit
from hypothesis import given, settings
from hypothesis import strategies as st

from agentsetup.changes import json_splice, toml_edit
from agentsetup.changes.json_splice import ABSENT

names = st.from_regex(r"[a-z][a-z0-9_-]{0,11}", fullmatch=True)
scalars = st.one_of(
    st.booleans(),
    st.integers(-1000, 1000),
    st.text(st.characters(codec="utf-8", exclude_categories=["Cs"]), max_size=12),
)
entries = st.dictionaries(names, scalars, min_size=1, max_size=4)
servers = st.dictionaries(names, entries, min_size=1, max_size=5)


def _json_file(data: dict, indent: int) -> str:
    return json.dumps(data, indent=indent, ensure_ascii=False) + "\n"


def _toml_file(data: dict) -> str:
    return '# my settings\nmodel = "x"  # keep me\n\n' + tomlkit.dumps({"mcp_servers": data})


EDITORS = [
    pytest.param(
        json_splice,
        lambda d, i: _json_file({"mcpServers": d, "other": 1}, i),
        "mcpServers",
        id="json",
    ),
    pytest.param(toml_edit, lambda d, i: _toml_file(d), "mcp_servers", id="toml"),
]


@pytest.mark.parametrize(("editor", "make", "root"), EDITORS)
@settings(max_examples=60, deadline=None)
@given(data=servers, indent=st.sampled_from([2, 4]))
def test_setting_an_entry_to_its_current_value_keeps_the_bytes(editor, make, root, data, indent):
    text = make(data, indent)
    name = sorted(data)[0]
    assert editor.set_value(text, (root, name), editor.get_value(text, (root, name))) == text


@pytest.mark.parametrize(("editor", "make", "root"), EDITORS)
@settings(max_examples=60, deadline=None)
@given(data=servers, new=entries, indent=st.sampled_from([2, 4]))
def test_adding_then_deleting_an_entry_restores_the_bytes(editor, make, root, data, new, indent):
    text = make(data, indent)
    added = editor.set_value(text, (root, "Added-Entry"), new)
    assert editor.get_value(added, (root, "Added-Entry")) == new
    assert editor.delete_value(added, (root, "Added-Entry")) == text


@pytest.mark.parametrize(("editor", "make", "root"), EDITORS)
@settings(max_examples=60, deadline=None)
@given(data=servers, indent=st.sampled_from([2, 4]))
def test_deleting_an_entry_changes_nothing_else(editor, make, root, data, indent):
    text = make(data, indent)
    target = sorted(data)[-1]
    edited = editor.delete_value(text, (root, target))
    assert editor.get_value(edited, (root, target)) is ABSENT
    for name in data:
        if name != target:
            assert editor.get_value(edited, (root, name)) == data[name]


@pytest.mark.parametrize(("editor", "make", "root"), EDITORS)
@settings(max_examples=60, deadline=None)
@given(data=servers, new=entries, indent=st.sampled_from([2, 4]))
def test_replacing_an_entry_changes_nothing_else(editor, make, root, data, new, indent):
    text = make(data, indent)
    target = sorted(data)[0]
    edited = editor.set_value(text, (root, target), new)
    assert editor.get_value(edited, (root, target)) == new
    for name in data:
        if name != target:
            assert editor.get_value(edited, (root, name)) == data[name]
