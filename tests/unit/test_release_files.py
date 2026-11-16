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
    assert f'KITDEN_VERSION="{version}"' in (ROOT / "install.sh").read_text()
    assert f'$KitdenVersion = "{version}"' in (ROOT / "install.ps1").read_text()
    registry = json.loads((ROOT / "server.json").read_text())
    assert registry["version"] == version
    assert [p["version"] for p in registry["packages"]] == [version]


def test_the_registry_entry_matches_the_package():
    """The MCP Registry checks the PyPI README for the server name (checked 2026-11-08)."""
    import json

    registry = json.loads((ROOT / "server.json").read_text())
    name = registry["name"]
    assert name == "io.github.KonstantinStarovoytov/kitden"
    assert f"<!-- mcp-name: {name} -->" in (ROOT / "README.md").read_text()
    (package,) = registry["packages"]
    assert package["registryType"] == "pypi"
    assert package["identifier"] == _project()["name"]
    assert package["transport"] == {"type": "stdio"}
    assert package["packageArguments"] == [{"type": "positional", "value": "mcp"}]
    glama = json.loads((ROOT / "glama.json").read_text())
    assert glama["maintainers"] == ["KonstantinStarovoytov"]


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


def _pypi_readme() -> str:
    """README.md as the build hands it to PyPI (hatch-fancy-pypi-readme in pyproject.toml)."""
    import re

    hooks = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["hatch"]["metadata"]
    hook = hooks["hooks"]["fancy-pypi-readme"]
    assert hook["fragments"] == [{"path": "README.md"}]
    page = (ROOT / "README.md").read_text()
    for rule in hook["substitutions"]:
        page = re.sub(rule["pattern"], rule["replacement"], page)
    return page


def test_the_readme_works_on_pypi():
    """PyPI shows every img: one light picture per place, every address absolute."""
    import re

    assert "readme" in _project()["dynamic"]
    readme = _pypi_readme()
    assert "-mode-only" not in readme and "<picture" not in readme
    targets = re.findall(r'(?:src|href)="([^"]+)"', readme)
    targets += re.findall(r"\]\(([^)\s]+)\)", readme)
    assert targets
    for target in targets:
        assert target.startswith("https://"), target
    images = "https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/"
    pictures = [src for src in re.findall(r'<img src="([^"]+)"', readme) if src.startswith(images)]
    assert len(pictures) == 5 and pictures[0] == images + "hero.svg"
    for picture in pictures:
        assert "-dark." not in picture, picture
        assert (ROOT / "docs/images" / picture.removeprefix(images)).is_file(), picture
    assert "https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md" in readme
