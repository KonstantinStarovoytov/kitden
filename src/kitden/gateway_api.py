"""Talk to a gateway: MetaMCP (sign in, list, add, remove) and Obot (list, feature 007).

MetaMCP 2.4.22 has no public management API; these are the tRPC calls its own web page makes
(checked 2026-10-19). Obot v0.26.3 takes an API key with the hidden `api` scope from
`obot login --scope api` (checked 2026-10-19). Every answer is checked for the shape we
expect, and an unexpected one raises `GatewayError` so nothing is written on a guess. Error
text never carries a response body: bodies can hold header values and tokens.
"""

import contextlib
import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlsplit

from kitden.model import Gateway

TIMEOUT_SECONDS = 5.0
NAME = re.compile(r"[A-Za-z0-9_-]+")
VERSION_CHECKED = "MetaMCP 2.4.22"
OBOT_VERSION_CHECKED = "Obot v0.26.3"


class GatewayError(Exception):
    """The gateway could not be reached, refused the sign-in, or answered unexpectedly."""


def gateway_name(name: str) -> str:
    """A name MetaMCP accepts: letters, digits, '-' and '_', no '__'."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-_")
    cleaned = re.sub(r"_{2,}", "_", cleaned)
    return cleaned or "server"


def endpoint_name(url: str) -> str:
    """`http://host/metamcp/<name>/mcp` -> `<name>`."""
    parts = urlsplit(url).path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "metamcp" and parts[1]:
        return parts[1]
    raise GatewayError("The gateway address is not a MetaMCP endpoint (…/metamcp/<name>/mcp)")


class MetaMcpClient:
    """One signed-in conversation with a MetaMCP gateway. Use it as a context manager."""

    def __init__(
        self,
        gateway: Gateway,
        env: Mapping[str, str] | None = None,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        if not gateway.managed:
            raise GatewayError("Add the sign-in email and password variable to this gateway first")
        parts = urlsplit(gateway.url)
        self.base = f"{parts.scheme}://{parts.netloc}"
        self.endpoint = endpoint_name(gateway.url)
        self.gateway = gateway
        self.env = os.environ if env is None else env
        self.timeout = timeout
        self._cookie: str | None = None
        self._namespace: dict | None = None

    def __enter__(self) -> "MetaMcpClient":
        self.sign_in()
        return self

    def __exit__(self, *exc) -> None:
        self.sign_out()

    # HTTP ----------------------------------------------------------------------------------

    def _request(self, method: str, path: str, body: dict | None = None) -> tuple[int, Any, str]:
        data = json.dumps(body).encode() if body is not None else None
        if not self.base.startswith(("http://", "https://")):
            raise GatewayError("The gateway address must be http or https")
        request = urllib.request.Request(self.base + path, data=data, method=method)  # noqa: S310 - checked above
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if self._cookie:
            request.add_header("Cookie", self._cookie)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - checked above
                cookie = response.headers.get("Set-Cookie", "")
                return response.status, _json(response.read()), cookie
        except urllib.error.HTTPError as error:
            return error.code, _json(error.read()), ""
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            reason = getattr(error, "reason", error)
            raise GatewayError(f"Could not reach the gateway at {self.base}: {reason}") from None

    def sign_in(self) -> None:
        var = self.gateway.login_password_env_var or ""
        password = self.env.get(var)
        if not password:
            raise GatewayError(f"Set {var} in the environment before starting Kitden")
        status, body, cookie = self._request(
            "POST",
            "/api/auth/sign-in/email",
            {"email": self.gateway.login_email, "password": password},
        )
        token = cookie.split(";", 1)[0] if cookie else ""
        if status != 200 or not token:
            raise GatewayError(
                f"The gateway refused the sign-in for {self.gateway.login_email} ({status})"
            )
        self._cookie = token

    def sign_out(self) -> None:
        if self._cookie:
            with contextlib.suppress(GatewayError):
                self._request("POST", "/api/auth/sign-out", {})
            self._cookie = None

    def _call(self, procedure: str, data: dict | None = None, mutation: bool = False) -> Any:
        path = f"/trpc/frontend/frontend.{procedure}"
        if mutation:
            status, body, _ = self._request("POST", path, data or {})
        else:
            query = f"?input={quote(json.dumps(data))}" if data is not None else ""
            status, body, _ = self._request("GET", path + query)
        if status != 200 or not isinstance(body, dict) or "result" not in body:
            raise GatewayError(f"The gateway answered {status} to {procedure}; nothing was changed")
        answer = body["result"].get("data") if isinstance(body["result"], dict) else None
        if not isinstance(answer, dict) or "success" not in answer:
            raise GatewayError(f"The gateway's answer to {procedure} has an unknown shape")
        if not answer["success"]:
            raise GatewayError(f"The gateway refused {procedure}: {answer.get('message', '')}")
        return answer.get("data")

    # What Kitden needs ---------------------------------------------------------------------

    def _namespace_with_servers(self) -> dict:
        if self._namespace is None:
            endpoints = self._call("endpoints.list")
            found = next((e for e in _list(endpoints) if e.get("name") == self.endpoint), None)
            if not found or not found.get("namespace_uuid"):
                raise GatewayError(f"The gateway has no endpoint named {self.endpoint}")
            self._namespace = {"uuid": found["namespace_uuid"]}
        data = self._call("namespaces.get", {"uuid": self._namespace["uuid"]})
        if not isinstance(data, dict) or not isinstance(data.get("servers"), list):
            raise GatewayError("The gateway's namespace answer has an unknown shape")
        self._namespace = {**self._namespace, **{k: data.get(k) for k in ("name", "description")}}
        return data

    def held(self) -> list[dict]:
        """Servers behind the endpoint: uuid, name, type and address (never headers)."""
        servers = self._namespace_with_servers()["servers"]
        return [
            {
                "uuid": s.get("uuid"),
                "name": s.get("name"),
                "type": s.get("type"),
                "url": s.get("url"),
            }
            for s in servers
            if isinstance(s, dict)
        ]

    def _set_servers(self, uuids: list[str]) -> None:
        assert self._namespace is not None
        self._call(
            "namespaces.update",
            {
                "uuid": self._namespace["uuid"],
                "name": self._namespace.get("name") or self.endpoint,
                "description": self._namespace.get("description") or "",
                "mcpServerUuids": uuids,
            },
            mutation=True,
        )

    def add(self, name: str, server: dict) -> str:
        """Create the server and put it behind the endpoint. Returns its uuid."""
        current = [s["uuid"] for s in self.held()]
        created = self._call("mcpServers.create", {"name": name, **server}, mutation=True)
        if not isinstance(created, dict) or not created.get("uuid"):
            raise GatewayError("The gateway did not return the new server; nothing was changed")
        try:
            self._set_servers([*current, created["uuid"]])
        except GatewayError:
            self._call("mcpServers.delete", {"uuid": created["uuid"]}, mutation=True)
            raise
        return created["uuid"]

    def remove(self, uuid: str) -> bool:
        """Take the server out of the endpoint and delete it. False if it was already gone."""
        current = [s["uuid"] for s in self.held()]
        if uuid in current:
            self._set_servers([u for u in current if u != uuid])
        try:
            self._call("mcpServers.delete", {"uuid": uuid}, mutation=True)
        except GatewayError as error:
            if "not found" in str(error).lower():
                return False
            raise
        return True


def vmcp_id(url: str) -> str:
    """`http://host/mcp-connect/<id>` -> `<id>`."""
    parts = urlsplit(url).path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "mcp-connect" and parts[1]:
        return parts[1]
    raise GatewayError("The gateway address is not an Obot connection (…/mcp-connect/<id>)")


class ObotClient:
    """Talk to an Obot gateway with the key from the environment variable the record names.

    Reading is one call, `GET /api/vmcps/<id>`: the components of the vMCP behind the stored
    address. Adding a remote server takes the administrator's path (checked 2026-10-19 against
    Obot v0.26.3 source, no reference docs exist): a catalog entry in the built-in catalog
    (`POST /api/mcp-catalogs/<catalog>/entries`), then the vMCP manifest written back with one
    more component (`PUT /api/vmcps/<id>`). Removing is the reverse. A key without the admin
    role gets 403 on the entry call, and nothing is written. The key never appears in a message.
    """

    def __init__(
        self,
        gateway: Gateway,
        env: Mapping[str, str] | None = None,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        if gateway.kind != "obot" or not gateway.key_env_var:
            raise GatewayError("Add the name of the Obot key variable to this gateway first")
        parts = urlsplit(gateway.url)
        self.base = f"{parts.scheme}://{parts.netloc}"
        self.vmcp = vmcp_id(gateway.url)
        self.gateway = gateway
        self.env = os.environ if env is None else env
        self.timeout = timeout

    def __enter__(self) -> "ObotClient":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def _request(self, method: str, path: str, body: dict | None = None) -> tuple[int, Any]:
        var = self.gateway.key_env_var or ""
        key = self.env.get(var)
        if not key:
            raise GatewayError(f"Set {var} in the environment before starting Kitden")
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method)  # noqa: S310 - http(s) checked on save
        request.add_header("Accept", "application/json")
        request.add_header("Authorization", f"Bearer {key}")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                return response.status, _json(response.read())
        except urllib.error.HTTPError as error:
            return error.code, None
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            reason = getattr(error, "reason", error)
            raise GatewayError(f"Could not reach the gateway at {self.base}: {reason}") from None

    def _refused(self, status: int, what: str) -> GatewayError:
        if status in (401, 403):
            return GatewayError(
                f"Obot refused the key for {what} ({status}); check its scope and role"
            )
        return GatewayError(f"Obot answered {status} to {what}; nothing else was changed")

    def _vmcp_manifest(self) -> dict:
        status, body = self._request("GET", f"/api/vmcps/{quote(self.vmcp)}")
        if status == 404:
            raise GatewayError(f"Obot has no connection named {self.vmcp}")
        if status != 200:
            raise self._refused(status, "the connection")
        if not isinstance(body, dict) or not isinstance(body.get("components"), list):
            raise GatewayError(
                f"Obot answered in an unexpected shape (checked against {OBOT_VERSION_CHECKED})"
            )
        return body

    def held(self) -> list[dict]:
        """Servers on the connection: name, kind (Obot's runtime) and address when it has one."""
        body = self._vmcp_manifest()
        held = []
        for component in body["components"]:
            if not isinstance(component, dict):
                continue
            entry = component.get("catalogEntry") or {}
            manifest = entry.get("manifest") if isinstance(entry, dict) else None
            manifest = manifest if isinstance(manifest, dict) else entry
            remote = manifest.get("remoteConfig") if isinstance(manifest, dict) else None
            held.append(
                {
                    "name": component.get("name"),
                    "type": manifest.get("runtime") if isinstance(manifest, dict) else None,
                    "url": remote.get("fixedURL") if isinstance(remote, dict) else None,
                    "uuid": component.get("mcpServerCatalogEntryID"),
                }
            )
        return held

    # Writing (the administrator's path) -------------------------------------------------

    MANIFEST_KEYS = ("displayName", "description", "icon", "toolSearch", "components", "profiles")

    def _write_components(self, body: dict, components: list[dict]) -> None:
        manifest = {k: body[k] for k in self.MANIFEST_KEYS if k in body}
        manifest["components"] = components
        status, _ = self._request("PUT", f"/api/vmcps/{quote(self.vmcp)}", manifest)
        if status != 200:
            raise self._refused(status, "changing the connection")

    def _catalog(self) -> str:
        status, body = self._request("GET", "/api/mcp-catalogs")
        if status != 200:
            raise self._refused(status, "the catalog")
        items = body.get("items") if isinstance(body, dict) else None
        ids = [i.get("id") for i in _list(items) if isinstance(i, dict) and i.get("id")]
        if not ids:
            raise GatewayError("Obot has no catalog to add the server to")
        return "default" if "default" in ids else ids[0]

    def add(self, name: str, server: dict) -> str:
        """Make the remote server a catalog entry and put it on the connection. Returns the
        entry id. `server` is `{type, url, headers?}`; header values become static, sensitive
        header configuration that Obot stores as a credential."""
        body = self._vmcp_manifest()
        catalog = self._catalog()
        manifest: dict = {
            "name": name,
            "shortDescription": "Added from Kitden",
            "description": "",
            "icon": "",
            "runtime": "remote",
            "remoteConfig": {"fixedURL": server["url"]},
        }
        headers = server.get("headers") or {}
        if headers:
            manifest["config"] = [
                {
                    "name": key,
                    "description": "",
                    "key": key,
                    "value": value,
                    "sensitive": True,
                    "required": True,
                    "usage": "header",
                }
                for key, value in headers.items()
            ]
        status, created = self._request(
            "POST", f"/api/mcp-catalogs/{quote(catalog)}/entries", manifest
        )
        if status == 403:
            raise GatewayError(
                "Only an Obot administrator can add servers; the key's user is not one (403)"
            )
        if status not in (200, 201):
            raise self._refused(status, "adding the server")
        entry = created.get("id") if isinstance(created, dict) else None
        if not entry:
            raise GatewayError("Obot did not return the new entry; nothing else was changed")
        component = {"name": name, "mcpCatalogID": catalog, "mcpServerCatalogEntryID": entry}
        try:
            self._write_components(body, [*body["components"], component])
        except GatewayError:
            self._request("DELETE", f"/api/mcp-catalogs/{quote(catalog)}/entries/{quote(entry)}")
            raise
        return entry

    def remove(self, entry: str) -> bool:
        """Take the server off the connection and delete its entry. False if already gone."""
        body = self._vmcp_manifest()
        kept = [c for c in body["components"] if c.get("mcpServerCatalogEntryID") != entry]
        catalog = next(
            (
                c.get("mcpCatalogID")
                for c in body["components"]
                if c.get("mcpServerCatalogEntryID") == entry
            ),
            None,
        )
        if len(kept) != len(body["components"]):
            self._write_components(body, kept)
        catalog = catalog or self._catalog()
        status, _ = self._request(
            "DELETE", f"/api/mcp-catalogs/{quote(catalog)}/entries/{quote(entry)}"
        )
        if status == 404:
            return False
        if status not in (200, 204):
            raise self._refused(status, "removing the server")
        return True


def _json(raw: bytes) -> Any:
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []
