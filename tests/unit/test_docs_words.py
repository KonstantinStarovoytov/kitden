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


def test_readme_says_what_an_unknown_folder_gets():
    readme = " ".join((ROOT / "README.md").read_text().split())
    words = "In a folder Kitden does not know as a project, the All projects switches apply."
    assert words in readme


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
