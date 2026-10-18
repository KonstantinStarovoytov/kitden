"""The built-files check the release workflow runs (feature 003, contracts/release.md)."""

import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check-dist.sh"


def _dist(tmp_path: Path, sdist_names: list[str], wheel_names: list[str]) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    with tarfile.open(dist / "kitden-0.1.0.tar.gz", "w:gz") as tar:
        for name in sdist_names:
            info = tarfile.TarInfo(name)
            tar.addfile(info)
    with zipfile.ZipFile(dist / "kitden-0.1.0-py3-none-any.whl", "w") as wheel:
        for name in wheel_names:
            wheel.writestr(name, "")
    return dist


def _check(dist: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-eo", "pipefail", str(SCRIPT), str(dist)], capture_output=True, text=True
    )


GOOD_SDIST = ["kitden-0.1.0/pyproject.toml", "kitden-0.1.0/src/kitden/cli.py"]
GOOD_WHEEL = ["kitden/cli.py", "kitden/web/static/index.html"]


def test_a_clean_build_passes(tmp_path):
    assert _check(_dist(tmp_path, GOOD_SDIST, GOOD_WHEEL)).returncode == 0


def test_an_sdist_with_tests_fails(tmp_path):
    dist = _dist(tmp_path, [*GOOD_SDIST, "kitden-0.1.0/tests/unit/test_x.py"], GOOD_WHEEL)
    done = _check(dist)
    assert done.returncode == 1
    assert "tests/" in done.stdout + done.stderr


def test_a_wheel_without_the_page_files_fails(tmp_path):
    done = _check(_dist(tmp_path, GOOD_SDIST, ["kitden/cli.py"]))
    assert done.returncode == 1
    assert "index.html" in done.stdout + done.stderr
