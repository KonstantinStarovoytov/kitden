"""The plugin package Claude Code and Codex install (feature 003: FR-008 to FR-011, FR-015)."""

import json
import re
import struct
from pathlib import Path

import kitden
from kitden import cli, mcp_server

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins/kitden"
SKILLS = ("audit", "before-install", "context", "install", "open", "show-setup")
# `kitden show` came with this version: the skills run it.
NEEDS = "0.7.2"
UPGRADE = "uv tool upgrade kitden"
INSTALL = "uv tool install --python 3.13 kitden"
BREW = "brew install konstantinstarovoytov/tap/kitden"
# The skills and the MCP server say this in the same words.
NO_EDITS = "Do not edit client settings files"


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_both_marketplaces_list_the_one_plugin():
    claude = _json(ROOT / ".claude-plugin/marketplace.json")
    codex = _json(ROOT / ".agents/plugins/marketplace.json")
    assert claude["name"] == codex["name"] == "kitden"
    assert [p["name"] for p in claude["plugins"]] == ["kitden"]
    assert [p["name"] for p in codex["plugins"]] == ["kitden"]
    # Both read the plugin from the `release` branch, so people get only released plugins.
    assert claude["plugins"][0]["source"] == {
        "source": "git-subdir",
        "url": "KonstantinStarovoytov/kitden",
        "path": "plugins/kitden",
        "ref": "release",
    }
    assert codex["plugins"][0]["source"] == {
        "source": "git-subdir",
        "url": "https://github.com/KonstantinStarovoytov/kitden.git",
        "path": "./plugins/kitden",
        "ref": "release",
    }


def test_both_manifests_carry_the_package_version():
    claude = _json(PLUGIN / ".claude-plugin/plugin.json")
    portable = _json(PLUGIN / "plugin.json")
    assert claude["name"] == portable["name"] == "kitden"
    assert claude["version"] == portable["version"] == kitden.__version__
    assert portable["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert claude["license"] == portable["license"] == "Apache-2.0"


def test_the_listing_links_to_the_guide_and_the_privacy_page():
    # Anthropic's directory shows these two links on the plugin's card.
    claude = _json(PLUGIN / ".claude-plugin/plugin.json")
    pages = "https://github.com/KonstantinStarovoytov/kitden/blob/main/"
    assert claude["documentationUrl"] == pages + "docs/guide.md"
    assert claude["privacyPolicyUrl"] == pages + "PRIVACY.md"
    privacy = " ".join((ROOT / "PRIVACY.md").read_text().split())
    for words in ("no telemetry", "no account", "[secret]", "your agent"):
        assert words in privacy


def _skill(name: str) -> tuple[str, str]:
    """A skill's head and body."""
    head, body = (PLUGIN / f"skills/{name}/SKILL.md").read_text().split("---\n")[1:3]
    assert f"name: {name}\n" in head
    assert "description: Use when" in head
    return head, body


def test_the_plugin_has_no_mcp_server():
    # Anthropic's directory holds a plugin that starts a local server (Validate, 2026-11-10), so
    # the skills run the `kitden` command instead.
    assert not (PLUGIN / ".mcp.json").exists() and not (PLUGIN / "mcp.json").exists()
    assert "mcpServers" not in _json(PLUGIN / ".claude-plugin/plugin.json")


def test_the_plugin_holds_these_skills_and_each_is_short():
    assert sorted(p.name for p in (PLUGIN / "skills").iterdir()) == list(SKILLS)
    for name in SKILLS:
        assert len(_skill(name)[1].split()) < 300, name


def test_the_skills_run_only_commands_kitden_has():
    asked = set()
    for name in SKILLS:
        asked |= set(re.findall(r"kitden show (\w+)", _skill(name)[1]))
    assert asked == set(cli.SHOW)


def test_every_skill_that_runs_kitden_sends_a_missing_kitden_to_the_install_skill():
    for name in SKILLS:
        if name != "install":
            assert "kitden `install` skill" in _skill(name)[1], name


def test_the_show_setup_skill_reads_and_sends_changes_to_the_page():
    head, body = _skill("show-setup")
    for word in ("MCP servers", "skills", "plugins", "hooks", "CLAUDE.md", "Codex", "Cursor"):
        assert word in head
    # A change request must reach the skill, so the agent sends the user to the page.
    assert "turn one on or off" in head and "remove" in head and "comes from" in head
    rules = ("kitden show setup", "--client", "kitden show findings", "kitden show item")
    for rule in (*rules, "kitden show projects", "kitden open", NO_EDITS):
        assert rule in body
    assert len(body.split()) < 200


def test_the_audit_skill_suggests_and_changes_nothing():
    head, body = _skill("audit")
    for word in ("turn off", "audit", "context"):
        assert word in head
    rules = ("kitden show setup", "kitden show findings", "kitden open", NO_EDITS, "not sure")
    for rule in rules:
        assert rule in body
    # Kitden does not count use, and the skill must say what it judges by.
    assert "how often" in body
    # The whole setup is too large for one answer; some items only their client can change.
    for field in ("--client", "kitden show item", "`actions`", "`change_hint`"):
        assert field in body


def test_the_install_skill_asks_first_and_names_each_way():
    head, body = _skill("install")
    assert "install" in head and "update" in head and "not found" in head
    for rule in ("kitden --version", NEEDS, INSTALL, UPGRADE, BREW, "brew upgrade kitden"):
        assert rule in body
    assert "uvx --python 3.13 kitden" in body
    # No line that downloads a script and runs it: without uv or Homebrew the user gets a link.
    assert "curl" not in body and "| sh" not in body
    assert "https://github.com/KonstantinStarovoytov/kitden#get-started" in body
    # Nothing is installed without the user's yes.
    assert "Ask" in body and "Without a yes" in body
    assert body.index("Ask") < body.index(INSTALL)
    # Kitden does not run on Windows: the skill says so and stops before any command.
    assert "On Windows" in body and "stop" in body
    assert body.index("On Windows") < body.index("kitden --version")


def test_the_context_skill_says_what_kitden_measured():
    head, body = _skill("context")
    for word in ("skills fit", "context", "description"):
        assert word in head
    for rule in ("kitden show context", "`say`", "`over`", "`how`", "Estimate", "kitden open"):
        assert rule in body
    assert NO_EDITS in body


def test_the_before_install_skill_looks_and_installs_nothing():
    head, body = _skill("before-install")
    for word in ("add", "install", "already"):
        assert word in head
    for rule in ("kitden show item", "kitden show setup", "`loads`", "`why`", "`summary`"):
        assert rule in body
    assert "do not add it" in body


def test_the_open_skill_opens_the_page():
    head, body = _skill("open")
    assert "open" in head and "Kitden" in head
    assert "`kitden open`" in body and "link" in body


def test_the_readmes_say_what_the_plugin_gives():
    plugin = (PLUGIN / "README.md").read_text()
    for name in SKILLS:
        assert f"`{name}`" in plugin, name
    readme = (ROOT / "README.md").read_text()
    assert "| **MCP server** |" in readme and "| **Plugin** |" in readme
    assert "/kitden:audit" in readme and "/kitden:context" in readme


def test_the_plugin_readme_says_what_the_plugin_runs_and_needs():
    text = (PLUGIN / "README.md").read_text()
    # What it runs: the kitden command, which only reads here. No server, and it says so.
    assert "`kitden show`" in text and "no MCP server" in text
    assert "kitden mcp" not in text
    # It offers the install and never runs it unasked.
    assert "asks before" in text and BREW in text
    # What a reviewer and a new user look for.
    headings = ("## What the skills do", "## Try it", "## What it reads")
    for heading in (*headings, "## If something goes wrong", "## Install and remove"):
        assert heading in text
    assert NEEDS in text and UPGRADE in text
    assert "https://github.com/KonstantinStarovoytov/kitden/issues" in text
    assert "https://pypi.org/project/kitden/" in text


def test_the_install_line_is_the_one_in_the_readme():
    assert INSTALL in (ROOT / "README.md").read_text()
    assert INSTALL in (PLUGIN / "README.md").read_text()


def test_every_description_says_it_uses_kitden_and_offers_the_install():
    texts = {
        _json(PLUGIN / ".claude-plugin/plugin.json")["description"],
        _json(PLUGIN / "plugin.json")["description"],
        _json(ROOT / ".claude-plugin/marketplace.json")["plugins"][0]["description"],
    }
    assert len(texts) == 1
    text = texts.pop()
    assert "Kitden program" in text and "offers to install" in text


def test_the_plugin_adds_nothing_that_runs_by_itself():
    for folder in ("hooks", "commands", "bin", "agents", "scripts"):
        assert not (PLUGIN / folder).exists()
    manifest = _json(PLUGIN / ".claude-plugin/plugin.json")
    assert not {"hooks", "commands", "mcpServers"} & manifest.keys()


def test_the_guide_cursor_link_adds_the_same_server():
    """FR-012: the "Add to Cursor" link adds the whole server, gateway tools too."""
    import base64

    readme = (ROOT / "docs/guide.md").read_text()
    configs = re.findall(r"install-mcp\?name=kitden&config=([A-Za-z0-9+/=]+)", readme)
    deeplink = (
        r"cursor://anysphere\.cursor-deeplink/mcp/install\?name=kitden&config=([A-Za-z0-9+/=]+)"
    )
    plain = re.findall(deeplink, readme)
    assert configs and plain, "the guide has the button link and the plain link"
    for config in {*configs, *plain}:
        decoded = json.loads(base64.b64decode(config))
        assert decoded == {"command": "kitden", "args": ["mcp"]}


def test_the_skills_and_the_server_forbid_edits_in_the_same_words():
    assert NO_EDITS in mcp_server.NO_EDITS


def test_the_plugin_has_an_icon_the_directory_accepts():
    # The directory reads `icon` from .claude-plugin/plugin.json: a path to an image in the plugin.
    # It accepts PNG; files must stay under 5 MiB. Checked 2026-11-09:
    # https://code.claude.com/docs/en/plugins-reference#directory-listing-fields
    manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
    assert manifest["icon"] == "./icon.png"
    data = (PLUGIN / "icon.png").read_bytes()
    assert len(data) < 5 * 1024 * 1024
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert width == height and 512 <= width <= 2048
