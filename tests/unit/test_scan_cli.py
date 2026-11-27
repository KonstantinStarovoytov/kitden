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
    # The block's order: the first line, the verdict, the names, the folder, what is here, and
    # why the counts differ.
    assert lines[:8] == [
        "Claude Code (version unknown)",
        "  In your last chat on Nov 7, 2 of 4 skills showed only a name. The agent may",
        "  not have used them.",
        "    gamma, delta",
        ELSEWHERE,
        "  On this computer: 1 plugin, 4 skills",
        "  A chat lists only one project's skills, and Claude Code's own too.",
        "",
    ]
    assert lines[-1] == "To make the skills fit, turn off the ones you do not use: kitden open"
    assert all(len(line) <= 80 for line in lines)


def test_scan_names_the_first_few_skills_and_counts_the_rest(bare, capsys):
    names = [f"plugin-dev:skill-number-{n}" for n in range(1, 10)]
    claude_chat(bare, {"alpha": "Does alpha."} | dict.fromkeys(names))
    lines = _summary(bare, capsys)
    assert lines[1].startswith("  In your last chat on Nov 6, 9 of 10 skills showed")
    assert _after(lines, lines[2]) == [
        "    plugin-dev:skill-number-1, plugin-dev:skill-number-2,",
        "    plugin-dev:skill-number-3, plugin-dev:skill-number-4,",
        "    plugin-dev:skill-number-5 +4 more",
        ELSEWHERE,
    ]


def test_scan_does_not_list_skills_set_to_name_only(bare, capsys):
    chosen_home(bare, {"delta": "name-only"})
    before_the_chat(bare / ".claude/settings.json")
    claude_chat(bare, {"alpha": LONG[:1000], "beta": LONG[:1000], "gamma": None, "delta": None})
    lines = _summary(bare, capsys)
    said = next(line for line in lines if line.endswith("1 more showed only a name, as you chose."))
    assert _after(lines, said) == ["    gamma", ELSEWHERE]


def test_scan_lists_nothing_when_every_name_only_skill_was_chosen(bare, capsys):
    chosen_home(bare, {"gamma": "name-only", "delta": "name-only"})
    before_the_chat(bare / ".claude/settings.json")
    claude_chat(bare, {"alpha": LONG[:1000], "beta": LONG[:1000], "gamma": None, "delta": None})
    lines = _summary(bare, capsys)
    said = "  In your last chat on Nov 6, all 4 skills were sent; 2 showed only a name, as"
    assert lines[1:4] == [said, "  you chose.", ELSEWHERE]
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
    assert "2 of 3 descriptions were cut" in " ".join(lines)
    assert lines[lines.index("    alpha, beta") + 1] == ELSEWHERE


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
    assert "left 1 of 3 skills out" in " ".join(" ".join(lines).split())
    assert lines[lines.index("    gamma") + 1] == ELSEWHERE


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
    said = next(line for line in lines if line.startswith("  In your last chat"))
    assert _after(lines, said)[-1:] == ["    That chat was in ~/work/there."]
    monkeypatch.chdir(there)
    lines = _summary(bare, capsys)
    assert not [line for line in lines if "That chat was in" in line]
    # The page and `kitden show context` still answer for the project itself.
    assert main(["show", "context", "--home", str(bare), "--project", str(here)]) == 0
    cards = {c["client"]: c for c in json.loads(capsys.readouterr().out)["clients"]}
    assert cards["claude_code"]["message"] == (
        "No Claude Code chat yet. Open one chat, and Kitden will show what Claude Code sent."
    )


def test_show_context_without_a_project_finds_the_last_chat_in_another_folder(
    bare, capsys, monkeypatch
):
    here, there = bare / "work/here", bare / "work/there"
    here.mkdir(parents=True)
    there.mkdir(parents=True)
    write_json(bare / ".claude.json", {"projects": {str(here): {}, str(there): {}}})
    skill(bare / ".claude/skills", "alpha", "Does alpha.")
    claude_chat(bare, {"alpha": "Does alpha."}, folder=str(there))
    monkeypatch.chdir(here)
    assert main(["show", "context", "--home", str(bare)]) == 0
    cards = {c["client"]: c for c in json.loads(capsys.readouterr().out)["clients"]}
    assert cards["claude_code"]["fact"]["folder"] == str(there)
    assert cards["claude_code"]["message"] is None
    # With --project the answer stays with that folder, as before.
    assert main(["show", "context", "--home", str(bare), "--project", str(here)]) == 0
    cards = {c["client"]: c for c in json.loads(capsys.readouterr().out)["clients"]}
    assert cards["claude_code"]["message"] == (
        "No Claude Code chat yet. Open one chat, and Kitden will show what Claude Code sent."
    )


def test_scan_with_no_chat_anywhere_says_there_is_none(bare, capsys):
    skill(bare / ".claude/skills", "alpha", "Does alpha.")
    lines = _summary(bare, capsys)
    assert lines[1:4] == [
        "  No Claude Code chat yet. Open one chat, and Kitden will show what Claude Code",
        "  sent.",
        "  On this computer: 1 plugin, 1 skill",
    ]
    # No chat's number beside it, so nothing to explain.
    assert not [line for line in lines if "its count differs" in line]


def test_scan_says_so_when_it_cannot_tell(bare, capsys):
    skill(bare / ".claude/skills", "alpha", "Does alpha.")
    skill(bare / ".cursor/skills", "alpha", "Does alpha.")
    lines = _summary(bare, capsys)
    assert lines[1:3] == [
        "  No Claude Code chat yet. Open one chat, and Kitden will show what Claude Code",
        "  sent.",
    ]
    cursor = lines.index("Cursor (version unknown)")
    assert lines[cursor + 1 : cursor + 4] == [
        "  Kitden cannot see what Cursor sends, so it cannot tell if your skills fit.",
        # One skill: Cursor's copy of Claude Code's is the same one, with a warning of its own.
        "  On this computer: 1 skill",
        "",
    ]


def test_scan_prints_no_verdict_for_a_client_with_no_skills(bare, capsys):
    skill(bare / ".claude/skills", "alpha", "Does alpha.")
    lines = _summary(bare, capsys)
    codex = lines.index("Codex (version unknown)")
    # Nothing to fit is not a verdict: the block is its first line and what it has.
    assert lines[codex : codex + 3] == [
        "Codex (version unknown)",
        "  On this computer: nothing yet",
        "",
    ]
    assert words.NOTHING_TO_FIT not in "\n".join(lines)


def test_scan_names_the_warnings_and_points_to_the_findings(bare, capsys):
    skill(bare / ".agents/skills", "docker-expert", "Helps with Docker.")
    skill(bare / ".codex/skills", "docker-expert", "Helps with Docker.")
    lines = _summary(bare, capsys)
    # Cursor reads both folders too.
    assert lines[-4:] == [
        "2 warnings: Codex loads skill 'docker-expert' twice; Cursor loads skill",
        "  'docker-expert' twice. 2 notes (nothing to fix): kitden show findings",
        "Your agents' settings were not changed: scan only reads them.",
        "To fix the warnings: kitden open",
    ]


def test_scan_reads_the_servers_kitden_holds_as_show_does(bare, capsys):
    # Cursor uses the Kitden gateway, which holds github; Cursor also has github directly.
    (bare / ".cursor/mcp.json").write_text(json.dumps({"mcpServers": {}}))
    for name, entry in (("kitden", KITDEN), ("github", {"command": "npx"})):
        add_entry(bare, "cursor", name, entry)
    hold_github(bare)
    lines = _summary(bare, capsys)
    cursor = lines.index("Cursor (version unknown)")
    # kitden, github, and github through Kitden
    assert any("3 MCP servers" in line for line in lines[cursor:])
    assert main(["show", "findings", "--home", str(bare)]) == 0
    shown = json.loads(capsys.readouterr().out)["findings"]
    assert lines[-3] == f"{len(shown)} notes (nothing to fix): kitden show findings"
    # The held copy replaces the direct one in Cursor's view: one server, no warning.
    assert not [f for f in shown if f["severity"] == "warning"]


def test_scan_counts_each_kind_in_one_line(home, capsys):
    lines = _summary(home, capsys)
    claude = lines.index("Claude Code (version unknown)")
    on = lines.index(
        "  On this computer: 2 plugins, 3 skills, 4 MCP servers, 1 hook, 5 instruction", claude
    )
    assert lines[on + 1] == "  files, 1 marketplace"
    assert set(words.SCAN_KINDS) == {str(kind) for kind in ItemKind}


def test_scan_counts_an_item_reached_twice_once(home, capsys, monkeypatch):
    from kitden.views import answers

    read = answers.read_setup

    def twice(root):
        # As when a project is listed by its path and by a symlink to it.
        inventory = read(root)
        inventory.items += [i for i in inventory.items if i.kind is ItemKind.SKILL]
        return inventory

    monkeypatch.setattr(answers, "read_setup", twice)
    lines = _summary(home, capsys)
    assert any("4 skills" in line for line in lines)


def test_scan_says_a_client_is_not_found_in_plain_words(tmp_path, capsys):
    lines = _summary(make_home(tmp_path, "claude_code/2.1.283"), capsys)
    assert lines[lines.index("Codex: not installed") - 1] == ""
    assert "Cursor: not installed" in lines
    assert not [line for line in lines if "not_found" in line]


def test_scan_puts_the_desktop_code_tab_under_claude_code(home, capsys):
    (claude_desktop_dir(home) / "claude-code/2.1.330").mkdir(parents=True)
    lines = _summary(home, capsys)
    clients = [line for line in lines if line.endswith("(version unknown)")]
    assert len(clients) == 3
    # Its own servers, last in Claude Code's block: the Code tab loads what it loads too.
    assert lines[lines.index("Codex (version unknown)") - 2] == (
        "  Only in the Claude Desktop app (Code tab, 2.1.330): MCP servers: 1"
    )


def test_scan_ends_by_saying_the_settings_were_not_changed(bare, capsys):
    before = _snapshot(bare)
    assert _summary(bare, capsys)[-3:] == [
        "1 note (nothing to fix): kitden show findings",
        "Your agents' settings were not changed: scan only reads them.",
        "To see or change it: kitden open",
    ]
    assert _snapshot(bare) == before


def test_scan_separates_the_blocks_and_the_closing_lines_by_one_blank_line(bare, capsys):
    out = _summary(bare, capsys)
    assert out[0] and out[-1]  # no blank line at the start or the end
    assert [i for i, line in enumerate(out) if not line] == [
        out.index("Codex (version unknown)") - 1,
        out.index("Cursor (version unknown)") - 1,
        out.index("1 note (nothing to fix): kitden show findings") - 1,
    ]


def test_scan_blocks_of_clients_that_are_not_found_are_one_line(tmp_path, capsys):
    lines = _summary(make_home(tmp_path, "claude_code/2.1.283"), capsys)
    assert lines[0] == "Claude Code (version unknown)"
    assert lines[lines.index("Codex: not installed") + 1 :][:2] == ["", "Cursor: not installed"]


def test_scan_names_a_client_and_its_version_on_one_line(home, tmp_path, monkeypatch, capsys):
    codex = fake_client_command(tmp_path, "codex", "echo codex-cli 0.159.2")
    monkeypatch.setattr(version_cache, "version_command", {"codex": [str(codex), "--version"]}.get)
    assert "Codex 0.159.2" in _summary(home, capsys)


def test_scan_last_line_says_what_to_do(bare, capsys):
    # Skills that did not fit.
    names = {"alpha": "Does alpha.", "beta": None}
    for name in names:
        skill(bare / ".claude/skills", name, "Does it.")
    claude_chat(bare, names)
    fits = "To make the skills fit, turn off the ones you do not use: kitden open"
    assert _summary(bare, capsys)[-1] == fits


def test_scan_last_line_for_a_warning_or_a_file_that_cannot_be_read(bare, capsys):
    (bare / ".claude.json").write_text("{ broken")
    assert main(["scan", "--home", str(bare)]) == 3
    lines = capsys.readouterr().out.splitlines()
    # It names what to fix: "this" pointed at a line three lines up (05-P14).
    assert lines[-1] == "To fix the file Kitden could not read: kitden open"
    # The reason is in words, not the id `scan --json` has.
    assert lines[-4].endswith(": the file has a syntax error")
    assert lines[-4].startswith("Could not read ")


def test_scan_explains_the_two_skill_counts_only_beside_a_chat_and_skills(bare, capsys):
    note = "  A chat lists only one project's skills, and Claude Code's own too."
    # No chat: no number to differ from.
    skill(bare / ".claude/skills", "alpha", "Does alpha.")
    assert note not in _summary(bare, capsys)
    # A chat and a skill: said once, right under the count.
    claude_chat(bare, {"alpha": "Does alpha."})
    lines = _summary(bare, capsys)
    assert lines[lines.index(note) - 1].startswith("  On this computer: ")
    assert lines.count(note) == 1
    # A chat, but no skill on this computer: nothing to compare.
    (bare / ".claude/skills/alpha/SKILL.md").unlink()
    assert note not in _summary(bare, capsys)


def test_scan_words_are_singular_for_one(bare, capsys):
    skill(bare / ".claude/skills", "alpha", "Does alpha.")
    assert "  On this computer: 1 plugin, 1 skill" in _summary(bare, capsys)


# The findings line, from the answer `kitden show findings` gives


def _finding(severity, client="codex", items=("a",), text="It is so.", kind="x"):
    return {
        "severity": severity,
        "type": kind,
        "client": client,
        "items": list(items),
        "names": list(items),
        "explanation": text,
    }


def _notes(n):
    """`n` notes that do not fold: each its own item and words."""
    return [_finding("info", items=(f"i{k}",), kind=f"t{k}") for k in range(n)]


def test_findings_lines_count_the_notes():
    assert cli._findings_lines([_finding("info")], {}) == [
        "1 note (nothing to fix): kitden show findings"
    ]
    notes = _notes(61)
    assert cli._findings_lines(notes, {}) == ["61 notes (nothing to fix): kitden show findings"]
    assert cli._findings_lines([], {}) == []


def test_findings_lines_with_warnings_only_still_say_where_to_look():
    lines = cli._findings_lines([_finding("warning")], {})
    assert lines == ["1 warning: It is so. See: kitden show findings"]


def test_findings_lines_name_the_first_few_warnings_and_fit_80_columns():
    warnings = [_finding("warning", text=f"Warning number {n} is here") for n in range(1, 6)]
    assert cli._findings_lines(warnings + _notes(2), {}) == [
        "5 warnings: Warning number 1 is here; Warning number 2 is here; Warning number 3",
        "  is here +2 more. 2 notes (nothing to fix): kitden show findings",
    ]


# A line never breaks inside "+N more" or inside a command to copy


def test_findings_lines_keep_the_command_whole():
    warning = _finding("warning", text="Cursor loads plugin 'superpowers' twice.")
    assert cli._findings_lines([warning, *_notes(61)], {}) == [
        "1 warning: Cursor loads plugin 'superpowers' twice. 61 notes (nothing to fix):",
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


def test_scan_counts_a_plugin_once_however_many_projects_set_it(tmp_path):
    """A project's own entry for a plugin is the same plugin: Codex has browser and superpowers
    (atlas turns browser off), Claude Code superpowers, its account plugin and one more."""
    from kitden.demo import build_demo_home, demo_build

    home = build_demo_home(tmp_path, "medium")
    atlas = home / "work/atlas/.codex/config.toml"
    atlas.parent.mkdir(parents=True, exist_ok=True)
    atlas.write_text('[plugins."browser@openai-bundled"]\nenabled = false\n')
    inventory = demo_build(home)()
    counts = cli._have_counts(inventory)
    names = {
        client: {i.name for i in inventory.items if i.client == client and i.kind == "plugin"}
        for client in ("claude_code", "codex")
    }
    assert counts[("codex", "plugin")] == len(names["codex"])
    assert counts[("claude_code", "plugin")] == len(names["claude_code"])
    # A plugin's skills count with their plugin, not again as skills.
    own = {
        i.name
        for i in inventory.items
        if i.client == "claude_code" and i.kind == "skill" and i.scope != "plugin"
    }
    assert counts[("claude_code", "skill")] == len(own)


def test_scan_counts_notes_as_the_overview_folds_them():
    """Four items with the same note are one row on the Overview; the scan says the same."""

    def note(name, kind="bypasses_gateway"):
        return {"type": kind, "severity": "info", "items": [], "names": [name], "client": None}

    findings = [note(n) for n in ("a", "b", "c", "d")] + [note("e", "scope_override")]
    assert cli._findings_lines(findings, {}) == [
        "2 notes (nothing to fix): kitden show findings".replace(" ", " ")
    ]
