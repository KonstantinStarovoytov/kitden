"""Run a client's own command (FR-021), for example `claude mcp add-json`. Output is redacted."""

import contextlib
import os
import shutil
import signal
import subprocess  # runs fixed client commands without a shell
from dataclasses import dataclass
from pathlib import Path

from kitden.clients.versions import app_commands
from kitden.redact import redact_text

TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: str


def find_command(name: str, home: Path) -> str | None:
    """The client binary on PATH, or in the places its installer uses."""
    found = shutil.which(name)
    if found:
        return found
    for candidate in (home / ".local/bin" / name, home / ".claude/local" / name):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    for bundled in app_commands(name):
        if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
            return bundled
    return None


class CommandRunner:
    """Runs commands with HOME set to the home folder the page shows."""

    def __init__(self, home: Path) -> None:
        self.home = Path(home)

    def __call__(self, command: list[str], cwd: str | None) -> CommandResult:
        binary = find_command(command[0], self.home)
        if binary is None:
            return CommandResult(127, f"{command[0]} was not found")
        env = {**os.environ, "HOME": str(self.home)}
        # No stdin, so a question never waits on the page's input; a group of its own, so a
        # timeout stops the helpers it started too and nothing keeps the pipes open.
        try:
            process = subprocess.Popen(  # noqa: S603 - fixed client command, no shell
                [binary, *command[1:]],
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
        except OSError as error:
            return CommandResult(1, redact_text(str(error)))
        try:
            out, err = process.communicate(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            _stop_group(process)
            return CommandResult(1, f"{command[0]} did not finish in {TIMEOUT_SECONDS:g} seconds")
        return CommandResult(process.returncode, redact_text((out + err).strip()))


def _stop_group(process: subprocess.Popen) -> None:
    """Stop the command and everything it started, then collect it. A helper that left the
    group can still hold the pipes: after a few seconds they are closed instead."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(process.pid, signal.SIGKILL)
    process.kill()
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        for pipe in (process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()
        process.wait()
