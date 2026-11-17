"""Which browser the browser tests drive. One engine per run, read from the environment and
not a pytest parameter, so a test's id is the same in every engine (tests/set-aside.txt
names tests by id)."""

from collections.abc import Mapping

ENGINES = ("chromium", "firefox", "webkit")


def engine_choice(environ: Mapping[str, str]) -> tuple[str, str | None]:
    """The engine KITDEN_BROWSER names (chromium when empty), and the channel
    KITDEN_BROWSER_CHANNEL names: None for Playwright's own build, or "chrome" for the
    installed Google Chrome. An unknown value is a ValueError that says what to use: a typo
    must not quietly test Chromium again."""
    engine = environ.get("KITDEN_BROWSER", "") or "chromium"
    channel = environ.get("KITDEN_BROWSER_CHANNEL", "")
    if engine not in ENGINES:
        raise ValueError(f"KITDEN_BROWSER={engine!r}: use chromium, firefox or webkit.")
    if channel not in ("", "chrome"):
        raise ValueError(f"KITDEN_BROWSER_CHANNEL={channel!r}: use chrome, or leave it empty.")
    if channel and engine != "chromium":
        raise ValueError(f"KITDEN_BROWSER_CHANNEL=chrome drives Chromium, not {engine}.")
    return engine, channel or None
