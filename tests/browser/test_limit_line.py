"""Flow 14: the skill list limit on the Context page, as a person does it (specs
skill-list-limit and limit-line-control). The limit line on the skill list's bar is the control:
its flag opens Details ("Set to 1.5%", Apply, Undo), its handle drags place by place with the
server's words and snaps at the place where everything fits, and keys do the same. Claude Code on
the medium sample: 4 of 20 skills showed only a name at 1% of a 200K window (8,000 characters);
1.5% fits all 20."""

import json
import os
import re
import tomllib

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import wait_until
from tests.browser.test_map_drag import still_box

pytestmark = pytest.mark.browser

SUGGESTED = "1.5% · all 20 fit · about 650 more characters per chat"
TODAY = "1% now · 4 of 20 show only a name"


def open_context(page):
    """Context on Claude Code: its limit handle, once it is on the page."""
    # The hash, not goto: goto would reload the page while its first reads run.
    page.evaluate("location.hash = '#context'")
    handle = page.get_by_role("slider", name="Skill list limit")
    expect(handle).to_be_visible()
    # The page takes no pointer while it changes place (app.js `place-change`).
    wait_until(
        lambda: not page.evaluate("document.documentElement.classList.contains('place-change')")
    )
    return handle


def bar_box(page) -> dict:
    """The skill list bar's box once it stands still: the page makes room while Details close
    (240 ms), and a drag aimed at a box read meanwhile lands short."""
    return still_box(page.locator(".ctx-hold"))


def center(locator) -> tuple[float, float]:
    box = locator.bounding_box()
    assert box is not None
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def readout(page) -> str:
    return page.locator(".ctx-readout").inner_text()


def settings(home) -> dict:
    path = home / ".claude/settings.json"
    return json.loads(path.read_text()) if path.exists() else {}


def api_reads(page) -> list[str]:
    """The page's reads of /api/, from now on, as the browser asks for them."""
    seen: list[str] = []
    page.on("request", lambda request: "/api/" in request.url and seen.append(request.url))
    return seen


def drag_to(page, handle, target_x: float, steps: int = 20) -> list[str]:
    """Press on the handle and move to target_x in steps, as a person moves the mouse; the
    readout after each move. The button stays down."""
    x, y = center(handle)
    page.mouse.move(x, y)
    page.mouse.down()
    seen = []
    for n in range(1, steps + 1):
        page.mouse.move(x + (target_x - x) * n / steps, y)
        if page.locator(".ctx-readout").is_visible():
            seen.append(readout(page))
    return seen


def test_the_flag_opens_details_and_set_to_applies_then_undo_brings_the_first_state_back(
    page, demo
):
    before = settings(demo.home)
    handle = open_context(page)
    flag = page.locator(".ctx-flag")
    expect(flag).to_have_text("Limit: 8,000 characters")
    # It shows it can be acted on: the grab cursor, and words on hover.
    assert handle.evaluate("node => getComputedStyle(node).cursor") == "grab"
    handle.hover()
    expect(page.locator("#tip")).to_contain_text("Drag the line to set the limit")
    flag.click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("Skill list limit")
    expect(details).to_contain_text("Now1% of the context window: 8,000 characters")
    expect(details).to_contain_text("Suggested1.5%: all 20 skills get their description")
    expect(details).to_contain_text("CostAbout 650 more characters in every chat")
    details.get_by_role("button", name="Set to 1.5%").click()
    dock = page.locator("#dock")
    expect(dock).to_contain_text("Set the skill list limit of Claude Code to 1.5%")
    dock.get_by_role("button", name="Apply").click()
    undo = page.get_by_role("button", name="Undo")
    expect(undo).to_be_visible()
    assert settings(demo.home)["skillListingBudgetFraction"] == 0.015
    main = page.get_by_role("main")
    expect(main).to_contain_text("The limit was changed after this chat: it is 1.5% now.")
    expect(main).to_contain_text("Estimate: On a 200K window, every skill would keep")
    # The chat's own limit line stays at 8,000; the next chats' line is at 12,000.
    expect(flag).to_have_text("Limit: 8,000 characters")
    expect(page.locator(".ctx-next-tag")).to_have_text("Next chats: 12,000 characters")
    undo.click()
    wait_until(lambda: settings(demo.home) == before, seconds=10)
    expect(main).not_to_contain_text("The limit was changed after this chat")
    expect(page.locator(".ctx-next-tag")).to_be_hidden()


def test_a_drag_moves_place_by_place_snaps_and_a_release_adds_the_row_with_no_read(page):
    handle = open_context(page)
    hold = bar_box(page)
    reads = api_reads(page)
    # To the bar's right end: every place up to 5%, one after another.
    seen = drag_to(page, handle, hold["x"] + hold["width"] * 0.99, steps=40)
    places = list(dict.fromkeys(seen))
    assert places[0] in (TODAY, SUGGESTED)
    assert SUGGESTED in places
    assert [p.split(" ")[0] for p in places if not p.startswith("1% ")] == [
        "1.5%",
        "2%",
        "2.5%",
        "3%",
        "3.5%",
        "4%",
        "4.5%",
        "5%",
    ]
    assert reads == [], "a drag reads nothing from the server"
    # Back near the suggested place, a little past it: it snaps there, the mark shows it.
    mark_x, _ = center(page.locator(".ctx-mark"))
    page.mouse.move(mark_x + hold["width"] * 0.02, center(handle)[1])
    assert readout(page) == SUGGESTED
    page.mouse.up()
    dock = page.locator("#dock")
    expect(dock).to_contain_text("Set the skill list limit of Claude Code to 1.5%")
    # Dragged back to today's place, the row is gone.
    line_x, _ = center(page.locator(".ctx-limit"))
    drag_to(page, page.get_by_role("slider", name="Skill list limit"), line_x)
    assert readout(page) == TODAY
    page.mouse.up()
    expect(dock.get_by_role("button", name="Apply")).to_be_hidden()


def test_the_hover_words_stay_off_the_tag_after_a_drag_until_the_pointer_comes_back(page):
    handle = open_context(page)
    hold = bar_box(page)
    tip = page.locator("#tip")
    tag = page.locator(".ctx-next-tag")
    # Drag to the suggested place and let go with the pointer still on the handle.
    drag_to(page, handle, hold["x"] + hold["width"] * 0.3)
    mark_x, y = center(page.locator(".ctx-mark"))
    page.mouse.move(mark_x, y)
    assert readout(page) == SUGGESTED
    page.mouse.up()
    expect(tag).to_have_text("Next chats: 12,000 characters")
    # The hover words wait 400 ms after the pointer rests; a negative check has to outlast that.
    page.wait_for_timeout(1000)
    expect(tip).to_be_hidden()
    # They are back once the pointer has left the handle and returns.
    page.mouse.move(mark_x, y + 150)
    page.mouse.move(*center(handle))
    expect(tip).to_contain_text("Drag the line to set the limit")


def test_the_hover_words_stay_off_the_tag_after_a_key_move_until_the_pointer_comes_back(page):
    handle = open_context(page)
    handle.hover()
    expect(page.locator("#tip")).to_contain_text("Drag the line to set the limit")
    # A key moves it while the pointer rests on it: the words go and stay gone.
    handle.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    expect(page.locator(".ctx-next-tag")).to_have_text("Next chats: 12,000 characters")
    page.wait_for_timeout(1000)
    expect(page.locator("#tip")).to_be_hidden()
    x, y = center(handle)
    page.mouse.move(x, y + 150)
    page.mouse.move(x, y)
    expect(page.locator("#tip")).to_contain_text("Drag the line to set the limit")


def test_escape_during_a_drag_changes_nothing(page):
    handle = open_context(page)
    mark_x = bar_box(page)
    drag_to(page, handle, mark_x["x"] + mark_x["width"] * 0.97)
    expect(page.locator(".ctx-readout")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".ctx-readout")).to_be_hidden()
    page.mouse.up()
    expect(page.locator("#dock").get_by_role("button", name="Apply")).to_be_hidden()
    expect(handle).to_have_attribute("aria-valuetext", TODAY)


def test_keys_only_tab_to_the_handle_move_commit_take_back_and_open_details(page):
    open_context(page)
    page.locator("body").click(position={"x": 5, "y": 5})
    for _ in range(80):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.getAttribute('role')") == "slider":
            break
    else:
        raise AssertionError("Tab never reached the limit handle")
    handle = page.get_by_role("slider", name="Skill list limit")
    page.keyboard.press("ArrowRight")
    expect(handle).to_have_attribute("aria-valuetext", SUGGESTED)
    page.keyboard.press("ArrowRight")
    expect(handle).to_have_attribute("aria-valuetext", re.compile(r"^2% · all 20 fit"))
    page.keyboard.press("Enter")
    dock = page.locator("#dock")
    expect(dock).to_contain_text("Set the skill list limit of Claude Code to 2%")
    # Focus stays on the handle as the page draws the row's estimate.
    expect(handle).to_be_focused()
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")
    expect(handle).to_have_attribute("aria-valuetext", TODAY)
    page.keyboard.press("Enter")
    expect(dock.get_by_role("button", name="Apply")).to_be_hidden()
    expect(handle).to_be_focused()
    # Enter with no move opens Details; closing them brings focus back to the handle.
    page.keyboard.press("Enter")
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("Skill list limit")
    details.get_by_role("button", name="Close").click()
    expect(handle).to_be_focused()


def test_drag_steps_are_measured_and_fast(page):
    handle = open_context(page)
    hold = bar_box(page)
    page.evaluate("performance.clearMeasures('kitden:limit-step')")
    drag_to(page, handle, hold["x"] + hold["width"] * 0.99, steps=60)
    page.keyboard.press("Escape")
    page.mouse.up()
    steps = page.evaluate(
        "performance.getEntriesByName('kitden:limit-step').map(entry => entry.duration)"
    )
    assert len(steps) >= 9, steps
    # The aim is under 16 ms a step; this catches a step that redraws the page.
    assert sum(steps) / len(steps) < 50, steps


@pytest.fixture
def narrow(browser, demo):
    """A tab 800 px wide, with reduced motion."""
    context = browser.new_context(viewport={"width": 800, "height": 900}, reduced_motion="reduce")
    tab = context.new_page()
    errors: list[str] = []
    tab.on("console", lambda message: message.type == "error" and errors.append(message.text))
    tab.on("pageerror", lambda error: errors.append(str(error)))
    tab.goto(demo.url)
    yield tab
    context.close()
    if errors:
        pytest.fail("The page had errors:\n" + "\n".join(errors))


def test_at_800_px_with_reduced_motion_the_drag_gives_the_same_places(narrow):
    handle = open_context(narrow)
    hold = bar_box(narrow)
    seen = drag_to(narrow, handle, hold["x"] + hold["width"] * 0.99, steps=40)
    assert SUGGESTED in seen and seen[-1].startswith("5% ")
    # The readout stays inside the window.
    box = narrow.locator(".ctx-readout").bounding_box()
    assert box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 800
    narrow.keyboard.press("Escape")
    narrow.mouse.up()


class TestBackToTheDefault:
    """A share already above the default in the user settings: the line drags back to 1%, which
    takes the key out."""

    @pytest.fixture
    def before_start(self):
        def write(home):
            path = home / ".claude/settings.json"
            data = json.loads(path.read_text()) if path.exists() else {}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({**data, "skillListingBudgetFraction": 0.015}))

        return write

    def test_the_line_drags_back_to_one_percent_and_apply_takes_the_key_out(self, page, demo):
        handle = open_context(page)
        main = page.get_by_role("main")
        expect(main).to_contain_text("The limit was changed after this chat: it is 1.5% now.")
        expect(handle).to_have_attribute("aria-valuetext", "1.5% now · all 20 fit")
        line_x, _ = center(page.locator(".ctx-limit"))
        drag_to(page, handle, line_x)
        assert readout(page).startswith("1%, the default · 4 of 20 show only a name")
        page.mouse.up()
        dock = page.locator("#dock")
        expect(dock).to_contain_text("Set the skill list limit of Claude Code back to 1%")
        dock.get_by_role("button", name="Apply").click()
        expect(page.get_by_role("button", name="Undo")).to_be_visible()
        assert "skillListingBudgetFraction" not in settings(demo.home)


class TestCodex:
    """Stage 2: the same control on the Codex card. The medium sample's Codex chat fits, so a
    newer Codex chat is written into the sample before the page starts: the cut-short chat of
    tests/unit/test_codex_limit.py (three skills on a tiny window, two cut short). 500 tokens fit
    all three."""

    @pytest.fixture
    def before_start(self):
        from tests.unit.test_codex_limit import cut_chat

        def write(home):
            # Later than the sample's own Codex chat, in its time and its file's, so it is the
            # last chat.
            cut_chat(home, at="2026-11-20T12:00:00Z")
            for log in (home / ".codex/sessions").rglob("rollout-a.jsonl"):
                os.utime(log)

        return write

    def test_the_codex_line_drags_to_500_tokens_applies_and_undo(self, page, demo):
        config = demo.home / ".codex/config.toml"
        before = config.read_bytes() if config.exists() else None
        page.evaluate("location.hash = '#context'")
        main = page.get_by_role("main")
        codex = main.get_by_role("group", name="Client").get_by_role("button", name="Codex")
        codex.click()
        expect(codex).to_have_attribute("aria-pressed", "true")
        handle = page.get_by_role("slider", name="Skill list limit")
        expect(handle).to_have_attribute("aria-valuetext", re.compile(r"tokens now · 2 of 3 cut"))
        wait_until(
            lambda: not page.evaluate("document.documentElement.classList.contains('place-change')")
        )
        page.locator(".ctx-flag").click()
        details = page.get_by_role("complementary", name="Details")
        expect(details).to_contain_text("2% of the context window:")
        expect(details).to_contain_text(
            "Suggested500 tokens: no description is cut and no skill is left out"
        )
        details.get_by_role("button", name="Close").click()
        reads = api_reads(page)
        mark = bar_box(page)
        seen = drag_to(page, handle, mark["x"] + mark["width"] * 0.99, steps=40)
        assert reads == [], "a drag reads nothing from the server"
        assert any(s.startswith("500 tokens · all 3 fit") for s in seen)
        assert seen[-1].startswith("10,000 tokens · all 3 fit")
        mark_x, _ = center(page.locator(".ctx-mark"))
        page.mouse.move(mark_x + 2, center(handle)[1])
        assert readout(page).startswith("500 tokens · all 3 fit")
        page.mouse.up()
        dock = page.locator("#dock")
        expect(dock).to_contain_text("Set the skill list limit of Codex to 500 tokens")
        dock.get_by_role("button", name="Apply").click()
        undo = page.get_by_role("button", name="Undo")
        expect(undo).to_be_visible()
        assert tomllib.loads(config.read_text())["skills"]["max_context_tokens"] == 500
        expect(main).to_contain_text("The limit was changed after this chat: it is 500 tokens now.")
        undo.click()
        wait_until(lambda: (config.read_bytes() if config.exists() else None) == before, seconds=10)
