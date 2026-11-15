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
- `delete-generic-password` removes the item.
- Exit code 44 means the item is not there. The man page does not list exit codes; 44 is what
  `security` returns for a missing item (errSecItemNotFound), not tried on this machine.

Seen on a GitHub macOS runner on 2026-11-15, not in the man page:
- A `security -i` line is cut at about 4 KB: of a line for a 2,048-character value, about 2,020
  characters were stored (so at least 4,078 bytes of the line were read whole), and the rest of
  the line ran as another command. 1,024 characters (a line of about 2,100 bytes) came back
  whole. So `store` refuses a value whose line would be longer than LINE_LIMIT, before it runs
  anything.
- `find-generic-password -w` prints a value with a byte outside printable ASCII as hex
  (`d0bad0bb…`), the same as an ASCII value made of hex digits would look. `-g` writes the item's
  attributes on stdout and on stderr `password: 0xD0BA…  "\\320\\272…"`: the bytes in hex, then
  in quotes with such bytes in octal. That `0x` form tells the two apart, so Kitden reads `-g`.
  A printable value is taken to be `password: "<value>"`, with a backslash in octal (`\\134`) or
  escaped (`\\\\`) and quotes as they are: to confirm on a runner. Any other line is not a
  value, and Kitden says it could not read the secret.

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
import re
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
# The longest `security -i` line Kitden writes, its newline included: under the 4,078 bytes a
# runner read whole, with room to spare.
LINE_LIMIT = 4000
TOO_LONG = (
    "The secret {account} is too long for the Keychain: {size:,} bytes, and Kitden can store "
    "at most {most:,}."
)
UNREADABLE = "Kitden could not read a secret of {server} from the {store}."
# `find-generic-password -g`'s password line: the hex of the bytes when one is not printable
# ASCII (then the same bytes in quotes), else the value in quotes.
PASSWORD = re.compile(r'password: (?:0x(?P<hex>(?:[0-9A-Fa-f]{2})+)(?:  ".*")?|"(?P<shown>.*)")')
# In the quotes: a byte in octal, an escaped backslash or quote, or a printable ASCII letter.
SHOWN = re.compile(r'\\([0-7]{3})|\\([\\"])|([ -\[\]-~])')

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
    check_size(server, key, value)
    if system.SYSTEM == "mac":
        code, _, _ = run(["-i"], stdin=_line(account, value))
    else:
        label = f"--label=Kitden: {account}"
        code, _, _ = run(["store", label, *_attributes(account)], stdin=value)
    if code != 0 or _find(account, run) != value:
        raise KeychainError(reach())
    return {"keychain": account}


def _line(account: str, value: str) -> str:
    """The `security -i` line that writes the item."""
    return f'add-generic-password -U -s {SERVICE} -a "{account}" -X {value.encode().hex()}\n'


def longest(server: str, key: str) -> int:
    """The most bytes of value that fit on the `security -i` line for this item."""
    return (LINE_LIMIT - len(_line(f"{server}/{key}", "").encode())) // 2


def check_size(server: str, key: str, value: str) -> None:
    """Refuse a value too long to be written whole, before anything is written. Only macOS has
    a limit: `secret-tool store` reads the value from stdin until EOF."""
    if system.SYSTEM != "mac":
        return
    size, most = len(value.encode()), longest(server, key)
    if size > most:
        raise KeychainError(TOO_LONG.format(account=f"{server}/{key}", size=size, most=most))


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
        raise KeychainError(UNREADABLE.format(server=server, store=system.secret_store_name()))
    return found


def _find(account: str, run: Runner) -> str | None:
    if system.SYSTEM == "mac":
        code, _, err = run(["find-generic-password", "-s", SERVICE, "-a", account, "-g"])
        if code == NOT_FOUND:
            return None
        if code != 0:
            raise KeychainError(reach())
        try:
            return _password(err)
        except ValueError:  # also a value that is not UTF-8
            server = account.rpartition("/")[0]
            raise KeychainError(UNREADABLE.format(server=server, store="Keychain")) from None
    code, out, err = run(["lookup", *_attributes(account)])
    if code == 0:
        return out
    if code == 1 and not out and not err.strip():
        return None
    raise KeychainError(reach())


def _password(said: str) -> str:
    """The value on `find-generic-password -g`'s password line. ValueError for any other line,
    no line or more than one."""
    lines = [line for line in said.splitlines() if line.startswith("password:")]
    found = PASSWORD.fullmatch(lines[0]) if len(lines) == 1 else None
    if found is None:
        raise ValueError("not a password line")
    if found["hex"] is not None:
        return bytes.fromhex(found["hex"]).decode()
    data, at = bytearray(), 0
    for part in SHOWN.finditer(found["shown"]):
        if part.start() != at:
            raise ValueError("not a printable letter or escape")
        octal, escaped, letter = part.groups()
        data += bytes([int(octal, 8)]) if octal else (escaped or letter).encode()
        at = part.end()
    if at != len(found["shown"]):
        raise ValueError("not a printable letter or escape")
    return data.decode()
