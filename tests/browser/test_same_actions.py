"""The same actions wherever a thing is shown: a skill, a plugin and an MCP server offer the same
switch in the Library, on Context and on the Gateway, and where a client cannot, the page says so
there. The medium sample, with Codex's `code-review` skill turned off in config.toml; Codex's
`sqlite` server is off in the sample itself."""

import re
import tomllib

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import change_states, wait_until
from tests.browser.test_limit_line import open_codex, open_context
from tests.browser.test_one_state import library, project_id

pytestmark = pytest.mark.browser


@pytest.fixture
def before_start():
    def write(home):
        config = home / ".codex/config.toml"
        skill = home / ".agents/skills/code-review/SKILL.md"
        rule = f'\n[[skills.config]]\npath = "{skill}"\nenabled = false\n'
        config.write_text(config.read_text() + rule)
        # atlas's local settings turn superpowers off there: the project decides it.
        local = home / "work/atlas/.claude/settings.local.json"
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text('{"enabledPlugins": {"superpowers@demo-market": false}}\n')

    return write


def state_switch(details, where: str):
    """The skill switch of one client and scope: "Claude Code · all projects"."""
    return details.get_by_role("group", name=f"State in {where}")


def apply(page, demo, done: int) -> None:
    page.locator("#dock").get_by_role("button", name="Apply").click()
    wait_until(lambda: len(change_states(page, demo)) == done, 15)


def test_a_skill_turned_off_in_the_library_turns_on_and_takes_name_only_there(page, demo):
    open_context(page)
    details = library(page, "skill:brandkit", kind="skill")
    switch = state_switch(details, "Claude Code · all projects")
    expect(switch.get_by_role("button")).to_have_text(["On", "Name only", "Off"])
    switch.get_by_role("button", name="Off").click()
    apply(page, demo, 1)
    details = library(page, "skill:brandkit", kind="skill")
    switch = state_switch(details, "Claude Code · all projects")
    expect(switch.get_by_role("button", name="Off")).to_have_attribute("aria-pressed", "true")
    expect(details).to_contain_text("Off in Claude Code")
    # On and Name only are there, where it was turned off.
    switch.get_by_role("button", name="On", exact=True).click()
    apply(page, demo, 2)
    assert "brandkit" not in (demo.home / ".claude/settings.json").read_text()


def test_a_codex_skill_that_is_off_turns_on_from_context_and_the_library(page, demo):
    open_codex(page)
    page.locator('.ctx-pill[data-skill="code-review"]').click()
    details = page.get_by_role("complementary", name="Details")
    switch = state_switch(details, "Codex · all projects")
    expect(switch.get_by_role("button")).to_have_text(["On", "Off"])
    expect(details).to_contain_text("Codex has no Name only setting.")
    # The Library has the same switch, in the same state.
    library_details = library(page, "skill:code-review", kind="skill")
    library_switch = state_switch(library_details, "Codex · all projects")
    expect(library_switch.get_by_role("button", name="Off")).to_have_attribute(
        "aria-pressed", "true"
    )
    library_switch.get_by_role("button", name="On", exact=True).click()
    apply(page, demo, 1)
    text = (demo.home / ".codex/config.toml").read_text()
    assert re.search(r"code-review/SKILL.md\"\nenabled = true", text)


def test_with_a_project_picked_a_plugin_has_the_librarys_switches_on_context(page, demo):
    atlas = project_id(page, demo, "atlas")
    details = library(page, "plugin:superpowers@demo-market", atlas)
    expect(details.get_by_role("button", name="Follow all projects…")).to_be_visible()
    in_library = details.get_by_role("button", name=re.compile(r"^Turn (off|on) |^Use the shared"))
    names = in_library.all_inner_texts()
    page.evaluate(f"location.hash = '#context?project={atlas}'")
    group = page.locator('.ctx-group[data-group="plugin:superpowers@demo-market"]')
    expect(group.locator(".ctx-gswitch")).to_have_text(names)
    expect(group).not_to_contain_text("no switch here")
    expect(group.locator(".ctx-gswitch")).to_contain_text(["Follow all projects…"])


def test_a_codex_server_that_is_off_shows_as_off_and_turns_on(page, demo):
    page.evaluate("location.hash = '#gateway?view=list'")
    row = page.locator(".tg-row", has_text="sqlite").first
    expect(row).to_contain_text("Off in Codex")
    # The header search finds it on the Gateway.
    page.get_by_role("searchbox", name="Search skills, plugins, servers and tools").fill("sqlite")
    expect(page.get_by_role("main")).not_to_contain_text("No matches")
    expect(row).to_be_visible()
    page.get_by_role("searchbox", name="Search skills, plugins, servers and tools").fill("")
    row.click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("Off in Codex")
    details.get_by_role("button", name="Turn on in Codex for all projects…").click()
    apply(page, demo, 1)
    assert change_states(page, demo) == ["verified"]
    config = tomllib.loads((demo.home / ".codex/config.toml").read_text())
    assert config["mcp_servers"]["sqlite"]["enabled"] is True


def test_where_a_client_has_no_switch_the_page_says_so_there(page, demo):
    # A Cursor skill on Context.
    page.evaluate("location.hash = '#context'")
    chips = page.get_by_role("main").get_by_role("group", name="Client")
    chips.get_by_role("button", name="Cursor").click()
    page.locator('.ctx-pill[data-skill="ui-polish"]').first.click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("Cursor has no switch to turn off one skill.")
    expect(details).to_contain_text("disable-model-invocation: true")
    # A hook in the Library.
    page.keyboard.press("Escape")
    page.evaluate("location.hash = '#library?kind=plugin&view=list'")
    page.locator(".tg-row", has_text="PreToolUse").first.get_by_role("gridcell").first.click()
    expect(details).to_contain_text("Kitden only shows hooks")
    # A Claude Code server outside the gateway.
    page.keyboard.press("Escape")
    page.evaluate("location.hash = '#gateway?view=list'")
    page.locator(".tg-row", has_text="github").first.click()
    expect(details).to_contain_text("Kitden has no switch to turn it off in Claude Code")
