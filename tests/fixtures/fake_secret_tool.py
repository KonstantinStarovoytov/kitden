"""A stand-in for Linux `secret-tool`, so tests never touch the real keyring.

    python fake_secret_tool.py ITEMS_FILE [secret-tool arguments]

It keeps items in ITEMS_FILE, a JSON object of "service account" → value, the same file shape
as fake_security.py. It knows only what Kitden runs: `store --label=L service S account A`
with the value on stdin, `lookup service S account A` and `clear service S account A`.

Like the real one (libsecret `tool/secret-tool.c`, checked 2026-11-03): `lookup` prints the
value with no newline and exits 1 silently when no item matches; `clear` exits 1 silently when
nothing was removed. With FAKE_SECRET_TOOL_DOWN=1 every command fails the way the real one
does without a keyring: exit 1 and one line on stderr.
"""

import json
import os
import sys
from pathlib import Path

DOWN = "secret-tool: Cannot autolaunch D-Bus without X11 $DISPLAY"


def attributes(words: list[str]) -> str:
    pairs = dict(zip(words[::2], words[1::2], strict=False))
    return f"{pairs.get('service')} {pairs.get('account')}"


def main() -> int:
    store, args = Path(sys.argv[1]), sys.argv[2:]
    if os.environ.get("FAKE_SECRET_TOOL_DOWN"):
        print(DOWN, file=sys.stderr)
        return 1
    items = json.loads(store.read_text()) if store.exists() else {}
    before = dict(items)
    command, words = args[0], [w for w in args[1:] if not w.startswith("--")]
    key, code = attributes(words), 0
    if command == "store":
        items[key] = sys.stdin.read()
    elif command == "lookup":
        if key not in items:
            return 1
        sys.stdout.write(items[key])
    elif command == "clear":
        code = 0 if items.pop(key, None) is not None else 1
    else:
        print(f"secret-tool: unknown command {command}", file=sys.stderr)
        return 2
    if items != before:
        temporary = store.with_suffix(".tmp")
        temporary.write_text(json.dumps(items))
        temporary.replace(store)
    return code


if __name__ == "__main__":
    sys.exit(main())
