"""Registered MCP gateways (T044, FR-033 to FR-035, FR-040).

Stored in the tool's settings file (mode 0600). Only addresses, the auth type and the name of the
key's environment variable are kept; a key value or a URL with credentials is refused.
"""

import contextlib
import json
import shutil
import tempfile
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


COPIED = ".copied-from-agentsetup"  # written last; without it the copy is not finished


def ensure_data_folder(home: Path) -> str | None:
    """Copy the working version's data folder once (feature 002, research R7). Returns a note.

    The old folder is never changed, so an old page that still runs keeps working. Each copy goes
    to its own temporary folder, so two commands starting at once cannot spoil each other; a copy
    that failed or was cut short is tried again on the next start. Backups are referenced by
    absolute paths, so the copy points them at the new folder.
    """
    new, old = data_dir(home), Path(home) / OLD_DATA_DIR
    if not old.is_dir():
        return None
    if (new / COPIED).exists():
        return f"Kitden uses {new}; the old folder {old} is not used."
    new.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(dir=new.parent, prefix=f"{new.name}.copying-"))
    try:
        copy = temp / "data"
        shutil.copytree(old, copy, symlinks=True)
        for record in copy.glob("changes/*/change.json"):
            _point_backups_at(record, old, new)
        new.mkdir(mode=0o700, exist_ok=True)
        new.chmod(0o700)
        for entry in copy.iterdir():  # whole entries move at once; ones already there stay
            with contextlib.suppress(OSError):
                entry.rename(new / entry.name)
        (new / COPIED).write_text(f"{old}\n")
    except (OSError, ValueError, shutil.Error) as error:
        reason = error.args[0] if isinstance(error, shutil.Error) and error.args else error
        if isinstance(reason, list):
            reason = f"{len(reason)} files could not be read"
        return f"Could not copy {old} to {new}: {reason}. Nothing was deleted."
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return f"Copied {old} to {new}. The old folder was left as it is and is no longer used."


def _point_backups_at(record: Path, old: Path, new: Path) -> None:
    """Point one change record's backups at the new folder. Unreadable records stay as they are."""
    try:
        data = json.loads(record.read_bytes())
        prefix = f"{old}/"
        for step in data.get("steps", []):
            edit = step.get("edit", {})
            path = edit.get("backup_path")
            if isinstance(path, str) and path.startswith(prefix):
                edit["backup_path"] = f"{new}/{path[len(prefix) :]}"
    except (ValueError, AttributeError):
        return
    record.write_text(json.dumps(data, indent=2))


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
