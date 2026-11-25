"""How the README recorder films (scripts/record_scenes.py): the page's clock stops where it is
and then moves one frame at a time."""

import importlib.util
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def scenes():
    spec = importlib.util.spec_from_file_location(
        "record_scenes", ROOT / "scripts/record_scenes.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tab(browser):
    context = browser.new_context()
    page = context.new_page()
    page.clock.install()
    page.goto("about:blank")
    yield page
    context.close()


def test_filming_keeps_the_pages_own_time(scenes, tab, tmp_path):
    """Playwright reads a number as seconds. Given milliseconds, the clock went to the year
    58871 and every timer on the page ran at once."""
    tab.evaluate("setTimeout(() => { window.rang = true; }, 5000)")
    film = scenes.Film(tab, {"x": 0, "y": 0, "width": 10, "height": 10}, tmp_path)
    film.start()
    started = tab.evaluate("Date.now()")
    assert abs(started / 1000 - time.time()) < 5
    assert not tab.evaluate("window.rang")
    for _ in range(30):
        film.step(keep=False)
    assert tab.evaluate("Date.now()") - started == 1000


def test_a_clock_that_stops_elsewhere_stops_the_recording(scenes, tab, tmp_path, monkeypatch):
    pause_at = tab.clock.pause_at
    monkeypatch.setattr(tab.clock, "pause_at", lambda at: pause_at(at + 60))
    film = scenes.Film(tab, {"x": 0, "y": 0, "width": 10, "height": 10}, tmp_path)
    with pytest.raises(RuntimeError, match="clock paused 60000 ms"):
        film.start()


def test_a_pause_that_comes_too_late_is_asked_again(scenes, tab, tmp_path, monkeypatch):
    """Playwright refuses a time that has passed: on a busy computer, 50 ms can be over."""
    pause_at, asked = tab.clock.pause_at, []

    def late_once(at):
        asked.append(at)
        if len(asked) == 1:
            tab.wait_for_timeout(200)
        pause_at(at)

    monkeypatch.setattr(tab.clock, "pause_at", late_once)
    scenes.Film(tab, {"x": 0, "y": 0, "width": 10, "height": 10}, tmp_path).start()
    assert len(asked) == 2
