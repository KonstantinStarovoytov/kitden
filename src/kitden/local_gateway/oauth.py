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
import logging
import sys
from urllib.parse import parse_qs, urlsplit

import anyio.to_thread
import httpx2
from mcp.client.auth import (
    AuthorizationCodeResult,
    OAuthClientProvider,
    OAuthFlowError,
    OAuthRegistrationError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from mcp.shared.auth_utils import calculate_token_expiry

from kitden import sign_in
from kitden.local_gateway import keychain
from kitden.sign_in import SignIn, SignIns

SECONDS = 10  # for each request of the flow; the person in the browser has sign_in.TIMEOUT

# The HTTP library logs each request with its full address, and the MCP client logs a failed
# sign-in with its exception, which may hold a token response; an address may hold a token too.
# Kitden says its own plain words instead, on the page and in the gateway.
for _logger in ("httpx2", "mcp.client"):
    logging.getLogger(_logger).setLevel(logging.CRITICAL)


class CannotSignIn(Exception):
    """The server offers sign-in, but Kitden cannot register as its client."""


class _Denied(Exception):
    """The browser came back without a code."""


class _NoBrowser(Exception):
    """The browser could not be opened."""


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


def initialize_body() -> dict:
    """One MCP `initialize` request, as the access check sends it."""
    from kitden.changes.actions import MCP_VERSION  # the page has it loaded; the gateway not

    return {
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
    ValueError with the reason when it fails before the browser. A second start while one runs
    joins it, so one press opens one browser tab."""
    if record.starting is not None and not record.starting.done():
        return await asyncio.shield(record.starting)
    record.starting = asyncio.ensure_future(_start(record, redirect_uri, open_browser))
    return await asyncio.shield(record.starting)


async def _start(record: SignIn, redirect_uri: str, open_browser) -> None:
    if record.task is not None and not record.task.done():
        cancel(record)
        await asyncio.wait({record.task})
    record.state, record.reason, record.cancelled = "new", None, False
    record.flow_state = None
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
        if await asyncio.to_thread(open_browser, url) is False:
            raise _NoBrowser()
        record.state = "waiting"
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
                    json=initialize_body(),
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
    except _NoBrowser:
        fail = sign_in.NO_BROWSER
    except (OAuthRegistrationError, OAuthFlowError):
        # Before the browser: Kitden cannot register, or the server's metadata is not what the
        # spec asks. A token then, not a dead end. After it: the sign-in did not finish.
        from kitden.changes.actions import SIGN_IN_LATER

        if not opened.is_set():
            record.state, record.reason = "failed", SIGN_IN_LATER.format(name=record.name)
            return CannotSignIn(record.reason)
    except Exception:  # noqa: BLE001, S110 - its text may hold a token; the reason says it
        pass
    record.state, record.reason = "failed", fail
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


# The gateway: a sign-in kept in the Keychain ------------------------------------------------

# Never sent: a stored sign-in has its client already, and the gateway never opens a browser.
NO_REDIRECT = "http://127.0.0.1/sign-in/done"


class SignedOut(Exception):
    """The stored sign-in no longer works: the server wants the person to sign in again."""


class KeychainStorage:
    """The SDK's token storage for the gateway: the one Keychain item `<server>/sign-in`. A
    refresh writes the new tokens back; `raw` is the item as it was read."""

    def __init__(self, name: str, ref: dict, run: keychain.Runner | None = None) -> None:
        self.name, self.ref, self.run = name, ref, run or keychain.run_security
        self.raw: str | None = None
        self.expires_at: float | None = None
        self.tokens: OAuthToken | None = None
        self.client: OAuthClientInformationFull | None = None

    async def read(self) -> str | None:
        return await anyio.to_thread.run_sync(keychain.read, self.ref, self.run)

    async def get_tokens(self) -> OAuthToken | None:
        self.raw = await self.read()
        data = json.loads(self.raw) if self.raw else {}
        self.expires_at = data.get("expires_at")
        self.tokens = OAuthToken.model_validate(data["tokens"]) if data.get("tokens") else None
        client = data.get("client")
        self.client = OAuthClientInformationFull.model_validate(client) if client else None
        return self.tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self.client

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self.tokens = tokens
        secret = secret_of(tokens, self.client)
        try:
            server, _, key = self.ref["keychain"].rpartition("/")
            await anyio.to_thread.run_sync(keychain.store, server, key, secret, self.run)
            self.raw = secret
        except keychain.KeychainError:
            print(f"Kitden could not save the new sign-in of {self.name}.", file=sys.stderr)

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self.client = client_info


class StoredSignIn(OAuthClientProvider):
    """The SDK's OAuth client on a stored sign-in. It refreshes before the token ends; when
    only a new sign-in would help, it sets `signed_out` and raises SignedOut."""

    def __init__(self, name: str, url: str, ref: dict, run: keychain.Runner | None = None):
        self.storage = KeychainStorage(name, ref, run)
        self.signed_out = False

        async def redirect(_: str) -> None:
            self.signed_out = True
            raise SignedOut()

        async def callback() -> AuthorizationCodeResult:
            raise SignedOut()

        super().__init__(
            server_url=url,
            client_metadata=client_metadata(NO_REDIRECT),
            storage=self.storage,
            redirect_handler=redirect,
            callback_handler=callback,
        )

    async def _initialize(self) -> None:
        # The SDK loads the stored tokens but not when they end (mcp 2.3.0, checked
        # 2026-11-02), so it would send an ended token and start a new sign-in on the 401
        # instead of refreshing first. test_expiry_restored_on_load pins this.
        await super()._initialize()
        self.context.token_expiry_time = self.storage.expires_at
