"""What an installed plugin holds: its skills, commands, agents, hooks and MCP server names."""

import os

from kitden.demo import build_demo_home
from kitden.views import catalog
from kitden.views.catalog import installed_inside
from kitden.views.inventory import default_adapters


def _adapters(home):
    return {a.id: a for a in default_adapters(home)}


def test_installed_inside_lists_what_each_installed_plugin_holds(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    held = installed_inside(_adapters(home))
    superpowers = held[next(i for i in held if i.startswith("superpowers@"))]
    assert superpowers["skills"] == ["brainstorming", "planning"]
    assert superpowers["mcp_servers"] == []
    review = held[next(i for i in held if i.startswith("pr-review@"))]
    assert review["mcp_servers"] == ["pr-index"]
    assert review["skills"] == []


def test_installed_inside_reads_each_folder_once_until_it_changes(tmp_path, monkeypatch):
    home = build_demo_home(tmp_path, "medium")
    adapters = _adapters(home)
    held = installed_inside(adapters)
    reads = []
    real = catalog._inside
    monkeypatch.setattr(catalog, "_inside", lambda *a: reads.append(a[0]) or real(*a))
    installed_inside(adapters)
    assert reads == []
    plugin_id = next(i for i in held if i.startswith("pr-review@"))
    folder = adapters["claude_code"].plugin_folders()[plugin_id]
    server_file = folder / ".mcp.json"
    server_file.write_text(server_file.read_text().replace("pr-index", "pr-search"))
    stamp = server_file.stat().st_mtime_ns + 5_000_000_000
    os.utime(server_file, ns=(stamp, stamp))
    assert installed_inside(adapters)[plugin_id]["mcp_servers"] == ["pr-search"]
    assert reads == [folder]


def test_installed_inside_keeps_no_command_lines(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    held = installed_inside(_adapters(home))
    for part in held.values():
        assert set(part) == {"skills", "commands", "agents", "hooks", "mcp_servers"}
        assert all(isinstance(name, str) for name in part["mcp_servers"])
    assert "node" not in str(held) and "server.js" not in str(held)


def test_installed_inside_reads_codex_and_cursor_plugins_too(tmp_path):
    held = installed_inside(_adapters(build_demo_home(tmp_path, "medium")))
    assert any(i.endswith("@openai-bundled") for i in held)
    assert any(i.endswith("@cursor-public") for i in held)
