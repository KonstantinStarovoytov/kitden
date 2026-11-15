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
- A `security -i` line of up to 4,095 bytes before its newline is read whole; from 4,096 bytes
  on it is cut there, and the rest of the line runs as another command. So `store` refuses a
  value whose line would be longer than LINE_LIMIT, before it runs anything.
- `find-generic-password -w` prints a value with a byte outside printable ASCII as hex
  (`d0bad0bb…`), the same as an ASCII value made of hex digits would look. `-g` writes the item's
  attributes on stdout and the password on stderr, in one of these forms:
  `password: "cafe1234"` for printable ASCII;
  `password: 0x6120226222205C20632764  "a "b" \\134 c'd"` for a value with a quote and a
  backslash (seen only together, so which one brings the hex is not known), and
  `password: 0x6109620A63  "a\\011b\\012c"` when a byte is outside printable ASCII: the hex,
  then the bytes in quotes, a backslash and the bytes outside printable ASCII in octal;
  `password: 0xE697A5E69CAC ` (no quotes) when no byte is printable; `password: ` for an empty
  value. The `0x` form tells hex from a value, so Kitden reads `-g` and takes the bytes from the
  hex. Quotes with no hex are read only when they hold printable ASCII and no backslash. Any
  other line is not a value, and Kitden says it could not read the secret; so is an empty
  password, which Kitden never stores.
- `-w` as the last option of `add-generic-password` asks for the value and reads it from stdin,
  but keeps only its first 128 bytes; inside `-i`, and on a `-i` line continued with a
  backslash, the rest runs as commands. No way was found to write a longer value whole without
  it in the arguments.

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
# The longest `security -i` line Kitden writes, its newline included: 95 bytes under the 4,095
# (newline not counted) that a runner read whole.
LINE_LIMIT = 4000
TOO_LONG = (
    "The secret {account} is too long for the Keychain: {size:,} bytes, and Kitden can store "
    "at most {most:,}. Keep the server in the client's own settings, or use a shorter token."
)
UNREADABLE = "Kitden could not read a secret of {server} from the {store}."
# `find-generic-password -g`'s password line: the hex of the bytes, then the printable ones in
# quotes if there are any, when a byte is not printable ASCII or the value has a backslash and a
# quote (seen together); else the value in quotes. The value comes from the hex, or from quotes
# that hold printable ASCII and no backslash: only these forms were seen.
PASSWORD = re.compile(r'password: (?:0x(?P<hex>(?:[0-9A-Fa-f]{2})+)(?: +".*"| *)|"(?P<shown>.*)")')
PLAIN = re.compile(r"[ -\[\]-~]+")  # printable ASCII but a backslash

Runner = Callable[..., tuple[int, str, str]]  # (args, stdin=None) → (code, stdout, stderr)


class KeychainError(Exception):
    """The Keychain could not be used. The message is one plain sentence, never a value."""


class TooLong(KeychainError):
    """A secret too long for the Keychain; nothing was written."""


class Unreadable(KeychainError):
    """The Keychain answered with a password Kitden does not read as a value."""


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
    mac = system.SYSTEM == "mac"
    tool = security_path() if mac else secret_tool_path()
    try:
        done = subprocess.run(  # noqa: S603 - a fixed program and no shell
            [tool, *args],
            input=None if stdin is None else stdin.encode(),
            capture_output=True,
            timeout=TIMEOUT,
            check=False,
            env=tool_env(),
        )
        # `secret-tool lookup` prints the value on stdout, so its bytes are read strictly. On
        # macOS stdout holds only an item's attributes (the keychain's path among them), and
        # stderr on both only `security`'s escaped password line or a message.
        out = done.stdout.decode(errors="replace" if mac else "strict")
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        raise KeychainError(reach()) from None
    return done.returncode, out, done.stderr.decode(errors="replace")


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
        raise TooLong(TOO_LONG.format(account=f"{server}/{key}", size=size, most=most))


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
            raise Unreadable(UNREADABLE.format(server=server, store="Keychain")) from None
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
    # Kitden never stores an empty secret (`secrets_out` leaves an empty value in place), and
    # `security` writes one as `password: ` anyway. A backslash in quotes with no hex before it
    # was never seen, so what it would mean is not guessed.
    if not PLAIN.fullmatch(found["shown"]):
        raise ValueError("not printable ASCII without a backslash")
    return found["shown"]
