"""One Details panel for a skill: Context and the Library offer the same actions, in the same
order, and Context adds only its own facts. The medium sample, with brandkit turned off in
atlas's local settings (the last Claude Code chat was in atlas)."""

import pytest
from playwright.sync_api import expect

from tests.browser.test_limit_line import open_context
from tests.browser.test_one_state import library

pytestmark = pytest.mark.browser


@pytest.fixture
def before_start():
    def write(home):
        local = home / "work/atlas/.claude/settings.local.json"
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text('{"skillOverrides": {"brandkit": "off"}}\n')

    return write


def actions(details) -> list[str]:
    """The names of every button in the Details' footer and switches, More opened."""
    more = details.get_by_role("button", name="More")
    if more.count():
        more.first.click()
    footer = details.locator("footer button, .skill-switches button, .copies button")
    # The Library's link to Context is a way there, not an action on the skill.
    skip = {"More", "Show in Context"}
    return [name.strip() for name in footer.all_inner_texts() if name.strip() not in skip]


def test_a_skill_has_one_details_panel_on_context_and_in_the_library(page, demo):
    open_context(page)
    page.locator('.ctx-pill[data-skill="brandkit"]').first.click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("brandkit")
    # Context adds its facts: the description's size.
    expect(details).to_contain_text("Size")
    on_context = actions(details)
    library_details = library(page, "skill:brandkit", kind="skill")
    expect(library_details).to_contain_text("brandkit")
    assert on_context == actions(library_details)
    assert "Turn off in some projects…" in on_context


def test_a_skill_off_in_the_last_chats_project_says_where(page, demo):
    """All projects picked, the last chat in atlas: the pill says Off in atlas, and Details name
    atlas beside On for all projects, in one sentence."""
    open_context(page)
    pill = page.locator('.ctx-pill[data-skill="brandkit"]').first
    expect(pill).to_contain_text("Off in atlas")
    pill.click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("On · Off in atlas")
    expect(details).to_contain_text("every project except atlas")
