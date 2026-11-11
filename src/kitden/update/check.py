"""The latest Kitden version, asked at most once a day. A failure is never an error."""

import json
import os
import re
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from kitden import __version__
from kitden.gateways import data_dir, private_data_dir

PYPI_URL = "https://pypi.org/pypi/kitden/json"
TAP_URL = (
    "https://raw.githubusercontent.com/KonstantinStarovoytov/homebrew-tap/main/Formula/kitden.rb"
)
RECORD = "update.json"
EVERY = timedelta(hours=24)
TIMEOUT_SECONDS = 5

_STABLE = re.compile(r"^\d+(\.\d+)*$")  # digits and dots only: no rc, dev or post
_FORMULA = re.compile(r"kitden-(\d+(?:\.\d+)*)\.tar\.gz")


def fetch(url: str) -> bytes:
    """One plain GET. Only the user agent is sent."""
    request = urllib.request.Request(url, headers={"User-Agent": f"kitden/{__version__}"})  # noqa: S310 - fixed https address
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        return response.read()


def _stable(version: object) -> str | None:
    return version if isinstance(version, str) and _STABLE.match(version) else None


def latest_version(method: str, fetch: Callable[[str], bytes]) -> str | None:
    """The newest stable version for this install method, or None (offline, odd answer, or
    only a pre-release)."""
    try:
        if method == "uv":
            info = json.loads(fetch(PYPI_URL)).get("info")
            return _stable(info.get("version")) if isinstance(info, dict) else None
        if method == "brew":
            found = _FORMULA.search(fetch(TAP_URL).decode("utf-8", "replace"))
            return found.group(1) if found else None
    except (OSError, ValueError, AttributeError):
        pass
    return None


def _parts(version: str) -> tuple[int, ...] | None:
    return tuple(int(n) for n in version.split(".")) if _STABLE.match(version) else None


def newer(current: str, latest: str | None) -> bool:
    """Is `latest` a higher version than `current`? A version Kitden cannot read says no."""
    if latest is None:
        return False
    have, want = _parts(current), _parts(latest)
    return have is not None and want is not None and want > have


def _read(path: Path, method: str, now: datetime) -> tuple[bool, str | None]:
    """(fresh, latest): fresh when a check for this method was made in the last 24 hours."""
    try:
        record = json.loads(path.read_text())
        checked = datetime.fromisoformat(record["checked"])
        latest = record["latest"]
        fresh = record["method"] == method and timedelta(0) <= now - checked < EVERY
    except (OSError, ValueError, KeyError, TypeError):
        return False, None
    return fresh, _stable(latest)


def _write(home: Path, method: str, now: datetime, latest: str | None) -> None:
    record = {"checked": now.isoformat(timespec="seconds"), "method": method, "latest": latest}
    try:
        path = private_data_dir(home) / RECORD
        temp = path.with_name(RECORD + ".tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, json.dumps(record).encode())
        finally:
            os.close(fd)
        os.replace(temp, path)
    except OSError:
        pass  # not saved: the next page load asks again


def cached_latest(
    home: Path, method: str, now: datetime, fetch: Callable[[str], bytes] = fetch
) -> str | None:
    """The latest version, asking the network only when the last check is over 24 hours old or
    was for another install method. A failed check is remembered too, so an offline machine
    does not try on every page load."""
    fresh, latest = _read(data_dir(home) / RECORD, method, now)
    if fresh:
        return latest
    latest = latest_version(method, fetch)
    _write(home, method, now, latest)
    return latest
