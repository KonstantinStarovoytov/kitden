"""The Keychain module: secrets of moved servers live in the macOS Keychain, not in gateway.json.

The tests run a stand-in for `security` (tests/fixtures/fake_security.py); never the real one.
"""

import json

import pytest

from kitden.local_gateway import keychain
from kitden.local_gateway.keychain import (
    KeychainError,
    delete,
    is_reference,
    read,
    references_in,
    resolve_entry,
    store,
)

REACH = "Kitden could not reach the Keychain."


def test_store_returns_a_reference_and_read_gets_the_value_back(fake_keychain):
    ref = store("github", "GITHUB_TOKEN", "SENTINEL_SECRET_GH")
    assert ref == {"keychain": "github/GITHUB_TOKEN"}
    assert read(ref) == "SENTINEL_SECRET_GH"
    # The item is a generic password of the service "kitden".
    assert json.loads(fake_keychain.read_text()) == {
        "kitden github/GITHUB_TOKEN": "SENTINEL_SECRET_GH"
    }
    delete(ref)
    assert read(ref) is None
    delete(ref)  # quiet when the item is gone


def test_store_updates_an_item_that_is_there(fake_keychain):
    store("github", "GITHUB_TOKEN", "SENTINEL_SECRET_OLD")
    store("github", "GITHUB_TOKEN", "SENTINEL_SECRET_NEW value with spaces")
    assert read({"keychain": "github/GITHUB_TOKEN"}) == "SENTINEL_SECRET_NEW value with spaces"


def test_resolve_entry_replaces_references_and_leaves_plain_values(fake_keychain):
    store("github", "GITHUB_TOKEN", "SENTINEL_SECRET_GH")
    store("github", "Authorization", "Bearer SENTINEL_SECRET_HEADER")
    entry = {
        "command": "npx",
        "env": {"GITHUB_TOKEN": {"keychain": "github/GITHUB_TOKEN"}, "PLAIN": "x"},
        "headers": {"Authorization": {"keychain": "github/Authorization"}},
    }
    assert resolve_entry(entry) == {
        "command": "npx",
        "env": {"GITHUB_TOKEN": "SENTINEL_SECRET_GH", "PLAIN": "x"},
        "headers": {"Authorization": "Bearer SENTINEL_SECRET_HEADER"},
    }
    # The entry itself keeps its references.
    assert entry["env"]["GITHUB_TOKEN"] == {"keychain": "github/GITHUB_TOKEN"}
    assert references_in(entry) == [
        {"keychain": "github/GITHUB_TOKEN"},
        {"keychain": "github/Authorization"},
    ]


def test_a_plain_entry_never_runs_security():
    def never(args, stdin=None):
        raise AssertionError("security ran")

    entry = {"command": "npx", "env": {"PLAIN": "x"}, "headers": None}
    assert resolve_entry(entry, run=never) == entry
    assert resolve_entry({"command": "npx"}, run=never) == {"command": "npx"}
    assert references_in(entry) == []


def test_a_missing_item_names_its_server(fake_keychain):
    entry = {"command": "npx", "env": {"TOKEN": {"keychain": "my-server/TOKEN"}}}
    with pytest.raises(KeychainError) as error:
        resolve_entry(entry)
    assert str(error.value) == "Kitden could not read a secret of my-server from the Keychain."


def test_is_reference():
    assert is_reference({"keychain": "a/b"})
    for value in ("a/b", {"keychain": 1}, {"keychain": "a/b", "x": 1}, None, ["keychain"]):
        assert not is_reference(value)


def test_a_failing_security_never_shows_the_value():
    def broken(args, stdin=None):
        return 1, "boom"

    with pytest.raises(KeychainError) as error:
        store("s", "k", "SENTINEL_SECRET_V", run=broken)
    assert "SENTINEL_SECRET_V" not in str(error.value)
    assert str(error.value) == REACH
    with pytest.raises(KeychainError, match=REACH):
        read({"keychain": "s/k"}, run=broken)
    with pytest.raises(KeychainError, match=REACH):
        delete({"keychain": "s/k"}, run=broken)


def test_the_value_goes_on_stdin_as_hex_and_is_read_back():
    calls = []

    def recording(args, stdin=None):
        calls.append((args, stdin))
        return (0, "SENTINEL_SECRET_V\n") if args[0] == "find-generic-password" else (0, "")

    store("srv", "KEY", "SENTINEL_SECRET_V", run=recording)
    hex_value = b"SENTINEL_SECRET_V".hex()
    assert calls == [
        (["-i"], f'add-generic-password -U -s kitden -a "srv/KEY" -X {hex_value}\n'),
        (["find-generic-password", "-s", "kitden", "-a", "srv/KEY", "-w"], None),
    ]
    # The value is never in the arguments, so never in the process list.
    assert all("SENTINEL" not in " ".join(args) for args, _ in calls)


def test_a_write_that_does_not_read_back_fails():
    # `security -i` exits with 0 even when its line fails, so store reads the item back.
    def lost(args, stdin=None):
        return (44, "") if args[0] == "find-generic-password" else (0, "")

    with pytest.raises(KeychainError, match=REACH):
        store("s", "k", "SENTINEL_SECRET_V", run=lost)


@pytest.mark.parametrize("server", ['a"b', "a\nb", "a\\b"])
def test_a_name_that_would_break_the_command_line_is_refused(server):
    def never(args, stdin=None):
        raise AssertionError("security ran")

    with pytest.raises(KeychainError, match=REACH):
        store(server, "KEY", "SENTINEL_SECRET_V", run=never)


def test_without_security_the_keychain_cannot_be_reached():
    # The autouse fixture points KITDEN_SECURITY at a path that does not exist.
    with pytest.raises(KeychainError, match=REACH):
        read({"keychain": "s/k"})


def test_security_is_run_by_its_full_path(monkeypatch):
    monkeypatch.delenv("KITDEN_SECURITY")
    assert keychain.security_path() == "/usr/bin/security"
