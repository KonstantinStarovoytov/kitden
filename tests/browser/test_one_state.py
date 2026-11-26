"""One state on every tab: the Library, the Gateway and Context say the same of one thing, and a
change waiting in the tray is marked wherever the thing shows. The medium sample, with Codex's
`browser` plugin off in atlas (where both last chats were), a share of its own in website, and in
atlas's local settings `release-notes` set to Name only."""

import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import change_states, origin, turn_off, wait_until
from tests.browser.test_limit_line import open_codex, open_context

pytestmark = pytest.mark.browser

PLUGIN = "plugin:superpowers@demo-market"


@pytest.fixture
def before_start():
    def write(home):
        atlas = home / "work/atlas/.codex/config.toml"
        atlas.parent.mkdir(parents=True, exist_ok=True)
        atlas.write_text('[plugins."browser@openai-bundled"]\nenabled = false\n')
        website = home / "work/website/.claude/settings.json"
        website.parent.mkdir(parents=True, exist_ok=True)
        website.write_text('{"skillListingBudgetFraction": 0.015}\n')
        local = home / "work/atlas/.claude/settings.local.json"
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text('{"skillOverrides": {"release-notes": "name-only"}}\n')

    return write


def project_id(page, demo, name: str) -> str:
    projects = page.request.get(f"{origin(demo)}/api/projects").json()
    return next(p["id"] for p in projects if p["path"].endswith(f"/{name}"))


def library(page, sel: str, project: str = "", kind: str = "plugin"):
    """The Library list with `sel`'s Details open (in `project` when given: the project first,
    then its row)."""
    page.keyboard.press("Escape")
    if not project:
        page.evaluate(f"location.hash = '#library?kind={kind}&view=list&sel={sel}'")
        return page.get_by_role("complementary", name="Details")
    page.evaluate(f"location.hash = '#library?kind={kind}&view=list&project={project}'")
    name = sel.partition(":")[2].partition("@")[0]
    row = page.get_by_role("row", name=re.compile(rf"^{re.escape(name)} "))
    row.get_by_role("gridcell").first.click()
    return page.get_by_role("complementary", name="Details")


def chip(page, name: str):
    chips = page.get_by_role("main").get_by_role("group", name="Client")
    button = chips.get_by_role("button", name=name)
    button.click()
    expect(button).to_have_attribute("aria-pressed", "true")


def test_library_details_say_nothing_of_a_list_context_cannot_read(page, demo):
    open_context(page)
    # Cursor: Kitden cannot see what it sends.
    details = library(page, "skill:ui-polish", kind="skill")
    expect(details).to_contain_text("ui-polish")
    expect(details).not_to_contain_text("skill list")
    # website has no chat: Context says so, and the Library makes no claim on that list either.
    website = project_id(page, demo, "website")
    page.evaluate(f"location.hash = '#context?project={website}'")
    expect(page.get_by_role("main")).to_contain_text("No Claude Code chat")
    details = library(page, "skill:brandkit", website, kind="skill")
    expect(details).to_contain_text("brandkit")
    expect(details).not_to_contain_text("skill list")


def test_a_plugins_line_in_the_library_is_its_group_line_on_context(page, demo):
    open_context(page)
    parts = page.locator(f'.ctx-group[data-group="{PLUGIN}"] .ctx-gmeta > span')
    meta = " · ".join(parts.all_inner_texts())
    assert meta.startswith("2 skills")
    details = library(page, PLUGIN)
    expect(details).to_contain_text(f"In Claude Code's skill list: {meta}.")
    # One skill: as its pill and Details on Context say it, by the same size.
    details = library(page, "skill:brainstorming")
    expect(details).to_contain_text(re.compile(r"Sends its description \(186 characters\)"))


def test_the_library_line_follows_an_apply(page, demo):
    open_context(page)
    turn_off(page, "superpowers@demo-market")
    page.locator("#dock").get_by_role("button", name="Apply").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    details = library(page, PLUGIN)
    expect(details).to_contain_text("In Claude Code's skill list: Off")
    page.get_by_role("button", name="Undo").click()
    wait_until(lambda: change_states(page, demo) == ["undone"], 15)
    details = library(page, PLUGIN)
    expect(details).to_contain_text("In Claude Code's skill list: 2 skills")
    expect(details).not_to_contain_text("Off")


def test_all_projects_on_context_names_the_last_chats_folder(page, demo):
    open_codex(page)
    main = page.get_by_role("main")
    expect(main.locator(".ctx-win em").first).to_have_text(re.compile(r"Last chat · .* · in atlas"))
    group = page.locator('.ctx-group[data-group="plugin:browser@openai-bundled"]')
    expect(group).to_contain_text("atlas's own settings set this plugin")
    # The Library says the same for all projects: on, and off in atlas by its own settings.
    details = library(page, "plugin:browser@openai-bundled")
    expect(details).to_contain_text("Codex loads it in every project.")
    expect(details).to_contain_text("It is off in atlas: atlas's own settings set this plugin")


def test_a_project_view_offers_codexs_own_switch_for_a_plugin_its_settings_set(page, demo):
    atlas = project_id(page, demo, "atlas")
    details = library(page, "plugin:browser@openai-bundled", atlas)
    expect(details.get_by_role("button", name="Turn on in this project…")).to_be_visible()
    expect(details).to_contain_text("Codex's setting for this comes from atlas's shared settings.")
    expect(details).not_to_contain_text("None yet")


def test_a_skill_set_to_name_only_in_a_projects_local_file_says_so_in_the_library(page, demo):
    atlas = project_id(page, demo, "atlas")
    details = library(page, "skill:release-notes", atlas, kind="skill")
    expect(details).to_contain_text("Name only")


def list_row(page, name: str):
    """A row of the List (Library or Gateway) by its name."""
    words = page.locator(".words.name", has_text=re.compile(rf"^{re.escape(name)}$"))
    return page.locator(".tg-row").filter(has=words).first


def marked(locator) -> None:
    """The preview's mark: the dashed lamp and the words "In preview"."""
    expect(locator).to_contain_text(re.compile("in preview", re.I))


def test_a_waiting_change_is_marked_on_every_row_and_card(page, demo):
    turn_off(page, "superpowers@demo-market")
    expect(page.locator("#dock")).to_contain_text("superpowers")
    # The Library's list row and its map card.
    page.evaluate("location.hash = '#library?kind=plugin&view=list'")
    marked(list_row(page, "superpowers"))
    page.evaluate("location.hash = '#library?kind=plugin&view=map'")
    marked(page.locator("div.map .block.plugin").filter(has_text="superpowers").first)
    # A gateway tool's rule: the server's list row and its map card.
    page.locator("#dock").get_by_role("button", name="Cancel").click()
    page.evaluate("location.hash = '#gateway?view=list'")
    list_row(page, "files").click()
    details = page.get_by_role("complementary", name="Details")
    details.get_by_role("switch", name=re.compile("delete_file")).click()
    expect(page.locator("#dock")).to_contain_text("delete_file")
    page.keyboard.press("Escape")
    marked(list_row(page, "files"))
    page.evaluate("location.hash = '#gateway?view=map'")
    marked(page.locator("div.map .block.held").filter(has_text="files").first)


def test_cursor_says_why_its_plugins_skills_are_not_listed(page, demo):
    open_context(page)
    chip(page, "Cursor")
    expect(page.get_by_role("main")).to_contain_text(
        re.compile(r"The skills inside its \d+ plugins? are not listed")
    )


def test_a_projects_own_share_is_in_the_lede(page, demo):
    website = project_id(page, demo, "website")
    page.evaluate(f"location.hash = '#context?project={website}'")
    expect(page.get_by_role("main")).to_contain_text("use 1.5% of the context window")


class TestPluginOn:
    """The sample as it is: Codex's `browser` is on, and the last Codex chat listed none of its
    skills."""

    @pytest.fixture
    def before_start(self):
        return lambda home: None

    def test_a_codex_plugin_that_is_on_stays_on_context(self, page, demo):
        open_codex(page)
        group = page.locator('.ctx-group[data-group="plugin:browser@openai-bundled"]')
        expect(group).to_be_visible()
        expect(group).to_contain_text("after your next Codex chat")
        expect(group.get_by_role("button", name="Turn off browser")).to_be_visible()
        wait_until(lambda: True)
