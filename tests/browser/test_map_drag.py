"""Check 24 of "Check before a release" (docs/development.md): a server dragged onto the gateway
on the Gateway map is moved into it on Apply, and Undo from the toast moves it back."""

import json
import re
import time

import pytest
from playwright.sync_api import expect

from kitden.gateways import data_dir
from kitden.local_gateway.settings import SETTINGS_FILE, load_settings
from tests.browser.conftest import wait_until

pytestmark = pytest.mark.browser

# The medium sample's server that Claude Code sets up on its own, for all projects, with no
# secret (kitden.demo.sample, _claude_code).
SERVER = "docs"


def still_box(locator) -> dict:
    """The element's box once it stands still: the map's blocks slide into place when a stack
    opens, and a press during the slide lands on whatever passes under the pointer."""
    last = None
    for _ in range(50):
        box = locator.bounding_box()
        if box and box == last:
            return box
        last = box
        time.sleep(0.1)
    raise AssertionError("the block did not stand still in 5 seconds")


def drag_onto_the_gateway(page, server: str) -> None:
    """Open the servers outside the gateway, then drag Claude Code's server by its grip onto the
    Kitden gateway's box, with the mouse as a person moves it: down, in steps, up."""
    page.get_by_role("button", name=re.compile(r"^Open Outside the gateway")).click()
    block = page.get_by_role("button", name=re.compile(rf"^{re.escape(server)}, In Claude Code"))
    grip = block.locator(".block-grip")
    gateway = page.get_by_role("button", name=re.compile(r"^Kitden gateway, "))
    expect(grip).to_be_visible()
    expect(gateway).to_be_visible()
    start, end = still_box(grip), still_box(gateway)
    page.mouse.move(start["x"] + start["width"] / 2, start["y"] + start["height"] / 2)
    page.mouse.down()
    page.mouse.move(end["x"] + end["width"] / 2, end["y"] + end["height"] / 2, steps=20)
    page.mouse.up()


def test_a_server_dragged_onto_the_gateway_is_moved_and_undo_from_the_toast_moves_it_back(
    page, demo
):
    files = [demo.home / ".claude.json", data_dir(demo.home) / SETTINGS_FILE]

    def now():
        return [f.read_bytes() if f.exists() else None for f in files]

    before = now()
    page.goto(f"{demo.url}#gateway?view=map")
    drag_onto_the_gateway(page, SERVER)
    dock = page.locator("#dock")
    expect(dock).to_contain_text(SERVER)
    dock.get_by_role("button", name="Apply").click()
    undo = page.get_by_role("button", name="Undo")
    expect(undo).to_be_visible()
    # Moved: in the gateway, and no longer in Claude Code's own list.
    assert SERVER in load_settings(demo.home)["servers"]
    assert SERVER not in json.loads(files[0].read_text())["mcpServers"]
    undo.click()
    wait_until(lambda: now() == before, seconds=10)
