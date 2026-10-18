"""The change engine: preview, stale check, back up, apply, verify, restore, undo (T042).

States follow data-model.md. Research R7 has the safe write pattern.

Two kinds of checks:
- "file": the whole file must be unchanged since preview (before apply) or since apply (before
  undo). Used for files that only people and our tool edit.
- "entry": only the edited entry is compared. Used for `~/.claude.json`, which Claude Code
  rewrites during normal use. Undo then restores just that entry, unless the whole file is still
  as we left it, in which case the backup bytes are restored exactly.
"""

import difflib
import hashlib
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import tomlkit

from kitden.changes import json_splice, toml_edit
from kitden.changes.atomic import RefusedWriteError, write_atomic
from kitden.changes.backup import ChangeStore
from kitden.changes.client_cli import CommandResult
from kitden.changes.json_splice import ABSENT, UnrecognizedFormatError
from kitden.model import Change, ChangeState, FileEdit, Scope, Step
from kitden.redact import redact

EDITORS = {"json": json_splice, "toml": toml_edit}
CLIENT_CLI = "client_cli"
FILE_EDIT = "format_preserving_edit"

Runner = Callable[[list[str], str | None], CommandResult]


class ChangeRefusedError(ValueError):
    """The change cannot be previewed (unknown format, hard link, nothing to change)."""


class _ApplyError(Exception):
    pass


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


def _encode(value: Any) -> dict:
    return {"absent": True} if value is ABSENT else {"value": value}


def _decode(record: dict) -> Any:
    return ABSENT if record.get("absent") else record.get("value")


def _record(change: Change) -> dict:
    steps = []
    for step in change.steps:
        edit = step.edit
        steps.append(
            {
                "client": step.client,
                "scope": str(step.scope),
                "name": step.name,
                "mechanism": step.mechanism,
                "command": step.command,
                "cwd": step.cwd,
                "restart_note": step.restart_note,
                "login_note": step.login_note,
                "shared_file": step.shared_file,
                "edit": {
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
                },
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
        steps.append(
            Step(
                client=raw["client"],
                scope=Scope(raw["scope"]),
                name=raw["name"],
                edit=edit,
                mechanism=raw["mechanism"],
                command=raw["command"],
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
    ) -> None:
        self.store = store
        self.run = run
        self.on_write = on_write or (lambda path, sha: None)
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
        targets: list[tuple[str, tuple]] = []
        for step in steps:
            edit = step.edit
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
            if edit.before == edit.after:
                raise ChangeRefusedError(f"nothing to change in {edit.path}")
            edit.before_hash = _sha(data)
            edit.masked_diff = masked_diff(edit)
        change = Change(action=action, steps=steps)
        self.changes[change.id] = change
        return change

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
        current = {step.edit.path: _read(step.edit.path) for step in change.steps}
        for step in change.steps:
            reason = self._stale(step, current[step.edit.path])
            if reason:
                change.move_to(ChangeState.STALE)
                change.error = reason
                self._log(change)
                return change

        saved = self.store.backup(change.id, current)
        for step in change.steps:
            copy = saved[step.edit.path]
            step.edit.backup_path = str(copy) if copy else None
        self.store.prune()
        change.move_to(ChangeState.APPLYING)
        try:
            # Steps on one file run in order, each on the result of the one before.
            working = dict(current)
            expected: dict[str, bytes | None] = {}
            for step in change.steps:
                path = step.edit.path
                result = self._apply_step(step, working[path])
                working[path] = result if result is not None else _read(path)
                expected[path] = result
            for step in change.steps:
                self._verify(step, step.edit.after, expected[step.edit.path])
        except (_ApplyError, OSError, RefusedWriteError, UnrecognizedFormatError) as error:
            for path, data in current.items():
                if _read(path) != data:
                    self._write(path, data)
            change.move_to(ChangeState.RESTORED)
            change.error = f"{error} The original settings were restored."
            self._finish(change)
            return change

        for step in change.steps:
            step.edit.after_hash = _sha(_read(step.edit.path))
        change.move_to(ChangeState.VERIFIED)
        self._finish(change)
        return change

    # Undo --------------------------------------------------------------------------------

    def undo(self, change_id: str) -> Change:
        change = self.changes[change_id]
        if change.state is not ChangeState.VERIFIED:
            change.move_to(ChangeState.UNDONE)  # raises: only a verified change can be undone
        by_path: dict[str, list[Step]] = {}
        for step in change.steps:
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

        for path, data in plans.items():
            self._write(path, data)
        for step in change.steps:
            if _value(step.edit, _read(step.edit.path)) != step.edit.before:
                raise RuntimeError(f"{step.edit.path}: undo did not read back as expected")
        change.move_to(ChangeState.UNDONE)
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
                        "path": s.edit.path,
                        "mechanism": s.mechanism,
                        "before_hash": s.edit.before_hash,
                        "after_hash": s.edit.after_hash,
                    }
                    for s in change.steps
                ],
            }
        )

    def _finish(self, change: Change) -> None:
        self.store.save(change.id, _record(change))
        self._log(change)
