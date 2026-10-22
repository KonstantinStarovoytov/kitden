"""The Library with the real clients in a sandbox home: add a marketplace, install a plugin in
Claude Code and Codex in one review, then Undo both. Run with: pytest -m contract

The marketplace is this repository's folder, so nothing is downloaded. The real home folder is
never touched.
"""

import json
import tomllib
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kitden.changes.client_cli import find_command
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    if find_command("claude", tmp_path) is None or find_command("codex", tmp_path) is None:
        pytest.skip("needs the claude and codex commands")
    for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        monkeypatch.delenv(name, raising=False)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2")
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        c.home = home
        yield c


def _run(client, body):
    preview = client.post("/api/changes/preview", json=body, headers=POST)
    assert preview.status_code == 200, preview.text
    change = preview.json()
    applied = client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified", applied.get("error")
    return change["id"]


def _cells(client, plugin):
    """The plugin's Library cells: what each client has, or the add it offers."""
    rows = client.get("/api/library?kind=plugin&show=all").json()["rows"]
    row = next(r for r in rows if r["offer"] == plugin)
    return {
        c: cell["add"]["action"] if cell["add"] else cell["state"]
        for c, cell in row["cells"].items()
    }


def _settings(home):
    data = json.loads((home / ".claude/settings.json").read_text())
    return {k: v for k, v in data.items() if v != {}}  # the CLI leaves empty tables behind


def test_add_a_marketplace_and_a_plugin_to_both_clients_then_undo(client):
    home = client.home
    settings = _settings(home)
    config = (home / ".codex/config.toml").read_bytes()
    both = [{"client": "claude_code"}, {"client": "codex"}]

    added = _run(
        client, {"action": "marketplace.add", "targets": both, "params": {"source": str(ROOT)}}
    )
    assert _cells(client, "kitden@kitden") == {
        "claude_code": "plugin.install",
        "codex": "plugin.install",
    }

    installed = _run(
        client, {"action": "plugin.install", "targets": both, "params": {"plugin": "kitden@kitden"}}
    )
    assert _cells(client, "kitden@kitden") == {"claude_code": "on", "codex": "on"}
    assert tomllib.loads((home / ".codex/config.toml").read_text())["plugins"]["kitden@kitden"] == {
        "enabled": True
    }

    for change_id in (installed, added):
        undone = client.post(f"/api/changes/{change_id}/undo", headers=POST).json()
        assert undone["state"] == "undone", undone.get("error")
    assert (home / ".codex/config.toml").read_bytes() == config
    assert _settings(home) == settings
