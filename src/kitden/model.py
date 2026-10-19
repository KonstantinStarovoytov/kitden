"""Shared data model: clients, items, sources, gateways and changes."""

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def _hash(*parts: object) -> str:
    return hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()[:16]


class SourceKind(StrEnum):
    FILE = "file"
    FOLDER = "folder"
    OTHER_CLIENT_FOLDER = "other_client_folder"
    PLUGIN = "plugin"
    ACCOUNT = "account"
    STATE_DATABASE = "state_database"
    MANAGED = "managed"


class ReadStatus(StrEnum):
    OK = "ok"
    UNKNOWN = "unknown"


class UnknownReason(StrEnum):
    STORED_IN_ACCOUNT = "stored_in_account"
    NO_ACCESS = "no_access"
    UNRECOGNIZED_FORMAT = "unrecognized_format"
    PARSE_ERROR = "parse_error"
    MAY_BE_STALE = "may_be_stale"
    NOT_DOCUMENTED = "not_documented"


class Scope(StrEnum):
    MANAGED = "managed"
    USER = "user"
    PROJECT = "project"
    LOCAL = "local"
    PLUGIN = "plugin"
    ACCOUNT = "account"


class ItemKind(StrEnum):
    MCP_SERVER = "mcp_server"
    SKILL = "skill"
    PLUGIN = "plugin"
    HOOK = "hook"
    MARKETPLACE = "marketplace"


class Enabled(StrEnum):
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


class FindingType(StrEnum):
    DUPLICATE_IN_CLIENT = "duplicate_in_client"
    CROSS_LOADED = "cross_loaded"
    SAME_IN_OTHER_CLIENTS = "same_in_other_clients"
    SCOPE_OVERRIDE = "scope_override"
    BYPASSES_GATEWAY = "bypasses_gateway"
    UNKNOWN_STATE = "unknown_state"
    VERSION_UNSUPPORTED = "version_unsupported"


class Severity(StrEnum):
    WARNING = "warning"
    INFO = "info"


class ChangeState(StrEnum):
    PREVIEWED = "previewed"
    STALE = "stale"
    CANCELLED = "cancelled"
    APPLYING = "applying"
    VERIFIED = "verified"
    RESTORED = "restored"
    UNDONE = "undone"
    UNDO_BLOCKED = "undo_blocked"


class GatewayAuth(StrEnum):
    NONE = "none"
    ENV_KEY = "env_key"
    OAUTH = "oauth"


class ClientStatus(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    UNREADABLE = "unreadable"


@dataclass(frozen=True)
class Client:
    id: str
    display_name: str
    status: ClientStatus
    version: str | None = None
    version_supported: bool = False
    config_roots: tuple[str, ...] = ()
    write_capabilities: frozenset[str] = frozenset()
    app_url: str | None = None  # `claude://` when the client's Mac app is installed (apps.py)


@dataclass(frozen=True)
class Source:
    kind: SourceKind
    path: str | None
    owner_client: str
    key_path: str | None = None
    read_status: ReadStatus = ReadStatus.OK
    unknown_reason: UnknownReason | None = None
    link_path: str | None = None
    content_hash: str | None = None

    def __post_init__(self) -> None:
        if (self.read_status is ReadStatus.UNKNOWN) != (self.unknown_reason is not None):
            raise ValueError("unknown_reason is required exactly when read_status is unknown")

    @property
    def id(self) -> str:
        return _hash(self.kind, self.path, self.key_path)


@dataclass(frozen=True)
class Item:
    client: str
    kind: ItemKind
    name: str
    source: Source
    scope: Scope
    project: str | None = None
    enabled: Enabled = Enabled.ON
    secret_present: bool = False
    summary: tuple[tuple[str, str], ...] = ()
    via_gateway: str | None = None
    actions: tuple[str, ...] = ()
    change_hint: str | None = None  # where to change it when the tool cannot (FR-028)

    @property
    def id(self) -> str:
        return _hash(self.client, self.kind, self.name, self.source.id)


@dataclass(frozen=True)
class Project:
    path: str
    exists: bool
    known_by: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return _hash(self.path)


@dataclass(frozen=True)
class Finding:
    type: FindingType
    severity: Severity
    items: tuple[str, ...]
    explanation: str
    names: tuple[str, ...] = ()
    client: str | None = None

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("a finding needs at least one item")

    @property
    def id(self) -> str:
        return _hash(self.type, *sorted(self.items))


_TRANSITIONS: dict[ChangeState, set[ChangeState]] = {
    ChangeState.PREVIEWED: {ChangeState.STALE, ChangeState.CANCELLED, ChangeState.APPLYING},
    ChangeState.APPLYING: {ChangeState.VERIFIED, ChangeState.RESTORED},
    ChangeState.VERIFIED: {ChangeState.UNDONE, ChangeState.UNDO_BLOCKED},
}


def _new_change_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


@dataclass
class FileEdit:
    """One entry changed in one file. `before` and `after` may hold secrets: never show them."""

    path: str
    fmt: str  # "json" or "toml"
    key: tuple[str, ...]
    after: Any  # json_splice.ABSENT removes the entry
    before: Any = None  # read at preview
    check: str = "file"  # "file": the whole file must be unchanged; "entry": only this entry
    before_hash: str | None = None  # None when the file did not exist
    after_hash: str | None = None
    backup_path: str | None = None
    masked_diff: str = ""


@dataclass
class GatewayEdit:
    """One remote server added to a gateway (feature 006). `server` may hold secrets."""

    gateway_id: str
    url: str  # the gateway's endpoint address: the step's place on the Changes page
    name: str  # the server's name in the gateway
    server: dict  # type, url, headers, as MetaMCP takes them
    server_uuid: str | None = None  # known after apply; undo removes it
    masked_diff: str = ""


GATEWAY_CLIENT = "gateway"  # the pseudo-client of a gateway step
COPY_FOLDER = "copy_folder"  # the mechanism of a step that copies a skill folder


@dataclass
class FolderCopy:
    """A skill folder copied into a client's skills folder (Discover, phase 2).

    The target must not exist before. Undo removes the copy only while its content hash is
    the one written at Apply; a changed copy stays.
    """

    source: str
    target: str
    readers: list[str] = field(default_factory=list)  # clients that read the target folder
    content_hash: str | None = None  # of the source at preview; the copy must read back the same
    masked_diff: str = ""


@dataclass
class Step:
    """One target of a change: one client, scope and entry, written by one mechanism.

    A step has a file edit, a gateway edit or a folder copy; a gateway step's client is
    "gateway".
    """

    client: str
    scope: Scope
    name: str
    edit: FileEdit | None = None
    mechanism: str = "format_preserving_edit"  # or "client_cli", "gateway_api", "copy_folder"
    gateway: GatewayEdit | None = None
    copy: FolderCopy | None = None
    command: list[str] | None = None
    undo_command: list[str] | None = None  # the inverse command; Undo runs it, no file restore
    cwd: str | None = None
    restart_note: str | None = None
    login_note: str | None = None
    shared_file: bool = False


@dataclass
class Change:
    action: str
    state: ChangeState = ChangeState.PREVIEWED
    id: str = field(default_factory=_new_change_id)
    steps: list[Step] = field(default_factory=list)
    error: str | None = None

    def move_to(self, new: ChangeState) -> None:
        if new not in _TRANSITIONS.get(self.state, set()):
            raise ValueError(f"cannot move from {self.state} to {new}")
        self.state = new

    @property
    def restart_needed(self) -> dict[str, bool]:
        return {step.client: bool(step.restart_note) for step in self.steps}

    @property
    def shared_file_warning(self) -> bool:
        return any(step.shared_file for step in self.steps)


_ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]*")


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, "")
    )


@dataclass(frozen=True)
class Gateway:
    url: str
    ui_url: str | None = None
    auth: GatewayAuth = GatewayAuth.NONE
    key_env_var: str | None = None
    # Sign-in for managing the gateway from Kitden (feature 006): the email is kept, the
    # password lives in an environment variable whose name is kept.
    login_email: str | None = None
    login_password_env_var: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", normalize_url(self.url))
        if self.auth is GatewayAuth.ENV_KEY and not self.key_env_var:
            raise ValueError("key_env_var must be an environment variable name, never a secret")
        if self.key_env_var and not _ENV_NAME.fullmatch(self.key_env_var):
            raise ValueError("key_env_var must be an environment variable name, never a secret")
        if bool(self.login_email) != bool(self.login_password_env_var):
            raise ValueError("A sign-in needs both the email and the password variable's name")
        if self.login_password_env_var and not _ENV_NAME.fullmatch(self.login_password_env_var):
            raise ValueError(
                "login_password_env_var must be an environment variable name, never a password"
            )
        if self.login_email and ("@" not in self.login_email or " " in self.login_email):
            raise ValueError("The sign-in email does not look like an email address")

    @property
    def kind(self) -> str:
        """Which gateway the address belongs to, told from its path: MetaMCP serves
        `/metamcp/<endpoint>/mcp`, Obot `/mcp-connect/<vmcp id>` (feature 007)."""
        path = urlsplit(self.url).path
        if path.startswith("/metamcp/"):
            return "metamcp"
        if path.startswith("/mcp-connect/"):
            return "obot"
        return "other"

    @property
    def managed(self) -> bool:
        """Kitden can read what the gateway holds: MetaMCP with a sign-in, Obot with a key."""
        if self.kind == "obot":
            return bool(self.key_env_var)
        return bool(self.login_email and self.login_password_env_var)

    @property
    def movable(self) -> bool:
        """Kitden can move servers into it from here: a managed MetaMCP or Obot gateway."""
        return self.kind in ("metamcp", "obot") and self.managed

    @property
    def id(self) -> str:
        return _hash(self.url)
