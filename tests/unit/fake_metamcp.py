"""A fake MetaMCP 2.4.22 for tests: sign-in, endpoints, namespaces and servers in memory.

It answers the calls `kitden.gateway_api` makes (research: gateway-api-2026-10-19.md) on
127.0.0.1 in a thread. No network, no real gateway.
"""

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

COOKIE = "better-auth.session_token"


class FakeMetaMcp:
    def __init__(self, email="me@example.com", password="right-password", endpoint="local"):
        self.email, self.password = email, password
        self.servers: dict[str, dict] = {}
        self.namespace = {"uuid": str(uuid.uuid4()), "name": endpoint, "description": None}
        self.in_namespace: list[str] = []
        self.endpoint = {
            "uuid": str(uuid.uuid4()),
            "name": endpoint,
            "namespace_uuid": self.namespace["uuid"],
        }
        self.sessions: set[str] = set()
        self.calls: list[str] = []
        self.fail_on: str | None = None  # a procedure name that answers 500
        self.odd_shape = False  # answers with a shape Kitden does not know
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    # Test helpers ------------------------------------------------------------------------

    def start(self) -> "FakeMetaMcp":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    @property
    def mcp_url(self) -> str:
        return f"{self.url}/metamcp/{self.endpoint['name']}/mcp"

    def hold(self, name: str, url: str, kind: str = "STREAMABLE_HTTP") -> str:
        """Put a server in the namespace, as a person would in the MetaMCP UI."""
        server = self._new_server({"name": name, "type": kind, "url": url})
        self.in_namespace.append(server["uuid"])
        return server["uuid"]

    def held_names(self) -> list[str]:
        return [self.servers[u]["name"] for u in self.in_namespace]

    def _new_server(self, data: dict) -> dict:
        server = {
            "uuid": str(uuid.uuid4()),
            "name": data["name"],
            "description": data.get("description"),
            "type": data.get("type", "STDIO"),
            "command": data.get("command"),
            "args": data.get("args", []),
            "env": data.get("env", {}),
            "url": data.get("url"),
            "bearerToken": data.get("bearerToken"),
            "headers": data.get("headers", {}),
            "user_id": None,
            "created_at": "2026-10-19T00:00:00Z",
        }
        self.servers[server["uuid"]] = server
        return server

    # Procedures ----------------------------------------------------------------------------

    def _procedure(self, name: str, data: dict) -> tuple[int, dict]:
        if name == "frontend.endpoints.list":
            return 200, {"success": True, "data": [self.endpoint]}
        if name == "frontend.mcpServers.list":
            return 200, {"success": True, "data": list(self.servers.values())}
        if name == "frontend.namespaces.get":
            if data.get("uuid") != self.namespace["uuid"]:
                return 200, {"success": False, "message": "Namespace not found"}
            servers = [{**self.servers[u], "status": "ACTIVE"} for u in self.in_namespace]
            return 200, {"success": True, "data": {**self.namespace, "servers": servers}}
        if name == "frontend.mcpServers.create":
            if any(s["name"] == data["name"] for s in self.servers.values()):
                return 200, {"success": False, "message": "Failed to create MCP server"}
            return 200, {"success": True, "data": self._new_server(data)}
        if name == "frontend.namespaces.update":
            if data.get("uuid") != self.namespace["uuid"]:
                return 200, {"success": False, "message": "Namespace not found"}
            wanted = data.get("mcpServerUuids", [])
            if any(u not in self.servers for u in wanted):
                return 200, {"success": False, "message": "One or more selected MCP servers"}
            self.in_namespace = list(wanted)
            return 200, {"success": True, "message": "Namespace updated successfully"}
        if name == "frontend.mcpServers.delete":
            if data.get("uuid") not in self.servers:
                return 200, {"success": False, "message": "MCP server not found"}
            del self.servers[data["uuid"]]
            self.in_namespace = [u for u in self.in_namespace if u != data["uuid"]]
            return 200, {"success": True, "message": "MCP server deleted successfully"}
        return 404, {"error": {"message": f'No procedure found on path "{name}"'}}

    def _handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # quiet
                pass

            def _json(self, status: int, body: dict, cookie: str | None = None) -> None:
                raw = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                if cookie:
                    self.send_header("Set-Cookie", f"{COOKIE}={cookie}; Path=/; HttpOnly")
                self.end_headers()
                self.wfile.write(raw)

            def _body(self) -> dict:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                return json.loads(raw) if raw else {}

            def _signed_in(self) -> bool:
                cookies = self.headers.get("Cookie") or ""
                for part in cookies.split(";"):
                    name, _, value = part.strip().partition("=")
                    if name == COOKIE and value in fake.sessions:
                        return True
                return False

            def _trpc(self, data: dict) -> None:
                name = urlsplit(self.path).path.rsplit("/", 1)[-1]
                fake.calls.append(name)
                if not self._signed_in():
                    self._json(
                        401,
                        {
                            "error": {
                                "message": "You must be logged in to access this resource",
                                "code": -32001,
                                "data": {"code": "UNAUTHORIZED", "httpStatus": 401},
                            }
                        },
                    )
                    return
                if fake.fail_on == name:
                    self._json(500, {"error": {"message": "boom"}})
                    return
                if fake.odd_shape:
                    self._json(200, {"result": {"data": {"surprise": True}}})
                    return
                status, body = fake._procedure(name, data)
                if status != 200:
                    self._json(status, body)
                else:
                    self._json(200, {"result": {"data": body}})

            def do_GET(self):
                if self.path.startswith("/trpc/frontend/"):
                    query = parse_qs(urlsplit(self.path).query)
                    data = json.loads(query["input"][0]) if "input" in query else {}
                    self._trpc(data)
                else:
                    self._json(404, {})

            def do_POST(self):
                path = urlsplit(self.path).path
                if path == "/api/auth/sign-in/email":
                    body = self._body()
                    if body.get("email") == fake.email and body.get("password") == fake.password:
                        token = str(uuid.uuid4())
                        fake.sessions.add(token)
                        self._json(200, {"user": {"email": fake.email}}, cookie=token)
                    else:
                        self._json(401, {"code": "INVALID_EMAIL_OR_PASSWORD"})
                elif path == "/api/auth/sign-out":
                    fake.sessions.clear()
                    self._json(200, {"success": True})
                elif path.startswith("/trpc/frontend/"):
                    self._trpc(self._body())
                else:
                    self._json(404, {})

        return Handler
