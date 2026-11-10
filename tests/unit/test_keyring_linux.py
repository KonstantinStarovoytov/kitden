"""Secrets in the Linux keyring through `secret-tool` (Linux spec, part 2)."""

import json

import pytest

from kitden.local_gateway import keychain
from kitden.local_gateway.keychain import KeychainError, delete, read, store

LINUX_REACH = (
    "Kitden could not reach the keyring. Install libsecret-tools and sign in to your desktop "
    "session."
)


@pytest.fixture(autouse=True)
def _as_linux(system):
    system("linux")


def test_store_puts_the_value_on_stdin_and_reads_it_back(fake_keychain):
    ref = store("srv", "KEY", "SENTINEL_SECRET_V")
    assert ref == {"keychain": "srv/KEY"}
    assert json.loads(fake_keychain.read_text()) == {"kitden srv/KEY": "SENTINEL_SECRET_V"}
    assert read(ref) == "SENTINEL_SECRET_V"


def test_the_command_lines_hold_no_value():
    calls = []

    def recording(args, stdin=None):
        calls.append((args, stdin))
        return (0, "SENTINEL_SECRET_V", "") if args[0] == "lookup" else (0, "", "")

    store("srv", "KEY", "SENTINEL_SECRET_V", run=recording)
    assert calls == [
        (
            ["store", "--label=Kitden: srv/KEY", "service", "kitden", "account", "srv/KEY"],
            "SENTINEL_SECRET_V",
        ),
        (["lookup", "service", "kitden", "account", "srv/KEY"], None),
    ]


def test_a_missing_item_is_none(fake_keychain):
    assert read({"keychain": "srv/NONE"}) is None


def test_a_keyring_that_is_down_cannot_be_reached_and_is_not_missing(fake_keychain, monkeypatch):
    monkeypatch.setenv("FAKE_SECRET_TOOL_DOWN", "1")
    for call in (
        lambda: read({"keychain": "srv/KEY"}),
        lambda: store("srv", "KEY", "SENTINEL_SECRET_V"),
        lambda: delete({"keychain": "srv/KEY"}),
    ):
        with pytest.raises(KeychainError) as error:
            call()
        assert str(error.value) == LINUX_REACH


def test_deleting_a_missing_item_is_quiet(fake_keychain):
    delete({"keychain": "srv/NONE"})


def test_a_write_that_does_not_read_back_fails():
    def lost(args, stdin=None):
        return (1, "", "") if args[0] == "lookup" else (0, "", "")

    with pytest.raises(KeychainError, match="could not reach the keyring"):
        store("s", "k", "SENTINEL_SECRET_V", run=lost)


def test_without_secret_tool_the_keyring_cannot_be_reached():
    # The autouse fixture points KITDEN_SECRET_TOOL at a path that does not exist.
    with pytest.raises(KeychainError) as error:
        read({"keychain": "s/k"})
    assert str(error.value) == LINUX_REACH


def test_a_missing_secret_names_its_server_and_the_keyring(fake_keychain):
    with pytest.raises(KeychainError) as error:
        keychain.resolve_entry({"env": {"T": {"keychain": "files/T"}}})
    assert str(error.value) == "Kitden could not read a secret of files from the keyring."


def test_secret_tool_is_run_by_its_full_path(monkeypatch):
    monkeypatch.delenv("KITDEN_SECRET_TOOL")
    assert keychain.secret_tool_path() == "/usr/bin/secret-tool"


def test_the_tool_env_fills_in_the_session_bus(monkeypatch):
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/501")
    assert keychain.tool_env()["DBUS_SESSION_BUS_ADDRESS"] == "unix:path=/run/user/501/bus"
    monkeypatch.delenv("XDG_RUNTIME_DIR")
    monkeypatch.setattr(keychain.os, "getuid", lambda: 1000)
    assert keychain.tool_env()["DBUS_SESSION_BUS_ADDRESS"] == "unix:path=/run/user/1000/bus"


def test_the_tool_env_keeps_a_bus_that_is_set(monkeypatch):
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/mine")
    assert keychain.tool_env()["DBUS_SESSION_BUS_ADDRESS"] == "unix:path=/tmp/mine"
