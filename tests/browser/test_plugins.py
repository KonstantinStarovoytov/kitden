"""Flow 6: add a marketplace plugin to Claude Code (Apply, then Undo), and remove one of the
sample's plugins. Two plugins, because the demo's runner writes only `enabledPlugins`: a plugin
added here does not show after a rescan, so it cannot be removed again (kitden.demo.runner)."""

import json
import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import SETTINGS, change_states, details_of, wait_until

pytestmark = pytest.mark.browser

ADDED = "db-tools@demo-market"  # in the sample's marketplace, not installed
REMOVED = "pr-review@demo-market"  # installed in Claude Code, and off


def enabled(demo) -> dict:
    return json.loads(SETTINGS(demo).read_text())["enabledPlugins"]


def test_a_plugin_added_from_this_computer_is_on_after_apply_and_gone_after_undo(page, demo):
    assert ADDED not in enabled(demo)
    page.get_by_role("link", name="Library", exact=True).click()
    page.get_by_role("button", name="Add plugins, skills or servers from the catalogs").click()
    panel = page.get_by_role("complementary", name="Details")
    panel.get_by_role("button", name="On this computer").click()
    panel.get_by_role("button", name=re.compile(r"^db-tools Plugin")).click()
    expect(panel.get_by_role("button", name=re.compile(r"^db-tools .*In preview$"))).to_be_visible()
    dock = page.locator("#dock")
    dock.get_by_role("button", name="Apply").click()
    undo = page.get_by_role("button", name="Undo")
    expect(undo).to_be_visible()
    assert enabled(demo)[ADDED] is True
    undo.click()
    wait_until(lambda: change_states(page, demo) == ["undone"], 15)
    assert ADDED not in enabled(demo)


def test_a_sample_plugin_removed_from_claude_code_is_gone_from_its_settings(page, demo):
    assert enabled(demo)[REMOVED] is False
    details = details_of(page, REMOVED)
    details.get_by_role("button", name="More").click()
    details.get_by_role("button", name="Remove from Claude Code…").click()
    page.locator("#dock").get_by_role("button", name="Apply").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    wait_until(lambda: REMOVED not in enabled(demo), 15)
