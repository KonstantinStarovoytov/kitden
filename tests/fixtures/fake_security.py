"""A stand-in for macOS `security`, so tests never touch the real Keychain.

    python fake_security.py ITEMS_FILE [security arguments]

It keeps generic password items in ITEMS_FILE, a JSON object of "service account" → value.
It knows only what Kitden runs: `-i` with `add-generic-password` lines on stdin,
`find-generic-password -g` (and `-w`) and `delete-generic-password`. Like the real one, a
missing item exits with 44, and `-i` exits with 0 even when a line fails. An option without its
value (`-X` at the end of a line) is a usage error: it exits with 2, also under `-i`.

It prints a value the way the real one did on a GitHub macOS runner (2026-11-15): `-w` prints
it as it is when every byte is printable ASCII, else as hex; `-g` writes the item's attributes
on stdout and the password on stderr, `password: 0x<HEX>  "<bytes>"` when a byte is not
printable ASCII, with each such byte in octal (`\\320`). Not seen yet, to confirm on a runner:
`password: "<value>"` for a printable value, with a backslash in octal (`\\134`) and quotes as
they are.
"""

import json
import shlex
import sys
from pathlib import Path

NOT_FOUND = 44
USAGE = 2


def printable(data: bytes) -> bool:
    return all(0x20 <= byte <= 0x7E for byte in data)


def password_line(value: str) -> str:
    """The line `find-generic-password -g` writes on stderr."""
    data = value.encode()
    quoted = "".join(
        chr(byte) if 0x20 <= byte <= 0x7E and byte != 0x5C else f"\\{byte:03o}" for byte in data
    )
    if printable(data):
        return f'password: "{quoted}"'
    return f'password: 0x{data.hex().upper()}  "{quoted}"'


def options(words: list[str]) -> dict[str, str | None]:
    """-s, -a and -X take a value (None when it is missing); any other word is a flag."""
    found, rest = {}, iter(words)
    for word in rest:
        found[word] = next(rest, None) if word in ("-s", "-a", "-X") else ""
    return found


def command(items: dict, words: list[str]) -> int:
    name, flags = words[0], options(words[1:])
    if None in flags.values():
        print("security: an option needs a value", file=sys.stderr)
        return USAGE
    key = f"{flags.get('-s')} {flags.get('-a')}"
    if name == "add-generic-password":
        if key in items and "-U" not in flags:
            return 45
        items[key] = bytes.fromhex(flags["-X"]).decode()
        return 0
    if name == "find-generic-password":
        if key not in items:
            print("The specified item could not be found in the keychain.", file=sys.stderr)
            return NOT_FOUND
        if "-g" in flags:
            print('keychain: "fake.keychain-db"\nclass: "genp"\nattributes:')
            print(password_line(items[key]), file=sys.stderr)
            return 0
        data = items[key].encode()
        print(items[key] if printable(data) else data.hex())
        return 0
    if name == "delete-generic-password":
        return 0 if items.pop(key, None) is not None else NOT_FOUND
    return 1


def main() -> int:
    store, args = Path(sys.argv[1]), sys.argv[2:]
    items = json.loads(store.read_text()) if store.exists() else {}
    before = dict(items)
    if args == ["-i"]:
        for line in sys.stdin:
            if line.strip() and command(items, shlex.split(line)) == USAGE:
                return USAGE  # nothing is written
        code = 0
    else:
        code = command(items, args)
    # Only a change is written, in one step: a gateway reading an item at the same time as a
    # test changes one neither loses the change nor reads half a file.
    if items != before:
        temporary = store.with_suffix(".tmp")
        temporary.write_text(json.dumps(items))
        temporary.replace(store)
    return code


if __name__ == "__main__":
    sys.exit(main())
