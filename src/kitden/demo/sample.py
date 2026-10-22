"""The sample home: a synthetic setup for `kitden demo` and for tests. No real client wrote it.

Each file has the shape the client of the matching fixture writes (`tests/fixtures`: Claude Code
2.1.283, Codex 0.159.2, Cursor 3.21.16). Every fake secret starts with `DEMO_SECRET_`. Paths
inside the files use the sample home's absolute path, and the same size always writes the same
files.
"""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from kitden.clients.cursor import INSTALLED_PREFIX, SNAPSHOT_PREFIX, STATE_DB, WORKSPACE_STATE
from kitden.gateways import data_dir
from kitden.local_gateway.settings import CALLS_FILE, SETTINGS_FILE, TOOLS_FILE

SIZES = ("small", "medium", "large")
DEMO_SECRET = "DEMO_SECRET_"  # noqa: S105 - the prefix of every fake secret
# The PATH the sample's gateway keeps, so a move into it never writes this computer's PATH.
SAMPLE_PATH = "/usr/local/bin:/usr/bin:/bin"
MARKET = "demo-market"
CURSOR_TEAM = "123"
UI_KIT_HASH = "9c1d2e3"  # the folder of the downloaded version, a commit hash in Cursor
WRITTEN_AT = "2026-10-01T00:00:00Z"
# Added to some names in the large sample, so the page always has a name to cut short.
LONG = "-with-a-name-long-enough-that-the-page-cuts-it-short"
BULK_TOOLS = (
    ("list_items", "List the items.", {"readOnlyHint": True}),
    ("get_item", "Show one item.", {"readOnlyHint": True}),
    ("create_item", "Add an item.", None),
    ("summarize", "Sum up the items.", None),
    ("delete_item", "Delete an item.", {"destructiveHint": True}),
    ("export_items", "Export the items.", None),
)


def demo_command(home: Path) -> str:
    """The `kitden` command the sample's entries run. Nothing runs it, and it does not exist."""
    return str(home / ".local/bin/kitden")


def keychain_file(home: Path) -> Path:
    """The file that stands in for the Keychain. It sits beside the home, so no scan reads it."""
    return home.parent / "keychain.json"


def build_demo_home(root: Path, size: str) -> Path:
    """Write the sample of this size in `root / "home"`, and its Keychain file. Fails when the
    home folder is there already."""
    if size not in SIZES:
        raise ValueError("Choose small, medium or large.")
    home = root / "home"
    home.mkdir(parents=True)
    medium = size != "small"
    _claude_code(home, medium)
    if medium:
        _codex(home)
        _cursor(home)
    _gateway(home, medium)
    if size == "large":
        _bulk(home)
    return home


def _json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _toml(value: str | list[str]) -> str:
    """A TOML string or list of strings: TOML writes them as JSON does, escapes too."""
    return json.dumps(value)


def _skill(folder: Path, name: str) -> None:
    _text(folder / name / "SKILL.md", f"---\nname: {name}\ndescription: A sample skill.\n---\n")


def _claude_code(home: Path, medium: bool) -> None:
    atlas, website = home / "work/atlas", home / "work/website"
    servers: dict[str, Any] = {
        "github": {
            "type": "http",
            "url": "https://api.github.example.test/mcp",
            "headers": {"Authorization": "Bearer DEMO_SECRET_GITHUB"},
        },
        "docs": {"type": "http", "url": "https://docs.example.test/mcp"},
    }
    projects: dict[str, Any] = {
        str(atlas): {
            "mcpServers": {},
            "enabledMcpjsonServers": ["docs"],
            "hasTrustDialogAccepted": True,
        }
    }
    if medium:
        servers["kitden"] = {"type": "stdio", "command": demo_command(home), "args": ["mcp"]}
        projects[str(atlas / "web")] = {"mcpServers": {}, "hasTrustDialogAccepted": True}
        projects[str(website)] = {
            "mcpServers": {
                "local-db": {"command": "uvx", "args": ["mcp-db", "--password", "DEMO_SECRET_DB"]}
            },
            "hasTrustDialogAccepted": True,
        }
        projects[str(home / "work/old-app")] = {"mcpServers": {}}  # its folder is gone
    _json(
        home / ".claude.json",
        {
            "numStartups": 12,
            "oauthAccount": {"emailAddress": "DEMO_SECRET_EMAIL"},
            "mcpServers": servers,
            "projects": projects,
        },
    )

    market = home / ".claude/plugins/marketplaces" / MARKET
    source = {"source": "directory", "path": str(market)}
    enabled = {f"superpowers@{MARKET}": True}
    settings: dict[str, Any] = {"enabledPlugins": enabled}
    if medium:
        enabled[f"pr-review@{MARKET}"] = False
        hook = {"type": "command", "command": "echo check"}
        settings["hooks"] = {"PreToolUse": [{"matcher": "Bash", "hooks": [hook]}]}
    settings["extraKnownMarketplaces"] = {MARKET: {"source": source}}
    _json(home / ".claude/settings.json", settings)

    plugins = home / ".claude/plugins"
    installed = {f"superpowers@{MARKET}": _claude_plugin(plugins, "superpowers", "7.0.0")}
    if medium:
        installed[f"pr-review@{MARKET}"] = _claude_plugin(plugins, "pr-review", "1.0.0")
    _json(plugins / "installed_plugins.json", {"version": 2, "plugins": installed})
    _json(
        plugins / "known_marketplaces.json",
        {MARKET: {"source": source, "installLocation": str(market), "lastUpdated": WRITTEN_AT}},
    )
    _marketplace(market)

    _skill(home / ".claude/skills", "brandkit")
    _skill(home / ".claude/skills", "release-notes")
    _text(
        home / ".claude/CLAUDE.md",
        "# My rules\n\nAnswer in short sentences.\ntoken: DEMO_SECRET_INSTRUCTIONS\n",
    )
    _text(atlas / "CLAUDE.md", "# Atlas\n\nRun `make test` before each commit.\n")
    if not medium:
        return

    _text(
        home / "shared/style/SKILL.md",
        "---\nname: shared-style\ndescription: A sample skill.\n---\n",
    )
    (home / ".claude/skills/shared-style").symlink_to("../../shared/style")
    _text(
        home / ".claude/commands/review.md",
        "---\ndescription: Review the current change\n---\nReview the diff for bugs.\n",
    )
    _text(
        home / ".claude/agents/reviewer.md",
        "---\nname: reviewer\ndescription: Reviews changes.\n---\nYou review code for bugs.\n",
    )
    _json(
        atlas / ".mcp.json",
        {"mcpServers": {"docs": {"type": "http", "url": "http://localhost:9000/mcp"}}},
    )
    (atlas / "web").mkdir()
    _json(website / ".claude/settings.json", {"enabledPlugins": {f"superpowers@{MARKET}": False}})


def _claude_plugin(plugins: Path, name: str, version: str) -> list[dict]:
    """A plugin in Claude Code's cache, and its record for installed_plugins.json."""
    folder = plugins / "cache" / MARKET / name / version
    _plugin_files(folder, name, version)
    return _record(folder, version)


def _record(folder: Path, version: str) -> list[dict]:
    """A user install of the plugin in `folder`, as installed_plugins.json keeps it."""
    return [
        {
            "scope": "user",
            "installPath": str(folder),
            "version": version,
            "installedAt": WRITTEN_AT,
            "lastUpdated": WRITTEN_AT,
        }
    ]


def _plugin_files(folder: Path, name: str, version: str) -> None:
    """A plugin folder: its manifest, and the skills or server it brings."""
    _json(folder / ".claude-plugin/plugin.json", {"name": name, "version": version})
    if name == "superpowers":
        _skill(folder / "skills", "brainstorming")
        _skill(folder / "skills", "planning")
    elif name == "pr-review":
        server = {"command": "node", "args": ["server.js"]}
        _json(folder / ".mcp.json", {"mcpServers": {"pr-index": server}})


def _marketplace(market: Path) -> None:
    """The local marketplace both clients know; its last two plugins are not installed."""
    offers = (
        ("superpowers", "7.0.0", "Skills for planning and brainstorming."),
        ("pr-review", "1.0.0", "Review pull requests."),
        ("test-helper", "1.2.0", "Write and run tests."),
        ("db-tools", "0.4.0", "Look into a database."),
    )
    for name, version, _ in offers:
        _plugin_files(market / "plugins" / name, name, version)
    _json(
        market / ".claude-plugin/marketplace.json",
        {
            "name": MARKET,
            "owner": {"name": "Demo"},
            "plugins": [
                {"name": name, "description": about, "source": f"./plugins/{name}"}
                for name, _, about in offers
            ],
        },
    )


def _codex(home: Path) -> None:
    atlas, sandbox = home / "work/atlas", home / "work/sandbox"
    market = home / ".claude/plugins/marketplaces" / MARKET
    _text(
        home / ".codex/config.toml",
        "[mcp_servers.docs]\n"
        'command = "npx"\n'
        'args = ["docs-mcp"]\n'
        "\n[mcp_servers.analytics]\n"
        'url = "https://analytics.example.test/mcp"\n'
        'http_headers = { Authorization = "Basic DEMO_SECRET_ANALYTICS" }\n'
        "\n[mcp_servers.sqlite]\n"
        'command = "uvx"\n'
        'args = ["mcp-server-sqlite"]\n'
        "enabled = false\n"
        "\n[mcp_servers.kitden]\n"
        f"command = {_toml(demo_command(home))}\n"
        'args = ["mcp"]\n'
        "startup_timeout_sec = 30\n"
        "tool_timeout_sec = 300\n"
        '\n[plugins."browser@openai-bundled"]\n'
        "enabled = true\n"
        f"\n[marketplaces.{MARKET}]\n"
        'source_type = "local"\n'
        f"source = {_toml(str(market))}\n"
        f"\n[projects.{_toml(str(atlas))}]\n"
        'trust_level = "trusted"\n'
        f"\n[projects.{_toml(str(sandbox))}]\n"
        'trust_level = "untrusted"\n',
    )
    browser = home / ".codex/plugins/cache/openai-bundled/browser/1.0.0"
    _json(browser / ".codex-plugin/plugin.json", {"name": "browser"})
    _text(home / ".codex/AGENTS.md", "# My Codex rules\n\nKeep answers short.\n")
    _text(atlas / "AGENTS.md", "# Atlas\n\nKeep each change small.\n")
    _skill(home / ".agents/skills", "code-review")
    _skill(home / ".agents/skills", "docker-expert")
    _skill(home / ".codex/skills", "langfuse")
    _skill(atlas / ".agents/skills", "api-style")
    # Not loaded: Codex does not trust this folder.
    _text(sandbox / ".codex/config.toml", '[mcp_servers.scratch]\ncommand = "curl"\n')


def _cursor(home: Path) -> None:
    atlas, website = home / "work/atlas", home / "work/website"
    _json(
        home / ".cursor/mcp.json",
        {
            "mcpServers": {
                "files": {"command": "npx", "args": ["files-mcp"]},
                "n8n": {
                    "command": "npx",
                    "args": ["n8n-mcp"],
                    "env": {"N8N_API_KEY": "DEMO_SECRET_N8N"},
                },
                "browser-tools": {"command": "npx", "args": ["browser-tools-mcp"]},
            }
        },
    )
    _skill(home / ".cursor/skills", "ui-polish")
    _json(
        home / ".cursor/hooks.json",
        {"version": 1, "hooks": {"afterFileEdit": [{"command": "./format.sh"}]}},
    )
    # Cut short: the file the page cannot read.
    _text(
        website / ".cursor/mcp.json",
        '{\n  "mcpServers": {\n    "site-db": {\n      "command": "uvx",\n',
    )
    _text(
        website / ".cursor/rules/style.mdc",
        "---\ndescription: Site style\nalwaysApply: true\n---\nUse plain CSS.\n",
    )

    ui_kit = home / ".cursor/plugins/cache/cursor-public/ui-kit" / UI_KIT_HASH
    _json(ui_kit / ".cursor-plugin/plugin.json", {"name": "ui-kit"})
    _skill(ui_kit / "skills", "ui-components")
    user = [{"id": "501", "sources": ["user"]}]
    _sqlite(
        home / STATE_DB,
        {
            f"{INSTALLED_PREFIX}{CURSOR_TEAM}|no-workspace": user,
            f"{INSTALLED_PREFIX}{CURSOR_TEAM}|{atlas.as_uri()}": user,
            f"{INSTALLED_PREFIX}{CURSOR_TEAM}|{website.as_uri()}": user,
            "mcpOAuth.files": {"access_token": "DEMO_SECRET_OAUTH"},
        },
    )
    # The snapshot that names plugin 501 (Cursor keeps no name for it elsewhere).
    snapshot = {
        "lastWrittenAt": 1792224000000,
        "descriptors": [
            {
                "id": "skill-1",
                "kind": "skill",
                "name": "ui-components",
                "scope": "plugin",
                "pluginId": "501",
                "marketplaceId": 34,
                "filePath": str(ui_kit / "skills/ui-components/SKILL.md"),
            }
        ],
    }
    workspace = home / WORKSPACE_STATE / "a1b2c3d4/state.vscdb"
    _sqlite(workspace, {f"{SNAPSHOT_PREFIX}skills.v3": snapshot})


def _sqlite(db: Path, rows: dict[str, Any]) -> None:
    """A Cursor state database with these key → value rows, values as JSON text."""
    db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as con, con:
        con.execute("CREATE TABLE ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
        con.executemany(
            "INSERT INTO ItemTable VALUES (?, ?)", [(k, json.dumps(v)) for k, v in rows.items()]
        )


def _tool(name: str, description: str, hints: dict | None = None) -> dict:
    """A tool as the gateway keeps it in its cache."""
    tool: dict[str, Any] = {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object"},
    }
    if hints:
        tool["annotations"] = hints
    return tool


def _gateway(home: Path, medium: bool) -> None:
    """Kitden's own data: the gateway's settings, its tool cache and call counts, and the
    Keychain stand-in. The small sample keeps only its PATH."""
    folder = data_dir(home)
    if not medium:
        _json(folder / SETTINGS_FILE, {"path": SAMPLE_PATH})
        _json(keychain_file(home), {})
        return
    atlas = str(home / "work/atlas")
    _json(
        folder / SETTINGS_FILE,
        {
            "path": SAMPLE_PATH,
            "servers": {
                "files": {
                    "command": "npx",
                    "args": ["files-mcp"],
                    "env": {"FILES_TOKEN": "DEMO_SECRET_FILES"},  # kept plain, not in Keychain
                },
                "tracker": {
                    "url": "https://tracker.example.test/mcp",
                    "headers": {"Authorization": {"keychain": "tracker/Authorization"}},
                },
            },
            "rules": {
                "global": {
                    "files": {"tools": {"delete_file": "off"}},
                    "tracker": {
                        "mode": "strict",
                        "tools": {"list_issues": "on", "create_issue": "on"},
                    },
                },
                "projects": {
                    atlas: {"files": {"tools": {"write_file": "off"}}},
                    f"{atlas}/web": {"files": {"tools": {"search_files": "off"}}},
                },
            },
        },
    )
    _json(
        folder / TOOLS_FILE,
        {
            "files": [
                _tool("read_file", "Read a file.", {"readOnlyHint": True}),
                _tool("write_file", "Write a file.", {"destructiveHint": True}),
                _tool("delete_file", "Delete a file."),
                _tool("search_files", "Find files by name."),
            ],
            "tracker": [
                _tool("list_issues", "List open issues.", {"readOnlyHint": True}),
                _tool("create_issue", "Open a new issue."),
                _tool("export_report", "Make a report of all issues."),
            ],
        },
    )
    _json(
        folder / CALLS_FILE,
        {
            "files": {
                "read_file": {"count": 12, "last": "2026-10-21T09:30Z"},
                "search_files": {"count": 3, "last": "2026-10-21T10:05Z"},
            },
            "tracker": {"list_issues": {"count": 5, "last": "2026-10-20T16:40Z"}},
        },
    )
    _json(keychain_file(home), {"kitden tracker/Authorization": "Bearer DEMO_SECRET_TRACKER"})


def _bulk(home: Path) -> None:
    """The large sample's extra items, written over the medium sample: 150 MCP servers (50 in
    each client), 30 Claude Code plugins, 120 skills, 12 projects, 10 held servers with their
    tools, and one Codex plugin whose on/off only Codex's plugin list knows. Some names are long
    (`LONG`). Nothing here holds a secret."""
    claude = json.loads((home / ".claude.json").read_text())
    cursor = json.loads((home / ".cursor/mcp.json").read_text())
    codex = []
    for n in range(150):
        name = f"bench-server-{n:03d}" + (LONG if n % 10 == 0 else "")
        remote = n % 2 == 1
        entry = (
            {"url": f"https://example.test/{name}"}
            if remote
            else {"command": "uvx", "args": [name]}
        )
        if n % 3 == 0:
            claude["mcpServers"][name] = {"type": "http", **entry} if remote else entry
        elif n % 3 == 1:
            fields = "".join(f"{key} = {_toml(value)}\n" for key, value in entry.items())
            codex.append(f"\n[mcp_servers.{name}]\n{fields}")
        else:
            cursor["mcpServers"][name] = entry
    for n in range(12):
        folder = home / "work" / (f"bench-project-{n:02d}" + (LONG if n % 4 == 0 else ""))
        server = f"bench-project-server-{n:02d}"
        _json(folder / ".mcp.json", {"mcpServers": {server: {"command": "uvx", "args": [server]}}})
        claude["projects"][str(folder)] = {
            "mcpServers": {},
            "enabledMcpjsonServers": [server],
            "hasTrustDialogAccepted": True,
        }
    _json(home / ".claude.json", claude)
    _json(home / ".cursor/mcp.json", cursor)
    with (home / ".codex/config.toml").open("a") as config:
        config.write("".join(codex))

    installed_file = home / ".claude/plugins/installed_plugins.json"
    installed = json.loads(installed_file.read_text())
    for n in range(30):
        name = f"plugin-{n:02d}"
        folder = home / ".claude/plugins/cache/bench-market" / name / "1.0.0"
        _json(folder / ".claude-plugin/plugin.json", {"name": name, "version": "1.0.0"})
        _skill(folder / "skills", f"{name}-skill")
        installed["plugins"][f"{name}@bench-market"] = _record(folder, "1.0.0")
    _json(installed_file, installed)

    folders = (".claude/skills", ".agents/skills", ".cursor/skills")
    for n in range(120):
        _skill(home / folders[n % 3], f"bench-skill-{n:03d}")

    settings_file, tools_file = data_dir(home) / SETTINGS_FILE, data_dir(home) / TOOLS_FILE
    settings, tools = json.loads(settings_file.read_text()), json.loads(tools_file.read_text())
    for n in range(10):
        name = f"bench-held-{n:02d}" + (LONG if n == 0 else "")
        remote = {"url": f"https://example.test/{name}"}
        settings["servers"][name] = remote if n % 2 else {"command": "uvx", "args": [name]}
        tools[name] = [_tool(*tool) for tool in BULK_TOOLS[: 4 + n % 3]]
    _json(settings_file, settings)
    _json(tools_file, tools)

    # In the cache with no config.toml entry: only `codex plugin list` knows whether it is on, so
    # a scan asks for that list (the slow step scripts/measure-start.py measures).
    calendar = home / ".codex/plugins/cache/openai-curated-remote/calendar"
    record = {"schema_version": 1, "remote_plugin_id": "plugin_demo_calendar"}
    _json(calendar / ".codex-remote-plugin-install.json", record)
    _json(calendar / "1.0.0/.codex-plugin/plugin.json", {"name": "calendar"})
