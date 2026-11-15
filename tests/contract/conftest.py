"""Helpers for the tests that run the real clients."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import NoReturn

import anyio
import pytest
from mcp import Client, StdioServerParameters

from kitden.changes.client_cli import find_command
from kitden.command import installed_command

# How each client names the project to `kitden mcp`, as src/kitden/local_gateway/project.py
# reads it: the env value it sets, or None when it starts the server in the project folder.
SIGNALS: dict[str, str | None] = {
    "claude_code": "CLAUDE_PROJECT_DIR",
    "cursor": "WORKSPACE_FOLDER_PATHS",
    "codex": None,
}

# A whole session fails after this many seconds rather than hang; each request after 60.
SESSION_SECONDS = 180


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


@asynccontextmanager
async def session(home: Path, project: Path, client: str) -> AsyncIterator[Client]:
    """The stand-in session: the installed `kitden mcp` over stdio, started as `client` starts
    it in `project`, with only the env the MCP SDK passes on plus the sandbox home and the
    client's signal. Other clients' signals stay unset: Claude Code and Cursor start it in the
    home folder, which names no project."""
    signal = SIGNALS[client]
    env = {"HOME": str(home)}
    if signal is not None:
        env[signal] = str(project)
    params = StdioServerParameters(
        command=need_kitden(),
        args=["mcp"],
        env=env,
        cwd=str(home if signal is not None else project),
    )
    with anyio.fail_after(SESSION_SECONDS):
        async with Client(params, read_timeout_seconds=60) as opened:
            yield opened
