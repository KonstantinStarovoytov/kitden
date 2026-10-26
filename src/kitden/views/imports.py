"""Claude Code's `@path` imports in a CLAUDE.md file, and the imports of those files.

Kitden only reads these files. It reads a file only inside the home folder or the picked
project, and only a plain file; it reads at most `READ_LIMIT` characters of each, and each file
once.

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


def read_text(path: Path) -> tuple[str, bool]:
    """At most `READ_LIMIT` characters of a file, and whether the file goes on past them; empty
    when it cannot be read."""
    try:
        with path.open(encoding="utf-8-sig", errors="replace") as file:
            text = file.read(READ_LIMIT + 1)
    except OSError:
        return "", False
    return text[:READ_LIMIT], len(text) > READ_LIMIT


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
            # A path in quotes is no import, and no path holds a NUL character.
            if not written.startswith(("'", '"')) and "\x00" not in written:
                found.append(written.replace("\\ ", " "))
    return found


def _target(written: str, file: Path, home: Path) -> Path | None:
    """The full path an import names; None when it names no path the system can take."""
    try:
        if written.startswith("~/"):
            return Path(os.path.realpath(home / written[2:]))
        return Path(os.path.realpath(file.parent / written))
    except (OSError, ValueError):
        return None


def _name(written: str) -> str:
    """The import's name on the page: what the file says after `@`, secrets hidden. A full path
    shows only its file's name, so no full path leaves `technical`."""
    return redact_line(Path(written).name if os.path.isabs(written) else written)


def imports(path: Path, root: Path | None, home: Path, text: str | None = None) -> list[dict]:
    """The files a CLAUDE.md imports, nearest first: `name`, `target` (the full path), `depth`
    (1 for the file's own imports), `outside` (outside the project `root`; with no root, a user
    file, nothing is), `missing` (not a plain file) and `via` (the file that imports it). `text`
    is the file's own text when the caller has read it already. Each target is listed once; a
    file outside both the home folder and `root` is named but never read."""
    home = Path(os.path.realpath(home))
    root = Path(os.path.realpath(root)) if root is not None else None
    start = Path(os.path.realpath(path))
    seen = {start}
    found: list[dict] = []
    queue = [(start, 1)]
    while queue:
        file, depth = queue.pop(0)
        own = text if file == start and text is not None else read_text(file)[0]
        for written in _written(own):
            target = _target(written, file, home)
            if target is None or target in seen:
                continue  # no path, a loop, or a file already listed: stop here
            seen.add(target)
            missing = not target.is_file()
            found.append(
                {
                    "name": _name(written),
                    "target": str(target),
                    "depth": depth,
                    "outside": root is not None and not target.is_relative_to(root),
                    "missing": missing,
                    "via": str(file),
                }
            )
            inside = target.is_relative_to(home) or bool(root and target.is_relative_to(root))
            if depth < MAX_HOPS and not missing and inside:
                queue.append((target, depth + 1))
    return found
