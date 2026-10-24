"""Finding the folder of a client session and the known projects whose rules apply there."""

from pathlib import Path

from kitden.local_gateway.project import (
    main_checkout,
    project_chain,
    project_chains,
    session_folder,
)


def project(tmp_path, name="app"):
    folder = tmp_path / name
    (folder / ".git").mkdir(parents=True)
    return folder


def worktree(tmp_path, main, name="feature"):
    """A git worktree of `main`: its .git is a file that points into the main checkout."""
    (main / ".git" / "worktrees" / name).mkdir(parents=True)
    folder = tmp_path / "worktrees" / name
    folder.mkdir(parents=True)
    (folder / ".git").write_text(f"gitdir: {main}/.git/worktrees/{name}\n")
    return folder


def find(tmp_path, known, env=None, roots=(), cwd=None, home=None):
    """The chain of known projects for a session, as the gateway finds it."""
    home = home or tmp_path / "home"
    folder = session_folder(env or {}, list(roots), cwd or home, home)
    return project_chain(folder, home, [str(p) for p in known])


def test_claude_project_dir_wins_over_roots_and_cwd(tmp_path):
    a, b, c = project(tmp_path, "a"), project(tmp_path, "b"), project(tmp_path, "c")
    env = {"CLAUDE_PROJECT_DIR": str(a), "WORKSPACE_FOLDER_PATHS": str(c)}
    assert find(tmp_path, [a, b, c], env, [b.as_uri()], cwd=c) == [str(a)]


def test_the_first_root_is_read_as_a_file_uri(tmp_path):
    a, b = project(tmp_path, "a"), project(tmp_path, "b")
    env = {"WORKSPACE_FOLDER_PATHS": str(b)}
    assert find(tmp_path, [a, b], env, [a.as_uri(), b.as_uri()], cwd=b) == [str(a)]


def test_a_root_with_an_escaped_space_is_read(tmp_path):
    spaced = project(tmp_path, "my app")
    assert "%20" in spaced.as_uri()
    assert find(tmp_path, [spaced], roots=[spaced.as_uri()]) == [str(spaced)]


def test_a_subfolder_belongs_to_its_project(tmp_path):
    app = project(tmp_path)
    sub = app / "packages" / "web"
    sub.mkdir(parents=True)
    assert find(tmp_path, [app], {"CLAUDE_PROJECT_DIR": str(sub)}) == [str(app)]
    assert find(tmp_path, [app], roots=[sub.as_uri()]) == [str(app)]
    assert find(tmp_path, [app], cwd=sub) == [str(app)]


def test_every_known_project_that_holds_the_folder_is_in_the_chain_deepest_first(tmp_path):
    outer = project(tmp_path, "outer")
    inner = project(outer, "inner")
    both = [str(inner), str(outer)]
    assert find(tmp_path, [outer, inner], {"CLAUDE_PROJECT_DIR": str(inner)}) == both
    assert find(tmp_path, [inner, outer], {"CLAUDE_PROJECT_DIR": str(inner / "src")}) == both
    assert find(tmp_path, [outer, inner], {"CLAUDE_PROJECT_DIR": str(outer)}) == [str(outer)]


def test_a_worktree_maps_to_its_main_checkout(tmp_path):
    app = project(tmp_path)
    wt = worktree(tmp_path, app)
    assert find(tmp_path, [app], {"CLAUDE_PROJECT_DIR": str(wt)}) == [str(app)]
    assert find(tmp_path, [app], cwd=wt) == [str(app)]  # Codex starts in a worktree


def test_a_known_worktree_comes_before_its_main_checkout(tmp_path):
    app = project(tmp_path)
    wt = worktree(tmp_path, app)
    (wt / "src").mkdir()
    chain = [str(wt), str(app)]
    assert find(tmp_path, [app, wt], {"CLAUDE_PROJECT_DIR": str(wt)}) == chain
    assert find(tmp_path, [app, wt], cwd=wt / "src") == chain
    # Only the worktree is known: the main checkout adds nothing.
    assert find(tmp_path, [wt], cwd=wt) == [str(wt)]


def test_a_worktree_inside_its_main_checkout_is_not_listed_twice(tmp_path):
    app = project(tmp_path)
    (app / ".git" / "worktrees" / "x").mkdir(parents=True)
    wt = app / ".claude" / "worktrees" / "x"  # where Claude Code Desktop puts its worktrees
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {app}/.git/worktrees/x\n")
    assert find(tmp_path, [app, wt], {"CLAUDE_PROJECT_DIR": str(wt)}) == [str(wt), str(app)]
    assert find(tmp_path, [app], {"CLAUDE_PROJECT_DIR": str(wt)}) == [str(app)]


def test_the_session_folder_is_the_first_named_folder_as_it_is_named(tmp_path):
    home = tmp_path / "home"
    app = project(tmp_path)
    wt = worktree(tmp_path, app)
    env = {"CLAUDE_PROJECT_DIR": str(wt)}
    # Before the worktree maps to its main checkout, and before any project matches.
    assert session_folder(env, [], home, home) == str(wt)
    assert session_folder({}, [], wt / "src", home) == str(wt / "src")
    assert session_folder({}, [], home, home) is None
    assert project_chain(None, home, [str(app)]) == []


def test_a_worktree_with_a_relative_gitdir_maps_too(tmp_path):
    app = project(tmp_path)
    (app / ".git" / "worktrees" / "feature").mkdir(parents=True)
    wt = tmp_path / "worktrees" / "feature"
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: ../../app/.git/worktrees/feature\n")
    assert main_checkout(wt) == app


def test_main_checkout_leaves_everything_else_alone(tmp_path):
    app = project(tmp_path)
    plain = tmp_path / "plain"
    plain.mkdir()
    submodule = tmp_path / "sub"
    submodule.mkdir()
    (submodule / ".git").write_text(f"gitdir: {app}/.git/modules/sub\n")
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / ".git").write_text("not a pointer")
    missing = tmp_path / "missing"
    for folder in (app, plain, submodule, broken, missing):
        assert main_checkout(folder) == folder


def test_home_or_an_unknown_folder_gives_no_project(tmp_path):
    app = project(tmp_path)
    home = tmp_path / "home"
    chat = tmp_path / "Documents" / "Codex" / "2026-10-21" / "chat"  # a Codex per-chat folder
    chat.mkdir(parents=True)
    assert find(tmp_path, [app], cwd=home, home=home) == []
    assert find(tmp_path, [app], cwd=Path("/")) == []
    assert find(tmp_path, [app], cwd=chat) == []
    assert find(tmp_path, [app]) == []


def test_the_first_candidate_wins_even_when_it_is_unknown(tmp_path):
    app, other = project(tmp_path, "app"), project(tmp_path, "other")
    assert find(tmp_path, [app], {"CLAUDE_PROJECT_DIR": str(other)}, cwd=app) == []


def test_an_empty_variable_or_a_root_that_is_not_a_file_is_skipped(tmp_path):
    app = project(tmp_path)
    env = {"CLAUDE_PROJECT_DIR": "", "WORKSPACE_FOLDER_PATHS": str(app)}
    assert find(tmp_path, [app], env, ["https://example.com/x"]) == [str(app)]


def test_cursor_workspace_paths_are_read(tmp_path):
    a, b = project(tmp_path, "a"), project(tmp_path, "b")
    env = {"WORKSPACE_FOLDER_PATHS": f"{b},{a}"}
    assert find(tmp_path, [a, b], env, cwd=tmp_path / "home") == [str(b)]


def test_a_known_home_or_root_matches_only_itself(tmp_path):
    home = tmp_path / "home"
    chat = home / "Documents" / "Codex" / "2026-10-21" / "chat"
    chat.mkdir(parents=True)
    assert find(tmp_path, [home], cwd=chat, home=home) == []
    assert find(tmp_path, [home], {"CLAUDE_PROJECT_DIR": str(chat)}, home=home) == []
    assert find(tmp_path, [home], {"CLAUDE_PROJECT_DIR": str(home)}, home=home) == [str(home)]
    assert find(tmp_path, ["/"], {"CLAUDE_PROJECT_DIR": str(chat)}) == []
    assert find(tmp_path, ["/"], {"CLAUDE_PROJECT_DIR": "/"}) == ["/"]


def test_a_project_inside_a_known_home_still_wins(tmp_path):
    home = tmp_path / "home"
    app = project(home, "app")
    assert find(tmp_path, [home, app], cwd=app / "src", home=home) == [str(app)]


def test_a_symlinked_folder_matches_its_real_path(tmp_path):
    app = project(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(app)
    sub = app / "src"
    sub.mkdir()
    # Known through the link, session in the real folder: the answer is the known string.
    assert find(tmp_path, [link], cwd=app) == [str(link)]
    assert find(tmp_path, [link], {"CLAUDE_PROJECT_DIR": str(sub)}) == [str(link)]
    # Known by its real path, session through the link.
    assert find(tmp_path, [app], {"CLAUDE_PROJECT_DIR": str(link)}) == [str(app)]
    assert find(tmp_path, [app], roots=[(link / "src").as_uri()]) == [str(app)]


def test_a_symlinked_home_is_still_the_home(tmp_path):
    real_home = tmp_path / "real-home"
    real_home.mkdir()
    home = tmp_path / "home"
    home.symlink_to(real_home)
    assert find(tmp_path, [home], cwd=real_home, home=home) == []
    assert find(tmp_path, [real_home], cwd=real_home, home=home) == []


def test_a_subfolder_of_a_worktree_maps_to_the_main_checkout(tmp_path):
    app = project(tmp_path)
    wt = worktree(tmp_path, app)
    sub = wt / "packages" / "web"
    sub.mkdir(parents=True)
    assert find(tmp_path, [app], {"CLAUDE_PROJECT_DIR": str(sub)}) == [str(app)]
    assert find(tmp_path, [app], roots=[sub.as_uri()]) == [str(app)]
    assert find(tmp_path, [app], cwd=sub) == [str(app)]


def test_the_walk_up_stops_at_the_first_git_folder(tmp_path):
    app = project(tmp_path)
    wt = worktree(tmp_path, app)
    nested = wt / "vendor" / "lib"
    (nested / ".git").mkdir(parents=True)
    assert find(tmp_path, [app], cwd=nested / "src") == []


def test_the_walk_up_never_goes_past_the_home_folder(tmp_path):
    app = project(tmp_path)
    home = worktree(tmp_path, app, "home")  # a home folder that holds a worktree's .git file
    chat = home / "Documents" / "chat"
    chat.mkdir(parents=True)
    assert find(tmp_path, [app], cwd=chat, home=home) == []


def test_every_chain_at_once_is_each_projects_own_chain(tmp_path):
    home = tmp_path / "home"
    app = project(tmp_path)
    wt = worktree(tmp_path, app)
    known = [str(p) for p in (home, app, app / "web", wt, wt / "docs")]
    for folder in known:
        Path(folder).mkdir(parents=True, exist_ok=True)
    chains = project_chains(home, known)
    assert chains == {k: project_chain(k, home, known) for k in known}
    assert chains[str(wt / "docs")] == [str(wt / "docs"), str(wt), str(app)]
