import hashlib
import json

import pytest

from kitden.cli import main
from kitden.clients import version_cache
from kitden.clients.version_cache import VERSIONS_FILE, cached_version
from kitden.gateways import data_dir
from tests.conftest import fake_client_command, make_home, write_cursor_fixture_state
from tests.unit.test_context_view import LONG, claude_chat, skill

ALL = ("claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")


@pytest.fixture
def home(tmp_path, monkeypatch):
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


def test_scan_reads_versions_first_and_keeps_them(home, tmp_path, monkeypatch, capsys):
    codex = fake_client_command(tmp_path, "codex", "echo codex-cli 0.159.2")
    commands = {"codex": [str(codex), "--version"]}
    monkeypatch.setattr(version_cache, "version_command", commands.get)
    assert main(["scan", "--json", "--home", str(home)]) == 0
    clients = {c["id"]: c for c in json.loads(capsys.readouterr().out)["clients"]}
    assert clients["codex"]["version"] == "0.159.2"
    assert (data_dir(home) / VERSIONS_FILE).exists()
    assert cached_version(home, "codex") == "0.159.2"


# The summary a person reads


@pytest.fixture
def bare(tmp_path):
    home = tmp_path / "bare"
    for root in (".claude", ".codex", ".cursor"):
        (home / root).mkdir(parents=True)
    return home


def _summary(home, capsys) -> list[str]:
    assert main(["scan", "--home", str(home)]) == 0
    return capsys.readouterr().out.splitlines()


def test_scan_says_which_skills_the_last_chat_cut(bare, capsys):
    for name in ("alpha", "beta", "gamma", "delta"):
        skill(bare / ".claude/skills", name, LONG[:1000])
    claude_chat(
        bare,
        {"alpha": LONG[:1000], "beta": LONG[:1000], "gamma": None, "delta": None},
        model="claude-sonnet-4-6",
        at="2026-11-07T12:00:00Z",
    )
    lines = _summary(bare, capsys)
    said = (
        "  Skill list: In your last chat on Nov 7, 2 of 4 skills showed only a name. "
        "The agent may not have used them."
    )
    claude, codex = lines.index("Claude Code: found (unknown version)"), lines.index(said)
    assert claude < codex < next(i for i, line in enumerate(lines) if line.startswith("Codex:"))


def test_scan_says_so_when_it_cannot_tell(bare, capsys):
    skill(bare / ".claude/skills", "alpha", "Does alpha.")
    skill(bare / ".cursor/skills", "alpha", "Does alpha.")
    lines = _summary(bare, capsys)
    assert (
        "  Skill list: No Claude Code chat yet. Open one chat, and Kitden will show what "
        "Claude Code sent."
    ) in lines
    assert (
        "  Skill list: Kitden cannot see what Cursor sends, so it cannot tell if your skills fit."
    ) in lines
    assert "  Skill list: There is nothing to fit." in lines  # Codex has no skills


def test_scan_ends_by_saying_it_changed_nothing(bare, capsys):
    before = _snapshot(bare)
    assert _summary(bare, capsys)[-1] == (
        "Nothing was changed: scan only reads your agents' settings."
    )
    assert _snapshot(bare) == before
