"""Which clients the user turned off in Kitden. An off client is not read at all.

Kept in `clients.json` in Kitden's data folder, as {"off": ["codex"]}. It is Kitden's own
preference, not a client's settings, so it is written directly.
"""

import json
from pathlib import Path

from kitden.changes.atomic import write_atomic
from kitden.gateways import data_dir, private_data_dir
from kitden.model import CLIENT_WORDS, CLIENTS

CHOICE_FILE = "clients.json"
LAST_ON = "Keep at least one client on."


def off_clients(home: Path) -> frozenset[str]:
    """The clients that are off. A missing or broken file means none; unknown ids are ignored."""
    try:
        data = json.loads((data_dir(home) / CHOICE_FILE).read_text())
        listed = data["off"]
    except (OSError, ValueError, KeyError, TypeError):
        return frozenset()
    if not isinstance(listed, list):
        return frozenset()
    return frozenset(c for c in listed if c in CLIENTS)


def clients_on(home: Path) -> list[str]:
    """The clients that are on, in the order the pages show them."""
    off = off_clients(home)
    return [c for c in CLIENTS if c not in off]


def set_client(home: Path, client: str, on: bool) -> frozenset[str]:
    """Turn a client on or off and return the clients that are off now. Raises ValueError for
    an unknown client and for the last client that is on."""
    if client not in CLIENTS:
        raise ValueError(f"Unknown client: {client}.")
    off = set(off_clients(home))
    if on:
        off.discard(client)
    else:
        off.add(client)
        if not set(CLIENT_WORDS) - off:
            raise ValueError(LAST_ON)
    if off != set(off_clients(home)):
        text = json.dumps({"off": [c for c in CLIENTS if c in off]}, indent=2)
        written = write_atomic(private_data_dir(home) / CHOICE_FILE, text.encode())
        written.chmod(0o600)
    return frozenset(off)
