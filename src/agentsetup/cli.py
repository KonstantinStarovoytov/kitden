"""Command line entry point. See specs/001-agent-setup-inventory/contracts/cli.md."""

import argparse
import json
import secrets
import socket
import sys
import webbrowser
from collections import Counter
from pathlib import Path

from agentsetup import __version__
from agentsetup.views.inventory import Inventory, build_inventory, inventory_dict

HOST = "127.0.0.1"
DEFAULT_PORT = 47800
EXIT_NO_PORT = 2
EXIT_UNREADABLE = 3
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


def run_server(app, host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning")


def _start(args: argparse.Namespace) -> int:
    from agentsetup.web.app import create_app

    port = pick_port(DEFAULT_PORT)
    if port is None:
        print(f"No free port from {DEFAULT_PORT}.", file=sys.stderr)
        return EXIT_NO_PORT
    home = Path(args.home).expanduser() if args.home else None
    root = home or Path.home()
    token = secrets.token_urlsafe(32)
    app = create_app(
        lambda: build_inventory(home),
        token=token,
        port=port,
        watch_folders=[root / name for name in WATCHED],
        flat_folders=[root],
        home=root,
    )
    url = f"http://{HOST}:{port}/?token={token}"
    print(f"agentsetup is running. Open: {url}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    run_server(app, HOST, port)
    return 0


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
    parser = argparse.ArgumentParser(prog="agentsetup")
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--home", help="read clients under this home folder (for testing)")
    commands = parser.add_subparsers(dest="command")
    scan = commands.add_parser("scan", help="print what each client loads, then exit")
    scan.add_argument("--json", action="store_true", help="print JSON instead of a summary")
    scan.add_argument("--home", help="read clients under this home folder (for testing)")
    args = parser.parse_args(argv)

    if args.version:
        print(f"agentsetup {__version__}")
        return 0
    if args.command == "scan":
        return _scan(args)
    return _start(args)


if __name__ == "__main__":
    sys.exit(main())
