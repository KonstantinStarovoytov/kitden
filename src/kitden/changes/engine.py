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
from typing import Any

import tomlkit

from kitden.changes import json_splice, toml_edit
from kitden.changes.atomic import RefusedWriteError, write_atomic
from kitden.changes.backup import ChangeStore
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
from kitden.model import (
    Change,
    ChangeState,
    FileEdit,
    FolderCopy,
    FolderRemoval,
    GatewayEdit,
    Scope,
    Step,
)
from kitden.redact import redact

EDITORS = {"json": json_splice, "toml": toml_edit}
CLIENT_CLI = "client_cli"
FILE_EDIT = "format_preserving_edit"
GATEWAY_API = "gateway_api"  # a step that adds a server to a gateway (feature 006)
# A step that copies a skill folder has mechanism model.COPY_FOLDER; one that removes a skill
# folder has model.REMOVE_FOLDER.

Runner = Callable[[list[str], str | None], CommandResult]
# Opens a signed-in client for the gateway a step names; used as a context manager.
GatewayClients = Callable[[GatewayEdit], AbstractContextManager]


class ChangeRefusedError(ValueError):
    """The change cannot be previewed (unknown format, hard link, nothing to change)."""


class NothingToChangeError(ChangeRefusedError):
    """The entry is already as the change would leave it; `client` is whose file it is."""

    def __init__(self, path: str, client: str) -> None:
        super().__init__(f"nothing to change in {path}")
        self.client = client


class _ApplyError(Exception):
    pass


def _step_path(step: Step) -> str | None:
    """Where a step writes: the file, the gateway address, the copied or the removed folder."""
    if step.edit is not None:
        return step.edit.path
    if step.gateway is not None:
        return step.gateway.url
    if step.removal is not None:
        return step.removal.path
    return step.copy.target if step.copy is not None else None


def _readers(step: Step) -> list[str] | None:
    """The clients that read a copied or removed folder; None for other steps."""
    if step.copy is not None:
        return step.copy.readers
    return step.removal.readers if step.removal is not None else None


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
        nested: Any = shown
        for key in reversed(edit.key):
            nested = {key: nested}
        return tomlkit.dumps(nested).strip().splitlines()
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


def _command_paths(steps: list[Step]) -> set[str]:
    """Files whose every step is taken back by an inverse command, not by restoring bytes."""
    paths: dict[str, bool] = {}
    for step in steps:
        if step.edit is not None:
            ok = step.mechanism == CLIENT_CLI and bool(step.undo_command)
            paths[step.edit.path] = paths.get(step.edit.path, True) and ok
    return {path for path, ok in paths.items() if ok}


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


def _record(change: Change) -> dict:
    steps = []
    for step in change.steps:
        steps.append(
            {
                "client": step.client,
                "scope": str(step.scope),
                "name": step.name,
                "mechanism": step.mechanism,
                "command": step.command,
                "undo_command": step.undo_command,
                "cwd": step.cwd,
                "restart_note": step.restart_note,
                "login_note": step.login_note,
                "shared_file": step.shared_file,
                "edit": _edit_record(step.edit),
                "gateway": _gateway_record(step.gateway),
                "copy": _copy_record(step.copy),
                "removal": _removal_record(step.removal),
            }
        )
    return {
        "id": change.id,
        "action": change.action,
        "state": str(change.state),
        "error": change.error,
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
            )
        )
    return Change(
        action=record["action"],
        state=ChangeState(record["state"]),
        id=record["id"],
        steps=steps,
        error=record["error"],
    )


class Engine:
    def __init__(
        self,
        store: ChangeStore,
        run: Runner,
        on_write: Callable[[str, str | None], None] | None = None,
        gateway_clients: GatewayClients | None = None,
    ) -> None:
        self.store = store
        self.run = run
        self.on_write = on_write or (lambda path, sha: None)
        self.gateway_clients = gateway_clients
        # Called as each step of an Apply or Undo is done: (change id, steps done, all steps).
        # The page shows "Applying 2 of 5" from it; it runs in the worker thread.
        self.on_progress: Callable[[str, int, int], None] = lambda change_id, done, total: None
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
        self._preview_gateway([s for s in steps if s.gateway is not None])
        self._preview_copies([s for s in steps if s.copy is not None])
        self._preview_removals([s for s in steps if s.removal is not None])
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
            if edit.before == edit.after or (edit.after is PRESENT and edit.before is not ABSENT):
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

    def _preview_copies(self, steps: list[Step]) -> None:
        """Read each source folder; a target that already exists refuses the change."""
        seen: set[str] = set()
        for step in steps:
            copy = step.copy
            assert copy is not None
            copy.source = os.path.realpath(copy.source)
            if os.path.lexists(copy.target):
                raise ChangeRefusedError(f"{copy.target} already exists; nothing is copied")
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
        if change.state is not ChangeState.PREVIEWED:
            change.move_to(ChangeState.APPLYING)  # raises: only a previewed change applies
        file_steps = [s for s in change.steps if s.edit is not None]
        gateway_steps = [s for s in change.steps if s.gateway is not None]
        copy_steps = [s for s in change.steps if s.copy is not None]
        removal_steps = [s for s in change.steps if s.removal is not None]
        current = {step.edit.path: _read(step.edit.path) for step in file_steps}
        reasons = [self._stale(s, current[s.edit.path]) for s in file_steps]
        reasons += [self._stale_copy(s) for s in copy_steps]
        reasons += [self._stale_removal(s) for s in removal_steps]
        for reason in reasons:
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
        try:
            # The gateway side first: a server that cannot be added leaves the files alone.
            self._apply_gateway(gateway_steps, tick)
            for step in copy_steps:
                self._apply_copy(step, copied)
                tick()
            for step in removal_steps:
                self._apply_removal(change.id, step, removed)
                tick()
            # Steps on one file run in order, each on the result of the one before.
            working = dict(current)
            expected: dict[str, bytes | None] = {}
            for step in file_steps:
                path = step.edit.path
                result = self._apply_step(step, working[path])
                ran.append(step)
                working[path] = result if result is not None else _read(path)
                expected[path] = result
                tick()
            for step in file_steps:
                self._verify(step, step.edit.after, expected[step.edit.path])
        except (
            _ApplyError,
            CopyRefusedError,
            GatewayError,
            OSError,
            RefusedWriteError,
            UnrecognizedFormatError,
        ) as error:
            # A step with an inverse command is taken back by that command (an install leaves
            # more than the file behind); every other file gets its original bytes.
            by_command = _command_paths(file_steps)
            for step in reversed(ran):
                if step.edit.path in by_command:
                    if self.run(step.undo_command, step.cwd).returncode != 0:
                        continue
                    # A failure here must not stop the rest of the restore.
                    with contextlib.suppress(
                        OSError, RefusedWriteError, UnicodeDecodeError, UnrecognizedFormatError
                    ):
                        self._put_entry_back(step)
            for path, data in current.items():
                if path not in by_command and _read(path) != data:
                    self._write(path, data)
            # A removed folder comes back from its backup, unless something is at the path.
            for step in reversed(removed):
                removal = step.removal
                with contextlib.suppress(CopyRefusedError, OSError):
                    if not os.path.lexists(removal.path):
                        copy_folder(removal.backup_path, removal.path)
            for step in reversed(copied):
                with contextlib.suppress(OSError):
                    remove_folder(step.copy.target)
            self._remove_from_gateway(gateway_steps, best_effort=True)
            change.move_to(ChangeState.RESTORED)
            change.error = f"{error} The original settings were restored."
            self._finish(change)
            return change

        for step in file_steps:
            step.edit.after_hash = _sha(_read(step.edit.path))
        change.move_to(ChangeState.VERIFIED)
        self._finish(change)
        return change

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
        removed.append(step)
        remove_folder(removal.path)
        if os.path.lexists(removal.path):
            raise _ApplyError(f"{removal.path}: the folder is still there after removing it")

    def _counter(self, change: Change) -> Callable[[], None]:
        """A function that counts one more step done and tells `on_progress`."""
        done = 0
        total = len(change.steps)

        def tick() -> None:
            nonlocal done
            done = min(done + 1, total)
            self.on_progress(change.id, done, total)

        return tick

    def _apply_gateway(self, steps: list[Step], tick: Callable[[], None] = lambda: None) -> None:
        """Add each server, then read the list back: every name must be there."""
        if not steps:
            return
        with self._client(steps[0].gateway) as client:
            for step in steps:
                g = step.gateway
                g.server_uuid = client.add(g.name, g.server)
                tick()
            held = {s["name"] for s in client.held()}
        missing = [s.gateway.name for s in steps if s.gateway.name not in held]
        if missing:
            raise _ApplyError(f"the gateway did not list {', '.join(missing)} after adding it")

    def _remove_from_gateway(
        self,
        steps: list[Step],
        best_effort: bool = False,
        tick: Callable[[], None] = lambda: None,
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
                    tick()
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
        by_path: dict[str, list[Step]] = {}
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

        # The gateway side goes first: if it cannot be reached, the files stay as they are.
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
            tick()
        for step in reversed(removals):
            copy_folder(step.removal.backup_path, step.removal.path)
            tick()
        # Inverse commands, last step first. An entry already gone needs no command.
        for step in reversed(change.steps):
            if step.edit is None or step.edit.path not in by_command:
                continue
            if _value(step.edit, _read(step.edit.path)) is ABSENT and step.edit.before is ABSENT:
                continue
            result = self.run(step.undo_command, step.cwd)
            if result.returncode != 0:
                change.move_to(ChangeState.UNDO_BLOCKED)
                shown = " ".join(step.undo_command[:4])
                change.error = f"`{shown}` failed: {result.output}"
                self._finish(change)
                return change
            self._put_entry_back(step)
            self.on_write(step.edit.path, _sha(_read(step.edit.path)))
            tick()
        for path, data in plans.items():
            self._write(path, data)
        for step in change.steps:
            if step.edit and _value(step.edit, _read(step.edit.path)) != step.edit.before:
                raise RuntimeError(f"{step.edit.path}: undo did not read back as expected")
            if step.copy and os.path.lexists(step.copy.target):
                raise RuntimeError(f"{step.copy.target}: undo did not remove the copy")
            if step.removal and digest(step.removal.path) != step.removal.content_hash:
                raise RuntimeError(f"{step.removal.path}: undo did not copy the folder back")
        self.on_progress(change.id, len(change.steps), len(change.steps))
        change.move_to(ChangeState.UNDONE)
        if gone:
            change.error = f"{', '.join(gone)} had already been removed from the gateway"
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
                "steps": [
                    {
                        "client": s.client,
                        "scope": str(s.scope),
                        "name": s.name,
                        "path": _step_path(s),
                        "mechanism": s.mechanism,
                        "reaches": _readers(s),
                        "restart_note": s.restart_note,
                        "login_note": s.login_note,
                        "before_hash": s.edit.before_hash if s.edit else None,
                        "after_hash": s.edit.after_hash if s.edit else None,
                    }
                    for s in change.steps
                ],
            }
        )

    def _finish(self, change: Change) -> None:
        self.store.save(change.id, _record(change))
        self._log(change)
