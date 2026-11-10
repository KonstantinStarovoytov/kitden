"""Secrets of moved servers in the macOS Keychain or the Linux keyring.

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

On Linux the same item is kept by `secret-tool` (package libsecret-tools; GNOME Keyring and KDE
Wallet serve it), with the attributes `service kitden account <server>/<key>`. Facts from its
Debian man page and libsecret's `tool/secret-tool.c`, checked 2026-11-03:
- `store` reads the value from stdin until EOF, so it is never in the process list; a newline
  would become part of it, and Kitden writes none. `store` exits 1 on any error, so `store`
  reads the item back here too.
- `lookup` prints the value with no newline when piped. It exits 1 with nothing on stdout both
  when no item matches and when the keyring cannot be reached; only the second writes to
  stderr. So "not there" is exit 1 with empty stdout and stderr, and anything else is
  "could not reach".
- `clear` removes the matching items; it is taken to exit 1 silently when there was none
  (libsecret reports a clear that removed nothing as a failure), to confirm on Ubuntu.
- It finds the keyring through DBUS_SESSION_BUS_ADDRESS. A gateway that Codex starts gets only
  a short list of variables (Codex config reference, `mcp_servers.<id>.env_vars`, checked
  2026-11-03), so `tool_env` fills in the session bus every systemd desktop listens on.
"""

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TypeGuard

from kitden import system

SERVICE = "kitden"
SECURITY = "/usr/bin/security"  # by its full path, never from PATH
SECRET_TOOL = "/usr/bin/secret-tool"  # noqa: S105 - a command, not a secret
NOT_FOUND = 44
TIMEOUT = 20  # seconds; the Keychain may ask the user to unlock it
SECRET_FIELDS = ("env", "headers")  # the gateway entry's maps whose values may be secrets
REACH = "Kitden could not reach the Keychain."
LINUX_REACH = (
    "Kitden could not reach the keyring. Install libsecret-tools and sign in to your desktop "
    "session."
)
# Characters that would break the `security -i` command line.
NOT_IN_ACCOUNTS = {'"', "\\"}

Runner = Callable[..., tuple[int, str, str]]  # (args, stdin=None) → (code, stdout, stderr)


class KeychainError(Exception):
    """The Keychain could not be used. The message is one plain sentence, never a value."""


def from_source() -> bool:
    """Kitden runs from a source checkout (tests, development), not from an installed release,
    which always lives in a site-packages folder."""
    return "site-packages" not in Path(__file__).resolve().parts


def _stand_in(variable: str, real: str) -> str:
    """The real tool, or in a source checkout the stand-in that tests name in `variable`. A
    release never reads it: whoever can set the gateway's environment (the `env` of its client
    entry) must not choose the program that gets every secret."""
    return os.environ.get(variable, real) if from_source() else real


def security_path() -> str:
    """The `security` command; tests point KITDEN_SECURITY at a stand-in."""
    return _stand_in("KITDEN_SECURITY", SECURITY)


def secret_tool_path() -> str:
    """The `secret-tool` command; tests point KITDEN_SECRET_TOOL at a stand-in."""
    return _stand_in("KITDEN_SECRET_TOOL", SECRET_TOOL)


def reach() -> str:
    """The sentence for a secret store Kitden cannot use, in this system's words."""
    return REACH if system.SYSTEM == "mac" else LINUX_REACH


def tool_env() -> dict[str, str]:
    """The environment for the secret tool: this one, with the session bus on Linux."""
    env = dict(os.environ)
    if system.SYSTEM != "mac" and not env.get("DBUS_SESSION_BUS_ADDRESS"):
        runtime = env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime}/bus"
    return env


def run_security(args: list[str], stdin: str | None = None) -> tuple[int, str, str]:
    """Run this system's secret tool (`security` or `secret-tool`) with args and return its
    exit code, output and error output."""
    tool = security_path() if system.SYSTEM == "mac" else secret_tool_path()
    try:
        done = subprocess.run(  # noqa: S603 - a fixed program and no shell
            [tool, *args],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
            env=tool_env(),
        )
    except (OSError, subprocess.SubprocessError):
        raise KeychainError(reach()) from None
    return done.returncode, done.stdout, done.stderr


def _attributes(account: str) -> list[str]:
    return ["service", SERVICE, "account", account]


def is_reference(value: object) -> TypeGuard[dict]:
    """True for `{"keychain": "<server>/<key>"}` and nothing else."""
    return (
        isinstance(value, dict)
        and set(value) == {"keychain"}
        and isinstance(value["keychain"], str)
    )


def store(server: str, key: str, value: str, run: Runner = run_security) -> dict:
    """Write the value to the secret store, or update it, and return its reference."""
    account = f"{server}/{key}"
    if NOT_IN_ACCOUNTS & set(account) or not account.isprintable():
        raise KeychainError(reach())
    if system.SYSTEM == "mac":
        line = f'add-generic-password -U -s {SERVICE} -a "{account}" -X {value.encode().hex()}\n'
        code, _, _ = run(["-i"], stdin=line)
    else:
        label = f"--label=Kitden: {account}"
        code, _, _ = run(["store", label, *_attributes(account)], stdin=value)
    if code != 0 or _find(account, run) != value:
        raise KeychainError(reach())
    return {"keychain": account}


def read(ref: dict, run: Runner = run_security) -> str | None:
    """The value a reference names, or None when the secret store has no such item."""
    return _find(ref["keychain"], run)


def delete(ref: dict, run: Runner = run_security) -> None:
    """Remove the item a reference names. Quiet when it is not there."""
    account = ref["keychain"]
    if system.SYSTEM == "mac":
        code, _, _ = run(["delete-generic-password", "-s", SERVICE, "-a", account])
        if code not in (0, NOT_FOUND):
            raise KeychainError(reach())
        return
    code, _, err = run(["clear", *_attributes(account)])
    if code != 0 and not (code == 1 and not err.strip()):
        raise KeychainError(reach())


def references_in(entry: dict) -> list[dict]:
    """The references among an entry's env values and header values, and its sign-in's."""
    found = [entry["sign_in"]] if is_reference(entry.get("sign_in")) else []
    for field in SECRET_FIELDS:
        values = entry.get(field)
        if isinstance(values, dict):
            found += [value for value in values.values() if is_reference(value)]
    return found


def resolve_entry(entry: dict, run: Runner = run_security) -> dict:
    """A copy of the entry with each reference replaced by its value from the secret store."""
    resolved = dict(entry)
    for field in SECRET_FIELDS:
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
        store = system.secret_store_name()
        raise KeychainError(f"Kitden could not read a secret of {server} from the {store}.")
    return found


def _find(account: str, run: Runner) -> str | None:
    if system.SYSTEM == "mac":
        code, out, _ = run(["find-generic-password", "-s", SERVICE, "-a", account, "-w"])
        if code == NOT_FOUND:
            return None
        if code != 0:
            raise KeychainError(reach())
        return out.removesuffix("\n")
    code, out, err = run(["lookup", *_attributes(account)])
    if code == 0:
        return out
    if code == 1 and not out and not err.strip():
        return None
    raise KeychainError(reach())
