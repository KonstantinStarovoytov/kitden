"""Change engine (T042, T043): preview, stale check, apply, verify, restore, undo."""

import json
import os
import stat

import pytest

from kitden.changes import json_splice, toml_edit
from kitden.changes.backup import ChangeStore
from kitden.changes.client_cli import CommandResult
from kitden.changes.engine import ChangeRefusedError, Engine
from kitden.changes.json_splice import ABSENT
from kitden.model import ChangeState, FileEdit, Scope, Step

CONFIG = """# my Codex settings
model = "gpt-5"  # keep this comment

[mcp_servers.neon]
url = "https://mcp.neon.tech/mcp"

[mcp_servers.neon.env]
NEON_KEY = "SENTINEL_SECRET_ENGINE"
"""
GATEWAY = {"url": "http://127.0.0.1:12008/mcp", "bearer_token_env_var": "GW_KEY"}


class FakeClaude:
    """Acts like `claude mcp add-json` / `remove` on one file; rewrites it like the CLI does."""

    def __init__(self, path, wrong_value=False):
        self.path = path
        self.wrong_value = wrong_value
        self.calls = []

    def __call__(self, command, cwd):
        self.calls.append((command, cwd))
        data = json.loads(self.path.read_text())
        if command[1:3] == ["mcp", "add-json"]:
            value = json.loads(command[-1])
            if self.wrong_value:
                value["url"] = "http://wrong"
            data.setdefault("mcpServers", {})[command[-2]] = value
        else:
            del data["mcpServers"][command[-1]]
        self.path.write_text(json.dumps(data, indent=2))
        return CommandResult(returncode=0, output="")


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(CONFIG)
    path.chmod(0o600)
    return path


@pytest.fixture
def claude_json(tmp_path):
    path = tmp_path / ".claude.json"
    path.write_text(
        json.dumps({"numStartups": 1, "mcpServers": {"old": {"command": "x"}}}, indent=2)
    )
    return path


def make_engine(tmp_path, run=None, written=None):
    def on_write(path, sha):
        if written is not None:
            written.append(path)

    return Engine(ChangeStore(tmp_path / "data"), run=run or FakeClaude(None), on_write=on_write)


def toml_step(path, key, after, **extra):
    edit = FileEdit(path=str(path), fmt="toml", key=key, after=after)
    return Step(client="codex", scope=Scope.USER, name=key[-1], edit=edit, **extra)


def claude_step(path, name, after, command):
    edit = FileEdit(
        path=str(path), fmt="json", key=("mcpServers", name), after=after, check="entry"
    )
    return Step(
        client="claude_code",
        scope=Scope.USER,
        name=name,
        edit=edit,
        mechanism="client_cli",
        command=command,
    )


def test_preview_writes_nothing_and_hides_secrets(tmp_path, config):
    engine = make_engine(tmp_path)
    change = engine.preview(
        "mcp.remove_direct", [toml_step(config, ("mcp_servers", "neon"), ABSENT)]
    )
    assert change.state is ChangeState.PREVIEWED
    assert config.read_text() == CONFIG
    diff = change.steps[0].edit.masked_diff
    assert "neon" in diff and "[secret]" in diff and "SENTINEL" not in diff


def test_apply_writes_verifies_keeps_comments_and_logs(tmp_path, config):
    written = []
    engine = make_engine(tmp_path, written=written)
    change = engine.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED
    text = config.read_text()
    assert toml_edit.get_value(text, ("mcp_servers", "gw")) == GATEWAY
    assert "# keep this comment" in text
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    assert written == [str(config)]
    entry = engine.store.entries()[0]
    assert (entry["id"], entry["state"]) == (change.id, "verified")
    assert "SENTINEL" not in json.dumps(engine.store.entries())


def test_a_file_changed_after_preview_blocks_apply(tmp_path, config):
    engine = make_engine(tmp_path)
    change = engine.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])
    config.write_text(CONFIG + "# edited by hand\n")
    engine.apply(change.id)
    assert change.state is ChangeState.STALE
    assert "changed since preview" in change.error
    assert config.read_text() == CONFIG + "# edited by hand\n"


def test_a_failed_verify_restores_the_backup(tmp_path, claude_json):
    original = claude_json.read_bytes()
    engine = make_engine(tmp_path, run=FakeClaude(claude_json, wrong_value=True))
    value = {"type": "http", "url": "http://127.0.0.1:12008/mcp"}
    command = ["claude", "mcp", "add-json", "-s", "user", "gw", json.dumps(value)]
    change = engine.preview("gateway.connect", [claude_step(claude_json, "gw", value, command)])
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED
    assert claude_json.read_bytes() == original
    assert engine.store.entries()[0]["state"] == "restored"


def test_undo_restores_the_exact_bytes(tmp_path, config):
    engine = make_engine(tmp_path)
    change = engine.preview(
        "mcp.remove_direct", [toml_step(config, ("mcp_servers", "neon"), ABSENT)]
    )
    engine.apply(change.id)
    assert toml_edit.get_value(config.read_text(), ("mcp_servers", "neon")) is ABSENT
    engine.undo(change.id)
    assert change.state is ChangeState.UNDONE
    assert config.read_text() == CONFIG


def test_undo_is_blocked_after_an_outside_edit(tmp_path, config):
    engine = make_engine(tmp_path)
    change = engine.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])
    engine.apply(change.id)
    edited = config.read_text() + "# later edit\n"
    config.write_text(edited)
    engine.undo(change.id)
    assert change.state is ChangeState.UNDO_BLOCKED
    assert config.read_text() == edited


def test_entry_check_ignores_other_changes_to_the_same_file(tmp_path, claude_json):
    # Claude Code rewrites ~/.claude.json during normal use, so only the entry is compared.
    fake = FakeClaude(claude_json)
    engine = make_engine(tmp_path, run=fake)
    value = {"type": "http", "url": "http://127.0.0.1:12008/mcp"}
    command = ["claude", "mcp", "add-json", "-s", "user", "gw", json.dumps(value)]
    change = engine.preview("gateway.connect", [claude_step(claude_json, "gw", value, command)])
    claude_json.write_text(json_splice.set_value(claude_json.read_text(), ("numStartups",), 2))
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED
    assert fake.calls == [(command, None)]
    claude_json.write_text(json_splice.set_value(claude_json.read_text(), ("numStartups",), 3))
    engine.undo(change.id)
    assert change.state is ChangeState.UNDONE
    text = claude_json.read_text()
    assert json_splice.get_value(text, ("mcpServers", "gw")) is ABSENT
    assert json_splice.get_value(text, ("numStartups",)) == 3


def test_unknown_format_is_refused(tmp_path):
    path = tmp_path / "mcp.json"
    path.write_text('{\n  // a comment\n  "mcpServers": {}\n}')
    edit = FileEdit(path=str(path), fmt="json", key=("mcpServers", "gw"), after={"url": "u"})
    with pytest.raises(ChangeRefusedError, match="not strict JSON"):
        make_engine(tmp_path).preview(
            "gateway.connect", [Step(client="cursor", scope=Scope.USER, name="gw", edit=edit)]
        )


def test_hard_linked_file_is_refused(tmp_path, config):
    os.link(config, tmp_path / "second-name.toml")
    with pytest.raises(ChangeRefusedError, match="hard link"):
        make_engine(tmp_path).preview(
            "gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)]
        )


def test_nothing_to_change_is_refused(tmp_path, config):
    with pytest.raises(ChangeRefusedError, match="nothing to change"):
        make_engine(tmp_path).preview(
            "mcp.remove_direct", [toml_step(config, ("mcp_servers", "missing"), ABSENT)]
        )


def test_cancelled_change_cannot_be_applied(tmp_path, config):
    engine = make_engine(tmp_path)
    change = engine.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])
    engine.cancel(change.id)
    assert change.state is ChangeState.CANCELLED
    with pytest.raises(ValueError, match="cannot move"):
        engine.apply(change.id)
    assert config.read_text() == CONFIG


def test_new_file_is_created_private_and_undo_removes_it(tmp_path):
    path = tmp_path / ".cursor/mcp.json"
    path.parent.mkdir()
    edit = FileEdit(path=str(path), fmt="json", key=("mcpServers", "gw"), after={"url": "u"})
    engine = make_engine(tmp_path)
    change = engine.preview(
        "gateway.connect", [Step(client="cursor", scope=Scope.USER, name="gw", edit=edit)]
    )
    engine.apply(change.id)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    engine.undo(change.id)
    assert not path.exists()


def test_applied_changes_can_be_undone_after_a_restart(tmp_path, config):
    first = make_engine(tmp_path)
    change = first.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])
    first.apply(change.id)
    second = make_engine(tmp_path)
    second.undo(change.id)
    assert second.changes[change.id].state is ChangeState.UNDONE
    assert config.read_text() == CONFIG


def test_change_reports_restarts_and_shared_files(tmp_path, config):
    step = toml_step(
        config, ("mcp_servers", "gw"), GATEWAY, restart_note="Restart Codex.", shared_file=True
    )
    change = make_engine(tmp_path).preview("gateway.connect", [step])
    assert change.restart_needed == {"codex": True}
    assert change.shared_file_warning is True
