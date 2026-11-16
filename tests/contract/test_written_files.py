"""The newest clients write their files in a sandbox home, and the parts Kitden reads keep
shapes a fixture knows. Run with: pytest -m contract

A failure means a client writes something no fixture knows, or stopped writing something: read
the sentences it prints and follow the steps in tests/fixtures/README.md. Set KITDEN_WRITTEN to
a folder to keep the files.

Each client installs the plugin from this repository's own marketplace files, as users do: it
clones the source they name on GitHub. A failure that names that clone is the network or a broken
source, not a shape. Then Kitden's own Library works on that plugin as users have it: it shows
it on, removes it, offers it again, installs it from the same source and undoes that.
"""

import json
import os
import tomllib
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.contract.conftest import need_command
from tests.contract.written import (
    MARKETPLACES,
    RECIPES,
    clone_failed,
    newest_fixture,
    parts,
    save,
    unknown,
)

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
PLUGIN = "kitden@kitden"


@pytest.mark.parametrize("client, name", [("claude_code", "claude"), ("codex", "codex")])
def test_the_newest_client_writes_only_shapes_the_fixtures_know(
    client, name, tmp_path, monkeypatch
):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    RECIPES[client](home, need_command(name, home), ROOT)
    if os.environ.get("KITDEN_WRITTEN"):
        save(home, client, Path(os.environ["KITDEN_WRITTEN"]))
    found = unknown(parts(home, client), parts(newest_fixture(client) / "home", client))
    assert found == [], "\n".join(found)

    # Kitden's own Library on the plugin installed from the real source (git-subdir on GitHub).
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        assert _cell(page, client) == "on"
        _check_enabled(home, client)

        _run(page, {"action": "plugin.remove", "targets": [_target(page, client)]})
        assert _cell(page, client) == "plugin.install"
        before = _files(home)

        # Kitden installs it from the same source: the client clones it again.
        body = {"action": "plugin.install", "targets": [{"client": client}]}
        body["params"] = {"plugin": PLUGIN}
        installed = _run(page, body, clone_failed(MARKETPLACES[client]))
        assert _cell(page, client) == "on"
        _check_enabled(home, client)

        _undo(page, installed)
        assert _cell(page, client) == "plugin.install"
        assert _files(home) == before


def _run(page, body: dict, why: str = "") -> str:
    """Preview and apply a change; its id."""
    preview = page.post("/api/changes/preview", json={"params": {}, **body}, headers=POST)
    assert preview.status_code == 200, preview.text
    change = preview.json()
    applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified", f"{why}{applied.get('error')}"
    return change["id"]


def _undo(page, change_id: str) -> None:
    undone = page.post(f"/api/changes/{change_id}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")


def _target(page, client: str) -> dict:
    items = page.get(f"/api/items?client={client}&kind=plugin&scope=user").json()
    return {"item": next(i["id"] for i in items if i["name"] == PLUGIN)}


def _cell(page, client: str) -> str:
    """What the client has in the plugin's Library row, or the add it offers."""
    rows = page.get("/api/library?kind=plugin&show=all").json()["rows"]
    cell = next(r for r in rows if r["offer"] == PLUGIN)["cells"][client]
    return cell["add"]["action"] if cell["add"] else cell["state"]


def _check_enabled(home: Path, client: str) -> None:
    if client == "codex":
        config = tomllib.loads((home / ".codex/config.toml").read_text())
        assert config["plugins"][PLUGIN] == {"enabled": True}
    else:
        settings = json.loads((home / ".claude/settings.json").read_text())
        assert settings["enabledPlugins"][PLUGIN] is True


def _files(home: Path) -> dict:
    """The files an install and its Undo change, without the empty tables a CLI leaves."""
    out = {}
    settings = home / ".claude/settings.json"
    if settings.is_file():
        out["settings"] = {k: v for k, v in json.loads(settings.read_text()).items() if v != {}}
    config = home / ".codex/config.toml"
    if config.is_file():
        out["config"] = config.read_bytes()
    return out
