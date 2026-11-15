"""Kitden's own data folder: where it is, the one-time copy from the working version's folder,
and removing what older versions kept there that Kitden no longer uses."""

import contextlib
import json
import shutil
import tempfile
from pathlib import Path

from kitden import system

OLD_DATA_DIR = "Library/Application Support/agentsetup"  # the working name, macOS only
OLD_SETTINGS_FILE = "settings.json"  # the outside gateways older versions kept


def data_dir(home: Path) -> Path:
    """Kitden's own folder: see kitden.system for where each system keeps it."""
    return system.data_dir(home)


def private_data_dir(home: Path) -> Path:
    """The data folder, made when missing, readable only by its owner."""
    folder = data_dir(home)
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)
    return folder


COPIED = ".copied-from-agentsetup"  # written last; without it the copy is not finished


def ensure_data_folder(home: Path) -> str | None:
    """Copy the working version's data folder once (feature 002, research R7). Returns a note.

    The old folder is never changed, so an old page that still runs keeps working. Each copy goes
    to its own temporary folder, so two commands starting at once cannot spoil each other; a copy
    that failed or was cut short is tried again on the next start. Backups are referenced by
    absolute paths, so the copy points them at the new folder.
    """
    new, old = data_dir(home), Path(home) / OLD_DATA_DIR
    if system.SYSTEM != "mac" or not old.is_dir():
        return None
    if (new / COPIED).exists():
        return f"Kitden uses {new}; the old folder {old} is not used."
    new.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(dir=new.parent, prefix=f"{new.name}.copying-"))
    try:
        copy = temp / "data"
        shutil.copytree(old, copy, symlinks=True)
        for record in copy.glob("changes/*/change.json"):
            _point_backups_at(record, old, new)
        new.mkdir(mode=0o700, exist_ok=True)
        new.chmod(0o700)
        for entry in copy.iterdir():  # whole entries move at once; ones already there stay
            with contextlib.suppress(OSError):
                entry.rename(new / entry.name)
        (new / COPIED).write_text(f"{old}\n")
    except (OSError, ValueError, shutil.Error) as error:
        reason = error.args[0] if isinstance(error, shutil.Error) and error.args else error
        if isinstance(reason, list):
            reason = f"{len(reason)} files could not be read"
        return f"Could not copy {old} to {new}: {reason}. Nothing was deleted."
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return f"Copied {old} to {new}. The old folder was left as it is and is no longer used."


def _point_backups_at(record: Path, old: Path, new: Path) -> None:
    """Point one change record's backups at the new folder. Unreadable records stay as they are."""
    try:
        data = json.loads(record.read_bytes())
        prefix = f"{old}/"
        for step in data.get("steps", []):
            edit = step.get("edit", {})
            path = edit.get("backup_path")
            if isinstance(path, str) and path.startswith(prefix):
                edit["backup_path"] = f"{new}/{path[len(prefix) :]}"
    except (ValueError, AttributeError):
        return
    record.write_text(json.dumps(data, indent=2))


def forget_gateways(home: Path) -> None:
    """Delete the list of outside gateways that older versions kept. Kitden works with its own
    gateway only now, and this file held nothing else."""
    with contextlib.suppress(OSError):
        (data_dir(home) / OLD_SETTINGS_FILE).unlink()
