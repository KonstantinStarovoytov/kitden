"""Helpers for the tests that run the real clients."""

import os
from pathlib import Path
from typing import NoReturn

import pytest

from kitden.changes.client_cli import find_command
from kitden.command import installed_command


def _missing(name: str) -> NoReturn:
    """Skip the test, or fail it on the nightly run, which sets KITDEN_NEED_CLIENTS=1 and must
    have every command."""
    if os.environ.get("KITDEN_NEED_CLIENTS") == "1":
        pytest.fail(f"the nightly must have {name}")
    pytest.skip(f"needs the {name} command")


def need_command(name: str, home: Path) -> str:
    """The client's path, or the test is skipped (failed on the nightly)."""
    found = find_command(name, home)
    if found is None:
        _missing(name)
    return found


def need_kitden() -> str:
    """The kitden command, or the test is skipped (failed on the nightly)."""
    found = installed_command()
    if found is None:
        _missing("kitden")
    return found
