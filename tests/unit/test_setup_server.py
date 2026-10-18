"""Adding the read-only setup server to clients (T060, FR-032)."""

import json

import pytest

import kitden.clients.base as base
from kitden.changes.actions import setup_server_steps
from kitden.views.inventory import default_adapters
from tests.conftest import make_home

COMMAND = "/Users/me/.local/bin/kitden"


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


def test_each_client_gets_a_stdio_entry_with_the_absolute_path(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2")
    adapters = {a.id: a for a in default_adapters(home)}
    steps = {
        s.client: s
        for s in setup_server_steps(adapters, ["claude_code", "codex", "cursor"], COMMAND)
    }

    claude = steps["claude_code"]
    value = {"type": "stdio", "command": COMMAND, "args": ["mcp"]}
    assert claude.command == [
        "claude",
        "mcp",
        "add-json",
        "-s",
        "user",
        "kitden",
        json.dumps(value),
    ]
    assert claude.edit.after == value
    assert steps["codex"].edit.after == {"command": COMMAND, "args": ["mcp"]}
    assert steps["codex"].edit.key == ("mcp_servers", "kitden")
    assert steps["cursor"].edit.after == {"command": COMMAND, "args": ["mcp"]}
    assert all(s.restart_note for s in steps.values())


def test_a_relative_command_is_refused(tmp_path):
    home = make_home(tmp_path, "codex/0.159.2")
    adapters = {a.id: a for a in default_adapters(home)}
    with pytest.raises(ValueError, match="absolute"):
        setup_server_steps(adapters, ["codex"], "kitden")
