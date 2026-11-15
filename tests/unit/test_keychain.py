"""The Keychain module: secrets of moved servers live in the macOS Keychain, not in gateway.json.

The tests run a stand-in for `security` (tests/fixtures/fake_security.py); never the real one.
"""

import asyncio
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

# macOS words and `security` command lines; Linux has its own tests.
pytestmark = pytest.mark.usefixtures("as_mac")

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
        return 1, "boom", ""

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
        if args[0] == "find-generic-password":
            return 0, 'class: "genp"\n', 'password: "SENTINEL_SECRET_V"\n'
        return 0, "", ""

    store("srv", "KEY", "SENTINEL_SECRET_V", run=recording)
    hex_value = b"SENTINEL_SECRET_V".hex()
    assert calls == [
        (["-i"], f'add-generic-password -U -s kitden -a "srv/KEY" -X {hex_value}\n'),
        (["find-generic-password", "-s", "kitden", "-a", "srv/KEY", "-g"], None),
    ]
    # The value is never in the arguments, so never in the process list.
    assert all("SENTINEL" not in " ".join(args) for args, _ in calls)


def test_a_write_that_does_not_read_back_fails():
    # `security -i` exits with 0 even when its line fails, so store reads the item back.
    def lost(args, stdin=None):
        return (44, "", "") if args[0] == "find-generic-password" else (0, "", "")

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


def answering(said: str):
    """A `security` whose `find-generic-password -g` writes `said` on stderr, as the real one
    writes the password there and the item's attributes on stdout."""

    def run(args, stdin=None):
        assert args[0] == "find-generic-password"
        assert args[-1] == "-g"
        return 0, 'keychain: "/x.keychain-db"\nclass: "genp"\n', said

    return run


@pytest.mark.parametrize(
    ("said", "value"),
    [
        # The lines are as `security` wrote them on a GitHub macOS runner (2026-11-15).
        ('password: "SENTINEL_SECRET_V"', "SENTINEL_SECRET_V"),
        # An ASCII value that is all hex digits is printed as itself and never decoded.
        ('password: "cafe1234"', "cafe1234"),
        ('password: "0xCAFE"', "0xCAFE"),
        # Quotes and a backslash: the hex, then the value in quotes, the backslash in octal.
        ('password: 0x6120226222205C20632764  "a "b" \\134 c\'d"', 'a "b" \\ c\'d'),
        # A quote alone: printed with the hex or without it (not seen alone), read either way.
        ('password: "a"b"', 'a"b'),
        ('password: 0x612262  "a"b"', 'a"b'),
        # Bytes outside printable ASCII: their hex, then the printable ones in quotes.
        ('password: 0x6109620A63  "a\\011b\\012c"', "a\tb\nc"),
        ('password: 0xD0BAD0BB2D68C3A9  "\\320\\272\\320\\273-h\\303\\251"', "кл-hé"),
        # No printable byte at all: only the hex, and one space.
        ("password: 0xE697A5E69CAC ", "日本"),
        ("password: 0xE697A5E69CAC", "日本"),
        ("password: 0xE697A5E69CAC   ", "日本"),
        ('password: 0xe697a5e69cac  "\\346\\227\\245\\346\\234\\254"', "日本"),
        ('password: 0x41 "A"', "A"),
        # The hex is the value; the quoted part is never read.
        ('password: 0x41  "B"', "A"),
    ],
)
def test_the_password_line_of_find_g_is_read(said, value):
    assert read({"keychain": "s/k"}, run=answering(said + "\n")) == value


@pytest.mark.parametrize(
    "said",
    [
        "",  # no password line
        # An empty password, as `security` wrote it on the runner: Kitden never stores one.
        "password: \n",
        'password: ""\n',
        "password:\n",
        "password: SENTINEL\n",  # not quoted
        'password: "a" more\n',
        # A backslash with no hex was never seen: whatever it means, it is not trusted.
        'password: "a "b" \\134 c\'d"\n',
        'password: "a \\"b\\" \\\\ c\'d"\n',
        'password: "\\134134"\n',
        'password: "\\101"\n',
        'password: "\\\\"\n',
        'password: "a\\qb"\n',
        'password: "a\\"\n',
        'password: "é"\n',  # a letter that would be in hex
        "password: 0xABC\n",  # half a byte
        "password: 0xZZ\n",
        "password: 0x\n",
        "password: 0xE697A5E69CAC x\n",
        'password: 0xFF  "\\377"\n',  # not UTF-8
        'password: "a"\npassword: "b"\n',  # two
    ],
)
def test_a_password_line_it_does_not_know_is_never_a_value(said):
    with pytest.raises(KeychainError) as error:
        read({"keychain": "my-server/TOKEN"}, run=answering(said))
    assert str(error.value) == "Kitden could not read a secret of my-server from the Keychain."


@pytest.mark.parametrize(
    "value",
    [
        "ключ-héllo-日本",
        "日本",
        "cafe1234",
        'a "b" \\ c\'d',
        'a"b',
        "a\\b",
        "line 1\nline\t2",
        "\\134",
    ],
)
def test_any_value_comes_back_unchanged(fake_keychain, value):
    ref = store("srv", "KEY", value)
    assert read(ref) == value
    assert json.loads(fake_keychain.read_text()) == {"kitden srv/KEY": value}


# A `security -i` line is cut at about 4 KB and the rest run as another command (seen
# 2026-11-15 on a GitHub macOS runner), so `store` refuses a line longer than 4,000 bytes.
# For the account "srv/LONG" the line around the hex is 52 bytes, so 1,974 bytes fit.


def line_for(account: str, value: str) -> str:
    return f'add-generic-password -U -s kitden -a "{account}" -X {value.encode().hex()}\n'


def test_the_longest_value_that_fits_on_a_security_line_is_stored(fake_keychain):
    assert keychain.longest("srv", "LONG") == 1974
    value = "v" * 1974
    assert len(line_for("srv/LONG", value).encode()) == 4000
    assert read(store("srv", "LONG", value)) == value


@pytest.mark.parametrize(
    ("value", "size"),
    [("v" * 1975, "1,975"), ("é" * 988, "1,976"), ("v" * 50_000, "50,000")],
)
def test_one_byte_more_is_refused_before_security_runs(value, size):
    def never(args, stdin=None):
        raise AssertionError("security ran")

    with pytest.raises(KeychainError) as error:
        store("srv", "LONG", value, run=never)
    assert str(error.value) == (
        f"The secret srv/LONG is too long for the Keychain: {size} bytes, and Kitden can "
        "store at most 1,974. Keep the server in the client's own settings, or use a shorter "
        "token."
    )


def test_the_limit_counts_the_account_too():
    assert keychain.longest("a-much-longer-server-name", "LONG") == 1974 - 11


def test_a_sign_in_too_long_for_the_keychain_keeps_the_one_there(fake_keychain, capsys):
    """A refreshed sign-in that does not fit is not written: the earlier one stays, and the
    gateway says why it was not saved."""
    from mcp.shared.auth import OAuthToken

    from kitden.local_gateway import oauth

    ref = store("signer", "sign-in", "SENTINEL_EARLIER_SIGN_IN")
    storage = oauth.KeychainStorage("signer", ref)
    tokens = OAuthToken(access_token="SENTINEL_" + "t" * 3000, token_type="Bearer")
    asyncio.run(storage.set_tokens(tokens))
    assert read(ref) == "SENTINEL_EARLIER_SIGN_IN"
    assert capsys.readouterr().err == (
        "Kitden could not save the new sign-in of signer: it is too long for the Keychain. "
        "Give signer a token in a header instead, if it takes one.\n"
    )


def test_a_sign_in_that_cannot_reach_the_keychain_says_so(capsys):
    from mcp.shared.auth import OAuthToken

    from kitden.local_gateway import oauth

    def broken(args, stdin=None):
        return 1, "", ""

    storage = oauth.KeychainStorage("signer", {"keychain": "signer/sign-in"}, run=broken)
    asyncio.run(storage.set_tokens(OAuthToken(access_token="SENTINEL_T", token_type="Bearer")))
    assert capsys.readouterr().err == (
        "Kitden could not save the new sign-in of signer. Kitden could not reach the Keychain.\n"
    )


def test_bytes_that_are_not_utf_8_on_stdout_do_not_break_a_read(tmp_path, monkeypatch):
    """`-g` writes the keychain's path on stdout; Kitden reads only stderr there."""
    tool = tmp_path / "security"
    tool.write_text(
        "#!/bin/sh\nprintf 'keychain: \"/x\\377.keychain-db\"\\n'\n"
        "printf 'password: \"SENTINEL_V\"\\n' >&2\n"
    )
    tool.chmod(0o755)
    monkeypatch.setenv("KITDEN_SECURITY", str(tool))
    assert read({"keychain": "s/k"}) == "SENTINEL_V"


def test_the_runner_returns_stderr_too(fake_keychain):
    code, out, err = keychain.run_security(
        ["find-generic-password", "-s", "kitden", "-a", "x/y", "-w"]
    )
    assert (code, out) == (44, "")
    assert "could not be found" in err


def test_a_release_ignores_the_stand_in_variables(monkeypatch):
    # Whoever sets the gateway's environment must not choose the program that gets the secrets.
    monkeypatch.setenv("KITDEN_SECURITY", "/tmp/x")
    monkeypatch.setenv("KITDEN_SECRET_TOOL", "/tmp/x")
    assert keychain.security_path() == "/tmp/x"  # a source checkout: the tests' stand-in
    monkeypatch.setattr(keychain, "from_source", lambda: False)
    assert keychain.security_path() == "/usr/bin/security"
    assert keychain.secret_tool_path() == "/usr/bin/secret-tool"
