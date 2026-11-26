"""Flow 8, its second half: "Move all N…" in the Kitden gateway's Details moves every server
outside the gateway that can move, in one change. (The drag of one server is
test_map_drag.py.)"""

import json
import re
import tomllib

import pytest
from playwright.sync_api import expect

from kitden.local_gateway.settings import load_settings
from tests.browser.conftest import wait_until

pytestmark = pytest.mark.browser

# What the medium sample's Move all takes. `docs` stays out: Claude Code and Codex set it up
# differently, so a person keeps one first. So does Cursor's `files`: the gateway's has a token,
# Cursor's none.
MOVED = ["analytics", "github", "browser-tools", "n8n"]


def test_move_all_moves_every_server_that_can_move(page, demo):
    page.evaluate("location.hash = '#gateway?view=list'")
    gateway = page.get_by_role("row", name=re.compile(r"^Kitden gateway "))
    gateway.get_by_role("gridcell").first.click()
    details = page.get_by_role("complementary", name="Details")
    details.get_by_role("button", name="More").click()
    details.get_by_role("button", name=f"Move all {len(MOVED)}…").click()
    dock = page.locator("#dock")
    expect(dock).to_contain_text(
        "Move analytics, github, browser-tools and n8n into the Kitden gateway"
    )
    assert sorted(load_settings(demo.home)["servers"]) == ["files", "tracker"]
    dock.get_by_role("button", name="Apply").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    wait_until(lambda: set(MOVED) <= set(load_settings(demo.home)["servers"]), 15)
    claude = json.loads((demo.home / ".claude.json").read_text())["mcpServers"]
    assert "github" not in claude and "docs" in claude
    cursor = json.loads((demo.home / ".cursor/mcp.json").read_text())["mcpServers"]
    assert not {"n8n", "browser-tools"} & set(cursor) and "files" in cursor
    codex = tomllib.loads((demo.home / ".codex/config.toml").read_text())["mcp_servers"]
    assert "analytics" not in codex and "docs" in codex
    # The list shows them in the gateway now; docs is left outside, once per client.
    expect(page.get_by_role("row", name=re.compile(r"^n8n On "))).to_be_visible()
    expect(page.get_by_role("row", name=re.compile(r"^docs (Claude Code|Codex) "))).to_have_count(2)
