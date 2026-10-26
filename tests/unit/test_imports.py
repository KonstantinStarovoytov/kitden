"""Claude Code's `@path` imports in a CLAUDE.md, as Kitden reads them (spec Part 6.1)."""

import os
from pathlib import Path

from kitden.views.imports import imports


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _names(found: list[dict]) -> list[str]:
    return [i["name"] for i in found]


def test_an_import_is_read_relative_to_its_file_and_home_works(tmp_path):
    home = tmp_path / "home"
    project = home / "work/app"
    claude = _write(project / ".claude/CLAUDE.md", "See @guide.md and @~/notes/me.md\n")
    _write(project / ".claude/guide.md", "# Guide\n")
    _write(home / "notes/me.md", "# Me\n")
    found = imports(claude, project, home)
    # Each name is what the file says after `@`.
    assert _names(found) == ["guide.md", "~/notes/me.md"]
    guide, mine = found
    assert guide["target"] == str((project / ".claude/guide.md").resolve())
    assert guide["via"] == str(claude.resolve())
    assert (guide["depth"], guide["missing"], guide["outside"]) == (1, False, False)
    # A file in the home folder, outside the project: Claude Code may ask before it reads it.
    assert (mine["missing"], mine["outside"]) == (False, True)


def test_imports_nest_four_hops_and_stop(tmp_path):
    home = tmp_path / "home"
    project = home / "work/app"
    claude = _write(project / "CLAUDE.md", "@a.md\n")
    for this, then in zip("abcde", "bcdef", strict=True):
        _write(project / f"{this}.md", f"@{then}.md\n")
    found = imports(claude, project, home)
    assert [(i["name"], i["depth"]) for i in found] == [
        ("a.md", 1),
        ("b.md", 2),
        ("c.md", 3),
        ("d.md", 4),
    ]


def test_an_import_in_a_code_span_or_a_fenced_block_is_skipped(tmp_path):
    home = tmp_path / "home"
    claude = _write(
        home / "work/app/CLAUDE.md",
        "Write `@README` to keep it literal, or ``@x.md`` too.\n"
        "```\n@fenced.md\n```\n"
        "~~~~ text\n@tilde.md\n```\n@still-fenced.md\n~~~~\n"
        "Mail me@example.com, see @real.md and not @'quoted.md'\n",
    )
    assert _names(imports(claude, claude.parent, home)) == ["real.md"]


def test_a_path_with_escaped_spaces_is_one_import(tmp_path):
    home = tmp_path / "home"
    claude = _write(home / "app/CLAUDE.md", "- API conventions @Design\\ Docs/api.md\n")
    _write(home / "app/Design Docs/api.md", "# API\n")
    found = imports(claude, claude.parent, home)
    assert _names(found) == ["Design Docs/api.md"]
    assert found[0]["missing"] is False


def test_a_loop_stops_at_the_first_repeat(tmp_path):
    home = tmp_path / "home"
    project = home / "app"
    claude = _write(project / "CLAUDE.md", "@a.md @b.md\n")
    _write(project / "a.md", "@b.md @CLAUDE.md\n")
    _write(project / "b.md", "@a.md @./a.md\n")
    found = imports(claude, project, home)
    # Each file once, the start file never, and nothing is read twice.
    assert [(i["name"], i["depth"]) for i in found] == [("a.md", 1), ("b.md", 1)]


def test_a_self_import_and_a_symlink_loop_end(tmp_path):
    home = tmp_path / "home"
    project = home / "app"
    claude = _write(project / "CLAUDE.md", "@CLAUDE.md @link.md\n")
    os.symlink(project / "CLAUDE.md", project / "link.md")
    assert imports(claude, project, home) == []


def test_a_missing_import_is_named_not_followed(tmp_path):
    home = tmp_path / "home"
    project = home / "app"
    claude = _write(project / "CLAUDE.md", "@gone.md @docs\n")
    (project / "docs").mkdir()
    found = imports(claude, project, home)
    assert [(i["name"], i["missing"]) for i in found] == [("gone.md", True), ("docs", True)]


def test_an_import_outside_the_project_is_marked_outside(tmp_path):
    home = tmp_path / "home"
    project = home / "work/app"
    _write(home / "work/shared.md", "@deeper.md\n")
    _write(home / "work/deeper.md", "# Deeper\n")
    claude = _write(project / "CLAUDE.md", "@../shared.md\n")
    found = imports(claude, project, home)
    assert [(i["name"], i["outside"]) for i in found] == [
        ("../shared.md", True),
        ("deeper.md", True),
    ]
    # In the user's own CLAUDE.md nothing is outside: Claude Code loads its imports without asking.
    user = _write(home / ".claude/CLAUDE.md", "@~/work/shared.md\n")
    assert [i["outside"] for i in imports(user, None, home)] == [False, False]


def test_an_import_outside_the_home_folder_is_named_but_never_read(tmp_path):
    home = tmp_path / "home"
    elsewhere = _write(tmp_path / "elsewhere/secret.md", "@other.md\n")
    _write(tmp_path / "elsewhere/other.md", "# Other\n")
    also = _write(tmp_path / "elsewhere/also.md", "@other.md\n")
    claude = _write(home / "app/CLAUDE.md", f"@{elsewhere} @/dev/zero @link.md\n")
    os.symlink(also, home / "app/link.md")  # a link in the home folder to a file outside it
    found = imports(claude, claude.parent, home)
    # The full path never becomes a name, only the file's name; other.md is never read.
    assert [(i["name"], i["outside"], i["missing"]) for i in found] == [
        ("secret.md", True, False),
        ("zero", True, True),
        ("link.md", True, False),
    ]


def test_a_long_file_is_read_only_so_far(tmp_path):
    home = tmp_path / "home"
    claude = _write(home / "app/CLAUDE.md", "x" * 300_000 + "\n@late.md\n")
    assert imports(claude, claude.parent, home) == []


def test_a_project_outside_the_home_folder_is_read_but_nothing_beyond_it(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "srv/app"
    claude = _write(project / "CLAUDE.md", "@a.md @../away.md\n")
    _write(project / "a.md", "@b.md\n")
    _write(project / "b.md", "# B\n")
    _write(tmp_path / "srv/away.md", "@never.md\n")
    _write(tmp_path / "srv/never.md", "# Never\n")
    found = imports(claude, project, home)
    assert [(i["name"], i["depth"], i["outside"]) for i in found] == [
        ("a.md", 1, False),
        ("../away.md", 1, True),
        ("b.md", 2, False),
    ]


def test_a_nul_character_or_a_bad_path_is_skipped(tmp_path):
    home = tmp_path / "home"
    project = home / "app"
    _write(project / "blob.md", "@a\x00b.md @ok.md\n")
    _write(project / "ok.md", "# OK\n")
    claude = _write(project / "CLAUDE.md", "@blob.md @c\x00d.md\n")
    assert _names(imports(claude, project, home)) == ["blob.md", "ok.md"]


def test_a_token_after_the_at_sign_is_hidden_in_the_name(tmp_path):
    home = tmp_path / "home"
    claude = _write(home / "app/CLAUDE.md", "@ghp_abcdefghijklmnopqrstuvwxyz0123456789\n")
    found = imports(claude, claude.parent, home)
    assert "ghp_" not in found[0]["name"]
