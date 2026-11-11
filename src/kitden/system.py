"""Where this system keeps things. The one place that knows macOS from Linux.

| What | macOS, under ~/Library/Application Support | Linux |
| --- | --- | --- |
| Kitden's data | kitden | ~/.local/share/kitden |
| Cursor's state | Cursor/User | ~/.config/Cursor/User |
| Claude Desktop | Claude | ~/.config/Claude |
| Secrets | the Keychain (`security`) | the keyring (`secret-tool`) |

Every Linux folder hangs off the home folder Kitden is given, never off XDG_DATA_HOME or
XDG_CONFIG_HOME: a gateway that a client starts may not get those variables (Codex passes a
short list), and a sample or test home must never reach the person's own folders.

`KITDEN_SYSTEM` (`mac` or `linux`) overrides the detected system, for tests and the demo only.
"""

import os
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

PLATFORMS = {"darwin": "mac", "linux": "linux"}
SYSTEM: str = os.environ.get("KITDEN_SYSTEM") or PLATFORMS.get(sys.platform, sys.platform)
MAC_SUPPORT = "Library/Application Support"

# A client's command inside its macOS app, for when it is not on PATH.
MAC_APP_COMMANDS = {
    "codex": ("/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",),
    "cursor": ("/Applications/Cursor.app/Contents/Resources/app/bin/cursor",),
}


def supported() -> bool:
    return SYSTEM in ("mac", "linux")


def data_dir(home: Path) -> Path:
    """Not moved by XDG_DATA_HOME: the gateway a client starts may not get that variable (Codex
    passes only a short list), and the page and the gateway must find the same folder."""
    if SYSTEM == "mac":
        return Path(home) / MAC_SUPPORT / "kitden"
    return Path(home) / ".local/share/kitden"


def cursor_state_dir(home: Path) -> Path:
    if SYSTEM == "mac":
        return Path(home) / MAC_SUPPORT / "Cursor/User"
    return Path(home) / ".config/Cursor/User"


def claude_desktop_dir(home: Path) -> Path:
    if SYSTEM == "mac":
        return Path(home) / MAC_SUPPORT / "Claude"
    return Path(home) / ".config/Claude"


def watched(home: Path) -> list[Path]:
    """The folders whose setup files trigger a rescan."""
    clients = [Path(home) / name for name in (".claude", ".codex", ".cursor", ".agents")]
    return [*clients, claude_desktop_dir(home)]


def app_roots(home: Path) -> list[Path]:
    """Where macOS keeps apps: the system folder and the person's own. None on Linux."""
    return [Path("/Applications"), Path(home) / "Applications"] if SYSTEM == "mac" else []


def app_commands(name: str) -> tuple[str, ...]:
    """Where an app keeps a client's command when it is not on PATH. None on Linux."""
    return MAC_APP_COMMANDS.get(name, ()) if SYSTEM == "mac" else ()


def secret_store_name() -> str:
    return "Keychain" if SYSTEM == "mac" else "keyring"


def process_starts(
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> list[tuple[datetime, str]]:
    """When each running process started and its command line, from `ps`. macOS and Linux say
    it the same way with LC_ALL=C: "Tue Nov 11 09:15:02 2026 <args>", a short day padded with a
    space. If `ps` fails, nothing is returned; a line that does not read is skipped."""
    try:
        done = run(
            ["ps", "-A", "-o", "lstart=,args="],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if done.returncode != 0:
        return []
    found = []
    for text in done.stdout.splitlines():
        words = text.split(None, 5)
        if len(words) < 6:
            continue
        try:
            started = datetime.strptime(" ".join(words[:5]), "%a %b %d %H:%M:%S %Y")
        except ValueError:
            continue
        found.append((started.astimezone(), words[5]))
    return found
