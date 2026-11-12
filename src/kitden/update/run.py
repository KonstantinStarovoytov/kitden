"""Run the installer and report its real steps. A step is reported only when the installer
prints the line that proves it."""

import json
import os
import subprocess
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import anyio
import anyio.to_thread
from anyio.streams.text import TextReceiveStream

from kitden.gateways import private_data_dir
from kitden.update.install import Install, installed_version

STEPS = ("Downloading…", "Installing…", "Restarting Kitden…", "Reloading…")
MARKER = "updated.json"
TAIL_LINES = 20

# The installer lines that end a step. Checked 2026-11-11:
# - uv 0.10.10: ran a real `uv tool upgrade kitden` (0.7.1 -> 0.7.2) with no terminal, in a
#   throwaway UV_TOOL_DIR. It printed "Updated kitden v0.7.1 -> v0.7.2", then " - kitden==0.7.1" and
#   " + kitden==0.7.2", then "Installed 1 executable: kitden". "Resolved" and "Prepared" are only
#   printed by `uv tool install`, never by `upgrade`. uv prints nothing while it downloads, so no
#   line proves step 0 for uv; the page shows step 0 from the start.
# - Homebrew 7.0.9: not run. Read from its source (Library/Homebrew): download_queue.rb prints the
#   heading "==> Fetching downloads for: kitden" (or "==> Downloading bottle manifests"), and
#   formula_installer.rb prints "==> Pouring <bottle file>". Older Homebrew printed
#   "==> Fetching kitden" and "==> Downloading <url>", which the same prefixes match.
# - Homebrew without a bottle (the tap has them only for arm64 Tahoe and x86_64 Linux) builds
#   from source and prints no "Pouring". Checked 2026-11-11 from brew source: after the
#   downloads, formula_installer.rb prints "==> Installing <tap>/kitden" (only when it installed
#   dependencies first) and "==> Installing <tap>/kitden dependency: <name>"; then build.rb runs
#   the formula's install, where language/python.rb (virtualenv_install_with_resources) runs
#   "python3.13 -m venv ..." and "python3.13 -m pip ...", which Formula#system echoes as
#   "==> python3.13 ...". The tap's formula names "python@3.13", so the command has no path.
# - Homebrew 7.0.13, seen 2026-11-12 with a real `brew upgrade` from a local tap that builds from
#   source: "==> Fetching downloads for: <tap>/kitden", then "==> Upgrading <tap>/kitden" while
#   it builds, with no "Installing" or "Pouring". A plain `brew upgrade` heads its list with
#   "==> Upgrading 1 outdated package", which comes before the downloads and proves nothing.
_STEP_LINES: dict[str, tuple[tuple[int, str], ...]] = {
    "uv": ((1, "Updated "),),
    "brew": (
        (0, "==> Fetching "),
        (0, "==> Downloading "),
        (1, "==> Pouring "),
        (1, "==> Installing "),
        (1, "==> python"),
        (1, "==> Upgrading "),
    ),
}
# Homebrew keeps the old keg, so a gateway that still runs the old version keeps its files
# until it moves to the new one.
_ENV = {"brew": {"HOMEBREW_NO_INSTALL_CLEANUP": "1"}}


def step_for(method: str, line: str) -> int | None:
    """The step this installer line ends, or None when it proves nothing."""
    if "outdated package" in line:
        return None
    for step, prefix in _STEP_LINES.get(method, ()):
        if line.startswith(prefix):
            return step
    return None


@dataclass
class Outcome:
    state: Literal["updated", "same", "failed"]
    version: str | None  # the version on disk after the run
    tail: list[str]  # the installer's last lines, to show why it failed


async def _lines(stream):
    """Whole lines from the installer, split at \\n or \\r (progress bars use \\r)."""
    pending = ""
    async for chunk in TextReceiveStream(stream, errors="replace"):
        *done, pending = (pending + chunk).replace("\r", "\n").split("\n")
        for line in done:
            yield line
    if pending:
        yield pending


async def upgrade(install: Install, on_step: Callable[[int], None], before: str) -> Outcome:
    """Run the installer. `before` is the version this page runs now. Steps are reported in
    order and never twice; the version on disk afterwards decides updated or same."""
    tail: deque[str] = deque(maxlen=TAIL_LINES)
    reached = -1
    try:
        process = await anyio.open_process(
            list(install.command),
            stdin=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            env={**os.environ, **_ENV.get(install.method, {})},
        )
    except OSError as error:
        return Outcome("failed", None, [str(error)])
    async with process:
        assert process.stdout is not None
        async for raw in _lines(process.stdout):
            line = raw.strip()
            if not line:
                continue
            tail.append(line)
            step = step_for(install.method, line)
            if step is not None and step > reached:
                reached = step
                on_step(step)
        code = await process.wait()
    if code != 0:
        return Outcome("failed", None, list(tail))
    after = await anyio.to_thread.run_sync(installed_version, install)
    if after is None:
        tail.append("Could not read the installed version.")
        return Outcome("failed", None, list(tail))
    return Outcome("same" if after == before else "updated", after, list(tail))


def write_marker(home: Path, version: str, launcher: Path) -> None:
    """Tell running gateways that Kitden was updated. Atomic, readable only by the owner."""
    record = {"version": version, "launcher": str(launcher), "time": datetime.now(UTC).isoformat()}
    path = private_data_dir(home) / MARKER
    temp = path.with_name(MARKER + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, json.dumps(record).encode())
    finally:
        os.close(fd)
    os.replace(temp, path)
