"""Flow 2: Context shows what Claude Code's last chat loaded on a 200K window, and which of
the user's skills were cut to a name; Codex had room for all of its own."""

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.browser

# The medium sample's last Claude Code chat (tests/unit/test_demo_home.py): 4 of 20 skills
# showed only a name.
NAME_ONLY = ["brandkit", "release-notes", "shared-style", "planning"]
# Its last Codex chat had room for all four of Codex's own skills.
CODEX = ["api-style", "code-review", "docker-expert", "langfuse"]


def test_context_shows_the_last_chat_and_the_skills_that_were_cut(page, demo):
    page.get_by_role("link", name="Context", exact=True).click()
    main = page.get_by_role("main")
    expect(main.get_by_role("heading", name="Do your skills fit?")).to_be_visible()
    window = main.get_by_role("button", name=re.compile(r"^200K window Last chat"))
    expect(window).to_have_attribute("aria-pressed", "true")
    expect(window).to_contain_text("4 of 20 showed only a name")
    expect(main.get_by_text("4 of 20 skills showed only a name")).to_be_visible()
    # Under "Name only": these four, by name and size, and no other.
    side = main.locator("section").filter(has=page.get_by_role("heading", name="Name only"))
    pills = side.get_by_role("button")
    expect(pills).to_have_count(len(NAME_ONLY))
    for name in NAME_ONLY:
        expect(side.get_by_role("button", name=re.compile(rf"^{name} [\d,]+$"))).to_be_visible()
    # Codex: every skill fits, all four of its own under "Full description".
    codex = main.get_by_role("group", name="Client").get_by_role("button", name="Codex")
    codex.click()
    expect(codex).to_have_attribute("aria-pressed", "true")
    full = main.locator("section").filter(has=page.get_by_role("heading", name="Full description"))
    expect(full.get_by_role("button")).to_have_count(len(CODEX))
    for name in CODEX:
        expect(full.get_by_role("button", name=re.compile(rf"^{name} [\d,]+$"))).to_be_visible()
    # Codex's own words: its last chat's window says all four were sent in full, none cut short.
    window = main.get_by_role("button", name=re.compile(r" window Last chat"), pressed=True)
    expect(window).to_contain_text(f"All {len(CODEX)} sent in full")
    cut = main.locator("section").filter(has=page.get_by_role("heading", name="Cut short"))
    expect(cut.get_by_role("button")).to_have_count(0)
