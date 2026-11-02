"""A local MCP server that signs in through the browser, for tests: never a real account.

It serves the MCP authorization flow (spec 2026-07-28, checked 2026-11-02): a 401 that names its
protected resource metadata, that metadata, authorization server metadata, dynamic client
registration, an authorize page that redirects at once, and a token endpoint for the code (with
PKCE) and refresh grants. `/mcp` answers like a streamable HTTP MCP server to a live token.
"""

import base64
import hashlib
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx


class FakeOAuth(ThreadingHTTPServer):
    def __init__(
        self,
        *,
        no_registration=False,
        deny=False,
        refuse_refresh=False,
        rotate_refresh=False,
        expires_in=3600,
        no_refresh_token=False,
        token_error_body=None,
    ):
        self.no_registration = no_registration
        self.deny = deny
        self.refuse_refresh = refuse_refresh
        self.rotate_refresh = rotate_refresh
        self.expires_in = expires_in
        self.no_refresh_token = no_refresh_token
        self.token_error_body = token_error_body
        self.issued: set[str] = set()  # live access tokens
        self.refresh_tokens: set[str] = set()
        self.refreshes = 0
        self.codes: dict[str, str] = {}  # code → code_challenge
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlsplit(self.path).path
                base = fake.base
                if path == "/.well-known/oauth-protected-resource" or path.startswith(
                    "/.well-known/oauth-protected-resource/"
                ):
                    return self.json(
                        200, {"resource": fake.url, "authorization_servers": [f"{base}/"]}
                    )
                if path == "/.well-known/oauth-authorization-server":
                    meta = {
                        "issuer": f"{base}/",
                        "authorization_endpoint": f"{base}/authorize",
                        "token_endpoint": f"{base}/token",
                        "response_types_supported": ["code"],
                        "code_challenge_methods_supported": ["S256"],
                    }
                    if not fake.no_registration:
                        meta["registration_endpoint"] = f"{base}/register"
                    return self.json(200, meta)
                if path == "/authorize":
                    query = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                    back = {"state": query.get("state", "")}
                    if fake.deny:
                        back["error"] = "access_denied"
                    else:
                        code = secrets.token_urlsafe(16)
                        fake.codes[code] = query.get("code_challenge", "")
                        back["code"] = code
                    self.send_response(302)
                    self.send_header("Location", f"{query['redirect_uri']}?{urlencode(back)}")
                    self.send_header("Content-Length", "0")
                    return self.end_headers()
                return self.json(405 if path == "/mcp" else 404, None)

            def do_DELETE(self):
                self.json(405, None)

            def do_POST(self):
                path = urlsplit(self.path).path
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if path == "/register":
                    if fake.no_registration:
                        return self.json(404, None)
                    body = json.loads(raw)
                    return self.json(
                        201,
                        {
                            **body,
                            "client_id": "client-" + secrets.token_hex(4),
                            "token_endpoint_auth_method": "none",
                        },
                    )
                if path == "/token":
                    return self.token({k: v[0] for k, v in parse_qs(raw.decode()).items()})
                if path == "/mcp":
                    return self.mcp(raw)
                return self.json(404, None)

            def token(self, form):
                if fake.token_error_body is not None:
                    data = fake.token_error_body.encode()
                    self.send_response(400)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    return self.wfile.write(data)
                if form.get("grant_type") == "authorization_code":
                    challenge = fake.codes.pop(form.get("code", ""), None)
                    digest = hashlib.sha256(form.get("code_verifier", "").encode()).digest()
                    if challenge is None or challenge != base64.urlsafe_b64encode(
                        digest
                    ).decode().rstrip("="):
                        return self.json(400, {"error": "invalid_grant"})
                    return self.json(200, fake.new_tokens())
                if form.get("grant_type") == "refresh_token":
                    fake.refreshes += 1
                    given = form.get("refresh_token", "")
                    if fake.refuse_refresh or given not in fake.refresh_tokens:
                        return self.json(400, {"error": "invalid_grant"})
                    if fake.rotate_refresh:
                        fake.refresh_tokens.discard(given)
                    tokens = fake.new_tokens(refresh=fake.rotate_refresh)
                    return self.json(200, tokens)
                return self.json(400, {"error": "unsupported_grant_type"})

            def mcp(self, raw):
                given = (self.headers.get("Authorization") or "").removeprefix("Bearer ")
                if given not in fake.issued:
                    self.send_response(401)
                    meta = f"{fake.base}/.well-known/oauth-protected-resource"
                    self.send_header("WWW-Authenticate", f'Bearer resource_metadata="{meta}"')
                    self.send_header("Content-Length", "0")
                    return self.end_headers()
                body = json.loads(raw)
                if "id" not in body:  # a notification
                    return self.json(202, None)
                if body["method"] == "initialize":
                    version = body["params"]["protocolVersion"]
                    info = {"name": "fake", "version": "1"}
                    reply = {
                        "protocolVersion": version,
                        "capabilities": {"tools": {}},
                        "serverInfo": info,
                    }
                    return self.rpc(body["id"], reply)
                if body["method"] == "tools/list":
                    tool = {"name": "echo", "inputSchema": {"type": "object"}}
                    return self.rpc(body["id"], {"tools": [tool]})
                return self.rpc(body["id"], {})

            def rpc(self, id, result):
                self.json(200, {"jsonrpc": "2.0", "id": id, "result": result})

            def json(self, status, message):
                data = json.dumps(message).encode() if message is not None else b""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        super().__init__(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def new_tokens(self, refresh=True):
        access = "access-" + secrets.token_hex(8)
        self.issued.add(access)
        tokens = {"access_token": access, "token_type": "Bearer"}
        if self.expires_in is not None:
            tokens["expires_in"] = self.expires_in
        if refresh and not self.no_refresh_token:
            again = "refresh-" + secrets.token_hex(8)
            self.refresh_tokens.add(again)
            tokens["refresh_token"] = again
        return tokens

    @property
    def base(self):
        return f"http://127.0.0.1:{self.server_port}"

    @property
    def url(self):
        return f"{self.base}/mcp"

    def stop(self):
        self.shutdown()
        self.server_close()


def browser(url):
    """A stand-in browser: open the authorize page and give the address it sends the person
    back to (the redirect's Location), without following it."""
    answer = httpx.get(url, follow_redirects=False)
    return answer.headers["location"]


def back_query(location):
    """The query of the address the browser comes back to, as a flat dict."""
    return {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}
