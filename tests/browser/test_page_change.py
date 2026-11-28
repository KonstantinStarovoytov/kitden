"""A page change on a wide window: the old page fades where it stood, at its own size."""

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import new_tab, wait_until

pytestmark = pytest.mark.browser

OLD_PAGE = "::view-transition-old(page)"
CONTEXT_TITLE = "Do your skills fit?"  # TITLE in js/context.js

# Set the address and resolve once the page has taken it in. The page's own hashchange
# listener was added first, so it has run by then: a change of place has set its class
# (place-change or map-entrance) at once (js/store.js show, js/motion.js transition).
TAKEN_IN = """location.hash === to ? null : new Promise(done => {
  addEventListener("hashchange", () => done(), { once: true });
  location.hash = to;
})"""
SET_HASH = f"to => {TAKEN_IN}"


@pytest.fixture
def wide(browser, demo):
    """A tab 1600 px wide, with motion on. An engine with no view transitions skips the test."""
    context = browser.new_context(viewport={"width": 1600, "height": 900})
    tab, errors = new_tab(context, demo.url)
    if not tab.evaluate("'startViewTransition' in document"):
        context.close()
        pytest.skip("this engine runs no view transitions")
    yield tab
    context.close()
    if errors:
        pytest.fail("The page had errors:\n" + "\n".join(errors))


def change_is_over(page) -> bool:
    return page.evaluate(
        "!['place-change', 'map-entrance'].some(name =>"
        " document.documentElement.classList.contains(name))"
    )


def go(page, to: str) -> None:
    """Set the address to `to` and wait until the page change is over."""
    page.evaluate(SET_HASH, to)
    wait_until(lambda: change_is_over(page))


def new_main_width(page) -> float:
    return page.evaluate("document.getElementById('main').getBoundingClientRect().width")


def old_picture(page, to: str) -> dict:
    """Go to `to`, and read the old page's picture as soon as it fades: the width of #main
    before (`before`) and the picture's width (`old`). With no fading picture in 60 frames,
    `old` is None. Waits until the change is over."""
    seen = page.evaluate(
        """async ([to, name]) => {
          const before = document.getElementById("main").getBoundingClientRect().width;
          await """
        + TAKEN_IN
        + """;
          for (let frame = 0; frame < 60; frame++) {
            await new Promise(requestAnimationFrame);
            const fading = document.getAnimations().find(a => a.effect.pseudoElement === name);
            if (fading) {
              const old = getComputedStyle(document.documentElement, name).width;
              return { before, old: parseFloat(old) };
            }
          }
          return { before, old: null };
        }""",
        [to, OLD_PAGE],
    )
    wait_until(lambda: change_is_over(page))
    return seen


def test_gateway_to_context_keeps_the_old_page_at_its_own_width(wide):
    go(wide, "#gateway")
    seen = old_picture(wide, "#context")
    assert seen["old"] is not None, seen
    assert seen["before"] > new_main_width(wide) + 100, seen  # the pair really differs at 1600 px
    assert abs(seen["old"] - seen["before"]) <= 1, seen


def test_context_to_gateway_keeps_the_old_page_at_its_own_width(wide):
    go(wide, "#context")
    seen = old_picture(wide, "#gateway")
    assert seen["old"] is not None, seen
    assert seen["before"] + 100 < new_main_width(wide), seen
    assert abs(seen["old"] - seen["before"]) <= 1, seen


def test_with_reduced_motion_a_page_change_draws_the_new_page_at_once(browser, demo):
    context = browser.new_context(viewport={"width": 1600, "height": 900}, reduced_motion="reduce")
    try:
        tab, errors = new_tab(context, demo.url)
        go(tab, "#gateway")
        seen = old_picture(tab, "#context")
        assert seen["old"] is None, seen
        expect(tab.locator("#main .page-head h1")).to_have_text(CONTEXT_TITLE)
    finally:
        context.close()
    assert not errors, errors
