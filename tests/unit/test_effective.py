from kitden.model import Enabled, Item, ItemKind, Scope, Source, SourceKind
from kitden.views.effective import effective_view
from kitden.views.inventory import Inventory, build_inventory
from tests.conftest import make_home, write_cursor_fixture_state


def loaded(view):
    return {(str(i.kind), i.name, str(i.scope)) for i in view.items}


def shadows(view):
    return {
        (str(w.kind), w.name, str(w.scope), str(lo.scope), mode) for w, lo, mode in view.shadowed
    }


def _home(tmp_path, fixture):
    home = make_home(tmp_path, fixture)
    if fixture.startswith("cursor"):
        write_cursor_fixture_state(home)
    return home, build_inventory(home)


def test_claude_project_view_applies_overrides_and_turned_off_plugins(tmp_path):
    home, inventory = _home(tmp_path, "claude_code/2.1.283")
    view = effective_view(inventory, "claude_code", str(home / "work/website"))
    assert loaded(view) == {
        ("mcp_server", "github", "user"),
        ("mcp_server", "local-db", "local"),
        ("mcp_server", "docs", "project"),
        ("plugin", "notes@synced", "account"),
        ("plugin", "Claude account plugins and connectors", "account"),
        ("skill", "brandkit", "user"),
        ("skill", "shared-style", "user"),
        ("skill", "site-style", "project"),
        ("hook", "PreToolUse: Bash", "user"),
        ("marketplace", "claude-plugins-official", "user"),
        ("instructions", "CLAUDE.md", "user"),
        ("instructions", "review", "user"),
        ("instructions", "reviewer", "user"),
        ("instructions", "CLAUDE.md", "project"),
        ("instructions", "deploy", "project"),
    }
    # superpowers is on for the user but off in this project, so its skills do not load here.
    assert shadows(view) == {
        ("plugin", "superpowers@claude-plugins-official", "project", "user", "override")
    }


def test_claude_view_outside_projects_keeps_user_plugins_and_their_parts(tmp_path):
    _, inventory = _home(tmp_path, "claude_code/2.1.283")
    view = effective_view(inventory, "claude_code", None)
    names = {name for _, name, _ in loaded(view)}
    assert {"superpowers@claude-plugins-official", "brainstorming", "github"} <= names
    assert not {"local-db", "docs", "site-style", "md-index"} & names


def _item(name, scope, kind=ItemKind.MCP_SERVER, client="claude_code", project="/p"):
    source = Source(kind=SourceKind.FILE, path=f"/{scope}.json", owner_client=client)
    return Item(
        client=client,
        kind=kind,
        name=name,
        source=source,
        scope=scope,
        project=None if scope in (Scope.USER, Scope.MANAGED) else project,
    )


def test_claude_mcp_precedence_is_local_then_project_then_user():
    inventory = Inventory(
        items=[_item("x", Scope.USER), _item("x", Scope.PROJECT), _item("x", Scope.LOCAL)]
    )
    view = effective_view(inventory, "claude_code", "/p")
    assert loaded(view) == {("mcp_server", "x", "local")}
    assert shadows(view) == {
        ("mcp_server", "x", "local", "project", "override"),
        ("mcp_server", "x", "local", "user", "override"),
    }


def test_claude_personal_skill_beats_project_skill():
    inventory = Inventory(
        items=[
            _item("style", Scope.PROJECT, ItemKind.SKILL),
            _item("style", Scope.USER, ItemKind.SKILL),
        ]
    )
    view = effective_view(inventory, "claude_code", "/p")
    assert loaded(view) == {("skill", "style", "user")}


def test_desktop_code_tab_adds_its_config_and_wins_on_a_name_clash(tmp_path):
    home, inventory = _home(tmp_path, "claude_code/2.1.283")
    desktop_github = Item(
        client="claude_desktop_code_tab",
        kind=ItemKind.MCP_SERVER,
        name="github",
        source=Source(
            kind=SourceKind.FILE, path="/desktop.json", owner_client="claude_desktop_code_tab"
        ),
        scope=Scope.USER,
    )
    inventory.items.append(desktop_github)
    view = effective_view(inventory, "claude_desktop_code_tab", str(home / "work/website"))
    clients = {(i.client, i.name) for i in view.items if str(i.kind) == "mcp_server"}
    assert clients == {
        ("claude_desktop_code_tab", "metamcp-local"),
        ("claude_desktop_code_tab", "github"),
        ("claude_code", "local-db"),
        ("claude_code", "docs"),
    }


def test_codex_merges_project_fields_and_loads_both_same_name_skills(tmp_path):
    home, inventory = _home(tmp_path, "codex/0.159.2")
    view = effective_view(inventory, "codex", str(home / "work/api"))
    assert loaded(view) == {
        ("mcp_server", "neon", "project"),
        ("mcp_server", "langfuse-data", "user"),
        ("mcp_server", "api-docs", "project"),
        ("plugin", "browser@openai-bundled", "user"),
        ("plugin", "gmail@openai-curated-remote", "user"),
        ("marketplace", "openai-bundled", "user"),
        ("skill", "docker-expert", "user"),
        ("skill", "langfuse", "user"),
        ("skill", "api-style", "project"),
    }
    assert shadows(view) == {("mcp_server", "neon", "project", "user", "merged")}
    assert len([i for i in view.items if i.name == "docker-expert"]) == 2


def test_codex_untrusted_project_loads_nothing_from_its_folder(tmp_path):
    home, inventory = _home(tmp_path, "codex/0.159.2")
    view = effective_view(inventory, "codex", str(home / "work/untrusted"))
    assert "evil" not in {i.name for i in view.items}


def test_cursor_project_wins_and_imported_items_load(tmp_path):
    home, inventory = _home(tmp_path, "cursor/3.21.16")
    view = effective_view(inventory, "cursor", str(home / "work/site"))
    assert loaded(view) == {
        ("mcp_server", "Neon", "user"),
        ("mcp_server", "n8n-mcp", "user"),
        ("mcp_server", "site-db", "project"),
        ("skill", "docker-expert", "user"),
        ("skill", "brandkit", "user"),
        ("skill", "langfuse", "user"),
        ("plugin", "superpowers@cursor-public", "user"),
        ("plugin", "plugin 4800 (name not stored locally)", "user"),
        ("plugin", "langfuse@cursor-public", "project"),
        ("plugin", "superpowers@claude-plugins-official", "user"),
        ("hook", "afterFileEdit", "user"),
        ("hook", "PreToolUse: Bash", "user"),
        ("marketplace", "team-mkt", "user"),
    }
    assert shadows(view) == set()


def test_turned_off_items_never_load():
    off = Item(
        client="codex",
        kind=ItemKind.MCP_SERVER,
        name="x",
        source=Source(kind=SourceKind.FILE, path="/c", owner_client="codex"),
        scope=Scope.USER,
        enabled=Enabled.OFF,
    )
    assert effective_view(Inventory(items=[off]), "codex", None).items == []
