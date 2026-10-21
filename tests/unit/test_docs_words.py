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
