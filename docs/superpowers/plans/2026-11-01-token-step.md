# Token Step (Part 3a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A server that needs access joins the preview as "waiting" (amber, "Needs token" or
"Needs sign-in"). Its token is checked against the server before Apply. Apply writes the ready
changes and leaves the waiting ones in the tray.

**Architecture:**
- The server side works out what a server needs and raises one typed refusal, `NeedsAccess`.
  The batch preview answers it with a `needs` object in place of a plain refusal.
- The tray keeps such a row as waiting, outside the batch. Giving a token re-asks the batch
  preview with that row in it. That ask is the check, so no new endpoint is needed.
- One shared access form serves the catalog details, the map and the dock.

**Tech Stack:** Python 3 / Starlette (`src/kitden`), vanilla JS modules
(`src/kitden/web/static/js`), pytest, `node --test` with the fake DOM in `tests/frontend`.

**Spec:** docs/superpowers/specs/2026-11-01-add-select-sign-in-design.md (Part 3, the
"Token" and "needs access" sections, the signal table, the motion table, and settled calls 1–4
and 7).

## Global Constraints

- **Language.** UI text is plain English. The owner reads Russian; the code and docs stay in
  English.
- **Change flow.**
  - Every client or gateway write goes through preview → Apply with a backup → verify → Undo.
  - A secret goes only to macOS Keychain, through the existing `_server_step` / `KeychainItem`
    path.
  - A secret is never echoed in an answer, a log or a change record.
- **Tests.** Tests use sandbox homes, the fake Keychain and local fake HTTP servers
  (`FakeRemote` in tests/unit/test_local_gateway_move.py). Never a real account or token.
- **What the owner never does.** The owner never picks the access kind and never types a header
  name.
- **Exact words.**
  - Status: "Needs token" and "Needs sign-in".
  - Buttons: "Add token" and "Checking…".
  - Results: "Token works".
  - Refusal: "{name} did not accept this token."
  - Sign-in Kitden cannot do yet: "{name} does not let Kitden sign in yet. It may take an API
    key; see its docs."
  - Local values: "Checked when the gateway starts it".
- **Colors.**
  - Needs you and refused: `--lamp-warn` (amber).
  - Works: the green lamp `--lamp-on`.
  - Red only for the page-level "Kitden itself broke" banner.
- **Motion.** Only the Calm rules, with no new tokens:
  - lamp color fade: 400 ms;
  - button fade in: 200 ms;
  - busy ring after 150 ms (`busyWhile`);
  - check draw: 320 ms;
  - refused words rise 4 px in 200 ms;
  - one `shake()` of the field row.
- **Reduced motion.** Everything lands at once and there is no shake.
- **Before each commit.** Run `uv run pytest -q`, `uv run ruff check .` and
  `node --test tests/frontend/*.test.mjs`.
- **Commit messages.** A short plain subject plus 1–3 lines, ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Docs.** Update docs/design.md and ROADMAP.md in the last task.

## Rulings in this plan (the owner can overturn them)

1. **The field opens in the side panel, not inline under the map card.**
   - Map cards are laid out with fixed heights and redrawn on every tray change, so an input
     inside a card would lose its value and focus.
   - "Add token" (the press on a waiting block, or the dock row's button) therefore opens the
     panel beside the map, focused on the field.
   - The catalog keeps its fields in the row's details, as the spec allows.
   - Cost if wrong: one more task to move the form under the card.
2. **On the map the waiting block itself is the button.**
   - A press opens the access panel, and the tip says "Needs a token. Click to add it."
   - Taking a waiting row out is done from the dock row's ×.
3. **Apply keeps its short label.**
   - The button reads "Apply 2". The waiting part goes in the bar's line: "neon waits for a
     token. It stays in preview." With two or more waiting: "2 wait for access."
   - The spec put both in the button, but the bar is narrow.
4. **Every sign-in server gets settled call 4 for now.**
   - Browser sign-in is Part 3b. Until then a server that offers sign-in shows "Needs sign-in"
     with the settled-call-4 reason and a token field. 3b swaps the field for **Sign in**.
5. **An unreachable server is still a refusal, not a waiting row.**
   - The words stay "Kitden could not reach {name}."
   - Kitden cannot know what such a server needs.

## Review Focus

1. **A pasted "Bearer abc" or " abc\n".** One "Bearer " prefix is kept and whitespace is
   trimmed. A newline inside the value is refused with the form's words, not a 500. (Task 4
   test `strips a pasted Bearer and trims`.)
2. **A token in any answer or record.** The 422 `needs` answer, the change record and the log
   never hold the typed value. (Task 1 test `test_needs_answer_holds_no_secret`.)
3. **Apply pressed while a check is out.** The tray is "asking", so Apply waits. A late answer
   for an older ask is dropped. (Task 2 test `apply waits while a token is checked`.)
4. **Undo of a partial Apply.** The waiting rows stay in the tray, and Undo removes only what
   was applied, including its Keychain item. (Task 2 test `a partial apply keeps the waiting
   rows`; Task 1 test `test_undo_removes_the_keychain_item_of_a_checked_token`.)
5. **A group drop where some servers need access.** The ready ones join as previews, the others
   as waiting, and no server is left behind. (Task 5 test `a group drop keeps the servers that
   need access as waiting rows`.)

---

### Task 1: The server says what access a server needs

**Files:**
- Modify: `src/kitden/changes/actions.py`:
  - replace `needs_sign_in` (≈513) with `access_needed`;
  - add `NeedsAccess` and `TOKEN_FIELD`;
  - change `OAUTH_MOVE`, `local_move_steps` (≈760–820) and `gateway_add_steps` (≈930–980).
- Modify: `src/kitden/discovery.py`, `configured_entry` (≈212): a missing required value raises
  `NeedsAccess`.
- Modify: `src/kitden/web/app.py`:
  - `_RowRefused` (≈275) carries `needs`;
  - `_batch` (≈1395) catches `NeedsAccess`;
  - `batch_preview` and `batch_check` answer `needs`;
  - the `GATEWAY_MOVE` branch passes `params.get("headers")`.
- Modify: `src/kitden/demo/__init__.py`: `no_sign_in` returns `"open"`.
- Test: `tests/unit/test_local_gateway_move.py`, `tests/unit/test_market_servers.py`,
  `tests/unit/test_discovery.py`, `tests/unit/test_api_changes.py` (or the file that already
  tests `/api/batch/preview`; find it with `grep -ln batch/preview tests/unit`).

**Interfaces:**
- **Produces `access_needed(url: str, headers: dict) -> str`.**
  - It returns `"open"`, `"token"` or `"sign-in"`.
  - It does the same POST as today's `needs_sign_in`: no redirect, no proxy, 5 s, user agent
    `kitden`.
  - 401/403 means access is needed. It is `"sign-in"` when the answer's `WWW-Authenticate`
    holds `resource_metadata`, or when a GET of `<origin>/.well-known/oauth-protected-resource`
    returns 200 (same opener). Otherwise it is `"token"`.
  - OSError is raised as today.
  - Write `(MCP authorization spec 2025-06-18, checked 2026-11-01)` next to the
    `resource_metadata` rule.
- **Produces `class NeedsAccess(ValueError)`.**
  - It is built as `NeedsAccess(server: str, kind: str, fields: list[dict], refused: bool = False)`.
  - `str(error)` gives the reason:
    - refused: `"{server} did not accept this token."`;
    - `kind == "sign-in"`: the settled-call-4 words;
    - otherwise: `"{server} needs a token."`.
  - `.answer() -> dict` gives `{"server", "kind", "fields", "reason", "refused"}`.
- **Produces `TOKEN_FIELD`:**
  `{"field": "headers", "name": "Authorization", "label": "Access token", "prefix": "Bearer "}`.
- **Field dicts** keep today's shape from `server_setup`: `field`, `name`, `label`, `prefix`,
  and an optional `optional`. Env fields gain `"later": True`.
- **The `sign_in` parameters** of `local_move_steps` and `gateway_add_steps` now have type
  `Callable[[str, dict], str]`.
- **`local_move_steps` gains `headers: dict | None = None`.**
  - Those headers are merged into the remote server's entry before the check, for a single
    server only.
  - Any name other than `Authorization` raises `ValueError("Only the server's declared access fields can be set.")`.
- **The batch preview's 422 body** is `{"detail", "row", "needs"}`, where `needs` is the
  `.answer()` dict or `null`.
- **The `batch_check` refusal** is `{"ok": False, "reason", "row", "needs"}`.

- [ ] **Step 1: Write the failing tests**

```python
# test_local_gateway_move.py — FakeRemote(401) already sends WWW-Authenticate resource_metadata
def test_access_needed_tells_sign_in_token_and_open(home):
    signs, plain, open_ = FakeRemote(401), FakeRemote(403), FakeRemote(200)
    try:
        assert access_needed(signs.url, {}) == "sign-in"
        assert access_needed(plain.url, {}) == "token"   # 403, no metadata
        assert access_needed(open_.url, {}) == "open"
    finally:
        stop(signs, plain, open_)

def test_a_sign_in_server_moves_as_a_waiting_row(home):
    remote = FakeRemote(401)
    add_claude(home, "neon", {"type": "http", "url": remote.url})
    with pytest.raises(NeedsAccess) as error:
        move(home, ("claude_code", "neon"))
    assert error.value.answer() == {"server": "neon", "kind": "sign-in", "fields": [TOKEN_FIELD],
        "reason": "neon does not let Kitden sign in yet. It may take an API key; see its docs.",
        "refused": False}

def test_a_refused_token_on_a_move_says_so(home):
    remote = FakeRemote(401)
    add_claude(home, "neon", {"type": "http", "url": remote.url})
    with pytest.raises(NeedsAccess) as error:
        move(home, ("claude_code", "neon"), headers={"Authorization": "Bearer bad"})
    assert error.value.refused and str(error.value) == "neon did not accept this token."

def test_a_move_takes_only_an_authorization_header(home): ...  # "X-Key" -> ValueError words above

def test_a_working_token_moves_into_keychain_not_the_settings(home): ...
    # FakeRemote(200); move with headers -> the settings step holds the Keychain ref, step.keychain has the value
```

```python
# test_discovery.py
def test_a_missing_required_value_waits_for_a_token():
    row = {"name": "io.github.x/neon", "entry": {"url": "https://x"}, "setup": [
        {"field": "headers", "name": "Authorization", "label": "Neon API key", "prefix": "Bearer "}]}
    with pytest.raises(NeedsAccess) as error:
        configured_entry(row, {})
    assert error.value.kind == "token" and error.value.fields == row["setup"]
```

```python
# the batch preview API test file
def test_needs_answer_holds_no_secret(client, ...):
    # a gateway.move row of a 401 server with headers {"Authorization": "Bearer SENTINEL_SECRET_X"}
    # -> 422, body["needs"]["refused"] is True, "SENTINEL_SECRET_X" not in response.text
def test_batch_preview_answers_needs_for_the_row(client, ...):
    # 422, body["row"] == that request's id, body["needs"]["kind"] in ("token", "sign-in")
def test_undo_removes_the_keychain_item_of_a_checked_token(...):
    # move with a working token, apply, undo -> fake Keychain no longer holds "<server>/Authorization"
```

Update the existing tests that expect `OAUTH_MOVE` or the "needs access … not supported yet"
words (`test_an_oauth_server_is_refused_after_a_401`,
`test_an_oauth_server_is_refused_at_preview_and_nothing_is_written`) to expect `NeedsAccess`
with the new words. Rename them to say "waits".

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest -q tests/unit/test_local_gateway_move.py tests/unit/test_market_servers.py tests/unit/test_discovery.py -k "access or waits or token or keychain"`
Expected: FAIL. `access_needed`, `NeedsAccess` and `TOKEN_FIELD` cannot be imported.

- [ ] **Step 3: Implement**

The changes are as the Interfaces block says. Where `gateway_add_steps` gets an access answer,
it raises one of three things:

| What happened | What it raises |
|---|---|
| The entry has no headers | `NeedsAccess(name, kind, fields=<the discovery row's setup or [TOKEN_FIELD]>)` |
| The entry has headers and the server still answers 401/403 | the same `NeedsAccess`, with `refused=True` |
| The server cannot be reached | `ValueError("Kitden could not reach {name}.")`, as today |

- `gateway_add_steps` does not see the discovery row's setup. Pass it in with a new keyword,
  `fields: list[dict] | None = None`.
- In app.py, catch `NeedsAccess` before the generic `ValueError` in `_batch`. Its words go
  through `refusal_words` as today.
- Delete `OAUTH_MOVE` and its import sites.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add -A src/kitden tests/unit
git commit -m "Say what access a server needs instead of refusing it

A 401 server becomes a waiting row with its token field; a bad token says so.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: The tray keeps waiting rows and checks a token

**Files:**
- Modify: `src/kitden/web/static/js/tray.js`
- Test: `tests/frontend/tray.test.mjs`

**Interfaces:**
- **Consumes:** the 422 `needs` body from Task 1.
- **Produces, row field:** `row.waits` is null or
  `{ server, kind, fields, reason, refused, checking }`.
- **Produces, row flag:** `row.works === true` after a token checked well, until the next Apply
  or a take-out.
- **Produces, phase:** `tray.phase` gains `"waiting"`: every row waits and there is no change.
- **Produces `readyRows(t = tray)`:** the rows without `waits`.
- **Produces `waitingRows(t = tray)`:** the rows with `waits`.
- **Produces `async giveAccess(key, values)`.**
  - `values` is `{ headers?, env? }` and the call returns true when the token works.
  - It puts the values in the row's `body.params.headers` / `body.params.env`, the same for
    `gateway.add` and `gateway.move`. It sets `waits.checking = true` and notifies.
  - It then asks the batch preview with the ready rows plus this one.
  - **A change comes back:** accept it, `waits = null`, `works = true`.
  - **`needs` for this row comes back:** put the body back as it was, set
    `waits = { ...needs, checking: false }`, and leave the change and phase as they were.
  - **Any other refusal:** `waits.reason` = the reason, `refused: true`.
- **Changed `addToTray`.** A `needs` answer for the new row makes it join as waiting, and the
  call returns true. The tray's change still covers the ready rows; if there are none, the
  phase is `"waiting"`.
- **Changed `previewRows`, `ask` and `repreview`.** They send `readyRows()` only, plus the row
  being checked. With no ready rows and none checked, nothing is asked: the change is
  cancelled and the phase becomes `"waiting"` (or `"idle"` with no rows at all).
- **Changed `takeOut`.** Taking out a waiting row asks nothing new.
- **Changed `applyTray`.** It runs on a ready tray with at least one ready row.
- **Changed `endApplied`.** It keeps the waiting rows: phase `"waiting"`, or `"idle"` when
  there are none.

- [ ] **Step 1: Write the failing tests** (in the file's style, with its fetch stub)

```js
test('a needs answer makes the row join as waiting', async () => {
  // stub /api/batch/preview → 422 { detail: 'neon needs a token.', row: <id>, needs: { server: 'neon', kind: 'token', fields: [F], reason: 'neon needs a token.', refused: false } }
  assert.equal(await addToTray(MOVE_NEON), true);
  assert.equal(tray.phase, 'waiting');
  assert.equal(tray.rows[0].waits.kind, 'token');
  assert.equal(tray.refused, null);
});
test('a waiting row is not sent with the ready rows', async () => { /* second add: the request holds only the ready row */ });
test('a working token makes the row ready and marks it works', async () => { /* giveAccess → change; waits null; works true; params.headers sent */ });
test('a refused token keeps the row waiting with the reason and the old change', async () => { /* change id unchanged; waits.refused; body has no headers */ });
test('apply waits while a token is checked', async () => { /* during giveAccess, applyTray() does nothing */ });
test('a partial apply keeps the waiting rows', async () => { /* apply verified → endApplied → rows = [waiting], phase 'waiting' */ });
test('taking out a waiting row asks nothing', async () => { /* no fetch to batch/preview */ });
```

- [ ] **Step 2: Run to see them fail**

Run: `node --test tests/frontend/tray.test.mjs`
Expected: the new tests FAIL. The first fails because `tray.phase` is `"ready"`/`"idle"`, and
`giveAccess` is not exported.

- [ ] **Step 3: Implement** as the Interfaces block says.
  - `previewRows` returns `{ needs, row }` beside `{ reason }`.
  - The words of a waiting row: `title` = `waits.server`, `detail` = `waits.reason`.
    `wordsFor` is not called for it, because it has no part.

- [ ] **Step 4: Run** `node --test tests/frontend/*.test.mjs`. Expected: all pass. Fix any
  old test that assumed a needs answer refused the add.

- [ ] **Step 5: Commit**: "Keep servers that need access waiting in the tray".

### Task 3: One access form, and the panel that opens it

**Files:**
- Create: `src/kitden/web/static/js/access-form.js`
- Modify: `src/kitden/web/static/style.css`: `.access-form`, `.access-why`, `.lamp` color
  transition 400 ms, `.access-check` (an SVG stroke draw)
- Test: `tests/frontend/access-form.test.mjs` (new)

**Interfaces:**
- **Consumes:** `giveAccess` and `tray` from Task 2; `openPanel`, `header` and `restoreFocus`
  from panel.js; `busyWhile` and `button` from dom.js; `shake`, `animateTo` and `D` from
  motion.js.
- **Produces `accessForm(waits, onCheck)`.** It returns
  `{ node, values(), focus(), checking(promise), works(), refuse(reason) }`.
  - **The fields.**
    - Required fields show open. Optional ones fold under `<details><summary>More values</summary>`.
    - Each field is a `password` input labelled with `field.label`.
    - Under one `<details>` per form, "Details", it lists "Sent as the {name} header" or "Set
      as {name}".
    - An env field with `later` adds the note "Checked when the gateway starts it".
    - The note "Saved in macOS Keychain on Apply." is kept.
  - **`values()`** returns `{ headers?, env? }`, or null while a required field is empty.
    - A field with `prefix` drops a pasted `/^bearer\s+/i` and adds the prefix once.
    - Every value is trimmed.
  - **The submit button** says "Add token" and calls `onCheck(values())`.
  - **`checking(promise)`** wraps the button in `busyWhile`. The label "Checking…" shows with
    the ring.
  - **`works()`** shows `.lamp.on` plus "Token works", with a check drawn in 320 ms (`D(320)`).
  - **`refuse(reason)`.**
    - It shows `p.access-why[role=alert]` with the amber `alert-triangle` icon and the reason.
      The words rise 4 px in 200 ms.
    - It focuses the first field and calls `shake()` on the field row.
    - With reduced motion there is no shake and no rise.
- **Produces `openAccess(row)`.**
  - It opens the panel with `header(kicker, row.waits.server, row.waits.reason)`. The kicker
    is "Needs token" or "Needs sign-in".
  - The panel holds `accessForm(row.waits, (v) => giveAccess(row.key, v))`.
  - When `giveAccess` resolves true: `works()`, then the panel closes after 600 ms and focus
    goes back.
  - When it resolves false: `refuse(row.waits.reason)`.
  - Focus starts in the first field.

- [ ] **Step 1: Write the failing tests**

```js
test('one Authorization field: only the token is asked', () => { /* one input, label 'Access token', no text 'Authorization' outside the Details fold */ });
test('strips a pasted Bearer and trims', () => { /* input ' Bearer abc \n' → values().headers.Authorization === 'Bearer abc' */ });
test('optional values fold under More values', () => {});
test('a required empty field gives no values', () => {});
test('refuse shows amber words as an alert and focuses the field', () => { /* .access-why role=alert, text = reason, document.activeElement = first input */ });
test('works shows Token works with the green lamp', () => {});
test('a local value says it is checked when the gateway starts it', () => {});
```

- [ ] **Step 2: Run** `node --test tests/frontend/access-form.test.mjs`. Expected: FAIL, the
  module is missing.
- [ ] **Step 3: Implement** as the Interfaces block says. Colors come only from `--lamp-warn`
  and `--lamp-on`.
- [ ] **Step 4: Run all three checks.** Expected: all pass.
- [ ] **Step 5: Commit**: "Add one access form for tokens and env values".

### Task 4: The catalog uses the form and its rows can wait

**Files:**
- Modify: `src/kitden/web/static/js/discovery.js` (`draw`'s `paint` ≈125–140; the mcp branch
  of `itemDetails` ≈300–365)
- Modify: `src/kitden/web/static/style.css`: `.res .st.warn` in amber
- Test: `tests/frontend/gateway-add.test.mjs`

**Interfaces:**
- **Consumes:** `accessForm` from Task 3. From Task 2: `addToTray` (a needs answer joins),
  `inTray`, `keyFor`, `tray`.
- **Produces, row status words.** A row that needs access and has no working values says
  "Needs token", with status class `st warn`. The catalog does not probe servers, so
  "Needs sign-in" shows only once a drop's answer says so: the map and the dock show it then.
- **Produces, drag.** The row drags whether or not it has values. A drop with no values joins
  the tray as waiting.
- **Produces, details.**
  - The mcp branch replaces its hand-built inputs with `accessForm`.
  - The fields come from `row.setup` plus the remote's optional `TOKEN_FIELD` (today's
    `definitions`).
  - Preview sends `installBody({ ...row, access: values() }, [])`.
  - **The row joined and does not wait:** `works()`, then `options.added`.
  - **The row joined as waiting with `refused`:** `refuse(waits.reason)`.
  - **The row joined waiting with no values:** `options.added` as today.
  - **Any other refusal:** `refuse(tray.refused.reason)`.
  - The "Token refused" status goes away; a refused row still says "Needs token", and its
    reason shows in the details.
- **Produces, hint.** The hint follows the one pattern: `"Click to review · drag onto the gateway"`
  (no final period), and the same for clients.

- [ ] **Step 1: Write the failing tests**
  - `a row that needs a token says so in amber and still drags`
  - `a refused token shows its reason under the field`, with the stub answering 422 `needs`
    and `refused: true`
  - `a working token closes nothing and marks the row added`
  - `the catalog hint has no final period`
- [ ] **Step 2: Run** `node --test tests/frontend/gateway-add.test.mjs`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run all three checks.** `tests/unit/test_page_words.py` may hold the old hint
  and "Token refused" strings; update them. Expected: all pass.
- [ ] **Step 5: Commit**: "Let catalog servers that need a token wait in preview".

### Task 5: Waiting servers on the map and in the dock

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js`:
  - `rowsOnMap` (≈193);
  - the preview blocks for `gateway.add` and moves (≈511–560);
  - `pressBlock` (≈1274–1295).
- Modify: `src/kitden/web/static/js/gateway-drag.js`: `dropIn`, `dropAdd`, `dropGroup` and
  `addInTurn`. A joined waiting row counts as joined; there is no fly-back.
- Modify: `src/kitden/web/static/js/dock.js`: `barWords` (≈62), the row drawing (≈245) and the
  refused status color (≈316).
- Modify: `src/kitden/web/static/style.css`:
  - `div.map .block.needs`: amber lamp, dashed accent edge kept, because it is still a preview;
  - the dock's `.bad` turns amber.
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/gateway-page.test.mjs`,
  `tests/frontend/dock.test.mjs`

**Interfaces:**
- **Consumes:** from Task 2, `row.waits`, `row.works`, `readyRows` and `waitingRows`; from
  Task 3, `openAccess(row)`.
- **Produces, `rowsOnMap(t)`.** It includes rows with `waits`, in any phase but `"applied"`.
- **Produces, the waiting block.**
  - It sits where the row's preview would be: `preview:<name>`, kind `"preview"`, plus
    `needs: true`.
  - Its fields: `lamp: "warn"`, `meta: "Needs token"` or `"Needs sign-in"`, `state: "needs"`,
    `takeOut: null`, and the tip `"Needs a token. Click to add it."` (or "…to sign in" words for
    `sign-in`: `"Needs sign-in. Click for a token instead."`).
  - A row with `works` draws its normal preview with `lamp: "on"` and meta "Token works".
- **Produces, `pressBlock` on a waiting block:** `openAccess(row)`.
- **Produces, `barWords`.**
  - With waiting rows and n ready rows: `apply = n ? (n > 1 ? \`Apply ${n}\` : "Apply") : null`.
  - The line is `"{server} waits for a token. It stays in preview."`, or `"… waits for sign-in. …"`,
    or `"{k} wait for access."` when k > 1.
  - When the ready count changes, the count in the Apply button rolls with `rollTo`
    (motion.js), the spec's "the number in the button rolls".
  - In phase `"waiting"` the head is `"{server} needs access"` or `"{k} servers need access"`,
    and Cancel stays.
- **Produces, the dock row of a waiting row:** an amber lamp, "Needs token" or "Needs sign-in",
  and an "Add token" button that calls `openAccess(row)`. The 200 ms fade comes in with the row.

- [ ] **Step 1: Write the failing tests**
  - `a waiting move draws an amber Needs token block where its preview goes` (gateway.test)
  - `a press on a waiting block opens the access panel` (gateway-page)
  - `a group drop keeps the servers that need access as waiting rows` (gateway-page)
    - The stub answers `needs` for one of the two, and both rows end in the tray, one with
      `waits`.
  - `the bar says who waits and Apply counts only ready rows` (dock)
  - `a waiting dock row offers Add token` (dock)
  - `a refused line in the dock is amber, not the accent` (dock, a class check)
- [ ] **Step 2: Run the three files.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run all three checks.** Expected: all pass.
- [ ] **Step 5: Check it by hand in the sandbox.**
  - Start the preview on a fixture home (memory: preview-on-fixture-home), with the local
    `fake_mcp.py` answering 401 to a missing or wrong token and 200 to the right one.
  - Drag the OAuth servers onto the gateway: amber waiting blocks appear.
  - Add a wrong token: the reason shows, the field shakes and gets focus.
  - Add the right one: "Token works", then Apply. The ready ones apply and the waiting one
    stays.
  - Never use a real token.
- [ ] **Step 6: Commit**: "Show servers that wait for a token on the map and in the dock".

### Task 6: One look for refused, and the docs

**Files:**
- Modify: `src/kitden/web/static/style.css`: the `.why` under add forms and the dock refusal
  use `--lamp-warn` with the `alert-triangle` icon. Today's accent or red goes, except the
  page banner.
- Modify: `src/kitden/web/static/js/add-panel.js` and the Library panel foot hint: the one
  hint pattern, with no final period.
- Modify: `docs/design.md`:
  - signal table rows for Needs token, Token works and Refused;
  - motion rows from the spec's table for Needs access, Waiting, Works and Refused;
  - the "Add token" panel pattern and Rulings 1–3 above.
- Modify: `ROADMAP.md`: Part 3a done (2026-11-01); 3b next.
- Test: `tests/unit/test_page_words.py`, and the "div.map rules"/style tests in
  `tests/frontend`.

- [ ] **Step 1: Write the failing tests.**
  - A style test: no `.why` rule uses `--accent` or a red token.
  - A words test: every map, catalog and Library hint matches `/^[^.]+$/` (no final period).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement and update the docs.**
- [ ] **Step 4: Run all three checks.** Expected: all pass.
- [ ] **Step 5: Commit**: "Use one amber look for refusals; describe the token step". Push the
  work branch with `git -c http.postBuffer=524288000 push`.
