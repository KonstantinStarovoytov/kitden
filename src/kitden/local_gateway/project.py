"""Finding the folder of a client session and the known projects whose rules apply there.

The gateway decides once, at start. The first place that names a folder wins: local servers
start there. The folder is then matched to the projects Kitden knows, which gives the chain of
projects whose rules apply, deepest first. An empty chain means the global set.
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


def _real(path: str | Path) -> Path:
    return Path(os.path.realpath(path))


def _worktree_main(folder: Path, stops: tuple[Path, ...]) -> Path:
    """The main checkout when `folder` is in a git worktree, otherwise `folder` itself.

    Walks up to the first folder that holds a `.git`, never into the home folder or `/`.
    """
    for parent in (folder, *folder.parents):
        if parent in stops:
            break
        if (parent / ".git").exists():
            main = main_checkout(parent)
            return folder if main == parent else main
    return folder


def _file_uri_path(uri: str) -> str | None:
    parsed = urlparse(uri)
    return unquote(parsed.path) if parsed.scheme == "file" else None


def _candidates(
    env: Mapping[str, str], roots: list[str], cwd: Path, stops: tuple[Path, ...]
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
    yield None if _real(cwd) in stops else str(cwd)


def session_folder(env: Mapping[str, str], roots: list[str], cwd: Path, home: Path) -> str | None:
    """The first folder the session names, as it names it, or None when none does.

    No worktree mapping and no matching: a local server starts in this folder.
    """
    stops = (_real(home), Path("/"))
    return next((c for c in _candidates(env, roots, cwd, stops) if c), None)


def project_chain(folder: str | None, home: Path, known: list[str]) -> list[str]:
    """The known projects (paths from `known`) whose rules apply in `folder`, deepest first.

    First the known projects that are the folder or contain it, then, when the folder is in a
    git worktree, the ones that are its main checkout or contain it; each one once. Paths are
    compared by their real path; the answer has the `known` strings as given. The home folder
    and `/` match only themselves: they must not claim the folders under them (a Codex chat
    folder is one). The gateway and the page both use this, so they agree.
    """
    if folder is None:
        return []
    stops = (_real(home), Path("/"))
    real = {k: _real(k) for k in known}

    def holding(place: Path) -> list[str]:
        found = [
            k for k, r in real.items() if r == place or (r not in stops and r in place.parents)
        ]
        return sorted(found, key=lambda k: len(real[k].parts), reverse=True)

    start = _real(folder)
    chain = holding(start)
    main = _real(_worktree_main(start, stops))
    if main != start:
        chain += [k for k in holding(main) if k not in chain]
    return chain
