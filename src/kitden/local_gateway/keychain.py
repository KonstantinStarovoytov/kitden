"""Secrets of moved servers in the macOS Keychain.

gateway.json keeps a reference `{"keychain": "<server>/<key>"}` in place of an env or header
value. The value is a generic password item of the service "kitden" with the account
"<server>/<key>". The gateway reads it when it starts the server.

Facts about `security` this relies on (from `man security`, checked 2026-10-22):
- `-i` reads commands from stdin until EOF. Kitden writes an item this way, so the value is
  never in the process list. The man page says nothing about the exit code of `-i` when a line
  fails, so `store` reads the item back instead of trusting it.
- `add-generic-password -U` updates the item when it is there; `-X` takes the value as a
  hexadecimal string, so it needs no quoting.
- `find-generic-password -w` prints only the value; `delete-generic-password` removes the item.
- Exit code 44 means the item is not there. The man page does not list exit codes; 44 is what
  `security` returns for a missing item (errSecItemNotFound), not tried on this machine.
"""

import os
import subprocess
from collections.abc import Callable

SERVICE = "kitden"
SECURITY = "/usr/bin/security"  # by its full path, never from PATH
NOT_FOUND = 44
TIMEOUT = 20  # seconds; the Keychain may ask the user to unlock it
REACH = "Kitden could not reach the Keychain."
# Characters that would break the `security -i` command line.
NOT_IN_ACCOUNTS = {'"', "\\"}

Runner = Callable[..., tuple[int, str]]  # (args, stdin=None) → (exit code, stdout)


class KeychainError(Exception):
    """The Keychain could not be used. The message is one plain sentence, never a value."""


def security_path() -> str:
    """The `security` command; tests point KITDEN_SECURITY at a stand-in."""
    return os.environ.get("KITDEN_SECURITY", SECURITY)


def run_security(args: list[str], stdin: str | None = None) -> tuple[int, str]:
    """Run `security` with args and return its exit code and output."""
    try:
        done = subprocess.run(  # noqa: S603 - a fixed program and no shell
            [security_path(), *args],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise KeychainError(REACH) from None
    return done.returncode, done.stdout


def is_reference(value: object) -> bool:
    """True for `{"keychain": "<server>/<key>"}` and nothing else."""
    return (
        isinstance(value, dict)
        and set(value) == {"keychain"}
        and isinstance(value["keychain"], str)
    )


def store(server: str, key: str, value: str, run: Runner = run_security) -> dict:
    """Write the value to the Keychain, or update it, and return its reference."""
    account = f"{server}/{key}"
    if NOT_IN_ACCOUNTS & set(account) or not account.isprintable():
        raise KeychainError(REACH)
    line = f'add-generic-password -U -s {SERVICE} -a "{account}" -X {value.encode().hex()}\n'
    code, _ = run(["-i"], stdin=line)
    if code != 0 or _find(account, run) != value:
        raise KeychainError(REACH)
    return {"keychain": account}


def read(ref: dict, run: Runner = run_security) -> str | None:
    """The value a reference names, or None when the Keychain has no such item."""
    return _find(ref["keychain"], run)


def delete(ref: dict, run: Runner = run_security) -> None:
    """Remove the item a reference names. Quiet when it is not there."""
    code, _ = run(["delete-generic-password", "-s", SERVICE, "-a", ref["keychain"]])
    if code not in (0, NOT_FOUND):
        raise KeychainError(REACH)


def references_in(entry: dict) -> list[dict]:
    """The references among an entry's env values and header values."""
    found = []
    for field in ("env", "headers"):
        values = entry.get(field)
        if isinstance(values, dict):
            found += [value for value in values.values() if is_reference(value)]
    return found


def resolve_entry(entry: dict, run: Runner = run_security) -> dict:
    """A copy of the entry with each reference replaced by its value from the Keychain."""
    resolved = dict(entry)
    for field in ("env", "headers"):
        values = entry.get(field)
        if isinstance(values, dict):
            resolved[field] = {name: _value(value, run) for name, value in values.items()}
    return resolved


def _value(value: object, run: Runner) -> object:
    if not is_reference(value):
        return value
    found = read(value, run)
    if found is None:
        server = value["keychain"].rpartition("/")[0]
        raise KeychainError(f"Kitden could not read a secret of {server} from the Keychain.")
    return found


def _find(account: str, run: Runner) -> str | None:
    code, out = run(["find-generic-password", "-s", SERVICE, "-a", account, "-w"])
    if code == NOT_FOUND:
        return None
    if code != 0:
        raise KeychainError(REACH)
    return out.removesuffix("\n")
