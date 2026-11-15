"""Release checks 17 to 21 against the real secret store: the macOS Keychain through
`/usr/bin/security`, the Linux keyring through `secret-tool`. Each test is the twin of one that
runs the stand-in (named in its docstring), written the same way without `fake_keychain`.

Only the nightly runs it (.github/workflows/nightly.yml, job `systems`): on macOS with
KITDEN_REAL_KEYCHAIN=1 and a keychain made for the run as the default one, on Ubuntu with
KITDEN_REAL_KEYRING=1 and a keyring daemon on the session bus. Everywhere else it is skipped,
never run against a developer's own Keychain. Every item it makes belongs to a server whose name
starts `kitden-ci-`, and a `finally` removes it, also when the test fails halfway.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

import kitden.system
from kitden.gateways import data_dir
from kitden.local_gateway import keychain
from kitden.local_gateway.keychain import KeychainError, resolve_entry
from kitden.local_gateway.settings import SETTINGS_FILE, load_settings, save_tools
from tests.unit.test_local_gateway_move import add_claude, new_home, page_for, preview
from tests.unit.test_local_gateway_proxy import echo, gateway, text, tool, write_settings
from tests.unit.test_local_gateway_views import POST, hold
from tests.unit.test_local_gateway_views import page_for as view_page_for

MAC = kitden.system.SYSTEM == "mac"
REAL = (
    os.environ.get("KITDEN_REAL_KEYCHAIN") == "1"
    if MAC
    else kitden.system.SYSTEM == "linux" and os.environ.get("KITDEN_REAL_KEYRING") == "1"
)
pytestmark = pytest.mark.skipif(
    not REAL,
    reason="needs the CI secret store (KITDEN_REAL_KEYCHAIN=1 on macOS, "
    "KITDEN_REAL_KEYRING=1 on Linux)",
)
mac_only = pytest.mark.skipif(not MAC, reason="a fact about macOS's `security`")


@pytest.fixture(autouse=True)
def _the_real_tool(monkeypatch):
    """Kitden calls the real `security` or `secret-tool`, in this process and its children."""
    monkeypatch.delenv("KITDEN_SECURITY", raising=False)
    monkeypatch.delenv("KITDEN_SECRET_TOOL", raising=False)


def run_tool(args: list[str], what: str) -> subprocess.CompletedProcess:
    """Run the real tool directly, with Kitden's environment for it. A tool that waits (for a
    prompt, a keychain it cannot find) fails the test with that said, not a bare timeout."""
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=keychain.TIMEOUT,
            check=False,
            env=keychain.tool_env(),
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"{args[0]} did not answer within {keychain.TIMEOUT} s ({what})")


def ci_keychain() -> Path:
    """The keychain the nightly made for this run, from KITDEN_CI_KEYCHAIN. Only a file named
    `kitden-ci.keychain-db` under a temp folder, so never a login keychain."""
    named = os.environ.get("KITDEN_CI_KEYCHAIN")
    if not named:
        pytest.fail("KITDEN_CI_KEYCHAIN is not set: the workflow step names the run's keychain")
    path = Path(named).resolve()
    temps = [Path(tempfile.gettempdir()).resolve()]
    if os.environ.get("RUNNER_TEMP"):
        temps.append(Path(os.environ["RUNNER_TEMP"]).resolve())
    if path.name != "kitden-ci.keychain-db" or not any(path.is_relative_to(t) for t in temps):
        pytest.fail(
            f"KITDEN_CI_KEYCHAIN must be a file named kitden-ci.keychain-db under a temp folder: "
            f"{path}"
        )
    if not path.is_file():
        pytest.fail(f"KITDEN_CI_KEYCHAIN names no file: {path}")
    return path


@pytest.fixture(autouse=True)
def _the_ci_keychain_in_the_sandbox_home(_never_the_real_home, _the_real_tool):
    """macOS: `security` keeps the user's keychain list and default keychain under HOME (in
    Library/Preferences/com.apple.security.plist), and the tests run with HOME in the sandbox,
    where there is none: a write then waits for a keychain. So the run's keychain becomes the
    list and the default of this test's HOME too. The sandbox home gets the Library folders a
    real home has first: `security` does not make them, and without them its settings are lost
    with exit code 0."""
    if not MAC:
        return
    chain = str(ci_keychain())
    home = Path(os.environ["HOME"])
    for folder in ("Library/Preferences", "Library/Keychains"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    said = []
    for args in (
        ["list-keychains", "-d", "user", "-s", chain],
        ["default-keychain", "-d", "user", "-s", chain],
        ["unlock-keychain", "-p", "kitden-ci", chain],
    ):
        done = run_tool([keychain.SECURITY, *args], f"security {args[0]}")
        said.append(f"security {args[0]}: exit {done.returncode}, stderr {done.stderr.strip()!r}")
    default = run_tool([keychain.SECURITY, "default-keychain", "-d", "user"], "the default")
    listed = run_tool([keychain.SECURITY, "list-keychains", "-d", "user"], "the list")
    plist = home / "Library/Preferences/com.apple.security.plist"
    if Path(chain).name not in default.stdout or any(" exit 0," not in line for line in said):
        pytest.fail(
            "the run's keychain is not the default under the sandbox HOME "
            f"({home}):\n"
            + "\n".join(said)
            + f"\nread back: default-keychain exit {default.returncode}, "
            f"stdout {default.stdout.strip()!r}, stderr {default.stderr.strip()!r}; "
            f"list-keychains stdout {listed.stdout.strip()!r}"
            f"\n{plist} exists: {plist.exists()}"
        )


@pytest.fixture
def anyio_backend():
    return "asyncio"


def ref(server: str, key: str) -> dict:
    return {"keychain": f"{server}/{key}"}


def remove(*refs: dict) -> None:
    """Remove the items, quiet when they are not there."""
    for each in refs:
        assert each["keychain"].startswith("kitden-ci-"), each
        keychain.delete(each)


def tool_lookup(account: str) -> subprocess.CompletedProcess:
    """The secret store's own answer for the item Kitden keeps for `account`, by the real tool
    and not through Kitden: `security find-generic-password -s kitden -a <account> -w`, or
    `secret-tool lookup service kitden account <account>`."""
    if MAC:
        args = [keychain.SECURITY, "find-generic-password", "-s", "kitden", "-a", account, "-w"]
    else:
        args = [keychain.SECRET_TOOL, "lookup", "service", "kitden", "account", account]
    return run_tool(args, f"looking up {account}")


def found(account: str) -> str | None:
    """The value the tool prints for the item, or None when it says there is none."""
    done = tool_lookup(account)
    if MAC:
        if done.returncode == keychain.NOT_FOUND:
            return None
        assert done.returncode == 0, done.stderr
        return done.stdout.removesuffix("\n")
    if done.returncode == 1 and not done.stdout and not done.stderr.strip():
        return None
    assert done.returncode == 0, done.stderr
    return done.stdout


def printed(value: str) -> str:
    """What `found` gets for a value: `security find-generic-password -w` prints a value with a
    byte outside printable ASCII as hex (seen 2026-11-15 on a GitHub macOS runner);
    `secret-tool lookup` prints it as it is."""
    data = value.encode()
    if MAC and not all(0x20 <= byte <= 0x7E for byte in data):
        return data.hex()
    return value


# Check 21: facts about `security` (any value comes back whole, a long one is refused), and the
# same round trips through `secret-tool`.


@mac_only
def test_a_missing_item_ends_with_44():
    """Twin: test_keychain.py::test_a_missing_item_names_its_server."""
    missing = ref("kitden-ci-missing", "TOKEN")
    remove(missing)
    try:
        assert tool_lookup(missing["keychain"]).returncode == 44
        assert keychain.read(missing) is None
        entry = {"command": "npx", "env": {"TOKEN": missing}}
        with pytest.raises(KeychainError) as error:
            resolve_entry(entry)
        assert str(error.value) == (
            "Kitden could not read a secret of kitden-ci-missing from the Keychain."
        )
    finally:
        remove(missing)


def _round_trip(key: str, value: str) -> None:
    """Twin: test_keychain.py::test_the_value_goes_on_stdin_as_hex_and_is_read_back. Kitden
    writes the item (`security -i` with the hex line, or `secret-tool store` from stdin); the
    tool itself prints it back."""
    item = ref("kitden-ci-values", key)
    try:
        assert keychain.store("kitden-ci-values", key, value) == item
        assert found(item["keychain"]) == printed(value)
        assert keychain.read(item) == value
    finally:
        remove(item)
    assert found(item["keychain"]) is None


@mac_only
def test_a_value_with_quotes_and_spaces_comes_back_unchanged():
    _round_trip("QUOTES", 'a "b" \\ c\'d')


def test_a_value_with_a_quote_comes_back_unchanged():
    """`-g` prints it in quotes, with the hex or without it: Kitden reads either."""
    _round_trip("QUOTE", 'a"b')


def test_a_value_with_a_backslash_comes_back_unchanged():
    """`-g` prints it as hex, then in quotes with the backslash as `\\134`."""
    _round_trip("BACKSLASH", "a\\b")


@mac_only
def test_an_account_with_a_space_is_quoted_on_the_security_line():
    """`-a "<account>"` on the `security -i` line keeps a space inside the account."""
    item = ref("kitden-ci-with space", "TOKEN")
    remove(item)
    try:
        assert keychain.store("kitden-ci-with space", "TOKEN", "SENTINEL_CI_SPACE") == item
        assert found("kitden-ci-with space/TOKEN") == "SENTINEL_CI_SPACE"
        assert found("kitden-ci-with") is None
    finally:
        remove(item)
    assert found(item["keychain"]) is None


def test_a_value_in_other_alphabets_comes_back_unchanged():
    """`find-generic-password -w` prints this value as hex; Kitden reads `-g`'s `0x` form."""
    _round_trip("ALPHABETS", "ключ-héllo-日本")


def test_a_value_with_no_ascii_letter_comes_back_unchanged():
    """`find-generic-password -g` prints this value as hex alone, with no quoted part."""
    _round_trip("NOASCII", "日本")


@mac_only
def test_an_ascii_value_of_hex_digits_is_not_decoded():
    _round_trip("HEXDIGITS", "cafe1234")


@mac_only
def test_a_1024_character_value_comes_back_unchanged():
    """The side of the `security -i` line limit that works (seen on a macOS runner)."""
    _round_trip("MEDIUM", ("kitden-ci-1kb-" * 80)[:1024])


def test_a_4_kb_value_comes_back_unchanged():
    """The name is from before Kitden had a limit; check 21 of docs/development.md cites it.
    On Linux a 4 KB secret comes back unchanged. On macOS a `security -i` line longer than
    4,095 bytes is cut (seen 2026-11-15 on a GitHub macOS runner), so Kitden refuses the secret
    before it writes anything, and the item that was there stays as it was."""
    value = ("kitden-ci-4kb-" * 300)[:4096]
    assert len(value) == 4096
    if not MAC:
        _round_trip("LONG", value)
        return
    item = ref("kitden-ci-values", "LONG")
    remove(item)
    most = keychain.longest("kitden-ci-values", "LONG")
    try:
        keychain.store("kitden-ci-values", "LONG", "SENTINEL_CI_EARLIER")
        with pytest.raises(KeychainError) as error:
            keychain.store("kitden-ci-values", "LONG", value)
        assert str(error.value) == (
            "The secret kitden-ci-values/LONG is too long for the Keychain: 4,096 bytes, and "
            f"Kitden can store at most {most:,}. Keep the server in the client's own settings, "
            "or use a shorter token."
        )
        assert found(item["keychain"]) == "SENTINEL_CI_EARLIER"
    finally:
        remove(item)
    assert found(item["keychain"]) is None


@mac_only
def test_the_longest_value_that_fits_comes_back_whole():
    """The edge of Kitden's limit on the `security -i` line: the longest value it accepts."""
    most = keychain.longest("kitden-ci-values", "EDGE")
    _round_trip("EDGE", ("kitden-ci-edge-" * 300)[:most])


@mac_only
def test_one_byte_more_is_refused_and_nothing_is_stored():
    item = ref("kitden-ci-values", "EDGE")
    remove(item)
    most = keychain.longest("kitden-ci-values", "EDGE")
    try:
        with pytest.raises(KeychainError) as error:
            keychain.store("kitden-ci-values", "EDGE", "e" * (most + 1))
        assert str(error.value) == (
            f"The secret kitden-ci-values/EDGE is too long for the Keychain: {most + 1:,} "
            f"bytes, and Kitden can store at most {most:,}. Keep the server in the client's "
            "own settings, or use a shorter token."
        )
        assert found(item["keychain"]) is None
    finally:
        remove(item)


# Checks 17 and 19: a move into the gateway stores the token; Undo removes it.

TOKEN = "SENTINEL_SECRET_CI_TOKEN"


def _entry() -> dict:
    return {"command": "npx", "args": ["files-mcp"], "env": {"FILES_TOKEN": TOKEN}}


def _add(home, server: str) -> None:
    """Give Claude Code the server. Before the page opens: the page reads the setup once when
    it opens, and a review names only servers it knows ("Choose a known server.")."""
    add_claude(home, server, {"type": "stdio", **_entry()})


def _move(page, home, server: str) -> str:
    """Review and apply moving `server` from Claude Code into the gateway; the change's id."""
    answer = preview(page, home, ("claude_code", server))
    assert answer.status_code == 200, answer.json()
    change_id = answer.json()["id"]
    applied = page.post(f"/api/changes/{change_id}/apply", headers=POST)
    assert applied.json()["state"] == "verified", applied.json()
    return change_id


def _holds_a_reference(home, server: str) -> None:
    held = load_settings(home)["servers"][server]
    assert held["env"] == {"FILES_TOKEN": ref(server, "FILES_TOKEN")}
    assert TOKEN not in (data_dir(home) / SETTINGS_FILE).read_text()


def test_a_move_stores_the_token_and_leaves_a_reference(tmp_path):
    """Twin: test_local_gateway_move.py::test_apply_stores_the_items_and_undo_removes_them."""
    server = "kitden-ci-move"
    item = ref(server, "FILES_TOKEN")
    remove(item)
    home = new_home(tmp_path)
    _add(home, server)
    try:
        with page_for(home) as page:
            _move(page, home, server)
        assert found(item["keychain"]) == TOKEN
        _holds_a_reference(home, server)
    finally:
        remove(item)


def test_undo_of_the_move_removes_the_item(tmp_path):
    """Twin: test_local_gateway_move.py::test_apply_stores_the_items_and_undo_removes_them."""
    server = "kitden-ci-undo"
    item = ref(server, "FILES_TOKEN")
    remove(item)
    home = new_home(tmp_path)
    _add(home, server)
    try:
        with page_for(home) as page:
            change_id = _move(page, home, server)
            assert found(item["keychain"]) == TOKEN
            undone = page.post(f"/api/changes/{change_id}/undo", headers=POST).json()
            assert undone["state"] == "undone", undone
            assert undone["error"] is None
        assert found(item["keychain"]) is None
        if MAC:
            assert tool_lookup(item["keychain"]).returncode == 44
    finally:
        remove(item)


# Check 20: a plain token in gateway.json goes to the store by "Move secrets to the Keychain…".


def test_a_plain_token_in_gateway_json_moves_to_the_keychain(tmp_path):
    """Twin: test_gateway_remove.py::test_a_held_server_with_plain_secrets_says_so_and_can_move_them
    (the action `gateway.keychain` behind the Details button)."""
    server = "kitden-ci-plain"
    item = ref(server, "FILES_TOKEN")
    remove(item)
    home = new_home(tmp_path)
    hold(home, {server: _entry()})
    try:
        with view_page_for(home) as page:
            body = {"action": "gateway.keychain", "targets": [], "params": {"server": server}}
            answer = page.post("/api/changes/preview", json=body, headers=POST)
            assert answer.status_code == 200, answer.json()
            change = answer.json()
            assert TOKEN not in json.dumps(change)
            applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
            assert applied["state"] == "verified", applied
        assert found(item["keychain"]) == TOKEN
        _holds_a_reference(home, server)
    finally:
        remove(item)


# Check 18: a new session's gateway reads the secret from the real store and starts the server.


@pytest.mark.anyio
async def test_a_session_gets_the_secret_from_the_real_store(tmp_path):
    """Twin: test_local_gateway_proxy.py::test_a_reference_is_resolved_before_the_server_starts.
    `kitden mcp` runs as a child process, as a client starts it, and calls the real tool."""
    server = "kitden-ci-session"
    item = ref(server, "NOTE")
    remove(item)
    home = new_home(tmp_path)
    saved = tmp_path / "note.txt"
    entry = echo(server, "--save-env", "NOTE", str(saved))
    entry["env"] = {"NOTE": item, "PLAIN": "x"}
    write_settings(home, {server: entry})
    save_tools(home, server, [tool("echo"), tool("where")])
    # The MCP SDK passes a child only a few variables. A desktop session's bus is where
    # `tool_env` looks without one; the CI keyring's bus is elsewhere, so it is passed on.
    bus = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    env = {"DBUS_SESSION_BUS_ADDRESS": bus} if bus and not MAC else None
    try:
        keychain.store(server, "NOTE", "SENTINEL_SECRET_CI_NOTE")
        log = tmp_path / "stderr.txt"
        with log.open("w") as errlog:
            async with gateway(home, env=env, errlog=errlog) as client:
                await client.list_tools()
                answer = await client.call_tool("echo", {"text": "hello"})
                where = json.loads(text(await client.call_tool("where", {})))
        assert not answer.is_error and text(answer) == "hello", log.read_text()
        assert saved.read_text() == "SENTINEL_SECRET_CI_NOTE"
        assert {"NOTE", "PLAIN"} <= set(where["env"])
        assert "SENTINEL" not in (data_dir(home) / SETTINGS_FILE).read_text() + log.read_text()
    finally:
        remove(item)
