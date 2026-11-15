"""The page's main flows in a real browser: it opens on the sample, a preview writes nothing,
Apply writes the file and Undo puts it back."""

import json

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import PLUGIN, SETTINGS, origin, turn_off, wait_until

pytestmark = pytest.mark.browser


def test_the_page_opens_on_the_sample(page, demo):
    expect(page).to_have_title("Overview · Kitden")
    for client in ("Claude Code", "Codex", "Cursor"):
        expect(page.get_by_text(client, exact=True).first).to_be_visible()
    assert page.request.get(f"{origin(demo)}/api/about").json()["demo"] is True


def test_a_preview_shows_the_change_and_writes_nothing(page, demo):
    before = SETTINGS(demo).read_bytes()
    turn_off(page, PLUGIN)
    expect(page.locator("#dock").get_by_role("button", name="Apply")).to_be_visible()
    assert SETTINGS(demo).read_bytes() == before


def test_apply_writes_the_file_and_says_so(page, demo):
    turn_off(page, PLUGIN)
    page.locator("#dock").get_by_role("button", name="Apply").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    assert json.loads(SETTINGS(demo).read_text())["enabledPlugins"][PLUGIN] is False
    (change,) = page.request.get(f"{origin(demo)}/api/changes").json()
    assert change["state"] == "verified"


def test_undo_puts_the_file_back(page, demo):
    before = SETTINGS(demo).read_bytes()
    turn_off(page, PLUGIN)
    page.locator("#dock").get_by_role("button", name="Apply").click()
    page.get_by_role("button", name="Undo").click()
    # Kitden records the change as undone, and the file is as it was.
    changes = f"{origin(demo)}/api/changes"
    wait_until(lambda: [c["state"] for c in page.request.get(changes).json()] == ["undone"], 15)
    wait_until(lambda: SETTINGS(demo).read_bytes() == before, 15)
