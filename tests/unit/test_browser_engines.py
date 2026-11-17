"""The browser tests drive the engine the environment names, and stop on a name they do not
know."""

import re

import pytest

from tests.browser.engines import engine_choice


def test_chromium_is_the_default():
    assert engine_choice({}) == ("chromium", None)
    assert engine_choice({"KITDEN_BROWSER": "", "KITDEN_BROWSER_CHANNEL": ""}) == ("chromium", None)


def test_each_engine_and_the_chrome_channel():
    assert engine_choice({"KITDEN_BROWSER": "firefox"}) == ("firefox", None)
    assert engine_choice({"KITDEN_BROWSER": "webkit"}) == ("webkit", None)
    assert engine_choice({"KITDEN_BROWSER_CHANNEL": "chrome"}) == ("chromium", "chrome")


@pytest.mark.parametrize(
    ("environ", "words"),
    [
        ({"KITDEN_BROWSER": "safari"}, "KITDEN_BROWSER='safari': use chromium, firefox or webkit."),
        ({"KITDEN_BROWSER": "Firefox"}, "KITDEN_BROWSER='Firefox'"),
        ({"KITDEN_BROWSER_CHANNEL": "msedge"}, "KITDEN_BROWSER_CHANNEL='msedge': use chrome"),
        (
            {"KITDEN_BROWSER": "webkit", "KITDEN_BROWSER_CHANNEL": "chrome"},
            "drives Chromium, not webkit",
        ),
    ],
)
def test_an_unknown_value_says_what_to_use(environ, words):
    with pytest.raises(ValueError, match=re.escape(words)):
        engine_choice(environ)
