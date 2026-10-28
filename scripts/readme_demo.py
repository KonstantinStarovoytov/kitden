"""Open the small sample used for README captures. Never reads a real client setup.

Run: uv run python scripts/readme_demo.py
All fixture files are made before the page starts. Changes on the page use its normal
preview, Apply, verification and Undo flow, with the demo's offline stand-ins.
"""

import json
import re
import secrets
import tempfile
from pathlib import Path

import uvicorn

from kitden.cli import pick_port
from kitden.demo import build_demo_home, demo_build, demo_command
from kitden.web.app import create_app


def build_sample(root: Path) -> Path:
    """Make a fresh, compact fixture. This only accepts an empty sample directory."""
    home = build_demo_home(root, "medium")
    claude_file = home / ".claude.json"
    claude = json.loads(claude_file.read_text())
    claude["mcpServers"].pop("github")
    claude_file.write_text(json.dumps(claude, indent=2))

    codex_file = home / ".codex/config.toml"
    codex_file.write_text(
        re.sub(
            r"^\[mcp_servers\.(?:docs|analytics|sqlite)\]\n.*?(?=^\[|\Z)",
            "",
            codex_file.read_text(),
            flags=re.MULTILINE | re.DOTALL,
        )
    )
    (home / ".cursor/mcp.json").write_text(
        json.dumps({"mcpServers": {"kitden": {"command": demo_command(home), "args": ["mcp"]}}})
    )
    (home / "work/website/.cursor/mcp.json").write_text('{"mcpServers": {}}\n')
    return home


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="kitden-readme-") as folder:
        home = build_sample(Path(folder).resolve())
        port = pick_port(47920)
        if port is None:
            raise SystemExit("No free demo port.")
        token = secrets.token_urlsafe(32)
        app = create_app(demo_build(home), token=token, port=port, home=home, demo=True)
        print(f"README sample: http://127.0.0.1:{port}/?token={token}", flush=True)
        print("Ctrl+C stops the page and deletes the sample.", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
