"""Rescan when client setup files change (FR-008, research R8).

Watches client folders, reacts only to setup files, waits for changes to settle (debounce),
and ignores files the tool itself just wrote.
"""

import asyncio
import hashlib
import inspect
import os
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from watchfiles import awatch

SETUP_FILES = {
    ".claude.json",
    ".mcp.json",
    "mcp.json",
    "config.toml",
    "settings.json",
    "settings.local.json",
    "hooks.json",
    "installed_plugins.json",
    "known_marketplaces.json",
    "claude_desktop_config.json",
    "plugin.json",
    "marketplace.json",
    "SKILL.md",
}
NOISY_FOLDERS = {"sessions", "archived_sessions", "logs", "log", "shell_snapshots"}
EXPECT_SECONDS = 10.0  # how long a planned own write is remembered


def is_relevant(path: str) -> bool:
    parts = Path(path).parts
    return parts[-1] in SETUP_FILES and not NOISY_FOLDERS.intersection(parts)


def _sha(path: str) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


class Watcher:
    def __init__(
        self,
        folders: Iterable[Path],
        on_change: Callable[[], object],
        debounce_ms: int = 800,
        flat_folders: Iterable[Path] = (),
    ) -> None:
        """`folders` are watched with subfolders; `flat_folders` (like home) without."""
        self.folders = [p for p in folders if Path(p).is_dir()]
        self.flat_folders = [p for p in flat_folders if Path(p).is_dir()]
        self.on_change = on_change
        self.debounce_ms = debounce_ms
        self._stop = asyncio.Event()
        self._expected: dict[str, tuple[str, float]] = {}

    def expect(self, path: Path, sha256: str) -> None:
        """The tool is about to write `path` with this content: do not treat it as a change."""
        self._expected[os.path.realpath(path)] = (sha256, time.monotonic() + EXPECT_SECONDS)

    def stop(self) -> None:
        self._stop.set()

    def _is_own(self, path: str) -> bool:
        # Events can arrive late, so a mismatch does not cancel the expectation; it expires.
        real = os.path.realpath(path)
        sha, until = self._expected.get(real, (None, 0.0))
        if time.monotonic() > until:
            self._expected.pop(real, None)
            return False
        return _sha(real) == sha

    async def _loop(self, folders: list[Path], recursive: bool) -> None:
        if not folders:
            return
        async for changes in awatch(
            *folders,
            watch_filter=lambda _c, p: is_relevant(p),
            debounce=self.debounce_ms,
            stop_event=self._stop,
            recursive=recursive,
        ):
            if any(not self._is_own(path) for _change, path in changes):
                result = self.on_change()
                if inspect.isawaitable(result):
                    await result

    async def run(self) -> None:
        await asyncio.gather(self._loop(self.folders, True), self._loop(self.flat_folders, False))
