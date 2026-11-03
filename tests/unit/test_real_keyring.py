"""One real round trip through `secret-tool` and a running keyring. Only the Ubuntu CI job runs
it, with KITDEN_REAL_KEYRING=1 and a keyring daemon on the session bus at
$XDG_RUNTIME_DIR/bus (see .github/workflows/release.yml); everywhere else it is skipped."""

import os

import pytest

import kitden.system
from kitden.local_gateway import keychain

pytestmark = pytest.mark.skipif(
    os.environ.get("KITDEN_REAL_KEYRING") != "1" or kitden.system.SYSTEM != "linux",
    reason="needs the CI keyring (KITDEN_REAL_KEYRING=1 on Linux)",
)


@pytest.fixture(autouse=True)
def _the_real_secret_tool(monkeypatch):
    monkeypatch.delenv("KITDEN_SECRET_TOOL", raising=False)


def _round_trip(key: str) -> None:
    ref = keychain.store("kitden-ci", key, "SENTINEL_CI_VALUE")
    try:
        assert keychain.read(ref) == "SENTINEL_CI_VALUE"
    finally:
        keychain.delete(ref)
    assert keychain.read(ref) is None
    keychain.delete(ref)  # quiet when it is not there


def test_store_read_and_delete_in_the_real_keyring():
    _round_trip("TOKEN")


def test_without_the_bus_address_the_session_bus_is_found(monkeypatch):
    # A gateway that Codex starts gets no DBUS_SESSION_BUS_ADDRESS; tool_env fills it in.
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS")
    _round_trip("NO_BUS")
