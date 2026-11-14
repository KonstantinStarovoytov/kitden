"""Tests never run a real client: a client binary outside the test folders is refused."""

import os
import subprocess

import pytest

from kitden.clients import codex, version_cache
from tests.conftest import client_homes, fake_client_command, refused
from tests.contract.conftest import need_command, need_kitden


def test_a_real_client_binary_is_refused_in_tests():
    with pytest.raises(AssertionError, match="real client"):
        subprocess.run(["/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex", "-V"])


def test_every_module_finds_no_client_command():
    assert version_cache.version_command("codex") is None
    assert codex.version_command("codex") is None


@pytest.mark.parametrize(
    "args",
    [
        "codex --version",
        ["/usr/bin/env", "codex", "--version"],
        ["sh", "-c", "codex --version"],
        ["/bin/zsh", "-lc", "cd /tmp && claude --version"],
        ["/Applications/Cursor.app/Contents/MacOS/Cursor", "--version"],
    ],
)
def test_shell_strings_wrappers_and_the_cursor_app_are_refused(args):
    with pytest.raises(AssertionError, match="real client"):
        subprocess.run(args, shell=isinstance(args, str), capture_output=True, check=False)


def test_a_fake_client_in_the_test_folder_may_run(tmp_path):
    fake = fake_client_command(tmp_path, "codex", "echo codex-cli 0.159.2")
    for args in ([str(fake), "-V"], ["sh", "-c", f"{fake} -V"], f"{fake} -V"):
        done = subprocess.run(
            args, shell=isinstance(args, str), capture_output=True, text=True, check=False
        )
        assert done.stdout == "codex-cli 0.159.2\n"


def test_other_commands_that_only_mention_a_client_still_run():
    done = subprocess.run(["echo", "codex"], capture_output=True, text=True, check=False)
    assert done.stdout == "codex\n"


@pytest.mark.parametrize(
    "args",
    [["/usr/bin/security", "find-generic-password"], "security -h", ["sh", "-c", "security"]],
)
def test_the_real_security_command_is_refused(args):
    with pytest.raises(AssertionError, match="real Keychain"):
        subprocess.run(args, shell=isinstance(args, str), capture_output=True, check=False)


def test_a_contract_test_may_run_a_client_in_a_sandbox_home(tmp_path):
    home = str(tmp_path / "home")
    assert refused(["/usr/local/bin/codex", "-V"], home, tmp_path, contract=True) is None


def test_a_contract_test_is_refused_a_client_outside_the_sandbox_home(tmp_path):
    for home in ("/Users/someone", None):
        assert "outside the sandbox" in refused(["codex"], home, tmp_path, contract=True)


def test_any_other_test_is_refused_a_real_client_and_the_keychain(tmp_path):
    assert "real client" in refused(["claude"], str(tmp_path), tmp_path, contract=False)
    assert "real Keychain" in refused(["security"], str(tmp_path), tmp_path, contract=False)
    assert "real Keychain" in refused(["secret-tool"], str(tmp_path), tmp_path, contract=True)


def test_a_client_can_take_three_folders_as_its_home():
    assert client_homes({"HOME": "/a"}) == ["/a"]
    assert client_homes({"HOME": "/a", "CODEX_HOME": "/b", "CLAUDE_CONFIG_DIR": "/c"}) == [
        "/a",
        "/c",
        "/b",
    ]
    assert client_homes({}) == [None]


def test_no_test_inherits_a_real_client_folder(monkeypatch):
    # The autouse fixtures ran before this body: both variables are gone whatever the shell had.
    assert "CLAUDE_CONFIG_DIR" not in os.environ and "CODEX_HOME" not in os.environ


def test_a_missing_client_skips_the_test_and_fails_it_on_the_nightly(tmp_path, monkeypatch):
    with pytest.raises(pytest.skip.Exception):
        need_command("no-such-client", tmp_path)
    monkeypatch.setenv("KITDEN_NEED_CLIENTS", "1")
    with pytest.raises(pytest.fail.Exception, match="the nightly must have no-such-client"):
        need_command("no-such-client", tmp_path)


def test_a_missing_kitden_command_skips_the_test_and_fails_it_on_the_nightly(monkeypatch):
    monkeypatch.setattr("tests.contract.conftest.installed_command", lambda: None)
    with pytest.raises(pytest.skip.Exception):
        need_kitden()
    monkeypatch.setenv("KITDEN_NEED_CLIENTS", "1")
    with pytest.raises(pytest.fail.Exception, match="the nightly must have kitden"):
        need_kitden()
