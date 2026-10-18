"""Backups and the change log (research R7, FR-017, FR-022).

Folders are 0700 and files 0600. A backup holds the original bytes, which may contain secrets;
the manifest and the log never do. A backup is removed only when it is older than 30 days and not
one of the newest 100 changes.
"""

import hashlib
import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from kitden.redact import redact, redact_text

KEEP_DAYS = 30
KEEP_COUNT = 100


def _private_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)


def _write_private(path: Path, data: bytes, append: bool = False) -> None:
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, data)
    finally:
        os.close(fd)


def _hide_text(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: _hide_text(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_hide_text(v) for v in value]
    return value


class ChangeStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.folder = self.root / "changes"
        self.log_path = self.root / "changes.log"

    def _change_folder(self, change_id: str) -> Path:
        for path in (self.root, self.folder, self.folder / change_id):
            _private_folder(path)
        return self.folder / change_id

    def backup(self, change_id: str, files: dict[str, bytes | None]) -> dict[str, Path | None]:
        """Save the original bytes of each file (None = the file did not exist)."""
        folder = self._change_folder(change_id)
        saved: dict[str, Path | None] = {}
        manifest = []
        for index, (path, data) in enumerate(files.items()):
            entry: dict[str, Any] = {"path": path, "existed": data is not None}
            saved[path] = None
            if data is not None:
                copy = folder / f"{index}-{Path(path).name}"
                _write_private(copy, data)
                saved[path] = copy
                entry["sha256"] = hashlib.sha256(data).hexdigest()
            manifest.append(entry)
        record = {"change": change_id, "files": manifest}
        _write_private(folder / "manifest.json", json.dumps(record, indent=2).encode())
        return saved

    def save(self, change_id: str, record: dict) -> None:
        """Keep what undo needs. Lives next to the backup and is just as private."""
        folder = self._change_folder(change_id)
        _write_private(folder / "change.json", json.dumps(record, indent=2).encode())

    def load(self) -> list[dict]:
        records = []
        for path in sorted(self.folder.glob("*/change.json")) if self.folder.is_dir() else []:
            try:
                records.append(json.loads(path.read_text()))
            except (OSError, ValueError):
                continue
        return records

    def log(self, entry: dict) -> None:
        _private_folder(self.root)
        line = json.dumps(_hide_text(redact(entry)[0]), ensure_ascii=False)
        _write_private(self.log_path, (line + "\n").encode(), append=True)

    def entries(self) -> list[dict]:
        """Change log entries, newest first."""
        if not self.log_path.is_file():
            return []
        lines = self.log_path.read_text().splitlines()
        return [json.loads(line) for line in reversed(lines) if line.strip()]

    def prune(self, now: datetime | None = None) -> None:
        if not self.folder.is_dir():
            return
        cutoff = (now or datetime.now(UTC)) - timedelta(days=KEEP_DAYS)
        folders = sorted(p for p in self.folder.iterdir() if p.is_dir())
        for folder in folders[:-KEEP_COUNT]:
            try:
                made = datetime.strptime(folder.name[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
            except ValueError:
                continue
            if made < cutoff:
                shutil.rmtree(folder)
