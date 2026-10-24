"""The page loads its fonts from local files and nothing from another site."""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "src" / "kitden" / "web" / "static"
CSS = (STATIC / "style.css").read_text()


def test_fonts_are_local_files():
    urls = re.findall(r"@font-face\s*{[^}]*url\(\"?([^\")]+)", CSS)
    assert urls and all(u.startswith("/static/fonts/") for u in urls)
    assert all((STATIC / u.removeprefix("/static/")).is_file() for u in urls)
    assert (STATIC / "fonts/OFL-Inter.txt").is_file()
    assert (STATIC / "fonts/OFL-JetBrainsMono.txt").is_file()


def test_nothing_loads_from_another_site():
    for path in [STATIC / "index.html", STATIC / "style.css", *STATIC.glob("js/*.js")]:
        assert not re.search(r"(src|href|url)\(?=?\"?https?://", path.read_text()), path.name
