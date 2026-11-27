"""Flow 7: on a home with no Kitden gateway, "Set up…" on the Gateway map adds Kitden's own
entry to Claude Code on Apply."""

import json
import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import wait_until

pytestmark = pytest.mark.browser


@pytest.fixture
def demo_size() -> str:
    """The small sample: no client has the `kitden` entry yet (the medium one has it)."""
    return "small"


def test_set_up_adds_kitdens_entry_to_claude_code(page, demo):
    claude = demo.home / ".claude.json"
    assert "kitden" not in json.loads(claude.read_text())["mcpServers"]
    page.evaluate("location.hash = '#gateway'")
    slot = page.get_by_role("button", name=re.compile(r"^No gateway yet, .*Set up…$"))
    slot.click()
    dock = page.locator("#dock")
    expect(dock.get_by_text("Connect Claude Code to the gateway")).to_be_visible()
    dock.get_by_role("button", name="Apply").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    wait_until(lambda: "kitden" in json.loads(claude.read_text())["mcpServers"])
    entry = json.loads(claude.read_text())["mcpServers"]["kitden"]
    assert entry["command"] == str(demo.home / ".local/bin/kitden")
    assert entry["args"] == ["mcp"]
    # The map now shows the gateway itself, not the empty slot.
    expect(page.get_by_role("button", name=re.compile(r"^Kitden gateway, "))).to_be_visible()
    expect(slot).to_have_count(0)
