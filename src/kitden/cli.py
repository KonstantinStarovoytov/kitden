"""Command line entry point: kitden, open, serve, scan, mcp."""

import argparse
import contextlib
import json
import secrets
import signal
import socket
import sys
import time
import webbrowser
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from kitden import __version__, page
from kitden.views.inventory import Inventory, build_inventory, inventory_dict

HOST = "127.0.0.1"
DEFAULT_PORT = 47800
EXIT_NO_PORT = 2
EXIT_UNREADABLE = 3
EXIT_NOT_STARTED = 4
# Folders whose setup files trigger a rescan; the home folder itself is watched without subfolders.
WATCHED = (".claude", ".codex", ".cursor", ".agents", "Library/Application Support/Claude")


def pick_port(start: int, tries: int = 20) -> int | None:
    """The first free loopback port from `start`, or None."""
    for port in range(start, start + tries):
        with socket.socket() as sock:
            try:
                sock.bind((HOST, port))
            except OSError:
                continue
            return port
    return None


def run_server(
    app,
    host: str,
    port: int,
    on_started: Callable[[], None] | None = None,
    stop_when: Callable[[], bool] | None = None,
) -> None:
    """Serve until stopped. `on_started` runs once the port listens; `stop_when` is checked
    on every server tick (about ten times a second) and stops the server when it says so."""
    import uvicorn

    class Server(uvicorn.Server):
        async def startup(self, sockets=None) -> None:
            await super().startup(sockets=sockets)
            if self.started and on_started:
                on_started()

        async def on_tick(self, counter: int) -> bool:
            if await super().on_tick(counter):
                return True
            return bool(stop_when and stop_when())

    # Open pages keep an event stream; do not wait for them when stopping.
    config = uvicorn.Config(
        app, host=host, port=port, log_level="warning", timeout_graceful_shutdown=2
    )
    # uvicorn shuts down on Ctrl+C or SIGTERM, then sends the signal again to the handler that was
    # there before. Make that a clean exit, so the caller's cleanup runs and the exit code is 0.
    previous = signal.getsignal(signal.SIGTERM)
    with contextlib.suppress(ValueError):  # only the main thread may set handlers
        signal.signal(signal.SIGTERM, _exit_cleanly)
    try:
        Server(config).run()
    except KeyboardInterrupt:
        pass
    finally:
        with contextlib.suppress(ValueError):
            signal.signal(signal.SIGTERM, previous)


def _exit_cleanly(signum, frame) -> None:
    raise SystemExit(0)


def _home(args: argparse.Namespace) -> Path | None:
    return Path(args.home).expanduser() if args.home else None


def _show(url: str, args: argparse.Namespace) -> None:
    print(f"Kitden: {url}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)


def _open(args: argparse.Namespace) -> int:
    """Open the running page for this home folder, or start one in the background (FR-008)."""
    root = _home(args) or Path.home()
    if not page.page_running(root):
        page.remove_record(root)  # left by a page that ended without cleaning up
        page.start_background(root, args.home)
    record = page.wait_for_record(root, page.WAIT_SECONDS)
    if record is None:
        print(f"The page did not start. See {page.log_path(root)}.", file=sys.stderr)
        return EXIT_NOT_STARTED
    _show(page.start_link(record), args)
    return 0


def _serve(args: argparse.Namespace) -> int:
    """Run the page here until stopped; only one page runs per home folder (FR-009, FR-013)."""
    from kitden.web.app import create_app

    home = _home(args)
    root = home or Path.home()
    lock = page.PageLock(root)
    if not lock.acquire():
        # Another page runs. A background start just ends; a person gets that page opened.
        return 0 if args.background else _open(args)
    try:
        page.remove_record(root)  # left by a page that ended without cleaning up
        port = pick_port(DEFAULT_PORT)
        if port is None:
            print(f"No free port from {DEFAULT_PORT}.", file=sys.stderr)
            return EXIT_NO_PORT
        token = secrets.token_urlsafe(32)
        app = create_app(
            lambda **options: build_inventory(home, **options),
            token=token,
            port=port,
            watch_folders=[root / name for name in WATCHED],
            flat_folders=[root],
            home=root,
            first_scan_later=True,  # listen first; the page shows its skeleton while it scans
            quick_first=True,  # data in a second or two; slow answers come in the background
        )
        url = f"http://{HOST}:{port}/?token={token}"
        if not args.background:  # a background page writes to page.log; keep the token out
            print(f"Kitden is running. Open: {url}", flush=True)
            print("Press Ctrl+C to stop.", flush=True)

        def started() -> None:
            page.write_record(root, port, token, background=args.background)
            if not args.no_browser:
                webbrowser.open(url)

        stop_when = None
        if args.background:
            clock = page.IdleClock(page.IDLE_SECONDS, time.monotonic())
            activity = app.state.activity

            def stop_when() -> bool:
                return clock.tick(activity.tabs(), activity.busy(), time.monotonic())

        run_server(app, HOST, port, on_started=started, stop_when=stop_when)
        return 0
    finally:
        page.remove_record(root)
        lock.release()


def _print_summary(inventory: Inventory) -> None:
    counts = Counter((i.client, str(i.kind)) for i in inventory.items)
    for client in inventory.clients:
        version = client.version or "unknown version"
        print(f"{client.display_name}: {client.status} ({version})")
        for (owner, kind), count in sorted(counts.items()):
            if owner == client.id:
                print(f"  {kind}: {count}")
    for problem in inventory.problems:
        print(f"Could not read {problem.path or problem.owner_client}: {problem.unknown_reason}")


def _scan(args: argparse.Namespace) -> int:
    inventory = build_inventory(Path(args.home).expanduser() if args.home else None)
    if args.json:
        json.dump(inventory_dict(inventory), sys.stdout, indent=2)
        print()
    else:
        _print_summary(inventory)
    return EXIT_UNREADABLE if inventory.problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kitden")
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--home", help="read clients under this home folder (for testing)")
    commands = parser.add_subparsers(dest="command")
    # SUPPRESS keeps an option given before the command (`kitden --home X open`).
    keep = argparse.SUPPRESS
    opener = commands.add_parser("open", help="open the page; start it in the background if needed")
    serve = commands.add_parser("serve", help="run the page here until Ctrl+C")
    serve.add_argument("--background", action="store_true", help=argparse.SUPPRESS)
    scan = commands.add_parser("scan", help="print what each client loads, then exit")
    scan.add_argument("--json", action="store_true", help="print JSON instead of a summary")
    mcp = commands.add_parser("mcp", help="run the Kitden MCP server and gateway over stdio")
    for sub in (opener, serve):
        sub.add_argument(
            "--no-browser", action="store_true", default=keep, help="only print the link"
        )
    for sub in (opener, serve, scan, mcp):
        sub.add_argument(
            "--home", default=keep, help="read clients under this home folder (for testing)"
        )
    args = parser.parse_args(argv)
    args.background = getattr(args, "background", False)

    if args.version:
        print(f"kitden {__version__}")
        return 0
    from kitden.gateways import ensure_data_folder

    note = ensure_data_folder(Path(args.home).expanduser() if args.home else Path.home())
    # The MCP server talks over stdio; keep its output clean.
    if note and args.command != "mcp":
        print(note, file=sys.stderr)
    if args.command == "scan":
        return _scan(args)
    if args.command == "mcp":
        from kitden import mcp_server

        mcp_server.run(_home(args))
        return 0
    if args.command == "serve":
        return _serve(args)
    return _open(args)


if __name__ == "__main__":
    sys.exit(main())
