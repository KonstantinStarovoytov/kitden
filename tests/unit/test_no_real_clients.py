"""Tests never run a real client: a client binary outside the test folders is refused."""

import subprocess

import pytest

from kitden.clients import codex, version_cache


def test_a_real_client_binary_is_refused_in_tests():
    with pytest.raises(AssertionError, match="real client"):
        subprocess.run(["/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex", "-V"])


def test_every_module_finds_no_client_command():
    assert version_cache.version_command("codex") is None
    assert codex.version_command("codex") is None
