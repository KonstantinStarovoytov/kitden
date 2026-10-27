"""The change engine: preview, stale check, back up, apply, verify, restore, undo (T042).

States follow data-model.md. Research R7 has the safe write pattern.

Two kinds of checks:
- "file": the whole file must be unchanged since preview (before apply) or since apply (before
  undo). Used for files that only people and our tool edit.
- "entry": only the edited entry is compared. Used for `~/.claude.json`, which Claude Code
  rewrites during normal use. Undo then restores just that entry, unless the whole file is still
  as we left it, in which case the backup bytes are restored exactly.
"""

import contextlib
import difflib
import hashlib
import json
import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomlkit

from kitden.changes import json_splice, toml_edit
from kitden.changes.atomic import RefusedWriteError, write_atomic
from kitden.changes.backup import ChangeStore, holds_secret
from kitden.changes.client_cli import CommandResult
from kitden.changes.copy_folder import (
    CopyRefusedError,
    copy_folder,
    digest,
    list_files,
    remove_folder,
)
from kitden.changes.json_splice import ABSENT, PRESENT, UnrecognizedFormatError
from kitden.gateway_api import GatewayError
from kitden.gateways import data_dir
from kitden.local_gateway import keychain
from kitden.local_gateway.keychain import KeychainError
from kitden.model import (
    Change,
    ChangeState,
    ClientStatus,
    FileEdit,
    FolderCopy,
    FolderRemoval,
    GatewayEdit,
    KeychainItem,
    Scope,
    Step,
)
from kitden.redact import masked_command, redact

if TYPE_CHECKING:
    from kitden.views.inventory import Inventory

EDITORS = {"json": json_splice, "toml": toml_edit}
CLIENT_CLI = "client_cli"
FILE_EDIT = "format_preserving_edit"
GATEWAY_API = "gateway_api"  # a step that adds a server to a gateway (feature 006)
# A step that copies a skill folder has mechanism model.COPY_FOLDER; one that removes a skill
# folder has model.REMOVE_FOLDER.

Runner = Callable[[list[str], str | None], CommandResult]
# Opens a signed-in client for the gateway a step names; used as a context manager.
GatewayClients = Callable[[GatewayEdit], AbstractContextManager]
# The home folder and the folders a change may write in (see `writable_roots`).
Roots = Callable[[], tuple[Path, list[Path]]]


class ChangeRefusedError(ValueError):
    """The change cannot be previewed (unknown format, hard link, nothing to change)."""


class NothingToChangeError(ChangeRefusedError):
    """The entry is already as the change would leave it; `client` is whose file it is."""

    def __init__(self, path: str, client: str) -> None:
        super().__init__(f"nothing to change in {path}")
        self.client = client


class _ApplyError(Exception):
    pass


OUTSIDE = "Kitden writes only in your home folder and your known projects."


def _real(path: str | Path) -> Path:
    return Path(os.path.realpath(path))


def writable_roots(home: Path, inventory: "Inventory") -> list[Path]:
    """The folders a change may write in, as real paths, each once and in this order: the home
    folder, Kitden's data folder, every known project of the inventory (there or not) and the
    settings folders of each found client (Codex's CODEX_HOME can sit elsewhere).

    Known projects come from the clients' own files and can sit on another disk; an empty or
    relative path there is left out (`realpath("")` is the folder Kitden runs in). A client
    folder linked out of the home folder stays writable (its real path is a root); a single
    settings file linked out does not. `/` and the folders that hold the home folder count only
    for a command's own folder (see `_allowed`).
    """
    known = [p.path for p in inventory.projects]
    for client in inventory.clients:
        if client.status is ClientStatus.FOUND:
            known += client.config_roots
    places = [home, data_dir(home), *(p for p in known if os.path.isabs(p))]
    return list(dict.fromkeys(_real(p) for p in places))


def _identity(path: Path) -> tuple[int, int] | None:
    try:
        found = os.stat(path)
    except OSError:
        return None
    return found.st_dev, found.st_ino


def _stops(home: Path, roots: list[Path]) -> set[Path]:
    """The roots that are `/` or hold the home folder, found by file identity, not by text:
    APFS ignores letter case (`/users`), `/System/Volumes/Data/Users` is `/Users`, and
    `/System/Volumes/Data` is not `/` but holds `Users/<name>` (checked 2026-10-23, macOS 26)."""
    real_home = _real(home)
    above = {_identity(p) for p in (Path("/"), *real_home.parents)} - {None}
    me, below = _identity(real_home), real_home.relative_to("/")

    def stop(root: Path) -> bool:
        return _identity(root) in above or (me is not None and _identity(root / below) == me)

    return {r for r in roots if stop(r)}


def _allowed(path: Path, roots: list[Path], stops: set[Path], folder: bool) -> bool:
    """`path` is a root or inside one.

    A root that is `/` or holds the home folder (one of `stops`) counts only as the very folder
    a command runs in, as `project_chain` matches such folders only to themselves: Claude Code
    records a project for any folder it started in, and that must not make every path writable.
    """
    for root in roots:
        if root in stops:
            if folder and path == root:
                return True
        elif path == root or root in path.parents:
            return True
    return False


def writable(path: str | Path, home: Path, roots: list[Path]) -> bool:
    """A change may write `path`: the test `_check_places` makes for each file, so a page that
    asks first never offers what the engine refuses. `roots` are `writable_roots`."""
    return _allowed(_real(path), roots, _stops(home, roots), folder=False)


def _places(step: Step) -> list[str]:
    """The files and folders a step writes. A gateway address and a Keychain item are not
    paths; the folder a command runs in is checked on its own."""
    places = [
        step.edit.path if step.edit is not None else None,
        step.copy.target if step.copy is not None else None,
        step.removal.path if step.removal is not None else None,
    ]
    return [p for p in places if p]


def step_path(step: Step) -> str | None:
    """Where a step writes: the file, the gateway address, the copied or the removed folder."""
    if step.edit is not None:
        return step.edit.path
    if step.gateway is not None:
        return step.gateway.url
    if step.removal is not None:
        return step.removal.path
    return step.copy.target if step.copy is not None else None


def step_readers(step: Step) -> list[str] | None:
    """The clients that read a copied or removed folder, or that a plugin step reaches; None for
    other steps."""
    if step.copy is not None:
        return step.copy.readers
    return step.removal.readers if step.removal is not None else step.reaches


def _sha(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def _read(path: str) -> bytes | None:
    try:
        return Path(path).read_bytes()
    except FileNotFoundError:
        return None


def _value(edit: FileEdit, data: bytes | None) -> Any:
    return EDITORS[edit.fmt].get_value((data or b"").decode(), edit.key)


def _render(edit: FileEdit, value: Any) -> list[str]:
    if value is ABSENT:
        return []
    if value is PRESENT:
        return [f'"{edit.key[-1]}": added by the client']
    shown = redact(value)[0]
    if edit.fmt == "toml":
        return tomlkit.dumps(toml_edit.nested(edit.key, shown)).strip().splitlines()
    return json.dumps({edit.key[-1]: shown}, indent=2, ensure_ascii=False).splitlines()


def masked_diff(edit: FileEdit) -> str:
    """The entry before and after, with secrets hidden. Never the raw values."""
    lines = difflib.unified_diff(
        _render(edit, edit.before), _render(edit, edit.after), "before", "after", lineterm="", n=99
    )
    return f"{' > '.join(edit.key)}\n" + "\n".join(lines)


def _matches(step: Step, value: Any, expected: Any) -> bool:
    if expected is PRESENT:
        return value is not ABSENT
    # A client command may add fields of its own; our fields must all be there.
    if step.mechanism == CLIENT_CLI and isinstance(value, dict) and isinstance(expected, dict):
        return all(value.get(k) == v for k, v in expected.items())
    return value == expected


def _undo_entries(steps: list[Step], data: bytes | None) -> bytes | None:
    """Put back each entry of one file, last step first. None if any entry is no longer ours."""
    try:
        text = (data or b"").decode()
    except UnicodeDecodeError:
        return None
    for step in reversed(steps):
        edit = step.edit
        if edit.check != "entry":
            return None
        editor = EDITORS[edit.fmt]
        try:
            ours = _matches(step, editor.get_value(text, edit.key), edit.after)
        except UnrecognizedFormatError:
            return None
        if not ours:
            return None
        if edit.before is ABSENT:
            text = editor.delete_value(text, edit.key)
        else:
            text = editor.set_value(text, edit.key, edit.before)
    return text.encode()


def _by_command(step: Step) -> bool:
    return step.mechanism == CLIENT_CLI and bool(step.undo_command)


def _command_paths(steps: list[Step]) -> set[str]:
    """Files whose every step is taken back by an inverse command, not by restoring bytes.

    On a file with both kinds of step, the inverse commands run first (an install leaves more
    than the file behind), then the file gets its planned bytes.
    """
    paths: dict[str, bool] = {}
    for step in steps:
        if step.edit is not None:
            paths[step.edit.path] = paths.get(step.edit.path, True) and _by_command(step)
    return {path for path, ok in paths.items() if ok}


def _shown(command: list[str]) -> str:
    return " ".join(masked_command(command))


def _encode(value: Any) -> dict:
    if value is PRESENT:
        return {"present": True}
    return {"absent": True} if value is ABSENT else {"value": value}


def _decode(record: dict) -> Any:
    if record.get("present"):
        return PRESENT
    return ABSENT if record.get("absent") else record.get("value")


def _edit_record(edit: FileEdit | None) -> dict | None:
    if edit is None:
        return None
    return {
        "path": edit.path,
        "fmt": edit.fmt,
        "key": list(edit.key),
        "check": edit.check,
        "before": _encode(edit.before),
        "after": _encode(edit.after),
        "before_hash": edit.before_hash,
        "after_hash": edit.after_hash,
        "backup_path": edit.backup_path,
        "masked_diff": edit.masked_diff,
    }


def _gateway_record(gateway: GatewayEdit | None) -> dict | None:
    if gateway is None:
        return None
    return {
        "gateway_id": gateway.gateway_id,
        "url": gateway.url,
        "name": gateway.name,
        "server": gateway.server,
        "server_uuid": gateway.server_uuid,
        "masked_diff": gateway.masked_diff,
    }


def _copy_record(copy: FolderCopy | None) -> dict | None:
    return None if copy is None else dict(copy.__dict__)


def _removal_record(removal: FolderRemoval | None) -> dict | None:
    return None if removal is None else dict(removal.__dict__)


def _keychain_record(items: list[KeychainItem]) -> list[dict]:
    """What a record keeps of the Keychain items: never the value."""
    return [{"server": i.server, "key": i.key, "existed": i.existed} for i in items]


def _record(change: Change) -> dict:
    steps = []
    for step in change.steps:
        steps.append(
            {
                "client": step.client,
                "scope": str(step.scope),
                "name": step.name,
                "mechanism": step.mechanism,
                # Only masked: Undo needs the inverse command, never this one.
                "command": masked_command(step.command) if step.command else step.command,
                "undo_command": step.undo_command,
                "cwd": step.cwd,
                "restart_note": step.restart_note,
                "login_note": step.login_note,
                "shared_file": step.shared_file,
                "edit": _edit_record(step.edit),
                "gateway": _gateway_record(step.gateway),
                "copy": _copy_record(step.copy),
                "removal": _removal_record(step.removal),
                "keychain": _keychain_record(step.keychain),
                "reaches": step.reaches,
            }
        )
    return {
        "id": change.id,
        "action": change.action,
        "state": str(change.state),
        "error": change.error,
        "holds_secret": change.holds_secret,
        "target": change.target,
        "rows": change.rows,
        "steps": steps,
    }


def _from_record(record: dict) -> Change:
    steps = []
    for raw in record["steps"]:
        e = raw["edit"]
        edit = None
        if e is not None:
            edit = FileEdit(
                path=e["path"],
                fmt=e["fmt"],
                key=tuple(e["key"]),
                after=_decode(e["after"]),
                before=_decode(e["before"]),
                check=e["check"],
                before_hash=e["before_hash"],
                after_hash=e["after_hash"],
                backup_path=e["backup_path"],
                masked_diff=e["masked_diff"],
            )
        g = raw.get("gateway")
        gateway = GatewayEdit(**g) if g is not None else None
        c = raw.get("copy")
        copy = FolderCopy(**c) if c is not None else None
        r = raw.get("removal")
        removal = FolderRemoval(**r) if r is not None else None
        steps.append(
            Step(
                client=raw["client"],
                scope=Scope(raw["scope"]),
                name=raw["name"],
                edit=edit,
                gateway=gateway,
                copy=copy,
                removal=removal,
                mechanism=raw["mechanism"],
                command=raw["command"],
                undo_command=raw.get("undo_command"),
                cwd=raw["cwd"],
                restart_note=raw["restart_note"],
                login_note=raw["login_note"],
                shared_file=raw["shared_file"],
                keychain=[KeychainItem(**k) for k in raw.get("keychain") or []],
                reaches=raw.get("reaches"),
            )
        )
    return Change(
        action=record["action"],
        state=ChangeState(record["state"]),
        id=record["id"],
        steps=steps,
        error=record["error"],
        holds_secret=record.get("holds_secret", False),
        target=record.get("target"),
        rows=record.get("rows"),
    )


class Engine:
    def __init__(
        self,
        store: ChangeStore,
        run: Runner,
        on_write: Callable[[str, str | None], None] | None = None,
        gateway_clients: GatewayClients | None = None,
        *,
        roots: Roots | None = None,
        keychain_run: keychain.Runner | None = None,
    ) -> None:
        self.store = store
        self.run = run
        self.on_write = on_write or (lambda path, sha: None)
        self.gateway_clients = gateway_clients
        # The home folder and the folders a change may write in; None checks nothing.
        self.roots = roots
        # Runs the Keychain's `security`; None is the real one (the demo has a stand-in).
        self.keychain_run = keychain_run
        # Called as each step of an Apply or Undo is done: (change id, steps done, all steps,
        # the index in the change's steps of the one just done; None for Undo's last count).
        # The page shows "Applying 2 of 5" from it, and the tray the row of that step; it runs
        # in the worker thread.
        self.on_progress: Callable[[str, int, int, int | None], None] = (
            lambda change_id, done, total, step: None
        )
        self.changes: dict[str, Change] = {}
        for record in store.load():
            try:
                change = _from_record(record)
            except (KeyError, ValueError):
                continue
            self.changes[change.id] = change

    # Preview -----------------------------------------------------------------------------

    def preview(self, action: str, steps: list[Step]) -> Change:
        """Read each target, fill in the before state and a masked diff. Writes nothing.

        Several steps may edit one file (research R2 of feature 002), but never the same entry
        or an entry inside another one.
        """
        if not steps:
            raise ChangeRefusedError("Nothing to change.")
        for step in steps:
            if step.cwd:  # Apply must not follow a link changed after the review
                step.cwd = os.path.realpath(step.cwd)
        if self.roots is not None:
            self._check_places(steps, *self.roots())
        self._preview_gateway([s for s in steps if s.gateway is not None])
        self._preview_copies([s for s in steps if s.copy is not None])
        self._preview_removals([s for s in steps if s.removal is not None])
        self._preview_keychain(steps)
        targets: list[tuple[str, tuple]] = []
        for step in steps:
            edit = step.edit
            if edit is None:
                continue
            edit.path = os.path.realpath(edit.path)
            key = tuple(edit.key)
            for path, other in targets:
                if path == edit.path and (other[: len(key)] == key or key[: len(other)] == other):
                    raise ChangeRefusedError(f"{edit.path} would be edited twice in one change")
            targets.append((edit.path, key))
            data = _read(edit.path)
            if data is not None and os.stat(edit.path).st_nlink > 1:
                raise ChangeRefusedError(f"{edit.path} has a hard link; it is not changed")
            try:
                edit.before = _value(edit, data)
            except (UnrecognizedFormatError, UnicodeDecodeError) as error:
                raise ChangeRefusedError(f"{edit.path}: {error}") from None
            # A new value of a secret changes only the Keychain; the reference stays.
            same = edit.before == edit.after and not step.keychain
            if same or (edit.after is PRESENT and edit.before is not ABSENT):
                raise NothingToChangeError(edit.path, step.client)
            if edit.after is PRESENT and step.mechanism != CLIENT_CLI:
                raise ChangeRefusedError(
                    "only a client command can write an entry in its own shape"
                )
            edit.before_hash = _sha(data)
            edit.masked_diff = masked_diff(edit)
        change = Change(action=action, steps=steps)
        self.changes[change.id] = change
        return change

    def check(self, steps: list[Step]) -> None:
        """Preview the steps and forget them: raises as `preview` does. Writes nothing. The
        preview tray asks this before a change joins it."""
        change = self.preview("check", steps)
        del self.changes[change.id]

    def _check_places(self, steps: list[Step], home: Path, roots: list[Path]) -> None:
        """Refuse the change when a step writes, or runs a command, outside the roots."""
        stops = _stops(home, roots)
        for step in steps:
            written = [writable(p, home, roots) for p in _places(step)]
            ran = not step.cwd or _allowed(Path(step.cwd), roots, stops, folder=True)
            if not all(written) or not ran:
                raise ChangeRefusedError(OUTSIDE)

    def _client(self, gateway: GatewayEdit) -> AbstractContextManager:
        if self.gateway_clients is None:
            raise ChangeRefusedError("The gateway cannot be managed from here")
        return self.gateway_clients(gateway)

    def _preview_gateway(self, steps: list[Step]) -> None:
        """Read what the gateway holds; a name already there refuses the change."""
        if not steps:
            return
        gateway = steps[0].gateway
        assert gateway is not None
        try:
            with self._client(gateway) as client:
                held = {s["name"] for s in client.held()}
        except GatewayError as error:
            raise ChangeRefusedError(str(error)) from None
        seen: set[str] = set()
        for step in steps:
            g = step.gateway
            assert g is not None
            if g.gateway_id != gateway.gateway_id:
                raise ChangeRefusedError("One change can move servers into one gateway only")
            if g.name in held:
                raise ChangeRefusedError(
                    f"The gateway already has {g.name}. Remove the direct entry instead."
                )
            if g.name in seen:
                raise ChangeRefusedError(f"{g.name} would be added twice in one change")
            seen.add(g.name)
            shown = redact(g.server)[0]
            lines = json.dumps({g.name: shown}, indent=2, ensure_ascii=False).splitlines()
            g.masked_diff = f"{g.url}\n" + "\n".join(f"+{line}" for line in lines)

    def _security(self) -> keychain.Runner:
        """The stand-in when one was given, else the real `security`."""
        return self.keychain_run or keychain.run_security

    def _preview_keychain(self, steps: list[Step]) -> None:
        """Read whether each Keychain item is there already: Undo deletes only new ones."""
        try:
            for step in steps:
                for item in step.keychain:
                    item.existed = keychain.read(item.ref, run=self._security()) is not None
        except KeychainError as error:
            raise ChangeRefusedError(str(error)) from None

    def _preview_copies(self, steps: list[Step]) -> None:
        """Read each source folder; a target that already exists refuses the change."""
        seen: set[str] = set()
        for step in steps:
            copy = step.copy
            assert copy is not None
            copy.source = os.path.realpath(copy.source)
            if os.path.lexists(copy.target):
                raise ChangeRefusedError(f"{copy.target} already exists; nothing is copied")
            # Apply must not follow a link changed after the review.
            copy.target = os.path.realpath(copy.target)
            if copy.target in seen:
                raise ChangeRefusedError(f"{copy.target} would be written twice in one change")
            seen.add(copy.target)
            try:
                files = list_files(copy.source)
                copy.content_hash = digest(copy.source)
            except (CopyRefusedError, OSError) as error:
                raise ChangeRefusedError(f"{step.name}: {error}") from None
            if not files:
                raise ChangeRefusedError(f"{copy.source} holds no files")
            copy.masked_diff = "\n".join(f"+{f}" for f in files)

    def _preview_removals(self, steps: list[Step]) -> None:
        """Read each folder to remove. Only a real folder of regular files is removed."""
        seen: set[str] = set()
        for step in steps:
            removal = step.removal
            assert removal is not None
            if os.path.islink(removal.path):
                raise ChangeRefusedError(
                    f"{removal.path} is a link; Kitden removes only real folders"
                )
            removal.path = os.path.realpath(removal.path)
            if not os.path.isdir(removal.path):
                raise ChangeRefusedError(f"{removal.path} is not a folder")
            if removal.path in seen:
                raise ChangeRefusedError(f"{removal.path} would be removed twice in one change")
            seen.add(removal.path)
            try:
                files = list_files(removal.path)
                removal.content_hash = digest(removal.path)
            except (CopyRefusedError, OSError) as error:
                raise ChangeRefusedError(f"{step.name}: {error}") from None
            removal.masked_diff = "\n".join(f"-{f}" for f in files)

    def cancel(self, change_id: str) -> Change:
        change = self.changes[change_id]
        change.move_to(ChangeState.CANCELLED)
        return change

    # Apply -------------------------------------------------------------------------------

    def _stale(self, step: Step, data: bytes | None) -> str | None:
        edit = step.edit
        if edit.check == "file":
            ok = _sha(data) == edit.before_hash
        else:
            try:
                ok = _value(edit, data) == edit.before
            except (UnrecognizedFormatError, UnicodeDecodeError):
                ok = False
        return None if ok else f"{edit.path} changed since preview; review the change again"

    def _write(self, path: str, data: bytes | None) -> None:
        if data is None:
            Path(path).unlink(missing_ok=True)
        else:
            write_atomic(path, data)
        self.on_write(path, _sha(data))

    def _apply_step(self, step: Step, data: bytes | None) -> bytes | None:
        """Make the edit. Returns the exact bytes expected afterwards, when we know them."""
        edit = step.edit
        if step.mechanism == CLIENT_CLI:
            result = self.run(step.command or [], step.cwd)
            if result.returncode != 0:
                shown = " ".join((step.command or [])[:3])
                raise _ApplyError(f"`{shown}` failed: {result.output}")
            self.on_write(edit.path, _sha(_read(edit.path)))
            return None
        editor = EDITORS[edit.fmt]
        text = (data or b"").decode()
        if edit.after is ABSENT:
            new = editor.delete_value(text, edit.key)
        else:
            new = editor.set_value(text, edit.key, edit.after)
        self._write(edit.path, new.encode())
        return new.encode()

    def _put_entry_back(self, step: Step) -> None:
        """After an inverse command, set the entry back as it was before the change.

        Installing a removed plugin again turns it on; one that was off is set off again, so
        Undo leaves the file as it was. Only the entry is written.
        """
        edit = step.edit
        data = _read(edit.path)
        now = _value(edit, data)
        if edit.before is ABSENT or now is ABSENT or now == edit.before:
            return
        text = EDITORS[edit.fmt].set_value((data or b"").decode(), edit.key, edit.before)
        self._write(edit.path, text.encode())

    def _verify(self, step: Step, expected: Any, exact: bytes | None = None) -> None:
        data = _read(step.edit.path)
        if not _matches(step, _value(step.edit, data), expected):
            raise _ApplyError(f"{step.edit.path}: the entry did not read back as expected")
        if exact is not None and data != exact:
            raise _ApplyError(f"{step.edit.path}: other parts of the file changed during the write")

    def apply(self, change_id: str) -> Change:
        change = self.changes[change_id]
        try:
            return self._apply(change)
        finally:
            self._forget_secrets(change)  # the values are needed only until Apply ends

    def stale_reason(self, change_id: str) -> str | None:
        """Why Apply would stop as stale now, or None. Reads the targets and changes nothing;
        only a previewed change is checked."""
        change = self.changes[change_id]
        if change.state is not ChangeState.PREVIEWED:
            return None
        current = {s.edit.path: _read(s.edit.path) for s in change.steps if s.edit is not None}
        return self._first_stale(change, current)

    def _first_stale(self, change: Change, current: dict[str, bytes | None]) -> str | None:
        """The first file, folder to copy or folder to remove that changed since the preview.
        `current` holds each file's bytes as read now."""
        for step in change.steps:
            if step.edit is not None and (reason := self._stale(step, current[step.edit.path])):
                return reason
        for step in change.steps:
            if step.copy is not None and (reason := self._stale_copy(step)):
                return reason
        for step in change.steps:
            if step.removal is not None and (reason := self._stale_removal(step)):
                return reason
        return None

    def _apply(self, change: Change) -> Change:
        if change.state is not ChangeState.PREVIEWED:
            change.move_to(ChangeState.APPLYING)  # raises: only a previewed change applies
        file_steps = [s for s in change.steps if s.edit is not None]
        gateway_steps = [s for s in change.steps if s.gateway is not None]
        copy_steps = [s for s in change.steps if s.copy is not None]
        removal_steps = [s for s in change.steps if s.removal is not None]
        current = {step.edit.path: _read(step.edit.path) for step in file_steps}
        reason = self._first_stale(change, current)
        if reason:
            change.move_to(ChangeState.STALE)
            change.error = reason
            self._log(change)
            return change

        saved = self.store.backup(change.id, current)
        for step in file_steps:
            copy = saved[step.edit.path]
            step.edit.backup_path = str(copy) if copy else None
        self.store.prune()
        change.move_to(ChangeState.APPLYING)
        tick = self._counter(change)
        ran: list[Step] = []
        copied: list[Step] = []
        removed: list[Step] = []
        stored: list[KeychainItem] = []
        try:
            # The Keychain first: the settings file then names items that are there.
            self._store_secrets(change, stored)
            # The gateway side next: a server that cannot be added leaves the files alone.
            self._apply_gateway(gateway_steps, tick)
            for step in copy_steps:
                self._apply_copy(step, copied)
                tick(step)
            for step in removal_steps:
                self._apply_removal(change.id, step, removed)
                tick(step)
            # Steps on one file run in order, each on the result of the one before.
            working = dict(current)
            expected: dict[str, bytes | None] = {}
            for step in file_steps:
                path = step.edit.path
                result = self._apply_step(step, working[path])
                ran.append(step)
                working[path] = result if result is not None else _read(path)
                expected[path] = result
                tick(step)
            for step in file_steps:
                self._verify(step, step.edit.after, expected[step.edit.path])
        except (
            _ApplyError,
            CopyRefusedError,
            GatewayError,
            OSError,
            RefusedWriteError,
            UnrecognizedFormatError,
            KeychainError,
        ) as error:
            # A step with an inverse command is taken back by that command (an install leaves
            # more than the file behind); then every other file gets its original bytes.
            by_command = _command_paths(file_steps)
            lost = []
            for step in reversed(ran):
                if not _by_command(step):
                    continue
                if self.run(step.undo_command, step.cwd).returncode != 0:
                    shown = _shown(step.undo_command)
                    lost.append(f"`{shown}` failed; {step.name} was not put back.")
                    continue
                if step.edit.path not in by_command:
                    continue
                # A failure here must not stop the rest of the restore.
                try:
                    self._put_entry_back(step)
                except (OSError, RefusedWriteError, UnicodeDecodeError, UnrecognizedFormatError):
                    lost.append(f"{step.name} could not be set as it was in {step.edit.path}.")
            for path, data in current.items():
                if path not in by_command and _read(path) != data:
                    self._write(path, data)
            # A removed folder comes back from its backup. What a removal that stopped halfway
            # left is part of that backup, so it goes first.
            for step in reversed(removed):
                if not self._put_folder_back(step.removal):
                    lost.append(
                        f"{step.name} could not be put back; its backup is in "
                        f"{step.removal.backup_path}."
                    )
            for step in reversed(copied):
                with contextlib.suppress(OSError):
                    remove_folder(step.copy.target)
            self._remove_from_gateway(gateway_steps, best_effort=True)
            for item in reversed(stored):
                if item.existed:
                    # Its old value is recorded nowhere.
                    lost.append(f"{item.server}/{item.key} in your Keychain keeps the new value.")
                    continue
                try:
                    keychain.delete(item.ref, run=self._security())
                except KeychainError:
                    lost.append(f"{item.server}/{item.key} stays in your Keychain.")
            self._mark_secret(change, file_steps)
            change.move_to(ChangeState.RESTORED)
            if lost:
                change.error = f"{error} {' '.join(lost)}"
            else:
                change.error = f"{error} The original settings were restored."
            self._finish(change)
            return change

        for step in file_steps:
            step.edit.after_hash = _sha(_read(step.edit.path))
        self._mark_secret(change, file_steps)
        change.move_to(ChangeState.VERIFIED)
        self._finish(change)
        return change

    def _mark_secret(self, change: Change, file_steps: list[Step]) -> None:
        """Once every backup exists: whether a backup, or an entry the record keeps (an old
        or a new value), holds a secret."""
        change.holds_secret = self.store.backup_holds_secret(change.id) or any(
            holds_secret(s.edit.before) or holds_secret(s.edit.after) for s in file_steps
        )

    def _store_secrets(self, change: Change, stored: list[KeychainItem]) -> None:
        """Write each secret to the Keychain; `store` reads it back."""
        for step in change.steps:
            for item in step.keychain:
                stored.append(item)  # first: a write that fails halfway is taken back too
                keychain.store(item.server, item.key, item.value, run=self._security())

    @staticmethod
    def _forget_secrets(change: Change) -> None:
        """Clear the values held in memory."""
        for step in change.steps:
            for item in step.keychain:
                item.value = ""

    def _stale_copy(self, step: Step) -> str | None:
        copy = step.copy
        if os.path.lexists(copy.target):
            return f"{copy.target} appeared since preview; review the change again"
        try:
            same = digest(copy.source) == copy.content_hash
        except (CopyRefusedError, OSError):
            same = False
        return None if same else f"{copy.source} changed since preview; review the change again"

    def _apply_copy(self, step: Step, copied: list[Step]) -> None:
        """Copy the folder, then read the copy back: it must hash like the source.

        The step joins `copied`, what a failed change takes back, only once the folder is the
        one Kitden made: a folder that appeared before the copy is refused and left alone.
        """
        copy = step.copy
        copy_folder(copy.source, copy.target)
        copied.append(step)
        if digest(copy.target) != copy.content_hash:
            raise _ApplyError(f"{copy.target}: the copy did not read back like the source")

    def _stale_removal(self, step: Step) -> str | None:
        removal = step.removal
        if not os.path.lexists(removal.path):
            return f"{removal.path} is gone since preview; review the change again"
        try:
            same = not os.path.islink(removal.path) and digest(removal.path) == removal.content_hash
        except (CopyRefusedError, OSError):
            same = False
        return None if same else f"{removal.path} changed since preview; review the change again"

    def _apply_removal(self, change_id: str, step: Step, removed: list[Step]) -> None:
        """Copy the folder into the change's backup folder, then remove it.

        The step joins `removed`, what a failed change puts back, once the backup is made.
        """
        removal = step.removal
        removal.backup_path = str(self.store.backup_folder(change_id, removal.path))
        if digest(removal.backup_path) != removal.content_hash:
            raise _ApplyError(f"{removal.path}: the backup did not read back like the folder")
        removed.append(step)
        remove_folder(removal.path)
        if os.path.lexists(removal.path):
            raise _ApplyError(f"{removal.path}: the folder is still there after removing it")

    def _put_folder_back(self, removal: FolderRemoval) -> bool:
        """Copy a removed folder back from its backup after a failed Apply. False when it
        could not be put back."""
        try:
            if os.path.islink(removal.path):
                return False  # not what the removal left
            if os.path.lexists(removal.path):
                if digest(removal.path) == removal.content_hash:
                    return True
                remove_folder(removal.path)
            copy_folder(removal.backup_path, removal.path)
            return digest(removal.path) == removal.content_hash
        except (CopyRefusedError, OSError):
            return False

    def _counter(self, change: Change) -> Callable[[Step], None]:
        """A function that counts one more step done and tells `on_progress` which one."""
        done = 0
        total = len(change.steps)
        # By identity: two steps may be equal as values.
        index = {id(step): i for i, step in enumerate(change.steps)}

        def tick(step: Step) -> None:
            nonlocal done
            done = min(done + 1, total)
            self.on_progress(change.id, done, total, index.get(id(step)))

        return tick

    def _apply_gateway(
        self, steps: list[Step], tick: Callable[[Step], None] = lambda step: None
    ) -> None:
        """Add each server, then read the list back: every name must be there."""
        if not steps:
            return
        with self._client(steps[0].gateway) as client:
            for step in steps:
                g = step.gateway
                g.server_uuid = client.add(g.name, g.server)
                tick(step)
            held = {s["name"] for s in client.held()}
        missing = [s.gateway.name for s in steps if s.gateway.name not in held]
        if missing:
            raise _ApplyError(f"the gateway did not list {', '.join(missing)} after adding it")

    def _remove_from_gateway(
        self,
        steps: list[Step],
        best_effort: bool = False,
        tick: Callable[[Step], None] = lambda step: None,
    ) -> list[str]:
        """Remove the added servers, last first. Returns the names that were already gone."""
        added = [s for s in reversed(steps) if s.gateway and s.gateway.server_uuid]
        if not added:
            return []
        gone = []
        try:
            with self._client(added[0].gateway) as client:
                for step in added:
                    if not client.remove(step.gateway.server_uuid):
                        gone.append(step.gateway.name)
                    tick(step)
        except GatewayError:
            if not best_effort:
                raise
        return gone

    # Undo --------------------------------------------------------------------------------

    def undo(self, change_id: str) -> Change:
        change = self.changes[change_id]
        if change.state is not ChangeState.VERIFIED:
            change.move_to(ChangeState.UNDONE)  # raises: only a verified change can be undone
        by_command = _command_paths(change.steps)
        by_path: dict[str, list[Step]] = {}  # files that get planned bytes, after any command
        for step in change.steps:
            if step.edit is not None and step.edit.path not in by_command:
                by_path.setdefault(step.edit.path, []).append(step)
        plans: dict[str, bytes | None] = {}
        for path, steps in by_path.items():
            data = _read(path)
            first = steps[0].edit
            if _sha(data) == first.after_hash:
                plans[path] = Path(first.backup_path).read_bytes() if first.backup_path else None
                continue
            restored = _undo_entries(steps, data)
            if restored is None:
                change.move_to(ChangeState.UNDO_BLOCKED)
                change.error = (
                    f"{path} changed after the change was applied; undo would overwrite that, "
                    "so nothing was changed"
                )
                self._finish(change)
                return change
            plans[path] = restored

        copies = [s for s in change.steps if s.copy is not None]
        for step in copies:
            copy = step.copy
            if not os.path.lexists(copy.target):
                continue  # already gone; nothing to remove
            try:
                same = digest(copy.target) == copy.content_hash
            except (CopyRefusedError, OSError):
                same = False
            if not same:
                change.move_to(ChangeState.UNDO_BLOCKED)
                change.error = (
                    f"{copy.target} changed after the change was applied; undo would delete "
                    "that, so nothing was changed"
                )
                self._finish(change)
                return change

        removals = [s for s in change.steps if s.removal is not None]
        for step in removals:
            removal = step.removal
            if os.path.lexists(removal.path):
                reason = f"{removal.path} is back; undo would overwrite it, so nothing was changed"
            elif not removal.backup_path or not os.path.isdir(removal.backup_path):
                reason = f"the backup of {removal.path} is gone, so nothing was changed"
            else:
                continue
            change.move_to(ChangeState.UNDO_BLOCKED)
            change.error = reason
            self._finish(change)
            return change

        # The Keychain is checked first: if it cannot be reached, nothing else changes. The
        # items the change created are deleted last, once the files read back as before, so a
        # blocked Undo leaves no setting naming a deleted item. An item the change only updated
        # keeps its new value: the old one is recorded nowhere.
        items = [i for s in change.steps for i in s.keychain]
        created = [i for i in items if not i.existed]
        try:
            for item in created:
                keychain.read(item.ref, run=self._security())
        except KeychainError:
            change.move_to(ChangeState.UNDO_BLOCKED)
            change.error = "Kitden could not reach the Keychain; nothing was changed."
            self._finish(change)
            return change
        kept = [
            f"{i.server}/{i.key} in your Keychain keeps the new value." for i in items if i.existed
        ]

        # The gateway side goes next: if it cannot be reached, the files stay as they are.
        tick = self._counter(change)
        try:
            gone = self._remove_from_gateway(
                [s for s in change.steps if s.gateway is not None], tick=tick
            )
        except GatewayError as error:
            change.move_to(ChangeState.UNDO_BLOCKED)
            change.error = f"{error}; the client files were not changed"
            self._finish(change)
            return change
        for step in reversed(copies):
            remove_folder(step.copy.target)
            tick(step)
        for step in reversed(removals):
            copy_folder(step.removal.backup_path, step.removal.path)
            tick(step)
        # Inverse commands, last step first. An entry already gone needs no command. A file
        # that also has direct edits gets its planned bytes afterwards.
        for step in reversed(change.steps):
            if step.edit is None or not _by_command(step):
                continue
            if _value(step.edit, _read(step.edit.path)) is ABSENT and step.edit.before is ABSENT:
                continue
            result = self.run(step.undo_command, step.cwd)
            if result.returncode != 0:
                change.move_to(ChangeState.UNDO_BLOCKED)
                change.error = f"`{_shown(step.undo_command)}` failed: {result.output}"
                self._finish(change)
                return change
            if step.edit.path in by_command:
                try:
                    self._put_entry_back(step)
                except (OSError, RefusedWriteError, UnicodeDecodeError, UnrecognizedFormatError):
                    change.move_to(ChangeState.UNDO_BLOCKED)
                    change.error = (
                        f"{step.name} is back, but {step.edit.path} could not be set as it was "
                        "before. Check it by hand."
                    )
                    self._finish(change)
                    return change
            self.on_write(step.edit.path, _sha(_read(step.edit.path)))
            tick(step)
        for path, data in plans.items():
            self._write(path, data)
        for step in change.steps:
            if step.edit and _value(step.edit, _read(step.edit.path)) != step.edit.before:
                raise RuntimeError(f"{step.edit.path}: undo did not read back as expected")
            if step.copy and os.path.lexists(step.copy.target):
                raise RuntimeError(f"{step.copy.target}: undo did not remove the copy")
            if step.removal and digest(step.removal.path) != step.removal.content_hash:
                raise RuntimeError(f"{step.removal.path}: undo did not copy the folder back")
        for item in reversed(created):
            try:
                keychain.delete(item.ref, run=self._security())
            except KeychainError:
                kept.append(f"{item.server}/{item.key} stays in your Keychain.")
        self.on_progress(change.id, len(change.steps), len(change.steps), None)
        change.move_to(ChangeState.UNDONE)
        notes = [f"{', '.join(gone)} had already been removed from the gateway."] if gone else []
        notes += kept
        if notes:
            change.error = " ".join(notes)
        self._finish(change)
        return change

    # Records -----------------------------------------------------------------------------

    def _log(self, change: Change) -> None:
        self.store.log(
            {
                "id": change.id,
                "time": datetime.now(UTC).isoformat(timespec="seconds"),
                "action": change.action,
                "state": str(change.state),
                "error": change.error,
                "holds_secret": change.holds_secret,
                "target": change.target,
                "rows": change.rows,
                "steps": [
                    {
                        "client": s.client,
                        "scope": str(s.scope),
                        "name": s.name,
                        "path": step_path(s),
                        "mechanism": s.mechanism,
                        "reaches": step_readers(s),
                        "keeps": s.removal.keeps if s.removal else None,
                        "restart_note": s.restart_note,
                        "login_note": s.login_note,
                        "before_hash": s.edit.before_hash if s.edit else None,
                        "after_hash": s.edit.after_hash if s.edit else None,
                        "keychain": _keychain_record(s.keychain),
                    }
                    for s in change.steps
                ],
            }
        )

    def _finish(self, change: Change) -> None:
        self.store.save(change.id, _record(change))
        self._log(change)
