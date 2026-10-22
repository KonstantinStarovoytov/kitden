"""A Claude Code entry that holds a secret is written to ~/.claude.json directly, so the secret
never sits in a process's arguments, where `ps` shows it."""

import json

import pytest

from kitden.changes.backup import ChangeStore
from kitden.changes.engine import Engine
from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.model import ChangeState

TOKEN = "SENTINEL_SECRET_ARGS"  # noqa: S105 - test value
SECRET_ENTRY = {"command": "npx", "args": ["files-mcp"], "env": {"FILES_TOKEN": TOKEN}}
PLAIN_ENTRY = {"type": "http", "url": "https://mcp.neon.tech/mcp"}
REFERENCE_ENTRY = {"type": "http", "url": "https://x.test/mcp", "headers": {"X-Key": "${KEY}"}}


@pytest.fixture
def home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    state = {
        "numStartups": 7,
        "projects": {"/p": {"x": 1}},
        "mcpServers": {"old": {"command": "x"}},
    }
    (home / ".claude.json").write_text(json.dumps(state, indent=2))
    return home


def test_an_entry_with_a_secret_is_a_direct_edit_without_a_command(home):
    step = ClaudeCodeAdapter(home).add_server_step("files", SECRET_ENTRY)
    assert step.command is None
    assert step.mechanism == "format_preserving_edit"
    edit = step.edit
    assert (edit.path, edit.fmt, edit.key, edit.after, edit.check) == (
        str(home / ".claude.json"),
        "json",
        ("mcpServers", "files"),
        SECRET_ENTRY,
        "entry",
    )


@pytest.mark.parametrize("entry", [PLAIN_ENTRY, REFERENCE_ENTRY])
def test_an_entry_without_a_secret_still_uses_add_json(home, entry):
    step = ClaudeCodeAdapter(home).add_server_step("neon", entry)
    assert step.mechanism == "client_cli"
    assert step.command[:6] == ["claude", "mcp", "add-json", "-s", "user", "neon"]
    assert json.loads(step.command[6]) == entry


def test_a_direct_edit_applies_verifies_and_undoes_on_a_sandbox_home(home, tmp_path):
    path = home / ".claude.json"
    before = json.loads(path.read_text())

    def no_command(command, cwd):
        raise AssertionError(f"no client command may run: {command}")

    engine = Engine(ChangeStore(tmp_path / "data"), run=no_command)
    step = ClaudeCodeAdapter(home).add_server_step("files", SECRET_ENTRY)
    change = engine.preview("mcp.add", [step])
    assert TOKEN not in step.edit.masked_diff

    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED
    after = json.loads(path.read_text())
    assert after["mcpServers"]["files"] == SECRET_ENTRY
    assert {k: v for k, v in after.items() if k != "mcpServers"} == {
        k: v for k, v in before.items() if k != "mcpServers"
    }
    assert after["mcpServers"]["old"] == before["mcpServers"]["old"]

    # Claude Code rewrites the file in normal use; Undo still takes out only our entry.
    after["numStartups"] = 8
    path.write_text(json.dumps(after, indent=2))
    engine.undo(change.id)
    assert change.state is ChangeState.UNDONE
    assert json.loads(path.read_text()) == {**before, "numStartups": 8}
    assert TOKEN not in json.dumps(engine.store.entries())
