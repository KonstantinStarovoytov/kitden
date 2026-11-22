import hashlib
import json
from pathlib import Path

import pytest

from kitden import cli
from kitden.cli import main
from kitden.clients import version_cache
from kitden.clients.version_cache import VERSIONS_FILE, cached_version
from kitden.context.rules import codex_rule
from kitden.gateways import data_dir
from kitden.model import ItemKind
from kitden.system import claude_desktop_dir
from kitden.views import words
from tests.conftest import fake_client_command, make_home, write_cursor_fixture_state
from tests.unit.test_context_view import (
    CODEX_A,
    CODEX_B,
    CODEX_C,
    LONG,
    a_budget,
    before_the_chat,
    chosen_home,
    claude_chat,
    codex_chat,
    codex_home,
    rule_skills,
    skill,
    window_for,
    write_json,
)
from tests.unit.test_findings import KITDEN, add_entry, hold_github

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


# The tests run outside any project, so the scan names the folder of the chat it read.
ELSEWHERE = "    That chat was in /work/a."


def _after(lines: list[str], line: str) -> list[str]:
    """The lines that follow `line`, up to the next one that is not indented further."""
    start = lines.index(line) + 1
    end = next((i for i in range(start, len(lines)) if not lines[i].startswith("    ")), len(lines))
    return lines[start:end]


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
    assert _after(lines, said) == [ELSEWHERE, "    gamma, delta"]
    assert lines[-1] == "To fix: kitden open"
    # The count beside it says why the two numbers can differ, in one line of the terminal.
    counted = "  Skills: 4 found; a chat has one project's, plus ones Claude Code adds"
    assert lines[lines.index(said) - 1] == counted
    assert len(counted.replace("4", "999")) <= 80


def test_scan_names_the_first_few_skills_and_counts_the_rest(bare, capsys):
    names = [f"plugin-dev:skill-number-{n}" for n in range(1, 10)]
    claude_chat(bare, {"alpha": "Does alpha."} | dict.fromkeys(names))
    lines = _summary(bare, capsys)
    said = next(line for line in lines if line.startswith("  Skill list:"))
    assert said.startswith("  Skill list: In your last chat on Nov 6, 9 of 10 skills showed")
    assert _after(lines, said) == [
        ELSEWHERE,
        "    plugin-dev:skill-number-1, plugin-dev:skill-number-2,",
        "    plugin-dev:skill-number-3, plugin-dev:skill-number-4,",
        "    plugin-dev:skill-number-5 +4 more",
    ]


def test_scan_does_not_list_skills_set_to_name_only(bare, capsys):
    chosen_home(bare, {"delta": "name-only"})
    before_the_chat(bare / ".claude/settings.json")
    claude_chat(bare, {"alpha": LONG[:1000], "beta": LONG[:1000], "gamma": None, "delta": None})
    lines = _summary(bare, capsys)
    said = next(line for line in lines if line.startswith("  Skill list:"))
    assert said.endswith("1 more showed only a name, as you chose.")
    assert _after(lines, said) == [ELSEWHERE, "    gamma"]


def test_scan_lists_nothing_when_every_name_only_skill_was_chosen(bare, capsys):
    chosen_home(bare, {"gamma": "name-only", "delta": "name-only"})
    before_the_chat(bare / ".claude/settings.json")
    claude_chat(bare, {"alpha": LONG[:1000], "beta": LONG[:1000], "gamma": None, "delta": None})
    lines = _summary(bare, capsys)
    said = (
        "  Skill list: In your last chat on Nov 6, all 4 skills were sent; 2 showed only a name, "
        "as you chose."
    )
    assert _after(lines, said) == [ELSEWHERE]
    assert lines[-1] == "To see or change it: kitden open"


def test_scan_names_the_codex_skills_whose_description_was_cut(bare, capsys):
    paths = codex_home(bare, window=1)
    budget = a_budget(paths, lambda fit: fit.cap is not None and fit.cap >= 30)
    cap = codex_rule(rule_skills(paths), budget).cap
    codex_home(bare, window=window_for(budget))
    codex_chat(
        bare,
        [
            f"- alpha: {CODEX_A[:cap]} (file: {paths['alpha']})",
            f"- beta: {CODEX_B[: cap - 1]} (file: {paths['beta']})",
            f"- gamma: {CODEX_C} (file: {paths['gamma']})",
        ],
    )
    lines = _summary(bare, capsys)
    said = next(line for line in lines if line.startswith("  Skill list: In your last chat on Oct"))
    assert "2 of 3 descriptions were cut" in said
    assert _after(lines, said) == [ELSEWHERE, "    alpha, beta"]


def test_scan_names_the_codex_skills_left_out(bare, capsys):
    paths = codex_home(bare, window=1)
    budget = a_budget(paths, lambda fit: fit.sent == {"alpha": 0, "beta": 0, "gamma": None})
    codex_home(bare, window=window_for(budget))
    before_the_chat(Path(paths["gamma"]))
    codex_chat(
        bare,
        [f"- alpha: (file: {paths['alpha']})", f"- beta: (file: {paths['beta']})"],
        at="2026-11-07T12:00:00Z",
    )
    lines = _summary(bare, capsys)
    said = next(line for line in lines if "left 1 of 3 skills out" in line)
    assert _after(lines, said) == [ELSEWHERE, "    gamma"]


def test_scan_in_a_folder_with_no_chat_shows_the_last_chat_and_its_folder(
    bare, capsys, monkeypatch
):
    here, there = bare / "work/here", bare / "work/there"
    here.mkdir(parents=True)
    there.mkdir(parents=True)
    write_json(bare / ".claude.json", {"projects": {str(here): {}, str(there): {}}})
    skill(bare / ".claude/skills", "alpha", "Does alpha.")
    claude_chat(bare, {"alpha": "Does alpha."}, folder=str(there))
    monkeypatch.chdir(here)
    lines = _summary(bare, capsys)
    said = next(line for line in lines if line.startswith("  Skill list: In your last chat"))
    assert _after(lines, said) == ["    That chat was in ~/work/there."]
    monkeypatch.chdir(there)
    lines = _summary(bare, capsys)
    said = next(line for line in lines if line.startswith("  Skill list: In your last chat"))
    assert _after(lines, said) == []
    # The page and `kitden show context` still answer for the project itself.
    assert main(["show", "context", "--home", str(bare), "--project", str(here)]) == 0
    cards = {c["client"]: c for c in json.loads(capsys.readouterr().out)["clients"]}
    assert cards["claude_code"]["message"] == (
        "No Claude Code chat yet. Open one chat, and Kitden will show what Claude Code sent."
    )


def test_scan_with_no_chat_anywhere_says_there_is_none(bare, capsys):
    skill(bare / ".claude/skills", "alpha", "Does alpha.")
    lines = _summary(bare, capsys)
    assert "  Skills: 1" in lines  # no chat's number beside it, so nothing to explain
    assert (
        "  Skill list: No Claude Code chat yet. Open one chat, and Kitden will show what "
        "Claude Code sent." in lines
    )


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


def test_scan_names_the_warnings_and_points_to_the_findings(bare, capsys):
    skill(bare / ".agents/skills", "docker-expert", "Helps with Docker.")
    skill(bare / ".codex/skills", "docker-expert", "Helps with Docker.")
    lines = _summary(bare, capsys)
    # Cursor reads both folders too.
    assert lines[-4:] == [
        "2 warnings: Codex loads skill 'docker-expert' twice; Cursor loads skill",
        "  'docker-expert' twice. 2 notes: kitden show findings",
        "Your agents' settings were not changed: scan only reads them.",
        "To fix: kitden open",
    ]


def test_scan_reads_the_servers_kitden_holds_as_show_does(bare, capsys):
    # Cursor uses the Kitden gateway, which holds github; Cursor also has github directly.
    (bare / ".cursor/mcp.json").write_text(json.dumps({"mcpServers": {}}))
    for name, entry in (("kitden", KITDEN), ("github", {"command": "npx"})):
        add_entry(bare, "cursor", name, entry)
    hold_github(bare)
    lines = _summary(bare, capsys)
    cursor = lines.index("Cursor: found (unknown version)")
    assert "  MCP servers: 3" in lines[cursor:]  # kitden, github, and github through Kitden
    assert main(["show", "findings", "--home", str(bare)]) == 0
    shown = json.loads(capsys.readouterr().out)["findings"]
    assert lines[-3] == f"{len(shown)} notes: kitden show findings"
    # The held copy replaces the direct one in Cursor's view: one server, no warning.
    assert not [f for f in shown if f["severity"] == "warning"]


def test_scan_counts_each_kind_in_plain_words(home, capsys):
    lines = _summary(home, capsys)
    claude = lines.index("Claude Code: found (unknown version)")
    assert lines[claude + 1 : claude + 7] == [
        "  Hooks: 1",
        "  Instruction files: 5",
        "  Marketplaces: 1",
        "  MCP servers: 4",
        "  Plugins: 3",
        "  Skills: 4",
    ]
    assert set(words.SCAN_KINDS) == {str(kind) for kind in ItemKind}


def test_scan_puts_the_desktop_code_tab_under_claude_code(home, capsys):
    (claude_desktop_dir(home) / "claude-code/2.1.330").mkdir(parents=True)
    lines = _summary(home, capsys)
    clients = [line.split(":")[0] for line in lines if ": found (" in line]
    assert clients == ["Claude Code", "Codex", "Cursor"]
    # Its own servers, after everything Claude Code loads: the Code tab loads that too.
    assert lines[lines.index("Codex: found (unknown version)") - 1] == (
        "  Only in the Claude Desktop app (Code tab, 2.1.330): MCP servers: 1"
    )


def test_scan_ends_by_saying_the_settings_were_not_changed(bare, capsys):
    before = _snapshot(bare)
    assert _summary(bare, capsys)[-2:] == [
        "Your agents' settings were not changed: scan only reads them.",
        "To see or change it: kitden open",
    ]
    assert _snapshot(bare) == before


# The findings line, from the answer `kitden show findings` gives


def _finding(severity, client="codex", items=("a",), text="It is so."):
    return {
        "severity": severity,
        "type": "x",
        "client": client,
        "items": list(items),
        "explanation": text,
    }


def test_findings_lines_count_the_notes():
    assert cli._findings_lines([_finding("info")], {}) == ["1 note: kitden show findings"]
    notes = [_finding("info")] * 61
    assert cli._findings_lines(notes, {}) == ["61 notes: kitden show findings"]
    assert cli._findings_lines([], {}) == []


def test_findings_lines_with_warnings_only_still_say_where_to_look():
    lines = cli._findings_lines([_finding("warning")], {})
    assert lines == ["1 warning: It is so. See: kitden show findings"]


def test_findings_lines_name_the_first_few_warnings_and_fit_80_columns():
    warnings = [_finding("warning", text=f"Warning number {n} is here") for n in range(1, 6)]
    assert cli._findings_lines(warnings + [_finding("info")] * 2, {}) == [
        "5 warnings: Warning number 1 is here; Warning number 2 is here; Warning number 3",
        "  is here +2 more. 2 notes: kitden show findings",
    ]


# A line never breaks inside "+N more" or inside a command to copy


def test_findings_lines_keep_the_command_whole():
    warning = _finding("warning", text="Cursor loads plugin 'superpowers' twice.")
    assert cli._findings_lines([warning] + [_finding("info")] * 61, {}) == [
        "1 warning: Cursor loads plugin 'superpowers' twice. 61 notes:",
        "  kitden show findings",
    ]


def test_the_count_of_more_stays_on_one_line():
    names = ["imagegen", "openai-docs", "Pixel Art Animator", "Pixel Art Exporter", "animate"]
    said = cli._first_few(names + ["other"] * 26, cli.FEW_NAMES, ", ")
    assert cli._wrap(said, "    ", "    ") == [
        "    imagegen, openai-docs, Pixel Art Animator, Pixel Art Exporter, animate",
        "    +26 more",
    ]
    texts = ("Warning one is here", "Warning two is here too", "Warning three is")
    warnings = [_finding("warning", text=text) for text in texts]
    assert cli._findings_lines(warnings * 2, {}) == [
        "6 warnings: Warning one is here; Warning two is here too; Warning three is",
        "  +3 more. See: kitden show findings",
    ]
