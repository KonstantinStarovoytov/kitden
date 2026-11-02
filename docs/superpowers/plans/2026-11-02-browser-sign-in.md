# Browser Sign-in (Part 3b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A server that signs in through the browser gets a **Sign in** button in place of a dead
end. Kitden runs the MCP sign-in flow (OAuth 2.1 with PKCE) and catches the redirect on its own
page. The tokens wait in memory until Apply and then go to Keychain. The gateway refreshes them,
and when that fails the server shows "Needs sign-in" again.

**Architecture:**
- **Where the flow runs.** The `mcp` SDK's `OAuthClientProvider` does discovery, client
  registration, PKCE, the token exchange and refresh. Kitden gives it three things: a redirect
  handler that opens the browser, a callback handler that waits for Kitden's own `/sign-in/done`
  page, and a storage. On the page that storage is memory; in the gateway it is one Keychain item.
- **How the page starts it.** A batch preview answers a sign-in server with
  `needs.sign_in = <id>`, an id the server hands out for that address. The page never sends an
  address. The page starts the flow with that id and waits for it to finish.
- **How the tokens join the change.** The page re-asks the preview with `params.sign_in = <id>`,
  as 3a's `giveAccess` does with a token. The preview checks the server with the new access token
  and writes the entry with a Keychain reference.
- **Light and heavy halves.** `kitden/sign_in.py` holds the id registry and the entry shape and
  never imports the SDK. `kitden/local_gateway/oauth.py` holds the SDK work and is imported
  lazily, the way `load_proxy` loads the proxy.

**Tech Stack:**
- Python 3.13+, Starlette, `mcp` 2.3.0 (`mcp.client.auth.OAuthClientProvider`, `httpx2`).
- Vanilla JS modules, pytest, `node --test` with the fake DOM.

**Spec:** docs/superpowers/specs/2026-11-01-add-select-sign-in-design.md. This plan covers
Part 3 "Browser sign-in", the "needs access" state, the signal and motion tables, and settled
calls 4, 5 and 7.

**Facts checked 2026-11-02:**
- **MCP authorization spec 2026-07-28** (modelcontextprotocol.io/specification/latest/basic/authorization):
  - PKCE S256 and the RFC 8707 `resource` parameter are MUST.
  - Clients find the server's metadata through PRM: `resource_metadata` in WWW-Authenticate,
    then the well-known path.
  - A present `iss` must match (RFC 9207).
  - Client registration, in priority order: pre-registered, then Client ID Metadata Documents
    (needs a public HTTPS `client_id` URL), then Dynamic Client Registration. DCR is deprecated
    but stays a MAY for backward compatibility.
  - Local clients SHOULD register with `application_type: "native"`.
  - A loopback `http://127.0.0.1:<port>/...` redirect is shown as valid.
  - Refresh tokens must be kept confidential, and a client must not assume one is issued.
- **SDK `mcp` 2.3.0** (read from site-packages):
  - `OAuthClientProvider(server_url, client_metadata, storage, redirect_handler,
    callback_handler)` is an `httpx2.Auth`.
  - The `TokenStorage` protocol: `get_tokens` / `set_tokens` / `get_client_info` /
    `set_client_info`.
  - It does PRM and authorization-server discovery, DCR, and the `state` and `iss` checks.
    On a 401 it runs the whole flow again.
  - It refreshes before expiry only when `context.token_expiry_time` is set, and
    `_initialize()` does not set it from stored tokens.
  - `OAuthClientMetadata.application_type` defaults to "native".

## Rulings made while planning (the owner can overturn any)

1. **One Keychain item per server: `<server>/sign-in`.** It holds JSON
   `{"tokens": …, "expires_at": …, "client": …}` instead of three fixed keys.
   - **Why:** a refresh writes the token, the refresh token and the expiry together, and the
     client registration is needed for refresh too. One item means one atomic write.
   - **This replaces:** settled call 7.
2. **Registration is DCR only.**
   - **Why:** Kitden has no public HTTPS address to host a Client ID Metadata Document, and no
     pre-registered clients.
   - **When a server has no DCR:** Kitden finds out when the flow starts, before any browser
     opens. The card says `SIGN_IN_LATER` and shows the token field, so there is no dead end.
3. **Kitden opens the browser itself (`webbrowser.open`).**
   - **Why:** browsers block a tab that the page opens after an `await`.
   - **How:** the call is injectable, so tests and the demo pass stand-ins.
4. **Redirect address:** `http://127.0.0.1:<page port>/sign-in/done` (settled call 5).
   - The page cookie is `SameSite=Strict`, so a redirect from another site arrives without it.
     The path is therefore exempt from the cookie check.
   - It takes only a `state` that a running flow is waiting for; anything else gets the plain
     "did not finish" page.
5. **The tokens' expiry is restored on load.**
   - **How:** the gateway's provider subclass overrides the SDK's private `_initialize`.
   - **Safety:** a test against the real SDK pins this, so an SDK change fails the test instead
     of failing silently.
6. **Several gateway processes.** Each client runs its own gateway, and a rotating refresh token
   can make one process fail after another has refreshed. A process that finds itself signed
   out reads the Keychain item once more. If another process has written new tokens, it retries
   once with them.
7. **Signing a held server in again is a `gateway.sign_in` change.** It updates the Keychain
   item; the entry is unchanged, which the engine allows when a step carries Keychain items
   (engine.py line 501). Undo keeps the new tokens: the engine never restores an item that
   existed before, and the old tokens did not work anyway.
8. **Waiting is a held request.** `POST /api/sign-in/wait` returns when the flow ends. A flow
   ends by itself after 5 minutes.

## Global Constraints

- **Language.** UI text is in simple English. Code and docs are in English.
- **Change flow.**
  - Every gateway write goes through preview → Apply with a backup → verify → Undo.
  - Sign-in tokens live only in memory until Apply, then only in macOS Keychain.
  - A token is never in an answer, the page, a log, a change record or an error sentence.
- **SDK text.** Never pass an SDK exception's text on: it can hold a token response body. Every
  reason is one of the fixed sentences below.
- **Tests.** Sandbox homes, the fake Keychain (`KITDEN_SECURITY` stand-in), and the local fake
  OAuth server from Task 1. Never a real account, token or browser.
- **Exact words.**
  - Status: "Needs sign-in".
  - Buttons: "Sign in", "Cancel", "Try again".
  - Busy: "Waiting for browser…".
  - Result: "Signed in".
  - Bar: "{name} waits for sign-in. It stays in preview." (3a's `waitWords` already says this).
  - Reasons:
    - "{name} needs sign-in."
    - "{name} did not accept this sign-in."
    - "Sign-in was cancelled."
    - "{name} did not finish sign-in."
    - "Sign-in did not finish in 5 minutes."
    - "Sign in again: that sign-in is no longer here."
    - `SIGN_IN_LATER` (3a's words).
  - Gateway, after a failed refresh: "{name} needs sign-in again."
  - Callback page: "Signed in. You can close this tab." /
    "Sign-in did not finish. You can close this tab and try again in Kitden."
- **Colors.**
  - Needs you and refused: `--lamp-warn`.
  - Signed in: `--lamp-on`.
  - No red.
- **Motion.** Calm rules only:
  - busy ring after 150 ms (`busyWhile`);
  - check draw 320 ms;
  - lamp fade 400 ms;
  - refused words rise 4 px in 200 ms, plus one `shake()`;
  - reduced motion: everything lands at once.
- **Before each commit.** Run `uv run pytest -q`, `uv run ruff check .` and
  `node --test tests/frontend/*.test.mjs`.
- **Commits.** A short plain subject plus 1–3 lines, ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The owner closes the browser tab without signing in.** The card keeps waiting until
   Cancel. Cancel ends the flow ("Sign-in was cancelled."), and Try again starts a fresh one.
   (Task 1 `test_cancel_ends_the_wait`, Task 4 `cancel then try again`.)
2. **Two servers sign in at once.** Each callback reaches its own flow, keyed by `state`.
   (Task 1 `test_two_flows_get_their_own_callbacks`.)
3. **Kitden restarts between sign-in and Apply.** A preview with an id it no longer has says
   "Sign in again: that sign-in is no longer here." and the row waits again. Nothing crashes.
   (Task 2 `test_unknown_sign_in_id_waits_again`.)
4. **The owner denies access, or the callback has a wrong or unknown `state`.** The tab shows
   the plain "did not finish" page, the flow fails with "{name} did not finish sign-in.", and no
   value appears on the page. (Task 1 `test_denied_or_unknown_callback`, Task 2
   `test_callback_page_needs_no_cookie`.)
5. **No refresh token, or no `expires_in`.** The gateway uses the token until a 401, then shows
   "{name} needs sign-in again". (Task 3 `test_no_refresh_token_signs_out_on_401`.)

---

### Task 1: The sign-in flow against a fake OAuth server

**Files:**
- Create: `tests/unit/fake_oauth.py`, `src/kitden/sign_in.py`, `src/kitden/local_gateway/oauth.py`
- Test: `tests/unit/test_sign_in_flow.py`

**Interfaces:**
- Produces, in `kitden/sign_in.py` (no SDK import):
  - `KEY = "sign-in"`, `TIMEOUT = 300`.
  - Reasons: `CANCELLED`, `NOT_FINISHED = "{name} did not finish sign-in."`,
    `TIMED_OUT`, `GONE`.
  - `@dataclass SignIn`: `id`, `url`, `name`, `state` ("new"|"waiting"|"done"|"failed"),
    `reason: str | None`, `access_token: str | None`, `secret: str | None` (the Keychain JSON).
    Its private fields hold the task, the `state` value from the authorization URL, and an
    `asyncio.Event`.
  - `class SignIns`:
    - `offer(url, name) -> str`: the same id for the same url until that sign-in is used or
      fails.
    - `get(id) -> SignIn | None`.
    - `by_state(state) -> SignIn | None`.
    - `signed(id, url) -> SignIn | None`: only when done and for that url.
    - `forget(id)`.
- Produces, in `kitden/local_gateway/oauth.py`:
  - `class CannotSignIn(Exception)`: no DCR, or registration refused; the message is
    `SIGN_IN_LATER`.
  - `async start(record, redirect_uri, open_browser) -> None`: returns once the browser is
    opened; raises `CannotSignIn`, or `ValueError(NOT_FINISHED)` for any other failure before
    the browser.
  - `finish(signins, query: dict) -> bool`: the callback. True when a waiting flow took the code.
  - `async wait(record) -> dict`: `{"state": "done"}`, or `{"state": "failed"|"cancelled",
    "detail": reason}`.
  - `cancel(record) -> None`.
- The client metadata:
  - `client_name="Kitden"`, `redirect_uris=[redirect_uri]`,
    `grant_types=["authorization_code", "refresh_token"]`, `response_types=["code"]`,
    `token_endpoint_auth_method="none"`.
  - `application_type` keeps the SDK default, "native".
- The flow:
  - One initialize POST (the 3a body, `User-Agent: kitden`) through
    `httpx2.AsyncClient(auth=provider)`.
  - A 200 after the flow means done.
  - The secret is `json.dumps({"tokens": OAuthToken json, "expires_at": float|None,
    "client": OAuthClientInformationFull json})`.

- [ ] **Step 1: Write `tests/unit/fake_oauth.py`**
  - **What it is:** `FakeOAuth(ThreadingHTTPServer)`, in the style of `FakeHttpServer` in
    test_local_gateway_proxy.py.
  - **Its paths:**
    - `/mcp`: 401 with `WWW-Authenticate: Bearer resource_metadata="<base>/.well-known/oauth-protected-resource"`
      unless the bearer is a live access token. With a live token it answers the initialize
      and `tools/list` (one tool, `echo`).
    - The PRM well-known path.
    - `/.well-known/oauth-authorization-server`, with `authorization_endpoint`,
      `token_endpoint` and `registration_endpoint`.
    - `/register`.
    - `/authorize`: a 302 to `redirect_uri?code=…&state=…`, or `?error=access_denied` when
      `deny`.
    - `/token`: the `authorization_code` grant (checks the PKCE verifier) and the
      `refresh_token` grant.
  - **Its flags:** `no_registration`, `deny`, `refuse_refresh`, `rotate_refresh`,
    `expires_in` (None leaves it out), `no_refresh_token`.
  - **What it records:** `issued` (the live access tokens) and `refreshes` (a count).
  - **`browser(url, client)`:** a stand-in browser for tests. It GETs the authorize URL without
    following redirects, then GETs the `Location` through `client`, a Starlette `TestClient`
    or httpx.

- [ ] **Step 2: Write the failing tests in `tests/unit/test_sign_in_flow.py`**
  - `test_sign_in_finishes`:
    - `start` calls `open_browser` with the fake's authorize URL, which carries
      `code_challenge_method=S256` and `resource=`.
    - Feeding the redirect query to `finish` returns True.
    - `wait` gives `{"state": "done"}`.
    - `signed(id, url).access_token in fake.issued`.
    - The secret parses, with `expires_at` set.
  - `test_no_registration_cannot_sign_in`: `no_registration=True` → `CannotSignIn` with
    `SIGN_IN_LATER.format(name=...)`, and `open_browser` is never called.
  - `test_cancel_ends_the_wait`: `cancel` → `wait` gives
    `{"state": "cancelled", "detail": "Sign-in was cancelled."}`.
  - `test_denied_or_unknown_callback`:
    - `finish({"state": "nope", "code": "x"})` is False.
    - A real state with `error=access_denied` makes `wait` give "failed" with
      `NOT_FINISHED.format(name=…)`.
  - `test_two_flows_get_their_own_callbacks`: two records for two fakes, finished in reverse
    order; each ends done with its own fake's token.
  - `test_times_out`: monkeypatch `TIMEOUT` to 0.2 → "failed",
    "Sign-in did not finish in 5 minutes."
  - `test_no_secret_in_reasons`: with `deny` and with a token endpoint answering 400 with a
    body holding `SENTINEL_SECRET`, no reason or `str(error)` holds it.

- [ ] **Step 3: Run them**
  - Run: `uv run pytest tests/unit/test_sign_in_flow.py -q`
  - Expected: FAIL on import (`kitden.sign_in` missing).

- [ ] **Step 4: Implement `sign_in.py` and `oauth.py`**
  - **The redirect handler:** reads `state` from the URL's query, stores it on the record,
    calls `open_browser(url)` in a thread, and sets the "browser opened" event.
  - **The callback handler:** awaits the record's code future and returns
    `AuthorizationCodeResult(code, state, iss)`.
  - **`start`:** runs the flow as an `asyncio` task and waits for whichever comes first: the
    "browser opened" event or the task's end.
  - **Exceptions:** `OAuthRegistrationError`, or a missing `registration_endpoint`, becomes
    `CannotSignIn`. Anything else becomes `NOT_FINISHED`.
  - **The time limit:** the task runs under `asyncio.timeout(TIMEOUT)`.

- [ ] **Step 5: Run them**
  - Run: `uv run pytest tests/unit/test_sign_in_flow.py -q`
  - Expected: PASS.

- [ ] **Step 6: Commit** — "Run the MCP sign-in flow against a local fake server"

### Task 2: Sign-in in the preview, the page routes and Apply

**Files:**
- Modify: `src/kitden/changes/actions.py` (`NeedsAccess`, `check_access`, `local_move_steps`,
  `gateway_add_steps`), `src/kitden/local_gateway/keychain.py` (`references_in`),
  `src/kitden/web/app.py`, `src/kitden/web/security.py`, `src/kitden/demo/__init__.py`
- Test: `tests/unit/test_api_sign_in.py`, `tests/security/` (the existing middleware tests),
  `tests/unit/test_keychain.py`

**Interfaces:**
- Consumes: Task 1's `SignIns`, `start`, `finish`, `wait`, `cancel`.
- Produces:
  - `NeedsAccess(server, kind, fields, refused=False, url=None)`.
    - Sign-in words: "{server} needs sign-in."; refused: "{server} did not accept this
      sign-in."
    - `SIGN_IN_LATER` now comes only from `CannotSignIn`.
  - `local_move_steps(..., signed_in=None)` and `gateway_add_steps(..., signed_in=None)`,
    where `signed_in: SignIn | None`.
    - The check runs with `Authorization: Bearer <access_token>` added to a copy of the entry.
    - The entry written has `"sign_in": {"keychain": "<name>/sign-in"}`, and
      `KeychainItem(name, KEY, secret)` is appended to the server step's `keychain`.
  - `references_in(entry)` also returns `entry["sign_in"]` when it is a reference.
    `resolve_entry` leaves it alone.
  - In `_batch`, a sign-in `NeedsAccess` gets `answer["sign_in"] = signins.offer(error.url,
    error.server)`.
  - `_given_sign_in(params) -> SignIn | None`: `params["sign_in"]` must be a done record for
    the row's url, else `NeedsAccess(..., kind="sign-in")` with the reason
    "Sign in again: that sign-in is no longer here."
  - Routes:
    - `POST /api/sign-in/start {id}` → `{}`; 422 `{detail, cannot: true}` (with
      `SIGN_IN_LATER`); 422 `{detail}`; 404.
    - `POST /api/sign-in/wait {id}`.
    - `POST /api/sign-in/cancel {id}`.
    - `GET /sign-in/done`: plain HTML with the callback words, `Cache-Control: no-store`.
  - `create_app(..., open_browser=webbrowser.open)`.
  - The demo answers every sign-in route with `NOT_IN_DEMO`.

- [ ] **Step 1: Write the failing tests**
  - In `test_api_sign_in.py`, with a sandbox home, the fake Keychain, `FakeOAuth`, and the
    page `TestClient` at `http://127.0.0.1:47800` with its cookie:
  - `test_preview_offers_sign_in`: a catalog/marketplace add of the fake's `/mcp` → 422 with
    `needs.kind == "sign-in"`, `needs.sign_in` set, the reason "x needs sign-in.", and no url
    in the answer.
  - `test_sign_in_joins_the_preview_and_applies`:
    - The flow goes start → stand-in browser through the TestClient → wait "done".
    - A preview with `params.sign_in` → 200.
    - Apply verifies. `gateway.json` holds `{"keychain": "x/sign-in"}` and no token. The fake
      Keychain item holds the JSON.
    - The change record and `changes.log` hold no access token.
    - Undo removes the item.
  - `test_unknown_sign_in_id_waits_again`: `params.sign_in = "gone"` → 422, `needs`, with the
    reason "Sign in again: that sign-in is no longer here."
  - `test_refused_sign_in`: the fake forgets issued tokens before the preview → "x did not
    accept this sign-in."
  - `test_cannot_sign_in_offers_the_token_field`: `no_registration` → start answers 422
    `cannot: true`, `SIGN_IN_LATER`, and the browser stand-in is not called.
  - `test_callback_page_needs_no_cookie`:
    - `GET /sign-in/done?state=unknown` without the cookie → 200 with the "did not finish"
      words.
    - `/api/sign-in/start` without the cookie → 403.
  - `test_demo_refuses_sign_in`.
- In `test_keychain.py`: `test_references_in_counts_sign_in`. Also check that removing a held
  sign-in server (`remove_server_steps`) deletes its item.

- [ ] **Step 2: Run them**
  - Run: `uv run pytest tests/unit/test_api_sign_in.py tests/unit/test_keychain.py -q`
  - Expected: FAIL.

- [ ] **Step 3: Implement.** The `signins` registry is one per app.
  - **The redirect:** `redirect_uri = f"http://127.0.0.1:{port}/sign-in/done"`.
  - **Loading:** `oauth.py` is imported in a thread on the first `start`, as `load_proxy` does.
  - **The preview path:** the move branch and the add branch pass
    `signed_in=_given_sign_in(params)`.
  - **Once applied:** the record is forgotten.

- [ ] **Step 4: Run them**
  - Run: `uv run pytest -q`
  - Expected: PASS. Update the 3a tests that expected `SIGN_IN_LATER` as the sign-in
    `NeedsAccess` words to "needs sign-in".

- [ ] **Step 5: Commit** — "Sign in through the browser before Apply"

### Task 3: The gateway uses and refreshes stored sign-ins

**Files:**
- Modify: `src/kitden/local_gateway/oauth.py`, `src/kitden/local_gateway/proxy.py`
  (`_target`, `_serve`, `REFUSED`)
- Test: `tests/unit/test_local_gateway_proxy.py`

**Interfaces:**
- Produces, in `oauth.py`:
  - `class KeychainStorage(TokenStorage)`: reads and writes the one item through
    `keychain.read` / `keychain.store` in a thread. A failed write only logs
    "Kitden could not save the new sign-in of {name}." (through proxy's `_say` style, to stderr).
  - `class SignedOut(Exception)`.
  - `stored_auth(name, url, ref, run) -> OAuthClientProvider`: a subclass whose `_initialize`
    also sets `context.token_expiry_time` from `expires_at`, and whose redirect handler sets
    `signed_out = True` and raises `SignedOut`.
- Produces, in `proxy.py`:
  - `SIGNED_OUT = "{server} needs sign-in again."`.
  - `REFUSED` becomes "{server} turned down its access: its token is wrong or has ended."
- `_target`: for an entry with a `sign_in` reference, the `httpx2.AsyncClient` gets
  `auth=stored_auth(...)`.
- `_serve`: when the start fails and that auth has `signed_out`:
  - it re-reads the item once; if the item changed, it retries once (ruling 6);
  - otherwise it raises `UpstreamError(SIGNED_OUT.format(server=server))`.

- [ ] **Step 1: Write the failing tests**, with the fake Keychain holding a sign-in JSON for
  `FakeOAuth`:
  - `test_stored_sign_in_lists_tools`: `list_tools` returns `echo`.
  - `test_expired_token_refreshes_and_saves`: `expires_at` in the past → one refresh, the tools
    list, and the item now holds the new access token.
  - `test_refused_refresh_signs_out`: `refuse_refresh` → `UpstreamError` with "x needs sign-in
    again.", and the browser is never opened.
  - `test_no_refresh_token_signs_out_on_401`: `no_refresh_token`, with the token removed from
    `issued` → the same sentence.
  - `test_token_refreshed_elsewhere_is_picked_up`: `rotate_refresh`. Refresh once through a
    second provider (the "other process"), then start → works, with no sign-out.
  - `test_expiry_restored_on_load`: pins ruling 5 (`token_expiry_time` equals the stored
    `expires_at`).

- [ ] **Step 2: Run them**
  - Run: `uv run pytest tests/unit/test_local_gateway_proxy.py -q`
  - Expected: the new tests FAIL.

- [ ] **Step 3: Implement** as in Interfaces.

- [ ] **Step 4: Run them**
  - Run: `uv run pytest -q`
  - Expected: PASS.

- [ ] **Step 5: Commit** — "Let the gateway refresh sign-ins and say when one ends"

### Task 4: Sign in on the page

**Files:**
- Modify: `src/kitden/web/static/js/access-form.js`, `tray.js` (only if `giveAccess` needs a
  change), `dock.js`, `discovery.js`, `src/kitden/web/static/css/style.css`
- Test: `tests/frontend/gateway-add.test.mjs`, `tests/frontend/dock.test.mjs`,
  `tests/frontend/tray.test.mjs`

**Interfaces:**
- Consumes:
  - Task 2's routes;
  - 3a's `giveAccess(key, values)` → true | false | null;
  - `accessForm`;
  - `busyWhile`, `shake`, `animateTo`.
- Produces:
  - `signInForm(waits, onSigned)` in access-form.js, where `waits` has `{server, kind,
    sign_in, fields, reason}`. It returns `{node, start, signed, refuse}`.
  - **Its flow:**
    1. **Sign in** → `POST /api/sign-in/start`.
    2. The button becomes "Waiting for browser…" with the busy ring after 150 ms, and a
       **Cancel** button appears.
    3. → `POST /api/sign-in/wait`.
    4. When it is done → `onSigned(waits.sign_in)`.
  - **Its results:**
    - **Joined:** "Signed in" with the green lamp and a 320 ms check.
    - **failed or cancelled:** the reason in amber, which stays (`role="alert"`), one shake,
      and the button reads **Try again**.
    - **`cannot`:** the reason, and 3a's `accessForm` token field under it.
  - `openAccess(row)`: with `waits.kind === "sign-in" && waits.sign_in` it uses `signInForm`.
    `onSigned` is `(id) => giveAccess(row.key, { sign_in: id })`.
  - Dock: the waiting row's button reads "Sign in" for the sign-in kind ("Add token" otherwise)
    and opens `openAccess`.
  - Catalog details for a row known to need sign-in: **Sign in** adds the row to the tray
    (where it waits), then opens `openAccess` on that row and starts at once.

- [ ] **Step 1: Write the failing tests** with the fake DOM and the stand-in fetch:
  - `sign in joins the preview`: start → wait done → the preview is re-asked with
    `params.sign_in`; "Signed in" shows.
  - `cancel then try again`: Cancel posts `/api/sign-in/cancel`; the reason "Sign-in was
    cancelled." stays; the button says "Try again"; pressing it posts start again.
  - `cannot sign in shows the token field`: a start answering 422 `cannot` → the reason plus
    the "Access token" field.
  - `refused sign-in`: the re-preview answers needs refused → "x did not accept this sign-in.",
    and the form shakes.
  - Dock: `a sign-in row offers Sign in`.
  - Catalog: `Sign in in the details adds the row and starts`.

- [ ] **Step 2: Run them**
  - Run: `node --test tests/frontend/*.test.mjs`
  - Expected: the new tests FAIL.

- [ ] **Step 3: Implement.** Styles reuse `.access-form`, `.access-works` and `.access-why`.
  Nothing new beyond the Cancel button's place beside the busy button.

- [ ] **Step 4: Run them**
  - Run: `node --test tests/frontend/*.test.mjs`, then `uv run pytest -q`
    (test_page_words, test_contrast).
  - Expected: PASS.

- [ ] **Step 5: Commit** — "Add the Sign in step to the access form"

### Task 5: A held server whose sign-in ended, and the docs

**Files:**
- Modify:
  - `src/kitden/changes/actions.py` (`GATEWAY_SIGN_IN = "gateway.sign_in"`, `sign_in_steps`);
  - `src/kitden/web/app.py` (gateway view `needs`, `POST /api/sign-in/offer`, the
    `gateway.sign_in` branch);
  - `gateway.js` (`kitdenServer`);
  - `gateway-details.js`;
  - `tray.js` (`keyFor`);
  - the change words;
  - `docs/design.md`, `ROADMAP.md`.
- Test: `tests/unit/test_api_sign_in.py`, `tests/frontend/gateway.test.mjs`,
  `tests/frontend/gateway-details.test.mjs`

**Interfaces:**
- Consumes: `SIGNED_OUT` (Task 3), `tool_problems` (app.py), `signInForm` (Task 4).
- Produces:
  - Gateway view: each Kitden server whose `tool_problems[name] == SIGNED_OUT.format(server=name)`
    gets `"needs": "sign-in"`.
  - `POST /api/sign-in/offer {server}` → `{id}`, for a held server with a `sign_in` reference.
  - `sign_in_steps(home, server, signed: SignIn) -> list[Step]`: one settings step with the
    same entry and `keychain=[KeychainItem(server, KEY, signed.secret)]`. First it checks the
    server with the new token, and refuses with "{server} did not accept this sign-in."
  - The tray row: `{action: "gateway.sign_in", params: {server, sign_in}}`, with `keyFor`
    `signin:${server}`. Its change words: "Sign in to {server}" / done: "Signed in to {server}".
  - Map: a held block with `server.needs === "sign-in"` gets `lamp: "warn"` and meta
    "Needs sign-in"; pressing it opens its details.
  - Details: an amber "Needs sign-in" line with `signInForm`. When signed, it adds the
    `gateway.sign_in` row; Apply then refreshes the tools.

- [ ] **Step 1: Write the failing tests**
  - Python:
    - `test_signed_out_server_shows_needs`: `tool_problems` holds `SIGNED_OUT` → the view has
      `needs`.
    - `test_sign_in_again_updates_the_item`: offer → flow → preview `gateway.sign_in` → Apply →
      the item holds the new token and `gateway.json` is unchanged; Undo leaves the new token
      (ruling 7).
  - JS:
    - `held server that needs sign-in is amber`.
    - `details offer Sign in and add the row`.

- [ ] **Step 2: Run them**
  - Run: `uv run pytest tests/unit/test_api_sign_in.py -q` and `node --test tests/frontend/*.test.mjs`
  - Expected: FAIL.

- [ ] **Step 3: Implement**, then update the docs:
  - `docs/design.md`: a "Sign in" row in the access patterns; the words; the motion rows for
    Waiting for browser and Signed in.
  - `ROADMAP.md`: 3b done; "Not released yet" says servers that sign in through the browser
    can move into the gateway.

- [ ] **Step 4: Run all three checks**
  - Run: `uv run pytest -q`, `uv run ruff check .` and `node --test tests/frontend/*.test.mjs`
  - Expected: all PASS.

- [ ] **Step 5: Commit** — "Show servers whose sign-in ended and let them sign in again"
