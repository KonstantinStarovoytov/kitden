"""Client apps on this Mac and their link schemes, from fixture Info.plist files."""

from pathlib import Path

from kitden.apps import app_url, registered_schemes
from tests.conftest import FIXTURES

APPS = FIXTURES / "apps"


def test_schemes_come_from_the_apps_info_plist():
    assert registered_schemes(APPS / "Claude.app/Contents/Info.plist") == {
        "claude",
        "msauth.com.anthropic.claudefordesktop",
    }
    assert registered_schemes(APPS / "Plain.app/Contents/Info.plist") == set()
    assert registered_schemes(APPS / "Missing.app/Contents/Info.plist") == set()


def test_each_client_links_to_its_app_when_installed():
    assert app_url("claude_code", [APPS]) == "claude://"
    assert app_url("codex", [APPS]) == "codex://"  # ChatGPT.app bundles Codex
    assert app_url("cursor", [APPS]) == "cursor://"
    assert app_url("claude_desktop", [APPS]) is None


def test_no_link_without_the_app_or_its_scheme(tmp_path):
    assert app_url("cursor", [tmp_path]) is None
    plain = tmp_path / "Cursor.app/Contents"
    plain.mkdir(parents=True)
    plain.joinpath("Info.plist").write_bytes((APPS / "Plain.app/Contents/Info.plist").read_bytes())
    assert app_url("cursor", [tmp_path]) is None
    # The person's own Applications folder counts too; the first root that has it wins.
    assert app_url("cursor", [tmp_path, APPS]) == "cursor://"


def test_a_broken_plist_gives_no_link(tmp_path):
    broken = tmp_path / "Claude.app/Contents"
    broken.mkdir(parents=True)
    broken.joinpath("Info.plist").write_text("not a plist")
    assert app_url("claude_code", [tmp_path, Path("/nonexistent")]) is None
