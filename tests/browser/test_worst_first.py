"""Step 5 of the UX audit: the page leads to what hurts most and to the simplest fix. The medium
sample, with four skills that Cursor loads twice each (`~/.claude/skills` and `~/.cursor/skills`,
so keeping Claude Code's copy costs no client the skill)."""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.browser

FOLDERS = (".claude/skills", ".cursor/skills")
COPIED = ("dup-a", "dup-b", "dup-c", "dup-d")


@pytest.fixture
def before_start():
    def write(home):
        for name in COPIED:
            for folder in FOLDERS:
                skill = home / folder / name / "SKILL.md"
                skill.parent.mkdir(parents=True, exist_ok=True)
                skill.write_text(f"---\nname: {name}\ndescription: Use when copied.\n---\n")

    return write


def test_the_first_card_is_the_skill_list_with_its_fix(page, demo):
    # 02-N06, 05-P3: the skill list card came after the file and copy cards, and only opened
    # Context. Now it is first, and its button is the suggested limit.
    first = page.locator(".ov-group[data-group=attention] .ov-cards > *").first
    expect(first).to_contain_text("Skill list in Claude Code")
    expect(first).to_contain_text("Set to 1.1% fits them: about")
    first.get_by_role("button", name="Set to 1.1%", exact=True).click()
    expect(first.get_by_role("button", name="In preview")).to_be_visible()


def test_many_copy_cards_fold_into_one_row(page, demo):
    # 02-N06: one kind of card cannot push the rest down.
    row = page.locator(".ov-card-fold")
    expect(row).to_contain_text("4 skills load more than once")
    cards = row.locator(".ov-fold-cards")
    expect(cards).to_be_hidden()
    row.get_by_role("button", name="Show", exact=True).click()
    expect(cards.locator("[data-card]")).to_have_count(4)
    expect(cards.get_by_role("button", name="Keep one…")).to_have_count(4)
    # Plain buttons inside the fold: only the row's own button is primary.
    expect(cards.locator(".btn.primary")).to_have_count(0)
    row.get_by_role("button", name="Hide").click()
    expect(cards).to_be_hidden()


def test_the_unreadable_file_card_names_its_project_and_copies_its_path(page, demo):
    # 02-N05: "Could not read mcp.json" named no path and did nothing.
    card = page.locator("[data-card]").filter(has_text="Could not read mcp.json")
    expect(card).to_contain_text("In project website")
    expect(card.get_by_role("button", name="Copy path")).to_be_visible()


def test_context_shows_the_fix_under_the_problem(page, demo):
    # 05-P3: the fix showed only after a press on the small limit label.
    page.evaluate("location.hash = '#context'")
    fix = page.locator(".ctx-fix")
    expect(fix).to_contain_text("1.1%: all 24 skills fit")
    expect(fix).to_contain_text("more characters in every chat")
    fix.get_by_role("button", name="Set to 1.1%").click()
    expect(fix.get_by_role("button", name="Set to 1.1%")).to_have_attribute("aria-pressed", "true")
    # 05-P6: what Kitden does not measure is said on the picture.
    expect(page.locator(".ctx-zoom")).to_contain_text("not measured (system prompt, MCP tools")


def test_the_search_says_what_it_finds_on_each_tab(page, demo):
    # 02-N02: from the Overview the search went to the Library, which has no servers.
    expect(
        page.get_by_role("searchbox", name="Search skills, plugins and marketplaces")
    ).to_be_visible()
    page.evaluate("location.hash = '#gateway'")
    expect(page.get_by_role("searchbox", name="Search servers and tools")).to_be_visible()
