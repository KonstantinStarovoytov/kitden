"""Flow 19: a plugin turned off from Context, as a person does it. Its switch waiting in the preview
counts in the verdict and on the limit line, as a skill's own switch does; once applied, its skills
stand under Turned off at once, also where Kitden cannot replay the last chat's list and the page
shows that chat's list. The medium sample's last Claude Code chat: 4 of 20 skills showed only a
name at 1% of a 200K window; superpowers brings two of them, brainstorming (sent) and planning."""

import json

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import SETTINGS, wait_until
from tests.browser.test_limit_line import open_context

pytestmark = pytest.mark.browser

PLUGIN = "superpowers@demo-market"
SKILLS = ("superpowers:brainstorming", "superpowers:planning")


def turn_off_from_context(page) -> None:
    """The plugin's switch in the Details of one of its skills."""
    page.locator(f'.ctx-pill[data-skill="{SKILLS[0]}"]').click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("Turns off all of superpowers: 2 skills.")
    details.get_by_role("button", name="Turn off superpowers").click()


def off_now(page) -> list[str]:
    return page.locator(".ctx-off .ctx-pill").evaluate_all("(n) => n.map((p) => p.dataset.skill)")


def test_a_plugins_switch_waiting_in_the_preview_counts_in_the_verdict_and_on_the_line(page, demo):
    handle = open_context(page)
    verdict = page.locator(".ctx-verdict")
    expect(handle).to_have_attribute("aria-valuetext", "1% now · 4 of 20 show only a name")
    turn_off_from_context(page)
    expect(verdict).to_contain_text("After Apply, estimate: On a 200K window, 1 of 18 skills")
    expect(handle).to_have_attribute("aria-valuetext", "1% now · 1 of 18 show only a name")
    # Taken out of the preview, everything counts as before.
    page.get_by_role("complementary", name="Details").get_by_role(
        "button", name="Turn off superpowers"
    ).click()
    expect(page.locator("#dock").get_by_role("button", name="Apply")).to_be_hidden()
    expect(handle).to_have_attribute("aria-valuetext", "1% now · 4 of 20 show only a name")


class TestCounted:
    """A chat the rule cannot rebuild (the sample's, with each skill's use turned round): the page
    shows the last chat's list, and counts what the setup now needs."""

    @pytest.fixture
    def before_start(self):
        def write(home):
            path = home / ".claude.json"
            data = json.loads(path.read_text())
            usage = data["skillUsage"]
            counts = [use["usageCount"] for use in usage.values()]
            for use in usage.values():
                use["usageCount"] = max(counts) + min(counts) - use["usageCount"]
            path.write_text(json.dumps(data))

        return write

    def test_after_apply_the_plugins_skills_are_off_at_once_and_counted(self, page, demo):
        before = SETTINGS(demo).read_bytes()
        handle = open_context(page)
        main = page.get_by_role("main")
        assert off_now(page) == []
        turn_off_from_context(page)
        about = "about 1 of 18 skills would show only a name. Kitden counted them"
        verdict = page.locator(".ctx-verdict")
        expect(verdict).to_contain_text(f"After Apply, estimate: On a 200K window, {about}")
        expect(handle).to_have_attribute(
            "aria-valuetext", "1% now · about 1 of 18 show only a name"
        )
        page.locator("#dock").get_by_role("button", name="Apply").click()
        undo = page.get_by_role("button", name="Undo")
        expect(undo).to_be_visible()
        assert json.loads(SETTINGS(demo).read_text())["enabledPlugins"][PLUGIN] is False
        # The last chat's fact stays; what is off now is drawn off, with no new chat.
        expect(main).to_contain_text("4 of 20 skills showed only a name")
        wait_until(lambda: off_now(page) == list(SKILLS))
        expect(main).to_contain_text(f"Estimate: On a 200K window, {about}")
        undo.click()
        wait_until(lambda: SETTINGS(demo).read_bytes() == before, seconds=10)
        wait_until(lambda: off_now(page) == [])
