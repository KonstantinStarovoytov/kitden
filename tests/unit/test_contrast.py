"""Text on the action and success fills stays readable in both themes (WCAG AA, 4.5:1)."""

import re
from pathlib import Path

CSS = (Path(__file__).parents[2] / "src/kitden/web/static/style.css").read_text()


def tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))


def block(selector_start: str) -> str:
    """The text between the braces of the rule that starts at `selector_start`."""
    start = CSS.index(selector_start) + len(selector_start)
    return CSS[start : CSS.index("}", start)]


LIGHT = tokens(block(":root {"))
DARK_RULE = tokens(block(':root[data-theme="dark"] {'))
DARK_AUTO = tokens(block(':root:not([data-theme="light"]) {'))
DARK = {**LIGHT, **DARK_RULE}


def luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_contrast_matches_known_values():
    assert round(contrast("#ffffff", "#000000"), 1) == 21.0
    assert round(contrast("#777777", "#ffffff"), 2) == 4.48


def test_success_and_action_labels_are_readable_in_both_themes():
    for theme in (LIGHT, DARK):
        assert contrast(theme["--on-success"], theme["--success"]) >= 4.5
        assert contrast(theme["--on-action"], theme["--action"]) >= 4.5
    done = ".btn.primary.done, .btn.primary.done:hover"
    assert done + " { background: var(--success); color: var(--on-success); }" in CSS


def test_system_dark_theme_has_the_same_success_tokens():
    for name in ("--success", "--on-success"):
        assert DARK_AUTO[name] == DARK_RULE[name]
