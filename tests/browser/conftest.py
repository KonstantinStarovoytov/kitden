"""The page on the demo sample, in a real browser. Playwright is not a project dependency:
these tests run with `uv run --with playwright==1.64.1 python -m pytest -m browser -q`.
KITDEN_BROWSER and KITDEN_BROWSER_CHANNEL pick the browser (tests/browser/engines.py)."""

import asyncio
import contextlib
import json
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

import kitden.web.app as web  # noqa: E402
from kitden import cli  # noqa: E402
from kitden.demo import (  # noqa: E402
    DemoRunner,
    build_demo_home,
    demo_adapters,
    demo_build,
    demo_command,
)
from kitden.update.install import Install  # noqa: E402
from kitden.update.run import Outcome  # noqa: E402
from kitden.web.app import create_app  # noqa: E402
from tests.browser.engines import engine_choice  # noqa: E402
from tests.conftest import guarded_lookups  # noqa: E402
from tests.offline import STAND_INS  # noqa: E402

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
    """One browser for all the tests, the one engine_choice picks; a name it does not know
    stops the run. It starts before any test moves HOME to the sandbox, so Playwright finds
    the browser it installed; the browser itself gets a sandbox HOME and no XDG_* folders,
    so it writes nothing of this computer's."""
    browser_home = tmp_path_factory.mktemp("browser-home")
    env = {key: value for key, value in os.environ.items() if not key.startswith("XDG_")}
    try:
        engine, channel = engine_choice(os.environ)
    except ValueError as error:
        pytest.exit(str(error), returncode=pytest.ExitCode.USAGE_ERROR)
    with sync_api.sync_playwright() as playwright:
        launched = getattr(playwright, engine).launch(
            env={**env, "HOME": str(browser_home)}, channel=channel
        )
        yield launched
        launched.close()


@contextlib.contextmanager
def serving(app, port: int):
    """The app served by uvicorn in a thread on 127.0.0.1:port, until the block ends; as
    start_page in scripts/record_readme.py."""
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
    try:
        yield server
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    assert not thread.is_alive(), "the page's server did not stop in 10 seconds"


@pytest.fixture
def demo(tmp_path):
    """The medium sample under tmp_path, served as `kitden demo` serves it, until the test ends."""
    home = build_demo_home(tmp_path / "demo", "medium")
    made = cli._page(create_app, demo_build(home), home, START, demo=True)
    assert made is not None, f"no free port from {START}"
    app, port, _, url = made
    with serving(app, port):
        yield Demo(home=home, url=url)


# The latest version the sample's update check hears of, and what the fake installer says.
LATEST = "99.0.0"


async def fake_upgrade(install, on_step, version):
    """The installer's steps, then "updated to LATEST"; nothing is installed."""
    for step in (0, 1):
        on_step(step)
        await asyncio.sleep(0.3)
    return Outcome("updated", LATEST, [])


@pytest.fixture
def sample(tmp_path, monkeypatch, fake_keychain):
    """The medium sample, served as `kitden open` serves a real home, not in demo mode: search,
    sources, Details of a found item and the update all work. Everything that would leave the
    sample is a stand-in (tests/offline.py, the demo's adapters and runner, the fake Keychain),
    and the network guard is on: a test that tries to connect outside this computer fails.
    Left real: a move into the gateway starts the server to read its tools; that flow uses demo."""
    guard = guarded_lookups(monkeypatch)
    next(guard)
    for module, name, value in STAND_INS:
        monkeypatch.setattr(module, name, value)
    monkeypatch.setattr(web, "default_adapters", demo_adapters)
    home = build_demo_home(tmp_path / "sample", "medium")
    options = {
        "run": DemoRunner(home),
        "setup_command": lambda: demo_command(home),
        "version_refresh": dict,
        "processes": list,
        "open_browser": lambda url: None,
        "fetch": lambda url: json.dumps({"info": {"version": LATEST}}).encode(),
        "upgrade": fake_upgrade,
        "install": Install("uv", home / ".local/bin/kitden", ("uv", "tool", "upgrade", "kitden")),
        # Flow 13 gives it a stand-in that starts the new version's page (Task 23).
        "start_page": lambda launcher, value: None,
    }
    made = cli._page(create_app, demo_build(home), home, START, **options)
    assert made is not None, f"no free port from {START}"
    app, port, _, url = made
    with serving(app, port):
        yield Demo(home=home, url=url)
    next(guard, None)  # fails the test when it tried to connect outside


@contextlib.contextmanager
def open_tab(browser, url: str):
    """A 1280 by 800 tab at url, once the page's first scan is ready. A console error or an
    uncaught error on the page fails the test: only a real browser shows a break of the page's
    Content-Security-Policy."""
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    tab = context.new_page()
    errors: list[str] = []
    tab.on("console", lambda message: message.type == "error" and errors.append(message.text))
    tab.on("pageerror", lambda error: errors.append(str(error)))
    tab.goto(url)
    progress = url.split("?")[0] + "api/progress"
    deadline = time.monotonic() + 30
    while not tab.request.get(progress).json()["ready"]:
        assert time.monotonic() < deadline, "the first scan was not ready in 30 seconds"
        time.sleep(0.1)
    yield tab
    context.close()
    if errors:
        pytest.fail("The page had errors:\n" + "\n".join(errors))


@pytest.fixture
def page(browser, demo):
    """A tab on the demo (open_tab)."""
    with open_tab(browser, demo.url) as tab:
        yield tab


@pytest.fixture
def sample_page(browser, sample):
    """A tab on the sample (open_tab)."""
    with open_tab(browser, sample.url) as tab:
        yield tab


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
