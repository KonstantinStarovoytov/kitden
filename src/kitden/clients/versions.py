"""Supported client versions and how to read them (research R11)."""

import os
import re
import shutil
from collections.abc import Callable, Iterable

# Lowest version each adapter is tested with.
MINIMUM_VERSIONS: dict[str, str] = {
    "claude_code": "2.1.283",
    "claude_desktop_code_tab": "2.1.283",
    "codex": "0.159.2",
    "cursor": "3.21.16",
}

# Executable on PATH first, then known install locations.
_COMMANDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "claude_code": ("claude", ()),
    "codex": ("codex", ("/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",)),
    "cursor": ("cursor", ("/Applications/Cursor.app/Contents/Resources/app/bin/cursor",)),
}

_VERSION = re.compile(r"\b(\d+(?:\.\d+)+)\b")


def parse_version(client: str, output: str) -> str | None:
    """Return the first dotted version number in a client's version output."""
    match = _VERSION.search(output)
    return match.group(1) if match else None


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def is_supported(client: str, version: str | None) -> bool:
    if version is None or client not in MINIMUM_VERSIONS:
        return False
    return _key(version) >= _key(MINIMUM_VERSIONS[client])


def highest_version(names: Iterable[str]) -> str | None:
    """Pick the highest version among folder names such as '2.1.299'."""
    versions = [name for name in names if re.fullmatch(r"\d+(?:\.\d+)+", name)]
    return max(versions, key=_key) if versions else None


def version_command(
    client: str,
    which: Callable[[str], str | None] = shutil.which,
    exists: Callable[[str], bool] = os.path.exists,
) -> list[str] | None:
    """Command that prints the client's version, or None if the client is not found."""
    if client not in _COMMANDS:
        return None
    name, fallbacks = _COMMANDS[client]
    path = which(name) or next((p for p in fallbacks if exists(p)), None)
    return [path, "--version"] if path else None
