"""Open the isolated sample used for README captures.

Run: uv run python scripts/readme_demo.py
Fixtures are written before the page starts. UI changes use preview, Apply, verify and Undo.
The sample never starts a real client or MCP server. See docs/readme-media.md for sources.
"""

import json
import secrets
import shutil
import tempfile
from pathlib import Path

import uvicorn

from kitden.cli import pick_port
from kitden.demo import build_demo_home, demo_build, demo_command
from kitden.gateways import data_dir
from kitden.local_gateway.settings import CALLS_FILE, SETTINGS_FILE, TOOLS_FILE
from kitden.web.app import create_app

# Checked 2026-10-29 against obra/superpowers skills/ and its plugin manifest.
SUPERPOWERS_SKILLS = (
    "brainstorming",
    "diagnosing-superpowers",
    "dispatching-parallel-agents",
    "executing-plans",
    "finishing-a-development-branch",
    "receiving-code-review",
    "requesting-code-review",
    "subagent-driven-development",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "using-superpowers",
    "verification-before-completion",
    "writing-plans",
    "writing-skills",
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


def sample_skill(folder: Path, name: str) -> None:
    path = folder / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: Offline README sample.\n---\n")


def build_sample(root: Path) -> Path:
    """Build a small synthetic setup with verified public names, never executable content."""
    home = build_demo_home(root, "small")
    shutil.rmtree(home / ".claude/plugins")
    shutil.rmtree(home / ".claude/skills")
    market = home / ".claude/plugins/marketplaces/superpowers-dev"
    plugin = market / "plugins/superpowers"
    write_json(plugin / ".claude-plugin/plugin.json", {"name": "superpowers", "version": "7.0.1"})
    for name in SUPERPOWERS_SKILLS:
        sample_skill(plugin / "skills", name)
    write_json(
        market / ".claude-plugin/marketplace.json",
        {
            "name": "superpowers-dev",
            "owner": {"name": "README sample"},
            "plugins": [
                {
                    "name": "superpowers",
                    "source": "./plugins/superpowers",
                    "description": "Offline sample of the Superpowers skills.",
                }
            ],
        },
    )
    source = {"source": "directory", "path": str(market)}
    write_json(
        home / ".claude/plugins/known_marketplaces.json",
        {
            "superpowers-dev": {"source": source, "installLocation": str(market)},
        },
    )
    write_json(
        home / ".claude/plugins/installed_plugins.json",
        {
            "version": 2,
            "plugins": {
                "superpowers@superpowers-dev": [
                    {"scope": "user", "installPath": str(plugin), "version": "7.0.1"},
                ]
            },
        },
    )
    write_json(
        home / ".claude/settings.json",
        {
            "enabledPlugins": {"superpowers@superpowers-dev": True},
            "extraKnownMarketplaces": {"superpowers-dev": {"source": source}},
        },
    )
    # Checked 2026-10-29: anthropics/skills/skills/frontend-design/SKILL.md.
    sample_skill(home / ".agents/skills", "frontend-design")
    connection = {"command": demo_command(home), "args": ["mcp"]}
    claude_path = home / ".claude.json"
    claude = json.loads(claude_path.read_text())
    claude["mcpServers"] = {
        "kitden": {"type": "stdio", **connection},
        "context7": {"type": "http", "url": "https://mcp.context7.com/mcp"},
    }
    for project in claude["projects"].values():
        project["enabledMcpjsonServers"] = []
    write_json(claude_path, claude)
    codex = home / ".codex/config.toml"
    codex.parent.mkdir(parents=True)
    codex.write_text(
        f'[mcp_servers.kitden]\ncommand = {json.dumps(demo_command(home))}\nargs = ["mcp"]\n'
        '[marketplaces.superpowers-dev]\nsource_type = "local"\n'
        f'source = {json.dumps(str(market))}\n'
    )
    write_json(home / ".cursor/mcp.json", {"mcpServers": {"kitden": connection}})
    folder = data_dir(home)
    write_json(folder / SETTINGS_FILE, {"path": "/usr/local/bin:/usr/bin:/bin", "servers": {}})
    # Checked 2026-10-29: upstash/context7/packages/mcp/src/lib/tool-names.ts.
    write_json(
        folder / TOOLS_FILE,
        {
            "context7": [
                {
                    "name": name,
                    "description": description,
                    "inputSchema": {"type": "object"},
                    "annotations": {"readOnlyHint": True},
                }
                for name, description in (
                    ("resolve-library-id", "Find the library ID."),
                    ("query-docs", "Read documentation for a library."),
                )
            ]
        },
    )
    write_json(folder / CALLS_FILE, {})
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
