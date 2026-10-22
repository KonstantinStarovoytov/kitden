"""A stand-in for macOS `security`, so tests never touch the real Keychain.

    python fake_security.py ITEMS_FILE [security arguments]

It keeps generic password items in ITEMS_FILE, a JSON object of "service account" → value.
It knows only what Kitden runs: `-i` with `add-generic-password` lines on stdin,
`find-generic-password -w` and `delete-generic-password`. Like the real one, a missing item
exits with 44, and `-i` exits with 0 even when a line fails.
"""

import json
import shlex
import sys
from pathlib import Path

NOT_FOUND = 44


def options(words: list[str]) -> dict[str, str]:
    """-s, -a and -X take a value; any other word is a flag on its own."""
    found, rest = {}, iter(words)
    for word in rest:
        found[word] = next(rest, "") if word in ("-s", "-a", "-X") else ""
    return found


def command(items: dict, words: list[str]) -> int:
    name, flags = words[0], options(words[1:])
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
        print(items[key])
        return 0
    if name == "delete-generic-password":
        return 0 if items.pop(key, None) is not None else NOT_FOUND
    return 1


def main() -> int:
    store, args = Path(sys.argv[1]), sys.argv[2:]
    items = json.loads(store.read_text()) if store.exists() else {}
    if args == ["-i"]:
        for line in sys.stdin:
            if line.strip():
                command(items, shlex.split(line))
        code = 0
    else:
        code = command(items, args)
    store.write_text(json.dumps(items))
    return code


if __name__ == "__main__":
    sys.exit(main())
