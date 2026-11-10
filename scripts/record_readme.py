"""Make the README's pictures from the real page.

Run: uv run --with playwright==1.64.1 python scripts/record_readme.py [--serve]

Each picture starts the real page on a fresh copy of the README sample (scripts/readme_demo.py)
in a temporary folder: memory in Claude Code, playwright in Codex and Context7 in Cursor.
The Context picture is taken on the sample `kitden demo` opens, so the demo shows the same.
Stand-ins keep it local: a fake Keychain, fake client commands, canned tool lists and
catalog answers, and no access checks. Nothing goes online, and nothing of the real home
folder is read or written.

Each scene is taken in light and dark, with a drawn cursor, and the part of the page it is
about is saved in docs/images/readme/: a still as a PNG, an animation as a looping WebP
(scripts/record_scenes.py).
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

import uvicorn  # noqa: E402
from readme_demo import build_sample, write_json  # noqa: E402

import kitden.changes.actions as actions  # noqa: E402
import kitden.clients.base as base  # noqa: E402
import kitden.discovery as discovery  # noqa: E402
import kitden.web.app as web  # noqa: E402
from conftest import install_fake_security  # noqa: E402
from kitden.demo import (  # noqa: E402
    DemoRunner,
    build_demo_home,
    canned_refresh,
    demo_build,
    demo_command,
    no_sign_in,
)
from kitden.local_gateway.settings import save_tools  # noqa: E402
from kitden.views.inventory import build_inventory  # noqa: E402

PORT, TOKEN = 47930, "readme"
OUT = ROOT / "docs/images/readme"
# Servers outside the gateway, as their makers document them (checked 2026-11-02; Context7's
# address as in the sample). The sample
# only shows them; nothing starts these commands or calls this address.
MEMORY = {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"]}
PLAYWRIGHT = ["npx", "@playwright/mcp@latest"]
CONTEXT7 = {"url": "https://mcp.context7.com/mcp"}  # as Cursor writes a remote server
# memory's tools, as its source lists them (src/memory/index.ts, checked 2026-11-02): the
# gateway knows these once memory is in it.
READS = {"readOnlyHint": True, "destructiveHint": False}
WRITES = {"readOnlyHint": False, "destructiveHint": False}
DELETES = {"readOnlyHint": False, "destructiveHint": True}
MEMORY_TOOLS = [
    {
        "name": name,
        "title": title,
        "description": f"{title}.",
        "inputSchema": {"type": "object"},
        "annotations": hints,
    }
    for name, title, hints in (
        ("create_entities", "Create Entities", WRITES),
        ("create_relations", "Create Relations", WRITES),
        ("add_observations", "Add Observations", WRITES),
        ("delete_entities", "Delete Entities", DELETES),
        ("delete_observations", "Delete Observations", DELETES),
        ("delete_relations", "Delete Relations", DELETES),
        ("read_graph", "Read Graph", READS),
        ("search_nodes", "Search Nodes", READS),
        ("open_nodes", "Open Nodes", READS),
    )
]

# skills.sh's answer to "mcp", the first six rows as the page sorts them, and the skill picked
# from it (checked 2026-11-05: https://skills.sh, https://github.com/anthropics/skills). The
# search scene reads these and nothing online.
SKILLS_COMMIT = "ca45fc496a3436251f191354091d557da31c15b5"
FOUND = [
    {"name": name, "source": source, "installs": installs}
    for name, source, installs in (
        ("mcp-builder", "anthropics/skills", 137257),
        ("mcp-apps-builder", "mcp-use/mcp-use", 33046),
        ("azure-aigateway", "microsoft/azure-skills", 616892),
        ("azure-compute", "microsoft/azure-skills", 573379),
        ("prisma-cli", "prisma/skills", 408799),
        ("supabase", "supabase/agent-skills", 356409),
    )
]
# The front matter of skills/mcp-builder/SKILL.md (Apache-2.0), without its guide.
MCP_BUILDER = (
    "---\nname: mcp-builder\ndescription: "
    "Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to "
    "interact with external services through well-designed tools. Use when building MCP "
    "servers to integrate external APIs or services, whether in Python (FastMCP) or "
    "Node/TypeScript (MCP SDK).\n"
    "---\n\n# MCP server development guide\n"
)
GITHUB = "https://api.github.com/repos/anthropics/skills"
SKILL_FILE = "skills/mcp-builder/SKILL.md"
CATALOG = {
    "https://skills.sh/api/search?q=mcp&limit=30": {"skills": FOUND},
    f"{GITHUB}/commits/HEAD": {"sha": SKILLS_COMMIT},
    f"{GITHUB}/git/trees/{SKILLS_COMMIT}?recursive=1": {
        "tree": [{"path": SKILL_FILE, "type": "blob", "mode": "100644"}]
    },
    discovery.raw_url("anthropics/skills", SKILLS_COMMIT, SKILL_FILE): MCP_BUILDER,
}


# The Official MCP Registry's answer to "linear": its first six servers in its own order, cut
# down to what the page reads (checked 2026-11-05: https://registry.modelcontextprotocol.io).
# Linear's own server asks for a sign-in, as Kitden's check of its address said that day.
LINEAR = "https://mcp.linear.app/mcp"
SERVERS = [
    {
        "name": "app.linear/linear",
        "version": "1.0.2",
        "description": "Find and manage issues, projects, and documents in your Linear workspace.",
        "remotes": [{"type": "streamable-http", "url": LINEAR}],
    },
    {
        "name": "co.civai.nova/mcp-linear",
        "version": "1.0.0",
        "description": "Issues, projects, cycles, and roadmaps via the official Linear hosted "
        "MCP server.",
        "remotes": [
            {"type": "streamable-http", "url": "https://nova.civai.co/mcp/agents/mcp-linear"}
        ],
    },
    {
        "name": "io.github.Evozim/linear-broker",
        "version": "1.0.0",
        "description": "Integrates agents with Linear software development workflows.",
        "remotes": [{"type": "sse", "url": "https://linear-broker-mcp.vercel.app/api/mcp"}],
    },
    {
        "name": "io.github.adelaidasofia/linear-mcp",
        "version": "0.3.2",
        "description": "Multi-workspace Linear MCP — PAT auth, 57 tools + 3 prompts, substrate "
        "enforcement, drop-in.",
        "packages": [
            {
                "registryType": "pypi",
                "identifier": "adelaidasofia-linear-mcp",
                "version": "0.3.2",
                "transport": {"type": "stdio"},
                "environmentVariables": [{"name": "LINEAR_PAT", "isRequired": True}],
            }
        ],
    },
    {
        "name": "io.github.mrfentmen/linear-mcp",
        "version": "1.1.0",
        "description": "Query the Linear GraphQL API: viewer, teams, issue search.",
        "packages": [
            {
                "registryType": "npm",
                "identifier": "@mrfentmen/linear-mcp",
                "version": "1.1.0",
                "transport": {"type": "stdio"},
            }
        ],
    },
    {
        "name": "io.github.pipeworx-io/linear",
        "version": "0.2.1",
        "description": "Linear MCP — wraps the Linear GraphQL API (OAuth)",
        "remotes": [{"type": "streamable-http", "url": "https://gateway.pipeworx.io/linear/mcp"}],
    },
]
ACTIVE = {"io.modelcontextprotocol.registry/official": {"status": "active"}}
REGISTRY = "https://registry.modelcontextprotocol.io/v0.1/servers"
CATALOG[f"{REGISTRY}?search=linear&version=latest&limit=100"] = {
    "servers": [{"server": server, "_meta": ACTIVE} for server in SERVERS]
}


def canned_access(url: str, headers: dict) -> str:
    """What a found server needs, without asking it."""
    return "sign-in" if url == LINEAR else "open"


def canned_download(url: str) -> bytes:
    """A catalog's answer from the table above; any other address is refused."""
    if url not in CATALOG:
        raise OSError("The README sample stays offline.")
    answer = CATALOG[url]
    return (answer if isinstance(answer, str) else json.dumps(answer)).encode()


def sample(root: Path) -> Path:
    """The README sample with the servers above, and memory's tools; Context7 moves to Cursor."""
    home = build_sample(root)
    claude_path = home / ".claude.json"
    claude = json.loads(claude_path.read_text())
    del claude["mcpServers"]["context7"]
    claude["mcpServers"]["memory"] = {"type": "stdio", **MEMORY}
    write_json(claude_path, claude)
    command, *args = PLAYWRIGHT
    with (home / ".codex/config.toml").open("a") as config:
        config.write("\n[mcp_servers.playwright]\n")
        config.write(f"command = {json.dumps(command)}\nargs = {json.dumps(args)}\n")
    cursor_path = home / ".cursor/mcp.json"
    cursor = json.loads(cursor_path.read_text())
    cursor["mcpServers"]["context7"] = CONTEXT7
    write_json(cursor_path, cursor)
    save_tools(home, "memory", MEMORY_TOOLS)
    return home


def stand_ins(root: Path) -> None:
    """Everything stays on this computer, once per run."""
    install_fake_security(root / "keychain")
    os.environ["KITDEN_SECURITY"] = str(root / "keychain/bin/security")
    base.read_command_version = lambda command: None  # no real client runs
    actions.access_needed = no_sign_in  # no server is asked for access
    web.refresh_tools = canned_refresh  # tool lists without starting any server
    discovery.download = canned_download  # catalogs answer from this file
    discovery.popular_skills = lambda: FOUND
    discovery.access_needed = canned_access


def start_page(home: Path, port: int = PORT, build=None) -> tuple[str, uvicorn.Server]:
    """The real page on the sample, and its server (set `should_exit` to stop it)."""
    app = web.create_app(
        build or (lambda **options: build_inventory(home, **options)),
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


def fresh_page(root: Path, run: int, scene: str) -> tuple[str, uvicorn.Server]:
    """A new sample and page for one picture, so each starts from the same setup. Context is
    taken on the demo's own sample, read as the demo reads it."""
    folder, port = root / f"run{run}", PORT + 1 + run
    if scene == "context":
        home = build_demo_home(folder, "medium")
        return start_page(home, port, demo_build(home))
    return start_page(sample(folder), port)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serve", action="store_true", help="only start the page")
    parser.add_argument("--only", default="", help="make only the animations that start so")
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

        record_all(lambda run, scene: fresh_page(folder, run, scene), OUT, args.only)
    except KeyboardInterrupt:
        pass
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
