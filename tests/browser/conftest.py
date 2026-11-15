"""The page on the demo sample, in a real Chromium. Playwright is not a project dependency:
these tests run with `uv run --with playwright==1.64.1 pytest -m browser -q`."""

import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn  # noqa: E402

from kitden import cli  # noqa: E402
from kitden.demo import build_demo_home, demo_build  # noqa: E402
from kitden.web.app import create_app  # noqa: E402

START = 47950  # the first port tried; the page takes the first free one from here

# A shared runner can be slow: every expect() waits up to 15 seconds, not Playwright's 5.
sync_api.expect.set_options(timeout=15_000)

# The sample's Claude Code plugin that is on for every project.
PLUGIN = "superpowers@demo-market"


@dataclass
class Demo:
    home: Path
    url: str


@pytest.fixture(scope="session")
def browser(tmp_path_factory):
    """One Chromium for all the tests. It starts before any test moves HOME to the sandbox, so
    Playwright finds the browser it installed; the browser itself gets a sandbox HOME and no
    XDG_* folders, so it writes nothing of this computer's."""
    browser_home = tmp_path_factory.mktemp("browser-home")
    env = {key: value for key, value in os.environ.items() if not key.startswith("XDG_")}
    with sync_api.sync_playwright() as playwright:
        chromium = playwright.chromium.launch(env={**env, "HOME": str(browser_home)})
        yield chromium
        chromium.close()


@pytest.fixture
def demo(tmp_path):
    """The medium sample under tmp_path, served as `kitden demo` serves it, until the test ends."""
    home = build_demo_home(tmp_path / "demo", "medium")
    made = cli._page(create_app, demo_build(home), home, START, demo=True)
    assert made is not None, f"no free port from {START}"
    app, port, _, url = made
    # As start_page in scripts/record_readme.py: uvicorn in a thread.
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", timeout_graceful_shutdown=2
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # A failed bind ends the thread: fail the test then, not when the job's time runs out.
    deadline = time.monotonic() + 10
    while not server.started:
        assert thread.is_alive(), f"the page's server stopped before it started (port {port})"
        assert time.monotonic() < deadline, (
            f"the page's server did not start in 10 seconds (port {port})"
        )
        time.sleep(0.05)
    yield Demo(home=home, url=url)
    server.should_exit = True
    thread.join(timeout=10)
    assert not thread.is_alive(), "the page's server did not stop in 10 seconds"


@pytest.fixture
def page(browser, demo):
    """A 1280 by 800 page at the demo, once its first scan is ready. A console error or an
    uncaught error on the page fails the test: only a real browser shows a break of the page's
    Content-Security-Policy."""
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    tab = context.new_page()
    errors: list[str] = []
    tab.on("console", lambda message: message.type == "error" and errors.append(message.text))
    tab.on("pageerror", lambda error: errors.append(str(error)))
    tab.goto(demo.url)
    progress = demo.url.split("?")[0] + "api/progress"
    deadline = time.monotonic() + 30
    while not tab.request.get(progress).json()["ready"]:
        assert time.monotonic() < deadline, "the first scan was not ready in 30 seconds"
        time.sleep(0.1)
    yield tab
    context.close()
    if errors:
        pytest.fail("The page had errors:\n" + "\n".join(errors))


# Helpers the tests share ------------------------------------------------------------------------


def SETTINGS(demo):
    return demo.home / ".claude/settings.json"


def origin(demo) -> str:
    parts = urlsplit(demo.url)
    return f"{parts.scheme}://{parts.netloc}"


def wait_until(check, seconds: float = 5) -> None:
    deadline = time.monotonic() + seconds
    while not check():
        if time.monotonic() > deadline:
            raise AssertionError("gave up waiting")
        time.sleep(0.05)


def details_of(page, plugin: str):
    """Library, the plugin's marketplace, the plugin's row: its Details panel."""
    name, market = plugin.split("@")
    page.get_by_role("link", name="Library", exact=True).click()
    page.get_by_role("button", name=f"Open {market}").click()
    page.get_by_role("button", name=re.compile(rf"^{re.escape(name)}, ")).click()
    return page.get_by_role("complementary", name="Details")


def turn_off(page, plugin: str) -> None:
    """The plugin's Details, "Turn off for all projects…": the plugin's own switch, which adds
    its change to the preview."""
    details_of(page, plugin).get_by_role("button", name="Turn off for all projects…").click()
