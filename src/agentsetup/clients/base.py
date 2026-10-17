"""The interface every client adapter implements, plus small shared reading helpers."""

import json
import os
import re
import subprocess
import time
import tomllib
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentsetup.clients.versions import is_supported, parse_version, version_command
from agentsetup.model import (
    Client,
    ClientStatus,
    Enabled,
    Gateway,
    GatewayAuth,
    Item,
    ItemKind,
    Project,
    ReadStatus,
    Scope,
    Source,
    SourceKind,
    Step,
    UnknownReason,
)
from agentsetup.redact import redact

# MCP entry fields shown on the page (after redaction). Everything else stays hidden.
_SUMMARY_FIELDS = ("type", "transport", "command", "args", "url")


@dataclass
class Scan:
    """Everything one adapter read in one pass. Reading never writes (FR-007)."""

    items: list[Item] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    problems: list[Source] = field(default_factory=list)


class Reader:
    """Reads files and records why a file could not be read, instead of failing."""

    def __init__(self, owner: str) -> None:
        self.owner = owner
        self.problems: list[Source] = []

    def problem(self, path: Path, reason: UnknownReason) -> None:
        self.problems.append(
            Source(
                kind=SourceKind.FILE,
                path=str(path),
                owner_client=self.owner,
                read_status=ReadStatus.UNKNOWN,
                unknown_reason=reason,
            )
        )

    def _read(self, path: Path, parse: Callable[[str], Any], errors: tuple) -> Any:
        try:
            text = path.read_text()
        except FileNotFoundError:
            return None
        except (PermissionError, IsADirectoryError):
            self.problem(path, UnknownReason.NO_ACCESS)
            return None
        try:
            return parse(text)
        except errors:
            self.problem(path, UnknownReason.PARSE_ERROR)
            return None

    def json(self, path: Path) -> Any:
        return self._read(path, json.loads, (json.JSONDecodeError, UnicodeDecodeError))

    def toml(self, path: Path) -> Any:
        return self._read(path, tomllib.loads, (tomllib.TOMLDecodeError, UnicodeDecodeError))

    def failed(self, path: Path) -> bool:
        return any(p.path == str(path) for p in self.problems)


def file_source(
    path: Path, owner: str, key_path: str | None = None, kind: SourceKind = SourceKind.FILE
) -> Source:
    return Source(kind=kind, path=str(path), owner_client=owner, key_path=key_path)


def skill_name(skill_md: Path) -> str:
    """The `name:` from SKILL.md front matter, or the folder name."""
    try:
        head = skill_md.read_text().split("---", 2)
    except OSError:
        return skill_md.parent.name
    if len(head) == 3 and (m := re.search(r"^name:\s*(.+?)\s*$", head[1], re.M)):
        return m.group(1).strip("'\"")
    return skill_md.parent.name


def skills_in(folder: Path) -> list[tuple[str, Path, Path | None]]:
    """(name, real SKILL.md path, link path if the skill folder is a symlink)."""
    if not folder.is_dir():
        return []
    found = []
    for entry in sorted(folder.iterdir()):
        skill_md = entry / "SKILL.md"
        if entry.name.startswith(".") or not skill_md.is_file():
            continue
        link = entry if entry.is_symlink() else None
        found.append((skill_name(skill_md), Path(os.path.realpath(skill_md)), link))
    return found


def skill_items(
    client: str,
    folder: Path,
    scope: Scope,
    owner: str,
    kind: SourceKind = SourceKind.FOLDER,
    project: str | None = None,
    enabled: Enabled = Enabled.ON,
) -> list[Item]:
    items = []
    for name, real, link in skills_in(folder):
        source = Source(
            kind=kind, path=str(real), owner_client=owner, link_path=str(link) if link else None
        )
        items.append(
            Item(
                client=client,
                kind=ItemKind.SKILL,
                name=name,
                source=source,
                scope=scope,
                project=project,
                enabled=enabled,
            )
        )
    return items


def mcp_item(
    client: str,
    name: str,
    entry: Any,
    source: Source,
    scope: Scope,
    project: str | None = None,
    enabled: Enabled = Enabled.ON,
) -> Item:
    """An MCP server item whose summary is already redacted (FR-006)."""
    redacted, secret = redact(entry if isinstance(entry, dict) else {})
    summary = tuple(
        (key, json.dumps(redacted[key]) if not isinstance(redacted[key], str) else redacted[key])
        for key in _SUMMARY_FIELDS
        if key in redacted
    )
    return Item(
        client=client,
        kind=ItemKind.MCP_SERVER,
        name=name,
        source=source,
        scope=scope,
        project=project,
        enabled=enabled,
        secret_present=secret,
        summary=summary,
    )


def project(path: str, known_by: str) -> Project:
    return Project(path=path, exists=Path(path).is_dir(), known_by=(known_by,))


# Version commands can be slow (Cursor starts Electron), so results are reused for a while.
VERSION_CACHE_SECONDS = 600.0
_VERSION_CACHE: dict[str, tuple[str | None, float]] = {}


def read_command_version(client: str) -> str | None:
    cached = _VERSION_CACHE.get(client)
    if cached and time.monotonic() < cached[1]:
        return cached[0]
    version = None
    command = version_command(client)
    if command:
        try:
            # The command is our own fixed client path plus "--version"; no user input.
            out = subprocess.run(  # noqa: S603
                command, capture_output=True, text=True, timeout=20, check=False
            ).stdout
            version = parse_version(client, out)
        except (OSError, subprocess.SubprocessError):
            version = None
    _VERSION_CACHE[client] = (version, time.monotonic() + VERSION_CACHE_SECONDS)
    return version


class ClientAdapter(ABC):
    """Reads one client's setup from files under `home`.

    `home` is the user's home folder in real use and a sandbox folder in tests.
    `read_version` returns the installed version, or None if the client command is missing.
    """

    id: str
    display_name: str
    config_root: str

    def __init__(self, home: Path, read_version: Callable[[], str | None] | None = None) -> None:
        self.home = home
        self._read_version = read_version or (lambda: read_command_version(self.id))

    def detect(self) -> Client:
        version = self._read_version()
        root = self.home / self.config_root
        found = version is not None or root.exists()
        return Client(
            id=self.id,
            display_name=self.display_name,
            status=ClientStatus.FOUND if found else ClientStatus.NOT_FOUND,
            version=version,
            version_supported=is_supported(self.id, version),
            config_roots=(str(root),),
        )

    def extra_clients(self) -> list[Client]:
        """Other client surfaces this adapter also reads (for example the Desktop Code tab)."""
        return []

    @abstractmethod
    def scan(self) -> Scan:
        """Read MCP servers, skills, plugins, hooks, marketplaces and known projects."""

    # Changes (write-matrix.md). Clients without writes keep these defaults.

    def item_actions(self, item: Item) -> tuple[str, ...]:
        """Actions the page may offer for this item."""
        return ()

    def gateway_step(self, gateway: Gateway, name: str) -> Step:
        """The edit that adds the gateway entry for this client (user scope)."""
        raise ValueError(f"{self.id} cannot be connected to a gateway")

    def remove_step(self, item: Item) -> Step:
        """The edit that removes one direct MCP entry."""
        raise ValueError(f"{item.name} cannot be removed here")

    def plugin_step(self, item: Item, enable: bool) -> Step:
        """The edit that turns one plugin on or off."""
        raise ValueError(f"{item.name} cannot be turned {'on' if enable else 'off'} here")

    def setup_server_step(self, command: str, args: list[str]) -> Step:
        """The edit that adds the read-only setup server (user scope, FR-032)."""
        raise ValueError(f"the setup server cannot be added to {self.id}")

    def marketplace_sources(self) -> dict[str, str | None]:
        """Marketplace name -> a source other clients can add (None: built into this client)."""
        return {}


REMOVE_DIRECT = "mcp.remove_direct"
PLUGIN_ENABLE = "plugin.enable"
SETUP_SERVER = "setup_server.register"
SETUP_NAME = "agentsetup"
PLUGIN_DISABLE = "plugin.disable"


def toggle_action(item: Item) -> tuple[str, ...]:
    """The opposite of a plugin's known state; nothing when the state is unknown."""
    if item.enabled is Enabled.ON:
        return (PLUGIN_DISABLE,)
    if item.enabled is Enabled.OFF:
        return (PLUGIN_ENABLE,)
    return ()


def check_toggle(adapter: "ClientAdapter", item: Item, enable: bool) -> None:
    if (PLUGIN_ENABLE if enable else PLUGIN_DISABLE) not in adapter.item_actions(item):
        raise ValueError(f"{item.name} cannot be turned {'on' if enable else 'off'} here")


def is_direct_entry(item: Item, client: str, scopes: set[Scope]) -> bool:
    """An MCP server written in a client file we can read, in a scope we may edit."""
    return (
        item.kind is ItemKind.MCP_SERVER
        and item.client == client
        and item.source.kind is SourceKind.FILE
        and item.source.read_status is ReadStatus.OK
        and item.scope in scopes
        and item.source.path is not None
        and item.via_gateway is None
    )


def bearer_header(gateway: Gateway, reference: str) -> dict[str, str]:
    """Authorization header that names the key's variable, never its value (FR-035)."""
    if gateway.auth is not GatewayAuth.ENV_KEY:
        return {}
    return {"Authorization": "Bearer " + reference.format(gateway.key_env_var)}
