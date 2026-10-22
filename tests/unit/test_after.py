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
    from kitden.changes.backup import ChangeStore
    from kitden.changes.engine import Engine
    from kitden.gateways import data_dir
    from kitden.views.inventory import build_inventory
    from tests.unit.test_local_gateway_move import FakeClaude, move

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


GUARANTEE = "For a real guarantee, give github a token that can only read."


def _strict_note(tmp_path, monkeypatch, on, tools):
    from kitden.local_gateway.settings import save_tools
    from kitden.local_gateway.views import strict_steps
    from kitden.views.inventory import build_inventory
    from tests.unit.test_local_gateway_move import gateway_file, new_home, tool, write_json
    from tests.unit.test_local_gateway_views import KITDEN, add_entry

    home = new_home(tmp_path)
    add_entry(home, "cursor", "kitden", {"command": KITDEN, "args": ["mcp"]})
    rules = {} if on else {"global": {"github": {"mode": "strict"}}}
    write_json(gateway_file(home), {"servers": {"github": {"command": "npx"}}, "rules": rules})
    if tools:
        save_tools(home, "github", [tool("list_issues")])
    params = {"server": "github", "state": "on" if on else "off"}
    steps = strict_steps(home, params, {"github": [tool("list_issues")]} if tools else {})
    change = Change(action="gateway.strict", steps=steps)
    return after_words(change, build_inventory(home), home=home)[0]["note"]


def test_strict_on_says_only_turned_on_tools_are_offered(tmp_path, monkeypatch):
    note = _strict_note(tmp_path, monkeypatch, True, True)
    assert note.startswith(
        "Strict mode on for github: only tools you turned on are offered; a new tool waits "
        f"until you turn it on. {GUARANTEE}"
    )
    assert note.endswith(
        "A tool turned off is refused at once. The client shows the new list in a new session."
    )


def test_strict_off_says_a_tool_without_a_rule_is_on(tmp_path, monkeypatch):
    note = _strict_note(tmp_path, monkeypatch, False, True)
    assert note.startswith("Strict mode off for github: a tool without a rule is on.")
    assert note.endswith("Applies to new sessions.")


def test_strict_on_without_a_tool_list_says_its_tools_show_as_off(tmp_path, monkeypatch):
    note = _strict_note(tmp_path, monkeypatch, True, False)
    assert note.startswith(
        f"Strict mode on for github: its tools show as off until you turn them on. {GUARANTEE}"
    )


def test_a_move_with_a_codex_allowlist_says_strict_mode_not_server_off(tmp_path, monkeypatch):
    from kitden.local_gateway.settings import save_tools
    from tests.unit.test_local_gateway_move import add_codex, new_home, tool

    home = new_home(tmp_path)
    add_codex(home, "github", 'command = "npx"\nenabled_tools = ["list_issues"]')
    save_tools(home, "github", [tool("list_issues"), tool("create_issue")])
    change, inv = _move_change(home, monkeypatch, ("codex", "github"))
    note = after_words(change, inv, home=home)[0]["note"]
    assert "Strict mode on for github" in note
    assert "github will be off" not in note and "github stays off" not in note
    assert "is on only in" not in note
    assert "will offer its tools through Kitden" in note


def _rule_note(tmp_path, monkeypatch, on):
    from kitden.local_gateway.settings import rule_step
    from kitden.views.inventory import build_inventory
    from tests.unit.test_local_gateway_move import gateway_file, new_home, write_json
    from tests.unit.test_local_gateway_views import KITDEN, add_entry

    home = new_home(tmp_path)
    add_entry(home, "cursor", "kitden", {"command": KITDEN, "args": ["mcp"]})
    write_json(gateway_file(home), {"servers": {"github": {"command": "npx"}}, "rules": {}})
    step = rule_step(home, None, "github", "list_issues", "on" if on else "off")
    change = Change(action="gateway.rule", steps=[step])
    return after_words(change, build_inventory(home), home=home)[0]["note"]


def test_a_rule_says_a_tool_turned_off_is_refused_at_once(tmp_path, monkeypatch):
    note = _rule_note(tmp_path, monkeypatch, False)
    assert note == (
        "list_issues of github will be off in all projects. A tool turned off is refused at "
        "once. The client shows the new list in a new session."
    )
    assert "Applies to new sessions." not in note


def test_turning_off_several_tools_names_them_and_says_names_are_a_guess(tmp_path, monkeypatch):
    from kitden.local_gateway.settings import save_tools
    from kitden.local_gateway.views import rules_steps
    from kitden.views.inventory import build_inventory
    from tests.unit.test_local_gateway_move import gateway_file, new_home, tool, write_json
    from tests.unit.test_local_gateway_views import KITDEN, add_entry

    home = new_home(tmp_path)
    add_entry(home, "cursor", "kitden", {"command": KITDEN, "args": ["mcp"]})
    write_json(gateway_file(home), {"servers": {"github": {"command": "npx"}}, "rules": {}})
    names = ["create_issue", "delete_issue", "merge_pr"]
    save_tools(home, "github", [tool(n) for n in names])
    params = {"server": "github", "tools": names, "state": "off", "project": None}
    change = Change(action="gateway.rules", steps=rules_steps(home, params, {}))
    words = after_words(change, build_inventory(home), home=home)
    assert words[0]["state"] == "off"
    assert words[0]["note"] == (
        "3 tools of github will be off in all projects: create_issue, delete_issue, merge_pr. "
        "Hints come from the server and names are a guess; check the list. "
        f"{GUARANTEE} "
        "A tool turned off is refused at once. The client shows the new list in a new session."
    )


def test_turning_off_tools_for_all_projects_names_projects_that_keep_them_on(tmp_path, monkeypatch):
    from pathlib import Path

    from kitden.local_gateway.settings import save_tools
    from kitden.local_gateway.views import rules_steps
    from kitden.views.inventory import build_inventory
    from tests.unit.test_local_gateway_move import gateway_file, new_home, tool, write_json
    from tests.unit.test_local_gateway_views import KITDEN, add_entry

    home = new_home(tmp_path)
    add_entry(home, "cursor", "kitden", {"command": KITDEN, "args": ["mcp"]})
    inventory = build_inventory(home)
    website = next(p.path for p in inventory.projects if Path(p.path).name == "website")
    rules = {"projects": {website: {"github": {"tools": {"create_issue": "on"}}}}}
    write_json(gateway_file(home), {"servers": {"github": {"command": "npx"}}, "rules": rules})
    names = ["create_issue", "delete_issue"]
    save_tools(home, "github", [tool(n) for n in names])
    params = {"server": "github", "tools": names, "state": "off", "project": None}
    change = Change(action="gateway.rules", steps=rules_steps(home, params, {}))
    note = after_words(change, inventory, home=home)[0]["note"]
    assert note.startswith(
        "2 tools of github will be off in all projects: create_issue, delete_issue. "
        "They stay on for create_issue in website, which has its own rule. "
        "Hints come from the server"
    )


def imported(name):
    """A Claude Code plugin Cursor loads from Claude Code's install record."""
    source = Source(
        kind=SourceKind.OTHER_CLIENT_FOLDER, path="/h/i.json", owner_client="claude_code"
    )
    return Item(client="cursor", kind=ItemKind.PLUGIN, name=name, source=source, scope=Scope.USER)


def test_removing_one_of_two_claude_code_copies_says_cursor_keeps_the_other():
    inv = inventory(
        plugin("claude_code", "x@a", "/h/a.json"),
        plugin("claude_code", "x@b", "/h/a.json"),
        imported("x@a"),
        imported("x@b"),
    )
    change = Change(action="plugin.remove", steps=[step("claude_code", "x@a")])
    assert after_words(change, inv, cursor_imports=True) == [
        {
            "client": "claude_code",
            "state": "on",
            "word": "Loads once",
            "note": "Undo installs it again; its saved options are not brought back.",
        },
        {
            "client": "cursor",
            "state": "on",
            "word": "Loads once",
            "note": "Cursor loads Claude Code plugins, so it loses this copy and keeps "
            "the other Claude Code copy.",
        },
    ]
    # With a copy of its own, Cursor keeps that one.
    own = plugin("cursor", "x@cursor-public", "/h/c.json")
    words = after_words(
        change,
        inventory(plugin("claude_code", "x@a", "/h/a.json"), imported("x@a"), own),
        cursor_imports=True,
    )
    assert words[1]["note"].endswith("keeps its own.")


def test_add_missing_names_cursor_for_a_claude_code_user_plugin():
    change = Change(action="project.align", steps=[step("claude_code", "notes@official")])
    assert after_words(change, inventory(), cursor_imports=True) == [
        {"client": "claude_code", "state": "on", "word": "Loads"},
        {
            "client": "cursor",
            "state": "on",
            "word": "Loads",
            "note": "Cursor loads Claude Code plugins, so it gets this one too.",
        },
    ]
    assert after_words(change, inventory()) == [
        {"client": "claude_code", "state": "on", "word": "Loads"}
    ]


def server(client, name, via=None):
    source = Source(kind=SourceKind.FILE, path=f"/h/{client}.json", owner_client=client)
    return Item(
        client=client,
        kind=ItemKind.MCP_SERVER,
        name=name,
        source=source,
        scope=Scope.USER,
        via_gateway=via,
    )


def test_removing_from_the_kitden_gateway_counts_a_client_on_another_gateway():
    # Codex reaches files through a registered gateway, so "then in no client" is untrue.
    inv = inventory(server("codex", "files", via="gw-1"), server("cursor", "files", via="kitden"))
    edit = FileEdit(path="/h/settings.json", fmt="json", key=("servers", "files"), after=0)
    change = Change(
        action="gateway.remove",
        steps=[Step(client="kitden", scope=Scope.USER, name="files", edit=edit)],
    )
    assert after_words(change, inv) == [
        {"note": "Codex still reaches files through another gateway. Undo brings it back."}
    ]
