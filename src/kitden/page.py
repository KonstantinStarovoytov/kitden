"""One page per home folder (feature 002, research R3 to R6).

The running page holds an exclusive lock on `page.lock` for its whole life; the operating system
releases it when the process ends, so a crash never leaves a "running" page behind. While it runs,
`page.json` (mode 0600) holds its port and start link, so `kitden open` can reopen it.
"""

import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from kitden.gateways import data_dir

HOST = "127.0.0.1"
LOCK = "page.lock"
RECORD = "page.json"
LOG = "page.log"
WAIT_SECONDS = 5.0


def _folder(home: Path) -> Path:
    folder = data_dir(home)
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)
    return folder


class PageLock:
    def __init__(self, home: Path) -> None:
        self.home = Path(home)
        self.fd: int | None = None

    def acquire(self) -> bool:
        fd = os.open(_folder(self.home) / LOCK, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return False
        self.fd = fd
        return True

    def release(self) -> None:
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


def page_running(home: Path) -> bool:
    probe = PageLock(home)
    if probe.acquire():
        probe.release()
        return False
    return True


def write_record(home: Path, port: int, token: str, background: bool) -> None:
    record = {
        "pid": os.getpid(),
        "port": port,
        "token": token,
        "background": background,
        "started": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    path = _folder(home) / RECORD
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, json.dumps(record).encode())
    finally:
        os.close(fd)


def read_record(home: Path) -> dict | None:
    try:
        return json.loads((data_dir(home) / RECORD).read_text())
    except (OSError, ValueError):
        return None


def remove_record(home: Path) -> None:
    (data_dir(home) / RECORD).unlink(missing_ok=True)


def running_page(home: Path) -> dict | None:
    """The record of the page that runs now. A record left by a page that ended is removed."""
    if page_running(home):
        return read_record(home)
    remove_record(home)
    return None


def wait_for_record(home: Path, seconds: float = WAIT_SECONDS) -> dict | None:
    """Wait until a running page has written its record."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        record = read_record(home)
        if record and page_running(home):
            return record
        time.sleep(0.1)
    return None


def start_link(record: dict) -> str:
    return f"http://{HOST}:{record['port']}/?token={record['token']}"


def log_path(home: Path) -> Path:
    return data_dir(home) / LOG


def start_background(home: Path, home_arg: str | None) -> None:
    """Start `kitden serve --background` detached from this terminal (research R5)."""
    command = [sys.executable, "-m", "kitden", "serve", "--background", "--no-browser"]
    if home_arg:
        command += ["--home", home_arg]
    fd = os.open(_folder(home) / LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        subprocess.Popen(  # noqa: S603 - our own command with fixed arguments
            command,
            stdin=subprocess.DEVNULL,
            stdout=fd,
            stderr=fd,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        os.close(fd)
