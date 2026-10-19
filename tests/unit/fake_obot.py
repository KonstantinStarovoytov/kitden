"""A fake Obot v0.26.3 for tests: keys, `/api/me` and vMCPs in memory.

It answers the read calls `kitden.gateway_api.ObotClient` makes on 127.0.0.1 in a thread.
No network, no real gateway. Error bodies are plain
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
        self.entries: dict[str, dict] = {}  # catalog entries Kitden created, by id
        self.profiles = [{"name": "default", "subjects": [{"type": "obotGroup", "id": "admin"}]}]
        self.profiles_kept = True  # a PUT wrote the profiles back unchanged
        self.vmcp_writes = 0
        self.calls: list[str] = []
        self.forbidden = False  # the key's role may not read vMCPs (403)
        self.forbid_writes = False  # the key's user is not an administrator (403 on entries)
        self.fail_vmcp_write = False  # PUT on the vMCP answers 500
        # PUTs on the vMCP that answer 409, counted from 1: the real Obot does this when its own
        # controller updated the vMCP status between the handler's read and write (v0.26.3).
        self.conflicts: set[int] = set()
        self.always_conflict = False
        self.vmcp_puts = 0
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
        entry = f"e{len(self.entries) + 1}"
        self.entries[entry] = {"id": entry, "manifest": manifest, "editable": False}
        self.components.append(self._component(name, entry))

    def held_names(self) -> list[str]:
        return [c["name"] for c in self.components]

    def _component(self, name: str, entry: str) -> dict:
        return {
            "id": f"c{len(self.components) + 1}",
            "name": name,
            "mcpCatalogID": "default",
            "mcpServerCatalogEntryID": entry,
            "catalogEntry": {"manifest": self.entries[entry]["manifest"]},
        }

    def _vmcp(self) -> dict:
        return {
            "id": self.vmcp_id,
            "displayName": "work",
            "description": "",
            "components": self.components,
            "profiles": self.profiles,
            "userID": "3",
            "status": {},
        }

    def _put_vmcp(self, manifest: dict) -> tuple[int, str]:
        """The real Update: components are matched to catalog entries, snapshots reloaded."""
        self.vmcp_puts += 1
        if self.always_conflict or self.vmcp_puts in self.conflicts:
            return 409, (
                f'Operation cannot be fulfilled on vmcps.obot.obot.ai "{self.vmcp_id}": the object '
                "has been modified; please apply your changes to the latest version and try again"
            )
        if self.fail_vmcp_write:
            return 500, "failed to update VMCP"
        if manifest.get("profiles") != self.profiles:
            self.profiles_kept = False
        rebuilt = []
        for component in manifest.get("components", []):
            entry = component.get("mcpServerCatalogEntryID")
            if entry not in self.entries:
                return 400, f"invalid VMCP manifest: catalog entry {entry} not found"
            rebuilt.append(
                {
                    **self._component(component["name"], entry),
                    **{k: v for k, v in component.items() if k == "id"},
                }
            )
        self.components = rebuilt
        self.vmcp_writes += 1
        return 200, ""

    def _create_entry(self, manifest: dict) -> tuple[int, dict | str]:
        """The real CreateEntry: a remote entry needs an http(s) fixedURL that is not local."""
        remote = manifest.get("remoteConfig") or {}
        url = remote.get("fixedURL", "")
        if manifest.get("runtime") != "remote" or not url.startswith(("http://", "https://")):
            return (
                400,
                "failed to validate entry manifest: either fixedURL, hostname, or urlTemplate "
                "must be provided",
            )
        host = urlsplit(url).hostname or ""
        if host in ("localhost", "127.0.0.1", "::1") or host.startswith(("10.", "192.168.")):
            return (
                400,
                "failed to validate entry manifest: fixedURL: localhost and private addresses "
                "are not allowed",
            )
        entry = f"default-{manifest['name'].lower().replace(' ', '-')}-{len(self.entries) + 1:04x}"
        self.entries[entry] = {"id": entry, "manifest": manifest, "editable": True}
        return 201, {"id": entry, "manifest": manifest, "editable": True}

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

            def _body(self) -> dict:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                return json.loads(raw) if raw else {}

            def _route(self, method: str) -> None:
                path = urlsplit(self.path).path
                fake.calls.append(f"{method} {path}")
                if self.headers.get("Authorization") != f"Bearer {fake.key}":
                    self._send(401, "unauthorized", text=True)
                elif method == "GET" and path == "/api/me":
                    self._send(200, {"id": "3", "username": "me", "role": 8, "effectiveRole": 8})
                elif method == "GET" and path == "/api/mcp-catalogs":
                    self._send(200, {"items": [{"id": "default", "displayName": "Default"}]})
                elif path == f"/api/vmcps/{fake.vmcp_id}":
                    if fake.forbidden:
                        self._send(403, "forbidden", text=True)
                    elif fake.odd_shape:
                        self._send(200, {"surprise": True})
                    elif method == "GET":
                        self._send(200, fake._vmcp())
                    elif method == "PUT":
                        status, text = fake._put_vmcp(self._body())
                        self._send(status, fake._vmcp()) if status == 200 else self._send(
                            status, text, text=True
                        )
                    else:
                        self._send(405, "method not allowed", text=True)
                elif path.startswith("/api/vmcps/"):
                    name = path.rsplit("/", 1)[-1]
                    self._send(404, f'VMCP.obot.obot.ai "{name}" not found', text=True)
                elif method == "POST" and path == "/api/mcp-catalogs/default/entries":
                    if fake.forbid_writes:
                        self._send(403, "forbidden", text=True)
                        return
                    status, body = fake._create_entry(self._body())
                    self._send(status, body, text=isinstance(body, str))
                elif method == "DELETE" and path.startswith("/api/mcp-catalogs/default/entries/"):
                    entry = path.rsplit("/", 1)[-1]
                    if fake.forbid_writes:
                        self._send(403, "forbidden", text=True)
                    elif entry not in fake.entries:
                        self._send(
                            404,
                            f'MCPServerCatalogEntry.obot.obot.ai "{entry}" not found',
                            text=True,
                        )
                    elif not fake.entries[entry]["editable"]:
                        self._send(
                            400, "entry is not editable and cannot be manually deleted", text=True
                        )
                    else:
                        del fake.entries[entry]
                        fake.components = [
                            c for c in fake.components if c["mcpServerCatalogEntryID"] != entry
                        ]
                        self._send(204, "", text=True)
                else:
                    self._send(404, "404 page not found", text=True)

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def do_PUT(self):
                self._route("PUT")

            def do_DELETE(self):
                self._route("DELETE")

        return Handler
