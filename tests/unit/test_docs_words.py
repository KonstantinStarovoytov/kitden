import re
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


def test_readme_is_short_and_names_the_page_words():
    text = (ROOT / "README.md").read_text()
    readme = " ".join(text.split())
    # The owner wants it short (2026-10-28): what Kitden does, then Install.
    assert len(text.splitlines()) <= 120
    for words in ("Add missing plugins and skills…", "Show changes", "Redo…", "See it on the map"):
        assert words in readme, words
    # Obot and MetaMCP cannot be added from the page now.
    assert "Obot" not in readme and "MetaMCP" not in readme


def test_the_check_before_a_release_names_the_management_actions():
    check = (ROOT / "docs/development.md").read_text()
    for words in ("Remove", "Put back", "Add missing", "Add to this project"):
        assert words in check, words


def test_docs_name_the_demo_and_the_write_boundary():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert "kitden demo" in readme
    assert "preview of the next release, run from source" in readme
    assert "Kitden writes only in your home folder and your known projects." in readme
    development = (ROOT / "docs/development.md").read_text()
    assert "kitden demo" in development and "build_demo_home" in development


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
    assert "23. Add a Remove for a Claude Code plugin to the preview" in development
    assert 'The bar says "Settings changed since this preview." and offers "Preview again"' in (
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


IMAGES = "https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/"


def test_every_readme_image_has_a_local_source_and_a_pypi_fallback():
    readme = (ROOT / "README.md").read_text()
    images = re.findall(r'(?:src|srcset)="([^"]+)"', readme)
    assert images
    marked = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", readme)
    for image in images + marked:
        if image.startswith(IMAGES):
            assert (ROOT / "docs/images" / image.removeprefix(IMAGES)).is_file(), image
        elif image.startswith("docs/images/"):
            assert (ROOT / image).is_file(), image
        else:
            assert image.startswith("https://"), image


def test_the_readme_names_no_old_review():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert "Every change opens a review first" not in readme
    assert "review.jpg" not in readme
