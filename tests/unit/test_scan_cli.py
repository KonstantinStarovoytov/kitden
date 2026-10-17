import hashlib
import json

import pytest

import agentsetup.clients.base as base
from agentsetup.cli import main
from tests.conftest import make_home, write_cursor_fixture_state

ALL = ("claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    home = make_home(tmp_path, *ALL)
    write_cursor_fixture_state(home)
    return home


def _snapshot(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.is_symlink()
    }


def test_scan_json_lists_items_from_all_clients_without_secrets(home, capsys):
    assert main(["scan", "--json", "--home", str(home)]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    names = {(i["client"], i["name"]) for i in data["items"]}
    assert {("claude_code", "github"), ("codex", "neon"), ("cursor", "Neon")} <= names
    assert {c["id"] for c in data["clients"]} >= {"claude_code", "codex", "cursor"}
    assert "SENTINEL_SECRET" not in out


def test_scan_exits_3_but_still_prints_when_a_file_cannot_be_read(home, capsys):
    (home / ".claude.json").write_text("{ broken")
    assert main(["scan", "--json", "--home", str(home)]) == 3
    data = json.loads(capsys.readouterr().out)
    assert [p["unknown_reason"] for p in data["problems"]] == ["parse_error"]


def test_scan_changes_no_file(home, capsys):
    before = _snapshot(home)
    main(["scan", "--json", "--home", str(home)])
    assert _snapshot(home) == before
