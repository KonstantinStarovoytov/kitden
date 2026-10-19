"""Which client apps are installed on this Mac, and the link scheme each one registers.

The Gateway page turns a client node into a link only when its app is here. The schemes come
from each app's `Info.plist` (`CFBundleURLTypes`), read at scan time: Claude.app registers
`claude`, Cursor.app `cursor`, and ChatGPT.app, which bundles Codex, `codex` (checked
2026-10-19 on the owner's Mac). An app that is missing, unreadable or registers no such
scheme gives no link.
"""

import plistlib
from pathlib import Path

# client id -> (app bundle name, scheme the page opens)
CLIENT_APPS = {
    "claude_code": ("Claude", "claude"),
    "codex": ("ChatGPT", "codex"),
    "cursor": ("Cursor", "cursor"),
}


def app_roots(home: Path) -> list[Path]:
    """Where macOS keeps apps: the system folder and the person's own."""
    return [Path("/Applications"), Path(home) / "Applications"]


def registered_schemes(plist: Path) -> set[str]:
    try:
        with plist.open("rb") as file:
            data = plistlib.load(file)
    except (OSError, ValueError, plistlib.InvalidFileException):
        return set()
    schemes: set[str] = set()
    for kind in data.get("CFBundleURLTypes", []) if isinstance(data, dict) else []:
        if isinstance(kind, dict):
            schemes |= {s for s in kind.get("CFBundleURLSchemes", []) if isinstance(s, str)}
    return schemes


def app_url(client: str, roots: list[Path]) -> str | None:
    """`claude://` when Claude.app is in one of the roots and registers that scheme."""
    if client not in CLIENT_APPS:
        return None
    app, scheme = CLIENT_APPS[client]
    for root in roots:
        if scheme in registered_schemes(root / f"{app}.app/Contents/Info.plist"):
            return f"{scheme}://"
    return None
