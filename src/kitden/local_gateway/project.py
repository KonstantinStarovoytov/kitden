"""Finding the project of a client session.

The gateway decides once, at start. The first place that names a folder wins; the folder is
then matched to the projects Kitden knows. No match means no project (the global set).
"""

import os
from collections.abc import Iterator, Mapping
from pathlib import Path
from urllib.parse import unquote, urlparse


def main_checkout(path: Path) -> Path:
    """A git worktree maps to its main checkout; any other folder to itself.

    A worktree's `.git` is a file: `gitdir: <main>/.git/worktrees/<name>`. Read it; no git command.
    """
    try:
        text = (path / ".git").read_text()
    except (OSError, ValueError):
        return path
    if not text.startswith("gitdir:"):
        return path
    # A relative gitdir is relative to the worktree; joining an absolute one keeps it as it is.
    gitdir = Path(os.path.normpath(path / text.removeprefix("gitdir:").strip()))
    if gitdir.parent.name == "worktrees" and gitdir.parent.parent.name == ".git":
        return gitdir.parent.parent.parent
    return path


def _file_uri_path(uri: str) -> str | None:
    parsed = urlparse(uri)
    return unquote(parsed.path) if parsed.scheme == "file" else None


def _candidates(
    env: Mapping[str, str], roots: list[str], cwd: Path, home: Path
) -> Iterator[str | None]:
    # Facts below were checked on 2026-10-21.
    # Claude Code passes CLAUDE_PROJECT_DIR to stdio servers (in a Desktop worktree session it is
    # the main checkout).
    yield env.get("CLAUDE_PROJECT_DIR")
    # Claude Code answers MCP roots with file:// URIs; Cursor IDE with the window's folders.
    yield _file_uri_path(roots[0]) if roots else None
    # Cursor IDE sets WORKSPACE_FOLDER_PATHS (undocumented), comma-joined.
    yield (env.get("WORKSPACE_FOLDER_PATHS") or "").split(",")[0].strip()
    # Codex sends no roots and clears the env: it starts the server in the session folder (a
    # project, a worktree or a per-chat folder). Cursor starts user-level servers in the home
    # folder, so the home folder says nothing.
    yield None if cwd in (home, Path("/")) else str(cwd)


def find_project(
    env: Mapping[str, str], roots: list[str], cwd: Path, home: Path, known: list[str]
) -> str | None:
    """The known project (a path from `known`) the session works in, or None.

    The first candidate wins. It is mapped to its main checkout, and the known project that is
    that folder or contains it (the longest one) is the answer.
    """
    start = next((c for c in _candidates(env, roots, cwd, home) if c), None)
    if start is None:
        return None
    folder = main_checkout(Path(start))
    matches = [k for k in known if Path(k) == folder or Path(k) in folder.parents]
    return max(matches, key=lambda k: len(Path(k).parts), default=None)
