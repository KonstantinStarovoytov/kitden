"""The page's main flows in a real browser: it opens on the sample, a preview writes nothing,
Apply writes the file and Undo puts it back."""

import json
import re
import time
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.browser

# The sample's Claude Code plugin that is on for every project.
PLUGIN = "superpowers@demo-market"


def SETTINGS(demo):
    return demo.home / ".claude/settings.json"


def origin(demo) -> str:
    parts = urlsplit(demo.url)
    return f"{parts.scheme}://{parts.netloc}"


def wait_until(check, seconds: float = 5) -> None:
    deadline = time.monotonic() + seconds
    while not check():
        if time.monotonic() > deadline:
            raise AssertionError("gave up waiting")
        time.sleep(0.05)


def turn_off(page, plugin: str) -> None:
    """Library, the plugin's marketplace, the plugin's Details, "Turn off for all projects…":
    the plugin's own switch, which adds its change to the preview."""
    name, market = plugin.split("@")
    page.get_by_role("link", name="Library", exact=True).click()
    page.get_by_role("button", name=f"Open {market}").click()
    page.get_by_role("button", name=re.compile(rf"^{re.escape(name)}, ")).click()
    details = page.get_by_role("complementary", name="Details")
    details.get_by_role("button", name="Turn off for all projects…").click()


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
    expect(page.locator("#dock").get_by_role("button", name="Apply")).to_be_hidden()
    wait_until(lambda: SETTINGS(demo).read_bytes() == before)
