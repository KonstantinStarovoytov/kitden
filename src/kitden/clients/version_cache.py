"""Client versions kept on disk, so a scan never waits for a version command.

Each entry is keyed by the real path of the binary Kitden would run and its modification time.
A binary that moved or changed makes its entry stale; only a refresh runs the command again.
"""

import json
import os
import subprocess
from collections.abc import Iterable
from pathlib import Path

from kitden.changes.atomic import write_atomic
from kitden.clients.versions import parse_version, version_command
from kitden.gateways import data_dir

VERSIONS_FILE = "versions.json"
VERSION_TIMEOUT_SECONDS = 20  # Cursor starts Electron to print its version
CLIENTS = ("claude_code", "codex", "cursor")


def run_version_command(client: str) -> str | None:
    """Run the client's version command; None when it is missing, fails or times out."""
    command = version_command(client)
    if not command:
        return None
    try:
        # The command is our own fixed client path plus "--version"; no user input.
        done = subprocess.run(  # noqa: S603
            command, capture_output=True, text=True, timeout=VERSION_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_version(client, done.stdout) if done.returncode == 0 else None


def load_versions(home: Path) -> dict[str, dict]:
    """The cache file as {client: {"path", "mtime_ns", "version"}}; {} when missing or broken."""
    try:
        data = json.loads((data_dir(home) / VERSIONS_FILE).read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {client: entry for client, entry in data.items() if isinstance(entry, dict)}


def _binary(client: str) -> tuple[str, int] | None:
    """The real path of the binary Kitden would run and its modification time, or None.
    The real path, so a link pointed at another binary never keeps the old version."""
    command = version_command(client)
    if not command:
        return None
    try:
        path = os.path.realpath(command[0])
        return path, os.stat(path).st_mtime_ns
    except OSError:
        return None


def _fresh(entry: dict | None, binary: tuple[str, int]) -> bool:
    return bool(entry) and (entry.get("path"), entry.get("mtime_ns")) == binary


def cached_version(home: Path, client: str) -> str | None:
    """The cached version while the binary is unchanged; no command runs."""
    binary = _binary(client)
    entry = load_versions(home).get(client)
    if binary is None or not _fresh(entry, binary):
        return None
    version = entry.get("version")
    return version if isinstance(version, str) else None


def stale_clients(home: Path, clients: Iterable[str]) -> list[str]:
    """The clients whose command exists and whose cache entry is missing or stale."""
    versions = load_versions(home)
    return [
        client
        for client in clients
        if (binary := _binary(client)) is not None and not _fresh(versions.get(client), binary)
    ]


def refresh_versions(home: Path, clients: Iterable[str]) -> dict[str, str | None]:
    """Run each client's version command; keep the ones that worked. Returns {client: version}."""
    found: dict[str, str | None] = {}
    entries: dict[str, dict] = {}
    for client in clients:
        binary = _binary(client)  # the time before the run, so an update during it reads stale
        found[client] = run_version_command(client) if binary else None
        if binary and found[client]:
            entries[client] = {"path": binary[0], "mtime_ns": binary[1], "version": found[client]}
    if entries:
        folder = data_dir(home)
        folder.mkdir(parents=True, exist_ok=True)
        folder.chmod(0o700)
        versions = {**load_versions(home), **entries}
        written = write_atomic(folder / VERSIONS_FILE, json.dumps(versions, indent=2).encode())
        written.chmod(0o600)  # write_atomic keeps an old file's mode; this file is always private
    return found
