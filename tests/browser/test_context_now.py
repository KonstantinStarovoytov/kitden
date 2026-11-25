"""Flow 15: Context when the skills changed after the last chat, as a person sees it: the fact of
the chat stays, and an estimate for the skills as they are now is said under it and drawn in the
bar and the two boxes. And the limit line counts the changes waiting in the preview, as the verdict
does. The medium sample's last Claude Code chat: 4 of 20 skills showed only a name at 1% of a 200K
window (8,000 characters)."""

import json
import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import SETTINGS, wait_until
from tests.browser.test_limit_line import bar_box, drag_to, open_context, readout

pytestmark = pytest.mark.browser

FACT = "4 of 20 skills showed only a name."
CHANGED = "Your skills changed after this list was sent. Your next chat will show the real list."
ADDED = ("changelog", "api-review")


def boxes(page) -> list[int]:
    """How many pills each of the two boxes holds."""
    sides = page.locator(".ctx-side")
    return [sides.nth(i).locator(".ctx-pill").count() for i in range(2)]


def pick(page, name: str):
    """The skill's pill; the switch in its Details. They stay open while the pill of a skill the
    preview turns off is off the page."""
    page.locator(f'.ctx-pill[data-skill="{name}"]').click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text(name)
    return details.get_by_role("group", name="State")


def switch(states, state: str) -> None:
    states.get_by_role("button", name=state, exact=True).click()


def picture_name(page):
    return page.locator(".ctx-zl").last


class TestAdded:
    """Two skills written to the sample after its last chat, 293 characters each."""

    @pytest.fixture
    def before_start(self):
        def write(home):
            for name in ADDED:
                path = home / ".claude/skills" / name / "SKILL.md"
                path.parent.mkdir(parents=True)
                text = "Use it when a change needs a careful plan. " * 7
                path.write_text(f"---\nname: {name}\ndescription: {text}\n---\nBody.\n")

        return write

    def test_skills_added_after_the_chat_are_said_and_drawn_as_an_estimate(self, page, demo):
        handle = open_context(page)
        main = page.get_by_role("main")
        # The fact: the verdict and the window card.
        expect(main).to_contain_text(FACT)
        window = main.get_by_role("button", name=re.compile(r"^200K window Last chat"))
        expect(window).to_contain_text("4 of 20 showed only a name")
        # The estimate, under it; the bar, the boxes and the limit line count the same.
        expect(main).to_contain_text(CHANGED)
        expect(main).to_contain_text(
            "Estimate: On a 200K window, 6 of 22 skills would show only a name."
        )
        expect(picture_name(page)).to_have_text("Skill list now, estimate")
        assert boxes(page) == [16, 6]
        expect(page.locator(".ctx-seg.over")).to_have_count(6)
        names = page.locator(".ctx-side.lo .ctx-pill")
        for name in ADDED:
            expect(names.filter(has_text=name)).to_have_count(1)
        expect(handle).to_have_attribute("aria-valuetext", "1% now · 6 of 22 show only a name")
        # Another window's estimate holds them too, and says nothing of the last chat.
        main.get_by_role("button", name=re.compile(r"^1M window Estimate")).click()
        expect(main).not_to_contain_text(CHANGED)
        expect(page.locator(".ctx-pill")).to_have_count(22)
        assert boxes(page) == [22, 0]


def test_a_skill_turned_off_after_the_chat_is_said_at_rest_until_undo(page, demo):
    before = SETTINGS(demo).read_bytes()
    open_context(page)
    main = page.get_by_role("main")
    expect(main).to_contain_text(FACT)
    expect(main).not_to_contain_text(CHANGED)
    expect(picture_name(page)).to_have_text("Skill list")
    assert boxes(page) == [16, 4]
    switch(pick(page, "dataviz"), "Off")
    expect(main).to_contain_text("After Apply, estimate: On a 200K window, every skill would keep")
    page.locator("#dock").get_by_role("button", name="Apply").click()
    undo = page.get_by_role("button", name="Undo")
    expect(undo).to_be_visible()
    assert json.loads(SETTINGS(demo).read_text())["skillOverrides"]["dataviz"] == "off"
    expect(main).to_contain_text(FACT)
    expect(main).to_contain_text(CHANGED)
    expect(main).to_contain_text("Estimate: On a 200K window, every skill would keep its")
    expect(main).to_contain_text(re.compile(r"Estimate: about [\d,]+ characters left before"))
    expect(picture_name(page)).to_have_text("Skill list now, estimate")
    assert boxes(page) == [19, 0]
    expect(page.locator(".ctx-seg.over")).to_have_count(0)
    expect(page.locator('.ctx-off .ctx-pill[data-skill="dataviz"]')).to_be_visible()
    undo.click()
    wait_until(lambda: SETTINGS(demo).read_bytes() == before, seconds=10)
    expect(main).not_to_contain_text(CHANGED)
    expect(picture_name(page)).to_have_text("Skill list")
    wait_until(lambda: boxes(page) == [16, 4])


def test_after_the_limit_is_raised_the_bar_shows_what_would_fit_now(page, demo):
    handle = open_context(page)
    expect(page.locator(".ctx-chip", has_text="Over the limit: not sent")).to_be_visible()
    handle.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    dock = page.locator("#dock")
    expect(dock).to_contain_text("Set the skill list limit of Claude Code to 1.1%")
    dock.get_by_role("button", name="Apply").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    main = page.get_by_role("main")
    expect(main).to_contain_text("The limit was changed after this chat: it is 1.1% now.")
    expect(main).to_contain_text(FACT)
    # Nothing over the limit in the bar, and no word of it under the handle.
    expect(picture_name(page)).to_have_text("Skill list now, estimate")
    expect(page.locator(".ctx-seg.over")).to_have_count(0)
    expect(page.locator(".ctx-chip", has_text="Over the limit: not sent")).to_have_count(0)
    assert boxes(page) == [20, 0]


def test_the_limit_line_counts_the_changes_waiting_in_the_preview(page, demo):
    handle = open_context(page)
    main = page.get_by_role("main")
    verdict = page.locator(".ctx-verdict")
    expect(handle).to_have_attribute("aria-valuetext", "1% now · 4 of 20 show only a name")
    # Off: the verdict, the boxes and the line count 19.
    states = pick(page, "release-notes")
    switch(states, "Off")
    expect(verdict).to_contain_text("3 of 19 skills would show only a name")
    expect(handle).to_have_attribute("aria-valuetext", "1% now · 3 of 19 show only a name")
    wait_until(lambda: boxes(page) == [16, 3])
    # Name only: it stays on the list.
    switch(states, "Name only")
    expect(verdict).to_contain_text("3 of 20 skills would show only a name")
    expect(handle).to_have_attribute("aria-valuetext", "1% now · 3 of 20 show only a name")
    # Back on: the row is gone, and the line counts as before.
    switch(states, "On")
    expect(main).to_contain_text(FACT)
    expect(handle).to_have_attribute("aria-valuetext", "1% now · 4 of 20 show only a name")
    expect(page.locator("#dock").get_by_role("button", name="Apply")).to_be_hidden()


def test_the_handle_stays_when_the_preview_makes_everything_fit_and_the_limit_waits_too(page, demo):
    handle = open_context(page)
    verdict = page.locator(".ctx-verdict")
    states = pick(page, "dataviz")
    switch(states, "Off")
    expect(verdict).to_contain_text("every skill would keep its description")
    expect(handle).to_have_attribute("aria-valuetext", "1% now · all 19 fit")
    # The readout of a drag counts the same, at every place.
    hold = bar_box(page)
    seen = drag_to(page, handle, hold["x"] + hold["width"] * 0.99)
    assert all("all 19 fit" in said for said in seen), seen
    assert readout(page).startswith("4% · all 19 fit")
    page.mouse.up()
    dock = page.locator("#dock")
    expect(dock).to_contain_text("Set the skill list limit of Claude Code to 4%")
    expect(handle).to_have_attribute("aria-valuetext", "4% · all 19 fit")
    # Both waiting: turned back on, the skill counts again, and the line still says the truth.
    switch(states, "On")
    expect(handle).to_have_attribute("aria-valuetext", re.compile(r"^4% · all 20 fit"))
    expect(verdict).to_contain_text("every skill would keep its description")
