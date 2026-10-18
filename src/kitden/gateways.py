"""Registered MCP gateways (T044, FR-033 to FR-035, FR-040).

Stored in the tool's settings file (mode 0600). Only addresses, the auth type and the name of the
key's environment variable are kept; a key value or a URL with credentials is refused.
"""

import json
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from kitden.changes.atomic import write_atomic
from kitden.model import Gateway, GatewayAuth
from kitden.redact import redact

DATA_DIR = "Library/Application Support/kitden"
OLD_DATA_DIR = "Library/Application Support/agentsetup"  # the working name, before feature 002
SETTINGS = f"{DATA_DIR}/settings.json"


def data_dir(home: Path) -> Path:
    return Path(home) / DATA_DIR


def ensure_data_folder(home: Path) -> str | None:
    """Copy the working version's data folder once (feature 002, research R7). Returns a note.

    The old folder is never changed, so an old page that still runs keeps working. Backups are
    referenced by absolute paths, so the copy points them at the new folder.
    """
    new, old = data_dir(home), Path(home) / OLD_DATA_DIR
    if not old.is_dir():
        return None
    if new.exists():
        return f"The old folder {old} is still there. Kitden does not use it; you can delete it."
    temp = new.with_name(f"{new.name}.copying")
    shutil.rmtree(temp, ignore_errors=True)
    try:
        shutil.copytree(old, temp, symlinks=True)
        for record in temp.glob("changes/*/change.json"):
            text = record.read_text()
            record.write_text(text.replace(json.dumps(str(old))[1:-1], json.dumps(str(new))[1:-1]))
        temp.rename(new)
    except OSError as error:
        shutil.rmtree(temp, ignore_errors=True)
        return f"Could not copy {old} to {new}: {error}. Nothing was deleted."
    return f"Copied {old} to {new}. The old folder was left as it is."


def _check_web_address(url: str, what: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"{what} must be an http or https address")
    if parts.username or parts.password or redact({"url": url})[1]:
        raise ValueError(f"{what} must not contain a secret; use a key variable instead")


def check_gateway(gateway: Gateway) -> None:
    _check_web_address(gateway.url, "The gateway address")
    if gateway.ui_url:
        _check_web_address(gateway.ui_url, "The interface link")


def _read(home: Path) -> dict:
    path = Path(home) / SETTINGS
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_gateways(home: Path) -> list[Gateway]:
    gateways = []
    for raw in _read(home).get("gateways", []):
        try:
            gateway = Gateway(
                url=raw["url"],
                ui_url=raw.get("ui_url"),
                auth=GatewayAuth(raw.get("auth", "none")),
                key_env_var=raw.get("key_env_var"),
            )
            check_gateway(gateway)
        except (KeyError, TypeError, ValueError):
            continue
        gateways.append(gateway)
    return gateways


def add_gateway(home: Path, gateway: Gateway) -> Gateway:
    """Save a gateway; one with the same address is replaced."""
    check_gateway(gateway)
    settings = _read(home)
    kept = [g for g in load_gateways(home) if g.id != gateway.id]
    settings["gateways"] = [
        {"url": g.url, "ui_url": g.ui_url, "auth": str(g.auth), "key_env_var": g.key_env_var}
        for g in [*kept, gateway]
    ]
    folder = data_dir(home)
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)
    write_atomic(Path(home) / SETTINGS, json.dumps(settings, indent=2).encode())
    return gateway
