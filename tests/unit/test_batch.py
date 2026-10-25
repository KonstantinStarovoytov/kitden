"""The preview tray as one change: requests, merged steps and their rows (Phase 3)."""

import json
import re

import pytest

from kitden.changes.backup import ChangeStore
from kitden.changes.batch import (
    LEAVES,
    NEEDS,
    REMOVES,
    SAME,
    SAME_ID,
    TWO_GATEWAYS,
    Part,
    clash,
    combine,
    first_clash,
    requests_in,
    same_write,
    step_rows,
)
from kitden.changes.client_cli import CommandResult
from kitden.changes.engine import Engine, NothingToChangeError
from kitden.changes.json_splice import ABSENT
from kitden.gateways import data_dir
from kitden.local_gateway.settings import (
    SETTINGS_FILE,
    remove_server_steps,
    rule_step,
    settings_step,
)
from kitden.model import (
    GATEWAY_CLIENT,
    ChangeState,
    FileEdit,
    GatewayEdit,
    KeychainItem,
    Scope,
    Step,
)


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
            "picked": None,
        },
        {
            "id": "b",
            "kind": "mcp.remove_direct",
            "title": "Remove y",
            "detail": "Only y.",
            "targets": [],
            "params": {},
            "picked": None,
        },
    ]


def test_requests_in_keeps_each_picked():
    one = {"kind": "gateway.rule", "title": "Turn off x"}
    body = {
        "requests": [
            {**one, "id": "a", "picked": "p1"},
            {**one, "id": "b"},
            {**one, "id": "c", "picked": 7},
        ]
    }
    assert [r["picked"] for r in requests_in(body)] == ["p1", None, None]


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


def _hold(home, servers):
    path = data_dir(home) / SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"servers": servers}))


def _json_step(path, key, after):
    edit = FileEdit(path=str(path), fmt="json", key=key, after=after)
    return Step(client="cursor", scope=Scope.USER, name=key[-1], edit=edit)


def _gateway_step(gateway_id, name):
    edit = GatewayEdit(gateway_id=gateway_id, url=f"http://{gateway_id}/mcp", name=name, server={})
    return Step(
        client=GATEWAY_CLIENT, scope=Scope.USER, name=name, gateway=edit, mechanism="gateway_api"
    )


def test_removing_a_server_clashes_with_a_rule_for_it(tmp_path):
    _hold(tmp_path, {"github": {"url": "https://github.example.test/mcp"}})
    remove = Part("a", "Remove github from the gateway", remove_server_steps(tmp_path, "github"))
    rule = Part(
        "b", "Turn off create_issue", [rule_step(tmp_path, None, "github", "create_issue", "off")]
    )
    assert clash([remove], rule) == LEAVES.format(
        other="Remove github from the gateway", server="github"
    )
    assert clash([rule], remove) == REMOVES.format(other="Turn off create_issue", server="github")
    other = Part(
        "c", "Turn off read_file", [rule_step(tmp_path, "/p", "files", "read_file", "off")]
    )
    assert clash([remove], other) is None


def test_the_same_entry_twice_clashes(tmp_path):
    on = Part("a", "Turn on read_file", [rule_step(tmp_path, None, "files", "read_file", "on")])
    off = Part("b", "Turn off read_file", [rule_step(tmp_path, None, "files", "read_file", "off")])
    again = Part("c", "Turn on read_file", [rule_step(tmp_path, None, "files", "read_file", "on")])
    assert clash([on], off) == SAME.format(other="Turn on read_file", what="setting")
    assert clash([on], again) is None


def test_one_entry_inside_another_clashes(tmp_path):
    path = tmp_path / "mcp.json"
    whole = Part("a", "Remove x", [_json_step(path, ("mcpServers", "x"), ABSENT)])
    inner = Part("b", "Change x", [_json_step(path, ("mcpServers", "x", "env"), {"A": "1"})])
    assert clash([whole], inner) == SAME.format(other="Remove x", what="setting")
    assert clash([inner], whole) == SAME.format(other="Change x", what="setting")
    elsewhere = Part(
        "c", "Remove x there", [_json_step(tmp_path / "b.json", ("mcpServers", "x"), ABSENT)]
    )
    assert clash([whole], elsewhere) is None


def test_two_registered_gateways_clash():
    one = Part("a", "Move neon into MetaMCP", [_gateway_step("g1", "neon")])
    two = Part("b", "Move docs into Obot", [_gateway_step("g2", "docs")])
    same = Part("c", "Move neon into MetaMCP", [_gateway_step("g1", "neon")])
    other = Part("d", "Move docs into MetaMCP", [_gateway_step("g1", "docs")])
    assert clash([one], two) == TWO_GATEWAYS.format(other="Move neon into MetaMCP")
    assert clash([one], same) == SAME.format(other="Move neon into MetaMCP", what="server")
    assert clash([one], other) is None


def test_first_clash_names_the_part_that_cannot_join(tmp_path):
    a = Part("a", "Turn on read_file", [rule_step(tmp_path, None, "files", "read_file", "on")])
    b = Part("b", "Turn off write_file", [rule_step(tmp_path, None, "files", "write_file", "off")])
    c = Part("c", "Turn off read_file", [rule_step(tmp_path, None, "files", "read_file", "off")])
    assert first_clash([a, b]) is None
    assert first_clash([a, b, c]) == (SAME.format(other="Turn on read_file", what="setting"), "c")


def test_engine_check_keeps_no_change(tmp_path):
    home = tmp_path / "home"
    _hold(home, {"files": {"command": "npx"}})
    engine = _engine(tmp_path)
    engine.check([rule_step(home, None, "files", "read_file", "off")])
    assert engine.changes == {}
    with pytest.raises(NothingToChangeError):
        engine.check([rule_step(home, None, "files", "read_file", None)])
    assert engine.changes == {}


def test_step_rows_names_the_first_row_of_a_shared_step():
    rows = [{"id": "a", "steps": [0, 1]}, {"id": "b", "steps": [0, 2]}]
    assert step_rows(rows) == {0: "a", 1: "a", 2: "b"}


def test_removing_a_server_clashes_with_a_move_that_needs_it(tmp_path):
    # A move into the gateway of a server it holds already writes no server step.
    _hold(tmp_path, {"files": {"command": "npx"}})
    remove = Part("a", "Remove files from the gateway", remove_server_steps(tmp_path, "files"))
    cursor = _json_step(tmp_path / "mcp.json", ("mcpServers", "files"), ABSENT)
    move = Part("b", "Move files into the gateway", [cursor], frozenset({"files"}))
    assert clash([remove], move) == LEAVES.format(
        other="Remove files from the gateway", server="files"
    )
    assert clash([move], remove) == REMOVES.format(
        other="Move files into the gateway", server="files"
    )
