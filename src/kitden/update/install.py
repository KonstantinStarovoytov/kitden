"""How Kitden was installed. Only `uv tool install` and Homebrew can be updated from the page."""

import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# What to tell the user to run when Kitden cannot update itself. None: not installed by uv or brew.
MANUAL_COMMAND: dict[str | None, str] = {
    "uv": "uv tool upgrade kitden",
    "brew": "brew upgrade kitden",
    None: "uv tool upgrade kitden",
}

_VERSION = re.compile(r"^kitden (\S+)$")


@dataclass(frozen=True)
class Install:
    method: Literal["uv", "brew"]
    launcher: Path  # the program to run after an upgrade
    command: tuple[str, ...]  # the upgrade command


def detect(
    prefix: Path | None = None, which: Callable[[str], str | None] = shutil.which
) -> Install | None:
    """The install that owns this Python, or None (uvx, pip, source checkout)."""
    prefix = Path(sys.prefix) if prefix is None else prefix
    if (prefix / "uv-receipt.toml").exists():
        uv = which("uv")
        if uv is None:
            return None
        return Install("uv", prefix / "bin" / "kitden", (uv, "tool", "upgrade", "kitden"))
    parts = prefix.parts
    for i in range(len(parts) - 1):
        if parts[i] == "Cellar" and parts[i + 1] == "kitden":
            brew = Path(*parts[:i])
            return Install(
                "brew",
                brew / "opt" / "kitden" / "bin" / "kitden",
                (str(brew / "bin" / "brew"), "upgrade", "kitden"),
            )
    return None


def installed_version(install: Install, run=subprocess.run) -> str | None:
    """The version of the program on disk now, which differs from this process after an upgrade."""
    try:
        done = run(
            [str(install.launcher), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    found = _VERSION.match(done.stdout.strip()) if done.returncode == 0 else None
    return found.group(1) if found else None
