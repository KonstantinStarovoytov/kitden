"""The guard in tests/conftest.py also holds in a contract test. No client starts here: the
guard refuses the command before anything runs."""

import subprocess

import pytest

pytestmark = pytest.mark.contract


def test_a_contract_test_cannot_start_a_client_with_a_home_outside_the_sandbox():
    with pytest.raises(AssertionError, match="outside the sandbox"):
        subprocess.run(["codex", "--version"], env={"HOME": "/nonexistent-home"}, check=False)
