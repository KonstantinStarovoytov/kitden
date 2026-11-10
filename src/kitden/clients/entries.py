"""What an MCP entry says about moving it into the Kitden gateway, read from the entry alone.

The scan reads it with the entry, so the page knows which outside rows stay direct without
reading any file again. A move asks the same checks before its review.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from kitden.local_gateway.settings import fill_placeholders

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
# A command inside a Mac app: "/Applications/Pen.app/Contents/...".
IN_APP = re.compile(r"(?:^|/)([^/]+)\.app/Contents/")


def gateway_entry(entry: dict) -> dict:
    """What the Kitden gateway runs: command, args, env and a start folder, or url and headers.
    Keys only the client reads (type, on/off, tool lists, timeouts) stay behind;
    local_move_steps adds a Codex entry's own start time."""
    keys = ("command", "args", "env", "cwd", "url")
    server = {key: entry[key] for key in keys if entry.get(key)}
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
    args = [fill_placeholders(arg, "") for arg in _strings(server.get("args"))]
    return any("${" in s for s in _strings({**server, "args": args}))


def entry_refusal(name: str, entry: dict) -> str | None:
    """Why the Kitden gateway cannot run this entry, so it stays direct; None when it can."""
    server = gateway_entry(entry)
    if "cwd" in entry:
        why = _folder_refusal(name, entry["cwd"])
        if why is not None:
            return why
    if reads_elsewhere(entry, server):
        # A variable, an env file or a helper command the client reads as it starts the server.
        return f"{name} needs values its client fills in when it starts; it stays direct for now."
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


def _folder_refusal(name: str, folder: Any) -> str | None:
    """Why the gateway cannot start a server in its own folder; None when it can: a full path
    to a folder on this computer. One the client fills in ("${CLAUDE_PLUGIN_ROOT}") is not
    named; a plain one is named by its base name. The gateway is the only way such a server
    runs in Cursor: its docs list command, args, env and envFile, no cwd (checked 2026-11-09)."""
    if not isinstance(folder, str):
        return f"{name} could not be read from its file."
    if "${" in folder:
        return f"{name} must start in a folder of its own; it stays direct for now."
    where = f"its own folder, {Path(folder).name}"
    if not Path(folder).is_absolute():
        return f"{name} must start in {where}; it stays direct for now."
    if not Path(folder).is_dir():
        gone = f"{where}, which is not on this computer"
        return f"{name} must start in {gone}; it stays direct for now."
    return None


def app_of(entry: dict) -> str | None:
    """The Mac app a server's command runs from ("Pen" for Pen.app), else None. Such an app
    may write its entry again when it starts: pen.dev "sets up supported MCP integrations when
    it starts" (docs.pencil.dev, checked 2026-11-08)."""
    command = entry.get("command")
    found = IN_APP.search(command) if isinstance(command, str) else None
    return found.group(1) if found else None
