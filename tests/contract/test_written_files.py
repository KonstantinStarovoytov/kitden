"""The newest clients write their files in a sandbox home, and the parts Kitden reads keep
shapes a fixture knows. Run with: pytest -m contract

A failure means a client writes something no fixture knows, or stopped writing something: read
the sentences it prints and follow the steps in tests/fixtures/README.md. Set KITDEN_WRITTEN to
a folder to keep the files.
"""

import os
from pathlib import Path

import pytest

from tests.contract.conftest import need_command
from tests.contract.written import RECIPES, newest_fixture, parts, save, unknown

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


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
