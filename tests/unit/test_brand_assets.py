"""The brand files the page ships: small, local and present."""

from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "src" / "kitden" / "web" / "static"
CLIENTS = STATIC / "brand" / "clients"


def test_every_client_icon_is_small():
    # Icons draw at 24-28 px; a large file only slows the first paint.
    for name in ("claude.png", "codex.png", "codex-dark.png", "cursor.png", "cursor-dark.png"):
        assert (CLIENTS / name).stat().st_size < 24_000, name


def test_the_house_keeps_its_color():
    assert "#C85835" in (STATIC / "brand" / "kitden.svg").read_text()
