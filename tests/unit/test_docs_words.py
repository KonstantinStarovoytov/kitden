from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_the_start_link_is_not_called_one_time():
    text = (ROOT / "src/kitden/web/security.py").read_text()
    assert "one-time" not in text and "The link works while the page runs" in text


def test_readme_says_where_secrets_go_and_what_the_agents_server_does():
    readme = (ROOT / "README.md").read_text()
    assert "Secrets stay on this Mac and go only to the server they belong to." in readme
    assert (
        "Servers moved into the gateway add their tools, which do what those servers do." in readme
    )
