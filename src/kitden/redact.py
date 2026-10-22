"""The single place where secret values are removed (FR-006).

Everything shown on the page, printed by `scan`, written to the change log, or returned by the
MCP server passes through `redact` first.
"""

import json
import re
from typing import Any
from urllib.parse import unquote_plus, urlsplit, urlunsplit

SECRET = "[secret]"  # noqa: S105 - placeholder text, not a password

# Maps whose values are secrets (env values, header values) in Claude Code, Codex and Cursor.
# Codex `env_http_headers` holds variable names, not values, so it is not listed here.
_SECRET_MAPS = {"env", "headers", "http_headers"}

_REFERENCE = re.compile(r"\$\{(env:)?[A-Za-z_][A-Za-z0-9_]*(:-[^}]*)?\}")
_SECRET_WORD = r"(api[-_]?key|access[-_]?key|token|secret|password|passwd|auth|credential|sig)"  # noqa: S105 - pattern of secret names
_SECRET_FLAG = re.compile(rf"--?[A-Za-z0-9_-]*{_SECRET_WORD}[A-Za-z0-9_-]*", re.I)
_SECRET_FLAG_VALUE = re.compile(rf"(--?[A-Za-z0-9_-]*{_SECRET_WORD}[A-Za-z0-9_-]*)=.+", re.I)
_SECRET_PARAM = re.compile(rf".*{_SECRET_WORD}.*", re.I)
# `NAME=value` arguments, for example `docker run -e API_KEY=...`.
_SECRET_PAIR = re.compile(
    rf"(?P<name>[A-Za-z0-9_.-]*{_SECRET_WORD}[A-Za-z0-9_.-]*)=(?P<value>.+)", re.I
)
_HEADER_ARG = re.compile(
    r"([A-Za-z0-9-]*(authorization|token|key|cookie|secret)[A-Za-z0-9-]*)\s*:\s*\S.*", re.I
)
_TOKEN_SHAPES = (
    re.compile(
        r"(sk-|sk_|ghp_|gho_|ghu_|ghs_|github_pat_|xox[baprs]-|glpat-|AKIA)[A-Za-z0-9_\-]{16,}"
    ),
    re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"),
    re.compile(r"(?i)(bearer|basic|token)\s+(?!\$\{)[^\s\"']{8,}"),
)


_AUTH_SCHEME = re.compile(r"(?i)\s*((bearer|basic|token)\s+)?")


def _is_reference(value: Any) -> bool:
    """`${VAR}`, or a value built only from references, like `Bearer ${VAR}`."""
    if not isinstance(value, str) or not _REFERENCE.search(value):
        return False
    rest = _REFERENCE.sub("", value)
    return bool(_AUTH_SCHEME.fullmatch(rest.replace(":", " ")))


class _Redactor:
    def __init__(self) -> None:
        self.found = False

    def secret(self) -> str:
        self.found = True
        return SECRET

    def walk(self, value: Any, key: str | None = None) -> Any:
        if isinstance(value, dict):
            return {k: self._field(k, v) for k, v in value.items()}
        if isinstance(value, list):
            return self._args(value) if key == "args" else [self.walk(v) for v in value]
        if isinstance(value, str):
            return self._string(value)
        return value

    def _field(self, key: str, value: Any) -> Any:
        if key in _SECRET_MAPS and isinstance(value, dict):
            return {k: v if _is_reference(v) else self.secret() for k, v in value.items()}
        return self.walk(value, key)

    def _args(self, args: list[Any]) -> list[Any]:
        out: list[Any] = []
        hide_next = False
        for arg in args:
            if hide_next and not _is_reference(arg):
                out.append(self.secret())
            elif isinstance(arg, str) and (m := _SECRET_FLAG_VALUE.fullmatch(arg)):
                self.found = True
                out.append(f"{m.group(1)}={SECRET}")
            elif (
                isinstance(arg, str)
                and (m := _SECRET_PAIR.fullmatch(arg))
                and not _is_reference(m.group("value"))
            ):
                self.found = True
                out.append(f"{m.group('name')}={SECRET}")
            else:
                out.append(self.walk(arg))
            hide_next = isinstance(arg, str) and bool(_SECRET_FLAG.fullmatch(arg))
        return out

    def _string(self, value: str) -> str:
        if _is_reference(value):
            return value
        if any(shape.fullmatch(value) for shape in _TOKEN_SHAPES):
            return self.secret()
        if m := _HEADER_ARG.fullmatch(value):
            self.found = True
            return f"{m.group(1)}: {SECRET}"
        if value.startswith(("http://", "https://")):
            return self._url(value)
        for shape in _TOKEN_SHAPES:  # a token inside a longer string
            value, count = shape.subn(SECRET, value)
            if count:
                self.found = True
        return value

    def _url(self, url: str) -> str:
        parts = urlsplit(url)
        netloc = parts.netloc
        if "@" in netloc:
            self.found = True
            netloc = f"{SECRET}@{netloc.rsplit('@', 1)[1]}"
        query = []
        for pair in parts.query.split("&") if parts.query else []:
            name, sep, val = pair.partition("=")
            if sep and _SECRET_PARAM.fullmatch(unquote_plus(name)) and not _is_reference(val):
                pair = f"{name}={self.secret()}"
            query.append(pair)
        return urlunsplit((parts.scheme, netloc, parts.path, "&".join(query), parts.fragment))


def redact(value: Any) -> tuple[Any, bool]:
    """Return a redacted copy of `value` and whether any secret was removed."""
    redactor = _Redactor()
    result = redactor.walk(value)
    return result, redactor.found


def redact_text(text: str) -> str:
    """Hide token-shaped parts of free text, such as a client command's output."""
    for shape in _TOKEN_SHAPES:
        text = shape.sub(SECRET, text)
    return text


# In free text: `NAME=value` or `name: value` whose name says secret, and a URL's user:password.
_LINE_PAIR = re.compile(
    rf"(?<![A-Za-z0-9_.-])(?P<name>[A-Za-z0-9_.-]*{_SECRET_WORD}[A-Za-z0-9_.-]*)"
    r"(?P<sep>\s*[:=]\s*)(?P<value>\S.*)",
    re.I,
)
_URL_USER = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^\s/@]+@")


def redact_line(line: str) -> str:
    """Hide secrets in one line of free text, such as an instruction file: token shapes, a
    URL's user and password, and the rest of the line after a secret-looking name and `=` or
    `:`. A few harmless words may be hidden too."""
    line = _URL_USER.sub(lambda m: f"{m.group(1)}{SECRET}@", line)
    line = redact_text(line)
    m = _LINE_PAIR.search(line)
    if m and not _is_reference(m.group("value")) and m.group("value") != SECRET:
        line = f"{line[: m.start('value')]}{SECRET}"
    return line


def masked_command(command: list[str]) -> list[str]:
    """A client command as the page, the change record and the log keep it: an argument that
    holds an entry as JSON (`claude mcp add-json <name> <json>`) is redacted. The command that
    runs still carries the real values."""
    out = []
    for arg in command:
        try:
            value = json.loads(arg)
        except ValueError:
            value = None
        out.append(json.dumps(redact(value)[0]) if isinstance(value, dict) else arg)
    return out
