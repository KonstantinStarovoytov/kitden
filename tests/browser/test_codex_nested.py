"""Flow 16: a Codex skill inside another skill's folder, as a person sees it: a pill with a switch
on Context, a row of its own in the Library, and named in the review of the outer skill's removal.
The Codex chat is written into the sample before the page starts."""

import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import change_states, wait_until
from tests.browser.test_context_now import pick, switch
from tests.browser.test_limit_line import codex_chat_alone, open_codex

pytestmark = pytest.mark.browser

OUTER, INNER = "qdrant", "hybrid-search"
TEXT = "Use it when a search must mix words and vectors."


def outer_folder(home):
    return home / ".agents/skills" / OUTER


def inner_file(home):
    return outer_folder(home) / "strategies" / INNER / "SKILL.md"


@pytest.fixture
def before_start():
    from tests.unit.test_context_now import rooted_chat
    from tests.unit.test_context_view import codex_chat, skill

    def write(home, at):
        rooted_chat(home)  # the window and its model
        skill(outer_folder(home).parent, OUTER, TEXT)
        skill(inner_file(home).parent.parent, INNER, TEXT)
        files = {OUTER: outer_folder(home) / "SKILL.md", INNER: inner_file(home)}
        lines = [f"- {n}: {TEXT} (file: {path.resolve()})" for n, path in files.items()]
        codex_chat(home, lines, at=at)

    return lambda home: codex_chat_alone(home, write)


def test_a_codex_skill_inside_another_one_has_a_switch_on_context(page, demo):
    config = demo.home / ".codex/config.toml"
    before = config.read_bytes() if config.exists() else None
    open_codex(page)
    switch(pick(page, INNER), "Off")
    page.locator("#dock").get_by_role("button", name="Apply").click()
    undo = page.get_by_role("button", name="Undo")
    expect(undo).to_be_visible()
    assert str(inner_file(demo.home).resolve()) in config.read_text()
    expect(page.locator(f'.ctx-pill.off[data-skill="{INNER}"]')).to_be_visible()
    # The outer skill stays on the list.
    expect(page.locator(f'.ctx-group .ctx-pill:not(.off)[data-skill="{OUTER}"]')).to_be_visible()
    undo.click()
    wait_until(lambda: (config.read_bytes() if config.exists() else None) == before, seconds=10)


def test_removing_the_outer_skill_names_the_inner_one_and_undo_brings_both_back(page, demo):
    page.evaluate("location.hash = '#library'")
    page.get_by_role("main").get_by_role("group", name="Show as").get_by_role(
        "button", name="List"
    ).click()
    outer = page.get_by_role("row", name=re.compile(rf"^{OUTER} Skill "))
    inner = page.get_by_role("row", name=re.compile(rf"^{INNER} Skill "))
    expect(inner).to_have_count(1)
    outer.get_by_role("gridcell").first.click()
    details = page.get_by_role("complementary", name="Details")
    details.get_by_role("button", name=re.compile(r"^Remove from Codex")).click()
    dock = page.locator("#dock")
    expect(dock).to_contain_text(f"Remove {OUTER} from")
    dock.get_by_role("button", name="Show changes").click()
    expect(details).to_contain_text(f"This also removes {INNER}, which is inside this folder.")
    dock.get_by_role("button", name="Apply").click()
    wait_until(lambda: not outer_folder(demo.home).exists(), 15)
    expect(outer).to_have_count(0)
    expect(inner).to_have_count(0)
    page.get_by_role("button", name="Undo").click()
    wait_until(lambda: change_states(page, demo) == ["undone"], 15)
    assert inner_file(demo.home).is_file()
    expect(inner).to_have_count(1)
