"""What an MCP entry says about moving it into the Kitden gateway, read from the entry alone.

The scan reads it with the entry, so the page knows which outside rows stay direct without
reading any file again. A move asks the same checks before its review.
"""

import hashlib
import json
from typing import Any

from kitden.local_gateway.settings import PLACEHOLDERS

# Keys whose values come from the shell or from another program (checked 2026-10-21): Cursor
# `envFile`; Codex `env_vars`, `bearer_token_env_var`, `env_http_headers` and
# `http_headers_helper`; Claude Code `headersHelper`.
FROM_ELSEWHERE = (
    "envFile",
    "env_vars",
    "bearer_token_env_var",
    "env_http_headers",
    "http_headers_helper",
    "headersHelper",
)
# Why an entry in a project's own file (or a project layer) stays where it is.
IN_PROJECT_FILES = "{} is in the project's own files; it stays there."


def gateway_entry(entry: dict) -> dict:
    """What the Kitden gateway runs: command, args and env, or url and headers. Keys only the
    client reads (type, on/off, tool lists, timeouts) stay behind; local_move_steps adds a
    Codex entry's own start time."""
    server = {key: entry[key] for key in ("command", "args", "env", "url") if entry.get(key)}
    headers = entry.get("headers") or entry.get("http_headers")
    if headers:
        server["headers"] = headers
    return server


def entry_key(entry: dict) -> str:
    """Equal for two entries the Kitden gateway would run the same way, as a move compares
    them: a hash of `gateway_entry`, so the key itself says nothing of a secret in it."""
    text = json.dumps(gateway_entry(entry), sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in (*_strings(k), *_strings(v))]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def reads_elsewhere(entry: dict, server: dict) -> bool:
    """A key or a `${...}` value that the client fills in from elsewhere. A project folder in
    the arguments is fine: the gateway fills it in."""
    if any(key in entry for key in FROM_ELSEWHERE):
        return True
    args = []
    for arg in _strings(server.get("args")):
        for placeholder in PLACEHOLDERS:
            arg = arg.replace(placeholder, "")
        args.append(arg)
    return any("${" in s for s in _strings({**server, "args": args}))


def entry_refusal(name: str, entry: dict) -> str | None:
    """Why the Kitden gateway cannot run this entry, so it stays direct; None when it can."""
    server = gateway_entry(entry)
    if reads_elsewhere(entry, server):
        return f"{name} reads values from your shell; it stays direct for now."
    if "cwd" in entry:
        return f"{name} starts in its own folder; it stays direct for now."
    # The gateway speaks streamable HTTP; Claude Code also has `sse` and `ws` (checked
    # 2026-10-21). Without a type, an address that ends in /sse is SSE, as Cursor reads it.
    kind = entry.get("type")
    by_address = kind is None and str(server.get("url", "")).rstrip("/").endswith("/sse")
    if str(kind).lower() in ("sse", "ws") or by_address:
        return (
            f"{name} uses a connection the Kitden gateway does not support yet; "
            "it stays direct for now."
        )
    shapes = {"command": str, "args": list, "env": dict, "url": str, "headers": dict}
    wrong = any(not isinstance(server.get(k, kind()), kind) for k, kind in shapes.items())
    if wrong or not ("command" in server or "url" in server):
        return f"{name} could not be read from its file."
    return None
