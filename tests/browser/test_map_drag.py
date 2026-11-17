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
    """The element's box once it stands still (three equal reads, 0.1 s apart): the map's blocks
    slide into place when a stack opens, and a press during the slide lands on whatever passes
    under the pointer."""
    reads: list = []
    for _ in range(50):
        reads = [*reads[-2:], locator.bounding_box()]
        if len(reads) == 3 and reads[0] and reads[0] == reads[1] == reads[2]:
            return reads[0]
        time.sleep(0.1)
    raise AssertionError("the block did not stand still in 5 seconds")


def drag_onto_the_gateway(page, server: str) -> None:
    """Open the servers outside the gateway, then drag Claude Code's server onto the Kitden
    gateway's box, with the mouse as a person moves it: down, in steps, up. The press is on the
    block itself, by its name: a press anywhere on a block that can move starts the drag (the
    map's pointerdown, pressGrip in gateway-drag.js); its grip is only a picture."""
    page.get_by_role("button", name=re.compile(r"^Open Outside the gateway")).click()
    block = page.get_by_role("button", name=re.compile(rf"^{re.escape(server)}, In Claude Code"))
    gateway = page.get_by_role("button", name=re.compile(r"^Kitden gateway, "))
    expect(block).to_be_visible()
    expect(gateway).to_be_visible()
    start, end = still_box(block), still_box(gateway)
    # A third of the way in: on the name, clear of the count at the block's right end.
    page.mouse.move(start["x"] + start["width"] / 3, start["y"] + start["height"] / 2)
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
    # The hash, not goto: goto would reload the page while its first reads run, and WebKit
    # reports those cancelled reads as page errors.
    page.evaluate("location.hash = '#gateway?view=map'")
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
