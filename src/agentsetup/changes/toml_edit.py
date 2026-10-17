"""Format-preserving TOML edits with tomlkit (research R7, FR-020).

Comments, order and spacing of everything we do not edit stay as they were. Used for Codex
`config.toml`, instead of `codex mcp add`, which drops comments (plan, Complexity Tracking).
"""

from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

from agentsetup.changes.json_splice import ABSENT, UnrecognizedFormatError


def _load(text: str) -> tomlkit.TOMLDocument:
    try:
        return tomlkit.parse(text)
    except TOMLKitError as error:
        raise UnrecognizedFormatError(f"not valid TOML: {error}") from None


def _plain(value: Any) -> Any:
    return value.unwrap() if hasattr(value, "unwrap") else value


def get_value(text: str, path: tuple[str, ...]) -> Any:
    """The value at `path` as plain Python, or ABSENT."""
    current: Any = _load(text)
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return ABSENT
        current = current[key]
    return _plain(current)


def set_value(text: str, path: tuple[str, ...], value: Any) -> str:
    """Add or replace the value at `path`, creating missing parent tables."""
    if get_value(text, path) == value:
        return text
    doc = _load(text)
    parent: Any = doc
    for key in path[:-1]:
        if key not in parent:
            parent[key] = tomlkit.table(is_super_table=True)
        parent = parent[key]
        if not isinstance(parent, dict):
            raise UnrecognizedFormatError(f"{key} is not a table")
    parent[path[-1]] = value
    return tomlkit.dumps(doc)


def delete_value(text: str, path: tuple[str, ...]) -> str:
    """Remove the value at `path`; a parent table that only grouped it goes too."""
    if get_value(text, path) is ABSENT:
        return text
    doc = _load(text)
    parents: list[Any] = [doc]
    for key in path[:-1]:
        parents.append(parents[-1][key])
    del parents[-1][path[-1]]
    for depth in range(len(path) - 1, 0, -1):
        table = parents[depth]
        if len(table) == 0 and getattr(table, "is_super_table", lambda: False)():
            del parents[depth - 1][path[depth - 1]]
    result = tomlkit.dumps(doc)
    # tomlkit keeps the blank line that separated a removed last table; do not leave it behind.
    if result.endswith("\n\n") and not text.endswith("\n\n"):
        result = result.rstrip("\n") + "\n"
    return result
