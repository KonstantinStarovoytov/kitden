"""Read online catalogs only on request. Install through the normal change engine.

Checked 2026-10-29: skills.sh's CLI uses /api/search (vercel-labs/skills/src/find.ts).
MCP Registry: modelcontextprotocol/registry/docs/reference/api/official-registry-api.md.
GitHub: docs.github.com/en/rest/git/trees. No downloaded code is executed here.
"""

import hashlib
import io
import json
import re
import shutil
import stat
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from kitden.gateways import data_dir
from kitden.marketplace_link import _repo
from kitden.redact import redact
from kitden.views.skills import _read_skill

MAX_BYTES = 20_000_000
HOSTS = {
    "api.github.com",
    "raw.githubusercontent.com",
    "codeload.github.com",
    "skills.sh",
    "www.skills.sh",
    "registry.modelcontextprotocol.io",
}
DEFAULTS = [
    {"id": "skills.sh", "name": "skills.sh", "kind": "skills"},
    {"id": "mcp-registry", "name": "Official MCP Registry", "kind": "mcp"},
    {"id": "anthropics/claude-plugins-official", "name": "Claude plugins", "kind": "github"},
    {"id": "obra/superpowers", "name": "Superpowers", "kind": "github"},
]


def checked_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in HOSTS or parts.username or parts.port:
        raise ValueError("This catalog address is not supported.")
    return url


class CatalogRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        checked_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def download(url: str) -> bytes:
    request = Request(  # noqa: S310 - checked HTTPS hosts, redirects checked too
        checked_url(url), headers={"User-Agent": "Kitden", "Accept": "application/json"}
    )
    with build_opener(CatalogRedirect()).open(request, timeout=15) as response:  # noqa: S310
        content = response.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError("This source is too large. Choose a smaller repository.")
    return content


def read_json(url: str) -> dict:
    value = json.loads(download(url))
    if not isinstance(value, dict):
        raise ValueError("The source returned an unreadable catalog.")
    return value


def safe_path(path: str) -> str:
    value = PurePosixPath(path)
    if value.is_absolute() or ".." in value.parts or "\\" in path:
        raise ValueError("The source contains an unsafe path.")
    return value.as_posix()


def row_key(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:24]


def server_entry(server: dict) -> tuple[dict | None, str | None]:
    """Use a complete transport as declared; never guess missing arguments or credentials."""
    for remote in server.get("remotes", []):
        if remote.get("type") != "streamable-http":
            continue
        url = remote.get("url", "")
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or "{" in url:
            continue
        if any(h.get("isRequired") for h in remote.get("headers", [])):
            continue
        return {"url": url}, None
    for package in server.get("packages", []):
        if package.get("transport", {}).get("type") != "stdio":
            continue
        if (
            any(v.get("isRequired") for v in package.get("environmentVariables", []))
            or package.get("runtimeArguments")
            or package.get("packageArguments")
        ):
            continue
        name, version = package.get("identifier", ""), package.get("version", "")
        if not version or not re.fullmatch(r"[A-Za-z0-9._+/-]+", version):
            continue
        if package.get("registryType") == "npm" and re.fullmatch(
            r"(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*", name
        ):
            return {"command": "npx", "args": ["-y", f"{name}@{version}"]}, None
    return None, "This server needs sign-in, configuration or a transport Kitden cannot add yet."


class Discovery:
    def __init__(self, home: Path):
        self.root = data_dir(home) / "discovery"
        self.results: dict[str, dict] = {}
        self.trees: dict[str, tuple[str, list[str]]] = {}

    def sources(self) -> list[dict]:
        try:
            custom = json.loads((self.root / "sources.json").read_text())
        except (OSError, ValueError):
            custom = []
        repos = [r for r in custom if isinstance(r, str) and _repo(r) == r]
        return DEFAULTS + [
            {"id": r, "name": r, "kind": "github"}
            for r in repos
            if r not in {s["id"] for s in DEFAULTS}
        ]

    def add_source(self, value: str) -> list[dict]:
        repo = _repo(value)
        if repo is None:
            raise ValueError("Use a public GitHub repository: owner/repo.")
        repos = [s["id"] for s in self.sources() if s["kind"] == "github"]
        if repo not in repos:
            repos.append(repo)
        if len(repos) > 25:
            raise ValueError("Keep at most 25 GitHub sources.")
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "sources.json").write_text(json.dumps(repos))
        return self.sources()

    def tree(self, repo: str) -> tuple[str, list[str]]:
        if _repo(repo) != repo:
            raise ValueError("This result has no supported GitHub source.")
        if repo not in self.trees:
            commit = read_json(f"https://api.github.com/repos/{repo}/commits/HEAD")["sha"]
            if not re.fullmatch(r"[a-f0-9]{40}", commit):
                raise ValueError("GitHub returned no commit.")
            tree = read_json(f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1")
            if tree.get("truncated"):
                raise ValueError("This repository is too large to browse completely.")
            paths = [
                safe_path(n["path"])
                for n in tree.get("tree", [])
                if n.get("type") == "blob" and n.get("mode") != "120000"
            ]
            self.trees[repo] = commit, paths
        return self.trees[repo]

    def github(self, repo: str, query: str, kind: str) -> list[dict]:
        commit, paths = self.tree(repo)
        rows = []
        if kind in ("all", "skill"):
            for path in paths:
                if PurePosixPath(path).name != "SKILL.md":
                    continue
                name = PurePosixPath(path).parent.name or repo.split("/")[-1]
                if query.lower() in name.lower():
                    rows.append(
                        {
                            "name": name,
                            "kind": "skill",
                            "repo": repo,
                            "commit": commit,
                            "path": str(PurePosixPath(path).parent),
                            "source": repo,
                            "description": "Skill from this GitHub source.",
                        }
                    )
        if kind == "mcp":
            for path in paths:
                if PurePosixPath(path).name not in ("server.json", ".mcp.json"):
                    continue
                data = read_json(f"https://raw.githubusercontent.com/{repo}/{commit}/{quote(path)}")
                if "name" in data and ("packages" in data or "remotes" in data):
                    entry, refusal = server_entry(data)
                    rows.append(
                        {
                            "name": data["name"],
                            "kind": "mcp",
                            "entry": entry,
                            "refusal": refusal,
                            "source": repo,
                            "commit": commit,
                            "description": str(data.get("description", ""))[:600],
                        }
                    )
                else:
                    for name, entry in data.get("mcpServers", {}).items():
                        if not isinstance(entry, dict):
                            continue
                        rows.append(
                            {
                                "name": name,
                                "kind": "mcp",
                                "entry": entry,
                                "source": repo,
                                "commit": commit,
                                "description": "MCP server from this GitHub source.",
                            }
                        )
                if len(rows) >= 60:
                    break
            rows = [r for r in rows if query.lower() in r["name"].lower()]
        if kind in ("all", "plugin"):
            manifest_path = next(
                (
                    p
                    for p in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json")
                    if p in paths
                ),
                None,
            )
            if manifest_path:
                manifest = read_json(
                    f"https://raw.githubusercontent.com/{repo}/{commit}/{manifest_path}"
                )
                for entry in manifest.get("plugins", []):
                    name = entry.get("name", "")
                    if (
                        isinstance(name, str)
                        and query.lower() in f"{name} {entry.get('description', '')}".lower()
                    ):
                        rows.append(
                            {
                                "name": name,
                                "kind": "plugin",
                                "repo": repo,
                                "commit": commit,
                                "marketplace": manifest.get("name"),
                                "formats": [
                                    "claude" if manifest_path.startswith(".claude") else "codex"
                                ],
                                "source": repo,
                                "description": str(entry.get("description", ""))[:600],
                            }
                        )
            elif ".claude-plugin/plugin.json" in paths:
                manifest = read_json(
                    f"https://raw.githubusercontent.com/{repo}/{commit}/.claude-plugin/plugin.json"
                )
                name = manifest.get("name", repo.split("/")[-1])
                if query.lower() in str(name).lower():
                    rows.append(
                        {
                            "name": name,
                            "kind": "plugin",
                            "repo": repo,
                            "commit": commit,
                            "standalone": True,
                            "source": repo,
                            "description": str(manifest.get("description", ""))[:600],
                        }
                    )
        return rows[:60]

    def search(self, source: str, query: str, kind: str) -> list[dict]:
        known = next((s for s in self.sources() if s["id"] == source), None)
        if known is None:
            raise ValueError("Choose a known source.")
        query = query.strip()[:100]
        if known["kind"] != "github" and len(query) < 3:
            raise ValueError("Enter at least three characters to search online.")
        if source == "skills.sh":
            data = read_json("https://skills.sh/api/search?" + urlencode({"q": query, "limit": 30}))
            rows = (
                [
                    {
                        "name": r["name"],
                        "kind": "skill",
                        "repo": r.get("source"),
                        "source": "skills.sh",
                        "description": f"{r.get('source', '')} · {r.get('installs', 0)} installs",
                    }
                    for r in data.get("skills", [])
                    if _repo(str(r.get("source", ""))) and isinstance(r.get("name"), str)
                ]
                if kind in ("all", "skill")
                else []
            )
        elif source == "mcp-registry":
            data = read_json(
                "https://registry.modelcontextprotocol.io/v0.1/servers?"
                + urlencode({"search": query, "version": "latest", "limit": 100})
            )
            rows = []
            for record in data.get("servers", []):
                if (
                    record.get("_meta", {})
                    .get("io.modelcontextprotocol.registry/official", {})
                    .get("status")
                    != "active"
                ):
                    continue
                server = record["server"]
                entry, refusal = server_entry(server)
                rows.append(
                    {
                        "name": server["name"],
                        "kind": "mcp",
                        "version": server.get("version"),
                        "source": "Official MCP Registry",
                        "description": str(server.get("description", ""))[:600],
                        "entry": entry,
                        "refusal": refusal,
                        "repository": server.get("repository", {}).get("url"),
                    }
                )
        else:
            rows = self.github(source, query, kind)
        for row in rows:
            row["id"] = row_key(row)
            self.results[row["id"]] = row
            folder = self.root / "results"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{row['id']}.json").write_text(json.dumps(row))
        return [self.public(row) for row in rows]

    def public(self, row: dict) -> dict:
        return {k: v for k, v in row.items() if k not in ("entry", "formats")}

    def get(self, key: str) -> dict:
        if key not in self.results:
            if not re.fullmatch(r"[a-f0-9]{24}", key):
                raise ValueError("Search this source again before adding the item.")
            try:
                row = json.loads((self.root / "results" / f"{key}.json").read_text())
                checked = {k: v for k, v in row.items() if k != "id"}
                if row_key(checked) != key:
                    raise ValueError("The source changed. Search again.")
                self.results[key] = row
            except OSError:
                raise ValueError("Search this source again before adding the item.") from None
        return self.results[key]

    def details(self, key: str, found: set[str]) -> dict:
        row = self.get(key)
        out = self.public(row)
        if row["kind"] == "skill":
            skill = self.skill(row, found)
            out["content"] = (Path(skill["path"]) / "SKILL.md").read_text()[:20000]
            out["commit"] = skill["commit"]
            if not skill["self_contained"]:
                out["refusal"] = (
                    "This skill needs files outside its folder. Add its plugin instead."
                )
        elif row["kind"] == "mcp":
            out["content"] = json.dumps(redact(row.get("entry") or {})[0], indent=2)
        else:
            out["content"] = "Installs through the client's plugin command from " + row["repo"]
        return out

    def checkout(self, repo: str, commit: str, subfolder: str = "") -> Path:
        folder = (
            self.root
            / "cache"
            / hashlib.sha256(f"{repo}/{commit}/{subfolder}".encode()).hexdigest()
        )
        if folder.is_dir():
            return folder
        content = (
            None if subfolder else download(f"https://codeload.github.com/{repo}/zip/{commit}")
        )
        folder.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(dir=folder.parent))
        try:
            if subfolder:
                tree = read_json(
                    f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1"
                )
                if tree.get("truncated"):
                    raise ValueError("This repository is too large to read completely.")
                total = 0
                deadline = time.monotonic() + 45
                files = [
                    n
                    for n in tree.get("tree", [])
                    if n.get("type") == "blob"
                    and PurePosixPath(safe_path(n["path"])).is_relative_to(PurePosixPath(subfolder))
                ]
                if len(files) > 200:
                    raise ValueError("This skill has too many files to install.")
                for item in files:
                    if time.monotonic() > deadline:
                        raise ValueError("Reading this skill took too long. Try a smaller source.")
                    if item.get("mode") == "120000":
                        raise ValueError("This skill contains symbolic links.")
                    path = safe_path(item["path"])
                    value = download(
                        f"https://raw.githubusercontent.com/{repo}/{commit}/{quote(path)}"
                    )
                    total += len(value)
                    if total > MAX_BYTES:
                        raise ValueError("This skill is too large to install.")
                    target = staging / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(value)
                staging.rename(folder)
                return folder
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                files = archive.infolist()
                if len(files) > 5000 or sum(f.file_size for f in files) > MAX_BYTES:
                    raise ValueError("This repository is too large to install.")
                for item in files:
                    rel = PurePosixPath(safe_path(item.filename))
                    relative = PurePosixPath(*rel.parts[1:])
                    if subfolder and not relative.is_relative_to(PurePosixPath(subfolder)):
                        continue
                    if stat.S_ISLNK(item.external_attr >> 16):
                        raise ValueError(
                            "This repository contains symbolic links. Use its marketplace instead."
                        )
                    if len(rel.parts) < 2 or item.is_dir():
                        continue
                    target = staging.joinpath(*rel.parts[1:])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(item))
            staging.rename(folder)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return folder

    def skill(self, row: dict, found: set[str]) -> dict:
        repo = row["repo"]
        commit, paths = self.tree(repo)
        path = row.get("path")
        if path is None:
            matches = [
                p
                for p in paths
                if p.endswith("/SKILL.md") and PurePosixPath(p).parent.name == row["name"]
            ]
            if len(matches) != 1:
                raise ValueError(
                    "Several folders match. Add the GitHub source and choose the exact skill."
                )
            path = str(PurePosixPath(matches[0]).parent)
        folder = self.checkout(repo, row.get("commit", commit), path) / safe_path(path)
        if not (folder / "SKILL.md").is_file():
            raise ValueError("The selected skill no longer has a SKILL.md file.")
        info = _read_skill(folder)
        name = (
            info["name"]
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", info["name"])
            else row["name"]
        )
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", name):
            raise ValueError("This skill has no usable folder name.")
        prepared = self.root / "skills" / row["id"] / name
        if not prepared.exists():
            prepared.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(folder, prepared)
        folder = prepared
        return {
            **info,
            "path": str(folder),
            "installed": {},
            "routes": {c: "ready" for c in found},
            "id": row["id"],
            "commit": row.get("commit", commit),
        }

    def plugin(self, row: dict) -> dict:
        repo = row["repo"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", row["name"]):
            raise ValueError("This plugin has no usable name.")
        name = row.get("marketplace")
        source = repo
        formats = row.get("formats", ["claude"])
        if row.get("standalone"):
            root = self.checkout(repo, row["commit"])
            name = "kitden-" + row["id"]
            wrapper = root.parent / name
            plugin = wrapper / "plugin"
            if not plugin.exists():
                shutil.copytree(root, plugin)
            manifest = wrapper / ".claude-plugin/marketplace.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                json.dumps(
                    {
                        "name": name,
                        "owner": {"name": "Kitden source"},
                        "plugins": [{"name": row["name"], "source": "./plugin"}],
                    }
                )
            )
            source = str(wrapper)
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", name):
            raise ValueError("This plugin source has no usable marketplace name.")
        return {
            "name": name,
            "source": source,
            "formats": formats,
            "plugin": f"{row['name']}@{name}",
        }
