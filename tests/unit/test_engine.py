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
    engine.on_progress = lambda change_id, done, total: seen.append((change_id, done, total))
    engine.apply(change.id)
    assert seen == [(change.id, 1, 2), (change.id, 2, 2)]
    seen.clear()
    engine.undo(change.id)
    assert seen[-1] == (change.id, 2, 2)
    assert all(done <= total for _, done, total in seen)


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
