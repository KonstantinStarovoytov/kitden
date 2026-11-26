"""Numbers and copies: "Keep one…" on the Overview lands on the skill with its copies named and
a way to keep one of them, and every place counts the copies the same. The medium sample, with
`dup-skill` in `~/.claude/skills`, `~/.agents/skills` and `~/.cursor/skills`: Cursor reads all
three folders, so it loads three copies."""

import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import change_states, wait_until

pytestmark = pytest.mark.browser

FOLDERS = (".claude/skills", ".agents/skills", ".cursor/skills")


@pytest.fixture
def before_start():
    def write(home):
        for folder in FOLDERS:
            skill = home / folder / "dup-skill/SKILL.md"
            skill.parent.mkdir(parents=True, exist_ok=True)
            skill.write_text("---\nname: dup-skill\ndescription: Use when copied.\n---\n")

    return write


def keep_one(page):
    """The Overview's card for dup-skill, "Keep one…": the Details it opens."""
    card = page.locator("[data-card]").filter(has_text="dup-skill")
    expect(card).to_contain_text("3 copies")
    card.get_by_role("button", name="Keep one…").click()
    return page.get_by_role("complementary", name="Details")


def test_keep_one_lands_on_the_skill_with_its_copies_named(page, demo):
    details = keep_one(page)
    expect(details).to_contain_text("dup-skill")
    row = page.get_by_role("row", name=re.compile(r"^dup-skill "))
    expect(row).to_be_in_viewport()
    copies = details.get_by_role("list", name="Copies in Cursor")
    expect(copies.get_by_role("listitem")).to_have_count(3)
    for folder in FOLDERS:
        expect(copies).to_contain_text(f"~/{folder}")


def test_keep_one_copy_goes_through_preview_apply_and_undo(page, demo):
    details = keep_one(page)
    copies = details.get_by_role("list", name="Copies in Cursor")
    mine = copies.get_by_role("listitem").filter(has_text="~/.cursor/skills")
    mine.get_by_role("button", name="Keep this one…").click()
    # Nothing is written before Apply.
    assert all((demo.home / f / "dup-skill").exists() for f in FOLDERS)
    page.locator("#dock").get_by_role("button", name="Apply").click()
    undo = page.get_by_role("button", name="Undo")
    expect(undo).to_be_visible()
    wait_until(lambda: change_states(page, demo) == ["verified"], 15)
    assert (demo.home / ".cursor/skills/dup-skill").exists()
    assert not (demo.home / ".claude/skills/dup-skill").exists()
    assert not (demo.home / ".agents/skills/dup-skill").exists()
    undo.click()
    wait_until(lambda: change_states(page, demo) == ["undone"], 15)
    assert all((demo.home / f / "dup-skill").exists() for f in FOLDERS)


def test_the_library_counts_the_copies_the_overview_counts(page, demo):
    keep_one(page)
    row = page.get_by_role("row", name=re.compile(r"^dup-skill "))
    expect(row).to_contain_text("Cursor loads it 3 times")
