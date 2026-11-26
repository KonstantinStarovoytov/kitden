"""Flow 20: Context groups the skills by where they come from, as a person uses it. A group's header
says what it takes and carries its plugin's switch; pressed, the estimate counts it at once. A
header opens its group with the mouse or the keyboard. A plugin's Details in the Library say what
it takes of the skill list and open its group on Context. The medium sample's last Claude Code chat:
4 of 20 skills showed only a name at 1% of a 200K window; superpowers brings two of them."""

import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import wait_until
from tests.browser.test_limit_line import open_context

pytestmark = pytest.mark.browser

GROUP = '.ctx-group[data-group="plugin:superpowers@demo-market"]'


def test_a_plugin_turned_off_from_its_header_counts_in_the_estimate_at_once(page, demo):
    handle = open_context(page)
    group = page.locator(GROUP)
    expect(group.locator(".ctx-gmeta")).to_contain_text("2 skills")
    switch = group.get_by_role("button", name="Turn off superpowers")
    switch.click()
    expect(page.locator(".ctx-verdict")).to_contain_text(
        "After Apply, estimate: On a 200K window, 1 of 18 skills"
    )
    expect(handle).to_have_attribute("aria-valuetext", "1% now · 1 of 18 show only a name")
    expect(group).to_have_class(re.compile(r"\bgoing\b"))
    expect(group.locator(".ctx-gmeta")).to_contain_text("Off after Apply")
    expect(switch).to_have_attribute("aria-pressed", "true")
    # One row, whichever tab adds it: the Details of its skill show it pressed.
    expect(page.locator("#dock")).to_contain_text("Turn off superpowers")
    # Three groups in the sample: they start open. The preview bar may stand over the pill at this
    # size: the keyboard opens it.
    group.locator('.ctx-pill[data-skill="superpowers:brainstorming"]').focus()
    page.keyboard.press("Enter")
    details = page.get_by_role("complementary", name="Details")
    expect(details.get_by_role("button", name="Turn off superpowers")).to_have_attribute(
        "aria-pressed", "true"
    )
    switch.click()
    expect(page.locator("#dock").get_by_role("button", name="Apply")).to_be_hidden()
    expect(handle).to_have_attribute("aria-valuetext", "1% now · 4 of 20 show only a name")


def test_a_header_opens_its_group_with_the_mouse_and_the_keyboard(page, demo):
    open_context(page)
    group = page.locator(GROUP)
    toggle = group.locator(".ctx-gtoggle")
    pill = group.locator('.ctx-pill[data-skill="superpowers:planning"]')
    # Three groups in the sample: they start open.
    expect(page.locator(".ctx-group")).to_have_count(3)
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(pill).to_be_visible()
    group.locator(".ctx-gmeta").click()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(pill).not_to_be_visible()
    toggle.focus()
    page.keyboard.press("Enter")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(pill).to_be_visible()
    page.keyboard.press("Space")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    # The switch is reachable without opening, by Tab from the name. WebKit on a Mac, as Safari,
    # moves to buttons with Option+Tab.
    tab = "Alt+Tab" if page.context.browser.browser_type.name == "webkit" else "Tab"
    page.keyboard.press(tab)
    expect(page.locator(":focus")).to_have_attribute("aria-label", re.compile(r"^superpowers: "))
    page.keyboard.press(tab)
    expect(page.locator(":focus")).to_have_attribute("aria-label", "Turn off superpowers")


def test_the_library_says_what_a_plugin_takes_and_opens_its_group(page, demo):
    open_context(page)
    page.evaluate(
        "location.hash = '#library?kind=plugin&view=list&sel=plugin:superpowers@demo-market'"
    )
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("superpowers")
    expect(details).to_contain_text(re.compile(r"In Claude Code's skill list: 2 skills · "))
    details.get_by_role("button", name=re.compile(r"^Show in Context")).first.click()
    wait_until(lambda: page.evaluate("location.hash").startswith("#context"))
    group = page.locator(GROUP)
    expect(group.locator(".ctx-gtoggle")).to_have_attribute("aria-expanded", "true")
    expect(group.locator(".ctx-gtoggle")).to_be_focused()
    # The name opens the same Details in the Library.
    group.get_by_role("button", name="superpowers: Details in the Library").click()
    wait_until(lambda: page.evaluate("location.hash").startswith("#library"))
    expect(page.get_by_role("complementary", name="Details")).to_contain_text("superpowers")


def test_a_plugins_skill_in_the_library_says_what_it_takes_and_opens_its_group(page, demo):
    open_context(page)
    page.evaluate("location.hash = '#library?kind=plugin&view=list&sel=skill:brainstorming'")
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("brainstorming")
    expect(details).to_contain_text(
        re.compile(r"Sends its description \([\d,]+ characters\) in Claude Code's skill list\.")
    )
    details.get_by_role("button", name=re.compile(r"^Show in Context")).first.click()
    wait_until(lambda: page.evaluate("location.hash").startswith("#context"))
    expect(page.locator(GROUP).locator(".ctx-gtoggle")).to_be_focused()
