"""Flow 12: Apply, Undo from the toast, then "Redo…" from the change's Details on Changes: a
fresh preview of the same change, and Apply writes it again."""

import json

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import PLUGIN, SETTINGS, change_states, turn_off, wait_until

pytestmark = pytest.mark.browser


def test_redo_from_changes_makes_the_undone_change_again(page, demo):
    dock = page.locator("#dock")
    turn_off(page, PLUGIN)
    dock.get_by_role("button", name="Apply").click()
    page.get_by_role("button", name="Undo").click()
    wait_until(lambda: change_states(page, demo) == ["undone"], 15)
    assert json.loads(SETTINGS(demo).read_text())["enabledPlugins"][PLUGIN] is True
    page.get_by_role("link", name="Changes", exact=True).click()
    page.get_by_role("listitem").filter(has_text="Turned off superpowers").click()
    details = page.get_by_role("complementary", name="Details")
    expect(details.get_by_text("Undone", exact=True)).to_be_visible()
    # Redo… from the keyboard.
    details.get_by_role("button", name="Redo…").focus()
    page.keyboard.press("Enter")
    apply = dock.get_by_role("button", name="Apply")
    expect(apply).to_be_visible()
    # A preview only: nothing written yet.
    assert json.loads(SETTINGS(demo).read_text())["enabledPlugins"][PLUGIN] is True
    apply.click()
    wait_until(lambda: change_states(page, demo) == ["verified", "undone"], 15)
    assert json.loads(SETTINGS(demo).read_text())["enabledPlugins"][PLUGIN] is False
