"""Installing the kitden plugin with the real clients in sandbox homes (feature 003, quickstart
§4 and §5). Run with: pytest -m contract

Each test adds the repository as a marketplace, installs the plugin, checks what the client
recorded, and removes everything again. The real home folder is never touched.
"""

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

import kitden.clients.base as base
from kitden.changes.client_cli import find_command
from kitden.views.inventory import build_inventory
from kitden.views.setup_server import setup_server_state
from tests.conftest import make_home
from tests.contract.test_mcp_handshake import CODEX_APP

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]
ENTRY = json.loads((ROOT / "plugins/kitden/.mcp.json").read_text())["mcpServers"]["kitden"]


@pytest.fixture
def home(tmp_path, monkeypatch):
    for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    return make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2")


def _run(binary: str, args: list[str], home: Path, env: dict | None = None) -> str:
    done = subprocess.run(  # noqa: S603 - fixed client command, no shell
        [binary, *args],
        env={**os.environ, "HOME": str(home), **(env or {})},
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, f"{args}: {done.stdout}\n{done.stderr}"
    return done.stdout


def _state(home: Path, client: str) -> str:
    states = setup_server_state(build_inventory(home))
    return next(s["state"] for s in states if s["client"] == client)


def test_claude_code_installs_the_plugin_from_the_repository(home):
    claude = find_command("claude", home)
    if claude is None:
        pytest.skip("needs the claude command")
    settings = home / ".claude/settings.json"
    before = json.loads(settings.read_text())
    _run(claude, ["plugin", "validate", "--strict", "./plugins/kitden"], home)
    _run(claude, ["plugin", "validate", "--strict", "."], home)

    _run(claude, ["plugin", "marketplace", "add", str(ROOT)], home)
    _run(claude, ["plugin", "install", "kitden@kitden", "--scope", "user"], home)
    listed = {p["id"]: p for p in json.loads(_run(claude, ["plugin", "list", "--json"], home))}
    assert listed["kitden@kitden"]["enabled"] is True
    assert listed["kitden@kitden"]["mcpServers"] == {"kitden": ENTRY}
    assert Path(listed["kitden@kitden"]["installPath"], "skills/setup/SKILL.md").is_file()
    assert _state(home, "claude_code") == "plugin"

    _run(claude, ["plugin", "uninstall", "kitden@kitden"], home)
    _run(claude, ["plugin", "marketplace", "remove", "kitden"], home)
    after = json.loads(settings.read_text())
    assert "kitden@kitden" not in after.get("enabledPlugins", {})
    assert "kitden" not in after.get("extraKnownMarketplaces", {})
    for key, value in before.items():
        if key not in ("enabledPlugins", "extraKnownMarketplaces"):
            assert after[key] == value, key
    assert _state(home, "claude_code") == "missing"


def test_codex_installs_the_plugin_from_the_repository(home):
    codex = shutil.which("codex") or (CODEX_APP if os.path.exists(CODEX_APP) else None)
    if codex is None:
        pytest.skip("needs the codex command")
    env = {"CODEX_HOME": str(home / ".codex")}
    config = home / ".codex/config.toml"
    before = tomllib.loads(config.read_text())

    add = ["plugin", "marketplace", "add", str(ROOT), "--json"]
    added = json.loads(_run(codex, add, home, env))
    assert added["marketplaceName"] == "kitden"
    installed = json.loads(_run(codex, ["plugin", "add", "kitden@kitden", "--json"], home, env))
    assert installed["pluginId"] == "kitden@kitden" and installed["version"] == "0.1.0"
    copied = Path(installed["installedPath"])
    assert copied.is_relative_to(home / ".codex/plugins/cache")
    assert (copied / "mcp.json").read_bytes() == (ROOT / "plugins/kitden/mcp.json").read_bytes()
    assert (copied / "skills/setup/SKILL.md").is_file()
    assert tomllib.loads(config.read_text())["plugins"]["kitden@kitden"] == {"enabled": True}
    items = build_inventory(home).items
    plugins = {i.name for i in items if i.client == "codex" and str(i.kind) == "plugin"}
    assert "kitden@kitden" in plugins
    assert _state(home, "codex") == "plugin"

    _run(codex, ["plugin", "remove", "kitden@kitden"], home, env)
    _run(codex, ["plugin", "marketplace", "remove", "kitden"], home, env)
    after = tomllib.loads(config.read_text())
    assert "kitden@kitden" not in after.get("plugins", {})
    assert "kitden" not in after.get("marketplaces", {})
    assert _state(home, "codex") == "missing"
    for key, value in before.items():
        if key not in ("plugins", "marketplaces"):
            assert after[key] == value, key
