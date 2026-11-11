"""A client may keep any value under any key in a later version: a scan must not fail on it."""

import copy
import json
import tomllib

import pytest
import tomlkit

from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.clients.codex import CodexAdapter
from kitden.clients.cursor import CursorAdapter
from tests.conftest import cursor_db, cursor_state_rows, make_home, write_cursor_state

ODD = (None, True, 7, "odd", [], ["odd"], [{}], {}, {"odd": {"odd": 1}})
CLIENTS = {
    "claude_code/2.1.283": ClaudeCodeAdapter,
    "codex/0.159.2": CodexAdapter,
    "cursor/3.21.16": CursorAdapter,
}


def _places(value, at=()):
    """Every place in a parsed settings file, as a path of keys and list positions."""
    if not isinstance(value, dict | list):
        return
    for key, child in value.items() if isinstance(value, dict) else enumerate(value):
        yield (*at, key)
        yield from _places(child, (*at, key))


def _with(data, place, odd):
    changed = copy.deepcopy(data)
    target = changed
    for key in place[:-1]:
        target = target[key]
    target[place[-1]] = odd
    return changed


@pytest.mark.parametrize("fixture", CLIENTS)
def test_a_scan_survives_an_odd_value_under_any_key(fixture, tmp_path, no_version):
    home = make_home(tmp_path, fixture)
    adapter = CLIENTS[fixture](home, read_version=no_version)
    failed = []
    files = [p for p in home.rglob("*") if p.suffix in (".json", ".toml") and p.is_file()]
    for path in sorted(files):
        text = path.read_text()
        toml = path.suffix == ".toml"
        data = tomllib.loads(text) if toml else json.loads(text)
        for place in _places(data):
            for odd in ODD:
                if toml and odd is None:
                    continue  # TOML has no null
                changed = _with(data, place, odd)
                path.write_text(tomlkit.dumps(changed) if toml else json.dumps(changed))
                try:
                    adapter.scan()
                except Exception as error:  # noqa: BLE001 - the test lists every failure
                    failed.append((path.name, place, odd, repr(error)))
        path.write_text(text)
    assert failed == [], "\n".join(map(str, failed))


def test_a_cursor_scan_survives_an_odd_value_in_any_state_row(tmp_path, no_version):
    home = make_home(tmp_path, "cursor/3.21.16")
    adapter = CursorAdapter(home, read_version=no_version)
    failed = []
    stored = cursor_state_rows(home)
    for place in _places(stored):
        for odd in ODD:
            cursor_db(home).unlink(missing_ok=True)
            write_cursor_state(home, _with(stored, place, odd))
            try:
                adapter.scan()
            except Exception as error:  # noqa: BLE001 - the test lists every failure
                failed.append((place, odd, repr(error)))
    assert failed == [], "\n".join(map(str, failed))
