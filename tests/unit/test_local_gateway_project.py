"""Finding the project of a client session."""

from pathlib import Path

from kitden.local_gateway.project import find_project, main_checkout


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
    home = home or tmp_path / "home"
    return find_project(env or {}, list(roots), cwd or home, home, [str(p) for p in known])


def test_claude_project_dir_wins_over_roots_and_cwd(tmp_path):
    a, b, c = project(tmp_path, "a"), project(tmp_path, "b"), project(tmp_path, "c")
    env = {"CLAUDE_PROJECT_DIR": str(a), "WORKSPACE_FOLDER_PATHS": str(c)}
    assert find(tmp_path, [a, b, c], env, [b.as_uri()], cwd=c) == str(a)


def test_the_first_root_is_read_as_a_file_uri(tmp_path):
    a, b = project(tmp_path, "a"), project(tmp_path, "b")
    env = {"WORKSPACE_FOLDER_PATHS": str(b)}
    assert find(tmp_path, [a, b], env, [a.as_uri(), b.as_uri()], cwd=b) == str(a)


def test_a_root_with_an_escaped_space_is_read(tmp_path):
    spaced = project(tmp_path, "my app")
    assert "%20" in spaced.as_uri()
    assert find(tmp_path, [spaced], roots=[spaced.as_uri()]) == str(spaced)


def test_a_subfolder_belongs_to_its_project(tmp_path):
    app = project(tmp_path)
    sub = app / "packages" / "web"
    sub.mkdir(parents=True)
    assert find(tmp_path, [app], {"CLAUDE_PROJECT_DIR": str(sub)}) == str(app)
    assert find(tmp_path, [app], roots=[sub.as_uri()]) == str(app)
    assert find(tmp_path, [app], cwd=sub) == str(app)


def test_the_longest_matching_project_wins(tmp_path):
    outer = project(tmp_path, "outer")
    inner = project(outer, "inner")
    assert find(tmp_path, [outer, inner], {"CLAUDE_PROJECT_DIR": str(inner)}) == str(inner)
    assert find(tmp_path, [inner, outer], {"CLAUDE_PROJECT_DIR": str(inner / "src")}) == str(inner)


def test_a_worktree_maps_to_its_main_checkout(tmp_path):
    app = project(tmp_path)
    wt = worktree(tmp_path, app)
    assert find(tmp_path, [app], {"CLAUDE_PROJECT_DIR": str(wt)}) == str(app)
    assert find(tmp_path, [app], cwd=wt) == str(app)  # Codex starts in a worktree


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
    assert find(tmp_path, [app], cwd=home, home=home) is None
    assert find(tmp_path, [app], cwd=Path("/")) is None
    assert find(tmp_path, [app], cwd=chat) is None
    assert find(tmp_path, [app]) is None


def test_the_first_candidate_wins_even_when_it_is_unknown(tmp_path):
    app, other = project(tmp_path, "app"), project(tmp_path, "other")
    assert find(tmp_path, [app], {"CLAUDE_PROJECT_DIR": str(other)}, cwd=app) is None


def test_an_empty_variable_or_a_root_that_is_not_a_file_is_skipped(tmp_path):
    app = project(tmp_path)
    env = {"CLAUDE_PROJECT_DIR": "", "WORKSPACE_FOLDER_PATHS": str(app)}
    assert find(tmp_path, [app], env, ["https://example.com/x"]) == str(app)


def test_cursor_workspace_paths_are_read(tmp_path):
    a, b = project(tmp_path, "a"), project(tmp_path, "b")
    env = {"WORKSPACE_FOLDER_PATHS": f"{b},{a}"}
    assert find(tmp_path, [a, b], env, cwd=tmp_path / "home") == str(b)
