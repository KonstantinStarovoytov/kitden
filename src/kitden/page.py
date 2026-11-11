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

from kitden.gateways import data_dir, private_data_dir

HOST = "127.0.0.1"
LOCK = "page.lock"
RECORD = "page.json"
LOG = "page.log"
# How long `kitden open` waits for a new page. The goal is under 5 s, but the first scan of a large
# home can take about that long (feature 001 validation: 4.2 s), so a slow start is not a failure.
WAIT_SECONDS = 20.0
IDLE_SECONDS = 600.0  # a background page stops after 10 minutes without an open tab
# After an update the new version's page takes over the old page's port, token and session, so
# open tabs keep working. They come in this env value as "port:token:session", never in the
# command line, which other users can see.
TAKE_OVER = "KITDEN_TAKE_OVER"
TAKE_OVER_SECONDS = 30.0  # how long the new page waits for the old one to stop


class PageLock:
    def __init__(self, home: Path) -> None:
        self.home = Path(home)
        self.fd: int | None = None

    def acquire(self, wait: float = 0) -> bool:
        """Take the lock, trying for up to `wait` seconds."""
        deadline = time.monotonic() + wait
        fd = os.open(private_data_dir(self.home) / LOCK, os.O_RDWR | os.O_CREAT, 0o600)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                if time.monotonic() < deadline:
                    time.sleep(0.1)
                    continue
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
    path = private_data_dir(home) / RECORD
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


def wait_for_record(home: Path, seconds: float = WAIT_SECONDS) -> dict | None:
    """Wait until a running page has written its record."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        record = read_record(home)
        if record and page_running(home):
            return record
        time.sleep(0.1)
    return None


class IdleClock:
    """Says when a background page has had no tab and no running change for `wait` seconds."""

    def __init__(self, wait: float, now: float) -> None:
        self.wait = wait
        self.idle_since = now

    def tick(self, tabs: int, busy: bool, now: float) -> bool:
        if tabs or busy:
            self.idle_since = now
            return False
        return now - self.idle_since >= self.wait


def start_link(record: dict) -> str:
    return f"http://{HOST}:{record['port']}/?token={record['token']}"


def log_path(home: Path) -> Path:
    return data_dir(home) / LOG


def start_background(
    home: Path, home_arg: str | None, launcher: Path | None = None, take_over: str | None = None
) -> None:
    """Start `kitden serve --background` detached from this terminal (research R5).

    `-P` and the data folder as working folder keep the caller's folder off the import path:
    a project's own `secrets.py` must never run inside the page. After an update, `launcher`
    is the new version's program and `take_over` the old page's "port:token:session".
    """
    folder = private_data_dir(home)
    program = [sys.executable, "-P", "-m", "kitden"] if launcher is None else [str(launcher)]
    command = [*program, "serve", "--background", "--no-browser"]
    env = None
    if take_over is not None:
        command.append("--take-over")
        env = {**os.environ, TAKE_OVER: take_over}
    if home_arg:
        command += ["--home", str(Path(home).absolute())]
    fd = os.open(folder / LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        subprocess.Popen(  # noqa: S603 - our own command with fixed arguments
            command,
            cwd=str(folder),
            stdin=subprocess.DEVNULL,
            stdout=fd,
            stderr=fd,
            start_new_session=True,
            close_fds=True,
            env=env,
        )
    finally:
        os.close(fd)
