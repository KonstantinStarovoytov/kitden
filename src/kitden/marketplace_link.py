"""Read a marketplace from a link before adding it, so the review can name it (Discover).

Two kinds of links: a folder on this computer, or a GitHub repository ("owner/repo" or its
github.com address). For a repository Kitden reads the marketplace file once from
raw.githubusercontent.com when the person asks for a preview; nothing else goes online.
"""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

FILES = {"claude": ".claude-plugin/marketplace.json", "codex": ".agents/plugins/marketplace.json"}
REPO = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}")
LIMIT = 2_000_000  # a marketplace file is a list of entries; anything larger is not one


class LinkError(ValueError):
    """The link is not one Kitden reads, or holds no marketplace."""


def _repo(link: str) -> str | None:
    """'owner/repo' for a GitHub repository link, else None."""
    link = link.strip()
    if link.startswith("https://github.com/"):
        parts = urlsplit(link)
        if parts.query or parts.fragment:
            return None
        link = parts.path.strip("/").removesuffix(".git")
    return link if REPO.fullmatch(link) and ".." not in link else None


def _summary(name_source: str, found: dict[str, dict]) -> dict:
    first = next(iter(found.values()))
    name = first.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", name):
        raise LinkError("The marketplace file has no usable name")
    plugins = first.get("plugins")
    return {
        "name": name,
        "source": name_source,
        "plugins": len(plugins) if isinstance(plugins, list) else 0,
        "formats": [f for f in FILES if f in found],
    }


RAW = "https://raw.githubusercontent.com/"


def _fetch(url: str) -> dict | None:
    if not url.startswith(RAW):  # the only host Kitden reads from
        raise LinkError("Kitden reads marketplace files only from raw.githubusercontent.com")
    request = Request(url, headers={"User-Agent": "kitden"})  # noqa: S310 - https, fixed host
    try:
        with urlopen(request, timeout=10) as answer:  # noqa: S310 - https, fixed host
            data = json.loads(answer.read(LIMIT + 1)[:LIMIT])
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def read_marketplace(link: str) -> dict:
    """{"name", "source", "plugins", "formats"} for a marketplace link, or LinkError."""
    link = link.strip()
    if link.startswith("/") or link.startswith("~"):
        folder = Path(link).expanduser().resolve()
        if not folder.is_dir():
            raise LinkError(f"There is no folder {folder}")
        found = {}
        for fmt, name in FILES.items():
            try:
                data = json.loads((folder / name).read_text())
            except (OSError, ValueError):
                continue
            if isinstance(data, dict):
                found[fmt] = data
        if not found:
            raise LinkError("This folder has no marketplace file")
        return _summary(str(folder), found)
    repo = _repo(link)
    if repo is None:
        raise LinkError("Use a folder on this computer or a GitHub repository (owner/repo)")
    found = {}
    for fmt, name in FILES.items():
        data = _fetch(f"{RAW}{repo}/HEAD/{name}")
        if data is not None:
            found[fmt] = data
    if not found:
        raise LinkError(f"{repo} has no marketplace file")
    return _summary(repo, found)
