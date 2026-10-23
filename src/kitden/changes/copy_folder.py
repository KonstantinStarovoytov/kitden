"""Copy a skill folder into a client's skills folder, and take the copy back.

Only regular files are copied. A link or a special file stops the change before anything is
written, so nothing outside the source folder is ever read, and nothing outside the target
folder is ever written. Nothing in the copied files is run. Finder's .DS_Store files are not
part of a skill: they are not copied or compared.
"""

import hashlib
import os
import shutil
from pathlib import Path

FINDER_FILE = ".DS_Store"


class CopyRefusedError(ValueError):
    """The folder cannot be copied as it is."""


def list_files(folder: Path | str) -> list[str]:
    """Relative paths of every file under `folder`, sorted, but Finder's .DS_Store. Refuses
    links and special files."""
    root = Path(folder)
    if root.is_symlink() or not root.is_dir():
        raise CopyRefusedError(f"{root} is not a folder")
    files = []
    for path in sorted(root.rglob("*")):
        if path.name == FINDER_FILE:
            continue
        if path.is_symlink():
            raise CopyRefusedError(f"{path.relative_to(root)} is a link; links are not copied")
        if path.is_dir():
            continue
        if not path.is_file():
            raise CopyRefusedError(f"{path.relative_to(root)} is not a regular file")
        files.append(path.relative_to(root).as_posix())
    return files


def digest(folder: Path | str) -> str:
    """One hash over every file's path and bytes, so a changed copy can be told apart."""
    root = Path(folder)
    sha = hashlib.sha256()
    for rel in list_files(root):
        sha.update(rel.encode())
        sha.update(b"\0")
        sha.update((root / rel).read_bytes())
        sha.update(b"\0")
    return sha.hexdigest()


def copy_folder(source: Path | str, target: Path | str) -> None:
    """Copy every file, keeping its mode. The target folder must not exist yet: one that
    appears meanwhile is refused and left alone. A copy that fails partway is removed."""
    src = Path(source)
    dst = Path(target)
    if dst.exists() or dst.is_symlink():
        raise CopyRefusedError(f"{dst} already exists")
    files = list_files(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.mkdir()  # fails if the folder appeared meanwhile; nothing is made then
    try:
        for rel in files:
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / rel, dst / rel)
            shutil.copymode(src / rel, dst / rel)
    except Exception:
        remove_folder(dst)  # this call made it
        raise


def remove_folder(target: Path | str) -> None:
    """Remove a copied folder. Nothing a link points to is touched."""
    dst = Path(target)
    if dst.is_symlink():
        dst.unlink()
    elif os.path.lexists(dst):
        shutil.rmtree(dst)
