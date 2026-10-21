# Part 5: Secrets have a lifecycle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gateway secrets live in the macOS Keychain and `gateway.json` keeps references; backups and records say when they hold a secret; and a remote server that needs OAuth can move into the gateway, with the page signing in once and the gateway only refreshing.

**Architecture:** One new module `src/kitden/local_gateway/keychain.py` wraps the `security` command (no library). A move writes references into `gateway.json` and keeps the values in memory on the previewed change until Apply stores them; the proxy resolves references when a server starts. The OAuth flow uses the MCP SDK's own client auth (`mcp.client.auth`): the page runs the browser flow at Apply, a Keychain-backed token storage keeps the tokens, and the proxy uses the same provider with the browser part refused.

**Tech Stack:** Python 3.13, the official MCP SDK 2.3 (`mcp.client.auth.oauth2`), httpx2 (the SDK's HTTP client), the macOS `security` command; pytest with a fake `security` on PATH.

**Spec:** `docs/superpowers/specs/2026-10-21-review-follow-up-design.md`, Part 5 (5.1 to 5.3). Master plan: `docs/superpowers/plans/2026-10-21-review-follow-up.md` (fixed names: `{"keychain": "<server>/<key>"}`, `store`, `read`, `delete`, `resolve_entry`; review focus 1, 2, 5).

## Global Constraints

- Code, comments, UI text and docs in simple English (`AGENTS.md`).
- `gateway.json` changes only through the engine; references replace values; the value never appears in a review, a record, a log, an error or stderr.
- Today's `gateway.json` (plain values, no references) keeps working unchanged.
- Tests use sandbox homes, a fake `security` command in the sandbox's `bin` and the fake MCP echo server; no real Keychain, no real network.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `node --test tests/frontend/*.test.mjs`. Commit subjects plain, no prefix.
- No new runtime dependency; the MCP SDK's auth client is already installed.
- A fact about `security`, the MCP authorization spec or GitHub's remote server is checked with the date in a comment.

## Decisions from the builder pass

Settled here so no task has to guess:

- `security` is run by its absolute path `/usr/bin/security`, never from PATH. An item is written
  with `security -i` reading the command line from stdin and the value as `-X <hex>`, so the value
  is never in the process list and needs no quoting; `find-generic-password -w` and
  `delete-generic-password` run with arguments. Exit code 44 means "not found". Task 1 checks
  these three facts by hand and writes the date.
- `tests/conftest.py` gets an autouse fixture `_never_the_real_keychain` that points
  `keychain.SECURITY` at a path that does not exist, and a `fake_keychain(tmp_path, monkeypatch)`
  fixture that installs the stand-in; a test that forgets the fake fails, it never touches the
  real Keychain.
- The OAuth callback is a one-shot `ThreadingHTTPServer` on `127.0.0.1:0`, not a route of the page
  (the page sits behind the token-guarded middleware and its port is not known when a client is
  registered). `page.py` is not modified.
- Undo of a move that updated an existing Keychain item keeps the new value (the old value is
  recorded nowhere, by this part's own rule) and the Undo result says
  `"<server>/<key> in your Keychain keeps the new value."`; an item the move created is deleted.
- Secrets inside `args` or a URL's query stay in `gateway.json` (spec 5.1 names env and header
  values only); the README says so in one line.
- "Clients that reached that server with their own OAuth keep nothing" needs no action: Kitden
  never reads or removes a client's own tokens.
- Values the spike cannot fix in advance (dynamic client registration, the loopback port the
  server accepts, refresh rotation, scopes) get RFC defaults in Tasks 7 and 8's tests; the spike's
  dated note amends those tests when GitHub differs.

## Review Focus

1. A `gateway.json` from before this part reads and runs exactly as before (Task 2 test `test_a_plain_entry_runs_unchanged`; the master's item 1).
2. The Keychain item is missing at start (deleted by hand): the server does not start and the gateway says `"Kitden could not read a secret of <server> from the Keychain."` on stderr and in the error result (Task 2 test `test_a_missing_keychain_item_gives_a_plain_sentence`).
3. The page restarted between preview and Apply of a move with secrets: Apply refuses with `"Review the change again."` and writes nothing (Task 3 test `test_apply_after_a_restart_asks_for_a_new_review`).
4. Two gateway processes refresh an OAuth token at once: the second waits for the lock and re-reads the token the first saved; neither revokes the other (Task 8 test `test_two_refreshes_take_turns`).
5. A `security` command that is missing or fails: the move's review is refused with `"Kitden could not reach the Keychain."` and no file changes (Task 3 test `test_a_failing_keychain_refuses_the_move_before_any_write`).

---

### Task 1: The Keychain module (5.1)

**Files:**
- Create: `src/kitden/local_gateway/keychain.py`
- Create: `tests/unit/fake_security.py` (a tiny `security` stand-in: a Python script written into `<sandbox>/bin/security` by a helper `install_fake_security(home) -> Path`, keeping items in `<sandbox>/fake-keychain.json`)
- Test: `tests/unit/test_keychain.py` (new)

**Interfaces:**
- Produces: `SERVICE = "kitden"`; `Runner = Callable[[list[str]], tuple[int, str]]`; `SECURITY = "/usr/bin/security"`; `run_security(args: list[str], stdin: str | None = None) -> tuple[int, str]` runs `[SECURITY, *args]` with `subprocess.run(capture_output=True, text=True, timeout=20)` and returns `(returncode, stdout)`; every public call takes `run: Runner = run_security`. `store(server: str, key: str, value: str, run=...) -> dict`: `security -i` with the line `add-generic-password -U -s kitden -a "<server>/<key>" -X <hex of the value>` on stdin (the value never in the process list) and returns `{"keychain": f"{server}/{key}"}`; raises `KeychainError("Kitden could not reach the Keychain.")` on a non-zero code; the exception text never holds the value. `read(ref: dict, run=...) -> str | None`: `find-generic-password -s kitden -a <account> -w`, `None` when the code is 44 (not found); `KeychainError` on other failures. `delete(ref, run=...) -> None`: `delete-generic-password`, quiet on not found. `is_reference(value) -> bool`: a dict with exactly the key `"keychain"` and a `str` value. `resolve_entry(entry: dict, run=...) -> dict`: a copy with every reference in `env` values and `headers` values replaced by `read`; a reference that reads `None` raises `KeychainError(f"Kitden could not read a secret of {server} from the Keychain.")` where `server` is the account's part before `/`; a plain entry comes back equal. `references_in(entry) -> list[dict]`.

- [ ] **Step 1: Check `security`'s flags** (`man security`, the `-U` update flag, the exit code for not found); write `# checked YYYY-MM-DD` in the module.
- [ ] **Step 2: Write the failing tests**

```python
def test_store_returns_a_reference_and_read_gets_the_value_back(home):
    run = fake_runner(home)
    ref = store("github", "GITHUB_TOKEN", "SENTINEL_SECRET_GH", run=run)
    assert ref == {"keychain": "github/GITHUB_TOKEN"}
    assert read(ref, run=run) == "SENTINEL_SECRET_GH"
    delete(ref, run=run); assert read(ref, run=run) is None


def test_resolve_entry_replaces_references_and_leaves_plain_values(home):
    run = fake_runner(home); store("github", "GITHUB_TOKEN", "SENTINEL_SECRET_GH", run=run)
    entry = {"command": "npx", "env": {"GITHUB_TOKEN": {"keychain": "github/GITHUB_TOKEN"}, "PLAIN": "x"}}
    assert resolve_entry(entry, run=run) == {"command": "npx", "env": {"GITHUB_TOKEN": "SENTINEL_SECRET_GH", "PLAIN": "x"}}
    assert resolve_entry({"command": "npx"}, run=run) == {"command": "npx"}


def test_a_failing_security_never_shows_the_value():
    def broken(args): return 1, "boom"
    with pytest.raises(KeychainError) as error: store("s", "k", "SENTINEL_SECRET_V", run=broken)
    assert "SENTINEL_SECRET_V" not in str(error.value) and "Kitden could not reach the Keychain." == str(error.value)
```

- [ ] **Step 3: Run them to see them fail**.
- [ ] **Step 4: Implement** the module and the fake.
- [ ] **Step 5: Run** `uv run pytest tests/unit/test_keychain.py tests/security -v` → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/local_gateway/keychain.py tests/unit/fake_security.py tests/unit/test_keychain.py
git commit -m "Gateway: a Keychain module over the security command"
```

---

### Task 2: The proxy resolves references (5.1)

**Files:**
- Modify: `src/kitden/local_gateway/proxy.py:285-311` (`Upstreams._target`: `entry = resolve_entry(entry)` first), `261-283` (`_serve`: a `KeychainError` becomes `UpstreamError` with its sentence, said once on stderr)
- Test: `tests/unit/test_local_gateway_proxy.py`

- [ ] **Step 1: Write the failing tests**

```python
async def test_a_plain_entry_runs_unchanged(home):
    # the existing echo server entry with env {"NOTE": "plain"}; the tool `where` reports env has NOTE=plain


async def test_a_reference_is_resolved_before_the_server_starts(home, monkeypatch):
    # install_fake_security(home); PATH set so the proxy's run_security finds it; store("echo", "NOTE", "SENTINEL_SECRET_N")
    # entry env {"NOTE": {"keychain": "echo/NOTE"}}; `where` reports NOTE present (the test checks the fake file, not the value in output)


async def test_a_missing_keychain_item_gives_a_plain_sentence(home, capsys):
    # reference to an item that does not exist → call_tool answers is_error with
    # "Kitden could not read a secret of echo from the Keychain." and stderr has the same line once
```

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** the proxy tests → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/local_gateway/proxy.py tests/unit/test_local_gateway_proxy.py
git commit -m "Gateway: resolve Keychain references at start"
```

---

### Task 3: The move puts secrets in the Keychain (5.1)

**Files:**
- Modify: `src/kitden/model.py:270-290` (`Step.secrets: dict[str, str] = field(default_factory=dict)`: Keychain account → value, memory only)
- Modify: `src/kitden/changes/actions.py:706-800` (`local_move_steps`: `secrets_out(name, server) -> tuple[dict, dict[str, str]]` turns each env or header value that `redact` hides into a reference and collects the values; the settings step gets the referenced entry and `step.secrets`), `src/kitden/changes/engine.py` (`_record` leaves `secrets` out and stores `command` masked with `redact`; `preview` refuses a step whose `undo_command` holds a secret; `apply`: before any file step, `keychain.store` for every `step.secrets` item, with a `KeychainError` taking the restore path; a previewed change loaded from a record whose `edit.after` holds references but has no `secrets` is refused at Apply with `"Review the change again."`; `undo`: `keychain.delete` for every reference in `edit.after` of a `kitden` step, after the files are restored), `src/kitden/views/after.py` (the line `"The token goes to your Keychain; the settings file keeps a reference."`)
- Modify: `src/kitden/web/app.py` (the `KeychainError` message becomes the 422 refusal of a preview)
- Test: `tests/unit/test_local_gateway_move.py`, `tests/unit/test_engine.py`, `tests/unit/test_after.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_a_move_writes_references_and_keeps_the_values_in_memory(home):
    steps = local_move_steps(adapters(home), [github_item], home, [], command, added_clients=set())
    kitden_step = next(s for s in steps if s.client == "kitden" and s.edit.key[0] == "servers")
    assert kitden_step.edit.after["env"] == {"GITHUB_TOKEN": {"keychain": "github/GITHUB_TOKEN"}}
    assert kitden_step.secrets == {"github/GITHUB_TOKEN": "SENTINEL_SECRET_GH"}


def test_apply_stores_the_items_and_undo_removes_them(home):
    # fake security; engine preview/apply: fake-keychain.json has github/GITHUB_TOKEN; gateway.json has the reference;
    # change.json has no SENTINEL and no "secrets" key; undo: item gone, client file back


def test_apply_after_a_restart_asks_for_a_new_review(home):
    # preview, then build a new Engine from the store (as after a restart), apply → state "previewed" unchanged, error "Review the change again.", nothing written


def test_a_failing_keychain_refuses_the_move_before_any_write(home):
    # fake security that exits 1 → engine.apply ends in "restored" with "Kitden could not reach the Keychain." and all files unchanged
```

`test_after.py`: the move note has the Keychain line when a step has `secrets`.

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** the three files and `tests/security` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/model.py src/kitden/changes src/kitden/views/after.py src/kitden/web/app.py tests/unit
git commit -m "Gateway: a move keeps secrets in the Keychain"
```

---

### Task 4: "Move secrets to the Keychain…" for a held server (5.1)

**Files:**
- Modify: `src/kitden/changes/actions.py` (`GATEWAY_KEYCHAIN = "gateway.keychain"`, `keychain_steps(home, server) -> list[Step]`: one settings step replacing the held entry with its referenced form, `secrets` set; raises `ValueError("<server> keeps no secret in the settings file.")` when nothing to move), `src/kitden/web/app.py` (dispatch), `src/kitden/views/after.py` (words: `"The secrets of <server> go to your Keychain; the settings file keeps references."`), `src/kitden/local_gateway/views.py:87-99` (`held_servers` rows gain `"plain_secrets": bool`), `src/kitden/web/static/js/gateway.js:317-327` (the button in Details when `plain_secrets`)
- Test: `tests/unit/test_local_gateway_views.py`, `tests/unit/test_api_changes.py`, `tests/unit/test_page_words.py`

- [ ] **Step 1: Write the failing tests**: `test_a_held_server_with_plain_secrets_says_so_and_can_move_them(home)`; API preview/apply/undo of `gateway.keychain`; words test for `"Move secrets to the Keychain…"`.
- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run the tests** → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/changes/actions.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/local_gateway/views.py src/kitden/web/static/js/gateway.js tests/unit
git commit -m "Gateway: move a held server's secrets to the Keychain"
```

---

### Task 5: Backups and records say when they hold a secret (5.2)

**Files:**
- Modify: `src/kitden/changes/backup.py:50-70` (`backup`: `entry["secret"] = redact_text(text) != text` per file; returns as today), `src/kitden/changes/engine.py` (`Change.holds_secret: bool` set at Apply from the manifest and from `redact(edit.before)[1]`; `_record` and `_from_record` carry it; `_log` too), `src/kitden/model.py` (`Change.holds_secret: bool = False`)
- Modify: `src/kitden/web/app.py` (`/api/changes` entries carry `holds_secret`), `src/kitden/web/static/js/changes.js:53-90` (the line `"The backup and record hold a secret"` on such a change)
- Modify: `README.md` (one line: backups are kept 30 days or the newest 100 changes)
- Test: `tests/unit/test_backup.py`, `tests/unit/test_engine.py`, `tests/unit/test_api_changes.py`, `tests/unit/test_page_words.py`, `tests/unit/test_docs_words.py`

- [ ] **Step 1: Write the failing tests**: `test_a_backup_of_a_file_with_a_secret_is_flagged_in_the_manifest`; `test_a_change_knows_when_its_backup_holds_a_secret`; `test_the_changes_api_says_holds_secret`; words tests.
- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run the tests** → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/changes src/kitden/model.py src/kitden/web README.md tests/unit
git commit -m "Changes: say when a backup holds a secret"
```

---

### Task 6: The OAuth spike (5.3)

**Files:**
- A throwaway branch `spike/oauth` or a folder in the scratchpad; nothing merged. Its result is a dated note appended to this plan under "Spike findings".

- [ ] **Step 1: Read the MCP authorization spec** at the current version under https://modelcontextprotocol.io/specification/ and the SDK's `mcp.client.auth.oauth2` (`OAuthClientProvider`, its `redirect_handler`, `callback_handler`, `TokenStorage`); write the spec version and the date in the note.
- [ ] **Step 2: Read GitHub's remote MCP docs** (https://github.com/github/github-mcp-server, the remote server section) for the server URL and its OAuth support; write the date.
- [ ] **Step 3: Run a throwaway script** that uses `OAuthClientProvider` against that URL with a `redirect_handler` that opens the browser and a `callback_handler` that waits on a one-shot `http.server` on `127.0.0.1:<free port>`; list the tools once; then force a refresh.
- [ ] **Step 4: Append "Spike findings" to this plan**: whether dynamic client registration worked or a client id must be registered; the exact redirect URI the server accepted; the token and refresh shapes the SDK stores (`OAuthToken` fields); whether refresh rotates the refresh token; how the SDK signals a failed refresh (which exception); the time a sign-in took. These values fix the open points of Tasks 7 and 8.
- [ ] **Step 5: Delete the throwaway** (branch or folder). No commit on `main` from this task except the note in the plan: `git commit -m "Plan: OAuth spike findings"`.

---

### Task 7: The page signs in at Apply (5.3)

**Files:**
- Create: `src/kitden/local_gateway/oauth.py` (`KeychainTokenStorage(ref: dict, run=...)` implementing the SDK's `TokenStorage` over one Keychain item `<server>/oauth` holding the tokens as JSON; `sign_in(server: str, url: str, open_browser: Callable[[str], None], timeout: float = 300) -> None` runs the SDK provider with a one-shot callback listener on `127.0.0.1` and stores the tokens; `provider_for(server, url, run=...) -> OAuthClientProvider` with handlers that raise `SignInNeeded`)
- Modify: `src/kitden/changes/actions.py:706-800` (`local_move_steps`: a server whose `needs_sign_in` is true is no longer refused; its gateway entry gets `"oauth": {"keychain": "<server>/oauth"}` and the step is marked `sign_in: str | None` with the server's url), `src/kitden/model.py` (`Step.sign_in: str | None = None`), `src/kitden/views/after.py` (the line `"Kitden will open your browser to sign in to <server>."`), `src/kitden/web/app.py` (the apply handler: before `engine.apply`, for each step with `sign_in`, `await oauth.sign_in(...)` with `webbrowser.open`; a failure cancels the change with `"Sign-in to <server> did not finish."` and writes nothing)
- Test: `tests/unit/test_oauth.py` (new; a fake authorization server in-process, as the SDK's own tests do), `tests/unit/test_local_gateway_move.py` (`test_an_oauth_server_is_refused_after_a_401` becomes `test_an_oauth_server_moves_with_a_sign_in_step`), `tests/unit/test_api_changes.py`

- [ ] **Step 1: Write the failing tests** (values from the spike findings): the storage round trip through the fake `security`; `sign_in` against a fake authorization server completes and stores tokens; the move step carries `sign_in` and the review line; the API apply calls the injected `sign_in` before writing.
- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_oauth.py tests/unit/test_local_gateway_move.py tests/unit/test_api_changes.py tests/security -v` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/local_gateway/oauth.py src/kitden/changes/actions.py src/kitden/model.py src/kitden/views/after.py src/kitden/web/app.py tests/unit
git commit -m "Gateway: sign in once on the page, then move an OAuth server in"
```

---

### Task 8: The gateway only refreshes (5.3)

**Files:**
- Modify: `src/kitden/local_gateway/proxy.py:285-311` (`_target`: with `entry["oauth"]`, the `httpx2.AsyncClient(auth=provider_for(...))`), `212-247` (`call`: `SignInNeeded` → `_error(f"Sign in to {server} again on the Kitden page.")`)
- Modify: `src/kitden/local_gateway/oauth.py` (`KeychainTokenStorage.set_tokens` under `fcntl.flock` on `<data folder>/oauth.lock`; `get_tokens` re-reads the item after taking the lock, so a refresh another process just did is used)
- Test: `tests/unit/test_local_gateway_proxy.py`, `tests/unit/test_oauth.py`

- [ ] **Step 1: Write the failing tests**: `test_an_oauth_server_runs_with_the_stored_token` (fake server that requires a bearer token the fake storage holds); `test_a_failed_refresh_says_to_sign_in_on_the_page` (the fake authorization server refuses the refresh → error result with the exact sentence; nothing opened); `test_two_refreshes_take_turns` (two storages on one item: the second `set_tokens` waits for the lock and the final item is the later one; `get_tokens` after the lock sees the first's write).
- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run the tests** → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/local_gateway/proxy.py src/kitden/local_gateway/oauth.py tests/unit
git commit -m "Gateway: refresh OAuth tokens under a lock, never open a browser"
```

---

### Task 9: Docs, hand check and roadmap for Part 5

**Files:**
- Modify: `README.md` (Gateway section: the Keychain; OAuth servers can move; the two lines the reviews show), `docs/development.md` ("Gateways": `gateway.json` keeps references, the Keychain items `kitden` / `<server>/<key>` and `<server>/oauth`, `oauth.lock`; hand check: a Keychain item appears after a move, sign in once, the server moves in, its tools work in a new session, a refresh after expiry works, Undo removes the items), `ROADMAP.md` (Part 5 from "## Planned" to "### Not released yet")

- [ ] **Step 1: Write the docs**.
- [ ] **Step 2: Do the hand check** once in each client on a throwaway project with the GitHub remote server; note the date.
- [ ] **Step 3: Run all checks**: `uv run pytest -q && uv run ruff check . && node --test tests/frontend/*.test.mjs`
- [ ] **Step 4: Commit**

```bash
git add README.md docs/development.md ROADMAP.md
git commit -m "Docs: Part 5 of the review follow-up"
```
