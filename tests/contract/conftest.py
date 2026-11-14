"""Helpers for the tests that run the real clients."""

import os
from pathlib import Path

import pytest

from kitden.changes.client_cli import find_command


def need_command(name: str, home: Path) -> str:
    """The client's path. Without it the test is skipped, or fails on the nightly run, which
    sets KITDEN_NEED_CLIENTS=1 and must have every client."""
    found = find_command(name, home)
    if found is None:
        if os.environ.get("KITDEN_NEED_CLIENTS") == "1":
            pytest.fail(f"the nightly must have {name}")
        pytest.skip(f"needs the {name} command")
    return found
