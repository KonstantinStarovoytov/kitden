"""Measure how fast the page opens on the large sample setup (never the real home folder).

Two runs, each on its own copy of the large sample (`kitden.demo`) with fake `claude`, `codex`
and `cursor` commands:
- first usable: the time to the first answer of /api/overview while Codex's plugin list
  takes `--slow` seconds; the start line must then say it still checks "Codex plugins";
- complete: the time until every step of the first scan is done, with the list answering at once.
The client versions are read once before each run, as on any start after the first.
A third run times `kitden demo` on the medium sample: from building it to the first answer of
/api/overview.

Usage: uv run python scripts/measure-start.py [--slow 10]
"""

import argparse
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.conftest import fake_client_command  # noqa: E402

from kitden.cli import WATCHED  # noqa: E402
from kitden.clients import version_cache  # noqa: E402
from kitden.demo import build_demo_home, demo_build  # noqa: E402
from kitden.views.inventory import build_inventory  # noqa: E402
from kitden.web.app import create_app  # noqa: E402

FIRST_USABLE_BUDGET = 2.0  # seconds, even while Codex's plugin list is slow
COMPLETE_BUDGET = 5.0  # seconds, with every answer at once
DEMO_BUDGET = 2.0  # seconds, from building the medium sample to its first overview
GIVE_UP_SECONDS = 60
SLOW_STEP = "Codex plugins"


def build_sandbox(root: Path, slow: float) -> Path:
    """The large sample in root/home, and fake clients in root/bin; Codex's plugin list takes
    `slow` seconds."""
    home = build_demo_home(root, "large")
    fake_client_command(root, "claude", 'echo "2.1.290 (Claude Code)"')
    fake_client_command(root, "cursor", 'echo "3.21.16"')
    fake_client_command(
        root,
        "codex",
        'case "$1" in\n'
        '  --version) echo "codex-cli 0.163.0" ;;\n'
        f"  plugin) sleep {slow}; echo '{{\"installed\": []}}' ;;\n"
        "  *) exit 1 ;;\n"
        "esac",
    )
    return home


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def still_checking(progress: dict) -> list[str]:
    """The steps the start line names, by the rule of `scanLine` in parts.js."""
    open_steps = [s for s in progress["steps"] if not s["done"]]
    named = [s["name"] for s in open_steps if bool(s["later"]) == bool(progress["ready"])]
    return named or [s["name"] for s in open_steps]


def measure(home: Path, slow: float) -> dict:
    """Start the page on `home`; return seconds to first usable and to complete data."""
    os.environ.update(HOME=str(home), PATH=f"{home.parent / 'bin'}:/usr/bin:/bin")
    os.environ.pop("CODEX_HOME", None)
    version_cache.refresh_versions(home, version_cache.CLIENTS)  # the common start: known

    port, token = _free_port(), secrets.token_urlsafe(16)
    app = create_app(
        lambda **options: build_inventory(home, **options),
        token=token,
        port=port,
        watch_folders=[home / name for name in WATCHED],
        flat_folders=[home],
        home=home,
        first_scan_later=True,
        quick_first=True,
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    found: dict = {}
    started = time.monotonic()
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=GIVE_UP_SECONDS) as http:
            _poll(lambda: http.get("/", params={"token": token}).status_code == 303)
            _poll(lambda: "headline" in _json(http.get("/api/overview")))
            found["first_usable"] = time.monotonic() - started
            found["still_checking"] = still_checking(http.get("/api/progress").json())
            if slow > 0 and SLOW_STEP not in found["still_checking"]:
                raise SystemExit(f"The start line does not say it still checks {SLOW_STEP}.")
            _poll(lambda: all(s["done"] for s in http.get("/api/progress").json()["steps"]))
            found["complete"] = time.monotonic() - started
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    return found


def measure_demo(root: Path) -> float:
    """Build the medium sample in `root` and start the demo page on it, as `kitden demo` does;
    return seconds from before the build to the first answer of /api/overview."""
    started = time.monotonic()
    home = build_demo_home(root, "medium")
    port, token = _free_port(), secrets.token_urlsafe(16)
    app = create_app(
        demo_build(home),
        token=token,
        port=port,
        watch_folders=[home / name for name in WATCHED],
        flat_folders=[home],
        home=home,
        first_scan_later=True,
        quick_first=True,
        demo=True,
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=GIVE_UP_SECONDS) as http:
            _poll(lambda: http.get("/", params={"token": token}).status_code == 303)
            _poll(lambda: "headline" in _json(http.get("/api/overview")))
            return time.monotonic() - started
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _json(response: httpx.Response) -> dict:
    return response.json() if response.status_code == 200 else {}


def _poll(ready) -> None:
    """Ask every 50 ms until `ready()` is true; a refused connection means not yet."""
    give_up = time.monotonic() + GIVE_UP_SECONDS
    while time.monotonic() < give_up:
        try:
            if ready():
                return
        except httpx.TransportError:
            pass
        time.sleep(0.05)
    raise SystemExit(f"No answer in {GIVE_UP_SECONDS} s.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure how fast the page opens.")
    parser.add_argument("--slow", type=float, default=10)
    args = parser.parse_args()
    real_home, real_path = os.environ.get("HOME"), os.environ.get("PATH")
    try:
        with tempfile.TemporaryDirectory(prefix="kitden-measure-") as folder:
            slow_home = build_sandbox(Path(folder) / "slow", slow=args.slow)
            slow_run = measure(slow_home, args.slow)
            quick_home = build_sandbox(Path(folder) / "quick", slow=0)
            quick_run = measure(quick_home, 0)
            demo = measure_demo(Path(folder) / "demo")
    finally:
        os.environ.update(HOME=real_home or "", PATH=real_path or "")
    first, complete = slow_run["first_usable"], quick_run["complete"]
    print(f"first usable: {first:.1f} s (budget {FIRST_USABLE_BUDGET:g} s)")
    print(f"  the start line then said: Still checking {', '.join(slow_run['still_checking'])}")
    print(f"complete: {complete:.1f} s (budget {COMPLETE_BUDGET:g} s)")
    print(f"demo (medium): {demo:.1f} s (budget {DEMO_BUDGET:g} s)")
    missed = first > FIRST_USABLE_BUDGET or complete > COMPLETE_BUDGET or demo > DEMO_BUDGET
    if missed:
        print("A budget is missed.")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
