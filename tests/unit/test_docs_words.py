import re
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_the_start_link_is_not_called_one_time():
    text = (ROOT / "src/kitden/web/security.py").read_text()
    assert "one-time" not in text and "The link works while the page runs" in text


def test_guide_says_where_secrets_go_and_what_the_agents_server_does():
    readme = " ".join((ROOT / "docs/guide.md").read_text().split())
    assert (
        "Credentials go to the server they belong to, or to a gateway you move that server into."
    ) in readme
    assert (
        "Servers moved into the gateway add their tools, which do what those servers do." in readme
    )


def test_docs_promise_no_undo_they_cannot_keep():
    # Undo can be blocked (a file changed after Apply), and backups stay for 30 days.
    guide = " ".join((ROOT / "docs/guide.md").read_text().split())
    assert "Look at each change first. Apply keeps a backup for Undo." in guide
    for name in ("README.md", "docs/guide.md"):
        assert "any time" not in (ROOT / name).read_text(), name


def test_readme_is_short_and_the_guide_names_the_page_words():
    text = (ROOT / "README.md").read_text()
    # The README has five parts, the other features and two commands; the details live in the
    # guide (2026-11-10).
    assert len(text.splitlines()) <= 125
    assert "docs/images/readme/context-light.png" in text
    assert "docs/guide.md" in text
    guide = " ".join((ROOT / "docs/guide.md").read_text().split())
    for words in ("Add missing plugins and skills…", "Show changes", "Redo…", "See it on the map"):
        assert words in guide, words
    # Obot and MetaMCP cannot be added from the page now.
    for words in (text, guide):
        assert "Obot" not in words and "MetaMCP" not in words


def test_the_check_before_a_release_names_the_management_actions():
    check = (ROOT / "docs/development.md").read_text()
    for words in ("Remove", "Put back", "Add missing", "Add to this project"):
        assert words in check, words


def test_docs_name_the_demo_and_the_write_boundary():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert "kitden demo" in readme
    assert "uvx --python 3.13 kitden demo" in readme
    assert "uv tool install --python 3.13 kitden" in readme
    guide = " ".join((ROOT / "docs/guide.md").read_text().split())
    assert (
        "Kitden writes to your home folder, its own data folder, known projects "
        "and detected client settings folders."
    ) in guide
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


def test_the_readme_has_four_parts_and_three_pictures_in_both_themes():
    readme = (ROOT / "README.md").read_text()
    # See it all, find and add, the gateway, and why it is safe, in this order (2026-11-05).
    parts = (
        "Everything your agents load, on one map",
        "Find and add from one place",
        "One gateway for your MCP servers",
        "Every change can be undone",
    )
    places = [readme.index(f"### {part}") for part in parts]
    assert places == sorted(places)
    # Two stills, then one animation: the scenes differ in look as in subject.
    for scene, kind in (("library", "png"), ("find", "png"), ("tools", "webp")):
        for theme in ("light", "dark"):
            image = ROOT / f"docs/images/readme/{scene}-{theme}.{kind}"
            assert f"docs/images/readme/{scene}-{theme}.{kind}" in readme, image.name
            # Small enough for a phone on a slow line.
            assert image.stat().st_size <= 1_600_000, image.name
    # The sharing animation is kept for posts, not shown here.
    assert "pick-" not in readme
