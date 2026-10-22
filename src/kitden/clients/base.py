"""The interface every client adapter implements, plus small shared reading helpers."""

import json
import os
import re
import tomllib
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kitden.clients import version_cache
from kitden.clients.versions import is_supported
from kitden.model import (
    COPY_FOLDER,
    REMOVE_FOLDER,
    Client,
    ClientStatus,
    Enabled,
    FolderCopy,
    FolderRemoval,
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
from kitden.redact import redact

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
    """(name, real SKILL.md path, link path if the skill folder or its SKILL.md is a symlink)."""
    if not folder.is_dir():
        return []
    found = []
    for entry in sorted(folder.iterdir()):
        skill_md = entry / "SKILL.md"
        if entry.name.startswith(".") or not skill_md.is_file():
            continue
        link = entry if entry.is_symlink() or skill_md.is_symlink() else None
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


def expand(folder: Path, category: str, glob: str = "*.md") -> list[tuple[Path, str, str]]:
    """(path, category, name) for each file matching `glob` in `folder` and its sub-folders.

    The name is the path inside `folder` without the extension, sub-folders joined by ":"
    (`frontend/component.md` -> `frontend:component`). Hidden files and folders are skipped.
    Symlinked sub-folders are not followed, so a link loop cannot hang the scan.
    """
    if not folder.is_dir():
        return []
    found = []
    for path in sorted(folder.rglob(glob)):
        parts = path.relative_to(folder).with_suffix("").parts
        if path.is_file() and not any(p.startswith(".") for p in parts):
            found.append((path, category, ":".join(parts)))
    return found


def is_home(folder: Path, home: Path) -> bool:
    """True when a project folder is the home folder. Project readers then skip the files that
    are already read for the user (for example `~/.claude/CLAUDE.md`)."""
    return os.path.realpath(folder) == os.path.realpath(home)


def instruction_items(
    client: str,
    files: list[tuple[Path, str] | tuple[Path, str, str]],
    scope: Scope,
    owner: str,
    project: str | None = None,
) -> list[Item]:
    """One item for each file that exists. A file is (path, category) or, from `expand`,
    (path, category, name); without a name the item is named by the file name."""
    items = []
    for path, category, *name in files:
        if not path.is_file():
            continue
        items.append(
            Item(
                client=client,
                kind=ItemKind.INSTRUCTIONS,
                name=name[0] if name else path.name,
                source=file_source(path, owner),
                scope=scope,
                project=project,
                summary=(("category", category),),
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


class ClientAdapter(ABC):
    """Reads one client's setup from files under `home`.

    `home` is the user's home folder in real use and a sandbox folder in tests.
    `read_version` returns the installed version, or None when it is not known yet. By default
    it reads the disk cache (version_cache), so a scan never runs a client command.
    """

    id: str
    display_name: str
    config_root: str
    skills_folder: str = ""  # where the client reads the user's own skills, under home
    skill_note: str = ""  # what to do after a skill is added
    skipped: bool = False  # a quick scan left out an answer that is still on its way

    def __init__(self, home: Path, read_version: Callable[[], str | None] | None = None) -> None:
        self.home = home
        self._read_version = read_version or (lambda: version_cache.cached_version(home, self.id))

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

    def add_server_step(self, name: str, entry: dict) -> Step:
        """The edit that adds one MCP entry, already in this client's format (user scope)."""
        raise ValueError(f"{self.id} cannot take an MCP entry")

    def plugin_step(self, item: Item, enable: bool) -> Step:
        """The edit that turns one plugin on or off."""
        raise ValueError(f"{item.name} cannot be turned {'on' if enable else 'off'} here")

    def setup_server_step(self, command: str, args: list[str]) -> Step:
        """The edit that adds the read-only setup server (user scope, FR-032)."""
        raise ValueError(f"the setup server cannot be added to {self.id}")

    def marketplace_sources(self) -> dict[str, str | None]:
        """Marketplace name -> a source other clients can add (None: built into this client)."""
        return {}

    def marketplace_roots(self) -> dict[str, Path]:
        """Marketplace name -> the folder on this computer that holds its marketplace file."""
        return {}

    def marketplace_add_step(self, name: str, source: str) -> Step:
        """Add a marketplace with the client's own command."""
        raise ValueError(f"{self.id} cannot add a marketplace from here")

    def plugin_install_step(self, plugin_id: str, project: str | None = None) -> Step:
        """Install a plugin with the client's own command: for the user, or into `project`."""
        raise ValueError(f"{self.id} cannot install a plugin from here")

    def plugin_remove_step(self, item: Item) -> Step:
        """Remove one installed plugin with the client's own command."""
        raise ValueError(f"{item.name} cannot be removed here")

    def skill_copy_step(self, folder: Path, readers: list[str], project: str | None = None) -> Step:
        """Copy a skill folder into this client's skills folder, or into the same folder
        inside `project` (a file the project shares).

        `readers` are the clients that read that folder; the review names them.
        """
        if not self.skills_folder:
            raise ValueError(f"{self.id} has no skills folder")
        if project is not None and not Path(project).is_dir():
            raise ValueError(f"the project folder {project} is missing")
        root = Path(project) if project is not None else self.home
        target = root / self.skills_folder / folder.name
        if target.exists() or target.is_symlink():
            raise ValueError(f"{self.display_name} already has a skill named {folder.name}")
        copy = FolderCopy(source=str(folder), target=str(target), readers=list(readers))
        return Step(
            client=self.id,
            scope=Scope.PROJECT if project is not None else Scope.USER,
            name=folder.name,
            mechanism=COPY_FOLDER,
            copy=copy,
            restart_note=self.skill_note or None,
            shared_file=project is not None,
        )

    def skill_remove_step(
        self, item: Item, readers: list[str], keeps: list[str] | None = None
    ) -> Step:
        """Remove one skill folder of this client; Undo copies it back from the backup.

        `readers` are the clients that read that folder; `keeps` those of them that load
        another copy still. The review names them.
        """
        if SKILL_REMOVE not in self.item_actions(item) or item.source.path is None:
            raise ValueError(f"{item.name} cannot be removed here")
        removal = FolderRemoval(
            path=str(Path(item.source.path).parent),
            readers=list(readers),
            keeps=list(keeps or []),
        )
        return Step(
            client=self.id,
            scope=item.scope,
            name=item.name,
            mechanism=REMOVE_FOLDER,
            removal=removal,
            restart_note=self.skill_note or None,
            shared_file=item.scope is Scope.PROJECT,
        )


REMOVE_DIRECT = "mcp.remove_direct"
PLUGIN_ENABLE = "plugin.enable"
SETUP_SERVER = "setup_server.register"
SETUP_NAME = "kitden"
PLUGIN_DISABLE = "plugin.disable"
PLUGIN_REMOVE = "plugin.remove"
SKILL_REMOVE = "skill.remove"


def is_own_skill(item: Item, client: str) -> bool:
    """A real skill folder in one of the client's own skills folders, global or a project's."""
    return (
        item.kind is ItemKind.SKILL
        and item.client == client
        and item.scope in (Scope.USER, Scope.PROJECT)
        and item.source.kind is SourceKind.FOLDER
        and item.source.owner_client == client
        and item.source.link_path is None
        and item.source.path is not None
    )


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


def plain_source(source: str, client: str) -> str:
    """A marketplace source to pass as a command argument. Arguments are visible to `ps`, so a
    source that holds a password or token (a URL's user part, a token shape) is refused."""
    if redact(source)[1]:
        raise ValueError(f"Its source holds a password or token; add it in {client} by hand.")
    return source


def bearer_header(gateway: Gateway, reference: str) -> dict[str, str]:
    """Authorization header that names the key's variable, never its value (FR-035)."""
    if gateway.auth is not GatewayAuth.ENV_KEY:
        return {}
    return {"Authorization": "Bearer " + reference.format(gateway.key_env_var)}
