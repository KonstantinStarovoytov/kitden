"""Where a change goes, for the review's first sentence, and what Undo cannot bring back
(spec 3.3). Synthetic steps; every folder is under tmp_path."""

from kitden.model import (
    Change,
    Client,
    ClientStatus,
    FileEdit,
    FolderCopy,
    FolderRemoval,
    Item,
    ItemKind,
    KeychainItem,
    Scope,
    Source,
    SourceKind,
    Step,
)
from kitden.views import after
from kitden.views.inventory import Inventory
from kitden.views.review import change_target, step_project, undo_note
from kitden.views.words import KEYCHAIN_UNDO, REMOVE_NOTE


def edit(path, scope=Scope.PROJECT, key=("mcpServers", "db"), client="cursor"):
    change = FileEdit(path=str(path), fmt="json", key=key, after=None)
    return Step(client=client, scope=scope, name="db", edit=change)


def rule(home, project):
    """A Kitden gateway rule for one project, as rule_step makes it."""
    key = ("rules", "projects", str(project), "github", "server")
    return edit(home / ".kitden/settings.json", Scope.USER, key, client="kitden")


def target(steps, projects):
    change = Change(action="mcp.remove_direct", steps=steps)
    return change_target(change, [str(p) for p in projects])


def test_one_project_file_is_that_project_and_others_are_unchanged(tmp_path):
    web, api = tmp_path / "web", tmp_path / "api"
    assert target([edit(web / ".mcp.json")], [web, api]) == {
        "scope": "project",
        "project": str(web),
        "others_unchanged": True,
    }


def test_a_parent_project_with_a_known_project_inside_is_not_contained(tmp_path):
    work = tmp_path / "work"
    # A gateway rule passes down to a child project.
    assert target([rule(tmp_path, work)], [work, work / "site"]) == {
        "scope": "project",
        "project": str(work),
        "others_unchanged": False,
    }


def test_a_child_project_under_a_known_parent_is_not_contained(tmp_path):
    work = tmp_path / "work"
    site = work / "site"
    # A client working in the parent may read the child's files too.
    assert target([edit(site / ".mcp.json")], [work, site]) == {
        "scope": "project",
        "project": str(site),
        "others_unchanged": False,
    }


def test_folders_that_only_start_alike_are_not_nested(tmp_path):
    web, website = tmp_path / "work/web", tmp_path / "work/website"
    projects = [str(web), str(website)]
    assert target([edit(web / ".mcp.json")], projects)["others_unchanged"] is True
    assert step_project(edit(website / ".mcp.json"), projects) == str(website)


def test_a_local_entry_in_claude_json_counts_as_its_project(tmp_path):
    web = tmp_path / "work/web"
    local = edit(tmp_path / ".claude.json", Scope.LOCAL, ("projects", str(web), "mcpServers", "db"))
    assert step_project(local, [str(web)]) == str(web)
    # A project Kitden does not know is no project of the list.
    assert step_project(local, [str(tmp_path / "work/api")]) is None


def test_a_copied_or_removed_skill_folder_counts_as_its_project(tmp_path):
    web = tmp_path / "web"
    copy = FolderCopy(source="/s/tidy", target=str(web / ".agents/skills/tidy"), project=str(web))
    copied = Step(client="codex", scope=Scope.PROJECT, name="tidy", copy=copy)
    removal = FolderRemoval(path=str(web / ".claude/skills/tidy"))
    removed = Step(client="claude_code", scope=Scope.PROJECT, name="tidy", removal=removal)
    assert step_project(copied, [str(web)]) == str(web)
    assert step_project(removed, [str(web)]) == str(web)


def test_user_files_are_all_projects_and_a_mix_is_mixed(tmp_path):
    web, api = tmp_path / "web", tmp_path / "api"
    user = edit(tmp_path / ".cursor/mcp.json", Scope.USER)
    everywhere = {"scope": "all", "project": None, "others_unchanged": False}
    mixed = {"scope": "mixed", "project": None, "others_unchanged": False}
    assert target([user], [web]) == everywhere
    assert target([user, edit(web / ".mcp.json")], [web]) == mixed
    assert target([edit(web / ".mcp.json"), edit(api / ".mcp.json")], [web, api]) == mixed
    # A project step outside every known project promises nothing.
    assert target([edit(tmp_path / "other/.mcp.json")], [web]) == mixed


def test_a_project_reached_through_a_link_still_matches(tmp_path):
    real = tmp_path / "real/web"
    real.mkdir(parents=True)
    link = tmp_path / "web"
    link.symlink_to(real)
    # The known list spells the link; the step names the real folder.
    assert step_project(edit(real / ".mcp.json"), [str(link)]) == str(link)
    assert target([rule(tmp_path, real)], [link])["project"] == str(link)


def test_removing_a_claude_code_plugin_names_the_undo_limit(tmp_path):
    plugin = edit(tmp_path / ".claude/settings.json", Scope.USER, client="claude_code")
    assert undo_note(Change(action="plugin.remove", steps=[plugin])) == REMOVE_NOTE
    assert REMOVE_NOTE == "Undo installs it again; its saved options are not brought back."
    assert undo_note(Change(action="plugin.disable", steps=[plugin])) is None
    codex = edit(tmp_path / ".codex/config.toml", Scope.USER, client="codex")
    assert undo_note(Change(action="plugin.remove", steps=[codex])) is None
    # The note is the review's lede now, said once: no After chip carries it.
    assert not hasattr(after, "REMOVE_NOTE")


def test_a_client_command_never_promises_other_projects_are_unchanged(tmp_path):
    web = tmp_path / "web"
    # `claude plugin uninstall -s project` runs in the project; Kitden cannot vouch for more
    # than the file it checks.
    uninstall = edit(web / ".claude/settings.json", client="claude_code")
    uninstall.command = ["claude", "plugin", "uninstall", "x@a", "-s", "project"]
    assert target([uninstall], [web]) == {
        "scope": "project",
        "project": str(web),
        "others_unchanged": False,
    }


def server(client, scope, project=None, path="/h/.mcp.json"):
    source = Source(kind=SourceKind.FILE, path=path, owner_client=client)
    kind = ItemKind.MCP_SERVER
    return Item(client=client, kind=kind, name="db", source=source, scope=scope, project=project)


def inventory(*items):
    found = [Client(id=c, display_name=c, status=ClientStatus.FOUND) for c in ("claude_code",)]
    return Inventory(clients=found, items=list(items))


def test_a_definition_the_picked_project_overrides_goes_to_all_projects_but_that_one(tmp_path):
    web = str(tmp_path / "web")
    user = edit(tmp_path / ".claude.json", Scope.USER, client="claude_code")
    inv = inventory(server("claude_code", Scope.USER), server("claude_code", Scope.LOCAL, web))
    change = Change(action="mcp.remove_direct", steps=[user])
    assert change_target(change, [web], inv, web) == {
        "scope": "others",
        "project": web,
        "others_unchanged": False,
    }
    # With All projects picked, or a project without its own definition, it is all projects.
    assert change_target(change, [web], inv, None)["scope"] == "all"
    other = str(tmp_path / "api")
    assert change_target(change, [web, other], inv, other)["scope"] == "all"
    # A client the step reaches that loads the user definition there still changes.
    user.reaches = ["claude_code", "cursor"]
    assert change_target(change, [web], inv, web)["scope"] == "all"


def test_a_merged_definition_still_changes_the_picked_project(tmp_path):
    api = str(tmp_path / "api")
    codex = edit(tmp_path / ".codex/config.toml", Scope.USER, client="codex")
    found = [Client(id="codex", display_name="Codex", status=ClientStatus.FOUND)]
    inv = Inventory(
        clients=found,
        items=[server("codex", Scope.USER), server("codex", Scope.PROJECT, api)],
    )
    change = Change(action="mcp.remove_direct", steps=[codex])
    # Codex merges a project's fields over the user entry: removing it changes the merge there.
    assert change_target(change, [api], inv, api)["scope"] == "all"


def test_a_keychain_item_that_was_there_keeps_its_new_value_after_undo(tmp_path):
    step = edit(tmp_path / ".kitden/settings.json", Scope.USER, client="kitden")
    step.keychain = [
        KeychainItem(server="github", key="TOKEN", existed=True),
        KeychainItem(server="github", key="URL", existed=False),
    ]
    change = Change(action="gateway.keychain", steps=[step])
    assert undo_note(change) == KEYCHAIN_UNDO.format("github/TOKEN")
    assert undo_note(change) == "Undo leaves github/TOKEN in your Keychain with the new value."
    step.keychain[1].existed = True
    assert undo_note(change).startswith("Undo leaves github/TOKEN and github/URL in your Keychain")
    step.keychain = [KeychainItem(server="github", key="TOKEN", existed=False)]
    assert undo_note(change) is None
