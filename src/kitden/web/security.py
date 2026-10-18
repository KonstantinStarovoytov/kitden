"""Protects the local page (research R6, FR-037).

- Only Host 127.0.0.1:<port> or localhost:<port> (blocks DNS rebinding).
- A one-time start link with a random token sets an HttpOnly, SameSite=Strict session cookie.
- Every request needs that cookie.
- State-changing requests also need the exact same Origin, `Sec-Fetch-Site: same-origin` when
  sent, and the header `X-Tool-Request: 1`, so other websites cannot trigger them.
- No CORS headers; a strict Content-Security-Policy without inline scripts (FR-041).
"""

import secrets
from typing import Any

from starlette.datastructures import Headers, QueryParams
from starlette.responses import PlainTextResponse, RedirectResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Named per port: browsers share cookies across ports of one host (RFC 6265, section 8.5).
COOKIE = "kitden_session"
SAFE_METHODS = {"GET", "HEAD"}
SECURITY_HEADERS = {
    "content-security-policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'"
    ),
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cache-control": "no-store",
}


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, token: str, port: int) -> None:
        self.app = app
        self.token = token
        self.cookie = f"{COOKIE}_{port}"
        self.session = secrets.token_urlsafe(32)
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response = self._check(scope)
        send = self._with_headers(send)
        if response is not None:
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _check(self, scope: Scope) -> Response | None:
        headers = Headers(scope=scope)
        host = headers.get("host", "")
        if host not in self.hosts:
            return PlainTextResponse("Forbidden host.", status_code=403)

        method, path = scope["method"], scope["path"]
        given = QueryParams(scope.get("query_string", b"")).get("token")
        if path == "/" and method == "GET" and given is not None:
            if not secrets.compare_digest(given, self.token):
                return PlainTextResponse("Wrong or expired link.", status_code=401)
            redirect = RedirectResponse("/", status_code=303)
            redirect.set_cookie(
                self.cookie, self.session, httponly=True, samesite="strict", path="/"
            )
            return redirect

        cookie = _cookie(headers.get("cookie", ""), self.cookie)
        if cookie is None or not secrets.compare_digest(cookie, self.session):
            return PlainTextResponse("Open the link printed in the terminal.", status_code=401)

        origin = headers.get("origin")
        fetch_site = headers.get("sec-fetch-site")
        same_origin = f"http://{host}"
        if method not in SAFE_METHODS:
            if (
                origin != same_origin
                or fetch_site not in (None, "same-origin")
                or headers.get("x-tool-request") != "1"
            ):
                return PlainTextResponse("Request not allowed.", status_code=403)
        elif path == "/api/events" and (
            (origin is not None and origin != same_origin)
            or fetch_site not in (None, "same-origin")
        ):
            return PlainTextResponse("Request not allowed.", status_code=403)
        return None

    @staticmethod
    def _with_headers(send: Send) -> Send:
        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[Any] = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if not k.decode().lower().startswith("access-control-")
                ]
                headers += [(k.encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]
                message = {**message, "headers": headers}
            await send(message)

        return wrapped


def _cookie(header: str, name: str) -> str | None:
    for part in header.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return None
