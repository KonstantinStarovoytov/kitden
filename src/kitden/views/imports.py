"""Claude Code's `@path` imports in a CLAUDE.md file, and the imports of those files.

Kitden only reads these files. It never reads a file outside the home folder or anything that
is not a plain file, reads at most `READ_LIMIT` characters of each, and reads each file once.

checked 2026-10-26 (code.claude.com/docs/en/memory, "Import additional files"):
- CLAUDE.md files import other files with `@path/to/import`. Relative and absolute paths both
  work; a relative path is relative to the file that holds the import. `@~/...` is in the home
  folder (the docs' own example).
- Imported files may import others, up to four hops.
- Markdown code spans and fenced code blocks are skipped.
- A backslash before a space keeps the space in the path; a path in quotes is not imported.
- In a project's file, an import outside the working folder is external: Claude Code asks once
  per project before it loads it. In the user's own files (`~/.claude/CLAUDE.md`) it does not ask.
The docs do not say how a loop ends; Kitden stops at the first file it has already read.
"""

import os
import re
from pathlib import Path

from kitden.redact import redact_line

MAX_HOPS = 4
READ_LIMIT = 256_000

# A fence opens with three or more backticks or tildes (at most three spaces in), and closes with
# at least as many of the same mark.
_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
# A code span: a run of backticks, then text, then a run of the same length.
_SPAN = re.compile(r"(?<!`)(`+)(?!`).+?(?<!`)\1(?!`)")
# `@` at the start of a line or after a space; the path runs to the next space not after `\`.
_IMPORT = re.compile(r"(?:^|(?<=\s))@((?:\\ |\S)+)")


def read_text(path: Path) -> str:
    """At most `READ_LIMIT` characters of a file; empty when it cannot be read."""
    try:
        with path.open(encoding="utf-8-sig", errors="replace") as file:
            return file.read(READ_LIMIT)
    except OSError:
        return ""


def _written(text: str) -> list[str]:
    """Each import as written, in order, outside code spans and fenced blocks."""
    found = []
    fence: str | None = None
    for line in text.splitlines():
        mark = _FENCE.match(line)
        if fence is not None:
            closes = mark and mark.group(1)[0] == fence[0] and len(mark.group(1)) >= len(fence)
            if closes and not line[mark.end() :].strip():
                fence = None
            continue
        if mark:
            fence = mark.group(1)
            continue
        for written in _IMPORT.findall(_SPAN.sub(" ", line)):
            if not written.startswith(("'", '"')):
                found.append(written.replace("\\ ", " "))
    return found


def _target(written: str, file: Path, home: Path) -> Path:
    if written.startswith("~/"):
        return Path(os.path.realpath(home / written[2:]))
    return Path(os.path.realpath(file.parent / written))


def _name(target: Path, root: Path | None, home: Path) -> str:
    """The import's name on the page: the path in the project, `~/...` in the home folder, else
    only the file's name, so no full path leaves `technical`."""
    if root is not None and target.is_relative_to(root):
        name = str(target.relative_to(root))
    elif target.is_relative_to(home):
        name = "~/" + str(target.relative_to(home))
    else:
        name = target.name
    return redact_line(name)


def imports(path: Path, root: Path | None, home: Path) -> list[dict]:
    """The files a CLAUDE.md imports, nearest first: `name`, `target` (the full path), `depth`
    (1 for the file's own imports), `outside` (outside the project `root`; with no root, a user
    file, nothing is), `missing` (not a plain file) and `via` (the file that imports it). Each
    target is listed once; a file outside the home folder is named but never read."""
    home = Path(os.path.realpath(home))
    root = Path(os.path.realpath(root)) if root is not None else None
    start = Path(os.path.realpath(path))
    seen = {start}
    found: list[dict] = []
    queue = [(start, 1)]
    while queue:
        file, depth = queue.pop(0)
        for written in _written(read_text(file)):
            target = _target(written, file, home)
            if target in seen:
                continue  # a loop, or a file already listed: stop here
            seen.add(target)
            missing = not target.is_file()
            found.append(
                {
                    "name": _name(target, root, home),
                    "target": str(target),
                    "depth": depth,
                    "outside": root is not None and not target.is_relative_to(root),
                    "missing": missing,
                    "via": str(file),
                }
            )
            if depth < MAX_HOPS and not missing and target.is_relative_to(home):
                queue.append((target, depth + 1))
    return found
