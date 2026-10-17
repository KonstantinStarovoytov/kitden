"""Run a client's own command (FR-021), for example `claude mcp add-json`. Output is redacted."""

import os
import shutil
import subprocess  # noqa: S404 - runs fixed client commands without a shell
from dataclasses import dataclass
from pathlib import Path

from agentsetup.redact import redact_text

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
    return None


class CommandRunner:
    """Runs commands with HOME set to the home folder the page shows."""

    def __init__(self, home: Path, timeout: float = TIMEOUT_SECONDS) -> None:
        self.home = Path(home)
        self.timeout = timeout

    def __call__(self, command: list[str], cwd: str | None) -> CommandResult:
        binary = find_command(command[0], self.home)
        if binary is None:
            return CommandResult(127, f"{command[0]} was not found")
        env = {**os.environ, "HOME": str(self.home)}
        try:
            done = subprocess.run(  # noqa: S603 - fixed client command, no shell
                [binary, *command[1:]],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return CommandResult(1, redact_text(str(error)))
        return CommandResult(done.returncode, redact_text((done.stdout + done.stderr).strip()))
