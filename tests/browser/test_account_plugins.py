"""Flow 17: a plugin of the Claude account, as a person sees it. The Library has a group for the
plugins the Claude app gives Claude Code, whose Details say where the plugin comes from and turn
it off with Apply and Undo; on Context its skill names the plugin and offers the plugin's switch.
The app's folder (tests/fixtures/claude_app, made-up plugins) and a chat that listed the plugin's
skill are written into the sample before the page starts."""

import json
import os
import re
import shutil
import time

import pytest
from playwright.sync_api import expect

from kitden.system import claude_desktop_dir
from tests.browser.conftest import SETTINGS, change_states, wait_until
from tests.conftest import FIXTURES

pytestmark = pytest.mark.browser

GARDEN = "garden@inline"
GROUP = "From your Claude account"
SKILL = "garden:rivals"


@pytest.fixture
def before_start():
    from tests.unit.test_context_claude_log import assistant, list_entry, write_chat

    def write(home):
        app = FIXTURES / "claude_app/6.28899.6/home/Library/Application Support/Claude"
        shutil.copytree(app, claude_desktop_dir(home), dirs_exist_ok=True)
        for path in claude_desktop_dir(home).rglob("plugins.json"):
            path.write_text(path.read_text().replace("{HOME}", str(home)))
        for manifest in claude_desktop_dir(home).glob("local-agent-mode-sessions/*/*/rpm/*.json"):
            newest = json.loads(manifest.read_text())["plugins"]
            at = time.time() if newest else 1_000_000_000
            os.utime(manifest, (at, at))
        # The sample's newest chat: the Claude app listed the plugin's skill.
        entry = list_entry(
            [SKILL, "alpha"],
            f"- {SKILL}: Lists the rivals of a garden shop.\n- alpha: Does alpha.",
            folder=str(home),
            at="2026-12-30T10:00:00Z",
        )
        write_chat(home, "account", "chat", [entry, assistant("claude-opus-5-5")], time.time())

    return write


def enabled(demo) -> dict:
    return json.loads(SETTINGS(demo).read_text()).get("enabledPlugins", {})


def test_the_library_groups_them_and_turns_one_off_with_undo(page, demo):
    assert GARDEN not in enabled(demo)
    page.get_by_role("link", name="Library", exact=True).click()
    page.get_by_role("button", name=f"Open {GROUP}").click()
    page.get_by_role("button", name=re.compile(r"^garden, ")).click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text(GROUP)
    expect(details).to_contain_text("The Claude app adds it from your Claude account.")
    expect(details).to_contain_text("2 skills · 1 agent · 1 MCP server")
    details.get_by_role("button", name="Turn off for all projects…").click()
    page.locator("#dock").get_by_role("button", name="Apply").click()
    undo = page.get_by_role("button", name="Undo")
    expect(undo).to_be_visible()
    assert enabled(demo)[GARDEN] is False
    undo.click()
    wait_until(lambda: change_states(page, demo) == ["undone"], 15)
    assert GARDEN not in enabled(demo)


def test_on_context_its_skill_names_the_plugin_and_offers_its_switch(page, demo):
    page.get_by_role("link", name="Context", exact=True).click()
    page.locator(f'.ctx-pill[data-skill="{SKILL}"]').click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("Plugin garden from your Claude account")
    expect(details).to_contain_text("The switch is garden's: it turns the whole plugin off")
    expect(details).not_to_contain_text("has no switch here")
    details.get_by_role("button", name="Turn off garden").click()
    page.locator("#dock").get_by_role("button", name="Apply").click()
    undo = page.get_by_role("button", name="Undo")
    expect(undo).to_be_visible()
    assert enabled(demo)[GARDEN] is False
    undo.click()
    wait_until(lambda: change_states(page, demo) == ["undone"], 15)
    assert GARDEN not in enabled(demo)
