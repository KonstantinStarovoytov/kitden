"""Talk to a MetaMCP gateway: sign in, list what it holds, add and remove a remote server.

MetaMCP 2.4.22 has no public management API; these are the tRPC calls its own web page makes
(docs/research/gateway-api-2026-10-19.md). Every answer is checked for the shape we expect, and
an unexpected one raises `GatewayError` so nothing is written on a guess. Error text never
carries a response body: bodies can hold header values and tokens.
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


def _json(raw: bytes) -> Any:
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []
