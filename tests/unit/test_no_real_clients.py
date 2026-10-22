"""Tests never run a real client: a client binary outside the test folders is refused."""

import subprocess

import pytest

from kitden.clients import codex, version_cache
from tests.conftest import fake_client_command


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
