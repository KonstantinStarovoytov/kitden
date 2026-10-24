"""The preview tray as one change: requests, merged steps and their rows (Phase 3)."""

import re

import pytest

from kitden.changes.backup import ChangeStore
from kitden.changes.batch import NEEDS, SAME_ID, Part, combine, requests_in, same_write
from kitden.changes.client_cli import CommandResult
from kitden.changes.engine import Engine
from kitden.gateways import data_dir
from kitden.local_gateway.settings import SETTINGS_FILE, rule_step, settings_step
from kitden.model import ChangeState, KeychainItem


def _engine(tmp_path):
    return Engine(ChangeStore(tmp_path / "data"), run=lambda command, cwd: CommandResult(0, ""))


def test_requests_in_reads_each_change():
    body = {
        "requests": [
            {"id": "a", "kind": "gateway.rule", "title": "Turn off x", "params": {"server": "s"}},
            {"id": "b", "kind": "mcp.remove_direct", "title": "Remove y", "detail": "Only y."},
        ]
    }
    assert requests_in(body) == [
        {
            "id": "a",
            "kind": "gateway.rule",
            "title": "Turn off x",
            "detail": "",
            "targets": [],
            "params": {"server": "s"},
        },
        {
            "id": "b",
            "kind": "mcp.remove_direct",
            "title": "Remove y",
            "detail": "Only y.",
            "targets": [],
            "params": {},
        },
    ]


def test_requests_in_refuses_a_missing_title_or_a_repeated_id():
    one = {"id": "a", "kind": "gateway.rule", "title": "Turn off x"}
    for body in (
        {},
        {"requests": []},
        {"requests": ["a"]},
        {"requests": [{**one, "title": ""}]},
        {"requests": [{"id": "a", "kind": "gateway.rule"}]},
        {"requests": [{**one, "id": 3}]},
    ):
        with pytest.raises(ValueError, match=re.escape(NEEDS)):
            requests_in(body)
    with pytest.raises(ValueError, match=re.escape(SAME_ID)):
        requests_in({"requests": [one, one]})


def test_combine_keeps_tray_order_and_maps_each_part(tmp_path):
    s1, s2, s3 = (rule_step(tmp_path, None, "files", t, "off") for t in ("a", "b", "c"))
    steps, maps = combine([Part("a", "First", [s1, s2]), Part("b", "Second", [s3])])
    assert steps == [s1, s2, s3] and all(x is y for x, y in zip(steps, [s1, s2, s3], strict=True))
    assert maps == [[0, 1], [2]]


def test_an_identical_write_is_kept_once(tmp_path):
    path_a = settings_step(tmp_path, ("path",), "/bin", "PATH")
    path_b = settings_step(tmp_path, ("path",), "/bin", "PATH")
    own_a = rule_step(tmp_path, None, "files", "read_file", "off")
    own_b = rule_step(tmp_path, None, "files", "write_file", "off")
    steps, maps = combine([Part("a", "A", [path_a, own_a]), Part("b", "B", [path_b, own_b])])
    assert len(steps) == 3 and steps[0] is path_a
    assert maps == [[0, 1], [0, 2]]
    assert same_write(path_a, path_b)
    assert not same_write(path_a, settings_step(tmp_path, ("path",), "/usr/bin", "PATH"))
    secret = settings_step(tmp_path, ("path",), "/bin", "PATH")
    secret.keychain = [KeychainItem("files", "TOKEN", "x")]
    assert not same_write(path_a, secret)


def test_record_keeps_the_rows(tmp_path):
    home = tmp_path / "home"
    (data_dir(home) / SETTINGS_FILE).parent.mkdir(parents=True)
    (data_dir(home) / SETTINGS_FILE).write_text("{}")
    engine = _engine(tmp_path)
    steps = [
        rule_step(home, None, "files", "read_file", "off"),
        rule_step(home, None, "files", "write_file", "off"),
    ]
    change = engine.preview("batch", steps)
    rows = [
        {
            "id": "a",
            "kind": "gateway.rule",
            "title": "A",
            "detail": "",
            "project": None,
            "steps": [0],
        },
        {
            "id": "b",
            "kind": "gateway.rule",
            "title": "B",
            "detail": "",
            "project": None,
            "steps": [1],
        },
    ]
    change.rows = rows
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED
    again = _engine(tmp_path)
    assert again.changes[change.id].rows == rows
    assert again.store.entries()[0]["rows"] == rows
