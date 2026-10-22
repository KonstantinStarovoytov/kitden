"""Measure how fast the page opens on a large sandbox setup (never the real home folder).

Two runs, each on its own sandbox home with fake `claude`, `codex` and `cursor` commands:
- first usable: the time to the first answer of /api/overview while Codex's plugin list
  takes `--slow` seconds; the start line must then say it still checks "Codex plugins";
- complete: the time until every step of the first scan is done, with the list answering at once.
The client versions are read once before each run, as on any start after the first.

Usage: uv run python scripts/measure-start.py
         [--servers 40] [--plugins 10] [--skills 20] [--slow 10]
"""

import argparse
import json
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

from tests.conftest import fake_client_command, make_home, write_cursor_fixture_state  # noqa: E402

from kitden.cli import WATCHED  # noqa: E402
from kitden.clients import version_cache  # noqa: E402
from kitden.views.inventory import build_inventory  # noqa: E402
from kitden.web.app import create_app  # noqa: E402

FIRST_USABLE_BUDGET = 2.0  # seconds, even while Codex's plugin list is slow
COMPLETE_BUDGET = 5.0  # seconds, with every answer at once
GIVE_UP_SECONDS = 60
SLOW_STEP = "Codex plugins"


def build_sandbox(root: Path, servers: int, plugins: int, skills: int, slow: float) -> Path:
    """A fixture home with extra servers, plugins and skills, and fake clients in root/bin."""
    home = make_home(root, "cursor/3.21.16", "codex/0.159.2", "claude_code/2.1.283")
    write_cursor_fixture_state(home)

    claude_file, cursor_file = home / ".claude.json", home / ".cursor/mcp.json"
    claude, cursor = json.loads(claude_file.read_text()), json.loads(cursor_file.read_text())
    codex = []
    for n in range(servers):
        name = f"bench-server-{n:02d}"
        entry = {"command": "uvx", "args": [name]}
        if n % 2:
            entry = {"url": f"https://example.test/{name}"}
        if n % 3 == 0:
            claude["mcpServers"][name] = entry
        elif n % 3 == 1:
            codex.append(f'\n[mcp_servers.{name}]\nurl = "https://example.test/{name}"\n')
        else:
            cursor["mcpServers"][name] = entry
    claude_file.write_text(json.dumps(claude, indent=2))
    cursor_file.write_text(json.dumps(cursor, indent=2))
    with (home / ".codex/config.toml").open("a") as config:
        config.write("".join(codex))

    installed_file = home / ".claude/plugins/installed_plugins.json"
    installed = json.loads(installed_file.read_text())
    for n in range(plugins):
        name = f"plugin-{n:02d}"
        folder = home / f".claude/plugins/cache/bench-market/{name}/1.0.0"
        manifest = folder / ".claude-plugin/plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": name, "version": "1.0.0"}))
        _skill(folder / "skills", f"{name}-skill")
        installed["plugins"][f"{name}@bench-market"] = [
            {"scope": "user", "installPath": str(folder), "version": "1.0.0"}
        ]
    installed_file.write_text(json.dumps(installed, indent=2))

    folders = [".claude/skills", ".agents/skills", ".cursor/skills"]
    for n in range(skills):
        _skill(home / folders[n % 3], f"bench-skill-{n:02d}")

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


def _skill(folder: Path, name: str) -> None:
    path = folder / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: A skill for the measurement.\n---\n")


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
    parser.add_argument("--servers", type=int, default=40)
    parser.add_argument("--plugins", type=int, default=10)
    parser.add_argument("--skills", type=int, default=20)
    parser.add_argument("--slow", type=float, default=10)
    args = parser.parse_args()
    sizes = (args.servers, args.plugins, args.skills)
    real_home, real_path = os.environ.get("HOME"), os.environ.get("PATH")
    try:
        with tempfile.TemporaryDirectory(prefix="kitden-measure-") as folder:
            slow_home = build_sandbox(Path(folder) / "slow", *sizes, slow=args.slow)
            slow_run = measure(slow_home, args.slow)
            quick_home = build_sandbox(Path(folder) / "quick", *sizes, slow=0)
            quick_run = measure(quick_home, 0)
    finally:
        os.environ.update(HOME=real_home or "", PATH=real_path or "")
    first, complete = slow_run["first_usable"], quick_run["complete"]
    print(f"first usable: {first:.1f} s (budget {FIRST_USABLE_BUDGET:g} s)")
    print(f"  the start line then said: Still checking {', '.join(slow_run['still_checking'])}")
    print(f"complete: {complete:.1f} s (budget {COMPLETE_BUDGET:g} s)")
    missed = first > FIRST_USABLE_BUDGET or complete > COMPLETE_BUDGET
    if missed:
        print("A budget is missed.")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
