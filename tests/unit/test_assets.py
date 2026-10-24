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


def test_every_font_file_is_declared_and_cyrillic_letters_have_their_own():
    # Folder names can be Cyrillic, so both fonts need the subset; a file nobody declares is waste.
    urls = re.findall(r"@font-face\s*{[^}]*url\(\"?([^\")]+)", CSS)
    files = {p.name for p in (STATIC / "fonts").glob("*.woff2")}
    assert files == {u.rsplit("/", 1)[1] for u in urls}
    for name in ("inter", "jetbrains-mono"):
        file = f"{name}-cyrillic-wght-normal.woff2"
        assert (STATIC / "fonts" / file).read_bytes()[:4] == b"wOF2"
        face = re.search(rf"@font-face\s*{{[^}}]*{file}[^}}]*}}", CSS)
        assert face and "unicode-range: U+0301,U+0400-045F" in face.group(0), file


def test_nothing_loads_from_another_site():
    for path in [STATIC / "index.html", STATIC / "style.css", *STATIC.glob("js/*.js")]:
        assert not re.search(r"(src|href|url)\(?=?\"?https?://", path.read_text()), path.name


def test_every_icon_name_used_is_in_the_module():
    module = (STATIC / "js/icons.js").read_text()
    used = set(
        re.findall(
            r"icon\(\"([a-z0-9-]+)\"", "".join(p.read_text() for p in STATIC.glob("js/*.js"))
        )
    )
    assert used <= set(re.findall(r"^\s*\"([a-z0-9-]+)\":", module, re.M))
