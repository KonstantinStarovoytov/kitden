"""Flow 4: add a GitHub source in the Library's add panel; it is listed, searched, and kept in
Kitden's data folder."""

import json

import pytest
from playwright.sync_api import expect

from kitden.gateways import data_dir

pytestmark = pytest.mark.browser

REPO = "anthropics/skills"  # tests/offline.py answers for its tree and its mcp-builder skill


def test_an_added_github_source_is_listed_and_kept(sample_page, sample):
    page = sample_page
    page.get_by_role("link", name="Library", exact=True).click()
    page.get_by_role("button", name="Add plugins, skills or servers from the catalogs").click()
    panel = page.get_by_role("complementary", name="Details")
    panel.get_by_role("button", name="Sources").click()
    panel.get_by_role("textbox", name="GitHub source").fill(REPO)
    panel.get_by_role("button", name="Add source").click()
    # "Source added." shows only until the search of the new source answers.
    source = panel.get_by_role("group", name="Source").get_by_role("button", name=REPO)
    expect(source).to_have_attribute("aria-pressed", "true")
    # The new source is searched at once: its one skill shows.
    expect(panel.get_by_role("status")).to_have_text("1 results")
    expect(panel.get_by_role("button", name=f"mcp-builder {REPO}")).to_be_visible()
    saved = json.loads((data_dir(sample.home) / "discovery/sources.json").read_text())
    # Kitden keeps the built-in GitHub catalog in the same list.
    assert saved == {"repositories": ["anthropics/claude-plugins-official", REPO]}
