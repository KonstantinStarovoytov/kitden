"""Flow 10: "Add to Cursor…" and "Add to Codex…" copy a Claude Code server whose header
names a variable; each client's file keeps the variable, never a value."""

import json
import tomllib

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import open_outside, wait_until

pytestmark = pytest.mark.browser

SERVER = "notes"
HEADER = "Bearer ${KITDEN_TEST_TOKEN}"
# The variable's value while the page runs (in this process): no client's file may get it.
TOKEN = "kitden-secret-4f9c2e"


@pytest.fixture
def before_start(monkeypatch):
    """A user-scope server in Claude Code with a `${VAR}` header: the sample has none. The
    variable is set, so a copy that put in its value would show."""
    monkeypatch.setenv("KITDEN_TEST_TOKEN", TOKEN)

    def add(home):
        path = home / ".claude.json"
        data = json.loads(path.read_text())
        data["mcpServers"][SERVER] = {
            "type": "http",
            "url": "https://notes.example.test/mcp",
            "headers": {"Authorization": HEADER},
        }
        path.write_text(json.dumps(data, indent=2) + "\n")

    return add


def add_to(page, client: str) -> None:
    details = open_outside(page, SERVER, "Claude Code")
    details.get_by_role("button", name="More").click()
    details.get_by_role("button", name=f"Add to {client}…").click()
    page.locator("#dock").get_by_role("button", name="Apply").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()


def test_a_server_added_to_cursor_keeps_its_variable(page, demo):
    cursor = demo.home / ".cursor/mcp.json"
    add_to(page, "Cursor")
    wait_until(lambda: SERVER in json.loads(cursor.read_text())["mcpServers"])
    entry = json.loads(cursor.read_text())["mcpServers"][SERVER]
    # Cursor's own spelling of the same variable.
    assert entry == {
        "url": "https://notes.example.test/mcp",
        "headers": {"Authorization": "Bearer ${env:KITDEN_TEST_TOKEN}"},
    }
    assert TOKEN not in cursor.read_text()


def test_a_server_added_to_codex_keeps_its_variable(page, demo):
    codex = demo.home / ".codex/config.toml"
    add_to(page, "Codex")
    wait_until(lambda: SERVER in tomllib.loads(codex.read_text())["mcp_servers"])
    entry = tomllib.loads(codex.read_text())["mcp_servers"][SERVER]
    # Codex names the variable that holds the bearer token.
    assert entry == {
        "url": "https://notes.example.test/mcp",
        "bearer_token_env_var": "KITDEN_TEST_TOKEN",
    }
    assert TOKEN not in codex.read_text()
