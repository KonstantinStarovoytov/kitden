"""The plugin package Claude Code and Codex install (feature 003: FR-008 to FR-011, FR-015)."""

import json
from pathlib import Path

import kitden

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins/kitden"
ENTRY = {"type": "stdio", "command": "kitden", "args": ["mcp"]}


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_both_marketplaces_list_the_one_plugin():
    claude = _json(ROOT / ".claude-plugin/marketplace.json")
    codex = _json(ROOT / ".agents/plugins/marketplace.json")
    assert claude["name"] == codex["name"] == "kitden"
    assert [p["name"] for p in claude["plugins"]] == ["kitden"]
    assert [p["name"] for p in codex["plugins"]] == ["kitden"]
    assert claude["plugins"][0]["source"] == "./plugins/kitden"
    assert codex["plugins"][0]["source"] == {"source": "local", "path": "./plugins/kitden"}


def test_both_manifests_carry_the_package_version():
    claude = _json(PLUGIN / ".claude-plugin/plugin.json")
    portable = _json(PLUGIN / "plugin.json")
    assert claude["name"] == portable["name"] == "kitden"
    assert claude["version"] == portable["version"] == kitden.__version__
    assert portable["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert claude["license"] == portable["license"] == "Apache-2.0"


def test_both_mcp_files_hold_only_the_read_only_server():
    assert (PLUGIN / ".mcp.json").read_bytes() == (PLUGIN / "mcp.json").read_bytes()
    assert _json(PLUGIN / ".mcp.json") == {"mcpServers": {"kitden": ENTRY}}


def test_the_skill_states_the_four_rules():
    text = (PLUGIN / "skills/setup/SKILL.md").read_text()
    head, body = text.split("---\n")[1:3]
    assert "name: setup" in head
    assert "description: Use when" in head
    for rule in ("show_setup", "kitden open", "Never edit", "install line"):
        assert rule in body
    assert len(body.split()) < 200


def test_the_plugin_adds_nothing_that_runs_by_itself():
    for folder in ("hooks", "commands", "bin", "agents", "scripts"):
        assert not (PLUGIN / folder).exists()
    manifest = _json(PLUGIN / ".claude-plugin/plugin.json")
    assert not {"hooks", "commands", "mcpServers"} & manifest.keys()
