"""Flow 14: the skill list limit on the Context page, as a person does it (specs
skill-list-limit and limit-line-control). The limit line on the skill list's bar is the control:
its flag opens Details ("Set to 1.1%", Apply, Undo), its handle drags place by place with the
server's words and snaps at the place where everything fits, and keys do the same. Claude Code on
the medium sample: 4 of 20 skills showed only a name at 1% of a 200K window (8,000 characters);
1.1% (8,800) fits all 20. The places are the shares of `CLAUDE_SHARES`: 1% to 4%."""

import itertools
import json
import os
import re
import shutil
import tomllib
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import wait_until
from tests.browser.test_map_drag import still_box

pytestmark = pytest.mark.browser

SUGGESTED = "1.1% · all 20 fit · about 650 more characters per chat"
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
    """The page's reads of /api/, from now on, as the browser asks for them. Not /api/update: the
    page looks there every 3 s by itself while the latest version is not known (update.js, ASKS),
    and a slow drag can fall on such a look."""
    seen: list[str] = []

    def note(request) -> None:
        path = urlsplit(request.url).path
        if path.startswith("/api/") and path != "/api/update":
            seen.append(request.url)

    page.on("request", note)
    return seen


def still_center(locator) -> tuple[float, float]:
    """The middle of the element once it stands still: the limit line's parts glide 160 ms to a
    new place and move 240 ms with the bar when it is drawn again."""
    box = still_box(locator)
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def drag_to(page, handle, target_x: float, steps: int = 20) -> list[str]:
    """Press on the handle and move to target_x in steps, as a person moves the mouse; the
    readout after each move. The button stays down."""
    x, y = still_center(handle)
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
    expect(details).to_contain_text("Suggested1.1%: all 20 skills get their description")
    expect(details).to_contain_text("CostAbout 650 more characters in every chat")
    details.get_by_role("button", name="Set to 1.1%").click()
    dock = page.locator("#dock")
    expect(dock).to_contain_text("Set the skill list limit of Claude Code to 1.1%")
    dock.get_by_role("button", name="Apply").click()
    undo = page.get_by_role("button", name="Undo")
    expect(undo).to_be_visible()
    assert settings(demo.home)["skillListingBudgetFraction"] == 0.011
    main = page.get_by_role("main")
    expect(main).to_contain_text("The limit was changed after this chat: it is 1.1% now.")
    expect(main).to_contain_text("Estimate: On a 200K window, every skill would keep")
    # The chat's own limit line stays at 8,000; the next chats' line is at 8,800.
    expect(flag).to_have_text("Limit: 8,000 characters")
    expect(page.locator(".ctx-next-tag")).to_have_text("Next chats: 8,800 characters")
    undo.click()
    wait_until(lambda: settings(demo.home) == before, seconds=10)
    expect(main).not_to_contain_text("The limit was changed after this chat")
    expect(page.locator(".ctx-next-tag")).to_be_hidden()


def test_a_drag_moves_place_by_place_snaps_and_a_release_adds_the_row_with_no_read(page):
    handle = open_context(page)
    hold = bar_box(page)
    reads = api_reads(page)
    # To the bar's right end: every place up to 4%, one after another.
    seen = drag_to(page, handle, hold["x"] + hold["width"] * 0.99, steps=40)
    places = list(dict.fromkeys(seen))
    assert places[0] in (TODAY, SUGGESTED)
    assert SUGGESTED in places
    assert [p.split(" ")[0] for p in places if not p.startswith("1% ")] == [
        "1.1%",
        "1.2%",
        "1.3%",
        "1.4%",
        "1.5%",
        "1.7%",
        "2%",
        "2.5%",
        "3%",
        "3.5%",
        "4%",
    ]
    assert reads == [], "a drag reads nothing from the server"
    # Back near the suggested place, a little past it: it snaps there, the mark shows it.
    mark_x, _ = still_center(page.locator(".ctx-mark"))
    page.mouse.move(mark_x + hold["width"] * 0.015, center(handle)[1])
    assert readout(page) == SUGGESTED
    page.mouse.up()
    dock = page.locator("#dock")
    expect(dock).to_contain_text("Set the skill list limit of Claude Code to 1.1%")
    # Dragged back to today's place, the row is gone.
    line_x, _ = still_center(page.locator(".ctx-limit"))
    drag_to(page, page.get_by_role("slider", name="Skill list limit"), line_x)
    assert readout(page) == TODAY
    page.mouse.up()
    expect(dock.get_by_role("button", name="Apply")).to_be_hidden()


def test_a_drag_through_the_first_three_places_releases_on_the_third(page, demo):
    handle = open_context(page)
    hold = bar_box(page)
    reads = api_reads(page)
    x, y = center(handle)
    page.mouse.move(x, y)
    page.mouse.down()
    # A first move makes it a drag; the mark of the suggested place (1.1%) shows then.
    page.mouse.move(x + 10, y)
    seen = [readout(page)]
    mark_x, _ = center(page.locator(".ctx-mark"))
    # The places past the suggested one are 3% of the bar apart: 1.2% is the next one.
    third = mark_x + hold["width"] * 0.03
    for n in range(1, 31):
        page.mouse.move(x + 10 + (third - x - 10) * n / 30, y)
        seen.append(readout(page))
    places = list(dict.fromkeys(seen))
    assert [p.split(" · ")[0] for p in places] == ["1% now", "1.1%", "1.2%"], places
    assert places[2] == "1.2% · all 20 fit · about 650 more characters per chat"
    assert reads == [], "a drag reads nothing from the server"
    page.mouse.up()
    dock = page.locator("#dock")
    expect(dock).to_contain_text("Set the skill list limit of Claude Code to 1.2%")
    expect(page.locator(".ctx-next-tag")).to_have_text("Next chats: 9,600 characters")
    dock.get_by_role("button", name="Apply").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    assert settings(demo.home)["skillListingBudgetFraction"] == 0.012


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
    expect(tag).to_have_text("Next chats: 8,800 characters")
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
    expect(page.locator(".ctx-next-tag")).to_have_text("Next chats: 8,800 characters")
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
    expect(handle).to_have_attribute("aria-valuetext", re.compile(r"^1\.2% · all 20 fit"))
    page.keyboard.press("Enter")
    dock = page.locator("#dock")
    expect(dock).to_contain_text("Set the skill list limit of Claude Code to 1.2%")
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


def test_the_handle_glides_to_the_next_place_and_ends_there(page):
    handle = open_context(page)
    hold = bar_box(page)
    assert "left" in handle.evaluate("node => getComputedStyle(node).transitionProperty")
    handle.focus()
    page.keyboard.press("ArrowRight")
    # The words change at once; the handle is on its way.
    expect(handle).to_have_attribute("aria-valuetext", SUGGESTED)
    assert readout(page) == SUGGESTED
    # It ends where the place is: its left, in % of the bar.
    box = still_box(handle)
    left = float(handle.evaluate("node => node.style.left").rstrip("%"))
    expected = hold["x"] + hold["width"] * left / 100
    assert abs(box["x"] + box["width"] / 2 - expected) < 1, (box, expected)
    assert handle.evaluate("node => node.getAnimations().length") == 0
    page.keyboard.press("Escape")


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
    assert SUGGESTED in seen and seen[-1].startswith("4% ")
    # The readout stays inside the window.
    box = narrow.locator(".ctx-readout").bounding_box()
    assert box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 800
    narrow.keyboard.press("Escape")
    narrow.mouse.up()


def test_with_reduced_motion_the_line_lands_on_each_place_at_once(narrow):
    handle = open_context(narrow)
    parts = ".ctx-grip, .ctx-next, .ctx-next-tag, .ctx-readout"
    nodes = f"[...document.querySelectorAll({parts!r})]"
    said = narrow.evaluate(f"{nodes}.map(n => getComputedStyle(n).transitionProperty)")
    assert said and all(p == "none" for p in said), said
    handle.focus()
    narrow.keyboard.press("ArrowRight")
    expect(handle).to_have_attribute("aria-valuetext", SUGGESTED)
    moving = narrow.evaluate(f"{nodes}.flatMap(n => n.getAnimations()).length")
    assert moving == 0
    narrow.keyboard.press("Escape")


def test_at_800_px_the_twelve_places_are_apart_and_each_can_be_had_with_the_pointer(narrow):
    handle = open_context(narrow)
    hold = bar_box(narrow)
    x0, y = center(handle)
    # Walk the right half of the bar with the button down, and note where the handle stands at
    # each place.
    narrow.mouse.move(x0, y)
    narrow.mouse.down()
    stands: dict[str, float] = {}
    for n in range(201):
        narrow.mouse.move(hold["x"] + hold["width"] * (0.5 + 0.5 * n / 200), y)
        if narrow.locator(".ctx-readout").is_visible():
            stands.setdefault(readout(narrow).split(" · ")[0], center(handle)[0])
    narrow.keyboard.press("Escape")
    narrow.mouse.up()
    assert len(stands) == 12, stands
    xs = list(stands.values())
    assert xs == sorted(xs)
    # Each place is further from the next than the handle is wide (12 px): a drag can land on it.
    gaps = [b - a for a, b in itertools.pairwise(xs)]
    assert min(gaps) >= 12, (min(gaps), stands)
    # The pointer put on a place gives that place, for every place.
    for name, x in stands.items():
        narrow.mouse.move(x0, y)
        narrow.mouse.down()
        narrow.mouse.move((x0 + x) / 2, y)
        narrow.mouse.move(x, y)
        assert readout(narrow).split(" · ")[0] == name, (name, readout(narrow))
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
        line_x, _ = still_center(page.locator(".ctx-limit"))
        drag_to(page, handle, line_x)
        assert readout(page).startswith("1%, the default · 4 of 20 show only a name")
        page.mouse.up()
        dock = page.locator("#dock")
        expect(dock).to_contain_text("Set the skill list limit of Claude Code back to 1%")
        dock.get_by_role("button", name="Apply").click()
        expect(page.get_by_role("button", name="Undo")).to_be_visible()
        assert "skillListingBudgetFraction" not in settings(demo.home)


class TestCounted:
    """A chat the rule cannot rebuild: the sample's chat, with the skills it showed by name the
    most used since, so the rule gives another list. Kitden counts what all descriptions need."""

    @pytest.fixture
    def before_start(self):
        def write(home):
            path = home / ".claude.json"
            data = json.loads(path.read_text())
            usage = data["skillUsage"]
            # The least used were dropped: turned round, they would be the first to fit.
            counts = [use["usageCount"] for use in usage.values()]
            most = max(counts)
            for use in usage.values():
                use["usageCount"] = most + min(counts) - use["usageCount"]
            path.write_text(json.dumps(data))

        return write

    def test_the_line_drags_to_the_share_that_fits_the_count_and_the_page_after_apply(
        self, page, demo
    ):
        before = settings(demo.home)
        handle = open_context(page)
        expect(handle).to_have_attribute("aria-valuetext", "1% now · 4 of 20 show only a name")
        main = page.get_by_role("main")
        expect(main).to_contain_text("4 of 20 skills showed only a name")
        page.locator(".ctx-flag").click()
        details = page.get_by_role("complementary", name="Details")
        expect(details).to_contain_text("Suggested1.1%: all 20 skills get their description")
        expect(details).to_contain_text(
            "Kitden could not replay this chat's list exactly, so it counts what all "
            "descriptions need."
        )
        details.get_by_role("button", name="Close").click()
        hold = bar_box(page)
        reads = api_reads(page)
        seen = drag_to(page, handle, hold["x"] + hold["width"] * 0.99, steps=40)
        assert reads == [], "a drag reads nothing from the server"
        suggested = next(s for s in seen if s.startswith("1.1% · all 20 fit · about "))
        mark_x, _ = center(page.locator(".ctx-mark"))
        page.mouse.move(mark_x, center(handle)[1])
        assert readout(page) == suggested
        page.mouse.up()
        dock = page.locator("#dock")
        expect(dock).to_contain_text("Set the skill list limit of Claude Code to 1.1%")
        expect(main).to_contain_text(
            "After Apply, estimate: On a 200K window, every skill would keep its description."
        )
        dock.get_by_role("button", name="Apply").click()
        undo = page.get_by_role("button", name="Undo")
        expect(undo).to_be_visible()
        assert settings(demo.home)["skillListingBudgetFraction"] == 0.011
        expect(main).to_contain_text("The limit was changed after this chat: it is 1.1% now.")
        expect(main).to_contain_text("Estimate: On a 200K window, every skill would keep")
        # The chat's own limit line stays at 8,000; the next chats' line is at 8,800.
        expect(page.locator(".ctx-flag")).to_have_text("Limit: 8,000 characters")
        expect(page.locator(".ctx-next-tag")).to_have_text("Next chats: 8,800 characters")
        expect(handle).to_have_attribute("aria-valuetext", "1.1% now · all 20 fit")
        undo.click()
        wait_until(lambda: settings(demo.home) == before, seconds=10)
        expect(main).not_to_contain_text("The limit was changed after this chat")


def codex_chat_alone(home, write):
    """A newer Codex chat than the sample's own, with no skill there that it does not hold.
    `write(home, at)` writes its skills and its log; a skill of the sample would count as added
    after it."""
    for folder in (".agents/skills", ".codex/skills"):
        shutil.rmtree(home / folder)
    # Later than the sample's own chat, in its time and its file's, so it is the last chat.
    write(home, at="2026-11-20T12:00:00Z")
    for log in (home / ".codex/sessions").rglob("rollout-a.jsonl"):
        os.utime(log)


def open_codex(page):
    """Context on Codex, once its card is pressed and the page stands still: its limit handle."""
    page.evaluate("location.hash = '#context'")
    chips = page.get_by_role("main").get_by_role("group", name="Client")
    codex = chips.get_by_role("button", name="Codex")
    codex.click()
    expect(codex).to_have_attribute("aria-pressed", "true")
    wait_until(
        lambda: not page.evaluate("document.documentElement.classList.contains('place-change')")
    )
    return page.get_by_role("slider", name="Skill list limit")


class TestCodex:
    """Stage 2: the same control on the Codex card. The medium sample's Codex chat fits, so a
    newer Codex chat is written into the sample before the page starts: the cut-short chat of
    tests/unit/test_codex_limit.py (three skills on a tiny window, two cut short). 500 tokens fit
    all three."""

    @pytest.fixture
    def before_start(self):
        from tests.unit.test_codex_limit import cut_chat

        return lambda home: codex_chat_alone(home, cut_chat)

    def test_the_codex_line_drags_to_500_tokens_applies_and_undo(self, page, demo):
        config = demo.home / ".codex/config.toml"
        before = config.read_bytes() if config.exists() else None
        main = page.get_by_role("main")
        handle = open_codex(page)
        expect(handle).to_have_attribute("aria-valuetext", re.compile(r"tokens now · 2 of 3 cut"))
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


class TestLowerPlace:
    """A share of 1.3% in the user settings, where every description fits already: the line also
    goes down to 1.2%, 1.1% and the default. A lower place is set like any other, and while its row
    waits every place up to today's stays where it was."""

    @pytest.fixture
    def before_start(self):
        def write(home):
            path = home / ".claude/settings.json"
            data = json.loads(path.read_text()) if path.exists() else {}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({**data, "skillListingBudgetFraction": 0.013}))

        return write

    def test_a_drag_down_to_1_2_percent_applies_and_undo_puts_1_3_back(self, page, demo):
        handle = open_context(page)
        expect(handle).to_have_attribute("aria-valuetext", "1.3% now · all 20 fit")
        line_x, _ = still_center(page.locator(".ctx-limit"))
        now_x, y = still_center(handle)
        reads = api_reads(page)
        # From today's place to the chat's line (1%): every place on the way, smallest last.
        seen = drag_to(page, handle, line_x, steps=40)
        assert reads == [], "a drag reads nothing from the server"
        assert [p.split(" · ")[0] for p in dict.fromkeys(seen)] == [
            "1.3% now",
            "1.2%",
            "1.1%",
            "1%, the default",
        ]
        # Back to 1.2%, a third of the way from today's place (10,400 characters) to 1% (8,000).
        page.mouse.move(now_x - (now_x - line_x) / 3, y)
        assert readout(page) == "1.2% · all 20 fit"
        dropped = still_center(handle)[0]
        page.mouse.up()
        dock = page.locator("#dock")
        expect(dock).to_contain_text("Set the skill list limit of Claude Code to 1.2%")
        expect(page.locator(".ctx-next-tag")).to_have_text("Next chats: 9,600 characters")
        # While the row waits, the bar keeps its scale: the handle stays where it was let go and
        # the chat's line where it was.
        again = page.get_by_role("slider", name="Skill list limit")
        assert abs(still_center(again)[0] - dropped) < 1
        assert abs(still_center(page.locator(".ctx-limit"))[0] - line_x) < 1
        before = settings(demo.home)
        dock.get_by_role("button", name="Apply").click()
        undo = page.get_by_role("button", name="Undo")
        expect(undo).to_be_visible()
        assert settings(demo.home)["skillListingBudgetFraction"] == 0.012
        undo.click()
        wait_until(lambda: settings(demo.home) == before, seconds=10)
        assert settings(demo.home)["skillListingBudgetFraction"] == 0.013

    def test_keys_down_to_1_1_percent_apply_and_undo(self, page, demo):
        handle = open_context(page)
        handle.focus()
        page.keyboard.press("ArrowLeft")
        expect(handle).to_have_attribute("aria-valuetext", "1.2% · all 20 fit")
        page.keyboard.press("ArrowLeft")
        expect(handle).to_have_attribute("aria-valuetext", "1.1% · all 20 fit")
        page.keyboard.press("Enter")
        dock = page.locator("#dock")
        expect(dock).to_contain_text("Set the skill list limit of Claude Code to 1.1%")
        expect(handle).to_be_focused()
        dock.get_by_role("button", name="Apply").click()
        undo = page.get_by_role("button", name="Undo")
        expect(undo).to_be_visible()
        assert settings(demo.home)["skillListingBudgetFraction"] == 0.011
        undo.click()
        wait_until(
            lambda: settings(demo.home).get("skillListingBudgetFraction") == 0.013, seconds=10
        )
