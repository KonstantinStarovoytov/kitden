"""Flow 3: search a catalog, "Show 5 more", and open a found item's details. The catalog
answers from tests/offline.py: 65 servers for "weather", one page is 60."""

import socket

import pytest
from playwright.sync_api import expect

from tests.conftest import PUBLIC_ADDRESS

pytestmark = pytest.mark.browser


def test_the_sample_has_the_network_guard_on(sample):
    """Every outside name resolves to an address nothing reaches, and a test that connects to
    it fails at its end (tests/conftest.py, guarded_lookups)."""
    assert socket.getaddrinfo("pypi.org", 443)[0][4][0] == PUBLIC_ADDRESS


def test_search_shows_more_and_opens_an_items_details(sample_page):
    page = sample_page
    page.get_by_role("link", name="Gateway", exact=True).click()
    page.get_by_role("button", name="+ Add servers").click()
    panel = page.get_by_role("complementary", name="Details")
    expect(panel.get_by_role("heading", name="Add an MCP server")).to_be_visible()
    panel.get_by_role("searchbox", name="Search catalogs").fill("weather")
    panel.get_by_role("button", name="Search").click()
    expect(panel.get_by_role("status")).to_have_text("Showing 60 of 65 results")
    found = panel.get_by_role("button", name="weather-", exact=False)
    expect(found).to_have_count(60)
    panel.get_by_role("button", name="Show 5 more").click()
    expect(found).to_have_count(65)
    expect(panel.get_by_role("button", name="Show 5 more")).to_have_count(0)
    panel.get_by_role("button", name="weather-65 example").click()
    details = page.get_by_role("region", name="Item details")
    expect(details.get_by_role("heading", name="weather-65")).to_be_visible()
    expect(details.get_by_text("Weather forecasts, sample server 65.")).to_be_visible()
    expect(details.get_by_role("button", name="Preview")).to_be_visible()
