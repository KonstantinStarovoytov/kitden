"""Where the installed `kitden` command lives (research R9 of feature 001).

Kept apart from the MCP server so the page does not load the MCP SDK just to find this path.
"""

import shutil
import sys
from pathlib import Path


def installed_command() -> str | None:
    """Absolute path of the `kitden` command, for client configs. GUI clients need it."""
    beside_python = Path(sys.executable).parent / "kitden"
    if beside_python.is_file():
        return str(beside_python)
    found = shutil.which("kitden")
    return str(Path(found).absolute()) if found else None
