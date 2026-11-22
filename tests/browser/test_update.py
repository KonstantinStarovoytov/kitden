"""Flow 13: update Kitden from the page. The check hears of 99.0.0, the button asks first,
the ring shows the steps, and the page reloads on the new version and says so.

What this cannot test: the real hand-over to a new process (KITDEN_TAKE_OVER, the page lock,
uv or Homebrew). The sample's fake start_page starts the new page in this process, on the same
port, token and session (tests/browser/conftest.py). The unit tests
(tests/unit/test_api_update.py) and the release check keep the rest. Each step's words are not
checked: the fake steps pass faster than the page asks."""

import json

import pytest
from playwright.sync_api import expect

from kitden import __version__
from kitden.gateways import data_dir
from tests.browser.conftest import LATEST, origin

pytestmark = pytest.mark.browser


def test_update_to_a_new_version_reloads_the_page_on_it(sample_page, sample):
    page = sample_page
    press = page.get_by_role("button", name=f"Update Kitden to {LATEST}")
    # The page asks the server again every 3 seconds until the check has answered.
    expect(press).to_be_visible()
    expect(page.get_by_text(f"Kitden {__version__}", exact=True)).to_be_visible()
    press.click()
    ask = page.get_by_role("dialog", name=f"Update to Kitden {LATEST}?")
    expect(ask).to_be_visible()
    with page.expect_event("load", timeout=30_000):
        ask.get_by_role("button", name="Update").click()
        # The ring: the button turns into the busy one while the steps run.
        expect(page.get_by_role("button", name="Updating Kitden")).to_be_visible()
    expect(page.locator("#said")).to_have_text(f"Updated to {LATEST}")
    expect(page.get_by_text(f"Kitden {LATEST}", exact=True)).to_be_visible()
    expect(press).to_have_count(0)
    about = page.request.get(f"{origin(sample)}/api/about").json()
    assert about["version"] == LATEST
    marker = json.loads((data_dir(sample.home) / "updated.json").read_text())
    assert marker["version"] == LATEST
    assert marker["launcher"] == str(sample.home / ".local/bin/kitden")
