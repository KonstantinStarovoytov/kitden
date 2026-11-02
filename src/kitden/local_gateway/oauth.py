"""Browser sign-in through the MCP authorization flow, with the `mcp` SDK's OAuth client.

Facts this relies on (MCP authorization spec 2026-07-28 and `mcp` 2.3.0, checked 2026-11-02):
- `OAuthClientProvider` is an `httpx2.Auth`. On a 401 it finds the server's protected resource
  metadata and its authorization server, registers the client (dynamic registration), sends the
  person to the authorize page with PKCE S256 and `resource`, checks `state` and `iss`, and swaps
  the code for tokens. Kitden gives it a redirect handler (open the browser) and a callback
  handler (wait for Kitden's own `/sign-in/done`).
- Kitden has no public HTTPS address for a Client ID Metadata Document, so it registers
  dynamically; a server without that cannot be signed in to (`CannotSignIn`).
- Local clients register with `application_type: "native"`, the SDK's default.

The SDK's error text may hold a token response, so it is never passed on: every reason is one of
`kitden.sign_in`'s sentences.
"""

import asyncio
import json
from urllib.parse import parse_qs, urlsplit

import httpx2
from mcp.client.auth import AuthorizationCodeResult, OAuthClientProvider, OAuthRegistrationError
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from mcp.shared.auth_utils import calculate_token_expiry

from kitden import sign_in
from kitden.changes.actions import MCP_VERSION, SIGN_IN_LATER
from kitden.sign_in import SignIn, SignIns

SECONDS = 10  # for each request of the flow; the person in the browser has sign_in.TIMEOUT


class CannotSignIn(Exception):
    """The server offers sign-in, but Kitden cannot register as its client."""


class _Denied(Exception):
    """The browser came back without a code."""


class MemoryStorage:
    """The SDK's token storage, in memory: a sign-in waits here until Apply."""

    def __init__(self) -> None:
        self.tokens: OAuthToken | None = None
        self.client: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self.tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self.client

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self.client = client_info


def secret_of(tokens: OAuthToken, client: OAuthClientInformationFull | None) -> str:
    """The Keychain item's JSON: the tokens, when they end, and the client registration that a
    refresh needs."""
    return json.dumps(
        {
            "tokens": tokens.model_dump(mode="json", exclude_none=True),
            "expires_at": calculate_token_expiry(tokens.expires_in),
            "client": client.model_dump(mode="json", exclude_none=True) if client else None,
        }
    )


def client_metadata(redirect_uri: str) -> OAuthClientMetadata:
    return OAuthClientMetadata(
        client_name="Kitden",
        redirect_uris=[redirect_uri],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",  # noqa: S106 - a public client: no secret
    )


INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": MCP_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "kitden", "version": "1"},
    },
}


async def start(record: SignIn, redirect_uri: str, open_browser) -> None:
    """Start the flow; return once the browser shows the sign-in page. Raises CannotSignIn, or
    ValueError with the reason when it fails before the browser."""
    if record.task is not None and not record.task.done():
        record.cancelled = True
        record.task.cancel()
        await asyncio.wait({record.task})
    record.state, record.reason, record.cancelled = "new", None, False
    record.flow_state = None
    record.ended = asyncio.Event()
    record.code = asyncio.get_running_loop().create_future()
    opened = asyncio.Event()
    record.task = asyncio.create_task(_run(record, redirect_uri, open_browser, opened))
    shown = asyncio.create_task(opened.wait())
    await asyncio.wait({record.task, shown}, return_when=asyncio.FIRST_COMPLETED)
    shown.cancel()
    if opened.is_set():
        return
    problem = record.task.result()
    if isinstance(problem, CannotSignIn):
        raise problem
    raise ValueError(record.reason or sign_in.NOT_FINISHED.format(name=record.name))


async def _run(record: SignIn, redirect_uri: str, open_browser, opened: asyncio.Event):
    """The flow itself, as a task. Returns CannotSignIn when registration fails, else None."""
    storage = MemoryStorage()

    async def redirect(url: str) -> None:
        record.flow_state = parse_qs(urlsplit(url).query).get("state", [""])[0]
        record.state = "waiting"
        await asyncio.to_thread(open_browser, url)
        opened.set()

    async def callback() -> AuthorizationCodeResult:
        return await record.code

    provider = OAuthClientProvider(
        server_url=record.url,
        client_metadata=client_metadata(redirect_uri),
        storage=storage,
        redirect_handler=redirect,
        callback_handler=callback,
    )
    fail = sign_in.NOT_FINISHED.format(name=record.name)
    try:
        async with asyncio.timeout(sign_in.TIMEOUT):
            async with httpx2.AsyncClient(
                auth=provider, headers={"User-Agent": "kitden"}, timeout=SECONDS, trust_env=False
            ) as http:
                answer = await http.post(
                    record.url,
                    json=INITIALIZE,
                    headers={"Accept": "application/json, text/event-stream"},
                )
        if answer.status_code == 200 and storage.tokens is not None:
            record.access_token = storage.tokens.access_token
            record.secret = secret_of(storage.tokens, storage.client)
            record.state = "done"
            return None
    except TimeoutError:
        fail = sign_in.TIMED_OUT if opened.is_set() else fail
    except asyncio.CancelledError:
        fail = sign_in.CANCELLED if record.cancelled else fail
    except OAuthRegistrationError:
        if not opened.is_set():
            record.state, record.reason = "failed", SIGN_IN_LATER.format(name=record.name)
            record.ended.set()
            return CannotSignIn(record.reason)
    except Exception:  # noqa: BLE001, S110 - its text may hold a token; the reason says it
        pass
    record.state, record.reason = "failed", fail
    record.ended.set()
    return None


def finish(signins: SignIns, query: dict) -> bool:
    """The browser is back at Kitden's `/sign-in/done`: hand the code to the flow that waits for
    it, by its `state`. False when no flow waits for that state."""
    record = signins.by_state(str(query.get("state") or ""))
    if record is None or record.state != "waiting" or record.code is None or record.code.done():
        return False
    if query.get("code"):
        result = AuthorizationCodeResult(
            code=str(query["code"]), state=str(query["state"]), iss=query.get("iss")
        )
        record.code.set_result(result)
    else:
        record.code.set_exception(_Denied())
    return True


def cancel(record: SignIn) -> None:
    """Stop a running flow; its wait answers "cancelled"."""
    if record.task is not None and not record.task.done():
        record.cancelled = True
        record.task.cancel()


async def wait(record: SignIn) -> dict:
    """When the flow ends: {"state": "done"}, or "failed" / "cancelled" with the reason."""
    if record.state == "done":
        return {"state": "done"}
    if record.task is not None:
        await asyncio.wait({record.task})
    if record.state == "done":
        return {"state": "done"}
    state = "cancelled" if record.cancelled else "failed"
    return {
        "state": state,
        "detail": record.reason or sign_in.NOT_FINISHED.format(name=record.name),
    }
