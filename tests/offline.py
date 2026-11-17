"""Offline stand-ins for the page on a sample home: catalog answers from the tables below, no
client command, no access check and no tool list from a real server. Shared by the browser
tests (the `sample` fixture in tests/browser/conftest.py) and the README pictures
(scripts/record_readme.py). Tests apply STAND_INS with monkeypatch; the script sets them
itself. Only stand-ins live here, no filming code. Nothing here ships: the wheel takes only
src/kitden."""

import json

import kitden.changes.actions as actions
import kitden.clients.codex as codex
import kitden.clients.version_cache as version_cache
import kitden.discovery as discovery
import kitden.web.app as web
from kitden.demo import canned_refresh, no_sign_in

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


# The Official MCP Registry's answer to "weather": more than one page of results (PAGE = 60 in
# kitden.discovery), so the page has "Show 5 more" to show. Made up; no such servers exist.
WEATHER = [
    {
        "name": f"io.github.example/weather-{number:02}",
        "version": "1.0.0",
        "description": f"Weather forecasts, sample server {number}.",
        "remotes": [
            {"type": "streamable-http", "url": f"https://weather-{number:02}.example.test/mcp"}
        ],
    }
    for number in range(1, 66)
]
CATALOG[f"{REGISTRY}?search=weather&version=latest&limit=100"] = {
    "servers": [{"server": server, "_meta": ACTIVE} for server in WEATHER]
}

# The add panel's first read, before anything is typed: the registry's listing. Empty here, so
# the panel shows no row and no error (a refused read is a console error in the browser tests).
CATALOG[f"{REGISTRY}?search=&version=latest&limit=100"] = {"servers": []}

# What the page reads through these, as (module, name, value).
STAND_INS = [
    # No client command runs for its version. (The script used to set
    # kitden.clients.base.read_command_version, a name nothing reads.)
    (version_cache, "version_command", lambda client: None),
    (codex, "version_command", lambda client: None),
    (actions, "access_needed", no_sign_in),  # no server is asked for access
    (web, "refresh_tools", canned_refresh),  # tool lists without starting any server
    (discovery, "download", canned_download),  # catalogs answer from the tables above
    (discovery, "popular_skills", lambda: FOUND),
    (discovery, "access_needed", canned_access),
]
