"""Write a file so that readers see either the old bytes or the new bytes, never a mix.

Research R7: resolve symlinks, refuse hard links, temp file in the same folder, keep the mode,
full fsync on macOS, then rename over the target.
"""

import contextlib
import fcntl
import os
import secrets
import stat
from pathlib import Path

NEW_FILE_MODE = 0o600


class RefusedWriteError(Exception):
    """The file must not be written this way."""


def _full_fsync(fd: int) -> None:
    # On macOS plain fsync does not flush the drive cache; F_FULLFSYNC does.
    try:
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
    except (AttributeError, OSError):
        os.fsync(fd)


def write_atomic(path: Path | str, data: bytes) -> Path:
    """Replace the file at `path` (or the file it links to) with `data`. Returns the real path."""
    target = Path(os.path.realpath(path))
    try:
        info = target.stat()
    except FileNotFoundError:
        mode = NEW_FILE_MODE
    else:
        if info.st_nlink > 1:
            raise RefusedWriteError(f"{target} has a hard link; renaming would break it")
        mode = stat.S_IMODE(info.st_mode)

    temp = target.with_name(f".{target.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fchmod(handle.fileno(), mode)
            _full_fsync(handle.fileno())
        os.replace(temp, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()
        raise

    folder = os.open(target.parent, os.O_RDONLY)
    try:
        os.fsync(folder)
    finally:
        os.close(folder)
    return target
