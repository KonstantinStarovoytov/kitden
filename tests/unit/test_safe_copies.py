"""Keep this one… never costs another client its skill, and the preview counts what stays."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kitden.views.findings import find_findings
from kitden.views.inventory import build_inventory, default_adapters
from kitden.views.library_map import library_map
from kitden.views.overview import _duplicates
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
SETTING = (
    "Cursor also reads Claude Code's and Codex's skill folders. To load each skill once, turn "
    "off Include Third-Party Plugins, Skills, and Other Configs in Cursor Settings → Agents → "
    "Third-Party Imports."
)


def _skill(home: Path, folder: str, name: str) -> None:
    path = home / folder / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: The {name} skill.\n---\nBody.\n")


@pytest.fixture
def home(tmp_path):
    """duo: Cursor's own copy and Claude Code's. trio: Cursor's, Claude Code's and Codex's."""
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    for folder in (".cursor/skills", ".claude/skills"):
        _skill(home, folder, "duo")
    for folder in (".cursor/skills", ".claude/skills", ".codex/skills"):
        _skill(home, folder, "trio")
    return home


def _copies(home, name):
    adapters = {a.id: a for a in default_adapters(home)}
    answer = library_map(build_inventory(home), adapters, None)
    item = next(i for g in answer["groups"] for i in g["items"] if i["name"] == name)
    return item["copies"]["cursor"]


def test_keep_is_offered_only_where_every_client_keeps_the_skill(home):
    duo = _copies(home, "duo")
    by_where = {copy["where"]: copy for copy in duo["list"]}
    # Keeping Cursor's own copy would delete Claude Code's folder: not offered.
    assert by_where["~/.cursor/skills"]["keep"] is None
    # Keeping Claude Code's copy removes only Cursor's own.
    cursors = by_where["~/.cursor/skills"]["remove"]
    assert by_where["~/.claude/skills"]["keep"] == [cursors]
    assert "why" not in duo


def test_with_no_safe_keep_nothing_is_offered_and_one_line_names_cursors_setting(home):
    trio = _copies(home, "trio")
    assert [copy["keep"] for copy in trio["list"]] == [None, None, None]
    assert trio["why"] == SETTING


def test_the_overview_card_follows_the_same_rule(home):
    inventory = build_inventory(home)
    cards = {c["name"]: c for c in _duplicates(inventory, find_findings(inventory))}
    assert cards["duo"]["action"]["label"] == "Keep one…"
    assert cards["trio"]["action"] is None
    assert cards["trio"]["line"] == f"3 copies load in Cursor. {SETTING}"
    assert cards["trio"]["group"] == "improve"


def test_the_preview_counts_the_copies_that_stay(home):
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        trio = _copies(home, "trio")
        own = next(x for x in trio["list"] if x["where"] == "~/.cursor/skills")["remove"]
        body = {"action": "skill.remove", "targets": [{"item": own}], "params": {}}
        change = c.post("/api/changes/preview", json=body, headers=POST).json()
        cursor = next(e for e in change["after"] if e["client"] == "cursor")
        assert cursor["word"] == "Loads twice"


def test_a_copy_in_another_project_does_not_count_as_kept(home):
    """Claude Code has duo in its user folder and in the project `website` only: keeping Cursor's
    own copy would still take duo from Claude Code everywhere but `website`."""
    _skill(home, "work/website/.claude/skills", "duo")
    duo = _copies(home, "duo")
    by_where = {copy["where"]: copy for copy in duo["list"]}
    assert by_where["~/.cursor/skills"]["keep"] is None
