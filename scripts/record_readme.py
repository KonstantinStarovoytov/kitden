"""Take the README's pictures from the real page.

Run: uv run --with playwright==1.64.1 python scripts/record_readme.py [--serve]

Each picture starts the real page on a fresh copy of the README sample (scripts/readme_demo.py)
in a temporary folder: three local servers that need no access (memory in Claude Code,
playwright in Codex, sequential-thinking in Cursor) and Stripe in Claude Code, which takes an
API key. Stand-ins keep it local: a fake Keychain, fake client commands, canned tool lists, and a
local test server that takes one key in place of Stripe's. Only the catalog search goes online
(Context7, whose remote server needs no key). Nothing of the real home folder is read or
written.

Each scene is played to its key moment, in light and dark, with a drawn cursor, and the part of
the page it is about is saved as a PNG in docs/images/readme/ (scripts/record_scenes.py).
`--serve` only starts the page and prints its link, to look around. See docs/readme-media.md.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

import uvicorn  # noqa: E402
from readme_demo import build_sample, write_json  # noqa: E402

import kitden.changes.actions as actions  # noqa: E402
import kitden.clients.base as base  # noqa: E402
import kitden.web.app as web  # noqa: E402
from conftest import install_fake_security  # noqa: E402
from kitden.demo import DemoRunner, canned_refresh, demo_command  # noqa: E402
from kitden.views.inventory import build_inventory  # noqa: E402

PORT, TOKEN = 47930, "readme"
TOKEN_PORT = 47929
SECRET = "sk_test_51ReadmeSampleKey"  # noqa: S105 - the local test server's only token, not a real key
OUT = ROOT / "docs/images/readme"
# Servers outside the gateway, as their makers document them (checked 2026-11-02). The sample
# only shows them; nothing starts these commands or calls this address.
MEMORY = {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"]}
PLAYWRIGHT = ["npx", "@playwright/mcp@latest"]
THINKING = {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]}
STRIPE = "https://mcp.stripe.com"


def token_server() -> None:
    """A local MCP server that takes one token: it stands for Stripe's in the sample."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.headers.get("Authorization") != f"Bearer {SECRET}":
                self.send_response(401)
                self.send_header("WWW-Authenticate", "Bearer")
                self.send_header("Content-Length", "0")
                return self.end_headers()
            if "id" not in body:
                self.send_response(202)
                self.send_header("Content-Length", "0")
                return self.end_headers()
            info = {"name": "stripe", "version": "1"}
            result = {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": info}
            data = json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": result}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", TOKEN_PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def sample(root: Path) -> Path:
    """The README sample with the servers above; Context7 is left to the catalog scene."""
    home = build_sample(root)
    claude_path = home / ".claude.json"
    claude = json.loads(claude_path.read_text())
    del claude["mcpServers"]["context7"]
    claude["mcpServers"]["memory"] = {"type": "stdio", **MEMORY}
    claude["mcpServers"]["stripe"] = {"type": "http", "url": STRIPE}
    write_json(claude_path, claude)
    command, *args = PLAYWRIGHT
    with (home / ".codex/config.toml").open("a") as config:
        config.write("\n[mcp_servers.playwright]\n")
        config.write(f"command = {json.dumps(command)}\nargs = {json.dumps(args)}\n")
    cursor_path = home / ".cursor/mcp.json"
    cursor = json.loads(cursor_path.read_text())
    cursor["mcpServers"]["sequential-thinking"] = THINKING
    write_json(cursor_path, cursor)
    return home


def stand_ins(root: Path) -> None:
    """Everything but the catalog search stays on this computer, once per run."""
    install_fake_security(root / "keychain")
    os.environ["KITDEN_SECURITY"] = str(root / "keychain/bin/security")
    base.read_command_version = lambda command: None  # no real client runs
    real_check = actions.access_needed
    local = f"http://127.0.0.1:{TOKEN_PORT}/mcp"

    def access_needed(url: str, headers: dict) -> str:
        # Only stripe needs access, from the local test server; the rest are open.
        return real_check(local, headers) if url == STRIPE else "open"

    actions.access_needed = access_needed
    web.refresh_tools = canned_refresh  # tool lists without starting any server
    token_server()


def start_page(home: Path, port: int = PORT) -> tuple[str, uvicorn.Server]:
    """The real page on the sample, and its server (set `should_exit` to stop it)."""
    app = web.create_app(
        lambda **options: build_inventory(home, **options),
        token=TOKEN,
        port=port,
        home=home,
        run=DemoRunner(home),
        setup_command=lambda: demo_command(home),
    )
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}/?token={TOKEN}", server


def fresh_page(root: Path, run: int) -> tuple[str, uvicorn.Server]:
    """A new sample and page for one picture, so each starts from the same setup."""
    return start_page(sample(root / f"run{run}"), PORT + 1 + run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serve", action="store_true", help="only start the page")
    parser.add_argument("--only", default="", help="take only the pictures that start so")
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix="kitden-record-")).resolve()
    try:
        stand_ins(folder)
        if args.serve:
            link, _ = start_page(sample(folder / "serve"))
            print(f"README sample: {link}", flush=True)
            print("Ctrl+C stops the page and deletes the sample.", flush=True)
            while True:
                time.sleep(3600)
        from record_scenes import record_all  # Playwright loads only to record

        record_all(lambda run: fresh_page(folder, run), OUT, args.only)
    except KeyboardInterrupt:
        pass
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
