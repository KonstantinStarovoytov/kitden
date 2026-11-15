"""Check 23 of "Check before a release" (docs/development.md): settings that change under a
preview stop its Apply; Preview again shows the plugin as it is now, and Cancel writes nothing."""

import json
import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import PLUGIN, SETTINGS, details_of

pytestmark = pytest.mark.browser

STALE = "Settings changed since this preview."


def remove(page, plugin: str) -> None:
    """The plugin's Details, More, its Remove: into the tray, not applied."""
    details = details_of(page, plugin)
    details.get_by_role("button", name="More").click()
    details.get_by_role("button", name=re.compile(r"^Remove from ")).click()


def as_the_client_would(settings, plugin: str, on: bool) -> None:
    """Turn the plugin on or off in the settings file, as Claude Code writes it."""
    data = json.loads(settings.read_text())
    data["enabledPlugins"][plugin] = on
    settings.write_text(json.dumps(data, indent=2) + "\n")


def test_settings_changed_under_a_preview_ask_for_a_new_one_and_cancel_writes_nothing(page, demo):
    dock = page.locator("#dock")
    remove(page, PLUGIN)
    expect(dock.get_by_role("button", name="Apply")).to_be_visible()
    as_the_client_would(SETTINGS(demo), PLUGIN, False)  # Claude Code turns the plugin off
    stale = dock.get_by_text(STALE)
    # The page rescans on its own; when it has not said so in 5 seconds, press Rescan, as the
    # manual step says.
    try:
        expect(stale).to_be_visible(timeout=5_000)
    except AssertionError:
        page.locator("#rescan").click()
        expect(stale).to_be_visible(timeout=10_000)
    expect(dock.get_by_role("button", name="Apply")).to_be_hidden()
    # What a Remove writes: the settings file and the list of installed plugins.
    files = [SETTINGS(demo), demo.home / ".claude/plugins/installed_plugins.json"]
    after = [f.read_bytes() for f in files]
    dock.get_by_role("button", name="Preview again").click()
    # A fresh preview: Apply is back and the bar no longer warns.
    expect(dock.get_by_role("button", name="Apply")).to_be_visible()
    expect(stale).to_be_hidden()
    # Of the plugin as it is now: the review's file change takes out the entry that is off now
    # (the first preview's took out `true`).
    dock.get_by_role("button", name="Show changes").click()
    review = page.get_by_role("complementary", name="Details")
    review.get_by_text("Show file change").click()
    expect(review.get_by_text(f'"{PLUGIN}": false')).to_be_visible()
    expect(review.get_by_text(f'"{PLUGIN}": true')).to_have_count(0)
    dock.get_by_role("button", name="Cancel").click()
    # The tray is empty: the bar has no buttons left.
    expect(dock.get_by_role("button")).to_have_count(0)
    # The page says so to a screen reader, and the review closed with it.
    said = page.get_by_role("status").filter(has_text="taken out of the preview")
    expect(said).to_have_count(1)
    expect(review).to_be_hidden()
    assert [f.read_bytes() for f in files] == after
