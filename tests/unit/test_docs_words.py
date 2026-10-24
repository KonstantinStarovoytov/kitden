from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_the_start_link_is_not_called_one_time():
    text = (ROOT / "src/kitden/web/security.py").read_text()
    assert "one-time" not in text and "The link works while the page runs" in text


def test_readme_says_where_secrets_go_and_what_the_agents_server_does():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert (
        "Secrets stay on this Mac. They go only to the server they belong to, or to a gateway "
        "you move that server into."
    ) in readme
    assert (
        "Servers moved into the gateway add their tools, which do what those servers do." in readme
    )


def test_readme_promises_no_undo_it_cannot_keep():
    # Undo can be blocked (a file changed after Apply), and backups stay for 30 days.
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert "Look at each change first. Apply keeps a backup for Undo." in readme
    assert "any time" not in readme


def test_readme_says_what_an_unknown_folder_gets():
    readme = " ".join((ROOT / "README.md").read_text().split())
    words = "In a folder Kitden does not know as a project, the All projects switches apply."
    assert words in readme


def test_readme_says_unknown_is_not_missing():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert (
        '"Unknown" means Kitden could not read it, so it may or may not be available; '
        "it never means missing"
    ) in readme
    # Both meanings: a file that could not be read, and an on/off state out of Kitden's sight.
    assert "Either a file could not be read, or the client keeps the on/off state" in readme


def test_readme_says_what_a_project_view_adds():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert '"This project" when the project\'s own settings decide it' in readme
    assert '"Only this project"' in readme
    assert 'A cell says "On" when the client has the item' in readme
    assert "is in the cell's hover text" in readme
    assert '"Needs review" means another client has an item with the same name' in readme
    assert "a skill only this project has adds into this project" in readme


def test_readme_names_the_management_actions():
    readme = " ".join((ROOT / "README.md").read_text().split())
    for words in (
        "Remove from",  # a plugin or a skill, with Undo
        '"+ Add" on an MCP server copies its entry to another client',
        "Add to this project…",
        "Add missing…",
        "Put back in",
        "Remove from the Kitden gateway…",
    ):
        assert words in readme, words
    check = (ROOT / "docs/development.md").read_text()
    for words in ("Remove", "Put back", "Add missing", "Add to this project"):
        assert words in check, words


def test_docs_name_the_demo_and_the_write_boundary():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert "uvx kitden demo" in readme
    assert "Kitden writes only in your home folder and your known projects." in readme
    development = (ROOT / "docs/development.md").read_text()
    assert "kitden demo" in development and "build_demo_home" in development


def test_readme_says_what_details_and_a_review_start_with():
    readme = " ".join((ROOT / "README.md").read_text().split())
    words = (
        "Technical details",
        "Compare across clients",
        "Manage tools",
        "One folder, read by Codex and Cursor.",
        "Remove from Codex and Cursor…",
        "Other projects are unchanged.",
        "Settings changed since this preview.",
        "Preview again",
    )
    # The page says each of them too, so the README cannot drift from it.
    page = " ".join(
        [(ROOT / "src/kitden/views/words.py").read_text()]
        + [p.read_text() for p in (ROOT / "src/kitden/web/static/js").glob("*.js")]
    )
    for text in words:
        assert text in readme, text
    for text in ("Technical details", "Compare across clients", "Manage tools"):
        assert f'"{text}"' in page, text
    for text in ("Other projects are unchanged.", "Settings changed since this preview."):
        assert text in page, text
    assert '"Preview again"' in page and "`One folder, read by ${joinWords(" in page


def test_the_check_before_a_release_turns_strict_mode_on_in_the_servers_details():
    development = " ".join((ROOT / "docs/development.md").read_text().split())
    step = (
        "5. Move the server in again. Turn strict mode on in the server's Details "
        '("Turn strict mode on…") and turn one tool off.'
    )
    assert step in development
    assert "Strict: only tools you turned on" not in development


def test_the_check_before_a_release_has_the_changed_settings_step():
    development = " ".join((ROOT / "docs/development.md").read_text().split())
    assert "23. Open a review (Remove for a Claude Code plugin)" in development
    assert 'The review says "Settings changed since this preview." and offers "Preview again"' in (
        development
    )
    assert "Not run yet for step 23:" in development


def test_walkthrough_script_one_has_the_seven_tasks_and_a_results_table():
    text = (ROOT / "docs/research/walkthrough-script-1.md").read_text()
    assert "kitden demo --size medium" in text
    assert all(f"## Task {n}:" in text for n in range(1, 8)) and "## Task 8" not in text
    assert "| Task | Done | Wrong turns | Time | What was confusing |" in text
    assert '"Loads" or "Available"' in text
    assert '"On" and "Off" or "Allowed" and "Blocked"' in text
