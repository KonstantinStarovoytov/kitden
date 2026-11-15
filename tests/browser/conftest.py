"""The page on the demo sample, in a real Chromium. Playwright is not a project dependency:
these tests run with `uv run --with playwright==1.64.1 pytest -m browser -q`."""

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn  # noqa: E402

from kitden import cli  # noqa: E402
from kitden.demo import build_demo_home, demo_build  # noqa: E402
from kitden.web.app import create_app  # noqa: E402

START = 47950  # the first port tried; the page takes the first free one from here


@dataclass
class Demo:
    home: Path
    url: str


@pytest.fixture(scope="session")
def browser(tmp_path_factory):
    """One Chromium for all the tests. It starts before any test moves HOME to the sandbox, so
    Playwright finds the browser it installed; the browser itself gets a sandbox HOME."""
    browser_home = tmp_path_factory.mktemp("browser-home")
    with sync_api.sync_playwright() as playwright:
        chromium = playwright.chromium.launch(env={**os.environ, "HOME": str(browser_home)})
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
    while not server.started:
        time.sleep(0.05)
    yield Demo(home=home, url=url)
    server.should_exit = True
    thread.join(timeout=10)


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
    deadline = time.monotonic() + 10
    while not tab.request.get(progress).json()["ready"]:
        assert time.monotonic() < deadline, "the first scan was not ready in 10 seconds"
        time.sleep(0.1)
    yield tab
    context.close()
    if errors:
        pytest.fail("The page had errors:\n" + "\n".join(errors))
