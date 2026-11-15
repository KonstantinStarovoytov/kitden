"""Stands in for the secret tool (macOS `security`, Linux `secret-tool`) in `kitden demo`
only: the items live in a JSON file `{"<service> <account>": value}` beside the sample home,
never in the Keychain or the keyring.

It knows only what Kitden runs (see `kitden.local_gateway.keychain`): `-i` with
`add-generic-password -U -s S -a "A" -X HEX` lines on stdin, `find-generic-password -g` (and
`-w`) and `delete-generic-password`; on Linux `store`, `lookup` and `clear`. It repeats the
rules of `tests/fixtures/fake_security.py` and `fake_secret_tool.py`, which the package cannot
import: a missing item exits 44 (`security`) or 1 with no output (`secret-tool`), an option
without its value exits 2, and `-g` writes the password on stderr as `security` does. A file it
cannot read or write, or one that is not a JSON object, exits 1, so Kitden says it could not
reach the store.
"""

import json
import shlex
from pathlib import Path

from kitden.changes.atomic import write_atomic
from kitden.local_gateway.keychain import NOT_FOUND

USAGE = 2
DUPLICATE = 45  # an item that is there already, added without -U


def _options(words: list[str]) -> dict[str, str | None]:
    """-s, -a and -X take a value (None when it is missing); any other word is a flag."""
    found, rest = {}, iter(words)
    for word in rest:
        found[word] = next(rest, None) if word in ("-s", "-a", "-X") else ""
    return found


def _printable(data: bytes) -> bool:
    return all(0x20 <= byte <= 0x7E for byte in data)


def _password_line(value: str) -> str:
    """The line `find-generic-password -g` writes on stderr: the value in quotes, after its hex
    when a byte is outside printable ASCII, a quote or a backslash, with a backslash and such
    bytes in octal; only the hex when no byte is printable."""
    data = value.encode()
    quoted = "".join(
        chr(byte) if _printable(bytes([byte])) and byte != 0x5C else f"\\{byte:03o}"
        for byte in data
    )
    if _printable(data) and not {0x22, 0x5C} & set(data):
        return f'password: "{quoted}"\n'
    if not any(_printable(bytes([byte])) for byte in data):
        return f"password: 0x{data.hex().upper()} \n"
    return f'password: 0x{data.hex().upper()}  "{quoted}"\n'


def _command(items: dict[str, str], words: list[str]) -> tuple[int, str, str]:
    if not words:
        return 1, "", ""
    name, flags = words[0], _options(words[1:])
    if None in flags.values():
        return USAGE, "", ""
    key = f"{flags.get('-s')} {flags.get('-a')}"
    if name == "add-generic-password":
        if key in items and "-U" not in flags:
            return DUPLICATE, "", ""
        items[key] = bytes.fromhex(flags.get("-X") or "").decode()
        return 0, "", ""
    if name == "find-generic-password":
        if key not in items:
            return NOT_FOUND, "", ""
        if "-g" in flags:
            return 0, 'class: "genp"\n', _password_line(items[key])
        data = items[key].encode()
        return 0, (items[key] if _printable(data) else data.hex()) + "\n", ""
    if name == "delete-generic-password":
        return (0, "", "") if items.pop(key, None) is not None else (NOT_FOUND, "", "")
    return 1, "", ""


def _linux_command(
    items: dict[str, str], args: list[str], stdin: str | None
) -> tuple[int, str, str]:
    """`secret-tool store|lookup|clear service S account A`: a missing item exits 1 silently."""
    pairs = [word for word in args[1:] if not word.startswith("--")]
    found = dict(zip(pairs[::2], pairs[1::2], strict=False))
    key = f"{found.get('service')} {found.get('account')}"
    if args[0] == "store":
        items[key] = stdin or ""
        return 0, "", ""
    if args[0] == "lookup":
        return (0, items[key], "") if key in items else (1, "", "")
    if args[0] == "clear":
        return (0, "", "") if items.pop(key, None) is not None else (1, "", "")
    return 1, "", ""


class DemoKeychain:
    """The Keychain runner in the demo: `(args, stdin=None) -> (code, stdout, stderr)`; only
    `find-generic-password -g` writes to stderr."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def __call__(self, args: list[str], stdin: str | None = None) -> tuple[int, str, str]:
        try:
            return self._run(args, stdin)
        except (OSError, ValueError):
            return 1, "", ""

    def _run(self, args: list[str], stdin: str | None) -> tuple[int, str, str]:
        items = json.loads(self.path.read_text()) if self.path.exists() else {}
        if not isinstance(items, dict):
            raise ValueError("not a JSON object")
        before = dict(items)
        code, out, err = 0, "", ""
        if args and args[0] in ("store", "lookup", "clear"):
            code, out, err = _linux_command(items, args, stdin)
        elif args == ["-i"]:
            for line in (stdin or "").splitlines():
                if line.strip() and _command(items, shlex.split(line))[0] == USAGE:
                    return USAGE, "", ""  # nothing is written
        else:
            code, out, err = _command(items, args)
        if items != before:  # only a change is written, in one step
            write_atomic(self.path, json.dumps(items).encode())
            self.path.chmod(0o600)
        return code, out, err
