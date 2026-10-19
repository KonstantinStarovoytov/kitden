"""A fake Obot v0.26.3 for tests: keys, `/api/me` and vMCPs in memory.

It answers the read calls `kitden.gateway_api.ObotClient` makes (specs/007-obot-gateway/
research.md) on 127.0.0.1 in a thread. No network, no real gateway. Error bodies are plain
text, as the real Obot answers them.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class FakeObot:
    def __init__(self, key="ok1-3-k1-rightsecret", vmcp_id="v1abc"):
        self.key = key
        self.vmcp_id = vmcp_id
        self.components: list[dict] = []
        self.calls: list[str] = []
        self.forbidden = False  # the key's role may not read vMCPs (403)
        self.odd_shape = False  # answers with a shape Kitden does not know
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> "FakeObot":
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
        return f"{self.url}/mcp-connect/{self.vmcp_id}"

    def hold(self, name: str, url: str | None = None, runtime: str = "remote") -> None:
        """Put a server on the vMCP, as an administrator would in the Obot UI."""
        manifest: dict = {"name": name, "runtime": runtime}
        if url:
            manifest["remoteConfig"] = {"fixedURL": url}
        self.components.append(
            {
                "id": f"c{len(self.components) + 1}",
                "name": name,
                "mcpCatalogID": "default",
                "mcpServerCatalogEntryID": f"e{len(self.components) + 1}",
                "catalogEntry": {"manifest": manifest},
            }
        )

    def _vmcp(self) -> dict:
        return {
            "id": self.vmcp_id,
            "displayName": "work",
            "components": self.components,
            "userID": "3",
            "status": {},
        }

    def _handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # quiet
                pass

            def _send(self, status: int, body, text: bool = False) -> None:
                raw = body.encode() if text else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "text/plain" if text else "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                path = urlsplit(self.path).path
                fake.calls.append(path)
                if self.headers.get("Authorization") != f"Bearer {fake.key}":
                    self._send(401, "unauthorized", text=True)
                elif path == "/api/me":
                    self._send(200, {"id": "3", "username": "me", "role": 8, "effectiveRole": 8})
                elif path == f"/api/vmcps/{fake.vmcp_id}":
                    if fake.forbidden:
                        self._send(403, "forbidden", text=True)
                    elif fake.odd_shape:
                        self._send(200, {"surprise": True})
                    else:
                        self._send(200, fake._vmcp())
                elif path.startswith("/api/vmcps/"):
                    name = path.rsplit("/", 1)[-1]
                    self._send(404, f'VMCP.obot.obot.ai "{name}" not found', text=True)
                else:
                    self._send(404, "404 page not found", text=True)

        return Handler
