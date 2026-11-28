"""The short project list: one row per real project."""

from kitden.changes.actions import KITDEN_GATEWAY
from kitden.clients.base import project
from kitden.model import Enabled, Item, ItemKind, Scope, Source, SourceKind
from kitden.views.inventory import Inventory
from kitden.views.project_rows import listed_items, own_rule_paths, project_rows, row_dict


def folder(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def worktree(main, folder_path, name):
    """A git worktree of `main` at `folder_path`: its .git is a file that points into main."""
    (main / ".git" / "worktrees" / name).mkdir(parents=True, exist_ok=True)
    folder(folder_path)
    (folder_path / ".git").write_text(f"gitdir: {main}/.git/worktrees/{name}\n")
    return folder_path


def item(name, path=None, kind=ItemKind.SKILL, scope=Scope.PROJECT, **more):
    source = Source(kind=SourceKind.FILE, path=f"/files/{name}", owner_client="claude_code")
    return Item(
        client="claude_code",
        kind=kind,
        name=name,
        source=source,
        scope=scope,
        project=str(path) if path else None,
        **more,
    )


def rows_of(paths, items=(), ruled=(), client="claude_code"):
    inventory = Inventory(projects=[project(str(p), client) for p in paths], items=list(items))
    return project_rows(inventory, ruled)


def ids(*paths):
    return tuple(project(str(p), "claude_code").id for p in paths)


def test_two_spellings_of_one_folder_are_one_row(tmp_path):
    main = folder(tmp_path / "work/kitden")
    link = tmp_path / "work/mcp-gateway"
    link.symlink_to(main)
    rows = rows_of([main, link])
    assert [r.project.path for r in rows] == [str(main)]
    assert rows[0].folded == ids(link)


def test_the_row_is_the_real_spelling_else_the_first_by_path(tmp_path):
    target = folder(tmp_path / "x")
    (tmp_path / "b-link").symlink_to(target)
    (tmp_path / "a-link").symlink_to(target)
    rows = rows_of([tmp_path / "b-link", tmp_path / "a-link"])
    assert [r.project.path for r in rows] == [str(tmp_path / "a-link")]
    assert rows[0].folded == ids(tmp_path / "b-link")


def test_a_worktree_folds_into_its_main_checkout(tmp_path):
    app = folder(tmp_path / "app")
    f = worktree(app, app / ".claude/worktrees/f", "f")
    g = worktree(app, tmp_path / "elsewhere/g", "g")
    (tmp_path / "link").symlink_to(app)
    through_link = tmp_path / "link/.claude/worktrees/f"
    rows = rows_of([app, f, g, through_link])
    assert [r.project.path for r in rows] == [str(app)]
    assert set(rows[0].folded) == set(ids(f, g, through_link))


def test_a_gone_folder_is_no_row(tmp_path):
    assert rows_of([tmp_path / "work/old"], client="codex") == []


def test_an_entry_with_a_setting_under_its_own_path_stays_a_row(tmp_path):
    # A gone folder with a Claude Code local server.
    gone = tmp_path / "gone"
    server = item("db", gone, kind=ItemKind.MCP_SERVER, scope=Scope.LOCAL)
    rows = rows_of([gone], [server])
    assert [(r.project.path, r.project.exists) for r in rows] == [(str(gone), False)]

    # A worktree with a user server's rule of its own.
    app = folder(tmp_path / "app")
    wt = worktree(app, app / ".claude/worktrees/wt", "wt")
    user = item(
        "search",
        kind=ItemKind.MCP_SERVER,
        scope=Scope.USER,
        project_rules=((str(wt), Enabled.OFF, Scope.LOCAL, "off"),),
    )
    rows = rows_of([app, wt], [user])
    assert [r.project.path for r in rows] == [str(app), str(wt)]
    assert ids(wt)[0] not in rows[0].folded

    # A symlink spelling with a gateway rule.
    link = tmp_path / "link"
    link.symlink_to(app)
    rows = rows_of([app, link], ruled={str(link)})
    assert [r.project.path for r in rows] == [str(app), str(link)]
    assert ids(link)[0] not in rows[0].folded
    assert rows[1].folded == ()

    # An existing worktree with a local server of its own.
    wt2 = worktree(app, app / ".claude/worktrees/wt2", "wt2")
    local = item("db", wt2, kind=ItemKind.MCP_SERVER, scope=Scope.LOCAL)
    rows = rows_of([app, wt2], [local])
    assert [r.project.path for r in rows] == [str(app), str(wt2)]
    assert ids(wt2)[0] not in rows[0].folded


def test_own_is_servers_skills_plugins_hooks_or_gateway_rules(tmp_path):
    app = folder(tmp_path / "app")

    def own(items=(), ruled=(), paths=(app,)):
        return next(r for r in rows_of(paths, items, ruled) if r.project.path == str(app)).own

    assert own([item("CLAUDE.md", app, kind=ItemKind.INSTRUCTIONS)]) is False
    assert own([item("demo", app)]) is True
    assert own(ruled={str(app)}) is True
    user = item(
        "search",
        kind=ItemKind.MCP_SERVER,
        scope=Scope.USER,
        project_rules=((str(app), Enabled.OFF, Scope.LOCAL, "off"),),
    )
    assert own([user]) is True
    gateway = item("db", app, kind=ItemKind.MCP_SERVER, via_gateway=KITDEN_GATEWAY)
    assert own([gateway]) is False
    wt = worktree(app, app / ".claude/worktrees/wt", "wt")
    assert own([item("demo", wt)], paths=(app, wt)) is False


def test_a_worktree_of_a_worktree_folds_into_no_folded_entry(tmp_path):
    # A hand-made `.git` file: x points into m, and m is itself a worktree of n.
    n = folder(tmp_path / "n")
    m = worktree(n, tmp_path / "m", "m")
    x = folder(tmp_path / "x")
    (x / ".git").write_text(f"gitdir: {m}/.git/worktrees/x\n")
    rows = rows_of([n, m, x])
    # m folds into n; x stays a row, since m is no row to fold into.
    assert [r.project.path for r in rows] == [str(n), str(x)]
    assert rows[0].folded == ids(m)
    assert rows[1].folded == ()


def test_a_symlink_loop_is_a_gone_folder(tmp_path):
    loop = tmp_path / "loop"
    loop.symlink_to(loop)
    assert rows_of([loop]) == []


def test_a_worktree_whose_main_checkout_is_gone_stays_a_row(tmp_path):
    wt = folder(tmp_path / "wt")
    (wt / ".git").write_text(f"gitdir: {tmp_path}/gone/.git/worktrees/wt\n")
    rows = rows_of([wt])
    assert [r.project.path for r in rows] == [str(wt)]

    main = folder(tmp_path / "main")
    other = worktree(main, tmp_path / "other", "other")
    rows = rows_of([other])
    assert [r.project.path for r in rows] == [str(other)]


def test_rows_with_the_same_folder_name_get_their_parent(tmp_path):
    paths = [tmp_path / p for p in ("a/x", "b/x", "c/work/x", "d/work/x", "y")]
    for path in paths:
        folder(path)
    rows = rows_of(paths)
    assert [r.parent for r in rows] == ["a", "b", "c/work", "d/work", None]


def test_the_home_folder_is_a_row_and_takes_no_folder_in(tmp_path):
    home = folder(tmp_path / "home")
    folder(home / ".git")
    app = folder(home / "work/app")
    rows = rows_of([home, app], [item("demo", app)])
    assert [r.project.path for r in rows] == [str(home), str(app)]
    assert rows[0].own is False
    assert rows[0].folded == ()


def test_listed_items_leave_out_folded_and_gone_entries(tmp_path):
    app = folder(tmp_path / "app")
    wt = worktree(app, app / ".claude/worktrees/wt", "wt")
    gone = tmp_path / "gone"
    items = [item("user"), item("app", app), item("wt", wt), item("gone", gone)]
    inventory = Inventory(
        projects=[project(str(p), "claude_code") for p in (app, wt, gone)], items=items
    )
    listed = listed_items(inventory, project_rows(inventory))
    assert [i.name for i in listed] == ["user", "app"]


def test_own_rule_paths_skips_empty_entries():
    assert own_rule_paths({"rules": {"projects": {"/a": {"s": "off"}, "/b": {}}}}) == {"/a"}


def test_row_dict_has_the_page_fields(tmp_path):
    app = folder(tmp_path / "app")
    link = tmp_path / "link"
    link.symlink_to(app)
    row = rows_of([app, link])[0]
    assert row_dict(row) == {
        "id": row.project.id,
        "path": str(app),
        "exists": True,
        "known_by": ["claude_code"],
        "folded": list(ids(link)),
        "own": False,
        "parent": None,
    }
