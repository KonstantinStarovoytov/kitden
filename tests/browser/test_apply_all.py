"""Flow 11: two changes wait in the tray; "Apply all" writes both."""

import json

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import PLUGIN, SETTINGS, open_outside, turn_off, wait_until

pytestmark = pytest.mark.browser


def test_apply_all_writes_both_changes_in_the_tray(page, demo):
    claude = demo.home / ".claude.json"
    dock = page.locator("#dock")
    turn_off(page, PLUGIN)
    expect(dock.get_by_role("button", name="Apply")).to_be_visible()
    details = open_outside(page, "docs", "Claude Code")
    details.get_by_role("button", name="More").click()
    details.get_by_role("button", name="Remove from Claude Code…").click()
    apply_all = dock.get_by_role("button", name="Apply all")
    expect(apply_all).to_be_visible()
    # Two previews, nothing written yet.
    assert json.loads(SETTINGS(demo).read_text())["enabledPlugins"][PLUGIN] is True
    assert "docs" in json.loads(claude.read_text())["mcpServers"]
    apply_all.click()
    # The page's own words after a verified Apply of both.
    expect(dock).to_contain_text("Applied 2 changes")
    expect(apply_all).to_be_hidden()
    wait_until(
        lambda: (
            "docs" not in json.loads(claude.read_text())["mcpServers"]
            and json.loads(SETTINGS(demo).read_text())["enabledPlugins"][PLUGIN] is False
        ),
        15,
    )
