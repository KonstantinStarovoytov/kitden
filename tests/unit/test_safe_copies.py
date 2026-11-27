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


def test_a_copy_whose_folder_holds_another_skill_is_not_removed_for_keep(home):
    """Codex loads solo from its own folder and from ~/.agents/skills; its own folder holds the
    skill inner too (Codex reads sub-folders). Keeping the shared copy would remove Codex's
    folder and inner with it: not offered. Keeping Codex's own copy costs nothing."""
    for folder in (".codex/skills", ".agents/skills"):
        _skill(home, folder, "solo")
    _skill(home, ".codex/skills/solo", "inner")
    adapters = {a.id: a for a in default_adapters(home)}
    answer = library_map(build_inventory(home), adapters, None)
    item = next(i for g in answer["groups"] for i in g["items"] if i["name"] == "solo")
    by_where = {copy["where"]: copy for copy in item["copies"]["codex"]["list"]}
    assert by_where["~/.agents/skills"]["keep"] is None
    assert by_where["~/.codex/skills"]["keep"] is not None


def test_a_copy_inside_another_copys_folder_is_never_the_one_kept(tmp_path):
    """Codex finds solo and, inside its folder, another solo (Codex reads sub-folders). Keeping
    the inner one would remove the outer folder, and the inner with it: not offered."""
    from kitden.clients.cursor import REACTIVE_KEY

    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home, {REACTIVE_KEY: {"thirdPartyExtensibilityEnabled": False}})
    _skill(home, ".codex/skills", "solo")
    _skill(home, ".codex/skills/solo/nested", "solo")
    adapters = {a.id: a for a in default_adapters(home)}
    answer = library_map(build_inventory(home), adapters, None)
    item = next(i for g in answer["groups"] for i in g["items"] if i["name"] == "solo")
    by_where = {copy["where"]: copy for copy in item["copies"]["codex"]["list"]}
    assert by_where["~/.codex/skills/solo/nested"]["keep"] is None
    assert by_where["~/.codex/skills"]["keep"] is not None


def test_a_copy_whose_state_kitden_does_not_know_does_not_count_as_kept():
    """Claude Code's only other duo comes from a plugin whose state Kitden does not know: keeping
    Cursor's own copy could leave Claude Code with none, so it is not offered."""
    from kitden.model import Enabled, Item, ItemKind, Scope, Source, SourceKind
    from kitden.views.inventory import Inventory
    from kitden.views.library_map import copy_choices

    def skill(client, path, owner, scope=Scope.USER, enabled=Enabled.ON, actions=()):
        source = Source(kind=SourceKind.FILE, path=path, owner_client=owner)
        return Item(
            client=client,
            kind=ItemKind.SKILL,
            name="duo",
            source=source,
            scope=scope,
            enabled=enabled,
            actions=actions,
        )

    claudes = "/h/.claude/skills/duo/SKILL.md"
    own = skill("cursor", "/h/.cursor/skills/duo/SKILL.md", "cursor", actions=("skill.remove",))
    read = skill("cursor", claudes, "claude_code")
    claude = skill("claude_code", claudes, "claude_code", actions=("skill.remove",))
    plugin = skill(
        "claude_code", "/h/p/skills/duo/SKILL.md", "claude_code", Scope.PLUGIN, Enabled.UNKNOWN
    )
    inventory = Inventory(clients=[], items=[own, read, claude, plugin])
    rows = copy_choices(inventory, [own, read], "cursor")["list"]
    assert rows[0]["keep"] is None


def test_a_copy_a_project_turns_off_does_not_count_as_kept_there(tmp_path):
    """Claude Code also has brainstorming from superpowers, which website's settings turn off:
    in website, keeping Cursor's own copy would leave Claude Code with none there."""
    from kitden.demo import build_demo_home, demo_adapters, demo_build

    home = build_demo_home(tmp_path, "medium")
    for folder in (".cursor/skills", ".claude/skills"):
        _skill(home, folder, "brainstorming")
    adapters = {a.id: a for a in demo_adapters(home)}

    def own_keep(project):
        answer = library_map(demo_build(home)(), adapters, project)
        items = [i for g in answer["groups"] for i in g["items"] if i["name"] == "brainstorming"]
        copies = next(i["copies"]["cursor"] for i in items if "cursor" in i.get("copies", {}))
        return next(c for c in copies["list"] if c["where"] == "~/.cursor/skills")["keep"]

    assert own_keep(None) is not None
    assert own_keep(str(home / "work/website")) is None
