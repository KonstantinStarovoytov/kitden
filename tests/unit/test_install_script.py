"""install.sh with fake uv, curl and uname (feature 003: FR-005 to FR-007, research R4).

The script runs in a temporary home with fake commands first on PATH. Every call is logged to
one file, so a test can say what ran and what did not.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "install.sh"

FAKE_UV = """#!/bin/sh
echo "uv $*" >> "$FAKE_LOG"
case "$1 $2" in
  "tool dir") echo "$FAKE_BIN" ;;
  "tool install")
    [ -n "$FAKE_UV_FAIL" ] && exit 1
    printf '#!/bin/sh\\necho "kitden $*" >> "$FAKE_LOG"\\n' > "$FAKE_BIN/kitden"
    chmod +x "$FAKE_BIN/kitden" ;;
esac
"""
# The installer line is `curl ... | sh`: the fake prints a script that puts uv in the default place.
FAKE_CURL = """#!/bin/sh
echo "curl $*" >> "$FAKE_LOG"
[ -n "$FAKE_CURL_FAIL" ] && exit 22
bin="$HOME/.local/bin"
printf 'mkdir -p "%s" && cp "%s" "%s/uv" && chmod +x "%s/uv"\\n' "$bin" "$FAKE_UV" "$bin" "$bin"
"""
FAKE_UNAME = '#!/bin/sh\necho "${FAKE_UNAME:-Darwin}"\n'


def _write(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(0o755)


@pytest.fixture
def box(tmp_path):
    """A temporary home, a fake-command folder first on PATH, and a log of every call."""
    home = tmp_path / "home"
    fakes = tmp_path / "fakes"
    tool_bin = tmp_path / "toolbin"
    for folder in (home, fakes, tool_bin):
        folder.mkdir()
    _write(fakes / "uv-fake", FAKE_UV)
    _write(fakes / "curl", FAKE_CURL)
    _write(fakes / "uname", FAKE_UNAME)
    log = tmp_path / "calls.log"
    env = {
        "HOME": str(home),
        "PATH": f"{fakes}:/usr/bin:/bin",
        "FAKE_LOG": str(log),
        "FAKE_BIN": str(tool_bin),
        "FAKE_UV": str(fakes / "uv-fake"),
    }
    return {"env": env, "fakes": fakes, "home": home, "tool_bin": tool_bin, "log": log}


def _run(box, **extra):
    env = {**box["env"], **extra}
    result = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True)
    log = box["log"].read_text() if box["log"].exists() else ""
    return result, log


def _uv_on_path(box):
    (box["fakes"] / "uv").write_bytes((box["fakes"] / "uv-fake").read_bytes())
    (box["fakes"] / "uv").chmod(0o755)


def _version() -> str:
    match = re.search(r'^KITDEN_VERSION="([^"]+)"', SCRIPT.read_text(), re.M)
    assert match, "install.sh names the release in KITDEN_VERSION"
    return match.group(1)


def test_without_uv_it_installs_uv_then_kitden_and_opens_the_page(box):
    result, log = _run(box)
    assert result.returncode == 0, result.stderr
    assert "curl -LsSf https://astral.sh/uv/install.sh" in log
    assert f"uv tool install --python 3.13 kitden=={_version()}" in log
    assert "kitden \n" in log  # ran with no arguments: open the page
    assert log.index("curl") < log.index("uv tool install") < log.index("kitden")


def test_with_uv_present_it_does_not_install_uv_again(box):
    _uv_on_path(box)
    result, log = _run(box)
    assert result.returncode == 0, result.stderr
    assert "curl" not in log
    assert "uv tool install" in log


def test_it_says_where_kitden_is_and_how_to_fix_path(box):
    _uv_on_path(box)
    result, _ = _run(box)
    assert str(box["tool_bin"] / "kitden") in result.stdout
    assert "uv tool update-shell" in result.stdout


def test_no_path_hint_when_the_tool_folder_is_on_path(box):
    _uv_on_path(box)
    result, _ = _run(box, PATH=f"{box['env']['PATH']}:{box['tool_bin']}")
    assert result.returncode == 0
    assert "uv tool update-shell" not in result.stdout


LIBSECRET = (
    "To store server secrets, install libsecret-tools (Debian, Ubuntu) or libsecret "
    "(Fedora, Arch)."
)


def test_on_linux_it_installs_kitden_and_opens_the_page(box, tmp_path):
    _uv_on_path(box)
    result, log = _run(box, FAKE_UNAME="Linux", KITDEN_SECRET_TOOL=str(tmp_path / "none"))
    assert result.returncode == 0, result.stderr
    assert f"uv tool install --python 3.13 kitden=={_version()}" in log
    assert "kitden \n" in log


def test_on_linux_without_secret_tool_it_says_which_package(box, tmp_path):
    _uv_on_path(box)
    result, _ = _run(box, FAKE_UNAME="Linux", KITDEN_SECRET_TOOL=str(tmp_path / "none"))
    assert LIBSECRET in result.stdout


def test_on_linux_with_secret_tool_it_says_nothing_about_it(box):
    _uv_on_path(box)
    _write(box["fakes"] / "secret-tool", "#!/bin/sh\n")
    result, _ = _run(box, FAKE_UNAME="Linux", KITDEN_SECRET_TOOL=str(box["fakes"] / "secret-tool"))
    assert "libsecret" not in result.stdout


def test_on_a_mac_it_says_nothing_about_secret_tool(box):
    _uv_on_path(box)
    result, _ = _run(box)
    assert "libsecret" not in result.stdout


def test_another_system_installs_nothing(box):
    result, log = _run(box, FAKE_UNAME="FreeBSD")
    assert result.returncode == 1
    assert "Kitden runs on macOS and Linux. Nothing was installed." in result.stderr
    assert log == ""


def test_uv_install_failure_gives_exit_2(box):
    result, log = _run(box, FAKE_CURL_FAIL="1")
    assert result.returncode == 2
    assert "Could not install uv" in result.stdout + result.stderr
    assert "uv tool install" not in log


def test_kitden_install_failure_gives_exit_3(box):
    _uv_on_path(box)
    result, log = _run(box, FAKE_UV_FAIL="1")
    assert result.returncode == 3
    assert "Could not install Kitden" in result.stdout + result.stderr
    assert "kitden \n" not in log  # the page was not opened


def test_the_script_never_touches_client_settings(box):
    _uv_on_path(box)
    _run(box)
    assert not os.path.exists(box["home"] / ".claude.json")
    assert not os.path.exists(box["home"] / ".codex")
    assert not os.path.exists(box["home"] / ".cursor")


def test_windows_script_names_the_same_release_and_stops_for_now():
    text = (ROOT / "install.ps1").read_text()
    assert f'$KitdenVersion = "{_version()}"' in text
    assert "Nothing was installed" in text
    assert "irm https://astral.sh/uv/install.ps1 | iex" in text
