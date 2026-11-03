"""Where this system keeps things. The one place that knows macOS from Linux.

| What | macOS, under ~/Library/Application Support | Linux |
| --- | --- | --- |
| Kitden's data | kitden | ~/.local/share/kitden |
| Cursor's state | Cursor/User | $XDG_CONFIG_HOME/Cursor/User (~/.config) |
| Claude Desktop | Claude | $XDG_CONFIG_HOME/Claude (~/.config) |
| Secrets | the Keychain (`security`) | the keyring (`secret-tool`) |

`KITDEN_SYSTEM` (`mac` or `linux`) overrides the detected system, for tests and the demo only.
"""

import os
import sys
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


def _xdg(name: str, home: Path, default: str) -> Path:
    return Path(os.environ.get(name) or Path(home) / default)


def data_dir(home: Path) -> Path:
    """Not moved by XDG_DATA_HOME: the gateway a client starts may not get that variable (Codex
    passes only a short list), and the page and the gateway must find the same folder."""
    if SYSTEM == "mac":
        return Path(home) / MAC_SUPPORT / "kitden"
    return Path(home) / ".local/share/kitden"


def cursor_state_dir(home: Path) -> Path:
    if SYSTEM == "mac":
        return Path(home) / MAC_SUPPORT / "Cursor/User"
    return _xdg("XDG_CONFIG_HOME", home, ".config") / "Cursor/User"


def claude_desktop_dir(home: Path) -> Path:
    if SYSTEM == "mac":
        return Path(home) / MAC_SUPPORT / "Claude"
    return _xdg("XDG_CONFIG_HOME", home, ".config") / "Claude"


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
