"""Where the installed `kitden` command lives (research R9 of feature 001).

Kept apart from the MCP server so the page does not load the MCP SDK just to find this path.
"""

import shutil
import sys
from pathlib import Path

from kitden.update.install import detect


def installed_command() -> str | None:
    """Absolute path of the `kitden` command, for client configs. GUI clients need it. For a uv
    tool or Homebrew install, its stable launcher: Homebrew's own Python sits in a versioned
    folder that an upgrade removes."""
    install = detect()
    if install is not None and install.launcher.is_file():
        return str(install.launcher)
    beside_python = Path(sys.executable).parent / "kitden"
    if beside_python.is_file():
        return str(beside_python)
    found = shutil.which("kitden")
    return str(Path(found).absolute()) if found else None
