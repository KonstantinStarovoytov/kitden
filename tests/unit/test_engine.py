"""Change engine (T042, T043): preview, stale check, apply, verify, restore, undo."""

import json
import os
import stat
from pathlib import Path

import pytest

from kitden.changes import json_splice, toml_edit
from kitden.changes.backup import ChangeStore
from kitden.changes.client_cli import CommandResult
from kitden.changes.copy_folder import digest
from kitden.changes.engine import ChangeRefusedError, Engine
from kitden.changes.json_splice import ABSENT
from kitden.gateway_api import MetaMcpClient
from kitden.model import (
    GATEWAY_CLIENT,
    ChangeState,
    FileEdit,
    FolderRemoval,
    Gateway,
    GatewayEdit,
    Scope,
    Step,
)
from tests.unit.fake_metamcp import FakeMetaMcp

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


def test_preview_refuses_an_empty_change(tmp_path):
    engine = make_engine(tmp_path)
    with pytest.raises(ChangeRefusedError, match="Nothing to change"):
        engine.preview("project.align", [])
    assert engine.changes == {}


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


def test_stale_reason_sees_a_file_changed_after_preview(tmp_path, config):
    engine = make_engine(tmp_path)
    change = engine.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])
    config.write_text(CONFIG + "# edited by hand\n")
    assert "changed since preview" in engine.stale_reason(change.id)
    assert change.state is ChangeState.PREVIEWED  # only looked
    assert engine.store.entries() == []  # nothing logged, nothing written
    assert config.read_text() == CONFIG + "# edited by hand\n"


def test_an_untouched_preview_is_not_stale(tmp_path, config):
    engine = make_engine(tmp_path)
    change = engine.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])
    assert engine.stale_reason(change.id) is None
    # Only a previewed change is checked: a cancelled one is not stale, whatever its file says.
    engine.cancel(change.id)
    config.write_text(CONFIG + "# edited by hand\n")
    assert engine.stale_reason(change.id) is None


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


def test_a_target_that_cannot_be_read_is_refused_not_an_error(tmp_path):
    # The page answers a refusal with its words; any other error would be a 500.
    folder = tmp_path / "config.toml"
    folder.mkdir()
    with pytest.raises(ChangeRefusedError, match="could not read"):
        make_engine(tmp_path).preview(
            "gateway.connect", [toml_step(folder, ("mcp_servers", "gw"), GATEWAY)]
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


def test_a_change_knows_when_its_backup_holds_a_secret(tmp_path, config):
    engine = make_engine(tmp_path)
    change = engine.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])
    assert change.holds_secret is False  # nothing is saved before Apply
    engine.apply(change.id)
    assert change.holds_secret is True  # the backup of config.toml has NEON_KEY
    assert engine.store.entries()[0]["holds_secret"] is True
    engine.undo(change.id)
    assert engine.store.entries()[0]["holds_secret"] is True
    assert make_engine(tmp_path).changes[change.id].holds_secret is True  # from the record


def _json_step(path, after):
    edit = FileEdit(path=str(path), fmt="json", key=("mcpServers", "a"), after=after)
    return Step(client="cursor", scope=Scope.USER, name="a", edit=edit)


def test_a_change_knows_when_only_its_record_holds_a_secret(tmp_path):
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {}}))
    engine = make_engine(tmp_path)
    plain = engine.preview("mcp.add", [_json_step(path, {"command": "npx", "env": {"K": "v"}})])
    engine.apply(plain.id)
    assert plain.holds_secret is True  # the record keeps the value Apply wrote
    engine.undo(plain.id)
    ref = {"command": "npx", "env": {"K": {"keychain": "a/K"}}}
    held = engine.preview("mcp.add", [_json_step(path, ref)])
    engine.apply(held.id)
    assert held.holds_secret is False  # a Keychain reference is not a secret


def test_change_reports_restarts_and_shared_files(tmp_path, config):
    step = toml_step(
        config, ("mcp_servers", "gw"), GATEWAY, restart_note="Restart Codex.", shared_file=True
    )
    change = make_engine(tmp_path).preview("gateway.connect", [step])
    assert change.restart_needed == {"codex": True}
    assert change.shared_file_warning is True


# Several steps on one file (feature 002, research R2) --------------------------------------

KITDEN = {"type": "stdio", "command": "/Users/me/.local/bin/kitden", "args": ["mcp"]}


def test_two_steps_on_one_toml_file_apply_in_order_and_undo_exactly(tmp_path, config):
    engine = make_engine(tmp_path)
    steps = [
        toml_step(config, ("mcp_servers", "neon"), ABSENT),
        toml_step(config, ("mcp_servers", "gw"), GATEWAY),
    ]
    change = engine.preview("setup_server.update", steps)
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED
    text = config.read_text()
    assert toml_edit.get_value(text, ("mcp_servers", "neon")) is ABSENT
    assert toml_edit.get_value(text, ("mcp_servers", "gw")) == GATEWAY
    assert "# keep this comment" in text
    engine.undo(change.id)
    assert change.state is ChangeState.UNDONE
    assert config.read_text() == CONFIG


def test_two_cli_steps_on_one_json_file_undo_after_an_outside_edit(tmp_path, claude_json):
    fake = FakeClaude(claude_json)
    engine = make_engine(tmp_path, run=fake)
    remove = ["claude", "mcp", "remove", "-s", "user", "old"]
    add = ["claude", "mcp", "add-json", "-s", "user", "kitden", json.dumps(KITDEN)]
    steps = [
        claude_step(claude_json, "old", ABSENT, remove),
        claude_step(claude_json, "kitden", KITDEN, add),
    ]
    change = engine.preview("setup_server.update", steps)
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED
    assert [call[0] for call in fake.calls] == [remove, add]
    claude_json.write_text(json_splice.set_value(claude_json.read_text(), ("numStartups",), 3))
    engine.undo(change.id)
    assert change.state is ChangeState.UNDONE
    text = claude_json.read_text()
    assert json_splice.get_value(text, ("mcpServers", "old")) == {"command": "x"}
    assert json_splice.get_value(text, ("mcpServers", "kitden")) is ABSENT
    assert json_splice.get_value(text, ("numStartups",)) == 3


def test_a_failed_second_step_restores_the_original_bytes(tmp_path, claude_json):
    original = claude_json.read_bytes()
    engine = make_engine(tmp_path, run=FakeClaude(claude_json, wrong_value=True))
    remove = ["claude", "mcp", "remove", "-s", "user", "old"]
    value = {"type": "http", "url": "http://127.0.0.1:12008/mcp"}
    add = ["claude", "mcp", "add-json", "-s", "user", "gw", json.dumps(value)]
    steps = [
        claude_step(claude_json, "old", ABSENT, remove),
        claude_step(claude_json, "gw", value, add),
    ]
    change = engine.preview("setup_server.update", steps)
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED
    assert claude_json.read_bytes() == original


def test_two_steps_on_the_same_entry_are_refused(tmp_path, config):
    engine = make_engine(tmp_path)
    steps = [
        toml_step(config, ("mcp_servers", "gw"), GATEWAY),
        toml_step(config, ("mcp_servers", "gw"), ABSENT),
    ]
    with pytest.raises(ChangeRefusedError, match="twice"):
        engine.preview("gateway.connect", steps)


# Moving a server into the gateway (feature 006) --------------------------------------------

NEON = {
    "type": "STREAMABLE_HTTP",
    "url": "https://mcp.neon.tech/mcp",
    "headers": {"Authorization": "Bearer SENTINEL_SECRET_NEON"},
}


@pytest.fixture
def fake():
    fake = FakeMetaMcp().start()
    yield fake
    fake.stop()


def gateway_engine(tmp_path, fake, run=None):
    gateway = Gateway(url=fake.mcp_url, login_email="me@example.com", login_password_env_var="PW")

    def clients(edit):
        return MetaMcpClient(gateway, {"PW": "right-password"})

    store = ChangeStore(tmp_path / "data")
    return Engine(store, run=run or FakeClaude(None), gateway_clients=clients), gateway


def gateway_step(gateway, name="neon", server=NEON):
    edit = GatewayEdit(gateway_id=gateway.id, url=gateway.url, name=name, server=server)
    return Step(
        client=GATEWAY_CLIENT, scope=Scope.USER, name=name, gateway=edit, mechanism="gateway_api"
    )


def move_steps(gateway, config):
    return [gateway_step(gateway), toml_step(config, ("mcp_servers", "neon"), ABSENT)]


def test_move_adds_to_the_gateway_then_removes_the_entry_and_undoes(tmp_path, fake, config):
    engine, gateway = gateway_engine(tmp_path, fake)
    change = engine.preview("gateway.move", move_steps(gateway, config))
    assert change.state is ChangeState.PREVIEWED
    assert fake.held_names() == [] and config.read_text() == CONFIG
    diff = change.steps[0].gateway.masked_diff
    assert "+" in diff and "neon" in diff and "SENTINEL" not in diff and "[secret]" in diff

    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED
    assert fake.held_names() == ["neon"]
    assert toml_edit.get_value(config.read_text(), ("mcp_servers", "neon")) is ABSENT
    uuid = change.steps[0].gateway.server_uuid
    assert fake.servers[uuid]["headers"]["Authorization"].endswith("SENTINEL_SECRET_NEON")
    assert "SENTINEL" not in json.dumps(engine.store.entries())
    entry = engine.store.entries()[0]
    assert entry["steps"][0]["path"] == gateway.url and entry["steps"][0]["client"] == "gateway"
    assert fake.sessions == set()

    second, _ = gateway_engine(tmp_path, fake)  # undo after a restart, from the record
    second.undo(change.id)
    assert second.changes[change.id].state is ChangeState.UNDONE
    assert fake.held_names() == [] and fake.servers == {}
    assert config.read_text() == CONFIG


def test_apply_and_undo_say_how_many_steps_are_done(tmp_path, fake, config):
    # The page shows "Applying 1 of 2" from these counts, so a long move is not a silent wait.
    engine, gateway = gateway_engine(tmp_path, fake)
    change = engine.preview("gateway.move", move_steps(gateway, config))
    seen = []
    engine.on_progress = lambda change_id, done, total, step: seen.append(
        (change_id, done, total, step)
    )
    engine.apply(change.id)
    # The last value is the index of the step just done, so the tray can name its row.
    assert seen == [(change.id, 1, 2, 0), (change.id, 2, 2, 1)]
    seen.clear()
    engine.undo(change.id)
    assert seen[0] == (change.id, 1, 2, 0) and seen[-1] == (change.id, 2, 2, None)
    assert all(done <= total for _, done, total, _ in seen)


def test_a_name_the_gateway_already_holds_is_refused(tmp_path, fake, config):
    engine, gateway = gateway_engine(tmp_path, fake)
    fake.hold("neon", "https://mcp.neon.tech/mcp")
    with pytest.raises(ChangeRefusedError, match="already has neon"):
        engine.preview("gateway.move", move_steps(gateway, config))


def test_an_unreachable_gateway_refuses_the_preview(tmp_path, config):
    fake = FakeMetaMcp().start()
    engine, gateway = gateway_engine(tmp_path, fake)
    fake.stop()
    with pytest.raises(ChangeRefusedError, match="Could not reach"):
        engine.preview("gateway.move", move_steps(gateway, config))
    assert config.read_text() == CONFIG


def test_without_a_gateway_client_the_step_is_refused(tmp_path, fake, config):
    _, gateway = gateway_engine(tmp_path, fake)
    with pytest.raises(ChangeRefusedError, match="cannot be managed"):
        make_engine(tmp_path).preview("gateway.move", move_steps(gateway, config))


def test_a_failed_file_step_removes_the_server_from_the_gateway_again(tmp_path, fake, claude_json):
    original = claude_json.read_bytes()
    engine, gateway = gateway_engine(tmp_path, fake, run=FakeClaude(claude_json, wrong_value=True))
    value = {"type": "http", "url": "http://127.0.0.1:12008/mcp"}
    command = ["claude", "mcp", "add-json", "-s", "user", "gw", json.dumps(value)]
    steps = [gateway_step(gateway), claude_step(claude_json, "gw", value, command)]
    change = engine.preview("gateway.move", steps)
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED
    assert claude_json.read_bytes() == original
    assert fake.held_names() == [] and fake.servers == {}


def test_undo_stops_when_the_gateway_cannot_be_reached(tmp_path, config):
    fake = FakeMetaMcp().start()
    engine, gateway = gateway_engine(tmp_path, fake)
    change = engine.preview("gateway.move", move_steps(gateway, config))
    engine.apply(change.id)
    after = config.read_text()
    fake.stop()
    engine.undo(change.id)
    assert change.state is ChangeState.UNDO_BLOCKED
    assert "not changed" in change.error
    assert config.read_text() == after


def test_undo_goes_on_when_the_server_was_removed_by_hand(tmp_path, fake, config):
    engine, gateway = gateway_engine(tmp_path, fake)
    change = engine.preview("gateway.move", move_steps(gateway, config))
    engine.apply(change.id)
    del fake.servers[change.steps[0].gateway.server_uuid]
    fake.in_namespace = []
    engine.undo(change.id)
    assert change.state is ChangeState.UNDONE
    assert "already been removed" in change.error
    assert config.read_text() == CONFIG


def test_undo_takes_the_server_out_of_the_gateway_last_and_can_be_tried_again(
    tmp_path, fake, claude_json
):
    # If putting the client entry back fails, the gateway still has the server: it is never
    # in neither place. Once the cause is gone, Undo can be pressed again and finishes.
    cli = FakeClaude(claude_json)
    engine, gateway = gateway_engine(tmp_path, fake, run=cli)
    entry = {"command": "x"}
    remove = claude_step(
        claude_json, "old", ABSENT, ["claude", "mcp", "remove", "-s", "user", "old"]
    )
    remove.undo_command = ["claude", "mcp", "add-json", "-s", "user", "old", json.dumps(entry)]
    change = engine.preview("gateway.move", [gateway_step(gateway), remove])
    assert engine.apply(change.id).state is ChangeState.VERIFIED

    engine.run = lambda command, cwd: CommandResult(returncode=1, output="no network")
    assert engine.undo(change.id).state is ChangeState.UNDO_BLOCKED
    assert fake.held_names() == ["neon"]

    engine.run = cli
    assert engine.undo(change.id).state is ChangeState.UNDONE, change.error
    assert fake.held_names() == []
    assert json.loads(claude_json.read_text())["mcpServers"] == {"old": entry}


def test_a_change_without_file_steps_is_still_recorded(tmp_path, fake):
    engine, gateway = gateway_engine(tmp_path, fake)
    change = engine.preview("gateway.move", [gateway_step(gateway)])
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED
    assert fake.held_names() == ["neon"]
    assert engine.store.entries()[0]["state"] == "verified"
    engine.undo(change.id)
    assert change.state is ChangeState.UNDONE and fake.held_names() == []


class FakePluginCli:
    """Acts like `claude plugin install/uninstall` and `marketplace add/remove` on settings.json:
    the client writes its own record, and uninstall really removes it."""

    def __init__(self, path, fail_on=None):
        self.path = path
        self.fail_on = fail_on
        self.calls = []

    def __call__(self, command, cwd):
        self.calls.append(command)
        if self.fail_on and self.fail_on in command:
            return CommandResult(returncode=1, output="refused")
        data = json.loads(self.path.read_text())
        if command[1:3] == ["plugin", "install"]:
            data.setdefault("enabledPlugins", {})[command[3]] = True
        elif command[1:3] == ["plugin", "uninstall"]:
            data.get("enabledPlugins", {}).pop(command[3], None)
        elif command[1:4] == ["plugin", "marketplace", "add"]:
            data.setdefault("extraKnownMarketplaces", {})["tools"] = {
                "source": {"source": "github", "repo": command[4]},
                "added": "2026-10-19",
            }
        elif command[1:4] == ["plugin", "marketplace", "remove"]:
            data.get("extraKnownMarketplaces", {}).pop(command[4], None)
        self.path.write_text(json.dumps(data, indent=2))
        return CommandResult(returncode=0, output="{}")


def plugin_steps(settings):
    add = Step(
        client="claude_code",
        scope=Scope.USER,
        name="tools",
        edit=FileEdit(
            path=str(settings),
            fmt="json",
            key=("extraKnownMarketplaces", "tools"),
            after=json_splice.PRESENT,
            check="entry",
        ),
        mechanism="client_cli",
        command=["claude", "plugin", "marketplace", "add", "acme/tools"],
        undo_command=["claude", "plugin", "marketplace", "remove", "tools"],
    )
    install = Step(
        client="claude_code",
        scope=Scope.USER,
        name="lint@tools",
        edit=FileEdit(
            path=str(settings),
            fmt="json",
            key=("enabledPlugins", "lint@tools"),
            after=True,
            check="entry",
        ),
        mechanism="client_cli",
        command=["claude", "plugin", "install", "lint@tools", "-s", "user", "--json"],
        undo_command=["claude", "plugin", "uninstall", "lint@tools", "-s", "user", "--json"],
    )
    return [add, install]


@pytest.fixture
def settings(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "dark"}, indent=2))
    return path


def test_an_entry_the_client_writes_itself_only_has_to_be_there(tmp_path, settings):
    engine = make_engine(tmp_path, run=FakePluginCli(settings))
    change = engine.preview("plugin.install", plugin_steps(settings))
    assert "added by the client" in change.steps[0].edit.masked_diff
    assert engine.apply(change.id).state is ChangeState.VERIFIED
    data = json.loads(settings.read_text())
    assert (
        data["enabledPlugins"] == {"lint@tools": True} and "tools" in data["extraKnownMarketplaces"]
    )


def test_undo_runs_the_inverse_commands_in_reverse_order(tmp_path, settings):
    cli = FakePluginCli(settings)
    engine = make_engine(tmp_path, run=cli)
    change = engine.preview("plugin.install", plugin_steps(settings))
    engine.apply(change.id)
    # Something else writes the same file afterwards: undo still works, it does not restore bytes.
    data = json.loads(settings.read_text())
    data["theme"] = "light"
    settings.write_text(json.dumps(data))
    assert engine.undo(change.id).state is ChangeState.UNDONE
    assert [c[1:3] for c in cli.calls[-2:]] == [["plugin", "uninstall"], ["plugin", "marketplace"]]
    after = json.loads(settings.read_text())
    assert after == {"theme": "light", "enabledPlugins": {}, "extraKnownMarketplaces": {}}


def removal(settings, plugin):
    """Uninstall one plugin; Undo installs it again with the client's own command."""
    return Step(
        client="claude_code",
        scope=Scope.USER,
        name=plugin,
        edit=FileEdit(
            path=str(settings),
            fmt="json",
            key=("enabledPlugins", plugin),
            after=ABSENT,
            check="entry",
        ),
        mechanism="client_cli",
        command=["claude", "plugin", "uninstall", plugin, "-s", "user", "--json"],
        undo_command=["claude", "plugin", "install", plugin, "-s", "user", "--json"],
    )


def test_undo_of_removing_an_off_plugin_puts_it_back_off(tmp_path, settings):
    # The client's install turns the plugin on; Undo then sets the entry back as it was.
    settings.write_text(json.dumps({"enabledPlugins": {"lint@tools": False}, "theme": "dark"}))
    cli = FakePluginCli(settings)
    engine = make_engine(tmp_path, run=cli)
    change = engine.preview("plugin.remove", [removal(settings, "lint@tools")])
    assert engine.apply(change.id).state is ChangeState.VERIFIED
    assert json.loads(settings.read_text())["enabledPlugins"] == {}
    assert engine.undo(change.id).state is ChangeState.UNDONE
    assert cli.calls[-1][1:3] == ["plugin", "install"]
    assert json.loads(settings.read_text()) == {
        "enabledPlugins": {"lint@tools": False},
        "theme": "dark",
    }


def test_a_failed_removal_puts_an_off_plugin_back_off(tmp_path, settings):
    settings.write_text(json.dumps({"enabledPlugins": {"lint@tools": False, "fmt@tools": True}}))
    cli = FakePluginCli(settings, fail_on="fmt@tools")
    engine = make_engine(tmp_path, run=cli)
    steps = [removal(settings, "lint@tools"), removal(settings, "fmt@tools")]
    change = engine.preview("plugin.remove", steps)
    assert engine.apply(change.id).state is ChangeState.RESTORED
    assert cli.calls[-1][1:4] == ["plugin", "install", "lint@tools"]
    plugins = json.loads(settings.read_text())["enabledPlugins"]
    assert plugins == {"lint@tools": False, "fmt@tools": True}


def test_a_failed_install_runs_the_inverse_of_what_already_ran(tmp_path, settings):
    cli = FakePluginCli(settings, fail_on="install")
    engine = make_engine(tmp_path, run=cli)
    change = engine.preview("plugin.install", plugin_steps(settings))
    assert engine.apply(change.id).state is ChangeState.RESTORED
    assert cli.calls[-1][1:4] == ["plugin", "marketplace", "remove"]
    assert json.loads(settings.read_text()).get("extraKnownMarketplaces", {}) == {}


def test_an_entry_that_is_already_there_is_refused(tmp_path, settings):
    settings.write_text(json.dumps({"extraKnownMarketplaces": {"tools": {}}}))
    engine = make_engine(tmp_path, run=FakePluginCli(settings))
    with pytest.raises(ChangeRefusedError):
        engine.preview("plugin.install", plugin_steps(settings)[:1])


def test_a_change_with_nothing_to_do_names_the_client_in_plain_words():
    # "nothing to change in /Users/…/config.toml" told the owner nothing (2026-10-20).
    from kitden.changes.engine import NothingToChangeError
    from kitden.web.app import refusal_words

    error = NothingToChangeError("/home/x/.codex/config.toml", "codex")
    assert "nothing to change" in str(error)
    assert refusal_words(error) == "Codex has this already. Nothing to change."
    assert refusal_words(ValueError("Choose at least one client")) == "Choose at least one client"


# Removing a skill folder (spec 3.2) --------------------------------------------------------


def removal_step(folder):
    removal = FolderRemoval(path=str(folder), readers=["codex", "cursor"])
    return Step(
        client="codex", scope=Scope.USER, name="tidy", mechanism="remove_folder", removal=removal
    )


def tidy_folder(tmp_path):
    folder = tmp_path / "skills/tidy"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("tidy\n")
    return folder


def test_a_folder_removal_is_backed_up_and_undone(tmp_path):
    folder = tidy_folder(tmp_path)
    before = digest(folder)
    engine = make_engine(tmp_path)
    change = engine.preview("skill.remove", [removal_step(folder)])
    assert change.steps[0].removal.masked_diff == "-SKILL.md"
    assert engine.apply(change.id).state is ChangeState.VERIFIED
    assert not folder.exists()
    backup = Path(change.steps[0].removal.backup_path)
    assert backup.is_relative_to(tmp_path / "data/changes") and digest(backup) == before
    assert engine.store.entries()[0]["steps"][0]["reaches"] == ["codex", "cursor"]
    assert engine.undo(change.id).state is ChangeState.UNDONE
    assert digest(folder) == before


def test_a_removed_folder_with_a_secret_flags_the_change(tmp_path):
    from kitden.web.app import change_dict

    folder = tidy_folder(tmp_path)
    engine = make_engine(tmp_path)
    plain = engine.preview("skill.remove", [removal_step(folder)])
    engine.apply(plain.id)
    assert plain.holds_secret is False
    engine.undo(plain.id)
    (folder / ".env").write_text("API_KEY=SENTINEL_SECRET_SKILL\n")
    change = engine.preview("skill.remove", [removal_step(folder)])
    assert engine.apply(change.id).state is ChangeState.VERIFIED
    assert change.holds_secret is True
    assert engine.store.entries()[0]["holds_secret"] is True
    record = (tmp_path / "data/changes" / change.id / "change.json").read_text()
    log = (tmp_path / "data/changes.log").read_text()
    page = json.dumps(change_dict(change))
    assert "SENTINEL" not in record + log + page


def test_a_removal_survives_a_restart_of_kitden(tmp_path):
    folder = tidy_folder(tmp_path)
    engine = make_engine(tmp_path)
    change = engine.preview("skill.remove", [removal_step(folder)])
    engine.apply(change.id)
    again = make_engine(tmp_path)
    assert again.undo(change.id).state is ChangeState.UNDONE
    assert (folder / "SKILL.md").read_text() == "tidy\n"


def test_a_failed_step_after_a_removal_puts_the_folder_back(tmp_path, claude_json):
    folder = tidy_folder(tmp_path)
    engine = make_engine(tmp_path, run=FakeClaude(claude_json, wrong_value=True))
    value = {"type": "http", "url": "http://127.0.0.1:12008/mcp"}
    command = ["claude", "mcp", "add-json", "-s", "user", "gw", json.dumps(value)]
    steps = [removal_step(folder), claude_step(claude_json, "gw", value, command)]
    change = engine.preview("skill.remove", steps)
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED and folder.is_dir()
    assert (folder / "SKILL.md").read_text() == "tidy\n"


def test_a_removal_of_a_link_is_refused(tmp_path):
    real = tmp_path / "elsewhere/tidy"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("x")
    link = tmp_path / "skills/tidy"
    link.parent.mkdir()
    link.symlink_to(real)
    with pytest.raises(ChangeRefusedError, match="is a link; Kitden removes only real folders"):
        make_engine(tmp_path).preview("skill.remove", [removal_step(link)])
    assert link.is_symlink() and (real / "SKILL.md").exists()


def test_a_missing_or_twice_listed_folder_is_refused(tmp_path):
    engine = make_engine(tmp_path)
    with pytest.raises(ChangeRefusedError, match="is not a folder"):
        engine.preview("skill.remove", [removal_step(tmp_path / "skills/none")])
    folder = tidy_folder(tmp_path)
    with pytest.raises(ChangeRefusedError, match="would be removed twice in one change"):
        engine.preview("skill.remove", [removal_step(folder), removal_step(folder)])


def test_a_folder_changed_since_preview_is_stale(tmp_path):
    folder = tidy_folder(tmp_path)
    engine = make_engine(tmp_path)
    change = engine.preview("skill.remove", [removal_step(folder)])
    (folder / "notes.md").write_text("new\n")
    assert engine.apply(change.id).state is ChangeState.STALE
    assert (folder / "notes.md").exists()
    gone = engine.preview("skill.remove", [removal_step(folder)])
    for path in folder.iterdir():
        path.unlink()
    folder.rmdir()
    assert engine.apply(gone.id).state is ChangeState.STALE
    assert gone.error == f"{folder} is gone since preview; review the change again"


def test_stale_reason_sees_a_folder_changed_after_preview(tmp_path):
    folder = tidy_folder(tmp_path)
    engine = make_engine(tmp_path)
    change = engine.preview("skill.remove", [removal_step(folder)])
    assert engine.stale_reason(change.id) is None
    (folder / "notes.md").write_text("new\n")
    assert engine.stale_reason(change.id) == (
        f"{folder} changed since preview; review the change again"
    )
    assert change.state is ChangeState.PREVIEWED and (folder / "notes.md").exists()


def test_undo_leaves_a_folder_that_came_back(tmp_path):
    folder = tidy_folder(tmp_path)
    engine = make_engine(tmp_path)
    change = engine.preview("skill.remove", [removal_step(folder)])
    engine.apply(change.id)
    folder.mkdir(parents=True)
    (folder / "notes.md").write_text("mine\n")
    assert engine.undo(change.id).state is ChangeState.UNDO_BLOCKED
    assert "is back" in change.error and (folder / "notes.md").read_text() == "mine\n"


def test_undo_without_the_backup_changes_nothing(tmp_path):
    import shutil

    folder = tidy_folder(tmp_path)
    engine = make_engine(tmp_path)
    change = engine.preview("skill.remove", [removal_step(folder)])
    engine.apply(change.id)
    shutil.rmtree(change.steps[0].removal.backup_path)
    assert engine.undo(change.id).state is ChangeState.UNDO_BLOCKED
    assert change.error == f"the backup of {folder} is gone, so nothing was changed"
    assert not folder.exists()


def test_a_removal_that_stops_halfway_is_put_back_whole(tmp_path, monkeypatch):
    import kitden.changes.engine as engine_module

    folder = tidy_folder(tmp_path)
    (folder / "notes.md").write_text("notes\n")
    before = digest(folder)

    real_remove = engine_module.remove_folder
    calls = []

    def half(path):  # the first call removes one file, then fails
        calls.append(path)
        if len(calls) > 1:
            return real_remove(path)
        (Path(path) / "notes.md").unlink()
        raise OSError("disk trouble")

    engine = make_engine(tmp_path)
    change = engine.preview("skill.remove", [removal_step(folder)])
    monkeypatch.setattr(engine_module, "remove_folder", half)
    assert engine.apply(change.id).state is ChangeState.RESTORED
    assert digest(folder) == before
    assert change.error.endswith("The original settings were restored.")


def test_a_folder_that_cannot_be_put_back_is_named_with_its_backup(tmp_path):
    folder = tidy_folder(tmp_path)
    locked = folder / "locked"
    locked.mkdir()
    (locked / "a.md").write_text("a\n")
    locked.chmod(0o555)  # rmtree cannot empty it
    try:
        engine = make_engine(tmp_path)
        change = engine.preview("skill.remove", [removal_step(folder)])
        assert engine.apply(change.id).state is ChangeState.RESTORED
        backup = change.steps[0].removal.backup_path
        assert "restored" not in change.error
        assert f"tidy could not be put back; its backup is in {backup}." in change.error
        assert digest(backup) == change.steps[0].removal.content_hash
    finally:
        locked.chmod(0o755)


# One file with both a client command and a direct edit (final review of part 3) -------------


class FakeCodexCli:
    """Acts like `codex plugin add/remove` on config.toml, and keeps a cache folder like Codex."""

    def __init__(self, config, cache, fail_on=()):
        self.config = config
        self.cache = cache
        self.fail_on = fail_on
        self.calls = []

    def __call__(self, command, cwd):
        self.calls.append(command)
        if command in self.fail_on:
            return CommandResult(returncode=1, output="refused")
        text = self.config.read_text()
        plugin = command[3]
        if command[1:3] == ["plugin", "add"]:
            text = toml_edit.set_value(text, ("plugins", plugin, "enabled"), True)
            (self.cache / plugin).mkdir(parents=True)
        elif command[1:3] == ["plugin", "remove"]:
            text = toml_edit.delete_value(text, ("plugins", plugin))
            (self.cache / plugin).rmdir()
        self.config.write_text(text)
        return CommandResult(returncode=0, output="{}")


def codex_add(config, plugin):
    edit = FileEdit(
        path=str(config), fmt="toml", key=("plugins", plugin, "enabled"), after=True, check="entry"
    )
    return Step(
        client="codex",
        scope=Scope.USER,
        name=plugin,
        edit=edit,
        mechanism="client_cli",
        command=["codex", "plugin", "add", plugin, "--json"],
        undo_command=["codex", "plugin", "remove", plugin],
    )


def test_undo_runs_the_inverse_command_on_a_file_with_a_direct_edit_too(tmp_path, config):
    cli = FakeCodexCli(config, tmp_path / "cache")
    engine = make_engine(tmp_path, run=cli)
    steps = [codex_add(config, "lint@tools"), toml_step(config, ("mcp_servers", "gw"), GATEWAY)]
    change = engine.preview("align", steps)
    assert engine.apply(change.id).state is ChangeState.VERIFIED
    assert engine.undo(change.id).state is ChangeState.UNDONE
    assert cli.calls[-1] == ["codex", "plugin", "remove", "lint@tools"]
    assert config.read_text() == CONFIG
    assert not (tmp_path / "cache/lint@tools").exists()


def test_a_failed_apply_runs_the_inverse_command_on_a_file_with_a_direct_edit_too(tmp_path, config):
    fails = [["codex", "plugin", "add", "fmt@tools", "--json"]]
    cli = FakeCodexCli(config, tmp_path / "cache", fail_on=fails)
    engine = make_engine(tmp_path, run=cli)
    steps = [
        codex_add(config, "lint@tools"),
        toml_step(config, ("mcp_servers", "gw"), GATEWAY),
        codex_add(config, "fmt@tools"),
    ]
    change = engine.preview("align", steps)
    assert engine.apply(change.id).state is ChangeState.RESTORED
    assert cli.calls[-1] == ["codex", "plugin", "remove", "lint@tools"]
    assert config.read_text() == CONFIG
    assert not (tmp_path / "cache/lint@tools").exists()
    assert change.error.endswith("The original settings were restored.")


def test_a_failed_inverse_command_is_named_and_nothing_claims_a_restore(tmp_path, settings):
    settings.write_text(json.dumps({"enabledPlugins": {"lint@tools": True, "fmt@tools": True}}))
    cli = FakePluginCli(settings, fail_on="fmt@tools")
    real = cli.__call__

    def run(command, cwd):  # the reinstall of lint@tools fails too
        if command[1:4] == ["plugin", "install", "lint@tools"]:
            return CommandResult(returncode=1, output="offline")
        return real(command, cwd)

    engine = make_engine(tmp_path, run=run)
    steps = [removal(settings, "lint@tools"), removal(settings, "fmt@tools")]
    change = engine.preview("plugin.remove", steps)
    assert engine.apply(change.id).state is ChangeState.RESTORED
    assert "restored" not in change.error
    assert (
        "`claude plugin install lint@tools -s user --json` failed; lint@tools was not put back."
        in change.error
    )


def test_a_backup_that_does_not_match_the_folder_removes_nothing(tmp_path, monkeypatch):
    folder = tidy_folder(tmp_path)
    before = digest(folder)
    engine = make_engine(tmp_path)
    real = engine.store.backup_folder

    def bad_backup(change_id, path):
        target = real(change_id, path)
        (target / "SKILL.md").write_text("half\n")
        return target

    monkeypatch.setattr(engine.store, "backup_folder", bad_backup)
    change = engine.preview("skill.remove", [removal_step(folder)])
    assert engine.apply(change.id).state is ChangeState.RESTORED
    assert digest(folder) == before
    assert "the backup did not read back like the folder" in change.error


def test_undo_stops_plainly_when_the_entry_cannot_be_set_back(tmp_path, settings):
    settings.write_text(json.dumps({"enabledPlugins": {"lint@tools": False}}))
    cli = FakePluginCli(settings)
    engine = make_engine(tmp_path, run=cli)
    change = engine.preview("plugin.remove", [removal(settings, "lint@tools")])
    assert engine.apply(change.id).state is ChangeState.VERIFIED

    def broken(command, cwd):  # the install leaves a file that is not JSON
        cli(command, cwd)
        settings.write_text("{not json")
        return CommandResult(returncode=0, output="{}")

    engine.run = broken
    assert engine.undo(change.id).state is ChangeState.UNDO_BLOCKED
    assert change.error == (
        f"lint@tools is back, but {settings} could not be set as it was before. Check it by hand."
    )


# A failed Apply puts everything back, or says what it could not (review 2026-11-03) ---------


def keychain_engine(tmp_path, run=None):
    """An engine whose Keychain is the demo stand-in, a JSON file in tmp_path."""
    from kitden.demo.keychain import DemoKeychain

    items = tmp_path / "keychain.json"
    engine = Engine(
        ChangeStore(tmp_path / "data"),
        run=run or FakeClaude(None),
        keychain_run=DemoKeychain(items),
    )
    return engine, items


def test_any_error_during_apply_restores_files_and_keychain(tmp_path, config):
    from kitden.model import KeychainItem

    engine, items = keychain_engine(tmp_path)
    second = tmp_path / "second.toml"
    second.write_text('model = "o3"\n')
    first = toml_step(config, ("mcp_servers", "gw"), GATEWAY)
    first.keychain = [KeychainItem("gw", "GW_KEY", "SENTINEL_SECRET_NEW")]
    steps = [first, toml_step(second, ("mcp_servers", "gw"), GATEWAY)]
    change = engine.preview("gateway.connect", steps)
    real = engine._apply_step

    def apply_step(step, data):
        if step is steps[1]:
            raise ValueError("bad gateway reply")
        return real(step, data)

    engine._apply_step = apply_step
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED
    assert config.read_text() == CONFIG and second.read_text() == 'model = "o3"\n'
    assert json.loads(items.read_text()) == {}
    assert change.error == "bad gateway reply The original settings were restored."


def test_a_restore_write_that_fails_does_not_stop_the_rest(tmp_path, config):
    engine = make_engine(tmp_path)
    second = tmp_path / "second.toml"
    second.write_text('model = "o3"\n')
    folder = tidy_folder(tmp_path)
    before = digest(folder)
    steps = [
        removal_step(folder),
        toml_step(config, ("mcp_servers", "gw"), GATEWAY),
        toml_step(second, ("mcp_servers", "gw"), GATEWAY),
    ]
    change = engine.preview("align", steps)
    writes = []
    real = engine._write

    def write(path, data):
        writes.append(path)
        if len(writes) == 3:  # the first write of the restore
            raise OSError("disk full")
        real(path, data)

    def verify(step, expected, exact=None):
        raise RuntimeError("the entry did not read back")

    engine._write = write
    engine._verify = verify
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED
    assert second.read_text() == 'model = "o3"\n'
    assert digest(folder) == before
    assert f"{config} is not as it was before." in change.error
    assert "restored" not in change.error


def test_a_command_that_fails_after_writing_is_taken_back(tmp_path, settings):
    settings.write_text(json.dumps({"theme": "dark"}))
    cli = FakePluginCli(settings)
    undone = []

    def run(command, cwd):  # the install writes its entry, then exits 1
        result = cli(command, cwd)
        if command[1:3] == ["plugin", "install"]:
            return CommandResult(returncode=1, output="half done")
        undone.append(command)
        return result

    engine = make_engine(tmp_path, run=run)
    change = engine.preview("plugin.install", plugin_steps(settings)[1:])
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED
    assert change.refused_by == "claude_code"
    assert undone and undone[0][1:3] == ["plugin", "uninstall"]
    assert json.loads(settings.read_text()).get("enabledPlugins") == {}
    assert change.error.endswith("The original settings were restored.")

    # An inverse command that does nothing: the file still differs, so no restore is claimed.
    settings.write_text(json.dumps({"theme": "dark"}))

    def run_no_undo(command, cwd):
        if "install" not in command:
            return CommandResult(returncode=0, output="")
        cli(command, cwd)
        return CommandResult(returncode=1, output="half done")

    engine = make_engine(tmp_path, run=run_no_undo)
    change = engine.preview("plugin.install", plugin_steps(settings)[1:])
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED
    assert f"{settings} is not as it was before." in change.error
    assert "restored" not in change.error


def test_a_client_that_refuses_is_named_for_the_bar(tmp_path, settings):
    # The bar's line after a failed Apply names who refused, in short; the command and its
    # output stay in the error, behind Show changes and on Changes.
    settings.write_text(json.dumps({"theme": "dark"}))
    cli = FakePluginCli(settings)

    def run(command, cwd):  # the client's own install says no
        if command[1:3] == ["plugin", "install"]:
            return CommandResult(returncode=1, output="installed for the user")
        return cli(command, cwd)

    engine = make_engine(tmp_path, run=run)
    change = engine.preview("plugin.install", plugin_steps(settings)[1:])
    assert engine.apply(change.id).state is ChangeState.RESTORED
    assert change.refused_by == "claude_code"
    assert change.error.endswith("The original settings were restored.")
    assert "`claude plugin install` failed: installed for the user" in change.error
    from kitden.web.app import change_dict

    assert change_dict(change)["refused_by"] == "claude_code"


def test_a_check_that_fails_after_writing_is_not_a_refusal(tmp_path, settings):
    # The check after the write is not a refusal, so no client is named: the bar keeps
    # "The change did not check out. Kitden put the files back." and says nothing else.
    settings.write_text(json.dumps({"theme": "dark"}))
    engine = make_engine(tmp_path, run=FakePluginCli(settings))

    def verify(step, expected, exact=None):
        raise RuntimeError("the entry did not read back as expected")

    engine._verify = verify
    change = engine.preview("plugin.install", plugin_steps(settings)[1:])
    assert engine.apply(change.id).state is ChangeState.RESTORED
    assert change.refused_by is None
    assert change.error.endswith("The original settings were restored.")


def test_a_failed_apply_puts_back_the_old_keychain_value(tmp_path, config):
    from kitden.model import KeychainItem

    engine, items = keychain_engine(tmp_path)
    items.write_text(json.dumps({"kitden gw/GW_KEY": "OLD"}))
    step = toml_step(config, ("mcp_servers", "gw"), GATEWAY)
    step.keychain = [KeychainItem("gw", "GW_KEY", "SENTINEL_SECRET_NEW")]
    change = engine.preview("gateway.connect", [step])
    items.write_text(json.dumps({"kitden gw/GW_KEY": "A"}))  # rotated since the preview

    def verify(step, expected, exact=None):
        raise RuntimeError("the entry did not read back")

    engine._verify = verify
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED
    assert json.loads(items.read_text()) == {"kitden gw/GW_KEY": "A"}
    assert step.keychain[0].old is None and step.keychain[0].value == ""


def test_a_cancelled_change_forgets_the_secrets_typed_for_it(tmp_path, config):
    import dataclasses

    from kitden.model import KeychainItem

    engine, _ = keychain_engine(tmp_path)
    typed = "sk-live-SENTINEL0123456789"
    step = toml_step(
        config, ("mcp_servers", "gw"), {**GATEWAY, "http_headers": {"Authorization": typed}}
    )
    step.keychain = [KeychainItem("gw", "GW_KEY", typed)]
    change = engine.preview("gateway.connect", [step])
    engine.cancel(change.id)
    assert change.state is ChangeState.CANCELLED
    assert typed not in json.dumps(dataclasses.asdict(change), default=str)


def test_a_crash_during_apply_leaves_a_record_that_says_so(tmp_path, config):
    class Crash(BaseException):  # as the process dying: no handler of Apply sees it
        pass

    engine = make_engine(tmp_path)
    change = engine.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])

    def die(path, data):
        raise Crash

    engine._write = die
    with pytest.raises(Crash):
        engine.apply(change.id)

    after_restart = make_engine(tmp_path).changes[change.id]
    assert after_restart.state is ChangeState.RESTORED
    assert after_restart.error.startswith("Kitden stopped during Apply")
    assert str(config) in after_restart.error
    logged = make_engine(tmp_path).store.entries()[0]
    assert logged["id"] == change.id and logged["state"] == "restored"
    # Found once: a second start does not log it again.
    assert len(make_engine(tmp_path).store.entries()) == 1


def test_apply_refuses_when_its_record_cannot_be_saved(tmp_path, config):
    engine = make_engine(tmp_path)
    change = engine.preview("gateway.connect", [toml_step(config, ("mcp_servers", "gw"), GATEWAY)])
    real = engine.store.save

    def full(change_id, record):
        raise OSError("No space left on device")

    engine.store.save = full
    with pytest.raises(ChangeRefusedError, match="could not save"):
        engine.apply(change.id)
    assert change.state is ChangeState.PREVIEWED and config.read_text() == CONFIG
    engine.store.save = real
    assert engine.apply(change.id).state is ChangeState.VERIFIED


def test_a_crash_record_says_what_secrets_it_may_have_left(tmp_path, config):
    from kitden.model import KeychainItem

    class Crash(BaseException):
        pass

    engine, _ = keychain_engine(tmp_path)
    config.write_text(
        CONFIG + '\n[mcp_servers.old]\nurl = "https://o.example"\n'
        'http_headers = { Authorization = "Bearer sk-live-OLD0123456789" }\n'
    )
    step = toml_step(config, ("mcp_servers", "gw"), GATEWAY)
    step.keychain = [KeychainItem("gw", "GW_KEY", "SENTINEL_SECRET_NEW")]
    change = engine.preview("gateway.connect", [step])

    def die(path, data):
        raise Crash

    engine._write = die
    with pytest.raises(Crash):
        engine.apply(change.id)
    found, _ = keychain_engine(tmp_path)
    after = found.changes[change.id]
    assert after.holds_secret
    assert "gw/GW_KEY" in after.error


def test_a_stale_change_forgets_the_secrets_typed_for_it(tmp_path, config):
    import dataclasses

    typed = "sk-live-SENTINEL0123456789"
    engine = make_engine(tmp_path)
    step = toml_step(
        config, ("mcp_servers", "gw"), {**GATEWAY, "http_headers": {"Authorization": typed}}
    )
    change = engine.preview("gateway.connect", [step])
    config.write_text(CONFIG + "\n# changed\n")
    assert engine.apply(change.id).state is ChangeState.STALE
    assert typed not in json.dumps(dataclasses.asdict(change), default=str)


# The client writes its file during Apply (review 2026-11-03) --------------------------------


def test_a_client_write_during_apply_is_kept(tmp_path, fake, claude_json):
    engine, gateway = gateway_engine(tmp_path, fake)
    edit = FileEdit(
        path=str(claude_json), fmt="json", key=("mcpServers", "old"), after=ABSENT, check="entry"
    )
    step = Step(client="claude_code", scope=Scope.USER, name="old", edit=edit)
    change = engine.preview("gateway.move", [gateway_step(gateway), step])
    real = engine._apply_gateway

    def apply_gateway(steps, tick):  # Claude Code writes its file meanwhile
        real(steps, tick)
        data = json.loads(claude_json.read_text())
        data["numStartups"] = 2
        claude_json.write_text(json.dumps(data, indent=2))

    engine._apply_gateway = apply_gateway
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED, change.error
    assert json.loads(claude_json.read_text()) == {"numStartups": 2, "mcpServers": {}}


def test_a_client_write_to_the_entry_during_apply_stops_it(tmp_path, fake, claude_json):
    engine, gateway = gateway_engine(tmp_path, fake)
    edit = FileEdit(
        path=str(claude_json), fmt="json", key=("mcpServers", "old"), after=ABSENT, check="entry"
    )
    step = Step(client="claude_code", scope=Scope.USER, name="old", edit=edit)
    change = engine.preview("gateway.move", [gateway_step(gateway), step])
    real = engine._apply_gateway
    newer = {"numStartups": 2, "mcpServers": {"old": {"command": "y"}}}

    def apply_gateway(steps, tick):
        real(steps, tick)
        claude_json.write_text(json.dumps(newer))

    engine._apply_gateway = apply_gateway
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED
    assert "changed since preview" in change.error
    assert json.loads(claude_json.read_text()) == newer
    assert fake.held_names() == []
