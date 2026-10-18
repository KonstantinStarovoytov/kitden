"""The page's own files keep the strict CSP and never turn text into HTML (FR-041)."""

import re
from pathlib import Path

STATIC = Path(__file__).parents[2] / "src/kitden/web/static"
SCRIPTS = sorted((STATIC / "js").glob("*.js"))
INDEX = STATIC / "index.html"
SVG_NS = "http://www.w3.org/2000/svg"


def test_no_html_injection_apis_in_scripts():
    assert SCRIPTS, "the page scripts live in static/js"
    banned = [
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "eval(",
        "new Function",
    ]
    for script in SCRIPTS:
        text = script.read_text()
        assert [b for b in banned if b in text] == [], script.name


def test_index_has_no_inline_code_or_styles():
    html = INDEX.read_text()
    assert "<style" not in html
    assert not re.search(r"\sstyle\s*=", html)
    assert not re.search(r"<script(?![^>]*\ssrc=)[^>]*>", html)
    assert not re.search(r"\son[a-z]+\s*=", html)


def test_nothing_is_loaded_from_another_site():
    # Example addresses in placeholders are fine; loading code, styles or data from them is not.
    loads = [
        r"""(src|href)\s*=\s*["']?https?://""",
        r"""url\(\s*["']?https?://""",
        r"@import",
        r"""import\s[^;]*["']https?://""",
        r"""fetch\(\s*["'`]https?://""",
        r"""EventSource\(\s*["'`]https?://""",
    ]
    for path in [INDEX, STATIC / "style.css", *SCRIPTS]:
        text = path.read_text()
        assert [p for p in loads if re.search(p, text)] == [], path.name


def test_every_module_import_exists():
    for script in SCRIPTS:
        for target in re.findall(r"""from\s+["'](\.[^"']+)["']""", script.read_text()):
            assert (script.parent / target).resolve().is_file(), f"{script.name} imports {target}"


def test_index_loads_the_app_as_a_module():
    assert '<script type="module" src="/static/js/app.js"></script>' in INDEX.read_text()
    assert not (STATIC / "app.js").exists()


def test_page_is_named_kitden():
    index = INDEX.read_text()
    assert "<title>Kitden</title>" in index and "</span>Kitden</div>" in index
    for path in [INDEX, *SCRIPTS]:
        assert "Agent setup" not in path.read_text(), path.name
