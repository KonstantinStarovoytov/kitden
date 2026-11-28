"""The top bar of the page: the search box and the project switch."""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.browser


@pytest.fixture
def narrow_tab(browser, demo):
    """A tab 800 px wide, with reduced motion."""
    context = browser.new_context(viewport={"width": 800, "height": 900}, reduced_motion="reduce")
    tab = context.new_page()
    tab.goto(demo.url)
    tab.locator(".search svg").wait_for()
    yield tab
    context.close()


def gaps(page) -> dict:
    """The room around the search box's icon and "/", and how the project switch lines up."""
    box = page.locator(".search").bounding_box()
    icon = page.locator(".search svg").bounding_box()
    slash = page.locator(".search .kbd").bounding_box()
    where = page.locator(".where").bounding_box()
    assert box and icon and slash and where
    return {
        "left": icon["x"] - box["x"],
        "right": box["x"] + box["width"] - (slash["x"] + slash["width"]),
        "middle": where["y"] + where["height"] / 2 - (box["y"] + box["height"] / 2),
    }


def test_the_magnifier_and_slash_sit_ten_pixels_inside_the_box(page):
    g = gaps(page)
    assert abs(g["left"] - 10) <= 0.5 and abs(g["right"] - 10) <= 0.5
    assert abs(g["middle"]) <= 1  # the top bar still lines up


def test_the_chip_and_slash_keep_their_room_while_a_search_counts(page):
    page.evaluate("location.hash = '#gateway'")
    page.locator("#q").fill("docs")  # a Codex server of the demo sample (demo/sample.py)
    expect(page.locator("#find-chip")).not_to_be_empty()
    assert abs(gaps(page)["right"] - 10) <= 0.5


def test_at_800_px_the_search_box_keeps_its_room_and_the_page_does_not_scroll_sideways(narrow_tab):
    g = gaps(narrow_tab)
    assert abs(g["left"] - 10) <= 0.5 and abs(g["right"] - 10) <= 0.5
    assert narrow_tab.evaluate("document.documentElement.scrollWidth <= innerWidth")
