"""Flow 5: add a skill found in a catalog to Claude Code, then remove it. The catalog and the
skill's files answer from tests/offline.py."""

import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import wait_until

pytestmark = pytest.mark.browser

SKILL = "mcp-builder"


def test_a_skill_from_the_catalog_is_added_to_claude_code_and_removed(sample_page, sample):
    page = sample_page
    skill_file = sample.home / f".claude/skills/{SKILL}/SKILL.md"
    assert not skill_file.exists()
    page.get_by_role("link", name="Library", exact=True).click()
    page.get_by_role("button", name="+ Add plugins").click()
    panel = page.get_by_role("complementary", name="Details")
    panel.get_by_role("searchbox", name="Search catalogs").fill("mcp")
    panel.get_by_role("button", name="Search").click()
    panel.get_by_role("button", name=f"{SKILL} anthropics/skills 137.3K installs").click()
    item = page.get_by_role("region", name="Item details")
    # The label, as a person clicks it: the box itself is drawn over.
    item.get_by_role("group", name="Add to").get_by_text("Claude Code", exact=True).click()
    expect(item.get_by_role("checkbox", name="Claude Code")).to_be_checked()
    item.get_by_role("button", name="Preview").click()
    dock = page.locator("#dock")
    expect(dock).to_contain_text(f"Add {SKILL} to Claude Code")
    assert not skill_file.exists()
    dock.get_by_role("button", name="Apply").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    wait_until(skill_file.exists, 15)
    assert skill_file.read_text().startswith(f"---\nname: {SKILL}\n")
    # Remove it again, from its row in the Library's list.
    panel.get_by_role("button", name="Close").click()
    page.get_by_role("main").get_by_role("group", name="Show as").get_by_role(
        "button", name="List"
    ).click()
    row = page.get_by_role("row", name=re.compile(rf"^{SKILL} Skill "))
    row.get_by_role("gridcell").first.click()
    details = page.get_by_role("complementary", name="Details")
    details.get_by_role("button", name="Remove from Claude Code…").click()
    dock.get_by_role("button", name="Apply").click()
    wait_until(lambda: not skill_file.parent.exists(), 15)
    expect(row).to_have_count(0)
