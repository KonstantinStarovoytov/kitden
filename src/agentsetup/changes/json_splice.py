"""Minimal-span edits for strict JSON files (research R7, FR-020, FR-021).

Only the text of the edited member changes; every other byte stays as it was. Adding a member
and then deleting it gives back the original bytes. Files that are not a strict JSON object (for
example JSON with comments) are refused (FR-042).
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any


class _Absent:
    def __repr__(self) -> str:
        return "ABSENT"


ABSENT: Any = _Absent()
"""Marks a missing value: get_value returns it, and edits use it for 'not there'."""


class UnrecognizedFormatError(ValueError):
    """The file is not in a format we can edit safely."""


@dataclass
class _Member:
    key: str
    key_start: int
    key_end: int
    value: "_Node"


@dataclass
class _Node:
    start: int
    end: int
    members: list[_Member] | None = None  # None for anything that is not an object
    children: list["_Node"] = field(default_factory=list)


class _Parser:
    """Finds the text span of every value. The text was already checked by json.loads."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def _skip(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t\r\n":
            self.pos += 1

    def _string(self) -> str:
        start = self.pos
        self.pos += 1
        while self.text[self.pos] != '"':
            self.pos += 2 if self.text[self.pos] == "\\" else 1
        self.pos += 1
        return json.loads(self.text[start : self.pos])

    def value(self) -> _Node:
        self._skip()
        start = self.pos
        char = self.text[self.pos]
        if char == "{":
            node = _Node(start, start, members=[])
            self.pos += 1
            self._skip()
            while self.text[self.pos] != "}":
                key_start = self.pos
                key = self._string()
                key_end = self.pos
                self._skip()
                self.pos += 1  # ':'
                node.members.append(_Member(key, key_start, key_end, self.value()))
                self._skip()
                if self.text[self.pos] == ",":
                    self.pos += 1
                    self._skip()
            self.pos += 1
        elif char == "[":
            node = _Node(start, start)
            self.pos += 1
            self._skip()
            while self.text[self.pos] != "]":
                node.children.append(self.value())
                self._skip()
                if self.text[self.pos] == ",":
                    self.pos += 1
            self.pos += 1
        elif char == '"':
            node = _Node(start, start)
            self._string()
        else:
            node = _Node(start, start)
            while self.pos < len(self.text) and self.text[self.pos] not in ",]} \t\r\n":
                self.pos += 1
        node.end = self.pos
        return node


def _load(text: str) -> tuple[dict, _Node]:
    try:
        data = json.loads(text)
    except ValueError as error:
        raise UnrecognizedFormatError(f"not strict JSON: {error}") from None
    if not isinstance(data, dict):
        raise UnrecognizedFormatError("the top level is not a JSON object")
    return data, _Parser(text).value()


def _member(node: _Node, key: str) -> _Member | None:
    # With duplicate keys JSON readers use the last one, so we do too.
    found = [m for m in node.members or [] if m.key == key]
    return found[-1] if found else None


def _line_indent(text: str, pos: int) -> str:
    line_start = text.rfind("\n", 0, pos) + 1
    return re.match(r"[ \t]*", text[line_start:]).group(0)


def _indent_unit(text: str) -> str:
    match = re.search(r"\n([ \t]+)\S", text)
    return match.group(1) if match else "  "


def _key_separator(text: str, root: _Node) -> str:
    def first(node: _Node) -> _Member | None:
        if node.members:
            return node.members[0]
        for member in node.members or []:
            found = first(member.value)
            if found:
                return found
        return None

    member = first(root)
    return text[member.key_end : member.value.start] if member else ": "


def _render(value: Any, unit: str, base: str, sep: str, multiline: bool) -> str:
    if not multiline:
        return json.dumps(value, ensure_ascii=False, separators=(", ", sep))
    text = json.dumps(value, ensure_ascii=False, indent=unit, separators=(",", sep))
    return text.replace("\n", "\n" + base)


def _nested(path: tuple[str, ...], value: Any) -> Any:
    for key in reversed(path):
        value = {key: value}
    return value


def _insert(text: str, node: _Node, key: str, value: Any, sep: str) -> str:
    multiline = "\n" in text
    unit = _indent_unit(text)
    rendered_key = json.dumps(key, ensure_ascii=False)
    if not node.members:
        if not multiline:
            body = "{" + rendered_key + sep + _render(value, unit, "", sep, False) + "}"
            return text[: node.start] + body + text[node.end :]
        outer = _line_indent(text, node.start)
        inner = outer + unit
        body = (
            "{\n"
            + inner
            + rendered_key
            + sep
            + _render(value, unit, inner, sep, True)
            + "\n"
            + outer
            + "}"
        )
        return text[: node.start] + body + text[node.end :]

    last = node.members[-1]
    if len(node.members) > 1:
        between = text[node.members[-2].value.end : last.key_start]
    else:
        between = "," + text[node.start + 1 : last.key_start]
    base = between[between.rfind("\n") + 1 :] if "\n" in between else ""
    addition = between + rendered_key + sep + _render(value, unit, base, sep, multiline)
    return text[: last.value.end] + addition + text[last.value.end :]


def get_value(text: str, path: tuple[str, ...]) -> Any:
    """The value at `path`, or ABSENT."""
    if not text.strip():
        return ABSENT
    current: Any = _load(text)[0]
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return ABSENT
        current = current[key]
    return current


def set_value(text: str, path: tuple[str, ...], value: Any) -> str:
    """Add or replace the member at `path`, creating missing parent objects."""
    if not text.strip():
        return json.dumps(_nested(path, value), ensure_ascii=False, indent=2) + "\n"
    if get_value(text, path) == value:
        return text
    _, node = _load(text)
    sep = _key_separator(text, node)
    for depth, key in enumerate(path):
        if node.members is None:
            raise UnrecognizedFormatError(f"{'.'.join(path[:depth])} is not an object")
        member = _member(node, key)
        if member is None:
            return _insert(text, node, key, _nested(path[depth + 1 :], value), sep)
        if depth == len(path) - 1:
            target = member.value
            base = _line_indent(text, member.key_start)
            rendered = _render(value, _indent_unit(text), base, sep, "\n" in text)
            return text[: target.start] + rendered + text[target.end :]
        node = member.value
    raise AssertionError("unreachable")


def delete_value(text: str, path: tuple[str, ...]) -> str:
    """Remove the member at `path`. A missing member leaves the text unchanged."""
    if get_value(text, path) is ABSENT:
        return text
    _, node = _load(text)
    for key in path[:-1]:
        node = _member(node, key).value
    members = node.members
    index = max(i for i, m in enumerate(members) if m.key == path[-1])
    if len(members) == 1:
        return text[: node.start + 1] + text[node.end - 1 :]
    if index < len(members) - 1:
        return text[: members[index].key_start] + text[members[index + 1].key_start :]
    return text[: members[index - 1].value.end] + text[members[index].value.end :]
