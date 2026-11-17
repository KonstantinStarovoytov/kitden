"""Flow 9: remove a server's direct entry from Claude Code: the preview, Apply from the
keyboard, and the entry is gone from the file."""

import json

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import open_outside, wait_until

pytestmark = pytest.mark.browser

# The medium sample's remote server that Claude Code sets up for all projects, with no secret.
SERVER = "docs"


def test_a_removed_direct_entry_is_gone_from_claude_codes_file(page, demo):
    claude = demo.home / ".claude.json"
    assert SERVER in json.loads(claude.read_text())["mcpServers"]
    details = open_outside(page, SERVER, "Claude Code")
    details.get_by_role("button", name="More").click()
    details.get_by_role("button", name="Remove from Claude Code…").click()
    dock = page.locator("#dock")
    apply = dock.get_by_role("button", name="Apply")
    expect(apply).to_be_visible()
    # Only the preview so far: the file still has it.
    assert SERVER in json.loads(claude.read_text())["mcpServers"]
    apply.focus()
    page.keyboard.press("Enter")
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    wait_until(lambda: SERVER not in json.loads(claude.read_text())["mcpServers"])
    # The other servers stay.
    assert "github" in json.loads(claude.read_text())["mcpServers"]
