"""Running the installer: the ring moves only on the installer's own lines."""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from kitden.gateways import data_dir
from kitden.update.install import Install
from kitden.update.run import STEPS, Outcome, step_for, upgrade, write_marker

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_steps_are_in_order():
    assert STEPS == ("Downloading…", "Installing…", "Restarting Kitden…", "Reloading…")


def test_uv_lines_move_the_ring():
    assert step_for("uv", "Updated kitden v0.7.1 -> v0.7.2") == 1
    assert step_for("uv", "Nothing to upgrade") is None
    assert step_for("uv", " + kitden==0.7.2") is None
    assert step_for("uv", "Installed 1 executable: kitden") is None


def test_brew_lines_move_the_ring():
    assert step_for("brew", "==> Fetching downloads for: kitden") == 0
    assert step_for("brew", "==> Fetching kitden") == 0
    assert step_for("brew", "==> Downloading https://example.org/kitden.tar.gz") == 0
    assert step_for("brew", "==> Pouring kitden--0.7.3.arm64_sonoma.bottle.tar.gz") == 1
    assert step_for("brew", "==> Upgrading kitden") == 1
    assert step_for("brew", "Updated 1 tap.") is None


def test_a_brew_source_build_moves_to_installing():
    # Without a bottle brew builds: the header (shown when it installed dependencies first), a
    # dependency, or the first command the formula runs ends the downloads.
    assert step_for("brew", "==> Installing konstantinstarovoytov/tap/kitden") == 1
    assert step_for("brew", "==> Installing konstantinstarovoytov/tap/kitden dependency: rust") == 1
    assert step_for("brew", "==> python3.13 -m venv --system-site-packages --without-pip /x") == 1
    assert step_for("brew", "==> python3.13 -m pip --python=/x/bin/python install kitden") == 1
    # `brew upgrade` that builds from source: seen 2026-11-12 with Homebrew 7.0.13.
    assert step_for("brew", "==> Upgrading local/kitden-test/kitden") == 1
    assert step_for("brew", "==> Upgrading 1 outdated package, with result:") is None


def test_a_line_from_the_other_tool_does_nothing():
    assert step_for("uv", "==> Pouring kitden--0.7.3.bottle.tar.gz") is None
    assert step_for("brew", "Updated kitden v0.7.1 -> v0.7.2") is None


def _launcher(folder: Path) -> Path:
    """A stand-in `kitden` that reports the version stored beside it."""
    path = folder / "kitden"
    path.write_text(
        f"#!{sys.executable}\n"
        "import pathlib\n"
        "print('kitden', (pathlib.Path(__file__).parent / 'version').read_text().strip())\n"
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    (folder / "version").write_text("0.7.1")
    return path


def _installer(folder: Path, lines: list[str], *, new_version: str, code: int = 0) -> Path:
    """A stand-in installer: prints `lines`, installs `new_version`, exits with `code`."""
    path = folder / "installer.py"
    path.write_text(
        "import pathlib, sys\n"
        f"for line in {lines!r}:\n"
        "    print(line, flush=True)\n"
        "print('to stderr', file=sys.stderr, flush=True)\n"
        f"(pathlib.Path({str(folder)!r}) / 'version').write_text({new_version!r})\n"
        f"sys.exit({code})\n"
    )
    return path


def _install(folder: Path, method: str, script: Path) -> Install:
    return Install(method, _launcher(folder), (sys.executable, str(script)))  # type: ignore[arg-type]


async def test_uv_run_reports_updated(tmp_path):
    script = _installer(
        tmp_path, ["Updated kitden v0.7.1 -> v0.7.2", " + kitden==0.7.2"], new_version="0.7.2"
    )
    steps = []
    out = await upgrade(_install(tmp_path, "uv", script), steps.append, "0.7.1")
    assert steps == [1]
    assert out == Outcome("updated", "0.7.2", out.tail)
    assert "to stderr" in out.tail  # stderr is merged into the same stream


async def test_steps_never_go_back_or_repeat(tmp_path):
    lines = [
        "==> Pouring kitden--0.7.2.bottle.tar.gz",
        "==> Fetching downloads for: kitden",
        "==> Pouring again",
        "==> Downloading something",
    ]
    script = _installer(tmp_path, lines, new_version="0.7.2")
    steps = []
    out = await upgrade(_install(tmp_path, "brew", script), steps.append, "0.7.1")
    assert steps == [1]
    assert out.state == "updated"


async def test_brew_steps_come_in_order(tmp_path):
    lines = [
        "==> Fetching downloads for: kitden",
        "==> Upgrading kitden",
        "==> Pouring kitden--0.7.2.tar.gz",
    ]
    script = _installer(tmp_path, lines, new_version="0.7.2")
    steps = []
    await upgrade(_install(tmp_path, "brew", script), steps.append, "0.7.1")
    assert steps == [0, 1]


async def test_brew_bottle_run(tmp_path):
    lines = [
        "==> Fetching downloads for: konstantinstarovoytov/tap/kitden",
        "==> Upgrading konstantinstarovoytov/tap/kitden",
        "  0.7.1 -> 0.7.2",
        "==> Pouring kitden--0.7.2.arm64_tahoe.bottle.1.tar.gz",
        "/opt/homebrew/Cellar/kitden/0.7.2: 1,234 files, 40MB",
    ]
    steps = []
    script = _installer(tmp_path, lines, new_version="0.7.2")
    out = await upgrade(_install(tmp_path, "brew", script), steps.append, "0.7.1")
    assert steps == [0, 1]
    assert out.state == "updated"


async def test_brew_source_build_run(tmp_path):
    # No "Pouring": the ring says Installing once the build starts, not Downloading to the end.
    lines = [
        "==> Fetching downloads for: konstantinstarovoytov/tap/kitden",
        "==> Upgrading konstantinstarovoytov/tap/kitden",
        "  0.7.1 -> 0.7.2",
        "==> python3.13 -m venv --system-site-packages --without-pip /c/kitden/0.7.2/libexec",
        "==> python3.13 -m pip --python=/c/kitden/0.7.2/libexec/bin/python install kitden",
        "/c/kitden/0.7.2: 1,234 files, 40MB, built in 3 minutes",
    ]
    steps = []
    script = _installer(tmp_path, lines, new_version="0.7.2")
    out = await upgrade(_install(tmp_path, "brew", script), steps.append, "0.7.1")
    assert steps == [0, 1]
    assert out.state == "updated"


async def test_brew_keeps_the_old_keg(tmp_path, monkeypatch):
    # Old gateways still run from the old keg until they move; brew must fetch the tap.
    monkeypatch.delenv("HOMEBREW_NO_INSTALL_CLEANUP", raising=False)
    monkeypatch.delenv("HOMEBREW_NO_AUTO_UPDATE", raising=False)
    monkeypatch.setenv("KITDEN_TEST_KEPT", "yes")
    script = tmp_path / "installer.py"
    names = ("HOMEBREW_NO_INSTALL_CLEANUP", "HOMEBREW_NO_AUTO_UPDATE", "KITDEN_TEST_KEPT")
    script.write_text(
        f"import os\nfor name in {names!r}:\n    print(name, os.environ.get(name), flush=True)\n"
    )
    brew = await upgrade(_install(tmp_path, "brew", script), lambda step: None, "0.7.1")
    assert "HOMEBREW_NO_INSTALL_CLEANUP 1" in brew.tail
    assert "HOMEBREW_NO_AUTO_UPDATE None" in brew.tail
    assert "KITDEN_TEST_KEPT yes" in brew.tail
    uv = await upgrade(_install(tmp_path, "uv", script), lambda step: None, "0.7.1")
    assert "HOMEBREW_NO_INSTALL_CLEANUP None" in uv.tail
    assert os.environ.get("HOMEBREW_NO_INSTALL_CLEANUP") is None  # this process is not changed


async def test_same_version_is_not_an_update(tmp_path):
    script = _installer(tmp_path, ["Nothing to upgrade"], new_version="0.7.1")
    steps = []
    out = await upgrade(_install(tmp_path, "uv", script), steps.append, "0.7.1")
    assert steps == []
    assert out.state == "same"
    assert out.version == "0.7.1"


async def test_failure_keeps_the_last_twenty_lines(tmp_path):
    lines = [f"line {n}" for n in range(30)]
    script = _installer(tmp_path, lines, new_version="0.7.1", code=1)
    out = await upgrade(_install(tmp_path, "uv", script), lambda step: None, "0.7.1")
    assert out.state == "failed"
    assert out.version is None
    assert len(out.tail) == 20
    assert out.tail[0] == "line 11"
    assert out.tail[-1] == "to stderr"


async def test_missing_installer_is_a_failed_outcome(tmp_path):
    install = Install(
        "uv", _launcher(tmp_path), (str(tmp_path / "no-such-uv"), "tool", "upgrade", "kitden")
    )
    out = await upgrade(install, lambda step: None, "0.7.1")
    assert out.state == "failed"
    assert "no-such-uv" in " ".join(out.tail)


async def test_exit_zero_but_unreadable_version_is_failed(tmp_path):
    script = _installer(tmp_path, ["Updated kitden v0.7.1 -> v0.7.2"], new_version="not a version")
    out = await upgrade(_install(tmp_path, "uv", script), lambda step: None, "0.7.1")
    assert out.state == "failed"
    assert out.tail  # why: the installer's own lines


async def test_last_line_without_newline_is_read(tmp_path):
    script = tmp_path / "installer.py"
    script.write_text(
        "import pathlib, sys\n"
        f"(pathlib.Path({str(tmp_path)!r}) / 'version').write_text('0.7.2')\n"
        "sys.stdout.write('Updated kitden v0.7.1 -> v0.7.2')\n"
    )
    steps = []
    out = await upgrade(_install(tmp_path, "uv", script), steps.append, "0.7.1")
    assert steps == [1]
    assert out.state == "updated"


def test_marker_is_private_and_atomic(tmp_path):
    launcher = tmp_path / "bin" / "kitden"
    write_marker(tmp_path, "0.7.2", launcher)
    path = data_dir(tmp_path) / "updated.json"
    record = json.loads(path.read_text())
    assert record["version"] == "0.7.2"
    assert record["launcher"] == str(launcher)
    assert isinstance(record["time"], str)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(path.parent.glob("updated.json.*")) == []  # no temp file left behind


def test_marker_replaces_the_old_one(tmp_path):
    write_marker(tmp_path, "0.7.2", tmp_path / "kitden")
    write_marker(tmp_path, "0.7.3", tmp_path / "kitden")
    record = json.loads((data_dir(tmp_path) / "updated.json").read_text())
    assert record["version"] == "0.7.3"
