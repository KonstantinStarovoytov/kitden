"""An MCP entry the Kitden gateway holds, written as a client writes it (spec 3.3).

The gateway holds `command`, `args`, `env` or `url`, `headers`, and maybe a Codex start time.
Each client writes a user-scope entry its own way:

- Claude Code (~/.claude.json): `type` "stdio" with command, args, env; or `type` "http" with
  url, headers.
- Codex (~/.codex/config.toml): command, args, env; or url with `http_headers`; it keeps
  `startup_timeout_sec`.
- Cursor (~/.cursor/mcp.json): the same fields as the gateway, without a type.

A project folder in the arguments (settings.PLACEHOLDERS) is not a shell value; each client
names it its own way:

- Claude Code sets CLAUDE_PROJECT_DIR in the server's environment, so a user-scope entry
  must write `${CLAUDE_PROJECT_DIR:-.}` (checked 2026-10-22, code.claude.com/docs/en/mcp).
- Cursor fills in `${workspaceFolder}` in command, args, env, url and headers (checked
  2026-10-22, cursor.com/docs/context/mcp).
- Codex has no project folder variable in an MCP entry, only a fixed `cwd` (checked
  2026-10-22, learn.chatgpt.com/docs/extend/mcp), so such an entry is refused.
"""

import re
from typing import Any

from kitden.changes.actions import CLIENT_WORDS, _gateway_entry, _reads_elsewhere
from kitden.local_gateway.settings import PLACEHOLDERS, START_TIME

UNREADABLE = "The entry could not be read."
PROJECT_FOLDER = {"claude_code": "${CLAUDE_PROJECT_DIR:-.}", "cursor": "${workspaceFolder}"}
# The longest first, so `${CLAUDE_PROJECT_DIR:-.}` is not read as `${CLAUDE_PROJECT_DIR}`.
_PLACEHOLDER = re.compile("|".join(re.escape(p) for p in sorted(PLACEHOLDERS, key=len)[::-1]))


def _strings(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    )


def _shape(entry: Any) -> dict:
    """The held entry's fields, checked; anything else raises "The entry could not be read."."""
    if not isinstance(entry, dict):
        raise ValueError(UNREADABLE)
    checks = {
        "command": lambda v: isinstance(v, str),
        "args": lambda v: isinstance(v, list) and all(isinstance(a, str) for a in v),
        "env": _strings,
        "url": lambda v: isinstance(v, str),
        "headers": _strings,
        START_TIME: lambda v: isinstance(v, int | float) and not isinstance(v, bool),
    }
    if any(key in entry and not check(entry[key]) for key, check in checks.items()):
        raise ValueError(UNREADABLE)
    if not isinstance(entry.get("command") or entry.get("url"), str):
        raise ValueError(UNREADABLE)
    return entry


def translate_entry(entry: dict, client: str) -> dict:
    """The entry as `client` writes it. Raises ValueError with a plain reason when it cannot."""
    if client not in CLIENT_WORDS:
        raise ValueError(f"{client} cannot take an MCP entry")
    held = _shape(entry)
    server = _gateway_entry(held)  # command, args, env or url, headers; the type is dropped
    if _reads_elsewhere(held, server):
        raise ValueError("The entry reads values from your shell; put the values in.")
    args = server.get("args")
    if args and any(_PLACEHOLDER.search(a) for a in args):
        folder = PROJECT_FOLDER.get(client)
        if folder is None:
            raise ValueError(
                f"{CLIENT_WORDS[client]} cannot fill in the project folder this server needs."
            )
        server["args"] = [_PLACEHOLDER.sub(lambda _: folder, a) for a in args]
    if client == "claude_code":
        return {"type": "http" if "url" in server else "stdio", **server}
    if client == "codex":
        if "headers" in server:
            server["http_headers"] = server.pop("headers")
        if START_TIME in held:
            server[START_TIME] = held[START_TIME]
    return server
