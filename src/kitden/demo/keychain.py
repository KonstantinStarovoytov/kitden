"""Stands in for macOS `security` in `kitden demo` only: the items live in a JSON file
`{"<service> <account>": value}` beside the sample home, never in the Keychain.

It knows only what Kitden runs (see `kitden.local_gateway.keychain`): `-i` with
`add-generic-password -U -s S -a "A" -X HEX` lines on stdin, `find-generic-password -w` and
`delete-generic-password`. It repeats the rules of `tests/fixtures/fake_security.py`, which the
package cannot import: a missing item exits 44, and an option without its value exits 2.
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


def _command(items: dict[str, str], words: list[str]) -> tuple[int, str]:
    name, flags = words[0], _options(words[1:])
    if None in flags.values():
        return USAGE, ""
    key = f"{flags.get('-s')} {flags.get('-a')}"
    if name == "add-generic-password":
        if key in items and "-U" not in flags:
            return DUPLICATE, ""
        items[key] = bytes.fromhex(flags.get("-X") or "").decode()
        return 0, ""
    if name == "find-generic-password":
        return (0, items[key] + "\n") if key in items else (NOT_FOUND, "")
    if name == "delete-generic-password":
        return (0, "") if items.pop(key, None) is not None else (NOT_FOUND, "")
    return 1, ""


class DemoKeychain:
    """The Keychain runner in the demo: `(args, stdin=None) -> (exit code, stdout)`."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def __call__(self, args: list[str], stdin: str | None = None) -> tuple[int, str]:
        items = json.loads(self.path.read_text()) if self.path.exists() else {}
        before = dict(items)
        code, out = 0, ""
        if args == ["-i"]:
            for line in (stdin or "").splitlines():
                if line.strip() and _command(items, shlex.split(line))[0] == USAGE:
                    return USAGE, ""  # nothing is written
        else:
            code, out = _command(items, args)
        if items != before:  # only a change is written, in one step
            write_atomic(self.path, json.dumps(items).encode())
            self.path.chmod(0o600)
        return code, out
