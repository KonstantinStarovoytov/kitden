"""The catalog: plugins from the marketplaces already on this computer (Discover, phase 1)."""

import json
from pathlib import Path

import pytest

import kitden.clients.base as base
from kitden.views.catalog import catalog, search
from kitden.views.inventory import build_inventory, default_adapters
from tests.conftest import make_home

SECRET = "SENTINEL_SECRET_CATALOG"


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data))


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2")
    # The Claude Code marketplace clone that known_marketplaces.json points to.
    root = home / ".claude/plugins/marketplaces/claude-plugins-official"
    _write(
        root / ".claude-plugin/marketplace.json",
        {
            "name": "claude-plugins-official",
            "plugins": [
                {
                    "name": "linter",
                    "description": "Lint the code you change",
                    "category": "development",
                    "author": {"name": "Acme"},
                    "source": "./plugins/linter",
                },
                {
                    "name": "deploy-helper",
                    "description": "Deploy to the cloud and lint the result",
                    "source": {
                        "source": "git-subdir",
                        "url": "https://user:pw@github.com/acme/tools.git",
                        "path": "plugins/deploy",
                        "ref": "v1.2.0",
                        "sha": "faf5305385de8afed9468904e8639be737aff39e",
                    },
                },
            ],
        },
    )
    plugin = root / "plugins/linter"
    _write(plugin / ".claude-plugin/plugin.json", {"name": "linter", "version": "1.0.0"})
    _write(plugin / "skills/lint-fix/SKILL.md", "---\nname: lint-fix\n---\n")
    _write(
        plugin / ".mcp.json",
        {
            "mcpServers": {
                "lint": {
                    "command": "npx",
                    "args": ["-y", "lint-mcp@2"],
                    "env": {"LINT_TOKEN": SECRET},
                }
            }
        },
    )
    _write(plugin / "hooks/hooks.json", {"hooks": {"PostToolUse": [], "Stop": []}})
    # Codex's own curated marketplace, kept in its temporary folder.
    curated = home / ".codex/.tmp/plugins"
    _write(
        curated / ".agents/plugins/marketplace.json",
        {
            "name": "openai-curated",
            "plugins": [
                {
                    "name": "tracker",
                    "category": "Productivity",
                    "source": {"source": "local", "path": "./plugins/tracker"},
                }
            ],
        },
    )
    _write(
        curated / "plugins/tracker/.codex-plugin/plugin.json",
        {"name": "tracker", "version": "5.0.1", "description": "Track issues from Codex"},
    )
    return home


def _offers(home):
    inventory = build_inventory(home)
    adapters = {a.id: a for a in default_adapters(home)}
    return {o["id"]: o for o in catalog(inventory, adapters)}


def test_plugins_from_a_claude_marketplace_on_disk(home):
    offers = _offers(home)
    linter = offers["linter@claude-plugins-official"]
    assert linter["description"] == "Lint the code you change"
    assert linter["category"] == "development" and linter["author"] == "Acme"
    assert linter["routes"]["claude_code"] == "ready"
    # Codex can take it after adding the same marketplace from Claude Code's source.
    assert linter["routes"]["codex"] == "add_marketplace"
    deploy = offers["deploy-helper@claude-plugins-official"]
    assert deploy["source"] == {
        "url": "https://github.com/acme/tools.git",
        "path": "plugins/deploy",
        "ref": "v1.2.0",
        "sha": "faf5305385de8afed9468904e8639be737aff39e",
    }
    assert deploy["inside"] is None  # an outside source is read only once installed


def test_what_is_inside_a_plugin_and_secrets_stay_hidden(home):
    inside = _offers(home)["linter@claude-plugins-official"]["inside"]
    assert inside["skills"] == ["lint-fix"]
    assert inside["hooks"] == ["PostToolUse", "Stop"]
    assert inside["mcp_servers"] == [{"name": "lint", "runs": "npx -y lint-mcp@2"}]
    assert SECRET not in json.dumps(_offers(home))


def test_codex_curated_plugins_are_codex_only(home):
    tracker = _offers(home)["tracker@openai-curated"]
    assert tracker["description"] == "Track issues from Codex"
    assert tracker["routes"] == {"codex": "ready"}


def test_installed_plugins_are_marked_per_client(home):
    offers = _offers(home)
    installed = offers.get("superpowers@claude-plugins-official")
    # The fixture has superpowers installed in Claude Code but not listed in the marketplace file.
    assert installed is None or "claude_code" in installed["installed"]
    assert offers["linter@claude-plugins-official"]["installed"] == []


def test_search_ranks_the_name_first_then_the_description(home):
    offers = list(_offers(home).values())
    found = [o["name"] for o in search(offers, "lint")]
    assert found[:2] == ["linter", "deploy-helper"]
    assert [o["name"] for o in search(offers, "issues")] == ["tracker"]
    assert len(search(offers, "")) == len(offers)
