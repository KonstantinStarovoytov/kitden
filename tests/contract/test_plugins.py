"""Plugin on/off with the real clients in a sandbox home (T056, quickstart scenario 4).

Run with: pytest -m contract
"""

import json
import os
import subprocess

import pytest

import agentsetup.clients.base as base
from agentsetup.changes.actions import plugin_steps
from agentsetup.changes.backup import ChangeStore
from agentsetup.changes.client_cli import CommandRunner, find_command
from agentsetup.changes.engine import Engine
from agentsetup.changes.toml_edit import get_value
from agentsetup.model import ChangeState
from agentsetup.views.inventory import build_inventory, default_adapters
from tests.conftest import make_home

pytestmark = pytest.mark.contract
PLUGIN = "superpowers@claude-plugins-official"


@pytest.fixture
def home(tmp_path, monkeypatch):
    if find_command("claude", tmp_path) is None:
        pytest.skip("needs the claude command")
    for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    return make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2")


def _claude_plugins(home, cwd=None) -> dict:
    done = subprocess.run(  # noqa: S603 - fixed test command
        [find_command("claude", home), "plugin", "list", "--json"],
        env={**os.environ, "HOME": str(home)},
        cwd=cwd or home,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return {(p["id"], p["scope"]): p["enabled"] for p in json.loads(done.stdout)}


def _plugin(inventory, client, name, scope):
    return next(
        i
        for i in inventory.items
        if (i.client, i.name, str(i.scope), str(i.kind)) == (client, name, scope, "plugin")
    )


def test_claude_plugin_off_and_undo_with_the_real_cli(home):
    settings = home / ".claude/settings.json"
    original = settings.read_bytes()
    adapters = {a.id: a for a in default_adapters(home)}
    engine = Engine(ChangeStore(home / "data"), CommandRunner(home))
    item = _plugin(build_inventory(home), "claude_code", PLUGIN, "user")

    change = engine.preview("plugin.disable", plugin_steps(adapters, item, False))
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED, change.error
    assert _claude_plugins(home)[(PLUGIN, "user")] is False

    engine.undo(change.id)
    assert change.state is ChangeState.UNDONE
    assert settings.read_bytes() == original
    assert _claude_plugins(home)[(PLUGIN, "user")] is True


def test_claude_project_plugin_on_and_undo_with_the_real_cli(home):
    project_settings = home / "work/website/.claude/settings.json"
    original = project_settings.read_bytes()
    adapters = {a.id: a for a in default_adapters(home)}
    engine = Engine(ChangeStore(home / "data"), CommandRunner(home))
    item = _plugin(build_inventory(home), "claude_code", PLUGIN, "project")

    change = engine.preview("plugin.enable", plugin_steps(adapters, item, True))
    assert change.shared_file_warning
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED, change.error
    engine.undo(change.id)
    assert project_settings.read_bytes() == original


def test_codex_plugin_off_and_undo_in_the_sandbox(home):
    config = home / ".codex/config.toml"
    original = config.read_bytes()
    adapters = {a.id: a for a in default_adapters(home)}
    engine = Engine(ChangeStore(home / "data"), CommandRunner(home))
    item = _plugin(build_inventory(home), "codex", "browser@openai-bundled", "user")

    change = engine.preview("plugin.disable", plugin_steps(adapters, item, False))
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED, change.error
    assert get_value(config.read_text(), ("plugins", "browser@openai-bundled", "enabled")) is False
    engine.undo(change.id)
    assert config.read_bytes() == original
