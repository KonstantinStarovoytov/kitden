"""Round 3, session C: focus after Details close, in the Library List (02-R12 did not reproduce
on the medium sample; these keep it so)."""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.browser


@pytest.fixture
def demo_size():
    return "medium"


def test_escape_gives_focus_back_to_the_row_not_to_its_add_cell(page, demo):
    # 02-R12: Esc closed Details and focus went to the row's "+" cell; Enter there would add.
    page.evaluate("location.hash = '#library?kind=plugin&view=list'")
    row = page.locator('[role="row"][data-row]').filter(has=page.locator("button.add")).first
    expect(row).to_be_visible()
    key = row.get_attribute("data-focus")
    row.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#drawer")).to_be_visible()
    page.keyboard.press("Escape")
    focused = page.evaluate("document.activeElement.dataset.focus || ''")
    assert focused == key


def test_escape_after_an_arrival_gives_focus_to_the_selected_row(page, demo):
    # Details opened by the address (a link from the Overview): Esc gives focus to that row.
    page.evaluate(
        "location.hash = '#library?kind=plugin&view=list&sel=plugin:superpowers@demo-market'"
    )
    expect(page.locator("#drawer")).to_be_visible()
    picked = page.locator('#main [role="row"][aria-selected="true"]')
    expect(picked).to_have_count(1)
    key = picked.get_attribute("data-focus")
    page.locator("#drawer").focus()
    page.keyboard.press("Escape")
    expect(page.locator("#drawer")).to_be_hidden()
    assert page.evaluate("document.activeElement.dataset.focus || ''") == key


def test_escape_after_a_click_on_a_row_gives_focus_to_that_row(page, demo):
    page.evaluate("location.hash = '#library?kind=plugin&view=list'")
    rows = page.locator('[role="row"][data-row]').filter(has=page.locator("button.add"))
    row = rows.nth(1)
    key = row.get_attribute("data-focus")
    row.locator(".tg-name").click()
    expect(page.locator("#drawer")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#drawer")).to_be_hidden()
    assert page.evaluate("document.activeElement.dataset.focus || ''") == key
