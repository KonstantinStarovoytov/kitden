"""The catalog: plugins in the marketplaces already on this computer.

Read only: nothing here goes to the network or runs anything. Claude Code keeps a clone of each
marketplace; Codex keeps local marketplaces and its curated one in `.tmp`. Formats checked on
2026-10-19: Claude Code 2.1.283, Codex CLI 0.163.
"""

import json
import re
import shlex
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from kitden.clients.base import ClientAdapter
from kitden.clients.entries import gateway_entry, reads_elsewhere
from kitden.model import ItemKind, Scope, SourceKind
from kitden.redact import redact
from kitden.views.setup_server import CLIENT_WORDS

# Clients whose command line installs plugins (Cursor keeps its plugins in the account).
INSTALLERS = ("claude_code", "codex")
MARKETPLACE_FILES = (
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
    ".cursor-plugin/marketplace.json",
)
PLUGIN_FILES = (
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    "plugin.json",
)


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _first(root: Path, names: tuple[str, ...]) -> Any:
    for name in names:
        data = _load(root / name)
        if isinstance(data, dict):
            return data
    return None


def _no_credentials(url: str) -> str:
    parts = urlsplit(url)
    if parts.netloc and "@" in parts.netloc:
        return urlunsplit(parts._replace(netloc=parts.netloc.rsplit("@", 1)[1]))
    return url


def _source(raw: Any) -> dict:
    """Where the plugin comes from, without credentials: path, repo or url, ref and sha."""
    if isinstance(raw, str):
        return {"path": raw}
    if not isinstance(raw, dict):
        return {}
    out = {k: raw[k] for k in ("repo", "url", "path", "ref", "sha") if isinstance(raw.get(k), str)}
    if "url" in out:
        out["url"] = _no_credentials(out["url"])
    return out


def _plugin_dir(root: Path, raw: Any) -> Path | None:
    """The plugin's folder inside the marketplace clone, for a relative source only."""
    path = raw if isinstance(raw, str) else None
    if isinstance(raw, dict) and raw.get("source") in ("local", None) and "url" not in raw:
        path = raw.get("path")
    if not isinstance(path, str) or "://" in path:
        return None
    folder = (root / path).resolve()
    return folder if folder.is_dir() and folder.is_relative_to(root.resolve()) else None


def _runs(entry: Any) -> str:
    """What an MCP server runs or where it connects, with secrets hidden."""
    entry = redact(entry)[0] if isinstance(entry, dict) else {}
    if isinstance(entry.get("url"), str):
        return _no_credentials(entry["url"])
    parts = [entry.get("command"), *(entry.get("args") or [])]
    return shlex.join(str(p) for p in parts if p is not None)


def _names(folder: Path, pattern: str) -> list[str]:
    return sorted(p.parent.name if p.name == "SKILL.md" else p.stem for p in folder.glob(pattern))


def _servers(folder: Path, manifest: dict) -> dict:
    """The plugin's MCP servers by name: the manifest's `mcpServers`, else `.mcp.json`."""
    servers: Any = manifest.get("mcpServers")
    if not isinstance(servers, dict):
        mcp = _first(folder, (".mcp.json", "mcp.json")) or {}
        servers = mcp.get("mcpServers", mcp) if isinstance(mcp, dict) else {}
    return servers


def _inside(folder: Path, entry: dict) -> dict:
    manifest = _first(folder, PLUGIN_FILES) or {}
    servers = _servers(folder, manifest)
    hooks: set[str] = set()
    for raw in (manifest.get("hooks"), entry.get("hooks"), _load(folder / "hooks/hooks.json")):
        if isinstance(raw, dict):
            hooks.update(
                raw.get("hooks", raw).keys() if isinstance(raw.get("hooks"), dict) else raw
            )
    return {
        "version": manifest.get("version") if isinstance(manifest.get("version"), str) else None,
        "description": manifest.get("description"),
        "skills": _names(folder, "skills/*/SKILL.md"),
        "commands": _names(folder, "commands/*.md"),
        "agents": _names(folder, "agents/*.md"),
        "hooks": sorted(hooks),
        "mcp_servers": [
            {"name": name, "runs": _runs(value)}
            for name, value in sorted(servers.items())
            if isinstance(value, dict)
        ],
    }


def _category_name(raw: Any) -> str | None:
    key = category_key(raw)
    return key[:1].upper() + key[1:] if key else None


def _author(raw: Any) -> str | None:
    if isinstance(raw, dict) and isinstance(raw.get("name"), str):
        return raw["name"]
    return raw if isinstance(raw, str) else None


def _can_add(client: str, marketplace: str, sources: dict[str, dict[str, str | None]]) -> bool:
    """Another client knows this marketplace with a source this client can add too."""
    for other, known in sources.items():
        source = known.get(marketplace) if other != client else None
        if not isinstance(source, str):
            continue
        path = Path(source)
        # Claude Code reads only its own format; Codex also reads the Claude Code one.
        if client == "claude_code" and path.is_absolute():
            return (path / ".claude-plugin/marketplace.json").is_file()
        return True
    return False


def _listed(adapters: dict[str, ClientAdapter]):
    """Each plugin a client's marketplaces list, as (client, marketplace, root, entry)."""
    for client in INSTALLERS:
        if client not in adapters:
            continue
        for marketplace, root in adapters[client].marketplace_roots().items():
            listed = _first(root, MARKETPLACE_FILES) or {}
            for entry in listed.get("plugins") or []:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                    yield client, marketplace, root, entry


def catalog(inventory, adapters: dict[str, ClientAdapter]) -> list[dict]:
    """Every plugin the marketplaces on this computer offer, once, with how each client gets it.

    `routes[client]` is "ready" (the client knows the marketplace) or "add_marketplace" (the
    marketplace can be added from another client's source first); a missing client cannot.
    """
    sources = {c: adapters[c].marketplace_sources() for c in INSTALLERS if c in adapters}
    installed: dict[str, list[str]] = {}
    for item in inventory.items:
        if item.kind is ItemKind.PLUGIN and "@" in item.name:
            clients = installed.setdefault(item.name, [])
            if item.client not in clients:
                clients.append(item.client)
    offers: dict[str, dict] = {}
    for client, marketplace, root, entry in _listed(adapters):
        plugin_id = f"{entry['name']}@{marketplace}"
        if plugin_id in offers:
            offers[plugin_id]["routes"][client] = "ready"
            continue
        folder = _plugin_dir(root, entry.get("source"))
        inside = _inside(folder, entry) if folder else None
        description = entry.get("description") or (inside or {}).get("description")
        offers[plugin_id] = {
            "id": plugin_id,
            "kind": "plugin",
            "name": entry["name"],
            "marketplace": marketplace,
            "description": description if isinstance(description, str) else "",
            "category": _category_name(entry.get("category")),
            "author": _author(entry.get("author")),
            "homepage": entry.get("homepage") if isinstance(entry.get("homepage"), str) else None,
            "source": _source(entry.get("source")),
            "inside": inside,
            "routes": {client: "ready"},
            "installed": installed.get(plugin_id, []),
        }
    for offer in offers.values():
        for client in INSTALLERS:
            missing = client in adapters and client not in offer["routes"]
            if missing and _can_add(client, offer["marketplace"], sources):
                offer["routes"][client] = "add_marketplace"
    return sorted(offers.values(), key=lambda o: (o["name"].lower(), o["marketplace"]))


def _offered_servers(adapters: dict[str, ClientAdapter]):
    """Each MCP server inside a plugin folder the marketplaces offer, once, as
    (plugin, marketplace, name, raw entry). The same plugins as `catalog`, and the entry is
    read as `_inside` reads it, but whole: the page never gets it, only the checks do."""
    seen: set[str] = set()
    for _, marketplace, root, entry in _listed(adapters):
        plugin_id = f"{entry['name']}@{marketplace}"
        folder = _plugin_dir(root, entry.get("source"))
        if plugin_id in seen or folder is None:
            continue
        seen.add(plugin_id)
        servers = _servers(folder, _first(folder, PLUGIN_FILES) or {})
        for name, value in sorted(servers.items()):
            if isinstance(value, dict):
                yield entry["name"], marketplace, name, value


def _from_plugin(item) -> bool:
    return item.scope is Scope.PLUGIN or item.source.kind is SourceKind.PLUGIN


def known_refusal(name: str, entry: dict, inventory, held: set[str]) -> str | None:
    """Why the Kitden gateway cannot take this server, from the entry alone (no network); None
    when it can. Checked against the plugin docs on 2026-10-26 (not a live client):
    - Claude Code reads `mcpServers` from plugin.json or `.mcp.json`; it also takes `.mcpb` and
      `.dxt` bundles, runs stdio servers from `${CLAUDE_PLUGIN_ROOT}`, and has http, sse and ws
      servers (code.claude.com/docs/en/plugins-reference).
    - Codex plugins keep `mcp.json` with a transport `type`; the docs show `streamable-http`
      only (developers.openai.com/codex/plugins/build).
    The gateway speaks streamable HTTP and stdio, so the rest is refused.
    """
    from kitden.views.skills import SCRIPT_SUFFIXES  # skills imports this module

    if name in held:
        return f"{name} is in the gateway already."
    same = [
        i
        for i in inventory.items
        if i.kind is ItemKind.MCP_SERVER and i.name == name and not i.via_gateway
    ]
    # A server an installed plugin brings is not the client's own entry; it cannot be moved.
    has = next((i for i in same if not _from_plugin(i)), None)
    if has is not None:
        client = CLIENT_WORDS.get(has.client, has.client)
        return f"{client} has {name} already. Move it into the gateway instead."
    server = gateway_entry(entry)
    kind = str(entry.get("type", "")).lower()
    if kind in ("sse", "ws") or str(server.get("url", "")).rstrip("/").endswith("/sse"):
        return f"{name} uses a connection the Kitden gateway does not support yet."
    if reads_elsewhere(entry, server):
        return f"{name} reads values Kitden can't fill in."
    words = [str(server.get("command", "")), *(str(a) for a in server.get("args") or [])]
    if any(w.endswith(".mcpb") for w in words):
        return f"{name} comes as a bundle; Kitden can't run it yet."
    in_folder = any(
        w.startswith(("./", "../")) or ("/" not in w and Path(w).suffix.lower() in SCRIPT_SUFFIXES)
        for w in words
    )
    if in_folder:
        return f"{name} runs a file inside its plugin folder; Kitden can't run it from the gateway."
    if "command" not in server and "url" not in server:
        return f"{name} could not be read from its file."
    # Last, so a plugin's own server says first why the gateway cannot run it: the client
    # would load the plugin's copy and the gateway's.
    plugin = next((i for i in same if _from_plugin(i)), None)
    if plugin is not None:
        client = CLIENT_WORDS.get(plugin.client, plugin.client)
        return f"{client} loads {name} from a plugin already."
    return None


def market_servers(inventory, adapters: dict[str, ClientAdapter], held: set[str]) -> list[dict]:
    """One row for each MCP server in a marketplace plugin on this computer. A row has no
    address and no command: the page shows a name, a kind and why it cannot be added."""
    rows = []
    for plugin, marketplace, name, entry in _offered_servers(adapters):
        remote = isinstance(entry.get("url"), str) or str(entry.get("type")).lower() in (
            "http",
            "streamable-http",
        )
        rows.append(
            {
                "id": f"{plugin}@{marketplace}/{name}",
                "name": name,
                "plugin": plugin,
                "marketplace": marketplace,
                "kind": "remote" if remote else "local",
                "held": name in held,
                "refusal": known_refusal(name, entry, inventory, held),
            }
        )
    return sorted(rows, key=lambda r: (r["marketplace"], r["name"].lower()))


def market_entry(adapters: dict[str, ClientAdapter], server_id: str) -> tuple[str, dict]:
    """The raw entry of a listed server, with its plugin's id; for the preview, not the page."""
    plugin_id, _, wanted = server_id.partition("/")
    for plugin, marketplace, name, entry in _offered_servers(adapters):
        if f"{plugin}@{marketplace}" == plugin_id and name == wanted:
            return plugin_id, entry
    raise ValueError("This server is no longer offered.")


# Marketplaces name the same category in different ways; one key per category.
CATEGORY_ALIASES = {
    "developer tools": "development",
    "engineering": "development",
    "creativity": "design",
}
WORD = re.compile(r"[a-z0-9]+")


def category_key(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    key = raw.strip().lower()
    return CATEGORY_ALIASES.get(key, key)


def _score(offer: dict, words: list[str]) -> int:
    """Name first, then category, then whole words of the description; 0 if a word is missing.

    A query word matches the start of a word in the name ("design" finds ui-designer), but the
    description needs the word itself or its plural, so "design" does not find "designed".
    """
    name = offer["name"].lower()
    name_words = WORD.findall(name)
    # A skill's `from` (its plugin) counts like a category.
    tags = f"{offer.get('category') or ''} {offer.get('from') or ''}".lower()
    category = WORD.findall(tags)
    text = set(WORD.findall(f"{offer['description']} {offer.get('marketplace') or ''}".lower()))
    score = 0
    for word in words:
        if name == word:
            score += 100
        elif any(w == word for w in name_words):
            score += 80
        elif any(w.startswith(word) for w in name_words):
            score += 60
        elif word in category or any(w.startswith(word) for w in category):
            score += 50
        elif word in text or f"{word}s" in text or f"{word}es" in text:
            score += 10
        else:
            return 0  # every word must match somewhere
    return score


def search(offers: list[dict], query: str) -> list[dict]:
    """Offers that match every word, best first: the name counts more than the description.

    Each found offer gets `match`: "name" when a word is in its name or category, "text" when
    only its description has the words, so the page can show those apart.
    """
    words = query.lower().split()
    if not words:
        return offers
    scored = [(_score(o, words), o) for o in offers]
    ranked = sorted(scored, key=lambda p: (-p[0], p[1]["name"].lower()))
    only_text = 10 * len(words)  # each word found in the description only
    return [{**o, "match": "text" if s == only_text else "name"} for s, o in ranked if s]
