"""Registered MCP gateways (T044, FR-033 to FR-035, FR-040).

Stored in the tool's settings file (mode 0600). Only addresses, the auth type and the name of the
key's environment variable are kept; a key value or a URL with credentials is refused.
"""

import json
from pathlib import Path
from urllib.parse import urlsplit

from agentsetup.changes.atomic import write_atomic
from agentsetup.model import Gateway, GatewayAuth
from agentsetup.redact import redact

DATA_DIR = "Library/Application Support/agentsetup"
SETTINGS = f"{DATA_DIR}/settings.json"


def data_dir(home: Path) -> Path:
    return Path(home) / DATA_DIR


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
