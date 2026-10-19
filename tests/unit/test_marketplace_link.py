"""Adding a marketplace from a link: a folder here or a GitHub repository (Discover, phase 1)."""

import json
import urllib.error

import pytest

from kitden import marketplace_link
from kitden.marketplace_link import LinkError, read_marketplace


def _folder(tmp_path, where=".claude-plugin/marketplace.json", name="tools"):
    path = tmp_path / "mkt" / where
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"name": name, "plugins": [{"name": "a"}, {"name": "b"}]}))
    return tmp_path / "mkt"


def test_a_folder_on_this_computer(tmp_path):
    found = read_marketplace(str(_folder(tmp_path)))
    assert found == {
        "name": "tools",
        "source": str(tmp_path / "mkt"),
        "plugins": 2,
        "formats": ["claude"],
    }


def test_a_codex_only_folder_is_marked(tmp_path):
    found = read_marketplace(str(_folder(tmp_path, ".agents/plugins/marketplace.json")))
    assert found["formats"] == ["codex"]


class FakeOpen:
    def __init__(self, files):
        self.files = files
        self.urls = []

    def __call__(self, request, timeout):
        url = request.full_url if hasattr(request, "full_url") else request
        self.urls.append(url)
        if url not in self.files:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        body = json.dumps(self.files[url]).encode()

        class Answer:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit=-1):
                return body

        return Answer()


@pytest.mark.parametrize(
    "link", ["acme/tools", "https://github.com/acme/tools", "https://github.com/acme/tools.git"]
)
def test_a_github_repository_is_read_once_from_raw_files(monkeypatch, link):
    raw = "https://raw.githubusercontent.com/acme/tools/HEAD/.claude-plugin/marketplace.json"
    fake = FakeOpen({raw: {"name": "acme-tools", "plugins": [{"name": "x"}]}})
    monkeypatch.setattr(marketplace_link, "urlopen", fake)
    found = read_marketplace(link)
    assert found == {
        "name": "acme-tools",
        "source": "acme/tools",
        "plugins": 1,
        "formats": ["claude"],
    }
    assert all(u.startswith("https://raw.githubusercontent.com/acme/tools/") for u in fake.urls)


@pytest.mark.parametrize(
    "link",
    ["http://example.com/x", "git@gitlab.com:a/b.git", "a/b/c", "../../etc", "acme/to;ols", ""],
)
def test_other_links_are_refused(monkeypatch, link):
    monkeypatch.setattr(marketplace_link, "urlopen", FakeOpen({}))
    with pytest.raises(LinkError):
        read_marketplace(link)


def test_a_repository_without_a_marketplace_file_says_so(monkeypatch):
    monkeypatch.setattr(marketplace_link, "urlopen", FakeOpen({}))
    with pytest.raises(LinkError, match="no marketplace file"):
        read_marketplace("acme/empty")
