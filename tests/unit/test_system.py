"""Where each system keeps things: one module, kitden.system (Linux spec, part 1)."""

import importlib
import sys
from pathlib import Path

import pytest

import kitden.system
from kitden.system import (
    app_commands,
    app_roots,
    claude_desktop_dir,
    cursor_state_dir,
    data_dir,
    secret_store_name,
    supported,
    watched,
)


def test_data_dir_on_each_system(system, tmp_path):
    system("mac")
    assert data_dir(tmp_path) == tmp_path / "Library/Application Support/kitden"
    system("linux")
    assert data_dir(tmp_path) == tmp_path / ".local/share/kitden"


def test_xdg_data_home_moves_the_linux_data_dir(system, tmp_path, monkeypatch):
    system("linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert data_dir(tmp_path) == tmp_path / "xdg/kitden"


def test_cursor_and_claude_desktop_folders(system, tmp_path, monkeypatch):
    system("mac")
    assert cursor_state_dir(tmp_path) == tmp_path / "Library/Application Support/Cursor/User"
    assert claude_desktop_dir(tmp_path) == tmp_path / "Library/Application Support/Claude"
    system("linux")
    assert cursor_state_dir(tmp_path) == tmp_path / ".config/Cursor/User"
    assert claude_desktop_dir(tmp_path) == tmp_path / ".config/Claude"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "conf"))
    assert cursor_state_dir(tmp_path) == tmp_path / "conf/Cursor/User"
    assert claude_desktop_dir(tmp_path) == tmp_path / "conf/Claude"


def test_app_roots_and_commands_are_empty_on_linux(system, tmp_path):
    system("mac")
    assert app_roots(tmp_path) == [Path("/Applications"), tmp_path / "Applications"]
    assert app_commands("cursor") == ("/Applications/Cursor.app/Contents/Resources/app/bin/cursor",)
    assert app_commands("codex") == (
        "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",
    )
    assert app_commands("claude") == ()
    system("linux")
    assert app_roots(tmp_path) == []
    assert app_commands("cursor") == ()


def test_watched_folders_hold_the_clients_and_claude_desktop(system, tmp_path):
    clients = [tmp_path / name for name in (".claude", ".codex", ".cursor", ".agents")]
    system("mac")
    assert watched(tmp_path) == [*clients, tmp_path / "Library/Application Support/Claude"]
    system("linux")
    assert watched(tmp_path) == [*clients, tmp_path / ".config/Claude"]


def test_secret_store_name(system):
    system("mac")
    assert secret_store_name() == "Keychain"
    system("linux")
    assert secret_store_name() == "keyring"


def _reloaded(monkeypatch, **changes):
    """The module read again with `changes` to the env or sys.platform, then put back."""
    for name, value in changes.items():
        if name == "platform":
            monkeypatch.setattr(sys, "platform", value)
        elif value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    found = importlib.reload(kitden.system).SYSTEM, kitden.system.supported()
    return found


@pytest.fixture(autouse=True)
def _module_read_again_after(monkeypatch):
    """After the test the env is put back first, then the module is read again from it."""
    yield
    monkeypatch.undo()
    importlib.reload(kitden.system)


def test_kitden_system_overrides_the_platform(monkeypatch):
    assert _reloaded(monkeypatch, KITDEN_SYSTEM="linux") == ("linux", True)


def test_the_platform_names_the_system(monkeypatch):
    assert _reloaded(monkeypatch, KITDEN_SYSTEM=None, platform="linux") == ("linux", True)
    assert _reloaded(monkeypatch, KITDEN_SYSTEM=None, platform="darwin") == ("mac", True)


def test_an_unknown_platform_is_not_supported(monkeypatch):
    assert _reloaded(monkeypatch, KITDEN_SYSTEM="plan9") == ("plan9", False)


def test_this_machine_is_supported():
    assert supported()
