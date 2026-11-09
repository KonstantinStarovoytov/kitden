"""The plugin package Claude Code and Codex install (feature 003: FR-008 to FR-011, FR-015)."""

import json
from pathlib import Path

import kitden

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins/kitden"
ENTRY = {"type": "stdio", "command": "kitden", "args": ["mcp"]}
INSTALL = "uv tool install --python 3.13 kitden"


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
    for rule in ("show_setup", "kitden open", "Never edit", "kitden --version", INSTALL):
        assert rule in body
    assert len(body.split()) < 200


def test_the_skill_description_names_what_users_ask_about():
    head = (PLUGIN / "skills/setup/SKILL.md").read_text().split("---\n")[1]
    for word in ("MCP servers", "skills", "plugins", "hooks", "CLAUDE.md", "Codex", "Cursor"):
        assert word in head
    # A change request must reach the skill, so the agent sends the user to the page.
    assert "turn one on or off" in head and "remove" in head


def test_the_audit_skill_suggests_and_changes_nothing():
    text = (PLUGIN / "skills/audit/SKILL.md").read_text()
    head, body = text.split("---\n")[1:3]
    assert "name: audit" in head
    assert "description: Use when" in head
    for word in ("turn off", "audit", "context"):
        assert word in head
    for rule in ("show_setup", "list_findings", "kitden open", "Never edit", "not sure"):
        assert rule in body
    # Kitden's tools do not count use, and the skill must say what it judges by.
    assert "how often" in body
    # The whole setup is too large for one answer; some items only their client can change.
    for field in ("`client`", "explain_item", "`actions`", "`change_hint`"):
        assert field in body
    assert len(body.split()) < 300


def test_the_readmes_say_what_the_server_and_the_plugin_each_give():
    plugin = (PLUGIN / "README.md").read_text()
    for words in ("## What the MCP server gives", "## What the plugin adds", "`setup`", "`audit`"):
        assert words in plugin
    readme = (ROOT / "README.md").read_text()
    assert "| **MCP server** |" in readme and "| **Plugin** |" in readme
    assert "/kitden:audit" in readme


def test_the_install_line_is_the_one_in_the_readme():
    assert INSTALL in (ROOT / "README.md").read_text()
    assert INSTALL in (PLUGIN / "README.md").read_text()


def test_every_description_says_kitden_must_be_installed():
    texts = {
        _json(PLUGIN / ".claude-plugin/plugin.json")["description"],
        _json(PLUGIN / "plugin.json")["description"],
        _json(ROOT / ".claude-plugin/marketplace.json")["plugins"][0]["description"],
    }
    assert len(texts) == 1
    assert "Needs Kitden installed" in texts.pop()


def test_the_plugin_adds_nothing_that_runs_by_itself():
    for folder in ("hooks", "commands", "bin", "agents", "scripts"):
        assert not (PLUGIN / folder).exists()
    manifest = _json(PLUGIN / ".claude-plugin/plugin.json")
    assert not {"hooks", "commands", "mcpServers"} & manifest.keys()


def test_the_guide_cursor_link_adds_the_same_server():
    """FR-012: the "Add to Cursor" link carries the entry of .mcp.json, without the type field."""
    import base64
    import re

    readme = (ROOT / "docs/guide.md").read_text()
    configs = re.findall(r"install-mcp\?name=kitden&config=([A-Za-z0-9+/=]+)", readme)
    deeplink = (
        r"cursor://anysphere\.cursor-deeplink/mcp/install\?name=kitden&config=([A-Za-z0-9+/=]+)"
    )
    plain = re.findall(deeplink, readme)
    assert configs and plain, "the guide has the button link and the plain link"
    for config in {*configs, *plain}:
        decoded = json.loads(base64.b64decode(config))
        assert decoded == {"command": ENTRY["command"], "args": ENTRY["args"]}
