"""Read online catalogs only on request. Install through the normal change engine.

Checked 2026-10-29: skills.sh's CLI uses /api/search (vercel-labs/skills/src/find.ts).
MCP Registry: modelcontextprotocol/registry/docs/reference/api/official-registry-api.md.
GitHub: docs.github.com/en/rest/git/trees. No downloaded code is executed here.
"""

import copy
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
from kitden.views.skills import _read_skill, front_matter

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


def popular_skills() -> list[dict]:
    """Read the public all-time leaderboard (checked 2026-10-29)."""
    page = download("https://skills.sh/").decode("utf-8")
    for script in re.findall(r"<script[^>]*>(.*?)</script>", page, re.S):
        prefix = "self.__next_f.push("
        if not script.startswith(prefix):
            continue
        try:
            payload = json.loads(script[len(prefix) :].rstrip(";)").strip())
            text = payload[1]
            marker = '"initialSkills":'
            if not isinstance(text, str) or marker not in text:
                continue
            rows, _ = json.JSONDecoder().raw_decode(text.split(marker, 1)[1].lstrip())
            if isinstance(rows, list):
                return sorted(
                    [
                        r
                        for r in rows
                        if isinstance(r, dict) and isinstance(r.get("installs"), (int, float))
                    ],
                    key=lambda r: r["installs"],
                    reverse=True,
                )[:30]
        except (ValueError, IndexError, TypeError):
            continue
    raise ValueError("Could not read popular skills. Enter a search to continue.")


def safe_path(path: str) -> str:
    value = PurePosixPath(path)
    if value.is_absolute() or ".." in value.parts or "\\" in path:
        raise ValueError("The source contains an unsafe path.")
    return value.as_posix()


def words_match(query: str, value: str) -> bool:
    def normalize(text):
        return re.sub(r"[-_\s]+", " ", text.casefold()).strip()

    return all(word in normalize(value) for word in normalize(query).split())


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


def server_setup(server: dict) -> tuple[dict | None, str | None, list[dict]]:
    """Required headers and environment values, per registry schema checked 2026-10-31."""
    simple, refusal = server_entry(server)
    if simple:
        return simple, None, []
    for group, field in (("remotes", "headers"), ("packages", "env")):
        for record in server.get(group, []):
            definitions = record.get(
                "headers" if field == "headers" else "environmentVariables", []
            )
            needed = [d for d in definitions if d.get("isRequired")]
            if not needed:
                continue
            if any(
                not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", str(d.get("name", ""))) for d in needed
            ):
                continue
            clean = copy.deepcopy(record)
            clean["headers" if field == "headers" else "environmentVariables"] = []
            entry, error = server_entry({group: [clean]})
            if entry is None:
                continue
            fields = []
            for definition in needed:
                template = definition.get("value", "")
                # A single token slot may carry a Bearer prefix; other templates need manual setup.
                if template and not re.fullmatch(
                    r"(?:Bearer )?\{[A-Za-z_][A-Za-z0-9_]*\}", template
                ):
                    error = "This server needs a configuration Kitden cannot build yet."
                    break
                fields.append(
                    {
                        "field": field,
                        "name": definition["name"],
                        "label": str(definition.get("description") or definition["name"])[:200],
                        # Registry entries often declare Authorization with no template
                        # (7 of 7 seen 2026-10-31); those take a Bearer token too.
                        "prefix": "Bearer "
                        if template.startswith("Bearer ")
                        or (not template and definition["name"].lower() == "authorization")
                        else "",
                    }
                )
            if error:
                continue
            return entry, None, fields
    return None, refusal, []


def configured_entry(row: dict, params: dict) -> dict:
    """Accept only declared values; secrets remain in preview memory until Apply."""
    entry = copy.deepcopy(row.get("entry"))
    if not entry:
        raise ValueError("This server needs a setup Kitden cannot add yet.")
    fields = row.get("setup", [])
    for field in ("headers", "env"):
        supplied = params.get(field, {})
        if not isinstance(supplied, dict):
            raise ValueError("Enter the required access details.")
        allowed = {f["name"] for f in fields if f["field"] == field}
        if field == "headers" and "url" in entry:
            allowed.add("Authorization")
        if set(supplied) - allowed:
            raise ValueError("Only the server's declared access fields can be set.")
        for key, value in supplied.items():
            if (
                not isinstance(value, str)
                or not value.strip()
                or value == "[secret]"
                or "\r" in value
                or "\n" in value
                or len(value) > 8192
            ):
                raise ValueError("Enter a valid access value again.")
            entry.setdefault(field, {})[key] = value.strip()
    for required in fields:
        if not entry.get(required["field"], {}).get(required["name"]):
            raise ValueError(f"Enter {required['name']} before previewing.")
    return entry


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
        legacy = isinstance(custom, list)
        values = custom if legacy else custom.get("repositories", [])
        repos = [
            r
            for r in values
            if isinstance(r, str) and _repo(r) == r and not (legacy and r == "obra/superpowers")
        ]
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
        (self.root / "sources.json").write_text(json.dumps({"repositories": repos}))
        return self.sources()

    def change_source(self, operation: str, value: str, previous: str) -> list[dict]:
        if operation == "add":
            return self.add_source(value)
        defaults = {s["id"] for s in DEFAULTS}
        repos = [s["id"] for s in self.sources() if s["id"] not in defaults]
        if previous not in repos:
            raise ValueError("Choose a custom GitHub source.")
        if operation == "edit":
            repo = _repo(value)
            if repo is None:
                raise ValueError("Use a public GitHub repository: owner/repo.")
            repos[repos.index(previous)] = repo
        elif operation == "remove":
            repos.remove(previous)
        else:
            raise ValueError("Choose add, edit or remove.")
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "sources.json").write_text(
            json.dumps({"repositories": list(dict.fromkeys(repos))})
        )
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
                if words_match(query, name):
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
                    entry, refusal, setup = server_setup(data)
                    rows.append(
                        {
                            "name": data["name"],
                            "kind": "mcp",
                            "entry": entry,
                            "refusal": refusal,
                            "setup": setup,
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
            rows = [r for r in rows if words_match(query, r["name"])]
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
                    if isinstance(name, str) and words_match(
                        query, f"{name} {entry.get('description', '')}"
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
                if words_match(query, str(name)):
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
        if query and known["kind"] != "github" and len(query) < 3:
            raise ValueError("Enter at least three characters to search online.")
        if source == "skills.sh":
            data = (
                read_json("https://skills.sh/api/search?" + urlencode({"q": query, "limit": 30}))
                if query
                else {"skills": popular_skills()}
            )
            rows = (
                [
                    {
                        "name": r["name"],
                        "kind": "skill",
                        "repo": r.get("source"),
                        "source": "skills.sh",
                        "installs": r.get("installs")
                        if isinstance(r.get("installs"), (int, float))
                        else None,
                        "description": f"{r.get('source', '')} · {r.get('installs', 0)} installs",
                    }
                    for r in data.get("skills", [])
                    if _repo(str(r.get("source", ""))) and isinstance(r.get("name"), str)
                ]
                if kind in ("all", "skill")
                else []
            )
        elif source == "mcp-registry":
            variants = list(dict.fromkeys([re.sub(r"[\s_]+", "-", query), query]))
            records = {}
            for term in variants:
                data = read_json(
                    "https://registry.modelcontextprotocol.io/v0.1/servers?"
                    + urlencode({"search": term, "version": "latest", "limit": 100})
                )
                for record in data.get("servers", []):
                    records[record["server"]["name"]] = record
            data = {"servers": list(records.values())}
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
                entry, refusal, setup = server_setup(server)
                rows.append(
                    {
                        "name": server["name"],
                        "kind": "mcp",
                        "version": server.get("version"),
                        "source": "Official MCP Registry",
                        "description": str(server.get("description", ""))[:600],
                        "entry": entry,
                        "refusal": refusal,
                        "setup": setup,
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
        out = {k: v for k, v in row.items() if k not in ("entry", "formats")}
        if row["kind"] == "mcp":
            # The map shows a dropped server in its group; the entry itself stays private.
            out["remote"] = bool((row.get("entry") or {}).get("url"))
        return out

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

    def skill_choices(self, row: dict) -> list[dict]:
        """Pin folder choices for the normal preview flow."""
        commit, paths = self.tree(row["repo"])
        paths = [p for p in paths if PurePosixPath(p).name == "SKILL.md"]
        matches = [p for p in paths if PurePosixPath(p).parent.name == row["name"]]
        choices = []
        for path in sorted(matches or paths):
            candidate = {k: v for k, v in row.items() if k not in ("id", "installs", "description")}
            candidate.update(
                path=str(PurePosixPath(path).parent),
                commit=commit,
                name=PurePosixPath(path).parent.name or row["repo"].split("/")[-1],
                description="Skill from this GitHub source.",
            )
            candidate["id"] = row_key(candidate)
            self.results[candidate["id"]] = candidate
            cache = self.root / "results"
            cache.mkdir(parents=True, exist_ok=True)
            (cache / f"{candidate['id']}.json").write_text(json.dumps(candidate))
            choices.append(self.public(candidate))
        return choices

    def details(self, key: str, found: set[str]) -> dict:
        row = self.get(key)
        if row["kind"] == "skill" and row.get("path") is None:
            choices = self.skill_choices(row)
            exact = [c for c in choices if c["name"] == row["name"]]
            if len(choices) == 1 or len(exact) == 1:
                row = self.get((exact or choices)[0]["id"])
            elif choices:
                return {**self.public(row), "choices": choices}
            else:
                raise ValueError("This repository no longer contains any skills.")
        out = self.public(row)
        if row["kind"] == "skill":
            # Read only the description here. Preview validates the complete folder.
            metadata = self.root / "metadata" / row["id"]
            skill_md = metadata / "SKILL.md"
            if not skill_md.is_file():
                path = (PurePosixPath(row["path"]) / "SKILL.md").as_posix()
                content = download(
                    f"https://raw.githubusercontent.com/{row['repo']}/{row['commit']}/{quote(path)}"
                )
                metadata.mkdir(parents=True, exist_ok=True)
                skill_md.write_bytes(content)
            meta = front_matter(skill_md)
            out["name"] = meta.get("name") or row["name"]
            out["description"] = meta.get("description", "")
            out["content"] = skill_md.read_text()[:20000]
        elif row["kind"] == "mcp":
            out["content"] = json.dumps(redact(row.get("entry") or {})[0], indent=2)
            if out["remote"] and not row.get("setup"):
                from kitden.changes.actions import needs_sign_in

                try:
                    out["access_required"] = needs_sign_in(row["entry"]["url"], {})
                except OSError:
                    out["access_note"] = "Could not reach this server. Preview will check again."
        else:
            out["content"] = "Installs through the client's plugin command from " + row["repo"]
        return out

    def checkout(self, repo: str, commit: str, subfolder: str = "") -> Path:
        # A root skill is one archive read, not one request for every repository file.
        if subfolder == ".":
            subfolder = ""
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
        if row.get("path") is None:
            choices = self.skill_choices(row)
            exact = [c for c in choices if c["name"] == row["name"]]
            if len(choices) != 1 and len(exact) != 1:
                raise ValueError("Open this skill and choose a folder before previewing.")
            row = self.get((exact or choices)[0]["id"])
        repo = row["repo"]
        commit = row["commit"]
        path = row["path"]
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
