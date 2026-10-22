"""An MCP entry written as a client writes it (spec 3.3, 3.4).

The entry may come from the Kitden gateway or from any client's file. It is read into one
shape (command, args, env or url, headers; references as `${VAR}`), then written the way the
chosen client writes a user-scope entry:

- Claude Code (~/.claude.json): `type` "stdio" with command, args, env; or `type` "http",
  "sse" or "ws" with url, headers. It has no start folder setting. It fills in `${VAR}` and
  `${VAR:-default}` in command, args, env, url and headers, also in user-scope entries in
  ~/.claude.json (checked 2026-10-22, code.claude.com/docs/en/mcp, "Environment variable
  expansion").
- Codex (~/.codex/config.toml): command, args, env, `env_vars` (names it passes on from your
  shell), `cwd`; or url with `http_headers`, `bearer_token_env_var` (a variable sent as
  `Authorization: Bearer`) and `env_http_headers` (header name to variable name). A remote
  server is streamable HTTP only, no SSE. No `${VAR}` form is documented, so any other
  reference is refused (checked 2026-10-22, learn.chatgpt.com/docs/extend/mcp).
- Cursor (~/.cursor/mcp.json): the same fields as the gateway, without a type. It fills in
  `${env:VAR}` in command, args, env, url and headers; no default form is documented. A url
  entry serves both streamable HTTP and SSE; no WebSocket and no start folder setting is
  documented (checked 2026-10-22, cursor.com/docs/context/mcp).

An entry copied from Cursor may use Cursor's own variables (`${userHome}`,
`${workspaceFolder}` and others); no other client has them, so they are refused. Codex fills
in no `${...}` text, so in an entry copied from Codex it is plain text; it is refused where
the new client would fill it in. A refusal names only the variable, never a `:-default`, which
may hold a secret.

A project folder (settings.PLACEHOLDERS) is not a shell value; each client names it its own way:

- Claude Code sets CLAUDE_PROJECT_DIR in the server's environment, so a user-scope entry
  must write `${CLAUDE_PROJECT_DIR:-.}` (checked 2026-10-22, code.claude.com/docs/en/mcp).
- Cursor fills in `${workspaceFolder}` in command, args, env, url and headers, as the folder
  that holds the mcp.json file (checked 2026-10-22, cursor.com/docs/context/mcp). In the user
  file ~/.cursor/mcp.json that is the home folder, not the project, so such an entry is refused.
- Codex has no project folder variable in an MCP entry, only a fixed `cwd` (checked
  2026-10-22, learn.chatgpt.com/docs/extend/mcp), so such an entry is refused.
"""

import re
from typing import Any

from kitden.changes.actions import CLIENT_WORDS
from kitden.local_gateway.settings import PLACEHOLDERS, START_TIME

UNREADABLE = "The entry could not be read."
PROJECT_FOLDER = {"claude_code": "${CLAUDE_PROJECT_DIR:-.}"}
# The longest first, so `${CLAUDE_PROJECT_DIR:-.}` is not read as `${CLAUDE_PROJECT_DIR}`.
_PLACEHOLDER = re.compile("|".join(re.escape(p) for p in sorted(PLACEHOLDERS, key=len)[::-1]))
# `${VAR}`, `${VAR:-default}`, and Cursor's `${env:VAR}`.
_REFERENCE = re.compile(r"\$\{(env:)?([A-Za-z_][A-Za-z0-9_]*)(:-[^}]*)?\}")
# Cursor's own variables, such as `${userHome}` and `${workspaceFolder}`: no other client has them.
_CURSOR_VARIABLE = re.compile(r"\$\{(?!env:)([^}:]*)")
# Text Codex keeps as it is: `${` stands for itself there, so it is marked while it is copied.
_LITERAL = "\x00{"
_MARKED = re.compile(r"\x00\{([^}:]*)")
# What Cursor fills in from a `${...}` in its files (checked 2026-10-22).
_CURSOR_FILLS = re.compile(r"\$\{(env:|userHome\}|workspaceFolder|pathSeparator\}|/\})")
_BEARER = re.compile(r"Bearer \$\{([A-Za-z_][A-Za-z0-9_]*)\}")
TOOL_TIME = "tool_timeout_sec"
_HELPERS = ("envFile", "http_headers_helper", "headersHelper")
_TOOL_LISTS = ("enabled_tools", "disabled_tools")
_KNOWN = {
    "type",
    "command",
    "args",
    "env",
    "url",
    "headers",
    "http_headers",
    "bearer_token_env_var",
    "env_http_headers",
    "env_vars",
    "cwd",
    "enabled",
    START_TIME,
    TOOL_TIME,
}


def _strings(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    )


def _text_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(a, str) for a in value)


def _number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


_CHECKS = {
    "type": lambda v: isinstance(v, str),
    "command": lambda v: isinstance(v, str),
    "args": _text_list,
    "env": _strings,
    "url": lambda v: isinstance(v, str),
    "headers": _strings,
    "http_headers": _strings,
    "bearer_token_env_var": lambda v: isinstance(v, str),
    "env_http_headers": _strings,
    "env_vars": _text_list,
    "cwd": lambda v: isinstance(v, str),
    "enabled": lambda v: isinstance(v, bool),
    START_TIME: _number,
    TOOL_TIME: _number,
}


def _canonical(entry: Any, client: str, source: str | None) -> dict:
    """The entry in one shape: references as `${VAR}`, Codex's own forms read back into
    headers and env. Refuses what cannot be copied as it is. `source` is the client the entry
    comes from, or None for the Kitden gateway's own entry."""
    if not isinstance(entry, dict):
        raise ValueError(UNREADABLE)
    if any(key in entry for key in _HELPERS):
        raise ValueError(
            "The entry reads values from a file or a helper program; put the values in."
        )
    if entry.get("enabled") is False:
        raise ValueError("The entry is turned off; turn it on first.")
    if any(key in entry for key in _TOOL_LISTS):
        raise ValueError(
            "The entry keeps some tools off. "
            "Move it into the gateway to share it with its switches."
        )
    for key in entry:
        if key not in _KNOWN:
            raise ValueError(f"Kitden does not know the setting {key}.")
    if any(key in entry and not check(entry[key]) for key, check in _CHECKS.items()):
        raise ValueError(UNREADABLE)
    if not isinstance(entry.get("command") or entry.get("url"), str):
        raise ValueError(UNREADABLE)

    if source == "cursor" and client != "cursor":
        for text in _texts({k: entry.get(k) for k in ("command", "args", "env", "url", "headers")}):
            if found := _CURSOR_VARIABLE.search(text):
                raise ValueError(
                    f"The entry uses a Cursor variable (`${{{found.group(1)}}}`) that "
                    f"{CLIENT_WORDS[client]} cannot read."
                )

    def plain(text: str) -> str:
        if source == "codex":  # Codex fills in nothing: `${X}` there is plain text
            return text.replace("${", _LITERAL)
        # Cursor's `${env:VAR}` is `${VAR}` here.
        return _REFERENCE.sub(lambda m: m.group(0).replace("${env:", "${"), text)

    out: dict = {}
    for key in ("command", "url"):
        if entry.get(key):
            out[key] = plain(entry[key])
    if entry.get("args"):
        out["args"] = [plain(a) for a in entry["args"]]
    env = {k: plain(v) for k, v in (entry.get("env") or {}).items()}
    for name in entry.get("env_vars") or []:
        env.setdefault(name, f"${{{name}}}")
    headers = {
        k: plain(v) for k, v in (entry.get("headers") or entry.get("http_headers") or {}).items()
    }
    if entry.get("bearer_token_env_var"):
        headers["Authorization"] = f"Bearer ${{{entry['bearer_token_env_var']}}}"
    for header, name in (entry.get("env_http_headers") or {}).items():
        headers[header] = f"${{{name}}}"
    if env:
        out["env"] = env
    if headers:
        out["headers"] = headers
    for key in ("type", "cwd", START_TIME, TOOL_TIME):
        if key in entry:
            out[key] = entry[key]
    return out


def _each_string(server: dict, change) -> dict:
    """The entry with `change` applied to each text: values, list items and map values."""
    out: dict = {}
    for key, value in server.items():
        if isinstance(value, str):
            out[key] = change(value)
        elif isinstance(value, list):
            out[key] = [change(v) for v in value]
        elif isinstance(value, dict):
            out[key] = {k: change(v) for k, v in value.items()}
        else:
            out[key] = value
    return out


def _refuse_reference(client: str, name: str) -> None:
    """Names only the variable: a `:-default` may hold a secret."""
    raise ValueError(
        f"{CLIENT_WORDS[client]} cannot read `${{{name}}}` from your shell; put the value in."
    )


def _texts(server: dict) -> list[str]:
    """Every text in the entry: values, list items and map values."""
    found: list[str] = []
    _each_string(server, lambda t: found.append(t) or t)
    return found


def _references(server: dict) -> list[re.Match]:
    return [m for t in _texts(server) for m in _REFERENCE.finditer(t)]


def _cursor(server: dict) -> dict:
    """References as Cursor writes them: `${env:VAR}`; it has no default form."""
    for found in _references(server):
        if found.group(3):
            _refuse_reference("cursor", found.group(2))

    return _each_string(server, lambda t: _REFERENCE.sub(lambda m: f"${{env:{m.group(2)}}}", t))


def _codex(server: dict) -> dict:
    """References as Codex writes them: only a whole value, in its own keys."""
    out = {key: server[key] for key in ("command", "args") if key in server}
    env, names = {}, []
    for key, value in server.get("env", {}).items():
        if _REFERENCE.fullmatch(value) and value == f"${{{key}}}":
            names.append(key)
        else:
            env[key] = value
    if env:
        out["env"] = env
    if names:
        out["env_vars"] = names
    if "url" in server:
        out["url"] = server["url"]
    plain_headers, from_env = {}, {}
    for header, value in server.get("headers", {}).items():
        whole = _REFERENCE.fullmatch(value)
        bearer = _BEARER.fullmatch(value)
        if header == "Authorization" and bearer:
            out["bearer_token_env_var"] = bearer.group(1)
        elif whole and not whole.group(1) and not whole.group(3):
            from_env[header] = whole.group(2)
        else:
            plain_headers[header] = value
    if plain_headers:
        out["http_headers"] = plain_headers
    if from_env:
        out["env_http_headers"] = from_env
    for key in ("cwd", START_TIME, TOOL_TIME):
        if key in server:
            out[key] = server[key]
    # A reference left in plain text would reach the server as it is.
    for found in _references(out):
        _refuse_reference("codex", found.group(2))
    return out


def translate_entry(entry: dict, client: str, *, source: str | None = None) -> dict:
    """The entry as `client` writes it. Raises ValueError with a plain reason when it cannot.
    `source` is the client the entry comes from; None is the Kitden gateway's own entry."""
    if client not in CLIENT_WORDS:
        raise ValueError(f"{client} cannot take an MCP entry")
    return _unmarked(_render(_canonical(entry, client, source), client), client)


def _unmarked(server: dict, client: str) -> dict:
    """Codex's plain `${` text back as it was, where the client keeps it as plain text."""
    for text in _texts(server):
        found = _MARKED.search(text)
        if found and (
            client == "claude_code" or _CURSOR_FILLS.search(text.replace(_LITERAL, "${"))
        ):
            raise ValueError(
                f"The entry holds `${{{found.group(1)}}}` as plain text; "
                f"{CLIENT_WORDS[client]} would fill it in."
            )
    return _each_string(server, lambda t: t.replace(_LITERAL, "${"))


def _render(server: dict, client: str) -> dict:
    """The entry in one shape, written as `client` writes it."""
    words = CLIENT_WORDS[client]
    kind = str(server.pop("type", "")).lower()
    if not kind and server.get("url", "").rstrip("/").endswith("/sse"):
        kind = "sse"
    if kind in ("sse", "ws") and (client == "codex" or (client == "cursor" and kind == "ws")):
        connection = "an SSE" if kind == "sse" else "a WebSocket"
        raise ValueError(f"{words} cannot use {connection} connection from here.")
    if "cwd" in server and client != "codex":
        raise ValueError(f"{words} has no setting for a start folder.")
    if client != "codex":
        server.pop(START_TIME, None)
        server.pop(TOOL_TIME, None)

    if any(_PLACEHOLDER.search(t) for t in _texts(server)):
        folder = PROJECT_FOLDER.get(client)
        if folder is None:
            raise ValueError(f"{words} cannot fill in the project folder this server needs.")
        server = _each_string(server, lambda t: _PLACEHOLDER.sub(lambda _: folder, t))

    if client == "claude_code":
        if kind not in ("sse", "ws"):
            kind = "http" if "url" in server else "stdio"
        return {"type": kind, **server}
    if client == "cursor":
        return _cursor(server)
    return _codex(server)
