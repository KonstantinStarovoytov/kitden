"""Format-preserving TOML edits with tomlkit (research R7, FR-020).

Comments, order and spacing of everything we do not edit stay as they were. Used for Codex
`config.toml`, instead of `codex mcp add`, which drops comments (plan, Complexity Tracking).
"""

from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError
from tomlkit.items import AoT

from kitden.changes.json_splice import ABSENT, UnrecognizedFormatError


def _load(text: str) -> tomlkit.TOMLDocument:
    try:
        return tomlkit.parse(text)
    except TOMLKitError as error:
        raise UnrecognizedFormatError(f"not valid TOML: {error}") from None


def _plain(value: Any) -> Any:
    return value.unwrap() if hasattr(value, "unwrap") else value


# A key segment "path=<value>" picks, in a list of tables, the table whose `path` is <value>:
# Codex keeps one `[[skills.config]]` table per skill. Each table is then its own entry, so two
# changes to two skills do not edit the same setting, and the other tables keep their comments.
PICK = "path="


def pick(path: str) -> str:
    """The key segment of the table whose `path` is `path`, in a list of tables."""
    return PICK + path


def _find(tables: Any, segment: str) -> int | None:
    """The index in `tables` (a list of tables) of the one the segment picks, or None."""
    if not segment.startswith(PICK) or not isinstance(tables, list):
        return None
    want = segment[len(PICK) :]
    found = [i for i, t in enumerate(tables) if isinstance(t, dict) and t.get("path") == want]
    return found[-1] if found else None


def nested(path: tuple[str, ...], value: Any) -> Any:
    """`value` inside its parents, as the file has it: a picked table is one table of a list."""
    for key in reversed(path):
        value = [value] if key.startswith(PICK) else {key: value}
    return value


def _trim(result: str, text: str) -> str:
    # tomlkit keeps the blank line that separated a last table; do not leave one more behind.
    if result.endswith("\n\n") and not text.endswith("\n\n"):
        return result.rstrip("\n") + "\n"
    return result


def get_value(text: str, path: tuple[str, ...]) -> Any:
    """The value at `path` as plain Python, or ABSENT."""
    current: Any = _load(text)
    for key in path:
        if isinstance(current, list):
            index = _find(current, key)
            if index is None:
                return ABSENT
            current = current[index]
        elif not isinstance(current, dict) or key not in current:
            return ABSENT
        else:
            current = current[key]
    return _plain(current)


def _set_picked(doc: Any, path: tuple[str, ...], value: Any) -> None:
    """Change the picked table in place, or add it after the others with a blank line before."""
    if not isinstance(value, dict) or PICK + str(value.get("path")) != path[-1]:
        raise ValueError("a picked table must keep its path")
    parent: Any = doc
    for key in path[:-2]:
        if key not in parent:
            parent[key] = tomlkit.table(is_super_table=True)
        parent = parent[key]
        if not isinstance(parent, dict):
            raise UnrecognizedFormatError(f"{key} is not a table")
    tables = parent.get(path[-2])
    if tables is None:
        tables = parent[path[-2]] = tomlkit.aot()
    if not isinstance(tables, AoT):
        raise UnrecognizedFormatError(f"{path[-2]} is not a list of tables")
    index = _find(tables, path[-1])
    if index is not None:
        table = tables[index]
        for key in [k for k in table if k not in value]:
            del table[key]
        for key, item in value.items():
            if table.get(key) != item:
                table[key] = item
        return
    if len(tables) and not tables[-1].as_string().endswith("\n\n"):
        tables[-1].add(tomlkit.nl())
    table = tomlkit.table()
    table.update(value)
    table.add(tomlkit.nl())
    tables.append(table)


def set_value(text: str, path: tuple[str, ...], value: Any) -> str:
    """Add or replace the value at `path`, creating missing parent tables."""
    if get_value(text, path) == value:
        return text
    doc = _load(text)
    if path[-1].startswith(PICK):
        _set_picked(doc, path, value)
        return _trim(tomlkit.dumps(doc), text)
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
    """Remove the value at `path`; a parent table that only grouped it goes too, and so does a
    list of tables left empty."""
    if get_value(text, path) is ABSENT:
        return text
    doc = _load(text)
    parents: list[Any] = [doc]
    for key in path[:-1]:
        parents.append(parents[-1][key])
    holder = parents[-1]
    index = _find(holder, path[-1])
    del holder[path[-1] if index is None else index]
    for depth in range(len(path) - 1, 0, -1):
        table = parents[depth]
        empty_list = isinstance(table, AoT) and len(table) == 0
        if empty_list or (len(table) == 0 and getattr(table, "is_super_table", lambda: False)()):
            del parents[depth - 1][path[depth - 1]]
    return _trim(tomlkit.dumps(doc), text)
