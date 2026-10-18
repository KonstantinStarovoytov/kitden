"""The files a release needs (feature 003, T001: FR-004, FR-015, research R2 and R10)."""

import tomllib
from pathlib import Path

import kitden

ROOT = Path(__file__).resolve().parents[2]


def _project() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]


def test_package_version_is_the_first_public_version():
    assert _project()["version"] == kitden.__version__ == "0.1.0"


def test_license_is_apache_2():
    assert _project()["license"] == "Apache-2.0"
    text = (ROOT / "LICENSE").read_text()
    assert "Apache License" in text and "Version 2.0" in text


def test_sdist_holds_only_what_runs():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    only = config["tool"]["hatch"]["build"]["targets"]["sdist"]["only-include"]
    assert only == ["src/kitden", "README.md", "LICENSE"]
