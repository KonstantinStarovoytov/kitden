"""The files a release needs (feature 003, T001: FR-004, FR-015, research R2 and R10)."""

import tomllib
from pathlib import Path

import kitden

ROOT = Path(__file__).resolve().parents[2]


def _project() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]


def test_the_version_is_the_same_everywhere():
    import json

    version = _project()["version"]
    assert kitden.__version__ == version
    for manifest in ("plugins/kitden/plugin.json", "plugins/kitden/.claude-plugin/plugin.json"):
        assert json.loads((ROOT / manifest).read_text())["version"] == version
    assert f'KITDEN_REF="v{version}"' in (ROOT / "install.sh").read_text()
    assert f'$KitdenRef = "v{version}"' in (ROOT / "install.ps1").read_text()


def test_license_is_apache_2():
    assert _project()["license"] == "Apache-2.0"
    text = (ROOT / "LICENSE").read_text()
    assert "Apache License" in text and "Version 2.0" in text


def test_sdist_holds_only_what_runs():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    only = config["tool"]["hatch"]["build"]["targets"]["sdist"]["only-include"]
    assert only == ["src/kitden", "README.md", "LICENSE"]


# Released before release notes files existed.
NO_NOTES = {"0.1.0", "0.1.1"}


def test_the_version_has_release_notes():
    """The release workflow stops a tag without notes; this catches it before the tag."""
    version = _project()["version"]
    if version in NO_NOTES:
        return
    notes = ROOT / f"docs/releases/v{version}.md"
    assert notes.is_file(), f"write docs/releases/v{version}.md before the release"
    assert notes.read_text().strip()


def test_the_readme_works_on_pypi():
    """PyPI keeps absolute fallback images; GitHub sources follow the current branch."""
    import re

    readme = (ROOT / "README.md").read_text()
    targets = re.findall(r'(?:src|href)="([^"]+)"', readme)
    targets += re.findall(r"\]\(([^)\s]+)\)", readme)
    assert targets
    for target in targets:
        assert target.startswith("https://"), target
    for picture in re.findall(r"<picture>.*?</picture>", readme, re.S):
        assert "<img " in picture, "PyPI drops source; keep a plain img inside"
    assert "https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md" in readme
