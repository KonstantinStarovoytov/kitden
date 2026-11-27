"""Flow 15: Context when the skills changed after the last chat, as a person sees it: the fact of
the chat stays, and an estimate for the skills as they are now is said under it and drawn in the
bar and the two boxes. And the limit line counts the changes waiting in the preview, as the verdict
does. The medium sample's last Claude Code chat: 4 of 20 skills showed only a name at 1% of a 200K
window (8,000 characters). The Codex chats are those of tests/unit, written into the sample before
the page starts."""

import json
import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import SETTINGS, wait_until
from tests.browser.test_limit_line import (
    bar_box,
    codex_chat_alone,
    drag_to,
    open_codex,
    open_context,
    readout,
)

pytestmark = pytest.mark.browser

FACT = "4 of 20 skills showed only a name."
CHANGED = "Your skills changed after this list was sent. Start a new chat to see the new list."
ADDED = ("changelog", "api-review")


def boxes(page) -> list[int]:
    """How many pills of the groups show a description, and how many only a name (or cut): the
    two sides of the list as the bar draws it. Off ones, and those in no list, are on neither."""
    sent = page.locator(".ctx-group .ctx-pill:not(.lo):not(.apart):not(.off):not(.going)")
    return [sent.count(), page.locator(".ctx-group .ctx-pill.lo").count()]


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
        names = page.locator(".ctx-pill.lo")
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
    expect(page.locator('.ctx-pill.off[data-skill="dataviz"]')).to_be_visible()
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


class TestCodexAdded:
    """A Codex chat that sent three skills whole, and two more written after it: on that window
    four of the five would be cut."""

    @pytest.fixture
    def before_start(self):
        from tests.unit.test_context_now import add_later, roomy_chat

        def write(home):
            codex_chat_alone(home, roomy_chat)
            add_later(home)

        return write

    def test_codex_skills_added_after_the_chat_are_said_and_drawn_as_an_estimate(self, page, demo):
        handle = open_codex(page)
        main = page.get_by_role("main")
        fact = "all 3 skills were sent with full descriptions."
        expect(main).to_contain_text(fact)
        window = main.get_by_role("button", name=re.compile(r"Last chat · Nov 20"))
        expect(window).to_contain_text("All 3 sent in full")
        expect(main).to_contain_text(CHANGED)
        expect(main).to_contain_text(re.compile(r"Estimate: On a \d+K window, .*4 of 5 desc"))
        expect(picture_name(page)).to_have_text("Skill list now, estimate")
        assert boxes(page) == [1, 4]
        expect(page.locator(".ctx-seg.over")).to_have_count(4)
        for name in ("later1", "later2"):
            pill = page.locator(".ctx-pill.lo").filter(has_text=name)
            expect(pill).to_have_text(re.compile(rf"^{name}\d+ of \d+$"))
        expect(handle).to_have_attribute("aria-valuetext", re.compile(r"now · 4 of 5 cut short"))
        # Another window's estimate holds them too, and says nothing of the last chat.
        main.get_by_role("button", name=re.compile(r"^500K window Estimate")).click()
        expect(main).not_to_contain_text(CHANGED)
        wait_until(lambda: boxes(page) == [5, 0])
        window.click()
        # Off in the preview, they leave the estimate again.
        for name in ("later1", "later2"):
            switch(pick(page, name), "Off")
        verdict = page.locator(".ctx-verdict")
        expect(verdict).to_contain_text("every skill would keep its full description")
        expect(handle).to_have_attribute("aria-valuetext", re.compile(r"now · all 3 fit"))
        wait_until(lambda: boxes(page) == [3, 0])


class TestCodexOff:
    """The Codex chat of tests/unit/test_codex_limit.py: three skills on a tiny window, two of them
    cut short. Without the third the two fit."""

    @pytest.fixture
    def before_start(self):
        from tests.unit.test_codex_limit import cut_chat

        return lambda home: codex_chat_alone(home, cut_chat)

    def test_a_codex_skill_turned_off_after_the_chat_is_said_at_rest_until_undo(self, page, demo):
        config = demo.home / ".codex/config.toml"
        before = config.read_bytes()
        open_codex(page)
        main = page.get_by_role("main")
        fact = re.compile(r"2 of 3 descriptions were cut to \d+–\d+ characters")
        expect(main).to_contain_text(fact)
        expect(main).not_to_contain_text(CHANGED)
        expect(picture_name(page)).to_have_text("Skill list")
        assert boxes(page) == [1, 2]
        switch(pick(page, "gamma"), "Off")
        expect(main).to_contain_text("After Apply, estimate: ")
        page.locator("#dock").get_by_role("button", name="Apply").click()
        undo = page.get_by_role("button", name="Undo")
        expect(undo).to_be_visible()
        assert b"enabled = false" in config.read_bytes()
        expect(main).to_contain_text(fact)
        expect(main).to_contain_text(CHANGED)
        expect(main).to_contain_text(
            re.compile(r"Estimate: On a \d+K window, every skill would keep its full description")
        )
        expect(main).to_contain_text(re.compile(r"Estimate: about [\d,]+ tokens left before"))
        expect(picture_name(page)).to_have_text("Skill list now, estimate")
        wait_until(lambda: boxes(page) == [2, 0])
        expect(page.locator(".ctx-seg.over")).to_have_count(0)
        expect(page.locator('.ctx-pill.off[data-skill="gamma"]')).to_be_visible()
        undo.click()
        wait_until(lambda: config.read_bytes() == before, seconds=10)
        expect(main).not_to_contain_text(CHANGED)
        expect(picture_name(page)).to_have_text("Skill list")
        wait_until(lambda: boxes(page) == [1, 2])
