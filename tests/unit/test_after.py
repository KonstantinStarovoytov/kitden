"""The review's first line: what each client shows after the change (feature 004)."""

from kitden.model import (
    Change,
    Client,
    ClientStatus,
    FileEdit,
    FolderCopy,
    Item,
    ItemKind,
    Scope,
    Source,
    SourceKind,
    Step,
)
from kitden.views.after import after_words
from kitden.views.inventory import Inventory


def plugin(client, name, path):
    source = Source(kind=SourceKind.FILE, path=path, owner_client=client)
    return Item(client=client, kind=ItemKind.PLUGIN, name=name, source=source, scope=Scope.USER)


def step(client, name):
    edit = FileEdit(path=f"/h/{client}/settings.json", fmt="json", key=("plugins", name), after=0)
    return Step(client=client, scope=Scope.USER, name=name, edit=edit)


def inventory(*items):
    clients = [Client(id=c, display_name=c, status=ClientStatus.FOUND) for c in ("claude_code",)]
    return Inventory(clients=clients, items=list(items))


def test_turning_off_a_plugin_says_off():
    inv = inventory(plugin("claude_code", "notes@official", "/h/a.json"))
    change = Change(action="plugin.disable", steps=[step("claude_code", "notes@official")])
    assert after_words(change, inv) == [{"client": "claude_code", "state": "off", "word": "Off"}]


def test_turning_off_one_of_two_copies_says_loads_once():
    inv = inventory(
        plugin("claude_code", "notes@official", "/h/a.json"),
        plugin("claude_code", "notes@other", "/h/b.json"),
    )
    change = Change(action="plugin.disable", steps=[step("claude_code", "notes@official")])
    assert after_words(change, inv) == [
        {"client": "claude_code", "state": "on", "word": "Loads once"}
    ]


def test_one_entry_per_client_even_with_two_steps():
    inv = inventory()
    change = Change(
        action="setup_server.update",
        steps=[step("claude_code", "agentsetup"), step("claude_code", "kitden")],
    )
    assert after_words(change, inv) == [{"client": "claude_code", "state": "on", "word": "Updated"}]


def test_cursor_gets_a_plugin_only_through_claude_code():
    change = Change(action="plugin.install", steps=[step("codex", "notes@official")])
    assert after_words(change, inventory(), cursor_imports=True) == [
        {"client": "codex", "state": "on", "word": "Loads"}
    ]


def test_a_skill_a_client_loads_from_a_plugin_counts_whatever_the_path(tmp_path):
    # The review reads the source folder by its real path; the skill list may name a link.
    real = tmp_path / "real/skills/a"
    real.mkdir(parents=True)
    (tmp_path / "link").symlink_to(tmp_path / "real")
    readers = ["claude_code", "cursor"]
    copy = FolderCopy(source=str(real), target="/h/.claude/skills/a", readers=readers)
    change = Change(
        action="plugin.skills",
        steps=[Step(client="claude_code", scope=Scope.USER, name="a", copy=copy)],
    )
    skills = [{"path": str(tmp_path / "link/skills/a"), "installed": {"cursor": "Via plugin"}}]
    assert after_words(change, inventory(), skills=skills) == [
        {"client": "claude_code", "state": "on", "word": "Loads"},
        {
            "client": "cursor",
            "state": "on",
            "word": "Loads twice",
            "note": "Cursor reads two folders that hold this skill, so it loads the skill twice.",
        },
    ]


def _move_change(home, monkeypatch, *wanted):
    import kitden.clients.base as base
    from kitden.changes.backup import ChangeStore
    from kitden.changes.engine import Engine
    from kitden.gateways import data_dir
    from kitden.views.inventory import build_inventory
    from tests.unit.test_local_gateway_move import FakeClaude, move

    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    change = Engine(ChangeStore(data_dir(home)), run=FakeClaude(home)).preview(
        "gateway.move", move(home, *wanted)
    )
    return change, build_inventory(home)


def test_a_remote_move_says_kitden_asked_the_server_once(tmp_path, monkeypatch):
    from tests.unit.test_local_gateway_move import add_claude, new_home

    home = new_home(tmp_path)
    monkeypatch.setattr("kitden.changes.actions.needs_sign_in", lambda url, headers: False)
    add_claude(home, "linear", {"type": "http", "url": "https://linear.invalid/mcp"})
    change, inv = _move_change(home, monkeypatch, ("claude_code", "linear"))
    note = after_words(change, inv, home=home)[0]["note"]
    assert "Kitden asked linear once whether it needs a sign-in." in note
    assert note.index("asked linear") < note.index("Applies to new sessions.")


def test_an_update_move_names_the_kept_switches(tmp_path, monkeypatch):
    import json

    from tests.unit.test_local_gateway_move import add_claude, gateway_file, new_home, write_json

    home = new_home(tmp_path)
    files = {"command": "npx", "args": ["files-mcp"]}
    write_json(gateway_file(home), {"servers": {"files": files}, "rules": {}})
    add_claude(home, "files", {"type": "stdio", **files})
    user = json.loads((home / ".claude/settings.json").read_text())
    user["permissions"] = {"deny": ["mcp__files__write"]}
    write_json(home / ".claude/settings.json", user)
    change, inv = _move_change(home, monkeypatch, ("claude_code", "files"))
    note = after_words(change, inv, home=home)[0]["note"]
    assert "keeps its" in note and "do not carry over" in note
