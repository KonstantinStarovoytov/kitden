"""The review's first line: what each client shows after the change (feature 004)."""

from kitden.model import (
    Change,
    Client,
    ClientStatus,
    FileEdit,
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
